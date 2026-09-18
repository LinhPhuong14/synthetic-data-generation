"""`agent/compose_page.py::_reconcile_sheet_count` -- gác SAU khi dàn trang
thật, không phải ước lượng ký tự TRƯỚC khi dàn trang.

Phase 8 (`docs/ke-hoach-refactor-engine.md`). Nothing below renders an image
or starts a model -- hàm chỉ đi qua `list[dict]`/`dict[str, int]` thuần, nên
file này chạy trong CI không phụ thuộc.

## Vì sao hàm này tồn tại

Lần thử đầu (`synthgen/llm_page.py::content_length_problems`, đã bỏ) ước
lượng số tờ từ SỐ KÝ TỰ, gác TRƯỚC khi dàn trang. Chạy thật trên pilot16 lộ
sai lầm ngay: một tài liệu bố cục key-value xếp dọc đo được ~1 150 ký tự MỖI
TỜ THẬT (so với 8 000 ước lượng từ văn xuôi/bảng dày) và bị gác NHẦM dù nó
xin 2 tờ mà dàn ra tới 3 tờ thật -- nhiều hơn xin, không phải thiếu. Hàm này
thay bằng số tờ THẬT (`synthgen/draw_llm.py` đã cắt xong, không phải ước
lượng), nên không còn kiểu sai đó."""

from __future__ import annotations

from agent.compose_page import SHEET_SHORTFALL_RATIO, _reconcile_sheet_count


def a_page(index, archetype="x", sheets_asked=1, ok=True):
    return {"index": index, "archetype": archetype, "ok": ok,
           "sheets_asked": sheets_asked, "why": []}


def test_a_page_that_rendered_at_least_the_ratio_is_left_alone():
    made = [a_page(0, sheets_asked=6)]
    actual = {"llm_x_0000": 5}                      # 5/6 = 83%, trên ngưỡng
    flipped = _reconcile_sheet_count(made, actual)
    assert flipped == []
    assert made[0]["ok"] is True


def test_a_page_that_rendered_far_fewer_sheets_is_flipped():
    made = [a_page(0, sheets_asked=8)]
    actual = {"llm_x_0000": 1}                      # 1/8 = 12%
    flipped = _reconcile_sheet_count(made, actual)
    assert flipped == ["llm_x_0000"]
    assert made[0]["ok"] is False
    assert any("dàn trang thật chỉ ra 1 tờ" in line for line in made[0]["why"])


def test_a_page_that_rendered_more_sheets_than_asked_is_never_flipped():
    """Chính ca đã đo sai trên pilot16 khi còn dùng ước lượng ký tự: xin 2
    mà dàn ra 3 tờ THẬT -- nhiều hơn xin, không phải thiếu."""
    made = [a_page(0, sheets_asked=2)]
    actual = {"llm_x_0000": 3}
    flipped = _reconcile_sheet_count(made, actual)
    assert flipped == []
    assert made[0]["ok"] is True


def test_a_single_sheet_document_is_never_checked():
    made = [a_page(0, sheets_asked=1)]
    actual = {"llm_x_0000": 1}
    assert _reconcile_sheet_count(made, actual) == []


def test_an_already_rejected_page_is_left_alone():
    """Trang đã trượt cổng chữ (`ok=False`) không cần đối chiếu lại --
    `why` của nó đã có lý do riêng, không phải chờ số tờ thật."""
    made = [a_page(0, sheets_asked=8, ok=False)]
    actual = {"llm_x_0000": 1}
    assert _reconcile_sheet_count(made, actual) == []
    assert made[0]["ok"] is False


def test_a_page_missing_from_actual_pages_is_left_alone():
    """`Artist` có thể chưa vẽ được tờ này (lỗi `playwright`) -- không có số
    tờ thật thì không đoán, giữ nguyên phán quyết của cổng chữ."""
    made = [a_page(0, sheets_asked=8)]
    flipped = _reconcile_sheet_count(made, actual_pages={})
    assert flipped == []
    assert made[0]["ok"] is True


def test_the_boundary_matches_the_ratio_constant():
    """Ngưỡng đúng bằng `SHEET_SHORTFALL_RATIO` -- test này khoá hằng số lại
    với hành vi, không phải một con số 0.6 chép tay có thể lệch nhau."""
    sheets = 10
    boundary = int(sheets * SHEET_SHORTFALL_RATIO)
    made_at = [a_page(0, sheets_asked=sheets)]
    assert _reconcile_sheet_count(made_at, {"llm_x_0000": boundary}) == []
    made_below = [a_page(0, sheets_asked=sheets)]
    assert _reconcile_sheet_count(made_below, {"llm_x_0000": boundary - 1}) \
        == ["llm_x_0000"]


def test_multiple_pages_are_each_judged_independently():
    made = [a_page(0, "a", sheets_asked=8), a_page(1, "b", sheets_asked=2)]
    actual = {"llm_a_0000": 1, "llm_b_0001": 2}
    flipped = _reconcile_sheet_count(made, actual)
    assert flipped == ["llm_a_0000"]
    assert made[0]["ok"] is False
    assert made[1]["ok"] is True
