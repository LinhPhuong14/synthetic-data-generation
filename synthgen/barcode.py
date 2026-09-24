"""Mã vạch THẬT, quét được -- không phải mấy vạch kẻ bằng CSS.

    from synthgen import barcode
    svg = barcode.svg(barcode.payload_for(doc))

## Vì sao có file này

`markup.py` vẽ ô `.barcode` bằng `repeating-linear-gradient`: bốn vạch lặp
đúng một chu kỳ, rộng hẹp theo `seed % 22 + 38` milimét, và không máy nào đọc
được. Đúng lời nói dối mà `synthgen/qr.py` được viết ra để xoá, chỉ khác chỗ
nó sống sót thêm một vòng: vùng ấy được gắn `data-graphic="barcode"`, bên dưới
in một số hiệu thật, nên một model học trên bộ này học rằng "mã vạch" nghĩa là
"vạch đều tăm tắp" và rằng dãy vạch KHÔNG liên quan gì tới con số dưới nó.

Ô caro QR có đúng một dáng cho cả bộ; ô vạch này cũng vậy -- chỉ bề rộng ô
thay đổi, còn chu kỳ vạch thì không.

## Vì sao EAN-13, và PHÉP KIỂM YẾU HƠN QR ở chỗ nào

EAN-13 vì nó là chuẩn có bảng mẫu vạch CÔNG KHAI và cố định, nên
`tests/test_barcode.py` giải mã lại được bằng chính ba bảng L/G/R -- một phép
kiểm vòng tròn thật sự cho BỘ MÃ HOÁ: sai bảng chẵn lẻ, sai vạch bảo vệ, sai
chữ số kiểm, lệch số mô-đun, tất cả đều kêu.

Nhưng nói thẳng chỗ nó YẾU HƠN `qr.py`: `cv2.QRCodeDetector` giải mã được ảnh
QR nên `tests/test_qr.py` quét đúng đường một máy quét đi. `cv2.barcode` thì
KHÔNG dùng được -- đo trên cv2 4.14 của kho này, `BarcodeDetector.detect()`
trả `False` ngay cả với một mã EAN-13 sạch, cao 200 pixel, sáu pixel một
mô-đun, vành trắng đủ chuẩn; thư mục `cv2/` không có dữ liệu mô hình nào cho
nó. Nên ở đây KHÔNG có phép kiểm "ảnh vẽ ra quét được", chỉ có "dãy bit đúng
chuẩn".

Chỗ hở còn lại là VẬT LÝ: một mã đúng chuẩn mà in quá nhỏ thì máy vẫn không
đọc nổi. Ghim nó bằng bề rộng mô-đun tính ra milimét, cùng lối `qr.py` ghim
trần số ô -- xem `MIN_MODULE_MM` và phép kiểm của nó.

Chứng từ Việt Nam in cả EAN-13 lẫn Code 128; EAN-13 là mã trên mọi vỏ hộp
hàng hoá, nên không phải lựa chọn sai về thực tế.

## SVG chứ không PNG

Cùng lẽ `qr.py`: nét sắc ở mọi khổ giấy, và màu bám mực trang qua
`currentColor` thay vì bị nung vào pixel.
"""
from __future__ import annotations

# Bảng mẫu vạch EAN-13. Mỗi chữ số là bảy mô-đun; ba bộ mã, và bộ nào dùng cho
# chữ số nào do chữ số ĐẦU quyết định -- đó là cách EAN-13 chở mười ba chữ số
# trong chỗ chỉ đủ cho mười hai.
_L = ("0001101", "0011001", "0010011", "0111101", "0100011",
      "0110001", "0101111", "0111011", "0110111", "0001011")
_G = ("0100111", "0110011", "0011011", "0100001", "0011101",
      "0111001", "0000101", "0010001", "0001001", "0010111")
_R = ("1110010", "1100110", "1101100", "1000010", "1011100",
      "1001110", "1010000", "1000100", "1001000", "1110100")
# Chữ số đầu chọn L hay G cho sáu chữ số nhóm trái.
_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
           "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")
# Vành trắng quanh mã, tính bằng SỐ MÔ-ĐUN. EAN-13 đòi chín mô-đun mỗi bên;
# thiếu nó thì bộ dò không thấy mép mã.
QUIET = 9
# Tổng mô-đun của một mã EAN-13: 3 (bảo vệ trái) + 6x7 + 5 (giữa) + 6x7 + 3.
MODULES = 95

# Bề rộng MỘT MÔ-ĐUN tối thiểu, tính bằng milimét trên giấy.
#
# Đây là chỗ hở mà phép kiểm dãy bit không bịt được: mã đúng chuẩn mà in quá
# nhỏ thì máy quét vẫn bỏ. Chuẩn EAN đòi 0.264mm ở cỡ danh định và cho thu nhỏ
# tới 80%, tức 0.211mm. Ô `.barcode` của `markup.py` rộng `seed % 22 + 38`
# milimét, tức 38-59mm, và 95 mô-đun cộng 18 mô-đun vành trắng là 113 mô-đun:
# hẹp nhất là 38/113 = 0.336mm một mô-đun, vẫn trên ngưỡng.
#
# Ghim con số ấy lại để một lần đổi bề rộng ô không lặng lẽ đưa mã xuống dưới
# ngưỡng in được -- cùng lối `qr.py` ghim trần số ô.
MIN_MODULE_MM = 0.211


def check_digit(twelve: str) -> int:
    """Chữ số kiểm của mười hai chữ số đầu.

    Ném nếu không đúng mười hai chữ số: một mã sai chữ số kiểm vẫn vẽ ra được
    và vẫn trông như mã thật, nhưng máy quét từ chối nó -- tức lại đúng lời nói
    dối cũ, chỉ tinh vi hơn.
    """
    if len(twelve) != 12 or not twelve.isdigit():
        raise ValueError(f"EAN-13 cần đúng 12 chữ số, nhận {twelve!r}")
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(twelve))
    return (10 - total % 10) % 10


def modules(code: str) -> list[bool]:
    """Dãy mô-đun của mã. `True` là vạch ĐEN.

    `code` là 12 hoặc 13 chữ số; 12 thì chữ số kiểm được thêm vào, 13 thì chữ
    số cuối được KIỂM LẠI chứ không tin.
    """
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) == 12:
        digits += str(check_digit(digits))
    if len(digits) != 13:
        raise ValueError(f"EAN-13 cần 12 hoặc 13 chữ số, nhận {code!r}")
    if int(digits[12]) != check_digit(digits[:12]):
        raise ValueError(f"chữ số kiểm sai: {digits!r}")
    parity = _PARITY[int(digits[0])]
    bits = "101"                                     # bảo vệ trái
    for i, ch in enumerate(digits[1:7]):
        bits += (_L if parity[i] == "L" else _G)[int(ch)]
    bits += "01010"                                  # bảo vệ giữa
    for ch in digits[7:]:
        bits += _R[int(ch)]
    bits += "101"                                    # bảo vệ phải
    out = [c == "1" for c in bits]
    if len(out) != MODULES:
        raise ValueError(f"dựng ra {len(out)} mô-đun, phải là {MODULES}")
    return out


def svg(code: str, *, quiet: int = QUIET, height: int = 60) -> str:
    """Mã vạch của `code`, dạng SVG nội tuyến.

    Các mô-đun đen liền nhau gộp thành MỘT `<rect>`, cùng lẽ `qr.svg`: hình vẽ
    ra không đổi một pixel, mà số hình chữ nhật giảm từ chín mươi lăm xuống
    khoảng ba mươi.
    """
    bits = modules(code)
    width = len(bits) + quiet * 2
    parts = []
    x = 0
    while x < len(bits):
        if not bits[x]:
            x += 1
            continue
        run = x
        while run < len(bits) and bits[run]:
            run += 1
        parts.append(f'<rect x="{x + quiet}" y="0" '
                     f'width="{run - x}" height="{height}"/>')
        x = run
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            f'shape-rendering="crispEdges" fill="currentColor">'
            f'{"".join(parts)}</svg>')


def payload_for(doc) -> str:
    """Mười ba chữ số cho MỘT tờ giấy, lấy từ chính tờ giấy ấy.

    Cùng lẽ `qr.payload_for`: mã phải KIỂM CHÉO được với chữ in. Lấy các chữ số
    của số hiệu chứng từ, rồi đệm bằng `seed` cho đủ mười hai -- nên quét mã ra
    một số hiệu khác số in trên giấy là một lỗi đọc được bằng máy.

    EAN-13 chỉ chở chữ số, nên phần chữ của số hiệu ("941/2024/HĐ") rụng lại và
    chỉ còn "9412024". Đó là giới hạn của chuẩn, không phải của phép lấy: chữ
    số còn lại vẫn đủ nối mã với tờ giấy.
    """
    serial = "".join(ch for ch in str(getattr(doc, "doc_no", "") or "")
                     if ch.isdigit())
    seed = "".join(ch for ch in str(getattr(doc, "seed", 0)) if ch.isdigit())
    digits = (serial + seed).ljust(12, "0")[:12]
    return digits + str(check_digit(digits))


__all__ = ["MODULES", "QUIET", "check_digit", "modules", "payload_for", "svg"]
