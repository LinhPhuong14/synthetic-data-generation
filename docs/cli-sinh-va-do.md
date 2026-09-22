# CLI: sinh, chỉnh, đo

Ba việc, ba lệnh. Mọi lệnh dưới đây đã chạy thật trước khi viết vào đây.

## 1 · Sinh

```bash
.venv/bin/python synthgen/run.py -n 100 -o data/thu --workers 4
```

Một lượt đi trọn bốn chặng: **vẽ → derive → export → báo cáo**. Ra mười thư
mục dưới `-o`, trong đó `records/` là nhãn đầy đủ, `sample/` là bộ xem nhanh,
`visualize_kie/` là ảnh vẽ đè hộp KIE để mắt kiểm.

| cờ | mặc định | dùng khi |
| --- | --- | --- |
| `-n` | 10000 | số **chứng từ**, không phải số ảnh — một chứng từ nhiều tờ ra nhiều ảnh |
| `-o` | `data/09-09-26-synthetics` | **luôn đặt tay**. Bỏ trống là ghi đè bộ cũ |
| `--workers` | CPU−2 | mỗi tiến trình mở một trình duyệt riêng |
| `--pages` | `1-4` | `3` \| `2-10` \| `2-5:75,7-10:25`. Chỉ là **ý định**: `paginate.py` đo trong trình duyệt rồi mới chốt |
| `--multipage-only` | tắt | **kết quả**, khác `--pages`: bỏ hẳn chứng từ đo xong còn một tờ |
| `--handwriting` | `both` | `font` \| `model` \| `off`. `model` cần WriteViT |
| `--hand-share` | 0 (bốc, sàn 0.3) | ép tỉ lệ tài liệu điền tay |
| `--augment` | `off` | `fast` \| `all` — làm cũ giấy ngay lúc vẽ |
| `--dry-run` | tắt | **in phân bố mà không mở trình duyệt**. Xem lượt sẽ ra những loại giấy nào trước khi bỏ ra vài giờ |
| `--raw` | tắt | chỉ vẽ, bỏ derive. Nhanh hơn, nhưng không có json gộp theo tài liệu |

`--dry-run` vẫn **ghi `kie_descriptions.json`** vào `-o`, nên đừng chạy nó
trỏ vào bộ đang dùng.

Chạy lại đúng lệnh ấy là **chạy tiếp**, không phải làm lại: mỗi shard để lại
một tệp `DONE` và shard xong được bỏ qua.

Có sẵn lối tắt: `make synth SYNTH=data/thu SYNTH_N=100 PAGES=1-4`.

## 2 · Chỉnh — nút vặn nằm ở đâu

Hai tầng, và đây là chỗ hay mò nhầm.

**Tầng YAML — đổi hình dạng bộ dữ liệu, không phải sửa code.**

| muốn đổi | sửa ở |
| --- | --- |
| tỉ lệ khối chảy (**bảng 20%**) | `rulebase/synthgen/_blocks.yaml:88` → `flow_weight.table` |
| khối nào gắn được vào phôi nào | cùng file, `chance` và bảng cho phép theo phôi |
| **nhãn vùng** của một khối (`Text`/`Form`/…) | cùng file, `region:` |
| dấu, mã vạch đứng đâu trên tờ | cùng file, `mark_place` |
| trường, cột, số dòng của **một loại giấy** | `rulebase/synthgen/<tên phôi>.yaml` |

`flow_weight` là trọng số **tương đối**, không phải phần trăm: `table: 0.3`
giữa `sections 1.2 / questions 1.1 / clauses 0.9` ra 20% số tài liệu có bảng.
Và nó có trần cứng ở tầng dưới — một khối chỉ 8% số phôi cho phép thì không
trọng số nào nâng lên quá 8%.

**Tầng `synthgen/design.py` — dáng tờ giấy.** Đều là tuple bốc đều, nên **tần
suất chỉnh bằng số lần lặp**, không bằng con số xác suất:

| dòng | tuple | nghĩa |
| ---: | --- | --- |
| 60 | `PAPERS` | khổ giấy. `[Paper('a4',…)] * 9` + 1 ngang = 90/10 |
| 181 | `TABLE_FRAMES` | kiểu kẻ khung bảng |
| 209 | `PAGE_COLUMNS` | 1/2/3 cột trang |
| 220 | `COL_GROUPS` | **nhóm cột** — tầng tiêu đề thứ 2 |
| 251 | `COL_SUPERS` | **nhóm của nhóm** — tầng thứ 3 |
| 266 | `ROW_GROUPS` | `khong` / `phan_muc` / `cot_gom` |
| 1179 | `BLOCKS` | kho khối; thứ tự do `_middle_order()` xáo có ràng buộc |
| 1430 | `tiers = 2 if roll < 0.82 else 1` | xác suất số tầng tiêu đề |

## 3 · Đo

**Dáng — nhanh, không mở trình duyệt.** Chạy TRƯỚC và SAU mỗi lần vặn nút:

```bash
make synth-balance BALANCE_N=400 PAGES=1-4
```

In ra khổ giấy, số trình tự khối khác nhau, nhãn vùng khối chữ ký, và với
riêng tài liệu có bảng: tỉ lệ ≥5 cột, số tầng tiêu đề, kiểu nhóm dòng. Kèm
bảng nhãn vùng cả bộ **và** trên **tờ giữa** — bộ cân theo phép đo thứ nhất
vẫn trượt phép đo thứ hai, và đã trượt.

**Đúng/sai — trên bộ đã sinh, có mã thoát:**

```bash
.venv/bin/python synthgen/check.py data/thu --sample 300
```

Bảy phép kiểm: đủ file, kích thước khớp, hộp trong trang, hộp có chữ, chỉ số
trỏ đúng, **số khớp nhau** (thành tiền = số lượng × đơn giá), luật lấp 80%.
Ra 0 khi sạch, 1 khi có lỗi — cắm được vào CI.

**Chạy lại riêng một chặng** khi đã có ảnh, khỏi vẽ lại:

```bash
.venv/bin/python synthgen/derive.py data/thu      # markdown, visualize_kie, schema
.venv/bin/python synthgen/export.py data/thu      # gộp json theo tài liệu
```

## 4 · Vòng làm việc

```
make synth-balance BALANCE_N=400 PAGES=1-4     # đo trước
  ↓ vặn nút ở _blocks.yaml hoặc design.py
make synth-balance BALANCE_N=400 PAGES=1-4     # đo lại, so hai bảng
  ↓ đạt thì mới sinh thật
.venv/bin/python synthgen/run.py -n 100 -o data/thu --workers 4
.venv/bin/python synthgen/check.py data/thu
```

Đo trước rồi mới vặn. Vặn trước đo sau là cách đổi một cái lệch này lấy một
cái lệch khác mà vẫn thấy mình đang sửa — kho này đã làm đúng thế hai lần:
`Table` 77% số tờ, rồi `List-Group` 82%.
