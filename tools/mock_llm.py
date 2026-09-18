#!/usr/bin/env python3
"""Một endpoint OpenAI-compatible KHÔNG có model thật ở sau — để diễn tập.

    python tools/mock_llm.py --seed 2026 --trace data/llm200/llm_trace.jsonl
    export VLM_LLM_URL=http://127.0.0.1:8077/v1 VLM_LLM_MODEL=planner
    python tools/agent_dataset.py -o data/llm200 -n 200 --plan-only

Nó nói đúng thứ tiếng mà `agent/client.py` gửi đi: `POST /v1/chat/completions`
với `response_format: json_schema`, `GET /v1/models` cho `alive()`. Nên
`planner.plan` không phân biệt được nó với vLLM, và mọi trang trong
`agent_plan.json` được ghi `by: "llm"` y như một lượt chạy thật.

Vì sao có file này
------------------

Một lượt 200 ảnh mất hàng chục phút để VẼ và vài giây để LẬP KẾ HOẠCH. Nhìn
phân phối trước khi vẽ là cách rẻ nhất để không vẽ nhầm 200 tờ. Nhưng chế độ
`coverage` (không server) KHÔNG phải cái sẽ chạy thật: nó tối ưu phủ đều, còn
model tối ưu "trang này có giống giấy thật không". Hai phân phối khác hẳn nhau,
nên diễn tập bằng `coverage` rồi chạy thật bằng model là diễn tập nhầm vở.

Cái này là vở đúng, với phần phán đoán viết thành DỮ LIỆU thay vì trọng số:
`tools/mock_llm.yaml` — tỷ lệ theo họ giấy (`share`), nhân theo id (`bias`),
và luật theo ngữ cảnh (`rules`, kích hoạt bằng THẺ mà rulebase đã gắn). Sửa
file đó, chạy lại, nhìn phân phối mới. Không id nào viết cứng trong code này.

Nó KHÔNG phải cái gì
--------------------

Không phải mô hình ngôn ngữ. Nó không đọc hiểu, không sinh chữ, và không thay
được một lượt chạy có `VLM_LLM_URL` trỏ vào vLLM thật — chỉ có model thật mới
nói được "quán phở này bán bún bò". Nó thay được đúng một việc: cho ra một
phân phối *có chủ đích* thay vì một phân phối *phủ đều*, để xem trước.

Legality
--------

Mọi đề xuất đi qua đúng vòng bốc của `planner.decide_one`: thuộc tính theo thứ
tự bốc, mỗi thuộc tính chỉ chọn trong `Option.allowed(tags)` với tags gom được
từ các thuộc tính trước. Nên một đề xuất ở đây không bao giờ bị planner từ chối
vì phạm luật — đúng như một model có constrained decoding trên enum của rules.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from fnmatch import fnmatchcase
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROFILE = Path(__file__).resolve().parent / "mock_llm.yaml"


# --------------------------------------------------------------- hồ sơ phán đoán


def _factor(table: dict, value: str) -> tuple[float, list[str]]:
    """Tích mọi hệ số có glob khớp `value`, kèm tên các glob đã khớp."""
    factor = 1.0
    hit: list[str] = []
    for pattern, number in (table or {}).items():
        if fnmatchcase(value, str(pattern)):
            factor *= float(number)
            hit.append(f"{pattern}×{number:g}")
    return factor, hit


class Profile:
    """`tools/mock_llm.yaml`, và các hệ số dẫn ra từ nó cho một bộ luật."""

    def __init__(self, raw: dict):
        self.raw = raw or {}
        self.persona = str(self.raw.get("persona") or "")
        self.pressure = float(self.raw.get("pressure", 0.55))
        self.block_pressure = float(self.raw.get("block_pressure", 0.9))
        self.share = self.raw.get("share") or {}
        self.bias = self.raw.get("bias") or {}
        self.rules = list(self.raw.get("rules") or [])
        # attribute -> id -> hệ số, dẫn từ `share` khi biết bộ luật.
        self._share_mult: dict[str, dict[str, float]] = {}
        self.notes: list[str] = []

    @classmethod
    def load(cls, path: Path) -> "Profile":
        import yaml

        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})

    def bind(self, rules: dict) -> None:
        """Đổi `share` (tỷ lệ mục tiêu) thành hệ số nhân, cho bộ luật NÀY.

        Tỷ lệ trung hoà của một họ là tổng weight của nó chia tổng weight toàn
        thuộc tính — đúng cái mà một lượt bốc độc lập sẽ ra. Hệ số là
        `mục tiêu / trung hoà`, nên một giá trị mới thêm vào rulebase rơi vào
        glob khớp nó và cả họ tự chia lại, không phải sửa gì ở đây.
        """
        self._share_mult = {}
        self.notes = []
        for attribute, targets in self.share.items():
            options = [o for o in rules.get(attribute, ())
                       if o.weight > 0 and o.enabled]
            total = sum(o.weight for o in options)
            if not options or total <= 0:
                self.notes.append(f"share.{attribute}: thuộc tính không có giá trị nào sống")
                continue
            family: dict[str, str] = {}
            for option in options:
                for pattern in targets:
                    if fnmatchcase(option.id, str(pattern)):
                        family[option.id] = str(pattern)
                        break
            neutral: dict[str, float] = {}
            for option in options:
                key = family.get(option.id, "")
                neutral[key] = neutral.get(key, 0.0) + option.weight / total
            multiplier: dict[str, float] = {}
            for pattern, target in targets.items():
                have = neutral.get(str(pattern), 0.0)
                if have <= 0:
                    self.notes.append(
                        f"share.{attribute}: glob {pattern!r} không khớp giá trị nào")
                    continue
                multiplier[str(pattern)] = float(target) / have
            rest_target = max(0.0, 1.0 - sum(float(v) for v in targets.values()))
            rest_neutral = neutral.get("", 0.0)
            multiplier[""] = (rest_target / rest_neutral) if rest_neutral > 0 else 1.0
            self._share_mult[attribute] = {
                option.id: multiplier.get(family.get(option.id, ""), 1.0)
                for option in options}

    def fired(self, tags: frozenset, picks: dict[str, str]) -> list[dict]:
        """Những luật ngữ cảnh mà trang đang bốc đã kích hoạt."""
        out = []
        for rule in self.rules:
            when = rule.get("when") or {}
            wanted = set(when.get("tags") or ())
            if wanted and not wanted <= set(tags):
                continue
            ids = when.get("ids") or {}
            if any(not fnmatchcase(picks.get(attribute, ""), str(pattern))
                   for attribute, pattern in ids.items()):
                continue
            out.append(rule)
        return out

    def weigh(self, attribute: str, option, fired: list[dict]
              ) -> tuple[float, list[str]]:
        """Hệ số nhân vào weight của rulebase, và lý do — cho log."""
        factor = self._share_mult.get(attribute, {}).get(option.id, 1.0)
        why: list[str] = []
        if abs(factor - 1.0) > 1e-9:
            why.append(f"share×{factor:.2f}")
        bias, hit = _factor(self.bias.get(attribute) or {}, option.id)
        factor *= bias
        why += [f"bias {h}" for h in hit]
        for rule in fired:
            step, hit = _factor((rule.get("then") or {}).get(attribute) or {}, option.id)
            if hit:
                factor *= step
                why.append(f"{rule.get('name', '?')}: {', '.join(hit)}")
        return factor, why


# ------------------------------------------------------------------ phán đoán


class Judge:
    """Bốc một trang: đúng vòng của planner, cộng phán đoán của hồ sơ."""

    def __init__(self, profile: Profile, seed: int, dressings: int,
                 layouts_with_table: bool = False):
        self.profile = profile
        self.rng = random.Random(seed)
        self.seed = seed
        self.dressings = dressings
        self.layouts_with_table = layouts_with_table
        self.rules: dict | None = None
        self.lock = threading.Lock()

    def ready(self) -> bool:
        """Dựng lại ĐÚNG bộ luật mà driver lập kế hoạch trên đó.

        Không đọc `<out>/rules`: `pipeline.config.materialise_rules` ghi ra
        weight và tags nhưng KHÔNG ghi `enabled: false`, nên bản trên đĩa nói
        `hand_font`, `stains`, `torn_edges`, `punched` là bốc được trong khi
        `rulebase/rules/*.yaml` đã tắt chúng. Đề xuất một giá trị đã tắt thì
        planner từ chối và thuộc tính ấy tụt về coverage — đúng 39/200 trang
        trong lần chạy đầu tiên. `agent.rules.compose` là bản mà planner dùng,
        nên đó là bản phải hỏi.

        `--seed`/`--dressings` phải khớp lượt chạy vì catalogue dressing bốc
        từ chúng. Cái gì lệch (ví dụ `--qualified` lọc bớt dressing) thì bị
        chặn ở bước sau: mọi lựa chọn còn phải nằm trong enum của chính prompt.
        """
        if self.rules is not None:
            return True
        from agent import policy as policy_module
        from agent import rules as agent_rules
        from agent import variants

        pol = policy_module.load()
        rules = agent_rules.compose(variants.build(count=self.dressings,
                                                   seed=self.seed), pol)
        if self.layouts_with_table:
            from agent_dataset import table_layout_ids

            keep = table_layout_ids()
            rules = agent_rules.switch_off(
                rules, "layout", {o.id for o in rules["layout"]} - keep)
        if agent_rules.writevit_missing() is not None:
            rules = agent_rules.switch_off(rules, "handwriting",
                                           agent_rules.NEEDS_WRITEVIT)
        self.rules = rules
        self.profile.bind(self.rules)
        for note in self.profile.notes:
            print(f"[mock-llm] ! {note}", file=sys.stderr)
        return True

    def page(self, order: tuple[str, ...], enums: dict[str, set],
             tally: dict[str, dict[str, int]],
             block_used: dict[str, dict[str, int]]) -> tuple[dict, dict]:
        """Một trang hợp luật, kèm giải trình từng thuộc tính."""
        picks: dict[str, str] = {}
        why: dict[str, str] = {}
        tags: frozenset = frozenset()
        for attribute in order:
            options = [o for o in self.rules.get(attribute, ())
                       if o.weight > 0 and o.enabled and o.allowed(tags)
                       and o.id in enums.get(attribute, ())]
            if not options:
                raise Clash(f"{attribute}: không còn giá trị nào hợp luật")
            fired = self.profile.fired(tags, picks)
            scored: list[tuple[float, object, list[str]]] = []
            for option in options:
                factor, reason = self.profile.weigh(attribute, option, fired)
                score = option.weight * factor
                seen = tally.get(attribute, {}).get(option.id, 0)
                if seen:
                    score /= (1.0 + seen) ** self.profile.pressure
                    reason.append(f"đã dùng {seen}")
                mine = block_used.get(attribute, {}).get(option.id, 0)
                if mine:
                    score /= (1.0 + mine) ** self.profile.block_pressure
                scored.append((max(score, 1e-9), option, reason))
            total = sum(s for s, _, _ in scored)
            option = self.rng.choices([o for _, o, _ in scored],
                                      weights=[s for s, _, _ in scored], k=1)[0]
            chosen = next(item for item in scored if item[1] is option)
            picks[attribute] = option.id
            block_used.setdefault(attribute, {})[option.id] = \
                block_used.setdefault(attribute, {}).get(option.id, 0) + 1
            tail = "; ".join(chosen[2]) if chosen[2] else "theo weight của rulebase"
            why[attribute] = (f"{option.id} (p={chosen[0] / total:.0%} trong "
                              f"{len(options)} hợp luật) ← {tail}")
            tags = tags | option.tags
        return picks, why


class Clash(RuntimeError):
    """Vòng bốc cụt đường — bốc lại trang, y như `sample_recipe`."""


# ---------------------------------------------------------------------- server


class Handler(BaseHTTPRequestHandler):
    judge: Judge
    trace: Path | None
    verbose: bool
    served = 0
    counter_lock = threading.Lock()

    def log_message(self, *args) -> None:      # noqa: A003 -- im lặng, tự log
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:                   # noqa: N802 -- tên của thư viện
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list",
                             "data": [{"id": "planner", "object": "model",
                                       "owned_by": "tools/mock_llm.py"}]})
            return
        self._send(404, {"error": {"message": f"no route {self.path}"}})

    def do_POST(self) -> None:                  # noqa: N802 -- tên của thư viện
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            self._send(400, {"error": {"message": f"body không phải JSON: {error}"}})
            return
        started = time.time()
        try:
            content, note = self.answer(request)
        except Unsupported as error:
            # 4xx: `client.Client._post` không thử lại, và `propose` coi
            # `LLMError` là "không có đề xuất" rồi bốc theo coverage. Đúng cái
            # cần: một prompt mà server này không diễn được thì trang ấy tụt
            # về coverage và ghi rõ như vậy, chứ không phải cả lượt chạy chết.
            self._send(400, {"error": {"message": str(error)}})
            return
        payload = {
            "id": f"mock-{int(started * 1000)}",
            "object": "chat.completion",
            "created": int(started),
            "model": request.get("model", "planner"),
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        self._send(200, payload)
        note["elapsed_ms"] = round((time.time() - started) * 1000, 1)
        self.write_trace(note)

    # ---------------------------------------------------------------- phán đoán

    def answer(self, request: dict) -> tuple[str, dict]:
        schema = (((request.get("response_format") or {}).get("json_schema") or {})
                  .get("schema") or {})
        pages = ((schema.get("properties") or {}).get("pages") or {})
        item = (pages.get("items") or {})
        properties = item.get("properties") or {}
        if not properties:
            raise Unsupported(
                "tools/mock_llm.py chỉ diễn được prompt lập kế hoạch của "
                "agent/planner.py (schema có `pages[].<thuộc tính>`). Prompt "
                "này cần một model thật.")
        self.judge.ready()

        order = tuple(properties.keys())
        enums = {name: set(spec.get("enum") or ()) for name, spec in properties.items()}
        block = int(pages.get("minItems") or 1)
        prompt = "\n".join(str(message.get("content") or "")
                           for message in (request.get("messages") or []))
        tally = _tally(prompt)

        with self.judge.lock:
            with Handler.counter_lock:
                Handler.served += 1
                index = Handler.served
            block_used: dict[str, dict[str, int]] = {}
            out: list[dict] = []
            explained: list[dict] = []
            for offset in range(block):
                for attempt in range(24):
                    try:
                        picks, why = self.judge.page(order, enums, tally, block_used)
                        break
                    except Clash:
                        if attempt == 23:
                            raise
                out.append(picks)
                explained.append({"page": offset, "picks": picks, "why": why})
                if self.verbose:
                    trail = " → ".join(picks[a] for a in order)
                    print(f"[mock-llm] #{index:02d}.{offset:02d} {trail}",
                          file=sys.stderr)

        note = {"request": index, "stage": "propose", "block": block,
                "order": list(order),
                "tally_seen": tally, "pages": explained}
        return json.dumps({"pages": out}, ensure_ascii=False), note

    def write_trace(self, note: dict) -> None:
        if self.trace is None:
            return
        note = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **note}
        with Handler.counter_lock:
            with self.trace.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(note, ensure_ascii=False) + "\n")


class Unsupported(RuntimeError):
    """Prompt này cần một model thật; trả 4xx để planner tự lo."""


def _tally(prompt: str) -> dict[str, dict[str, int]]:
    """Bảng "đã dùng nhiều nhất" mà `planner.propose` dán vào prompt.

    Đọc lại từ chính prompt chứ không giữ trạng thái ở server: một model thật
    cũng chỉ thấy đúng chừng ấy — sáu giá trị đông nhất mỗi thuộc tính — và
    diễn tập với nhiều thông tin hơn model thật có là diễn tập sai.
    """
    start = prompt.find("{")
    if start < 0:
        return {}
    try:
        raw = json.loads(prompt[start:])
    except ValueError:
        return {}
    return {str(a): {str(k): int(v) for k, v in counts.items()}
            for a, counts in raw.items() if isinstance(counts, dict)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--dressings", type=int, default=48,
                        help="phải KHỚP --dressings của lượt chạy: catalogue "
                             "dressing bốc từ (--dressings, --seed)")
    parser.add_argument("--layouts-with-table", action="store_true",
                        help="gương của cờ cùng tên bên tools/agent_dataset.py")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--trace", type=Path, default=None,
                        help="JSONL: mỗi dòng một lượt hỏi, kèm giải trình từng trang")
    parser.add_argument("--seed", type=int, default=2026,
                        help="phải KHỚP --seed của lượt chạy")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    profile = Profile.load(args.profile)
    Handler.judge = Judge(profile, args.seed, args.dressings,
                          args.layouts_with_table)
    Handler.trace = args.trace
    Handler.verbose = not args.quiet
    if args.trace:
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        args.trace.write_text("", encoding="utf-8")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[mock-llm] {args.host}:{args.port} — hồ sơ {args.profile}, "
          f"seed {args.seed}, {args.dressings} dressing", file=sys.stderr)
    print(f"[mock-llm] export VLM_LLM_URL=http://{args.host}:{args.port}/v1",
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
