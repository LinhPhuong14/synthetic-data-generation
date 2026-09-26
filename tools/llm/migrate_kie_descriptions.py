#!/usr/bin/env python3
"""Di trú `kie_descriptions.json` từ hình 1 sang hình 2, KHÔNG mất một câu nào.

    python3 tools/llm/migrate_kie_descriptions.py data/review100d
    python3 tools/llm/migrate_kie_descriptions.py --all --write

Mặc định chỉ ĐO và in ra; `--write` mới ghi đè (giữ bản cũ ở `*.v1.json`).

## Bảng cũ sai hình như thế nào

Hình 1 là `{loại giấy: {trường: câu}}`. Hai phép nhân nằm trong chính cách
`synthgen/descriptions.py::tables` dựng nó:

  * mỗi trường được chép qua sáu hậu tố `''`, `_2`..`_6`, vì một nhãn in
    nhiều lần trên một trang thì `pipeline/kie.py::pair_fields` đánh số nó;
  * toàn bộ nền dùng chung (`_shared`) được chép vào TỪNG loại giấy.

Đo trên `data/review100d/kie_descriptions.json`: 63.060 cặp khoá→câu, 171
loại giấy, 368,8 khoá mỗi loại -- và đúng **247** câu khác nhau. Tức 62.813
dòng trong số đó là bản sao của một trong 247 câu.

Cái giá không phải dung lượng. Một bảng 63.060 dòng cho 247 câu là bảng mà
không ai soát được, một câu sai phải sửa ở tới sáu trăm chỗ, và -- đúng thứ
`AGENTS.md` mục 5 cấm -- nó là bảng phẳng mà loại giấy thứ 172 sẽ thiếu
khỏi, im lặng.

## Hình 2

    {"_schema": 2,
     "_shared": {khoá gốc: câu},           # câu dùng ở >= 2 loại giấy
     "layouts": {loại giấy: {khoá gốc: câu}}}   # chỉ khoá KHÁC `_shared`

`pipeline/kie.py::_table_for` đọc được cả hai hình, nên bộ cũ trên đĩa vẫn
dùng được mà không phải sinh lại.

## Câu tả riêng cho từng lần xuất hiện

Hậu tố `_N` biến mất khỏi BẢNG, không biến mất khỏi NHÃN: nó nói lần xuất
hiện thứ mấy, và `pipeline/kie.py::_occurrence_note` dựng lại nó thành lớp
thứ hai của câu tả lúc xuất -- cùng phép ghép (`synthgen/field_tier.py::
compose`) mà nhánh LLM dùng. Ba `ma_so_thue` trên một hoá đơn ra ba câu khác
nhau sau khi di trú, trong khi bảng cũ cho chúng chung một câu.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen.descriptions import SCHEMA, base_key  # noqa: E402

_BLOB = re.compile(r"\s+")


def _blob(value) -> str:
    """Giá trị thành chuỗi so sánh được -- câu trần hay `{description,…}`."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def shrink(old: dict) -> dict:
    """Hình 1 -> hình 2. Không quyết định gì ngoài việc BỎ BẢN SAO."""
    base: dict[str, dict] = {}
    for layout, fields in old.items():
        mine: dict[str, object] = {}
        for field, text in (fields or {}).items():
            mine.setdefault(base_key(field), text)
        base[layout] = mine

    times: dict[tuple[str, str], int] = {}
    for fields in base.values():
        for field, text in fields.items():
            key = (field, _blob(text))
            times[key] = times.get(key, 0) + 1
    shared = {field: json.loads(blob)
              for (field, blob), n in times.items() if n >= 2}

    layouts = {}
    for layout, fields in base.items():
        mine = {f: t for f, t in fields.items()
                if not (f in shared and _blob(shared[f]) == _blob(t))}
        if mine:
            layouts[layout] = mine
    return {"_schema": SCHEMA, "_shared": shared, "layouts": layouts}


def verify(old: dict, new: dict) -> list[str]:
    """MỌI (loại giấy, trường) của bảng cũ phải tra ra ĐÚNG câu cũ qua bảng mới.

    Đây là phần đáng giá nhất của script. Một phép di trú "hình như đúng" là
    đúng thứ kho này đã bị cắn: bảng nhỏ đi, không ai kiểm, và sáu tháng sau
    một trường tra ra câu của trường khác. Kiểm hết, không lấy mẫu."""
    shared = new.get("_shared") or {}
    layouts = new.get("layouts") or {}
    bad: list[str] = []
    for layout, fields in old.items():
        table = {**shared, **(layouts.get(layout) or {})}
        for field, text in (fields or {}).items():
            got = table.get(field)
            if got is None:
                got = table.get(base_key(field))
            if got is None:
                bad.append(f"{layout}/{field}: MẤT HẲN")
            elif _blob(got) != _blob(text):
                bad.append(f"{layout}/{field}: câu đổi")
    return bad


def rows(table: dict) -> int:
    if table.get("_schema") == SCHEMA:
        return (len(table.get("_shared") or {})
                + sum(len(v) for v in (table.get("layouts") or {}).values()))
    return sum(len(v or {}) for v in table.values())


def sentences(table: dict) -> int:
    """Số câu KHÁC NHAU -- con số phải không đổi qua phép di trú."""
    out = set()
    if table.get("_schema") == SCHEMA:
        for one in [table.get("_shared") or {},
                    *(table.get("layouts") or {}).values()]:
            out |= {_blob(t) for t in one.values()}
    else:
        for fields in table.values():
            out |= {_blob(t) for t in (fields or {}).values()}
    return len(out)


def migrate(path: Path, write: bool) -> int:
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"  ✗ {path}: không đọc được -- {error}")
        return 1
    if not isinstance(old, dict):
        print(f"  ✗ {path}: không phải object")
        return 1
    if old.get("_schema") == SCHEMA:
        print(f"  · {path}: đã là hình {SCHEMA}, bỏ qua")
        return 0

    new = shrink(old)
    bad = verify(old, new)
    before, after = rows(old), rows(new)
    said_before, said_after = sentences(old), sentences(new)
    print(f"  {path}")
    print(f"      dòng  {before:>7} -> {after:<7} ({1 - after / before:.1%} bớt)"
          if before else "      bảng rỗng")
    print(f"      câu   {said_before:>7} -> {said_after:<7}"
          f"{'  ✓ không mất câu nào' if said_before == said_after else '  ✗ MẤT CÂU'}")
    if bad:
        # KÊU, không ghi. Một bảng di trú sai còn tệ hơn một bảng to.
        print(f"      ✗ {len(bad)} trường tra sai sau di trú; 5 ca đầu:")
        for line in bad[:5]:
            print(f"          {line}")
        return 1
    if said_before != said_after:
        return 1
    if write:
        keep = path.with_suffix(".v1.json")
        if not keep.exists():
            keep.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        print(f"      ✓ đã ghi; bản cũ giữ ở {keep.name}")
    else:
        print("      (chưa ghi -- thêm `--write`)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*", type=Path,
                    help="thư mục bộ dữ liệu, hoặc chính tệp kie_descriptions.json")
    ap.add_argument("--all", action="store_true",
                    help="mọi data/*/kie_descriptions.json")
    ap.add_argument("--write", action="store_true",
                    help="ghi đè thật (bản cũ giữ ở *.v1.json)")
    args = ap.parse_args()

    paths: list[Path] = []
    if args.all:
        paths = sorted((REPO_ROOT / "data").glob("*/kie_descriptions.json"))
    for root in args.roots:
        paths.append(root if root.is_file() else root / "kie_descriptions.json")
    paths = [p for p in dict.fromkeys(paths) if p.exists()]
    if not paths:
        print("không có `kie_descriptions.json` nào", file=sys.stderr)
        return 1

    print(f"# Di trú {len(paths)} bảng sang hình {SCHEMA}\n")
    bad = sum(migrate(p, args.write) for p in paths)
    print(f"\n{len(paths) - bad}/{len(paths)} bảng di trú được"
          + ("" if args.write else "  (chạy lại với `--write` để ghi)"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
