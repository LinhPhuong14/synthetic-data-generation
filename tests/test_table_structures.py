"""`kie_full.table_structures` — khai cấu trúc bảng để chấm được TEDS/GriTS.

Không có bảng thì không chấm được TEDS: cả TEDS lẫn GriTS đều so hai lưới, và
bên phải phải có một lưới để so. `table_pairs` trả về QUAN HỆ (ô nào dưới tiêu
đề nào) nhưng không trả về cái BẢNG.

Việc này ban đầu được đặt là "canonicalize ô gộp như PubTables-1M". Đo thì
không có gì để canonicalize: trên 400 trang nhánh luật và 118 trang nhánh LLM,
0 ô tiêu đề trống, 0 ô tiêu đề `colspan>1`, 0 chuỗi "có chữ rồi trống" cùng
tầng. PubTables-1M cần gộp vì họ suy ngược cấu trúc từ PDF đã in; ở đây markup
khai sẵn. Cái mập mờ thật là BẢNG NÀO LÀ BẢNG — 4,7 bảng mỗi trang, 52,2% có
`<thead>`.

Chạy trên chuỗi markup, không vẽ ảnh, không gọi model.
"""

from __future__ import annotations

from synthgen.kie_full import table_structures

DATA_TABLE = """
<div class="sheet">
  <table>
    <thead>
      <tr><th colspan="2">Hàng hoá</th><th rowspan="2">Thành tiền</th></tr>
      <tr><th>Tên</th><th>Số lượng</th></tr>
    </thead>
    <tbody>
      <tr><td>Máy in</td><td>2</td><td>1.000</td></tr>
      <tr><td colspan="3">TỔNG CỘNG</td></tr>
    </tbody>
  </table>
</div>
"""

LAYOUT_TABLE = """
<div class="sheet">
  <table><tr><td>SỞ TÀI CHÍNH</td><td>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</td></tr></table>
</div>
"""

CONTINUATION = """
<div class="sheet">
  <table>
    <tbody>
      <tr><td>1</td><td>Bàn phím</td><td>50</td></tr>
      <tr><td>2</td><td>Chuột</td><td>30</td></tr>
      <tr><td>3</td><td>Màn hình</td><td>20</td></tr>
    </tbody>
  </table>
</div>
"""


def only(markup):
    found = table_structures(markup)
    assert len(found) == 1, f"mong đúng một bảng, được {len(found)}"
    return found[0]


# ------------------------------------------------------------- vai và chứng cứ


def test_a_table_with_a_head_is_data_on_that_evidence():
    table = only(DATA_TABLE)
    assert table["role"] == "data"
    assert table["role_basis"] == "thead"


def test_a_one_row_table_is_layout():
    """Khối tiêu đề thư dựng bằng `<table>` để dàn trang. Chấm TEDS nó ra một
    con số vô nghĩa."""
    table = only(LAYOUT_TABLE)
    assert table["role"] == "layout"
    assert table["role_basis"] == "small"


def test_a_headless_grid_is_data_but_says_so():
    """Mảnh nối tiếp sau khi cắt trang: tiêu đề nằm ở mảnh trước. Vẫn là dữ
    liệu — bỏ nó là bỏ thân của mọi bảng dài — nhưng `role_basis` nói rõ kết
    luận này đến từ hình lưới, không từ `<thead>`, nên ai không đồng ý vẫn lọc
    lại được."""
    table = only(CONTINUATION)
    assert table["role"] == "data"
    assert table["role_basis"] == "grid"
    assert table["header_tiers"] == 0


def test_every_table_carries_the_evidence_for_its_role():
    for markup in (DATA_TABLE, LAYOUT_TABLE, CONTINUATION):
        table = only(markup)
        assert table["role_basis"] in {"thead", "grid", "small"}


# --------------------------------------------------------------- hình lưới


def test_the_grid_shape_counts_spans_not_tags():
    """`<th colspan="2">` chiếm hai cột, `rowspan="2"` giữ chỗ ở hàng sau."""
    table = only(DATA_TABLE)
    assert table["n_cols"] == 3
    assert table["n_rows"] == 4
    assert table["header_tiers"] == 2


def test_a_spanning_header_keeps_its_span_and_seat():
    table = only(DATA_TABLE)
    top = next(c for c in table["cells"] if c["text"] == "Hàng hoá")
    assert (top["row"], top["col"], top["colspan"]) == (0, 0, 2)
    assert top["is_header"] and top["tier"] == 0


def test_a_rowspan_header_holds_its_column_on_the_next_row():
    """`Thành tiền` chiếm cột 2 ở cả hai tầng, nên `Số lượng` của tầng dưới
    phải ngồi ở cột 1 — không phải cột 2."""
    table = only(DATA_TABLE)
    money = next(c for c in table["cells"] if c["text"] == "Thành tiền")
    qty = next(c for c in table["cells"] if c["text"] == "Số lượng")
    assert (money["col"], money["rowspan"]) == (2, 2)
    assert qty["col"] == 1
    assert qty["tier"] == 1


def test_a_row_label_spanning_the_whole_body_keeps_its_span():
    table = only(DATA_TABLE)
    total = next(c for c in table["cells"] if c["text"] == "TỔNG CỘNG")
    assert total["colspan"] == 3
    assert not total["is_header"]
    assert total["tier"] == -1


def test_cells_come_back_in_reading_order():
    table = only(DATA_TABLE)
    seats = [(c["row"], c["col"]) for c in table["cells"]]
    assert seats == sorted(seats)


# ------------------------------------------------------- nhiều bảng, nhiều trang


TWO_ON_ONE_PAGE = """
<div class="sheet">
  <table>
    <thead><tr><th>Tên</th><th>Số lượng</th></tr></thead>
    <tbody><tr><td>Máy in</td><td>2</td></tr></tbody>
  </table>
  <table>
    <thead><tr><th>Khoản</th><th>Số tiền</th></tr></thead>
    <tbody><tr><td>Thuế GTGT</td><td>100</td></tr></tbody>
  </table>
</div>
"""


def test_two_tables_on_one_page_are_two_entries():
    """Hai bảng cùng trang phải là hai mục: gộp chúng là cách cột số 1 của
    bảng dưới đè lên cột số 1 của bảng trên -- đo trên `data/pilot13`, tờ
    `insurance_partner_cert_application` mất 69 trên 273 cặp đúng vì thế."""
    found = table_structures(TWO_ON_ONE_PAGE)
    assert len(found) == 2
    assert [t["page"] for t in found] == [1, 1]
    assert len({t["table_id"] for t in found}) == 2


def test_the_first_table_of_every_page_gets_its_own_id():
    """Bản trước đánh id theo SỐ BẢNG TRONG TRANG, nên bảng đầu của mọi trang
    đều là `t1`. Tài liệu một tờ không thấy gì; tài liệu 2-10 tờ thì
    `export.py` gom theo `table_id` và hai bảng nhập làm một.

    Kiểm bằng "hai id khác nhau", không kiểm đúng chuỗi: hình dạng id là việc
    của `kie_full.table_key`, còn lời hứa ở đây là DUY NHẤT."""
    found = table_structures(DATA_TABLE + CONTINUATION)
    assert len(found) == 2
    assert [t["page"] for t in found] == [1, 2]
    assert len({t["table_id"] for t in found}) == 2, (
        f"hai bảng hai trang mang cùng id: {[t['table_id'] for t in found]}")


def test_pages_are_counted_from_the_sheet_divs():
    found = table_structures(DATA_TABLE + CONTINUATION)
    assert [t["page"] for t in found] == [1, 2]


def test_markup_without_a_table_yields_nothing():
    assert table_structures("<div class='sheet'><p>Không có bảng nào.</p></div>") == []


# --------------------------------------- không phá `table_pairs` đang dùng chung parser


def test_collecting_cells_does_not_disturb_the_span_seats():
    """`_Spans` giờ ghi cả ô lẫn span từ CÙNG một con trỏ lưới. Nếu việc ghi ô
    làm lệch chỗ ngồi của span thì `table_pairs` hỏng im lặng."""
    from synthgen.kie_full import seats

    markup = """
    <div class="sheet"><table>
      <thead><tr><th><span data-kind="colhdr">Tên</span></th>
                 <th><span data-kind="colhdr">SL</span></th></tr></thead>
      <tbody><tr><td><span data-kind="menu.name">Máy in</span></td>
                 <td><span data-kind="menu.qty">2</span></td></tr></tbody>
    </table></div>
    """
    found = seats(markup)
    assert [s["cell"]["col"] for s in found] == [0, 1, 0, 1]
    assert [s["text"] for s in found] == ["Tên", "SL", "Máy in", "2"]


# ------------------------------------------- mảnh nối tiếp trỏ về mảnh có tiêu đề


def test_a_continuation_points_back_at_the_fragment_that_has_the_head():
    """Một bảng logic được vẽ thành nhiều `<table>`: mảnh đầu mang `<thead>`,
    các mảnh sau chỉ có thân. Đo trên `bang_cham_cong_00090`: 14 mảnh, 2 mảnh
    có tiêu đề, 12 mảnh nối tiếp.

    Chấm thì chấm TỪNG MẢNH — model đọc ảnh không thấy tiêu đề ở mảnh khác —
    nhưng liên kết phải có, nếu không thông tin ấy mất hẳn."""
    found = table_structures(DATA_TABLE + CONTINUATION)
    head, tail = found
    assert head["continues"] is None
    assert tail["continues"] == head["table_id"]


def test_a_continuation_matches_on_column_count():
    """Mảnh nối tiếp giữ nguyên số cột của bảng nó nối. Một bảng rộng khác thì
    không được nhận nhầm làm mảnh của nó."""
    wider = """
    <div class="sheet"><table><tbody>
      <tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>
      <tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>
      <tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>
    </tbody></table></div>
    """
    found = table_structures(DATA_TABLE + wider)
    assert found[0]["n_cols"] == 3 and found[1]["n_cols"] == 4
    assert found[1]["continues"] is None


def test_a_layout_table_never_claims_to_continue_anything():
    found = table_structures(DATA_TABLE + LAYOUT_TABLE)
    assert found[1]["role"] == "layout"
    assert found[1]["continues"] is None
