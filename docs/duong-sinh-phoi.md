# Đường sinh thứ ba — model viết PHÔI, mã điền giá trị

> Tài liệu này ghi **số đo**, không ghi ý kiến. Mỗi khẳng định đến từ một phép
> đo trên dữ liệu thật trong `data/`, và ghi rõ đo trên bao nhiêu mẫu.
>
> Đọc cùng: [`llm-in-pipeline.md`](llm-in-pipeline.md) (ba track hiện có),
> [`kiem-soat-llm.md`](kiem-soat-llm.md) (số đo của đường model-viết-từng-trang),
> [`ke-hoach-refactor-engine.md`](ke-hoach-refactor-engine.md) (Phase 1-8).

---

## 1. Ba đường, cùng một bản ghi ở cuối

| đường | cấu hình | ai viết HTML | ai quyết giá trị | lời gọi model |
| --- | --- | --- | --- | --- |
| luật | `path: rule` | `synthgen/markup.py` | `rulebase/` + `synthgen/content.py` | **0** |
| model viết từng trang | `path: page` | model, mỗi trang một lần | model | **1 mỗi trang thử** |
| **model viết phôi** | `path: template` | model, mỗi **phôi** một lần | `synthgen/values.py` | **1 mỗi phôi** |

Cả ba đổ về `pipeline/record.py` và ra cùng một hình dạng bản ghi
(`schema_version: 8`). Không đường nào thay đường nào — chọn bằng
`rulebase/synthgen/_blocks.yaml::llm_path.path`, hoặc bằng chính lệnh chạy.

```bash
python -m agent.compose_template --want 200 -o data/phoi-v1   # pha 1, có model
python -m synthgen.run_fill data/phoi-v1 --per-template 50    # pha 2, KHÔNG model
```

Hoặc qua `tasks.py`: `make llm-templates N=200`, rồi `make llm-fill`.

---

## 2. Một phôi là gì

Một tờ giấy Việt Nam viết bằng HTML, với **chữ in sẵn giữ nguyên** và **giá
trị thay bằng `{{đường.dẫn}}`**:

```html
<p>Mã số thuế:
   <span data-kind="store.tax_code" data-path="issuer.tax_code">{{issuer.tax_code}}</span></p>
```

`Mã số thuế:` là chữ đã in trên tờ mẫu trắng, nên nó ở lại. Mã số thật là thứ
người ta điền vào, nên nó là chỗ trống. Ranh giới ấy là toàn bộ phán đoán mà
pha 1 xin ở model.

Bảng hàng viết **đúng một dòng mẫu**, đánh dấu `data-repeat="line_items"`;
`synthgen/template.py::fill_html` nhân nó ra N dòng và thay `[]` bằng `[0]`,
`[1]`, … ở **cả** `data-path` lẫn chữ.

### Ba tính chất có được miễn phí

1. **`data-path` và chữ in không thể lệch nhau.** Cả hai đọc cùng một ô của tờ
   khai sự thật. Đo trên `data/pilot16`: 15 tờ trượt cổng vì
   `data-path="X"` in ra hai giá trị khác nhau, và **không tờ nào** là hai sự
   thật mâu thuẫn — toàn bộ là một sự thật viết hai kiểu chữ. Đường phôi
   không sinh ra được ca ấy.
2. **Số học đóng kín.** `qty × unit_price = amount` tính ở một chỗ
   (`synthgen/values.py::_rows`). Đường cũ có hai nguồn cho cùng cái bảng —
   mảng `rows` trong JSON và các `<tr>` trong HTML — và đo trên 48 tài liệu,
   22 tài liệu khai nhiều dòng hơn vẽ, tệ nhất khai 129 vẽ 18.
3. **Đường dẫn không trôi nghĩa.** `slots[].path` là `enum` lấy từ sổ đóng 60
   khoá của `synthgen/field_tier.py`, nên bộ giải mã có ràng buộc không sinh
   nổi một tên ngoài sổ. Đo trên 394 tệp `declared/` của đường cũ: **7 841**
   đường dẫn khác nhau, **377 họ**, cho cùng chừng ấy khái niệm mà 50 họ đã
   gọi tên xong.

---

## 3. Chi phí — bảng sinh ra từ báo cáo, không viết tay

`make llm-cost` (hay `python -m tools.llm.path_cost --images 10000`) đọc
`data/*/report.json`, `data/*/compose_report.json`,
`data/*/template_report.json` và `data/*/fill_report.json` rồi dựng bảng. Ô nào
chưa có lượt nào đo được thì nó ghi **chưa đo được** — không có ước lượng nào
trong bảng ấy, vì một con số ước lượng trong bảng so sánh trông giống hệt một
con số đo được.

Chạy ngày 25-09-2026, cho 10 000 ảnh — **cả ba đường đều đo thật**:

```text
đường        lời gọi model         giây          token  đo trên
---------------------------------------------------------------
rule                     0        4 980              0  22-09-26-synthetics-multipage
page                26 500    1 821 300    645 699 000  30 lượt
template             1 472       99 105     27 072 141  pha1 1 lượt · pha2 1 lượt

  `page`     tỉ lệ đạt cổng 38% -> 2,65 lời gọi cho mỗi ảnh GIỮ LẠI
  `template` 417 phôi x 24 lần điền; pha 2 đạt 100%, pha 1 đạt 28%
             -> 18 lần ít lời gọi model hơn `page`
```

**18 lần ít lời gọi, 24 lần ít token.** Con số ấy tính với tỉ lệ đạt pha 1 là
**28%** — mức đo được TRƯỚC khi `mark_repeats` có mặt. Với 70% (mục 3b) thì số
lời gọi xuống còn 596, tức **44 lần** ít hơn; bảng sẽ tự cập nhật ở lượt pha 1
tiếp theo, và cho tới lúc ấy nó giữ con số đã đo chứ không giữ con số đã suy.

### 3b. Pha 1 — hai lượt thật, và ba phép chữa giữa chúng

| lượt | phép chữa đang có | đạt | ghi chú |
| --- | --- | --- | --- |
| `data/24-09-phoi-v1` | không | **2/14 = 14%** | đứt ở 20/60 vì máy chủ vLLM treo |
| `data/25-09-phoi-v2` | `runify` + `enclose` | **17/60 = 28%** | 1 965s, 220 505 token ra, phủ 85% sổ |
| *(chạy lại cổng)* | + `mark_repeats` | **42/60 = 70%** | replay trên chính `rejected/`, 0 lời gọi |

Giá mỗi lời gọi, đo trên lượt v1 (v2 chạy ở concurrency 6 nên giây không so
được với `pilot16` ở concurrency 4):

| | phôi | trang (`data/pilot16`) |
| --- | --- | --- |
| token RA mỗi lời gọi (trung vị) | **3 596** | 9 334 |
| token VÀO mỗi lời gọi | ~13 000 | 23 346 |

Một phôi tốn **2,6 lần ít token đầu ra** hơn một trang: nó không mang giá trị
nào, và bảng của nó là một dòng mẫu thay vì N dòng.

**`enum` làm đúng việc của nó.** Qua cả hai lượt, không một phôi nào bịa đường
dẫn trong mảng `slots`. Hai ca lọt được đều nằm trong `html` — một `string` tự
do mà `enum` không với tới, và đúng lý do lớp gác thứ hai tồn tại.

#### Taxonomy đổi sau mỗi phép chữa, và đó là cách đọc nó

Lượt v1, hình trội là **chỗ trống trần** (7/12). Sau `runify` + `enclose` hình
ấy **biến mất khỏi v2**, và hình trội thành một hình khác: **chỗ trống dòng lặp
nằm ngoài mọi khối `data-repeat`** (28/43). Model viết đúng cú pháp `[]` rồi
quên đánh dấu khối bao nó.

| phép chữa | chữa hình gì | ở đâu |
| --- | --- | --- |
| `runify()` | nhãn nằm trên `<div>`/`<h1>`/`<td>` thay vì `<span>` | `synthgen/repair.py` |
| `enclose()` | chỗ trống trần, bọc bằng chính `slots` model khai | `synthgen/template.py` |
| `mark_repeats()` | khối lặp model quên đánh dấu | `synthgen/template.py` |

Cả ba là phép **ĐỌC**, không phép đoán, và cả ba đều tự dừng đúng chỗ:

* `runify` không chạm thẻ có thẻ con — bọc nó là dựng đúng cái run-có-thẻ-lồng
  mà cổng cấm.
* `enclose` không bọc chỗ trống model **không** khai trong `slots` — bịa một
  nhãn là gắn sai danh tính cho một run, tệ hơn không gắn. Cùng luật "hỏng thì
  đóng, không ánh xạ về khoá gần nhất" của `synthgen/field_tier.py`.
* `mark_repeats` không đánh dấu khi một khối ôm **hai** nhóm — lúc ấy không
  khối nào bung được mà không kéo khối kia theo, và đó là vấn đề cấu trúc thật
  chứ không phải thiếu một thuộc tính.

Tám phôi vẫn trượt hình dòng-lặp sau `mark_repeats`: chúng là ca khối ôm hai
nhóm, đúng chỗ phép suy tự dừng.

#### Còn lại là việc của lời dặn, không của mã

Sau ba phép chữa, 18/60 phôi còn trượt, và không hình nào chiếm quá 8. Chúng
là mâu thuẫn nội tại của chính phôi — chỉ số tường minh `signers[0].name`,
`slots` khai thiếu so với HTML, đường dẫn bịa trong `html`, khối `data-repeat`
không đóng thẻ. Không phép chữa nào đoán được ý model ở những ca ấy mà không
đoán sai, nên chúng ở lại cho `agent/prompts/template.md` §2b — mục ấy đã liệt
kê đủ sáu hình kèm số đo.

**Cả hai pha đều đo thật.** Pha 1: `data/25-09-phoi-v2`. Pha 2:
`data/24-09-phoi-fill`, 232 tờ, 0 lời gọi, 5,09 giây mỗi tờ, 232/232 qua cổng.

**Cột đáng tin là LỜI GỌI.** Giây không so trực tiếp được: mỗi lượt chạy ở một
mức song song khác nhau, và nhánh LLM còn đổi theo tải máy chủ — 43 ký tự/giây
lúc bận so với 137-145 lúc rảnh, chênh hơn ba lần trên cùng một đường sinh
(`kiem-soat-llm.md` mục 1).

### Cái nhân lớn nhất là tỉ lệ đạt cổng, không phải tốc độ

Đường `page` trả giá cổng **cho mỗi tờ**. Đường `template` trả nó **một lần
cho mỗi phôi**, rồi mọi lần điền sau đều đạt — phôi đã qua cổng thì tờ điền từ
nó cũng qua, vì cấu trúc HTML không đổi giữa hai lần điền.

| | tờ thử | tờ qua cổng | tỉ lệ |
| --- | --- | --- | --- |
| `page`, `data/pilot16` | 60 | 12 | 20% |
| `page`, `data/24-09-div-before` | 40 | 8 | 20% |
| `page`, cộng 30 lượt | — | — | **38%** |
| **`template` pha 2, `data/24-09-phoi-fill`** | 232 | 232 | **100%** |

Một trăm phần trăm không phải vì cổng bị nới: `synthgen/run_fill.py` chạy đúng
`synthgen/llm_page.py::problems()` mà đường cũ chạy, không sửa một dòng. Nó
đạt vì **cổng đã chạy một lần ở pha 1**, trên chính phôi ấy, và cấu trúc HTML
không đổi giữa hai lần điền — thứ đổi là chữ và số dòng. `why_tally` của lượt
232 tờ ấy rỗng.

---

## 4. Hộp đo trên trang ĐÃ ĐIỀN, không bao giờ trên phôi

Phôi dàn ra được và đo được — đó chính là cái bẫy. Giá trị thật dài ngắn khác
chỗ trống, nên mọi hộp đo trên phôi đều sai cho trang điền từ nó. Đo trên một
phôi hoá đơn, toạ độ phần nghìn:

| | `x0` | `y0` | `x1` | `y1` | bề rộng |
| --- | --- | --- | --- | --- | --- |
| hộp `store.name` trên **phôi** | 62 | 50 | 179 | 63 | **117** |
| hộp `store.name` trên **trang đã điền** | 62 | 50 | 449 | 63 | **387** |

`{{issuer.name}}` là 17 ký tự; `CÔNG TY TNHH KỸ THUẬT VÀ TỰ ĐỘNG HOÁ TÂN PHÁT`
là 45. Dùng lại hộp của phôi là gắn nhãn cho **30%** vệt mực.

Nên `synthgen/template.py::Template` **không mang một toạ độ nào** — không
`bbox`, không `layout_annotations`, không gì. Cách chắc chắn nhất để không ai
lỡ tay dùng lại chúng là không bao giờ đo chúng. Trang đã điền đi qua đúng
`synthgen/draw_llm.py::draw_one` mà mọi trang khác của kho đi qua, và Chromium
đo lại từ đầu (AGENTS.md luật 1 và 2). `tests/test_fill_measure.py` khoá lại
điều ấy.

---

## 5. Đa dạng — hai tầng, và cái bẫy lớn nhất của đường này

| tầng | câu hỏi | ai giữ trí nhớ | khi nào |
| --- | --- | --- | --- |
| trong một phôi | tổ hợp giá trị này đã điền vào ĐÚNG phôi này chưa | `synthgen/fill.py::Filler` (`agent/coverage.py::CoverageMemory` dùng lại nguyên văn) | trước khi vẽ, miễn phí |
| cả lô | tờ vừa vẽ có ĐÁP xuống chỗ một tờ gần đây không | `agent/diversity.py::DiversityWarden` | sau khi vẽ, đọc pixel |

Tầng một chạy trên `agent/fingerprint.py::Fingerprint` ba tầng dựng từ **giá
trị** thay vì từ `DocumentPlan` — cùng lớp, cùng phép xếp hạng từ điển, khác
mỗi nguồn của ba tuple. Tầng hai là `DiversityWarden` không sửa một dòng.

Cái giá của hai tầng ở đây rẻ hơn hẳn đường cũ: một tờ bị loại vì trùng hình
học đốt thêm **một lần bốc giá trị** (một phần nghìn giây) cộng **một lần dàn
trang** (một tới ba giây), thay vì một lời gọi model 110-430 giây.

### Cái bẫy: một phôi không có khối lặp chỉ làm được ba tờ

`tools/llm/template_yield.py` điền mỗi phôi **16 lần**, dàn từng tờ, băm
`layout_annotations` thành lưới 8×12 rồi đếm dấu vân **khác nhau**. Đo trên 18
phôi chuyển từ `data/pilot17` + `data/24-09-div-before`:

| khối `data-repeat` | dấu vân khác nhau / 16 | J trung vị giữa hai tờ | cặp vượt ngưỡng 0,60 |
| --- | --- | --- | --- |
| **0** (10 phôi) | 2, 2, 3, 3, 3, 3, 3, 3, 5, 7 — trung vị **3** | 0,82 – 1,00 | **100%** |
| **≥1** (8 phôi) | 11, 12, 12, 13, 14, 14, 14, 16 — trung vị **14** | 0,42 – 0,57 | 34% |

Một phôi không có khối lặp chỉ đổi được **độ dài chữ** giữa hai lần điền, và
một cái tên dài thêm mười ký tự không đẩy khối nào sang ô lưới khác. Điền nó 50
lần là ghi 47 bản sao vào bộ dữ liệu — và chúng **qua cổng**, nên không gì kêu
lên. Con số 100% ở cột cuối là chỗ duy nhất điều đó đọc được.

Hai chỗ đã sửa theo số đo này:

* `synthgen/run_fill.py::budget()` — phôi không khối lặp nhận tối đa
  `NO_REPEAT_FILLS = 4` tờ, phôi có khối lặp nhận trọn `per_template`. Luật đọc
  từ **dữ liệu của phôi** (có khối lặp hay không), không từ một bảng theo loại
  chứng từ (AGENTS.md mục 5).
* `agent/prompts/template.md` — nói thẳng con số ra và bảo model tìm cho ra thứ
  lặp lại trên tờ giấy nó đang vẽ. Gần như mọi biểu mẫu Việt Nam đều có một:
  dòng bảng, khối chữ ký, điều khoản đánh số, danh mục tài liệu đính kèm, dãy
  ô tích.

`template_report.json` đếm `templates_without_repeat`, nên tỉ lệ ấy đọc được
ngay sau pha 1 — **không gác**, vì một giấy báo một trang là giấy thật.

---

## 6. Ba lớp gác của pha 1, và vì sao chặt hơn đường cũ

`agent/compose_page.py` cố ý **không** ép `data-path` thuộc sổ đóng: một tên
lạ ở đó hỏng đúng một tờ, và `synthgen/field_tier.py` hạ nó xuống `staging` mà
không mất tờ nào. Phép tính ấy đảo ngược khi phôi được dùng lại hàng nghìn lần.

| lớp | ở đâu | bắt được gì |
| --- | --- | --- |
| 1 | `enum` trong `response_format` | bộ giải mã không sinh nổi đường dẫn ngoài sổ |
| 2 | `synthgen/template.py::problems()` | cú pháp chỗ trống, chỗ ngồi của nó, khối lặp |
| 3 | điền thử rồi chạy `synthgen/llm_page.py::problems()` | mọi thứ cổng trang vẫn bắt — nhưng chỉ đo được trên bản ĐÃ ĐIỀN |

Lớp 3 điền thử **ba** lần với ba số dòng khác nhau, không một: một phôi qua
cổng ở 8 dòng rồi vỡ bố cục ở 24 dòng là một phôi hỏng mà một lần thử không
thấy — và ta không chọn được số dòng cho từng lần điền về sau.

---

## 7. Mồi bộ phôi đầu tiên từ trang đã có

`tools/llm/pages_to_templates.py` chuyển trang model đã viết thành phôi, không
gọi model lần nào:

```bash
python -m tools.llm.pages_to_templates data/24-09-div-before data/pilot17 -o data/24-09-phoi-boot
```

Một `<span data-path="X">chữ</span>` thành `{{X}}` khi và chỉ khi `X` nằm trong
sổ đóng; mọi span khác giữ nguyên chữ và bị gỡ `data-path` — nó thành chữ in
sẵn của tờ mẫu. Những `<tr>`/`<div>` liền nhau mang cùng bộ đường dẫn
`line_items[]` gom lại thành một dòng mẫu.

Mất mát **đo được**, và công cụ in ra:

| lượt chuyển | lượt `data-path` vào sổ |
| --- | --- |
| `data/24-09-div-before` | 81% |
| `data/pilot17` | 74% |
| `data/pilot13` | 3% |
| `data/pilot14` | 0% |

Ba lô cuối sinh **trước khi sổ tồn tại**. Chuyển chúng thì phần lớn giá trị
đóng băng thành chữ in — phôi vẫn hợp lệ, nhưng mọi tờ ra từ nó mang cùng một
cái tên công ty. Số `slots` mỗi phôi trong `convert_report.json` là chỗ thấy
điều đó.

Kết quả trên hai lô mới nhất: **18/18 phôi qua cổng**, 77% lượt `data-path`
thành chỗ trống.

---

## 8. Đa dạng thật — ba đường, cùng một thước

Rẻ hơn mà kém đa dạng hơn thì không giải quyết được gì. `tools/llm/
path_diversity.py` đọc `records/**/*.json` của cả ba đường, băm bằng đúng
`agent/fingerprint.py::geometry_fingerprint` (lưới 8×12 trên
`layout_annotations` phần nghìn), rồi đếm dấu vân **khác nhau**.

```bash
python -m tools.llm.path_diversity data/22-09-26-synthetics-multipage \
    data/24-09-div-before data/pilot17 data/24-09-phoi-fill --by-template
```

### Trên cỡ lô thật

| lô | đường | ảnh | bố cục khác nhau | tỉ lệ | lưới mực khác nhau |
| --- | --- | --- | --- | --- | --- |
| `22-09-26-synthetics-multipage` | luật | 899 | 318 | 35,4% | 77 |
| `24-09-div-before` | page | 70 | 32 | 45,7% | 28 |
| `pilot17` | page | 81 | 42 | 51,8% | 42 |
| `24-09-phoi-fill` | **template** | 427 | 161 | 37,7% | **110** |

### Cắt mọi lô về 70 ảnh đầu — cột duy nhất so được

Tỉ lệ `bố cục / ảnh` **giảm tự nhiên theo cỡ lô** (lô càng lớn càng dễ đụng
lại một bố cục cũ), nên bảng trên không so được trực tiếp giữa một lô 899 ảnh
và một lô 70 ảnh.

| lô | đường | bố cục khác nhau / 70 | tỉ lệ | lưới mực |
| --- | --- | --- | --- | --- |
| `22-09-26-synthetics-multipage` | luật | 26 | 37,1% | 10 |
| `24-09-div-before` | page | 32 | 46,4% | 28 |
| `pilot17` | page | 39 | 55,7% | 39 |
| `24-09-phoi-fill` | **template** | **19** | **27,1%** | 18 |

**Đường phôi thua cả hai đường kia ở cỡ này, và con số ấy phải đọc nguyên
văn.** Nó không phải một chi tiết để giải thích cho qua.

### Vì sao nó thua, và con số nói ra điều đó

Đa dạng của đường phôi **bị chặn trên bởi SỐ PHÔI**, không bởi số ảnh. Điền
một phôi thêm nghìn lần không thêm được bố cục nào sau khi nó đã cạn. Đo trực
tiếp (`--by-template`, gắn từng bản ghi về phôi qua `template_id` trong
`declared/`):

    18 phôi, 307 ảnh, 124 bố cục khác nhau
    -> 6,89 bố cục mỗi phôi

Phân bố rất lệch, và nó lệch đúng theo mục 5: bốn phôi nhiều khối lặp cho
15-22 bố cục mỗi cái, còn ba phôi không khối lặp cho đúng **1**.

Lô `24-09-phoi-fill` chạy trên **18 phôi** — bộ mồi chuyển từ hai lượt cũ,
không phải bộ phôi thật của đường này (mục 3 tính 417 phôi cho 10 000 ảnh).
Bảy mươi ảnh đầu của nó nhất thiết đến từ 18 bộ xương, còn 70 ảnh của đường
`page` đến từ 70 bộ xương khác nhau. Phép cắt về cùng cỡ ảnh, vốn là phép
cắt ĐÚNG cho hai đường kia, lại đo sai biến ở đây.

**Điểm hoà với nhánh luật, tính từ số đo:** nhánh luật cho 318 bố cục trên cả
lô 899 ảnh của nó. Ở 6,89 bố cục mỗi phôi, đường phôi vượt con số ấy ở
**318 ÷ 6,89 ≈ 46 phôi**. Bộ 417 phôi mà bảng chi phí tính cho 10 000 ảnh
ngoại suy ra chừng **2 900 bố cục** — gấp chín lần nhánh luật, với 0 lời gọi
model ở pha 2.

Đó là phép ngoại suy, và nó được ghi ở đây **là** phép ngoại suy: con số đo
được là 6,89 bố cục mỗi phôi trên 18 phôi, phần còn lại là phép nhân. Một
lượt pha 1 thật sẽ vừa lấp ô trống trong bảng chi phí vừa kiểm lại chính hằng
số này trên phôi model viết (thay vì phôi chuyển từ trang cũ — chúng đóng băng
77% lượt `data-path` thành chữ in, xem mục 7, nên chúng ÍT chỗ trống hơn phôi
model sẽ viết, và ít chỗ trống là ít đa dạng).

### Hai thứ đường phôi thắng, đo được ngay

* **Lưới mực khác nhau trên mỗi ảnh.** 110 lưới từ 427 ảnh so với 77 lưới từ
  899 ảnh của nhánh luật — gấp **2,7 lần** trên mỗi ảnh. Đây là tín hiệu đọc
  MỰC, không đọc nhãn, nên nó độc lập với cột bên cạnh.
* **Không hai tờ nào trùng giá trị.** 232/232 tờ có `fine` riêng
  (`plan_fingerprints.distinct_fine`), và `mean_pairwise_distance` 0,989.

---

## 9. Cái này KHÔNG giải quyết

**Đa dạng bố cục bị chặn trên bởi số phôi** — mục 8 đo nó. Mười nghìn ảnh từ
hai trăm phôi là hai trăm bộ xương, không phải mười nghìn. Đường `page` viết
một bố cục mới cho mỗi tờ và trả giá bằng một lời gọi model mỗi tờ; đây là
đúng cái đánh đổi ấy, đọc theo chiều ngược lại. Ai cần nhiều bố cục hơn thì
**xin thêm phôi**, không phải điền nhiều hơn — và đó là lý do bảng chi phí ở
mục 3 tính theo `phôi × số tờ mỗi phôi` chứ không theo một con số tổng.

**Nội dung có thật hay không.** Một hoá đơn của "Công ty TNHH Mặt Trời Mọc" là
hợp lệ và có thể chẳng tồn tại. Cùng giới hạn `agent/corpus_rules.py` đã viết
ra cho corpus, và nó không đổi ở đây.

**Phôi có hợp lý không.** `{{issuer.tax_code}}` đặt sau chữ "Số điện thoại:" là
một phôi qua hết ba lớp gác và sai. Cổng máy bắt cái đo được; ảnh vẽ ra và
người đọc bắt phần còn lại.
