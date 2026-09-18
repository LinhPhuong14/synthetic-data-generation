"""`agent/compose_page.py::resolve_path`/`data_path_mismatches`.

Không mở trình duyệt, không gọi model -- cả hai hàm chỉ đi qua một dict
Python và một chuỗi HTML, nên file này chạy trong CI không phụ thuộc.

## Vì sao file này tồn tại

`schema()` bắt model viết cây `data` TRƯỚC khi viết HTML (xem docstring của
`schema()`), nhưng cây ấy chỉ được ghi ra `declared/*.json` rồi không ai đọc
lại -- xác nhận qua audit và qua chính comment tại chỗ đọc nó ra
(`agent/compose_page.py` quanh dòng khai `answer.get("data")`). Đo trên
`data/pilot12` thật (4 tài liệu có `data` không rỗng -- `data/pilot10` sinh
trước khi việc đọc ra được sửa, nên `data` luôn `null`): 2/4 khớp hoàn toàn,
2/4 lệch nhưng đều là khác biệt ĐỊNH DẠNG lành tính (`"1583000000"` trong
`data` so với `"1.583.000.000"` in trên giấy; `"452/BB-SYT"` trong `data` so
với `"Số: 452/BB-SYT"` in kèm nhãn) -- không phải mâu thuẫn ngữ nghĩa. Đây là
lý do `data_path_mismatches` là hàm ĐO cho việc gỡ lỗi, không phải hàm GATE:
xem docstring của nó.
"""

from __future__ import annotations

from agent.compose_page import data_path_mismatches, resolve_path


def test_a_simple_dotted_path_resolves():
    data = {"issuer": {"tax_code": "0312345678"}}
    assert resolve_path(data, "issuer.tax_code") == (True, "0312345678")


def test_an_array_index_resolves():
    data = {"line_items": [{"name": "Máy in"}, {"name": "Mực in"}]}
    assert resolve_path(data, "line_items[1].name") == (True, "Mực in")


def test_a_bare_digit_segment_resolves_as_an_index_too():
    """`[N]` không còn là hình DUY NHẤT hợp lệ cho chỉ số -- `synthgen/
    llm_page.py::_PATH` giờ chấp nhận `clause.1.body` (Phase 8, đo trên
    pilot16: 16 đường bị cổng cũ loại một tờ đúng mọi luật khác chỉ vì thiếu
    ngoặc vuông). `resolve_path` phải đọc được hình này để không âm thầm bỏ
    qua đoạn số, trỏ nhầm sang trường khác."""
    data = {"clause": [{"body": "Điều khoản một"}, {"body": "Điều khoản hai"}]}
    assert resolve_path(data, "clause.1.body") == (True, "Điều khoản hai")


def test_a_missing_key_fails_cleanly():
    data = {"issuer": {"tax_code": "x"}}
    assert resolve_path(data, "issuer.address") == (False, None)


def test_an_out_of_range_index_fails_cleanly():
    data = {"rows": [1]}
    assert resolve_path(data, "rows[5]") == (False, None)


def test_indexing_into_something_that_is_not_a_list_fails_cleanly():
    data = {"issuer": "not a list"}
    assert resolve_path(data, "issuer[0]") == (False, None)


def test_a_matching_value_has_no_mismatch():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.name">'
           "CÔNG TY ABC</span></div>")
    assert data_path_mismatches(data, html) == []


def test_a_different_printed_value_is_reported():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.name">'
           "CÔNG TY XYZ</span></div>")
    found = data_path_mismatches(data, html)
    assert len(found) == 1
    assert "issuer.name" in found[0]


def test_a_path_the_data_tree_never_declared_is_reported():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.ghost">'
           "nope</span></div>")
    found = data_path_mismatches(data, html)
    assert any("không tra được" in line for line in found)


def test_a_span_with_no_data_path_is_ignored():
    data = {}
    html = '<div class="sheet"><span data-kind="x">bất kỳ chữ gì</span></div>'
    assert data_path_mismatches(data, html) == []


def test_the_same_path_printed_twice_with_the_same_value_is_fine():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet">'
           '<span data-kind="x" data-path="issuer.name">CÔNG TY ABC</span>'
           '<span data-kind="x" data-path="issuer.name">CÔNG TY ABC</span>'
           "</div>")
    assert data_path_mismatches(data, html) == []
