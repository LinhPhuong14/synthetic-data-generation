"""Ba tầng tên trường: cái gì vào Closed, cái gì vào Semi-open, cái gì chờ soát.

Test này canh một luật mà hỏng thì KHÔNG ai nhìn thấy được từ ảnh hay từ hộp:
một cái tên trượt bị ánh xạ về khoá gần nhất, rồi câu tả tra theo cái khoá sai
ấy. Hộp vẫn đúng pixel, nhãn vẫn đọc trôi chảy, và nghĩa thì sai -- đúng thứ
`synthgen/field_tier.py` gọi là lỗi kép.

Nên bài kiểm ở đây không chỉ hỏi "rơi đúng tầng chưa". Nó hỏi thêm hai câu mà
một cổng ánh xạ ngầm sẽ trả lời sai:

* tên `staging` có giữ NGUYÊN VĂN không, hay đã thành một cái tên khác;
* tên `staging` có mang câu tả của ai đó khác không, hay `describe is None`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FT = pytest.importorskip("synthgen.field_tier",
                         reason="cần pyyaml để nạp phôi và cổng mô tả")

# Loại chứng từ SOẠN TỰ DO, để ba tầng đều mở. Hợp đồng lao động trúng luật
# `^HỢP ĐỒNG\b` của `rulebase/field_tiers.json`, nên nó là `open_domain` --
# `test_group_of_a_freely_drafted_contract_is_open` canh chính điều đó, và nếu
# nó đổi nhóm thì mọi ca dưới đây đổi nghĩa chứ không im lặng vẫn xanh.
OPEN_DOC = "hop_dong_lao_dong"

# Câu tả đề xuất ĐẠT chuẩn: dài hơn `min_useful_chars` và không khớp mẫu
# `generic:` nào của `rulebase/synthgen/_kie_gates.yaml`.
GOOD_DESCRIBE = ("Serial number stamped on the utility meter this bill was "
                 "read from.")


# ------------------------------------------------------- ba ca bắt buộc

def test_a_registry_key_lands_in_closed_with_the_registry_sentence():
    """CLOSED: khoá có trong sổ, và câu tả tới từ sổ chứ không từ đâu khác."""
    got = FT.classify("store.tax_code", doc_type=OPEN_DOC)

    assert got.tier == FT.CLOSED
    assert got.in_batch is True
    assert got.status == ""
    assert got.source == "registry"
    assert got.describe == FT.registry().describe("store.tax_code", FT.KIND)
    assert got.describe and len(got.describe) > 20


def test_a_new_leaf_in_a_known_family_is_accepted_when_it_brings_a_sentence():
    """SEMI-OPEN: họ `store.` có thật, lá `meter_serial` chưa có -- vẫn nhận.

    Điều kiện là câu tả đi kèm TRONG CÙNG câu trả lời. Ca thứ hai trong test
    này (cùng cái tên, bỏ câu tả) là chỗ luật thật sự nằm: nếu thiếu câu tả mà
    vẫn lên `semi_open` thì sổ đã ngầm cho nó mượn nghĩa của họ."""
    got = FT.classify("store.meter_serial", describe=GOOD_DESCRIBE,
                      doc_type=OPEN_DOC)

    assert got.tier == FT.SEMI_OPEN
    assert got.in_batch is True
    assert got.family == "store."
    assert got.source == "proposed"
    assert got.describe == GOOD_DESCRIBE

    # Cùng cái tên, không câu tả -> KHÔNG được lên `semi_open`.
    bare = FT.classify("store.meter_serial", doc_type=OPEN_DOC)
    assert bare.tier == FT.STAGING
    assert bare.describe is None


def test_an_unknown_family_goes_to_staging_and_is_neither_rejected_nor_remapped():
    """STAGING: `patient.` không phải họ nào trong sổ.

    Ba điều phải đúng cùng lúc, và mỗi điều chặn một cách hỏng khác nhau:

    * KHÔNG bị loại thẳng -- tên đọc được, tờ giấy vẫn dùng được;
    * KHÔNG bị ánh xạ -- `key` vẫn là chính cái tên model viết;
    * KHÔNG mượn câu tả -- `describe is None`, không phải câu của `patient`
      nào đó hay của khoá gần nhất trong sổ.
    """
    name = "patient.bed_number"
    got = FT.classify(name, describe=GOOD_DESCRIBE, doc_type=OPEN_DOC)

    assert got.tier == FT.STAGING
    assert got.tier != FT.REJECT
    assert got.status == FT.CANDIDATE
    assert got.in_batch is False
    assert got.key == name and got.name == name
    assert got.key not in FT.registry().closed[FT.KIND]
    assert got.describe is None and got.source == ""
    assert "patient." in got.reason


# ------------------------------------------------ hỏng thì đóng, không đoán

@pytest.mark.parametrize("name", [
    "patient.dob",            # gần `customer.dob` trong không gian path
    "store.tax_codes",        # gần `store.tax_code` đúng một chữ cái
    "sign.titles",            # gần `sign.title` đúng một chữ cái
    "issuer.taxcode",         # gần `issuer.tax_code` đúng một dấu gạch
])
def test_a_near_miss_is_never_resolved_to_the_key_it_nearly_matches(name):
    """Không có ngưỡng tương tự nào, và đây là chỗ chứng minh điều đó.

    Bốn cái tên này lệch một ký tự khỏi một khoá có thật. Một cổng có phép đo
    tương tự sẽ nhận cả bốn, gán khoá kia, rồi gán luôn câu tả của khoá kia --
    và bản ghi ra đời không mang dấu vết nào của việc đã đoán."""
    got = FT.classify(name, doc_type=OPEN_DOC)

    assert got.tier in (FT.SEMI_OPEN, FT.STAGING)
    assert got.key == name
    assert got.describe is None or got.source == "proposed"
    # Không bao giờ là câu tả của khoá nó suýt trúng.
    for near in ("customer.dob", "store.tax_code", "sign.title"):
        said = FT.registry().describe(near, FT.KIND) or ""
        assert not said or got.describe != said


def test_a_name_that_is_not_a_name_is_rejected_not_staged():
    """Tên không đọc được KHÁC tên lạ. `staging` là hàng đợi soát của người,
    và đổ chữ Việt có dấu vào đó là biến nó thành sọt rác."""
    for junk in ("Số hoá đơn", "", "   ", "Tên/Địa chỉ"):
        got = FT.classify(junk, doc_type=OPEN_DOC)
        assert got.tier == FT.REJECT, junk
        assert got.in_batch is False


# ----------------------------------------------------- không gian `path`

def test_a_taught_path_is_closed_and_an_invented_spelling_of_it_is_not():
    """`line_items[].name` có trong sổ; `items[].name` là chính nó viết khác.

    Đây là trôi nghĩa đo được: 3 033 lượt `items[]` cạnh 2 038 lượt
    `line_items[]` trên cùng một kho, cho cùng một cái bảng hàng. Nhận cả hai
    là dạy mô hình rằng tên trường không có nghĩa; ánh xạ cái sau về cái trước
    là đoán. Nên cái sau vào hàng đợi soát, có tên có số, để người quyết."""
    good = FT.classify("line_items[3].name", space=FT.PATH, doc_type=OPEN_DOC)
    assert good.tier == FT.CLOSED
    assert good.key == "line_items[].name", "chỉ số phải gom về `[]`"

    drift = FT.classify("items[3].name", space=FT.PATH, doc_type=OPEN_DOC)
    assert drift.tier == FT.STAGING
    assert drift.describe is None


def test_bare_numeric_segments_are_indices_too():
    """`clause.1.body` và `clauses[0].body` là hai lối viết một chỗ ngồi --
    cổng chữ nhận cả hai (đo trên pilot16), nên chỗ gom cũng phải nhận cả hai."""
    assert FT.normalise("clauses[0].body") == "clauses[].body"
    assert FT.normalise("clause.1.body") == "clause.[].body"


# -------------------------------------------------- nhóm loại chứng từ

def test_group_of_a_freely_drafted_contract_is_open():
    assert FT.doc_group(OPEN_DOC) == FT.OPEN_DOMAIN


def test_a_statutory_form_takes_closed_only():
    """Tờ khai thuế: một lá mới có câu tả tử tế VẪN không vào bộ chính.

    Lý do không nằm ở chất lượng câu tả mà ở tờ giấy: tập trường của mẫu tờ
    khai do TT 80/2021/TT-BTC ấn định, nên một trường thêm vào là một tờ giấy
    tự nhận là mẫu luật định mà mang trường luật không có."""
    assert FT.doc_group("to_khai_thue_gtgt") == FT.CLOSED_BY_LAW

    got = FT.classify("store.meter_serial", describe=GOOD_DESCRIBE,
                      doc_type="to_khai_thue_gtgt")
    assert got.tier == FT.SEMI_OPEN
    assert got.in_batch is False
    assert got.status == FT.DROPPED

    # Khoá ĐÓNG thì vẫn qua, không nhóm nào siết được tầng `closed`.
    keep = FT.classify("store.tax_code", doc_type="to_khai_thue_gtgt")
    assert keep.tier == FT.CLOSED and keep.in_batch is True


def test_an_unreviewed_document_is_treated_strictly_not_loosely():
    """Chưa ai xếp nhóm thì siết, không nới.

    Hai chiều sai không cân nhau: siết nhầm một tờ tự do thì mất đa dạng, đếm
    được, sửa bằng một dòng `overrides`. Nới nhầm một biểu mẫu luật định thì
    sinh nhãn sai, và nhãn sai không tự kêu."""
    assert FT.effective_group(FT.UNREVIEWED) != FT.OPEN_DOMAIN


def test_the_title_rule_reaches_archetypes_declared_in_yaml():
    """Luật xếp nhóm phải đọc được tiêu đề của phôi khai bằng file.

    Bản đầu của `doc_group()` chỉ nhìn `id`, nên 437 phôi YAML im lặng rơi vào
    `unreviewed` dù luật tiêu đề đọc ra được chúng -- đúng kiểu hỏng mục 5
    `AGENTS.md` cảnh báo: bảng tay thì loại giấy mới thiếu khỏi, im lặng."""
    design = pytest.importorskip("synthgen.design")
    by_id = {a.id: a for a in design.ARCHETYPES}
    assert "hop_dong_xay_dung" in by_id, "phôi YAML không nạp được"
    assert FT.doc_group("hop_dong_xay_dung") == FT.OPEN_DOMAIN


# ------------------------------------------------------------ sổ đăng ký

def test_the_registry_never_lost_a_key_it_already_had():
    """Khoá đã duyệt thì không bao giờ biến mất khỏi tầng Closed.

    `_by_kind` là nửa ĐÓNG của từ vựng và có những khoá `kinds()` không in ra
    (`sidebar.label`, `entry.title` -- phôi cũ vẫn dùng). Một sổ chỉ đọc
    `kinds()` sẽ lặng lẽ hạ chúng xuống `semi_open`."""
    from rulebase import kie_glossary

    _, by_kind = kie_glossary.load()
    closed = FT.registry().closed[FT.KIND]
    missing = sorted(k for k in by_kind if k not in closed)
    assert not missing, f"khoá đã duyệt rơi khỏi sổ: {missing}"

    from synthgen.llm_page import kinds
    engine = sorted(k for k in kinds() if k not in closed)
    assert not engine, f"kind engine in ra mà sổ không biết: {engine}"


def test_every_closed_key_carries_a_sentence():
    """Tầng Closed hứa "câu tả tra từ sổ". Một khoá đóng không có câu tả là
    một lời hứa rỗng, và nó sẽ lặng lẽ thành `description: ""` trong bản ghi."""
    for space in FT.SPACES:
        bare = sorted(k for k, v in FT.registry().closed[space].items() if not v)
        assert not bare, f"khoá `{space}` chưa có câu tả: {bare[:10]}"


def test_the_decoder_enum_and_the_gate_accept_the_same_closed_names():
    """`enum` gửi cho model và cổng chữ phải nhận cùng một tập.

    Ba chỗ ép luật tên `data-kind` đã một lần lệch nhau và nó giết những trang
    làm đúng mọi điều được dặn (`acceptable_kind` sinh ra để dọn). `enum` là
    chỗ thứ tư; nó không được mở một cái tên mà cổng ngay sau đó loại."""
    from synthgen.llm_page import acceptable_kind, kinds

    known = kinds()
    for name in FT.closed_enum(FT.KIND):
        assert acceptable_kind(name, known), name


def test_marking_pairs_takes_the_stricter_of_role_and_path():
    """Một cặp KIE mang hai cái tên, và nó chỉ đáng tin bằng cái yếu hơn."""
    pairs = [
        {"role": "store.name", "path": "issuer.name"},        # đóng + đóng
        {"role": "store.name", "path": "vendor.name"},        # đóng + lạ
        {"role": "store.name"},                               # chỉ role
    ]
    counts = FT.mark_pairs(pairs, doc_type=OPEN_DOC)

    assert pairs[0]["tier"] == FT.CLOSED and pairs[0]["in_batch"] is True
    assert pairs[1]["tier"] == FT.STAGING and pairs[1]["in_batch"] is False
    assert pairs[2]["tier"] == FT.CLOSED and pairs[2]["in_batch"] is True
    assert counts["total"] == 3


def test_export_drops_held_pairs_but_keeps_the_rest():
    """Phễu duy nhất: `export.document()` bỏ cặp `in_batch: False`.

    Kiểm bằng chính hàm ấy chứ không bằng một bản sao logic, vì cái đáng hỏng
    là nó QUÊN đọc dấu, không phải dấu bị tính sai."""
    export = pytest.importorskip("synthgen.export")
    record = {
        "pages": [{"page_number": 1, "width_px": 1000, "height_px": 1000}],
        "entity_annotations": [{"entity_index": 2, "kind": "store.name"},
                               {"entity_index": 3, "kind": "patient.bed_number"}],
        "kie": {"pairs": [
            {"role": "store.name", "path": "issuer.name", "page_number": 1,
             "field": "issuer_name", "value_entity_index": 2,
             "key_text": "Đơn vị", "value_text": "Công ty A",
             "value_bbox": {"x1": 1, "y1": 1, "x2": 9, "y2": 9},
             "description": "Trading name.", "in_batch": True},
            {"role": "patient.bed_number", "page_number": 1,
             "field": "patient_bed_number", "value_entity_index": 3,
             "key_text": "Giường", "value_text": "B12",
             "value_bbox": {"x1": 1, "y1": 20, "x2": 9, "y2": 29},
             "description": "", "in_batch": False},
        ]},
    }
    out = export.document(record, "hop_dong_lao_dong")
    assert out.get("held_for_review") == 1
    printed = str(out)
    assert "Công ty A" in printed
    assert "B12" not in printed
