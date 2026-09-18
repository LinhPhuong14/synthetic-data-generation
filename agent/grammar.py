"""Document grammar as a compositional constraint space, not a Cartesian product.

    from agent.grammar import FAMILIES, space_size, valid_options

Phase 3 of `docs/ke-hoach-refactor-engine.md`. Answers the question the
phase header asks before any code gets written: this is not `DOMAINS`
(`agent/compose_page.py` -- twelve static industries the model reads and
then invents everything else inside) and it is not `inspiration()` (three
real archetypes shown so the model reads their SHAPE, never enforced). A
`Grammar` is enforceable structure a sampler (Phase 4) can draw a weighted,
constraint-satisfying instance from -- the archetype/`DOMAINS` level picks
*which* grammar applies; this level says what is INSIDE it.

## Why `Constraint`, not just `Branch`

A family described as independent branches --
`header x customer_info x table x signature`, four branches, four options
each -- is a Cartesian product no matter how many branches you add: 4**4 =
256 "templates in disguise", exactly the trap G1 (top of this plan)
documents from `agent/compose_page.py::schema()`'s own history. A
`Constraint` narrows one branch's valid options based on another branch's
already-chosen value, so the reachable space is smaller than the raw
product and -- more importantly -- SHAPED: choosing `table = multi_tier`
actually changes what `header` may become, the way a real document's
choices are not independent of each other. `space_size()` below proves the
narrowing is real by counting raw vs. constrained size; a family whose
constrained count equals its raw count has decorative constraints, not
real ones, and should not be considered done.

## Scope of this pilot

Three families (`invoice`, `contract`, `certificate`), deliberately not all
twelve `DOMAINS` industries -- the point of a pilot is to find out whether
this shape generalizes before writing thirty of them.

**Cross-checked against `rulebase/layouts/*.yaml`, not left as hand-written
guesses.** A first draft of these three families was written from plausible
reasoning alone; checked against real layout files before scaling up (see
the long comment above the family definitions below), which is exactly how
it caught two real errors -- invoices coded as sometimes having no table
(23/23 real invoice layouts have one) and as always having a signature
(6/23 real layouts have none) -- neither guessable from "plausible
reasoning" alone. `rulebase/layouts/` answers presence/absence of a whole
section reliably (its `sections:` list); it does not describe a discrete
decision tree the way this module does, so the finer options *inside* a
present block (how many `header` variants, what they are named) are still
this module's own vocabulary, not something transcribed from rulebase --
noted at each such branch. Widen or replace any of it as real generated
output disagrees -- the mechanism (branches + constraints + measured
narrowing + cross-checked against a second, independently-built source of
domain knowledge) is what this pilot validates, not that every rule here
is final.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

Condition = tuple[str, str, Any]           # (branch_name, operator, value)

_OPS = {
    "==": lambda value, target: value == target,
    "!=": lambda value, target: value != target,
    "in": lambda value, target: value in target,
    "not in": lambda value, target: value not in target,
}


@dataclass(frozen=True)
class Branch:
    """One axis of a document family. `options` is the FULL set this axis
    can take before any constraint narrows it for a particular instance."""

    name: str
    options: tuple[Any, ...]


@dataclass(frozen=True)
class Constraint:
    """`when` a condition on one branch holds, `then` another branch is
    narrowed to a subset of its own options.

    Both sides name branches that must exist in the same `Grammar`. `then`'s
    value is always interpreted as the ALLOWED set for that branch under
    this constraint -- a single value is short for a one-element set, kept
    for readability (`("layout", "==", "centered_hierarchy")` reads better
    than `("layout", "in", ["centered_hierarchy"])`)."""

    when: Condition
    then: Condition

    def when_holds(self, assignment: dict[str, Any]) -> bool:
        branch, op, target = self.when
        if branch not in assignment:
            return False
        return _OPS[op](assignment[branch], target)

    def then_allows(self, value: Any) -> bool:
        branch, op, target = self.then
        if op == "==":
            return value == target
        if op == "!=":
            return value != target
        if op == "in":
            return value in target
        if op == "not in":
            return value not in target
        raise ValueError(f"unknown operator {op!r}")


@dataclass(frozen=True)
class FieldCompat:
    """Which hard-negative strategies are plausible for one semantic field.

    Phase 6 (`docs/ke-hoach-refactor-engine.md`) implements the mechanism;
    this is the compatibility knowledge it reads, declared here (3.4) so
    the planner (Phase 4) can sample a `hard_negative_profile` that is
    already valid for the fields it picked, instead of sampling a strategy
    and field independently and hoping they make sense together.

    `strategies=()` is a real answer, not a gap: a document title or a
    signer's printed name has no plausible near-duplicate decoy in the same
    document -- forcing one would violate page.md's "hard negatives must
    remain semantically valid" (section 11)."""

    field_kind: str
    strategies: tuple[str, ...]


STRATEGIES = ("lexical", "format", "same_value", "contextual", "positional",
             "table", "visual")


@dataclass(frozen=True)
class Grammar:
    family: str
    branches: tuple[Branch, ...]
    constraints: tuple[Constraint, ...]
    field_compat: tuple[FieldCompat, ...] = ()

    def branch(self, name: str) -> Branch:
        for b in self.branches:
            if b.name == name:
                return b
        raise KeyError(f"{self.family!r} has no branch {name!r}")


def valid_options(grammar: Grammar, branch_name: str,
                  assignment: dict[str, Any]) -> list[Any]:
    """Options for `branch_name` still allowed given branches already fixed
    in `assignment`. Intersects every constraint whose `when` already holds
    -- a branch with no applicable constraint keeps its full option set."""
    options = list(grammar.branch(branch_name).options)
    for constraint in grammar.constraints:
        if constraint.then[0] != branch_name:
            continue
        if not constraint.when_holds(assignment):
            continue
        options = [o for o in options if constraint.then_allows(o)]
    return options


def _consistent(grammar: Grammar, assignment: dict[str, Any]) -> bool:
    for constraint in grammar.constraints:
        if not constraint.when_holds(assignment):
            continue
        target_branch = constraint.then[0]
        if target_branch not in assignment:
            continue
        if not constraint.then_allows(assignment[target_branch]):
            return False
    return True


def space_size(grammar: Grammar) -> dict[str, int]:
    """`{raw, constrained, cut}` -- the number the whole point of 3.2 is to
    report. `raw` is the Cartesian product of every branch's full option
    set (the "N hidden templates" size if constraints did nothing);
    `constrained` is how many FULL assignments satisfy every constraint
    simultaneously; `cut` is how many raw combinations that removes.

    `cut == 0` means the constraints in this grammar are decorative --
    review before trusting the family as "done" per Phase 3's DoD."""
    names = [b.name for b in grammar.branches]
    option_lists = [b.options for b in grammar.branches]
    raw = 1
    for options in option_lists:
        raw *= len(options)
    constrained = 0
    for combo in itertools.product(*option_lists):
        assignment = dict(zip(names, combo))
        if _consistent(grammar, assignment):
            constrained += 1
    return {"raw": raw, "constrained": constrained, "cut": raw - constrained}


# ------------------------------------------------------------- pilot families

# ĐỐI CHIẾU VỚI `rulebase/layouts/*.yaml`, không suy luận tay.
#
# Bản đầu của ba family này (trước khi đối chiếu) viết ra từ suy luận hợp
# lý, và người dùng đúng khi không tin điều đó ở quy mô 30 family -- so với
# `rulebase/layouts/invoice_*.yaml` (23 layout gốc, không tính biến thể
# `_part`/`_note`/`_titl`/`_word` chỉ đè một phần) lộ ra hai chỗ sai thật:
#
# 1. Bản đầu cho `table` của invoice có lựa chọn `"none"` -- SAI. **23/23**
#    layout hoá đơn thật đều có `table` trong `sections:`. Không có invoice
#    layout nào bỏ bảng. Xoá `"none"` khỏi nhánh này.
# 2. Bản đầu coi chữ ký là bắt buộc (`signature_count: (1, 2)`, không có 0).
#    Thật ra **6/23 (26%)** layout (`invoice_dense_table`, `invoice_
#    multipage`, `invoice_brand`, `invoice_logo_center`, `invoice_
#    minimalist`, `invoice_tax_en`) KHÔNG có `signatures` trong
#    `sections:`. Thêm `0` vào `signature_count`.
#
# Certificate: đối chiếu `rulebase/layouts/insurance_*_certificate.yaml` (5
# layout gốc) lộ ra ràng buộc "sparse -> không bảng" bản đầu PHÓNG ĐẠI mức
# hiếm của bảng -- **3/5** (`fire`, `health`, `travel`) CÓ `table`, chỉ
# `auto`/`moto` không có. Bảng ở certificate không hiếm, nó gắn với việc
# certificate có xác nhận NHIỀU khoản mục (quyền lợi, hạng mục bảo hiểm) hay
# chỉ MỘT sự việc đơn (xác nhận một xe, một người) -- đổi tên trục cho đúng
# nghĩa thay vì mượn "density".
#
# Contract: đối chiếu `rulebase/layouts/insurance_property_contract.yaml`
# (đại diện gần nhất trong rulebase cho "hợp đồng có phụ lục bảng") lộ ra
# bản đầu THIẾU HẲN nhánh `table` -- layout thật có `table` + `totals`
# (bảng hạng mục/mức trách nhiệm). Thêm nhánh này.
#
# Vẫn còn giới hạn thật: `rulebase/layouts/` mô tả layout do ENGINE vẽ
# (track 1, tham số liên tục -- `width: [88, 100]`, `name_scale: [1.25,
# 1.45]`), không phải mô tả cây quyết định rời rạc kiểu grammar này. Việc
# đối chiếu ở đây dùng được cho CÓ/KHÔNG một block (`sections:` liệt kê gì)
# -- đáng tin. Dùng để suy ra CÁCH bố cục bên trong một block (`header` nên
# chia mấy kiểu) thì rulebase không có câu trả lời trực tiếp, nên các
# option chi tiết bên trong (`centered`/`left_aligned`/...) vẫn là suy luận
# có chủ đích, chưa tra được từ đâu xa hơn -- nói rõ để không tưởng đã đối
# chiếu hết.


INVOICE = Grammar(
    family="invoice",
    branches=(
        Branch("header", ("centered", "left_aligned", "two_column", "compact")),
        Branch("customer_info", ("horizontal", "vertical", "boxed", "mixed")),
        # KHÔNG có "none" -- 23/23 layout hoá đơn thật trong rulebase có bảng.
        Branch("table", ("simple", "grouped", "multi_tier")),
        # 0 THÊM VÀO sau đối chiếu: 6/23 layout thật không có `signatures`.
        Branch("signature_count", (0, 1, 2)),
        Branch("signature_layout", ("none", "horizontal", "stacked")),
        Branch("density", ("sparse", "medium", "dense")),
    ),
    constraints=(
        # A grouped or multi-tier table needs the header out of the way --
        # a two-column or compact header leaves more vertical room for the
        # table to breathe before the page runs out.
        Constraint(when=("table", "in", ("grouped", "multi_tier")),
                  then=("header", "in", ("two_column", "compact"))),
        # A boxed customer block wants width; compact header claims that
        # width for itself, so the two do not pair on one real invoice.
        Constraint(when=("customer_info", "==", "boxed"),
                  then=("header", "!=", "compact")),
        # `signature_layout` only means something once there is at least
        # one signature to lay out.
        Constraint(when=("signature_count", "==", 0),
                  then=("signature_layout", "==", "none")),
        Constraint(when=("signature_count", "in", (1, 2)),
                  then=("signature_layout", "!=", "none")),
    ),
    field_compat=(
        FieldCompat("store.tax_code", ("lexical", "format", "same_value")),
        FieldCompat("invoice.total", ("format", "table")),
        FieldCompat("invoice.number", ("lexical", "format", "positional")),
        FieldCompat("doc_title", ()),
        FieldCompat("sign.name", ()),
    ),
)

CONTRACT = Grammar(
    family="contract",
    branches=(
        Branch("header", ("national_heading", "corporate_masthead", "compact_corner")),
        Branch("party_block", ("side_by_side", "stacked", "single_block")),
        Branch("clause_section", ("fixed", "repeatable")),
        # THÊM sau đối chiếu với `insurance_property_contract.yaml`, layout
        # thật gần nhất trong rulebase cho "hợp đồng có phụ lục bảng":
        # `sections:` của nó có cả `table` VÀ `totals` (bảng hạng mục/mức
        # trách nhiệm) -- bản đầu của grammar này không có nhánh `table` ở
        # tất cả, một thiếu sót thật, không phải một biến thể hiếm.
        Branch("table", ("none", "simple", "schedule")),
        Branch("signature_count", (2, 3)),
        Branch("signature_layout", ("horizontal", "stacked", "approval_chain")),
        Branch("density", ("medium", "dense", "very_dense")),
    ),
    constraints=(
        # Three signers rarely lay out in one horizontal row on A4 width --
        # stacked or an approval chain are the layouts that actually fit.
        Constraint(when=("signature_count", "==", 3),
                  then=("signature_layout", "in", ("approval_chain", "stacked"))),
        # Repeatable clauses (a contract that enumerates many numbered
        # terms) is the thing that makes a contract run dense to begin
        # with -- a fixed, short clause list does not produce a dense page.
        Constraint(when=("clause_section", "==", "repeatable"),
                  then=("density", "in", ("dense", "very_dense"))),
        # A compact corner header leaves no width for two parties printed
        # side by side -- that layout wants the header out of the way
        # (national heading, full-width masthead).
        Constraint(when=("header", "==", "compact_corner"),
                  then=("party_block", "!=", "side_by_side")),
        # A `schedule` table (itemized coverage/liability amounts, per
        # insurance_property_contract.yaml) is itself the thing that makes
        # a contract dense -- it does not coexist with a short, fixed
        # clause list on a sparse-reading page.
        Constraint(when=("table", "==", "schedule"),
                  then=("density", "in", ("dense", "very_dense"))),
    ),
    field_compat=(
        FieldCompat("legal.basis", ("contextual",)),
        FieldCompat("clause.body", ()),
        FieldCompat("sign.title", ("lexical", "positional")),
        FieldCompat("sign.name", ()),
        FieldCompat("doc_title", ()),
    ),
)

CERTIFICATE = Grammar(
    family="certificate",
    branches=(
        Branch("header", ("centered", "national_heading", "seal_top")),
        Branch("layout", ("single_column", "centered_hierarchy")),
        Branch("table", ("none", "simple")),
        # THAY "density" bằng trục đúng nghĩa hơn sau đối chiếu:
        # `insurance_fire/health/travel_certificate.yaml` (3/5 layout thật)
        # CÓ bảng -- bảng gắn với "xác nhận nhiều khoản mục" (quyền lợi,
        # hạng mục), không gắn với sparse/dense. `insurance_auto/moto_
        # certificate.yaml` (2/5, không bảng) xác nhận một sự việc đơn.
        Branch("confirms", ("single_fact", "itemized_list")),
        Branch("signature_count", (1, 2)),
    ),
    constraints=(
        # Xác nhận một sự việc đơn (một xe, một người) không có gì để liệt
        # kê thành bảng -- bảng tồn tại để xếp NHIỀU khoản mục.
        Constraint(when=("confirms", "==", "single_fact"),
                  then=("table", "==", "none")),
        # Two signers (issuer + witness, or two co-signing officials) is
        # the case a centered hierarchy exists to arrange; a plain single
        # column reads as one voice, which fits one signer better.
        Constraint(when=("signature_count", "==", 2),
                  then=("layout", "==", "centered_hierarchy")),
    ),
    field_compat=(
        FieldCompat("doc_title", ()),
        FieldCompat("meta.value", ("lexical", "format")),
        FieldCompat("sign.name", ()),
    ),
)

FAMILIES: dict[str, Grammar] = {g.family: g for g in (INVOICE, CONTRACT, CERTIFICATE)}


__all__ = ["CERTIFICATE", "CONTRACT", "FAMILIES", "INVOICE", "STRATEGIES",
          "Branch", "Condition", "Constraint", "FieldCompat", "Grammar",
          "space_size", "valid_options"]
