# Schema KIE v2 — thiết kế lại từ kết quả `pilot13`

> Đo trên **`data/pilot13`** (35 bản ghi, 35 trang xuất, 5 286 thực thể, 5 290
> cặp KIE), ngày 18-09-2026. Tham chiếu hình dạng:
> `format3trang.json` — bản xuất 3 trang người dùng đưa.
>
> Bản **thiết kế**, không có code.

---

## 1. `pilot13` đo được gì

### Ba việc đã chạy đúng

| | `pilot10` | **`pilot13`** |
| --- | ---: | ---: |
| độ phủ thực thể | 0,913 | **0,926** (0,783–1,000) |
| thực thể mang >1 trường (đếm hai lần) | 57/77 | **0 / 5 286** |
| tài liệu nhiều trang | 8/24 hai trang | **14×2tr · 12×3tr · 5×5tr** |

Phép khử trùng đã vào và sạch tuyệt đối. Đây là chỗ hỏng nặng nhất của
`pilot10` và nó biến mất hoàn toàn.

### Năm chỗ hỏng còn lại, tất cả đều đo được

**1 · 93 cặp KIE bị NUỐT trong lúc xuất.**

> **Đính chính.** Bản đầu của mục này ghi 461 và nêu `clause_head` 22→1 làm ví
> dụ. Sai: phép đếm ấy chỉ đếm khoá cấp trang, trong khi `export.py` đã gói các
> lần in lặp vào `type: "list"` với 22 phần tử trong `items`. Đếm lại theo Ô
> GIÁ TRỊ (kể cả phần tử của `list` và ô của bảng): **1 994 cặp → 1 901 ô, mất
> 93**. Nguyên nhân cũng khác hẳn, và nằm ở chỗ dưới đây.

Mất tập trung ở một chỗ: **hai bảng trên cùng một trang bị gộp làm một**.
`_table()` khoá ô theo `(row, column)`, mà bảng thứ hai đánh số dòng lại từ
đầu — nên bảng sau đè bảng trước.

| tài liệu | cặp | ô ra `json` | mất |
| --- | ---: | ---: | ---: |
| insurance_partner_cert_application | 273 | 205 | **68** |
| bank_deposit_statement | 66 | 56 | 10 |
| monthly_fleet_activity_report | 367 | 357 | 10 |

`kie_full.table_pairs` biết bảng nào là bảng nào từ lúc đọc markup
(`cell["table"]`) — con số ấy chỉ chưa bao giờ ra khỏi hàm.

**2 · Bảng có hai bản, bản tốt thì phẳng, bản có cấu trúc thì rỗng.**

Cùng một bảng xuất hiện hai lần trong cùng một trang:

```
"items_0_stt": {"value": "1",  "bbox": [86, 304, 92, 313]},      ← declared: ĐÚNG
"items_0_name": {"value": "Khám bệnh ngoại trú", ...},
...  (84 khoá như vậy)
"line_items": {"type": "table", "rows": [ {}, {}, … 22 hàng RỖNG ]}  ← table: HỎNG
```

Đo cả bộ: **272/814 trường cấp trang (33,4%) là ô bảng phẳng** `items_N_*`;
**8/70 cột mang tên `cell`**. Trang nặng nhất có **197 trường**.

> **Đính chính.** Bản đầu còn ghi "26/144 hàng không có một ô nào". Sai: đó là
> các dòng `group` và `subtotal`, và chúng mang `label` thay cho `cells` — đúng
> theo thiết kế. Chỗ hỏng thật của bảng hình học trên trang ấy là **nhận được
> hai cột trên bảy cột có thật**.

**3 · Chữ in sẵn vẫn làm giá trị.** 21 cặp có `value` là
`"(Ký, ghi rõ họ tên)"` / `"(Ký, đóng dấu, ghi rõ họ tên)"`. `FURNITURE` chặn
theo `kind`, còn chuỗi thì mỗi tờ in một kiểu.

**4 · Tên trường nói sai nội dung.** `total_words` (nghĩa: số tiền bằng chữ)
mang giá trị `"II. ĐÁNH GIÁ TÌNH HÌNH THỰC HIỆN"` — một tiêu đề mục. Cùng trang
đó `so_tien_bang_chu` mới là số tiền bằng chữ thật.

**5 · Ba bản KIE không khớp nhau.** Cùng một tờ có ba hình dạng khác hẳn:

| nơi | hình dạng | bảng |
| --- | --- | --- |
| `records/*.json` → `kie.pairs` | danh sách cặp phẳng | có, đủ |
| `json/*.json` | trang → `fields` phẳng | hai bản, một hỏng |
| `kie_schemas/*.json` | nhóm lồng (`chu_ky`, `dieu_khoan`…) | **không có** |

Ba người đọc ba nơi sẽ ra ba con số khác nhau cho cùng câu hỏi.

---

## 2. Schema tham chiếu: lấy gì, bỏ gì

`format3trang.json` chia theo **trang**, mỗi trang là một map trường phẳng cộng
một mảng `line_items`.

### Bốn điều nó làm đúng, v2 giữ nguyên

1. **Chia theo TRANG, không theo tài liệu.** Đầu vào của VLM là **một ảnh một
   trang**. Nhãn phải cùng biên với ảnh, nếu không thì mọi câu hỏi phải kèm chú
   thích "nhưng phần này ở tờ khác".
2. **Một hình dạng duy nhất cho trường:** `{value, bbox, key_text, key_bbox}`.
   `key_bbox: []` khi không có nhãn in. Đồng nhất, dễ sinh, dễ chấm.
3. **Bảng là MỘT mảng hàng**, ô chỉ `{value, bbox}` — không lặp lại tên cột
   trong từng ô.
4. **`stt` chạy liên tục qua các trang** (1–23 · 24–56 · 57–83). Bảng trải trang
   đọc lên tự nhiên, không cần khoá nối.

### Sáu chỗ nó cũng hỏng, v2 phải chữa

| # | trong file tham chiếu | vì sao hỏng |
| ---: | --- | --- |
| 1 | không có `size`, không có đơn vị toạ độ | `bbox: [115, 72, 340, 85]` là pixel hay phần nghìn? Không ai biết, và hộp không kiểm được |
| 2 | `nguoi_cham_cong.value = "(Ký, ghi rõ họ tên)"` | chữ in sẵn làm giá trị — ba ô ký đều thế |
| 3 | `signer_name`, `signer_name_2` rời khỏi ba chức danh | 3 chức danh · 2 tên, không gì nối ai với ai |
| 4 | `period.value = "Thái Nguyên, ngày 21 tháng 08 năm 2024"` | tên trường là "kỳ", nội dung là nơi + ngày |
| 5 | `doc_subtitle.value = "Bộ phận: ...."` | nhãn để trống, bắt làm giá trị |
| 6 | `org_branch_2`, `signer_name_2` · hàng thiếu `note` | danh tính theo vị trí, và ô trống thì biến mất |

---

## 3. Schema v2

```jsonc
{
  "doc_type": "bang_cham_cong",
  "doc_id": "llm_bang_cham_cong_0007",
  "page_count": 3,
  "bbox_unit": "per_mille_of_size",        // hoặc "pixel" — KHAI, không ngầm

  "page_1": {
    "size": [1816, 2568],

    // ---- trường DUY NHẤT trên trang -------------------------------------
    "fields": {
      "org_name": {
        "value": "CÔNG TY CỔ PHẦN ĐẦU TƯ HẠ TẦNG PHƯƠNG NAM",
        "state": "printed",
        "bbox": [115, 85, 628, 101],
        "key_text": "", "key_bbox": [],
        "path": "issuer.name", "role": "store.name"
      },
      "ngay_lap": {
        "value": "21/08/2024", "value_norm": "2024-08-21", "format": "dd/mm/yyyy",
        "state": "printed",
        "bbox": [544, 282, 875, 295],
        "key_text": "Ngày lập:", "key_bbox": [480, 282, 540, 295],
        "path": "meta.issued_at", "role": "meta"
      },
      "bo_phan": {
        "value": null, "state": "blank",
        "bbox": [204, 248, 420, 261],
        "key_text": "Bộ phận:", "key_bbox": [115, 248, 204, 261],
        "path": "meta.department"
      }
    },

    // ---- MỌI thứ LẶP LẠI đều là MẢNG, không phải trường đánh số ---------
    "lists": {
      "clauses": [
        {"index": 1,
         "head": {"value": "Điều 1. Phạm vi", "bbox": [...]},
         "body": {"value": "Bản cam kết này…",  "bbox": [...]}}
      ],
      "legal_basis": [{"index": 1, "value": "Căn cứ Luật Đất đai 2024", "bbox": [...]}],
      "toc":         [{"index": 1, "title": {...}, "page": {...}}]
    },

    // ---- bảng: MỘT bản, có tiêu đề cột ----------------------------------
    "tables": [{
      "table_id": "t1",
      "caption": {"value": "Danh mục thiết bị", "bbox": [...]},
      "continues_from_page": null,
      "columns": [
        {"key": "stt",  "header": "STT",       "header_bbox": [...],
         "path": "items[].stt",  "role": "menu.stt",  "type": "integer", "col_index": 0},
        {"key": "name", "header": "Tên thiết bị", "header_bbox": [...],
         "path": "items[].name", "role": "menu.name", "type": "string",  "col_index": 1},
        {"key": "qty",  "header": "Số lượng",  "header_bbox": [...],
         "path": "items[].qty",  "role": "menu.qty",  "type": "number",  "col_index": 2,
         "unit_from": "items[].unit"},
        {"key": "note", "header": "Ghi chú",   "header_bbox": [...],
         "path": "items[].note", "role": "menu.note", "type": "string",  "col_index": 3}
      ],
      "rows": [
        {"row_index": 1, "row_kind": "data", "cells": {
           "stt":  {"value": "1",  "value_norm": 1,  "state": "printed", "bbox": [145, 346, 155, 360]},
           "name": {"value": "Đồng hồ đo điện vạn năng", "state": "printed", "bbox": [191, 346, 409, 360]},
           "qty":  {"value": "25", "value_norm": 25, "state": "printed", "bbox": [709, 346, 731, 360]},
           "note": {"value": "Hàng mới 100%", "state": "printed", "bbox": [747, 346, 877, 360]}}},
        {"row_index": 4, "row_kind": "data", "cells": {
           "note": {"value": null, "state": "blank", "bbox": [747, 419, 877, 433]}}}
      ]
    }],

    // ---- khối chữ ký: chức danh ĐI VỚI tên ------------------------------
    "signatures": {
      "order_basis": "reading",
      "blocks": [
        {"index": 1,
         "title": {"value": "NGƯỜI CHẤM CÔNG", "bbox": [158, 783, 327, 797]},
         "name":  {"value": "Tạ Thị Lệ Thuỷ",  "bbox": [175, 868, 310, 882]},
         "signed": true,
         "block_bbox": [150, 780, 335, 890]},
        {"index": 2,
         "title": {"value": "PHỤ TRÁCH BỘ PHẬN", "bbox": [414, 783, 598, 797]},
         "name":  {"value": null, "state": "blank", "bbox": [430, 862, 590, 886]},
         "signed": false}
      ]
    },

    // ---- vùng có mực nhưng KHÔNG phải trường ------------------------------
    "marks": [
      {"kind": "seal",      "text": "BẢN SAO", "bbox": [783, 852, 834, 871]},
      {"kind": "sign_note", "text": "(Ký, ghi rõ họ tên)", "bbox": [179, 800, 305, 812]}
    ],

    // ---- những gì tờ này KHÔNG có ------------------------------------------
    "absent": ["meta.tax_code", "items[].unit_price"],

    // ---- quan hệ số học bộ sinh đã biết ------------------------------------
    "checks": [
      {"op": "count", "target": "tables[t1].rows", "declared": 23, "computed": 23, "ok": true}
    ]
  },

  "page_2": { "size": [...], "fields": {...},
              "tables": [{"table_id": "t1", "continues_from_page": 1,
                          "header_repeated": false, "columns": [...],
                          "rows": [{"row_index": 24, ...}]}] }
}
```

---

## 4. Bảy quyết định, mỗi cái gắn với một phép đo

| # | quyết định | chữa gì | đo được |
| ---: | --- | --- | --- |
| 1 | **Lặp thì thành MẢNG, không thành `tên_2`, `tên_3`** | 461 cặp bị nuốt | `clause_head` 22 → 1 |
| 2 | **Một bảng một bản**, xoá `items_N_*` phẳng | trang 197 trường | 272/814 trường (33,4%) là ô bảng |
| 3 | **Cột phải có `header` in trên giấy** | cột vô danh | 8/70 cột tên `cell`; `line_items` 26 hàng rỗng |
| 4 | **`state: printed / blank / absent`** | ô trống biến mất | tham chiếu: hàng thiếu `note` im lặng |
| 5 | **`marks[]` cho mực không phải trường** | chữ in sẵn làm giá trị | 21 cặp `"(Ký, ghi rõ họ tên)"` |
| 6 | **`signatures.blocks` nối chức danh với tên** | 3 chức danh, 2 tên rời | tham chiếu trang 3 |
| 7 | **`size` + `bbox_unit` khai rõ** | hộp không kiểm được | tham chiếu không có |

### Luật gốc: **lặp thì thành mảng**

Hôm nay kho có **ba** cách xử lý cùng một chuyện "thứ này xuất hiện nhiều lần",
và chúng đá nhau:

| cách | ví dụ | hậu quả |
| --- | --- | --- |
| hậu tố `_N` | `org_branch_2`, `signer_name_2` | danh tính theo vị trí |
| khoá phẳng `items_N_cột` | `items_3_qty` | 84 khoá cho một bảng |
| đè lên nhau | `clause_body` ×22 → 1 | **mất dữ liệu, im lặng** |

v2 chỉ có **một** cách: mảng, phần tử mang `index`. Điều khoản, căn cứ, mục lục,
câu hỏi khảo sát, hàng bảng, khối chữ ký — cùng một luật.

---

## 5. Lấy ở đâu ra — không đo lại gì

| khoá v2 | nguồn đã có hôm nay |
| --- | --- |
| `fields.*.value` / `bbox` | `kie.pairs[].value_text` / `value_bbox` |
| `key_text` / `key_bbox` | `kie.pairs[].key_text` / `key_bbox` |
| `path` | `kie.pairs[].path` (nhánh `declared`, 1 335 cặp ở `pilot13`) |
| `role` | `entity_annotations[].kind` |
| `columns[].header` | `kie.pairs[source=table].column_path` |
| `rows[].row_index` | `kie.pairs[source=table].row` |
| `lists.clauses[]` | gom `kie.pairs` có `field` trùng nhau, theo `reading_order` |
| `marks[]` | thực thể có `kind ∈ FURNITURE ∪ {seal.*, watermark}` |
| `state: blank` | span/`<td>` rỗng — `markup.py` biết lúc nó viết ra |
| `value_norm` | giá trị **trước khi** `content.py` định dạng |
| `size`, `bbox_unit` | `record.pages[].width/height`; `export.py` đã có `to_grid` |

Chỉ hai khoá cần thông tin bộ sinh hiện **vứt đi**: `state: blank` và
`value_norm`. Phần còn lại là **đổi hình dạng**, không phải đi tìm dữ liệu mới.

---

## 6. Xoá gì

1. **`items_N_*` phẳng** khỏi `fields` — 272 khoá ở `pilot13`.
2. **`line_items` kiểu cũ** (`type: "table"` với hàng rỗng) — thay bằng `tables[]`.
3. **Hậu tố `_2`, `_3`** cho trường lặp — thay bằng mảng.
4. **`kie_schemas/` dạng nhóm lồng** — hoặc bỏ, hoặc sinh lại từ v2 để ba bản
   không còn đá nhau. Một nguồn sự thật, hai bản dẫn xuất.

---

## 7. Nghiệm thu — chạy được trên bộ kế tiếp

| phép đo | v1 (`pilot13`) | ngưỡng v2 | **đã chạy** |
| --- | ---: | ---: | ---: |
| cặp KIE bị nuốt lúc xuất | 93 | **0** | 71 · **0** sau khi dựng lại nhãn |
| trường cấp trang, cao nhất | 197 | < 30 | **33** |
| trường là ô bảng phẳng | 272 (33,4%) | 0 | **0** |
| bảng nhận ra trên cả bộ | 10 | > 10 | **17** |
| cột mang tên `cell` | 8/70 | 0 | **1/111** |
| `value` là chữ in sẵn | 7 | 0 | **0** |
| trang có `size` + `bbox_unit` | có | giữ | **giữ** |
| ô trống có `state: blank` | 0 | 100% | *chưa — cần bộ sinh phát span rỗng* |
| bảng trải trang có `continues_from_page` | 0 | 100% | *chưa — 0/9 bảng trải trang* |

Cột cuối đo trên bản `export.py` đã sửa, chạy lại trên chính `data/pilot13`.
Dòng đầu có hai số vì `table_id` chỉ có trong nhãn sinh MỚI: trên nhãn cũ của
`pilot13` phần mất giảm 93 → 71, còn khi dựng lại nhãn bằng `kie_full` hiện tại
thì tờ nặng nhất (273 cặp) mất **0**, và trang 2 của nó tách ra đúng **4 bảng**
thay vì một.

Hai dòng cuối cần bộ sinh, không phải chỗ xuất: `state: blank` đòi `markup.py`
phát cả span rỗng, `continues_from_page` đòi có bảng thật sự tràn trang.

---

## Liên quan

- [`kie-thiet-ke-nhan.md`](kie-thiet-ke-nhan.md) — 12 bản chữa cho 167 ca hỏng
- [`kie-cau-hoi-kiem-schema.md`](kie-cau-hoi-kiem-schema.md) — 250 câu kiểm nhãn
- [`ban-do-repo.md`](ban-do-repo.md) — bốn tầng nhãn của một trang
