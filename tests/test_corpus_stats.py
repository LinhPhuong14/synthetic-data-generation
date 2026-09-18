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


def test_not_measurable_yet_names_every_phase_3_4_6_concept(tmp_path):
    """Không suy diễn số liệu cho những khái niệm chưa tồn tại trong code."""
    out = _write(tmp_path, {"asked": 0, "pages": []})
    result = stats(out)
    for key in ("table_morphology", "layout_topology", "density_profile",
               "hard_negative_profile", "structural_diversity_fingerprint"):
        assert key in result["not_measurable_yet"]
