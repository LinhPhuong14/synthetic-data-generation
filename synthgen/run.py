"""Sinh một tập chứng từ tổng hợp. Bố cục soạn mới, không lấy từ phôi có sẵn.

    python synthgen/run.py -o data/09-09-26-synthetics -n 10000 --workers 14

Ra đúng năm thư mục, mỗi thư mục chia tiếp theo LOẠI chứng từ, cùng một tên
gốc ở cả năm, kèm một `manifest.jsonl`:

    images/       <loại>/<stem>.jpg    trang giấy
    html/         <loại>/<stem>.html   chính markup đã vẽ ra nó
    json/         <loại>/<stem>.json   bản ghi đầy đủ, có `kie` kèm mô tả trường
    layout_boxes/ <loại>/<stem>.json   `layout_annotations` của riêng trang ấy
                  <loại>/<stem>.jpg    chính các hộp ấy vẽ đè lên trang
    word_boxes/   <loại>/<stem>.json   `word_annotations`, kèm mô tả KIE từng từ
                  <loại>/<stem>.jpg    chính các hộp ấy vẽ đè lên trang

Ba lời hứa, và cả ba đều được KIỂM TRA chứ không phải hứa suông:

* **không trùng dáng** -- `design.signature()` là mọi quyết định nhìn thấy
  được của một tờ giấy, và tập chữ ký được lọc TRƯỚC khi mở trình duyệt;
* **không trùng nội dung** -- `Doc.content_signature()` băm tên đơn vị, số
  hiệu, ngày, tổng tiền và từng dòng hàng; trùng thì báo lại ở cuối lượt;
* **trang bị cắt lấp ít nhất 80%** -- `paginate.py` đo trong trình duyệt rồi
  mới chốt, và `report.json` ghi lại phân bố tỉ lệ lấp để đếm được.

Nghỉ giữa chừng thì chạy lại đúng lệnh ấy: mỗi shard để lại một tệp `DONE`,
và shard đã xong được bỏ qua.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import random
import socket
import shutil
import sys
import time
from collections import Counter

# Sàn tỉ lệ tài liệu được điền tay, và muối để tỉ lệ ấy không trùng với bất kỳ
# thứ gì khác cũng bốc từ `--seed`.
HAND_FLOOR = 0.30
HAND_SALT = 0x48414E44
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import descriptions  # noqa: E402
from synthgen import design as D  # noqa: E402
from synthgen.draw import KINDS  # noqa: E402

SHARD_DIR = '.shards'
DESCRIPTIONS = 'kie_descriptions.json'
NAMING = '{document}_{index:05d}'


def parse_pages(text: str):
    """`--pages` -> `(lo, hi)` hoặc `[((lo, hi), trọng số), ...]`. `None` là sai.

    Ba dạng, và dạng thứ ba là lý do hàm này tồn tại:

        3                  đúng ba tờ
        2-10               rải đều từ hai tới mười tờ
        2-5:75,7-10:25     75% tài liệu hai-tới-năm tờ, 25% bảy-tới-mười

    Một khoảng phẳng không dựng được phân bố hai cụm, mà hồ sơ ngoài đời là
    hai cụm: phần lớn vài tờ, một phần nhỏ rất dày. Trọng số không cần cộng
    thành 100 -- `design.pick_span` chuẩn hoá.

    TỪ CHỐI chứ không lặng lẽ về mặc định: một lượt chạy vài giờ khởi động
    bằng `--pages 2:5` mà vẫn vẽ theo mặc định là đúng thứ im lặng kho này
    liên tục bị cắn."""
    text = (text or '').replace('–', '-').strip()
    if not text:
        return None

    def one(chunk: str):
        parts = [p for p in chunk.split('-') if p.strip()]
        try:
            numbers = [int(p) for p in parts]
        except ValueError:
            return None
        if len(numbers) == 1:
            numbers = numbers * 2
        if len(numbers) != 2 or min(numbers) < 1:
            return None
        return (min(numbers), max(numbers))

    if ',' not in text and ':' not in text:
        return one(text)

    mixed = []
    for chunk in text.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        span_text, _, weight_text = chunk.partition(':')
        span = one(span_text.strip())
        if span is None:
            return None
        try:
            weight = float(weight_text) if weight_text.strip() else 1.0
        except ValueError:
            return None
        if weight < 0:
            return None
        mixed.append((span, weight))
    if not mixed or sum(w for _s, w in mixed) <= 0:
        return None
    return mixed


def unique_seeds(count: int, seed: int, *, spread: int = 64,
                 pages=None, multipage_only: bool = False,
                 balance: bool = True) -> list[int]:
    """`count` seed mà không hai seed nào cho ra cùng một DÁNG.

    Tính trước, trong tiến trình cha, trước khi bất kỳ trình duyệt nào mở ra:
    `design.draw` là hàm thuần của seed (nội dung rút từ một dòng ngẫu nhiên
    khác, xem `draw.CONTENT_SALT`), nên chữ ký dáng biết được mà không phải
    vẽ. Khử trùng sau khi vẽ thì cái giá là một trang đã render.

    QUOTA THEO LOẠI khi `balance` -- và đây là vế phải đọc kỹ.

    `design.draw` bốc phôi ĐỀU TAY, nhưng đi tuần tự đủ seed cho `count` chứng
    từ thì mỗi loại chỉ được bốc trúng `count/99` lần, và phép bốc đều ở cỡ
    mẫu ấy lệch rất rộng: đo trên một kế hoạch 1000 chứng từ, nhiều nhất 21
    lần và ít nhất 6 lần -- đúng dải một phép bốc đều sinh ra, không phải bug.
    `--multipage-only` rồi nhân cái lệch ấy với tỉ lệ sống của từng phôi, và
    kết quả là `so_ho_khau` hai bản còn `bien_ban_hop` hai mươi mốt bản.

    Quota chữa bằng cách ĐI THÊM SEED chứ không bằng cách đổi phép bốc: mỗi
    loại có một trần, và seed của loại đã đủ trần bị bỏ qua. Trần tự nới lên
    một bậc khi cả một vòng dài không nhận được gì -- không có vế ấy thì một
    lượt chạy đòi nhiều tờ sẽ quay mãi để tìm một loại không bao giờ đủ hai
    tờ (`phieu_gui_xe` là một). Cùng tinh thần `pipeline/plan.py::uncovered`
    của pipeline chính: mọi bố cục đều phải có ảnh.

    Cái giá là số seed phải đi qua, và nó được in ra ở `main()`."""
    chosen: list[int] = []
    seen = set()
    per = Counter()
    kinds = max(len(D.ARCHETYPES), 1)
    # Trần khởi điểm: chia đều, làm tròn lên. Với 1000 chứng từ và 99 phôi là
    # 11 bản mỗi loại.
    cap = max(-(-count // kinds), 1) if balance else count
    # Bao nhiêu lần bị trần chặn liên tiếp thì nới trần. Một vòng qua hết số
    # phôi vài lần: ngắn hơn thì nới quá sớm và quota không có tác dụng, dài
    # hơn thì lượt chạy đứng im.
    patience = kinds * 12
    stalled = 0
    candidate = seed
    tried = 0
    limit = count * spread + 10000
    while len(chosen) < count and tried < limit:
        plan = D.draw(random.Random(candidate), candidate, pages=pages)
        here = candidate
        candidate += 1
        tried += 1
        # LOẠI TỪ ĐÂY, không loại sau khi vẽ. `--multipage-only` bỏ mọi chứng
        # từ ra một tờ, và một chứng từ NHẮM một tờ thì chắc chắn ra một tờ --
        # `paginate.py` chỉ hạ số tờ xuống, không nâng lên. Vẽ nó rồi mới vứt
        # là trả tiền trình duyệt cho một tấm ảnh không ai giữ; đo trên một
        # kế hoạch 600 chứng từ: 124 tờ, hơn một phần năm lượt chạy.
        #
        # Cổng cuối vẫn ở `_shard`: phép đo trong trình duyệt mới nói số tờ
        # THẬT, và nó hạ được hai tờ xuống một.
        if multipage_only and plan.target_pages < 2:
            continue
        kind = plan.archetype.id
        if balance and per[kind] >= cap:
            stalled += 1
            if stalled >= patience:
                cap += 1
                stalled = 0
            continue
        signature = plan.signature()
        if signature in seen:
            continue
        seen.add(signature)
        chosen.append(here)
        per[kind] += 1
        stalled = 0
    return chosen


def _shard(job: dict, ticks=None) -> dict:
    """Một shard: một tiến trình, một trình duyệt, `len(seeds)` tài liệu.

    `ticks` là hàng đợi để BÁO TỪNG TÀI LIỆU về tiến trình cha. Không có nó thì
    thanh tiến độ chỉ nhích khi xong CẢ shard, và một lượt chạy `--shard 100`
    với 40 chứng từ đứng im ở 0% suốt rồi nhảy thẳng lên 100% -- đúng lỗi người
    dùng báo. Thanh tiến độ nói dối còn tệ hơn không có thanh nào.
    """
    out = Path(job['out'])
    marker = Path(job['marker'])
    if marker.exists():
        return {'shard': job['shard'], 'skipped': True, 'dropped': [],
                'rows': json.loads(marker.read_text(encoding='utf-8'))}

    os.environ['VLM_KIE_DESCRIPTIONS'] = job['descriptions']
    os.environ.setdefault('PYTHONWARNINGS', 'ignore')
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from synthgen.draw import Studio, write

    rows = []
    failures = []
    dropped = []
    started = time.time()
    # `pages` đã đi qua JSON, nên `(2, 10)` thành `[2, 10]` và hỗn hợp
    # `[((2,5),75), ...]` thành `[[[2,5],75], ...]`. `design.pick_span` nhận cả
    # hai hình dạng ấy, nên KHÔNG ép lại tuple ở đây: ép tuple làm hỗn hợp
    # thành một tuple hai phần tử và `pick_span` đọc nó như một khoảng.
    pages = job.get('pages')
    if isinstance(pages, list) and len(pages) == 2 and all(
            isinstance(v, int) for v in pages):
        pages = (pages[0], pages[1])
    with Studio(scale=job['scale'], jpeg_quality=job['quality'],
                augment=job.get('augment', 'off'),
                handwriting=job.get('handwriting', 'off'),
                hand_share=float(job.get('hand_share', 1.0)),
                pages=pages or None) as studio:
        for index, seed in zip(job['indices'], job['seeds']):
            try:
                drawn = studio.document(seed, index, job['naming'])
            except Exception as error:                       # noqa: BLE001
                failures.append(f'seed={seed}: {type(error).__name__}: {error}')
                continue
            # CHỈ NHIỀU TỜ. Lọc ở đây chứ không ở `unique_seeds`: số tờ
            # thật chỉ biết được SAU khi `paginate.py` đo trong trình duyệt,
            # và nó hạ số tờ xuống bất cứ khi nào không tờ nào lấp nổi 80%.
            # Lọc theo ý định thì vẫn lọt tờ lẻ vào bộ.
            if job.get('multipage_only') and len(drawn.images) < 2:
                # GHI CẢ LÝ DO, không chỉ số tờ. `plan_note` là câu
                # `paginate.py` viết ra khi nó hạ số tờ, và nó là thứ duy nhất
                # phân biệt "chứng từ này hết nội dung" với "ước lượng sức
                # chứa lạc quan quá". Đo trên một lượt 120 chứng từ: 62 bản bị
                # vứt, và không có câu này thì con số 62 không nói được nên
                # sửa ở đâu.
                dropped.append(f'{drawn.stem}: ra {len(drawn.images)} tờ'
                               + (f' -- {drawn.note}' if drawn.note else ''))
                continue
            page_rows = write(drawn, out, indent=job.get('indent'))
            for row in page_rows:
                row['design_signature'] = str(hash(drawn.design_signature))
                row['content_signature'] = drawn.content_signature
                row['plan_note'] = drawn.note
                row['plan_rounds'] = drawn.rounds
            rows.extend(page_rows)
            if ticks is not None:
                # Một nhịp cho mỗi TÀI LIỆU vẽ xong. Hàng đợi có thể đầy hoặc
                # tiến trình cha đã đi, và khi ấy mất một nhịp còn hơn giết cả
                # shard vì một cái thanh.
                try:
                    ticks.put_nowait(1)
                except Exception:                            # noqa: BLE001
                    pass
    payload = {'shard': job['shard'], 'rows': rows, 'failures': failures,
               'dropped': dropped,
               'seconds': round(time.time() - started, 2)}
    marker.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    if failures:
        marker.with_suffix('.failures.txt').write_text(
            '\n'.join(failures) + '\n', encoding='utf-8')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-o', '--out', type=Path,
                        default=REPO_ROOT / 'data' / '09-09-26-synthetics')
    parser.add_argument('-n', '--count', type=int, default=10000,
                        help='số CHỨNG TỪ; một chứng từ nhiều tờ ra nhiều ảnh')
    parser.add_argument('--seed', type=int, default=20260910)
    parser.add_argument('--workers', type=int, default=0,
                        help='0 = số CPU trừ 2')
    parser.add_argument('--shard', type=int, default=100,
                        help='số chứng từ mỗi tiến trình; mỗi shard một trình duyệt')
    parser.add_argument('--scale', type=float, default=2.0,
                        help='device scale factor lúc chụp; vẽ to rồi thu nhỏ')
    parser.add_argument('--quality', type=int, default=92, help='chất lượng JPEG')
    parser.add_argument('--raw', action='store_true',
                        help='chỉ vẽ, không chạy bước derive cuối lượt '
                             '(không có json gộp theo tài liệu, mô tả KIE '
                             'không đổi giọng)')
    parser.add_argument('--naming', default=NAMING)
    parser.add_argument('--handwriting', default='both',
                        help='both (mặc định) | font | model | off — rót chữ viết '
                             'tay vào các ô người ta điền, qua chính '
                             'generators/html/handwriting.py mà pipeline chính dùng. '
                             'model/both cần WriteViT; thiếu thì tự lùi về font')
    parser.add_argument('--hand-share', type=float, default=0.0, metavar='X',
                        help='tỉ lệ tài liệu được điền tay, 0..1. Mặc định 0 = '
                             f'bốc ngẫu nhiên cho mỗi lượt, sàn {HAND_FLOOR:g}')
    parser.add_argument('--augment', default='off',
                        help='off (mặc định, giấy sạch) | fast | all | none — '
                             'làm cũ ngay lúc vẽ qua degradation/ của pipeline '
                             'chính; xem synthgen/augment.py')
    # argparse nội suy chuỗi help THÊM MỘT LẦN nữa lúc in (`help % params`,
    # để `%(default)s` chạy được). Nên đừng nội suy sẵn bằng toán tử `%`:
    # `%%` qua lần một còn lại `%`, lần hai vấp ngay -- và vấp ở `--help`,
    # tức đúng lệnh đầu tiên người ta gõ. Dùng f-string cho phần thay số, và
    # giữ `%%` cho dấu phần trăm CHỮ để lần nội suy của argparse hạ về một dấu.
    parser.add_argument('--pages', default='', metavar='SPEC',
                        help='số TỜ mỗi chứng từ nhắm tới. Ba dạng: `3` (đúng '
                             'ba tờ), `2-10` (rải đều), `2-5:75,7-10:25` (75%% '
                             'hai-tới-năm tờ, 25%% bảy-tới-mười). Mặc định '
                             f'{D.PAGE_SPAN[0]}-{D.PAGE_SPAN[1]}. Chỉ là Ý ĐỊNH: '
                             '`synthgen/paginate.py` ĐO '
                             'trong trình duyệt rồi mới chốt, và hạ số tờ xuống '
                             'khi không tờ nào lấp nổi 80%%. Sàn lớn hơn 1 còn '
                             'ép thêm một khối CHẢY vào tờ giấy nào bốc phải '
                             'không có khối nào')
    parser.add_argument('--no-balance', action='store_true',
                        help='TẮT quota theo loại chứng từ. Mặc định là BẬT: '
                             'mỗi loại có một trần bằng `-n` chia số phôi, và '
                             'lượt chạy đi thêm seed cho tới khi mọi loại đủ '
                             'trần. Không có quota thì phép bốc đều ở cỡ mẫu '
                             'này lệch rất rộng -- đo trên 1000 chứng từ: loại '
                             'nhiều nhất 21 bản, ít nhất 2. Tắt khi cần đúng '
                             'một phép bốc đều để so sánh')
    parser.add_argument('--multipage-only', action='store_true',
                        help='CHỈ giữ chứng từ ra từ hai tờ trở lên. Khác '
                             '`--pages`: `--pages` là ý định, còn cờ này là '
                             'KẾT QUẢ -- `paginate.py` đo xong có thể hạ một '
                             'chứng từ xuống một tờ, và không có cờ này thì '
                             'một lượt xin toàn nhiều trang vẫn lẫn tờ lẻ. '
                             'Chứng từ bị loại không ghi ra đĩa và được đếm '
                             'lại trong `report.json`')
    parser.add_argument('--indent', type=int, default=0, metavar='N',
                        help='thụt lề JSON nhãn; 0 = gọn (mặc định). Bản ghi ra đĩa một lần cho MỖI TRANG, nên thụt lề nhân với số trang chứ không với số bản ghi')
    # Chọn seed và in phân bố mà không mở trình duyệt: rẻ, và là cách xem
    # lượt chạy sẽ ra những loại giấy nào trước khi bỏ ra vài giờ.
    parser.add_argument('--dry-run', action='store_true',
                        help='chỉ chọn seed và in phân bố, không mở trình duyệt')
    args = parser.parse_args()

    # `--pages LO-HI` -> `(lo, hi)`. Từ chối chứ không lặng lẽ về mặc định:
    # một lượt chạy vài giờ khởi động bằng `--pages 2:10` mà vẫn vẽ một tờ là
    # đúng thứ im lặng kho này liên tục bị cắn.
    pages = None
    if args.pages:
        pages = parse_pages(args.pages)
        if pages is None:
            print(f'[synthgen] --pages {args.pages!r} không đọc được. Viết một '
                  'trong ba dạng:\n'
                  '    --pages 3                 đúng ba tờ\n'
                  '    --pages 2-10              rải đều từ hai tới mười tờ\n'
                  '    --pages 2-5:75,7-10:25    75% hai-tới-năm tờ, 25% bảy-tới-mười',
                  file=sys.stderr)
            return 2

    out = args.out.resolve()
    shards_dir = out / SHARD_DIR
    shards_dir.mkdir(parents=True, exist_ok=True)

    # Bao nhiêu phần trăm tài liệu được điền tay. Bốc MỘT LẦN cho cả lượt và
    # bốc từ chính `--seed`, nên hai lượt cùng seed ra cùng tỉ lệ; `--hand-share`
    # ghim lại khi cần một con số cố định để so.
    #
    # Sàn 30%: dưới ngưỡng ấy thì một bộ vài nghìn ảnh có quá ít trang viết tay
    # để mô hình học được nét chữ, mà vẫn đủ nhiều để không ai nhận ra là thiếu.
    share = args.hand_share
    if args.handwriting in ('', 'off'):
        share = 0.0
    elif share <= 0:
        share = random.Random(args.seed ^ HAND_SALT).uniform(HAND_FLOOR, 1.0)
    share = max(0.0, min(1.0, share))

    started = time.time()
    seeds = unique_seeds(args.count, args.seed, pages=pages,
                         multipage_only=bool(args.multipage_only),
                         balance=not args.no_balance)
    # Ngăn chỉ dựng cho loại chứng từ lượt này THẬT SỰ vẽ. Loại nào không bốc
    # trúng thì không có ngăn rỗng nằm đó -- một thư mục rỗng đọc lên như "loại
    # này có mà không sinh được ảnh nào", trong khi sự thật là nó không được
    # gọi tên.
    #
    # Suy từ chính seed: `design.draw` quyết loại chứng từ trước mọi thứ khác
    # và không cần trình duyệt, nên biết trước được -- đo: 20 000 seed hết
    # 1,6 giây. Vẫn dựng SẴN ở tiến trình cha vì lý do cũ: mười bốn tiến trình
    # con cùng `mkdir` một đường dẫn là mười bốn lần chạy đua, và `exist_ok`
    # che được lỗi chứ không che được cái nửa-tạo mà tiến trình khác nhìn thấy.
    drawn_kinds = sorted({D.draw(random.Random(s), s, pages=pages).archetype.id
                          for s in seeds})
    for kind in KINDS:
        for name in drawn_kinds:
            (out / kind / name).mkdir(parents=True, exist_ok=True)
    if len(seeds) < args.count:
        print(f'[synthgen] chỉ tìm được {len(seeds)}/{args.count} dáng khác nhau'
              ' — không gian dáng đã cạn, nới ngữ pháp ở synthgen/design.py')
        return 1
    plans = [D.draw(random.Random(s), s, pages=pages) for s in seeds]
    spread = Counter(p.archetype.id for p in plans)
    print(f'[synthgen] {len(seeds)} chứng từ, {len(spread)} loại, '
          f'{min(spread.values())}–{max(spread.values())} tờ mỗi loại')

    described = descriptions.write(out / DESCRIPTIONS)
    os.environ['VLM_KIE_DESCRIPTIONS'] = str(out / DESCRIPTIONS)
    print(f'[synthgen] {described} mô tả trường KIE -> {out / DESCRIPTIONS}')

    aim = Counter(p.target_pages for p in plans)
    flows = Counter(p.flow or '(khong)' for p in plans)
    has_table = sum(1 for p in plans if 'table' in p.blocks)
    many = sum(n for sheets, n in aim.items() if sheets > 1)
    total = max(len(plans), 1)
    print('[synthgen] nhắm số tờ: '
          + ', '.join(f'{sheets} tờ x{n}' for sheets, n in sorted(aim.items())))
    print('[synthgen] khối chảy: '
          + ', '.join(f'{k} x{n}' for k, n in flows.most_common())
          + f' | có bảng {has_table / total:.0%}'
          + f' | nhiều tờ {many / total:.0%}')

    if args.dry_run:
        for name, number in spread.most_common():
            print(f'    {name:28s} {number}')
        return 0

    size = max(args.shard, 1)
    jobs = []
    for start in range(0, len(seeds), size):
        block = seeds[start:start + size]
        number = start // size
        jobs.append({
            'shard': number,
            'out': str(out),
            'marker': str(shards_dir / f'shard-{number:04d}.json'),
            'descriptions': str(out / DESCRIPTIONS),
            'seeds': block,
            'indices': list(range(start, start + len(block))),
            'naming': args.naming,
            'scale': args.scale,
            'quality': args.quality,
            'augment': args.augment,
            'handwriting': args.handwriting,
            'hand_share': share,
            'indent': args.indent or None,
            'pages': pages or None,
            'multipage_only': bool(args.multipage_only),
        })

    workers = args.workers or max(os.cpu_count() or 2, 3) - 2
    workers = max(1, min(workers, len(jobs)))
    if share:
        print(f'[synthgen] chữ viết tay: {args.handwriting}, '
              f'{share:.0%} số tài liệu')
    if args.multipage_only:
        print('[synthgen] --multipage-only: chứng từ ra một tờ sẽ bị loại, '
              'nên số chứng từ ra ít hơn số xin')
    print(f'[synthgen] {len(jobs)} shard x {size} chứng từ, {workers} tiến trình')

    import concurrent.futures as cf

    from pipeline.progress import Bar  # noqa: PLC0415

    # SỔ CHẠY, ghi ngay từ đầu và cập nhật sau mỗi shard. Đây là thứ trả lời
    # "lượt trước làm tới đâu" khi tiến trình chết giữa chừng: `manifest.jsonl`
    # chỉ ra đời ở dòng cuối, `report.json` cũng thế, nên một lượt bị giết để
    # lại đầy đủ ảnh mà không một dòng nào nói nó đã chạy bao lâu, mấy worker,
    # xong mấy shard. `.shards/` biết đủ để CHẠY TIẾP nhưng không biết gì để
    # KỂ LẠI.
    book = out / 'run.json'
    started_at = _dt.datetime.now().astimezone()

    def note(state: str) -> None:
        book.write_text(json.dumps({
            'state': state,
            'pid': os.getpid(),
            'command': ' '.join(sys.argv),
            'started': started_at.isoformat(timespec='seconds'),
            'updated': _dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            'seconds': round(time.time() - started, 1),
            'documents_asked': len(seeds),
            'workers': workers,
            'shards': len(jobs),
            'shard_size': size,
            'shards_done': done,
            'images_so_far': len(rows),
            'failures_so_far': len(failures),
            'seed': args.seed,
            'handwriting': args.handwriting,
            'augment': args.augment,
        }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    rows = []
    failures = []
    dropped_docs = []
    done = 0
    note('đang chạy')
    import multiprocessing as mp

    manager = mp.Manager()
    ticks = manager.Queue()
    ticked = 0
    with cf.ProcessPoolExecutor(max_workers=workers) as pool, \
            Bar(total=len(seeds), label='chứng từ') as bar:
        futures = {pool.submit(_shard, job, ticks): job for job in jobs}

        def drain() -> None:
            """Mọi nhịp đã đến, đẩy vào thanh. Không chặn."""
            nonlocal ticked
            while True:
                try:
                    ticks.get_nowait()
                except Exception:                            # noqa: BLE001
                    return
                ticked += 1
                bar.advance(1)

        # `timeout` chứ không `as_completed` trần: phải quay lại vét hàng đợi
        # đều đặn, nếu không thanh chỉ nhích mỗi lần một shard xong -- đúng cái
        # vừa sửa. Nửa giây đủ mượt mà không tốn gì.
        pending = set(futures)
        while pending:
            finished, pending = cf.wait(pending, timeout=0.5)
            drain()
            for future in finished:
                job = futures[future]
                try:
                    payload = future.result()
                except Exception as error:                   # noqa: BLE001
                    failures.append(f'shard {job["shard"]}: {error}')
                    note('đang chạy')
                    continue
                rows.extend(payload['rows'])
                failures.extend(payload.get('failures') or [])
                dropped_docs.extend(payload.get('dropped') or [])
                done += 1
                if payload.get('skipped'):
                    # Shard lấy từ `.shards/` không vẽ gì nên không gửi nhịp
                    # nào; đẩy bù để thanh vẫn tới 100%.
                    bar.advance(len(job['seeds']), note='sẵn có')
                    ticked += len(job['seeds'])
                note('đang chạy')
        drain()
        if ticked < len(seeds):
            bar.advance(len(seeds) - ticked)

    rows.sort(key=lambda row: (row['document'], row['page_number']))
    (out / 'manifest.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
        encoding='utf-8')

    payload = summarise(rows, failures, seconds=round(time.time() - started, 1),
                        dropped_docs=dropped_docs)
    # HIỆU NĂNG vào chính báo cáo. `seconds` một mình không so được hai lượt
    # chạy: mười phút trên hai worker và mười phút trên mười sáu là hai chuyện
    # khác hẳn, và không có dòng nào nói cái nào là cái nào.
    spent = max(time.time() - started, 1e-6)
    payload['run'] = {
        'started': started_at.isoformat(timespec='seconds'),
        'finished': _dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'seconds': round(spent, 1),
        'workers': workers,
        'shards': len(jobs),
        'shard_size': size,
        'documents_per_second': round(len(seeds) / spent, 2),
        'images_per_second': round(len(rows) / spent, 2),
        'seconds_per_image': round(spent / max(len(rows), 1), 3),
        'seed': args.seed,
        'handwriting': args.handwriting,
        'augment': args.augment,
        'command': ' '.join(sys.argv),
        'host': socket.gethostname(),
        'cpus': os.cpu_count(),
    }
    (out / 'report.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')

    print(f'\n[synthgen] {payload["images"]} ảnh / {payload["documents"]} chứng từ -> '
          f'{out}')
    # `.get`, không `[...]`: một lượt chạy nhỏ có thể không có tài liệu một tờ
    # nào, và khi ấy dòng tổng kết này làm nổ cả lượt chạy ĐÃ GHI XONG hết --
    # gặp thật khi vẽ lại đúng một chứng từ hai tờ để đối chiếu.
    print(f'[synthgen] một tờ: {payload["pages"].get("1", 0)}, hai tờ: '
          f'{payload["pages"].get("2", 0)}, ba tờ trở lên: '
          f'{sum(v for k, v in payload["pages"].items() if int(k) >= 3)}')
    cut = payload['fill_on_cut_pages']
    print(f'[synthgen] trang bị cắt: {cut["pages"]} trang, lấp trung vị '
          f'{cut["median"]:.0%}, thấp nhất {cut["min"]:.0%}, dưới 80%: '
          f'{cut["under_80"]}')
    print(f'[synthgen] dáng khác nhau: {payload["distinct_designs"]}, '
          f'nội dung khác nhau: {payload["distinct_content"]}')
    if failures:
        print(f'[synthgen] {len(failures)} trang hỏng — xem report.json')
    if dropped_docs:
        # NÓI RA. `--multipage-only` loại chứng từ một tờ, và một lượt xin 500
        # mà ra 380 là chuyện phải đọc được ngay trên màn hình, không phải một
        # con số người ta tự phát hiện lúc đếm file.
        print(f'[synthgen] {len(dropped_docs)} chứng từ bị loại vì chỉ ra một '
              'tờ (--multipage-only)')
    # Và dọn nốt ngăn nào vẫn rỗng: loại chứng từ được bốc trúng nhưng MỌI tờ
    # của nó đều hỏng lúc vẽ. Biết trước từ seed không đủ để loại trừ ca ấy,
    # nên quét lại sau mới chắc.
    empty = 0
    for kind in KINDS:
        for ngan in sorted((out / kind).glob('*')):
            if ngan.is_dir() and not any(ngan.iterdir()):
                ngan.rmdir()
                empty += 1
    if empty:
        print(f'[synthgen] dọn {empty} ngăn rỗng (loại chứng từ không ra tờ nào)')

    # `.shards/` là dấu vết để CHẠY LẠI tiếp được giữa chừng. Lượt đã xong thì
    # nó hết việc, và để lại là để lại một cái bẫy: lần sau ai đó chạy cùng
    # lệnh vào cùng thư mục sẽ được báo "(sẵn có)" cho mọi shard và không vẽ
    # gì -- đúng cái người ta muốn khi resume, đúng cái người ta KHÔNG muốn khi
    # định vẽ lại. Chỉ dọn khi không tờ nào hỏng: còn lỗi thì còn cần resume.
    if not failures:
        shutil.rmtree(shards_dir, ignore_errors=True)
    # Một dòng cho mỗi lượt, NỐI THÊM chứ không ghi đè: so hai lượt chạy với
    # nhau là việc người ta làm nhiều nhất sau khi đổi một tham số, và một file
    # bị ghi đè thì không so được với gì.
    with open(out.parent / 'synthgen_runs.jsonl', 'a', encoding='utf-8') as book_all:
        book_all.write(json.dumps({'out': out.name, **payload['run'],
                                   'images': payload['images'],
                                   'documents': payload['documents'],
                                   'failures': payload['failure_count']},
                                  ensure_ascii=False) + '\n')
    note('xong' if not failures else 'xong, có lỗi')
    run = payload['run']
    print(f'[synthgen] {run["seconds"]:.0f}s, {workers} tiến trình, '
          f'{run["images_per_second"]:.2f} ảnh/s, '
          f'{run["seconds_per_image"]:.2f}s mỗi ảnh')
    print(f'[synthgen] sổ chạy -> {out / "run.json"}  |  '
          f'nhật ký -> {out.parent / "synthgen_runs.jsonl"}')
    print(f'[synthgen] báo cáo -> {out / "report.json"}')

    # BƯỚC CUỐI, chạy luôn ở đây chứ không để thành một lệnh thứ hai người phải
    # nhớ. Đây là chỗ đã cắn hai lần: người dùng mở `json/` ra, thấy ba file cho
    # một chứng từ ba tờ và thấy mọi file mô tả trường bằng cùng một câu -- vì
    # cả hai thứ ấy do `derive.py` làm, và `derive.py` chưa ai chạy.
    #
    # Một lượt chạy phải để lại một BỘ DỮ LIỆU DÙNG ĐƯỢC, không phải nguyên
    # liệu cho một lệnh nữa. `--raw` cho ai thật sự chỉ muốn phần vẽ.
    if not args.raw:
        print()
        from synthgen.derive import main as derive_main  # noqa: PLC0415

        argv = sys.argv
        sys.argv = ['derive', str(out), '--workers', str(workers)]
        try:
            derive_main()
        finally:
            sys.argv = argv
    return 1 if failures else 0


def summarise(rows: list[dict], failures: list[str], seconds: float,
              dropped_docs: list[str] | None = None) -> dict:
    pages = Counter(str(row['pages_in_document']) for row in rows
                    if row['page_number'] == 1)
    cut = [row['fill'] for row in rows
           if row['pages_in_document'] > 1 and row.get('fill') is not None]
    cut.sort()
    single = [row['fill'] for row in rows
              if row['pages_in_document'] == 1 and row.get('fill') is not None]
    single.sort()

    def band(values: list[float]) -> dict:
        if not values:
            return {'pages': 0, 'median': 0.0, 'min': 0.0, 'max': 0.0,
                    'under_80': 0, 'over_100': 0}
        return {
            'pages': len(values),
            'median': round(values[len(values) // 2], 4),
            'min': round(values[0], 4),
            'max': round(values[-1], 4),
            'under_80': sum(1 for v in values if v < 0.8),
            'over_100': sum(1 for v in values if v > 1.0),
        }

    return {
        'images': len(rows),
        'documents': sum(1 for row in rows if row['page_number'] == 1),
        'seconds': seconds,
        'pages': dict(sorted(pages.items())),
        'by_archetype': dict(Counter(row['archetype'] for row in rows
                                     if row['page_number'] == 1).most_common()),
        'fill_on_cut_pages': band(cut),
        'fill_on_single_pages': band(single),
        'distinct_designs': len({row['design_signature'] for row in rows}),
        'distinct_content': len({row['content_signature'] for row in rows}),
        'word_boxes': sum(row['word_box_count'] for row in rows),
        'layout_boxes': sum(row['layout_box_count'] for row in rows),
        'kie_pairs': sum(row['kie_pairs'] for row in rows),
        'plan_notes': dict(Counter(row.get('plan_note', '') for row in rows
                                   if row.get('plan_note')).most_common(10)),
        'failures': failures[:200],
        'failure_count': len(failures),
        'dropped_single_page': (dropped_docs or [])[:200],
        'dropped_single_page_count': len(dropped_docs or []),
    }


if __name__ == '__main__':
    os.environ.setdefault('PYTHONWARNINGS', 'ignore')
    raise SystemExit(main())
