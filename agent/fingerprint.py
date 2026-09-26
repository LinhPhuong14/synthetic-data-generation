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
- **fine** -- `family` plus the complete `assignment` (every branch, sorted)
  plus the `hard_negative_profile`. The full picture; two documents are
  fine-identical only if `sample()` drew the literal same plan.

`coarse` and `fine` each IDENTIFY a plan, so same-fine implies same-coarse.
`mid` deliberately does NOT carry the family and is therefore comparable
ACROSS families -- it answers "how many documents anywhere in this corpus
came out in this structural shape", which is the question a coverage
tie-break wants. That asymmetry is on purpose; the sentence that used to
stand here ("each tier is a strict refinement of the one before it") was
true of coarse->fine and false of mid, and calling all three a chain hid it.

`family` was ADDED to `fine` on 24-09 because it was missing and the
docstring's own claim above was false without it. Measured before the fix:
over 200 simulated 40-page round-robin batches (8 000 plans), 138 pages
(1,73%) had a `fine` tuple matching a DIFFERENT family inside a 24-page
window, and 0 (0,00%) matched the same family. The whole 28-family block
built by `agent/grammar.py::_family` draws from the same branch names and
the same option lists, so identical assignments across families are common,
not exotic. Any caller treating same-fine as same-plan -- `agent/
diversity.py` does, to veto a repeated configuration -- was therefore acting
on false positives 100% of the time. `fingerprint()` takes only a `DocumentPlan` today
-- the DoD mentions deriving one from "a DocumentPlan + render result" too,
but no render-derived signal (geometry, actual box count) exists yet in
this pipeline for grammar-sampled documents (Phase 5 is what would produce
one) -- `render_extra` is accepted and folded into `fine` when a caller has
it, so this does not need to change shape once that exists.

## The geometry layer, and why it is a SECOND fingerprint, not `render_extra`

`geometry_fingerprint()` below reads the drawn page -- `layout_annotations`
straight out of `pipeline/record.py`, per-mille boxes measured by Chromium --
and answers the question the plan tiers above structurally cannot:

    "did this page LAND in the same place as one we already made?"

Measured on the 94 LLM-written documents in `data/pilot16` + `data/pilot17`,
the three closest pairs of pages in the whole corpus are:

    J=0.895  handover_record_0010   vs  invoice_detailed_0023
    J=0.891  form_roster_0007       vs  invoice_detailed_0023
    J=0.858  form_roster_0007       vs  handover_record_0010

All three are 3-sheet pages carrying `Page-Header + Title/Section-Header +
Table x3 + Text`, in the same grid cells. They are near-identical paper --
and `agent/document_distance.py::distance` scores every one of those pairs
**1.0, maximally different**, because the tiers above start at `family` and
those are three different families. A plan fingerprint cannot see this by
construction: dressing and realization live entirely outside `DocumentPlan`.

So geometry is kept as its OWN fingerprint with its OWN memory, and is
deliberately NOT folded into `fine` via `render_extra`: `agent/coverage.py::
CoverageMemory` ranks CANDIDATE plans (drawn before any render, so their
`render_extra` is empty) against OBSERVED ones. Mixing a render signal into
`fine` means an observed fingerprint can never again match a candidate's
`fine` tuple, every fine count reads 0, and the coarse/mid/fine tie-break
that `coverage.py`'s docstring is entirely about quietly stops working. The
hook stays for a caller that wants it; the collision path does not use it.
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

    # `plan.family` PHẢI có ở đây. Thiếu nó thì `hospital_bill` và
    # `handover_record` rút cùng một assignment cho ra cùng một `fine`, và
    # mọi caller đọc `fine` như "đúng plan này" đang đọc sai -- xem số đo
    # trong docstring module.
    fine = (plan.family,) + tuple(sorted(assignment.items()))
    fine += tuple(sorted(plan.hard_negative_profile.items()))
    fine += render_extra

    return Fingerprint(coarse=coarse, mid=mid, fine=fine)


# --------------------------------------------------------------------- hình học

# Lưới thô phủ tờ giấy. 8x12 = 96 ô trên khổ A4, tức mỗi ô chừng 26x25 mm --
# đủ mịn để một khối dời chỗ nửa trang thì đổi ô, đủ thô để một dòng chữ dài
# thêm vài milimet thì không.
#
# Ba độ phân giải đã đo trên 94 tài liệu `data/pilot16` + `data/pilot17`
# (4 371 cặp), đếm số cặp có Jaccard >= 0,60:
#
#     6x8  ..... 45 cặp (1,03%)   -- quá thô, một tờ dày lấp gần hết lưới
#     8x12 ..... 38 cặp (0,87%)
#     10x14 .... 31 cặp (0,71%)   -- quá mịn, hai tờ giống nhau vẫn lệch ô
#
# Ba thứ tự xếp hạng cặp gần nhau nhất GIỐNG NHAU ở cả ba lưới (cùng ba cặp
# đứng đầu), nên con số 8x12 không phải chỗ duy nhất luật này chạy được --
# nó là chỗ giữa.
GRID_COLS = 8
GRID_ROWS = 12


@dataclass(frozen=True)
class GeometryFingerprint:
    """Chỗ mực THẬT rơi xuống, đọc từ `layout_annotations` sau khi vẽ.

    - `cells` -- tập `(số tờ, nhãn lớp bố cục, cột, hàng)`. Đây là tầng
      QUYẾT ĐỊNH: nó biết một `Table` ngồi ở nửa dưới tờ hai khác một
      `Table` ngồi ở nửa trên tờ một, thứ mà một bitmap mực không biết.
      Số tờ nằm TRONG khoá, nên một tài liệu ba tờ không bao giờ trùng khít
      một tài liệu một tờ dù trang đầu giống hệt.
    - `grid` -- bitmask `GRID_COLS * GRID_ROWS` bit của TỜ ĐẦU: ô nào có
      mực, bất kể mực loại gì. Rẻ, so bằng XOR, và là tín hiệu ĐỘC LẬP với
      `cells` (không đọc nhãn) nên nó nói được khi hai phép đo bất đồng.
    - `pages`, `regions` -- hai con số thô để đọc báo cáo, không vào phép đo
      khoảng cách.
    """

    cells: frozenset
    grid: int
    pages: int
    regions: int


def geometry_fingerprint(layout_annotations: Any,
                        cols: int = GRID_COLS,
                        rows: int = GRID_ROWS) -> GeometryFingerprint:
    """`layout_annotations` (per-mille, `pipeline/record.py`) -> dấu vân hình học.

    Đọc `bbox` chứ không `bbox_px`: `bbox` là PHẦN NGHÌN của cạnh tờ giấy
    (`bbox_mode: "xyxy_per_mille"`, xem AGENTS.md mục 4), nên hai tờ vẽ ở hai
    độ phân giải khác nhau vẫn rơi vào cùng một ô lưới. Dùng `bbox_px` ở đây
    là buộc dấu vân vào `device_scale_factor` của lần vẽ.

    Bản ghi thiếu `bbox` hoặc thiếu `layout_class` KHÔNG ném: một vùng không
    đo được là một vùng không vào dấu vân, và tờ giấy vẫn còn những vùng
    khác. Danh sách rỗng trả về một dấu vân rỗng -- `geometry_distance` đọc
    được nó, và caller quyết định có tin hay không qua `regions == 0`."""
    cells: set = set()
    grid = 0
    pages = 0
    counted = 0
    for annotation in (layout_annotations or ()):
        if not isinstance(annotation, dict):
            continue
        box = annotation.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in box[:4])
        except (TypeError, ValueError):
            continue
        page = int(annotation.get("page_number", 1) or 1)
        pages = max(pages, page)
        counted += 1
        label = str(annotation.get("layout_class") or "?")
        # `min(cols - 1, ...)`: một hộp chạm đúng mép phải (x = 1000) rơi vào
        # ô thứ `cols`, thứ không tồn tại. Kẹp, không bỏ -- mép phải là chỗ
        # số trang và dấu giáp lai hay ngồi.
        c0 = min(cols - 1, max(0, int(x0 * cols // 1000)))
        c1 = min(cols - 1, max(0, int(x1 * cols // 1000)))
        r0 = min(rows - 1, max(0, int(y0 * rows // 1000)))
        r1 = min(rows - 1, max(0, int(y1 * rows // 1000)))
        if c1 < c0:
            c0, c1 = c1, c0
        if r1 < r0:
            r0, r1 = r1, r0
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                cells.add((page, label, col, row))
                if page == 1:
                    grid |= 1 << (row * cols + col)
    return GeometryFingerprint(cells=frozenset(cells), grid=grid,
                              pages=pages, regions=counted)


__all__ = ["GRID_COLS", "GRID_ROWS", "Fingerprint", "GeometryFingerprint",
          "fingerprint", "geometry_fingerprint"]
