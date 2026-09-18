#!/usr/bin/env python3
"""Thay mô tả trường trong `kie` của một lượt chạy đã vẽ xong, không vẽ lại.

    python tools/kie_backfill.py data/llm200_v3

`pipeline/kie.py` đọc mô tả từ file mà `VLM_KIE_DESCRIPTIONS` trỏ tới, và biến
ấy phải có TRƯỚC khi lượt chạy bắt đầu. Lượt nào đã chạy mà thiếu nó thì mọi
trường mang mô tả dự phòng — chính chữ in trên giấy, "Mẫu số" mô tả là "Mẫu
số", không thêm thông tin nào cho một mô hình chưa từng thấy chứng từ Việt Nam.

Sửa lại bằng cách vẽ lại 200 tờ là trả giá bằng hàng chục phút render cho một
thay đổi không đụng tới một pixel nào. Bản ghi là JSON, mô tả nằm ở hai chỗ
trong đó (`kie.pairs[].description` và `kie.schema.properties[].description`),
và cả hai đều là hàm thuần của `field` — nên viết lại tại chỗ là đúng phép,
không phải đường tắt.

Chỉ đụng vào hai chỗ ấy. Hộp, chữ, quan hệ nhãn–giá trị: không.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
GLOSSARY = REPO / "rulebase" / "kie_field_glossary.json"

from rulebase import kie_glossary  # noqa: E402


def backfill(record: dict, tables: tuple[dict[str, str], dict[str, str]]) -> int:
    """Số trường đã thay mô tả trong một bản ghi.

    Tra qua `rulebase/kie_glossary.py` chứ không tra thẳng bảng phẳng: bảng ấy
    khoá theo slug caption, mà slug caption là từ vựng mở nên không bao giờ đủ.
    `kind` của entity là từ vựng đóng và là mức sàn."""
    kie = record.get("kie")
    if not isinstance(kie, dict):
        return 0
    by_slug, by_kind = tables
    entities = record.get("entity_annotations") or []
    changed = 0
    properties = ((kie.get("schema") or {}).get("properties") or {})
    for pair in kie.get("pairs") or []:
        field = str(pair.get("field", ""))
        index = pair.get("key_entity_index")
        kind = ""
        if isinstance(index, int) and 0 <= index < len(entities):
            kind = str((entities[index] or {}).get("kind") or "")
        found = kie_glossary.describe(field, kind=kind,
                                      by_slug=by_slug, by_kind=by_kind)
        description = found[0] if found else ""
        if not description or pair.get("description") == description:
            continue
        pair["description"] = description
        # `llm` là giá trị đúng: mô tả này do một mô hình viết, chỉ là viết ra
        # thành file thay vì gọi qua HTTP lúc chạy. `fallback` nghĩa là "không
        # ai viết, đây là chữ trên giấy", và để nguyên nó sẽ là một lời khai sai
        # về nguồn gốc của chính dòng chữ vừa thay.
        pair["description_source"] = "llm"
        if field in properties and isinstance(properties[field], dict):
            properties[field]["description"] = description
        changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="thư mục lượt chạy đã vẽ xong")
    parser.add_argument("--glossary", type=Path, default=GLOSSARY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tables = kie_glossary.load(args.glossary)
    files = [p for p in sorted(args.run.rglob("*.json"))
             if p.name not in ("synthesis.json", "agent_plan.json",
                               "agent_report.json", "plan.json",
                               "kie_descriptions.json", "content_overrides.json")]
    records = fields = 0
    missing: dict[str, int] = {}
    for path in files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(record, dict) or "kie" not in record:
            continue
        entities = record.get("entity_annotations") or []
        for pair in (record.get("kie") or {}).get("pairs") or []:
            field = str(pair.get("field", ""))
            index = pair.get("key_entity_index")
            kind = ""
            if isinstance(index, int) and 0 <= index < len(entities):
                kind = str((entities[index] or {}).get("kind") or "")
            if field and kie_glossary.describe(field, kind=kind, by_slug=tables[0],
                                               by_kind=tables[1]) is None:
                missing[field] = missing.get(field, 0) + 1
        count = backfill(record, tables)
        if count and not args.dry_run:
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        records += 1
        fields += count

    print(f"[kie] {records} bản ghi · {fields} trường có mô tả tiếng Anh"
          + ("  (thử, chưa ghi)" if args.dry_run else ""))
    if missing:
        top = sorted(missing.items(), key=lambda kv: -kv[1])[:15]
        print(f"[kie] {len(missing)} slug chưa có nghĩa trong từ điển — "
              "thêm vào rulebase/kie_field_glossary.json:")
        for field, count in top:
            print(f"        {field:44s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
