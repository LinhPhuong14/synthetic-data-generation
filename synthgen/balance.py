"""Bộ này có CÂN không — đo mà không mở trình duyệt.

    python synthgen/balance.py                 # 1500 tờ, --pages 2-10
    python synthgen/balance.py 3000 1-4        # số tờ, khoảng trang

`markup()` là hàm thuần của `(design, doc, slices)`, nên đếm được `data-region`
trên vài nghìn tờ trong vài giây. Đây là thứ phải chạy TRƯỚC và SAU mỗi lần
chỉnh `rulebase/synthgen/_blocks.yaml` — chỉnh trước rồi đo sau là cách đổi
một cái lệch này lấy một cái lệch khác mà vẫn thấy mình đang sửa. Kho này đã
làm đúng thế hai lần: `Table` 77%, rồi `List-Group` 82%.

HAI PHÉP ĐO, và phải đọc cả hai:

* **cả bộ** -- nhãn vùng nào có mặt trên bao nhiêu phần trăm số tờ;
* **tờ giữa** -- tài liệu từ ba tờ trở lên, bỏ tờ đầu và tờ cuối, thì các tờ
  còn lại có gì.

Bộ cân theo phép đo thứ nhất vẫn trượt phép đo thứ hai, và đã trượt: cả bộ cân
(List-Group 44%, Form 27%, Figure 20%) trong khi 100% tờ giữa chỉ có đúng một
khối chảy chạy từ mép trên xuống mép dưới. Một mô hình học trên bộ ấy học rằng
trang giữa của tài liệu dài thì không có gì.

KHÔNG NUỐT LỖI. Bản đầu của phép đo này `except: continue`, nên nó in "1318
tờ" khi được xin 1500 và con số ấy đọc như thể đủ -- 182 tờ chết vì một phôi
khai `columns: []` mà không ai thấy. Số tờ hỏng in ra trước mọi con số khác.
"""
from __future__ import annotations

import collections
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import content as C  # noqa: E402
from synthgen import design as D  # noqa: E402
from synthgen import markup as M  # noqa: E402

REGION = re.compile(r'data-region="([^"]+)"')
FLOW = re.compile(r'data-flow="([^"]+)"')
# Nhãn vùng của RIÊNG khối chữ ký. Trong bảng "cả bộ" nó lẫn vào `Text` cùng
# mọi khối chữ khác, nên đếm riêng -- và đây đúng là chỗ đã sai lặng lẽ một
# lần: `_blocks.yaml` khai `Form` trong khi `pipeline/record.py` khai `Text`.
SIGNS = re.compile(r'class="signs[^"]*"[^>]*data-region="([^"]+)"')
SHEET = '<div class="sheet">'

# Khối không có `data-region` riêng thì nhận diện bằng class của chính nó.
# Bảng và ô dán ảnh nằm trong nhóm ấy, và đó đúng là hai thứ người ta hỏi tới
# nhiều nhất -- đếm theo nhãn thôi thì chúng vô hình.
BY_CLASS = (
    ('class="items"', 'table'), ('class="photo"', 'photo'),
    ('class="cols"', '2-3 cột'), ('class="fields"', 'fields'),
    ('class="notes"', 'notes'), ('class="checks"', 'checks'),
    ('class="fml"', 'formula'), ('class="toc"', 'toc'),
    ('class="fig"', 'figure'), ('class="summary"', 'summary'),
)


def items_of(doc: C.Doc, flow: str):
    """Các mục của khối chảy. Lấy theo ĐÚNG khối chảy, không đoán.

    Lấy `doc.rows` rồi mới tới `doc.clauses` là cách phép đo trước đánh rơi
    nhãn `Form`: tài liệu chảy bằng câu hỏi ra lát `(0, 0)`, khối rỗng, và
    `Form` biến mất khỏi bảng kết quả chứ không khỏi bộ dữ liệu."""
    return {'table': doc.rows, 'clauses': doc.clauses,
            'questions': doc.questions}.get(flow, ())


def draw_one(seed: int, span: tuple[int, int]):
    """`(design, html)` của một tờ giấy, hoặc ném. Không bắt ngoại lệ ở đây."""
    d = D.draw(random.Random(seed), seed, pages=span)
    doc = C.build(d, random.Random(seed ^ 0x9E3779B9),
                  max(d.target_pages * 12, 6))
    total = len(items_of(doc, d.flow))
    pages = max(d.target_pages, 1)
    if total >= pages > 1:
        step = total // pages
        slices = [(i * step, (i + 1) * step if i < pages - 1 else total)
                  for i in range(pages)]
    else:
        slices = [(0, total)]
    return d, M.markup(doc, slices)


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    span = (tuple(int(x) for x in sys.argv[2].split('-'))
            if len(sys.argv) > 2 else (2, 10))

    reg, reg_sheets = collections.Counter(), collections.Counter()
    flows, aimed = collections.Counter(), collections.Counter()
    inner_blocks, inner_regions = collections.Counter(), collections.Counter()
    broke = collections.Counter()
    sheets_seen = inner_seen = inner_flow_only = docs = long_docs = 0
    # DÁNG TỜ GIẤY -- các mục tiêu đặt ra bằng lời ("chỉ A4", "bảng >=5 cột",
    # "3 tầng tiêu đề", "chữ ký là chữ") chỉ là lời cho tới khi đếm được.
    papers, tiers, rows_g, signs = (collections.Counter() for _ in range(4))
    wide_cols = tabled = 0
    orders: set[tuple[str, ...]] = set()

    for seed in range(count):
        try:
            d, html = draw_one(seed, span)
        except Exception as error:                        # noqa: BLE001
            broke[f'{type(error).__name__}: {error}'] += 1
            continue
        docs += 1
        flows[d.flow or '(khong)'] += 1
        aimed[d.target_pages] += 1
        papers[d.paper.id] += 1
        orders.add(d.order)
        signs.update(SIGNS.findall(html))
        if 'table' in d.blocks or d.flow == 'table':
            tabled += 1
            tiers[d.head_tiers] += 1
            rows_g[d.row_groups] += 1
            wide_cols += len(d.columns) >= 5
        pages = html.split(SHEET)[1:]
        for sheet in pages:
            sheets_seen += 1
            for label in set(REGION.findall(sheet)):
                reg[label] += len(REGION.findall(sheet))
                reg_sheets[label] += 1
        if len(pages) < 3:
            continue
        long_docs += 1
        for sheet in pages[1:-1]:
            inner_seen += 1
            if sheet.count('class="blk"') <= 1 and FLOW.findall(sheet):
                inner_flow_only += 1
            for label in set(REGION.findall(sheet)) - {'Watermark'}:
                inner_regions[label] += 1
            for marker, name in BY_CLASS:
                if marker in sheet:
                    inner_blocks[name] += 1

    if broke:
        print(f'!! {sum(broke.values())} TỜ HỎNG — sửa trước khi đọc số nào khác')
        for message, n in broke.most_common(5):
            print(f'   {n:5d}  {message[:110]}')
        print()

    pages_label = f'--pages {span[0]}-{span[1]}'
    print(f'{docs} tài liệu, {sheets_seen} tờ   {pages_label}')
    print('  khối chảy: '
          + ', '.join(f'{k} {v / max(docs, 1):.0%}' for k, v in flows.most_common()))
    print('  nhắm số tờ: '
          + ', '.join(f'{k}:{v}' for k, v in sorted(aimed.items())))

    pct = lambda n, d: f'{n / max(d, 1):.0%}'
    print(f'\nDÁNG TỜ GIẤY — {docs} tài liệu')
    print('  khổ giấy:  '
          + ', '.join(f'{k} {pct(v, docs)}' for k, v in papers.most_common()))
    print(f'  trình tự khối khác nhau: {len(orders)}/{docs}')
    print('  khối chữ ký nhãn: '
          + (', '.join(f'{k} {v}' for k, v in signs.most_common()) or '(khong)'))
    if tabled:
        print(f'  có bảng: {tabled} ({pct(tabled, docs)} số tài liệu)')
        print(f'    >=5 cột:      {pct(wide_cols, tabled)}')
        print('    tầng tiêu đề: '
              + ', '.join(f'{k} tầng {pct(v, tabled)}'
                          for k, v in sorted(tiers.items())))
        print('    nhóm dòng:    '
              + ', '.join(f'{k} {pct(v, tabled)}' for k, v in rows_g.most_common()))

    print(f"\n{'NHÃN VÙNG — CẢ BỘ':26s} {'hộp':>7s} {'% tờ có':>9s}")
    for label, n in reg.most_common():
        print(f'  {label:24s} {n:7d} {reg_sheets[label] / max(sheets_seen, 1):8.0%}')

    print(f'\nTỜ GIỮA — {long_docs} tài liệu >=3 tờ, {inner_seen} tờ giữa')
    if inner_seen:
        print(f'  chỉ có khối chảy: {inner_flow_only / inner_seen:.0%}'
              f'  ({inner_flow_only}/{inner_seen})')
        for name, n in inner_blocks.most_common():
            print(f'    {name:24s} {n / inner_seen:5.0%}')
        for label, n in inner_regions.most_common():
            print(f'    {label:24s} {n / inner_seen:5.0%}  (nhãn)')
    return 1 if broke else 0


if __name__ == '__main__':
    raise SystemExit(main())
