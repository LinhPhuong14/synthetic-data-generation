"""Dòng nhóm trong bảng: số hàng riêng, câu tả đúng vai, trích dẫn không cụt.

Đo trên `data/verify_inkbox_img` (25 trang):

* dòng tiêu đề nhóm "Vật tư phụ" mang cùng `data-row` với dòng hàng đầu, nên
  ô STT của dòng ấy tả thành "Stt của “Vật tư phụ”";
* 60 nhãn trải cột thiếu `description_source`, và 36 tiêu đề nhóm bị tả là
  "tên của tổng các con số bên cạnh";
* 547 câu trích chữ trên giấy bị cắt giữa chữ ("…tổ chứ”").
"""

from __future__ import annotations

from types import SimpleNamespace

from synthgen.kie_full import table_pairs
from synthgen.markup import _row_number
from synthgen.phrasing import excerpt

MARKUP = """
<div class="sheet">
  <table>
    <thead>
      <tr><th data-cell="colhdr" data-row="0" data-col="0"><span data-kind="colhdr">Tên hàng</span></th>
          <th data-cell="colhdr" data-row="0" data-col="1"><span data-kind="colhdr">Thành tiền</span></th></tr>
    </thead>
    <tbody>
      <tr class="grouphdr"><td colspan="2" data-cell="cell" data-row="1" data-col="0"><span data-kind="colhdr">Vật tư phụ</span></td></tr>
      <tr><td data-cell="menu.name" data-row="2" data-col="0"><span data-kind="menu.name">Máy in laser</span></td>
          <td data-cell="menu.amount" data-row="2" data-col="1"><span data-kind="menu.amount">1.000</span></td></tr>
      <tr><td data-cell="menu.name" data-row="3" data-col="0"><span data-kind="menu.name">Bàn phím cơ</span></td>
          <td data-cell="menu.amount" data-row="3" data-col="1"><span data-kind="menu.amount">500</span></td></tr>
    </tbody>
  </table>
</div>
"""

TEXTS = ["Tên hàng", "Thành tiền", "Vật tư phụ", "Máy in laser", "1.000",
         "Bàn phím cơ", "500"]
KINDS = ["colhdr", "colhdr", "colhdr", "menu.name", "menu.amount",
         "menu.name", "menu.amount"]


def pairs(markup=MARKUP, texts=TEXTS, kinds=KINDS):
    record = {"entity_annotations": [
        {"entity_index": i, "text": t, "kind": k, "page_number": 1,
         "bbox": [i * 10, 0, i * 10 + 8, 10]}
        for i, (t, k) in enumerate(zip(texts, kinds))]}
    return {p["field"]: p for p in table_pairs(record, markup)}


def test_group_title_does_not_name_the_first_item_row():
    first = [p for p in pairs().values() if p["row"] == 2]
    assert len(first) == 2
    for pair in first:
        assert "Vật tư phụ" not in pair["description"], pair["description"]


def test_group_title_is_described_as_a_title_not_a_total():
    title = next(p for p in pairs().values() if p["value_text"] == "Vật tư phụ")
    assert title["row_kind"] == "label"
    assert title["line_item_id"] is None
    assert title["description_source"] == "row_label"
    assert title["description"].startswith("Tiêu đề nhóm")


def test_first_item_is_row_one_to_the_reader():
    name = next(p for p in pairs().values() if p["value_text"] == "Máy in laser")
    assert name["description"].endswith("ở dòng 1."), name["description"]


def test_a_total_row_label_names_the_figures_beside_it():
    # Dòng cộng: nhãn trải cột ở cột 0, ô tiền cùng dòng.
    markup = MARKUP.replace(
        '</tbody>',
        '<tr class="grouptot"><td data-cell="cell" colspan="2" data-row="4" data-col="0">'
        '<span data-kind="total.group">Cộng Vật tư phụ</span></td>'
        '<td data-cell="total.group_amount" data-row="4" data-col="2">'
        '<span data-kind="total.group_amount">1.500</span></td></tr></tbody>')
    got = pairs(markup, TEXTS + ["Cộng Vật tư phụ", "1.500"],
                KINDS + ["total.group", "total.group_amount"])
    label = next(p for p in got.values() if p["value_text"] == "Cộng Vật tư phụ")
    amount = next(p for p in got.values() if p["value_text"] == "1.500")
    assert label["description"].startswith("Nhãn của dòng")
    assert amount["line_item_id"] is None, "tiền cộng nhóm không phải một món hàng"


def test_group_rows_get_their_own_row_numbers():
    doc = SimpleNamespace(row_group_size=2, row_group_names=["A", "B"])
    # A: tiêu đề 1, hàng 2-3, cộng 4. B: tiêu đề 5, hàng 6-7, cộng 8.
    assert [_row_number(doc, i, True, True) for i in range(4)] == [2, 3, 6, 7]
    assert [_row_number(doc, i, True, False) for i in range(4)] == [2, 3, 5, 6]
    assert [_row_number(doc, i, False, False) for i in range(4)] == [1, 2, 3, 4]


def test_excerpt_cuts_on_a_word_boundary():
    text = ("Người đứng đầu các bộ phận liên quan chịu trách nhiệm tổ chức "
            "thực hiện quyết định này")
    cut = excerpt(text)
    assert cut.endswith("…")
    assert text.startswith(cut[:-1])
    assert text[len(cut) - 1] == " ", "phải dừng ở ranh giới từ"
    assert excerpt("ngắn") == "ngắn"
