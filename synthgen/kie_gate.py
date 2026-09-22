#!/usr/bin/env python3
"""Cổng chất lượng cho MÔ TẢ KIE của một bộ đã sinh.

    python synthgen/kie_gate.py data/thu1k
    python synthgen/kie_gate.py data/pilot16 --show 6
    python synthgen/kie_gate.py data/pilot7 data/pilot8 data/pilot9

Ra mã 0 khi mọi cổng xanh, 1 khi có cổng đỏ. Ngưỡng và mẫu câu fallback đọc
từ `rulebase/synthgen/_kie_gates.yaml`, không viết trong file này.

## Câu hỏi mà công cụ này hỏi

Mô tả KIE tồn tại để một mô hình PHÂN BIỆT trường này với trường kia trên
cùng một trang. Ba cách nó thôi làm được việc ấy, và mỗi cách là một cổng:

1. **Gộp nghĩa** -- hai cột khác nhau cùng một câu. Đo trên pilot: bốn mươi
   mốt cột (`document_issue_date`, `owner_address`, ...) cùng mang "Reference
   label printed on the document." Mô tả khi ấy mang zero thông tin phân
   biệt, và tệ hơn: nó nói sai về trường.
2. **Fallback chung chung** -- câu `pipeline/kie.py::describe` trả về khi
   không tìm được gì tốt hơn. Đúng ngữ pháp, vô dụng.
3. **Chung giữa loại giấy** -- một câu dùng cho hầu hết loại giấy thì nó
   không còn tả loại giấy nào.

## Khác `synthgen/check.py` ở chỗ nào

`check.py` kiểm TỪNG bản ghi: hộp có trong trang không, số có khớp không. Ba
cổng ở đây là câu hỏi GIỮA các bản ghi -- không bản ghi nào một mình sai, cả
bộ mới sai. Hai câu hỏi khác nhau nên hai công cụ; nhét cổng liên-bản-ghi vào
`check_record` là ép một hàm trả lời câu nó không thấy đủ dữ liệu để trả lời.

## KHÔNG nuốt lỗi

Số file đọc không được được ĐẾM và in TRƯỚC mọi con số khác. Một phép đo lặng
lẽ bỏ qua một phần dữ liệu rồi báo "sạch" là thứ tệ hơn không đo -- kho này đã
bị đúng một lần, khi một script đo im lặng bỏ 182 tờ hỏng.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GATES_FILE = REPO_ROOT / "rulebase" / "synthgen" / "_kie_gates.yaml"

# Mọi chuỗi số thành `#`, nên `line_items_7_name` và `line_items_8_name` là
# MỘT cột logic. Đây là ranh giới giữa "bốn mươi dòng của một bảng lặp một
# câu" (đúng, chúng cùng nghĩa) và "hai trường khác nhau cùng một câu" (sai).
# Không có phép gộp này thì cổng báo đỏ cho mọi bảng dài, và một cổng kêu
# đúng cái không hỏng là một cổng người ta sẽ tắt.
_DIGITS = re.compile(r"\d+")


def logical(field) -> str:
    return _DIGITS.sub("#", str(field or ""))


def load_gates(path: Path | None = None) -> dict:
    """Ngưỡng và mẫu câu. Mất file thì DỪNG, không chạy với ngưỡng đoán."""
    path = path or GATES_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "thresholds" not in data:
        raise SystemExit(f"[kie-gate] {path} không phải bảng ngưỡng hợp lệ")
    return data


def text_of(value) -> str:
    """Mô tả về một CHUỖI.

    `description` trong kho có hai hình dạng: chuỗi (67.585 lần) và list
    `[kind, câu]` (98 lần, chỉ pilot10/11 -- một tuple bị ghi nhầm vào ô mô
    tả). Gộp cả hai về chuỗi để ĐẾM ĐƯỢC, và đếm riêng số ca dạng list để
    người đọc thấy nó tồn tại: bỏ qua là giấu mất một lỗi thật.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return text_of(value[-1]) if value else ""
    if isinstance(value, dict):
        return text_of(value.get("text") or value.get("description"))
    return ""


# Tên file bộ sinh đặt ra: `llm_<loại giấy>_0007.json`, `hoa_don_gtgt_00012_p2`.
# Cắt tiền tố `llm_` và đuôi số (kèm `_pN` nếu là trang sau) thì còn LOẠI GIẤY.
_STEM_TYPE = re.compile(r"^(?:llm_)?(?P<kind>.+?)_\d+(?:_p\d+)?$")


def doc_type(path: Path) -> str:
    """Loại giấy của một bản ghi.

    Đọc TÊN FILE trước, thư mục sau. Thư mục là câu trả lời đúng ở mọi bộ
    hiện có -- `records/<loại>/<file>.json` -- nhưng nó là câu trả lời về
    CÁCH XẾP FILE, không phải về tài liệu. Một bộ xếp phẳng thì mọi bản ghi
    cùng một "loại" tên `records`, và cổng "câu dùng chung nhiều loại giấy"
    sẽ báo 0% cho một bộ trùng hoàn toàn -- một cổng xanh vì phép đo mù.
    """
    found = _STEM_TYPE.match(path.stem)
    if found:
        return found.group("kind")
    parent = path.parent.name
    return "" if parent == "records" else parent


def records_under(root: Path) -> list[Path]:
    """Mọi bản ghi của một bộ, dù bộ ấy xếp thư mục kiểu nào."""
    found = sorted(root.rglob("*.json"))
    return [p for p in found if "records" in p.parts]


def scan(roots: list[Path], gates: dict) -> dict:
    generic = [re.compile(p, re.I) for p in (gates.get("generic") or ())]
    floor = int(gates.get("min_useful_chars") or 0)

    total = broke = listed = short = 0
    per_doc_clash = 0
    docs = 0
    columns: set[tuple[str, str]] = set()   # (bộ, cột logic)
    collapsed: set[tuple[str, str]] = set()
    generic_hits = 0
    by_text_type: dict[str, set[str]] = collections.defaultdict(set)
    worst: list[tuple[int, str, str, list[str]]] = []
    every = collections.Counter()

    for root in roots:
        for path in records_under(root):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:                              # noqa: BLE001
                broke += 1
                continue
            docs += 1
            kind = doc_type(path) or path.parent.name
            seen: dict[str, set[str]] = collections.defaultdict(set)
            for pair in (record.get("kie") or {}).get("pairs") or []:
                raw = pair.get("description")
                if raw is None:
                    continue
                if isinstance(raw, (list, tuple)):
                    listed += 1
                text = text_of(raw)
                if not text:
                    continue
                total += 1
                every[text] += 1
                if any(p.search(text) for p in generic):
                    generic_hits += 1
                if len(text) < floor:
                    short += 1
                by_text_type[text].add(kind)
                column = logical(pair.get("field"))
                if column:
                    columns.add((str(root), column))
                    seen[text].add(column)
            clash = {t: c for t, c in seen.items() if len(c) > 1}
            if clash:
                per_doc_clash += 1
                for cols in clash.values():
                    collapsed |= {(str(root), c) for c in cols}
                big = max(clash.items(), key=lambda kv: len(kv[1]))
                worst.append((len(big[1]), str(path), big[0], sorted(big[1])))

    shared = sum(1 for kinds in by_text_type.values() if len(kinds) > 1)
    worst.sort(key=lambda row: -row[0])
    return dict(
        docs=docs, broke=broke, total=total, listed=listed, short=short,
        distinct=len(every), columns=len(columns), collapsed=len(collapsed),
        clash_docs=per_doc_clash, generic=generic_hits,
        shared=shared, texts=len(by_text_type), worst=worst,
        top=every.most_common(5))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, nargs="+",
                        help="một hay nhiều thư mục bộ đã sinh")
    parser.add_argument("--show", type=int, default=3,
                        help="số ca nặng nhất in ra cho cổng gộp nghĩa")
    parser.add_argument("--gates", type=Path, default=None,
                        help="bảng ngưỡng khác (mặc định _kie_gates.yaml)")
    args = parser.parse_args()

    gates = load_gates(args.gates)
    limit = gates["thresholds"]
    got = scan(list(args.run), gates)

    if got["broke"]:
        print(f"[kie-gate] !! {got['broke']} file ĐỌC KHÔNG ĐƯỢC -- sửa trước "
              f"khi đọc con số nào bên dưới")
    if not got["total"]:
        print("[kie-gate] không có mô tả nào để kiểm")
        return 1

    print(f"[kie-gate] {got['docs']} bản ghi | {got['total']} mô tả | "
          f"{got['distinct']} chuỗi khác nhau "
          f"({got['distinct'] / got['total']:.1%})")
    if got["listed"]:
        print(f"[kie-gate] {got['listed']} mô tả ghi dạng LIST `[kind, câu]` "
              f"-- tuple lọt vào ô mô tả, `field` đã mang khoá ấy rồi")
    if got["short"]:
        print(f"[kie-gate] {got['short']} mô tả ngắn hơn "
              f"{gates.get('min_useful_chars')} ký tự (đếm, không phải cổng)")

    rows = [
        ("cột logic bị gộp nghĩa",
         got["collapsed"] / max(got["columns"], 1),
         limit["collapsed_columns"],
         f"{got['collapsed']}/{got['columns']} cột, "
         f"{got['clash_docs']}/{got['docs']} bản ghi"),
        ("mô tả là câu fallback",
         got["generic"] / got["total"], limit["generic_descriptions"],
         f"{got['generic']}/{got['total']} mô tả"),
        ("câu dùng chung >=2 loại giấy",
         got["shared"] / max(got["texts"], 1), limit["shared_across_types"],
         f"{got['shared']}/{got['texts']} câu"),
    ]
    print()
    print(f"  {'cổng':32s} {'đo được':>9s} {'trần':>7s}  {'':4s} chi tiết")
    red = 0
    for name, value, cap, detail in rows:
        ok = value <= float(cap)
        red += 0 if ok else 1
        print(f"  {name:32s} {value:8.1%} {float(cap):6.1%}  "
              f"{'XANH' if ok else 'ĐỎ  '} {detail}")

    if got["worst"] and args.show:
        print("\n  nặng nhất -- cột khác nhau chung một mô tả:")
        for n, path, text, cols in got["worst"][:args.show]:
            print(f"    {n} cột | {Path(path).name}")
            print(f'      "{text[:64]}"')
            print(f"      {cols[:6]}")

    print(f"\n  5 câu bị lặp nhiều nhất:")
    for text, n in got["top"]:
        print(f"    {n:6d}  {text[:66]}")

    print(f"\n[kie-gate] {'MỌI CỔNG XANH' if not red else str(red) + ' CỔNG ĐỎ'}")
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())
