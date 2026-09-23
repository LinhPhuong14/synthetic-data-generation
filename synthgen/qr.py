"""Mã QR THẬT, quét được -- không phải một ô caro vẽ bằng CSS.

    from synthgen import qr
    svg = qr.svg(qr.payload_for(doc, design))

## Vì sao có file này

`markup.py` trước đây vẽ mã QR bằng `repeating-conic-gradient`: một lưới ô đen
trắng đều tăm tắp, đúng cỡ, đúng chỗ, và không máy nào đọc được. Với một bộ
dữ liệu OCR thì đó là một cái nhãn nói dối -- vùng ấy được gắn `data-graphic`
và một mô hình học trên đó học rằng "mã QR" nghĩa là "một ô bàn cờ", trong khi
mã QR thật có ba ô định vị ở ba góc, một ô căn chỉnh, vành định thì, và một
mặt nạ làm lưới KHÔNG đều. Ba dấu hiệu ấy chính là thứ một bộ dò tìm.

Và ô caro chỉ có ĐÚNG MỘT dáng cho cả bộ dữ liệu: cùng bước ô, cùng tỉ lệ đen
trắng, cùng mọi thứ. Mã thật đổi theo nội dung -- số hiệu khác thì lưới khác,
nội dung dài hơn thì phiên bản lớn hơn và số ô nhiều hơn.

## Không thêm phụ thuộc

`cv2.QRCodeEncoder` có sẵn trong OpenCV mà kho này đã bắt buộc. Và `cv2`
cũng có `QRCodeDetector`, nên `tests/` KIỂM ĐƯỢC rằng cái vẽ ra thật sự quét
được -- một phép kiểm mà bản CSS không thể qua nổi.

## SVG chứ không PNG

Cùng lẽ `textures/figure/*.svg`: nét phải sắc ở mọi khổ giấy mà `paginate.py`
leo tới, và màu đi theo bảng màu của trang qua `currentColor` thay vì bị nung
vào pixel. Một mã QR in bằng mực xanh trên giấy ngả vàng vẫn quét được -- máy
đọc tương phản, không đọc màu.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Vành trắng quanh mã, tính bằng SỐ Ô. Bốn là mức chuẩn ISO/IEC 18004 đòi, và
# dưới mức ấy nhiều máy đọc bỏ cuộc -- vành trắng là thứ cho bộ dò biết đâu là
# mép mã.
QUIET = 4


def matrix(text: str) -> list[list[bool]]:
    """Lưới ô của mã QR cho `text`. `True` là ô ĐEN.

    Ném nếu không mã hoá được: một mã QR vẽ hỏng trông y hệt một mã vẽ đúng
    trên ảnh, nên hỏng lặng lẽ ở đây là thứ không ai phát hiện ra cho tới lúc
    cầm máy quét thử một bộ hai mươi nghìn ảnh.
    """
    import cv2  # noqa: PLC0415 -- chỉ cần khi tờ giấy có mã

    art = cv2.QRCodeEncoder.create().encode(str(text))
    if art is None or getattr(art, "size", 0) == 0:
        raise ValueError(f"không mã hoá được QR cho {text!r}")
    # `encode` trả 0 cho ô đen, 255 cho ô trắng.
    return [[bool(value == 0) for value in row] for row in art.tolist()]


def svg(text: str, *, quiet: int = QUIET) -> str:
    """Mã QR của `text`, dạng SVG nội tuyến.

    Mỗi HÀNG gộp thành một `<rect>` liền khi các ô đen liền nhau, thay vì một
    `<rect>` cho mỗi ô. Một mã phiên bản 4 là 33x33 = 1089 ô; gộp hàng đưa nó
    xuống vài trăm hình chữ nhật, và cả trang HTML nhẹ đi tương ứng. Hình vẽ
    ra không đổi một pixel nào -- hai ô đen cạnh nhau và một hình chữ nhật dài
    gấp đôi là cùng một vệt mực.
    """
    grid = matrix(text)
    size = len(grid) + quiet * 2
    parts = []
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            if not row[x]:
                x += 1
                continue
            run = x
            while run < len(row) and row[run]:
                run += 1
            parts.append(f'<rect x="{x + quiet}" y="{y + quiet}" '
                         f'width="{run - x}" height="1"/>')
            x = run
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'shape-rendering="crispEdges" fill="currentColor">'
            f'{"".join(parts)}</svg>')


def payload_for(doc, design) -> str:
    """Nội dung mã QR của MỘT tờ giấy -- lấy từ chính tờ giấy ấy.

    Không phải chuỗi ngẫu nhiên. Mã QR trên chứng từ Việt Nam thật trỏ tới một
    trang tra cứu, và phần định danh trong đường dẫn là số hiệu chứng từ cộng
    mã số thuế bên phát hành -- đúng hai thứ đã in trên giấy. Nên nội dung mã
    KIỂM CHÉO được với chữ in: quét mã ra một số hiệu khác số in trên giấy là
    một lỗi đọc được bằng máy.

    Đó cũng là lý do hàm này ở đây chứ không ở `markup.py`: nó cần biết tờ
    giấy NÓI GÌ, và `markup.py` chỉ biết tờ giấy trông ra sao.
    """
    serial = (getattr(doc, "doc_no", "") or "").strip() or str(getattr(doc, "seed", ""))
    tax = ""
    for field, value in getattr(doc, "fields", ()) or ():
        if getattr(field, "key", "") in ("seller_tax", "buyer_tax"):
            tax = str(value).replace(" ", "")
            break
    # NGẮN, và đó là một ràng buộc VẬT LÝ chứ không phải sở thích.
    #
    # Ô mã trên giấy rộng 22mm. Ở độ phân giải bộ này vẽ ra, 22mm là khoảng
    # 140 pixel, nên số ô của mã quyết định mỗi ô được mấy pixel -- và dưới
    # khoảng 4 pixel một ô thì `cv2.QRCodeDetector` TÌM THẤY mã mà không giải
    # mã nổi. Đo trên một tờ vẽ thật: một URL 59 ký tự ra lưới 37 ô, 3.8
    # pixel một ô, và quét ra chuỗi rỗng.
    #
    # Một mã tra cứu "mã số thuế - số hiệu" là 19 ký tự, ra lưới 25 ô và 5.6
    # pixel một ô -- quét được. Và đó cũng đúng thứ chứng từ Việt Nam in: mã
    # để nhập vào trang tra cứu, không phải cả đường dẫn.
    parts = [p for p in (tax, serial.replace(" ", "")) if p]
    return "-".join(parts) or str(getattr(doc, "seed", "0"))


__all__ = ["QUIET", "matrix", "payload_for", "svg"]
