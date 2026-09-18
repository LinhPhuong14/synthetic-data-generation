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

## Scope

Started as three families (a generic "invoice"/"contract"/"certificate"),
deliberately not all twelve `DOMAINS` industries -- the point of a pilot
was to find out whether this shape generalizes before writing thirty of
them. It did, so there are thirty now: two hand-reasoned families kept from
the pilot (`invoice_detailed`, `insurance_property_contract` -- renamed
from the generic pilot labels once cross-checking showed no
`rulebase/documents/invoice.yaml` or `contract.yaml` exists, only specific
document names) plus twenty-eight more built by `_family()` from real
signature counts and section presence read out of `rulebase/`. Five of the
thirty are the specific certificate types that used to be one generic
"certificate" pilot family -- see `_SOURCE` and the long comment above the
family definitions for exactly what was read from where.

**Cross-checked against `rulebase/layouts/*.yaml` and
`rulebase/documents/*.yaml`, not left as hand-written guesses.** The first
draft of the three pilot families was written from plausible reasoning
alone; checked against real layout files before scaling up, which is
exactly how it caught two real errors -- invoices coded as sometimes having
no table (23/23 real invoice layouts have one) and as always having a
signature (6/23 real layouts have none) -- neither guessable from
"plausible reasoning" alone. The same two numbers (`sections:` presence,
`len(signature_labels)`) drove all twenty-eight `_family()` grammars too.
`rulebase/` answers presence/absence of a whole section reliably; it does
not describe a discrete decision tree the way this module does, so the
finer options *inside* a present block (how many `header` variants, what
they are named) are still this module's own vocabulary, not something
transcribed from rulebase -- noted at each such branch. Widen or replace
any of it as real generated output disagrees -- the mechanism (branches +
constraints + measured narrowing + cross-checked against a second,
independently-built source of domain knowledge) is what this pilot
validated, not that every rule here is final.
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


# ------------------------------------------- two hand-reasoned pilot families

# ĐỐI CHIẾU VỚI `rulebase/layouts/*.yaml` VÀ `rulebase/documents/*.yaml`,
# không suy luận tay -- áp dụng cho cả hai family thí điểm dưới đây
# (`invoice_detailed`, `insurance_property_contract`) và cho cả 30 family
# ở phần dưới file này.
#
# Bản đầu của hai family này (trước khi đối chiếu, khi còn tên chung
# "invoice"/"contract") viết ra từ suy luận hợp lý, và người dùng đúng khi
# không tin điều đó ở quy mô 30 family -- so với `rulebase/layouts/
# invoice_*.yaml` (23 layout gốc, không tính biến thể `_part`/`_note`/
# `_titl`/`_word` chỉ đè một phần) lộ ra hai chỗ sai thật:
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
# Contract: đối chiếu `rulebase/layouts/insurance_property_contract.yaml`
# (đại diện gần nhất trong rulebase cho "hợp đồng có phụ lục bảng") lộ ra
# bản đầu THIẾU HẲN nhánh `table` -- layout thật có `table` + `totals`
# (bảng hạng mục/mức trách nhiệm). Thêm nhánh này.
#
# Sau đối chiếu, đổi TÊN family từ nhãn chung ("invoice", "contract") sang
# đúng tên tài liệu thật trong `rulebase/documents/` -- không có
# `rulebase/documents/invoice.yaml` hay `contract.yaml` chung chung nào cả,
# chỉ có `invoice_detailed.yaml`/`invoice_plain.yaml` (đại diện bởi
# `invoice_detailed` dưới đây) và `insurance_property_contract.yaml`. Tám
# loại certificate cụ thể (`insurance_auto_certificate`,
# `insurance_fire_certificate`, ...) đã tách riêng trong phần 30 family bên
# dưới, nên "certificate" chung chung của bản thí điểm không còn cần nữa --
# gộp về đúng tên thật, không giữ một nhãn hư cấu song song với tên thật.
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


INVOICE_DETAILED = Grammar(
    family="invoice_detailed",
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

INSURANCE_PROPERTY_CONTRACT = Grammar(
    family="insurance_property_contract",
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

# ------------------------------------------- remaining 28, built from data

# CÙNG CÁCH ĐỐI CHIẾU với hai family thí điểm ở trên, mở rộng ra 30 tên
# thật lấy từ `rulebase/documents/*.yaml` (bộ tham số nội dung track 1 --
# 44 file, chọn 30 loại khác biệt nhất về cấu trúc, bỏ các biến thể gần
# trùng: `resort_stay`≈`hotel_stay`, `convenience_store`≈`retail_vat_
# invoice`, `form_checklist_table`≈`form_checklist`, `bakery_order` không
# có layout khớp để đối chiếu `sections:`).
#
# Với mỗi family, hai con số đọc trực tiếp từ dữ liệu thật, không suy luận:
#
# - `sig`: `len(signature_labels)` trong chính `rulebase/documents/<tên>.yaml`.
# - `table`/`parties`: đọc `sections:` của layout khớp nhất trong
#   `rulebase/layouts/` (ánh xạ tên ghi trong `_SOURCE` dưới, vì tên file
#   layout không phải lúc nào cũng trùng tên file document -- ví dụ
#   `utility_power` (document) dựng bằng `invoice_power.yaml` (layout)).
#
# `_family()` dựng Grammar từ hai con số ấy cộng branch chung (`header`,
# `density`) -- KHÔNG viết 30 câu chuyện khác nhau cho từng family (30 lần
# suy luận tay còn tệ hơn 1 lần, đúng bài học vừa học được với 3 family
# đầu). Ràng buộc sinh ra generic nhưng đúng cùng logic đã dùng ở hai family
# thí điểm (bảng phức tạp cần header nhường chỗ; nhiều chữ ký cần layout
# xếp chồng) -- áp lại có chủ đích, không phải áp bừa.
#
# `sig_center` cho khoảng `signature_count` bằng `{center-1, center, center+1}`
# (sàn ở 0) -- biến thiên thật quanh con số đã đo, không bịa một khoảng
# rộng hơn dữ liệu cho phép.

_SOURCE: dict[str, dict[str, object]] = {
    "authorisation_letter": {"sig": 4, "table": False, "parties": True,
                             "doc": "authorisation_letter.yaml",
                             "layout": "authorisation_letter.yaml"},
    "cash_receipt_voucher": {"sig": 5, "table": False, "parties": True,
                             "doc": "cash_receipt_voucher.yaml",
                             "layout": "form_cash_voucher.yaml"},
    "dispatch_letter": {"sig": 1, "table": False, "parties": True,
                        "doc": "dispatch_letter.yaml",
                        "layout": "form_dispatch_letter.yaml"},
    "export_invoice": {"sig": 1, "table": True, "parties": True,
                       "doc": "export_invoice.yaml", "layout": "invoice_export.yaml"},
    "form_activity": {"sig": 2, "table": True, "parties": False,
                      "doc": "form_activity.yaml",
                      "layout": "form_activity_signature.yaml"},
    "form_checklist": {"sig": 1, "table": False, "parties": True,
                       "doc": "form_checklist.yaml",
                       "layout": "form_checkbox_heavy.yaml"},
    "form_dense": {"sig": 1, "table": False, "parties": True,
                  "doc": "form_dense.yaml", "layout": "form_dense_registration.yaml"},
    "form_roster": {"sig": 3, "table": True, "parties": False,
                    "doc": "form_roster.yaml", "layout": "form_timesheet_grid.yaml"},
    "form_sectioned": {"sig": 1, "table": True, "parties": True,
                       "doc": "form_sectioned.yaml", "layout": "form_multi_section.yaml"},
    "form_symmetric": {"sig": 2, "table": False, "parties": True,
                       "doc": "form_symmetric.yaml", "layout": "form_two_column.yaml"},
    "handover_record": {"sig": 3, "table": True, "parties": True,
                        "doc": "handover_record.yaml",
                        "layout": "form_handover_record.yaml"},
    "hospital_bill": {"sig": 4, "table": True, "parties": True,
                      "doc": "hospital_bill.yaml", "layout": "medical_statement.yaml"},
    "hotel_stay": {"sig": 2, "table": True, "parties": True,
                  "doc": "hotel_stay.yaml", "layout": "invoice_hotel_stay.yaml"},
    "insurance_application_form": {"sig": 2, "table": True, "parties": True,
                                   "doc": "insurance_application_form.yaml",
                                   "layout": "insurance_application_form.yaml"},
    "insurance_auto_certificate": {"sig": 1, "table": False, "parties": True,
                                   "doc": "insurance_auto_certificate.yaml",
                                   "layout": "insurance_auto_certificate.yaml"},
    "insurance_cargo_policy": {"sig": 1, "table": False, "parties": True,
                               "doc": "insurance_cargo_policy.yaml",
                               "layout": "insurance_cargo_policy.yaml"},
    "insurance_fire_certificate": {"sig": 2, "table": True, "parties": True,
                                   "doc": "insurance_fire_certificate.yaml",
                                   "layout": "insurance_fire_certificate.yaml"},
    "insurance_health_certificate": {"sig": 1, "table": True, "parties": True,
                                     "doc": "insurance_health_certificate.yaml",
                                     "layout": "insurance_health_certificate.yaml"},
    "insurance_health_id_card": {"sig": 0, "table": False, "parties": True,
                                 "doc": "insurance_health_id_card.yaml",
                                 "layout": "insurance_health_id_card.yaml"},
    "insurance_life_schedule": {"sig": 2, "table": True, "parties": True,
                                "doc": "insurance_life_schedule.yaml",
                                "layout": "insurance_life_schedule.yaml"},
    "insurance_moto_certificate": {"sig": 1, "table": False, "parties": True,
                                   "doc": "insurance_moto_certificate.yaml",
                                   "layout": "insurance_moto_certificate.yaml"},
    "insurance_travel_certificate": {"sig": 1, "table": True, "parties": True,
                                     "doc": "insurance_travel_certificate.yaml",
                                     "layout": "insurance_travel_certificate.yaml"},
    "leave_application": {"sig": 3, "table": False, "parties": True,
                          "doc": "leave_application.yaml",
                          "layout": "form_leave_application.yaml"},
    "meeting_minutes": {"sig": 2, "table": False, "parties": True,
                        "doc": "meeting_minutes.yaml",
                        "layout": "form_meeting_minutes.yaml"},
    # market_vat.yaml has no `sections:` list (till-receipt family uses a
    # different, row-oriented layout schema) -- table=True is read from its
    # own docstring instead ("dòng đầu... tên; dòng thứ hai... số lượng,
    # đơn giá, thành tiền" is an item table by definition), not from
    # `sections:`. `parties=False`: a retail till slip has no buyer/seller
    # block, just a header and an item list.
    "retail_vat_invoice": {"sig": 2, "table": True, "parties": False,
                           "doc": "retail_vat_invoice.yaml", "layout": "market_vat.yaml"},
    "tax_invoice_en": {"sig": 0, "table": True, "parties": True,
                       "doc": "tax_invoice_en.yaml", "layout": "invoice_tax_en.yaml"},
    "utility_power": {"sig": 2, "table": True, "parties": True,
                      "doc": "utility_power.yaml", "layout": "invoice_power.yaml"},
    "utility_water": {"sig": 2, "table": True, "parties": True,
                      "doc": "utility_water.yaml", "layout": "invoice_water.yaml"},
}


def _sig_options(center: int) -> tuple[int, ...]:
    return tuple(sorted({max(0, center - 1), center, center + 1}))


def _family(name: str) -> Grammar:
    info = _SOURCE[name]
    branches = [
        Branch("header", ("centered", "left_aligned", "two_column", "compact")),
        Branch("density", ("sparse", "medium", "dense")),
    ]
    constraints = []
    if info["parties"]:
        branches.append(Branch("party_block", ("side_by_side", "stacked", "single_block")))
        # Same reasoning as `insurance_property_contract`/`invoice_detailed`
        # above: a compact header claims the width a side-by-side party
        # block needs.
        constraints.append(Constraint(when=("header", "==", "compact"),
                                     then=("party_block", "!=", "side_by_side")))
    if info["table"]:
        branches.append(Branch("table", ("simple", "grouped")))
        constraints.append(Constraint(when=("table", "==", "grouped"),
                                     then=("header", "in", ("two_column", "compact"))))
    sig_center = int(info["sig"])
    sig_options = _sig_options(sig_center)
    branches.append(Branch("signature_count", sig_options))
    if max(sig_options) >= 3:
        branches.append(Branch("signature_layout", ("stacked", "approval_chain")))
        many = tuple(n for n in sig_options if n >= 3)
        constraints.append(Constraint(when=("signature_count", "in", many),
                                     then=("signature_layout", "in",
                                           ("stacked", "approval_chain"))))
    return Grammar(family=name, branches=tuple(branches), constraints=tuple(constraints))


_THIRTY = tuple(_family(name) for name in _SOURCE)


FAMILIES: dict[str, Grammar] = {
    g.family: g for g in (INVOICE_DETAILED, INSURANCE_PROPERTY_CONTRACT) + _THIRTY
}


__all__ = ["FAMILIES", "INSURANCE_PROPERTY_CONTRACT", "INVOICE_DETAILED",
          "STRATEGIES", "Branch", "Condition", "Constraint", "FieldCompat",
          "Grammar", "space_size", "valid_options"]
