"""Vùng ĐỆM của một lát cắt phải cùng màu với GIẤY của tờ ấy.

## Vì sao file này tồn tại

`to_a4` đệm phần thiếu chiều cao, `_pad_top` đệm lề trên của tờ thứ hai trở
đi. Cả hai tô một màu phẳng, và màu ấy phải là **màu giấy**. Khi nó không
phải màu giấy, kết quả không phải một ngoại lệ -- nó là một tấm ảnh ghi
được, mở được, có đủ nhãn, và có một DẢI XÁM vắt ngang tờ giấy.

Đo trên 111 tờ tiếp (`*_p[0-9].jpg`) của `data/pilot16` và `data/pilot17`:
**23 tờ, 21%**, có dải đệm lệch màu nền quá 4 mức. Tách theo cổng:

    tờ NHẬN  (html/)      4/34   12%   Δ tới 102
    tờ TRƯỢT (rejected/) 19/77   25%   Δ tới 255

Lỗi chạm CẢ HAI, nên siết cổng không chữa được nó.
`llm_utility_power_0028_p3` và `_p4` là trang ĐÃ NHẬN, có trong
`manifest.jsonl`, và `_p4` mang dải xám `#e5e5e5` phủ từ y=54% xuống đáy.
Nặng nhất:

    llm_form_roster_0007_p2      đệm trên (0,0,0)     nền (255,255,255)  Δ=255
    llm_form_sectioned_0008_p2   đệm trên (45,95,46)  nền (255,255,255)  Δ=210
    llm_retail_vat_invoice_0026_p4  đệm trên (51,51,51)                  Δ=204
    llm_utility_power_0028_p4    đệm trên (204,204,204)                  Δ=51
                                 đệm dưới (229,229,229) chiếm 52%-100% tờ

Hai lỗi nối nhau, và file này canh cả hai:

1. `_pad_top` lấy trung vị ĐÚNG MỘT HÀNG -- hàng đầu của lát. Mà `cut_lines`
   nhắm nhát cắt vào mép dưới một hàng ô bảng, nên hàng đầu của lát sau
   chính là ĐƯỜNG KẺ VIỀN của hàng kế tiếp, kẻ suốt bề rộng trang. Đếm trên
   26 tờ đo được: hàng ấy có 5-17 màu và 85%-99,9% số điểm ảnh đúng bằng màu
   đường kẻ.
2. `to_a4` đo lại màu giấy trên ảnh ĐÃ ĐỆM LỀ TRÊN, bằng trung vị bốn góc --
   nên hai trên bốn mẫu mang màu đường kẻ, và trung vị ra đúng TRUNG ĐIỂM.
   Số học khớp từng tờ một trên `pilot17`:

       viền #000 -> đệm dưới (127,127,127) = median(0,0,255,255)
       viền #333 -> (153,153,153)          = median(51,51,255,255)
       viền #999 -> (204,204,204)          = median(153,153,255,255)
       viền #ccc -> (229,229,229)          = median(204,204,255,255)

Nên test không chỉ hỏi "đệm trên có đúng không": nó dựng lại đúng chuỗi
`_pad_top` -> `to_a4` và hỏi CẢ HAI dải, vì lỗi thứ hai chỉ hiện ra khi lỗi
thứ nhất đã xảy ra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

pytest.importorskip("numpy", reason="draw_llm.py imports numpy")
pytest.importorskip("cv2", reason="draw_llm.py imports OpenCV")

import numpy as np                                              # noqa: E402

from synthgen import draw_llm as D                              # noqa: E402

# Dung sai. Ảnh vào là ảnh chụp PNG của Chromium, tô phẳng tuyệt đối, nên
# "đúng màu giấy" nghĩa là ĐÚNG BẰNG. Để 2 mức cho phép một lần làm tròn
# `astype`, và đủ chặt để mọi ca đã đo ở trên (Δ 17..255) đều đỏ.
TOLERANCE = 2

# Màu viền hay gặp trong CSS model viết, lấy từ 26 tờ đo được -- và dải tiêu
# đề xanh của `llm_form_sectioned_0008`, thứ chứng minh lỗi không chỉ là
# "xám nhạt trên trắng".
RULES = [(0, 0, 0), (51, 51, 51), (153, 153, 153), (204, 204, 204),
         (45, 95, 46)]

# Màu giấy: trắng, và hai màu giấy THẬT trong bộ (`llm_cash_receipt_voucher`
# ngà, `llm_form_checklist` xám nhạt). Giấy không trắng là lý do `to_a4` tô
# màu đo được chứ không tô trắng cứng, nên nó phải nằm trong test.
PAPERS = [(255, 255, 255), (255, 251, 231), (249, 249, 249)]

WIDTH = 1740
PAGE_H = int(round(WIDTH * D.A4_RATIO))


def _flow(paper, rule, *, tail_rows: int) -> "np.ndarray":
    """Một dòng chảy dài hai trang: tờ đầu đủ khổ, lát cuối NGẮN.

    Dựng đúng hình dạng đã đo: giấy, một cái bảng có viền kẻ ngang suốt bề
    rộng, và nhát cắt rơi ĐÚNG lên một đường viền -- nên hàng đầu của lát
    hai là đường kẻ ấy.
    """
    height = PAGE_H + tail_rows
    flow = np.full((height, WIDTH, 3), paper, dtype=np.uint8)
    # Bảng: viền kẻ ngang mỗi 60 hàng, dày 3 điểm, suốt bề rộng trừ lề.
    left, right = WIDTH // 12, WIDTH - WIDTH // 12
    for y in range(120, height - 20, 60):
        flow[y:y + 3, left:right] = rule
    # Chữ: những vệt mực ngắn giữa hai đường kẻ, để trang không phải giấy trơn.
    for y in range(140, height - 40, 60):
        flow[y:y + 22, left + 30:left + 700] = (17, 17, 17)
    # Nhát cắt rơi lên một đường viền -- ca đã đo, không phải ca dựng ra.
    flow[PAGE_H:PAGE_H + 3, left:right] = rule
    return flow


def _pages(flow, *, thread: bool = False):
    """Chạy ĐÚNG chuỗi của `draw_llm.run`: cắt, đệm lề trên cho tờ hai, rồi
    đưa mọi tờ về khổ A4.

    `thread=False` gọi `_pad_top`/`to_a4` KHÔNG kèm màu giấy -- đường mà mọi
    tờ trong bộ đã đi qua, và đường duy nhất mà cả bản cũ lẫn bản mới đều
    chạy được. Test chính đi đường này, nên khi nó đỏ thì nó đỏ vì MÀU SAI,
    không vì chữ ký hàm đổi.

    `thread=True` truyền màu đo một lần trên cả dòng chảy -- thứ `run` làm
    thật, và là lớp phòng thủ thứ hai: lát giữa có hai mép CẮT nên vành lề
    của riêng nó không phải chỗ hỏi tốt nhất.
    """
    given = (D._paper_colour(flow),) if thread else ()
    top = int(round(PAGE_H * D.TOP_MM / 297.0))
    slices = [(1, flow[:PAGE_H]), (2, flow[PAGE_H:])]
    padded = [(n, img if n == 1 else D._pad_top(img, top, *given))
              for n, img in slices]
    return [(n, D.to_a4(img, *given)) for n, img in padded]


def _bands(image):
    """Dải PHẲNG chạm mép trên hoặc mép dưới ảnh = vùng đệm. Đo lại từ ảnh
    ra, không tin con số nào code đưa cho."""
    height = image.shape[0]
    out = []
    y = 0
    while y < height and bool((image[y] == image[y, 0]).all()):
        y += 1
    if y:
        out.append(("trên", tuple(int(v) for v in image[0, 0]), y))
    y = height - 1
    while y >= 0 and bool((image[y] == image[y, 0]).all()):
        y -= 1
    if y < height - 1:
        out.append(("dưới", tuple(int(v) for v in image[-1, 0]),
                    height - 1 - y))
    return out


@pytest.mark.parametrize("paper", PAPERS, ids=lambda p: "giay%d_%d_%d" % p)
@pytest.mark.parametrize("rule", RULES, ids=lambda r: "vien%d_%d_%d" % r)
def test_dai_dem_dung_mau_giay(paper, rule):
    """Mọi dải đệm, trên và dưới, phải nằm trong `TOLERANCE` của màu giấy."""
    # 380 hàng: lát cuối ngắn hơn nửa trang, nên `to_a4` phải đệm hơn 84% tờ.
    pages = _pages(_flow(paper, rule, tail_rows=380))
    for number, image in pages:
        assert image.shape[:2] == (PAGE_H, WIDTH), f"tờ {number} sai khổ"
        for where, colour, rows in _bands(image):
            delta = max(abs(colour[i] - paper[i]) for i in range(3))
            assert delta <= TOLERANCE, (
                f"tờ {number}: dải đệm {where} dày {rows} hàng tô {colour}, "
                f"giấy là {paper} -- lệch {delta} mức")


@pytest.mark.parametrize("rule", RULES, ids=lambda r: "vien%d_%d_%d" % r)
def test_mau_do_mot_lan_tren_ca_dong_chay(rule):
    """Đường mà `run` đi thật: đo màu MỘT LẦN trên cả dòng chảy rồi dùng
    chung cho mọi lát.

    Test trên đã canh đường mặc định. Cái này canh đường truyền tay, vì đó
    mới là đường chạy trong sản xuất -- và vì màu giấy là thuộc tính của TỜ
    GIẤY, không phải của nhát cắt: một lát giữa chỉ có hai mép cắt, còn dòng
    chảy có mép trên thật và mép dưới thật."""
    paper = (255, 255, 255)
    for number, image in _pages(_flow(paper, rule, tail_rows=380),
                                thread=True):
        for where, colour, rows in _bands(image):
            delta = max(abs(colour[i] - paper[i]) for i in range(3))
            assert delta <= TOLERANCE, (
                f"tờ {number}: dải đệm {where} dày {rows} hàng tô {colour}, "
                f"giấy là {paper} -- lệch {delta} mức")


def test_vanh_le_chiu_duoc_mot_canh_ban():
    """`_paper_colour` phải sống sót khi MỘT cạnh của vành lề không phải giấy.

    Bản trước lấy trung vị bốn góc, nên hai góc bẩn là đủ kéo kết quả về
    trung điểm. Vành lề bốn cạnh thì một cạnh bẩn thua ba cạnh sạch theo số
    điểm ảnh -- đó là tính chất phải giữ, và đây là chỗ nói ra."""
    paper = (255, 251, 231)
    flow = _flow(paper, (0, 0, 0), tail_rows=380)
    # Cạnh TRÊN đen đặc suốt một dải dày, như `llm_form_roster_0007`.
    flow[:90, :] = (0, 0, 0)
    got = tuple(int(v) for v in D._paper_colour(flow))
    assert got == paper, f"đo ra {got}, phải là {paper}"


def test_giay_mau_khong_bi_keo_ve_trang():
    """Giấy ngà phải ra giấy ngà. Một bản vá tô trắng cứng sẽ làm mọi test
    trên xanh trừ cái này -- và nó chính là lỗi `to_a4` sinh ra để tránh."""
    paper = (255, 251, 231)
    pages = _pages(_flow(paper, (204, 204, 204), tail_rows=380))
    for _, image in pages:
        assert tuple(int(v) for v in image[-1, 0]) == paper
