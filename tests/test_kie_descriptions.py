"""Câu tả KIE phải nói đúng loại giấy nó đang tả.

Bản trước dựng ĐÚNG MỘT bảng rồi gán cho cả 99 phôi. `put` dùng `setdefault`,
tức ai viết trước thắng, và vòng `field_pool` chạy trước `FIXED`, nên
`design.py::seller_addr` chiếm slug `dia_chi` cho mọi phôi — kể cả công văn và
quyết định bổ nhiệm, những tờ không có bên bán nào.

Đo trên `data/09-09-26-synthetics-document`, 6.456 cặp KIE của 14 loại giấy
phi thương mại: **2.340 cặp (36,2%)** mang câu tả nói "seller"/"invoice"/
"goods". Tra cùng ngần ấy cặp qua bảng mới: **53 (0,8%)**.

Không file nào ở đây vẽ ảnh hay gọi model — `tables()` đọc `design.ARCHETYPES`
và `build_page` chạy trên list dict, nên bộ này chạy được trong CI không có
thư viện, giống `test_kie.py`.
"""

from __future__ import annotations

import json
import re

import pytest

from pipeline import kie
from synthgen import descriptions

# Từ chỉ vai THƯƠNG MẠI. Một tờ công văn không có bên bán, bên mua, hàng hoá
# nào, nên câu tả cho trường của nó không được dùng những chữ này.
COMMERCE = re.compile(r"\b(seller|buyer|sold|purchase)\b", re.I)

# Phôi không phải chứng từ mua bán, lấy đúng 14 cái đã đo được 36,2% ở trên.
NON_COMMERCIAL = (
    "cong_van", "to_trinh", "bien_ban_hop", "bien_ban_ban_giao",
    "don_xin_nghi_phep", "giay_uy_quyen", "giay_gioi_thieu", "don_dang_ky",
    "phieu_khao_sat", "giay_ra_vien", "don_thuoc", "danh_sach_hoc_vien",
    "bang_cham_cong", "bang_luong",
)


@pytest.fixture(scope="module")
def built():
    return descriptions.tables()


def text_of(entry):
    """Câu tả của một mục, dù mục ấy là chuỗi hay `{description, guidelines}`."""
    return entry if isinstance(entry, str) else entry["description"]


# ------------------------------------------------- bảng theo phôi, không dùng chung


def test_each_archetype_gets_its_own_table(built):
    """Hai phôi khác nhau phải là hai bảng khác nhau, không phải một tham
    chiếu chung — chính cái chung ấy là lỗi."""
    assert len(built) > 50
    assert built["cong_van"] is not built["hoa_don_gtgt"]
    assert built["cong_van"] != built["hoa_don_gtgt"]


@pytest.mark.parametrize("archetype", NON_COMMERCIAL)
def test_no_commercial_role_on_a_non_commercial_document(built, archetype):
    """`dia_chi` trên công văn từng là "Registered address of the seller."."""
    table = built[archetype]
    guilty = {field: text_of(entry) for field, entry in table.items()
              if COMMERCE.search(text_of(entry))}
    assert guilty == {}, (
        f"{archetype} không có bên bán/bên mua nào, nhưng {len(guilty)} trường "
        f"vẫn tả bằng vai thương mại: {sorted(guilty)[:5]}")


def test_the_address_on_an_administrative_sheet_names_the_issuer(built):
    said = text_of(built["cong_van"]["dia_chi"])
    assert "seller" not in said.lower()
    assert "issued" in said.lower() or "issuing" in said.lower()


# --------------------------------------------------------- nhãn bị hai vai đòi


def test_a_contested_caption_is_neutral_and_carries_guidelines(built):
    """"Địa chỉ" trên hoá đơn là của CẢ bên bán lẫn bên mua. Ở đó không đoán:
    lấy câu trung tính, và nói cách phân biệt trong `guidelines`."""
    entry = built["hoa_don_gtgt"]["dia_chi"]
    assert isinstance(entry, dict), "nhãn bị tranh phải mang cả chỉ dẫn"
    assert set(entry) == {"description", "guidelines"}
    assert not COMMERCE.search(entry["description"])
    # Chỉ dẫn phải nói CẢ HAI vai, và nói hậu tố nào là lần in nào.
    assert "seller" in entry["guidelines"].lower()
    assert "buyer" in entry["guidelines"].lower()
    assert "dia_chi_2" in entry["guidelines"]


def test_an_uncontested_caption_stays_a_plain_string(built):
    """99,2% số cặp (phôi, slug) chỉ có một vai đòi. Chúng không cần chỉ dẫn,
    và khoá `guidelines` vắng mặt chứ không rỗng — để người đọc phân biệt
    "không cần chỉ dẫn" với "chỉ dẫn không nói gì"."""
    assert isinstance(built["cong_van"]["dia_chi"], str)


def test_contested_captions_are_rare(built):
    """Nếu con số này vọt lên thì `design.py` đã đặt trùng nhãn ở đâu đó —
    đo được lúc viết: 13 nhãn trên 9 phôi."""
    contested = sum(1 for table in built.values()
                    for entry in table.values() if isinstance(entry, dict))
    # 13 nhãn × 6 hậu tố = 78.
    assert contested <= 120, f"{contested} mục bị tranh, lúc viết là 78"


# ------------------------------------------------------- nền dùng chung phải trung tính


def test_the_shared_base_is_true_on_any_document_type():
    """`_shared()` phủ cả 99 phôi, nên câu của nó phải đúng ở mọi nơi caption
    ấy in ra được. "Ký hiệu" là chữ hành chính phổ thông — giấy ra viện cũng
    in — nên nó từng nhận "Invoice symbol..." trên 103 cặp của `giay_ra_vien`."""
    said = descriptions.table()["ky_hieu"]
    assert "invoice" not in said.lower()


# --------------------------------------------- phía ĐỌC: pipeline/kie.py


def test_describe_reads_the_object_form(monkeypatch, tmp_path):
    """Dạng dict từng rơi thẳng qua cổng `isinstance(..., str)` rồi đáp xuống
    câu dựng từ caption — giá trị có đó mà không ai đọc."""
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({
        "hoa_don_gtgt": {"dia_chi": {"description": "Address of a party.",
                                     "guidelines": "Two parties print this."}},
    }), encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    said, source = kie.describe("dia_chi", caption="Địa chỉ:",
                                layout="hoa_don_gtgt")
    assert said == "Address of a party."
    assert source == "llm"
    assert kie.guidelines_for("dia_chi", "hoa_don_gtgt") == "Two parties print this."


def test_guidelines_are_empty_for_a_plain_description(monkeypatch, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({"cong_van": {"dia_chi": "Address of the issuer."}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    assert kie.describe("dia_chi", layout="cong_van")[0] == "Address of the issuer."
    assert kie.guidelines_for("dia_chi", "cong_van") == ""


def test_an_unknown_key_in_the_ledger_shouts(monkeypatch, tmp_path):
    """Luật 6 của AGENTS.md. Một khoá lạ nghĩa là ai đó đã ghi thứ mà phía đọc
    không biết đọc; bỏ qua nó là cách chắc chắn phát hiện sau hai mươi nghìn
    tờ."""
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({"cong_van": {"dia_chi": {"description": "x",
                                                         "note": "y"}}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    with pytest.raises(ValueError, match="unknown"):
        kie.describe("dia_chi", layout="cong_van")


def test_a_wrong_type_in_the_ledger_shouts(monkeypatch, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({"cong_van": {"dia_chi": ["a", "b"]}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    with pytest.raises(TypeError, match="expected a string"):
        kie.describe("dia_chi", layout="cong_van")


def test_build_page_carries_guidelines_onto_the_pair(monkeypatch, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({
        "hoa_don_gtgt": {"dia_chi": {"description": "Address of a party.",
                                     "guidelines": "First printing is the seller."}},
    }), encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    blocks = [
        {"kind": "store.address.label", "text": "Địa chỉ:",
         "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}},
        {"kind": "store.address", "text": "Số 1 Lê Lợi",
         "bbox": {"x1": 12, "y1": 0, "x2": 40, "y2": 10}},
    ]
    page = kie.build_page(blocks, layout="hoa_don_gtgt")
    pair = next(p for p in page["pairs"] if p["field"] == "dia_chi")
    assert pair["guidelines"] == "First printing is the seller."
    assert page["schema"]["properties"]["dia_chi"]["guidelines"] == \
        "First printing is the seller."


def test_a_pair_without_guidelines_has_no_such_key(monkeypatch, tmp_path):
    path = tmp_path / "desc.json"
    path.write_text(json.dumps({"cong_van": {"dia_chi": "Address of the issuer."}}),
                    encoding="utf-8")
    monkeypatch.setenv(kie.DESCRIPTIONS_ENV, str(path))
    kie._all_descriptions.cache_clear()

    blocks = [
        {"kind": "store.address.label", "text": "Địa chỉ:",
         "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}},
        {"kind": "store.address", "text": "Số 1 Lê Lợi",
         "bbox": {"x1": 12, "y1": 0, "x2": 40, "y2": 10}},
    ]
    page = kie.build_page(blocks, layout="cong_van")
    pair = next(p for p in page["pairs"] if p["field"] == "dia_chi")
    assert "guidelines" not in pair
