#!/usr/bin/env python3
"""Ba đường sinh có lặp lại bố cục không — CÙNG một thước, trên ảnh đã vẽ.

    python -m tools.llm.path_diversity data/22-09-26-synthetics-multipage \
        data/24-09-div-before data/24-09-phoi-fill

Đọc `records/**/*.json` -- `layout_annotations` THẬT do Chromium đo -- rồi trả
lời đúng một câu cho mỗi lô:

    bao nhiêu dấu vân bố cục KHÁC NHAU trên tổng số ảnh?

## Vì sao không dùng thẳng `tools/llm/diversity_report.py`

File ấy đo **láng giềng gần nhất trong cửa sổ 24 tờ** -- câu hỏi của một cổng
gác đang chạy ("tờ này có trùng tờ vừa rồi không"). Đây là câu hỏi của một bộ
dữ liệu đã xong ("cả lô này có bao nhiêu bố cục"), và hai câu trả lời khác
nhau một cách quan trọng: một lô xen kẽ hoàn hảo 3 bố cục A-B-C-A-B-C không
bao giờ chạm cửa sổ, nhưng nó vẫn chỉ có 3 bố cục.

Cả hai đều cần. Cổng gác dùng cửa sổ; báo cáo bộ dữ liệu dùng con số ở đây.

## Vì sao so được giữa ba đường

Cùng `agent/fingerprint.py::geometry_fingerprint` (lưới 8x12 trên
`layout_annotations` phần nghìn), cùng nguồn (`records/`), cùng phép đếm.
Không đường nào được chấm bằng thước của riêng nó -- đó là cả lý do file này
tồn tại thay vì ba con số trong ba báo cáo.

Một cảnh báo phải đọc cùng bảng: **số ảnh khác nhau giữa các lô**, và tỉ lệ
"dấu vân khác nhau / ảnh" giảm tự nhiên theo cỡ lô (lô càng lớn càng dễ đụng
lại một bố cục cũ). Nên bảng in cả con số TUYỆT ĐỐI và, khi các lô lệch cỡ
nhau, một cột cắt mọi lô về cùng cỡ với lô nhỏ nhất.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.fingerprint import geometry_fingerprint  # noqa: E402


def records(root: Path) -> list[dict]:
    """Bản ghi theo thứ tự tên tệp -- ổn định giữa hai lần chạy."""
    out = []
    for path in sorted((root / "records").rglob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:                                    # noqa: BLE001
            continue
    return out


def measure(root: Path, cut: int = 0) -> dict:
    rows = records(root)
    if cut:
        rows = rows[:cut]
    cells, grids = [], []
    for record in rows:
        fp = geometry_fingerprint(record.get("layout_annotations") or [])
        if not fp.regions:
            continue
        cells.append(fp.cells)
        grids.append(fp.grid)
    n = len(cells)
    return {
        "run": root.name,
        "images": n,
        "distinct_layouts": len(set(cells)),
        "share": round(len(set(cells)) / n, 4) if n else 0.0,
        # Bitmask MỰC của tờ đầu, không đọc nhãn -- tín hiệu ĐỘC LẬP với
        # `cells`, nên nó nói được khi hai phép đo bất đồng.
        "distinct_ink_grids": len(set(grids)),
        "skipped_no_regions": len(rows) - n,
    }


def by_template(root: Path) -> dict:
    """Mỗi phôi cho ra mấy bố cục khác nhau -- chỉ có nghĩa cho lô `run_fill`.

    Đây là con số quyết định câu "đường phôi có giải được bài đa dạng không",
    và nó KHÔNG đọc được từ tỉ lệ `bố cục / ảnh` của cả lô: đa dạng của đường
    này bị chặn trên bởi SỐ PHÔI, không bởi số ảnh. Điền một phôi thêm nghìn
    lần không thêm được bố cục nào sau khi nó đã cạn.

    Nên thước đúng là **bố cục mỗi phôi**, và nó ngoại suy được: N phôi cho ra
    chừng `N × (số này)` bố cục. Gắn bản ghi về phôi qua `declared/*.json`
    (`template_id`), không qua tên tệp -- tên tệp là thứ đổi khi ai đó sửa
    công thức đặt tên, `template_id` thì không."""
    layouts: dict = {}
    images: dict = {}
    for path in sorted((root / "records").rglob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        # `records/` tách mỗi TỜ thành một tệp `<stem>_pNN`, `declared/` giữ
        # một tệp cho cả TÀI LIỆU -- cắt hậu tố trang để tìm lại nó.
        base = path.stem.rsplit("_p", 1)[0] if "_p" in path.stem else path.stem
        declared = root / "declared" / f"{base}.json"
        if not declared.is_file():
            continue
        try:
            tid = json.loads(declared.read_text(encoding="utf-8")).get("template_id")
        except Exception:                                    # noqa: BLE001
            continue
        if not tid:
            continue
        fp = geometry_fingerprint(record.get("layout_annotations") or [])
        if not fp.regions:
            continue
        layouts.setdefault(tid, set()).add(fp.cells)
        images[tid] = images.get(tid, 0) + 1
    if not layouts:
        return {}
    total = sum(len(v) for v in layouts.values())
    return {
        "templates": len(layouts),
        "images": sum(images.values()),
        "layouts": total,
        "layouts_per_template": round(total / len(layouts), 2),
        "images_per_template": round(sum(images.values()) / len(layouts), 2),
        "per_template": {k: {"images": images[k], "layouts": len(v)}
                         for k, v in sorted(layouts.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--by-template", action="store_true",
                        help="thêm bảng bố cục-mỗi-phôi cho lô `synthgen.run_fill`")
    parser.add_argument("--cut", type=int, default=0,
                        help="cắt mọi lô về N ảnh đầu; 0 = cắt về cỡ lô nhỏ nhất")
    parser.add_argument("--no-cut", action="store_true",
                        help="chỉ in con số trên cỡ lô thật")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    full = [measure(run.resolve()) for run in args.runs]
    rows = {"full": full}
    if not args.no_cut:
        cut = args.cut or min((r["images"] for r in full if r["images"]),
                              default=0)
        rows["cut"] = [measure(run.resolve(), cut) for run in args.runs] if cut else []
        rows["cut_at"] = cut

    head = f"{'lô':34s} {'ảnh':>6s} {'bố cục khác nhau':>18s} {'tỉ lệ':>8s} {'lưới mực':>10s}"
    print("\ntrên cỡ lô thật\n")
    print(head)
    print("-" * len(head))
    for r in full:
        print(f"{r['run']:34s} {r['images']:6d} {r['distinct_layouts']:18d} "
              f"{r['share']:7.1%} {r['distinct_ink_grids']:10d}")
    if rows.get("cut"):
        print(f"\ncắt mọi lô về {rows['cut_at']} ảnh đầu "
              "(tỉ lệ giảm theo cỡ lô, nên chỉ cột này so được)\n")
        print(head)
        print("-" * len(head))
        for r in rows["cut"]:
            print(f"{r['run']:34s} {r['images']:6d} {r['distinct_layouts']:18d} "
                  f"{r['share']:7.1%} {r['distinct_ink_grids']:10d}")
    if args.by_template:
        rows["by_template"] = {}
        for run in args.runs:
            got = by_template(run.resolve())
            if not got:
                continue
            rows["by_template"][run.name] = got
            print(f"\n{run.name}: {got['templates']} phôi, {got['images']} ảnh, "
                  f"{got['layouts']} bố cục khác nhau")
            print(f"  -> {got['layouts_per_template']} bố cục mỗi phôi "
                  f"({got['images_per_template']} ảnh mỗi phôi)")
            print("  Đa dạng của đường này bị chặn trên bởi SỐ PHÔI: N phôi ra "
                  f"chừng N x {got['layouts_per_template']} bố cục, bất kể "
                  "điền bao nhiêu lần.")
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print(f"\n{args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
