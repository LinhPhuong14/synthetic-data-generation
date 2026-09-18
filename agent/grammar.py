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
this shape generalizes before writing thirty of them. The constraints below
encode plausible document conventions, not verified domain expertise; they
are a starting point for the 30-family pass this pilot is meant to unblock,
not a claim that e.g. a 3-signer contract could never lay signatures out
horizontally. Widen or replace them as real generated output disagrees --
the mechanism (branches + constraints + measured narrowing) is what this
pilot is validating, not the specific rules.
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


INVOICE = Grammar(
    family="invoice",
    branches=(
        Branch("header", ("centered", "left_aligned", "two_column", "compact")),
        Branch("customer_info", ("horizontal", "vertical", "boxed", "mixed")),
        Branch("table", ("none", "simple", "grouped", "multi_tier")),
        Branch("signature_count", (1, 2)),
        Branch("signature_layout", ("horizontal", "stacked")),
        Branch("density", ("sparse", "medium", "dense")),
    ),
    constraints=(
        # A grouped or multi-tier table needs the header out of the way --
        # a two-column or compact header leaves more vertical room for the
        # table to breathe before the page runs out.
        Constraint(when=("table", "in", ("grouped", "multi_tier")),
                  then=("header", "in", ("two_column", "compact"))),
        # A sparse invoice (few line items) does not plausibly carry a
        # multi-tier table -- that structure exists to organize MANY rows.
        Constraint(when=("density", "==", "sparse"),
                  then=("table", "in", ("none", "simple"))),
        # A boxed customer block wants width; compact header claims that
        # width for itself, so the two do not pair on one real invoice.
        Constraint(when=("customer_info", "==", "boxed"),
                  then=("header", "!=", "compact")),
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
        Branch("signature_count", (1, 2)),
        Branch("density", ("sparse", "medium")),
    ),
    constraints=(
        # A sparse certificate (name, date, one statement, a seal) has
        # nothing tabular to show -- a table implies enough itemized
        # content that the page stops being sparse.
        Constraint(when=("density", "==", "sparse"),
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
