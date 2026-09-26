# Schema KIE v3 — `field_type` + `provenance`, một JSON một tài liệu

> Đo trên `data/tmp_shape_check` (15 tài liệu, sinh mới bằng
> `synthgen/run.py --raw`, ngày 24-09-2026) và `data/review100d` +
> `data/pilot16` (bộ đã có sẵn, dùng để soi lỗi cấp trang cũ). Bản **thiết kế
> + code**, không như v2 (thiết kế trước, code sau) — v3 là phần thêm nhỏ
> trên v2, không phải viết lại.

---

## 1. v3 kế thừa gì từ v2, thêm gì

[`docs/kie-schema-v2.md`](kie-schema-v2.md) (18-09-2026) đã giải quyết bốn
việc khó nhất: bảng thành một mảng có tiêu đề cột, chữ ký ghép chức danh với
tên, chữ in sẵn tách khỏi trường, và thứ lặp lại thành mảng chứ không phải
`_2`/`_3`. `synthgen/export.py` đã ship đúng thiết kế ấy. v3 **không sửa lại
bốn việc đó** — nó thêm hai thứ v2 chưa có:

1. **`field_type`** — ô tích, ma trận, dãy số, chữ ký/con dấu, không chỉ
   "chuỗi". Không có ở đâu trong kho trước phiên này.
2. **`provenance`** — commit, seed, model, augment của lượt sinh ra tài
   liệu này.

Và đổi một quyết định của v2: v2 chia theo **trang** (`page_1`, mỗi trang
một khoá) vì lý do đúng (ảnh vào VLM là một trang một ảnh). v3 chia theo
**tài liệu**, `pages[]` chỉ còn là bảng kích thước — quyết định của người
dùng kho lúc thiết kế phiên này, đổi lại lấy đúng cách `synthgen/export.py`
đã gộp bảng/chữ ký/mực đúng đắn (xem §2 dưới, mục "sao không viết lại"), và
`fields`/`words`/`layout`/`tables` mỗi cái tự mang `page` của mình nên vẫn
lọc được về một trang khi cần.

---

## 2. Lỗi đo được, sửa trong phiên này

### 2.1 · `records/<tài liệu>.json` mô tả CẢ TÀI LIỆU, không phải trang tên nó chỉ tới

Đo lại hôm nay, trực tiếp trên hai bộ:

| | `review100d/records/ban_cam_ket_00032.json` | `_p2.json` |
| --- | ---: | ---: |
| kích thước file | 1 316 886 byte | 1 316 886 byte |
| `page_number` trong `word_annotations` | [1, 2, 3] | [1, 2, 3] |

| | `pilot16/records/llm_insurance_health_certificate_0017.json` | `_p2.json` |
| --- | ---: | ---: |
| kích thước file | 671 658 byte | 671 658 byte |

Hai file **giống hệt nhau về byte**, ở CẢ HAI nhánh (luật lẫn LLM) — cùng
một lỗi vì cùng gọi `pipeline/record.py::build()`. Đã có ghi nhận việc này
trước phiên này (dưới tên `json/` cũ), nhưng ghi nhận ấy sai một điểm: từng
nói nhánh LLM "đã đúng hình" — đo lại thì KHÔNG, `pilot16` mắc lỗi giống hệt.
Xem bộ nhớ `record-json-la-cap-tai-lieu` (đã sửa).

**Sửa ở đây**: `synthgen/export_v3.py::document_v3()` lọc MỌI mảng theo
`page_number` khi gộp — hệt cách `synthgen/export.py::document()` đã làm
đúng từ v2. Đây không phải một vá riêng — nó là hệ quả tự nhiên của việc
xây trên nền `export.py` thay vì đọc lại `records/` thô.

### 2.2 · Ô tích trong `sheets/form.py::_checklist()` ra ĐÚNG 0 cặp KIE

Đo bằng cách dựng lại chính hàm lắp bản ghi (`pipeline/record.py`) trên
hai dòng checklist giả lập: dòng chữ mang `kind="note"` — cùng kind
`_notes_block` dùng cho một đoạn văn thường — nên `is_caption()` (đuôi
`.label`/`.title`) không nhận nó làm khoá. Cả ô tích lẫn dòng chữ rơi xuống
nhánh khoá-ảo (`key_source: "implied"`) ĐỘC LẬP với nhau:

```
entity_index=0 kind='survey.tick'  field_name='survey_tick'    text='☑'
entity_index=1 kind='note'         field_name='note'           text='Da hoan thanh ho so'
entity_index=2 kind='survey.tick'  field_name='survey_tick_2'  text='☐'
entity_index=3 kind='note'         field_name='note_2'         text='Da nop le phi'

pipeline.kie.pair_entities() -> 0 cặp
```

Trạng thái tích và dòng chữ mô tả nó — thứ DUY NHẤT một checklist muốn nói
— không nối được với nhau.

**Sửa**: đổi kind của dòng chữ từ `note` (dùng chung) sang `survey.checklist`
(riêng của khối này — cố ý KHÔNG mang đuôi `.label`/`.title`, xem comment tại
chỗ sửa cho lý do), thêm cặp `("survey.checklist", "survey.tick")` vào
`PAIRED` (`synthgen/kie_full.py`). Đo lại sau khi sửa: 2 cặp, tên trường lấy
từ chính dòng chữ (`da_hoan_thanh_ho_so`, `da_nop_le_phi`), value đúng ký tự
tích (`☑`/`☐`).

### 2.3 · Tấm `visualize_kie/` gọi nhầm tên field_type cho ô nằm TRONG một nhóm

Đo bằng ảnh thật (`data/tmp_shape_check`, tài liệu `gcn_tai_chinh_ke_toan_00006`,
câu hỏi ma trận "Đánh giá mức độ đáp ứng..."): lần đầu tra field_type theo
`value_entity_index` của chính ô tích, mọi ô trong ma trận 4×4 đều ra nhãn
`[boolean_choice]` — đúng cho MỘT ô tích đứng riêng (`_checklist`'s dòng),
sai cho một ô NẰM TRONG ma trận, vì field_type thật của cả nhóm
(`categorical_matrix`) chỉ nằm trên thực thể CÂU HỎI, không trên từng ô.

**Sửa**: `synthgen/overlay.py::kie()` tra theo `pair["group"]` (thực thể câu
hỏi) thay vì `pair["value_entity_index"]` khi `pair["source"] == "survey"`.

---

## 3. Schema v3

```jsonc
{
  "doc_id": "gcn_tai_chinh_ke_toan_00006",
  "schema_version": 3,
  "doc_type": "gcn_tai_chinh_ke_toan",
  "registry_version": "-7872907190907098866",  // manifest's design_signature; null khi vắng (nhánh LLM hôm nay)
  "provenance": {
    "generator": "synthgen@<commit>",  // commit của LẦN XUẤT, xem §5 cho giới hạn khi vá bộ cũ
    "seed": 20260910,                  // report.json's run.seed -- CỦA CẢ LƯỢT, không phải riêng tài liệu này
    "llm": null,                       // compose_report.json's "model", null khi file ấy không tồn tại
    "augment": "off"                   // report.json's run.augment, nguyên văn
  },
  "pages": [{"page": 1, "size": [827, 1169]}],
  "fields": [
    {"key": "ho_va_ten_benh_nhan", "field_type": "text", "surface_key": "Họ và tên bệnh nhân:",
     "value": "Đinh Công Khanh", "value_norm": "Đinh Công Khanh", "state": "printed", "page": 1,
     "key_bbox": [...], "key_bbox_px": [...], "value_bbox": [...], "value_bbox_px": [...]},
    {"key": "so_can_cuoc_cong_dan...", "field_type": "digit_sequence", "page": 1,
     "value": "752742838374", "value_norm": "752742838374",
     "value_bbox": [...], "digit_bboxes": [[...], ...]},
    {"key": "quy_vi_da_tung_nop_ho_so...", "field_type": "boolean_choice", "page": 1,
     "value": true, "options": [{"label": "Có", "checked": false, ...}, {"label": "Không", "checked": true, ...}]},
    {"key": "muc_do_hai_long_chung", "field_type": "multi_choice", "page": 1,
     "value": ["4"], "options": [...]},
    {"key": "bac_si_dieu_tri", "field_type": "presence", "page": 1,
     "value": {"signed": true, "stamped": false}, "bbox": [...]}
  ],
  "tables": [
    {"table_id": "survey_4", "field_type": "data_table", "page": 1,
     "columns": ["Họ và tên", "Quan hệ", "Năm sinh", "Số giấy tờ"],
     "rows": [{"key": "1", "row_bbox": [...], "cell_bboxes": [...], "value": ["Lý Gia Bảo", "Em", "1971", "49456952"]}]},
    {"table_id": "survey_8", "field_type": "categorical_matrix", "page": 1,
     "columns": ["Tốt", "Khá", "Trung bình", "Kém"],
     "rows": [{"key": "Thái độ tiếp dân", "row_bbox": [...], "cell_bboxes": [...], "checked": [true, false, false, false]}]}
  ],
  "words": [{"page": 1, "text": "Đinh", "bbox": [...], "field": "ho_va_ten_benh_nhan"}],
  "layout": [{"page": 1, "layout_class": "Table", "bbox": [...]}]
}
```

Đo trên `data/tmp_shape_check` (15 tài liệu, 391 trường):

| `field_type` | số trường |
| --- | ---: |
| `text` | 350 |
| `presence` | 30 |
| `multi_choice` | 5 |
| `boolean_choice` | 3 |
| `digit_sequence` | 3 |

| `field_type` (bảng) | số bảng |
| --- | ---: |
| `data_table` | 2 |
| `categorical_matrix` | 1 |

---

## 4. `field_type`: sáu giá trị cấp thực thể, một giá trị TỔNG HỢP

`presence` KHÔNG nằm trong `pipeline.record.ENTITY_FIELD_TYPES` — nó không
phải một sự thật về MỘT thực thể, nó GỘP một khối chữ ký (chức danh + tên,
`synthgen/export.py::_signatures()` đã ghép sẵn) với việc có mặt của bất kỳ
thực thể `seal.*` nào trên trang. Tổng hợp một lần, ở `export_v3.py`, không
bao giờ thành `entity["field_type"]`.

Sáu giá trị còn lại đọc theo thứ tự (giống hệt `ink_for`):

1. **`data-shape`** trên chính span câu hỏi (`synthgen/markup.py::_span`'s
   `shape=` mới) — `item["shape"]` của `_shape_rows`, tag DUY NHẤT thêm vào
   trong phiên này, vì đây là chỗ DUY NHẤT giá trị ấy bị bỏ đi trước khi tới
   DOM: `yesno` và `options` vẽ ra đúng một khuôn `kind`
   (`survey.tick`+`survey.option`) và chỉ khác ở việc được chọn MỘT hay
   NHIỀU.
2. **`kind`** — đủ cho phần còn lại KHÔNG CẦN tag mới: `survey.char` (một ô
   ký tự), `survey.tick` (một ô tích ĐỨNG RIÊNG, không trong nhóm câu hỏi
   nào) đã là những `kind` không kind nào khác dùng.
3. **mặc định `text`** — không mất gì, hộp và giá trị vẫn còn nguyên, chỉ
   là không phân loại đặc biệt.

Bảng ánh xạ `shape` → `field_type`:

| `shape` | `field_type` |
| --- | --- |
| `yesno` | `boolean_choice` |
| `options`, `scale`, `attachment` | `multi_choice` |
| `boxchar`, `date_boxes`, `rank` | `digit_sequence` |
| `grid` | `categorical_matrix` |
| `table_form` | `data_table` |
| (không có shape khớp) | `text` |

Với bảng THẬT (`<table>`, không phải `grid`/`table_form`): field_type đọc
từ `record["kie"]["tables"]` (đã tính sẵn lúc `kie_full.complete()` chạy,
không đo lại) — `role="data"` → `data_table`, `role="layout"` → LOẠI khỏi
`tables[]` (không phải bảng thật, chỉ là mảnh trang trí).

---

## 5. Lấy `provenance`/`registry_version` ở đâu ra — đo trên file thật

| khoá | nguồn | đo được |
| --- | --- | --- |
| `provenance.seed` | `report.json`'s `run.seed` | `20260910` (`review100d`) |
| `provenance.augment` | `report.json`'s `run.augment`, nguyên văn | `"off"` (`review100d`) |
| `provenance.llm` | `compose_report.json`'s `model`, CHỈ khi file ấy tồn tại | `"Qwen/Qwen3.8-27B-FP8"` (`pilot16`) |
| `registry_version` | manifest row's `design_signature` | có ở `review100d`, **vắng ở `pilot16`** — `null` khi vắng |

**Khoảng trống thật, không phải lỗi hàm đọc**: nhánh LLM/agent hôm nay không
ghi `report.json` ở đâu cả — `seed`/`augment` của nó luôn `null` cho tới khi
`agent/compose_page.py` tự ghi ra. Không suy đoán để lấp chỗ trống này.

**Giới hạn của `provenance.generator`**: với một bộ sinh MỚI, commit ghi ra
là commit ĐÃ VẼ RA bộ ấy — đúng. Với một bộ **vá** bằng `--migrate`
(bộ CŨ, sinh ra trước khi `field_type` tồn tại), commit ghi ra là commit của
LẦN VÁ, không phải commit đã sinh ra dữ liệu gốc — commit gốc chưa từng được
ghi lại ở đâu và không dựng lại được. `export_v3.py --migrate` in dòng cảnh
báo này ra màn hình mỗi lần chạy.

---

## 6. Cắt sang v3: mốc và cách làm

**Không xoá `records/`/`json/` nào** — v3 ghi vào thư mục MỚI,
`documents_v3/`, cạnh `records/`/`json/`/`kie_schemas/`/`sample/`/`markdown/`/
`visualize_kie/` đã có.

**Bộ đã sinh** (`data/review100d`, `data/pilot16`, mọi bộ cũ khác): vá một
lần bằng

```bash
python synthgen/export_v3.py data/review100d --migrate
python synthgen/export_v3.py data/pilot16 --migrate
```

**Bộ sinh MỚI**: mốc cắt là lần `synthgen/derive.py` chạy tiếp theo trên một
bộ vừa sinh xong — `derive.py` đã có lời gọi `export_v3.document_v3()` cạnh
lời gọi `export.run()` đã có từ trước, sau `field_type`/`data-shape` đã
được kiểm bằng `make dataset`/`make check-boxes` (xem `docs/ban-do-repo.md`).
Không cần một lệnh riêng: `make synth`/`synthgen/run.py` bình thường của một
lượt mới đã ra `documents_v3/` cùng lúc với `json/`.

---

## 7. Đã đo, chưa làm — khoảng trống thật, không phải thiếu sót

- **`state: blank`** (ô có nhãn in nhưng để trống, khác `absent` — ô không
  có nhãn nào cả) — vẫn CHƯA hiện thực, đúng như `docs/kie-schema-v2.md`'s
  bảng nghiệm thu đã ghi ("chưa — cần bộ sinh phát span rỗng"). v3 dùng trục
  `state: printed | handwritten | absent` — MỘT trục khác, đọc từ
  `handwriting.kinds`/`handwriting.inked` (dữ liệu đã có sẵn hôm nay) — chứ
  không phải bản vá cho trục `blank` còn thiếu.
- **Ô chấm công của `sheets/form.py::_roster_table()`** — cột ngày trong
  bảng chấm công vẽ bằng chữ "x" trần, không `span()`/`data-kind` nào —
  không có mặt trong `entity_annotations` để mà gán field_type. Mực có
  hộp mà không nhãn (luật 3, `AGENTS.md`) — khoảng trống có trước phiên
  này, cần thêm entity mới chứ không phải phân loại lại entity đã có, nên
  để lại cho một phiên riêng.
- **`_declared_table`** (bảng model tự khai `items[N].path`, nhánh LLM) —
  code có, chưa đo trên dữ liệu thật vì `data/tmp_shape_check` (nhánh
  luật/procedural, `synthgen/run.py` không qua agent) không có ví dụ nào.
  Kiểm lại khi có một bộ agent mới.

---

## Liên quan

- [`kie-schema-v2.md`](kie-schema-v2.md) — schema v3 kế thừa, bảng lấy-ở-đâu
- [`ban-do-repo.md`](ban-do-repo.md) — bốn tầng nhãn của một trang
