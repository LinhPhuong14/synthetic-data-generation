"""`agent/fingerprint.py::geometry_fingerprint` + `agent/geometry_distance.py`.

Tầng hình học: dấu vân đọc từ `layout_annotations` đã vẽ, và phép so hai tờ
ấy. Không file nào dưới đây vẽ ảnh hay gọi model, nên chúng chạy trong job CI
không cần thư viện -- cùng luật với `tests/test_fingerprint.py`.
"""

from __future__ import annotations

from agent.fingerprint import GRID_COLS, GRID_ROWS, geometry_fingerprint
from agent.geometry_distance import (
    JACCARD_CEILING,
    collides,
    corpus_geometry,
    hamming,
    jaccard,
    nearest,
)


def box(label, x0, y0, x1, y1, page=1):
    """Một vùng bố cục đúng hình dạng `pipeline/record.py` ghi ra."""
    return {"layout_class": label, "bbox": [x0, y0, x1, y1],
            "bbox_mode": "xyxy_per_mille", "page_number": page}


# ------------------------------------------------------------ geometry_fingerprint


def test_a_box_lands_in_the_grid_cell_its_per_mille_corner_names():
    """1000 phần nghìn / 8 cột = 125 mỗi cột; x=0..124 là cột 0."""
    fp = geometry_fingerprint([box("Title", 0, 0, 100, 50)])
    assert fp.cells == {(1, "Title", 0, 0)}
    assert fp.grid == 1                       # bit 0 = (hàng 0, cột 0)
    assert fp.regions == 1
    assert fp.pages == 1


def test_a_box_touching_the_right_edge_is_clamped_not_dropped():
    """x=1000 chia đúng thành cột thứ 8, thứ không tồn tại trên lưới 8 cột.

    Kẹp chứ không bỏ: mép phải là chỗ số trang và dấu giáp lai hay ngồi, và
    một vùng biến mất khỏi dấu vân là một vùng không được so."""
    fp = geometry_fingerprint([box("Page-Footer", 990, 990, 1000, 1000)])
    assert fp.cells == {(1, "Page-Footer", GRID_COLS - 1, GRID_ROWS - 1)}


def test_a_wide_box_occupies_every_cell_it_crosses():
    """Một hàng lưới cao 1000/12 = 83,3 phần nghìn, nên y=0..83 là hàng 0."""
    fp = geometry_fingerprint([box("Table", 0, 0, 1000, 83)])
    assert len(fp.cells) == GRID_COLS         # cả hàng đầu
    assert bin(fp.grid).count("1") == GRID_COLS


def test_the_sheet_number_is_part_of_the_cell_key():
    """Cùng một khối ở cùng một chỗ nhưng trên tờ hai KHÔNG phải cùng một ô."""
    one = geometry_fingerprint([box("Title", 0, 0, 100, 50, page=1)])
    two = geometry_fingerprint([box("Title", 0, 0, 100, 50, page=2)])
    assert one.cells != two.cells
    assert jaccard(one, two) == 0.0


def test_only_sheet_one_reaches_the_ink_bitmap():
    """`grid` là bitmask của TỜ ĐẦU -- một khối ở tờ hai không bật bit nào."""
    fp = geometry_fingerprint([box("Title", 0, 0, 100, 50, page=2)])
    assert fp.grid == 0
    assert fp.cells                           # nhưng nó vẫn có trong `cells`
    assert fp.pages == 2


def test_the_label_is_part_of_the_key_so_two_classes_never_share_a_cell():
    fp = geometry_fingerprint([box("Title", 0, 0, 100, 50),
                               box("Table", 0, 0, 100, 50)])
    assert len(fp.cells) == 2
    assert bin(fp.grid).count("1") == 1       # cùng một ô mực, hai nhãn


def test_a_malformed_annotation_is_skipped_not_fatal():
    """Bản ghi thiếu `bbox`, `bbox` cụt, hay không phải dict -- bỏ qua.

    Một vùng không đo được là một vùng không vào dấu vân; cả tờ vẫn còn
    những vùng khác, và ném ở đây là để một khoá lạ giết một tờ giấy."""
    fp = geometry_fingerprint([
        {"layout_class": "Title"},                       # thiếu bbox
        {"layout_class": "Text", "bbox": [1, 2]},        # bbox cụt
        {"layout_class": "Text", "bbox": ["a", 0, 1, 1]},  # không phải số
        "không phải dict",
        box("Table", 0, 0, 100, 83),
    ])
    assert fp.regions == 1
    assert fp.cells == {(1, "Table", 0, 0)}


def test_an_empty_page_gives_an_empty_fingerprint_not_an_error():
    for empty in ([], None, ()):
        fp = geometry_fingerprint(empty)
        assert fp.cells == frozenset() and fp.grid == 0 and fp.regions == 0


def test_a_missing_layout_class_becomes_a_placeholder_not_a_crash():
    fp = geometry_fingerprint([{"bbox": [0, 0, 10, 10], "page_number": 1}])
    assert fp.cells == {(1, "?", 0, 0)}


def test_the_fingerprint_is_hashable_so_it_can_key_a_set():
    fp = geometry_fingerprint([box("Title", 0, 0, 100, 50)])
    {fp.cells: 1}                             # ném nếu `cells` không băm được


# ------------------------------------------------------------------- khoảng cách


def test_two_identical_pages_are_jaccard_one_and_hamming_zero():
    page = [box("Title", 0, 0, 500, 100), box("Table", 0, 200, 1000, 600)]
    a, b = geometry_fingerprint(page), geometry_fingerprint(list(page))
    assert jaccard(a, b) == 1.0
    assert hamming(a, b) == 0.0


def test_two_pages_sharing_nothing_are_jaccard_zero():
    a = geometry_fingerprint([box("Title", 0, 0, 100, 50)])
    b = geometry_fingerprint([box("Table", 800, 900, 1000, 1000)])
    assert jaccard(a, b) == 0.0


def test_an_unmeasurable_page_is_never_called_a_duplicate():
    """Hai dấu vân rỗng trả 0.0, không 1.0.

    `len(a & b) / len(a | b)` trên hai tập rỗng là chia cho không; và cái
    bẫy thật sự là nếu nó trả 1.0 thì MỌI tờ không dàn ra được sẽ bị loại vì
    "trùng" với tờ không dàn ra được trước nó."""
    empty = geometry_fingerprint([])
    other = geometry_fingerprint([box("Title", 0, 0, 100, 50)])
    assert jaccard(empty, empty) == 0.0
    assert jaccard(empty, other) == 0.0
    assert nearest(empty, [("x", other)]) is None
    assert collides(empty, [("x", other)]) is None


def test_nearest_returns_the_closest_not_the_first():
    target = geometry_fingerprint([box("Title", 0, 0, 500, 100)])
    far = geometry_fingerprint([box("Table", 800, 900, 1000, 1000)])
    near = geometry_fingerprint([box("Title", 0, 0, 500, 100)])
    got = nearest(target, [("far", far), ("near", near)])
    assert got is not None and got[0] == "near" and got[1] == 1.0


def test_collides_is_nearest_plus_a_threshold_and_nothing_else():
    target = geometry_fingerprint([box("Title", 0, 0, 500, 100)])
    same = geometry_fingerprint([box("Title", 0, 0, 500, 100)])
    assert collides(target, [("a", same)], ceiling=0.9) is not None
    assert collides(target, [("a", same)], ceiling=1.1) is None
    assert collides(target, []) is None


def test_hamming_counts_only_cells_where_the_two_pages_disagree():
    # Một cột rộng 1000/8 = 125, nên x=0..124 là cột 0 và x=125 đã sang cột 1.
    a = geometry_fingerprint([box("Title", 0, 0, 124, 83)])     # đúng một ô
    b = geometry_fingerprint([box("Title", 0, 0, 249, 83)])     # hai ô
    assert hamming(a, b) == 1 / (GRID_COLS * GRID_ROWS)


# ------------------------------------------------------------------ corpus_geometry


def test_corpus_geometry_on_an_empty_batch_reports_nothing_not_zero():
    """`median: None` chứ không `0.0`: "chưa đo tờ nào" và "mọi tờ đều khác
    nhau hoàn toàn" là hai câu trái ngược, và cả hai đều in ra được 0.0."""
    got = corpus_geometry([])
    assert got["documents"] == 0
    assert got["nearest_jaccard"]["median"] is None
    assert got["over_ceiling"] == 0


def test_corpus_geometry_counts_a_repeated_page_as_over_the_ceiling():
    page = [box("Title", 0, 0, 500, 100), box("Table", 0, 200, 1000, 600)]
    fps = [geometry_fingerprint(page) for _ in range(3)]
    got = corpus_geometry(fps, window=24, ceiling=JACCARD_CEILING)
    # Tờ đầu không có gì đứng trước để so, nên hai tờ sau mới bị đếm.
    assert got["over_ceiling"] == 2
    assert got["nearest_jaccard"]["max"] == 1.0
    assert got["distinct_cell_sets"] == 1


def test_the_window_forgets_pages_that_fell_out_of_it():
    """Một tờ giống tờ đầu nhưng cách nó xa hơn cửa sổ thì KHÔNG bị đếm."""
    same = [box("Title", 0, 0, 500, 100)]
    other = [box("Table", 800, 900, 1000, 1000)]
    order = ([geometry_fingerprint(same)]
             + [geometry_fingerprint(other)] * 3
             + [geometry_fingerprint(same)])
    assert corpus_geometry(order, window=2, ceiling=0.6)["over_ceiling"] == 2
    assert corpus_geometry(order, window=99, ceiling=0.6)["over_ceiling"] == 3


def test_the_histogram_has_the_same_ten_bins_whatever_the_data():
    """Khoang cố định: hai lượt chạy chỉ so được với nhau nếu trục giống nhau."""
    empty = corpus_geometry([])["jaccard_histogram"]
    filled = corpus_geometry(
        [geometry_fingerprint([box("Title", 0, 0, 500, 100)])] * 4
    )["jaccard_histogram"]
    assert list(empty) == list(filled)
    assert len(empty) == 10
