"""`agent/fingerprint.py::fingerprint` -- coarse/mid/fine, not a flat tuple.

Phase 4, task 4.2. Nothing below renders an image or starts a model, so
this runs in the dependency-free CI job.
"""

from __future__ import annotations

from agent.document_plan import DocumentPlan
from agent.fingerprint import fingerprint


def test_two_plans_sharing_coarse_and_mid_but_differing_in_fine_are_distinguished():
    """DoD của 4.3 đọc thẳng ở tầng 4.2: hai plan trùng coarse+mid nhưng
    khác fine vẫn phải phân biệt được."""
    base = {"table": "simple", "header": "compact", "density": "medium"}
    plan_a = DocumentPlan(family="invoice_detailed",
                          assignment={**base, "signature_count": 1})
    plan_b = DocumentPlan(family="invoice_detailed",
                          assignment={**base, "signature_count": 2})
    fp_a, fp_b = fingerprint(plan_a), fingerprint(plan_b)
    assert fp_a.coarse == fp_b.coarse
    assert fp_a.mid == fp_b.mid
    assert fp_a.fine != fp_b.fine


def test_two_plans_differing_in_density_have_different_coarse():
    plan_a = DocumentPlan(family="f", assignment={"density": "sparse"})
    plan_b = DocumentPlan(family="f", assignment={"density": "dense"})
    assert fingerprint(plan_a).coarse != fingerprint(plan_b).coarse


def test_two_plans_differing_only_in_table_morphology_share_coarse_not_mid():
    plan_a = DocumentPlan(family="f", assignment={"density": "medium", "table": "simple"})
    plan_b = DocumentPlan(family="f", assignment={"density": "medium", "table": "grouped"})
    fp_a, fp_b = fingerprint(plan_a), fingerprint(plan_b)
    assert fp_a.coarse == fp_b.coarse   # cả hai đều "có table"
    assert fp_a.mid != fp_b.mid         # nhưng khác kiểu bảng


def test_table_presence_not_just_value_affects_coarse():
    with_table = DocumentPlan(family="f", assignment={"density": "medium", "table": "simple"})
    without_table = DocumentPlan(family="f", assignment={"density": "medium"})
    assert fingerprint(with_table).coarse != fingerprint(without_table).coarse


def test_hard_negative_profile_is_part_of_fine_only():
    base = {"density": "medium", "table": "simple"}
    plan_a = DocumentPlan(family="f", assignment=dict(base), hard_negative_profile={})
    plan_b = DocumentPlan(family="f", assignment=dict(base),
                          hard_negative_profile={"store.tax_code": "lexical"})
    fp_a, fp_b = fingerprint(plan_a), fingerprint(plan_b)
    assert fp_a.coarse == fp_b.coarse
    assert fp_a.mid == fp_b.mid
    assert fp_a.fine != fp_b.fine


def test_render_extra_only_touches_fine():
    plan = DocumentPlan(family="f", assignment={"density": "medium"})
    fp_plain = fingerprint(plan)
    fp_with_render = fingerprint(plan, render_extra=(("box_count", 42),))
    assert fp_plain.coarse == fp_with_render.coarse
    assert fp_plain.mid == fp_with_render.mid
    assert fp_plain.fine != fp_with_render.fine
    assert ("box_count", 42) in fp_with_render.fine


def test_a_family_without_mid_branches_gets_an_empty_mid_not_an_error():
    plan = DocumentPlan(family="f", assignment={"density": "sparse"})
    fp = fingerprint(plan)
    assert fp.mid == ()


def test_fingerprint_is_hashable_for_use_as_a_counter_key():
    plan = DocumentPlan(family="invoice_detailed",
                        assignment={"table": "simple", "density": "medium"})
    fp = fingerprint(plan)
    {fp.coarse: 1, fp.mid: 1, fp.fine: 1}  # raises if any tier is unhashable
