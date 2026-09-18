"""How different two track-3 documents are STRUCTURALLY -- never geometry.

    from agent.document_distance import distance, corpus_diversity

Phase 7, task 7.2 (`docs/ke-hoach-refactor-engine.md`), corresponds to
sections 6/14 of the original design doc. `agent/distance.py` answers "how
far did dressing move the boxes on THIS phôi" -- a question about pixels,
and one that only makes sense for track 1 (a phôi rendered twice, once
plain, once dressed). Track 3 has no phôi and no second render to diff
against; what varies between two LLM-written documents is not geometry, it
is which family/density/table-morphology/field-composition the engine's
`DocumentPlan` (Phase 3-4) drew. This module measures THAT, reading only
`agent.fingerprint.Fingerprint` -- never a box, never a pixel.

## Why a plain fraction, not a weighted score

`agent/coverage.py` already made this call for priority ranking and the
same reasoning applies here: a weighted sum ("coarse counts for 0.6, mid
for 0.3, fine for 0.1") requires picking numbers nobody can justify. Three
tiers, three yes/no questions -- how many of them differ is the whole
metric, so `distance()` is exactly `differing_tiers / 3`. 0.0 is the same
plan; 1.0 differs at every tier including family/density (`coarse`).

## The point of this module (task 7.2's DoD)

Dressing lives entirely outside `DocumentPlan` -- nothing in `agent/
document_plan.py` or `agent/grammar.py` reads or writes pixels, fonts, or
margins. So `fingerprint(plan)` of the SAME plan is identical no matter how
many times (or how differently) that plan gets rendered -- document
diversity and dressing diversity are orthogonal by construction, not by
convention. `tests/test_document_distance.py` demonstrates this concretely
(mục 49, tư duy gốc): one document rendered 100 different ways measures 0.0
document-diversity distance across all 100, because this module never reads
the render at all."""

from __future__ import annotations

from agent.fingerprint import Fingerprint

TIERS = ("coarse", "mid", "fine")


def distance(a: Fingerprint, b: Fingerprint) -> float:
    """Fraction of the three tiers that differ -- 0.0 (same plan) to 1.0
    (differs even at family/density, the broadest tier)."""
    differing = sum(getattr(a, tier) != getattr(b, tier) for tier in TIERS)
    return differing / len(TIERS)


def corpus_diversity(fingerprints: list[Fingerprint]) -> dict:
    """Corpus-level summary: how much of the structural space a batch
    touched, and how different its documents are from each other.

    `distinct_*` answers "how many different (coarse/mid/fine) buckets did
    this batch land in" -- the same question `agent/coverage.py::
    CoverageMemory` tracks live during generation, read back after the fact.
    `mean_pairwise_distance` answers a different question, "on average, how
    far apart are two documents drawn from this batch" -- the mean of
    `distance()` over every unordered pair. O(n^2) comparisons of small
    tuples; at corpus sizes this pipeline actually produces (hundreds, not
    millions) that is microseconds, not a scaling concern."""
    n = len(fingerprints)
    out = {
        "documents": n,
        "distinct_coarse": len({fp.coarse for fp in fingerprints}),
        "distinct_mid": len({fp.mid for fp in fingerprints}),
        "distinct_fine": len({fp.fine for fp in fingerprints}),
        "mean_pairwise_distance": None,
    }
    if n < 2:
        return out
    total = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += distance(fingerprints[i], fingerprints[j])
            pairs += 1
    out["mean_pairwise_distance"] = round(total / pairs, 4)
    return out


__all__ = ["TIERS", "corpus_diversity", "distance"]
