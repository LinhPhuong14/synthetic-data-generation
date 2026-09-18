"""Axis 3 — how the mark got onto the paper.

`agent/prompts/regions.md` defines three axes for every run on a page: it IS a
region (axis 1), it DOES a role (axis 2), and it was PUT THERE somehow (axis
3). The record carried the first two -- `layout_class` and `field_role` -- and
not the third, so a reader could tell a heading from a table cell and a key
from a value, and could not tell printed text from a stamp impression or from
something a person wrote by hand.

That distinction is the entire reason `generators/html/handwriting.py` and
`generators/html/signature.py` exist, and it was reaching the dataset only as
pixels.

Six values, and they are known in three different places, which is why the
answer is assembled rather than looked up:

* **the renderer** knows `hand`, `stamp` and `reversed` -- all three are
  decided while drawing and leave no trace in `kind`. It says so with
  `data-ink` on the span;
* **the kind** knows `stamp` on its own (`seal.` is always an impression),
  which is the belt to that braces;
* **the recipe** knows `thermal` and `dotmatrix`, because those are properties
  of the whole sheet rather than of one run -- a thermal roll prints every run
  thermally.

`print` is what is left, and it is most of every page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline import record  # noqa: E402


def _box(kind: str, ink: str = "", text: str = "x"):
    return {"kind": kind, "ink": ink, "text": text,
            "quad": [[0, 0], [10, 0], [10, 10], [0, 10]]}


# --------------------------------------------------------------- the vocabulary


def test_the_six_values_are_the_ones_the_axis_document_defines():
    """Fixed by what reads these records, the same way `DOCSYNTH_LABELS` is."""
    assert record.INK_VALUES == {"print", "hand", "stamp", "dotmatrix",
                                 "thermal", "reversed"}


def test_the_axis_document_and_the_code_name_the_same_six():
    """`agent/prompts/regions.md` is what a labelling model is handed. Two
    lists of six that drift apart is a model told one vocabulary and judged
    against another."""
    text = (REPO_ROOT / "agent" / "prompts" / "regions.md").read_text(encoding="utf-8")
    section = text.split("## Ink")[1].split("##")[0]
    for value in record.INK_VALUES:
        assert f"`{value}`" in section, value


# ------------------------------------------------------------- what decides it


def test_the_renderer_wins_because_it_is_the_only_one_that_can_know():
    """`hand` and `reversed` are invisible to `kind` and to the recipe: a
    hand-filled `store.name` and a printed one are the same field."""
    assert record.ink_for("store.name", "hand", "thermal") == "hand"
    assert record.ink_for("colhdr", "reversed", "print") == "reversed"


def test_a_seal_is_a_stamp_even_on_a_page_that_says_nothing():
    """The belt to the renderer's braces: a set drawn before `data-ink`
    existed still classifies its seals correctly."""
    assert record.ink_for("seal.round_company", "", "print") == "stamp"
    assert record.ink_for("seal.round_company", "", "thermal") == "stamp"


def test_the_page_default_covers_everything_else():
    assert record.ink_for("store.name", "", "thermal") == "thermal"
    assert record.ink_for("total.grand", "", "dotmatrix") == "dotmatrix"
    assert record.ink_for("store.name", "", "print") == "print"


def test_a_value_outside_the_vocabulary_is_dropped_not_trusted():
    """The set is closed. A typo in a family module must not put a seventh ink
    in a dataset a consumer has six classes for."""
    assert record.ink_for("store.name", "crayon", "print") == "print"
    assert record.ink_for("store.name", "", "crayon") == "print"


# ------------------------------------------------------------- the page default


def test_the_page_ink_is_read_off_tags_the_recipe_already_carries():
    """Not a new attribute: `thermal` and `impact` are decided by
    `document`/`visual`, and both already tag themselves. Measured over 300
    draws: `thermal` on 54, `impact` on 97 -- so neither branch is dead."""
    # `render` pulls in cv2 and playwright, which only the renderer's own venv
    # has. The rest of this file is pure `pipeline/record.py` and runs on the
    # bare interpreter CI uses; these two ask the render path and skip there.
    page_ink = pytest.importorskip("render").page_ink

    class _Recipe:
        def __init__(self, *tags):
            self.tags = frozenset(tags)

    assert page_ink(_Recipe("thermal", "till_receipt")) == "thermal"
    assert page_ink(_Recipe("impact")) == "dotmatrix"
    assert page_ink(_Recipe("doc_invoice", "a4")) == "print"
    # A roll that is both is thermal: the paper decides before the print head.
    assert page_ink(_Recipe("thermal", "impact")) == "thermal"


def test_both_tags_are_ones_the_shipped_rules_actually_draw():
    """A mapping onto a tag no recipe carries is dead code that looks alive.

    Asked of the RULES, not of 120 sampled recipes. Sampling answered the same
    question and answered it differently depending on what ran before it in
    the file -- `rulebase` caches the rules it loaded, so a test that imports
    the render path first can move which root the sampler reads. A tag either
    is written on some option or it is not, and that is a fact about the files.
    """
    from rulebase import load_rules

    INK_BY_TAG = pytest.importorskip("render").INK_BY_TAG

    written = {tag for options in load_rules().values()
               for option in options for tag in option.tags}
    for tag, _ink in INK_BY_TAG:
        assert tag in written, f"no option in rules/ is tagged {tag!r}"


# ------------------------------------------------------------------ the record


def test_every_word_carries_an_ink():
    words = record.words_from_boxes(
        [_box("store.name"), _box("seal.round", ""), _box("sign.name", "hand")],
        "thermal")
    assert [w["ink"] for w in words] == ["thermal", "stamp", "hand"]


def test_the_record_refuses_a_word_with_no_ink():
    """A key nothing requires is a key that silently goes missing -- which is
    the failure this whole axis was added after."""
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")], ink="print")
    del built["word_annotations"][0]["ink"]
    assert any("ink" in problem for problem in record.validate(built))


def test_the_record_refuses_an_ink_outside_the_vocabulary():
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")], ink="print")
    built["word_annotations"][0]["ink"] = "crayon"
    assert any("ink must be one of" in problem for problem in record.validate(built))


def test_a_record_built_with_no_ink_argument_is_still_valid():
    """Additive: every existing caller keeps working and gets `print`."""
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")],
                         extracted={"store": {"name": "x"}})
    assert built["word_annotations"][0]["ink"] == "print"
    assert record.validate(built) == []


# ----------------------------------------------------- what the renderer marks


@pytest.mark.parametrize("source,marker", [
    ("generators/html/sheets/base.py", 'data-ink="stamp"'),
    ("generators/html/handwriting.py", 'data-ink="hand"'),
])
def test_the_renderer_says_so_where_only_it_can_know(source, marker):
    assert marker in (REPO_ROOT / source).read_text(encoding="utf-8"), source


def test_the_measurement_reads_the_nearest_marked_ancestor():
    """`closest`, not the span's own dataset: a family marks a whole reversed
    BAND once rather than every run inside it, and a hand-filled field wraps
    its ink in an element of its own."""
    page = (REPO_ROOT / "generators" / "html" / "page.py").read_text(encoding="utf-8")
    assert "closest('[data-ink]')" in page


# ------------------------------------------------------------ reversed


def test_a_design_that_paints_the_heads_dark_declares_it():
    """Declared beside the CSS, not sniffed out of it. Reading
    `background:#...` and `color:#fff` back out of a stylesheet is right until
    a design writes the same thing another way; a boolean is right because the
    author said so."""
    from agent import redesign

    reversing = [d for d in redesign.DESIGNS if d.reversed_header]
    assert reversing, "no design reverses its heads; drop this axis value"
    for design in reversing:
        assert "color:#fff" in design.css, (
            f"{design.id} claims a reversed head band and paints no light type")


def test_the_flag_survives_the_trip_to_the_renderer():
    """`Design` -> `Variant` -> the option's `params` -> `sheets/variant.py`.
    Four hops, and the value is useless if any one drops it."""
    from agent import policy, redesign
    from agent import rules as agent_rules

    options = agent_rules.variant_options(redesign.as_variants(), policy.load())
    by_id = {option.id: option for option in options}
    for design in redesign.DESIGNS:
        assert by_id[design.id].params["reversed_header"] is design.reversed_header


def test_the_heads_of_the_item_table_are_marked_and_nothing_else_is():
    from sheets import variant

    markup = ('<div id="sheet"><table class="items"><thead>'
              '<tr><th data-cell="" data-col="0">STT</th>'
              '<th data-cell="" data-col="1">Tên</th></tr></thead>'
              '<tbody><tr><td data-cell="">1</td>'
              '<td data-cell=""><table><thead><tr><th >Phí</th></tr></thead>'
              '</table></td></tr></tbody></table>'
              '<table class="summary"><thead><tr><th >Thuế</th></tr>'
              '</thead></table></div>')
    out = variant.mark_reversed(markup)
    assert out.count('data-ink="reversed"') == 2, (
        "only the item table's own head band: a nested table in a body cell is "
        "another table's heads, and a summary table is not `table.items`")
    assert '<th data-ink="reversed" data-cell="" data-col="0">STT' in out


def test_a_page_with_no_item_table_is_left_alone():
    from sheets import variant

    markup = '<div id="sheet"><p>không có bảng nào</p></div>'
    assert variant.mark_reversed(markup) == markup


def test_the_measurement_covers_every_word_in_a_marked_cell():
    """One attribute on the `<th>`, not one per run: `CELL_RECTS_JS` reads
    `closest('[data-ink]')`, so a heading that wraps to two lines needs one
    mark, not two."""
    words = record.words_from_boxes(
        [_box("colhdr", "reversed", "Thành"), _box("colhdr", "reversed", "tiền")],
        "print")
    assert [w["ink"] for w in words] == ["reversed", "reversed"]
