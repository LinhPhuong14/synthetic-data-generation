"""`pipeline/kie.py`'s pairing rule, slug, and fallback/override split.

Nothing below renders an image or starts a model -- `pair_fields`/`build_page`
work off a plain list of block dicts, so this runs in the dependency-free CI
job, same as `test_record.py`.
"""

from __future__ import annotations

import json

import pytest

from pipeline import kie


def a_block(kind, text, x1=0):
    return {"kind": kind, "text": text, "bbox": {"x1": x1, "y1": 0, "x2": x1 + 10, "y2": 10}}


# --------------------------------------------------------------------- slug


def test_slug_folds_diacritics_and_punctuation():
    assert kie.slug("Người mua:") == "nguoi_mua"
    assert kie.slug("ĐỊA CHỈ") == "dia_chi"


def test_slug_never_empty():
    assert kie.slug("") == "field"
    assert kie.slug("###") == "field"


# --------------------------------------------------------------- pair_fields


def test_pairs_a_label_with_the_block_right_after_it():
    blocks = [a_block("store.name.label", "Tên:"), a_block("store.name", "NHA HANG")]
    pairs = kie.pair_fields(blocks)
    assert len(pairs) == 1
    assert pairs[0]["field"] == "ten"
    assert pairs[0]["key_text"] == "Tên:"
    assert pairs[0]["value_text"] == "NHA HANG"


def test_pairs_the_generic_kind_every_shared_field_kind_uses():
    """`invoice.field.label`/`invoice.field` repeats across every row on a
    page -- see the module docstring's whole reason for pairing by adjacency
    instead of by `kind`."""
    blocks = [
        a_block("invoice.field.label", "Số:"), a_block("invoice.field", "00123"),
        a_block("invoice.field.label", "Ngày:"), a_block("invoice.field", "01/01/2024"),
    ]
    pairs = kie.pair_fields(blocks)
    assert [p["field"] for p in pairs] == ["so", "ngay"]
    assert [p["value_text"] for p in pairs] == ["00123", "01/01/2024"]


def test_a_repeated_caption_gets_a_numbered_field_name():
    blocks = [
        a_block("invoice.field.label", "KM:"), a_block("invoice.field", "-1.000"),
        a_block("invoice.field.label", "KM:"), a_block("invoice.field", "-2.000"),
    ]
    pairs = kie.pair_fields(blocks)
    assert [p["field"] for p in pairs] == ["km", "km_2"]


def test_two_captions_back_to_back_do_not_pair():
    """A caption followed by another caption (no real value between them) is
    not a key-value pair -- `.label`/`.title` on the second block excludes it."""
    blocks = [a_block("store.name.label", "Tên:"), a_block("subhead.label", "Ghi chú")]
    assert kie.pair_fields(blocks) == []


def test_a_caption_with_nothing_after_it_is_dropped():
    assert kie.pair_fields([a_block("store.name.label", "Tên:")]) == []


def test_a_blank_value_does_not_pair():
    blocks = [a_block("store.name.label", "Tên:"), a_block("store.name", "  ")]
    assert kie.pair_fields(blocks) == []


def test_a_caption_at_the_end_of_one_page_does_not_pair_across_a_page_break():
    """`pipeline.record.build`'s multi-page `sheets=` argument concatenates
    every side's blocks into one flat list -- a caption that happens to be
    the last block of page 1 must not pair with page 2's first block just
    because adjacency alone would say so."""
    last_of_page_1 = {**a_block("invoice.field.label", "Ký hiệu:"), "page_number": 1}
    first_of_page_2 = {**a_block("menu.stt", "1"), "page_number": 2}
    assert kie.pair_fields([last_of_page_1, first_of_page_2]) == []


def test_a_caption_still_pairs_with_a_value_on_the_same_page_number():
    key = {**a_block("invoice.field.label", "Ký hiệu:"), "page_number": 2}
    value = {**a_block("invoice.field", "1K20MXS"), "page_number": 2}
    pairs = kie.pair_fields([key, value])
    assert len(pairs) == 1 and pairs[0]["value_text"] == "1K20MXS"


# ---------------------------------------------------------------- build_page


def test_a_known_field_is_described_in_english_with_no_overrides_file(monkeypatch):
    """No overrides file is the ORDINARY case, and it must not leave a page
    describing "Tên cửa hàng" as "Tên cửa hàng". `rulebase/kie_glossary.py`
    answers first now, so the description is English and says what the value
    is -- which is the whole point of the field, since the printed caption is
    already in `key_text` beside it."""
    monkeypatch.delenv(kie.DESCRIPTIONS_ENV, raising=False)
    kie._all_descriptions.cache_clear()
    blocks = [a_block("store.name.label", "Tên cửa hàng:"), a_block("store.name", "NHA HANG")]
    page = kie.build_page(blocks, layout="some_layout")
    described = page["schema"]["properties"]["ten_cua_hang"]["description"]
    assert described != "Tên cửa hàng"
    assert not any(mark in described for mark in "ăâđêôơư")
    pair = page["pairs"][0]
    assert pair["description_source"] == "llm"
    assert pair["field"] in page["schema"]["properties"]


def test_a_caption_no_glossary_entry_names_still_falls_back_to_its_own_text():
    """The floor is still there for a slug nobody has written a meaning for --
    an invented caption resolves to nothing in either table, and the page keeps
    the printed text rather than losing the field.

    Nhưng câu tả KHÔNG còn là chính cái nhãn. Bản trước trả về nguyên văn
    nhãn, nên trường `cccd` có câu tả "CCCD" -- một câu tả lặp lại tên trường
    thì người đọc `kie.schema` không biết thêm gì. Đo trên `data/test1`: 35
    trường như vậy, còn 7 sau khi sửa, và bảy cái ấy là mục có thật trong từ
    điển chứ không phải tiếng vọng.

    Thứ ta biết chắc vẫn là chữ in trên giấy, nên nó vẫn nằm trong câu tả --
    chỉ là thành một câu nói rõ nó là GIÁ TRỊ in cạnh cái nhãn ấy."""
    kie._all_descriptions.cache_clear()
    blocks = [a_block("zzz.label", "Chuyến phà cuối cùng qua sông Mẫu Hạ:"),
              a_block("zzz", "Bốn mươi ba năm")]
    page = kie.build_page(blocks, layout="some_layout")
    pair = page["pairs"][0]
    assert pair["description_source"] in ("caption", "fallback")
    assert "Chuyến phà cuối cùng qua sông Mẫu Hạ" in pair["description"]
    assert pair["description"] != "Chuyến phà cuối cùng qua sông Mẫu Hạ", (
        "câu tả không được là chính cái nhãn")


def test_build_page_uses_an_override_when_the_layout_and_field_match(tmp_path, monkeypatch):
    path = tmp_path / "kie_descriptions.json"
    path.write_text(json.dumps({"some_layout": {"ten_cua_hang": "The shop's own name"}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()
    blocks = [a_block("store.name.label", "Tên cửa hàng:"), a_block("store.name", "NHA HANG")]
    page = kie.build_page(blocks, layout="some_layout")
    assert page["pairs"][0]["description"] == "The shop's own name"
    assert page["pairs"][0]["description_source"] == "llm"
    kie._all_descriptions.cache_clear()


def test_build_page_ignores_an_override_for_a_different_layout(tmp_path, monkeypatch):
    path = tmp_path / "kie_descriptions.json"
    path.write_text(json.dumps({"other_layout": {"ten_cua_hang": "wrong layout"}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()
    blocks = [a_block("store.name.label", "Tên cửa hàng:"), a_block("store.name", "NHA HANG")]
    page = kie.build_page(blocks, layout="some_layout")
    assert page["pairs"][0]["description"] != "wrong layout"
    kie._all_descriptions.cache_clear()


def test_an_unreadable_overrides_file_falls_back_quietly(tmp_path, monkeypatch):
    path = tmp_path / "kie_descriptions.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()
    blocks = [a_block("store.name.label", "Tên:"), a_block("store.name", "NHA HANG")]
    page = kie.build_page(blocks, layout="some_layout")
    # Quietly: no exception out of the broken file, and a description anyway.
    assert page["pairs"][0]["description"].strip()
    kie._all_descriptions.cache_clear()


def test_build_page_with_no_pairs_is_an_empty_schema():
    page = kie.build_page([a_block("title", "HOÁ ĐƠN")], layout="x")
    assert page == {"schema": {"type": "object", "properties": {}}, "pairs": []}
