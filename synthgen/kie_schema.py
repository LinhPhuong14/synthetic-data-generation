"""KIE viết lại thành JSON Schema, kèm bản giá trị khớp schema ấy.

`kie.pairs` là danh sách cặp có HỘP -- đúng thứ cần để chấm định vị. Nhưng
một mô hình sinh JSON có ràng buộc (vLLM/xgrammar, structured outputs) không
ăn danh sách cặp: nó ăn một **schema**, rồi trả về một **instance** khớp
schema. Hai thứ ấy dựng ở đây, và KHÔNG thay `pairs` -- schema không mang toạ
độ, nên thay là mất sạch phần định vị vừa dựng.

    record["kie"]["schema"]  ->  JSON Schema của tờ giấy này
    record["kie"]["value"]   ->  giá trị thật, khớp schema trên
    record["kie"]["pairs"]   ->  giữ nguyên, vẫn có hộp

Ba quyết định đáng nói:

* **Bảng thành một mảng, không thành trăm trường.** Một hoá đơn bốn mươi dòng
  có hơn hai trăm ô; đổ chúng thành `qty_r1`, `qty_r2`, … là một schema hai
  trăm trường mà không mô hình nào sinh nổi, và mỗi tờ giấy một schema khác.
  Gộp thành `line_items: array of object` thì schema chỉ phụ thuộc BỘ CỘT,
  còn số dòng là chuyện của dữ liệu.
* **Kiểu suy từ NGHĨA, không từ hình dạng chuỗi.** "0909954657" trông như số
  nhưng là số điện thoại; "4.551.901.200 đ" trông như chữ nhưng là tiền. Nên
  `number` chỉ dành cho những `kind` vốn là số -- cột tiền, cột lượng, dòng
  cộng -- và ngay cả thế, chuỗi nào không đọc ra số vẫn tụt về `string`
  ("Không chịu thuế" là một giá trị hợp lệ của dòng thuế).
* **Bỏ phần khung của bảng.** `column_heading`, `column_number`, `row_group`
  là chữ in ra để NGƯỜI đọc bảng, không phải trường để trích. Chúng vẫn nằm
  đủ trong `pairs` kèm hộp; đưa vào schema chỉ tổ bảo mô hình đi trích lại
  cái tên cột mà chính schema đã nói.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen.design import COLUMNS  # noqa: E402
from synthgen.phrasing import describe as phrase  # noqa: E402

# Câu tả chính cái MẢNG dòng hàng -- không thuộc cột nào nên không nằm trong
# `COLUMNS`, và vì thế từng là câu duy nhất trong schema không ai đổi giọng.
ITEMS_DESCRIBE = "Rows of the item table printed on this document."

# Cột mang SỐ. `stt` là số thứ tự nên là số nguyên; `vat_rate` in ra "10%"
# hoặc "KCT" nên vẫn là chuỗi.
NUMBER_COLUMNS = {"qty", "unit_price", "amount", "vat_amount", "discount",
                  "copay", "fund"}
INTEGER_COLUMNS = {"stt"}

# `kind` của thực thể mà giá trị vốn là một con số tiền.
NUMBER_KINDS = {"total.line", "total.grand", "total.group_amount",
                "summary.gross"}

# Chữ in ra để đọc bảng, không phải trường để trích.
STRUCTURE = {"column_heading", "column_number", "row_group"}

GROUPS_PATH = REPO_ROOT / "rulebase" / "kie_groups.json"


def groups() -> tuple[dict[str, dict], int]:
    """`({tiền tố kind: {name, describe}}, số trường tối thiểu)`.

    Đọc từ `rulebase/kie_groups.json` chứ không viết trong Python: đây là một
    bảng CẤU HÌNH -- ai thêm một nhóm không nên phải sửa mã, cùng lối
    `rulebase/kie_field_glossary.json` và mọi thứ khác trong `rulebase/`.

    Khoá theo TIỀN TỐ của `data-kind`, không theo tên trường in trên giấy.
    `kind` là từ vựng đóng do code sinh, còn tên in ra là tiếng Việt tự do --
    đo được 99 tên khác nhau chỉ riêng họ `invoice.` trên tám mươi tờ. Khoá
    theo thứ đóng thì một loại chứng từ mới dùng lại nhóm cũ miễn phí."""
    import json as _json                                       # noqa: PLC0415

    try:
        data = _json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Thiếu file thì schema phẳng -- đúng hành vi trước khi có nhóm. Một
        # bảng cấu hình hỏng không được làm hỏng cả lượt sinh.
        return {}, 2
    return (dict(data.get("groups") or {}), int(data.get("min_fields") or 2))

ITEMS = "line_items"

# `items[13].vat` -> chỉ số 13. Nhận cả `items.13.vat`, dạng model
# thỉnh thoảng viết ra khi bỏ ngoặc.
_INDEX = re.compile(r"\[(\d+)\]|\.(\d+)(?=\.|$)")


def _number(text: str) -> int | None:
    """"4.551.901.200 đ" -> 4551901200. None nếu không có chữ số nào.

    Bỏ mọi thứ không phải chữ số: dấu chấm phân cách nghìn, khoảng trắng,
    hậu tố "đ"/"đồng"/"kWh". Không có chữ số thì đây không phải một con số --
    "Không chịu thuế" là giá trị hợp lệ của dòng thuế, và ép nó thành 0 là
    bịa ra một con số tờ giấy không in."""
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def _kind_of(record: dict) -> dict[int, str]:
    return {e["entity_index"]: str(e.get("kind", ""))
            for e in record.get("entity_annotations") or []}


def build(record: dict, page: int | None = None) -> tuple[dict, dict]:
    """`(schema, value)` từ chính `kie.pairs`.

    `page=None` tả CẢ tài liệu; `page=n` chỉ tả tờ thứ `n`.

    Cần cả hai vì bản ghi được chép bên cạnh TỪNG TỜ. Một hoá đơn ba tờ có
    ba file json giống hệt nhau, nên bản tả-cả-tài-liệu nằm trong file của tờ
    một sẽ kể cả những dòng hàng chỉ có trên tờ ba -- huấn luyện một mô hình
    nhìn MỘT ảnh bằng cặp ấy là dạy nó bịa ra thứ không có trong ảnh."""
    pairs = (record.get("kie") or {}).get("pairs") or []
    # Cùng hạt giống `derive.py` dùng cho `kie.pairs`, nên schema và danh sách
    # cặp của một file nói cùng một giọng.
    seed = record.get("job_id") or record.get("filename", "")
    if page is not None:
        pairs = [p for p in pairs if int(p.get("page_number", 1) or 1) == page]
    kinds = _kind_of(record)

    # ---------------------------------------------------------- dòng hàng
    rows: dict[int, dict] = {}
    columns: dict[str, dict] = {}
    for pair in pairs:
        # Ô BẢNG LÀ Ô BẢNG, DÙ TÊN NÓ ĐẾN TỪ ĐÂU.
        #
        # Bản trước gác bằng `source == "table"`. Nhưng từ khi đường khai đi
        # trước (xem `kie_full.complete`), một ô bảng mà model có khai
        # `data-path` sẽ mang `source: "declared"` -- nó vẫn là ô bảng, vẫn có
        # `column` và `row`, chỉ khác chỗ lấy tên.
        #
        # Đo trên `llm_vat_return_0003`: 41 trên 42 cặp `items[...]` mang đủ
        # `column` và `row` mà vẫn rơi vào vòng trường phẳng, thành
        # `items_0_name`, `items_0_qty`... -- 50 thuộc tính cho một tờ, trong
        # khi `line_items` bên cạnh đã mang đúng cái bảng ấy dạng mảng. Cùng
        # một bảng nằm trong schema hai lần, và bốn mươi mốt câu tả là một câu
        # duy nhất chép lại: "Value bound to `items[0].name`...".
        #
        # Gác bằng CHỖ NGỒI thay vì nguồn tên: có cột và có dòng thì là ô bảng.
        column = str(pair.get("column") or "")
        if not column or pair.get("row") is None:
            continue
        spec = COLUMNS.get(column) or {}
        if column in INTEGER_COLUMNS:
            kind = "integer"
        elif column in NUMBER_COLUMNS:
            kind = "number"
        else:
            kind = "string"
        # Mô tả lấy từ CHÍNH CẶP, không từ `COLUMNS[...]["describe"]`. Cặp đã
        # qua `phrasing.describe` nên mỗi tài liệu một giọng; đọc lại câu gốc ở
        # đây là dựng lại đúng cái vừa bỏ -- đo được: `line_items.qty` y hệt
        # nhau trên cả hai mươi nghìn trang trong khi `kie.pairs` của cùng file
        # đã có bốn cách nói. Mọi ô của một cột cùng một câu (khoá theo cột),
        # nên lấy câu của ô đầu tiên là lấy câu của cả cột.
        columns.setdefault(column, {
            "type": kind,
            "description": (str(pair.get("description") or "")
                            or spec.get("describe")
                            or f"Table column {column}."),
        })
        row = rows.setdefault(int(pair.get("row") or 0), {})
        text = str(pair.get("value_text", ""))
        if kind == "string":
            row[column] = text
        else:
            number = _number(text)
            row[column] = number if number is not None else text

    # ------------------------------------------------------- trường phẳng
    # Đường dẫn khai sẵn mang CHỈ SỐ thì nó nói "đây là một hàng", y hệt ô
    # bảng -- chỉ khác là model khai bằng `data-path` chứ không ngồi trong
    # `<table>`, nên vòng trên không nhặt. Không gộp thì `items[13].vat` ra
    # một thuộc tính phẳng tên `items_13_vat`, và một bảng mười lăm dòng năm
    # cột thành bảy mươi lăm thuộc tính. Đo trên pilot15: schema lớn nhất 52
    # thuộc tính, 41 tên còn mang chữ số.
    #
    # `pipeline/kie.py::_folded` đã viết đúng luật này từ trước và chạy đúng,
    # nhưng `synthgen/derive.py:228` ghi đè cả `record["kie"]["schema"]` bằng
    # bản dựng ở đây, nên kết quả của nó không tới được bản ghi. Một luật,
    # hai người dựng -- nên chép luật sang, không chép schema về.
    listed: dict[str, dict[int, dict]] = {}
    listed_cols: dict[str, dict[str, dict]] = {}
    seen: dict[str, list] = {}
    described: dict[str, str] = {}
    typed: dict[str, str] = {}
    for pair in pairs:
        # Đối xứng với vòng trên: ô bảng đã vào mảng thì không vào đây nữa.
        if pair.get("column") and pair.get("row") is not None:
            continue
        field = str(pair.get("field") or "")
        if not field or field in STRUCTURE:
            continue
        text = str(pair.get("value_text", "")).strip()
        if not text:
            continue
        kind = kinds.get(pair.get("value_entity_index"), "")
        if kind in NUMBER_KINDS:
            number = _number(text)
            value, as_type = ((number, "number") if number is not None
                              else (text, "string"))
        else:
            value, as_type = text, "string"
        path = str(pair.get("path") or "")
        spot = _INDEX.search(path)
        if spot:
            root = path.split("[")[0].split(".")[0]
            leaf = _INDEX.sub("", path).split(".")[-1].strip(".") or root
            if root and leaf and leaf != root:
                listed.setdefault(root, {}).setdefault(
                    int(spot.group(1) or spot.group(2)), {})[leaf] = value
                listed_cols.setdefault(root, {}).setdefault(leaf, {
                    "type": as_type,
                    "description": str(pair.get("description", "")),
                })
                continue
        seen.setdefault(field, []).append(value)
        described.setdefault(field, str(pair.get("description", "")))
        # Một trường xuất hiện hai lần với hai kiểu thì kiểu chung là chuỗi:
        # `string` chứa được mọi thứ, `number` thì không.
        typed[field] = "string" if typed.get(field, as_type) != as_type else as_type

    # ------------------------------------------------- gom trường vào nhóm
    # Trường nào thuộc nhóm nào, theo `kind` của thực thể mang GIÁ TRỊ. Nhóm
    # chỉ dựng khi đủ `min_fields` trường khác nhau; dưới ngưỡng thì trường ở
    # lại tầng một, vì một đối tượng bọc đúng một trường chỉ làm đường dẫn dài
    # thêm một đoạn.
    spec, floor = groups()
    home: dict[str, str] = {}
    if spec:
        family: dict[str, set[str]] = {}
        for pair in pairs:
            if pair.get("source") == "table":
                continue
            field = str(pair.get("field") or "")
            if not field or field not in seen:
                continue
            kind = kinds.get(pair.get("value_entity_index"), "")
            for prefix in spec:
                if kind.startswith(prefix):
                    family.setdefault(prefix, set()).add(field)
                    break
        for prefix, fields in family.items():
            if len(fields) < floor:
                continue
            for field in fields:
                home[field] = prefix

    properties: dict[str, dict] = {}
    value: dict = {}
    nested: dict[str, dict] = {}
    nested_value: dict[str, dict] = {}
    for field, found in seen.items():
        description = described.get(field, "")
        # Trường có nhà thì đi vào nhà, không nằm ở tầng một.
        where = home.get(field)
        into = nested.setdefault(where, {}) if where else properties
        into_value = nested_value.setdefault(where, {}) if where else value
        if len(found) == 1:
            into[field] = {"type": typed[field], "description": description}
            into_value[field] = found[0]
        else:
            # Cùng một tên trường in ra nhiều lần -- nhiều ghi chú, nhiều chữ
            # ký, nhiều con dấu. Một mảng nói đúng chuyện ấy; một chuỗi thì
            # phải chọn lấy một cái và vứt phần còn lại.
            into[field] = {
                "type": "array",
                "items": {"type": typed[field]},
                "description": description,
            }
            into_value[field] = found

    # Nhóm thành `object` lồng. `required` của nhóm liệt kê đúng những trường
    # tờ giấy NÀY in ra -- cùng lý lẽ `required` ở tầng ngoài.
    for prefix, fields in nested.items():
        name = str(spec[prefix].get("name") or prefix.strip("."))
        properties[name] = {
            "type": "object",
            "description": phrase(str(spec[prefix].get("describe") or ""),
                                  seed, name),
            "properties": {k: fields[k] for k in sorted(fields)},
            "required": sorted(fields),
        }
        value[name] = {k: nested_value[prefix][k] for k in sorted(fields)}

    for root in sorted(listed):
        cols = listed_cols.get(root) or {}
        properties[root] = {
            "type": "array",
            "description": phrase(ITEMS_DESCRIBE, seed, root),
            "items": {"type": "object",
                      "properties": {k: cols[k] for k in sorted(cols)}},
        }
        value[root] = [listed[root][n] for n in sorted(listed[root])]

    if rows:
        properties[ITEMS] = {
            "type": "array",
            "description": phrase(ITEMS_DESCRIBE, seed, ITEMS),
            "items": {"type": "object",
                      "properties": {k: columns[k] for k in sorted(columns)}},
        }
        value[ITEMS] = [rows[n] for n in sorted(rows)]

    schema = {
        "type": "object",
        "properties": properties,
        # Schema này tả ĐÚNG tờ giấy này, nên mọi trường trong đó đều có mặt
        # thật. Bản gộp theo LOẠI chứng từ (`kie_schemas/`) mới là chỗ
        # `required` phân biệt được trường luôn có với trường thỉnh thoảng.
        "required": sorted(properties),
    }
    return schema, value


def merge(schemas: list[dict], floor: float = 0.9) -> dict:
    """Gộp nhiều schema một-tờ thành schema của cả LOẠI chứng từ.

    `required` ở đây mới có nghĩa: một trường là bắt buộc khi nó có mặt trên
    ít nhất `floor` số tờ của loại ấy. Trường hiếm vẫn nằm trong
    `properties` -- chúng có thật, chỉ là không phải tờ nào cũng in."""
    if not schemas:
        return {"type": "object", "properties": {}, "required": []}
    count: dict[str, int] = {}
    properties: dict[str, dict] = {}
    for schema in schemas:
        for field, spec in (schema.get("properties") or {}).items():
            count[field] = count.get(field, 0) + 1
            old = properties.get(field)
            if old is None:
                properties[field] = dict(spec)
            elif old.get("type") != spec.get("type"):
                properties[field] = {"type": "string",
                                     "description": old.get("description", "")}
            elif field == ITEMS:
                merged = dict(old.get("items", {}).get("properties") or {})
                merged.update(spec.get("items", {}).get("properties") or {})
                properties[field] = dict(spec)
                properties[field]["items"] = {"type": "object",
                                             "properties": dict(sorted(merged.items()))}
    total = len(schemas)
    return {
        "type": "object",
        "properties": dict(sorted(properties.items())),
        "required": sorted(f for f, n in count.items() if n >= floor * total),
        "documents": total,
    }


__all__ = ["build", "merge"]
