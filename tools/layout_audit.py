"""Soát chất lượng BỐ CỤC của một lượt chạy đã render xong.

    python tools/layout_audit.py data/llm200/.shards/shard-0001
    python tools/layout_audit.py data/llm200 --recursive --json audit.json --top 20

`check_boxes.py` hỏi "hộp có nằm đúng chỗ có mực không". Câu ấy trả lời được
bằng chính tấm ảnh. Còn bốn câu dưới đây thì không: chúng chỉ lộ ra khi đặt cả
lượt chạy cạnh nhau, mà không ai đặt 200 tờ cạnh nhau bằng mắt.

1. **Trùng bố cục** — hai trang có bộ khung hộp gần như y hệt. Chữ ký đo được
   là nhị phân và không phụ thuộc nội dung: đưa hộp về toạ độ [0,1] theo bề
   rộng/cao trang, rời rạc hoá thành lưới, lấy "ô nào có mực". Hai trang trùng
   khi Jaccard của hai chữ ký vượt ngưỡng. Báo theo cụm, vì luật của lượt chạy
   là **một kiểu không lặp quá hai lần** — nên cụm 3 thành viên trở lên mới là
   vi phạm, cụm 2 chỉ là ghi nhận.
2. **Trang rỗng / thưa** — phần diện tích trang được hộp phủ, và mực chạy tới
   đâu theo chiều cao. Một tờ mà 60% giấy phía dưới trống rỗng vẫn là một tờ
   hợp lệ, nhưng nó dạy mô hình về giấy chứ không dạy về bố cục.
3. **Hộp chồng nhau** — hai block khác nhau cùng mô tả một vùng pixel. Đo trên
   **quad chứ không trên bbox**: xem phần "Vì sao quad" bên dưới.
4. **Hộp ra ngoài khung / diện tích 0** — nhãn không mô tả pixel nào cả.

## Vì sao quad, không phải bbox

Trang bị vênh (`warped`, `folded`, thẻ in ngang) có dòng chữ chạy chéo. Hộp
trục-thẳng của một dòng chéo cao gấp nhiều lần chính dòng ấy, nên hai dòng
liền nhau chồng lấn tới IoU 0.64 trong khi hai vệt mực **không chạm nhau**.
Đo trên bbox thì mọi trang vênh đều bị báo sai; đo trên quad thì đúng bằng 0.
Chữ ký bố cục và phép đo độ phủ cũng tô theo quad, vì cùng một lý do: trên
trang vênh, bbox thổi phồng diện tích mực.

Phần chênh ấy tự nó là một con số đáng nhìn, nên nó được báo riêng ở mục
"chẩn đoán": tỷ lệ `diện tích quad / diện tích bbox` của trang. Tỷ lệ 0.45 có
nghĩa hộp trục-thẳng rộng gấp đôi vệt mực thật — ai huấn luyện trên `bbox`
thay vì `quad` của lượt chạy ấy đang học hộp phồng.

## Giới hạn đã biết

Phép đo Jaccard là bộ dò **độ chính xác cao, độ phủ thấp**. Đối chiếu với
`synthesis.json` của chính shard-0001: 30 cặp trang dùng cùng một `layout`,
Jaccard của chúng trải từ 0.28 đến 0.99 — cùng bố cục nhưng khác độ dài nội
dung thì khung hộp khác nhau thật, không ngưỡng nào tách được. Ngược lại, ở
ngưỡng cao thì không có báo nhầm nào: mọi cặp vượt 0.78 đều đúng là cùng
`layout`. Nên hình học trả lời "hai trang này gần như một tờ", chứ không trả
lời "kiểu này đã dùng mấy lần" — câu sau đọc thẳng từ công thức trong
`synthesis.json`, và được báo cùng chỗ ở mục 1.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

# --- Chữ ký bố cục ----------------------------------------------------------

# Lưới chữ ký. 32x32 trên tờ A4 là ô ~2.4mm: đủ mịn để phân biệt hai cột với
# một cột, đủ thô để hai tờ cùng phôi nhưng lệch dòng vẫn khớp nhau. Đo trên
# shard-0001: ở 32, cặp KHÁC bố cục cao nhất chỉ tới 0.72 — còn cách ngưỡng
# 0.90 một quãng an toàn. Lưới thô hơn (16) bắt được nhiều cặp cùng phôi hơn
# nhưng cặp khác phôi đã chạm 0.88, tức là sát mép báo nhầm.
SIGNATURE_GRID = 32

# Ngưỡng "gần như y hệt". Trên shard-0001 nó không báo nhầm cặp nào.
DUP_JACCARD = 0.90

# Tầng theo dõi: chưa gọi là trùng, nhưng đáng liếc. Chọn 0.78 vì đó là mức
# mà mọi cặp vượt qua đều đúng là cùng `layout` theo công thức đã ghi.
NEAR_JACCARD = 0.78

# Luật của lượt chạy: một kiểu không lặp quá hai lần. Cụm đông hơn số này là
# vi phạm, không phải ghi nhận.
MAX_REPEATS = 2

# --- Trang rỗng / thưa ------------------------------------------------------

# Độ mịn của tấm mặt nạ dùng để tính diện tích phủ. 256x256 cho ô ~7px trên
# tờ cao 1800px, nên một dòng chữ cao 25px vẫn bắt được vài hàng tâm ô; thô
# hơn nữa thì dòng mảnh lọt qua khe và trang bị chấm là thưa oan.
COVERAGE_RASTER = 256

# Hợp của mọi quad phủ dưới 5% mặt giấy nghĩa là hơn 95% số pixel không mang
# nhãn nào. Đo trên shard-0001: trang trung vị phủ 14.5%, trang đặc nhất 34%,
# nên 5% là khoảng một phần ba lượng mực của một tờ bình thường — chỗ mà tờ
# giấy chủ yếu là lề. Ngưỡng này tính trên **quad**; nếu tô theo bbox thì cùng
# một tập trang cho con số cao gần gấp rưỡi và ngưỡng phải khác.
MIN_INK_COVERAGE = 0.05

# Mực dừng trước 55% chiều cao tờ giấy nghĩa là gần nửa dưới bỏ trắng — dấu
# hiệu khổ giấy không khớp lượng nội dung, chứ không phải một tờ ngắn tự nhiên.
MIN_BOTTOM_REACH = 0.55

# --- Hộp chồng nhau ---------------------------------------------------------

# Hai hộp nhãn ở IoU 0.5 là hai hộp mà bất kỳ bộ dò nào cũng không tách nổi:
# đó đúng là ngưỡng khớp của COCO/DocLayNet, nên một trong hai chắc chắn sai.
OVERLAP_IOU = 0.50

# Tầng theo dõi, để thấy cả những chồng lấn chưa tới mức trên.
OVERLAP_IOU_WATCH = 0.30

# Chồng lấn hợp lệ giữa block và vùng chứa nó: hộp nhỏ nằm gọn (>=98%) trong
# hộp lớn, và hộp lớn phải lớn thật (hộp nhỏ chiếm dưới 80% diện tích). Thiếu
# vế sau thì hai hộp gần trùng khít cũng bị coi là quan hệ chứa — mà đó mới
# đúng là lỗi cần báo.
CONTAINMENT_COVER = 0.98
CONTAINMENT_AREA_RATIO = 0.80

# Lớp mực đè lên lớp in là chuyện thiết kế, không phải lỗi: con dấu đóng chồng
# chữ ký, nét tay điền vào dòng kẻ chấm. Lấy từ trường `ink` của chính bản ghi
# nên không phải đoán theo tên trường nào.
OVERLAY_INKS = ("stamp", "hand")

# --- Khung và suy biến ------------------------------------------------------

# Toạ độ hộp làm tròn về pixel, nên lố 1px là chuyện làm tròn chứ không phải
# hộp rơi khỏi ảnh.
FRAME_TOLERANCE_PX = 1.0

# Dưới 1px vuông thì không có pixel nào để học.
MIN_BOX_AREA_PX = 1.0

# Bản ghi khai kiểu toạ độ; gặp kiểu lạ thì báo ra chứ không đọc bừa.
EXPECTED_BBOX_MODE = "xyxy_pixel"

# --- Chẩn đoán --------------------------------------------------------------

# Trang nghiêng quá 1 độ thì bbox bắt đầu phồng thấy rõ; báo ra để người đọc
# biết vì sao mục 3 của trang ấy im lặng dù nhìn ảnh thấy hộp đè nhau.
ROTATION_NOTE_DEG = 1.0

# Quad chiếm dưới 70% bbox: hộp trục-thẳng rộng hơn vệt mực khoảng 1.4 lần trở
# lên. Không phải lỗi, nhưng ai train trên `bbox` cần biết.
BOX_INFLATION_WARN = 0.70


# ---------------------------------------------------------------------------
# Hình học
# ---------------------------------------------------------------------------

def polygon_area(points) -> float:
    """Diện tích đa giác theo công thức dây giày, luôn không âm."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return 0.0
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def clip_polygon(subject, clipper):
    """Cắt `subject` bằng `clipper` lồi (Sutherland–Hodgman).

    Quad do bộ dựng trang sinh ra là tứ giác lồi, nên thuật toán này đủ; nó
    được chọn thay vì shapely để công cụ chạy bằng thư viện chuẩn + numpy.
    """
    output = [tuple(map(float, p)) for p in subject]
    edges = [tuple(map(float, p)) for p in clipper]
    if len(output) < 3 or len(edges) < 3:
        return []

    # Sutherland–Hodgman giữ nửa mặt phẳng bên trái mỗi cạnh, nên clipper phải
    # quay ngược chiều kim đồng hồ; quad trong bản ghi quay theo chiều kia.
    signed = 0.0
    for i in range(len(edges)):
        x1, y1 = edges[i]
        x2, y2 = edges[(i + 1) % len(edges)]
        signed += x1 * y2 - x2 * y1
    if signed < 0:
        edges = edges[::-1]

    for i in range(len(edges)):
        if not output:
            return []
        ax, ay = edges[i]
        bx, by = edges[(i + 1) % len(edges)]
        ex, ey = bx - ax, by - ay
        clipped = []
        count = len(output)
        for k in range(count):
            px, py = output[k]
            qx, qy = output[(k + 1) % count]
            p_in = ex * (py - ay) - ey * (px - ax) >= 0
            q_in = ex * (qy - ay) - ey * (qx - ax) >= 0
            if p_in:
                clipped.append((px, py))
            if p_in != q_in:
                dx, dy = qx - px, qy - py
                denom = ex * dy - ey * dx
                if abs(denom) > 1e-12:
                    t = (ey * (px - ax) - ex * (py - ay)) / denom
                    clipped.append((px + t * dx, py + t * dy))
        output = clipped
    return output


def polygon_iou(a, b, area_a: float, area_b: float) -> float:
    inter = polygon_area(clip_polygon(a, b))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def fill_polygon(mask, points, width: float, height: float) -> None:
    """Tô đa giác vào mặt nạ vuông bằng phép thử chẵn–lẻ trên tâm ô."""
    n = mask.shape[0]
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3 or width <= 0 or height <= 0:
        return
    col0 = max(0, int(math.floor(pts[:, 0].min() / width * n)))
    col1 = min(n, int(math.ceil(pts[:, 0].max() / width * n)))
    row0 = max(0, int(math.floor(pts[:, 1].min() / height * n)))
    row1 = min(n, int(math.ceil(pts[:, 1].max() / height * n)))
    if col1 <= col0 or row1 <= row0:
        return

    gx, gy = np.meshgrid((np.arange(col0, col1) + 0.5) * width / n,
                         (np.arange(row0, row1) + 0.5) * height / n)
    inside = np.zeros(gx.shape, dtype=bool)
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        crosses = (y1 > gy) != (y2 > gy)
        with np.errstate(divide="ignore", invalid="ignore"):
            cut = (x2 - x1) * (gy - y1) / (y2 - y1) + x1
        inside ^= crosses & (gx < np.nan_to_num(cut, nan=-np.inf, posinf=np.inf,
                                                neginf=-np.inf))
    mask[row0:row1, col0:col1] |= inside


# ---------------------------------------------------------------------------
# Đọc bản ghi
# ---------------------------------------------------------------------------

def is_record(data) -> bool:
    """Bản ghi một trang đã render, phân biệt với `synthesis.json` cùng thư mục.

    Công thức của lượt chạy cũng có khoá `pages`, nhưng của nó là dict tra theo
    tên ảnh; của bản ghi là danh sách trang. Phân biệt bằng đúng chỗ ấy chứ
    không bằng tên file, để công cụ không vỡ khi lượt chạy đổi cách đặt tên.
    """
    if not isinstance(data, dict):
        return False
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    return all(isinstance(p, dict) and p.get("width") and p.get("height")
               for p in pages)


def load_records(root: Path, recursive: bool):
    """(đường dẫn, bản ghi) của mọi trang trong thư mục, đã bỏ bản sao.

    Một lượt chạy giữ cùng một trang ở hai chỗ (shard và thư mục kết quả). Hai
    bản sao ấy mang cùng `job_id`, nên chúng bị gộp thay vì bị báo là hai trang
    trùng bố cục — báo thế thì đúng số nhưng vô nghĩa.
    """
    paths = sorted(root.rglob("*.json") if recursive else root.glob("*.json"))
    records, skipped, seen = [], [], {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            skipped.append((path, f"không đọc được JSON: {error}"))
            continue
        if not is_record(data):
            skipped.append((path, "không phải bản ghi trang"))
            continue
        job = data.get("job_id")
        if job and job in seen:
            skipped.append((path, f"bản sao của {seen[job].name}"))
            continue
        if job:
            seen[job] = path
        records.append((path, data))
    return records, skipped


def block_polygon(block):
    """Quad nếu bản ghi có, bbox nếu không — cùng một hình dùng khắp file."""
    quad = block.get("quad")
    if isinstance(quad, list) and len(quad) >= 3:
        pts = [(float(p[0]), float(p[1])) for p in quad
               if isinstance(p, (list, tuple)) and len(p) >= 2]
        # Quad khép kín lặp lại đỉnh đầu ở cuối; bỏ đi để dây giày không hụt.
        if len(pts) >= 4 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) >= 3:
            return pts
    box = block.get("bbox") or {}
    try:
        x1, y1 = float(box["x1"]), float(box["y1"])
        x2, y2 = float(box["x2"]), float(box["y2"])
    except (KeyError, TypeError, ValueError):
        return []
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def block_rect(block):
    box = block.get("bbox") or {}
    try:
        return (float(box["x1"]), float(box["y1"]),
                float(box["x2"]), float(box["y2"]))
    except (KeyError, TypeError, ValueError):
        return None


def ink_by_kind(record):
    """`kind` -> lớp mực, dựng từ chú thích từ của chính bản ghi.

    Cùng một `kind` đổi lớp mực giữa các tờ (`invoice.field` khi in, khi viết
    tay), nên bảng này phải dựng lại theo từng bản ghi chứ không dùng chung.
    """
    tally: dict[str, dict[str, int]] = {}
    for word in record.get("word_annotations") or []:
        path, ink = word.get("field_path"), word.get("ink")
        if path and ink:
            tally.setdefault(path, {})
            tally[path][ink] = tally[path].get(ink, 0) + 1
    return {path: max(inks, key=inks.get) for path, inks in tally.items()}


# ---------------------------------------------------------------------------
# Đo từng trang
# ---------------------------------------------------------------------------

class Page:
    """Mọi con số đo được của một trang, gom vào một chỗ."""

    def __init__(self, path: Path, record, page, grid: int):
        self.path = path
        self.name = path.name
        self.number = int(page.get("page_number") or 1)
        self.width = float(page["width"])
        self.height = float(page["height"])
        self.blocks = [b for b in (record.get("blocks") or [])
                       if int(b.get("page_number") or 1) == self.number]

        self.polygons = [block_polygon(b) for b in self.blocks]
        self.areas = [polygon_area(p) for p in self.polygons]

        fine = np.zeros((COVERAGE_RASTER, COVERAGE_RASTER), dtype=bool)
        for poly in self.polygons:
            fill_polygon(fine, poly, self.width, self.height)
        self.coverage = float(fine.mean())

        # Chữ ký là chính tấm mặt nạ ấy gộp lại: một ô của lưới thô "có mực"
        # khi bất kỳ ô mịn nào bên trong nó có mực. Gộp thay vì tô lại để dòng
        # mảnh không biến mất ở độ phân giải thô.
        step = max(1, COVERAGE_RASTER // grid)
        usable = grid * step
        self.signature = fine[:usable, :usable].reshape(
            grid, step, grid, step).any(axis=(1, 3))

        tops = [min(p[1] for p in poly) for poly in self.polygons if poly]
        bottoms = [max(p[1] for p in poly) for poly in self.polygons if poly]
        self.top_start = min(tops) / self.height if tops else 1.0
        self.bottom_reach = max(bottoms) / self.height if bottoms else 0.0

        # Nghiêng và phồng: đo trên cạnh trên của quad so với bbox của nó.
        angles, inflation = [], []
        for block, poly, area in zip(self.blocks, self.polygons, self.areas):
            quad = block.get("quad")
            if not (isinstance(quad, list) and len(quad) >= 2):
                continue
            (x1, y1), (x2, y2) = quad[0][:2], quad[1][:2]
            angles.append(math.degrees(math.atan2(y2 - y1, x2 - x1)))
            rect = block_rect(block)
            if rect:
                box_area = max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])
                if box_area > 0:
                    inflation.append(area / box_area)
        self.rotation = float(np.median(angles)) if angles else 0.0
        self.quad_fill = float(np.median(inflation)) if inflation else 1.0


def overlapping_pairs(page: Page, inks, iou_floor: float):
    """Cặp block cùng mô tả một vùng pixel, đã trừ chồng lấn hợp lệ.

    Trả kèm số cặp mà phép đo thô trên bbox sẽ báo, để thấy phép đo này đã bỏ
    đi những gì: trang vênh, quan hệ chứa, và lớp mực đè lên lớp in.
    """
    count = len(page.blocks)
    if count < 2:
        return [], 0

    rects = np.array([block_rect(b) or (0.0, 0.0, 0.0, 0.0)
                      for b in page.blocks], dtype=float)
    areas = np.array(page.areas, dtype=float)

    x1, y1, x2, y2 = (rects[:, 0:1], rects[:, 1:2], rects[:, 2:3], rects[:, 3:4])
    inter = (np.clip(np.minimum(x2, x2.T) - np.maximum(x1, x1.T), 0, None)
             * np.clip(np.minimum(y2, y2.T) - np.maximum(y1, y1.T), 0, None))

    # Quad nằm trong bbox của nó, nên giao của hai quad không thể lớn hơn giao
    # của hai bbox, còn hợp thì không nhỏ hơn quad lớn hơn. Cận trên ấy loại
    # gần hết số cặp trước khi phải cắt đa giác.
    biggest = np.maximum(areas[:, None], areas[None, :])
    with np.errstate(divide="ignore", invalid="ignore"):
        bound = np.where(biggest > 0, inter / np.maximum(biggest, 1e-9), 0.0)
    rows, cols = np.triu_indices(count, 1)
    candidates = np.flatnonzero((inter[rows, cols] > 0)
                                & (bound[rows, cols] >= iou_floor))

    rect_area = (np.clip(rects[:, 2] - rects[:, 0], 0, None)
                 * np.clip(rects[:, 3] - rects[:, 1], 0, None))
    rect_union = rect_area[:, None] + rect_area[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        rect_iou = np.where(rect_union > 0, inter / np.maximum(rect_union, 1e-9), 0.0)
    naive = int((rect_iou[rows, cols] >= iou_floor).sum())

    found = []
    for index in candidates:
        i, j = int(rows[index]), int(cols[index])
        area_i, area_j = areas[i], areas[j]
        if area_i <= 0 or area_j <= 0:
            continue
        iou = polygon_iou(page.polygons[i], page.polygons[j], area_i, area_j)
        if iou < iou_floor:
            continue

        first, second = page.blocks[i], page.blocks[j]
        ink_i = inks.get(first.get("kind"))
        ink_j = inks.get(second.get("kind"))
        if ink_i != ink_j and (ink_i in OVERLAY_INKS or ink_j in OVERLAY_INKS):
            continue  # dấu đè chữ, nét tay điền vào dòng in — đúng thiết kế

        overlap = polygon_area(clip_polygon(page.polygons[i], page.polygons[j]))
        smaller = min(area_i, area_j)
        cover = overlap / smaller if smaller > 0 else 0.0
        if cover >= CONTAINMENT_COVER and smaller / max(area_i, area_j) <= CONTAINMENT_AREA_RATIO:
            continue  # block nằm gọn trong vùng chứa nó

        found.append({
            "file": page.name,
            "page": page.number,
            "iou": round(iou, 3),
            "cover_smaller": round(cover, 3),
            "a": {"id": first.get("id"), "kind": first.get("kind"),
                  "text": (first.get("text") or "")[:60], "bbox": block_rect(first)},
            "b": {"id": second.get("id"), "kind": second.get("kind"),
                  "text": (second.get("text") or "")[:60], "bbox": block_rect(second)},
        })
    found.sort(key=lambda item: -item["iou"])
    return found, naive


def frame_problems(path: Path, record, pages):
    """Hộp rơi khỏi ảnh hoặc không bao pixel nào, trên cả ba lớp nhãn.

    Soát cả `layout_annotations` và `word_annotations` chứ không chỉ `blocks`:
    hai lớp ấy mới là thứ đi vào tập huấn luyện, và chúng được dựng bằng đường
    khác nên hỏng được riêng.
    """
    sizes = {int(p.get("page_number") or 1): (float(p["width"]), float(p["height"]))
             for p in pages}
    default = next(iter(sizes.values()))
    problems = []

    def check(kind, label, points, page_number, override=None):
        width, height = override or sizes.get(page_number, default)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        outside = max(-min(xs), -min(ys), max(xs) - width, max(ys) - height)
        if outside > FRAME_TOLERANCE_PX:
            problems.append({"file": path.name, "source": kind, "label": label,
                             "problem": "ngoài khung", "overshoot_px": round(outside, 1),
                             "page_size": [width, height]})
        if polygon_area(points) < MIN_BOX_AREA_PX:
            problems.append({"file": path.name, "source": kind, "label": label,
                             "problem": "diện tích 0",
                             "bbox": [round(min(xs), 1), round(min(ys), 1),
                                      round(max(xs), 1), round(max(ys), 1)]})

    for block in record.get("blocks") or []:
        number = int(block.get("page_number") or 1)
        name = f"{block.get('id')} ({block.get('kind')})"
        rect = block_rect(block)
        if rect:
            check("block.bbox", name,
                  [(rect[0], rect[1]), (rect[2], rect[1]),
                   (rect[2], rect[3]), (rect[0], rect[3])], number)
        polygon = block_polygon(block)
        if block.get("quad") and polygon:
            check("block.quad", name, polygon, number)

    # Hai lớp chú thích không mang số trang, nên với bản ghi nhiều trang thì
    # lấy khổ lớn nhất làm khung: thà bỏ sót một hộp lố còn hơn báo nhầm cả
    # lớp chú thích của trang khổ lớn khi so với trang khổ nhỏ.
    frame = (max(w for w, _ in sizes.values()), max(h for _, h in sizes.values()))
    for source in ("layout_annotations", "word_annotations"):
        for item in record.get(source) or []:
            mode = item.get("bbox_mode")
            if mode and mode != EXPECTED_BBOX_MODE:
                problems.append({"file": path.name, "source": source,
                                 "label": str(item.get("layout_class") or ""),
                                 "problem": f"bbox_mode lạ: {mode}"})
                continue
            box = item.get("bbox")
            if not (isinstance(box, list) and len(box) == 4):
                continue
            name = str(item.get("field_path") or item.get("layout_class") or "?")
            check(source, name,
                  [(box[0], box[1]), (box[2], box[1]),
                   (box[2], box[3]), (box[0], box[3])], 1, override=frame)
    return problems


# ---------------------------------------------------------------------------
# Trùng bố cục
# ---------------------------------------------------------------------------

def jaccard_matrix(pages):
    """Jaccard từng đôi một, tính bằng một phép nhân ma trận."""
    flat = np.array([p.signature.ravel() for p in pages], dtype=np.float32)
    inter = flat @ flat.T
    counts = flat.sum(axis=1)
    union = counts[:, None] + counts[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)


def cluster(pages, matrix, threshold: float):
    """Gộp các trang nối với nhau bởi một cặp vượt ngưỡng thành một cụm."""
    parent = list(range(len(pages)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    rows, cols = np.triu_indices(len(pages), 1)
    linked = [(int(r), int(c)) for r, c in zip(rows, cols)
              if matrix[r, c] >= threshold]
    for i, j in linked:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    groups: dict[int, list[int]] = {}
    for index in range(len(pages)):
        groups.setdefault(find(index), []).append(index)

    clusters = []
    for members in groups.values():
        if len(members) < 2:
            continue
        scores = [float(matrix[a, b]) for a in members for b in members if a < b]
        clusters.append({
            "members": [f"{pages[m].name}#p{pages[m].number}" for m in members],
            "size": len(members),
            "min_jaccard": round(min(scores), 3) if scores else 1.0,
            "max_jaccard": round(max(scores), 3) if scores else 1.0,
            "over_limit": len(members) > MAX_REPEATS,
        })
    clusters.sort(key=lambda c: (-c["size"], -c["max_jaccard"]))
    return clusters, linked


def recipe_repeats(root: Path, recursive: bool, axis: str):
    """Đếm số lần mỗi giá trị của một trục công thức được dùng.

    Hình học không đếm nổi việc này (xem docstring đầu file), nhưng công thức
    của lượt chạy nằm ngay cạnh các bản ghi và nói thẳng ra. Trục đọc theo tên
    khoá trong `attributes` của chính file, nên không có tên bố cục nào bị ghim
    vào công cụ.
    """
    manifests = sorted(root.rglob("synthesis.json") if recursive
                       else root.glob("synthesis.json"))
    tally: dict[str, list[str]] = {}
    axes: set[str] = set()
    # Cùng một trang nằm trong HAI công thức: một trong thư mục kết quả, một
    # trong shard đã dựng nó. `--recursive` thấy cả hai, và đếm cả hai thì mọi
    # con số lặp gấp đôi -- đo được: `eatery_indexed` báo 22 lần thay vì 11,
    # và danh sách ví dụ in mỗi tên hai lần cạnh nhau. Gộp theo `job_id`, cùng
    # khoá mà `load_records` gộp, để hai nửa của công cụ đếm cùng một tập.
    seen: set[str] = set()
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        pages = data.get("pages")
        if not isinstance(pages, dict):
            continue
        for image, recipe in pages.items():
            attributes = (recipe or {}).get("attributes") or {}
            axes |= set(attributes)
            # `job_id` khi có; nếu công thức không mang thì tên ảnh -- trong
            # một lượt chạy tên ảnh cũng là duy nhất.
            key = str((recipe or {}).get("job_id") or image)
            if key in seen:
                continue
            seen.add(key)
            value = attributes.get(axis)
            if value:
                tally.setdefault(str(value), []).append(str(image))
    return tally, sorted(axes), len(manifests)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_report(root: Path, args):
    records, skipped = load_records(root, args.recursive)
    if not records:
        raise SystemExit(f"không có bản ghi trang nào trong {root}")

    pages, overlaps, frame, watch_overlaps = [], [], [], []
    axis_aligned_hits = 0
    for path, record in records:
        inks = ink_by_kind(record)
        frame += frame_problems(path, record, record["pages"])
        for raw in record["pages"]:
            page = Page(path, record, raw, args.grid)
            pages.append(page)
            pairs, naive = overlapping_pairs(page, inks, args.iou_watch)
            axis_aligned_hits += naive
            for pair in pairs:
                (overlaps if pair["iou"] >= args.iou else watch_overlaps).append(pair)

    matrix = jaccard_matrix(pages)
    clusters, _ = cluster(pages, matrix, args.jaccard)
    near_clusters, _ = cluster(pages, matrix, args.jaccard_watch)

    sparse = []
    for page in pages:
        reasons = []
        if page.coverage < args.coverage:
            reasons.append(f"phủ {page.coverage:.1%} < {args.coverage:.0%}")
        if page.bottom_reach < args.reach:
            reasons.append(f"mực dừng ở {page.bottom_reach:.0%} chiều cao")
        if reasons:
            sparse.append({"file": page.name, "page": page.number,
                           "coverage": round(page.coverage, 4),
                           "bottom_reach": round(page.bottom_reach, 3),
                           "top_start": round(page.top_start, 3),
                           "blocks": len(page.blocks), "reasons": reasons})
    sparse.sort(key=lambda item: item["coverage"])

    rotated = sorted(({"file": p.name, "page": p.number,
                       "rotation_deg": round(p.rotation, 2),
                       "quad_over_bbox": round(p.quad_fill, 2)}
                      for p in pages if abs(p.rotation) > ROTATION_NOTE_DEG
                      or p.quad_fill < BOX_INFLATION_WARN),
                     key=lambda item: item["quad_over_bbox"])

    tally, axes, manifests = recipe_repeats(root, args.recursive, args.recipe_axis)
    repeats = sorted(({"value": value, "count": len(images), "images": sorted(images)}
                      for value, images in tally.items() if len(images) > MAX_REPEATS),
                     key=lambda item: -item["count"])

    return {
        "run": str(root),
        "pages_audited": len(pages),
        "files_skipped": [{"file": str(p), "why": why} for p, why in skipped],
        "thresholds": {
            "signature_grid": args.grid, "duplicate_jaccard": args.jaccard,
            "near_jaccard": args.jaccard_watch, "min_ink_coverage": args.coverage,
            "min_bottom_reach": args.reach, "overlap_iou": args.iou,
            "overlap_iou_watch": args.iou_watch, "max_repeats": MAX_REPEATS,
        },
        "duplicate_clusters": clusters,
        "near_duplicate_clusters": near_clusters,
        "recipe_repeats": {"axis": args.recipe_axis, "manifests": manifests,
                           "axes_available": axes, "over_limit": repeats},
        "coverage_spread": {
            "min": round(float(np.min([p.coverage for p in pages])), 4),
            "p25": round(float(np.percentile([p.coverage for p in pages], 25)), 4),
            "median": round(float(np.median([p.coverage for p in pages])), 4),
            "max": round(float(np.max([p.coverage for p in pages])), 4),
        },
        "sparse_pages": sparse,
        "overlaps": overlaps,
        "overlaps_watch": watch_overlaps,
        "overlaps_if_measured_on_bbox": axis_aligned_hits,
        "frame_problems": frame,
        "geometry_notes": rotated,
        "per_page": [{"file": p.name, "page": p.number,
                      "size": [p.width, p.height], "blocks": len(p.blocks),
                      "coverage": round(p.coverage, 4),
                      "bottom_reach": round(p.bottom_reach, 3),
                      "top_start": round(p.top_start, 3),
                      "rotation_deg": round(p.rotation, 2),
                      "quad_over_bbox": round(p.quad_fill, 2)} for p in pages],
    }


def show(report, top: int) -> int:
    def more(items):
        if len(items) > top:
            print(f"      ... còn {len(items) - top} mục nữa")

    thresholds = report["thresholds"]
    print(f"\n{report['run']} — {report['pages_audited']} trang\n")

    clusters = report["duplicate_clusters"]
    over = [c for c in clusters if c["over_limit"]]
    near = report["near_duplicate_clusters"]
    state = "PROBLEM" if over else "ok"
    print(f"[{state}] 1. TRÙNG BỐ CỤC — {len(clusters)} cụm ở Jaccard "
          f">= {thresholds['duplicate_jaccard']}, {len(over)} cụm quá "
          f"{thresholds['max_repeats']} trang")
    for item in clusters[:top]:
        mark = "VƯỢT LUẬT" if item["over_limit"] else "trong luật"
        print(f"      {item['size']} trang  jaccard {item['min_jaccard']}–"
              f"{item['max_jaccard']}  [{mark}]")
        print(f"        {', '.join(item['members'])}")
    more(clusters)
    seen = {tuple(c["members"]) for c in clusters}
    extra = [c for c in near if tuple(c["members"]) not in seen]
    print(f"      tầng theo dõi (>= {thresholds['near_jaccard']}): "
          f"thêm {len(extra)} cụm chưa tới ngưỡng trên")
    for item in extra[:top]:
        print(f"        {item['size']} trang  {item['max_jaccard']}  "
              f"{', '.join(item['members'])}")
    more(extra)

    recipes = report["recipe_repeats"]
    repeats = recipes["over_limit"]
    if recipes["manifests"]:
        state = "PROBLEM" if repeats else "ok"
        print(f"\n[{state}] 1b. LẶP THEO CÔNG THỨC (trục '{recipes['axis']}', "
              f"{recipes['manifests']} file synthesis.json) — {len(repeats)} giá trị "
              f"dùng quá {thresholds['max_repeats']} lần")
        for item in repeats[:top]:
            print(f"      {item['count']}x {item['value']}")
            print(f"        {', '.join(i.replace('.jpg', '') for i in item['images'])}")
        more(repeats)
    else:
        print(f"\n[skip] 1b. LẶP THEO CÔNG THỨC — không thấy synthesis.json cạnh bản ghi")

    sparse = report["sparse_pages"]
    spread = report["coverage_spread"]
    print(f"\n[{'PROBLEM' if sparse else 'ok'}] 2. TRANG RỖNG / THƯA — {len(sparse)} trang "
          f"(phủ < {thresholds['min_ink_coverage']:.0%} hoặc mực dừng trước "
          f"{thresholds['min_bottom_reach']:.0%} chiều cao)")
    print(f"      độ phủ của lượt chạy: thấp nhất {spread['min']:.1%}, "
          f"tứ phân vị 1 {spread['p25']:.1%}, trung vị {spread['median']:.1%}, "
          f"cao nhất {spread['max']:.1%}")
    for item in sparse[:top]:
        print(f"      {item['file']}  phủ {item['coverage']:.1%}  "
              f"mực tới {item['bottom_reach']:.0%}  {item['blocks']} block "
              f"— {'; '.join(item['reasons'])}")
    more(sparse)

    overlaps = report["overlaps"]
    watch = report["overlaps_watch"]
    print(f"\n[{'PROBLEM' if overlaps else 'ok'}] 3. HỘP CHỒNG NHAU — {len(overlaps)} cặp "
          f"IoU >= {thresholds['overlap_iou']}, {len(watch)} cặp ở tầng theo dõi "
          f">= {thresholds['overlap_iou_watch']}")
    naive = report["overlaps_if_measured_on_bbox"]
    if naive:
        print(f"      (đo thô trên bbox, chưa trừ gì, sẽ báo {naive} cặp — phần chênh "
              f"là trang vênh và chồng lấn hợp lệ, không phải nhãn sai)")
    for item in (overlaps + watch)[:top]:
        print(f"      {item['file']}  IoU {item['iou']}  "
              f"{item['a']['kind']} × {item['b']['kind']}")
        print(f"        {item['a']['text']!r}")
        print(f"        {item['b']['text']!r}")
    more(overlaps + watch)

    frame = report["frame_problems"]
    print(f"\n[{'PROBLEM' if frame else 'ok'}] 4. HỘP RA NGOÀI KHUNG / DIỆN TÍCH 0 — "
          f"{len(frame)} hộp")
    for item in frame[:top]:
        detail = item.get("overshoot_px")
        print(f"      {item['file']}  {item['source']}  {item['label']}  "
              f"{item['problem']}" + (f" (lố {detail}px)" if detail else ""))
    more(frame)

    notes = report["geometry_notes"]
    if notes:
        print(f"\n[info] CHẨN ĐOÁN — {len(notes)} trang nghiêng hoặc có bbox phồng "
              f"so với quad")
        for item in notes[:top]:
            print(f"      {item['file']}  nghiêng {item['rotation_deg']:+.2f}°  "
                  f"quad/bbox {item['quad_over_bbox']}")
        more(notes)

    skipped = report["files_skipped"]
    if skipped:
        print(f"\n[info] bỏ qua {len(skipped)} file không phải bản ghi trang")
        for item in skipped[:top]:
            print(f"      {Path(item['file']).name}: {item['why']}")

    return 1 if (over or repeats or sparse or overlaps or frame) else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog="Mọi ngưỡng mặc định là hằng số có tên ở đầu file, kèm lý do.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục lượt chạy (ảnh + json cạnh nhau)")
    parser.add_argument("--json", type=Path, metavar="BÁO_CÁO.json",
                        help="ghi báo cáo máy đọc được")
    parser.add_argument("--top", type=int, default=10, metavar="N",
                        help="số ví dụ in ra mỗi mục (mặc định 10)")
    parser.add_argument("--recursive", action="store_true",
                        help="soát cả thư mục con, gộp bản sao theo job_id")
    parser.add_argument("--grid", type=int, default=SIGNATURE_GRID)
    parser.add_argument("--jaccard", type=float, default=DUP_JACCARD)
    parser.add_argument("--jaccard-watch", type=float, default=NEAR_JACCARD)
    parser.add_argument("--coverage", type=float, default=MIN_INK_COVERAGE)
    parser.add_argument("--reach", type=float, default=MIN_BOTTOM_REACH)
    parser.add_argument("--iou", type=float, default=OVERLAP_IOU)
    parser.add_argument("--iou-watch", type=float, default=OVERLAP_IOU_WATCH)
    parser.add_argument("--recipe-axis", default="layout",
                        help="trục trong attributes để đếm lặp (mặc định layout)")
    args = parser.parse_args()

    if not args.run.is_dir():
        raise SystemExit(f"không phải thư mục: {args.run}")

    report = build_report(args.run, args)
    code = show(report, args.top)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\nbáo cáo: {args.json}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
