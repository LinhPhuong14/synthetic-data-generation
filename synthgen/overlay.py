"""Vẽ hộp nhãn đè lên chính trang giấy nó đọc được.

Một con số ("98,7% hộp nằm trên mực") trả lời được cho một cửa kiểm tự động
nhưng không trả lời được cho người: người muốn NHÌN thấy hộp nào ôm chữ nào.
File này vẽ ra cái ấy -- hai ảnh cho mỗi trang, một cho vùng bố cục và một
cho từng từ.

Chỉ dùng ẢNH và BẢN GHI, đúng thứ người dùng bộ dữ liệu có trong tay. Không
đọc lại DOM, không dùng chung trạng thái với thứ đã vẽ ra trang -- một ảnh
kiểm chứng dùng chung trạng thái với thứ nó kiểm là một ảnh tự chứng minh
mình đúng.

Chữ trên ảnh viết bằng `cv2.putText`, tức là chỉ có Latin không dấu. Nên nhãn
in ra là tên LỚP (`Table`, `Page-Header`) chứ không phải chữ tiếng Việt trong
ô: tên lớp vốn đã không dấu, còn chữ trong ô thì đã nằm ngay dưới hộp rồi.
"""

from __future__ import annotations

import cv2
import numpy as np

# Cạnh của hệ toạ độ chuẩn hoá trong bản ghi. Cùng con số
# `pipeline/record.py::GRID` và `synthgen/export.py::GRID` -- ba nơi cùng nói
# một chuyện, và nơi nào lệch thì hộp lệch theo.
GRID = 1000

# ---------------------------------------------------------------- màu cố định
#
# Hộp TỪ mang ba màu theo vai trò của từ trong cặp KIE. Khoá CAM, giá trị LAM
# -- không phải đỏ với lục như bản trước. Đỏ với lục đúng là cặp màu mà mắt
# thiếu thụ thể L hoặc M không tách nổi, tức khoảng một trong mười hai người
# mở tấm ảnh này ra xem thấy hai màu ấy là một. Cam với lam thì mọi dạng mù
# màu phổ biến đều tách được, vì chúng khác nhau trên CẢ trục vàng-lam lẫn độ
# sáng, chứ không chỉ trên trục đỏ-lục.
KEY_COLOUR = (0, 94, 213)        # #d55e00, cam gạch
VALUE_COLOUR = (178, 114, 0)     # #0072b2, lam
PLAIN_COLOUR = (150, 140, 130)   # #828c96, xám lam -- từ không thuộc cặp nào

# Mũi tên khoá -> giá trị. Tím, không phải xám đậm như bản trước: xám đậm trên
# giấy trắng đọc ra là MỰC, nên mũi tên trông như một gạch chân ai đó in sẵn.
LINK_COLOUR = (173, 68, 142)     # #8e44ad

# Nhãn bố cục không có trong `DOCSYNTH_LABELS`. Giữ xám: xám là câu "kho này
# chưa đặt tên màu cho lớp đó", và nó đọc được đúng như thế vì mọi màu lớp bên
# dưới đều bão hoà.
OTHER = (90, 90, 90)

# Hai màu MỌI khung phải tránh: giấy và mực. Một khung vàng chanh trên giấy
# trắng vẫn là một màu riêng, nhưng vẽ hai pixel lên trang thì không ai thấy.
PAPER = (255, 255, 255)
INK = (20, 20, 20)

# Độ mờ của lớp tô trong vùng bố cục, theo DIỆN TÍCH vùng. Xem `layout()`.
WASH_MAX, WASH_MIN = 0.20, 0.035


# ------------------------------------------------------------- bảng màu lớp
def _lab(colours) -> np.ndarray:
    """Dãy BGR thành dãy CIE-Lab.

    Khoảng cách Euclid trong Lab xấp xỉ khoảng cách MẮT thấy; trong BGR thì
    không. Trong BGR, đỏ (0,0,255) cách lục (0,255,0) đúng bằng đỏ cách vàng
    (0,255,255) -- mà mắt thì thấy cặp sau gần nhau hơn hẳn. Chọn màu "xa
    nhau" bằng thước BGR nên chỉ là chọn màu xa nhau theo một thước không ai
    nhìn bằng."""
    rows = np.array(list(colours), dtype=np.uint8).reshape(-1, 1, 3)
    return cv2.cvtColor(rows, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)


def _candidates() -> np.ndarray:
    """Lưới màu để chọn ra: 90 sắc độ x 3 nấc sáng, đã lọc theo độ sáng.

    Ba nấc chứ không một. Trải đều SẮC ĐỘ mà giữ nguyên độ sáng -- đúng điều
    bản trước làm, `S=205, V=225` cho cả hai mươi mốt lớp -- thì hai lớp cạnh
    nhau chỉ còn đúng MỘT chiều để khác nhau. Thêm chiều sáng-tối vào là thêm
    một chiều nữa, và hai lớp trùng sắc độ vẫn tách được.

    Lọc L* về [25, 78] rồi mới chọn: trên 78 thì khung chìm vào giấy trắng
    (vàng chanh, xanh non), dưới 25 thì lẫn vào mực. Lọc TRƯỚC chứ không sửa
    sau, vì một màu quá sáng mà kéo tối lại thì nó không còn là màu đã chọn."""
    hues = np.arange(0, 180, 2, dtype=np.uint8)
    grid = []
    for saturation, value in ((255, 145), (240, 195), (150, 235)):
        hsv = np.stack([hues,
                        np.full(len(hues), saturation, dtype=np.uint8),
                        np.full(len(hues), value, dtype=np.uint8)], axis=1)
        grid.append(cv2.cvtColor(hsv.reshape(-1, 1, 3),
                                 cv2.COLOR_HSV2BGR).reshape(-1, 3))
    grid = np.concatenate(grid, axis=0)
    light = _lab(grid)[:, 0] * 100.0 / 255.0
    return grid[(light >= 25.0) & (light <= 78.0)]


def _palette() -> dict[str, tuple[int, int, int]]:
    """Một màu cho MỖI nhãn trong `DOCSYNTH_LABELS`, chọn xa nhau nhất có thể.

    Bản trước trải đều sắc độ: `linspace(0, 179, 21)`. Đủ để nói "mỗi lớp một
    màu" nhưng không đủ để NHÌN ra, vì hai mươi mốt sắc độ trên một vòng màu
    là mỗi bước tám độ rưỡi. Đo bằng Lab: hai lớp gần nhau nhất cách nhau
    dE 8,4 -- `Text` #e12ccf, `Title` #e12c9f và `Watermark` #e12c68 đều ra
    hồng, `Section-Header`, `Page-Header` và `Stamp` đều ra lam. Trên một tờ
    có đủ ba nhãn hồng, ảnh không trả lời được câu hỏi nó sinh ra để trả lời.

    Đây chọn theo lối xa-nhất-trước: mỗi lớp lấy ô nào trong lưới CÁCH XA
    NHẤT mọi màu đã lấy. Cùng lưới ấy, cùng hai mươi mốt lớp ấy: dE nhỏ nhất
    lên 34,1, gấp bốn lần. Bậc thang sáng chạy từ L* 25,5 đến 76,9.

    Tập "đã lấy" được MỒI sẵn bằng giấy, mực, `OTHER` và cả ba màu vai trò
    KIE. Nên không lớp bố cục nào rơi vào màu mà `words()`/`kie()` đang dùng
    để nói "đây là khoá" hay "đây là giá trị": nhìn màu một khung là biết mình
    đang xem lớp ảnh nào, không phải đọc tên thư mục. Một luật -- "xa những
    màu kia" -- trả lời cả hai câu hỏi, nên không có bảng loại trừ nào để
    quên cập nhật.

    Màu của một lớp ỔN ĐỊNH giữa các lượt chạy: lưới cố định, thứ tự cố định,
    không có ngẫu nhiên. Thêm một nhãn vào `pipeline/record.py` thì chỉ các
    nhãn sắp xếp SAU nó đổi màu -- `linspace` thì đổi cả hai mươi mốt, vì nó
    chia vòng màu cho tổng số nhãn.

    Ai cần bảng này thì IMPORT `CLASS_COLOURS`, đừng dựng lại.
    `tools/proof_boxes.py::_docsynth_palette` từng dựng lại đúng cùng một luật
    và đã lệch: `S=200, V=220` ở đó so với `S=205, V=225` ở đây, nên hai tấm
    ảnh cùng nói về một lớp lại ra hai màu. Một luật mà hai chỗ dựng thì sớm
    muộn là hai luật."""
    from pipeline.record import DOCSYNTH_LABELS               # noqa: PLC0415

    grid = _candidates()
    lab = _lab(grid)
    taken = _lab([PAPER, INK, OTHER,
                  KEY_COLOUR, VALUE_COLOUR, PLAIN_COLOUR, LINK_COLOUR])
    out: dict[str, tuple[int, int, int]] = {}
    for name in sorted(DOCSYNTH_LABELS):
        far = np.linalg.norm(lab[:, None, :] - taken[None, :, :], axis=2).min(axis=1)
        pick = int(np.argmax(far))
        out[name] = tuple(int(c) for c in grid[pick])
        taken = np.vstack([taken, lab[pick]])
    return out


CLASS_COLOURS: dict[str, tuple[int, int, int]] = _palette()


def _ink_on(colour: tuple[int, int, int]) -> tuple[int, int, int]:
    """Đen hay trắng -- cái nào đọc được trên nền `colour`.

    Bản trước luôn viết chữ TRẮNG, và đúng, vì khi ấy mọi màu cùng một độ
    sáng. Bảng màu mới trải L* từ 25 đến 77, nên chữ trắng trên `List-Group`
    (#abc30b, L* 74) là chữ nhạt trên nền nhạt.

    Chọn bằng TỈ SỐ TƯƠNG PHẢN WCAG, không bằng ngưỡng độ chói. Ngưỡng thì
    rẻ nhưng sai ở màu bão hoà: `Bibliography` #0bc30b có độ chói 119 trên
    255, dưới mọi ngưỡng hợp lý, nên ngưỡng trả về chữ trắng -- mà trắng trên
    lục ấy chỉ được 2,4:1, còn đen được 8,8:1. Tỉ số thì so đúng cái mắt phải
    làm: đọc chữ này trên nền kia."""
    def luminance(bgr) -> float:
        channels = []
        for raw in (bgr[2], bgr[1], bgr[0]):                     # R, G, B
            value = raw / 255.0
            channels.append(value / 12.92 if value <= 0.04045
                            else ((value + 0.055) / 1.055) ** 2.4)
        return (0.2126 * channels[0] + 0.7152 * channels[1]
                + 0.0722 * channels[2])

    background = luminance(colour)
    on_paper = (luminance(PAPER) + 0.05) / (background + 0.05)
    on_ink = (background + 0.05) / (luminance(INK) + 0.05)
    return INK if on_ink > on_paper else PAPER


def _rect(box) -> tuple[int, int, int, int] | None:
    """`[x1,y1,x2,y2]` hoặc `{x1,...}` thành bốn số nguyên. None nếu hỏng."""
    if isinstance(box, dict):
        box = [box.get("x1"), box.get("y1"), box.get("x2"), box.get("y2")]
    if not box or len(box) != 4 or any(v is None for v in box):
        return None
    x1, y1, x2, y2 = (int(round(float(v))) for v in box)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _on(image: np.ndarray, px, per_mille) -> tuple[int, int, int, int] | None:
    """Hộp theo PIXEL CỦA CHÍNH TẤM ẢNH đang vẽ, từ hai cách nói về nó.

    `*_px` khi có: đó là số pixel đo được, dùng thẳng.

    Không có thì `bbox` là PHẦN NGHÌN của cạnh giấy -- hợp đồng bản ghi kể từ
    `pipeline/record.py::to_per_mille`, ghi ở đầu file ấy -- nên phải nhân lại
    theo cạnh ảnh. Bản trước viết `pair.get("key_bbox_px") or pair.get(
    "key_bbox")` và vẽ THẲNG số phần nghìn như pixel: mọi hộp dồn vào ô vuông
    1000×1000 ở góc trên-trái, đo trên `data/thu1k` là 685/966 hộp trường
    (71%). Không gì báo lỗi -- một hộp 221 vẫn là một hộp hợp lệ -- nên chỉ
    người nhìn tấm ảnh mới thấy, và tấm ảnh ấy chính là thứ người ta nhìn để
    tin vào nhãn.

    Nhân lại chứ không bỏ qua: một bộ cũ chỉ còn `bbox` vẫn vẽ ra đúng, thay
    vì mất sạch hộp.
    """
    rect = _rect(px)
    if rect:
        return rect
    rect = _rect(per_mille)
    if not rect:
        return None
    high, wide = image.shape[:2]
    return (int(round(rect[0] / GRID * wide)), int(round(rect[1] / GRID * high)),
            int(round(rect[2] / GRID * wide)), int(round(rect[3] / GRID * high)))


def _tag(image, text: str, at: tuple[int, int], colour,
         scale: float | None = None) -> None:
    """Nhãn nhỏ có nền, để chữ đọc được cả trên vùng mực đậm.

    Nhãn nằm NGAY TRÊN hộp, không đè vào nó: cái nó đang chỉ vào là mực trong
    hộp, mà đè lên thì che mất đúng thứ người xem mở ảnh ra để nhìn. Hết chỗ
    phía trên -- hộp sát mép giấy -- thì mới tụt xuống dưới.

    Nền nhãn dùng CHÍNH màu khung, nên nhãn và hộp nó gọi tên là một cặp nhìn
    ra ngay, kể cả khi hai hộp khác lớp chồng lên nhau."""
    if scale is None:
        scale = max(image.shape[1] / 2200.0, 0.34)
    thick = 1
    # `baseline` là phần chữ THÒ XUỐNG dưới đường chân -- đuôi `p`, `g`, `y`.
    # Bản trước bỏ nó đi và chừa cứng 4 pixel. Ở cỡ chữ của một trang 1832
    # pixel, `getTextSize` đòi 8: nên MỌI tên lớp có đuôi -- `List-Group`,
    # `Page-Footer`, `Bibliography`, `Diagram` -- cụt mất 4 pixel cuối, đúng
    # ngay trên khung. Một cái nhãn đọc sai tên lớp thì không còn là nhãn.
    (w, h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX,
                                       scale, thick)
    tall = h + baseline + 4
    x, y = at
    top = y - tall - 1
    if top < 0:
        top = y + 2
    cv2.rectangle(image, (x, top), (x + w + 6, top + tall), colour, -1)
    cv2.rectangle(image, (x, top), (x + w + 6, top + tall), PAPER, 1)
    cv2.putText(image, text, (x + 3, top + h + 2), cv2.FONT_HERSHEY_SIMPLEX,
                scale, _ink_on(colour), thick, cv2.LINE_AA)


def layout(image: np.ndarray, regions: list[dict]) -> np.ndarray:
    """Vùng bố cục: khung dày, tô mờ bên trong, tên lớp ở góc trên trái."""
    out = image.copy()
    height, width = out.shape[:2]
    page = float(height * width) or 1.0

    drawn: list[tuple[tuple[int, int, int, int], tuple[int, int, int], str]] = []
    for region in regions:
        # `bbox_px` khi có, còn không thì nhân `bbox` phần nghìn trở lại theo
        # cạnh ảnh -- xem `_on`. Từ khi `pipeline/record.py` chuyển bản ghi
        # sang hệ 0..1000, `bbox` là phần nghìn của cạnh giấy. Vẽ phần nghìn
        # lên ảnh pixel thì mọi hộp co về góc trên trái -- và co ĐẸP, không
        # báo lỗi, nên chỉ nhìn ảnh mới thấy. `bbox_px` là chính con số cũ.
        rect = _on(image, region.get("bbox_px"), region.get("bbox"))
        if not rect:
            continue
        x1 = max(0, min(rect[0], width))
        y1 = max(0, min(rect[1], height))
        x2 = max(0, min(rect[2], width))
        y2 = max(0, min(rect[3], height))
        if x2 <= x1 or y2 <= y1:
            continue
        name = str(region.get("layout_class", "") or "?")
        drawn.append(((x1, y1, x2, y2), CLASS_COLOURS.get(name, OTHER), name))

    # Vùng LỚN vẽ trước, vùng nhỏ vẽ sau và nằm trên. Ngược lại thì một
    # `Watermark` ôm cả trang sẽ phủ lên mọi vùng nằm trong nó.
    #
    # `Watermark` LUÔN vẽ trước, bất kể to nhỏ. Chữ chìm là MỰC PHỦ lên tờ
    # giấy, không phải một vùng trong mạch nội dung, nên nó không được phép
    # nằm trên vùng nào. Khi hộp của nó còn ôm cả trang thì luật diện tích ở
    # trên đã vô tình làm đúng việc ấy; từ lúc hộp co sát chữ (13-21% bề
    # ngang) nó thành vùng NHỎ và vẽ sau cùng -- lớp tô của nó cắt ngang một
    # `List-Group` hai cột, và trên ảnh kiểm tra vùng ấy trông như bị đứt
    # đoạn trong khi hộp trong JSON vẫn liền. Đo trên `so_lien_lac_00007_p2`.
    drawn.sort(key=lambda item: (item[2] == "Watermark",
                                 (item[0][2] - item[0][0]) * (item[0][3] - item[0][1])),
               reverse=True)

    # Lớp tô ĐẬM cho vùng nhỏ, NHẠT cho vùng lớn. Bản trước dùng chung một mức
    # 0,12 cho mọi vùng. `llm_bien_ban_ban_giao_hang_hoa_0008` mang một
    # `Watermark` ôm ĐÚNG cả tờ -- (0,0,1588,2246) trên trang 1588x2246 -- nên
    # ở mức chung ấy nó nhuộm màu toàn bộ trang, kể cả con dấu nằm trong nó.
    # Mà một lớp tô kín trang không nói thêm gì về vùng ấy: vùng ấy vốn đã là
    # cả trang. Ở đây nó xuống 0,035. Diện tích càng lớn, tiếng nói càng nhỏ.
    for (x1, y1, x2, y2), colour, _name in drawn:
        share = min(1.0, (x2 - x1) * (y2 - y1) / page)
        alpha = WASH_MIN + (WASH_MAX - WASH_MIN) * (1.0 - share) ** 2
        roi = out[y1:y2, x1:x2]
        patch = np.empty_like(roi)
        patch[:] = colour
        cv2.addWeighted(patch, alpha, roi, 1.0 - alpha, 0.0, roi)

    # Khung và nhãn vẽ SAU mọi lớp tô: một khung 2 pixel bị lớp tô của vùng
    # tiếp theo phủ lên thì nhạt đi đúng ở chỗ nó cần đậm nhất.
    #
    # Viền giấy 1 pixel bọc ngoài mỗi khung. Trên giấy trắng nó tàng hình, nên
    # không mất gì; trên nền màu thì nó là cái cứu tấm ảnh. Đo trên
    # `llm_annual_health_station_report_0012`: letterhead của tờ ấy là một dải
    # LỤC ĐẬM (#37 8a 3a), và khung `Text` (#0bc36d) vẽ thẳng lên đó gần như
    # biến mất. Bảng màu nào cũng chỉ chọn được màu xa những màu nó BIẾT --
    # giấy, mực, các lớp khác -- chứ không xa được màu mà chính tờ giấy in ra.
    for rect, colour, name in drawn:
        cv2.rectangle(out, rect[:2], rect[2:], PAPER, 4)
        cv2.rectangle(out, rect[:2], rect[2:], colour, 2)
        _tag(out, name, (rect[0], rect[1]), colour)
    return out


def words(image: np.ndarray, boxes: list[dict]) -> np.ndarray:
    """Hộp từ: khung mảnh, màu theo vai trò KIE.

    Không viết chữ lên: một trang có hàng nghìn từ, và một nhãn cho mỗi từ
    thì che hết chính cái mực nó đang chỉ vào."""
    out = image.copy()
    for box in boxes:
        rect = _on(image, box.get("bbox_px"), box.get("bbox"))
        if not rect:
            continue
        role = str(box.get("kie_role") or "")
        colour = (KEY_COLOUR if role == "key" else
                  VALUE_COLOUR if role == "value" else PLAIN_COLOUR)
        cv2.rectangle(out, rect[:2], rect[2:], colour, 1)
    return out


def kie(image: np.ndarray, pairs: list[dict], page: int = 1) -> np.ndarray:
    """Từng cặp KHOÁ → GIÁ TRỊ, và đường nối giữa hai hộp của nó.

    `word_boxes` tô màu theo vai trò nhưng không nói hộp nào ĐI VỚI hộp nào.
    Trên một tờ giấy có "Địa chỉ:" hai lần -- bên bán và bên mua -- đó chính
    là câu hỏi khó nhất, và một mũi tên trả lời nó nhanh hơn ba cột JSON.

    Nhãn viết bằng tên trường (`dia_chi`, `ma_so_thue`): `kie.slug()` đã bỏ
    dấu sẵn, nên `cv2.putText` in được -- còn chữ tiếng Việt trên giấy thì
    đã nằm ngay trong hộp rồi, không cần in lại.
    """
    out = image.copy()
    for pair in pairs:
        if int(pair.get("page_number", page) or page) != page:
            continue
        # Ô bảng vẽ GỌN: một trang có thể mang hơn hai trăm ô, và hai trăm
        # mũi tên chụm về cùng một ô tiêu đề thì tấm ảnh thành một búi chỉ.
        # Khung vẫn đủ nói ô nào là khoá ô nào là giá trị.
        dense = pair.get("source") == "table"
        # `*_bbox_px` cùng lẽ như trên: cặp KIE cũng đã sang hệ 0..1000.
        key = _on(image, pair.get("key_bbox_px"), pair.get("key_bbox"))
        value = _on(image, pair.get("value_bbox_px"), pair.get("value_bbox"))
        if key:
            cv2.rectangle(out, key[:2], key[2:], KEY_COLOUR, 1)
        if value:
            cv2.rectangle(out, value[:2], value[2:], VALUE_COLOUR, 1)
        if dense:
            continue
        if key and value:
            start = (key[2], (key[1] + key[3]) // 2)
            end = (value[0], (value[1] + value[3]) // 2)
            cv2.arrowedLine(out, start, end, LINK_COLOUR, 1,
                            cv2.LINE_AA, tipLength=0.04)
        # Nhãn mang màu của CHÍNH hộp nó đậu lên. Bản trước luôn tô màu khoá,
        # nên một cặp chỉ có hộp giá trị -- trường suy ra được mà không in
        # tên khoá lên giấy -- đội một nhãn cam trên một khung lam.
        anchor, anchor_colour = ((key, KEY_COLOUR) if key else
                                 (value, VALUE_COLOUR))
        if anchor:
            # Cỡ chữ theo CHIỀU CAO CỦA HỘP, không theo bề ngang tấm ảnh: một
            # trường cao mười lăm pixel mà đội cái nhãn cao ba mươi thì nhãn
            # che ba dòng chữ quanh nó. Đo trên một phiếu chi: nhãn cỡ cố
            # định phủ kín cả khối letterhead.
            tall = anchor[3] - anchor[1]
            _tag(out, str(pair.get("field", "?")), (anchor[0], anchor[1]),
                 anchor_colour, scale=max(0.26, min(0.42, tall / 44.0)))
    return out


def kie_index(record: dict) -> dict[int, dict[str, str]]:
    """`{entity_index: {field, description, role}}` từ các cặp KIE.

    Từ nối vào cặp qua `entity_index` chứ không qua toạ độ: hai hộp chồng
    nhau vẫn là hai trường khác nhau, còn `entity_index` thì đã do
    `pipeline/kie.py` chốt sẵn."""
    out: dict[int, dict[str, str]] = {}
    for pair in (record.get("kie") or {}).get("pairs") or []:
        field = str(pair.get("field", ""))
        description = str(pair.get("description", ""))
        for role, key in (("key", "key_entity_index"),
                          ("value", "value_entity_index")):
            index = pair.get(key)
            if isinstance(index, int):
                out[index] = {"kie_field": field,
                              "kie_description": description,
                              "kie_role": role}
    return out


def annotate(boxes: list[dict], index: dict[int, dict[str, str]]) -> list[dict]:
    """Chép mô tả KIE vào từng hộp từ.

    `word_boxes/` là file mà một trình huấn luyện đọc MỘT MÌNH, không mở bản
    ghi đầy đủ bên cạnh. Nên mô tả trường phải nằm ngay trong nó, chứ không
    phải một cái khoá trỏ sang file khác."""
    out = []
    for box in boxes:
        row = dict(box)
        extra = index.get(box.get("entity_index"))
        if extra:
            row.update(extra)
        out.append(row)
    return out


def slice_for(record: dict, page: int,
              index: dict[int, dict[str, str]] | None = None
              ) -> tuple[list[dict], list[dict]]:
    """`(hộp vùng, hộp từ)` của MỘT tờ, dựng từ chính bản ghi.

    Đây là thứ thay cho `layout_boxes/*.json` và `word_boxes/*.json`. Hai file
    ấy từng được ghi ra bên cạnh mỗi trang và không mang một bit nào mà bản ghi
    chưa có -- 14,1 GB trên bộ 20 099 trang. Một hàm dựng lại được thì một file
    chép sẵn chỉ là một chỗ nữa để lệch.

    `index` truyền vào khi gọi nhiều lần trên cùng một bản ghi (`kie_index`
    quét cả danh sách cặp, và một tài liệu ba tờ thì quét ba lần là thừa hai).
    """
    if index is None:
        index = kie_index(record)
    on_page = lambda items: [item for item in items or []          # noqa: E731
                             if int(item.get("page_number", 1) or 1) == page]
    return (on_page(record.get("layout_annotations")),
            annotate(on_page(record.get("word_annotations")), index))


__all__ = ["annotate", "kie", "kie_index", "layout", "slice_for", "words"]
