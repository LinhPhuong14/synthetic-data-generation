"""Three-tier document fingerprint -- coarse/mid/fine, not a flat tuple.

    from agent.fingerprint import fingerprint

Phase 4, task 4.2 (`docs/ke-hoach-refactor-engine.md`). The review
correction this answers: coverage keyed on one flat tuple
(`family x density x table`) cannot tell two documents apart that share
those three values but differ in field composition or component detail --
and cannot tell that a document is *close* to another at a coarse level
even when they differ in every fine-grained way. Three separate tuples,
checked separately by `agent/coverage.py` (task 4.3), fix both problems at
once.

## What goes in which tier, and why

- **coarse** -- `family`, `density`, and whether a `table`/`party_block`
  block exists at all. The broadest facts: "is this roughly the same KIND
  of document." Two auto-insurance certificates are coarse-identical even
  if one has two signers and the other three.
- **mid** -- the actual VALUE of the structural branches (table morphology,
  header topology, signature layout) when present. Two documents can share
  a coarse fingerprint and still differ here -- a grouped-table invoice and
  a simple-table invoice are coarse-identical, mid-different.
- **fine** -- the complete `assignment` (every branch, sorted) plus the
  `hard_negative_profile`. The full picture; two documents are fine-identical
  only if `sample()` drew the literal same plan.

Each tier is a strict refinement of the one before it: same coarse is
necessary but not sufficient for same mid; same mid is necessary but not
sufficient for same fine. `fingerprint()` takes only a `DocumentPlan` today
-- the DoD mentions deriving one from "a DocumentPlan + render result" too,
but no render-derived signal (geometry, actual box count) exists yet in
this pipeline for grammar-sampled documents (Phase 5 is what would produce
one) -- `render_extra` is accepted and folded into `fine` when a caller has
it, so this does not need to change shape once that exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.document_plan import DocumentPlan

# Nhánh nào thuộc tầng nào. Không phải mọi grammar có đủ ba nhánh này --
# `_MID_BRANCHES` chỉ được đọc nếu có mặt trong `plan.assignment` (28/30
# family không có `party_block` khi rulebase không xác nhận có -- xem
# `agent/grammar.py::_family`), nên thiếu một nhánh không phải lỗi.
_COARSE_PRESENCE_BRANCHES = ("table", "party_block")
_MID_BRANCHES = ("table", "header", "signature_layout")


@dataclass(frozen=True)
class Fingerprint:
    coarse: tuple[Any, ...]
    mid: tuple[Any, ...]
    fine: tuple[Any, ...]


def fingerprint(plan: DocumentPlan, render_extra: tuple[Any, ...] = ()) -> Fingerprint:
    """Ba tuple riêng biệt cho một `DocumentPlan`.

    `render_extra` là chỗ cắm cho tín hiệu đọc được sau khi vẽ (số hộp thật,
    tỉ lệ lấp trang...) một khi Phase 5 có nó -- gộp vào `fine`, không đổi
    hình dạng `coarse`/`mid`. Rỗng hôm nay không phải thiếu sót: chưa có gì
    để gộp."""
    assignment = plan.assignment

    coarse = (plan.family, assignment.get("density"))
    coarse += tuple(sorted(
        (branch, branch in assignment) for branch in _COARSE_PRESENCE_BRANCHES
    ))

    mid = tuple(
        (branch, assignment[branch]) for branch in _MID_BRANCHES if branch in assignment
    )

    fine = tuple(sorted(assignment.items()))
    fine += tuple(sorted(plan.hard_negative_profile.items()))
    fine += render_extra

    return Fingerprint(coarse=coarse, mid=mid, fine=fine)


__all__ = ["Fingerprint", "fingerprint"]
