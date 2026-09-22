#!/usr/bin/env python3
"""Kiểm tra một tập đã sinh: hộp có đúng chỗ không, số có khớp không.

    python synthgen/check.py data/09-09-26-synthetics
    python synthgen/check.py data/09-09-26-synthetics --sample 500

Bảy điều được kiểm, và mỗi điều là một cách tập dữ liệu có thể sai mà nhìn
ảnh thì không thấy:

1. **Đủ file.** Mỗi ảnh có đủ `html/`, `records/`, ảnh vẽ hộp của
   `layout_boxes/` và `word_boxes/` cùng tên gốc, trong đúng ngăn
   theo loại chứng từ. Một trang thiếu nhãn là một trang huấn luyện âm thầm
   sai.
2. **Kích thước khớp.** Ảnh trên đĩa đúng bằng `width`/`height` trong bản ghi.
   Lệch một pixel ở đây là lệch mọi hộp trên trang.
3. **Hộp nằm trong trang.** Không hộp nào âm, tràn mép, hay có diện tích 0.
4. **Hộp có chữ.** Không hộp từ nào rỗng, và không chữ nào không có hộp.
5. **Chỉ số trỏ đúng.** `word.layout_region_index` và `word.entity_index`
   trỏ vào phần tử có thật của chính bản ghi ấy. Và mọi cặp KIE có hộp cho
   GIÁ TRỊ; hộp cho KHOÁ thì chỉ bắt buộc khi trên giấy có in nhãn ấy thật.
6. **Số khớp nhau.** Thành tiền = số lượng x đơn giá trên từng dòng, và tổng
   tiền hàng = tổng cột thành tiền. Đây là chỗ một tập dữ liệu OCR hỏng mà
   không ai nhìn ra: chữ sắc nét, hộp đúng chỗ, con số vô nghĩa.
7. **Luật 80%.** Mọi trang của một chứng từ NHIỀU TỜ lấp ít nhất 80% khổ
   giấy. Trang đơn không bị ràng buộc -- một biên nhận ba dòng là tờ giấy
   thật; nó chỉ không được tràn.

Ra mã 0 khi sạch, 1 khi có lỗi. In tối đa `--show` lỗi mỗi loại.
"""
from __future__ import annotations

import argparse
import json
import re
import random
import sys
from collections import Counter
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import overlay as O  # noqa: E402

MIN_FILL = 0.8

# Sai số cho phép khi so tiền: mọi số in ra đều là số nguyên đồng, nên một
# đồng lệch là làm tròn chứ không phải sai phép tính.
MONEY_SLACK = 1


def _int(text: str) -> int | None:
    """Số đọc từ một ô đã định dạng: "1.234.000" -> 1234000. Trả None khi ô
    không phải số -- "KCT", "Không chịu thuế", một ngày tháng."""
    keep = ''.join(ch for ch in str(text) if ch.isdigit())
    if not keep or any(ch.isalpha() for ch in str(text)):
        return None
    return int(keep)


def check_record(record: dict, image_path: Path, row: dict,
                 problems: Counter, examples: dict[str, list[str]]) -> None:
    def fail(kind: str, detail: str) -> None:
        problems[kind] += 1
        examples.setdefault(kind, [])
        if len(examples[kind]) < 6:
            examples[kind].append(detail)

    stem = image_path.stem
    number = int(row['page_number'])
    pages = record.get('pages') or []
    meta = pages[min(number - 1, len(pages) - 1)] if pages else {}
    width, height = int(meta.get('width') or 0), int(meta.get('height') or 0)

    image = cv2.imread(str(image_path))
    if image is None:
        fail('ảnh không đọc được', stem)
        return
    if (image.shape[1], image.shape[0]) != (width, height):
        fail('kích thước ảnh lệch bản ghi',
             f'{stem}: ảnh {image.shape[1]}x{image.shape[0]} != nhãn {width}x{height}')

    words = [w for w in record.get('word_annotations') or []
             if int(w.get('page_number', 1) or 1) == number]
    regions = [r for r in record.get('layout_annotations') or []
               if int(r.get('page_number', 1) or 1) == number]
    entities = record.get('entity_annotations') or []

    if not words:
        fail('trang không có hộp từ nào', stem)
    for word in words:
        box = word.get('bbox') or []
        if len(box) != 4:
            fail('hộp từ sai dạng', f'{stem}: {box}')
            continue
        x1, y1, x2, y2 = box
        if x2 <= x1 or y2 <= y1:
            fail('hộp từ diện tích 0', f'{stem}: {box} ({word.get("text")!r})')
        if x1 < -1 or y1 < -1 or x2 > width + 1 or y2 > height + 1:
            fail('hộp từ ra ngoài trang',
                 f'{stem}: {box} ngoài {width}x{height}')
        if not str(word.get('text', '')).strip():
            fail('hộp từ không có chữ', f'{stem}: {box}')
        index = word.get('entity_index')
        if isinstance(index, int) and not (0 <= index < len(entities)):
            fail('word.entity_index trỏ ra ngoài', f'{stem}: {index}')
        index = word.get('layout_region_index')
        all_regions = record.get('layout_annotations') or []
        if isinstance(index, int) and not (0 <= index < len(all_regions)):
            fail('word.layout_region_index trỏ ra ngoài', f'{stem}: {index}')
        elif isinstance(index, int):
            # TRỎ ĐÚNG CHỖ, không chỉ trỏ TRONG MẢNG.
            #
            # Một chỉ số nằm trong mảng vẫn có thể là chỉ số của vùng khác:
            # `record.py::_unwrap` bỏ vùng rồi đánh số lại, và con trỏ của từ
            # từng giữ nguyên số cũ. Đo lúc tìm ra: 30 trên 1105 bản ghi
            # trong `data/` (3%) và 4231 từ (0,6%) trỏ vào một vùng không
            # chứa chúng -- phép kiểm cũ không thấy một cái nào, vì mọi chỉ
            # số đều hợp lệ.
            #
            # Xét theo TÂM hộp từ, cùng phép xét `regions_from_words` dùng để
            # gán vùng. Nới một điểm ảnh vì hộp vùng làm tròn về số nguyên.
            host = all_regions[index].get('bbox') or []
            if len(host) == 4:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                if not (host[0] - 1 <= cx <= host[2] + 1
                        and host[1] - 1 <= cy <= host[3] + 1):
                    fail('word.layout_region_index trỏ vào vùng không chứa nó',
                         f'{stem}: từ {word.get("text")!r} {box} -> vùng #{index} '
                         f'{all_regions[index].get("layout_class")} {host}')

    for region in regions:
        box = region.get('bbox') or []
        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            fail('vùng bố cục diện tích 0', f'{stem}: {box}')
            continue
        if (box[0] < -1 or box[1] < -1 or box[2] > width + 1
                or box[3] > height + 1):
            fail('vùng bố cục ra ngoài trang', f'{stem}: {box}')

    for pair in (record.get('kie') or {}).get('pairs') or []:
        if not str(pair.get('description', '')).strip():
            fail('cặp KIE không có mô tả', f'{stem}: {pair.get("field")}')
        # GIÁ TRỊ thì luôn phải có hộp -- nó là chữ in trên giấy. KHOÁ thì
        # không: một tiêu đề tài liệu hay một con dấu không có nhãn nào in
        # kèm, và `kie_full.py` ghi rõ điều đó bằng `source: implied`. Bắt
        # chúng phải có `key_bbox` là bắt một cái hộp cho thứ không tồn tại.
        if not pair.get('value_bbox'):
            fail('cặp KIE thiếu hộp giá trị', f'{stem}: {pair.get("field")}')
        if not pair.get('key_bbox') and pair.get('source') != 'implied':
            fail('cặp KIE thiếu hộp khoá', f'{stem}: {pair.get("field")}')

    # Một file không được tự nói hai câu khác nhau về cùng một trường.
    # `entity_annotations` mang mô tả riêng của nó, do `pipeline/kie.py` ghi
    # lúc vẽ; `derive.py` đổi giọng cho `kie.pairs` và phải đổi cả ở đây.
    # Lần đầu nó không làm thế, và không gì báo: hai nhãn lệch nhau nằm im
    # trong hai mươi nghìn file.
    voice = {e.get('entity_index'): str(e.get('description') or '')
             for e in entities}
    for pair in (record.get('kie') or {}).get('pairs') or []:
        index = pair.get('value_entity_index')
        said = voice.get(index)
        if said and said != str(pair.get('description', '')):
            fail('mô tả trong pairs khác mô tả trong entity_annotations',
                 f'{stem}: {pair.get("field")}: {said[:40]!r} != '
                 f'{str(pair.get("description", ""))[:40]!r}')

    # HAI TRƯỜNG KHÁC NHAU TRÊN MỘT TRANG KHÔNG ĐƯỢC CÙNG MÔ TẢ.
    #
    # Một mô tả dùng chung mang zero thông tin để phân biệt hai cái hộp, và
    # người huấn luyện đọc chúng thì không biết hộp nào là hộp nào -- tệ hơn
    # là không có mô tả, vì nó trông như có. Đo được trước khi vá: 84% số
    # trang có ít nhất hai trường cùng mô tả, nặng nhất là chức danh ký (mọi
    # vai dùng chung một câu).
    #
    # Ô BẢNG không tính: mọi ô của một cột PHẢI cùng giọng, và `column` là thứ
    # phân biệt chúng.
    said: dict[str, list[str]] = {}
    for pair in (record.get('kie') or {}).get('pairs') or []:
        if pair.get('source') == 'table':
            continue
        if int(pair.get('page_number', 1) or 1) != number:
            continue
        text = str(pair.get('description') or '')
        name = str(pair.get('field') or pair.get('column') or '')
        if text and name:
            # Bỏ hậu tố số trước khi gom: `nguoi_duoc_bao_hiem` và
            # `nguoi_duoc_bao_hiem_2` là CÙNG MỘT TRƯỜNG in hai lần trên một
            # tờ, không phải hai trường. `rulebase/kie_glossary.py` đã ghi
            # đúng chuyện ấy ("cùng một chữ in hai lần trên một tờ -- hai tài
            # khoản ngân hàng. Nghĩa y hệt, chỉ khác lần in"), và chúng PHẢI
            # dùng chung một mô tả. Không bỏ thì luật này báo sai ở mọi tờ có
            # một trường in lặp -- đo được: một lỗi trên 46 trang, và là lỗi
            # của chính luật.
            said.setdefault(text, []).append(re.sub(r'_\d+$', '', name))
    for text, names in said.items():
        if len(set(names)) > 1:
            fail('hai trường khác nhau cùng một mô tả',
                 f'{stem}: {sorted(set(names))} -> {text[:48]!r}')

    # Mô tả trong `kie.schema` phải là mô tả của cặp, không phải câu gốc đọc
    # lại từ `design.COLUMNS` -- đó đúng là lỗi đã xảy ra: `line_items.qty` y
    # hệt nhau trên cả hai mươi nghìn trang trong khi `kie.pairs` của cùng
    # file đã có bốn cách nói.
    for which in ('schema', 'page_schema'):
        items = (((record.get('kie') or {}).get(which) or {})
                 .get('properties', {}).get('line_items') or {})
        for column, spec in (items.get('items') or {}).get('properties', {}).items():
            said = str(spec.get('description') or '')
            mine = {str(p.get('description', ''))
                    for p in (record.get('kie') or {}).get('pairs') or []
                    if p.get('column') == column}
            if mine and said not in mine:
                fail(f'mô tả cột trong {which} khác mô tả trong pairs',
                     f'{stem}: line_items.{column}: {said[:40]!r}')

    # Số học tiền chỉ kiểm trên trang một: bản ghi mô tả CẢ tài liệu, nên
    # kiểm lại ở từng trang là đếm cùng một lỗi nhiều lần.
    if number != 1:
        return
    rows = (record.get('extracted') or {}).get('menu') or []
    total = 0
    counted = 0
    for item in rows:
        qty = _int(item.get('qty', ''))
        price = _int(item.get('unit_price', ''))
        amount = _int(item.get('amount', ''))
        if amount is None:
            continue
        total += amount
        counted += 1
        if qty is None or price is None:
            continue
        if abs(qty * price - amount) > MONEY_SLACK:
            fail('thành tiền != số lượng x đơn giá',
                 f'{stem}: {qty} x {price} = {qty * price} nhưng in {amount}')
    if counted and counted == len(rows):
        printed = (record.get('extracted') or {}).get('total') or {}
        for label, value in printed.items():
            if 'tiền hàng' not in label.lower() and 'thành tiền' not in label.lower():
                continue
            got = _int(value)
            if got is not None and abs(got - total) > MONEY_SLACK:
                fail('cộng tiền hàng != tổng cột thành tiền',
                     f'{stem}: cột cộng ra {total}, in {got}')


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='thư mục đã sinh')
    parser.add_argument('--sample', type=int, default=0,
                        help='chỉ kiểm N trang rút ngẫu nhiên; 0 = kiểm hết')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--show', type=int, default=4, help='ví dụ mỗi loại lỗi')
    args = parser.parse_args()

    root = args.run.resolve()
    manifest = root / 'manifest.jsonl'
    if not manifest.is_file():
        print(f'không có {manifest} — đây có phải thư mục đã sinh xong không?')
        return 1

    rows = [json.loads(line)
            for line in manifest.read_text(encoding='utf-8').splitlines()
            if line.strip()]
    if args.sample and args.sample < len(rows):
        rows = random.Random(args.seed).sample(rows, args.sample)

    problems = Counter()
    examples = {}
    designs = Counter()
    contents = Counter()
    thin = 0

    for row in rows:
        stem = row['stem']
        # Đường dẫn lấy từ CHÍNH manifest, không ghép lại từ `stem`: manifest
        # là thứ duy nhất biết tài liệu ấy nằm trong ngăn nào, và một bộ kiểm
        # tự ghép đường dẫn là một bộ kiểm phải sửa mỗi lần cách chia thư mục
        # đổi -- tức là một bộ kiểm sẽ có lúc kiểm nhầm chỗ mà vẫn báo sạch.
        # `record` chứ không `json`: từ khi `json/` thành định dạng gộp theo
        # TÀI LIỆU, nó không còn là một file cho mỗi TỜ nữa, nên hỏi từng tờ
        # xem có file json của nó không là hỏi sai câu -- và bộ kiểm đã báo
        # đúng 21/21 trang thiếu một thứ không trang nào phải có.
        for kind in ('images', 'html', 'record',
                     'layout_boxes_image', 'word_boxes_image'):
            where = row.get(kind) or (row.get('json') if kind == 'record' else None)
            if where and (root / where).is_file():
                continue
            problems[f'thiếu {kind}/'] += 1
            examples.setdefault(f'thiếu {kind}/', []).append(stem)
        # `record` là bản ghi đầy đủ của MỘT TỜ. Bộ cũ gọi nó là `json`;
        # nhận cả hai để một bộ 44 GB không phải sinh lại vì một cái tên.
        record_path = root / (row.get('record') or row.get('json')
                              or f'records/{stem}.json')
        if not record_path.is_file():
            continue
        record = json.loads(record_path.read_text(encoding='utf-8'))
        check_record(record, root / (row.get('images') or f'images/{stem}.jpg'),
                     row, problems, examples)

        # Hộp từ và hộp vùng của tờ này dựng từ CHÍNH bản ghi
        # (`overlay.slice_for`) -- không còn hai file chép sẵn bên cạnh để mà
        # lệch nhau. Vẫn kiểm rằng dựng ra được và đếm khớp `manifest`, vì đó
        # là con số `manifest` hứa với người đọc.
        regions, words = O.slice_for(record, int(row['page_number']))
        for name, got, want in (('word_box_count', len(words),
                                 row.get('word_box_count')),
                                ('layout_box_count', len(regions),
                                 row.get('layout_box_count'))):
            if want is not None and got != int(want):
                problems[f'{name} không khớp bản ghi'] += 1
                examples.setdefault(f'{name} không khớp bản ghi', []).append(
                    f'{stem}: {got} != {want}')

        if row['pages_in_document'] > 1:
            fill = row.get('fill')
            if fill is not None and fill < MIN_FILL:
                thin += 1
                problems['trang bị cắt lấp dưới 80%'] += 1
                examples.setdefault('trang bị cắt lấp dưới 80%', []).append(
                    f'{stem}: {fill:.0%}')

        if int(row['page_number']) == 1:
            designs[row.get('design_signature', '')] += 1
            contents[row.get('content_signature', '')] += 1

    repeat_design = [key for key, count in designs.items() if count > 1]
    repeat_content = [key for key, count in contents.items() if count > 1]

    print(f'[check] {len(rows)} trang trong {root}')
    print(f'[check] {sum(designs.values())} chứng từ; dáng: {len(designs)} khác nhau, '
          f'{len(repeat_design)} bị lặp')
    print(f'[check] nội dung: {len(contents)} khác nhau, '
          f'{len(repeat_content)} bị lặp')
    print(f'[check] trang bị cắt lấp dưới 80%: {thin}')
    if not problems:
        print('[check] SẠCH — không lỗi nào')
        return 0
    print(f'[check] {sum(problems.values())} lỗi, {len(problems)} loại:')
    for kind, count in problems.most_common():
        print(f'  {count:>6}  {kind}')
        for line in (examples.get(kind) or [])[:args.show]:
            print(f'          {line}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
