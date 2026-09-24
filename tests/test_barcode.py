"""Mã vạch synthgen vẽ ra phải là EAN-13 ĐÚNG CHUẨN, không phải mấy vạch kẻ.

Cùng lý do `tests/test_qr.py` tồn tại: trên ảnh, một dãy vạch đều tăm tắp
trông y hệt một mã vạch thật, nên không có phép kiểm này thì không ai biết
nhãn `data-graphic="barcode"` đang nói dối. Bản trước ô `.barcode` là bốn vạch
lặp bằng `repeating-linear-gradient` -- một dáng duy nhất cho cả bộ, không mã
hoá gì.

PHÉP KIỂM Ở ĐÂY YẾU HƠN `test_qr.py`, và phải nói rõ: `cv2.QRCodeDetector`
giải mã được ảnh QR nên bên ấy quét đúng đường máy quét đi. `cv2.barcode` thì
không dùng được -- đo trên cv2 4.14 của kho này, `BarcodeDetector.detect()`
trả `False` ngay cả với mã EAN-13 sạch, cao 200 pixel, sáu pixel một mô-đun,
vành trắng đủ chuẩn, và thư mục `cv2/` không có dữ liệu mô hình nào cho nó.

Nên thay vì quét ảnh, ở đây GIẢI MÃ LẠI dãy mô-đun bằng chính ba bảng L/G/R
của chuẩn, viết độc lập với bộ mã hoá. Nó bắt đúng những lỗi đáng bắt: sai
bảng chẵn lẻ, sai vạch bảo vệ, sai chữ số kiểm, lệch số mô-đun. Nó KHÔNG bắt
được "in quá nhỏ nên máy không đọc nổi" -- chỗ ấy do
`test_the_bars_stay_wide_enough_to_scan_on_paper` ghim bằng milimét.
"""
from __future__ import annotations

import random
import re

import pytest

from synthgen import barcode
from synthgen import content as C
from synthgen import design as D

# Ba bảng của chuẩn, VIẾT LẠI ở đây chứ không nhập từ `barcode.py`. Nhập lại
# bảng của bộ mã hoá thì phép kiểm chỉ chứng minh "bộ mã hoá đồng ý với chính
# nó" -- một bảng gõ sai vẫn qua.
L = ("0001101", "0011001", "0010011", "0111101", "0100011",
     "0110001", "0101111", "0111011", "0110111", "0001011")
G = ("0100111", "0110011", "0011011", "0100001", "0011101",
     "0111001", "0000101", "0010001", "0001001", "0010111")
R = ("1110010", "1100110", "1101100", "1000010", "1011100",
     "1001110", "1010000", "1000100", "1001000", "1110100")
PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
          "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


def _decode(bits: list[bool]) -> str:
    """Đọc dãy mô-đun ra mười ba chữ số. Ném khi dãy không hợp chuẩn."""
    s = "".join("1" if b else "0" for b in bits)
    assert len(s) == 95, f"{len(s)} mô-đun, phải 95"
    assert s[:3] == "101", "thiếu vạch bảo vệ trái"
    assert s[45:50] == "01010", "thiếu vạch bảo vệ giữa"
    assert s[92:] == "101", "thiếu vạch bảo vệ phải"
    left = [s[3 + i * 7: 10 + i * 7] for i in range(6)]
    right = [s[50 + i * 7: 57 + i * 7] for i in range(6)]
    # Nhóm trái: mỗi ô là L hay G, và CHUỖI L/G ấy mã hoá chữ số đầu.
    shape, digits = "", ""
    for group in left:
        if group in L:
            shape += "L"
            digits += str(L.index(group))
        elif group in G:
            shape += "G"
            digits += str(G.index(group))
        else:
            raise AssertionError(f"nhóm trái không thuộc L hay G: {group}")
    assert shape in PARITY, f"chuỗi chẵn lẻ {shape} không có trong bảng"
    first = str(PARITY.index(shape))
    for group in right:
        assert group in R, f"nhóm phải không thuộc R: {group}"
        digits += str(R.index(group))
    return first + digits


@pytest.mark.parametrize("code", [
    "5901234123457",   # vector chuẩn của EAN-13
    "8934567890120",   # tiền tố 893 -- mã quốc gia Việt Nam
    "9412024202604",
])
def test_the_modules_decode_back_to_what_went_in(code):
    assert _decode(barcode.modules(code)) == code


def test_the_check_digit_matches_the_standard():
    """Chữ số kiểm sai thì máy quét từ chối, mà mắt người không thấy gì lạ."""
    assert barcode.check_digit("590123412345") == 7
    assert barcode.check_digit("978030640615") == 7
    assert barcode.check_digit("893456789012") == 0


def test_a_wrong_check_digit_is_refused_not_drawn():
    """Ném chứ không vẽ: một mã sai vẫn trông như mã thật trên ảnh."""
    with pytest.raises(ValueError):
        barcode.modules("8934567890121")
    with pytest.raises(ValueError):
        barcode.check_digit("12345")
    with pytest.raises(ValueError):
        barcode.modules("89345")


def test_twelve_digits_get_their_check_digit_added():
    """Khai mười hai chữ số thì bộ mã hoá tự thêm chữ số thứ mười ba."""
    assert _decode(barcode.modules("590123412345")) == "5901234123457"


def test_every_document_code_is_a_valid_ean13():
    for seed in range(40):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        code = barcode.payload_for(doc)
        assert _decode(barcode.modules(code)) == code


def test_the_svg_draws_every_dark_module_and_nothing_else():
    """SVG gộp các mô-đun đen liền nhau; vệt mực phải không đổi."""
    code = "8934567890120"
    bits = barcode.modules(code)
    art = barcode.svg(code)
    assert f'viewBox="0 0 {len(bits) + barcode.QUIET * 2} 60"' in art
    drawn = sum(int(w) for w in re.findall(r'width="(\d+)" height="60"', art))
    assert drawn == sum(1 for b in bits if b)


def test_two_documents_do_not_get_the_same_bars():
    """Dãy vạch cũ có ĐÚNG MỘT chu kỳ cho cả bộ; mã thật đổi theo nội dung."""
    seen = set()
    for seed in (5, 41, 908, 1207):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        seen.add(barcode.payload_for(doc))
    assert len(seen) == 4


def test_the_payload_repeats_digits_printed_on_the_paper():
    """Quét mã ra số không có trên giấy là lỗi đọc được bằng máy."""
    for seed in (41, 908, 1207):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        serial = "".join(ch for ch in str(doc.doc_no or "") if ch.isdigit())
        if serial:
            assert barcode.payload_for(doc).startswith(serial[:12])


def test_the_bars_stay_wide_enough_to_scan_on_paper():
    """Chỗ mà phép giải mã dãy bit KHÔNG bịt được: mã đúng chuẩn in quá nhỏ.

    Ô `.barcode` của `markup.py` rộng `d.seed % 22 + 38` milimét, và cả mã kể
    cả vành trắng là 95 + 2x9 = 113 mô-đun."""
    total = barcode.MODULES + barcode.QUIET * 2
    for narrowest_mm in (38, 59):
        assert narrowest_mm / total >= barcode.MIN_MODULE_MM, (
            f"ô rộng {narrowest_mm}mm ra {narrowest_mm / total:.3f}mm một "
            f"mô-đun, dưới ngưỡng {barcode.MIN_MODULE_MM}mm")
