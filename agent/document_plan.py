"""`DocumentPlan` -- one sampled, constraint-satisfying instance of a `Grammar`.

    from agent.document_plan import DocumentPlan, sample

Phase 4 of `docs/ke-hoach-refactor-engine.md`, task 4.1. `agent/grammar.py`
defines the valid SPACE (Phase 3); this module draws ONE point from it.

## Sampled, not literal

The YAML example in the original design note (mục 4) wrote a `DocumentPlan`
as a fixed literal -- `table: {morphology: grouped, columns: 7, rows: 14}`,
one value per field. Applied literally that is the same "phôi đã khai sẵn"
architecture `agent/compose_page.py::schema()`'s own docstring says already
collapsed a corpus once (see G1, top of the plan doc): the model filled in
a pre-declared mold and thirty pages came out of the same shape. `sample()`
below returns a fresh, weighted DRAW every call -- "different plans must be
reachable and sampled according to weighted distributions and coverage
state; the sampler must not require every consecutive sample to be unique"
(the review correction that landed on this exact line). A `DocumentPlan`
that repeats a common combination is not a bug; a `DocumentPlan` that could
ONLY ever produce one combination per family would be.

## Why topological order, not rejection sampling

A `Grammar`'s constraints are directed: `Constraint.then` depends on
`Constraint.when`. Assigning branches in an order where every `when` branch
is already fixed before its dependent `then` branch is sampled means
`valid_options()` always sees a complete picture and never needs to guess
or retry -- no rejection loop, no risk of picking a value now that turns
out unreachable once a later branch is fixed. `_topological_order()` proves
this order exists (raises on a cycle, which none of the 30 families in
`agent/grammar.py` have) and computes it once per `sample()` call.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from agent.grammar import Grammar, valid_options

WeightFn = Callable[[str, Any], float]

# Hồ sơ cường độ hard-negative -- mục 13 (page.md)/mục 21 (SYSTEM_PROMPT.md)
# đặt tên "none/low/medium/high" cho concept này; xác suất mỗi field ĐỦ
# ĐIỀU KIỆN (có strategy trong field_compat) thực sự nhận một hard negative.
# Số chưa đo trên dữ liệu thật -- đặt hợp lý, giống mọi tham số khác của
# Phase 4 trước khi có corpus thật để hiệu chỉnh (xem `docs/ke-hoach-
# refactor-engine.md` Phase 8).
INTENSITY_LEVELS = ("none", "low", "medium", "high")
_INTENSITY_PROBABILITY = {"none": 0.0, "low": 0.15, "medium": 0.4, "high": 0.7}


@dataclass(frozen=True)
class DocumentPlan:
    """Một draw từ một `Grammar`: gán đủ mọi nhánh, cộng hồ sơ hard-negative
    đã rút tương thích với `field_compat` của chính family đó.

    `assignment` là nguồn sự thật cho Phase 5 (LLM context) -- không phải
    plan model tự viết lại. Xem G-điểm-3 (review) trong plan doc."""

    family: str
    assignment: dict[str, Any]
    hard_negative_profile: dict[str, str] = field(default_factory=dict)


def _topological_order(grammar: Grammar) -> list[str]:
    """Thứ tự gán sao cho `when` luôn có giá trị trước `then` của nó.

    Ném lỗi nếu có vòng lặp -- phòng thủ cho grammar tương lai; cả hai
    family thí điểm và 28 family dựng từ `_family()` trong `agent/grammar.py`
    hôm nay không family nào có vòng."""
    names = [b.name for b in grammar.branches]
    deps: dict[str, set[str]] = {n: set() for n in names}
    for c in grammar.constraints:
        when_branch = c.when[0]
        then_branch = c.then[0]
        if when_branch in deps and then_branch in deps:
            deps[then_branch].add(when_branch)

    ordered: list[str] = []
    seen: set[str] = set()

    def visit(name: str, stack: tuple[str, ...]) -> None:
        if name in seen:
            return
        if name in stack:
            raise ValueError(
                f"vòng lặp ràng buộc trong grammar {grammar.family!r}: "
                f"{' -> '.join(stack + (name,))}")
        for dep in deps[name]:
            visit(dep, stack + (name,))
        seen.add(name)
        ordered.append(name)

    for name in names:
        visit(name, ())
    return ordered


def _sample_hard_negatives(grammar: Grammar, rng: random.Random,
                          intensity: str | None = None) -> dict[str, str]:
    """Rút hồ sơ hard-negative TỪ `grammar.field_compat` -- không có field
    nào ở đây nhận một strategy nó không khai là hợp lệ (task 3.4's DoD,
    đọc lại ở tầng sample)."""
    eligible = [fc for fc in grammar.field_compat if fc.strategies]
    if not eligible:
        return {}
    intensity = intensity if intensity is not None else rng.choice(INTENSITY_LEVELS)
    probability = _INTENSITY_PROBABILITY[intensity]
    profile: dict[str, str] = {}
    for compat in eligible:
        if rng.random() < probability:
            profile[compat.field_kind] = rng.choice(compat.strategies)
    return profile


def sample(grammar: Grammar, rng: random.Random | None = None,
          weight_fn: WeightFn | None = None,
          hard_negative_intensity: str | None = None) -> DocumentPlan:
    """Một draw có trọng số, luôn thoả mọi ràng buộc.

    `weight_fn(branch_name, option) -> float`, mặc định đều (uniform). Đây
    là chỗ Phase 4.3 (coverage memory) cắm vào: một caller muốn ưu tiên tổ
    hợp thiếu coverage truyền `weight_fn` ưu tiên option ít gặp nhất trong
    corpus -- hàm này không cần biết gì về coverage, chỉ biết cách dùng một
    trọng số. Trọng số âm hoặc tổng bằng 0 rơi về đều, không lỗi -- một
    `weight_fn` tính sai không nên làm sampler chết."""
    rng = rng if rng is not None else random.Random()
    order = _topological_order(grammar)
    assignment: dict[str, Any] = {}
    for name in order:
        options = valid_options(grammar, name, assignment)
        if not options:
            raise RuntimeError(
                f"{grammar.family}.{name}: không còn lựa chọn nào hợp lệ với "
                f"{assignment} -- kiểm lại ràng buộc của grammar này, có thể "
                "đang mâu thuẫn nhau")
        if weight_fn is None:
            choice = rng.choice(options)
        else:
            weights = [max(0.0, weight_fn(name, option)) for option in options]
            choice = (rng.choices(options, weights=weights, k=1)[0]
                     if sum(weights) > 0 else rng.choice(options))
        assignment[name] = choice
    hard_negatives = _sample_hard_negatives(grammar, rng, hard_negative_intensity)
    return DocumentPlan(family=grammar.family, assignment=assignment,
                        hard_negative_profile=hard_negatives)


__all__ = ["INTENSITY_LEVELS", "DocumentPlan", "WeightFn", "sample"]
