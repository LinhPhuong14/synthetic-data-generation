# Kiểm soát LLM sinh dữ liệu — những gì đã ĐO được

> Tài liệu này ghi **số đo**, không ghi ý kiến. Mỗi khẳng định ở đây đến từ một
> phép đo trên dữ liệu thật trong `data/pilot*`, và ghi rõ đo trên bao nhiêu
> mẫu. Sửa gì trong `agent/compose_page.py`, `agent/prompts/page*.md` hay
> `synthgen/llm_page.py` thì cập nhật cả đây.
>
> Đọc cùng: [`llm-in-pipeline.md`](llm-in-pipeline.md) (kiến trúc),
> [`duong-ong.md`](duong-ong.md) (đường ống chính).

## 1. Thời gian = độ dài đầu ra. Không có gì khác.

Đo 60 lượt gọi (`pilot2`, `pilot-llm`), chia bốn phần tư theo độ dài HTML:

| Ký tự HTML | Giây (trung vị) | Ký tự/giây |
|---|---|---|
| 4 641 – 7 473 | 45,6 | 138 |
| 7 568 – 9 813 | 61,9 | 139 |
| 9 831 – 11 272 | 74,4 | 140 |
| 11 284 – 16 253 | 88,4 | 145 |

**Tốc độ giải mã là hằng số THEO ĐỘ DÀI TRANG, nhưng không phải hằng số theo
thời gian.** Đo lại trên `pilot7`/`pilot8`: **43** ký tự/giây khi bốn request
chạy cùng lúc lúc máy chủ bận, so với 137–145 ở bảng trên lúc rảnh. Bảng trên
vẫn đúng ở điều nó chứng minh — trang ngắn và trang dài ra cùng một tốc độ —
nhưng **con số tuyệt đối đổi theo tải, đừng viết nó vào prompt**. Một lời dặn
nói "tờ 10 000 ký tự mất 71 giây" là sai gấp ba lần khi máy bận.

Tỉ lệ đo được: **2,05 ký tự mỗi token** (không phải 2,4 như ước lượng đầu).

Suy luận đã tắt sẵn (`enable_thinking: false`, `reasoning_effort: "low"` trong
`agent/client.py`). Nên:

* Không có nút "nghĩ nhanh hơn". Chỉ có "viết ngắn hơn".
* Prompt dài thêm KHÔNG làm chậm đáng kể — đầu vào là prefill.
* Muốn nhanh thì cắt đầu ra. Đầu ra chia ra: `<style>` **23%**, `<tbody>`
  **21%**, khoảng trắng **5%**, khối `rows` **4%**.

Hệ quả thực hành: bỏ `rows` chỉ tiết kiệm ~3 giây — **không đáng** đánh đổi
phép kiểm số học.

## 2. Thời gian đổ vào tờ HỎNG là khoản lãng phí lớn nhất

Cùng 60 lượt ấy: tờ đạt trung vị 56,2s, tờ hỏng 72,5s, và **83% tổng số giây
đổ vào tờ bị loại**. Ở tỉ lệ đạt 22%, mỗi tờ *giữ được* tốn 333 giây thay vì
72.

**Nâng tỉ lệ đạt đáng giá hơn mọi thứ khác.** Một phần trăm tỉ lệ đạt đáng giá
hơn một phần trăm tốc độ.

## 3. Ba nguyên nhân hỏng đã tìm ra, xếp theo số tờ

### 3.1. Prompt dạy một `kind` KHÔNG TỒN TẠI — 5/8 tờ hỏng ở pilot5

`page.md` từng viết *"con dấu có chữ thì viết `data-kind="seal.round"`"*, mà
từ vựng không có `kind` nào tên `seal`. Model làm đúng như được dặn rồi bị
loại vì đúng điều ấy.

**Bài học**: prompt là văn xuôi, và văn xuôi cũ đi lặng lẽ. Từ vựng phái sinh
từ `synthgen/llm_page.py::kinds()`, không ai buộc prompt khớp với nó.

**Cổng đã dựng**: `tests/test_llm.py::
test_the_prompt_never_teaches_a_kind_that_does_not_exist` đối chiếu mọi
`data-kind` trong CẢ BA bản prompt với `kinds()`.

### 3.2. Xin thay vì ép — `field_plan[].kind` từng là `string` tự do

Lời dặn *"đừng tự đặt tên mới"* là một lời **xin**. Model vẫn viết
`patient.name`, `project.code`, `admission.date` — những cái tên rất hợp lý mà
danh sách không có.

**Đã sửa**: `schema()` đổi `kind` thành `enum` 80 giá trị. Bộ giải mã có ràng
buộc của vLLM **không thể** sinh tên ngoài danh sách. Hết là chuyện trí nhớ.

**Nguyên tắc rút ra**: *thứ gì schema ép được thì đừng đi xin bằng prompt.*

### 3.3. Kỷ luật đánh dấu — 5/6 tờ hỏng ở pilot6, và MÁY chữa được

Sau khi sửa 3.1, nguyên nhân hỏng đổi hẳn sang hai lỗi máy móc:

| Lỗi | Cách chữa, không cần đoán |
|---|---|
| `<td class="lbl">` thiếu `data-cell` | thêm `data-cell` |
| `<br>` nằm TRONG span có nhãn | tách thành hai span |

`synthgen/repair.py` chữa cả hai **trước** khi ra cổng. Đo trên pilot6: **5/6
tờ bị loại được cứu**, tỉ lệ đạt 3/9 → 8/9.

**Nguyên tắc**: chỉ chữa thứ có ĐÚNG MỘT cách chữa. Một `data-kind` model tự
bịa thì KHÔNG chữa — đoán xem nó định nói gì là đoán, và một cái hộp gán nhãn
đoán còn tệ hơn một cái hộp không có.

Đây cũng đúng ranh giới `synthgen/markup.py` vẫn giữ: nó không "cố gắng" phát
`data-cell`, nó phát theo cấu tạo. Đừng nhờ model làm việc mà mười dòng mã làm
đúng mọi lần.

## 4. Từ vựng bị lấy mẫu thiếu

`kinds()` nhặt `data-kind` bằng cách chạy thử engine `SAMPLE` lần. Đường cong
đo được:

| Số mẫu | Số kind | Thời gian |
|---|---|---|
| 60 | 68 | 0,5s |
| 120 | 77 | 0,5s |
| 200 | 80 | 0,6s |
| 400 | 81 | 0,7s |

`SAMPLE = 60` đang nói với model rằng `menu.meter_prev`, `menu.rate_bhyt`,
`menu.self_pay` KHÔNG TỒN TẠI — rồi loại trang nào dùng chúng. **Mười hai cái
nhãn bị chối bỏ để tiết kiệm hai phần mười giây.** Đã nâng lên 300.

## 5. Lỗ hổng thật không phải mật độ, mà là ĐỘ PHỦ

| | Engine vẽ | LLM viết |
|---|---|---|
| kind khác nhau **mỗi trang** | 30 | 26 |
| kind khác nhau **cả bộ** | **72** | **48** |

LLM **không** thiếu trường trên mỗi trang (26 so với 30, và nó đạt 10/10 bốn
khối gần-phổ-quát của phôi thật). Thứ nó thiếu là **24 kind chưa bao giờ đụng
tới**: `caption.figure`, `caption.table`, `footnote`, `formula`, `colnum`,
`footer.page`, `menu.barcode`…

Nên **sàn "trường tối thiểu" sẽ không ràng buộc được gì**. Cái cần là áp lực
phủ ở mức CẢ LƯỢT — cùng lối `agent/planner.py` dùng `pressure` để phủ đuôi
phân phối. *(Chưa làm.)*

## 6. Đừng ép trường theo phôi

Model tự nghĩ ra loại chứng từ, nên **không có ánh xạ** từ "Biên bản kiểm kê
kho" nó vừa bịa về phôi `don_thuoc`. Ép trường của `don_thuoc` lên tờ kiểm kê
kho là làm ra một tờ **sai**, không phải một tờ nghèo. Và đó là lối "N phôi"
đã bị bác.

Cách dùng phôi ĐÚNG là `agent/compose_page.py::inspiration()`: đưa ba phôi rút
gọn còn **hình dạng** (danh sách khối, một bộ chữ ký), quay vòng mỗi lượt, kèm
câu *"phần lớn giấy tờ không có bảng hàng nào"*. Ví dụ để hiểu, không phải
khuôn để điền.

## 7. Tỉ lệ bảng: code từng nói dối docstring của chính nó

`wants_table` ghi "khớp engine 46%" mà viết `index % 10 < 6` = **60%**. Trong
khi 97 phôi ở `rulebase/synthgen/` chỉ **18%** BẮT BUỘC có bảng.

Đã sửa thành `(index * 46) % 100 < 46` — dãy độ lệch thấp, nên lượt 24 tờ ra
45,8% và rải đều, thay vì `index % 50 < 23` đúng tỉ lệ trên giấy nhưng dồn 23
tờ có bảng liền nhau.

## 8. Ngôn ngữ prompt: tiếng Anh làm HỎNG tiếng Việt đầu ra

`--lang` chọn giữa `page.md` (vi), `page.en.md`, `page.zh.md`. Token nạp: vi
~3 643, en ~2 578, zh ~2 485.

Nhưng đo `doc_kind` model trả về ở pilot6 (lời dặn tiếng Anh):

```
bang_tong_hop_bao_hiem            <- viết SLUG, không phải tên tiếng Việt
bien_ban_nghi_em_thu_cong_trinh   <- slug sai chính tả
binh_bao_niem_yeu                 <- tiếng Việt vô nghĩa
Hoạt động công chứng              <- không phải tên chứng từ
```

**Lời dặn tiếng Anh làm model xuất tiếng Việt kém hơn.** Cả ba bản prompt đều
nói rõ ngay đầu file rằng TỜ GIẤY phải là tiếng Việt, nhưng nói không đủ. Đây
là lý do `--lang zh` đáng thử: tiếng Trung rẻ token như tiếng Anh, mà không ở
cùng họ chữ Latin với tiếng Việt nên ít kéo đầu ra sang tiếng Anh hơn.

*(Chưa đo xong — cần một lượt `--lang zh` và một lượt `--lang vi` để so.)*

## 9. Nhãn `Watermark` và `Stamp`

Chữ chìm và con dấu là **mực phủ**: có toạ độ, có chữ đọc được, nhưng không
thuộc mạch nội dung. Gộp chúng vào `Text`/`Image` là bảo người huấn luyện rằng
"BẢN SAO" xoay 25 độ là một đoạn văn, và con dấu đỏ là ảnh minh hoạ.

Đã thêm vào `pipeline/record.py::DOCSYNTH_LABELS` (19 → 21 nhãn):

* `watermark` → `Watermark`
* hình có `data-graphic="seal"` → `Stamp` (qua `graphic_label`)

`synthgen/llm_page.py::REGIONS` giờ **phái sinh** từ `DOCSYNTH_LABELS` thay vì
chép tay — bản chép tay đã sai lúc được viết (nó có `Picture`, thuộc bảng nhãn
cũ) và sẽ không biết gì về hai nhãn mới.

## 10. Khối chữ ký là `Text`, không phải `Form`

`DOCSYNTH_LABEL_FOR_KIND` từng gán `sign.` → `Form`, lý lẽ "dòng chữ ký là ô
người ký điền vào". Nhưng thứ ĐƯỢC ĐO là chữ ĐÃ IN: "GIÁM ĐỐC", "(Ký, ghi rõ
họ tên)", tên người ký. Không ô nào, không dòng kẻ để điền.

Và `LABELS`, bảng nhãn còn lại của chính file ấy, vẫn luôn nói `Text` cho cùng
tiền tố. **Hai bảng nói khác nhau về cùng một đoạn chữ là một lỗi bất kể bên
nào đúng.**

## 11. KIE chưa phủ hết layout

Đo `data/14-09-test2` (141 bản ghi). `kie.coverage` trung vị 0,967 ở mức THỰC
THỂ nghe có vẻ ổn, nhưng ở mức VÙNG BỐ CỤC chỉ **82,1%**, và lệch rất nặng:

| Vùng | Phủ |
|---|---|
| Text, Table, Title, Page-Header, Table-Of-Contents | ~100% |
| Form | 79,8% |
| Image | 58,4% |
| List-Group | 55,8% |
| Formula | 53,1% |
| Footnote | 49,1% |
| Caption | 37,5% |
| Section-Header | 34,2% |
| Bibliography | 20,0% |
| **Page-Footer** | **7,5%** |

**15 `kind` KHÔNG BAO GIỜ vào KIE**: cả sáu họ `survey.*`, cả hai `clause.*`,
cả hai `caption.*`, cộng `footnote`, `formula`, `legal.basis`,
`masthead.motto`, `footer.page`, `watermark`.

Đó đúng là các khối thêm vào synthgen SAU, mà bộ dựng KIE chưa bao giờ được
mở rộng theo. Hệ quả: tờ khai và bảng câu hỏi có coverage 0,20–0,34 --
`bang_cau_hoi_benh` 0,20, `to_khai_y_te` 0,26.

Ba cái nên ở NGOÀI KIE (`watermark`, `footer.page`, `masthead.motto` — mực phủ
và chữ in sẵn). Mười hai cái còn lại là **lỗ hổng thật**: câu hỏi và câu trả
lời của một tờ khai CHÍNH LÀ thông tin cần trích. *(Chưa làm.)*

## 12. Chữ in sẵn không phải giá trị

Đếm trên cùng bộ: **281 trên 421** cặp thuộc họ `sign.` có `value_text` là
`"(Ký, ghi rõ họ tên)"` — lời nhắc nhà in, giống hệt trên mọi tờ. Bộ dữ liệu
đang dạy mô hình rằng người chấm công tên là "(Ký, ghi rõ họ tên)".

Luật rút ra: **một giá trị KIE phải là thứ THAY ĐỔI giữa các tờ.** Chữ in sẵn
mang đúng không bit thông tin nào. `pipeline/kie.py::FURNITURE` loại chúng
khỏi cặp; chúng vẫn nằm đủ trong `word_annotations` kèm hộp.

## 13. Trường lồng theo nhóm

`rulebase/kie_groups.json` khai nhóm theo **tiền tố `data-kind`**, không theo
tên trường in trên giấy — `kind` là từ vựng đóng do code sinh, còn tên in ra
là tiếng Việt tự do (99 tên khác nhau chỉ riêng họ `invoice.` trên 80 tờ).

Nhóm chỉ dựng khi có **từ hai trường trở lên**: một đối tượng bọc đúng một
trường chỉ làm đường dẫn dài thêm một đoạn.

Họ `invoice.` cố ý KHÔNG có nhóm — nó là chỗ chứa mọi cặp nhãn-giá trị chung
chung, và gộp chúng lại là đặt tên "thông tin" cho một cái túi.

## 14. Đọc số ở đâu

Mỗi lượt `agent.compose_page` để lại:

| Tệp | Dùng khi |
|---|---|
| `performance.md` | xem nhanh bằng mắt: vào/ra, token, giây, số lần hết hạn, vì sao trượt |
| `calls.jsonl` | một dòng một lời gọi — so hai lượt, dựng biểu đồ |
| `compose_report.json` | đầy đủ, máy đọc |
| `layout_boxes/`, `visualize_kie/` | **ảnh** — thứ duy nhất nói trang có DÙNG ĐƯỢC không |
| `rejected/`, `rejected_boxes/` | tờ trượt và ảnh của chúng, để đọc ra model hiểu sai chỗ nào |

## 15. Trần token phải co giãn theo số tờ

Trần cố định 9 000 mâu thuẫn với chính lời dặn của nó: ngân sách 8 000 ký tự
mỗi tờ, 2,05 ký tự/token, nên một tờ tốn ~3 900 token.

| Số tờ | Cần ≈ | Trần cũ 9 000 |
|---|---|---|
| 1 | 3 900 | vừa |
| 2 | 7 800 | vừa |
| 3 | 11 700 | **vượt** |
| 4 | 15 600 | **vượt** |
| 6 | 23 400 | **vượt** |

Đo trên `pilot8`: hai lời gọi duy nhất trả `reply was not JSON` là **đúng hai
tài liệu 4 tờ và 6 tờ**, cụt giữa chừng sau 168 giây. `budget(sheets)` và
`patience(sheets, floor)` trong `agent/compose_page.py` co giãn cả trần lẫn hạn
chờ — trần cao mà hạn chờ cố định thì chỉ đổi kiểu hỏng.

## 16. Model không được tự quyết nhát cắt trang

Giấy thật sang trang vì chữ chảy hết tờ, không vì người viết quyết định. Khi
model tự mở `<div class="sheet">`, đo trên `pilot8`:

| Tài liệu | Từ mỗi tờ | Độ đầy |
|---|---|---|
| `phieu_bao_chuyen_hang_0019` | 150, 43, 48, **13**, 17, 23 | 80% 18% 16% 14% 17% 15% |
| `bien_ban_hop_bcd_0006` | 237, 168 | 36% 37% |
| `bang_danh_gia_nguy_co_bao_hiem_0017` | 194, 200, 106, 185 | 59% 34% 56% 38% |

Chỉ **2 trên 11** tài liệu nhiều trang có mọi tờ đầy từ 80%.

Giờ model viết MỘT dải liên tục; `synthgen/draw_llm.py::cut_lines` nhắm bội số
chiều cao A4 rồi trượt nhát cắt vào khoảng trống giữa hai khối. Chiều cao trang
suy TỪ chiều rộng đo được (297/210), không viết cứng điểm ảnh.

Ba cái bẫy đi kèm, đều đã sập một lần:

* **Bỏ `height` làm tờ giấy co bằng nội dung** — tài liệu ngắn ra 1588×650 thay
  vì 1588×2246, và "độ đầy" thành 100% ở mọi trang vì mẫu số co theo tử số.
  `to_a4()` đệm bằng màu nền đo ở hàng dưới cùng.
* **`rects["fields"]` không mang toạ độ** — chọn theo Y thì mọi trường rơi về tờ
  một. Nối qua chỉ số `field` của các run.
* **Prompt dạy hai điều trái nhau** — mục mới bảo viết một dải, hai đoạn cũ vẫn
  dạy "mở `.sheet` thứ hai khi tờ đầu đầy 80%" và "in dòng Trang N/M". Sửa mục
  mới thì phải đi tìm mọi đoạn cũ nói ngược.

Chỉ số cần nhìn ở lượt sau: dòng `xin N -> cắt ra M tờ` trong log vẽ. Trang nào
cũng qua cổng dù ngắn hay dài, nên đó là cách **duy nhất** thấy model viết
thiếu.

## 17. Hộp vùng phải cắt về vệt mực

Hộp vùng lấy theo khung `<div>` model khai, mà một `<div>` thường rộng hết cột
dù chữ trong nó chỉ chiếm một mẩu. Bề ngang thừa, đo trên `pilot8`:

| Nhãn | Trước | Sau `tighten()` | Engine |
|---|---|---|---|
| `Section-Header` | 69% | **3%** | 4% |
| `Page-Footer` | 59% | **3%** | 12% |
| `Caption` | 58% | **2%** | 62% |
| `Formula` | 35% | **2%** | 7% |
| `Footnote` | 33% | **1%** | 27% |
| `Bibliography` | 31% | **1%** | 43% |

Tứ phân vị trên toàn bộ: 17% → **3%**.

**Mực phủ cắt theo KIND, không theo hình học.** `data-region="Watermark"` đặt
trên `.wm{position:absolute;inset:0}` phủ đúng cả tờ, nên "chữ nằm trong nó" là
MỌI chữ trên trang — cắt hình học chỉ co từ cả-tờ xuống gần-cả-tờ. Sau khi cắt
theo kind: `[377,844,1211,1401]` so với mực thật `[383,850,1205,1395]`; trước là
`[0,0,1588,2246]`.

## 18. Ba lần tôi kết luận sai vì phép đo hỏng

Ghi lại vì cả ba đều tốn thời gian và đều tránh được:

1. **`rglob("records/*.json")` quét cả `sample/records/`** — bản sao cũ `derive`
   tạo ra. Đo "sau khi sửa" trên bản cũ nên thấy y hệt "trước khi sửa", và suýt
   kết luận bản vá không chạy.
2. **`pytest` báo `Interrupted: 1 error during collection`** — nó chết lúc thu
   thập vì một tệp test không import được, **chưa chạy một test nào**. Con số "1
   ca đỏ" của lượt gốc là vô nghĩa, và tôi đã dùng nó để kết luận "26 ca đỏ do
   mã của tôi". Luôn đọc dòng tổng kết, không chỉ đếm `FAILED`.
3. **So cây làm việc với cây gốc mà quên hai biến** — cây gốc có đủ `data/` và
   đủ tệp test. Phải chép mã sang cây gốc (giữ dữ liệu) và xoá cùng những tệp
   test, mới là phép so cùng điều kiện. Kết quả đúng: gốc 25, sau khi sửa 25.

Quy tắc rút ra: **một phép đo không nói được nó đã đo bao nhiêu mẫu là một phép
đo chưa dùng được.**
