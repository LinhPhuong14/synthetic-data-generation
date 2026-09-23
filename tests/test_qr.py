"""Mã QR synthgen vẽ ra phải QUÉT ĐƯỢC, không chỉ trông giống mã QR.

Đây là phép kiểm mà bản trước -- một ô bàn cờ vẽ bằng `repeating-conic-gradient`
-- không thể qua nổi, và đó chính là lý do nó tồn tại: trên ảnh, một lưới ô
đen trắng đều tăm tắp trông y hệt một mã QR thật, nên không có phép kiểm này
thì không ai biết nhãn `data-graphic="qr"` đang nói dối.
"""
from __future__ import annotations

import random

import cv2
import numpy as np
import pytest

from synthgen import content as C
from synthgen import design as D
from synthgen import qr


def _scan(grid: list[list[bool]]) -> str:
    """Vẽ lưới ô ra ảnh rồi để OpenCV đọc lại -- đúng đường một máy quét đi."""
    art = np.array([[0 if cell else 255 for cell in row] for row in grid],
                   dtype=np.uint8)
    # Phóng to bằng NEAREST: một ô phải ra một khối vuông sắc cạnh, không phải
    # một vệt mờ. Và chừa vành trắng, nếu không bộ dò không thấy mép mã.
    big = cv2.resize(art, (art.shape[1] * 8, art.shape[0] * 8),
                     interpolation=cv2.INTER_NEAREST)
    big = cv2.copyMakeBorder(big, 32, 32, 32, 32, cv2.BORDER_CONSTANT, value=255)
    text, _points, _rectified = cv2.QRCodeDetector().detectAndDecode(big)
    return text


@pytest.mark.parametrize("payload", [
    "https://tracuu.chungtu.vn/tra-cuu/hoa_don_gtgt/0312845679/702-2026",
    "HD-2026-000123",
    "https://x.vn/a",
])
def test_the_matrix_decodes_back_to_what_went_in(payload):
    assert _scan(qr.matrix(payload)) == payload


def test_the_svg_draws_every_dark_module_and_nothing_else():
    """SVG gộp các ô đen liền nhau thành một `<rect>`; vệt mực phải không đổi."""
    grid = qr.matrix("https://tracuu.chungtu.vn/tra-cuu/thu")
    art = qr.svg(grid and "https://tracuu.chungtu.vn/tra-cuu/thu")
    size = len(grid) + qr.QUIET * 2
    assert f'viewBox="0 0 {size} {size}"' in art
    # Tổng bề rộng các hình chữ nhật phải bằng đúng số ô đen.
    import re
    drawn = sum(int(w) for w in re.findall(r'width="(\d+)" height="1"', art))
    assert drawn == sum(sum(1 for cell in row if cell) for row in grid)


def test_two_documents_do_not_get_the_same_code():
    """Ô bàn cờ cũ có ĐÚNG MỘT dáng cho cả bộ; mã thật đổi theo nội dung."""
    seen = set()
    for seed in (5, 41, 908, 1207):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        seen.add(qr.payload_for(doc, design))
    assert len(seen) == 4


def test_the_payload_repeats_what_is_printed_on_the_paper():
    """Quét mã ra một số hiệu khác số in trên giấy là lỗi đọc được bằng máy."""
    for seed in (41, 908, 1207):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        payload = qr.payload_for(doc, design)
        if doc.doc_no:
            assert doc.doc_no.strip().replace(" ", "") in payload
        for field, value in doc.fields or ():
            if field.key in ("seller_tax", "buyer_tax"):
                assert str(value).replace(" ", "") in payload
                break


def test_the_payload_stays_small_enough_to_scan_at_print_size():
    """Ô mã rộng 22mm. Nội dung dài ra thì số ô nhiều lên và mỗi ô nhỏ đi --
    dưới bốn pixel một ô thì máy TÌM THẤY mã mà không giải mã nổi, đo được
    trên một tờ vẽ thật. Ghim trần số ô để một thay đổi nội dung không lặng
    lẽ đưa mã xuống dưới ngưỡng ấy."""
    for seed in range(40):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x9E3779B9), 6)
        modules = len(qr.matrix(qr.payload_for(doc, design)))
        assert modules <= 29, f"seed {seed}: {modules} ô, quá nhỏ khi in 22mm"
