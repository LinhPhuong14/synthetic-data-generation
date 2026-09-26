#!/usr/bin/env python3
"""Kiểm `layout_annotations` của một bộ đã sinh: hai vùng một hộp, và đầu mục
trông như nhãn trường.

    python tools/check_regions.py data/pilot18
    python tools/check_regions.py data/pilot16 data/pilot17 data/pilot18 --show 8

Đọc `records/` (hoặc `json/` với bộ cũ) của từng thư mục, mỗi TÀI LIỆU một
lần -- bản `_p2`, `_p3` là bản chép của cùng bản ghi cạnh từng tờ, đếm lại là
đếm gấp đôi. Không mở ảnh, không cần thư viện ngoài.

Hai điều được kiểm, cả hai đo được trên pilot18, trên tờ ĐÃ QUA CỔNG:

(a) **Hai vùng một hộp** -- cùng `bbox`, cùng `page_number`. Là LỖI: hai nhãn
    cho cùng một chỗ mực là hai nhãn tranh nhau một điểm ảnh, dù giống nhau
    (bản sao) hay khác nhau (`Page-Footer` và `Text` cho cùng một dòng chân
    trang). `pipeline/record.py::_unwrap` gộp chúng từ khi có luật ấy; bộ nào
    vẫn còn là bộ vẽ trước luật, hoặc luật hỏng. Mã thoát 1.

(b) **Đầu mục trông như nhãn trường** -- `Section-Header`/`Page-Header`/`Title`
    mà chữ kết thúc bằng `:` và ngắn dưới 30 ký tự ("Họ và tên:", "Tên đơn
    vị:"). Dấu hiệu mạnh của một nhãn trường mang nhầm nhãn đầu mục, nhưng
    KHÔNG phải bằng chứng: "Kính gửi:" đứng một mình có thể là đầu mục thật.
    Nên chỉ liệt kê cho người xem, không tính là lỗi.

Và một con số thông tin: vùng mang `twins_dropped` KHÁC nhãn -- những cặp
`_unwrap` đã gộp và ghi lại -- để thấy model còn khai chồng bao nhiêu.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Nhãn nói về CHỖ ĐỨNG -- xem `pipeline/record.py::STRUCTURAL_LABELS`. Chép
# ba cái thay vì import: script này phải chạy được ở chỗ chỉ có bản ghi, không
# có kho, và `Page-Footer` cố ý không nằm đây -- "Hotline:" ở chân trang là
# chân trang thật.
HEADING_LABELS = frozenset({"Section-Header", "Page-Header", "Title"})
CAPTION_MAX_CHARS = 30

_PAGE_COPY = re.compile(r"_p\d+$")


def twins(record: dict) -> list[dict]:
    """Mỗi nhóm vùng cùng (`bbox`, `page_number`), theo thứ tự gặp."""
    groups: dict[tuple, list[dict]] = {}
    for region in record.get("layout_annotations") or []:
        bbox = region.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        key = (tuple(int(round(float(v))) for v in bbox),
               int(region.get("page_number", 1) or 1))
        groups.setdefault(key, []).append(region)
    out = []
    for (bbox, page), members in groups.items():
        if len(members) < 2:
            continue
        labels = [str(m.get("layout_class") or "") for m in members]
        out.append({
            "bbox": list(bbox), "page_number": page, "labels": labels,
            "conflict": len(set(labels)) > 1,
            "text": str(members[0].get("text") or ""),
            "region_indices": [m.get("region_index") for m in members],
        })
    return out


def caption_suspects(record: dict) -> list[dict]:
    """Đầu mục ngắn kết thúc bằng hai chấm -- để người xem lại."""
    out = []
    for region in record.get("layout_annotations") or []:
        label = str(region.get("layout_class") or "")
        text = str(region.get("text") or "").strip()
        if (label in HEADING_LABELS and text.endswith(":")
                and len(text) < CAPTION_MAX_CHARS):
            out.append({"text": text, "layout_class": label,
                        "bbox": region.get("bbox"),
                        "page_number": int(region.get("page_number", 1) or 1),
                        "region_index": region.get("region_index")})
    return out


def merged_conflicts(record: dict) -> int:
    """Số vùng `_unwrap` đã gộp từ một cặp KHÁC nhãn."""
    count = 0
    for region in record.get("layout_annotations") or []:
        gone = region.get("twins_dropped") or []
        if any(str(g.get("layout_class")) != str(region.get("layout_class"))
               for g in gone):
            count += 1
    return count


def documents(root: Path):
    """`(tên, bản ghi)` của từng TÀI LIỆU trong `root`, bỏ bản chép theo tờ."""
    folder = next((root / name for name in ("records", "json")
                   if (root / name).is_dir()), None)
    if folder is None:
        return
    for path in sorted(folder.rglob("*.json")):
        if _PAGE_COPY.search(path.stem):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and "layout_annotations" in record:
            yield path.relative_to(root), record


def audit(root: Path) -> dict:
    """Số đo của một bộ, kèm ví dụ."""
    tally: Counter = Counter()
    examples: dict[str, list[str]] = {"twins": [], "conflicts": [], "suspects": []}
    for name, record in documents(root):
        tally["documents"] += 1
        tally["regions"] += len(record.get("layout_annotations") or [])
        found = twins(record)
        if found:
            tally["documents_with_twins"] += 1
        for twin in found:
            tally["twin_groups"] += 1
            tally["twin_extra_regions"] += len(twin["labels"]) - 1
            kind = "conflicts" if twin["conflict"] else "twins"
            tally["twin_conflicts" if twin["conflict"] else "twin_copies"] += 1
            examples[kind].append(
                f"{name} tờ {twin['page_number']} {twin['bbox']} "
                f"{' / '.join(twin['labels'])} {twin['text'][:40]!r}")
        for suspect in caption_suspects(record):
            tally["suspects"] += 1
            examples["suspects"].append(
                f"{name} tờ {suspect['page_number']} {suspect['bbox']} "
                f"{suspect['layout_class']} {suspect['text']!r}")
        tally["merged_conflicts"] += merged_conflicts(record)
    return {"root": str(root), "tally": tally, "examples": examples}


def report(results: list[dict], show: int) -> int:
    """In bảng và ví dụ; trả mã thoát."""
    total: Counter = Counter()
    head = (f"{'bộ':32s} {'tài liệu':>8s} {'vùng':>7s} {'trùng hộp':>9s} "
            f"{'bản sao':>7s} {'khác nhãn':>9s} {'đã gộp':>6s} {'xem lại':>7s}")
    print(head)
    print("-" * len(head))
    for result in results:
        t = result["tally"]
        total.update(t)
        print(f"{Path(result['root']).name:32s} {t['documents']:8d} {t['regions']:7d} "
              f"{t['twin_groups']:9d} {t['twin_copies']:7d} {t['twin_conflicts']:9d} "
              f"{t['merged_conflicts']:6d} {t['suspects']:7d}")
    if len(results) > 1:
        print("-" * len(head))
        t = total
        print(f"{'tổng':32s} {t['documents']:8d} {t['regions']:7d} "
              f"{t['twin_groups']:9d} {t['twin_copies']:7d} {t['twin_conflicts']:9d} "
              f"{t['merged_conflicts']:6d} {t['suspects']:7d}")
    print()
    print("trùng hộp = nhóm vùng cùng (bbox, tờ); bản sao = cùng nhãn; "
          "khác nhãn = hai nhãn cho một chỗ mực -- LỖI.")
    print("đã gộp = vùng `_unwrap` đã gộp từ cặp khác nhãn (thông tin). "
          "xem lại = đầu mục ngắn kết thúc bằng ':' -- để NGƯỜI xem, không phải lỗi.")
    if show:
        for result in results:
            for kind, title in (("conflicts", "khác nhãn"), ("twins", "bản sao"),
                                ("suspects", "xem lại")):
                lines = result["examples"][kind]
                if not lines:
                    continue
                print(f"\n[{Path(result['root']).name}] {title} ({len(lines)}):")
                for line in lines[:show]:
                    print("  " + line)
                if len(lines) > show:
                    print(f"  … còn {len(lines) - show}")
    return 1 if total["twin_groups"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", type=Path, nargs="+", help="thư mục đã sinh xong")
    parser.add_argument("--show", type=int, default=6,
                        help="số ví dụ mỗi loại mỗi bộ; 0 = chỉ bảng")
    args = parser.parse_args()
    results = []
    for root in args.runs:
        root = root.resolve()
        if not any((root / name).is_dir() for name in ("records", "json")):
            print(f"{root}: không có records/ hay json/ -- đây có phải thư mục "
                  f"đã sinh xong không?", file=sys.stderr)
            return 2
        results.append(audit(root))
    return report(results, args.show)


if __name__ == "__main__":
    raise SystemExit(main())
