"""Coverage-aware selection across the three fingerprint tiers.

    from agent.coverage import CoverageMemory, sample_with_coverage

Phase 4, task 4.3. Answers a different question than "have I seen this
exact document before":

    "Which regions of the generation space are already saturated?"

## Why lexicographic (coarse, mid, fine), not a weighted sum

`priority()` returns a plain `(coarse_count, mid_count, fine_count)` tuple
and candidates are ranked by Python's normal tuple comparison -- coarse
count decides first, mid only breaks a coarse tie, fine only breaks a
mid tie. This is a deliberate simplification over "detect which tier is
currently most skewed and weight that one more": it is simple, it is
exactly reproducible, and it already satisfies the concrete case the DoD
names -- two candidates tied on coarse+mid are still told apart by fine.
Revisit if Phase 8's real corpus measurements show coarse-first ordering
produces a bad distribution in practice; nothing here assumes it is the
last word on ranking, only that it is a real, testable first one.

## Not forced uniqueness

`sample_with_coverage()` draws `candidates` independent plans from the
grammar and keeps the one with the lowest (least-seen) priority tuple --
it does not reject a plan for repeating a common configuration, and with
`candidates=1` it degrades to plain `sample()`. "Controlled distribution,
not maximum uniqueness" (mục 5, `docs/ke-hoach-refactor-engine.md`).
"""

from __future__ import annotations

import random
from collections import Counter

from agent.document_plan import DocumentPlan, WeightFn, sample
from agent.fingerprint import Fingerprint, fingerprint
from agent.grammar import Grammar

Priority = tuple[int, int, int]


class CoverageMemory:
    """Ba `Counter` độc lập, một cho mỗi tầng -- không phải một Counter
    trên tuple đã gộp phẳng (đúng lỗi review đã bắt ở đầu Phase 4)."""

    def __init__(self) -> None:
        self._coarse: Counter[tuple] = Counter()
        self._mid: Counter[tuple] = Counter()
        self._fine: Counter[tuple] = Counter()

    def observe(self, fp: Fingerprint) -> None:
        self._coarse[fp.coarse] += 1
        self._mid[fp.mid] += 1
        self._fine[fp.fine] += 1

    def counts(self, fp: Fingerprint) -> dict[str, int]:
        return {"coarse": self._coarse[fp.coarse], "mid": self._mid[fp.mid],
               "fine": self._fine[fp.fine]}

    def priority(self, fp: Fingerprint) -> Priority:
        """Nhỏ hơn = ưu tiên hơn (ít thấy hơn). So sánh tuple Python tự
        làm đúng thứ tự coarse trước, mid phân định khi coarse hoà, fine
        phân định khi cả hai hoà -- xem docstring module."""
        c = self.counts(fp)
        return (c["coarse"], c["mid"], c["fine"])

    def total_observed(self) -> int:
        return sum(self._coarse.values())


def sample_with_coverage(grammar: Grammar, memory: CoverageMemory,
                        rng: random.Random | None = None,
                        candidates: int = 8,
                        weight_fn: WeightFn | None = None,
                        hard_negative_intensity: str | None = None,
                        ) -> tuple[DocumentPlan, Fingerprint]:
    """Rút `candidates` plan độc lập, giữ plan có `priority()` nhỏ nhất,
    ghi nhận (`observe`) rồi trả về CẢ plan lẫn fingerprint của nó -- gọi
    lại `fingerprint()` lần nữa ở caller là lãng phí một việc hàm này đã
    làm.

    `candidates=1` suy biến về `sample()` trần -- không ép coverage, chỉ
    làm sampler THIÊN VỀ vùng thiếu khi có nhiều hơn một lựa chọn để so."""
    rng = rng if rng is not None else random.Random()
    best_plan: DocumentPlan | None = None
    best_fp: Fingerprint | None = None
    best_priority: Priority | None = None
    for _ in range(max(1, candidates)):
        plan = sample(grammar, rng, weight_fn=weight_fn,
                     hard_negative_intensity=hard_negative_intensity)
        fp = fingerprint(plan)
        priority = memory.priority(fp)
        if best_priority is None or priority < best_priority:
            best_plan, best_fp, best_priority = plan, fp, priority
    assert best_plan is not None and best_fp is not None
    memory.observe(best_fp)
    return best_plan, best_fp


__all__ = ["CoverageMemory", "Priority", "sample_with_coverage"]
