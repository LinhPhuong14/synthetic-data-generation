"""Axis 4 -- WHAT KIND OF WIDGET a run's value answers with.

Same shape as `test_ink_axis.py` (axis 3): a vocabulary block, a
what-decides-it block ordered most-specific-signal-first, a record
build+validate block, and a what-the-renderer-marks block.

`presence` (signature/stamp) is deliberately absent from
`pipeline.record.ENTITY_FIELD_TYPES` and from every test below: it is not a
fact about one entity, it aggregates a signature block with page-wide stamp
existence, and is synthesized once in `synthgen/export_v3.py` instead --
see `pipeline/record.py::field_type_for`'s own docstring and
`docs/kie-schema-v3.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline import record  # noqa: E402


def _box(kind: str, shape: str = "", text: str = "x", field: int = 0):
    return {"kind": kind, "shape": shape, "text": text, "field": field,
            "quad": [[0, 0], [10, 0], [10, 10], [0, 10]]}


# --------------------------------------------------------------- the vocabulary


def test_the_six_values_are_the_ones_the_axis_defines():
    assert record.ENTITY_FIELD_TYPES == {
        "text", "boolean_choice", "multi_choice", "digit_sequence",
        "categorical_matrix", "data_table"}


def test_presence_is_not_in_the_entity_vocabulary():
    """It is synthesized at export time from a signature BLOCK plus
    page-wide stamp existence, never a fact `field_type_for` can compute
    from one kind/shape."""
    assert "presence" not in record.ENTITY_FIELD_TYPES


# ------------------------------------------------------------- what decides it


def test_the_shape_wins_over_kind_because_it_is_more_specific():
    """`yesno` and `options` draw byte-identical `survey.tick` runs and
    differ only in whether more than one may be picked -- authorial intent
    that leaves no trace in the ink except the tagged `shape`."""
    assert record.field_type_for("survey.question", "yesno") == "boolean_choice"
    assert record.field_type_for("survey.question", "options") == "multi_choice"
    assert record.field_type_for("survey.question", "scale") == "multi_choice"
    assert record.field_type_for("survey.question", "attachment") == "multi_choice"


def test_shape_covers_the_table_shaped_answers_too():
    """`grid`/`table_form` describe a whole answer TABLE, not one field --
    callers building `tables[]` read these off the question the same way."""
    assert record.field_type_for("survey.question", "grid") == "categorical_matrix"
    assert record.field_type_for("survey.question", "table_form") == "data_table"


def test_shape_covers_the_digit_box_answers():
    for shape in ("boxchar", "date_boxes", "rank"):
        assert record.field_type_for("survey.question", shape) == "digit_sequence"


def test_kind_alone_is_enough_when_no_other_shape_uses_it():
    """`survey.char` (a single digit box) and a lone `survey.tick`
    (`sheets/form.py::_checklist`'s own row, not inside a `survey.question`
    group) need no separate tag -- their `kind` is already unique to them."""
    assert record.field_type_for("survey.char") == "digit_sequence"
    assert record.field_type_for("survey.tick") == "boolean_choice"


def test_a_plain_field_with_no_signal_at_all_is_text():
    assert record.field_type_for("store.name") == "text"
    assert record.field_type_for("invoice.field") == "text"


def test_explicit_wins_outright():
    assert record.field_type_for("store.name", "", "digit_sequence") == "digit_sequence"


def test_an_unrecognised_shape_or_explicit_is_dropped_not_trusted():
    """The set is closed, same as `ink_for`: a typo in a family module must
    not put a seventh field_type in a dataset a consumer has six classes
    for."""
    assert record.field_type_for("store.name", "made_up_shape") == "text"
    assert record.field_type_for("store.name", "", "made_up_type") == "text"


# ------------------------------------------------------------------ the record


def test_every_word_carries_a_field_type():
    words = record.words_from_boxes(
        [_box("store.name"), _box("survey.char"), _box("survey.tick")])
    assert [w["field_type"] for w in words] == ["text", "digit_sequence",
                                                "boolean_choice"]


def test_entities_read_shape_off_the_fields_array_not_the_word():
    """`shape` is a RUN-level signal (like `role`/`key`), carried through
    `entities_from_words`'s `fields` parameter -- the same array
    `data-role`/`data-key` already ride on -- not through `words`."""
    boxes = [_box("survey.question", "yesno", "Đã ký chưa?")]
    words = record.words_from_boxes(boxes)
    fields = [{"field": 0, "kind": "survey.question", "ink": "", "role": "key",
              "key": "", "shape": "yesno", "text": "Đã ký chưa?", "page": 1}]
    entities = record.entities_from_words(words, fields)
    assert entities[0]["field_type"] == "boolean_choice"


def test_a_record_built_with_no_shape_argument_is_still_valid():
    """Additive: every existing caller (no `shape` key in its `fields`
    entries) keeps working and gets the kind-based answer, `text` for a
    plain field."""
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")],
                         extracted={"store": {"name": "x"}})
    assert record.validate(built) == []
    assert all("field_type" in w for w in built["word_annotations"])
