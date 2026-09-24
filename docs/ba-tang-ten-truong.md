# Ba tầng cho một cái tên trường

> Đã hiện thực: [`synthgen/field_tier.py`](../synthgen/field_tier.py),
> [`rulebase/field_tiers.json`](../rulebase/field_tiers.json),
> [`tests/test_field_tier.py`](../tests/test_field_tier.py). Số đo trong tài
> liệu này lấy từ **394 tệp `data/*/declared/*.json`** (8 555 lượt
> `field_plan.kind`, 12 318 lượt `data.path`) và **12 423 tệp HTML** trong
> `data/*/html` + `data/*/rejected`, đo ngày **24-09-2026** bằng
> [`tools/llm/field_tiers_report.py`](../tools/llm/field_tiers_report.py).

---

## 0. Lỗi mà tài liệu này chặn

Một cái tên trường model viết ra mà kho chưa biết, bị **ánh xạ về khoá gần
nhất**. Hộp vẫn đúng pixel, nhãn vẫn đọc trôi chảy, và nghĩa thì sai. Tệ hơn:
câu mô tả cũng tra theo cái khoá sai ấy, nên bản ghi mang **hai** thông tin sai
mà chỉ có **một** trong hai nhìn thấy được.

Đường đi cũ có đúng hai chỗ làm chuyện này, và cả hai đều được dặn làm:

| chỗ | câu dặn | hậu quả đo được |
| --- | --- | --- |
| lời dặn model (`SAY["en"]["map"]`, `page.en.md`) | *"If none fits, take the nearest in meaning"* | 1 352 / 8 555 lượt (**15,8%**) rơi vào ba khoá hứng chung |
| [`synthgen/repair.py::settle`](../synthgen/repair.py) | ánh xạ tên không đọc được về `invoice.field` | **0** lần trên 1 748 010 lượt `data-kind` |

Con số 0 của `settle()` đo hai lần, vì phép đo đầu quẩn: HTML trong
`data/*/html` đã ĐI QUA `repair()` rồi, nên đếm trên đó là đếm sau khi ánh xạ
đã xảy ra. Phép đo thứ hai chạy trên 8 555 lượt `field_plan.kind` —
**không qua `repair()` bao giờ** — và cũng ra 0. Nhánh chót ấy là mã chết.

Ba khoá hứng chung ấy: `meta.value` (547 lượt, nhiều nhất cả bộ),
`invoice.field` (454), `invoice.field.label` (351).

`settle()` thì hoá ra là mã chết trên dữ liệu thật — nhánh chót của nó không
chạy lần nào. Nên **không sửa nó**: lý lẽ của nó ("mất cả tờ đắt hơn một nhãn
rộng") đúng cho `data-kind` trên giấy, và nó không đá nhau với luật ở đây vì nó
không bao giờ tới lượt.

Chỗ thật sự hỏng là **lời dặn**, và nó đã được thay.

---

## 1. `data.path` là nửa không ai gác

`field_plan.kind` nửa đóng từ lâu: từ vựng đo được cộng cửa thoát `_COINED`.
`data.path` thì hoàn toàn tự do, và số đo cho thấy cái giá:

| | lượt | tên khác nhau | họ khác nhau |
| --- | ---: | ---: | ---: |
| `field_plan.kind` | 8 555 | 338 | **50** |
| `data.path` | 12 318 | 7 841 | **377** |

377 họ đường dẫn cho chừng ấy khái niệm mà 50 họ `kind` đã gọi tên xong. Riêng
cái bảng hàng có **bốn** tên: `items[]` (3 033 lượt), `line_items[]` (2 038),
`rows[]` (270), `table.rows[]` (392). Một mô hình học trên bộ ấy học được rằng
tên trường không mang nghĩa.

---

## 2. Ba tầng

| tầng | điều kiện | câu tả từ đâu | vào bộ chính |
| --- | --- | --- | --- |
| `closed` | khoá **trúng đúng** một khoá trong sổ | sổ đăng ký | có |
| `semi_open` | họ quen, lá mới, **kèm câu tả model đề xuất** | model, ghi nguyên văn | có |
| `staging` | không họ nào quen, **hoặc** thiếu câu tả | **không có** (`None`) | không |
| `reject` | tên không đọc được | — | không |

`reject` không phải tầng mới: đó đúng là điều cổng chữ
[`llm_page.problems`](../synthgen/llm_page.py) vẫn làm, chỉ được gọi tên để báo
cáo đếm được.

### 2.1 Vì sao không có ngưỡng tương tự

Câu hỏi tự nhiên là "đặt ngưỡng bao nhiêu thì coi là trúng". Câu trả lời là
**không có ngưỡng nào**, và đó là quyết định chứ không phải thiếu sót.

`patient.dob` gần `customer.dob` hơn mọi khoá khác trong sổ. Một ngưỡng tương
tự sẽ nhận nó, gán khoá kia, rồi gán luôn **câu tả** của khoá kia — và bản ghi
ra đời không mang dấu vết nào của việc đã đoán.
[`tests/test_field_tier.py::test_a_near_miss_is_never_resolved_to_the_key_it_nearly_matches`](../tests/test_field_tier.py)
canh đúng chuyện đó trên bốn cái tên lệch một ký tự.

Ngưỡng duy nhất trong hệ này là **chất lượng câu tả** cho tầng `semi_open`, và
nó đọc từ [`rulebase/synthgen/_kie_gates.yaml`](../rulebase/synthgen/_kie_gates.yaml)
— cùng bảng [`synthgen/kie_gate.py`](../synthgen/kie_gate.py) đã chấm mô tả,
không phải một bảng thứ hai.

### 2.2 Sổ đăng ký phái sinh, không chép

`registry()` dựng từ ba nguồn đã có:

```
synthgen/llm_page.py::kinds()          87 kind đo từ chính HTML engine dựng
synthgen/design.py::COLUMNS            27 cột, mỗi cột đã mang sẵn `describe`
rulebase/kie_field_glossary.json       `_by_kind` 74 · `_by_path` 60
```

Gộp lại: **101 khoá `kind`**, **60 khoá `path`**, và **họ thì không khai ở đâu
cả** — nó là đoạn đầu của chính những khoá ấy.

`COLUMNS` vào sổ là một sửa đo được: `kinds()` nhặt từ 300 trang dựng thật nên
nó bỏ sót cột hiếm — `menu.quota`, `menu.meter_prev`, `menu.meter_now`,
`menu.discountprice`, `menu.rate_service` có trong `COLUMNS` mà không có trong
mẫu. Chính `llm_page.py` đã viết ra cái bẫy này và chữa nó bằng cách nâng cỡ
mẫu; nhưng cỡ mẫu nào cũng còn một cái đuôi, còn `COLUMNS` thì không phải mẫu.

---

## 3. Hai nhóm loại chứng từ

| nhóm | tầng được dùng | vì sao |
| --- | --- | --- |
| `closed_by_law` | **chỉ** `closed` | tập trường do văn bản pháp quy ấn định; thêm một trường là dựng tờ giấy tự nhận là mẫu luật định mà mang trường luật không có |
| `open_domain` | cả ba | tập trường do người soạn |
| `unreviewed` | như `closed_by_law` | chưa ai xếp — xem §3.2 |

Xếp nhóm **đọc từ dữ liệu phôi** (`id` và tiêu đề in trên giấy), không từ một
bảng 471 dòng: một bảng phẳng là thứ mà loại giấy thứ 472 sẽ thiếu khỏi, im
lặng — đúng điều [`AGENTS.md`](../AGENTS.md) mục 5 cấm. Mỗi luật ghi kèm số
hiệu văn bản pháp quy, vì khi ai đó hỏi *"vì sao tờ này không được đặt tên
trường mới"*, câu trả lời phải là một số hiệu, không phải một ý kiến.

### 3.1 Đã xếp được bao nhiêu

Trên **471 phôi** (34 viết bằng Python + 437 khai bằng YAML) và **30 family**
của [`agent/grammar.py`](../agent/grammar.py):

| nhóm | phôi | family |
| --- | ---: | ---: |
| `open_domain` | 268 | 11 |
| `unreviewed` | **178** | 12 |
| `closed_by_law` | 25 | 7 |

178 phôi chưa xếp gom thành 68 cụm tiêu đề, và **tám cụm đầu phủ 109 phôi**:
`GIẤY XÁC NHẬN` (19), `GIẤY CHỨNG NHẬN` (18), rồi sáu họ `PHIẾU *`/`BẢNG KÊ`
mười hai cái một. Chúng chưa xếp vì thật sự lưỡng nghĩa: `PHIẾU THU`,
`PHIẾU CHI`, `BẢNG CHẤM CÔNG`, `BẢNG THANH TOÁN TIỀN LƯƠNG` là biểu mẫu kế toán
của TT 200/2014/TT-BTC và TT 133/2016/TT-BTC, nhưng hai thông tư ấy là **hướng
dẫn**, không phải lệnh cấm sửa — nên "có phải `closed_by_law` không" là một câu
hỏi cho chủ kho, không phải cho một luật regex.

### 3.2 Vì sao `unreviewed` siết chứ không nới

Hai chiều sai không cân nhau:

* siết nhầm một tờ soạn tự do → **mất đa dạng**, đếm được ngay trong báo cáo,
  sửa bằng một dòng `overrides`;
* nới nhầm một biểu mẫu luật định → **sinh nhãn sai**, và nhãn sai không tự kêu.

Đổi `unreviewed_policy` sang `open_domain` là quyết định của chủ kho, không
phải mặc định của mã. Báo cáo in ra đúng bao nhiêu loại giấy đang bị siết vì
chưa ai xếp nhóm.

> **Đã quyết (24-09-2026).** Chủ kho chọn **giữ siết** và soát dần 178 phôi,
> thay vì mở `unreviewed` thành `open_domain`. Nên `compose_page.run()` in
> thêm một dòng mỗi lượt: bao nhiêu tờ thuộc loại chưa xếp nhóm và vì thế chỉ
> được dùng tầng `closed`. Không có dòng ấy thì cái giá của quyết định này
> nằm im trong `compose_report.json`, và một quyết định không ai thấy cái giá
> là một quyết định sẽ không bao giờ được xem lại.

---

## 4. Đường đi của một cái tên, sau khi sửa

```
schema()            `kind`: anyOf[ enum 101 khoá đã duyệt | ngữ pháp _COINED ]
                    `describe`: bắt buộc có mặt, rỗng được khi `kind` đã đóng
                    `path`: description liệt kê 6 họ đã duyệt
      |
llm_page.problems   cổng chữ — KHÔNG đổi, vẫn nhận/loại đúng như cũ
      |
field_tier.classify xếp tầng. KHÔNG thêm dòng nào vào `found`: một cái tên lạ
                    không làm mất tờ giấy
      |
draw_llm            mark_pairs() gắn `tier`/`status`/`in_batch` lên từng cặp KIE
                    (lấy vế NGHIÊM hơn giữa `role` và `path`)
      |
export.document     bỏ cặp `in_batch: False`, ghi `held_for_review: N`
compose_page.run    ghi `staging/field_candidates.jsonl` để người soát
```

Hai điều cố ý **không** làm:

* **Không gác trang.** `field_plan` vốn không vào bộ huấn luyện, nên loại cả tờ
  vì một cái tên lạ là trả giá cao nhất cho lỗi rẻ nhất.
* **Không xoá câu tả cũ của cặp `staging`.** Nó còn nguyên trong `records/`,
  vì người soát cần đọc nó mới quyết được. Thứ đổi là **ai được tin nó**.

---

## 5. Đo được gì trên 394 tệp `declared/`

Cùng một mẫu, chấm bằng luật cũ và luật mới.

### `kind` — 8 555 lượt

| | lượt | phần |
| --- | ---: | ---: |
| **trước:** rơi vào khoá hứng chung | 1 352 | **15,8%** |
| `closed` | 8 224 | 96,1% |
| `semi_open` | 0 | 0,0% |
| `staging` | 331 | 3,9% |
| `reject` | 0 | 0,0% |

### `path` — 12 318 lượt

| | lượt | phần |
| --- | ---: | ---: |
| `closed` | 3 077 | 25,0% |
| `semi_open` | 0 | 0,0% |
| `staging` | 9 236 | **75,0%** |
| `reject` | 5 | 0,0% |

### Hai con số phải đọc kèm

**`semi_open` bằng 0 không phải vì tầng ấy vô dụng — nó chưa được HỎI lần
nào.** Mọi `declared/*.json` trên đĩa sinh ra trước khi schema có khoá
`describe`, nên một lá mới trong họ quen không thể mang câu tả và rơi xuống
`staging` vì thiếu câu tả, không vì cái tên. Tách ra:

| | `kind` | `path` |
| --- | ---: | ---: |
| `staging` vì **thiếu câu tả** (họ quen — lượt tới tự thu) | 74 | 308 |
| `staging` vì **họ lạ** (phải người soát) | 257 | 8 928 |

**75% của `path` là một con số thật, không phải một cái cổng đặt quá chặt.**
Nó nói rằng ba phần tư đường dẫn model viết dùng một họ chưa ai duyệt, và
`items[]` một mình là 3 033 trên 8 928 lượt ấy — đúng cái bảng hàng mà
`line_items[]` đã có tên. Đây là việc soát, không phải việc chỉnh ngưỡng:
duyệt `items[]` vào sổ là chấp nhận hai tên cho một thứ, mà đó chính là bệnh.

---

## 6. Còn phải làm

| # | việc | đo gì để biết đúng |
| --- | --- | --- |
| 1 | Chủ kho xếp nhóm cho 8 cụm phủ 109 phôi (§3.1) | `unreviewed` 178 → ? |
| 2 | Một lượt sinh thật với schema mới | `semi_open` > 0 lần đầu; `generic_share` so với 15,8% |
| 3 | Soát `staging/field_candidates.jsonl`, duyệt khoá đáng duyệt vào `_by_path` | `path.closed` 25,0% → ? |
| 4 | Đo lại sau khi lời dặn mới chạy | `meta.value` 547 lượt → ? |

Mục 2 phải chạy **trước** mục 3: duyệt khoá dựa trên một lượt chạy sinh bằng
lời dặn cũ là duyệt cho một phân bố sắp biến mất.

---

## 7. Tham chiếu

- [`synthgen/field_tier.py`](../synthgen/field_tier.py) — xếp tầng, một vị từ cho mọi nơi hỏi
- [`rulebase/field_tiers.json`](../rulebase/field_tiers.json) — chính sách: nhóm loại giấy, khoá hứng chung
- [`rulebase/kie_field_glossary.json`](../rulebase/kie_field_glossary.json) — sổ đăng ký: `_by_kind`, `_by_path`
- [`tools/llm/field_tiers_report.py`](../tools/llm/field_tiers_report.py) — đo trước/sau trên cùng một mẫu
- [`bon-muc-kiem-soat-nhan-llm.md`](bon-muc-kiem-soat-nhan-llm.md) — §7b, ba lỗi "một luật, nhiều người dựng"
- [`kie-thiet-ke-nhan.md`](kie-thiet-ke-nhan.md) — hình dạng nhãn KIE
