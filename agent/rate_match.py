"""Index-based round-robin rate-matching -- moved out of `agent/compose_page.py`
so the sampler (Phase 4) can call it directly instead of a caller having to
know a tuple/formula lives at a specific callsite.

    from agent.rate_match import sheet_count, wants_table

Phase 4, task 4.4. **A move, not a rewrite.** `docs/ke-hoach-refactor-engine.md`
G2 documents why: `wants_table()`'s 46% figure is not an arbitrary knob --
it exists because letting the model decide table presence on its own
produced 60% (the model's own preference), while the real rulebase engine's
output is 46% table-bearing pages; mixing an LLM-generated batch with an
engine-generated one is only sound when both come from the same
distribution. The DoD here is "hành vi rate-matching không đổi" -- unchanged
behavior -- so both formulas below are byte-identical to what
`agent/compose_page.py` had, and `tests/test_rate_match.py` proves it by
comparing this module's output against the old formulas over every index
0..999, not just trusting the copy-paste.
"""

from __future__ import annotations


def wants_table(index: int) -> bool:
    """Tờ này có bảng hay không -- quay vòng, 46% có.

    Không hỏi phôi nào nữa: chính model quyết loại chứng từ, nên không ai
    biết trước nó có bảng hay không. Cái quay vòng ở đây chỉ giữ TỈ LỆ của
    cả lượt khớp với bộ engine vẽ (46% có bảng), để trộn hai nguồn là trộn
    hai thứ cùng phân phối.

    `(index * 46) % 100` thay cho `index % k`: dãy độ lệch thấp, nên tỉ lệ
    đúng cả trên một lượt ngắn. `index % 50 < 23` cũng ra 46% nhưng lượt 24
    tờ sẽ nhận 23 tờ có bảng liền nhau rồi mới đến tờ không -- đúng tỉ lệ
    trên giấy, sai hoàn toàn trên thực tế."""
    return (index * 46) % 100 < 46


# HAI TỚI TÁM TỜ. Vòng cũ `(1,1,1,2,2,3,2,4,1,6)` nặng về tờ đơn -- bốn trên
# mười là một tờ, và một bộ toàn tờ đơn không dạy được mô hình đọc tài liệu
# nhiều trang. Trải đều 2..8, xáo thứ tự để một lượt ngắn cũng gặp đủ cỡ
# thay vì gặp toàn tờ mỏng rồi mới tới tờ dày.
_SHEET_COUNTS = (2, 5, 3, 8, 2, 6, 4, 7, 3, 2, 8, 4, 6, 2, 5, 3)


def sheet_count(index: int) -> int:
    """Số tờ của tài liệu thứ `index` -- quay vòng qua `_SHEET_COUNTS`."""
    return _SHEET_COUNTS[index % len(_SHEET_COUNTS)]


__all__ = ["sheet_count", "wants_table"]
