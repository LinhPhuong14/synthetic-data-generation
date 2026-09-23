#!/usr/bin/env python3
"""So NHIỀU LƯỢT CHẠY trên cùng một bộ thước. Không gọi model, không vẽ lại.

    python tools/llm/batches.py data/23-09-llm-*
    python tools/llm/batches.py data/23-09-llm-f data/23-09-llm-h --rows

## Vì sao cần

`compose_report.json` in ra tỉ lệ qua cổng, và một mình nó nói dối theo hai
chiều. Lô `g` đọc lên là "1/12 qua cổng" trong khi nó xuất ra 12 tài liệu và
547 trường -- vì "qua cổng" đếm ở cổng CHỮ, còn cái loại tờ sau đó là phép đo
SỐ TỜ chạy muộn hơn. Ngược lại một lô 10/12 có thể toàn tờ một trang.

Nên đọc thẳng thứ ra đĩa, và đọc đủ bốn trục mà một bộ OCR/KIE sống chết vì
chúng:

* **có chữ thì có hộp** -- đoạn chữ hiển thị nào không nằm trong `<span
  data-kind>` nào. Mô hình học trên bộ ấy thấy mực mà nhãn bảo không có gì --
  đúng hạng mục olmOCR-Bench chấm bằng *text presence*;
* **số tờ** -- phân bố thật, không phải số đã xin;
* **KIE** -- bao nhiêu cặp mỗi trang, và bao nhiêu phần trăm có nhãn IN thật
  (cặp `implied` vẫn hợp lệ nhưng không dạy được quan hệ nhãn↔giá trị);
* **ngôn ngữ câu tả** -- một bộ lẫn hai thứ tiếng cho cùng một trường là bộ
  dạy mô hình hai điều khác nhau về một khái niệm.

## Vì sao phép nhận ngôn ngữ bỏ phần trích

Câu tả hay nhét chữ IN TRÊN GIẤY vào giữa một câu tiếng Anh: `The person
signing as "THƯ KÝ" on this document.` Đếm dấu trên cả chuỗi thì câu ấy thành
"tiếng Việt". Đo được: 19 câu gốc trong kho bị nhận nhầm đúng kiểu ấy.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VN_MARKS = "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
QUOTED = re.compile(r"[“\"'‘][^”\"'’]*[”\"'’]")
SKIP_TEXT = frozenset({"style", "script", "title", "head"})
VOID = frozenset({"br", "img", "hr", "input", "meta", "link", "source", "col"})


def language_of(say: str) -> str:
    """`vi` hoặc `en` cho một CÂU, bỏ mọi phần trích dẫn."""
    body = QUOTED.sub(" ", str(say or "")).lower()
    return "vi" if any(ch in body for ch in VN_MARKS) else "en"


class _Unlabelled:
    """Chữ hiển thị KHÔNG nằm trong `<span data-kind>` nào.

    Quét tuyến tính tự giữ ngăn xếp, không dùng `HTMLParser`: cùng lý do
    `synthgen/llm_page.py::outside_sheet` đã ghi -- bộ phân tích chuẩn đẩy thẻ
    rỗng vào ngăn xếp mà không ai lấy ra, và từ đó mọi phép hỏi tổ tiên lệch
    một tầng mà không ai thấy."""

    TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>")

    def __init__(self, html: str) -> None:
        self.bare: list[str] = []
        stack: list[tuple[str, bool, bool]] = []
        at = 0
        for match in self.TAG.finditer(html):
            text = html[at:match.start()].strip()
            if text and stack:
                _tag, run, skip = stack[-1]
                if not skip and not run:
                    self.bare.append(text[:60])
            at = match.end()
            closing, tag = match.group(1), match.group(2).lower()
            attrs, selfclose = match.group(3), match.group(4)
            if tag in VOID or selfclose:
                continue
            if closing:
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == tag:
                        del stack[i:]
                        break
                continue
            top = stack[-1] if stack else ("", False, False)
            stack.append((tag, top[1] or "data-kind" in attrs,
                          top[2] or tag in SKIP_TEXT))


def measure(root: Path) -> dict:
    """Một lượt chạy -> các con số so được."""
    report = root / "compose_report.json"
    out: dict = {"tên": root.name}
    if report.is_file():
        try:
            got = json.loads(report.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            got = {}
        out["xin"] = got.get("asked", 0)
        out["qua cổng chữ"] = got.get("kept", 0)
        out["token/tờ"] = got.get("tokens_out_per_page", 0)
        out["sai số học"] = got.get("arithmetic_error_rate", 0.0)

    # SỐ TỜ THẬT: đếm ảnh, không tin lời khai.
    pages: Counter = Counter()
    for image in (root / "images").rglob("*.jpg"):
        pages[re.sub(r"_p\d+$", "", image.stem)] += 1
    out["_sheets"] = Counter(pages.values())
    out["tài liệu"] = len(pages)
    out["trang"] = sum(pages.values())

    # CÓ CHỮ THÌ CÓ HỘP.
    bare = clean = sheets = 0
    for page in list((root / "html").rglob("*.html")) + \
            list((root / "rejected").glob("*.html")):
        found = _Unlabelled(page.read_text(encoding="utf-8")).bare
        bare += len(found)
        clean += not found
        sheets += 1
    out["chữ không nhãn/tờ"] = round(bare / sheets, 2) if sheets else 0.0
    out["tờ sạch %"] = round(clean / sheets * 100, 1) if sheets else 0.0

    # KIE.
    pairs: list[int] = []
    printed = total = 0
    langs: Counter = Counter()
    seen: set[str] = set()
    for record in (root / "records").rglob("*.json"):
        try:
            got = json.loads(record.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        stem = re.sub(r"_p\d+$", "", record.stem)
        if stem in seen:
            continue
        seen.add(stem)
        on = (got.get("kie") or {}).get("pairs") or []
        pairs.append(len(on))
        for pair in on:
            total += 1
            printed += bool(pair.get("key_bbox"))
            say = str(pair.get("description") or "")
            if say:
                langs[language_of(say)] += 1
    out["cặp KIE/tài liệu"] = statistics.median(pairs) if pairs else 0
    out["nhãn IN %"] = round(printed / total * 100, 1) if total else 0.0
    said = sum(langs.values())
    out["câu tả tiếng Anh %"] = round(langs["en"] / said * 100, 1) if said else 0.0
    return out


ROWS = ("xin", "qua cổng chữ", "tài liệu", "trang", "token/tờ",
        "chữ không nhãn/tờ", "tờ sạch %", "cặp KIE/tài liệu", "nhãn IN %",
        "câu tả tiếng Anh %", "sai số học")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--rows", action="store_true",
                        help="in thêm phân bố số tờ")
    args = parser.parse_args(argv)

    sides = [measure(r) for r in args.roots if r.is_dir()]
    if not sides:
        print("không thư mục nào đọc được", file=sys.stderr)
        return 2
    width = max(len(s["tên"]) for s in sides) + 2

    print("\n=== SO CÁC LƯỢT CHẠY ===\n")
    head = f"{'chỉ số':<22}" + "".join(f"{s['tên']:>{width}}" for s in sides)
    print(head)
    print("-" * len(head))
    for key in ROWS:
        cells = "".join(f"{s.get(key, 0):>{width}}" for s in sides)
        print(f"{key:<22}{cells}")

    print(f"\n{'phân bố SỐ TỜ':<22}")
    every = sorted({n for s in sides for n in s["_sheets"]})
    for n in every:
        cells = "".join(f"{s['_sheets'].get(n, 0):>{width}}" for s in sides)
        print(f"  {n} tờ{'':<16}{cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
