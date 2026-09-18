"""`pipeline/fields.py::FieldRecord` -- một hình dạng chung cho entity và pair.

Nothing below renders an image or starts a model -- `registry()` works off
plain entity/pair dicts, so this runs in the dependency-free CI job, same as
`test_kie.py` and `test_record.py`.
"""

from __future__ import annotations

import pytest

from pipeline import fields as F


def an_entity(index, kind="menu.item", text="x", field_role="value",
              key_source=""):
    return {"entity_index": index, "kind": kind, "text": text,
            "field_role": field_role, "key_source": key_source}


def a_pair(value_index, path="", kind="menu.item", value="x", source="table"):
    return {"value_entity_index": value_index, "path": path, "role": kind,
            "value_text": value, "source": source}


# ----------------------------------------------------------------------- role


def test_only_the_four_known_roles_are_accepted():
    F.FieldRecord(path="", kind="x", value="y", role=F.POSITIVE)
    with pytest.raises(ValueError):
        F.FieldRecord(path="", kind="x", value="y", role="bogus")


def test_an_entity_that_is_a_caption_becomes_a_label():
    rec = F.from_entity(an_entity(0, field_role="key"))
    assert rec.role == F.LABEL


def test_an_entity_that_is_a_value_with_no_pair_becomes_ordinary():
    rec = F.from_entity(an_entity(0, field_role="value"))
    assert rec.role == F.ORDINARY


def test_an_entity_never_carries_a_path_on_its_own():
    """`entities_from_words` không đọc `data-path` -- chỉ tầng pair biết."""
    rec = F.from_entity(an_entity(0))
    assert rec.path == ""


def test_a_pair_is_always_positive():
    rec = F.from_pair(a_pair(3, path="issuer.tax_code"))
    assert rec.role == F.POSITIVE
    assert rec.path == "issuer.tax_code"


def test_a_pairs_role_key_is_the_data_kind_not_the_field_record_role():
    """`pair["role"]` là tên `kie_full.py` dùng cho `data-kind` -- trùng chữ
    với `FieldRecord.role` một cách tình cờ, không cùng nghĩa."""
    rec = F.from_pair(a_pair(3, kind="store.tax_code"))
    assert rec.kind == "store.tax_code"
    assert rec.role == F.POSITIVE


# ------------------------------------------------------------------ registry


def test_a_box_with_a_pair_uses_the_pairs_path_and_role():
    entities = [an_entity(0, field_role="value")]
    pairs = [a_pair(0, path="issuer.tax_code", source="declared")]
    out = F.registry(entities, pairs)
    assert len(out) == 1
    assert out[0].role == F.POSITIVE
    assert out[0].path == "issuer.tax_code"
    assert out[0].source == "declared"


def test_a_box_with_no_pair_falls_back_to_the_entity():
    entities = [an_entity(0, field_role="key", text="Mã số thuế:")]
    out = F.registry(entities, pairs=[])
    assert len(out) == 1
    assert out[0].role == F.LABEL
    assert out[0].path == ""


def test_every_entity_produces_exactly_one_field_record():
    entities = [an_entity(i) for i in range(5)]
    pairs = [a_pair(1), a_pair(3)]
    out = F.registry(entities, pairs)
    assert len(out) == len(entities)


def test_hard_negative_has_no_producer_yet():
    """Chưa có cơ chế hard-negative nào trong code -- khai vai trước để
    Phase 6 (docs/ke-hoach-refactor-engine.md) không phải đổi hình dạng."""
    assert F.HARD_NEGATIVE in F.ROLES
    entities = [an_entity(0)]
    out = F.registry(entities, pairs=[])
    assert all(r.role != F.HARD_NEGATIVE for r in out)
