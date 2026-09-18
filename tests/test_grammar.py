"""`agent/grammar.py` -- compositional constraint space, not a Cartesian
product (Phase 3, `docs/ke-hoach-refactor-engine.md`).

Nothing below renders an image or starts a model -- `Grammar` is plain
dataclasses and `space_size`/`valid_options` are pure functions over them,
so this runs in the dependency-free CI job.
"""

from __future__ import annotations

from agent.grammar import (FAMILIES, STRATEGIES, Branch, Constraint,
                          FieldCompat, Grammar, space_size, valid_options)


def _toy_grammar(constrained: bool = True) -> Grammar:
    """2 nhánh x 3 lựa chọn = 9 thô. `b` bị `a == "x"` xoá còn 1/3 lựa chọn
    -> 3 + 6 = ... tính tay dưới, đừng đoán."""
    constraints = ()
    if constrained:
        constraints = (Constraint(when=("a", "==", "x"), then=("b", "==", "p")),)
    return Grammar(
        family="toy",
        branches=(Branch("a", ("x", "y", "z")), Branch("b", ("p", "q", "r"))),
        constraints=constraints,
    )


# --------------------------------------------------------------- space_size


def test_no_constraints_means_constrained_equals_raw():
    result = space_size(_toy_grammar(constrained=False))
    assert result == {"raw": 9, "constrained": 9, "cut": 0}


def test_a_real_constraint_cuts_the_space_by_hand_computed_amount():
    # a=x forces b=p (1 combo instead of 3): -2. a=y, a=z unconstrained: 3+3.
    # constrained = 1 + 3 + 3 = 7, cut = 2.
    result = space_size(_toy_grammar(constrained=True))
    assert result == {"raw": 9, "constrained": 7, "cut": 2}


def test_every_family_has_a_real_not_decorative_constraint():
    for name, grammar in FAMILIES.items():
        result = space_size(grammar)
        assert result["cut"] > 0, (
            f"{name}: constraints removed nothing -- decorative, not real "
            "(Phase 3 DoD)")
        assert result["constrained"] < result["raw"]


def test_thirty_family_pass_plus_the_two_hand_reasoned_pilots():
    """`docs/ke-hoach-refactor-engine.md` Phase 3.1 mở rộng: 30 tên thật lấy
    từ `rulebase/documents/*.yaml`, cộng hai family thí điểm đã đối chiếu
    trước đó (`invoice_detailed`, `insurance_property_contract`) -- không
    còn nhãn chung "invoice"/"contract"/"certificate" song song với tên
    thật, tám loại certificate cụ thể nằm trong 30."""
    assert len(FAMILIES) == 30
    assert "invoice_detailed" in FAMILIES
    assert "insurance_property_contract" in FAMILIES
    assert "invoice" not in FAMILIES
    assert "certificate" not in FAMILIES
    certificates = [n for n in FAMILIES if n.startswith("insurance_") and
                    n.endswith("_certificate")]
    assert len(certificates) == 5


def test_every_family_traces_to_a_real_rulebase_source():
    """Không family nào trong đợt 30 thiếu nguồn đối chiếu (`_SOURCE`)."""
    from agent.grammar import _SOURCE
    thirty = set(FAMILIES) - {"invoice_detailed", "insurance_property_contract"}
    assert thirty == set(_SOURCE)
    for name, info in _SOURCE.items():
        assert info["doc"], name
        assert info["layout"], name


# ------------------------------------------------------------ valid_options


def test_valid_options_is_unrestricted_with_no_matching_constraint():
    grammar = _toy_grammar()
    assert valid_options(grammar, "b", {"a": "y"}) == ["p", "q", "r"]


def test_valid_options_narrows_once_the_condition_holds():
    grammar = _toy_grammar()
    assert valid_options(grammar, "b", {"a": "x"}) == ["p"]


def test_valid_options_ignores_a_condition_on_an_unassigned_branch():
    grammar = _toy_grammar()
    assert valid_options(grammar, "b", {}) == ["p", "q", "r"]


def test_invoice_header_narrows_when_table_is_complex():
    grammar = FAMILIES["invoice_detailed"]
    narrowed = valid_options(grammar, "header", {"table": "multi_tier"})
    assert set(narrowed) == {"two_column", "compact"}
    unrestricted = valid_options(grammar, "header", {"table": "simple"})
    assert set(unrestricted) == {"centered", "left_aligned", "two_column", "compact"}


# ---------------------------------------------------------------- operators


def test_not_equal_operator():
    grammar = Grammar(
        family="t", branches=(Branch("a", ("x", "y")), Branch("b", ("p", "q"))),
        constraints=(Constraint(when=("a", "==", "x"), then=("b", "!=", "p")),))
    assert valid_options(grammar, "b", {"a": "x"}) == ["q"]


def test_not_in_operator():
    grammar = Grammar(
        family="t", branches=(Branch("a", ("x",)), Branch("b", ("p", "q", "r"))),
        constraints=(Constraint(when=("a", "==", "x"),
                               then=("b", "not in", ("p", "q"))),))
    assert valid_options(grammar, "b", {"a": "x"}) == ["r"]


# -------------------------------------------------------------- field_compat


def test_a_field_with_no_plausible_decoy_declares_an_empty_tuple_not_a_gap():
    for grammar in FAMILIES.values():
        for compat in grammar.field_compat:
            assert isinstance(compat.strategies, tuple)


def test_doc_title_has_no_hard_negative_strategy_in_any_family():
    for grammar in FAMILIES.values():
        for compat in grammar.field_compat:
            if compat.field_kind == "doc_title":
                assert compat.strategies == ()


def test_every_declared_strategy_is_a_known_strategy():
    for grammar in FAMILIES.values():
        for compat in grammar.field_compat:
            for strategy in compat.strategies:
                assert strategy in STRATEGIES


def test_field_compat_lookup_raises_on_an_unknown_branch():
    import pytest
    with pytest.raises(KeyError):
        FAMILIES["invoice_detailed"].branch("not_a_real_branch")


# ------------------------------------------------------- generic 30-family


def test_a_family_with_no_signature_data_gets_a_zero_floor_not_negative():
    from agent.grammar import _sig_options
    assert _sig_options(0) == (0, 1)
    assert _sig_options(1) == (0, 1, 2)
    assert _sig_options(5) == (4, 5, 6)


def test_a_family_without_a_table_in_its_source_has_no_table_branch():
    grammar = FAMILIES["insurance_auto_certificate"]
    assert "table" not in [b.name for b in grammar.branches]


def test_a_family_with_a_table_in_its_source_has_one():
    grammar = FAMILIES["utility_power"]
    assert "table" in [b.name for b in grammar.branches]


def test_a_family_with_no_parties_section_has_no_party_block_branch():
    grammar = FAMILIES["form_activity"]
    assert "party_block" not in [b.name for b in grammar.branches]


def test_high_signature_count_families_get_a_layout_branch():
    grammar = FAMILIES["cash_receipt_voucher"]      # sig=5 -> options include >=3
    assert "signature_layout" in [b.name for b in grammar.branches]


def test_low_signature_count_families_skip_the_layout_branch():
    grammar = FAMILIES["insurance_health_id_card"]  # sig=0 -> options (0, 1)
    assert "signature_layout" not in [b.name for b in grammar.branches]
