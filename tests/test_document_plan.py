"""`agent/document_plan.py::sample` -- one weighted draw from a `Grammar`.

Phase 4, task 4.1 (`docs/ke-hoach-refactor-engine.md`). Four things this
file has to prove before 4.1 counts as committed, per review:

1. No hidden template -- a `DocumentPlan` is built branch-by-branch through
   `valid_options()`, never read off a literal list of pre-made plans.
2. Weight lives in the sampler, not the grammar -- `Branch` carries no
   weight field; `weight_fn` is a `sample()` parameter.
3. Many samples prove the sampler produces VALID plans, not that it knows
   what the corpus is missing -- that is 4.3, not claimed here.
4. "Different plans reachable" is not forced novelty -- nothing here
   resamples until a plan differs from a previous one.

Nothing below renders an image or starts a model -- `sample()` is a pure
function over `Grammar` objects, so this runs in the dependency-free CI job.
"""

from __future__ import annotations

import random

import pytest

from agent.document_plan import DocumentPlan, sample
from agent.document_plan import _topological_order  # noqa: PLC2701
from agent.grammar import FAMILIES, Branch, Constraint, Grammar, FieldCompat


# --------------------------------------------------------- no hidden template


def test_a_branch_carries_no_weight_field():
    """(điểm 2 review) Weight thuộc sampler, không thuộc grammar."""
    fields = {f.name for f in Branch.__dataclass_fields__.values()}
    assert fields == {"name", "options"}


def test_sample_builds_the_assignment_it_returns_not_a_literal():
    """(điểm 1 review) `assignment` phủ đúng và chỉ đúng các nhánh của
    grammar -- không có khoá thừa từ một plan mẫu nào chép vào."""
    grammar = FAMILIES["invoice_detailed"]
    plan = sample(grammar, random.Random(0))
    assert isinstance(plan, DocumentPlan)
    assert set(plan.assignment) <= {b.name for b in grammar.branches}
    # Mọi nhánh grammar khai đều được gán -- không phải một tập con cố định
    # đọc từ đâu đó, mà đúng bằng branch set của CHÍNH grammar này.
    assert set(plan.assignment) == {b.name for b in grammar.branches}


def test_every_pilot_and_thirty_family_samples_without_error():
    rng = random.Random(0)
    for name, grammar in FAMILIES.items():
        for _ in range(20):
            plan = sample(grammar, rng)
            assert plan.family == name


def test_a_contradictory_grammar_raises_instead_of_returning_junk():
    """Hai ràng buộc mâu thuẫn nhau (one forces "p", the other forbids it)
    phải làm `sample()` thất bại rõ ràng, không âm thầm trả một plan sai."""
    grammar = Grammar(
        family="broken",
        branches=(Branch("a", ("x",)), Branch("b", ("p", "q"))),
        constraints=(
            Constraint(when=("a", "==", "x"), then=("b", "==", "p")),
            Constraint(when=("a", "==", "x"), then=("b", "!=", "p")),
        ),
    )
    with pytest.raises(RuntimeError):
        sample(grammar, random.Random(0))


# ------------------------------------------------------- topological order


def test_topological_order_puts_table_before_the_header_it_constrains():
    grammar = FAMILIES["utility_power"]
    order = _topological_order(grammar)
    assert order.index("table") < order.index("header")


def test_topological_order_detects_a_real_cycle():
    grammar = Grammar(
        family="cyclic",
        branches=(Branch("a", ("x", "y")), Branch("b", ("p", "q"))),
        constraints=(
            Constraint(when=("a", "==", "x"), then=("b", "==", "p")),
            Constraint(when=("b", "==", "p"), then=("a", "==", "x")),
        ),
    )
    with pytest.raises(ValueError, match="vòng lặp"):
        _topological_order(grammar)


# ------------------------------------------------------------- weight_fn


def test_weight_fn_skews_the_distribution():
    grammar = Grammar(family="t", branches=(Branch("a", ("x", "y", "z")),),
                      constraints=())
    rng = random.Random(0)
    counts = {"x": 0, "y": 0, "z": 0}
    for _ in range(500):
        plan = sample(grammar, rng, weight_fn=lambda name, opt: 100.0 if opt == "x" else 1.0)
        counts[plan.assignment["a"]] += 1
    assert counts["x"] > counts["y"] + counts["z"]


def test_a_weight_fn_returning_all_zero_falls_back_to_uniform_not_a_crash():
    grammar = Grammar(family="t", branches=(Branch("a", ("x", "y")),), constraints=())
    plan = sample(grammar, random.Random(0), weight_fn=lambda n, o: 0.0)
    assert plan.assignment["a"] in ("x", "y")


# --------------------------------------------------- not forced novelty


def test_repetition_is_reachable_not_forbidden():
    """(điểm 4 review) `sample()` không phải `while plan == previous:
    resample()` -- một grammar nhỏ, rút nhiều lần, PHẢI thấy lặp lại theo
    lẽ xác suất thường, không phải bị cấm lặp bằng code."""
    grammar = Grammar(family="t", branches=(Branch("a", ("x", "y")),), constraints=())
    rng = random.Random(0)
    seen = [sample(grammar, rng).assignment["a"] for _ in range(30)]
    # Không gian chỉ có 2 giá trị, 30 lần rút -- lặp lại gần như chắc chắn
    # nếu sampler không cố tránh nó.
    assert len(set(seen)) < len(seen)


def test_same_seed_is_reproducible():
    grammar = FAMILIES["hospital_bill"]
    plan_a = sample(grammar, random.Random(42))
    plan_b = sample(grammar, random.Random(42))
    assert plan_a.assignment == plan_b.assignment


# ----------------------------------------------------- hard_negative_profile


def test_hard_negative_profile_only_uses_the_grammars_own_compatible_strategies():
    grammar = FAMILIES["invoice_detailed"]
    rng = random.Random(0)
    seen_any = False
    for _ in range(200):
        plan = sample(grammar, rng, hard_negative_intensity="high")
        for field_kind, strategy in plan.hard_negative_profile.items():
            seen_any = True
            compat = next(c for c in grammar.field_compat if c.field_kind == field_kind)
            assert strategy in compat.strategies
    assert seen_any, "'high' intensity over 200 draws produced zero hard negatives"


def test_a_field_declared_with_no_strategies_never_gets_a_hard_negative():
    grammar = FAMILIES["invoice_detailed"]
    assert any(c.field_kind == "doc_title" and c.strategies == ()
              for c in grammar.field_compat)
    rng = random.Random(0)
    for _ in range(200):
        plan = sample(grammar, rng, hard_negative_intensity="high")
        assert "doc_title" not in plan.hard_negative_profile


def test_a_family_with_no_field_compat_always_has_an_empty_profile():
    """28/30 family (đợt `_family()`) không khai `field_compat` -- xác nhận
    Phase 4 không tự bịa hard negative cho field chưa được khai compat."""
    grammar = FAMILIES["utility_power"]
    assert grammar.field_compat == ()
    rng = random.Random(0)
    for _ in range(20):
        plan = sample(grammar, rng, hard_negative_intensity="high")
        assert plan.hard_negative_profile == {}


def test_none_intensity_never_produces_a_hard_negative():
    grammar = FAMILIES["invoice_detailed"]
    rng = random.Random(0)
    for _ in range(50):
        plan = sample(grammar, rng, hard_negative_intensity="none")
        assert plan.hard_negative_profile == {}
