"""`repair.rows_out` — dựng nốt dòng bảng model đã KHAI mà không vẽ.

Model trả hai thứ cho cùng một cái bảng: mảng `rows` trong JSON và các `<tr>`
trong HTML. Đo trên 48 tài liệu (`data/23-09-llm-d..g`): **22 tài liệu khai
nhiều dòng hơn vẽ**, tệ nhất khai 129 và vẽ 18.

Hệ quả đo được là cổng "xin N tờ, dàn ra M<N": 11 trên 12 tờ của lô `g` trượt
vì đúng nó, sau khi mọi lỗi markup khác đã hết. Bảng không dài ra thì không có
gì để cắt sang tờ sau.

Chữ của dòng mới là chữ MODEL ĐÃ VIẾT. Engine không nghĩ ra mặt hàng nào,
không tra corpus nào — nên file này cũng không kiểm nội dung, chỉ kiểm rằng
phép chép chép đúng.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen.repair import _like, rows_out                    # noqa: E402

TEMPLATE = (
    '<table><tbody>'
    '<tr><td data-row="1" data-col="0" data-cell="colnum">'
    '<span data-kind="colnum" data-path="line_items[0].stt">1</span></td>'
    '<td data-row="1" data-col="1" data-cell="menu.name">'
    '<span data-kind="menu.name" data-path="line_items[0].name">Bàn phím</span></td>'
    '<td data-row="1" data-col="2" data-cell="menu.amount">'
    '<span data-kind="menu.amount" data-path="line_items[0].amount">1.250.000</span></td>'
    '</tr></tbody></table>')

ROWS = [
    {"name": "Bàn phím", "unit": "cái", "qty": 1,
     "unit_price": 1250000, "amount": 1250000},
    {"name": "Chuột quang", "unit": "cái", "qty": 2,
     "unit_price": 350000, "amount": 700000},
    {"name": "Màn hình", "unit": "cái", "qty": 3,
     "unit_price": 2400000, "amount": 7200000},
]


def _rows(html: str) -> list[str]:
    return re.findall(r"<tr\b.*?</tr>", html, re.S)


def test_the_declared_rows_that_were_never_drawn_get_drawn():
    out, made = rows_out(TEMPLATE, ROWS)
    assert made == 2, "một dòng mẫu + ba dòng khai -> thêm đúng hai"
    rows = _rows(out)
    assert len(rows) == 3
    texts = [re.findall(r">([^<>]+)</span>", tr) for tr in rows]
    assert texts == [["1", "Bàn phím", "1.250.000"],
                     ["2", "Chuột quang", "700.000"],
                     ["3", "Màn hình", "7.200.000"]]


def test_each_new_row_gets_its_own_seat():
    """`data-row` và chỉ số `line_items[i]` phải tăng cùng nhau.

    Hai dòng cùng `data-row` là hai dòng `kie_full` gộp làm một, và hai dòng
    cùng `line_items[i]` là hai giá trị khác nhau dưới một danh tính -- đúng
    thứ cổng `data-path` loại cả tờ vì nó."""
    out, _ = rows_out(TEMPLATE, ROWS)
    seats, paths = [], []
    for tr in _rows(out):
        seats.append(re.search(r'data-row="(\d+)"', tr).group(1))
        paths.append(sorted(set(re.findall(r"line_items\[(\d+)\]", tr))))
    assert seats == ["1", "2", "3"]
    assert paths == [["0"], ["1"], ["2"]]


def test_numbers_are_written_the_way_the_template_writes_them():
    """Kiểu viết số lấy từ CHÍNH ô mẫu, không từ một quy ước đoán: ô mẫu là
    lời khai của model về cách tờ giấy này viết số, và đó là lời khai duy
    nhất có."""
    assert _like("1.250.000", 7200000) == "7.200.000"
    assert _like("1,250,000", 7200000) == "7,200,000"
    assert _like("1250000", 7200000) == "7200000"
    assert _like("cái", 3) == "3"
    assert _like("x", None) == ""
    # PHẦN CHỮ HAI BÊN cũng là kiểu. Bản đầu chỉ nhận ô số THUẦN, nên
    # `6.720 USD` không khớp và dòng mới in `6720` -- mất cả dấu nhóm lẫn đơn
    # vị. Đo trên `data/23-09-llm-h`: 18 tờ trượt vì `('6.720 USD', '6720')`
    # và `('30', '30 USD')` -- cùng đường dẫn, hai cách viết.
    assert _like("6.720 USD", 7200) == "7.200 USD"
    assert _like("30 USD", 22) == "22 USD"
    assert _like("đ 1.250.000", 7200000) == "đ 7.200.000"


def test_nothing_happens_without_a_template_to_copy():
    """Không mẫu thì không chép. Dựng một dòng từ hư không là đúng thứ
    `repair.py` không làm -- xem nguyên tắc đầu file ấy."""
    assert rows_out("<table><tbody></tbody></table>", ROWS) == (
        "<table><tbody></tbody></table>", 0)
    assert rows_out("<p>không bảng nào</p>", ROWS)[1] == 0
    # Dòng mẫu không mang `data-path` dạng `x[i].y` -> không biết chép vào đâu.
    bare = '<table><tbody><tr><td><span data-kind="menu.name">x</span></td></tr></tbody></table>'
    assert rows_out(bare, ROWS)[1] == 0


def test_a_table_already_longer_than_the_declaration_is_left_alone():
    """Vẽ nhiều hơn khai là chuyện của model, không phải lỗi. Cắt bớt cho
    khớp `rows` là xoá mực đã có trên giấy."""
    assert rows_out(TEMPLATE, ROWS[:1])[1] == 0
    assert rows_out(TEMPLATE, [])[1] == 0


def test_the_copy_never_invents_a_value():
    """Mọi chữ trong dòng mới phải có mặt trong `rows` (hoặc là số thứ tự).

    Đây là lời hứa chính của hàm: engine KHÔNG nghĩ ra nội dung. Vi phạm nó
    là bộ dữ liệu có chữ không ai viết ra, và không ảnh nào cho thấy điều đó.
    """
    out, _ = rows_out(TEMPLATE, ROWS)
    declared = {str(v) for row in ROWS for v in row.values()}
    declared |= {f"{i + 1}" for i in range(len(ROWS))}
    declared |= {_like("1.250.000", v) for row in ROWS
                 for v in row.values() if isinstance(v, int)}
    for tr in _rows(out):
        for text in re.findall(r">([^<>]+)</span>", tr):
            assert text.strip() in declared, f"{text!r} không có trong `rows`"


TWO_TABLES = (
    '<table><tbody><tr><td><span data-kind="meta.value">SỞ Y TẾ</span></td></tr></tbody></table>'
    + TEMPLATE)

TWO_ITEM_TABLES = TEMPLATE + TEMPLATE


def test_a_layout_table_beside_the_item_table_does_not_confuse_it():
    """Bảng dàn trang không mang `line_items[i].name` nào, nên nó tự rơi ra
    khỏi phép lọc -- và cái bảng hàng hoá vẫn được dựng thêm."""
    out, made = rows_out(TWO_TABLES, ROWS)
    assert made == 2, "bảng dàn trang không được làm hỏng phép chọn"
    assert out.count("SỞ Y TẾ") == 1, "bảng dàn trang bị đụng vào"


def test_two_item_tables_stop_the_copy():
    """`rows` tả MỘT cái bảng. Hai bảng cùng mang đường dẫn hàng hoá thì
    không biết nó tả cái nào, và đoán sai làm một bảng dài ra bằng nội dung
    của bảng khác.

    Đo trên 18 tài liệu: 6 tờ có từ hai `<tbody>` trở lên."""
    assert rows_out(TWO_ITEM_TABLES, ROWS) == (TWO_ITEM_TABLES, 0)


MIXED_SEATS = (
    '<table><tbody>'
    '<tr><td data-row="1" data-cell="menu.name">'
    '<span data-kind="menu.name" data-path="line_items[0].name">Bàn phím</span></td>'
    '<td data-row="1" data-cell="menu.note">'
    '<span data-kind="menu.note" data-path="line_items[10].muc">Ghi chú</span></td>'
    '</tr></tbody></table>')


def test_every_index_in_the_cloned_row_moves_together():
    """Model không nhất quán chỉ số: một ô `line_items[6].name` cạnh một ô
    `line_items[16].muc` trong CÙNG một dòng.

    Bản đầu chỉ thay chỉ số của ô đầu tiên, nên ô lệch giữ nguyên chỉ số cũ ở
    MỌI dòng nhân ra -- một đường dẫn mang nhiều chữ khác nhau, và cổng loại
    cả tờ. Đo được: một tờ `xin 8 -> cắt ra 4 tờ`, 433 cặp KIE, mất trắng."""
    out, made = rows_out(MIXED_SEATS, ROWS)
    assert made == 2
    every = []
    for tr in _rows(out):
        seats = set(re.findall(r"line_items\[(\d+)\]", tr))
        assert len(seats) == 1, f"một dòng mang nhiều chỉ số: {sorted(seats)}"
        every.append(seats.pop())
    # Dòng MẪU cũng được nắn: để nguyên `[10]` thì bản nhân ở chỉ số 10 đụng
    # đúng nó, và một đường dẫn mang hai chữ là tờ bị loại.
    assert every == ["0", "1", "2"], every
