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
    'invoice': ('items_invoice',),
    'market': ('items_market',),
    'eatery': ('items_eatery',),
    'menu': ('catalogue_menu_appetizer', 'catalogue_menu_main', 'catalogue_menu_dessert'),
    'bakery': ('items_bakery',),
    'hotel': ('items_hotel',),
    'export': ('items_export',),
    'admin': ('items_admin',),
    'power': ('items_utility_power',),
    'water': ('items_utility_water',),
    'medical': (
    'catalogue_medical_kham',
    'catalogue_medical_thuoc',
    'catalogue_medical_xetnghiem',
    'catalogue_medical_chandoan',
    'catalogue_medical_vattu',
    'catalogue_medical_giuong',
    'catalogue_medical_thamdo',
    'catalogue_medical_phauthuat',
),
    'insurance': (
    'catalogue_insurance_health_inpatient',
    'catalogue_insurance_health_outpatient',
    'catalogue_insurance_life',
    'catalogue_insurance_property',
    'catalogue_insurance_travel',
),
}
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


def people() -> tuple[str, ...]:
    return lines('people')


def streets() -> tuple[str, ...]:
    return lines('streets')


def wards() -> tuple[str, ...]:
    return lines('wards')


def payments() -> tuple[tuple[str, str], ...]:
    return paired('payments')


def sample(rng: random.Random, pool, count: int) -> list:
    """`count` phần tử KHÁC NHAU khi kho đủ dài, lặp lại khi không.

    `random.sample` nổ khi xin nhiều hơn kho có, và một bảng 40 dòng rút từ
    kho 30 mặt hàng là chuyện bình thường -- một hoá đơn dài in cùng một mặt
    hàng hai lần với số lượng khác nhau, đúng như đời thật."""
    pool = list(pool)
    if not pool:
        return []
    if count <= len(pool):
        return rng.sample(pool, count)
    out = rng.sample(pool, len(pool))
    while len(out) < count:
        out.append(rng.choice(pool))
    return out
