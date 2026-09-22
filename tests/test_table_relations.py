"""Khoá QUAN HỆ trên cặp bảng: chỗ ngồi đầy đủ và `line_item_id`.

`row` với `column_index` một mình chưa tả được một ô. `tier` nói ô tiêu đề ở
tầng nào, `colspan`/`rowspan` nói ô chiếm mấy chỗ — thiếu ba khoá này thì người
đọc nhãn không dựng lại được cái lưới, mà TEDS/GriTS thì so lưới với lưới.

`line_item_id` theo lối DocILE (arXiv 2302.05658): mọi trường của cùng một dòng
hàng hoá mang cùng một id, nên việc "gom trường thành dòng hàng" (LIR) chấm
được bằng chính id ấy. Đo trên `data/09-09-26-synthetics-document`: trong phạm
vi một tài liệu, trung bình 4,4 trường mỗi dòng hàng — đúng cho bảng bốn cột.
"""

from __future__ import annotations

from synthgen.kie_full import table_pairs

MARKUP = """
<div class="sheet">
  <table>
    <thead>
      <tr><th><span data-kind="colhdr">Tên hàng</span></th>
          <th><span data-kind="colhdr">Số lượng</span></th></tr>
    </thead>
    <tbody>
      <tr><td><span data-kind="menu.name">Máy in</span></td>
          <td><span data-kind="menu.qty">2</span></td></tr>
      <tr><td><span data-kind="menu.name">Bàn phím</span></td>
          <td><span data-kind="menu.qty">5</span></td></tr>
      <tr><td colspan="2"><span data-kind="menu.total">TỔNG CỘNG</span></td></tr>
    </tbody>
  </table>
</div>
"""


def a_record():
    texts = ["Tên hàng", "Số lượng", "Máy in", "2", "Bàn phím", "5", "TỔNG CỘNG"]
    kinds = ["colhdr", "colhdr", "menu.name", "menu.qty",
             "menu.name", "menu.qty", "menu.total"]
    return {"entity_annotations": [
        {"entity_index": i, "text": t, "kind": k, "page_number": 1,
         "bbox": [i * 10, 0, i * 10 + 8, 10]}
        for i, (t, k) in enumerate(zip(texts, kinds))]}


def pairs():
    return table_pairs(a_record(), MARKUP)


def test_every_body_cell_carries_its_full_seat():
    for pair in pairs():
        for key in ("table_id", "row", "column_index", "tier",
                    "colspan", "rowspan", "row_kind"):
            assert key in pair, f"{pair['field']} thiếu {key}"


def test_fields_of_one_row_share_a_line_item_id():
    by_row = {}
    for pair in pairs():
        if pair["row_kind"] != "data":
            continue
        by_row.setdefault(pair["line_item_id"], []).append(pair["field"])
    assert len(by_row) == 2, "hai dòng hàng, hai id"
    for fields in by_row.values():
        assert len(fields) == 2


def test_two_rows_do_not_share_an_id():
    ids = {p["line_item_id"] for p in pairs() if p["row_kind"] == "data"}
    assert len(ids) == 2


def test_the_id_names_its_table_so_two_tables_never_collide():
    for pair in pairs():
        if pair["line_item_id"]:
            assert pair["line_item_id"].startswith(pair["table_id"] + "#")


def test_a_row_label_is_not_a_line_item():
    """`<td colspan="2">TỔNG CỘNG` là nhãn của cả dòng, không phải một món
    hàng. Gộp nó vào một dòng hàng là khai một món không có thật."""
    label = next(p for p in pairs() if p["value_text"] == "TỔNG CỘNG")
    assert label["row_kind"] == "label"
    assert label["line_item_id"] is None
    assert label["colspan"] == 2


def test_a_body_cell_knows_it_is_not_a_header():
    cell = next(p for p in pairs() if p["value_text"] == "Máy in")
    assert cell["tier"] == -1
    assert cell["key_text"] == "Tên hàng"
    assert cell["column_path"] == ["Tên hàng"]
