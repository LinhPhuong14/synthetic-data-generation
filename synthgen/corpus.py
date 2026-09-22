"""Kho chữ tiếng Việt, đọc thẳng từ `rulebase/corpus/vi/`.

Đọc FILE chứ không đi qua `rulebase/content.py`: file corpus là dữ liệu chữ
-- tên hàng, tên người, tên phố -- còn `content.py` là bộ lắp nội dung theo
bố cục có sẵn, và gói này không dùng bố cục có sẵn. Định dạng mỗi file giống
nhau và đã có sẵn trong kho: dòng bắt đầu bằng `#` là chú thích, còn lại là
các cột ngăn bằng TAB.

Mọi hàm ở đây trả về LIST, cache một lần cho mỗi tiến trình. Một shard là một
tiến trình, nên chi phí đọc trả đúng một lần cho hàng nghìn trang.
"""
from __future__ import annotations

import functools
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / 'rulebase' / 'corpus' / 'vi'


def _rows(stem: str) -> list[list[str]]:
    path = CORPUS / f'{stem}.txt'
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        out.append(line.split('\t'))
    return out


@functools.lru_cache(maxsize=64)
def lines(stem: str) -> tuple[str, ...]:
    """Cột đầu của mỗi dòng -- dùng cho file một cột (người, phố, phường)."""
    return tuple(row[0].strip() for row in _rows(stem) if row and row[0].strip())


@functools.lru_cache(maxsize=64)
def priced(stem: str) -> tuple[tuple[str, int, int], ...]:
    """`(tên, giá tối thiểu, giá tối đa)` -- định dạng của mọi `items_*.txt`
    và `catalogue_*.txt`. Dòng thiếu cột giá bị bỏ, không đoán: một mặt hàng
    không có khoảng giá thì số tiền sinh ra là số bịa, và cột thành tiền là
    thứ người đọc nhãn tin tưởng nhất."""
    out = []
    for row in _rows(stem):
        if len(row) < 3:
            continue
        try:
            lo, hi = int(float(row[1])), int(float(row[2]))
        except ValueError:
            continue
        name = row[0].strip()
        if name and lo > 0 and hi >= lo:
            out.append((name, lo, hi))
    return tuple(out)


@functools.lru_cache(maxsize=64)
def spans(stem: str) -> tuple[tuple[str, ...], ...]:
    """MỌI cột của mỗi dòng, cho file có số cột thay đổi từng dòng.

    `clauses_*.txt` là file đầu tiên như thế: cột đầu là tiêu đề một điều,
    các cột sau là các KHOẢN của chính điều ấy, và số khoản mỗi điều một
    khác. `paired()` cắt ở cột hai nên không đọc được, còn ép mọi điều có
    đúng ba khoản là ép dữ liệu theo bộ đọc."""
    out = []
    for row in _rows(stem):
        cells = tuple(cell.strip() for cell in row if cell.strip())
        if len(cells) >= 2:
            out.append(cells)
    return tuple(out)


@functools.lru_cache(maxsize=64)
def paired(stem: str) -> tuple[tuple[str, str], ...]:
    """`(cột 1, cột 2)` -- `shops_*.txt` (pháp nhân, chi nhánh) và
    `payments.txt` (nhãn, nhóm)."""
    out = []
    for row in _rows(stem):
        first = row[0].strip()
        if not first:
            continue
        out.append((first, row[1].strip() if len(row) > 1 else ''))
    return tuple(out)


# Hồ sơ nào đọc file nào. Một hồ sơ có thể gộp nhiều file -- thực đơn và
# viện phí đều là nhiều nhóm hàng in chung một bảng.
ITEM_FILES: dict[str, tuple[str, ...]] = {
    'invoice': ('items_invoice', 'items_invoice_b'),
    'market': ('items_market',),
    'eatery': ('items_eatery',),
    'menu': ('catalogue_menu_appetizer', 'catalogue_menu_main',
             'catalogue_menu_dessert', 'catalogue_menu_b'),
    'bakery': ('items_bakery',),
    'hotel': ('items_hotel', 'items_hotel_b'),
    'export': ('items_export',),
    'admin': ('items_admin', 'items_admin_b'),
    'power': ('items_utility_power', 'items_utility_power_b'),
    'water': ('items_utility_water', 'items_utility_water_b'),
    'medical': (
    'catalogue_medical_kham',
    'catalogue_medical_thuoc',
    'catalogue_medical_xetnghiem',
    'catalogue_medical_chandoan',
    'catalogue_medical_vattu',
    'catalogue_medical_giuong',
    'catalogue_medical_thamdo',
    'catalogue_medical_phauthuat',
    'catalogue_medical_b',
),
    'insurance': (
    'catalogue_insurance_health_inpatient',
    'catalogue_insurance_health_outpatient',
    'catalogue_insurance_life',
    'catalogue_insurance_property',
    'catalogue_insurance_travel',
    'catalogue_insurance_b',
),
}
# Điều khoản đánh số. Khác ba bảng trên ở một chỗ: `clauses_chung` vào MỌI hồ
# sơ. Điều khoản chung -- hiệu lực, bất khả kháng, tranh chấp, bảo mật -- có
# trên mọi tờ giấy có hai bên ký, còn phần riêng theo hồ sơ mới là phần phân
# biệt một hợp đồng mua bán với một quy chế nội bộ.
#
# Hồ sơ không có file riêng (`hotel`, `market`, `menu`, `power`, `water`) rơi
# về chung + invoice: giấy của chúng là giấy mua bán.
# Phần CHUNG, vào mọi hồ sơ. Thêm một file vào tuple này là mọi loại chứng từ
# dài ra được thêm vài tờ, vì trần số tờ của một tài liệu chảy bằng điều khoản
# đúng bằng số điều đọc được ở đây -- xem `design.FLOW_BLOCKS`.
CLAUSE_COMMON: tuple[str, ...] = ('clauses_chung', 'clauses_chung_b',
                                  'clauses_chung_c')
CLAUSE_FILES: dict[str, tuple[str, ...]] = {
    'admin': ('clauses_admin', 'clauses_admin_b'),
    'invoice': ('clauses_invoice', 'clauses_invoice_b'),
    'insurance': ('clauses_insurance', 'clauses_insurance_b'),
    'medical': ('clauses_medical', 'clauses_medical_b'),
}
CLAUSE_FALLBACK: tuple[str, ...] = ('clauses_invoice', 'clauses_invoice_b')

SHOP_FILES: dict[str, str] = {
    'invoice': 'shops_invoice',
    'market': 'shops_market',
    'eatery': 'shops_eatery',
    'menu': 'shops_eatery',
    'bakery': 'shops_bakery',
    'hotel': 'shops_hotel',
    'export': 'shops_export',
    'admin': 'shops_admin',
    'power': 'shops_utility_power',
    'water': 'shops_utility_water',
    'medical': 'shops_medical',
    'insurance': 'shops_insurance',
}
FOOTER_FILES: dict[str, str] = {
    'invoice': 'footers_invoice',
    'market': 'footers_market',
    'eatery': 'footers_eatery',
    'menu': 'footers_eatery',
    'bakery': 'footers_bakery',
    'hotel': 'footers_hotel',
    'export': 'footers_export',
    'admin': 'footers_admin',
    'power': 'footers_utility_power',
    'water': 'footers_utility_water',
    'medical': 'footers_medical',
    'insurance': 'footers_insurance',
}

def catalogue(profile: str) -> tuple[tuple[str, int, int], ...]:
    """Mọi mặt hàng một hồ sơ có thể ghi, gộp từ các file của nó."""
    out = []
    for stem in ITEM_FILES.get(profile, ITEM_FILES['invoice']):
        out.extend(priced(stem))
    return tuple(out) or priced('items_invoice')


def shops(profile: str) -> tuple[tuple[str, str], ...]:
    return paired(SHOP_FILES.get(profile, 'shops_invoice')) or paired('shops_invoice')


def footers(profile: str) -> tuple[str, ...]:
    return lines(FOOTER_FILES.get(profile, 'footers_invoice')) or lines('footers_invoice')


# Chủ đề câu hỏi khai bằng file: `questions_<chủ đề>.txt`. Tên file LÀ tên chủ
# đề -- thêm một file là thêm một chủ đề, không phải sửa mã. Cùng lệ
# `clauses_*.txt`.
QUESTION_PREFIX = "questions_"

# Dạng nào nhận tham số gì. Bảng này là chỗ DUY NHẤT biết định dạng cột của
# `questions_*.txt`; `content.py` đọc kết quả đã dựng, không đọc lại file.
#
# `|` ngăn các mục BÊN TRONG một cột, `TAB` ngăn các cột -- nên một danh sách
# lựa chọn nằm gọn trong một cột và không đụng tới số cột của dòng.
QUESTION_PARAMS: dict[str, tuple[str, ...]] = {
    "blank": (),
    "yesno": (),
    "options": ("options",),
    "boxchar": ("cells",),
    "date_boxes": (),
    "grid": ("rows", "cols"),
    "scale": ("low_label", "high_label", "levels"),
    "rank": ("items",),
    "inline_blank": (),
    "subquestion": ("subs",),
    "table_form": ("cols", "lines"),
    "attachment": ("items",),
}
_LIST_PARAMS = frozenset({"options", "rows", "cols", "items", "subs"})
_INT_PARAMS = frozenset({"cells", "levels", "lines"})


def question_themes() -> dict[str, dict]:
    """`{chủ đề: {"items": (...), "answers": (...)}}` đọc từ corpus.

    `items` là tuple các dict đã dựng sẵn tham số, để `content.py` chỉ còn
    việc bốc trạng thái đã điền -- ô nào tích, số nào viết vào. Tách thế vì
    hai việc ấy đổi theo hai thứ khác nhau: định dạng câu hỏi là DỮ LIỆU,
    còn trạng thái điền là chuyện của từng tờ giấy.

    Dòng sai định dạng bị BỎ QUA chứ không làm chết lượt chạy, cùng lối
    `archetypes.load()`: một dòng hỏng là mất một câu hỏi, không phải mất cả
    bộ dữ liệu.
    """
    out: dict[str, dict] = {}
    if not CORPUS.is_dir():
        return out
    for path in sorted(CORPUS.glob(f"{QUESTION_PREFIX}*.txt")):
        theme = path.stem[len(QUESTION_PREFIX):]
        items: list[dict] = []
        answers: list[str] = []
        for row in _rows(path.stem):
            cells = [c.strip() for c in row]
            if len(cells) < 2:
                continue
            shape, prompt = cells[0], cells[1]
            if shape == "answer":
                answers.append(prompt)
                continue
            names = QUESTION_PARAMS.get(shape)
            if names is None:
                continue
            item: dict = {"shape": shape, "prompt": prompt}
            for index, name in enumerate(names):
                raw = cells[2 + index] if 2 + index < len(cells) else ""
                if name in _LIST_PARAMS:
                    item[name] = tuple(v.strip() for v in raw.split("|") if v.strip())
                elif name in _INT_PARAMS:
                    try:
                        item[name] = int(raw)
                    except ValueError:
                        item[name] = 0
                else:
                    item[name] = raw
            items.append(item)
        if items:
            out[theme] = {"items": tuple(items), "answers": tuple(answers)}
    return out


def items_for(arch, rules: dict | None = None) -> tuple[tuple[str, int, int], ...]:
    """Kho hàng hợp với PHÔI này, không chỉ với ngành của nó.

    `rules` là mục `items:` của `rulebase/synthgen/_blocks.yaml`, tra theo tên
    tài liệu. Không khớp mẫu nào thì rơi về `catalogue(profile)` như cũ -- kho
    theo ngành vẫn đúng cho hoá đơn, phiếu kho, viện phí.

    Gộp nhiều kho khi khớp nhiều mẫu, rồi mới trả về: một `bảng chấm công
    tăng ca` khớp cả `items_luong` lẫn (nếu có) kho khác thì bảng của nó được
    lấy từ cả hai, chứ không phải kho đầu tiên thắng."""
    out: list[tuple[str, int, int]] = []
    titles = " ".join(arch.titles).lower()
    for stem, rule in (rules or {}).items():
        words = (rule or {}).get("title_any") or ()
        if any(str(w).lower() in titles for w in words):
            out.extend(priced(stem))
    return tuple(out) or catalogue(arch.profile)


def clauses(profile: str) -> tuple[tuple[str, ...], ...]:
    """Mọi điều khoản một hồ sơ viết được: `(tiêu đề, khoản, khoản, ...)`.

    Đây là thứ cho một tờ giấy KHÔNG CÓ BẢNG dài ra: `synthgen/paginate.py`
    cắt trang theo số MỤC của khối chảy, và trước khi có kho này khối chảy
    duy nhất là bảng hàng -- nên mọi tài liệu nhiều trang trong bộ đều là một
    cái bảng."""
    out = []
    for stem in CLAUSE_COMMON + CLAUSE_FILES.get(profile, CLAUSE_FALLBACK):
        out.extend(spans(stem))
    return tuple(out) or spans('clauses_chung')


def people() -> tuple[str, ...]:
    return lines('people')


def streets() -> tuple[str, ...]:
    return lines('streets')


def wards() -> tuple[str, ...]:
    return lines('wards')


def payments() -> tuple[tuple[str, str], ...]:
    return paired('payments')


def sample(rng: random.Random, pool, count: int) -> list:
    """`count` phần tử KHÁC NHAU khi kho đủ dài; hết kho thì XÁO LẠI, không bốc lẻ.

    `random.sample` nổ khi xin nhiều hơn kho có, và một bảng 240 dòng rút từ
    kho 133 mặt hàng là chuyện bình thường -- một bảng kê tài sản dài in cùng
    một mặt hàng hai lần với số lượng khác nhau, đúng như đời thật.

    NHƯNG lặp thế nào thì quan trọng. Bản trước hết kho rồi `rng.choice` từng
    phần tử một, tức là bốc có hoàn lại: hai dòng LIỀN NHAU trùng nhau là
    chuyện thường gặp, và đo được trên một trang thật -- `Máy in đa chức
    năng` ở dòng 28 và 29. Không bảng kê nào trên đời in như thế.

    Xáo lại cả kho cho mỗi vòng thì khoảng cách giữa hai lần xuất hiện của
    cùng một mặt hàng ít nhất là... không, không đảm bảo được điều đó ở chỗ
    nối hai vòng. Cái đảm bảo được, và là cái đáng giá: trong BẤT KỲ cửa sổ
    `len(pool)` dòng liên tiếp nào NẰM GỌN trong một vòng, không có dòng nào
    lặp. Chỗ nối hai vòng được chặn riêng ở dưới."""
    pool = list(pool)
    if not pool:
        return []
    if count <= len(pool):
        return rng.sample(pool, count)
    out: list = []
    while len(out) < count:
        lap = rng.sample(pool, len(pool))
        # Chỗ NỐI hai vòng: phần tử cuối vòng trước và phần tử đầu vòng sau có
        # thể là một. Đổi chỗ phần tử đầu với một phần tử khác thì hết -- rẻ
        # hơn xáo lại cả vòng, và không làm lệch phân bố đáng kể.
        if out and len(lap) > 1 and lap[0] == out[-1]:
            swap = rng.randrange(1, len(lap))
            lap[0], lap[swap] = lap[swap], lap[0]
        out.extend(lap)
    return out[:count]
