"""Phase 6 (`docs/ke-hoach-refactor-engine.md`): hard negatives model tự khai.

Ba lớp việc, ba nơi:

* `synthgen/kie_full.py::hard_negative_spans[_all]` -- đọc `data-decoy-for`
  ra khỏi HTML thật, ghép với thực thể đúng thứ tự DOM (`zip`, cùng kỹ
  thuật `declared_pairs`).
* `pipeline/fields.py::HardNegativeRecord`/`from_hard_negative`/`registry()`
  -- xem `tests/test_fields.py`.
* `synthgen/llm_page.py::problems()` -- cổng chặn một span vừa khai
  `data-decoy-for="X"` vừa tự mang `data-kind="X"`.

Nothing below renders an image or starts a model -- chuỗi HTML và dict
`record` thuần, chạy trong CI không phụ thuộc, cùng chỗ `test_kie_full_dedup.py`
và `test_llm_page.py`."""

from __future__ import annotations

import pytest

from synthgen import kie_full
from synthgen.llm_page import problems

_STUB_KINDS = frozenset({"title", "note", "store.tax_code", "invoice.total"})


@pytest.fixture(autouse=True)
def _stub_kinds(monkeypatch):
    """`problems()` calls `kinds()`, which renders 300 engine pages to harvest
    the real `data-kind` vocabulary -- currently broken by unrelated
    in-progress work on `synthgen/markup.py` (`KeyError: 'table'` in
    `_BUILDERS`, same breakage documented as Phase 5.5 in
    `docs/ke-hoach-refactor-engine.md`, confirmed independent of anything in
    this file). Stub it, same precedent as `tests/test_plan_conformance.py`."""
    monkeypatch.setattr("synthgen.llm_page.kinds", lambda: _STUB_KINDS)


def an_entity(index, text="x", bbox=(0, 0, 10, 10), page=1):
    return {"entity_index": index, "text": text, "bbox": list(bbox),
            "page_number": page}


# ------------------------------------------------- kie_full.hard_negative_spans


def test_a_plain_declared_pair_span_is_not_a_hard_negative():
    markup = ('<div class="sheet"><table><tr><td data-cell="x">'
             '<span data-kind="store.tax_code" data-path="store.tax_code">'
             '12-3456789</span></td></tr></table></div>')
    record = {"entity_annotations": [an_entity(0, text="12-3456789")]}
    assert kie_full.hard_negative_spans(record, markup, page=1) == []


def test_a_decoy_span_is_picked_up_with_its_target_and_own_kind():
    markup = ('<div class="sheet"><table><tr><td data-cell="x">'
             '<span data-kind="note" data-decoy-for="store.tax_code">'
             '99-9999999</span></td></tr></table></div>')
    record = {"entity_annotations": [an_entity(0, text="99-9999999")]}
    out = kie_full.hard_negative_spans(record, markup, page=1)
    assert len(out) == 1
    assert out[0]["target_kind"] == "store.tax_code"
    assert out[0]["negative_kind"] == "note"
    assert out[0]["text"] == "99-9999999"
    assert out[0]["value_entity_index"] == 0


def test_a_decoy_span_with_no_own_kind_still_counts():
    """`data-decoy-for` không cần đi cùng `data-kind` -- mồi giả có thể là
    một run trần, chỉ khai mình đang giả làm gì."""
    markup = ('<div class="sheet"><table><tr><td data-cell="x">'
             '<span data-decoy-for="invoice.total">1.000.000</span>'
             '</td></tr></table></div>')
    record = {"entity_annotations": [an_entity(0, text="1.000.000")]}
    out = kie_full.hard_negative_spans(record, markup, page=1)
    assert len(out) == 0, "span không có data-kind không lọt qua bộ đọc span"


def test_hard_negative_spans_all_calls_one_page_at_a_time_and_merges(monkeypatch):
    """Cùng khuôn `declared_pairs_all` -- gọi `hard_negative_spans` cho từng
    trang `1..pages` rồi nối kết quả lại, không tự đọc lại markup."""
    calls: list[int] = []

    def fake(record, markup, page):
        calls.append(page)
        return [{"target_kind": f"kind{page}"}]

    monkeypatch.setattr(kie_full, "hard_negative_spans", fake)
    record = {"source_files": ["p1.png", "p2.png", "p3.png"]}
    out = kie_full.hard_negative_spans_all(record, "<html/>")
    assert calls == [1, 2, 3]
    assert [o["target_kind"] for o in out] == ["kind1", "kind2", "kind3"]


# --------------------------------------------------- llm_page gate (Phase 6.3)


def test_a_decoy_that_also_claims_its_own_target_kind_is_refused():
    bad = ('<div class="sheet">'
          '<span data-kind="store.tax_code" data-decoy-for="store.tax_code">'
          '99-9999999</span></div>')
    found = problems(bad)
    assert any("mồi giả không được trùng kind" in line for line in found)


def test_a_decoy_with_a_different_own_kind_is_fine():
    good = ('<div class="sheet">'
           '<span data-kind="note" data-decoy-for="store.tax_code">'
           '99-9999999</span></div>')
    assert not any("mồi giả" in line for line in problems(good))


def test_a_span_with_no_decoy_attribute_is_never_flagged_by_this_gate():
    plain = '<div class="sheet"><span data-kind="title">A</span></div>'
    assert not any("mồi giả" in line for line in problems(plain))
