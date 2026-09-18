# Thiết kế nhãn KIE: chữa 167 ca hỏng, cho VLM học trích xuất có căn cứ

> Bản **thiết kế**, chưa phải hiện thực — không một dòng code nào trong tài liệu
> này. Đối tượng: nhãn KIE của cả hai đường sinh
> ([`pipeline/record.py`](../pipeline/record.py),
> [`pipeline/kie.py`](../pipeline/kie.py),
> [`synthgen/kie_full.py`](../synthgen/kie_full.py),
> [`synthgen/export.py`](../synthgen/export.py)).
>
> Căn cứ: 250 câu hỏi trong
> [`kie-cau-hoi-kiem-schema.md`](kie-cau-hoi-kiem-schema.md), đo trên
> `data/test1` (24 tài liệu) và `data/pilot10` (15 tài liệu, độ phủ 0,913).
> Kết quả: **83 ✅ · 78 ⚠️ · 89 ❌**. Tài liệu này thiết kế cho **toàn bộ 167 ca
> ⚠️ và ❌**, mỗi ca gán đúng một bản chữa, không ca nào bỏ sót.

---

## 0. Bốn ràng buộc mọi bản chữa phải tôn trọng

Lấy từ [`AGENTS.md`](../AGENTS.md); bản chữa nào phá một trong bốn điều này thì
sai, dù nó chữa được bao nhiêu câu.

1. **Không đo lại.** Mọi hộp mới phải đến từ chỗ engine đã dàn chữ — rect của
   `<td>`, rect của `<div>` — chứ không từ một phép dò trên ảnh.
2. **Không bảng tra theo loại chứng từ.** Luật đọc từ dữ liệu trang đã có
   (`data-path`, `data-kind`, chữ in trên giấy, cấu trúc markup).
3. **Nhãn chỉ khai thứ bộ sinh ĐÃ BIẾT.** Không suy ngược từ chuỗi đã in ra.
   Đây là trục xương sống của cả tài liệu: gần hết 167 ca hỏng là **thông tin
   bộ sinh có trong tay rồi vứt đi**, không phải thông tin phải đi tìm.
4. **Lỗi phải kêu.** Một trường khai mà không in ra là lỗi sinh, phải báo —
   không được lặng lẽ thành "không có".

---

## 1. Mười hai bản chữa, xếp theo số câu chữa được

| bản chữa | chữa | loại việc |
| --- | ---: | --- |
| **F2** · Giá trị chuẩn hoá | 35 | mang sẵn giá trị chưa định dạng |
| **F1** · Ba trạng thái & nhãn âm đóng | 27 | thêm trạng thái + tập đóng |
| **F3** · Quan hệ kiểm tra khai sẵn | 22 | mang sẵn phép tính |
| **F4** · Danh tính trường hợp nhất, bảng là mảng | 15 | hợp nhất, khử trùng |
| **F8** · Xuất xứ ảnh & độ đọc được | 15 | chép dict đã có |
| **F10** · Dữ liệu còn thiếu | 11 | **sinh thêm**, không phải nhãn |
| **F9** · Ngữ cảnh model đã khai | 9 | chép `declared.plan` |
| **F11** · Chỉ mục cấp bộ | 9 | một file mới cấp bộ |
| **F5** · Khối chữ ký & danh sách có thứ tự | 8 | đổi hình dạng |
| **F6** · Thứ tự đọc & lân cận | 7 | tính một lần lúc ghi |
| **F12** · Siêu dữ liệu & từ chối trả lời | 6 | dẫn xuất từ F1 |
| **F7** · Đơn vị đo gắn với cột số | 3 | một con trỏ |
| | **167** | |

**Bảy bản đầu chữa 134/167 ca (80%)**, và năm trong bảy là *chép lại thứ đã có*
chứ không phải nghĩ ra thứ mới.

---

## F1 · Ba trạng thái & nhãn âm đóng — 27 câu

### Triệu chứng đo được
192/773 ô bảng (24,8%) vắng mặt khỏi nhãn, và **không gì phân biệt ô trống trên
giấy với ô bị rớt khỏi nhãn**. Cả khối N (81–90) và khối AC (231–240) hỏng vì
một lý do: nhãn chỉ biết nói "có gì".

### Nhãn sau khi chữa
Mọi chỗ đáng lẽ có giá trị mang một trong ba trạng thái:

```json
{"value": "Thiếu 5 túi", "state": "printed", "bbox": [612, 498, 707, 512]}
{"value": null,          "state": "blank",   "bbox": [598, 520, 720, 534]}
{"value": null,          "state": "absent",  "bbox": null}
```

- **`blank`** — ô có trên giấy, không có mực. Hộp là rect của `<td>`/`<div>`
  rỗng, đọc từ đúng chỗ DOM đã cho mọi hộp khác (ràng buộc 1).
- **`absent`** — tờ này không có trường ấy. Chỉ sinh cho **tập đóng**, không
  bao giờ cho thế giới mở.

### Tập đóng lấy từ đâu
```
absent(tờ) = ( trường-có-thể-có(loại chứng từ) )  −  ( trường in ra trên tờ )
trường-có-thể-có = ⋃ declared.plan.field_plan của mọi tờ cùng archetype
                   ∪ tập `kind` engine phát cho archetype ấy
```

Hợp của các tờ cùng loại, không phải một bảng viết tay (ràng buộc 2). Một loại
chứng từ mới tự có tập của nó ngay tờ đầu tiên.

### Chỗ lỗi phải kêu
| trong `field_plan` | có thực thể | nghĩa |
| --- | --- | --- |
| có | có | `printed` |
| có | không | **lỗi sinh — báo, không được thành `absent`** |
| không | — | `absent` hợp lệ |

### Chi phí
`markup.py` đã biết ô nào rỗng lúc nó viết ra `<td></td>`. Việc là **đừng bỏ
qua span rỗng** khi dựng thực thể.

**Chữa:** 26–30, 81–90, 152, 156, 160, 169, 231–233, 235–236, 238–240.

---

## F2 · Giá trị chuẩn hoá — 35 câu

### Triệu chứng
Schema khai `"type": "number"` nhưng `value` là `"2.500.000"`. Mọi câu số học,
so sánh, sắp xếp, đổi đơn vị, đọc ngày đều thành câu **parse chuỗi** — và không
có gì để chấm đúng sai.

### Nhãn sau khi chữa
Chuỗi in **giữ nguyên** (OCR phải học đúng cái in ra); thêm bản đã chuẩn hoá
bên cạnh:

```json
{"value": "2.500.000", "value_norm": 2500000,
 "unit": "VND", "scale": 1, "format": "vi_thousand_dot"}

{"value": "15/06/2024", "value_norm": "2024-06-15", "format": "dd/mm/yyyy"}
{"value": "15%",        "value_norm": 0.15,         "format": "percent"}
{"value": "925",        "value_norm": 925000000,    "unit": "VND", "scale": 1000000,
 "scale_from": "Đơn vị tính: triệu đồng"}
{"value": "BB/ĐSBQ/2024/047", "format": "serial",
 "parts": {"prefix": "BB", "org": "ĐSBQ", "year": "2024", "seq": "047"}}
```

### Lấy ở đâu — điểm mấu chốt
**Không parse ngược.** `synthgen/content.py` sinh ra con số `2500000` rồi mới
định dạng nó thành `"2.500.000"`. `value_norm` là **giá trị trước khi định
dạng**, mang theo chứ không tính lại. Cùng lý lẽ với ràng buộc "hộp sinh một
lần, không đo lại": *giá trị cũng thế*.

`scale` lấy từ dòng "Đơn vị tính: triệu đồng" mà chính bộ sinh đã in ra, và
`scale_from` ghi lại chữ ấy để truy ngược.

### Chi phí
Đường LLM phức tạp hơn: model viết thẳng chuỗi. Cách rẻ: lời dặn đòi model khai
`data-value` bên cạnh `data-path` cho mọi ô số và ngày — cùng cơ chế `data-path`
đã chạy được ở `pilot10` (401 điểm khai một lượt).

**Chữa:** 19–22, 24, 51–53, 55, 60, 70–73, 75–77, 79–80, 137, 151, 154, 158,
161–162, 165, 167–168, 170–171, 174–176, 179, 227.

---

## F3 · Quan hệ kiểm tra khai sẵn — 22 câu

### Triệu chứng
Khối L (61–70) hỏng 9/10. "Thành tiền có bằng số lượng × đơn giá không?" — nhãn
có cả ba số mà không có gì nói chúng liên quan. Model học **đọc**, không học
**kiểm**.

### Nhãn sau khi chữa
```json
"checks": [
  {"op": "product", "args": ["items[2].qty", "items[2].unit_price"],
   "target": "items[2].amount", "declared": 50000000, "computed": 50000000, "ok": true},

  {"op": "sum", "column": "items[].amount", "over_rows": [0, 10],
   "target": "totals.grand", "declared": 352000000, "computed": 352000000, "ok": true},

  {"op": "percent_of", "rate": "vat.rate", "base": "totals.net",
   "target": "vat.amount", "ok": false, "delta": 1200},

  {"op": "words_of_number", "target": "totals.in_words",
   "declared": "Ba trăm năm hai triệu đồng", "ok": true},

  {"op": "count", "target": "body.clause_count", "declared": 11, "computed": 11, "ok": true},
  {"op": "date_order", "args": ["meta.issued_at", "meta.signed_at"], "ok": true}
]
```

### Vì sao bộ sinh làm được mà bộ đọc không
Nó **vừa in ra cả hai vế**. `ok: false` không phải lỗi cần sửa — một phần tờ
giấy thật có số lệch, và đó là mẫu quý nhất: nó dạy model rằng **không phải tờ
nào cũng nhất quán**, thay vì dạy rằng cộng lại thì luôn khớp.

Tỉ lệ tờ cố tình lệch nên là một thuộc tính khai trong luật, không phải hằng số
trong code.

**Chữa:** 10, 16, 18, 23, 50, 56, 61–69, 164, 172, 178, 180, 189, 219, 234.

---

## F4 · Danh tính trường hợp nhất, bảng là mảng — 15 câu

### Triệu chứng
Đo trên `pilot10`: **57/77 thực thể mang từ hai cặp trở lên** —
`items_0_ad_revenue` (declared) và `doanh_thu_quang_cao_dong_r1` (table) cùng
giá trị, cùng hộp. Và `kie.schema` bị bảng phẳng hoá: TB 37,2 thuộc tính một
trang, **cao nhất 113**.

### Nhãn sau khi chữa
Một chỗ mực → **một** trường, mang ba tên cho ba mục đích khác nhau:

```json
{"path": "items[].ad_revenue",              // danh tính MÁY, model tự khai
 "printed_header": ["Doanh thu quảng cáo (đồng)"],  // NGHĨA, lấy từ giấy
 "role": "menu.amount",                     // VAI, engine khai
 "col_index": 4, "tier": 0, "colspan": 1,
 "table_id": "t1", "row_index": 2, "row_kind": "data"}
```

Và bảng là **mảng**, không phẳng:

```json
"tables": [{"table_id": "t1", "page": 1, "header_tiers": 2,
            "columns": [...], "rows": [{"row_kind": "data", "cells": {...}}]}]
```

`kie.schema` khai `items: {"type": "array", ...}` — một mục cho cả bảng, không
phải 113 mục cho 113 ô.

### Luật khử trùng
Một thực thể chỉ được thuộc **một** trường. Thứ tự ưu tiên đặt tên:
`declared` → `table` → `label` → `family` → `implied`. Đường thua **không biến
mất**, nó chui vào trường ấy làm thuộc tính (`printed_header` của đường `table`
chính là thứ đường `declared` thiếu).

**Chữa:** 34–35, 58, 93, 96–99, 122, 130, 146, 184, 187, 190, 237.

---

## F5 · Khối chữ ký & danh sách có thứ tự — 8 câu

### Triệu chứng
`signer_name` là list phẳng xếp **phải→trái** (`x = 749, 455, 104`). Câu "người
ký thứ hai" vô nghĩa. Chức danh nằm ở list khác.

### Nhãn sau khi chữa
```json
"signatures": {
  "order_basis": "reading",
  "blocks": [
    {"index": 1, "title": "NGƯỜI ĐỀ NGHỊ", "role_note": "Chuyên viên kinh doanh",
     "name": "Nguyễn Thị Hồng Nhung", "signed": true, "ink": "hand",
     "title_bbox": [...], "name_bbox": [...], "block_bbox": [...]}
  ]}
```

Và **mọi** list trong nhãn mang `order_basis` + `index` ổn định: căn cứ pháp lý,
điều khoản, mục lục. Không list nào được để thứ tự tuỳ ý hình học.

`family` (`sign.title ↔ sign.name`) đã vào HEAD và đã chạy — 8 cặp trên
`pilot10`. Phần còn lại là gói nó thành object và khai thứ tự.

**Chữa:** 8, 42–44, 101, 111–112, 211.

---

## F6 · Thứ tự đọc & lân cận — 7 câu

### Triệu chứng
"Trường nào nằm ngay bên phải 'Số:'?" — suy từ toạ độ thì được, nhưng mỗi người
đọc nhãn lại suy một kiểu, và không ai chấm được ai đúng.

### Nhãn sau khi chữa
Trên mỗi thực thể:
```json
{"reading_order": 27, "page_order": 27,
 "neighbors": {"left": 26, "right": 28, "above": 19, "below": 34}}
```

Tính **một lần lúc ghi**, từ hộp engine đã có — không phải một phép dò, và
không ai tính lại về sau (ràng buộc 1 áp cho cả thứ tự đọc, không riêng hộp).

Thứ tự đọc cũng là thứ `order_basis` của F5 trỏ tới, nên hai bản chữa dùng
chung một định nghĩa thay vì mỗi chỗ một kiểu.

**Chữa:** 40, 102–103, 106, 108–109, 128.

---

## F7 · Đơn vị đo gắn với cột số — 3 câu

### Triệu chứng
Cột "Đơn vị" và cột "Số lượng" là hai cột rời. Không nhãn nào nói cột nào **đo**
cột nào, nên "Theo sổ tính bằng đơn vị gì?" không trả lời được.

### Nhãn sau khi chữa
Một con trỏ, trên cột đơn vị:
```json
{"path": "items[].unit", "measures": ["items[].qty", "items[].stock_qty"]}
```

Model đã khai cả hai đường dẫn rồi; lời dặn chỉ cần đòi thêm quan hệ giữa chúng.

**Chữa:** 59, 74, 163.

---

## F8 · Xuất xứ ảnh & độ đọc được — 15 câu

### Triệu chứng
Cả khối Z (201–210) hỏng. `manifest.jsonl` của `synthgen` **không ghi một chữ
nào** về chuỗi làm cũ — bộ sinh vừa bôi vệt mực, vừa nén JPEG, vừa vặn trang,
rồi vứt hết thông tin ấy đi.

### Nhãn sau khi chữa
Cấp trang:
```json
"provenance": {"augmentation": ["ink_decay", "scan_banding"],
               "toner": "low", "drum": null, "warp": "page_curl",
               "jpeg_quality": 74, "scale": 0.82}
```
Cấp thực thể, chỉ khi có:
```json
{"occluded_by": "seal.round", "occluded_ratio": 0.18,
 "clipped": false, "warped": true}
```

### Chi phí
**Rẻ nhất trong cả tài liệu.** `rulebase` bốc chuỗi làm cũ ra rồi mới gọi
`degradation`; dict ấy đang nằm trong bộ nhớ. Chép nó vào manifest là xong.
`occluded_by` cần một phép giao hộp giữa vùng con dấu (đã có trong
`layout_annotations`) và hộp chữ — không phải phép dò trên ảnh.

**Chữa:** 105, 149, 197–198, 201–210, 220.

---

## F9 · Ngữ cảnh model đã khai — 9 câu

### Triệu chứng
`declared/*.json` có `plan.purpose`, `plan.issuer`, `plan.signers`,
`plan.doc_kind` — model **viết ra rồi vứt**. Câu "tóm tắt tờ giấy", "ai gửi cho
ai", "bên nào có nghĩa vụ" không có căn cứ nào, dù căn cứ ấy từng tồn tại.

### Nhãn sau khi chữa
```json
"context": {"purpose": "Đối chiếu doanh thu bản quyền quý II/2024",
            "issuer": "CÔNG TY CỔ PHẦN BÁO CHÍ VÀ XUẤT BẢN SÔNG THU",
            "recipient": "Tác giả Nguyễn Văn Thanh",
            "parties": [{"role": "bên A", "name": "..."}],
            "doc_role": "reconciliation", "template_id": "copyright_statement_v2",
            "source": "declared"}
```

`"source": "declared"` quan trọng: đây là **ý định của bộ sinh**, không phải
thứ đọc được từ pixel. Người đọc nhãn phải phân biệt được hai loại.

**Chữa:** 114, 134–135, 138–139, 212, 214, 216–217.

---

## F10 · Dữ liệu còn thiếu — 11 câu

### Đây không phải bản chữa nhãn
Bốn nhánh dưới đây **nhãn đã sẵn sàng, chỉ là chưa có một mẫu nào để học**:

| nhánh | đo được | phải sinh |
| --- | --- | --- |
| bảng trải trang | **0/11** bảng tràn trang, dù 8/24 tài liệu 2 trang | ép bảng đủ dài để `paginate.py` phải cắt |
| mực viết tay | `ink` **100% `print`** trên `pilot10` | bật trục `handwriting` cho một phần lượt chạy |
| ô để trống | 24,8% ô vắng nhưng không cố ý | sinh biểu mẫu **chưa điền** |
| dòng trùng nhau | không có mẫu | cho phép hai dòng giống hệt |

Khi bảng trải trang có mẫu, nhãn khai thêm:
```json
{"table_id": "t1", "page": 2, "continues_from_page": 1,
 "row_index_global": 14, "row_index_in_page": 2, "header_repeated": true}
```
`synthgen/paginate.py` cắt bằng phép đo và **biết chỗ cắt** — chỉ là chưa khai.

**Chữa:** 49, 115, 121, 126, 191–193, 195–196, 199–200.

---

## F11 · Chỉ mục cấp bộ — 9 câu

### Triệu chứng
Mọi câu so sánh nhiều tờ (khối AD) hỏng, vì không có chỗ nào nhìn được cả bộ:
"hai tờ trùng số hiệu không", "tờ nào lệch khỏi mẫu chuẩn".

### Nhãn sau khi chữa
Một file cấp bộ, một dòng một tài liệu:
```jsonl
{"doc_id": "...0011", "archetype": "copyright_reconciliation_statement",
 "issuer": "...", "serial": "BB/ĐSBQ/2024/047", "issued_at": "2024-07-15",
 "template_id": "...", "field_set": ["issuer.name", "items[].royalty", ...],
 "field_set_hash": "a3f1…", "pages": 1, "table_rows": 7}
```

`field_set_hash` cho câu "tờ nào lệch khỏi mẫu chuẩn của loại nó" một đáp án
đo được: tờ có tập trường khác đa số các tờ cùng archetype.

**Chữa:** 125, 129, 243–245, 247–250.

---

## F12 · Siêu dữ liệu & từ chối trả lời — 6 câu

### Nhãn sau khi chữa
```json
{"certainty": "high", "certainty_basis": "declared"}
```
`certainty` **dẫn xuất từ `source`**, không phải điểm số ai đó nghĩ ra:
`declared` → high · `table`/`label` → high · `family` → medium · `implied` → low.

Và cấp trang, dẫn xuất thẳng từ tập `absent` của F1:
```json
"unanswerable": ["merchant.tax_code", "customer.name"]
```

Đây là thứ biến câu "câu hỏi nào về tờ này không trả lời được" từ một câu đánh
đố thành một câu có đáp án — và là nguồn mẫu huấn luyện cho **model biết nói
không biết**.

**Chữa:** 143, 150, 223, 225, 229–230.

---

## 2. Hình dạng nhãn đích, một chỗ

Gộp mười hai bản chữa lại, một trường bảng trông như sau — và đây là toàn bộ
cái mới so với hôm nay:

```json
{
  "path": "items[].qty",
  "printed_header": ["Số lượng", "Theo sổ"],
  "role": "menu.qty",
  "table_id": "t1", "row_index": 2, "row_kind": "data",
  "col_index": 5, "tier": 1, "colspan": 1,

  "value": "200", "value_norm": 200, "unit": "Túi", "scale": 1,
  "format": "integer",
  "unit_from": "items[].unit",

  "state": "printed",
  "bbox": [640, 443, 690, 455], "bbox_1000": [403, 197, 435, 203],
  "lines": [[640, 443, 690, 455]],

  "reading_order": 61, "neighbors": {"left": 60, "right": 62},
  "certainty": "high", "certainty_basis": "declared",
  "occluded_by": null, "warped": false
}
```

Ba nguyên tắc đọc ra từ hình dạng này:

1. **Ba tên cho ba mục đích** — `path` (máy), `printed_header` (giấy),
   `role` (engine). Hôm nay một tên gánh cả ba và chỉ đúng một.
2. **Hai bản của giá trị** — `value` để OCR học đọc, `value_norm` để KIE chấm.
3. **Trạng thái là bắt buộc** — không có `state` thì "không có" và "chưa biết"
   là một.

---

## 3. Ma trận truy vết — 167 ca, không ca nào bỏ sót

| bản chữa | câu chữa được | số câu |
| --- | --- | ---: |
| **F2 · Giá trị chuẩn hoá** | 19–22, 24, 51–53, 55, 60, 70–73, 75–77, 79–80, 137, 151, 154, 158, 161–162, 165, 167–168, 170–171, 174–176, 179, 227 | 35 |
| **F1 · Ba trạng thái & nhãn âm đóng** | 26–30, 81–90, 152, 156, 160, 169, 231–233, 235–236, 238–240 | 27 |
| **F3 · Quan hệ kiểm tra khai sẵn** | 10, 16, 18, 23, 50, 56, 61–69, 164, 172, 178, 180, 189, 219, 234 | 22 |
| **F4 · Danh tính trường hợp nhất, bảng là mảng** | 34–35, 58, 93, 96–99, 122, 130, 146, 184, 187, 190, 237 | 15 |
| **F8 · Xuất xứ ảnh & độ đọc được** | 105, 149, 197–198, 201–210, 220 | 15 |
| **F10 · Dữ liệu còn thiếu (sinh thêm)** | 49, 115, 121, 126, 191–193, 195–196, 199–200 | 11 |
| **F9 · Ngữ cảnh model đã khai** | 114, 134–135, 138–139, 212, 214, 216–217 | 9 |
| **F11 · Chỉ mục cấp bộ** | 125, 129, 243–245, 247–250 | 9 |
| **F5 · Khối chữ ký & danh sách có thứ tự** | 8, 42–44, 101, 111–112, 211 | 8 |
| **F6 · Thứ tự đọc & lân cận** | 40, 102–103, 106, 108–109, 128 | 7 |
| **F12 · Siêu dữ liệu & từ chối trả lời** | 143, 150, 223, 225, 229–230 | 6 |
| **F7 · Đơn vị đo gắn với cột số** | 59, 74, 163 | 3 |
| | **cộng** | **167** |

---

## 4. Thứ tự làm, theo đòn bẩy

| đợt | làm gì | chữa | vì sao trước |
| ---: | --- | ---: | --- |
| 1 | **F2 + F3** | 57 | cùng một nguồn: giá trị chưa định dạng và phép tính bộ sinh đã làm. Làm một lượt thì đi một lần qua `content.py` |
| 2 | **F1** | 27 | mở khoá cả khối phủ định và khối bẫy — thứ chống bịa, quan trọng nhất cho VLM |
| 3 | **F4 + F8** | 30 | F4 gỡ trùng lặp trước khi nhãn phình thêm; F8 rẻ nhất, chép một dict |
| 4 | **F10** | 11 | đổi kế hoạch sinh, chạy được song song với đợt 3 |
| 5 | **F5 + F6 + F7 + F9** | 27 | đều nhỏ, đều phụ thuộc thứ tự đọc chung của F6 |
| 6 | **F11 + F12** | 15 | dẫn xuất, làm sau khi các bản trên đã ổn định |

Đợt 1 và 2 cộng lại chữa **84/167 ca (50%)** và không đụng tới phép ghép nào.

---

## 4b. Đo thế nào để biết đã xong

Mỗi bản chữa phải kèm một phép đo chạy được trên bộ mới sinh, không phải một
câu khẳng định:

| bản | phép đo | ngưỡng |
| --- | --- | --- |
| F1 | tỉ lệ ô bảng có `state` | 100% |
| F1 | số trường `field_plan` khai mà không in ra | **0**, và mỗi cái phải báo |
| F2 | tỉ lệ trường số/ngày có `value_norm` | 100% |
| F3 | tỉ lệ dòng tổng có `checks` | 100% |
| F4 | thực thể mang >1 trường | **0** (hôm nay 57/77) |
| F4 | thuộc tính trong `kie.schema` một trang | < 25 (hôm nay cao nhất 113) |
| F5 | khối chữ ký có `title` lẫn `name` | 100% |
| F8 | trang có `provenance` | 100% |
| F10 | bảng trải trang | > 0 (hôm nay 0/11) |
| F10 | trang có `ink: hand` | > 0 (hôm nay 0) |

---

## 5. Bốn thứ cố tình KHÔNG làm

1. **Không nhãn âm mở.** `absent` chỉ sinh cho tập đóng dẫn từ `field_plan` và
   `kind`. "Mọi thứ không có trên tờ giấy" là vô hạn và dạy được đúng số không.
2. **Không để model viết hộp.** `data-path` model khai là **tên**, không phải
   toạ độ. Hộp vẫn do engine dàn chữ sinh ra, không có ngoại lệ.
3. **Không parse ngược chuỗi đã in.** `value_norm` mang từ nguồn xuống. Nếu một
   ngày phải parse ngược thì đó là dấu hiệu nhãn bị ghi sai chỗ, không phải lý
   do viết bộ parse.
4. **Không nhét ô bảng vào `kie.schema` dạng phẳng.** Bảng là mảng. Một trang
   113 thuộc tính không phải thứ đem hỏi một VLM.

---

## Liên quan

- [`kie-cau-hoi-kiem-schema.md`](kie-cau-hoi-kiem-schema.md) — 250 câu và phép đo sinh ra tài liệu này
- [`ban-do-repo.md`](ban-do-repo.md) — bản đồ kho, bốn tầng nhãn
- [`duong-ong.md`](duong-ong.md) — ai sở hữu toạ độ
- [`AGENTS.md`](../AGENTS.md) — bốn ràng buộc ở §0
