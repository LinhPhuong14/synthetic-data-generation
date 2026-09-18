"""Phase 5 (`docs/ke-hoach-refactor-engine.md`): the engine's `DocumentPlan`
is authoritative, the LLM's own `plan` in its JSON answer is not.

- `describe_plan()` -- turns a DocumentPlan into the brief text ask_for()
  sends (task 5.1).
- `plan_conformance_problems()` -- checks HTML against the ENGINE's plan,
  not against the model's self-reported `plan` dict (task 5.2).
- `ask_for()` takes a DocumentPlan and fixes table presence from it, not
  from a separate `wants_table()` roll.
- `one()`'s family/plan sampling is deterministic per (seed, index), so two
  calls with the same seed never disagree about what was asked for.

Nothing below starts a model or opens a browser -- `plan_conformance_
problems`/`describe_plan`/`ask_for` are pure functions over strings and
`DocumentPlan` objects, so this runs in the dependency-free CI job.
"""

from __future__ import annotations

import random

import pytest

from agent.compose_page import (ask_for, describe_plan, plan_conformance_problems)
from agent.document_plan import DocumentPlan, sample
from agent.grammar import FAMILIES

_STUB_KINDS = frozenset({"title", "note", "menu.name", "sign.name",
                         "store.tax_code", "invoice.total"})


@pytest.fixture(autouse=True)
def _stub_kinds(monkeypatch):
    """`ask_for()` calls `kinds()`, which (via `synthgen.llm_page.kinds`)
    renders 300 random engine pages to harvest the real `data-kind`
    vocabulary -- slow, and, right now, broken by unrelated in-progress
    work on `synthgen/markup.py` (confirmed independent of anything in this
    file: `synthgen.llm_page.kinds()` raises `KeyError: 'table'` on its
    own, with nothing from Phase 5 involved). Stub it so these tests check
    what Phase 5 actually changed, not the health of a different track."""
    monkeypatch.setattr("agent.compose_page.kinds", lambda: _STUB_KINDS)

SHEET_WITH_TABLE = ('<div class="sheet"><table><tr><td data-cell="x">'
                    '<span data-kind="menu.name">A</span></td></tr></table></div>')
SHEET_NO_TABLE = '<div class="sheet"><span data-kind="title">A</span></div>'
SHEET_WITH_SIGNATURE = ('<div class="sheet">'
                        '<span data-kind="sign.name">Nguyễn Văn A</span></div>')


# ------------------------------------------------------- plan_conformance_problems


def test_plan_wants_a_table_html_has_none_is_flagged():
    plan = DocumentPlan(family="x", assignment={"table": "simple"})
    found = plan_conformance_problems(plan, SHEET_NO_TABLE)
    assert any("yêu cầu có bảng" in line for line in found)


def test_plan_wants_a_table_html_has_one_is_clean():
    plan = DocumentPlan(family="x", assignment={"table": "simple"})
    assert plan_conformance_problems(plan, SHEET_WITH_TABLE) == []


def test_plan_has_no_table_branch_html_has_a_table_is_flagged():
    plan = DocumentPlan(family="x", assignment={"density": "sparse"})
    found = plan_conformance_problems(plan, SHEET_WITH_TABLE)
    assert any("không có nhánh `table`" in line for line in found)


def test_plan_has_no_table_branch_html_has_none_is_clean():
    plan = DocumentPlan(family="x", assignment={"density": "sparse"})
    assert plan_conformance_problems(plan, SHEET_NO_TABLE) == []


def test_zero_signatures_but_html_has_one_is_flagged():
    plan = DocumentPlan(family="x", assignment={"signature_count": 0})
    found = plan_conformance_problems(plan, SHEET_WITH_SIGNATURE)
    assert any("yêu cầu 0 chữ ký" in line for line in found)


def test_signatures_required_but_html_has_none_is_flagged():
    plan = DocumentPlan(family="x", assignment={"signature_count": 2})
    found = plan_conformance_problems(plan, SHEET_NO_TABLE)
    assert any("yêu cầu 2 chữ ký" in line for line in found)


def test_signatures_required_and_present_is_clean():
    plan = DocumentPlan(family="x", assignment={"signature_count": 1})
    assert plan_conformance_problems(plan, SHEET_WITH_SIGNATURE) == []


def test_no_signature_count_in_plan_is_never_flagged():
    """Family không có nhánh `signature_count` (hiếm, nhưng không phải
    không thể) -- không kiểm được thì không kiểm, không đoán."""
    plan = DocumentPlan(family="x", assignment={"density": "sparse"})
    assert plan_conformance_problems(plan, SHEET_WITH_SIGNATURE) == []


# ------------------------------------------------------------ describe_plan


def test_describe_plan_states_the_family_as_fixed():
    plan = DocumentPlan(family="hospital_bill", assignment={"density": "dense"})
    text = describe_plan(plan)
    assert "hospital_bill" in text
    assert "KHÔNG đổi" in text


def test_describe_plan_says_no_table_explicitly_when_absent():
    plan = DocumentPlan(family="x", assignment={"density": "sparse"})
    assert "KHÔNG" in describe_plan(plan)


def test_describe_plan_includes_hard_negative_profile_when_present():
    plan = DocumentPlan(family="x", assignment={},
                        hard_negative_profile={"store.tax_code": "lexical"})
    text = describe_plan(plan)
    assert "store.tax_code" in text
    assert "lexical" in text


def test_describe_plan_omits_hard_negative_section_when_empty():
    plan = DocumentPlan(family="x", assignment={})
    assert "hard negatives" not in describe_plan(plan)


# --------------------------------------------------------------- ask_for


def test_ask_for_tells_the_model_to_realize_not_invent():
    plan = sample(FAMILIES["hospital_bill"], random.Random(0))
    brief = ask_for(0, [], plan, sheets=2, lang="en")
    assert "REALIZE" in brief
    assert "INVENT the document" not in brief


def test_ask_for_table_instruction_matches_the_plans_table_branch():
    with_table = sample(FAMILIES["invoice_detailed"], random.Random(1))
    brief = ask_for(0, [], with_table, sheets=1, lang="en")
    if "table" in with_table.assignment:
        assert "HAS an item table" in brief
    else:
        assert "no item table at all" in brief


def test_ask_for_runs_for_every_family_without_crashing():
    rng = random.Random(0)
    for name, grammar in FAMILIES.items():
        plan = sample(grammar, rng)
        brief = ask_for(0, [], plan, sheets=2, lang="en")
        assert name in brief or plan.family in brief
