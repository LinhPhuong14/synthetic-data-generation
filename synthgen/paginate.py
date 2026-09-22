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
    """Một tờ giấy đã dàn xong, đo trong trình duyệt.

    `rows`, `flow_*` nói về KHỐI CHẢY của tài liệu -- khối bị cắt ra giữa các
    tờ -- chứ không riêng về bảng. Các tên này từng là `thead`, `table_top`,
    `table_bottom`, và cái tên ấy là lý do file này chỉ cắt trang được cho tài
    liệu có bảng: một khái niệm mang tên của trường hợp đầu tiên dùng nó thì
    trường hợp thứ hai trông như một ngoại lệ. Xem `design.FLOW_BLOCKS`.
    """

    paper: float
    used: float
    height: float
    # Chiều cao từng MỤC của khối chảy: dòng hàng của bảng, hoặc một điều
    # khoản với các khoản của nó.
    rows: list[float]
    # Phần in lại ở ĐẦU mỗi tờ: `<thead>` của bảng. Khối chảy không có gì in
    # lại -- điều khoản chẳng hạn -- thì bằng 0.
    flow_head: float
    pad_top: float
    pad_bottom: float
    flow_top: float
    flow_bottom: float

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
    """BƯỚC dọc của một mục: chiều cao của nó cộng khoảng cách tới mục sau.

    Cộng khoảng cách, vì đó là chỗ nó thật sự chiếm trên tờ giấy -- xem
    `_gap` về việc trừ tổng khoảng cách khỏi chỗ trống mỗi tờ sai thế nào."""
    heights = [h for sheet in sheets for h in sheet.rows if h > 0]
    if not heights:
        return 0.0
    gap = max((_gap(s) for s in sheets), default=0.0)
    # Trung vị, không phải trung bình: một dòng hàng có chữ xuống hai hàng
    # kéo trung bình lên, còn sức chứa thì do dòng THƯỜNG quyết định.
    heights.sort()
    return heights[len(heights) // 2] + gap


def _gap(probe: Sheet) -> float:
    """Khoảng cách dọc TRUNG BÌNH giữa hai mục liền nhau của khối chảy.

    Bản trước không có hàm này, và thay vào đó trừ CẢ TỔNG khoảng cách khỏi
    chỗ trống của MỌI tờ, dưới tên `chrome`:

        chrome = flow_bottom - flow_top - flow_head - sum(rows)

    Với `n` mục, hiệu ấy là `(n-1)` lần khoảng cách cộng lề khối -- một con
    số LỚN DẦN theo số mục dò được. Đo được khi nới lần dò từ 8 lên 40 mục:
    chỗ trống tờ đầu ra 105 trên khổ A5 và **âm 23** trên A4 ngang, trong khi
    tờ giữa 397. Tờ đầu gần như không nhận nổi mục nào, nên `paginate` hạ số
    tờ rồi `--multipage-only` vứt tài liệu.

    Lỗi có sẵn từ trước, chỉ là lần dò tám mục làm nó nhỏ tới mức không ai
    thấy. Chỗ đúng của khoảng cách là CỘNG VÀO CHIỀU CAO MỖI MỤC, không phải
    trừ khỏi chỗ trống mỗi tờ: nó phát sinh theo mục, không theo tờ."""
    items = [h for h in probe.rows if h > 0]
    if len(items) < 2:
        return 0.0
    span = probe.flow_bottom - probe.flow_top - probe.flow_head
    extra = span - sum(items)
    return max(extra / (len(items) - 1), 0.0)


def _room(probe: Sheet, *, head: bool, tail: bool) -> float:
    """CHỖ trống cho các mục trên MỘT tờ, tuỳ tờ ấy có khối đầu / khối cuối.

    KHÔNG trừ khoảng cách giữa các mục ở đây -- xem `_gap`. Chỉ trừ thứ mỗi
    tờ đều phải trả: lề trên, lề dưới, và phần in lại ở đầu tờ (`<thead>`)."""
    top = probe.flow_top if head else probe.pad_top
    bottom = (probe.used - probe.flow_bottom) if tail else probe.pad_bottom
    return max(probe.paper - top - bottom - probe.flow_head, 0.0)


def _capacity(probe: Sheet, row_h: float, *, head: bool, tail: bool) -> int:
    """Bao nhiêu MỤC lọt vào một tờ, ƯỚC theo chiều cao TRUNG VỊ.

    Đường lùi, dùng khi không biết chiều cao của từng mục -- bảng hai trăm
    dòng thì không đo hết được trong một lần dò. Xem `_pack` cho đường chính."""
    if row_h <= 0:
        return 0
    return max(int(_room(probe, head=head, tail=tail) // row_h), 0)


def _pack(heights: list[float], rooms: list[float], aim: float) -> list[int]:
    """Chia các mục vào từng tờ theo CHIỀU CAO THẬT của chúng.

    Vì sao cần, và đo được. `_capacity` chia chỗ trống cho chiều cao TRUNG VỊ
    -- đúng cho dòng hàng của một bảng, nơi mọi dòng cao gần như nhau. Sai
    cho khối chảy là văn xuôi: một mục `sections` cao một đến ba đoạn, chênh
    nhau ba lần, nên "mười hai mục vừa một tờ" tính theo trung vị hoá ra chỉ
    lấp 70%. `paginate` thấy tờ chưa đầy 80% thì hạ số tờ, và
    `--multipage-only` vứt luôn tài liệu: đo trên một lượt 90 chứng từ, 35
    trên 47 ca bị vứt mang đúng câu `không tờ nào đầy tới 80%`.

    Xếp tham lam theo thứ tự: mục nào còn vừa chỗ thì vào tờ này, hết chỗ thì
    sang tờ sau. Không tối ưu toàn cục, và không cần -- thứ tự mục là thứ tự
    đọc, đảo nó để xếp khít hơn là đổi nội dung tài liệu.

    Mỗi tờ nhận ÍT NHẤT một mục kể cả khi mục ấy cao hơn chỗ trống: thà một
    tờ tràn rồi để `plan()` hạ số tờ, hơn là một tờ rỗng.
    """
    counts: list[int] = []
    at = 0
    for room in rooms:
        budget = room * aim
        used = 0.0
        taken = 0
        while at + taken < len(heights):
            nxt = heights[at + taken]
            if taken and used + nxt > budget:
                break
            used += nxt
            taken += 1
        if taken == 0 and at < len(heights):
            taken = 1
        counts.append(taken)
        at += taken
        if at >= len(heights):
            break
    while len(counts) < len(rooms):
        counts.append(0)
    return counts


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
    # Không có khối chảy thì không có gì để cắt: một tờ, lấp bằng cỡ chữ.
    if rows_ceiling <= 0:
        return _fit_single(measure, [0], set_boost, 'không có khối chảy',
                           set_paper)

    refill(rows_probe)
    probe = measure([(0, rows_probe)])
    if not probe:
        return Plan([(0, rows_probe)], rows_probe, 1, [], 0, 'không đo được', 1.0)
    row_h = _row_height(probe)
    if row_h <= 0:
        return _fit_single(measure, [rows_probe], set_boost,
                           'không có mục nào để đo', set_paper)

    cap_one = _capacity(probe[0], row_h, head=True, tail=True)
    cap_first = _capacity(probe[0], row_h, head=True, tail=False)
    cap_mid = _capacity(probe[0], row_h, head=False, tail=False)
    cap_last = _capacity(probe[0], row_h, head=False, tail=True)

    # CHIỀU CAO THẬT của từng mục, khi lần dò đã đo được HẾT.
    #
    # `refill()` trả về TIỀN TỐ của một hoán vị cố định (xem
    # `content.clauses_of`), nên mục thứ k luôn là cùng một mục và cao đúng
    # bằng thế ở mọi lần đo. Điều đó cho phép xếp theo chiều cao thật thay vì
    # chia chỗ cho trung vị -- xem `_pack` về việc trung vị sai ở đâu.
    #
    # Chỉ dùng khi dò được hết: một bảng hai trăm bốn mươi dòng thì lần dò
    # tám dòng không nói gì về dòng thứ hai trăm, và khi ấy trung vị vẫn là
    # câu trả lời đúng nhất có được.
    # BƯỚC của từng mục: chiều cao cộng khoảng cách tới mục sau.
    gap = _gap(probe[0])
    item_heights = [h + gap for h in probe[0].rows if h > 0]
    rooms_of = {
        'one': _room(probe[0], head=True, tail=True),
        'first': _room(probe[0], head=True, tail=False),
        'mid': _room(probe[0], head=False, tail=False),
        'last': _room(probe[0], head=False, tail=True),
    }

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

        # Biết đủ chiều cao cho SỐ TỜ NÀY hay không -- quyết theo từng vòng,
        # không một lần cho cả hàm: xếp hai tờ cần ít mục hơn xếp mười tờ, và
        # một lần dò bốn mươi mục đủ cho vòng trước mà không đủ cho vòng sau.
        want = cap_first + cap_mid * max(pages - 2, 0) + cap_last
        if len(item_heights) >= want > 0:
            # Xếp theo chiều cao thật. `AIM_FILL` là đích lấp, và nó nằm
            # trong khoảng [MIN_FILL, MAX_FILL] nên một tờ xếp tới đích thì
            # đã qua ngưỡng 80% -- đúng thứ vòng lặp dưới kia phải sửa mãi
            # khi ước lượng theo trung vị bắn trượt.
            rooms = ([rooms_of['first']] + [rooms_of['mid']] * (pages - 2)
                     + [rooms_of['last']])
            counts = _pack(item_heights, rooms, AIM_FILL)
        else:
            tail_rows = max(int(round(cap_last * AIM_FILL)), 1)
            counts = [cap_first] + [cap_mid] * (pages - 2) + [tail_rows]
        if min(counts) <= 0:
            pages -= 1
            note = 'khổ giấy không chứa nổi một mục trên tờ tiếp theo'
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
