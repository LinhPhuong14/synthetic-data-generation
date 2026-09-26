"""Trang demo: bấm nút, thấy một tờ chứng từ vừa sinh kèm nhãn phủ lên ảnh.

    python tasks.py demo              # rồi mở http://127.0.0.1:8765
    generators/html/.venv/bin/python tools/demo/server.py --port 8765

Chạy bằng interpreter của renderer html vì nó vẽ TRONG tiến trình: giữ một
Chromium sống suốt phiên thay vì gọi `render.py` mỗi lần bấm. Đo trên máy này:
gọi `render.py -c 1` mất 12 s một tờ, gần hết là khởi động interpreter và
Chromium; giữ trình duyệt ấm thì tờ sau chỉ còn phần vẽ.

Vẽ bằng đúng `HtmlReceiptRenderer.render` + `_emit_page` của `render.py`, nên
ảnh và bản ghi là thứ một lượt `make dataset` sẽ ra với cùng seed và cùng ghim
-- trang này không có đường vẽ riêng để lệch khỏi đường thật.

Chỉ nhánh luật. Nhánh LLM cần model chạy ngoài sandbox; muốn xem trang model
viết thì vẽ lại từ `html/` + `declared/` bằng `synthgen/draw_llm.py`.

Mỗi lần sinh ghi vào thư mục mới `data/demo/<giờ>-s<seed>/`: ảnh, bản ghi
json, `synthesis.json`, markup trước khi chụp, và `demo.json` (ghim + thời gian)
để danh sách lịch sử đọc lại được.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import random
import shutil
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS_ROOT = REPO_ROOT / "data" / "demo"
for _extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

import render as html_render  # noqa: E402
import sheets  # noqa: E402

import rulebase  # noqa: E402
from pipeline import record, synthesis  # noqa: E402

# Thứ tự bốc (`rulebase/rules/_order.yaml`), đọc từ luật chứ không chép tay:
# thêm một thuộc tính là nó hiện thêm một ô chọn.
ATTRIBUTES = list(rulebase.ATTRIBUTES)
PRISTINE = "pristine"
MAX_BODY = 64 * 1024


class DemoError(ValueError):
    """Yêu cầu sai -- trả 400 kèm lời, không vẽ bừa theo mặc định."""


# ----------------------------------------------------------------- luật


def options() -> dict:
    """Mọi giá trị ghim được của từng thuộc tính, và bố cục nào đi với loại
    giấy nào.

    Bố cục lọc theo tag mà `document` gắn (`Option.allowed`), cùng phép
    sampler dùng -- nên ô bố cục chỉ đưa ra thứ bốc được thật, không phải bảng
    ghép tay sẽ thiếu loại giấy mới.
    """
    rules = rulebase.load_rules()
    attributes = {}
    for attribute in ATTRIBUTES:
        attributes[attribute] = [
            {"id": option.id, "enabled": option.enabled,
             "weight": option.weight, "group": option.group,
             "title": _title(option)}
            for option in rules[attribute]
        ]
    layouts_by_document = {
        document.id: [layout.id for layout in rules["layout"]
                      if layout.allowed(document.tags)]
        for document in rules["document"]
    }
    return {"attributes": attributes, "layouts_by_document": layouts_by_document}


def _title(option) -> str:
    """Tên in trên giấy nếu luật có (`params.titles`), để người xem đọc
    "HOÁ ĐƠN GTGT" thay vì `vat_invoice_form`. Chỉ là chỗ đỡ: thiếu thì trống."""
    titles = (option.params or {}).get("titles")
    if isinstance(titles, list) and titles and isinstance(titles[0], str):
        return titles[0]
    return ""


def parse_request(body: dict) -> tuple[int, dict[str, str], bool]:
    """`{seed, force: {attr: id}, compare}` -> đã kiểm. Khoá lạ thì từ chối."""
    unknown = set(body) - {"seed", "force", "compare"}
    if unknown:
        raise DemoError(f"khoá lạ {sorted(unknown)}; nhận seed, force, compare")
    seed = body.get("seed")
    if seed in (None, ""):
        seed = random.randrange(1_000_000)
    try:
        seed = int(seed)
    except (TypeError, ValueError) as error:
        raise DemoError(f"seed phải là số nguyên, nhận {seed!r}") from error
    force = body.get("force") or {}
    if not isinstance(force, dict):
        raise DemoError("force là {thuộc tính: giá trị}")
    rules = rulebase.load_rules()
    clean: dict[str, str] = {}
    for attribute, value in force.items():
        if value in (None, ""):
            continue
        if attribute not in rules:
            raise DemoError(f"thuộc tính lạ {attribute!r}; có {', '.join(ATTRIBUTES)}")
        known = {option.id for option in rules[attribute]}
        if value not in known:
            raise DemoError(f"{attribute}={value!r} không có trong rulebase/rules/")
        clean[attribute] = str(value)
    return seed, clean, bool(body.get("compare"))


# ------------------------------------------------------------- vẽ


class Studio:
    """Một Chromium, một luồng.

    Playwright sync gắn với luồng đã mở nó, nên mọi lần vẽ đi qua đúng một
    luồng thợ -- `ThreadPoolExecutor(max_workers=1)` giữ nguyên luồng đó suốt
    đời. Yêu cầu tới cùng lúc thì xếp hàng, không tranh trình duyệt.
    """

    def __init__(self, scale: float) -> None:
        self.scale = scale
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chromium")
        self._renderer = None

    def generate(self, seed: int, force: dict[str, str], compare: bool) -> dict:
        return self._pool.submit(self._generate, seed, force, compare).result()

    def close(self) -> None:
        def _close():
            if self._renderer is not None:
                self._renderer.__exit__(None, None, None)
        self._pool.submit(_close).result()
        self._pool.shutdown()

    def _ensure(self):
        if self._renderer is None:
            renderer = html_render.HtmlReceiptRenderer(
                scale=self.scale, template=sheets.resolve("auto"))
            renderer.__enter__()
            self._renderer = renderer
        return self._renderer

    def _generate(self, seed: int, force: dict[str, str], compare: bool) -> dict:
        started = time.monotonic()
        renderer = self._ensure()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = RUNS_ROOT / f"{stamp}-s{seed}"
        suffix = 1
        while out.exists():
            suffix += 1
            out = RUNS_ROOT / f"{stamp}-s{seed}-{suffix}"
        out.mkdir(parents=True)

        # Bản sạch vẽ cùng seed, chỉ ghim thêm `augmentation=pristine`. Làm cũ
        # đứng cuối thứ tự bốc, nên ghim nó không đổi thuộc tính nào trước nó:
        # cùng tờ, cùng chữ -- khác nhau đúng phần làm cũ.
        variants = [("aged", "anh.jpg", force)]
        if compare and force.get("augmentation") != PRISTINE:
            variants.append(("clean", "anh_sach.jpg", {**force, "augmentation": PRISTINE}))

        args = SimpleNamespace(out=out, template=renderer.template, save_html=True)
        drawn_variants = []
        try:
            with synthesis.Writer(synthesis.beside(out), "html") as notes:
                for key, name, pins in variants:
                    began = time.monotonic()
                    (recipe, receipt, _grid, drawn, hand_report, sign_report,
                     markup) = renderer.render(seed, dict(pins) or None)
                    html_render._emit_page(args, name, recipe, receipt, drawn,
                                           hand_report, sign_report, markup, seed, notes)
                    drawn_variants.append({
                        "key": key,
                        "record": Path(name).with_suffix(".json").name,
                        "html": Path(name).with_suffix(".html").name,
                        "images": record.page_names(name, len(drawn)),
                        "seconds": round(time.monotonic() - began, 2),
                        "attributes": {attr: option.id
                                       for attr, option in recipe.choices.items()},
                    })
        except BaseException:
            # Ghim trái luật hỏng ngay ở sampler, trước khi có ảnh: đừng để
            # lại thư mục rỗng trong lịch sử. Lỗi vẫn ném lên cho trang hiện.
            shutil.rmtree(out, ignore_errors=True)
            raise

        meta = {
            "run": out.name, "seed": seed, "force": force,
            "variants": drawn_variants,
            "seconds": round(time.monotonic() - started, 2),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        (out / "demo.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
        return meta


def history(limit: int = 40) -> list[dict]:
    """Các lần sinh trước, mới nhất trước. Thư mục thiếu `demo.json` (sinh dở,
    lỗi giữa chừng) bị bỏ qua -- nó không có gì để mở lại."""
    if not RUNS_ROOT.is_dir():
        return []
    runs = []
    for directory in sorted(RUNS_ROOT.iterdir(), reverse=True):
        meta = directory / "demo.json"
        if meta.is_file():
            try:
                runs.append(json.loads(meta.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        if len(runs) >= limit:
            break
    return runs


# ------------------------------------------------------------- http


def make_handler(studio: Studio):
    class Handler(BaseHTTPRequestHandler):
        server_version = "vlm-ocr-demo"

        def log_message(self, fmt, *args):  # gọn hơn mặc định, vẫn in
            sys.stderr.write(f"[demo] {self.address_string()} {fmt % args}\n")

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status: int = 200) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _file(self, path: Path) -> None:
            kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if kind.startswith("text/") or kind == "application/json":
                kind += "; charset=utf-8"
            self._send(200, path.read_bytes(), kind)

        def do_GET(self):  # noqa: N802 -- tên do http.server đặt
            path = unquote(urlparse(self.path).path)
            if path in ("/", "/index.html"):
                return self._file(HERE / "index.html")
            if path == "/api/options":
                return self._json(options())
            if path == "/api/runs":
                return self._json(history())
            if path.startswith("/runs/"):
                target = (RUNS_ROOT / path[len("/runs/"):]).resolve()
                # Chặn `../`: chỉ phát file nằm trong data/demo.
                if RUNS_ROOT.resolve() not in target.parents or not target.is_file():
                    return self._json({"error": "không có file này"}, 404)
                return self._file(target)
            return self._json({"error": f"không có {path}"}, 404)

        def do_POST(self):  # noqa: N802
            if urlparse(self.path).path != "/api/generate":
                return self._json({"error": "không có"}, 404)
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    raise DemoError("thân yêu cầu quá lớn")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise DemoError("thân yêu cầu là một object JSON")
                seed, force, compare = parse_request(body)
            except (DemoError, json.JSONDecodeError) as error:
                return self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            try:
                return self._json(studio.generate(seed, force, compare))
            except Exception as error:  # noqa: BLE001 -- trả về trang, không nuốt
                # Ghim trái luật (bố cục không hợp loại giấy...) rơi vào đây từ
                # sampler: lời lỗi của luật là thứ người bấm cần đọc.
                detail = traceback.format_exc()
                sys.stderr.write(detail)
                return self._json({"error": f"{type(error).__name__}: {error}",
                                   "trace": detail[-4000:]},
                                  HTTPStatus.INTERNAL_SERVER_ERROR)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--scale", type=float, default=2.0,
                        help="hệ số chụp màn hình, như `render.py --scale`")
    args = parser.parse_args()

    studio = Studio(scale=args.scale)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(studio))
    print(f"[demo] mở http://{args.host}:{args.port}  (ảnh ghi vào {RUNS_ROOT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        studio.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
