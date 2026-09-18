"""`agent/coverage.py` -- coverage memory across coarse/mid/fine tiers.

Phase 4, task 4.3. Nothing below renders an image or starts a model, so
this runs in the dependency-free CI job.
"""

from __future__ import annotations

import random

from agent.coverage import CoverageMemory, sample_with_coverage
from agent.document_plan import DocumentPlan
from agent.fingerprint import fingerprint
from agent.grammar import FAMILIES


def _plan(**assignment):
    return DocumentPlan(family="f", assignment=assignment)


# --------------------------------------------------------------- CoverageMemory


def test_an_unseen_fingerprint_has_zero_counts_everywhere():
    memory = CoverageMemory()
    fp = fingerprint(_plan(density="sparse"))
    assert memory.counts(fp) == {"coarse": 0, "mid": 0, "fine": 0}


def test_observing_increments_all_three_tiers():
    memory = CoverageMemory()
    fp = fingerprint(_plan(density="sparse", table="simple"))
    memory.observe(fp)
    counts = memory.counts(fp)
    assert counts["coarse"] == 1
    assert counts["mid"] == 1
    assert counts["fine"] == 1


def test_same_coarse_and_mid_different_fine_are_told_apart():
    """DoD literal của 4.3: hai plan trùng coarse+mid nhưng khác fine vẫn
    được coverage phân biệt."""
    memory = CoverageMemory()
    base = dict(table="simple", header="compact", density="medium")
    fp_a = fingerprint(DocumentPlan(family="f", assignment={**base, "signature_count": 1}))
    fp_b = fingerprint(DocumentPlan(family="f", assignment={**base, "signature_count": 2}))
    memory.observe(fp_a)
    memory.observe(fp_a)
    memory.observe(fp_a)
    counts_a, counts_b = memory.counts(fp_a), memory.counts(fp_b)
    assert counts_a["coarse"] == counts_b["coarse"] == 3
    assert counts_a["mid"] == counts_b["mid"] == 3
    assert counts_a["fine"] == 3
    assert counts_b["fine"] == 0
    # priority phải phản ánh đúng: fp_b (chưa từng thấy ở fine) ưu tiên hơn
    assert memory.priority(fp_b) < memory.priority(fp_a)


def test_priority_is_coarse_first_lexicographic():
    memory = CoverageMemory()
    common = fingerprint(_plan(density="dense"))
    rare = fingerprint(_plan(density="sparse"))
    for _ in range(5):
        memory.observe(common)
    # `rare` chưa được `observe()` lần nào -- vẫn phải đọc là hoàn toàn mới,
    # kể cả khi nó chia sẻ bucket `mid` rỗng với `common` (không nhánh nào
    # thuộc `_MID_BRANCHES` có mặt trong assignment của cả hai plan).
    assert memory.priority(rare) < memory.priority(common)
    assert memory.priority(rare)[0] == 0        # coarse: chưa từng thấy
    assert memory.priority(common) == (5, 5, 5)


def test_total_observed_counts_every_observation():
    memory = CoverageMemory()
    memory.observe(fingerprint(_plan(density="sparse")))
    memory.observe(fingerprint(_plan(density="dense")))
    assert memory.total_observed() == 2


# ----------------------------------------------------------- sample_with_coverage


def test_sample_with_coverage_records_what_it_returns():
    grammar = FAMILIES["hospital_bill"]
    memory = CoverageMemory()
    plan, fp = sample_with_coverage(grammar, memory, random.Random(0), candidates=4)
    assert memory.counts(fp)["fine"] == 1
    assert fingerprint(plan) == fp


def test_more_candidates_favours_underrepresented_configurations():
    """Với một grammar nhỏ (2 lựa chọn), sau khi một giá trị đã bị chọn
    nhiều lần, `candidates>1` phải thiên về giá trị còn lại nhiều hơn hẳn
    so với `candidates=1` (không thiên vị gì)."""
    from agent.grammar import Branch, Grammar
    tiny = Grammar(family="tiny", branches=(Branch("a", ("x", "y")),), constraints=())

    memory = CoverageMemory()
    rng = random.Random(0)
    # Gieo trước: "x" đã bị chọn rất nhiều lần.
    for _ in range(50):
        memory.observe(fingerprint(DocumentPlan(family="tiny", assignment={"a": "x"})))

    picks_biased = []
    for _ in range(60):
        plan, fp = sample_with_coverage(tiny, memory, rng, candidates=8)
        picks_biased.append(plan.assignment["a"])
        memory.observe(fp)

    # "y" phải được rút áp đảo, vì "x" đã bão hoà từ trước.
    assert picks_biased.count("y") > picks_biased.count("x")


def test_candidates_one_degrades_to_plain_sampling_not_an_error():
    grammar = FAMILIES["insurance_health_id_card"]
    memory = CoverageMemory()
    plan, fp = sample_with_coverage(grammar, memory, random.Random(0), candidates=1)
    assert plan.family == "insurance_health_id_card"


def test_sample_with_coverage_never_crashes_across_all_thirty_families():
    rng = random.Random(0)
    for name, grammar in FAMILIES.items():
        memory = CoverageMemory()
        for _ in range(10):
            plan, fp = sample_with_coverage(grammar, memory, rng, candidates=4)
            assert plan.family == name
