"""`tools/llm/corpus_stats.py` -- đọc một `compose_report.json` + `html/`
đã sinh, không gọi model, không vẽ ảnh.

Nothing below starts a browser or a model, so this runs in the
dependency-free CI job.
"""

from __future__ import annotations

import json

from tools.llm.corpus_stats import stats


def _write(tmp_path, report, html_by_slug=None, rejected_by_slug=None):
    (tmp_path / "compose_report.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")
    for slug, html in (html_by_slug or {}).items():
        d = tmp_path / "html" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"llm_{slug}_0000.html").write_text(html, encoding="utf-8")
    for slug, html in (rejected_by_slug or {}).items():
        d = tmp_path / "rejected"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"llm_{slug}_0000.html").write_text(html, encoding="utf-8")
    return tmp_path


SPAN = '<span data-kind="title" data-path="doc.title">A</span>'
SPAN_NO_PATH = '<span data-kind="note">B</span>'


def test_raises_a_clear_error_when_the_report_is_missing(tmp_path):
    import pytest
    with pytest.raises(SystemExit, match="compose_report.json"):
        stats(tmp_path)


def test_family_counts_come_from_archetype(tmp_path):
    report = {"asked": 2, "pages": [
        {"archetype": "invoice", "ok": True, "why": []},
        {"archetype": "invoice", "ok": False, "why": ["trang rỗng"]},
    ]}
    out = _write(tmp_path, report)
    result = stats(out)
    assert result["family_counts"] == {"invoice": 2}
    assert result["kept"] == 1
    assert result["pass_rate"] == 0.5


def test_failure_codes_come_from_pipeline_failures_when_report_lacks_them(tmp_path):
    report = {"asked": 1, "pages": [
        {"archetype": "x", "ok": False,
         "why": ["3 ô bảng thiếu `data-cell` (vd `<td>`)"]},
    ]}
    out = _write(tmp_path, report)
    result = stats(out)
    assert result["failure_codes"] == {"INVALID_TABLE_CELL": 1}


def test_failure_codes_prefer_the_reports_own_tally_when_present(tmp_path):
    report = {"asked": 1, "pages": [{"archetype": "x", "ok": False, "why": []}],
             "failure_codes": {"MISSING_BOX": 7}}
    out = _write(tmp_path, report)
    result = stats(out)
    assert result["failure_codes"] == {"MISSING_BOX": 7}


def test_table_asked_rate_averages_across_pages(tmp_path):
    report = {"asked": 4, "pages": [
        {"archetype": "x", "ok": True, "why": [], "table_asked": True},
        {"archetype": "x", "ok": True, "why": [], "table_asked": True},
        {"archetype": "x", "ok": True, "why": [], "table_asked": False},
        {"archetype": "x", "ok": True, "why": [], "table_asked": False},
    ]}
    out = _write(tmp_path, report)
    assert stats(out)["table_asked_rate"] == 0.5


def test_data_path_coverage_is_split_kept_vs_rejected(tmp_path):
    report = {"asked": 2, "pages": [
        {"archetype": "a", "ok": True, "why": []},
        {"archetype": "b", "ok": False, "why": ["trang rỗng"]},
    ]}
    out = _write(tmp_path, report,
                html_by_slug={"a": f'<div class="sheet">{SPAN}</div>'},
                rejected_by_slug={"b": f'<div class="sheet">{SPAN_NO_PATH}</div>'})
    result = stats(out)
    assert result["data_path_coverage_on_kept_pages"] == {
        "pages": 1, "min": 1.0, "max": 1.0, "mean": 1.0}
    assert result["data_path_coverage_on_rejected_pages"] == {
        "pages": 1, "min": 0.0, "max": 0.0, "mean": 0.0}


def test_not_measurable_here_names_what_needs_a_different_tool(tmp_path):
    """Phase 7.3: những khái niệm Phase 3/4/6 viết rồi (table morphology,
    density, hard-negative profile, fingerprint) giờ ĐO ĐƯỢC (xem
    `document_diversity`/`hard_negative_coverage` bên dưới) -- chỉ còn thứ
    cần ảnh đã vẽ (`synthgen/check.py`, Phase 8.2) hoặc không áp dụng cho
    track 3 (dressing diversity, Phase 7.1) là thật sự ngoài script này."""
    out = _write(tmp_path, {"asked": 0, "pages": []})
    result = stats(out)
    for key in ("missing_box_rate", "text_table_confusion_rate",
               "duplicate_or_near_duplicate_rate", "dressing_diversity"):
        assert key in result["not_measurable_here"]


# ------------------------------------------------- document_diversity (7.3)


def _kept_page(archetype, engine_plan, hard_negative_profile=None, index=0):
    return {"archetype": archetype, "ok": True, "why": [], "index": index,
           "engine_plan": engine_plan,
           "hard_negative_profile": hard_negative_profile or {}}


def test_document_diversity_of_identical_plans_is_zero(tmp_path):
    plan = {"density": "sparse", "table": "simple"}
    report = {"asked": 2, "pages": [_kept_page("x", plan, index=0),
                                    _kept_page("x", plan, index=1)]}
    out = _write(tmp_path, report)
    result = stats(out)["document_diversity"]
    assert result["distinct_coarse"] == 1
    assert result["mean_pairwise_distance"] == 0.0


def test_document_diversity_across_different_families_is_nonzero(tmp_path):
    report = {"asked": 2, "pages": [
        _kept_page("invoice", {"density": "sparse"}, index=0),
        _kept_page("contract", {"density": "dense"}, index=1),
    ]}
    out = _write(tmp_path, report)
    result = stats(out)["document_diversity"]
    assert result["distinct_coarse"] == 2
    assert result["mean_pairwise_distance"] > 0.0


def test_document_diversity_only_counts_kept_pages(tmp_path):
    report = {"asked": 2, "pages": [
        _kept_page("invoice", {"density": "sparse"}, index=0),
        {"archetype": "x", "ok": False, "why": ["trang rỗng"], "index": 1},
    ]}
    out = _write(tmp_path, report)
    result = stats(out)["document_diversity"]
    assert result["documents"] == 1


# ---------------------------------------------- hard_negative_coverage (7.3)


def test_hard_negative_coverage_counts_pages_asked_vs_realized(tmp_path):
    report = {"asked": 2, "pages": [
        _kept_page("a", {}, hard_negative_profile={"store.tax_code": "lexical"},
                  index=0),
        _kept_page("b", {}, hard_negative_profile={"invoice.total": "format"},
                  index=1),
    ]}
    decoy_html = ('<div class="sheet"><span data-kind="note" '
                 'data-decoy-for="store.tax_code">99</span></div>')
    plain_html = '<div class="sheet"><span data-kind="title">A</span></div>'
    out = _write(tmp_path, report)
    (out / "html").mkdir(parents=True, exist_ok=True)
    (out / "html" / "llm_a_0000.html").write_text(decoy_html, encoding="utf-8")
    (out / "html" / "llm_b_0001.html").write_text(plain_html, encoding="utf-8")
    result = stats(out)["hard_negative_coverage"]
    assert result["pages_asked"] == 2
    assert result["pages_realized"] == 1
    assert result["decoys_realized"] == 1
    assert result["realization_rate"] == 0.5


def test_hard_negative_coverage_is_none_when_nothing_was_asked(tmp_path):
    report = {"asked": 1, "pages": [_kept_page("a", {}, index=0)]}
    out = _write(tmp_path, report)
    result = stats(out)["hard_negative_coverage"]
    assert result["pages_asked"] == 0
    assert result["realization_rate"] is None
