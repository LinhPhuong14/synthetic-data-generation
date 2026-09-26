#!/usr/bin/env python3
"""Một phôi cho ra được BAO NHIÊU tờ khác nhau, đo bằng cách điền thật.

    python -m tools.llm.template_yield data/phoi-v1 --fills 24
    python -m tools.llm.template_yield data/phoi-v1 --fills 24 --json san-luong.json

Câu hỏi này quyết `per-template` của `synthgen/run_fill.py`, và nó KHÔNG đoán
được từ số chỗ trống. Đo trên 18 phôi chuyển từ `data/pilot17` +
`data/24-09-div-before` (36 tờ, mỗi phôi 2 lần điền): 10 trên 36 tờ có một tờ
gần như y hệt (Jaccard >= 0,60) trong 24 tờ liền trước, và **cả mười đều ra
từ phôi KHÔNG có khối `data-repeat` nào**. Một phôi như thế chỉ đổi được ĐỘ
DÀI CHỮ giữa hai lần điền, và một cái tên dài thêm mười ký tự không đẩy khối
nào sang ô lưới khác.

Nên "sản lượng" của một phôi là số dấu vân hình học KHÁC NHAU nó cho ra, và
đây là chỗ đo nó. Điền `--fills` lần, dàn từng tờ, băm thành lưới 8x12
(`agent/fingerprint.py`), rồi đếm.

## Vì sao đo chứ không suy từ cấu tạo

Suy được một nửa: có khối lặp thì số dòng đổi, số dòng đổi thì chiều cao đổi.
Nửa còn lại thì không: một bảng ba dòng và một bảng năm dòng có thể vẫn nằm
gọn trong cùng hai ô lưới, và một phôi hai trang cắt sang tờ ba ở một số dòng
nào đó mà chỉ phép dàn trang biết là số nào. Con số ấy phải đo.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.fingerprint import geometry_fingerprint  # noqa: E402
from agent.geometry_distance import jaccard  # noqa: E402
from synthgen import fill as FILL  # noqa: E402
from synthgen.run_fill import load_templates  # noqa: E402


def yields(templates, fills: int, seed: int, out: Path) -> list[dict]:
    from synthgen.draw_llm import Drawer  # noqa: PLC0415

    rows: list[dict] = []
    with Drawer(out) as drawer:
        for template in templates:
            filler = FILL.Filler(template)
            seen: list = []
            pages = 0
            for i in range(fills):
                got = filler.draw(random.Random(seed + 7919 * i))
                html, _m, _s, _g = FILL.prepare(got.html, seed + i)
                record = drawer.measure(html, f"yield_{template.template_id}_{i}",
                                        template.family)
                if not record:
                    continue
                pages += 1
                seen.append(geometry_fingerprint(
                    record.get("layout_annotations") or []))
            distinct = len({fp.cells for fp in seen})
            # Cặp gần nhau nhất TRONG CHÍNH phôi này. Trung vị nói "hai tờ bất
            # kỳ ra từ phôi này giống nhau tới đâu" -- con số đọc được, khác
            # hẳn `distinct` (một ô lưới lệch cũng thành "khác").
            pairs = [jaccard(seen[i], seen[j])
                     for i in range(len(seen)) for j in range(i + 1, len(seen))]
            pairs.sort()
            rows.append({
                "template_id": template.template_id,
                "family": template.family,
                "repeats": template.repeat_names,
                "slots": len(template.scalar_paths) + sum(
                    1 for p in filler._slots if "[]" in p),
                "fills": pages,
                "distinct_geometry": distinct,
                "yield": round(distinct / pages, 3) if pages else 0.0,
                "median_pair_jaccard": round(
                    pairs[len(pairs) // 2], 3) if pairs else None,
                "share_over_ceiling": round(
                    sum(1 for j in pairs if j >= 0.60) / len(pairs), 3)
                if pairs else None,
            })
            print(f"  {template.template_id:44s} {len(template.repeat_names)} "
                  f"khối lặp  {distinct:3d}/{pages:3d} dấu vân khác nhau  "
                  f"J trung vị {rows[-1]['median_pair_jaccard']}", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--fills", type=int, default=24)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    templates = load_templates(args.root.resolve())
    if not templates:
        print(f"không có phôi nào trong {args.root}/templates")
        return 1
    print(f"[sản lượng] {len(templates)} phôi x {args.fills} lần điền")
    out = args.root.resolve() / "_yield"
    rows = yields(templates, args.fills, args.seed, out)
    with_repeat = [r for r in rows if r["repeats"]]
    without = [r for r in rows if not r["repeats"]]
    print()
    for name, group in (("CÓ khối lặp", with_repeat),
                        ("KHÔNG khối lặp", without)):
        if not group:
            continue
        mean_yield = sum(r["yield"] for r in group) / len(group)
        overs = [r["share_over_ceiling"] for r in group
                 if r["share_over_ceiling"] is not None]
        print(f"[sản lượng] {name}: {len(group)} phôi, "
              f"{mean_yield:.0%} số tờ có dấu vân riêng, "
              f"{sum(overs) / len(overs):.0%} số cặp vượt ngưỡng 0,60"
              if overs else f"[sản lượng] {name}: {len(group)} phôi")
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print(f"[sản lượng] {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
