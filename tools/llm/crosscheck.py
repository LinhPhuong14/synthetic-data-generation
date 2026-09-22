#!/usr/bin/env python3
"""Đo chéo hai NGƯỜI DỰNG trang trên cùng một lớp suy diễn.

    python tools/llm/crosscheck.py data/thu1k data/pilot-llm
    python tools/llm/crosscheck.py data/thu1k data/pilot-llm --per-page

## Câu hỏi tệp này trả lời

`synthgen/markup.py` và một model ngôn ngữ đều sinh ra HTML có `data-region`,
`data-kind`, `data-path`. Sau đó CÙNG một lớp suy diễn (`derive.py`,
`kie_full.py`, `overlay.py`) đọc DOM đã dàn và dựng ra vùng bố cục, thực thể,
cặp KIE.

Nhưng lớp suy diễn ấy được viết và chỉnh bằng cách nhìn đầu ra của
`markup.py`. Nếu nó mang giả định ngầm nào về hình dạng HTML -- thẻ nào bọc
thẻ nào, nhãn in nằm ở đâu so với giá trị, cột bảng xếp thế nào -- thì trang
do model viết sẽ suy ra ÍT HƠN mà không có lỗi nào được nêu. Trang vẫn vẽ ra,
hộp vẫn đúng pixel, chỉ là mỏng nhãn.

Một cái mỏng lặng lẽ thì không cổng nào bắt được, vì cổng hỏi "trang này có
hợp lệ không", còn đây là câu khác: **cùng một lớp đọc, hai nguồn viết, thu
hoạch có bằng nhau không.**

## Vì sao so TỈ LỆ chứ không so số tuyệt đối

Một tờ hoá đơn 40 dòng có nhiều thực thể hơn một tờ giấy uỷ quyền, và hai bộ
không cùng phân bố loại giấy. Nên mọi con số ở đây đều chia cho cái mẫu của
chính nó: bao nhiêu phần trăm chữ nằm trong một vùng, bao nhiêu phần trăm
thực thể vào được một cặp. Tỉ lệ so được; tổng thì không.

## Cái này KHÔNG đo

Nhãn có ĐÚNG không. Một trang gán sạch 100% chữ vào vùng `Text` vẫn đạt điểm
tuyệt đối ở đây và vẫn vô dụng. Tệp này đo ĐỘ PHỦ và ĐỘ PHONG PHÚ; phần đúng
sai ngữ nghĩa là việc của `synthgen/check.py` và của mắt người.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def records(root: Path, limit: int) -> list[dict]:
    """Mọi `records/**/*.json` dưới `root`, tối đa `limit` tệp."""
    found = sorted(root.glob("records/**/*.json"))
    out = []
    for path in found[:limit]:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:                                    # noqa: BLE001
            continue
    return out


def _pairs(record: dict) -> list[dict]:
    kie = record.get("kie") or {}
    return kie.get("pairs") or []


def measure(record: dict) -> dict:
    """Một trang → các tỉ lệ so được. Trang rỗng trả `{}` để bị bỏ qua."""
    words = record.get("word_annotations") or []
    ents = record.get("entity_annotations") or []
    regions = record.get("layout_annotations") or []
    pairs = _pairs(record)
    if not words:
        return {}

    # ĐỘ PHỦ VÙNG -- chữ không thuộc vùng nào là chữ có hộp mà không có ngữ
    # cảnh bố cục. `layout_region_index` None hoặc âm đều là "không thuộc".
    inside = sum(1 for w in words
                 if isinstance(w.get("layout_region_index"), int)
                 and w["layout_region_index"] >= 0)

    # ĐỘ PHỦ KIE -- thực thể không vào cặp nào là thực thể không ai trích được.
    in_pair = {p.get("key_entity_index") for p in pairs}
    in_pair |= {p.get("value_entity_index") for p in pairs}
    in_pair.discard(None)
    covered = sum(1 for e in ents
                  if e.get("entity_index") in in_pair)

    # NHÃN IN THẬT vs NHÃN SUY RA. `key_source == "implied"` nghĩa là cặp ấy
    # không có nhãn in trên giấy -- vẫn hợp lệ, nhưng một bộ toàn `implied`
    # là bộ không dạy được mô hình đọc quan hệ nhãn↔giá trị.
    printed = sum(1 for p in pairs if p.get("key_bbox"))

    # ĐỘ SÂU QUAN HỆ -- `relation_path` là đường dẫn lồng nhau
    # ("total.group › amount"). Sâu 1 là phẳng; bộ dữ liệu KIE lồng nhau cần
    # sâu hơn 1 thì mới có cái để học.
    depths = [len(str(w.get("relation_path") or "").split("."))
              for w in words if w.get("relation_path")]

    described = sum(1 for p in pairs if (p.get("description") or "").strip())

    return {
        "words": len(words),
        "ents": len(ents),
        "regions": len(regions),
        "pairs": len(pairs),
        "phủ vùng %": inside / len(words) * 100,
        "phủ KIE %": covered / len(ents) * 100 if ents else 0.0,
        "nhãn IN %": printed / len(pairs) * 100 if pairs else 0.0,
        "có mô tả %": described / len(pairs) * 100 if pairs else 0.0,
        "sâu quan hệ": statistics.mean(depths) if depths else 0.0,
        # `tag` là THẺ HTML (`div` ở mọi vùng); nhãn bố cục thật nằm ở
        # `layout_class`. Đọc nhầm trường này ra "1 nhãn vùng" cho cả hai
        # bên -- một phép đo trông hợp lệ và nói sai hoàn toàn.
        "_tags": Counter(r.get("layout_class") or r.get("tag") or "?"
                         for r in regions),
        "_modes": Counter(r.get("bbox_mode") or "?" for r in regions),
        "_strats": Counter(r.get("bbox_strategy") or "?" for r in regions),
        "_kinds": Counter(e.get("kind") or "?" for e in ents),
    }


ROWS = ("words", "ents", "regions", "pairs", "phủ vùng %", "phủ KIE %",
        "nhãn IN %", "có mô tả %", "sâu quan hệ")


def summarise(name: str, got: list[dict]) -> dict:
    """Trung vị từng chỉ số, cộng vốn từ vựng gộp cả bộ."""
    out = {"tên": name, "trang": len(got)}
    for key in ROWS:
        vals = [g[key] for g in got if key in g]
        out[key] = statistics.median(vals) if vals else 0.0
    tags: Counter = Counter()
    kinds: Counter = Counter()
    modes: Counter = Counter()
    strats: Counter = Counter()
    for g in got:
        tags.update(g.get("_tags") or {})
        kinds.update(g.get("_kinds") or {})
        modes.update(g.get("_modes") or {})
        strats.update(g.get("_strats") or {})
    out["_tags"], out["_kinds"] = tags, kinds
    out["_modes"], out["_strats"] = modes, strats
    # Bao nhiêu NHÃN VÙNG KHÁC NHAU mỗi trang -- một trang toàn `Text` và một
    # trang có Title/Table/Form/Caption cùng đạt 100% độ phủ, nhưng chỉ cái
    # sau dạy được mô hình phân biệt vùng.
    per_page = [len(g["_tags"]) for g in got if g.get("_tags")]
    out["nhãn vùng/trang"] = statistics.median(per_page) if per_page else 0.0
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="+", type=Path,
                        help="thư mục bộ dữ liệu, mỗi cái có records/")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--top", type=int, default=12,
                        help="bao nhiêu nhãn vùng / kind hay gặp nhất")
    args = parser.parse_args(argv)

    sides = []
    for root in args.roots:
        got = [m for m in (measure(r) for r in records(root, args.limit)) if m]
        if not got:
            print(f"{root}: không có bản ghi đọc được", file=sys.stderr)
            continue
        sides.append(summarise(root.name, got))
    if len(sides) < 2:
        print("cần ít nhất hai bộ có bản ghi để so", file=sys.stderr)
        return 2

    width = max(len(s["tên"]) for s in sides) + 2
    print("\n=== ĐO CHÉO: cùng lớp suy diễn, khác người dựng ===\n")
    head = f"{'chỉ số (trung vị)':<20}" + "".join(f"{s['tên']:>{width}}" for s in sides)
    print(head)
    print("-" * len(head))
    print(f"{'số trang':<20}" + "".join(f"{s['trang']:>{width}}" for s in sides))
    for key in ROWS:
        cells = "".join(f"{s[key]:>{width}.1f}" for s in sides)
        print(f"{key:<20}{cells}")
    print(f"{'nhãn vùng/trang':<20}"
          + "".join(f"{s['nhãn vùng/trang']:>{width}.1f}" for s in sides))

    print(f"\n{'vốn từ GỘP CẢ BỘ':<20}"
          + "".join(f"{len(s['_tags']):>{width}}" for s in sides) + "  nhãn vùng")
    print(f"{'':<20}" + "".join(f"{len(s['_kinds']):>{width}}" for s in sides)
          + "  data-kind")

    for field, label in (("_modes", "BBOX_MODE"), ("_strats", "BBOX_STRATEGY")):
        print(f"\n--- {label} ---")
        for s in sides:
            print(f"  {s['tên']}: {dict(s[field])}")

    for field, label in (("_tags", "NHÃN VÙNG"), ("_kinds", "DATA-KIND")):
        print(f"\n--- {label}: chỉ MỘT BÊN có ---")
        seen = [set(s[field]) for s in sides]
        for i, s in enumerate(sides):
            others: set = set()
            for j, o in enumerate(seen):
                if j != i:
                    others |= o
            only = sorted(seen[i] - others,
                          key=lambda k: -s[field][k])[: args.top]
            shown = ", ".join(f"{k} ({s[field][k]})" for k in only) or "—"
            print(f"  chỉ {s['tên']}: {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
