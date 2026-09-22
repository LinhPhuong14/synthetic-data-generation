"""Phôi khai bằng file: định dạng tả đủ một phôi, và cổng nói đúng cái sai.

Không vẽ ảnh, không gọi model -- `archetypes` chỉ đọc YAML và so với từ vựng
`design.py` đã có -- nên nó chạy trong cái CI không cần phụ thuộc nào.

Cái khiến file này tồn tại: `design.py::ARCHETYPES` là ngữ pháp của cả bộ sinh,
và giờ nó nhận thêm phôi từ đĩa. Một định dạng file tả THIẾU một trường thì phôi
nạp vào im lặng mất thứ ấy; một cái cổng quá chặt thì loại cả phôi đúng. Hai
test đầu khoá đúng hai chuyện đó.
"""

from __future__ import annotations

import yaml

from synthgen import archetypes as A
from synthgen import design as D


def a_spec(**over) -> dict:
    """Một phôi hợp lệ tối thiểu, sửa được từng trường để thử cổng."""
    spec = {
        "id": "phieu_thu_thu_nghiem",
        "titles": ["PHIẾU THU THỬ", "BIÊN LAI THỬ"],
        "subtitles": ["", "(Mẫu thử)"],
        "profile": "admin",
        "org_kind": "company",
        "national": 0.2,
        "fields": ["full_name", "id_no", "address_home", "phone_home"],
        "field_span": [2, 4],
        "columns": [["stt", "name", "amount"], ["stt", "ref", "name", "amount"]],
        "totals": "money",
        "words": False,
        "sign_sets": [["NGƯỜI NỘP TIỀN", "THỦ QUỸ"]],
        "notes": ["Liên 1: Lưu."],
        "rows": [2, 20],
        "always": ["letterhead", "doctitle", "fields", "table", "signatures"],
        "optional": ["notes", "footer"],
        "en_ok": False,
    }
    spec.update(over)
    return spec


# ------------------------------------------------------- định dạng tả đủ chưa


def test_every_archetype_in_the_engine_survives_a_round_trip_through_yaml():
    """34 phôi viết tay đi qua YAML rồi về, không mất gì.

    Đây là phép kiểm thật sự của định dạng file: nếu nó tả thiếu một trường,
    một phôi đi vòng sẽ về khác bản gốc, và một phôi do model viết sẽ thiếu
    đúng trường ấy mà không ai biết."""
    for arch in D.ARCHETYPES:
        spec = yaml.safe_load(yaml.safe_dump(A.as_spec(arch), allow_unicode=True))
        assert not A.problems(spec, taken=set()), arch.id
        assert A.as_spec(A.build(spec)) == A.as_spec(arch), arch.id


def test_the_gate_accepts_every_archetype_a_person_wrote():
    """Luật nào loại một phôi người đã viết là luật sai, không phải phôi sai.

    Cùng bất biến `agent/corpus_rules.py` dựng cho corpus. Đã bắt được hai luật
    sai của chính file này: `sign_sets` đòi ít nhất một bộ (`thuc_don` là thực
    đơn, không ai ký vào thực đơn) và "có khối `totals` thì `totals` không được
    là `none`" (khối ấy chỉ in ra rỗng, vô hại)."""
    for arch in D.ARCHETYPES:
        spec = A.as_spec(arch)
        assert not A.problems(spec, taken=set()), f"{arch.id}: {A.problems(spec, taken=set())}"


def test_the_schema_is_read_off_the_engine_not_written_down():
    """Thêm một cột vào `design.COLUMNS` thì schema tự biết.

    Một schema khai tay sẽ cũ đi đúng vào ngày ai đó thêm cột, và một schema cũ
    từ chối một phôi đúng."""
    rules = A.schema()
    assert set(rules["columns"]["values"]) == set(D.COLUMNS)
    assert set(rules["profile"]["values"]) == {a.profile for a in D.ARCHETYPES}
    blocks = {b for a in D.ARCHETYPES for b in a.always + a.optional}
    assert set(rules["always"]["values"]) == blocks


# ------------------------------------------------------------- cổng nói gì sai


def test_a_name_outside_the_closed_vocabulary_is_named_with_what_is_allowed():
    found = A.problems(a_spec(profile="ke_toan"), taken=set())
    assert any("ke_toan" in line and "admin" in line for line in found), found


def test_a_block_declared_both_always_and_optional_is_caught():
    spec = a_spec(always=["letterhead", "doctitle", "notes"],
                  optional=["notes", "footer"])
    assert any("vừa `always` vừa `optional`" in line
               for line in A.problems(spec, taken=set()))


def test_a_table_with_no_columns_is_caught():
    spec = a_spec(columns=[])
    assert any("`table` mà không khai `columns`" in line
               for line in A.problems(spec, taken=set()))


def test_a_span_wider_than_the_field_pool_is_caught():
    spec = a_spec(field_span=[9, 12])
    assert any("chỉ có 4" in line for line in A.problems(spec, taken=set()))


def test_an_id_already_taken_is_caught():
    spec = a_spec(id="hoa_don_gtgt")
    assert any("đã có một phôi mang id ấy"
               in line for line in A.problems(spec, taken={"hoa_don_gtgt"}))


def test_a_signature_block_with_no_signers_is_caught():
    spec = a_spec(sign_sets=[])
    assert any("`signatures` mà `sign_sets` rỗng"
               in line for line in A.problems(spec, taken=set()))


# ------------------------------------------- cổng của bước sinh: so với BỘ có










def test_the_national_masthead_is_never_a_title_wherever_it_is_printed():
    """Quốc hiệu in ở HAI nhánh của `markup.py`, và một lần sửa chỉ đổi một.

    Mọi công văn đều in đúng hai dòng ấy, nên chúng không nói tờ này là giấy
    gì. Gọi là `Title` thì một trang có HAI `Title` và không cái nào là tên
    chứng từ. Đếm ở đây chứ không tin mắt: lần trước tôi sửa một nhánh, nửa số
    tờ giấy nhà nước vẫn ra hai `Title`, và chỉ lộ ra khi đọc bản ghi."""
    from synthgen import markup as M

    source = (M.__file__ or "")
    text = __import__("pathlib").Path(source).read_text(encoding="utf-8")
    for line in text.splitlines():
        if "NATIONAL_1" in line and "_span(" in line:
            assert '_span("masthead"' in line, line.strip()


