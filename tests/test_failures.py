"""`pipeline/failures.py::classify` against every reason string the real
per-page gate (`synthgen/llm_page.py::problems`,
`agent/compose_page.py::plan_problems`/`sheet_plan_problems`) can produce.

Not synthetic guesses at what the gate MIGHT say -- each test calls the real
gate function with a crafted bad input and classifies whatever string comes
back, the same way `pipeline.failures` would see it live. If a gate function
ever rewords a reason, the matching test here breaks before `classify()`
silently starts mis-filing it under `SCHEMA_VIOLATION`.

Nothing below renders an image or starts a model, so this runs in the
dependency-free CI job.
"""

from __future__ import annotations

from agent.compose_page import plan_problems, sheet_plan_problems
from pipeline import failures as F
from synthgen.llm_page import problems

SHEET = ('<div class="sheet">'
        '<span data-kind="title">HOÁ ĐƠN</span>'
        '<span data-kind="invoice.field">0312345678</span>'
        '</div>')


def _one(reasons: list[str]) -> str:
    assert reasons, "gate function không thấy lỗi nào -- fixture chưa sai"
    return F.classify(reasons[0])


# ---------------------------------------------------------- problems()


def test_a_bare_table_cell_is_invalid_table_cell():
    bad = ('<div class="sheet"><table><tr><td>x</td></tr></table></div>')
    assert _one(problems(bad)) == F.INVALID_TABLE_CELL


def test_a_malformed_data_path_is_schema_violation():
    bad = (SHEET.replace("</div>", "") +
          '<span data-kind="x" data-path="Bad Path!">y</span></div>')
    assert _one(problems(bad)) == F.SCHEMA_VIOLATION


def test_conflicting_values_for_the_same_path_is_duplicate_data_path():
    bad = ('<div class="sheet">'
          '<span data-kind="title" data-path="issuer.tax_code">1</span>'
          '<span data-kind="title" data-path="issuer.tax_code">2</span>'
          '</div>')
    assert _one(problems(bad)) == F.DUPLICATE_DATA_PATH


def test_an_unknown_data_region_is_wrong_region_type():
    bad = ('<div class="sheet"><div data-region="Bang">'
          '<span data-kind="title">X</span></div></div>')
    assert _one(problems(bad)) == F.WRONG_REGION_TYPE


def test_a_nested_tag_is_missing_box():
    bad = '<div class="sheet"><span data-kind="title">A <b>B</b></span></div>'
    assert _one(problems(bad)) == F.MISSING_BOX


def test_a_run_outside_every_sheet_is_missing_box():
    bad = SHEET + '<span data-kind="note">lạc</span>'
    assert _one(problems(bad)) == F.MISSING_BOX


def test_no_sheet_at_all_is_schema_violation():
    bad = '<div><span data-kind="title">X</span></div>'
    assert _one(problems(bad)) == F.SCHEMA_VIOLATION


def test_an_unknown_data_kind_is_schema_violation():
    bad = '<div class="sheet"><span data-kind="totally.bogus.kind">X</span></div>'
    assert _one(problems(bad)) == F.SCHEMA_VIOLATION


def test_no_labelled_run_at_all_is_schema_violation():
    bad = '<div class="sheet"><p>không nhãn nào</p></div>'
    assert _one(problems(bad)) == F.SCHEMA_VIOLATION


def test_an_empty_page_is_schema_violation():
    assert _one(problems("")) == F.SCHEMA_VIOLATION


def test_a_forbidden_script_tag_is_schema_violation():
    bad = SHEET + "<script>x()</script>"
    assert _one(problems(bad)) == F.SCHEMA_VIOLATION


def test_a_declared_value_no_run_prints_is_kie_false_negative():
    found = problems(SHEET, {"mst": "0312345678 không tồn tại trên trang"})
    assert _one(found) == F.KIE_FALSE_NEGATIVE


def test_a_value_printed_twice_is_duplicate_data_path():
    twice = ('<div class="sheet"><span data-kind="title">A</span>'
            '<span data-kind="note">A</span></div>')
    found = problems(twice, {"x": "A"})
    assert _one(found) == F.DUPLICATE_DATA_PATH


# ------------------------------------------------------- plan_problems()


def test_an_unknown_field_plan_kind_is_plan_violation():
    plan = {"field_plan": [{"label": "x", "kind": "totally.bogus"}]}
    assert _one(plan_problems(plan, SHEET)) == F.PLAN_VIOLATION


def test_dropping_most_of_the_field_plan_is_plan_violation():
    """`note` là kind hợp lệ nhưng KHÔNG in trong `SHEET` -- kế hoạch hứa
    mười lần, trang không giữ lời hứa nào."""
    plan = {"field_plan": [{"label": str(i), "kind": "note"} for i in range(10)]}
    assert _one(plan_problems(plan, SHEET)) == F.PLAN_VIOLATION


def test_a_signature_with_no_declared_signer_is_plan_violation():
    html = '<div class="sheet"><span data-kind="sign.name">A</span></div>'
    plan = {"field_plan": [], "signers": []}
    assert _one(plan_problems(plan, html)) == F.PLAN_VIOLATION


# --------------------------------------------------- sheet_plan_problems()


def test_an_empty_sheet_plan_is_density_violation():
    assert _one(sheet_plan_problems({}, 3)) == F.DENSITY_VIOLATION


def test_too_few_planned_sheets_is_density_violation():
    plan = {"sheet_plan": [{"sheet": 1, "sections": ["a"]}]}
    assert _one(sheet_plan_problems(plan, 3)) == F.DENSITY_VIOLATION


def test_a_sheet_with_no_sections_is_density_violation():
    plan = {"sheet_plan": [{"sheet": 1, "sections": []}]}
    assert _one(sheet_plan_problems(plan, 1)) == F.DENSITY_VIOLATION


# ----------------------------------------------------------------- tally


def test_tally_counts_by_code_not_by_sentence():
    reasons = [
        "2 ô bảng thiếu `data-cell` (vd `<td>`)",
        "5 ô bảng thiếu `data-cell` (vd `<th>`)",
        "`data-region=\"Bang\"` không phải một trong 16 nhãn vùng",
    ]
    assert F.tally(reasons) == {F.INVALID_TABLE_CELL: 2, F.WRONG_REGION_TYPE: 1}


def test_every_code_constant_is_in_codes():
    for name in ("MISSING_BOX", "WRONG_REGION_TYPE", "TEXT_TABLE_CONFUSION",
                "MISSING_DATA_PATH", "DUPLICATE_DATA_PATH",
                "INVALID_TABLE_CELL", "KIE_FALSE_POSITIVE",
                "KIE_FALSE_NEGATIVE", "PLAN_VIOLATION", "DENSITY_VIOLATION",
                "SCHEMA_VIOLATION", "DIVERSITY_COLLAPSE"):
        assert getattr(F, name) in F.CODES
    assert len(F.CODES) == 12


def test_an_unrecognized_reason_still_gets_a_code():
    assert F.classify("một câu chưa từng thấy trước đây") == F.SCHEMA_VIOLATION
