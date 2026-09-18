"""The CSS sheets, everything above the engine.

No browser and no print engine here, on purpose. The markup, the labelled runs
and the structure tokens are pure functions of a seed, and they are the half a
silent break would ruin: a structure label that has drifted from its page still
looks like a valid label.

What is checked is what the brief in `docs/brief-engine-html.md` asked for and
what the old single-template `a4.py` could not do -- a sheet chosen by the
layout, merged cells that are real `colspan`/`rowspan`, and a table whose rows
all add up to the same width, which is the machine-checkable form of "the two
tables on this page line up".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import sheets  # noqa: E402
from conftest import force_for  # noqa: E402

import rulebase  # noqa: E402
from rulebase.layout import every as every_layout  # noqa: E402

# `every_layout`, not `available_layouts`: a layout switched off with
# `enabled: false` means no RUN draws it, not that nobody checks it any more.

KINDS = re.compile(r'data-kind="([^"]+)"')

SEEDS = (1, 7, 2026)
LAYOUTS = every_layout()

_PAGES: dict[tuple[str, int], tuple] = {}


def page(layout: str, seed: int):
    """`(recipe, receipt, markup)` for one sheet, built once and reused."""
    key = (layout, seed)
    if key not in _PAGES:
        recipe, receipt, _rng = rulebase.make_content(seed=seed, force=force_for(layout))
        _PAGES[key] = (recipe, receipt, sheets.build(recipe, receipt))
    return _PAGES[key]


def test_every_layout_has_a_sheet():
    """A layout with no family is a page drawn as some other document."""
    missing = [layout for layout in LAYOUTS if layout not in sheets.FAMILIES]
    assert not missing, f"no CSS sheet for {missing}"
    extra = [name for name in sheets.FAMILIES if name not in LAYOUTS]
    assert not extra, f"sheets.FAMILIES names layouts that do not exist: {extra}"


def test_the_fillable_tag_matches_the_pages_that_really_have_fields():
    """Attribute 7 asks the rules "can a pen reach anything here", and the
    rules answer with a tag. This is the measurement behind that answer.

    `handwriting.yaml` gives `hand_font` `requires: [fillable]`, and the tag is
    hand-written on 25 layout options in `rules/layout.yaml`. A hand-written
    list of "every X" goes stale the day a sheet changes -- somebody adds a
    signature block and the layout stays un-tagged, so no page of it is ever
    hand-filled and nothing says why. So the list is MEASURED here and compared:
    build each layout's markup and count the runs its family offers a pen.

    The other direction matters as much: a layout tagged `fillable` whose sheet
    stopped printing a signature block would draw ink on nothing, and the page
    would record `hand_font` with an empty `inked` list.
    """
    import handwriting

    tagged = {option.id for option in rulebase.load_rules()["layout"]
              if "fillable" in option.tags}
    measured = set()
    for layout in LAYOUTS:
        kinds = sheets.hand_kinds(layout, handwriting.HAND_KINDS)
        every = kinds == handwriting.ALL_KINDS
        for seed in (3, 17, 91, 205):
            recipe, receipt, _rng = rulebase.make_content(seed=seed, force=force_for(layout))
            markup = sheets.build(recipe, receipt, None)
            if any(every or kind in kinds for kind in KINDS.findall(markup)):
                measured.add(layout)
                break

    assert measured - tagged == set(), (
        f"a pen reaches fields on {sorted(measured - tagged)} and the rules do "
        f"not say so, so no page of them is ever hand-filled")
    assert tagged - measured == set(), (
        f"{sorted(tagged - measured)} are tagged `fillable` and print nothing a "
        f"pen can reach; a page of them would record ink it does not have")


def test_unknown_layout_is_an_error():
    with pytest.raises(KeyError):
        sheets.family_of("no_such_layout")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_builds_and_is_one_document(layout):
    _recipe, _receipt, markup = page(layout, 7)
    assert markup.startswith("<!doctype html>")
    assert markup.count('id="sheet"') == 1
    assert "{FONT_FACES}" in markup, "the font block placeholder must survive"


def test_the_sheet_follows_the_layout():
    """The defect this package exists to fix: one page for every layout.

    `a4.build()` never read `recipe.layout.id`, so a hotel folio forced through
    it came out a VAT invoice -- measured as three different layouts producing
    pages of identical size. Different families must now differ in the markup.
    """
    seen = {}
    for layout in ("invoice_vat_summary", "invoice_hotel_stay", "invoice_brand"):
        _recipe, _receipt, markup = page(layout, 7)
        seen[layout] = markup
    assert len(set(seen.values())) == 3
    # And in the thing a reader would notice first: the paper.
    sizes = {re.search(r"@page\{size:([^;]+);", markup).group(1)
             for markup in seen.values()}
    assert len(sizes) > 1, f"every family printed on the same paper: {sizes}"


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("seed", SEEDS)
def test_rows_all_span_the_same_width(layout, seed):
    """Every row of a table covers the table, counting both kinds of span.

    This is the check that a merged cell is *modelled* rather than drawn. A row
    whose cells leave a gap has a hole; one that runs past the last column has a
    cell hanging off the end. Either way the structure label describes a table
    that is not on the page.

    Occupancy, not a sum of `colspan`. A two-level header's lower band holds
    four cells and covers thirteen columns, because nine cells in the band above
    it reach down with `rowspan="2"` -- adding up one row's colspans and calling
    that its width would report the row that makes the header work as the one
    that breaks it.
    """
    _recipe, _receipt, markup = page(layout, seed)
    cells = sheets.cells_from_markup(markup)
    if not cells:
        return                # a form of fields has no table; see sheets/statement.py
    occupied: dict[int, set[int]] = {}
    for cell in cells:
        for row in range(cell["row"], cell["row"] + cell["rowspan"]):
            occupied.setdefault(row, set()).update(
                range(cell["col"], cell["col"] + cell["colspan"]))
    widths = {row: max(columns) + 1 for row, columns in occupied.items()}
    for row, columns in occupied.items():
        assert columns == set(range(widths[row])), (
            f"{layout} seed {seed}: row {row} covers {sorted(columns)}, "
            f"which is not columns 0..{widths[row] - 1}")
    # Two tables on one sheet are allowed two widths -- the item table and the
    # tax summary have different column counts -- but never a width used by a
    # single row, which is what a hole looks like.
    counts: dict[int, int] = {}
    for width in widths.values():
        counts[width] = counts.get(width, 0) + 1
    odd = [width for width, count in counts.items() if count == 1 and len(counts) > 1]
    assert not odd, f"{layout} seed {seed}: row width(s) {odd} used once, of {counts}"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_columns_never_overlap_within_a_row(layout):
    _recipe, _receipt, markup = page(layout, 7)
    rows: dict[int, list[dict]] = {}
    for cell in sheets.cells_from_markup(markup):
        rows.setdefault(cell["row"], []).append(cell)
    for row, cells in rows.items():
        taken: set[int] = set()
        for cell in sorted(cells, key=lambda c: c["col"]):
            columns = set(range(cell["col"], cell["col"] + cell["colspan"]))
            assert not (columns & taken), (
                f"{layout} row {row}: two cells claim column(s) {columns & taken}")
            taken |= columns


def test_row_numbers_are_page_wide():
    """Two tables on one page must not share row numbers.

    `structure_from_cells` groups by `data-row`; a second table that restarted
    at zero would have its first row welded onto the item table's first row --
    one row of thirteen cells that exists nowhere on the paper.
    """
    _recipe, _receipt, markup = page("invoice_vat_summary", 7)
    cells = sheets.cells_from_markup(markup)
    widths = {cell["row"]: 0 for cell in cells}
    for cell in cells:
        widths[cell["row"]] += cell["colspan"]
    assert {8, 5} <= set(widths.values()), (
        "the item table and the tax summary should have their own widths, "
        f"got {sorted(set(widths.values()))}")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_structure_tokens_match_the_cells(layout):
    """The token stream and the cells describe one table."""
    _recipe, _receipt, markup = page(layout, 7)
    tokens = sheets.structure_from_markup(markup)
    cells = sheets.cells_from_markup(markup)
    assert tokens.count("<tr>") == len({cell["row"] for cell in cells})
    assert tokens.count("</td>") == len(cells)
    merged = sum(1 for cell in cells if cell["colspan"] > 1 or cell["rowspan"] > 1)
    spans = sum(1 for token in tokens if token.startswith((" colspan", " rowspan")))
    assert spans >= merged, "a merged cell lost its span in the token stream"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_labelled_run_is_a_span_with_a_kind(layout):
    """The box contract. `CELL_RECTS_JS` reads these and nothing else."""
    _recipe, _receipt, markup = page(layout, 7)
    runs = sheets.labelled_runs(markup)
    assert runs, f"{layout} labelled nothing"
    for kind, text in runs:
        assert kind, f"a run with no kind: {text!r}"
        assert text.strip(), f"an empty run labelled {kind!r}"
    # Labelled runs are text only: `CELL_RECTS_JS` measures the span's first
    # element child when it has one, so a nested tag would make the quad
    # describe a fragment of the run instead of the run.
    for match in re.finditer(r'<span data-kind="[^"]*"[^>]*>(.*?)</span>', markup, re.S):
        assert "<" not in match.group(1), f"{layout}: a labelled run has a child element"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_what_the_label_says_the_page_prints(layout):
    """Every label value is somewhere in the markup, joined by kind.

    The same rule `pipeline/invariants.py` applies to a rendered page, checked
    here where a failure names the layout rather than an image -- and against
    the same `SUPPRESSED` table, so a sheet is held to exactly the standard the
    character grid is held to. A till roll has no column for a barcode on
    either path; an invoice has room for everything it is given on both.
    """
    from pipeline.invariants import SUPPRESSED, _tight

    allowed = SUPPRESSED.get(layout, frozenset())
    for seed in SEEDS:
        _recipe, receipt, markup = page(layout, seed)
        by_kind: dict[str, list[str]] = {}
        for kind, text in sheets.labelled_runs(markup):
            by_kind.setdefault(kind, []).append(text)
        printed = " ".join(" ".join(sum(by_kind.values(), [])).split())
        joined = {kind: " ".join(" ".join(texts).split())
                  for kind, texts in by_kind.items()}
        for name, value in _leaves(receipt.ground_truth()):
            if not value.strip() or name == "doc_type":
                continue
            field = "total" if name.startswith("total.") else name
            if field in allowed:
                continue
            wanted = " ".join(value.split())
            if wanted in printed or any(wanted in text for text in joined.values()):
                continue
            # `comb_box()` (base.py) prints one character per `data-kind` run
            # rather than one run for the whole value -- see its own
            # docstring on why -- so the space-sensitive check above rejoins
            # it as "T r ầ n" rather than "Trần". The same whitespace-
            # insensitive fallback `pipeline/invariants.py::_printed()`
            # already applies to a wrapped-at-a-hyphen run applies here too.
            tight = _tight(wanted)
            assert any(tight in _tight(text) for text in joined.values()), (
                f"{layout} seed {seed}: {name} {wanted!r} is in the label and on no run")


def _leaves(value, path: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item, path)
    else:
        yield path, str(value)


def test_the_same_seed_gives_the_same_markup():
    for layout in ("invoice_vat_summary", "invoice_hotel_compact", "market_vat"):
        force = force_for(layout)
        recipe, receipt, _rng = rulebase.make_content(seed=11, force=force)
        again, again_receipt, _rng2 = rulebase.make_content(seed=11, force=force)
        assert sheets.build(recipe, receipt) == sheets.build(again, again_receipt)


def test_a_grid_is_not_laid_over_the_contents_first():
    """`make_content` must leave the receipt as it was sampled.

    `build_grid` cuts a value that will not fit its character column and writes
    the cut back, so the label matches the drawn page. A CSS sheet has no
    character columns, and a sheet built after a grid prints "Hàng hoá không
    chịu thuế GTG" on a line with room for the whole label.
    """
    seed = 77
    _recipe, receipt, _rng = rulebase.make_content(seed=seed,
                                                   force={"layout": "invoice_vat_summary"})
    assert receipt.invoice is not None
    labels = [row.get("label", "") for row in receipt.invoice.summary]
    assert any(label.rstrip().endswith(":") for label in labels), labels


# --------------------------------------------------------- nhiều tờ một chứng từ


def test_page_order_absent_means_one_sheet():
    """Every layout that says nothing keeps drawing the single sheet it drew."""
    from sheets import base

    assert base.page_order({}, ["header", "table"]) == []
    assert base.page_order({"page_order": []}, ["header", "table"]) == []
    # One group is one sheet spelled the long way, not an error: a variant that
    # dropped a page should still draw.
    assert base.page_order({"page_order": [["header", "table"]]},
                           ["header", "table"]) == []


def test_page_order_refuses_a_page_nobody_can_print():
    """Three ways to write a layout that prints short, all refused."""
    from sheets import base

    sections = ["header", "table", "totals"]
    with pytest.raises(base.PageOrderError, match="not in sections"):
        base.page_order({"page_order": [["header"], ["signatures"]]}, sections)
    with pytest.raises(base.PageOrderError, match="on no page at all"):
        base.page_order({"page_order": [["header"], ["table"]]}, sections)
    with pytest.raises(base.PageOrderError, match="may run across pages"):
        base.page_order({"page_order": [["header", "totals"], ["table", "totals"]]},
                        sections)
    # The item table is the one name allowed to repeat -- that is what a table
    # running onto a second sheet looks like.
    assert base.page_order(
        {"page_order": [["header", "table"], ["table", "totals"]]}, sections
    ) == [["header", "table"], ["table", "totals"]]


def test_items_are_split_so_the_last_sheet_is_not_a_stub():
    """`rows_first` fills the opening sheet; the rest divide over what follows."""
    from sheets import base

    assert base.split_items(7, 2, first=6) == [(0, 6), (6, 7)]
    assert base.split_items(10, 2) == [(0, 5), (5, 10)]
    # The remainder goes to the EARLIER sheets: a final page carrying one line
    # is the shape that reads as a mistake.
    assert base.split_items(11, 3) == [(0, 4), (4, 8), (8, 11)]
    # Fewer items than the first sheet holds -- every later slice is empty, and
    # `modern.build` reads that as "no second sheet".
    assert base.split_items(3, 2, first=6) == [(0, 3), (3, 3)]
    assert base.split_items(0, 3) == [(0, 0)]


def test_page_names_hang_off_the_first_page_stem():
    from pipeline.record import page_names

    assert page_names("html_007.jpg", 1) == ["html_007.jpg"]
    assert page_names("html_007.jpg", 3) == [
        "html_007.jpg", "html_007_p2.jpg", "html_007_p3.jpg"]


def test_a_multipage_layout_draws_one_sheet_element_per_declared_page():
    """The markup carries as many `.sheet` elements as the content needs.

    `invoice_multipage.yaml` declares two, and whether the second one exists
    depends on how many items were drawn -- which is the point: a four-line
    invoice printing its totals alone on sheet two is not a document anybody
    has been handed. Both outcomes must appear across a handful of seeds, or
    the collapse rule is doing nothing (or everything).
    """
    counts = set()
    for seed in range(12):
        recipe, receipt, _rng = rulebase.make_content(
            seed=seed, force=force_for("invoice_multipage"))
        markup = sheets.build(recipe, receipt)
        counts.add(markup.count('class="sheet"'))
    assert counts <= {1, 2}, counts
    assert counts == {1, 2}, (
        "every seed drew the same number of sheets; the split is not reading "
        "the item count")


def test_only_a_family_that_reads_page_order_may_declare_one():
    """A layout that declares pages a family cannot draw would print ONE sheet.

    Not an error anywhere -- `base.page_order` is read by the family, so a
    family that never calls it simply ignores the key and draws the whole
    document on one sheet, which is the silent short page this repository
    refuses everywhere else. Listed here rather than guessed at: wiring a
    second family is a deliberate act, and adding it to this set is how the
    author says so.
    """
    from rulebase.layout import PAGINATING_FAMILIES

    reads_page_order = set(PAGINATING_FAMILIES)
    offenders = []
    for layout_id in rulebase.available_layouts():
        spec = rulebase.load_layout(layout_id)
        if spec.get("page_order") and spec.get("family") not in reads_page_order:
            offenders.append(f"{layout_id} ({spec.get('family')})")
    assert not offenders, (
        "these layouts declare page_order in a family that does not read it, so "
        "they would silently print one sheet: " + ", ".join(offenders)
        + f" — families that read it: {', '.join(sorted(reads_page_order))}")
