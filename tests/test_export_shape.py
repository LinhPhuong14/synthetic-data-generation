"""Hình dạng `synthgen/export.py` dựng, và bảy quyết định nó khoá lại.

Không vẽ ảnh, không mở trình duyệt: `document()` nhận một dict bản ghi, nên
file này chạy trong cái CI không cần phụ thuộc nào -- cùng chỗ với
`test_kie.py` và `test_record.py`.

Mỗi test dưới đây là một chỗ định dạng cũ đã sai, và sai theo kiểu không ai
thấy: bảng nằm phẳng ngang hàng tiêu đề tài liệu, tiêu đề cột không có hộp,
một loại thứ mang hai tên, và một phần sáu tên trường là số thứ tự.
"""

from __future__ import annotations

import pytest

from synthgen.export import EXPORT_NAME, document, type_of

TYPES = {"string", "integer", "number", "date", "list", "table"}


def a_pair(**kw):
    """Một cặp KIE tối thiểu. `box` là `[x1, y1, x2, y2]` theo pixel."""
    box = kw.pop("box", [10, 10, 90, 20])
    key_box = kw.pop("key_box", None)
    out = {
        "page_number": 1,
        "value_text": kw.pop("value", "x"),
        "value_bbox": {"x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]},
        "key_text": kw.pop("key_text", ""),
        "key_bbox": (None if key_box is None else
                     {"x1": key_box[0], "y1": key_box[1],
                      "x2": key_box[2], "y2": key_box[3]}),
        "description": kw.pop("description", ""),
    }
    out.update(kw)
    return out


def a_record(pairs, entities=None, width=1000, height=1000):
    return {
        "pages": [{"page_number": 1, "width": width, "height": height}],
        "entity_annotations": entities or [],
        "kie": {"pairs": pairs},
    }


def an_entity(index, kind):
    return {"entity_index": index, "kind": kind}


# ------------------------------------------------------------ khung tài liệu


def test_pages_is_an_array_so_the_schema_has_no_dynamic_keys():
    """`page_1`/`page_2` là khoá ĐỘNG.

    JSON Schema phải tả chúng bằng `patternProperties`, và một bộ sinh có ràng
    buộc (vLLM/xgrammar) phải đoán tên khoá thay vì đi theo một hình dạng cố
    định. Mảng thì không."""
    doc = document(a_record([a_pair(field="so", value="123")]), "hoa_don")
    assert doc["doc_type"] == "hoa_don"
    assert isinstance(doc["pages"], list)
    assert doc["pages"][0]["page"] == 1
    # Bốn khoang của một trang, LUÔN có mặt kể cả rỗng -- cùng lý do khiến
    # `pages` là mảng: hình dạng cố định thì bộ sinh có ràng buộc đi theo được.
    assert set(doc["pages"][0]) == {"page", "size", "fields",
                                    "tables", "signatures", "marks"}
    assert doc["pages"][0]["tables"] == []
    assert doc["pages"][0]["signatures"] == []
    assert doc["pages"][0]["marks"] == []
    assert doc["page_count"] == 1


def test_the_page_carries_its_size_so_the_thousand_grid_reverses():
    """Quy về hệ 1000 là phép làm tròn MỘT CHIỀU.

    Không có kích thước thật thì không ai kiểm ngược được một bộ dữ liệu."""
    doc = document(a_record([a_pair(field="so")], width=1101, height=1811),
                   "hoa_don")
    assert doc["pages"][0]["size"] == [1101, 1811]


# --------------------------------------------------------------------- type


def test_every_entry_declares_a_type_from_the_closed_set():
    doc = document(a_record([a_pair(field="so", value="123")]), "hoa_don")
    for entry in doc["pages"][0]["fields"].values():
        assert entry["type"] in TYPES


def test_a_tax_code_is_a_string_however_much_it_looks_like_a_number():
    """Cùng lập luận `kie_schema.py::_number` viết ra.

    "7159917591" toàn chữ số nhưng không phải một con số để cộng; gọi nó là
    `number` là mời bên đọc đi làm số học trên một mã định danh."""
    assert type_of(kind="store.tax_code") == "string"
    assert type_of(kind="period") == "string"
    assert type_of(kind="total.grand") == "number"
    assert type_of(column="qty") == "number"
    assert type_of(column="stt") == "integer"
    assert type_of(column="date") == "date"


# -------------------------------------------------------------------- bảng


def a_table_record():
    """Một bảng hai dòng, hai cột, có cụm dòng và dòng cộng."""
    cells = []
    for row in (1, 2):
        for index, (column, text) in enumerate((("stt", str(row)),
                                                ("amount", "100"))):
            cells.append(a_pair(
                source="table", column=column, row=row, column_index=index,
                column_path=["Stt" if column == "stt" else "Thành tiền"],
                key_text="Stt" if column == "stt" else "Thành tiền",
                key_box=[10 + index * 100, 10, 60 + index * 100, 20],
                box=[10 + index * 100, 100 + row * 20,
                     60 + index * 100, 115 + row * 20],
                value=text, field=f"{column}_r{row}"))
    others = [
        a_pair(field="row_group", source="implied", value="Chi khác",
               box=[10, 90, 80, 99], value_entity_index=1),
        a_pair(field="cong", source="pair", key_text="Cộng Chi khác",
               value="200", box=[110, 170, 160, 180],
               key_box=[10, 170, 90, 180],
               key_entity_index=2, value_entity_index=3),
        a_pair(field="doc_title", source="implied", value="BẢNG KÊ",
               box=[10, 5, 90, 15], value_entity_index=4),
    ]
    entities = [an_entity(1, "colhdr"), an_entity(2, "total.group"),
                an_entity(3, "total.group_amount"), an_entity(4, "title")]
    return a_record(cells + others, entities)


def only_table(record, kind="bang_ke"):
    page = document(record, kind)["pages"][0]
    assert len(page["tables"]) == 1
    return page["tables"][0]


def test_tables_are_an_array_so_a_second_table_has_a_name_not_a_number():
    """Một trang có N bảng, N không cố định -- đúng lập luận đã dựng nên `pages`.

    Trong `fields` thì bảng thứ hai phải tên `line_items_2`: số thứ tự làm danh
    tính, thứ định dạng này đã bỏ được ở chỗ khác."""
    page = document(a_table_record(), "bang_ke")["pages"][0]
    assert page["tables"][0]["type"] == "table"
    assert page["tables"][0]["table_id"] == "t1"
    assert page["fields"]["doc_title"]["type"] == "string"
    assert "line_items" not in page["fields"]


def test_two_tables_on_one_page_do_not_overwrite_each_other():
    """Hai bảng có cùng `(row, column)`, nên gộp theo toạ độ là mất một bảng.

    Đo trên `data/pilot13`: tờ `insurance_partner_cert_application` mất 69
    trên 273 cặp đúng vì thế, không một dòng báo. `table_id` là thứ tách
    chúng, và `kie_full.table_pairs` đã biết nó từ lúc đọc markup."""
    record = a_table_record()
    second = [dict(p, table_id="t2", value=f"B{p['value_text']}",
                   value_text=f"B{p['value_text']}")
              for p in record["kie"]["pairs"] if p.get("source") == "table"]
    record["kie"]["pairs"] += second
    tables = document(record, "bang_ke")["pages"][0]["tables"]
    assert [t["table_id"] for t in tables] == ["t1", "t2"]
    # Bốn ô dữ liệu mỗi bảng, không bảng nào nuốt bảng nào. Dòng cộng chỉ về
    # bảng đầu -- nó đến từ đường `implied`, chỗ không biết bảng nào là bảng nào.
    for table in tables:
        data = [r for r in table["rows"] if r["kind"] == "data"]
        assert sum(len(r["cells"]) for r in data) == 4
    assert [r["cells"]["amount"]["value"] for r in tables[1]["rows"]
            if r["kind"] == "data"] == ["B100", "B100"]


def test_a_column_header_keeps_its_box():
    """Tiêu đề cột là mực in trên giấy, có toạ độ.

    Định dạng cũ bỏ hẳn nó: ô bảng chỉ giữ `value`/`bbox`, và tiêu đề cột
    không có mặt ở đâu."""
    table = only_table(a_table_record())
    for column in table["columns"]:
        assert column["header"]["value"]
        assert len(column["header"]["bbox"]) == 4
        assert column["path"]


def test_the_ordinal_column_is_exported_as_no_dot():
    """`no` KHÔNG quoted đọc ra boolean trong YAML 1.1.

    Phôi và bố cục viết danh sách cột không quoted, và
    `agent/compose_archetype.py` để model viết YAML -- nên một khoá tên `no` là
    cái bẫy sẽ sập lại đều đặn và im lặng. Dấu chấm là thứ tránh nó."""
    import yaml

    assert yaml.safe_load("c: [no]")["c"] == [False]
    assert yaml.safe_load("c: [no.]")["c"] == ["no."]
    assert EXPORT_NAME["stt"] == "no."
    table = only_table(a_table_record())
    assert [c["key"] for c in table["columns"]] == ["no.", "amount"]
    assert set(table["rows"][1]["cells"]) == {"no.", "amount"}


def test_rows_read_in_the_order_the_paper_reads():
    """Cụm dòng LÀ một dòng trong dãy, không phải một mảng riêng.

    Nhờ thế "dòng này thuộc cụm nào" là chuyện của thứ tự, và tên cụm không bị
    chép vào từng dòng -- hai cụm trùng tên vẫn phân biệt được."""
    table = only_table(a_table_record())
    assert [r["kind"] for r in table["rows"]] == [
        "group", "data", "data", "subtotal"]
    assert table["rows"][0]["label"]["value"] == "Chi khác"
    assert table["rows"][3]["cells"]["amount"]["value"] == "200"


def test_a_row_kind_comes_from_the_entity_kind_not_from_the_label_text():
    """Phân loại bằng tiền tố chuỗi chết trên chứng từ tiếng Anh.

    Nhãn "Grand total" không bắt đầu bằng "Tổng"; một trường tên "Tổng giám
    đốc" thì lại bắt đầu bằng thế. `kind` do bộ dựng HTML gắn, là từ vựng
    đóng."""
    record = a_table_record()
    for pair in record["kie"]["pairs"]:
        if pair.get("key_text") == "Cộng Chi khác":
            pair["key_text"] = "Grand total"
    table = only_table(record)
    assert [r["kind"] for r in table["rows"]][-1] == "subtotal"


def test_a_cell_the_paper_never_printed_is_absent_not_empty():
    """Dựng `{"value": "", "bbox": []}` là khai một thứ không tồn tại.

    `columns` đã nói đủ bộ cột, nên bên đọc tự điền được."""
    record = a_table_record()
    record["kie"]["pairs"] = [p for p in record["kie"]["pairs"]
                              if not (p.get("row") == 2 and p.get("column") == "amount")]
    table = only_table(record)
    second = next(r for r in table["rows"]
                  if r["kind"] == "data" and r["index"] == 2)
    assert set(second["cells"]) == {"no."}


# ------------------------------------------------------- trường in nhiều lần


@pytest.mark.parametrize("same_kind,expect", [(True, "list"), (False, "string")])
def test_a_field_printed_twice_merges_only_when_the_kind_agrees(same_kind, expect):
    """Bốn đoạn ghi chú là MỘT trường in bốn dòng; `note_2` là số thứ tự.

    Nhưng `dien_thoai` của bên bán và của bên mua slug ra cùng một tên mà là
    hai trường -- đo trên 141 tài liệu: 284/308 lượt lặp cùng `kind`, 24 lượt
    khác. Phân biệt bằng từ vựng đóng, không bằng tên."""
    pairs = [a_pair(field="note", value="một", box=[10, 10, 90, 20],
                    value_entity_index=1),
             a_pair(field="note", value="hai", box=[10, 30, 90, 40],
                    value_entity_index=2)]
    entities = [an_entity(1, "note"),
                an_entity(2, "note" if same_kind else "store.phone")]
    fields = document(a_record(pairs, entities), "cong_van")["pages"][0]["fields"]
    assert fields["note"]["type"] == expect
    if same_kind:
        assert [i["value"] for i in fields["note"]["items"]] == ["một", "hai"]
        assert "note_2" not in fields
    else:
        assert fields["note_2"]["value"] == "hai"


# ------------------------------------------------- bảng model TỰ KHAI (v2)


def test_a_declared_path_becomes_a_table_not_a_flat_field_per_cell():
    """`items[0].qty` là một Ô BẢNG, không phải một trường tên `items_0_qty`.

    Đo trên `data/pilot13`: 272 trên 814 trường cấp trang (33,4%) là ô bảng nằm
    lẫn với `doc_title`, và trang nặng nhất có 197 trường. Đường dẫn đã nói đủ
    bảng nào, dòng nào, cột nào -- không phải suy gì."""
    pairs = [a_pair(field="items_0_stt", path="items[0].stt", source="declared",
                    value="1", box=[10, 100, 30, 110], value_entity_index=1),
             a_pair(field="items_0_qty", path="items[0].qty", source="declared",
                    value="25", box=[40, 100, 70, 110], value_entity_index=2),
             a_pair(field="items_1_stt", path="items[1].stt", source="declared",
                    value="2", box=[10, 120, 30, 130], value_entity_index=3),
             a_pair(field="doc_title", source="implied", value="BẢNG KÊ",
                    box=[10, 5, 90, 15], value_entity_index=4)]
    entities = [an_entity(i, "menu.name") for i in (1, 2, 3)] + [an_entity(4, "title")]
    page = document(a_record(pairs, entities), "bang_ke")["pages"][0]
    assert list(page["fields"]) == ["doc_title"]
    table = page["tables"][0]
    assert table["table_id"] == "items" and table["source"] == "declared"
    assert [c["key"] for c in table["columns"]] == ["stt", "qty"]
    assert table["rows"][0]["cells"]["qty"]["value"] == "25"
    assert [r["index"] for r in table["rows"]] == [0, 1]


def test_a_declared_column_carries_no_invented_header():
    """Model khai tên MÁY (`unit_price`), không khai chữ trên giấy.

    Nối nó với tiêu đề in bằng phép chồng hộp là thứ `kie_full` đã thử và hỏng
    hai lần. Ở đây `header` để trống thay vì bịa."""
    pairs = [a_pair(field="items_0_qty", path="items[0].qty", source="declared",
                    value="25", value_entity_index=1)]
    table = only_table(a_record(pairs, [an_entity(1, "menu.qty")]))
    assert table["columns"][0]["header"] == {"value": "", "bbox": []}
    assert table["columns"][0]["path"] == ["items[].qty"]


# ------------------------------------------------------- marks & chữ ký (v2)


def test_printed_furniture_is_a_mark_not_a_value():
    """"(Ký, ghi rõ họ tên)" in dưới mọi ô ký, giống hệt nhau trên mọi tờ.

    `pipeline.kie.FURNITURE` chặn nó ở đường có nhãn, nhưng đường `declared`
    chạy trước và không qua chỗ chặn ấy -- đo trên `data/pilot13`: 12 cặp lọt,
    ba trong số đó còn dính vào đường dẫn của một cột bảng."""
    pairs = [a_pair(field="criteria_3_quota", source="declared",
                    path="criteria[3].quota", value="(Ký, ghi rõ họ tên)",
                    value_entity_index=1),
             a_pair(field="so", value="123", value_entity_index=2)]
    page = document(a_record(pairs, [an_entity(1, "sign.note"),
                                     an_entity(2, "meta")]), "cong_van")["pages"][0]
    assert list(page["fields"]) == ["so"]
    assert page["tables"] == []
    assert page["marks"] == [{"kind": "sign.note",
                              "text": "(Ký, ghi rõ họ tên)",
                              "bbox": [10, 10, 90, 20]}]


def test_a_signature_block_keeps_the_title_with_the_name():
    """Chức danh và tên là MỘT khối. Rời nhau thì "ai ký chức danh X" vô nghĩa.

    Cặp `family` của `kie_full` đã nối sẵn; ở đây chỉ gói lại và đánh số theo
    thứ tự đọc."""
    pairs = [a_pair(source="family", key_text="KẾ TOÁN TRƯỞNG",
                    key_box=[10, 700, 120, 715], value="Trần Văn Hải",
                    box=[10, 760, 120, 775],
                    key_entity_index=1, value_entity_index=2),
             a_pair(source="implied", field="signer_name", value="Lê Thị Mai",
                    box=[400, 760, 520, 775], value_entity_index=3)]
    entities = [an_entity(1, "sign.title"), an_entity(2, "sign.name"),
                an_entity(3, "sign.name")]
    page = document(a_record(pairs, entities), "cong_van")["pages"][0]
    assert "signer_name" not in page["fields"]
    assert [b["index"] for b in page["signatures"]] == [1, 2]
    assert page["signatures"][0]["title"]["value"] == "KẾ TOÁN TRƯỞNG"
    assert page["signatures"][0]["name"]["value"] == "Trần Văn Hải"
    assert page["signatures"][0]["signed"] is True
    assert "title" not in page["signatures"][1]


def test_two_columns_the_lookup_cannot_name_keep_their_printed_headers():
    """`kie_full.BY_KIND` trả `"cell"` cho mọi cột nó không biết mặt.

    Đo trên `data/pilot13`: 8 trên 70 cột mang tên ấy. Gộp theo tên thì hai cột
    `cell` thành một và một trong hai mất sạch ô; chữ trên giấy phân biệt
    được chúng."""
    pairs = []
    for index, header in enumerate(("Quy cách", "Tình trạng")):
        pairs.append(a_pair(source="table", column="cell", row=1,
                            column_index=index, column_path=[header],
                            key_text=header,
                            key_box=[10 + index * 100, 10,
                                     60 + index * 100, 20],
                            box=[10 + index * 100, 100,
                                 60 + index * 100, 115],
                            value=f"v{index}", field=f"cell_r1_{index}"))
    table = only_table(a_record(pairs))
    assert [c["key"] for c in table["columns"]] == ["quy_cach", "tinh_trang"]
    assert set(table["rows"][0]["cells"]) == {"quy_cach", "tinh_trang"}
