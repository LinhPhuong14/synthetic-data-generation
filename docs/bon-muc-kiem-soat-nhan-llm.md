# Bốn mức kiểm soát nhãn khi LLM thay rule-base

> Bản **thiết kế**, chưa phải hiện thực — không một dòng code nào trong tài
> liệu này. Câu hỏi nó trả lời: *nếu bỏ rule-base + corpus và để LLM sinh, làm
> sao kiểm soát được tới mức synthgen — không thiếu hộp layout nào, không
> thiếu hộp KIE nào?*
>
> Căn cứ: đo ngày **21-09-2026** trên `data/thu1k` (158 bản ghi nhánh luật),
> `data/pilot-llm` (9 bản ghi nhánh LLM), 40 tờ HTML từ `kind-mo3` /
> `kind-mo-vllm` / `pilot16`, và 122 tệp `declared/*.json` của mọi lượt LLM đã
> chạy. Công cụ: [`tools/llm/crosscheck.py`](../tools/llm/crosscheck.py),
> [`tools/llm/probe.py`](../tools/llm/probe.py).
>
> Đọc cùng: [`kiem-soat-llm.md`](kiem-soat-llm.md) (số đo tháng trước, không
> lặp lại ở đây), [`phan-tich-de-xuat-mot-luong-llm.md`](phan-tich-de-xuat-mot-luong-llm.md)
> (§3 ba bất biến nền tảng, §5 vì sao không gọi LLM cho từng hộp).

---

## 0. Tóm tắt

Độ phủ nhãn của synthgen **không đến từ `rulebase/` hay từ corpus**. Nó đến từ
ba tính chất cấu trúc, và chỉ một trong ba dính tới rule-base:

| # | tính chất | ở đâu | nhánh LLM có? |
| :--- | :--- | :--- | :--- |
| 1 | Nhãn phát theo **cấu tạo**, không phải gắn thêm | [`markup._span()`](../synthgen/markup.py) — mọi ký tự in ra đi qua đúng một hàm, hàm ấy luôn kèm `data-kind` | ✗ |
| 2 | **Cây nội dung chốt TRƯỚC khi vẽ** | `extracted` — engine biết nó định in gì | ✗ *(model đã sinh, bị vứt)* |
| 3 | Hộp **đo từ DOM**, không từ lời khai | 5 phép đo JS trong `generators/html/page.py` | ✓ |

Với tính chất 1, *"không chữ nào thiếu hộp"* **không phải một chỉ số chất
lượng — nó là điều bất khả**. Không tồn tại đường mã nào in chữ mà không kèm
nhãn. Synthgen không *cố gắng* gắn đủ nhãn; nó *không thể* gắn thiếu.

Đó là toàn bộ khác biệt, và nó tái tạo được mà không cần rule-base.

---

## 1. Hiện trạng, đo được

### 1.1 Cùng lớp suy diễn, hai người dựng, hai kết quả

`derive.py` + `kie_full.py` + `overlay.py` đọc DOM đã dàn và dựng vùng, thực
thể, cặp KIE. Cùng mã ấy chạy cho cả hai nhánh:

| chỉ số (trung vị/trang) | thu1k (luật) | pilot-llm (LLM) |
| :--- | ---: | ---: |
| thực thể | 203 | 52 |
| **cặp KIE** | **176** | **6** |
| **% thực thể vào được một cặp** | **89,6%** | **24,6%** |
| % cặp có **nhãn in thật** | 12% | **100%** |
| nhãn vùng khác nhau / trang | 7 | 5 |
| vốn từ nhãn vùng, gộp cả bộ | **16** | **7** |

Hai dòng cuối là hai vấn đề riêng biệt, không cùng nguyên nhân.

### 1.2 Vấn đề KIE — và vì sao chẩn đoán đầu của tôi SAI

> **Đính chính (23-09-2026).** Bản đầu của tài liệu này nói 24,6% là hệ quả
> của `draw_llm.py` truyền `extracted={}`. Kiểm lại thì **cả hai vế đều sai**,
> và tôi để nguyên phần dưới vì cách một chẩn đoán sai trông *đúng* đáng ghi
> lại hơn cả kết luận.
>
> **Vế sai thứ nhất — `extracted` không phải nguyên nhân.** `kie_full.py` đọc
> `extracted` ở đúng bốn chỗ, và cả bốn chỉ lấy `doc_type` làm **khoá tra
> `kie_descriptions.json`**. Docstring nói lưới bảng "được ĐỐI CHIẾU với
> `extracted.menu`" — đối chiếu một lần lúc viết, không phải phụ thuộc lúc
> chạy. `extracted` rỗng làm hỏng **câu mô tả**, không làm mất **cặp**.
>
> **Vế sai thứ hai — 24,6% là số chết.** `data/pilot-llm/records` sinh
> 14-09; commit `d14df8e` ("Lưu kie.pairs đầy đủ ngay lúc vẽ") là 21-09, và
> từ đó `draw_llm.py` gọi `kie_full.complete()` + `phrasing.voice_record()`
> y như nhánh luật. Tôi đo trên bản ghi sinh ra một tuần TRƯỚC bản vá.
>
> Bài học là về PHÉP ĐO, không về KIE: **một thư mục `data/` không mang ngày
> tháng trong tên là một cái bẫy.** `crosscheck.py` đọc bất cứ thứ gì được
> trỏ vào và không hỏi bộ ấy sinh bằng bản mã nào.

`kie_full.py` tự khai trong docstring rằng nó dựng lưới bảng **bằng hình học**
rồi **đối chiếu với `extracted.menu`** — "khớp 600/600 tài liệu thử".

```
extracted RỖNG:   thu1k 0/60        pilot-llm 9/9
```

Nguồn: [`synthgen/draw_llm.py:578`](../synthgen/draw_llm.py) —
`R.build(..., extracted={}, ...)`, đóng cứng.

Nhưng model **đã sinh ra cây nội dung**. `declared/*.json` có:

```
khoá:       ['loai_tai_lieu', 'plan', 'data', 'doc_title', 'archetype', 'rows', …]
data tree:  ['issuer', 'document', 'customer', 'amount', 'note', 'signers']
```

Cây tồn tại, được lưu, rồi bị vứt ở bước dựng bản ghi.

Bằng chứng khớp: **12% cặp có nhãn in bên luật, 100% bên LLM**. Nghĩa là bên
LLM chỉ còn sót đúng loại cặp tầm thường nhất — "nhãn in : giá trị". **88% số
cặp của nhánh luật là loại cần suy từ hình học, và bên LLM chúng bằng 0.**

### 1.3 Vấn đề layout: chín nhãn không bao giờ xuất hiện

Nhãn chỉ có ở nhánh luật: `Image`, `List-Group`, `Stamp`, `Footnote`,
`Formula`, `Watermark`, `Caption`, `Bibliography`, `Table-Of-Contents` — **9
trên 16**. Nhánh LLM không có nhãn nào mà nhánh luật thiếu.

Và chữ nằm ngoài mọi vùng đã khai, đo trên 40 tờ model viết:

| | run mồ côi | vùng `declared` | vùng suy từ thẻ |
| :--- | ---: | ---: | ---: |
| trước `repair.zoned()` | 926 (18,2%) | 299 | 222 |
| sau `repair.zoned()` | **589 (11,6%)** | **521** | **0** |

337 run (36%) vá được bằng máy vì tổ tiên chúng là thẻ ngữ nghĩa (`<p>`,
`<section>`, `<header>`, `<ol>`). **589 run còn lại (64%) nằm trong
`<div class="field-row">`, `"checklist-item"`, `"field-value"`,
`"clause-item"`** — tên class model tự đặt. Suy nhãn vùng từ những cái tên ấy
là **đoán**, và `repair.py` có nguyên tắc riêng cấm đúng chuyện đó.

---

## 2. Bốn mức

| mức | model viết | engine viết | phủ nhãn | đa dạng bố cục |
| :--- | :--- | :--- | :--- | :--- |
| **0** hiện tại | trọn HTML, tự gắn nhãn | không gì | 88% run · **24,6% KIE** | tối đa |
| **1** sửa + gác | trọn HTML | `repair` vá cơ học, cổng đo | ~88% run · KIE tuỳ `extracted` | tối đa |
| **2** khung/mực | khung + CSS + cây nội dung | **phát mọi span** | **100% theo cấu tạo** | cao |
| **3** nội dung | chỉ cây nội dung | dựng toàn bộ trang | 100% | = synthgen |

Mức 0→1 là chỗ đang đứng. Mức 3 là synthgen với corpus do LLM viết — kiểm soát
tối đa, đa dạng bố cục bằng không, và nó **không giải quyết bài toán** đã đặt
ra (xem [`muc-tieu.md`](muc-tieu.md)).

Nên tài liệu này bàn mức 2.

---

## 3. Mức 2: model đặt CHỖ, engine điền MỰC

### 3.1 Repo đã tự phát minh ra nguyên tắc này

[`synthgen/adorn.py`](../synthgen/adorn.py) viết thẳng:

> *"Model quyết tờ giấy này CÓ con dấu hay không, và dấu nằm ở đâu. Engine
> quyết con dấu ấy TRÔNG RA SAO."*

`agent/compose_page.py` đã gọi `seals(html)` rồi `hands(html)` — điền con dấu
và nét chữ ký thật vào chỗ model đặt sẵn, **trước cổng gác**. Nguyên tắc đã
chạy trong production cho **hai loại mực**.

Mức 2 là mở rộng đúng nguyên tắc ấy ra **mọi chữ**. Không phải một kiến trúc
mới; là một kiến trúc đã có, áp cho một tập rộng hơn.

### 3.2 Hợp đồng

Model viết khung — tự do đặt class, tự do viết CSS, tự do xếp khối:

```html
<div class="hdr-left">
  <slot data-path="issuer.name"></slot>
  <slot data-path="issuer.address" label="Địa chỉ"></slot>
</div>
```

Engine thay mỗi `<slot>` bằng `_span(kind, text)` lấy từ cây `data`. Thuộc
tính `label` sinh thêm một span nhãn in — **nhãn cũng do engine phát**, vì
48% phần chữ model không khai vào cây chính là nhãn in và tiêu đề (§4).

### 3.3 Bảng cần một vòng lặp

Một slot là một giá trị; bảng là cấu trúc lặp:

```html
<tr data-each="rows">
  <td data-path="name"></td>
  <td data-path="qty"></td>
  <td data-path="price"></td>
</tr>
```

Đây là chỗ khó nhất của mức 2, và là chỗ quan trọng nhất: **88% cặp KIE của
nhánh luật sinh ra từ bảng.** Vòng lặp cũng là nơi engine biết cột nào là cột
nào, nên `table_pairs()` có neo mà không cần dựng lại lưới bằng hình học.

### 3.4 Cross-check hai chiều, miễn phí

Vì chữ chỉ còn **một nguồn**, hai lỗi thành bất khả thay vì phải gác:

| lỗi | trước | sau |
| :--- | :--- | :--- |
| slot trỏ `data-path` không có trong cây | — | lỗi cứng, bắt được lúc thay |
| lá cây không slot nào trỏ tới | *"kế hoạch hứa X mà trang không in nó ra"* — **101 lần** trong log | lỗi cứng |
| một giá trị in ra hai lần | **25 lần** trong log | bất khả — một lá, một slot |

Đúng "đo chéo hai đầu ra" mà repo vẫn dùng để bắt lỗi, nhưng ở đây nó không
phải một phép kiểm chạy sau: nó là **điều kiện để có mực trên giấy**.

---

## 4. Cái mức 2 KHÔNG tự giải quyết

Đây là chỗ tôi đã suýt nói quá. Luận điểm "100% theo cấu tạo" chỉ đúng nếu cây
`data` chứa mọi chữ sắp in. Hôm nay nó không:

Đo trên **122 tệp `declared/`, 12.997 run có nhãn**, so cây `data`+`rows` với
chữ thật trong HTML (đã chuẩn hoá số định dạng và văn xuôi dài):

```
  phủ bởi cây          : 7.295 / 12.997  =  56,1%
  trung vị theo tài liệu:                   47,3%
  phân vị 10%           :                   22,2%
```

5.702 run không được cây phủ, chia hai:

| | số | xử lý |
| :--- | ---: | :--- |
| **nhãn in / tiêu đề** (`colhdr`, `meta.label`, `invoice.field.label`, `clause.head`, `sign.title`, `section`) | 2.738 (48%) | engine sở hữu — thuộc tính `label` ở §3.2 |
| **nội dung model viết thẳng vào HTML** (`clause.body` 404, `menu.note` 325, `sign.name` 151, `meta.value` 142, `note` 117) | 2.964 (52%) | **model phải khai** |

Nên phát biểu đúng của mức 2 là:

> **Mức 2 không cải thiện tỉ lệ khai báo — nó làm việc KHÔNG khai báo trở
> thành bất khả.** Cây nội dung là đường duy nhất để chữ lên giấy.

Đó là một cơ chế mạnh hơn mọi cổng gác, nhưng nó **dịch chuyển gánh nặng chứ
không xoá**: model phải viết cây đầy đủ gấp đôi hôm nay. Nếu nó không viết nổi,
trang ra thiếu chữ — và thiếu chữ thì **nhìn thấy được**, khác hẳn thiếu nhãn.

---

## 5. Kinh tế token — tính lại cho trung thực

Đo được ([`probe.py`](../tools/llm/probe.py), song song 64):

```
  decode   874 token/s        prefill  92.880 token/s     → prefill nhanh gấp 106×
  50k tờ × 5.000 token ra:    decode 79,4 giờ (96%)   prefill 3,4 giờ (4%)
```

**Token ra quyết định gần như toàn bộ thời gian.** Nên thay đổi nào cắt token
ra là thay đổi đáng giá, và cắt prompt vào thì không (prompt 22.722 token chỉ
chiếm 4%).

Mức 2 đổi cấu trúc đầu ra:

| | hôm nay | mức 2 |
| :--- | :--- | :--- |
| cây nội dung | 56% lượng chữ | **100%** lượng chữ |
| HTML | 100% lượng chữ + markup | chỉ khung + CSS, **0%** chữ |
| **tổng chữ viết ra** | **1,56×** | **1,0×** + chi phí slot |

Tiết kiệm thật nhưng **khiêm tốn hơn con số 30–40% tôi ước lúc đầu**: cây phải
dày gấp đôi, và mỗi `<slot data-path="…">` tốn token của chính nó. Ước dè dặt:
**15–25%**, và cần đo chứ không tin.

---

## 6. Điểm không quay lại được

| quyết định | quay lại được? |
| :--- | :--- |
| ~~Nối `extracted`~~ — chẩn đoán đã bác (§1.2) | — |
| `repair.zoned()` — vùng khai từ thẻ | ✓ đã làm, đảo được |
| Cổng đo `orphan_share`, ngưỡng trong YAML | ✓ ngưỡng là dữ liệu |
| **Hợp đồng `<slot>`** | ✗ — đổi `page.md`, đổi schema, mọi lượt cũ không sinh lại được bằng prompt mới |
| **Bỏ HTML tự do, chỉ nhận khung** | ✗ — mất khả năng model bịa cấu trúc chưa ai nghĩ ra |

Dòng cuối là cái giá thật của mức 2, và nó không đo được bằng số: **một khối
model chưa từng được dạy thì nó vẫn đặt slot vào đó được, nhưng một CÁCH SẮP
XẾP chưa từng có thì khung vẫn cho, còn một LOẠI MỰC chưa từng có thì không.**
Ví dụ: mã vạch, con dấu, chữ ký đã có đường riêng; loại thứ tư thì phải thêm
vào engine trước.

---

## 7. Đường đi đề xuất

Mỗi bậc **đo trước khi đi tiếp** — repo này đã một lần siết luật kế hoạch mà
không đo trước, và nó giết 4 trên 6 tờ:

| # | việc | đo gì để biết đúng | chi phí |
| :--- | :--- | :--- | :--- |
| 1 | ~~Nối `extracted`~~ — **đã bác**, xem §1.2 | — | — |
| 2 | Đo lại KIE trên bộ sinh SAU `d14df8e` | `crosscheck.py` trên `data/23-09-llm-*` | một lượt chạy |
| 3 | Siết `orphan_share` 0,99 → 0,85 → 0,45 | tỉ lệ qua cổng ở từng bậc | chỉ sửa YAML |
| 4 | Dạy `page.md` chín nhãn vùng chưa bao giờ xuất hiện | vốn từ nhãn vùng 7 → ? | prompt |
| 5 | **Hợp đồng `<slot>`** cho khối không bảng | phủ nhãn, token ra, tỉ lệ qua cổng | lớn |
| 6 | Mở rộng slot sang bảng (`data-each`) | % cặp KIE từ bảng | lớn |

Bậc 1–2 có thể làm hôm nay và chúng trả lời câu hỏi quan trọng nhất: **24,6%
là do thiếu neo, hay do chuyện khác?** Nếu nối `extracted` kéo được lên
70–80% thì mức 2 chỉ còn phải gánh phần layout, và bậc 5–6 nhẹ đi nhiều.

---

## 7b. ĐÃ LÀM GÌ, VÀ ĐO ĐƯỢC GÌ (23-09-2026)

> Phần này ghi kết quả thật, ghi đè mọi ước lượng ở các mục trên khi hai bên
> chỏi nhau. Công cụ: [`tools/llm/batches.py`](../tools/llm/batches.py).

### Chỗ nghẽn gốc: schema KHÔNG được ép

`data` khai là object tự do ⇒ schema MỞ ⇒ `strict` phải tắt trên OpenAI ⇒
model trả nửa vời. Cùng phôi, cùng lời nhờ, chỉ khác một cờ:

| | `strict: false` | `strict: true` |
| :--- | ---: | ---: |
| token ra | 812 | **5 192** |
| khoá trả về | các khoá CON của `plan` ở mức gốc | `plan`, `rows`, `data`, `html` |
| `html` | rỗng | **11 847 ký tự**, vẽ được |

Sửa: `data` thành danh sách phẳng `[{path, value}]`, schema tự đóng, và
`agent/client.py::closed()` tự nhận ra để bật ép — không buộc `planner.py`
hay `compose_layout.py` (vốn gửi schema mở) phải đổi theo.

### Bốn lô cùng seed 606, so có kiểm soát

| | f | g | h | **i** |
| :--- | ---: | ---: | ---: | ---: |
| qua cổng | 2/12 | 1/12 | 4/12 | *(xem báo cáo)* |
| trang xuất ra | 9 | 15 | 21 | |
| trường KIE | 490 | 547 | **1 495** | |
| lỗi markup | 9 tờ | **0** | 0 | 0 |

`g` khác `f` ở `repair.unnest()` + bí danh nhãn vùng; `h` khác `g` ở
`repair.rows_out()`; `i` thêm bảng từ tiếng Việt và vị từ `acceptable_kind`
dùng chung.

### Ba lỗi "một luật, nhiều người dựng" đã bắt

| luật | mấy người dựng | hậu quả đo được |
| :--- | :--- | :--- |
| bảng nào là bảng | `_Spans` khôi phục số đếm khi `</table>` đóng | hai bảng CÙNG trang gộp làm một; `table_id` đụng nhau giữa các trang |
| tên `data-kind` nào hợp lệ | cổng chữ, bộ giải mã, `plan_problems` | `plan_problems` quên vế `_COINED` -> loại `menu.number`, `contract.party_a` |
| ngôn ngữ câu tả | kho `POOL`, nhánh lùi `implied_for` | nhánh lùi tự chế câu tiếng Anh cho mọi kind ngoài bảng -> **66,6%** câu tả nhánh LLM là tiếng Anh |

### Multipage: nội dung ĐÃ CÓ, chỉ không vào HTML

Model trả `rows` (JSON) và `<tr>` (HTML) cho cùng một cái bảng, và chúng lệch
rất xa: **22 trên 48 tài liệu khai nhiều dòng hơn vẽ**, tệ nhất khai 129 vẽ
18. `repair.rows_out()` dựng nốt phần thiếu bằng chính chữ model đã viết --
`data-path="line_items[13].name"` nói cả chỉ số lẫn tên trường, nên đó là một
phép CHÉP, không phải phép suy.

Cái KHÔNG giải quyết được bằng lời dặn: ép model viết đủ số dòng. Thử bốn cách
(khoảng, con số chính xác, lệnh đếm, doạ loại) và một thí nghiệm ép thẳng
"đúng 80 dòng" cho 63 `<tr>` ở lần chạy đầu, **11 ở lần thứ hai** -- không lặp
lại được. n=1 không nói được gì, và tôi đã một lần kết luận sai từ đúng một
mẫu.

---

## 8. Tham chiếu

- [`tools/llm/crosscheck.py`](../tools/llm/crosscheck.py) — đo chéo hai người dựng trên cùng lớp suy diễn
- [`tools/llm/probe.py`](../tools/llm/probe.py) — trần thông lượng, prefill vs decode, prefix cache
- [`synthgen/adorn.py`](../synthgen/adorn.py) — nguyên tắc "model đặt CHỖ, engine điền MỰC"
- [`synthgen/repair.py`](../synthgen/repair.py) — `zoned()`, và nguyên tắc "chỉ chữa thứ có đúng một cách chữa"
- [`rulebase/synthgen/_blocks.yaml`](../rulebase/synthgen/_blocks.yaml) — `gate.orphan_share`, kèm đường siết
- [`kiem-soat-llm.md`](kiem-soat-llm.md) — 18 mục số đo tháng trước
- [`phan-tich-de-xuat-mot-luong-llm.md`](phan-tich-de-xuat-mot-luong-llm.md) — §3 ba bất biến, §5 vì sao không gọi LLM cho từng hộp
