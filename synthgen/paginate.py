"""Cắt trang bằng phép ĐO, không bằng con số viết sẵn trong file bố cục.

Luật, đúng một câu: **một chứng từ chỉ được cắt làm N tờ khi CẢ N tờ đều
được lấp ít nhất `MIN_FILL`; không đủ thì in ít tờ hơn.** Hệ quả trực tiếp
là "nếu height không quá dài thì đừng cắt" -- một hoá đơn bốn dòng hàng
không có cách nào lấp 80% hai tờ giấy, nên nó ra một tờ.

Vì sao phải đo. Cách cũ trong kho này chia đều số dòng cho các tờ và chỉ gộp
lại khi tờ sau RỖNG HẲN (`generators/html/sheets/modern.py`), nên hai dòng
tràn sang tờ hai vẫn cắt. Đo trên 21 trang của bảy bố cục có `page_order`:
tờ hai lấp 25%, 31%, 32%, 36%... Và `table.rows_first: 8` viết trong YAML là
một con số đoán, không phải sức chứa thật của tờ giấy -- cùng một `8` ấy
lấp 45% một tờ A4 và tràn một tờ A5.

Sức chứa ở đây tính từ phép đo trong chính trình duyệt vừa dàn trang: chiều
cao một dòng hàng, chiều cao khối đầu, khối cuối, và tiêu đề cột. Không hằng
số nào mô tả một bố cục cụ thể.

`plan()` không biết Playwright. Nó gọi lại `measure(slices)` mà bên gọi đưa
vào, nên `tests/` chạy được nó bằng một hàm giả và `render.py` đưa vào cái đo
thật. Đó cũng là lý do nó ở file riêng.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Ngưỡng lấp, đo theo chiều cao đã dùng chia chiều cao khổ giấy.
MIN_FILL = 0.8
MAX_FILL = 1.0
AIM_FILL = 0.92

# Tờ giấy DUY NHẤT được thả lỏng hơn: không có tờ nào sau nó để dồn chữ sang,
# nên chỗ trống ở đây lấp bằng cỡ chữ chứ không bằng dòng hàng.
MIN_SINGLE_FILL = 0.7
AIM_SINGLE_FILL = 0.8
MAX_BOOST = 1.6

MIN_BOOST = 0.68
ROUNDS = 4


@dataclass
class Sheet:
    """Một tờ giấy đã dàn xong, đo trong trình duyệt."""

    paper: float
    used: float
    height: float
    rows: list[float]
    thead: float
    pad_top: float
    pad_bottom: float
    table_top: float
    table_bottom: float

    @property
    def fill(self) -> float:
        return self.used / self.paper if self.paper else 0.0

    @property
    def grown(self) -> bool:
        return self.height > self.paper + 1.0


@dataclass
class Plan:
    slices: list[tuple[int, int]]
    rows_total: int
    pages: int
    fills: list[float]
    rounds: int
    note: str
    boost: float = 1.0

    @property
    def ok(self) -> bool:
        """Mọi tờ nằm trong khoảng cho phép. Tờ duy nhất chỉ cần không tràn."""
        if not self.fills:
            return True
        if any(f > MAX_FILL for f in self.fills):
            return False
        return len(self.fills) == 1 or min(self.fills) >= MIN_FILL


def _row_height(sheets: list[Sheet]) -> float:
    heights = [h for sheet in sheets for h in sheet.rows if h > 0]
    if not heights:
        return 0.0
    # Trung vị, không phải trung bình: một dòng hàng có chữ xuống hai hàng
    # kéo trung bình lên, còn sức chứa thì do dòng THƯỜNG quyết định.
    heights.sort()
    return heights[len(heights) // 2]


def _capacity(probe: Sheet, row_h: float, *, head: bool, tail: bool) -> int:
    """Bao nhiêu dòng hàng lọt vào MỘT tờ, tuỳ tờ ấy có khối đầu / khối cuối.

    `chrome` là phần bảng chiếm mà không phải dòng hàng: chú thích bảng,
    viền, lề khối. Đo bằng hiệu, chứ không cộng từng thành phần -- cộng tay
    là cách bỏ sót đúng cái thứ CSS vừa thêm vào."""
    if row_h <= 0:
        return 0
    body = sum(h for h in probe.rows if h > 0)
    chrome = max(probe.table_bottom - probe.table_top - probe.thead - body, 0.0)
    top = probe.table_top if head else probe.pad_top
    bottom = (probe.used - probe.table_bottom) if tail else probe.pad_bottom
    room = probe.paper - top - bottom - probe.thead - chrome
    return max(int(room // row_h), 0)


def _slices(counts: list[int]) -> list[tuple[int, int]]:
    out, cursor = [], 0
    for count in counts:
        out.append((cursor, cursor + count))
        cursor += count
    return out


def _fit_single(measure, counts: list[int], set_boost, note: str,
                set_paper=None) -> Plan:
    """Một tờ giấy duy nhất: không được TRÀN, và không nên quá trống.

    Chỗ trống ở đây lấp bằng cỡ chữ chứ không bằng dòng hàng: số dòng của một
    tờ khai hay một biên nhận là chuyện nội dung -- sáu mục thì sáu mục -- còn
    cỡ chữ là chuyện nhà in. Với tài liệu nhiều tờ thì ngược lại, và
    `plan()` lấp bằng cách thêm dòng.

    Khi thu hết cỡ mà chữ vẫn tràn thì đổi KHỔ GIẤY, không thu tiếp: dưới
    `MIN_BOOST` là cỡ chữ không đọc nổi, còn nhà in thật gặp đúng tình huống
    ấy thì in sang khổ lớn hơn. `set_paper()` trả về True khi còn khổ để leo.

    Trả về lần đo TỐT NHẤT đã thấy, kèm `boost` của chính lần ấy: bên gọi
    phải đặt lại hệ số đó trước khi chụp, nếu không tấm ảnh sẽ là tấm cuối
    cùng được dàn chứ không phải tấm được chọn."""
    boost = 1.0
    best = None
    best_grown = True

    for _round in range(14):
        sheets = measure(_slices(counts))
        fills = [sheet.fill for sheet in sheets]
        grown = bool(sheets and sheets[0].grown)
        attempt = Plan(_slices(counts), sum(counts), max(len(sheets), 1), fills,
                       _round + 1,
                       note if boost <= 1.0 else
                       f"{note + '; ' if note else ''}phóng cỡ chữ x{boost:.2f}",
                       boost)
        fill = fills[0] if fills else 1.0
        if not grown and fill >= MIN_SINGLE_FILL:
            return attempt

        # Giữ lần đo tốt nhất: chưa tràn thì lấy lần lấp nhiều nhất, còn khi
        # mọi lần đều tràn thì lấy lần tràn ít nhất.
        if best is None:
            best, best_grown = attempt, grown
        else:
            seen = (best.fills or [0.0])[0]
            better = ((not grown and (best_grown or fill > seen))
                      or (grown and best_grown and fill < seen))
            if better:
                best, best_grown = attempt, grown
        if set_boost is None or fill <= 0:
            break

        want = boost * (AIM_SINGLE_FILL / fill)
        # Thu hết cỡ mà vẫn tràn thì leo lên khổ giấy lớn hơn, không thu tiếp.
        if grown and want < MIN_BOOST and set_paper is not None and set_paper():
            boost = 1.0
            set_boost(boost)
            continue
        clamped = max(min(want, MAX_BOOST), MIN_BOOST)
        if abs(clamped - boost) <= boost * 0.03:
            break
        boost = clamped
        set_boost(boost)

    if best is None:
        sheets = measure(_slices(counts))
        best = Plan(_slices(counts), sum(counts), max(len(sheets), 1),
                    [sheet.fill for sheet in sheets], 1,
                    f"{note + '; ' if note else ''}không tìm được cách lấp vừa",
                    boost)
    if set_boost is not None:
        set_boost(best.boost)
    return best


def plan(measure, *, rows_probe: int, target_pages: int, rows_floor: int,
         rows_ceiling: int, refill, set_boost=None,
         set_paper=None) -> Plan:
    """Số dòng và các lát trang, sau khi đã đo thật.

    `measure(slices) -> list[Sheet]` dàn tài liệu với các lát ấy rồi đo lại.
    `refill(n)` dựng lại nội dung với `n` dòng hàng; `set_boost(x)` đổi hệ số
    phóng cỡ chữ. Cả ba do bên gọi đưa vào, nên file này không biết Playwright.

    Trả về kế hoạch TỐT NHẤT tìm được, kèm `note` nói nó đã phải nhượng bộ ở
    đâu. Không bao giờ ném: một trang không cắt được đẹp vẫn là một trang vẽ
    được, và `run.py` ghi lại tỉ lệ lấp để đếm."""
    # Không có bảng hàng thì không có gì để cắt: một tờ, lấp bằng cỡ chữ.
    if rows_ceiling <= 0:
        return _fit_single(measure, [0], set_boost, 'không có bảng hàng',
                           set_paper)

    refill(rows_probe)
    probe = measure([(0, rows_probe)])
    if not probe:
        return Plan([(0, rows_probe)], rows_probe, 1, [], 0, 'không đo được', 1.0)
    row_h = _row_height(probe)
    if row_h <= 0:
        return _fit_single(measure, [rows_probe], set_boost,
                           'không có dòng hàng để đo', set_paper)

    cap_one = _capacity(probe[0], row_h, head=True, tail=True)
    cap_first = _capacity(probe[0], row_h, head=True, tail=False)
    cap_mid = _capacity(probe[0], row_h, head=False, tail=False)
    cap_last = _capacity(probe[0], row_h, head=False, tail=True)

    pages = max(int(target_pages), 1)
    note = ''
    best = None

    while pages >= 1:
        if pages == 1:
            # Một tờ: số dòng là sức chứa thật, chặn trên bởi trần của chứng
            # từ và chặn dưới bởi sàn của nó -- rồi cỡ chữ lấp phần còn thiếu.
            want = min(cap_one, rows_ceiling) if cap_one else max(rows_floor, 1)
            if cap_one >= rows_floor:
                want = max(want, rows_floor)
            want = max(want, 1)
            refill(want)
            return _fit_single(measure, [want], set_boost, note, set_paper)

        tail_rows = max(int(round(cap_last * AIM_FILL)), 1)
        counts = [cap_first] + [cap_mid] * (pages - 2) + [tail_rows]
        if min(counts) <= 0:
            pages -= 1
            note = 'khổ giấy không chứa nổi một dòng hàng trên tờ tiếp theo'
            continue

        if sum(counts) > rows_ceiling:
            pages -= 1
            note = (f'hạ xuống {pages} tờ: {sum(counts)} dòng cần cho '
                    f'{pages + 1} tờ vượt trần {rows_ceiling} của chứng từ')
            continue

        total = sum(counts)
        refill(total)
        sheets = measure(_slices(counts))
        attempt = Plan(_slices(counts), total, len(sheets),
                       [s.fill for s in sheets], 1, note, 1.0)

        for round_no in range(2, ROUNDS + 1):
            if attempt.ok:
                break
            counts = list(counts)
            changed = False

            for index, sheet in enumerate(sheets):
                if not (sheet.grown or sheet.fill > MAX_FILL):
                    continue
                over = max(sheet.used - sheet.paper, sheet.height - sheet.paper)
                drop = max(int(math.ceil(over / row_h)), 1)
                drop = min(drop, counts[index] - 1 if counts[index] > 1 else 0)
                if not drop:
                    continue
                counts[index] -= drop
                if index + 1 < len(counts):
                    counts[index + 1] += drop
                changed = True

            if len(counts) > 1 and sheets[-1].fill < MIN_FILL:
                short = (MIN_FILL + 0.06) * sheets[-1].paper - sheets[-1].used
                add = max(int(math.ceil(short / row_h)), 1)
                counts[-1] += add
                changed = True
            if not changed:
                break
            total = sum(counts)
            refill(total)
            sheets = measure(_slices(counts))
            attempt = Plan(_slices(counts), total, len(sheets),
                           [s.fill for s in sheets], round_no, note, 1.0)

        if attempt.ok:
            return attempt
        if best is None:
            best = attempt
        pages -= 1
        note = (f'hạ từ {pages + 1} xuống {pages} tờ: không tờ nào đầy tới '
                f'{MIN_FILL:.0%}')

    assert best is not None
    return best
