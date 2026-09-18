#!/usr/bin/env python3
"""Trải bộ từ điển nghĩa trường ra thành file `VLM_KIE_DESCRIPTIONS` đọc được.

    python tools/kie_descriptions.py -o data/<run>/kie_descriptions.json

`pipeline/kie.py` tra mô tả theo LAYOUT (`{layout: {field: description}}`), vì
"cái nhãn này nghĩa là gì" là tính chất của tờ giấy chứ không của trường —
"Số:" trên hoá đơn và "Số:" trên công văn là hai thứ khác nhau. Nhưng phần lớn
slug thì nghĩa giống nhau ở mọi tờ, nên nguồn viết tay là MỘT từ điển phẳng
(`rulebase/kie_field_glossary.json`) và file này trải nó ra mọi layout.

Vì sao phải có file này thay vì để `_fallback_description`: fallback chép lại
chính chữ in trên giấy — "Mẫu số" mô tả là "Mẫu số". Với một mô hình chưa từng
thấy chứng từ Việt Nam thì đó là không thêm thông tin nào. Mô tả thật phải nói
giá trị ấy LÀ GÌ và ai cấp, bằng tiếng Anh, vì đó là ngôn ngữ chú thích của
schema chứ không phải ngôn ngữ của tờ giấy.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
GLOSSARY = REPO / "rulebase" / "kie_field_glossary.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()

    glossary = {k: v for k, v in
                json.loads(GLOSSARY.read_text(encoding="utf-8")).items()
                if not k.startswith("_")}
    import rulebase
    layouts = sorted(rulebase.every_layout())
    # Cùng một từ điển dưới mọi layout: trường nào tờ ấy không in thì không ai
    # tra tới, và một bản sao thừa rẻ hơn nhiều so với một bảng thiếu.
    out = {layout: dict(glossary) for layout in layouts}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"[kie] {len(glossary)} nghĩa × {len(layouts)} bố cục -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
