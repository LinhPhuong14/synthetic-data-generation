#!/usr/bin/env python3
"""Pha 2: phôi -> ảnh. Không một lời gọi model nào.

    python -m synthgen.run_fill data/phoi-v1 --per-template 50
    python -m synthgen.run_fill data/phoi-v1 --per-template 50 -o data/25-09-phoi

Đọc phôi `agent/compose_template.py` để lại, điền giá trị thật vào từng phôi
nhiều lần, gác cổng, rồi vẽ bằng ĐÚNG `synthgen/draw_llm.py::Drawer` mà mọi
trang khác của kho đi qua. Ra một thư mục có hình dạng y hệt một lượt
`compose_page`, nên `synthgen/derive.py`, `tools/`, và mọi thứ đọc
`manifest.jsonl` chạy trên nó không sửa một dòng.

## Cái đắt ở đây là VẼ, không phải nghĩ

Một lần điền tốn chừng một phần nghìn giây; một lần dàn trang tốn một tới ba
giây. Nên vòng chạy này một luồng, một trình duyệt, và phần song song hoá
(nếu cần) là chạy nhiều tiến trình trên nhiều phôi -- đúng cách nhánh luật
(`synthgen/run.py`) vẫn chia việc. `playwright` bản đồng bộ gắn trình duyệt
với luồng tạo ra nó, nên nhiều luồng cùng vẽ là hỏng; đó cũng là lý do
`agent/compose_page.py::Artist` chỉ có một luồng vẽ.

## Hai tầng chống trùng gặp nhau ở đây

`synthgen/fill.py::Filler` giữ tầng TRONG MỘT PHÔI (tổ hợp giá trị). File này
giữ tầng CẢ LÔ (hình học sau khi vẽ), bằng `agent/diversity.py::
DiversityWarden` -- cùng lớp, cùng ngưỡng Jaccard 0,60, cùng cửa sổ 24 tờ mà
`agent/compose_page.py` dùng. Một tờ trùng thì ĐIỀN LẠI (một phần nghìn giây)
thay vì gọi lại model (110-430 giây), nên `--attempts` ở đây để rộng tay
được: mặc định 4.

Dấu vân tầng plan mà warden nhận ở đây là dấu vân GIÁ TRỊ
(`fill.value_fingerprint`), không phải dấu vân `DocumentPlan`: cấu hình của
một tờ ở đường này là phôi cộng tổ hợp giá trị, và `DocumentPlan` đã bị
"đông cứng" vào phôi từ pha 1 nên nó giống nhau cho mọi tờ ra từ một phôi.
Báo cáo gọi tên đúng như thế -- xem `fingerprint_source` trong
`fill_report.json` -- để không ai đọc nhầm con số này là con số của đường cũ.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import diversity as DIV  # noqa: E402
from agent import geometry_distance as GD  # noqa: E402
from agent.fingerprint import geometry_fingerprint  # noqa: E402
from synthgen import fill as FILL  # noqa: E402
from synthgen import template as T  # noqa: E402
from synthgen.llm_page import orphan_share, problems  # noqa: E402

# Mấy lần điền lại khi tờ vừa vẽ trùng bố cục một tờ gần đây. Bốn, không hai
# như `agent/diversity.py::MAX_ATTEMPTS`: ở đó một lượt nữa là một lời gọi
# model 110-430 giây, ở đây là một lần điền cộng một lần dàn trang -- chừng
# hai giây. Cái giá khác ba bậc thì con số cũng phải khác.
ATTEMPTS = 4

# Trần số tờ cho một phôi KHÔNG có khối `data-repeat` nào. Xem `budget()` cho
# bảng số đo ra con số này.
NO_REPEAT_FILLS = 4


def load_templates(root: Path) -> list[T.Template]:
    """Phôi ĐÃ QUA CỔNG, theo thứ tự tên tệp.

    Chỉ đọc `templates/`, không đọc `rejected/`: một phôi trượt cổng ở pha 1
    trượt vì nó điền ra một trang không đo được, và điền nó thêm nghìn lần
    nữa chỉ nhân cái lỗi ấy lên."""
    folder = root / "templates"
    out = []
    for path in sorted(folder.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("ok") is False:
            continue
        out.append(T.Template.from_dict(raw))
    return out


def budget(template, per_template: int) -> int:
    """Phôi này đáng được điền mấy lần, đọc từ CẤU TẠO của chính nó.

    ## Con số, và phép đo ra nó

    `tools/llm/template_yield.py` điền mỗi phôi 16 lần, dàn từng tờ, băm
    `layout_annotations` thành lưới 8x12 rồi đếm dấu vân KHÁC NHAU. Đo trên
    đủ 18 phôi chuyển từ `data/pilot17` + `data/24-09-div-before`:

    | khối `data-repeat` | dấu vân khác nhau / 16 | J trung vị hai tờ | cặp vượt 0,60 |
    | --- | --- | --- | --- |
    | 0 (10 phôi) | 2,2,3,3,3,3,3,3,5,7 — **trung vị 3** | 0,82 - 1,00 | **100%** |
    | >=1 (8 phôi) | 11,12,12,13,14,14,14,16 — **trung vị 14** | 0,42 - 0,57 | 34% |

    Một phôi không có khối lặp chỉ đổi được ĐỘ DÀI CHỮ giữa hai lần điền, và
    một cái tên dài thêm mười ký tự không đẩy khối nào sang ô lưới khác. Điền
    nó 50 lần là ghi 47 bản sao vào bộ dữ liệu -- và chúng QUA CỔNG, nên
    không gì kêu lên: 100% số cặp vượt ngưỡng trùng là con số nói ra điều đó.

    Nên `NO_REPEAT_FILLS`: bốn, hơn trung vị đo được (3) một nhịp để không
    cắt mất cái đuôi (một phôi ra 7). Phôi CÓ khối lặp thì chưa chạm trần ở
    16 lần (83% số tờ vẫn có dấu vân riêng), nên nó nhận trọn `per_template`.

    Luật này đọc từ DỮ LIỆU CỦA PHÔI -- có khối lặp hay không -- chứ không
    tra một bảng theo loại chứng từ (AGENTS.md mục 5). Một phôi của loại giấy
    thứ 472 được xếp đúng mà không ai phải thêm dòng nào."""
    return per_template if template.repeat_names else min(per_template,
                                                          NO_REPEAT_FILLS)


def schedule(templates: list, per_template: int, want: int = 0) -> list[int]:
    """Thứ tự phôi cho cả lô -- XEN KẼ, không phôi này xong mới tới phôi kia.

    Thứ tự quan trọng vì cửa sổ so trùng hình học chỉ nhìn 24 tờ gần nhất.
    Chạy hết 50 tờ của phôi A rồi mới sang B thì cửa sổ lúc nào cũng toàn tờ
    cùng một phôi, và nó báo trùng liên tục cho những tờ mà cả lô coi là bình
    thường. Xen kẽ thì cửa sổ luôn là một lát cắt ngang cả bộ phôi -- đúng
    thứ mà "hai phôi khác nhau đừng vẽ ra hai tờ giống nhau" cần nhìn.

    Mỗi phôi có hạn mức riêng (`budget()`), nên vòng xen kẽ bỏ qua phôi đã
    hết hạn thay vì chia đều: chia đều là quay lại đúng chuyện điền một phôi
    không khối lặp năm mươi lần."""
    if not templates:
        return []
    left = [budget(t, per_template) for t in templates]
    total = want if want > 0 else sum(left)
    order: list[int] = []
    i = 0
    while len(order) < total and any(left):
        if left[i % len(templates)] > 0:
            left[i % len(templates)] -= 1
            order.append(i % len(templates))
        i += 1
    return order


def run(root: Path, out: Path, *, per_template: int, want: int, seed: int,
        attempts: int = ATTEMPTS, diversity: bool = True,
        window: int = GD.WINDOW, ceiling: float = GD.JACCARD_CEILING,
        no_draw: bool = False, skip_derive: bool = False) -> int:
    templates = load_templates(root)
    if not templates:
        print(f"không có phôi nào trong {root / 'templates'}; chạy "
              f"`python -m agent.compose_template -o {root}` trước")
        return 1
    order = schedule(templates, per_template, want)
    thin = [t for t in templates if not t.repeat_names]
    print(f"[điền] {len(templates)} phôi -> {len(order)} tờ "
          f"(tối đa {per_template} mỗi phôi)")
    if thin:
        print(f"[điền] {len(thin)}/{len(templates)} phôi KHÔNG có khối "
              f"`data-repeat` nào, nên chỉ nhận {NO_REPEAT_FILLS} tờ mỗi phôi "
              "-- đo được chúng chỉ ra 2-7 bố cục khác nhau dù điền 16 lần "
              "(`tools/llm/template_yield.py`)")
    print("[điền] không gọi model; giá trị từ `synthgen/values.py` "
          "(corpus `rulebase/corpus/vi/`)")
    for name in ("html", "rejected", "declared"):
        (out / name).mkdir(parents=True, exist_ok=True)

    fillers = {t.template_id: FILL.Filler(t) for t in templates}
    warden = DIV.DiversityWarden(enabled=diversity, steer=False, window=window,
                                 ceiling=ceiling)
    started = time.time()
    made: list[dict] = []
    drawer = None
    drawer_cm = None
    if not no_draw:
        from synthgen.draw_llm import Drawer  # noqa: PLC0415

        drawer_cm = Drawer(out)
        drawer = drawer_cm.__enter__()

    try:
        for n, which in enumerate(order):
            template = templates[which]
            filler = fillers[template.template_id]
            stem = f"fill_{template.template_id}_{n:05d}"
            row = _one(filler, template, stem, seed + n, attempts, warden,
                       drawer)
            made.append(row)
            folder = "html" if row["ok"] else "rejected"
            (out / folder / f"{stem}.html").write_text(row.pop("html"),
                                                       encoding="utf-8")
            (out / "declared" / f"{stem}.json").write_text(
                json.dumps(row["declared"], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
            mark = "✓" if row["ok"] else "✗"
            note = "" if row["ok"] else f"  {row['why'][0][:60]}"
            print(f"  {mark} {n + 1:5d}/{len(order)}  "
                  f"{template.template_id:26s} {row['rows']:3d} dòng"
                  f"{'  ↻' + str(row['attempt']) if row['attempt'] > 1 else '   '}"
                  f"{note}", flush=True)
            if drawer is not None:
                line, _ok = drawer.draw(out / folder / f"{stem}.html", row["ok"])
                print(f"[vẽ]{line}", flush=True)
    finally:
        rows = list(drawer.rows) if drawer is not None else []
        if drawer_cm is not None:
            drawer_cm.__exit__()

    spent = time.time() - started
    kept = [m for m in made if m["ok"]]
    report = _report(root, out, templates, fillers, made, kept, warden, spent,
                     per_template, seed)
    (out / "fill_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"\n[điền] {len(kept)}/{len(made)} qua cổng trong {spent:.0f}s "
          f"({report['seconds_per_page']}s mỗi tờ)  ·  0 lời gọi model")
    if rows:
        from synthgen.draw_llm import finish  # noqa: PLC0415

        finish(out, rows, skip_derive)
    return 0 if kept else 1


def _one(filler, template, stem: str, seed: int, attempts: int, warden,
         drawer) -> dict:
    """Một tờ: điền, chữa, gác, đo hình học, nhận hay điền lại."""
    row: dict = {}
    for attempt in range(1, max(1, attempts) + 1):
        got = filler.draw(random.Random(seed + 104729 * (attempt - 1)))
        html, mended, stamped, signed = FILL.prepare(got.html, seed + attempt)
        why = list(problems(html))
        if got.missing:
            why.append(f"{len(got.missing)} chỗ trống không có giá trị: "
                       + ", ".join(got.missing[:3]))
        loose, runs = orphan_share(html)
        row = {
            "stem": stem, "template_id": template.template_id,
            "family": template.family, "ok": not why, "why": why,
            "html": html, "attempt": attempt,
            "rows": got.counts.get("line_items", 0),
            "counts": dict(got.counts),
            "chars": len(html),
            "slots_printed": len(got.printed),
            "orphan_runs": loose, "runs": runs,
            "orphan_share": round(loose / runs, 3) if runs else 0.0,
            "mended": {k: v for k, v in mended.items() if v},
            "stamped": stamped, "signed": signed,
            "declared": {
                "loai_tai_lieu": template.doc_kind or template.family,
                "archetype": template.family,
                "doc_title": template.doc_title,
                "template_id": template.template_id,
                # DÒNG BẢNG ở dạng SỐ NGUYÊN. `synthgen/check.py` kiểm
                # `qty × unit_price == amount` trên cả kho và nó đọc khoá
                # này; không ghi ra thì phép kiểm ấy im lặng bỏ qua cả
                # đường sinh mới.
                "rows": got.rows,
                "sheets_asked": 1,
                "ok": not why, "why": why,
                # TỜ KHAI SỰ THẬT đầy đủ, kể cả những trường phôi KHÔNG in.
                # Chúng là hard-negative có sẵn: một mô hình học rằng
                # `customer.tax_code` tồn tại trên tờ giấy này trong khi nó
                # không được in ra là học sai, và bản ghi phải nói được
                # "trường ấy có giá trị, tờ này không in nó".
                "facts": got.tree,
                "printed_paths": sorted(got.printed),
            },
        }
        if why:
            break                       # trượt cổng chữ thì chưa tới cổng hình
        geo = None
        if drawer is not None:
            record = drawer.measure(html, stem, template.family)
            if record:
                geo = geometry_fingerprint(record.get("layout_annotations") or [])
        collision, taken = warden.judge(
            got.fingerprint, geo, key=stem, attempt=attempt,
            force=attempt >= max(1, attempts))
        if collision is not None:
            row["collision"] = collision.as_dict()
        if taken:
            break
    return row


def _report(root, out, templates, fillers, made, kept, warden, spent,
            per_template, seed) -> dict:
    per_tpl: dict = {}
    for row in made:
        slot = per_tpl.setdefault(row["template_id"],
                                  {"pages": 0, "kept": 0, "retried": 0})
        slot["pages"] += 1
        slot["kept"] += int(row["ok"])
        slot["retried"] += int(row["attempt"] > 1)
    return {
        "when": _dt.datetime.now().isoformat(timespec="seconds"),
        "templates_from": str(root),
        "templates": len(templates),
        "per_template": per_template,
        "seed": seed,
        "pages": len(made), "kept": len(kept),
        # SỐ LỜI GỌI MODEL, viết thẳng ra là 0. Đây là con số cả đường sinh
        # này tồn tại vì nó, và một báo cáo không nói nó ra bắt người đọc suy
        # từ chỗ khác.
        "llm_calls": 0, "tokens_in": 0, "tokens_out": 0,
        "seconds": round(spent, 1),
        "seconds_per_page": round(spent / len(made), 2) if made else 0.0,
        "median_chars": _median([m["chars"] for m in kept]),
        "median_rows": _median([m["rows"] for m in kept]),
        "retried": sum(1 for m in made if m["attempt"] > 1),
        "why_tally": _tally(m for row in made for m in row["why"]),
        "per_template_stats": per_tpl,
        "within_template": {tid: f.metrics() for tid, f in fillers.items()},
        # TÊN NGUỒN DẤU VÂN, viết ra vì hai đường sinh cho `plan_fingerprints`
        # ăn hai thứ khác nhau -- xem docstring module.
        "fingerprint_source": "value_fingerprint (synthgen/fill.py)",
        "diversity": warden.metrics(pages=len(kept)),
    }


def _median(values) -> float:
    rows = sorted(v for v in values if v)
    if not rows:
        return 0.0
    mid = len(rows) // 2
    return float(rows[mid] if len(rows) % 2 else (rows[mid - 1] + rows[mid]) / 2)


def _tally(items) -> dict:
    out: dict = {}
    for item in items:
        head = str(item).split(";")[0][:70]
        out[head] = out.get(head, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path,
                        help="thư mục `agent.compose_template` để lại")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="thư mục ảnh ra (mặc định <root>/filled)")
    parser.add_argument("--per-template", type=int, default=20)
    parser.add_argument("--want", type=int, default=0,
                        help="tổng số tờ; đè --per-template khi > 0")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=ATTEMPTS)
    parser.add_argument("--no-diversity", action="store_true",
                        help="ĐO nhưng không loại tờ trùng (nhánh đối chứng)")
    parser.add_argument("--window", type=int, default=GD.WINDOW)
    parser.add_argument("--ceiling", type=float, default=GD.JACCARD_CEILING)
    parser.add_argument("--no-draw", action="store_true",
                        help="chỉ sinh HTML, không mở trình duyệt")
    parser.add_argument("--no-derive", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    return run(root, (args.out or root / "filled").resolve(),
               per_template=args.per_template, want=args.want, seed=args.seed,
               attempts=args.attempts, diversity=not args.no_diversity,
               window=args.window, ceiling=args.ceiling,
               no_draw=args.no_draw, skip_derive=args.no_derive)


if __name__ == "__main__":
    raise SystemExit(main())
