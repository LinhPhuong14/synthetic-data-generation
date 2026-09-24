#!/usr/bin/env python3
"""Vẽ những trang HTML do model viết, kể cả trang đã TRƯỢT cổng.

    python synthgen/draw_llm.py data/pilot-llm
    python synthgen/draw_llm.py data/pilot-llm --only rejected

Bước sau `agent/compose_page.py`. Nó mở Chromium, dàn trang, đo hộp bằng ĐÚNG
những phép đo đang dùng cho mọi trang khác của kho, rồi để lại:

    images/<stem>.jpg         tờ giấy
    layout_boxes/<stem>.jpg   vùng bố cục vẽ đè lên nó
    word_boxes/<stem>.jpg     hộp từ vẽ đè lên nó
    records/<stem>.json       bản ghi đầy đủ

## Vì sao vẽ cả trang trượt

Vì đó là những trang đáng nhìn nhất. Một trang qua cổng nói "model làm đúng
chỗ này"; một trang trượt nói **model hiểu sai cái gì**, và đó là thứ sửa được
lời dặn. Đo trên 30 trang đầu: 21 trượt, và cả 21 biến mất cùng lý do của
chúng vì bản đầu chỉ lưu trang qua cổng.

Trang trượt vẫn dàn ra được -- cổng nói nó SAI NHÃN, không nói nó sai HTML.
Nên ảnh vẽ hộp của một trang trượt trả lời đúng câu người ta muốn hỏi: bố cục
có đúng không, và thiếu hộp ở chỗ nào.

Ảnh của chúng đi vào `rejected_boxes/` chứ không lẫn vào `layout_boxes/`: một
thư mục lẫn trang hỏng là một thư mục không ai dám đưa vào tập huấn luyện.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from page import (  # noqa: E402
    CELL_RECTS_JS, CELL_REGIONS_JS, GRAPHIC_RECTS_JS, ZONE_REGIONS_JS, served,
)
from render import (  # noqa: E402
    clip_to_page, graphics_from_rects, quads_from_rects, regions_from_rects,
    zones_from_rects,
)

from pipeline import record as R  # noqa: E402
from synthgen import field_tier as FT  # noqa: E402
from synthgen import overlay as O  # noqa: E402
from synthgen.kie_full import complete as kie_complete  # noqa: E402
from synthgen.phrasing import voice_record  # noqa: E402
from synthgen.llm_page import problems  # noqa: E402

JPEG_QUALITY = 92
SCALE = 2.0


def _slug(text: str) -> str:
    """Tên thư mục an toàn từ một chuỗi tự do.

    `loai_tai_lieu` model trả về là chữ tiếng Việt có dấu và có thể có gạch
    chéo -- "Tờ khai báo y tế / Phiếu khai báo dịch tễ". Dùng thẳng làm tên
    thư mục thì gạch chéo cắt đường dẫn làm đôi và `derive.py` đổ ở bước ghi
    schema. Ưu tiên `archetype` (đã là slug) rồi mới tới đây."""
    plain = unicodedata.normalize("NFD", str(text).lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    out = re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
    return out or "llm"


# Hai nhãn MỰC PHỦ và tiền tố `data-kind` thuộc về chúng. Vùng mang nhãn ở đây
# cắt theo kind chứ không theo hình học -- xem `tighten`.
WASH = {"Watermark": "watermark", "Stamp": "seal"}


def tighten(zones: list[dict], words: list[dict]) -> list[dict]:
    """Cắt mỗi hộp vùng về đúng vệt mực nó chứa.

    Hộp vùng lấy theo khung `<div>` model khai, và một `<div>` thường rộng hết
    cột dù chữ trong nó chỉ chiếm một mẩu. Đo trên pilot8, bề ngang THỪA so với
    mực (trung vị, so với bộ sinh của kho):

        Section-Header 69% (engine 4%)   Page-Footer 59% (12%)
        Caption        58% (62%)         Figure      46%
        Formula        35% (7%)          Footnote    33% (27%)
        Bibliography   31% (43%)

    Tệ nhất là `data-region="Watermark"` đặt lên `.wm{position:absolute;inset:0}`:
    hộp ra đúng `[0, 0, 1588, 2246]` -- CẢ TỜ GIẤY -- và trường `text` của vùng
    gom mọi đoạn chữ trên trang. Một vùng bằng cả trang không phải một vùng.

    Cắt được vì không cần đoán: vùng ấy CHỨA những chữ nào là chuyện hình học
    đã đo xong. Nhãn giữ nguyên, chỉ hộp co lại.

    Vùng không chứa chữ nào (khung hình, con dấu) giữ nguyên hộp: chúng là mực
    chứ không phải chữ, và `GRAPHIC_RECTS_JS` đã đo đúng."""
    if not zones or not words:
        return zones
    boxes = []
    for w in words:
        q = w.get("quad") or []
        if len(q) == 4:
            xs = [pt[0] for pt in q]; ys = [pt[1] for pt in q]
            boxes.append((w.get("kind"),
                          (min(xs), min(ys), max(xs), max(ys))))
    out = []
    for zone in zones:
        q = zone.get("quad") or []
        if len(q) != 4:
            out.append(zone)
            continue
        xs = [pt[0] for pt in q]; ys = [pt[1] for pt in q]
        zx0, zy0, zx1, zy1 = min(xs), min(ys), max(xs), max(ys)
        inside = [b for k, b in boxes
                  if zx0 <= (b[0] + b[2]) / 2 <= zx1
                  and zy0 <= (b[1] + b[3]) / 2 <= zy1
                  # MỰC PHỦ cắt theo KIND, không theo hình học.
                  #
                  # `data-region="Watermark"` model đặt lên
                  # `.wm{position:absolute;inset:0}` -- khung phủ đúng cả tờ,
                  # nên "chữ nằm trong nó" là MỌI chữ trên trang, và cắt theo
                  # hình học chỉ co từ cả-tờ xuống gần-cả-tờ. Vùng chữ chìm
                  # thì chứa chữ chìm; đó là định nghĩa, không phải suy đoán.
                  and (WASH.get(str(zone.get("label") or "")) is None
                       or str(k or "").startswith(WASH[str(zone["label"])]))]
        if not inside:
            out.append(zone)
            continue
        # Kẹp vào trong hộp cũ: mực có thể tràn ra ngoài khung (chữ xoay, chữ
        # âm lề), và một cái hộp NỞ ra thì tệ hơn cái hộp thừa.
        nx0 = max(zx0, min(b[0] for b in inside))
        ny0 = max(zy0, min(b[1] for b in inside))
        nx1 = min(zx1, max(b[2] for b in inside))
        ny1 = min(zy1, max(b[3] for b in inside))
        if nx1 <= nx0 or ny1 <= ny0:
            out.append(zone)
            continue
        out.append({**zone, "quad": [[round(nx0, 1), round(ny0, 1)],
                                     [round(nx1, 1), round(ny0, 1)],
                                     [round(nx1, 1), round(ny1, 1)],
                                     [round(nx0, 1), round(ny1, 1)]]})
    return out


# Tỉ lệ A4: 297mm cao trên 210mm rộng. Suy chiều cao một trang TỪ chiều rộng
# đo được, không viết cứng số điểm ảnh -- model tự chọn CSS, và một con số DPI
# viết cứng ở đây là con số đúng với đúng một cách viết CSS.
A4_RATIO = 297.0 / 210.0

# Lề DƯỚI mỗi tờ, theo phần chiều cao trang. Nhát cắt nhắm sớm hơn bấy nhiêu,
# rồi `to_a4` đệm phần thiếu bằng màu giấy -- nên tờ vẫn đủ khổ A4 mà chữ
# không chạy sát mép.
#
# Vì sao cần: bản trước cắt đúng bội số chiều cao trang, nên dòng cuối cùng của
# mỗi tờ nằm ngay mép giấy. Giấy in thật không có tờ nào như thế, và người
# dùng nhìn ảnh thấy ngay.
BOTTOM_MM = 14.0

# Lề TRÊN của tờ thứ hai trở đi. Tờ đầu đã có lề do CSS của model
# (`.sheet{padding}`), nhưng những tờ cắt ra thì không -- chữ bắt đầu ngay mép
# trên. Đệm vào khi ghép ảnh, và dời toạ độ xuống theo đúng bấy nhiêu.
TOP_MM = 12.0


def _pad_top(image, rows: int):
    """Đệm `rows` dòng màu giấy lên đầu ảnh."""
    if rows <= 0:
        return image
    paper = np.median(image[0], axis=0).astype(image.dtype)
    pad = np.tile(paper, (rows, image.shape[1], 1)).astype(image.dtype)
    return np.vstack([pad, image])


def to_a4(image):
    """Đệm ảnh cho đủ chiều cao A4. Tờ giấy ngắn vẫn là tờ A4.

    Từ khi lời dặn bảo model **đừng đặt `height`** -- để nội dung chảy liên tục
    rồi máy cắt -- một tài liệu ngắn cho ra `.sheet` co đúng bằng nội dung: đo
    được 1588x650 thay vì 1588x2246. Cả bộ dữ liệu sẽ có khổ giấy mỗi tờ một
    khác, và "độ đầy" thành 100% ở mọi trang vì mẫu số co theo tử số.

    Lát CUỐI của một dòng chảy cũng vậy: nó là phần dư, ngắn hơn A4.

    Đệm bằng màu nền đo được ở hàng dưới cùng, không bằng trắng cứng: model
    chọn màu giấy của nó (ngà, xám nhạt), và một vệt trắng nối vào giấy ngà là
    một đường kẻ ngang không có trên giấy thật."""
    height, width = image.shape[:2]
    want = int(round(width * A4_RATIO))
    if height >= want:
        return image
    paper = _paper_colour(image)
    pad = np.tile(paper, (want - height, width, 1)).astype(image.dtype)
    return np.vstack([image, pad])


def _paper_colour(image):
    """Màu GIẤY của trang, đo ở chỗ chắc chắn là giấy.

    Bản trước lấy trung vị HÀNG DƯỚI CÙNG của lát cắt. Hàng ấy không phải giấy
    khi nhát cắt rơi ngay dưới một dải đậm -- một đầu bảng, một vạch màu, một
    chân khối tô nền. Rồi màu đậm ấy được trải kín phần đệm.
    
    Đo được trên `llm_freight_invoice_0007`: bảng mười lăm dòng bị đẩy nguyên
    khối sang tờ sau (đúng luật "bảng không chảy qua trang"), để lại khoảng
    trống nửa tờ -- và khoảng trống ấy bị tô `#4a5a6a` từ y=50% xuống đáy. Bảng
    còn đủ, dữ liệu còn đúng, nhưng tờ một thành một khối tối không đọc được.
    
    Lấy ở BỐN GÓC LỀ thay vì hàng cuối: lề trang là chỗ giấy thật sự trống,
    dù nội dung bên trong có gì. Trung vị của bốn mẫu chịu được một góc lỡ
    dính con dấu hay chữ chìm."""
    height, width = image.shape[:2]
    band = max(4, min(height, width) // 40)
    corners = [image[:band, :band], image[:band, -band:],
               image[-band:, :band], image[-band:, -band:]]
    picks = np.stack([np.median(c.reshape(-1, 3), axis=0) for c in corners])
    return np.median(picks, axis=0).astype(image.dtype)


# CƠ CHẾ IN CỦA TRÌNH SOẠN THẢO, áp theo LOẠI vùng.
#
# `break-inside: avoid` không phải luật chung cho mọi khối. Một đoạn văn dài
# hay một danh sách điều khoản CHẢY qua trang -- giấy thật vẫn ngắt giữa đoạn,
# và Word/Docs làm đúng thế. Cắt ngang một cái BẢNG hay một cái HÌNH thì khác:
# nửa bảng không có đầu bảng, nửa hình không đọc được.
#
# Bản trước coi MỌI vùng là rào, nên một `List-Group` chín mươi khoản thành một
# khối không cắt được -- và khi không có khe nào, thuật toán lùi về khe xa phía
# trước, cho ra tờ đầy 46% rồi tờ sau đầy 93%.
ATOMIC = frozenset({
    "Table", "Figure", "Image", "Diagram", "Caption", "Form", "Formula",
    "Code-Block", "Title", "Section-Header", "Page-Header", "Page-Footer",
    "Stamp", "Footnote",
})
# Mọi nhãn còn lại chảy được: `Text`, `List-Group`, `Bibliography`,
# `Table-Of-Contents`, `Complex-Block`. `Watermark` phủ cả tờ nên nó không bao
# giờ là rào -- coi nó là rào thì không tờ nào cắt được.


def _merge(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Gộp những khoảng chồng nhau thành khoảng liền."""
    if not spans:
        return []
    out = [list(s) for s in sorted(spans)]
    merged = [out[0]]
    for low, high in out[1:]:
        if low <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    return [(a, b) for a, b in merged]


def inside(at: float, barriers: list[tuple[float, float]]) -> tuple | None:
    """Rào chứa điểm `at`, hoặc `None`. Mép rào không tính là bên trong."""
    for low, high in barriers:
        if low < at < high:
            return (low, high)
    return None


def cut_lines(height: float, page_height: float, gaps: list[tuple[float, float]],
              slack: float = 0.12,
              barriers: list[tuple[float, float]] | None = None,
              splits: list[float] | None = None) -> list[float]:
    """Cắt ở đâu để một dòng chảy dài thành nhiều tờ A4.

    Người dùng nói đúng bản chất: giấy thật KHÔNG sang trang vì người viết
    quyết định sang trang, mà vì chữ chảy hết chiều cao tờ giấy. Bản trước để
    model tự mở `<div class="sheet">` mới, và nó mở tuỳ hứng -- đo trên pilot8,
    `phieu_bao_chuyen_hang_0019` ra sáu tờ với [150, 43, 48, 13, 17, 23] từ,
    độ đầy 80% rồi 18% 16% 14% 17% 15%. Tờ thứ tư có mười ba từ.

    Nên cắt ở đây, theo chiều cao, chứ không hỏi model.

    `gaps` là những khoảng TRỐNG giữa hai khối liên tiếp `(đỉnh, đáy)`. Nhát
    cắt nhắm đúng bội số của `page_height`, rồi trượt về khoảng trống gần nhất
    trong phạm vi `slack` -- để không cắt ngang một dòng chữ. Không có khoảng
    trống nào đủ gần thì cắt thẳng: một nhát cắt hơi xấu vẫn hơn một tờ giấy
    dài gấp đôi khổ A4."""
    if page_height <= 0 or height <= page_height * 1.15:
        return []
    cuts: list[float] = []
    window = page_height * slack
    target = page_height
    while target < height - window:
        # `>=`, không `>`. Ranh giới MỘT DÒNG CHỮ là một khe rộng bằng không --
        # đáy dòng trên trùng đỉnh dòng dưới -- và nó là chỗ cắt hoàn toàn đúng.
        # Bản trước lọc `g[1] > g[0]`, nên mọi ranh giới dòng bị bỏ, và khi
        # quanh đích không có khe THẬT nào thì thuật toán cắt thẳng: đo được
        # trên tờ biên bản, dòng "Hà Nội, ngày 28 tháng 8 năm 2026" bị xẻ ngang
        # thân chữ, nửa trên ở tờ này nửa dưới ở tờ kia, và không tờ nào có hộp
        # cho nó.
        near = [g for g in gaps
                if abs((g[0] + g[1]) / 2 - target) <= window and g[1] >= g[0]]
        if near:
            best = min(near, key=lambda g: abs((g[0] + g[1]) / 2 - target))
            at = (best[0] + best[1]) / 2
        else:
            # Không có khe nào quanh đích: LÙI về khe cuối cùng TRƯỚC đích,
            # đừng cắt thẳng.
            #
            # Cắt thẳng là xẻ đôi một khối -- đo được trên tờ hợp đồng: ba thẻ
            # tổng bị cắt ngang, nửa trên ở tờ này nửa dưới ở tờ kia, và vùng
            # của chúng gán về một tờ theo trung điểm nên tờ còn lại có chữ mà
            # không có hộp. Một tờ ngắn hơn vẫn là một tờ giấy đúng; một khối
            # bị xẻ đôi thì không.
            floor_at = cuts[-1] if cuts else 0.0
            before = [g for g in gaps
                      if floor_at + page_height * 0.35 < (g[0] + g[1]) / 2 <= target]
            at = (max((g[0] + g[1]) / 2 for g in before) if before else target)
        # Không lùi lại phía sau nhát trước: một nhát cắt ở TRÊN nhát trước
        # sinh ra một tờ có chiều cao âm.
        if cuts and at <= cuts[-1] + page_height * 0.3:
            at = target
        # RÀO: nhát cắt không được rơi vào trong một vùng nguyên khối.
        hit = inside(at, barriers or [])
        if hit is not None:
            low, high = hit
            floor_at = cuts[-1] if cuts else 0.0
            if high - low <= page_height and low > floor_at + page_height * 0.25:
                # Vừa một trang: ĐẨY CẢ KHỐI sang tờ sau, cắt ngay trên nó.
                at = low
            else:
                # Cao hơn một trang, hoặc đẩy đi thì tờ này gần như trống: buộc
                # phải xẻ, nhưng xẻ ở mép con gần nhất -- với bảng đó là ranh
                # giới giữa hai hàng, không phải giữa thân một hàng.
                near = [s for s in (splits or []) if low < s < high and s > floor_at]
                if near:
                    at = min(near, key=lambda s: abs(s - target))
        cuts.append(at)
        target = at + page_height
    return cuts


def gaps_between(boxes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Khoảng trống dọc giữa các khối, gộp những khối chồng nhau."""
    if not boxes:
        return []
    spans = sorted(boxes)
    merged = [list(spans[0])]
    for top, bottom in spans[1:]:
        if top <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], bottom)
        else:
            merged.append([top, bottom])
    return [(merged[i][1], merged[i + 1][0]) for i in range(len(merged) - 1)
            if merged[i + 1][0] > merged[i][1]]


def draw_one(page, html: str, stem: str, declared: dict) -> dict | None:
    """Dàn một trang, đo, dựng bản ghi. `None` khi không có `.sheet` nào."""
    with served(html) as uri:
        page.goto(uri, wait_until="load", timeout=120_000)
    page.wait_for_timeout(35)

    # THẢ CHIỀU CAO khi chữ tràn ra ngoài tờ.
    #
    # Lời dặn giờ bảo model viết một dòng chảy và đừng đặt `height`, nhưng thói
    # quen cũ còn đó -- và `.sheet{height:297mm}` với nội dung dài hơn một tờ
    # thì phần tràn KHÔNG mất đi: nó vẫn được đo, rồi `clip_to_page` kẹp mọi
    # hộp về đúng mép dưới. Dựng lại được: tám mươi dòng trong một tờ cố định
    # cho ra 380 hộp từ với `y` lớn nhất đúng bằng 2246 -- một chồng nhãn xếp
    # lên nhau ở mép giấy, trỏ vào chữ không nhìn thấy.
    #
    # Thả `height` ra thì tờ giấy dài đúng bằng nội dung, và `cut_lines` cắt nó
    # thành mấy tờ A4 -- đúng thứ ta muốn. Sửa một thói quen, không loại một
    # trang viết đúng mọi luật khác.
    page.evaluate("""() => {
      let freed = 0;
      for (const el of document.querySelectorAll('.sheet')) {
        if (el.scrollHeight > el.clientHeight + 4) {
          el.style.height = 'auto';
          el.style.minHeight = '0';
          el.style.overflow = 'visible';
          freed += 1;
        }
      }
      return freed;
    }""")
    page.wait_for_timeout(20)

    rects = page.evaluate(CELL_RECTS_JS)
    regions = page.evaluate(CELL_REGIONS_JS)
    graphics = page.evaluate(GRAPHIC_RECTS_JS)
    zones = page.evaluate(ZONE_REGIONS_JS)
    sheets = page.query_selector_all(".sheet")
    if not sheets:
        return None

    # MỌI tờ, không chỉ tờ đầu. Một chứng từ nhiều trang là nhiều `.sheet`, và
    # bản trước chụp `sheets[0]` rồi bỏ phần còn lại -- model viết ba tờ thì hai
    # tờ biến mất không một dòng nào nói.
    pages = []
    for number, element in enumerate(sheets, start=1):
        shot = element.screenshot(type="png")
        image = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
        pages.append((number, image))

    # MỘT DÒNG CHẢY DÀI, CẮT THEO BỀ DÀI A4.
    #
    # Khi model viết đúng MỘT `.sheet` mà nó cao hơn một khổ A4, đấy là một
    # dòng chảy liên tục -- và giấy thật sang trang vì chữ chảy hết tờ, không
    # vì người viết quyết định sang trang. Cắt ở đây.
    #
    # Model tự mở `.sheet` mới thì nó mở tuỳ hứng: đo trên pilot8,
    # `phieu_bao_chuyen_hang_0019` ra sáu tờ [150, 43, 48, 13, 17, 23] từ,
    # đầy 80% rồi 18% 16% 14% 17% 15%. Tờ thứ tư mười ba từ.
    cuts: list[float] = []
    cuts: list[float] = []
    page_h = 0.0
    if len(pages) == 1:
        tall = pages[0][1]
        page_h = tall.shape[1] * A4_RATIO
        # Khoảng trống giữa KHỐI, không giữa DÒNG.
        #
        # Bản trước lấy `rects["words"]`, nên khe giữa hai dòng chữ trong cùng
        # một thẻ cũng tính là chỗ cắt được. Đo trên tờ hợp đồng: nhát cắt rơi
        # đúng vào giữa ba thẻ tổng, thẻ bị xẻ đôi -- nửa trên ở tờ 1, nửa dưới
        # ở tờ 2, và vùng của nó gán về tờ 1 theo trung điểm nên tờ 2 có chữ mà
        # không có hộp nào.
        #
        # Vùng model tự khai và bảng là những thứ KHÔNG được cắt ngang. Dòng
        # chữ trong một đoạn văn thì cắt được -- giấy thật vẫn ngắt đoạn giữa
        # trang. Nên gộp hai nguồn: khối làm rào, từ làm chỗ cắt mịn khi giữa
        # hai khối là một đoạn văn dài.
        span_of = (lambda r: (r["y"] * SCALE, (r["y"] + r["h"]) * SCALE))
        cells = [r for r in (regions or []) if r.get("h", 0) > 0]
        # RÀO: vùng nguyên khối model tự khai, cộng MỌI bảng. Một ô bảng có
        # `row`, nên cả bảng là rào và ranh giới hàng là chỗ xẻ khi buộc phải.
        barriers = [span_of(r) for r in (zones or [])
                    if r.get("h", 0) > 0 and str(r.get("label") or "") in ATOMIC]
        if cells:
            tops = [span_of(r) for r in cells]
            barriers.append((min(a for a, _ in tops), max(b for _, b in tops)))
        barriers = _merge(barriers)
        # CHỖ XẺ MỊN trong một rào quá cao: mép dưới của từng hàng ô bảng, và
        # mép dưới của từng dòng chữ.
        splits = sorted({round(span_of(r)[1], 1) for r in cells}
                        | {round(span_of(r)[1], 1)
                           for r in (rects["words"] or []) if r.get("h", 0) > 0})
        # KHE: giữa mọi khối, kể cả vùng chảy được -- nhưng khe nằm trong rào
        # đã bị `cut_lines` loại, nên gộp cả hai nguồn ở đây là an toàn.
        flow = [span_of(r) for r in (list(zones or []) + cells)
                if r.get("h", 0) > 0]
        gaps = gaps_between(flow) + [(s, s) for s in splits]
        usable = page_h * (1 - (TOP_MM + BOTTOM_MM) / 297.0)
        cuts = cut_lines(tall.shape[0], usable, gaps,
                         barriers=barriers, splits=splits)
        if cuts:
            # `bounds`, không phải `edges`: dưới kia có một `edges` khác, dùng
            # `inf` làm mép cuối để LỌC. Cái này cắt ẢNH nên mép cuối phải là
            # chiều cao thật.
            bounds = [0.0, *cuts, float(tall.shape[0])]
            pages = [(i + 1, tall[int(bounds[i]):int(bounds[i + 1])])
                     for i in range(len(bounds) - 1)]
            # Lát mỏng dưới tám điểm ảnh là mẩu vụn của phép dàn trang, không
            # phải một tờ giấy. Bỏ trước khi `to_a4` đệm nó thành một tờ trắng.
            pages = [(n, img) for n, img in pages if img.shape[0] > 8]
            # LỀ TRÊN cho tờ thứ hai trở đi: đệm màu giấy lên đầu lát.
            top = int(round(page_h * TOP_MM / 297.0))
            pages = [(n, img if n == 1 else _pad_top(img, top))
                     for n, img in pages]
    # Mọi tờ về đúng khổ A4 -- lát cuối của dòng chảy, và cả tài liệu một tờ
    # ngắn hơn một trang.
    pages = [(n, to_a4(img)) for n, img in pages]

    number, image = pages[0]
    height, width = image.shape[:2]

    # Khi đã cắt theo chiều cao, `page` mà trình duyệt gắn không còn nghĩa --
    # mọi thứ đều thuộc `.sheet` số một. Chọn theo Y, và DỜI gốc toạ độ về
    # đỉnh lát: hộp của tờ hai phải đo từ mép trên tờ hai.
    edges = [0.0, *cuts, float("inf")] if cuts else []

    def slice_of(num: int) -> tuple[float, float]:
        return (edges[num - 1], edges[num]) if edges else (0.0, float("inf"))

    # `rects["fields"]` KHÔNG mang toạ độ -- khoá của nó là
    # `['field', 'ink', 'key', 'kind', 'page', 'role', 'text']`. Chọn nó theo Y
    # thì mọi trường rơi về tờ một (`y` mặc định 0), và tài liệu nhiều trang
    # mất sạch KIE từ tờ hai trở đi.
    #
    # Nó nối với các run qua chỉ số `field`, nên hỏi các run xem trường ấy được
    # in ở tờ nào. Mọi loại khác (`cells`, `words`, `regions`, `graphics`,
    # `zones`) đều có `y`+`h` -- đã kiểm từng cái.
    field_page: dict[int, int] = {}
    if cuts:
        for run in rects["words"] or []:
            index = run.get("field")
            if index is None or index in field_page:
                continue
            mid = (run.get("y", 0) + run.get("h", 0) / 2) * SCALE
            for num in range(1, len(edges)):
                if edges[num - 1] <= mid < edges[num]:
                    field_page[int(index)] = num
                    break

    top_pad = (page_h * TOP_MM / 297.0) if cuts else 0.0

    def take(items, num: int, whole: bool = False):
        """`whole=True`: giữ mọi phần tử PHỦ lên tờ này, không chỉ phần tử có
        trung điểm nằm trong nó.

        BẬT cho `zones` và `regions`. Lần trước bật thì `record.py::build` chỉ
        giữ 8 trên 31 vùng, vì nó bỏ mọi vùng không còn chữ CHƯA AI NHẬN -- nên
        vùng bọc xử lý trước nuốt hết chữ của vùng con. Đã sửa ở đó: xếp vùng
        theo diện tích tăng dần, và một vùng có nội dung thì được ghi dù nội
        dung ấy thuộc về vùng con.

        Một VÙNG vắt qua nhát cắt thuộc về cả hai tờ -- nửa trên ở tờ này, nửa
        dưới ở tờ kia, và trang nào cũng phải có hộp của nó. Gán theo trung
        điểm thì nó rơi vào đúng một tờ, rồi `clip_to_page` xoá nốt phần thò ra
        ở tờ ấy: đo được trên tờ hợp đồng, `Section-Header` "Phần IV" đo được 5
        vùng mà chỉ 4 vào bản ghi, và ba thẻ tổng biến mất khỏi CẢ HAI tờ.

        Một TỪ thì không: nó nằm gọn trên một dòng, và một chữ bị xẻ đôi theo
        chiều ngang thân chữ là chuyện phép dàn trang không sinh ra."""
        if not cuts:
            return [i for i in items or [] if int(i.get("page", 1) or 1) == num]
        lo, hi = slice_of(num)
        out = []
        for i in items or []:
            if "y" not in i:
                if field_page.get(i.get("field"), 1) == num:
                    out.append(dict(i))
                continue
            top = i.get("y", 0) * SCALE
            bottom = top + i.get("h", 0) * SCALE
            mid = (top + bottom) / 2
            hit = (top < hi and bottom > lo) if whole else (lo <= mid < hi)
            if hit:
                # Trừ gốc lát, rồi CỘNG lề trên -- ảnh đã được đệm bấy nhiêu.
                shift = lo / SCALE - (0 if num == 1 else top_pad / SCALE)
                out.append({**i, "y": i.get("y", 0) - shift})
        return out

    on = lambda items, whole=False: take(items, 1, whole)   # noqa: E731
    sheet = {
        "filename": f"{stem}.jpg", "width": width, "height": height,
        "boxes": clip_to_page(quads_from_rects(on(rects["cells"]), SCALE, 1.0),
                              width, height),
        "words": clip_to_page(quads_from_rects(on(rects["words"]), SCALE, 1.0),
                              width, height),
        "cells": clip_to_page(regions_from_rects(on(regions, True), SCALE, 1.0),
                              width, height),
        "graphics": clip_to_page(graphics_from_rects(on(graphics), SCALE, 1.0),
                                 width, height),
        "zones": tighten(
            clip_to_page(zones_from_rects(on(zones, True), SCALE, 1.0), width, height),
            clip_to_page(quads_from_rects(on(rects["words"]), SCALE, 1.0),
                         width, height)),
        "fields": on(rects.get("fields") or []),
    }
    others = []
    for num, img in pages[1:]:
        pick = lambda items, whole=False, n=num: take(items, n, whole)  # noqa: E731
        h2, w2 = img.shape[:2]
        others.append({
            "filename": f"{stem}_p{num}.jpg", "width": w2, "height": h2,
            "boxes": clip_to_page(quads_from_rects(pick(rects["cells"]), SCALE, 1.0), w2, h2),
            "words": clip_to_page(quads_from_rects(pick(rects["words"]), SCALE, 1.0), w2, h2),
            "cells": clip_to_page(regions_from_rects(pick(regions, True), SCALE, 1.0), w2, h2),
            "graphics": clip_to_page(graphics_from_rects(pick(graphics), SCALE, 1.0), w2, h2),
            "zones": tighten(
                clip_to_page(zones_from_rects(pick(zones, True), SCALE, 1.0), w2, h2),
                clip_to_page(quads_from_rects(pick(rects["words"]), SCALE, 1.0),
                             w2, h2)),
            "fields": pick(rects.get("fields") or []),
        })
    record = R.build(filename=f"{stem}.jpg", width=width, height=height,
                     parser="html", ink="print", extracted={},
                     seed=0, layout=str(declared.get("archetype")
                                or declared.get("loai_tai_lieu") or "llm"),
                     sheets=[sheet, *others])
    return {"record": record, "image": image,
            "images": [img for _n, img in pages]}


class Drawer:
    """Một trình duyệt mở sẵn, vẽ từng tài liệu một.

    Tách ra khỏi `run()` để `agent/compose_page.py` VẼ NGAY khi model vừa viết
    xong một tờ, thay vì đợi cả lượt rồi mới chạy một lệnh thứ hai. Một lượt
    hai mươi tư tờ trước đây phải xong hết mới có tấm ảnh đầu tiên -- và nếu
    lượt ấy gãy giữa chừng thì không có tấm nào.

    Mở trình duyệt là việc đắt (khoảng một giây) nên mở MỘT lần rồi dùng lại
    cho mọi tài liệu, đúng như `run()` vẫn làm."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rows: list[dict] = []
        self._play = self._browser = self._page = None
        for name in ("images", "layout_boxes", "word_boxes", "records",
                     "rejected_boxes", "visualize_kie"):
            (root / name).mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> "Drawer":
        from playwright.sync_api import sync_playwright   # noqa: PLC0415

        self._play = sync_playwright().start()
        self._browser = self._play.chromium.launch(
            args=["--font-render-hinting=none"])
        self._page = self._browser.new_page(device_scale_factor=SCALE)
        return self

    def __exit__(self, *_exc: object) -> None:
        for closer in (getattr(self._page, "close", None),
                       getattr(self._browser, "close", None),
                       getattr(self._play, "stop", None)):
            try:
                if closer:
                    closer()
            except Exception:                               # noqa: BLE001
                pass

    def measure(self, html: str, stem: str, archetype: str = "llm") -> dict | None:
        """Dàn trang CHỈ ĐỂ ĐO. Không ghi một tệp nào, không dựng KIE.

        `agent/compose_page.py` cần `layout_annotations` -- chỗ mực THẬT rơi
        xuống -- để biết tờ vừa sinh có trùng bố cục với một tờ gần đây
        không, và nó cần biết điều ấy TRƯỚC khi nhận tờ giấy. `draw()` dưới
        đây trả lời đúng câu hỏi ấy nhưng kèm theo mười hai tệp trên đĩa:
        gọi nó để đo rồi xoá là ghi ảnh của một tờ sắp bị loại vào chính thư
        mục người ta sẽ đưa vào tập huấn luyện.

        Nên tách phần ĐO ra khỏi phần GHI. `draw_one()` đã là phần đo -- nó
        dựng bản ghi rồi trả về, không chạm đĩa; hàm này chỉ là tên gọi cho
        việc dùng nó một mình. Không có luật nào mới ở đây, và đặc biệt
        không có phép đo hộp thứ hai: hộp vẫn do đúng Chromium ấy sinh ra,
        một lần, qua đúng `draw_one()` ấy (AGENTS.md luật 1).

        `None` khi trang không dàn ra được -- caller phải đọc nó là "chưa
        biết", không phải "không trùng"."""
        try:
            got = draw_one(self._page, html, stem, {"archetype": archetype})
        except Exception:                                   # noqa: BLE001
            return None
        return got["record"] if got else None

    def draw(self, path: Path, passed: bool) -> tuple[str, bool]:
        """Vẽ một tài liệu. `(dòng tóm tắt để in, vẽ được hay không)`.

        "Vẽ được" KHÁC "qua cổng": một tờ trượt cổng vẫn vẽ ra ảnh, và ảnh
        ấy chính là thứ để đọc xem model sai ở đâu."""
        root, stem = self.root, path.stem
        declared_path = root / "declared" / f"{stem}.json"
        declared = (json.loads(declared_path.read_text(encoding="utf-8"))
                    if declared_path.is_file() else {})
        try:
            got = draw_one(self._page, path.read_text(encoding="utf-8"),
                           stem, declared)
        except Exception as error:                          # noqa: BLE001
            return (f"  ✗ {stem:34s} {type(error).__name__}: "
                    f"{str(error)[:60]}", False)
        if got is None:
            return f"  ✗ {stem:34s} không có phần tử `.sheet` nào", False

        record, kind = got["record"], _slug(
            declared.get("archetype") or declared.get("loai_tai_lieu") or "llm")
        total = len(got["images"])
        for folder in ("images", "records", "layout_boxes", "word_boxes",
                       "html", "rejected_boxes", "visualize_kie"):
            (root / folder / kind).mkdir(parents=True, exist_ok=True)
        source = path.read_text(encoding="utf-8")
        # KIE ĐẦY ĐỦ NGAY LÚC VẼ, không đợi `finish()` chạy `derive` ở cuối cả
        # lượt. Người xem cần thấy mũi tên khoá->giá trị của MỘT tờ ngay khi
        # tờ ấy vừa xong -- đợi hết lượt (có thể hàng chục phút) mới có ảnh
        # đầu tiên là đúng cái giá `Artist` (lớp gọi hàm này) sinh ra để né.
        # Bản rút gọn: không đổi giọng mô tả, không dựng lại `kie.schema` --
        # những việc đó vẫn là việc của `finish()`/`derive.py` chạy một lần
        # cho cả lô, khi nó chạy.
        try:
            full_pairs, kie_counts = kie_complete(record, source)
        except Exception:                                    # noqa: BLE001
            full_pairs, kie_counts = [], {}
        # GHI LẠI VÀO CHÍNH `record`, không chỉ dùng để vẽ. Trước đây
        # `full_pairs` chỉ tồn tại trong bộ nhớ cho một tấm ảnh rồi mất --
        # `records/*.json` ghi ra đĩa vẫn giữ `kie.pairs` NGHÈO của `pipeline/
        # record.py::build()` (label-kề-nhau, bỏ sót toàn bộ ô bảng) cho tới
        # khi `derive.py` chạy. Một lượt không tới lượt `derive` (`--no-draw`
        # rồi vẽ tay bằng `draw_llm` đơn, batch bị ngắt giữa chừng, hay
        # `finish(skip_derive=True)`) thì JSON nằm lại mãi ở dạng nghèo đó --
        # đo được đúng ca này trên `data/rerun-unwrap`: `kie.pairs` chỉ 4 cặp
        # (MST/ĐT/Số hiệu/Ngày), không cặp nào cho bảng, dù bảng có `data-row`/
        # `data-col` đầy đủ và `complete()` chạy tay ra đúng 153 cặp kể cả
        # `tc1_r1` khớp thẳng dòng "Nguyễn Văn Hùng". Ghi thẳng ở đây thì JSON
        # trên đĩa ĐÚNG NGAY TỪ ĐẦU, không phụ thuộc có chạy `derive` sau hay
        # không -- `derive.py` vẫn ghi đè lại bằng bản đổi giọng mô tả nếu nó
        # chạy, không xung đột.
        # ĐỔI GIỌNG MÔ TẢ NGAY Ở ĐÂY, cùng lẽ với `full_pairs` ở trên. Câu tả
        # gốc do `design.py`/`kie_full.py` sinh ra là MỘT câu cho mỗi kind, nên
        # nó lặp: đo trên `data/thu1k` (bộ vẽ trước thay đổi này) 8 564 câu tả
        # chỉ có 171 câu khác nhau -- 2,0% -- và "Questionnaire tick box
        # printed on the document." một mình 671 lần. Một mô hình học trên bộ
        # ấy học thuộc câu chứ không học nghĩa.
        #
        # Luật nằm ở `phrasing.voice_record`, không chép lại ở đây: `derive.py`
        # gọi đúng hàm ấy, và hàm ấy luỹ đẳng nên chạy cả hai lần vẫn ra một
        # kết quả. Hỏng lặng lẽ thì thôi đa dạng, không thôi mô tả.
        try:
            voice_record(record, full_pairs, stem=stem)
        except Exception:                                    # noqa: BLE001
            pass
        # BA TẦNG, gắn lên từng cặp TRƯỚC khi bản ghi ra đĩa.
        #
        # Gắn ở đây chứ không ở `export.py` vì bản ghi là thứ tồn tại lâu:
        # một cặp `staging` phải mang dấu ấy trong chính `records/*.json`, để
        # ai đọc bản ghi sáu tháng sau cũng thấy cái tên ấy chưa được duyệt.
        # `export.py` chỉ việc ĐỌC dấu và bỏ qua, không xếp tầng lại -- xếp
        # hai lần là hai người dựng một luật.
        try:
            record["kie_tiers"] = FT.mark_pairs(
                full_pairs, doc_type=str(declared.get("archetype") or ""),
                doc_title=str(declared.get("doc_title") or ""))
        except Exception as error:                           # noqa: BLE001
            # KÊU, không nuốt. Bản ghi thiếu dấu tầng vẫn vẽ ra được, nhưng
            # nó sẽ đi vào bộ chính với mọi cặp không ai duyệt -- đúng thứ
            # tầng này sinh ra để chặn, nên dòng này phải đọc được trong log.
            print(f"[tầng] {stem}: không xếp tầng được -- {error}")
        record.setdefault("kie", {})["pairs"] = full_pairs
        if kie_counts:
            record["kie"]["coverage"] = kie_counts
        for num, img in enumerate(got["images"], start=1):
            name = stem if num == 1 else f"{stem}_p{num}"
            cv2.imwrite(str(root / "images" / kind / f"{name}.jpg"), img,
                        [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            # MỘT bản ghi cho MỖI TỜ, đúng như `synthgen/draw.py::write`:
            # người cầm `..._p2.jpg` phải tìm thấy bản ghi mô tả tài liệu mà
            # tờ ấy thuộc về, không phải một thư mục 404.
            (root / "records" / kind / f"{name}.json").write_text(
                json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "html" / kind / f"{name}.html").write_text(
                source, encoding="utf-8")
            h2, w2 = img.shape[:2]
            self.rows.append({
                "stem": name, "archetype": kind, "document": stem,
                "page_number": num, "pages_in_document": total,
                "width": w2, "height": h2,
                "images": f"images/{kind}/{name}.jpg",
                "record": f"records/{kind}/{name}.json",
                "html": f"html/{kind}/{name}.html",
                "layout_boxes_image": f"layout_boxes/{kind}/{name}.jpg",
                "word_boxes_image": f"word_boxes/{kind}/{name}.jpg",
                "visualize_kie_image": f"visualize_kie/{kind}/{name}.jpg",
                "fill": 1.0,
                "kie_pairs": sum(1 for p in full_pairs
                                if int(p.get("page_number", 1) or 1) == num),
                "llm_passed_gate": passed,
            })

        layout = record.get("layout_annotations") or []
        words = record.get("word_annotations") or []
        # Trang trượt vẽ vào `rejected_boxes/`, không lẫn vào thư mục của trang
        # sạch: một thư mục lẫn trang hỏng là một thư mục không ai dám đưa vào
        # tập huấn luyện.
        target = "layout_boxes" if passed else "rejected_boxes"
        for num, img in enumerate(got["images"], start=1):
            name = stem if num == 1 else f"{stem}_p{num}"
            cv2.imwrite(
                str(root / target / kind / f"{name}.jpg"),
                O.layout(img.copy(),
                         [a for a in layout
                          if int(a.get("page_number", 1) or 1) == num]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
            cv2.imwrite(
                str(root / "word_boxes" / kind / f"{name}.jpg"),
                O.words(img.copy(),
                        [w for w in words
                         if int(w.get("page_number", 1) or 1) == num]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
            cv2.imwrite(
                str(root / "visualize_kie" / kind / f"{name}.jpg"),
                O.kie(img.copy(), full_pairs, num),
                [cv2.IMWRITE_JPEG_QUALITY, 88])
        kie_total = len(full_pairs)
        why = declared.get("why") or []
        asked = int(declared.get("sheets_asked") or 0)
        # "xin 4 -> cắt ra 2" là dấu hiệu model viết THIẾU: trang qua mọi cổng,
        # sạch sẽ, chỉ ngắn hơn nửa lượng chữ được nhờ. Từ khi máy cắt theo bề
        # dài A4, đây là cách DUY NHẤT thấy chuyện ấy -- không còn `.sheet`
        # rỗng nào để đếm.
        note = f", {total} tờ" if total > 1 else ""
        if asked and asked != total:
            note = f", xin {asked} -> cắt ra {total} tờ"
        return (f"  {'✓' if passed else '✗'} {stem:34s} {len(layout):3d} vùng, "
                f"{len(words):4d} hộp từ, {kie_total:3d} cặp KIE{note}"
                + (f"  — {why[0][:48]}" if why else ""), True)


def finish(root: Path, rows: list[dict], skip_derive: bool = False) -> None:
    """Ghi manifest rồi chạy `derive`. Gọi sau khi vẽ xong mọi tài liệu."""
    # MANIFEST đúng hình dạng một lượt chạy synthgen. Nhờ nó `derive.py` chạy
    # được y nguyên trên thư mục này: `json/` gộp theo tài liệu, `markdown/`,
    # `visualize_kie/`, `kie_schemas/`, `sample/` -- người xem trang model viết
    # có đúng bộ file như trang engine vẽ, không phải học một cách bày thứ hai.
    (root / "manifest.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8")
    if not rows or skip_derive:
        return
    print()
    from synthgen.derive import main as derive_main          # noqa: PLC0415

    argv = sys.argv
    sys.argv = ["derive", str(root), "--workers", "4"]
    try:
        derive_main()
    finally:
        sys.argv = argv


def run(root: Path, only: str, skip_derive: bool = False) -> int:
    folders = (["html", "rejected"] if only == "all"
               else [only] if only in ("html", "rejected") else [])
    if not folders:
        print(f"--only chỉ nhận html, rejected hoặc all; không nhận {only!r}")
        return 1
    jobs: list[tuple[Path, bool]] = []
    for name in folders:
        for path in sorted((root / name).glob("*.html")):
            jobs.append((path, name == "html"))
    if not jobs:
        print(f"không có trang nào trong {root}/{{{', '.join(folders)}}}")
        return 1

    print(f"[vẽ] {len(jobs)} trang ({sum(1 for _, ok in jobs if ok)} qua cổng, "
          f"{sum(1 for _, ok in jobs if not ok)} trượt)")
    drawn = 0
    with Drawer(root) as drawer:
        for path, passed in jobs:
            line, ok = drawer.draw(path, passed)
            drawn += ok
            print(line)
        rows = drawer.rows
    print(f"\n[vẽ] {drawn} trang vẽ được, {len(jobs) - drawn} không")
    print(f"[vẽ] trang qua cổng -> {root}/layout_boxes, "
          f"trang trượt -> {root}/rejected_boxes")
    finish(root, rows, skip_derive)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục `agent.compose_page` để lại")
    parser.add_argument("--only", default="all",
                        help="html | rejected | all (mặc định)")
    parser.add_argument("--no-derive", action="store_true",
                        help="chỉ vẽ, không chạy bước derive (không có json gộp, "
                             "markdown, visualize_kie, kie_schemas)")
    args = parser.parse_args()
    return run(args.run.resolve(), args.only, args.no_derive)


if __name__ == "__main__":
    raise SystemExit(main())
