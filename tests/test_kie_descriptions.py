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


# ===========================================================================
# NGÔN NGỮ CỦA CÂU TẢ
#
# `synthgen/phrasing.py` giữ bốn cách nói cho mỗi câu gốc: hai Anh, hai Việt.
# Trộn CÁCH NÓI là chủ ý -- một câu lặp 7 920 lần dạy mô hình học thuộc câu
# chứ không học nghĩa. Trộn NGÔN NGỮ là trục khác, và trước 23-09-2026 không
# ai chọn nó: đo trên `data/thu1k`, 7,0% câu tả ra tiếng Anh, dồn vào vài
# nguồn (`implied` 69%, `llm` 53%, `rule` 100%) trong khi bốn nguồn dựng câu
# TỪ chữ in thì 0%. Bảy phần trăm là tỉ lệ tệ nhất cho cả hai đường.
# ===========================================================================


def test_the_pool_offers_both_languages_for_every_base_sentence():
    """Một câu gốc chỉ có một thứ tiếng thì `description_lang` không ép được
    nó, và nó lặng lẽ thành ngoại lệ trên cả bộ dữ liệu."""
    from synthgen.phrasing import language_of, pool

    one_sided = {base: sorted({language_of(c) for c in choices})
                 for base, choices in pool().items()
                 if len({language_of(c) for c in choices}) < 2}
    assert not one_sided, (
        f"{len(one_sided)} câu gốc chỉ có một thứ tiếng: "
        f"{list(one_sided)[:3]}")


def test_choosing_a_language_keeps_more_than_one_way_of_saying_it():
    """Ép ngôn ngữ mà chỉ còn một cách nói thì đổi một bệnh lấy bệnh kia:
    hết lẫn tiếng, nhưng cả bộ lại đọc lên như một cái máy."""
    from synthgen.phrasing import describe, language_of, pool

    for base in list(pool())[:40]:
        for lang in ("vi", "en"):
            said = {describe(base, seed, "x", ordinal=seed, lang=lang)
                    for seed in range(12)}
            assert {language_of(s) for s in said} == {lang}, base
            assert len(said) > 1, f"{base} / {lang}: chỉ một cách nói"


GLUED = (
    ("Tax identification number of the seller: “0312345678”.",
     "Tax identification number of the seller.", ": ", "“0312345678”."),
    ("Answer ticked for the question printed beside it — “Có”.",
     "Answer ticked for the question printed beside it.", " — ", "“Có”."),
    ("Value printed on the sheet beside the caption “1. Thời hạn”.",
     "Value printed on the sheet beside the caption.", " ", "“1. Thời hạn”."),
)


def test_a_sentence_with_the_printed_text_glued_on_still_gets_a_voice():
    """`kie_full` dựng câu tả bằng câu gốc + chữ in dán vào đuôi. Chuỗi ghép
    ấy không khớp kho, nên trước bản sửa nó đi thẳng qua `describe()` không
    đổi: giữ tiếng Anh, giữ một cách nói duy nhất. Đo trên `data/thu1k`: 416
    câu tiếng Anh còn lại thuộc ĐÚNG 12 mẫu, và 11 trong 12 là câu gốc CÓ
    trong kho cộng một cái đuôi."""
    from synthgen.phrasing import _split_quoted, describe, language_of

    for whole, head, sep, tail in GLUED:
        assert _split_quoted(whole) == (head, sep, tail), whole
        said = describe(whole, 7, "x", ordinal=3, lang="vi")
        assert language_of(said.split("“")[0]) == "vi", said
        assert said.endswith(tail), f"mất phần trích: {said}"


def test_a_plain_sentence_is_not_mistaken_for_a_glued_one():
    """Phép tách chỉ được chạy khi câu KHÔNG có trong kho. Một câu gốc kết
    thúc bằng dấu ngoặc kép vẫn phải đi đường thường."""
    from synthgen.phrasing import _split_quoted

    assert _split_quoted("Motto line printed under the national heading.") == ("", "", "")
    assert _split_quoted("") == ("", "", "")


# ===========================================================================
# NHÁNH LÙI CỦA `implied_for` — nơi 658/666 câu tiếng Anh sinh ra
# ===========================================================================


def test_a_generated_description_is_never_english():
    """`implied_for` chế câu cho MỌI `kind` không có trong `IMPLIED`, và câu
    nó chế không bao giờ khớp kho cách nói (mỗi `kind` một câu riêng). Nên
    `description_lang` không với tới được nó: nó đi thẳng ra bộ dữ liệu đúng
    như được viết.

    Đo trên `data/23-09-llm-g`: 66,6% câu tả ra tiếng Anh, và 658 trên 666
    câu ấy đến từ đúng nhánh này."""
    from synthgen.kie_full import IMPLIED, NEVER, implied_for
    from synthgen.llm_page import kinds
    from synthgen.phrasing import language_of

    english = {}
    for kind in sorted(kinds()):
        if kind in IMPLIED or kind in NEVER or kind.startswith("menu."):
            continue
        got = implied_for(kind)
        if got and language_of(got[1]) == "en":
            english[kind] = got[1]
    assert not english, f"{len(english)} kind ra câu tiếng Anh: {list(english)[:4]}"


def test_the_vietnamese_glossary_covers_every_token_the_engine_emits():
    """Token lạ giữ nguyên tiếng Anh -- câu vẫn đọc được, chỉ lẫn một chữ.
    Nhưng một token của CHÍNH engine mà thiếu thì là lỗ hổng biết trước."""
    import re

    from synthgen.kie_full import _WORDS_VI
    from synthgen.llm_page import kinds

    missing = {w for kind in kinds() for w in re.split(r"[._]+", kind)
               if w and w not in _WORDS_VI}
    assert not missing, f"thiếu token: {sorted(missing)}"


def test_a_compound_name_reads_head_first_the_way_vietnamese_does():
    """`kind` viết theo lối Anh (`legal.basis` = "legal" bổ nghĩa "basis").
    Dịch xuôi ra "Pháp lý căn cứ" -- đúng chữ, sai tiếng."""
    from synthgen.kie_full import implied_for

    assert implied_for("legal.basis")[1].startswith("Căn cứ pháp lý")
    assert implied_for("clause.head")[1].startswith("Tiêu đề điều khoản")
    assert implied_for("store.address")[1].startswith("Địa chỉ đơn vị")


def test_only_label_marks_a_printed_caption_not_title():
    """`.label` là caption của trường kia -- `page.md` mục 9. `.title` thì
    KHÔNG: `sign.title` là CHỨC DANH người ký. Một hậu tố nhập nhằng không
    được làm luật."""
    from synthgen.kie_full import implied_for

    assert implied_for("store.tax_code.label")[1].startswith("Nhãn in của")
    assert not implied_for("sign.title")[1].startswith("Nhãn in của")
    assert "Chức danh" in implied_for("sign.title")[1]
