"""`pipeline/metrics.py` — PCC cho KIE, GriTS cho bảng.

Mỗi test dưới đây kiểm một tính chất mà bài báo gốc đòi, không phải một con số
tôi tự chọn. Chỗ nào bản dựng này XẤP XỈ thay vì làm đúng bài báo thì test nói
rõ nó đang canh cận dưới.

Không vẽ ảnh, không gọi model.
"""

from __future__ import annotations

import pytest

from pipeline import metrics

# ------------------------------------------------------------------ PCC


def test_centers_sit_inside_the_word_box():
    got = metrics.pseudo_character_centers([0, 0, 40, 10], "abcd")
    assert len(got) == 4
    assert [round(x, 1) for x, _ in got] == [5.0, 15.0, 25.0, 35.0]
    assert all(y == 5.0 for _, y in got)


def test_a_space_has_no_ink_so_it_has_no_center():
    """Một hộp cắt ngang khoảng trắng giữa hai từ không vì thế mà trùm chữ."""
    got = metrics.pseudo_character_centers([0, 0, 30, 10], "a c")
    assert len(got) == 2


def test_an_empty_word_yields_nothing():
    assert metrics.pseudo_character_centers([0, 0, 40, 10], "") == []
    assert metrics.pseudo_character_centers([0, 0, 0, 10], "abc") == []


WORDS = [
    {"bbox": [10, 0, 50, 10], "text": "Hà Nội"},
    {"bbox": [60, 0, 90, 10], "text": "Huế"},
    {"bbox": [10, 20, 50, 30], "text": "0123456"},
]


def test_two_boxes_round_the_same_word_agree():
    assert metrics.pcc_hit([8, -2, 52, 12], [10, 0, 50, 10], WORDS)


def test_a_box_that_swallows_the_neighbour_disagrees():
    """Hộp ôm cả dòng quây thêm chữ "Huế", nên nó KHÔNG chỉ vào cùng chỗ mà
    hộp thật chỉ vào — và phải bị tính là trượt."""
    assert not metrics.pcc_hit([0, -2, 100, 12], [10, 0, 50, 10], WORDS)


def test_a_box_that_clips_the_target_disagrees():
    assert not metrics.pcc_hit([10, 0, 30, 10], [10, 0, 50, 10], WORDS)


def test_a_box_catching_no_word_is_never_a_hit():
    """Hộp rỗng quây ra tập rỗng. Hai tập rỗng bằng nhau, nên phép so tập trần
    sẽ coi mọi hộp ngoài lề là khớp nhau — chặn ở đây."""
    assert not metrics.pcc_hit([200, 200, 210, 210], [300, 300, 310, 310], WORDS)


def test_a_generous_box_still_hits_where_iou_would_fail():
    """Lý do chọn PCC: hộp đọc từ DOM ôm cả phần đệm của thẻ. Hộp dưới đây chỉ
    đạt IoU ~0,25 với hộp thật mà vẫn quây đúng một từ ấy."""
    wide = [0, -15, 58, 18]
    assert metrics._iou(wide, [10, 0, 50, 10]) < 0.3
    assert metrics.pcc_hit(wide, [10, 0, 50, 10], WORDS)


def test_nested_gold_boxes_do_not_make_the_truth_fail():
    """Nhãn kho này có hộp lồng nhau hợp lệ. Đo trên `bang_luong_00000`: 145
    trên 306 trường có hộp chứa tâm ký tự của trường khác. Luật "không chứa gì
    khác" bắt chính sự thật trượt; phép so tập thì không."""
    outer = {"field": "dong", "bbox": [5, -2, 95, 12]}
    inner = {"field": "o", "bbox": [8, -2, 52, 12]}
    gold = [outer, inner]
    assert metrics.score_kile(gold, gold, WORDS)["f1"] == 1.0


# ----------------------------------------------------------------- KILE


def gold_fields():
    return [
        {"field": "dia_chi", "bbox": [8, -2, 52, 12]},
        {"field": "dien_thoai", "bbox": [8, 18, 52, 32]},
    ]


def test_a_perfect_prediction_scores_one():
    got = metrics.score_kile(gold_fields(), gold_fields(), WORDS)
    assert got["f1"] == 1.0
    assert got["matched"] == 2


def test_the_right_box_under_the_wrong_field_name_is_wrong():
    wrong = [{"field": "ten", "bbox": [8, -2, 52, 12]}]
    assert metrics.score_kile(wrong, gold_fields(), WORDS)["matched"] == 0


def test_one_gold_field_is_claimed_at_most_once():
    """Mười dự đoán chồng lên một trường đúng không được ra recall hoàn hảo."""
    same = {"field": "dia_chi", "bbox": [8, -2, 52, 12]}
    got = metrics.score_kile([dict(same) for _ in range(10)], gold_fields(), WORDS)
    assert got["matched"] == 1
    assert got["recall"] == 0.5
    assert got["precision"] == 0.1


def test_predicting_nothing_scores_zero_without_dividing_by_zero():
    got = metrics.score_kile([], gold_fields(), WORDS)
    assert got == {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                   "matched": 0, "predicted": 0, "gold": 2}


# ------------------------------------------------------------------ LIR


ITEM_WORDS = [
    {"bbox": [0, 0, 20, 10], "text": "Máy in"},
    {"bbox": [30, 0, 40, 10], "text": "2"},
    {"bbox": [0, 20, 20, 30], "text": "Bàn phím"},
    {"bbox": [30, 20, 40, 30], "text": "5"},
    {"bbox": [0, 40, 40, 50], "text": "TỔNG"},
]


def a_table_of_items():
    return [
        {"field": "ten", "bbox": [0, 0, 20, 10], "text": "Máy in",
         "line_item_id": "t1#r1"},
        {"field": "sl", "bbox": [30, 0, 40, 10], "text": "2",
         "line_item_id": "t1#r1"},
        {"field": "ten", "bbox": [0, 20, 20, 30], "text": "Bàn phím",
         "line_item_id": "t1#r2"},
        {"field": "sl", "bbox": [30, 20, 40, 30], "text": "5",
         "line_item_id": "t1#r2"},
    ]


def test_line_items_matched_row_for_row():
    got = metrics.score_lir(a_table_of_items(), a_table_of_items(), ITEM_WORDS)
    assert got["f1"] == 1.0


def test_the_id_may_be_named_anything_as_long_as_it_groups():
    """LIR chấm phép GOM, không chấm cái tên. Đổi hết id mà nhóm vẫn đúng thì
    điểm không đổi."""
    renamed = [dict(row, line_item_id="x" + row["line_item_id"])
               for row in a_table_of_items()]
    assert metrics.score_lir(renamed, a_table_of_items(), ITEM_WORDS)["f1"] == 1.0


def test_merging_two_rows_into_one_loses_half():
    """Gộp hai dòng hàng thành một là hỏng đúng thứ LIR đo — và nó phải mất
    điểm, dù mọi ô đều đọc đúng chữ."""
    merged = [dict(row, line_item_id="t1#r1") for row in a_table_of_items()]
    got = metrics.score_lir(merged, a_table_of_items(), ITEM_WORDS)
    assert got["matched"] == 2
    assert got["recall"] == 0.5


def test_a_row_label_is_not_scored_by_lir():
    """`line_item_id` rỗng thì cả hai vế bỏ qua: LIR không hỏi về nó."""
    rows = a_table_of_items() + [
        {"field": "tong", "bbox": [0, 40, 40, 50], "text": "TỔNG",
         "line_item_id": None}]
    assert metrics.score_lir(rows, rows, ITEM_WORDS)["gold"] == 4


# ---------------------------------------------------------------- GriTS


def a_table(rows, cols, cells):
    return {"n_rows": rows, "n_cols": cols, "cells": cells}


def cell(row, col, text="", colspan=1, rowspan=1, bbox=None):
    out = {"row": row, "col": col, "text": text,
           "colspan": colspan, "rowspan": rowspan}
    if bbox:
        out["bbox"] = bbox
    return out


SIMPLE = a_table(2, 2, [cell(0, 0, "Tên"), cell(0, 1, "SL"),
                        cell(1, 0, "Máy in"), cell(1, 1, "2")])


def test_a_spanning_cell_occupies_every_seat_it_covers():
    """Định nghĩa "dạng ma trận" của GriTS — và lý do phép đo này không cần
    canonicalize: ô gộp đã trải ra, nên hai cách viết cùng một bảng cho cùng
    một ma trận."""
    wide = a_table(1, 3, [cell(0, 0, "Hàng hoá", colspan=3)])
    grid = metrics.as_matrix(wide)
    assert len(grid[0]) == 3
    assert all(c is not None and c["text"] == "Hàng hoá" for c in grid[0])


def test_a_table_against_itself_scores_one():
    for kind in ("top", "con"):
        assert metrics.grits(SIMPLE, SIMPLE, kind) == 1.0


def test_a_wrong_word_costs_content_but_not_topology():
    changed = a_table(2, 2, [cell(0, 0, "Tên"), cell(0, 1, "SL"),
                             cell(1, 0, "May in"), cell(1, 1, "2")])
    assert metrics.grits(SIMPLE, changed, "top") == 1.0
    assert 0.8 < metrics.grits(SIMPLE, changed, "con") < 1.0


def test_a_wrong_span_costs_topology_but_not_content():
    gold = a_table(1, 2, [cell(0, 0, "Hàng hoá", colspan=2)])
    split = a_table(1, 2, [cell(0, 0, "Hàng hoá"), cell(0, 1, "Hàng hoá")])
    assert metrics.grits(gold, split, "top") < 1.0
    assert metrics.grits(gold, split, "con") == 1.0


def test_losing_a_row_and_losing_a_column_cost_the_same():
    """Chính bất đối xứng này là lý do bài báo bỏ TEDS: cây HTML dựng theo
    dòng nên thiếu một cột và thiếu một dòng bị phạt khác nhau, dù bản thân
    cái bảng không có bất đối xứng ấy."""
    square = a_table(2, 2, [cell(0, 0, "a"), cell(0, 1, "b"),
                            cell(1, 0, "c"), cell(1, 1, "d")])
    no_row = a_table(1, 2, [cell(0, 0, "a"), cell(0, 1, "b")])
    no_col = a_table(2, 1, [cell(0, 0, "a"), cell(1, 0, "c")])
    assert metrics.grits(square, no_row, "con") == \
        metrics.grits(square, no_col, "con")


def test_location_uses_the_pixel_boxes():
    gold = a_table(1, 1, [cell(0, 0, "x", bbox=[0, 0, 10, 10])])
    near = a_table(1, 1, [cell(0, 0, "x", bbox=[0, 0, 10, 20])])
    assert metrics.grits(gold, gold, "loc") == 1.0
    assert 0.4 < metrics.grits(gold, near, "loc") < 0.6


def test_an_unknown_kind_shouts():
    with pytest.raises(ValueError, match="top"):
        metrics.cell_similarity({"text": "a"}, {"text": "a"}, "whatever")


def test_an_empty_table_scores_zero_without_crashing():
    assert metrics.grits(a_table(0, 0, []), SIMPLE, "con") == 0.0


# ------------------------------------------- nối với nhãn kho này thật sự sinh ra


def test_it_scores_a_real_table_structure_straight_from_the_labeller():
    """`kie_full.table_structures` phải nhả ra đúng hình dạng mà `grits` ăn —
    nếu hai bên lệch nhau thì thước đo này không đo được nhãn của chính kho."""
    from synthgen.kie_full import table_structures

    markup = """
    <div class="sheet"><table>
      <thead><tr><th colspan="2">Hàng hoá</th></tr>
             <tr><th>Tên</th><th>SL</th></tr></thead>
      <tbody><tr><td>Máy in</td><td>2</td></tr></tbody>
    </table></div>
    """
    table = table_structures(markup)[0]
    assert metrics.grits(table, table, "con") == 1.0
    assert metrics.grits(table, table, "top") == 1.0


def test_both_sides_empty_at_a_seat_is_agreement():
    """Bảng thật có hàng răng cưa, nên ma trận có lỗ — và lỗ là một sự thật về
    cái bảng, không phải chỗ thiếu dữ liệu. Tính `f(None, None) = 0` thì mẫu
    số vẫn đếm ô ấy mà tử số không, nên bảng so với CHÍNH NÓ không ra 1,0: đo
    trên 555 bảng thật, trung bình 0,727, thấp nhất 0,257."""
    assert metrics.cell_similarity(None, None, "con") == 1.0
    assert metrics.cell_similarity(None, None, "top") == 1.0
    assert metrics.cell_similarity(None, {"text": "x"}, "con") == 0.0
    assert metrics.cell_similarity({"text": "x"}, None, "con") == 0.0


def test_a_ragged_table_still_scores_one_against_itself():
    ragged = a_table(3, 3, [cell(0, 0, "a"), cell(0, 1, "b"), cell(0, 2, "c"),
                            cell(1, 0, "d"),
                            cell(2, 0, "e"), cell(2, 1, "f")])
    assert metrics.as_matrix(ragged)[1][2] is None
    for kind in ("top", "con"):
        assert metrics.grits(ragged, ragged, kind) == 1.0


def test_row_indexes_need_not_start_at_zero():
    """`_Spans` lấy `row` từ `data-row`, và engine đánh số theo cả bảng dài
    chứ không theo mảnh. Đo trên `bang_cham_cong_00007` mảnh `t2`: 54 hàng,
    `row` chạy 0..92. Bản trước dựng lưới 54 dòng rồi bỏ mọi ô `row > 53`, nên
    GriTS tự chấm ra 0,33."""
    offset = a_table(2, 2, [cell(40, 0, "Tên"), cell(40, 1, "SL"),
                            cell(92, 0, "Máy in"), cell(92, 1, "2")])
    grid = metrics.as_matrix(offset)
    assert len(grid) == 2 and len(grid[0]) == 2
    assert grid[0][0]["text"] == "Tên" and grid[1][1]["text"] == "2"
    assert metrics.grits(offset, offset, "con") == 1.0
