"""`agent/rate_match.py` -- moved out of `agent/compose_page.py`, Phase 4
task 4.4. The DoD is "hành vi rate-matching không đổi" (unchanged
behavior); this file proves it against the exact old formulas, not just
trusts the copy-paste.

Nothing below renders an image or starts a model, so this runs in the
dependency-free CI job.
"""

from __future__ import annotations

from agent import compose_page
from agent.rate_match import sheet_count, wants_table


def _old_wants_table(index: int) -> bool:
    return (index * 46) % 100 < 46


_OLD_SHEET_COUNTS = (2, 5, 3, 8, 2, 6, 4, 7, 3, 2, 8, 4, 6, 2, 5, 3)


def _old_sheet_count(index: int) -> int:
    return _OLD_SHEET_COUNTS[index % 16]


def test_wants_table_matches_the_old_formula_over_a_thousand_indices():
    for index in range(1000):
        assert wants_table(index) == _old_wants_table(index), index


def test_sheet_count_matches_the_old_formula_over_a_thousand_indices():
    for index in range(1000):
        assert sheet_count(index) == _old_sheet_count(index), index


def test_wants_table_rate_is_46_percent_over_a_long_run():
    hits = sum(1 for i in range(10_000) if wants_table(i))
    assert hits == 4600


def test_sheet_count_spans_two_to_eight():
    seen = {sheet_count(i) for i in range(16)}
    assert seen == {2, 3, 4, 5, 6, 7, 8}


def test_compose_page_wants_table_is_the_same_function_object():
    """`compose_page.wants_table` là alias, không phải bản chép riêng --
    một sửa ở `rate_match.py` phải lập tức có hiệu lực ở đây, không cần
    đồng bộ tay hai nơi."""
    assert compose_page.wants_table is wants_table
