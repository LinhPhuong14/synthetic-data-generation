"""Tiêu đề bảng BA tầng: `header_supers:` gộp chính những `header_groups:`.

Không mở trình duyệt: `_header_rows` là hàm thuần của một danh sách cột và một
khối `table:` trong file bố cục, và phần đáng sai của nó là số học --
`colspan` cộng lại phải đúng bề rộng bảng, `rowspan` phải chạm đáy `<thead>`.
Một tiêu đề vẽ lệch vẫn ra một tấm ảnh trông như bảng, nên chỗ này phải được
kiểm bằng số chứ không bằng mắt.

Ngữ pháp bảng của pipeline chính đã có tiêu đề hai tầng (`header_groups`), hàng
số cột (`column_numbers`), dòng nhóm và dòng cộng (`group_span`) — tầng thứ ba
là chỗ cuối cùng nó còn thua `synthgen/markup.py`, và luật xếp ở hai nơi phải
là MỘT câu: mỗi cột thuộc về ô hẹp nhất phủ nó, ô nào không có tầng dưới thì
`rowspan` xuống đáy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

from sheets.base import _header_rows  # noqa: E402

KEYS = ["stt", "name", "qty", "price", "fund", "copay", "self_pay", "note"]
COLUMNS = [{"key": key, "title": key.upper()} for key in KEYS]

GROUPS = [{"title": "Nguồn thanh toán", "from": "fund", "to": "self_pay"}]
SUPERS = [{"title": "Chi phí khám chữa bệnh", "from": "qty", "to": "self_pay"}]


def text_of(cell) -> str:
    return re.sub(r"<[^>]+>", "", cell.content).strip()


def shape(rows):
    """`[(chữ, colspan, rowspan)]` mỗi tầng — đủ để kiểm mà không cần markup."""
    return [[(text_of(c), c.colspan, c.rowspan) for c in row.cells] for row in rows]


def widths(rows) -> list[int]:
    """Bề rộng mỗi tầng CHIẾM, tính cả ô từ tầng trên với xuống."""
    total = [0] * len(rows)
    for index, row in enumerate(rows):
        for cell in row.cells:
            for reach in range(index, min(index + cell.rowspan, len(rows))):
                total[reach] += cell.colspan
    return total


# ------------------------------------------------------------------ ba tầng


def test_three_tiers_are_built_when_a_super_is_declared():
    rows = _header_rows(COLUMNS, {"table": {"header_groups": GROUPS,
                                            "header_supers": SUPERS}})
    assert len(rows) == 3
    assert shape(rows)[0] == [
        ("STT", 1, 3), ("NAME", 1, 3), ("Chi phí khám chữa bệnh", 5, 1),
        ("NOTE", 1, 3),
    ]
    assert shape(rows)[1] == [
        ("QTY", 1, 2), ("PRICE", 1, 2), ("Nguồn thanh toán", 3, 1),
    ]
    assert shape(rows)[2] == [("FUND", 1, 1), ("COPAY", 1, 1), ("SELF_PAY", 1, 1)]


def test_every_tier_covers_the_full_width_of_the_table():
    """Số học của cả chuyện này. Một tầng hụt một cột là một bảng vẹo."""
    rows = _header_rows(COLUMNS, {"table": {"header_groups": GROUPS,
                                            "header_supers": SUPERS}})
    assert widths(rows) == [len(COLUMNS)] * 3


def test_a_column_outside_everything_reaches_the_bottom():
    rows = _header_rows(COLUMNS, {"table": {"header_groups": GROUPS,
                                            "header_supers": SUPERS}})
    stt = shape(rows)[0][0]
    assert stt[2] == 3, "cột đứng ngoài mọi nhóm phải với xuống đáy thead"


def test_a_group_outside_every_super_spans_two_tiers():
    rows = _header_rows(COLUMNS, {"table": {
        "header_groups": [{"title": "Tiền", "from": "fund", "to": "self_pay"}],
        "header_supers": [{"title": "Chi tiết", "from": "qty", "to": "price"}],
    }})
    # `Tiền` trùm ba cột (colspan) và với xuống hai tầng (rowspan): các cột
    # của nó rơi thẳng xuống đáy, bỏ qua tầng giữa mà `Chi tiết` chiếm.
    top = {text: (colspan, rowspan) for text, colspan, rowspan in shape(rows)[0]}
    assert top["Tiền"] == (3, 2)
    assert top["Chi tiết"] == (2, 1)
    assert widths(rows) == [len(COLUMNS)] * len(rows)


def test_a_super_that_cuts_a_group_in_half_is_dropped_not_drawn_crooked():
    """HTML không có ô nào cắt đôi được một `colspan`.

    Khai báo kiểu ấy là sai, và thà mất cái nhóm còn hơn vẽ ra một tiêu đề
    lệch — bảng vẹo vẫn ra một tấm ảnh trông như bảng, và cái nhãn đi kèm nó
    thì sai mà không ai thấy."""
    rows = _header_rows(COLUMNS, {"table": {
        "header_groups": [{"title": "Tiền", "from": "fund", "to": "self_pay"}],
        "header_supers": [{"title": "Nửa", "from": "price", "to": "copay"}],
    }})
    assert widths(rows) == [len(COLUMNS)] * len(rows)
    assert "Tiền" not in [text for text, _, _ in shape(rows)[0]]


# --------------------------------------------- hai tầng và một tầng vẫn nguyên


def test_two_tiers_still_behave_exactly_as_before():
    rows = _header_rows(COLUMNS, {"table": {"header_groups": GROUPS}})
    assert len(rows) == 2
    assert widths(rows) == [len(COLUMNS)] * 2
    assert shape(rows)[0][0] == ("STT", 1, 2)


def test_one_tier_when_a_layout_declares_no_groups():
    rows = _header_rows(COLUMNS, {"table": {}})
    assert len(rows) == 1
    assert [text for text, _, _ in shape(rows)[0]] == [k.upper() for k in KEYS]


def test_a_super_naming_a_column_that_does_not_exist_is_ignored():
    """Cột bị bỏ khỏi bố cục thì khai báo trỏ tới nó phải im, không được vỡ."""
    rows = _header_rows(COLUMNS, {"table": {
        "header_supers": [{"title": "Không có", "from": "khong_co", "to": "note"}],
    }})
    assert len(rows) == 1
    assert widths(rows) == [len(COLUMNS)]
