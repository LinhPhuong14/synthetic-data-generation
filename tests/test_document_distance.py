"""Phase 7 (`docs/ke-hoach-refactor-engine.md`): document-diversity distance,
independent of geometry.

Nothing below renders an image, draws a phôi, or starts a model --
`distance()`/`corpus_diversity()` are pure functions over `Fingerprint`
tuples, so this runs in the dependency-free CI job, same as
`tests/test_fingerprint.py` and `tests/test_coverage.py`.
"""

from __future__ import annotations

import random

from agent.document_distance import corpus_diversity, distance
from agent.document_plan import DocumentPlan, sample
from agent.fingerprint import fingerprint
from agent.grammar import FAMILIES

# ---------------------------------------------------------------- distance()


def test_the_same_plan_has_zero_distance_from_itself():
    plan = sample(FAMILIES["invoice_detailed"], random.Random(0))
    fp = fingerprint(plan)
    assert distance(fp, fp) == 0.0


def test_differing_only_in_fine_scores_one_third():
    """Cùng family/density/table (nên cùng coarse), cùng giá trị `table`
    (nên cùng mid), khác nhau ở một nhánh KHÔNG thuộc coarse/mid -- chỉ
    `fine` lệch."""
    a = DocumentPlan(family="x", assignment={"density": "sparse",
                                             "table": "simple", "extra": "a"})
    b = DocumentPlan(family="x", assignment={"density": "sparse",
                                             "table": "simple", "extra": "b"})
    fp_a, fp_b = fingerprint(a), fingerprint(b)
    assert fp_a.coarse == fp_b.coarse
    assert fp_a.mid == fp_b.mid
    assert fp_a.fine != fp_b.fine
    assert distance(fp_a, fp_b) == 1 / 3


def test_differing_at_every_tier_scores_one():
    a = DocumentPlan(family="invoice", assignment={"density": "sparse", "table": "simple"})
    b = DocumentPlan(family="contract", assignment={"density": "dense", "table": "grouped"})
    fp_a, fp_b = fingerprint(a), fingerprint(b)
    assert fp_a.coarse != fp_b.coarse
    assert fp_a.mid != fp_b.mid
    assert fp_a.fine != fp_b.fine
    assert distance(fp_a, fp_b) == 1.0


def test_differing_family_alone_with_ties_elsewhere_scores_two_thirds():
    """Family/density khác (coarse lệch) nhưng cả hai không có nhánh nào
    thuộc `_MID_BRANCHES` -- mid hoà ở tuple rỗng, chỉ coarse và fine lệch."""
    a = DocumentPlan(family="invoice", assignment={"density": "sparse"})
    b = DocumentPlan(family="contract", assignment={"density": "dense"})
    fp_a, fp_b = fingerprint(a), fingerprint(b)
    assert fp_a.coarse != fp_b.coarse
    assert fp_a.mid == fp_b.mid  # cả hai rỗng
    assert fp_a.fine != fp_b.fine
    assert distance(fp_a, fp_b) == 2 / 3


def test_distance_is_symmetric():
    plans = [sample(FAMILIES[name], random.Random(i))
            for i, name in enumerate(sorted(FAMILIES)[:5])]
    fps = [fingerprint(p) for p in plans]
    for a in fps:
        for b in fps:
            assert distance(a, b) == distance(b, a)


def test_distance_is_between_zero_and_one():
    plans = [sample(FAMILIES[name], random.Random(i))
            for i, name in enumerate(sorted(FAMILIES))]
    fps = [fingerprint(p) for p in plans]
    for a in fps:
        for b in fps:
            d = distance(a, b)
            assert 0.0 <= d <= 1.0


# --------------------------------------------------- corpus_diversity()


def test_corpus_diversity_of_a_single_document_has_no_pairwise_mean():
    fp = fingerprint(sample(FAMILIES["invoice_detailed"], random.Random(0)))
    out = corpus_diversity([fp])
    assert out["documents"] == 1
    assert out["mean_pairwise_distance"] is None


def test_corpus_diversity_of_identical_fingerprints_is_zero():
    fp = fingerprint(sample(FAMILIES["invoice_detailed"], random.Random(0)))
    out = corpus_diversity([fp, fp, fp])
    assert out["distinct_coarse"] == 1
    assert out["distinct_fine"] == 1
    assert out["mean_pairwise_distance"] == 0.0


def test_corpus_diversity_across_every_family_is_clearly_nonzero():
    plans = [sample(FAMILIES[name], random.Random(i))
            for i, name in enumerate(sorted(FAMILIES))]
    fps = [fingerprint(p) for p in plans]
    out = corpus_diversity(fps)
    assert out["documents"] == len(FAMILIES)
    assert out["distinct_coarse"] > 1
    assert out["mean_pairwise_distance"] > 0.5


# -------------------------------- mục 49 (tư duy gốc): dressing != document

def test_one_document_rendered_a_hundred_ways_is_zero_document_diversity():
    """1 document x 100 dressing KHÔNG PHẢI 100 document diversity.

    Dressing (font, màu, khoảng cách, bố cục hình học) không đụng tới
    `DocumentPlan.assignment` -- không dòng nào trong `agent/document_plan.py`
    hay `agent/grammar.py` đọc/ghi thứ đó. Nên `fingerprint()` của CÙNG một
    plan là y hệt nhau dù trang được "mặc" 100 kiểu khác nhau -- module này
    không đọc render nên không thể thấy dressing thay đổi, đúng như tên
    Phase 7 đặt ra: hai trục trực giao NHỜ CẤU TRÚC, không phải quy ước."""
    plan = sample(FAMILIES["insurance_property_contract"], random.Random(7))
    # "100 dressing" của CÙNG một document: gọi lại fingerprint() trên cùng
    # plan nhiều lần, y hệt cách 100 lượt vẽ khác nhau vẫn cùng một
    # DocumentPlan bên dưới.
    fps = [fingerprint(plan) for _ in range(100)]
    out = corpus_diversity(fps)
    assert out["distinct_coarse"] == 1
    assert out["distinct_mid"] == 1
    assert out["distinct_fine"] == 1
    assert out["mean_pairwise_distance"] == 0.0

    # Đối chứng: 100 document THẬT SỰ khác nhau (family khác nhau, DocumentPlan
    # khác nhau) đo được diversity rõ ràng khác 0 -- hai trục là hai thứ khác
    # nhau, không phải cùng một số đo gọi bằng hai tên.
    different_plans = [sample(FAMILIES[sorted(FAMILIES)[i % len(FAMILIES)]],
                              random.Random(i))
                       for i in range(100)]
    different_out = corpus_diversity([fingerprint(p) for p in different_plans])
    assert different_out["mean_pairwise_distance"] > out["mean_pairwise_distance"]
    assert different_out["distinct_coarse"] > 1
