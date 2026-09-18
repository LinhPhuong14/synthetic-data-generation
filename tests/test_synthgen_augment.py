"""Nối bộ sinh synthgen vào chuỗi làm cũ của pipeline chính.

Không có gì ở đây mở Chromium, gọi Blender hay đọc một tấm ảnh: phần đáng sai
của `synthgen/augment.py` là **hộp**, và hộp thì kiểm được trên một bản ghi
viết tay với một phép cong giả. Phép cong thật (`degradation/paper_warp.py`) có
bộ kiểm riêng; cái file này canh là chuyện khác hẳn -- rằng một tờ giấy có BA
hình dạng hộp khác nhau trong cùng một bản ghi, và ghi nhầm hình dạng nào thì
file vẫn mở được còn cái đọc nó thì vỡ.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy", reason="augment.py imports numpy")
pytest.importorskip("cv2", reason="augment.py imports OpenCV")

from degradation import blender  # noqa: E402
from synthgen import augment as A  # noqa: E402


def a_record():
    """Một tờ giấy nhỏ nhất còn giữ đủ ba hình dạng hộp."""
    return {
        "word_annotations": [
            {"page_number": 1, "text": "A", "field_path": "store.name",
             "bbox": [10, 10, 20, 20],
             "polygon": [[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]},
            {"page_number": 2, "text": "B", "field_path": "store.name",
             "bbox": [30, 30, 40, 40],
             "polygon": [[30, 30], [40, 30], [40, 40], [30, 40], [30, 30]]},
        ],
        "layout_annotations": [
            {"page_number": 1, "layout_class": "Table", "bbox": [5, 5, 50, 50],
             "polygon": [[5, 5], [50, 5], [50, 50], [5, 50], [5, 5]]},
        ],
        "entity_annotations": [
            # KHÔNG có `polygon` -- đúng như bản ghi thật, và đó là chỗ lần đầu
            # chạy vỡ với một KeyError.
            {"page_number": 1, "entity_index": 0, "text": "A",
             "bbox": [10.0, 10.0, 20.0, 20.0], "lines": [[10, 10, 20, 20]]},
        ],
        "blocks": [
            {"page_number": 1, "id": "p1-b0", "text": "A",
             "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
             "quad": [[10, 10], [20, 10], [20, 20], [10, 20]]},
        ],
        "kie": {"pairs": [
            {"page_number": 1, "field": "ten",
             "key_bbox": {"x1": 1, "y1": 1, "x2": 5, "y2": 5},
             "value_bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20}},
        ]},
        "pages": [{"page_number": 1, "width": 60, "height": 60},
                  {"page_number": 2, "width": 60, "height": 60}],
    }


@pytest.fixture()
def shifted(monkeypatch):
    """Thay phép cong thật bằng một phép dịch +3 pixel.

    Đủ để trả lời câu hỏi của file này -- hộp có đi theo không, và có về đúng
    hình dạng của nó không -- mà không cần một tấm ảnh chụp giấy nào."""
    def fake(name, image, params, rng, *region_lists):
        moved = [[{**box, "quad": [[x + 3, y + 3] for x, y in box["quad"]]}
                  for box in regions] for regions in region_lists]
        return (image, *moved)

    monkeypatch.setattr(A.W, "warp_regions", fake)
    return fake


# ------------------------------------------------------ hộp đi theo trang cong


def test_every_kind_of_box_moves_and_keeps_its_own_shape(shifted):
    record = a_record()
    A.warp_record("bất kỳ", None, None, object(), record, page=1)

    word = record["word_annotations"][0]
    assert word["polygon"][0] == [13, 13]
    assert word["polygon"][0] == word["polygon"][-1], "polygon phải là vòng kín"
    assert word["bbox"] == [13, 13, 23, 23]

    # `entity` không có polygon và không được mọc thêm một cái.
    entity = record["entity_annotations"][0]
    assert "polygon" not in entity
    assert entity["bbox"] == [13.0, 13.0, 23.0, 23.0]
    assert entity["lines"] == [[13, 13, 23, 23]]

    # `block.bbox` là DICT, `entity.bbox` và `word.bbox` là DANH SÁCH.
    block = record["blocks"][0]
    assert block["bbox"] == {"x1": 13, "y1": 13, "x2": 23, "y2": 23}
    assert block["quad"] == [[13, 13], [23, 13], [23, 23], [13, 23]]

    pair = record["kie"]["pairs"][0]
    assert pair["key_bbox"] == {"x1": 4, "y1": 4, "x2": 8, "y2": 8}
    assert pair["value_bbox"] == {"x1": 13, "y1": 13, "x2": 23, "y2": 23}


def test_a_page_that_was_not_aged_keeps_its_boxes(shifted):
    """Làm cũ tờ một không được động tới hộp của tờ hai.

    Bản ghi được chép bên cạnh TỪNG TỜ và tả cả tài liệu, nên một hàm cong
    theo trang mà quên lọc sẽ cong tất cả -- và tờ hai sẽ mang hộp của một
    phép cong nó chưa từng đi qua."""
    record = a_record()
    A.warp_record("bất kỳ", None, None, object(), record, page=1)
    assert record["word_annotations"][1]["polygon"][0] == [30, 30]


def test_one_call_warps_every_list_so_they_share_one_field(monkeypatch):
    """Bảy danh sách, một lần gọi. Gọi bảy lần là bảy tờ giấy khác nhau."""
    calls = []

    def counting(name, image, params, rng, *region_lists):
        calls.append(len(region_lists))
        return (image, *[list(regions) for regions in region_lists])

    monkeypatch.setattr(A.W, "warp_regions", counting)
    A.warp_record("bất kỳ", None, None, object(), a_record(), page=1)
    assert calls == [7]


# --------------------------------------------------------------- chọn warp nào


def test_the_slow_warps_are_recognised_by_engine_not_by_name():
    """Danh sách tên viết tay sẽ đúng hôm nay và sai lần sau.

    `blender_free` hỏi `degradation/warp.py` engine nào vẽ tên ấy, nên một
    engine mới thêm vào kho là hàm này tự phân loại đúng."""
    from rulebase import spec

    options = spec.load_rules()["augmentation"]
    keep, dropped = A.blender_free(options)
    assert dropped, "phải có giá trị dùng Blender để bài kiểm này có nghĩa"
    assert len(keep) + len(dropped) == len(options)
    slow = set(blender.names())
    for option in keep:
        assert ((option.params.get("warp") or {}).get("name") or "") not in slow
    by_id = {option.id: option for option in options}
    for name in dropped:
        assert by_id[name].params["warp"]["name"] in slow


def test_warp_none_strips_the_bending_but_keeps_the_dirt():
    """`crumpled` còn cả một chuỗi vết bẩn đáng giữ; chỉ phần bẻ hình học là bỏ.

    Lọc BỎ những giá trị ấy sẽ làm nghèo bộ đi vì một lý do không liên quan
    tới vết bẩn."""
    from rulebase import spec

    options = spec.load_rules()["augmentation"]
    stripped = A.no_warp(options)
    assert len(stripped) == len(options)
    assert not any((o.params.get("warp") or {}).get("name") for o in stripped)
    before = {o.id: len(o.params.get("chain") or []) for o in options}
    for option in stripped:
        assert len(option.params.get("chain") or []) == before[option.id]


# ------------------------------------------------------------------ dựng lại


def test_the_same_document_always_meets_the_same_machine():
    """`crc32`, không `hash()`: `hash()` có muối riêng mỗi tiến trình, nên một
    bộ chạy lại trên tám worker sẽ ra tám kết quả khác nhau."""
    rules, _dropped = A.options_for("fast")
    once = A.recipe_for("hoa_don_gtgt_00014", 0, rules)
    again = A.recipe_for("hoa_don_gtgt_00014", 0, rules)
    assert once.seed == again.seed
    assert once.choices["augmentation"].id == again.choices["augmentation"].id


def test_a_second_variant_is_a_different_machine():
    rules, _dropped = A.options_for("fast")
    seeds = {A.recipe_for("hoa_don_gtgt_00014", n, rules).seed for n in range(4)}
    assert len(seeds) == 4


def test_a_document_gets_more_than_one_kind_of_ageing_across_the_set():
    rules, _dropped = A.options_for("fast")
    drawn = {A.recipe_for(f"hoa_don_gtgt_{n:05d}", 0, rules)
             .choices["augmentation"].id for n in range(60)}
    assert len(drawn) > 5, f"chỉ bốc trúng {sorted(drawn)}"
