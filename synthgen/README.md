# 🧬 `synthgen/` — bộ sinh chứng từ soạn dáng mới

> Một tờ giấy chưa từng có trong kho thì trông thế nào? Gói này dựng dáng từ
> một **ngữ pháp bố cục** chứ không đọc `rulebase/layouts/`, và khử trùng
> bằng **chữ ký dáng** chứ không bằng số lượng file có sẵn.

```bash
python synthgen/run.py    -o data/09-09-26-synthetics-document -n 10000 --workers 11
python synthgen/derive.py    data/09-09-26-synthetics-document --sample 200
python synthgen/check.py     data/09-09-26-synthetics-document --sample 800
```

Bộ **5000 chứng từ nhiều trang**, mỗi chứng từ 2–10 tờ:

```bash
python synthgen/run.py -o data/synth5k -n 5000 --pages 2-10 --augment fast --workers 14
python synthgen/run.py -o data/synth5k -n 5000 --pages 2-10 --dry-run   # chỉ in phân bố
```

`-n` là số **chứng từ**, không phải số ảnh: ở khoảng 2–10 tờ thì 5000 chứng từ
ra khoảng mười tám nghìn ảnh. Nghỉ giữa chừng thì chạy lại đúng lệnh ấy — mỗi
shard để lại một tệp `DONE`.

---

## 0.1 Khối CHẢY: vì sao "nhiều trang" không còn nghĩa là "có bảng"

Trước `--pages`, phép cắt trang của `paginate.py` chỉ cắt được theo **dòng
bảng**. Hệ quả không ai viết ra nhưng đo được: **mọi** tài liệu nhiều trang
trong bộ đều có một cái bảng, dù xác suất bảng có hạ xuống bao nhiêu — "nhiều
trang" và "có bảng" là cùng một thứ với bất kỳ mô hình nào học trên bộ ấy.

`design.FLOW_BLOCKS` đặt tên cho khái niệm bị thiếu: **khối chảy** là khối
quyết định tài liệu dài bao nhiêu, và là khối bị cắt ra giữa các tờ. Ba khối
chảy được, và thêm khối thứ tư là thêm một dòng ở `FLOW_BLOCKS` cộng một dòng
ở `markup.FLOW_BUILDERS` — không phải sửa `paginate.py`, `draw.py`:

| khối chảy | nhãn vùng | mục là gì | sức chứa đọc từ |
| :--- | :--- | :--- | :--- |
| `table` | *(Table)* | một dòng hàng | `rows` của phôi |
| `clauses` | `List-Group` | một điều khoản đánh số | `rulebase/corpus/vi/clauses_*.txt` |
| `questions` | `Form` | một câu hỏi của tờ khai | `content.QUESTION_THEMES` |

Khối nào thắng thì **bốc theo trọng số**, không xếp thứ tự ưu tiên — xem
`rulebase/synthgen/_blocks.yaml::flow_weight` và lý do viết ngay trong file
ấy. Bản đầu xếp `clauses` trước mọi khối không-bảng, và đo ra `List-Group`
có mặt trên 82% số tờ: cùng một cái lệch, chỉ đổi tên nhãn.

Đo trước và sau (1500 tờ, đếm `data-region` trên chính markup):

| | trước | sau |
| :--- | ---: | ---: |
| tờ có bảng | 77% | 39% |
| `List-Group` | — | 44% |
| `Form` | 2% | 21% |
| `Table-Of-Contents` | 6% | 10% |
| `Figure` + `Caption` | 5% | 11% |

Hai tầng quyết cân bằng, và tầng dưới mạnh hơn tầng trên: `chance:` chỉ đổi
được **trong giới hạn** của `allow:`. Một khối chỉ 8% số phôi cho phép thì
`chance: 1.0` vẫn ra 8% — đó là lý do chỉnh `chance` mãi mà `Form` không lên
được.

## 0.2 Trang GIỮA: vì sao cân cả bộ vẫn chưa đủ

Bộ có thể cân theo nhãn mà từng tài liệu vẫn đơn điệu, và hai câu hỏi ấy phải
đo riêng. Bản đầu của khối chảy dồn mọi khối đầu vào tờ một và mọi khối đuôi
vào tờ cuối, nên một tài liệu sáu tờ ra:

```
tờ 1: tiêu đề + điều khoản    tờ 2..5: điều khoản    tờ 6: điều khoản + chữ ký
```

Bốn tờ giữa chỉ có đúng một nhãn vùng chạy từ mép trên xuống mép dưới —
**100% tờ giữa chỉ có khối chảy**. Ba thay đổi, đo trên 1219 tờ giữa:

| | trước | sau |
| :--- | ---: | ---: |
| tờ giữa CHỈ có khối chảy | 100% | 24% |
| tờ giữa dùng 2–3 cột | 0% | 23% |
| tờ giữa có bảng | 0% | 26% |
| tờ giữa có khối trường | 0% | 26% |

1. **`markup._page_plan`** rải khối theo trang thay vì dồn hai đầu. Neo thì
   không rải — tiêu đề đơn vị ở tờ đầu, chữ ký ở tờ cuối, vì đó là chỗ của
   chúng trên giấy thật; `design.BOUND_GROUPS` giữ bảng và dòng tổng của nó
   không rơi hai tờ.
2. **Hai cột xét theo TỜ, không theo tài liệu.** Tờ mang bảng thì một cột
   (bảy cột bảng nhét vào cột 8cm thì chữ vỡ ra từng ký tự); tờ mang điều
   khoản hoặc câu hỏi thì `_chunks` cắt khối chảy thành mấy khối vừa một
   cột, mỗi khối vẫn là một vùng `List-Group` trọn vẹn.
3. **`multipage_boost`** làm giàu tài liệu dài — theo TỪNG KHỐI, vì thứ làm
   một tờ hết đơn điệu là khối *chiếm chỗ*. Ghi chú dấu sao và dòng "bằng
   chữ" để ở 1.0: nhân chúng lên là trả giá mà không mua được gì (đo ở hệ số
   2.4 đều tay: `Footnote` 82% số tờ, `Figure` mới 22%).

---

## 0. Ranh giới: cái gì dùng lại, cái gì soạn mới

**Dáng thì mới hoàn toàn. Nhãn thì dùng lại nguyên si.** Ba thứ gói này lấy
của kho đều là phép ĐO hoặc từ vựng, không thứ nào là bố cục:

| Dùng lại | Ở đâu | Vì sao |
| :--- | :--- | :--- |
| hợp đồng nhãn | `generators/html/page.py::CELL_RECTS_JS` | hộp ĐO trong chính trình duyệt vừa dàn trang, không phải tính tay |
| từ vựng nhãn | `pipeline/record.py` | `data-kind` → 11 nhãn `blocks[]` và 19 nhãn `docsynth.annotations.v1` |
| kho chữ tiếng Việt | `rulebase/corpus/vi/*.txt`, `rulebase/text.py` | tên hàng, tên người, tên phố, và tiền bằng chữ |

Đó là ba thứ quyết định "nhãn có đúng không". Còn "tờ giấy trông thế nào" thì
`design.py` tự dựng.

---

## 1. Các file

| File | Việc |
| :--- | :--- |
| `design.py` | ngữ pháp bố cục: khổ giấy, lề, mực, phông, kiểu tiêu đề, **kiểu bảng**, thứ tự khối, 32 phôi chứng từ. `signature()` gói mọi quyết định nhìn thấy được thành một tuple |
| `content.py` | tờ giấy ấy NÓI gì: tên đơn vị, số hiệu, ngày, từng dòng hàng, và **mọi con số tiền** |
| `corpus.py` | đọc `rulebase/corpus/vi/`, cache một lần cho mỗi tiến trình |
| `markup.py` | dựng HTML + CSS. Mọi chữ in ra nằm trong một `<span data-kind>` |
| `paginate.py` | **luật 80%**: cắt N tờ chỉ khi cả N tờ đều lấp ≥ 80%; không đủ thì in ít tờ hơn |
| `draw.py` | mở Chromium, đo, chụp, dựng bản ghi, ghi ra đĩa |
| `overlay.py` | vẽ hộp nhãn đè lên chính trang giấy nó đọc được: vùng bố cục, hộp từ, và cặp KIE có mũi tên nối |
| `plain.py` | lấy HTML **trần** của một tờ: giữ `colspan`/`rowspan`, bỏ sạch CSS |
| `kie_full.py` | KIE cho **mọi** nhãn in ra, không riêng mấy cặp "nhãn: giá trị" |
| `kie_schema.py` | cùng KIE ấy viết thành **JSON Schema** + một instance khớp nó |
| `descriptions.py` | mô tả tiếng Anh cho từng trường KIE, sinh từ chính nhãn `design.py` in ra |
| `phrasing.py` | **nhiều cách nói** cho mỗi câu mô tả ấy, hai thứ tiếng; chọn theo `crc32(seed\|trường\|câu gốc)` |
| `run.py` | chia shard, chạy song song, resume được, viết `manifest.jsonl` + `report.json` |
| `check.py` | đọc ngược bộ đã sinh và chấm: bảy điều, ra mã 0 khi sạch |
| `derive.py` | **bước sau lượt chạy**: dựng `markdown/`, `visualize_kie/`, `sample/` |
| `augment.py` | **bước sau lượt chạy**: làm cũ ảnh qua `degradation/` của pipeline chính, và di chuyển MỌI cái hộp theo |

---

## 2. Lượt chạy để lại những gì

```
data/09-09-26-synthetics-document/
  images/        <loại>/<stem>.jpg     trang giấy
  html/          <loại>/<stem>.html    chính markup đã vẽ ra nó
  records/       <loại>/<stem>.json    bản ghi đầy đủ MỘT TỜ, `kie` kèm mô tả
  json/          <loại>/<tài liệu>.json MỘT file MỘT TÀI LIỆU: `loai_tai_lieu`
                                       + `page_1`/`page_2`/… — định dạng để
                                       huấn luyện
  layout_boxes/  <loại>/<stem>.jpg     vùng bố cục vẽ đè lên trang
  word_boxes/    <loại>/<stem>.jpg     hộp từ vẽ đè lên trang
  kie_descriptions.json                bảng mô tả trường của cả lượt
  manifest.jsonl                       một dòng cho mỗi TRANG
  report.json                          phủ, phân bố tỉ lệ lấp, thời gian
```

Hai thư mục json, và hai vai khác nhau. `records/` là NGUỒN: mọi hộp từ, mọi
vùng, mọi cặp KIE của một TỜ — `check`, `overlay`, `augment`, `derive` đọc nó.
`json/` là thứ bên huấn luyện đọc: một tài liệu một file, bốn khoá mỗi trường.
Chúng từng cùng tên, và đó là lý do có người mở `json/` ra rồi thấy ba file cho
một chứng từ ba tờ.

`layout_boxes/` và `word_boxes/` chỉ còn ảnh. Bản `.json` của chúng là bản chép
nguyên văn một lát cắt của bản ghi — đo trên bộ 20 099 trang: 5,4 GB + 8,7 GB
không mang một bit nào bản ghi chưa có. `overlay.slice_for` dựng lại cả hai
trong một dòng.

`synthgen/derive.py` dựng thêm ba thứ từ bộ ĐÃ XONG (bước sau, không phải một
bước của bộ sinh):

```
  markdown/      <loại>/<stem>.html    HTML TRẦN: đúng cấu trúc, không CSS
  visualize_kie/ <loại>/<stem>.jpg     từng cặp khoá → giá trị, có mũi tên nối
  sample/                              ~200 trang đã lọc, gom vào một thư mục
```

Vì sao là bước sau: lượt chạy mười nghìn chứng từ nạp code vào RAM lúc khởi
động, nên sửa `draw.py` giữa chừng thì phần đã vẽ không có, phần vẽ sau lại
có — một bộ nửa nọ nửa kia mà không gì báo. Đọc lại bộ đã xong thì cả hai mươi
nghìn trang đi qua đúng một đường.

**`markdown/`** giữ `colspan`/`rowspan` **và `bbox`**, bỏ mọi thứ còn lại —
không `class`, không `style`, không `<colgroup>`. Một bảng tiêu đề ba tầng ra
đúng thế này:

```html
<thead>
<tr><th rowspan="3" bbox="93,682,141,700">Stt</th>
    <th colspan="4" bbox="402,682,655,700">Giá trị và thuế</th>
    <th rowspan="3" bbox="1180,682,1301,700">Tổng</th></tr>
<tr><th colspan="2" bbox="410,710,520,728">Khoản mục</th>
    <th colspan="2" bbox="700,710,880,728">Số lượng và đơn giá</th></tr>
<tr><th bbox="402,738,470,756">Diễn giải</th>…</tr>
</thead>
```

`bbox` là `x1,y1,x2,y2` **pixel trên chính tấm ảnh của trang ấy** — cùng hệ
toạ độ với `word_boxes/` và `layout_boxes/`, nên ba file nói về cùng một tấm
ảnh. Hộp gắn vào từng đoạn chữ (`<span data-kind>` của markup, đổi thành
`<div bbox=…>`), và mỗi ô bảng mang **hợp** các hộp bên trong nó.

Hai điều về loại hộp này: đây là **hộp chữ**, ôm sát mực, không phải hình chữ
nhật của ô — nên **ô trống không có hộp**. Hình chữ nhật ô thật thì
`page.py::CELL_REGIONS_JS` có đo lúc vẽ, nhưng `pipeline/record.py` chỉ dùng
nó để tính khung ngoài của vùng `Table` rồi bỏ, nên nó không có trong bản ghi.

Hộp gắn được vì **`<span data-kind>` khớp một-một với `entity_annotations`,
cùng thứ tự** — đo trên 60 tài liệu: 60/60. Span TRANG TRÍ (vạch mã vạch, ô
logo) không có `data-kind` và không sinh thực thể, nên nó không được lấy hộp:
cho nó lấy là đẩy lệch mọi hộp phía sau đúng một chỗ, mà ảnh và HTML vẫn
trông đúng nên không gì báo. Bắt được bằng cách đòi tập hộp trong `markdown/`
phủ đúng tập hộp trong bản ghi — 300/300 trang.

Nó **không** dùng `record['html']`: bộ chuyển của `pipeline/record.py` gom khối
theo dòng nhìn thấy rồi mới gắn thẻ, nên một bảng ba mươi dòng ra ba mươi thẻ
`<table>` mỗi thẻ một dòng chữ, không ô nào, không `colspan` nào. `plain.py`
đọc thẳng markup đã vẽ nên cấu trúc còn nguyên như trình duyệt đã thấy.

**`sample/`** bốc theo VÒNG chứ không ngẫu nhiên: mỗi vòng một trang cho mỗi
loại chứng từ, ưu tiên trang mang kiểu bảng chưa ai mang. Bốc ngẫu nhiên hai
trăm trang từ hai mươi nghìn ra một tập giống cả bộ về thống kê và bỏ sót đúng
những thứ hiếm — mà cái hiếm mới là cái người mở thư mục mẫu muốn nhìn.

`<loại>` là id phôi chứng từ (`hoa_don_gtgt`, `bang_luong`, …). Chia ngăn vì
hai mươi nghìn file phẳng trong một thư mục là thứ `ls` treo, còn câu hỏi hay
hỏi nhất — "cho tôi xem hết mấy tờ hoá đơn tiền điện" — thì trả lời được bằng
một đường dẫn thay vì một vòng lặp.

Bản ghi được chép **bên cạnh từng trang**, không phải chỉ trang một: người cầm
`..._p2.jpg` phải tìm thấy `records/.../..._p2.json`, chứ không phải một 404.

---

## 3. Ba lời hứa, và cả ba đều được kiểm

* **không trùng dáng** — `design.signature()` là 36 quyết định nhìn thấy được
  của một tờ giấy, và tập chữ ký được lọc **trước khi mở trình duyệt**
  (`run.unique_seeds`): khử trùng sau khi vẽ thì cái giá là một trang đã render.
* **không trùng nội dung** — `Doc.content_signature()` băm tên đơn vị, số hiệu,
  ngày, tổng tiền và từng dòng hàng.
* **trang bị cắt lấp ít nhất 80%** — `paginate.py` ĐO trong trình duyệt rồi mới
  chốt, và hạ số tờ xuống khi không tờ nào đầy tới ngưỡng.

---

## 4. Luật cắt trang, đúng một câu

> **Một chứng từ chỉ được cắt làm N tờ khi CẢ N tờ đều lấp ít nhất
> `MIN_FILL` (80%); không đủ thì in ít tờ hơn.**

Hệ quả trực tiếp là "nếu height không quá dài thì đừng cắt". Sức chứa tính từ
phép đo trong chính trình duyệt vừa dàn trang — chiều cao một dòng hàng (lấy
**trung vị**, không phải trung bình), chiều cao khối đầu, khối cuối, tiêu đề
cột — chứ không từ một con số viết sẵn trong file bố cục.

Tờ giấy **duy nhất** được thả lỏng hơn: nó không có tờ nào sau để dồn chữ
sang, nên chỗ trống ở đó lấp bằng **cỡ chữ** (`boost`, trong khoảng 0.68–1.60)
chứ không bằng dòng hàng. Thu hết cỡ mà vẫn tràn thì **đổi khổ giấy**, không
thu tiếp — đúng cái nhà in thật làm.

---

## 5. Bảng phức: bảy trục dáng bảng

Mô hình đọc bảng một tầng không đọc được bảng kê nhà nước. Nên bảng ở đây
không chỉ là một lưới:

| Trục | Giá trị | Dựng bằng |
| :--- | :--- | :--- |
| `head_tiers` | 1 / 2 / 3 tầng tiêu đề | `colspan` cho nhóm, `rowspan` cho cột đứng riêng |
| `col_numbers` | có / không hàng "(1) (2) (3)" | một `<tr>` trong `<thead>`, lặp lại ở đầu mỗi tờ |
| `row_groups` | `khong` / `phan_muc` / `cot_gom` | dòng tiêu đề nhóm chạy hết chiều ngang, hoặc một ô `rowspan` bên trái |
| dòng cộng nhóm | tự động khi có cột thành tiền | in **ngay sau** dòng cuối của nhóm, cộng bằng SỐ chứ không đọc ngược chuỗi |
| `nested_detail` | có / không | một `<table>` con thật lồng trong ô mô tả |
| `table_frame` | 7 kiểu nét kẻ | khung đủ, chỉ kẻ ngang, không kẻ, viền ngoài, … |
| `zebra`, `compact_rows` | có / không | sọc dòng, độ nén dòng |

Luật xếp tiêu đề nhiều tầng, đúng một câu: **mỗi cột thuộc về ô hẹp nhất phủ
nó, và ô nào không có tầng dưới thì `rowspan` xuống tới đáy `<thead>`.**

Hộp của ô gộp **không phải khai thêm gì**: `page.py::CELL_REGIONS_JS` đọc
thẳng `td.colSpan` / `td.rowSpan` của trình duyệt, nên một ô phủ bốn cột có
đúng một hộp phủ bốn cột.

`data-row` của tiêu đề đếm âm theo tầng (0, −1, −2, hàng số cột là −3) còn
dòng hàng đếm từ 1, nên hai dãy không bao giờ đụng nhau.

---

## 6. Ảnh vẽ hộp

Một con số ("98,7% hộp nằm trên mực") trả lời được cho một cửa kiểm tự động
nhưng không trả lời được cho người. `overlay.py` vẽ ra cái ấy:

* `layout_boxes/<loại>/<stem>.jpg` — khung dày, tô mờ, **tên lớp** ở góc
  (`Table`, `Page-Header`, `Title`, `Form`, …);
* `word_boxes/<loại>/<stem>.jpg` — khung mảnh cho từng từ, **màu theo vai trò
  KIE**: đỏ = khoá, xanh lá = giá trị, cam = không thuộc cặp nào.

Chỉ dùng ẢNH và BẢN GHI, đúng thứ người dùng bộ dữ liệu có trong tay — một ảnh
kiểm chứng dùng chung trạng thái với thứ nó kiểm là một ảnh tự chứng minh mình
đúng.

`word_boxes/*.json` mang luôn `kie_field`, `kie_description`, `kie_role` trên
từng hộp: đó là file một trình huấn luyện đọc **một mình**, không mở bản ghi
đầy đủ bên cạnh.

---

## 6b. KIE phủ mọi nhãn

`pipeline/kie.py` ghép một trường với cái nhãn in ngay trước nó, và làm việc ấy
tốt — nhưng nó chỉ thấy được chỗ **có nhãn in kèm**. Đo trên 400 trang lấy ngẫu
nhiên khắp 32 loại: **91 396 đoạn chữ có hộp, chỉ 10 220 (11,2%) nằm trong một
cặp KIE**. Toàn bộ ô bảng, tiêu đề cột, ghi chú, tiêu đề tài liệu, con dấu,
dòng cộng nhóm — có hộp, có nhãn lớp, mà không có mặt trong `kie`.

`kie_full.py` lấp nốt, ba loại cặp:

| Loại | Khoá | Giá trị |
| :--- | :--- | :--- |
| **ô bảng** | tiêu đề cột, kèm `column_path` cho bảng nhiều tầng | ô |
| **cặp mới** | `total.group`, `checks.question` | `total.group_amount`, `checks.answer` |
| **không có nhãn in** | `key_bbox: null`, `key_source: implied` | tiêu đề, ghi chú, con dấu, tên đơn vị, tên nhóm dòng |

Sau khi lấp: **100%** — 250 file thử, không một nhãn nào ngoài KIE.

Lưới bảng dựng lại bằng **hình học** từ chính `entity_annotations` (ô cùng cột
thì cùng dải hoành độ, ô cùng dòng thì chồng nhau theo tung độ), rồi **đối
chiếu với `extracted.menu`** — bản ghi nội dung bộ sinh đã chốt trước khi vẽ.
Khớp 600/600 tài liệu thử. Nhờ thế không phải vẽ lại hai mươi nghìn trang.

`column_path` là thứ bảng một tầng không có: khoá của một ô không phải "Đơn
giá" mà là `["Phần II - Chi tiết thanh toán", "Số lượng và đơn giá", "Đơn
giá"]` — vì cái tên lá đứng một mình không nói nó là đơn giá của cái gì.

Chạy lại `derive.py` **không nhân đôi cặp**: nó chỉ lấy cặp gốc (`source:
label`) làm nền, phần tự thêm bị bỏ đi rồi dựng lại.

---

## 6c. KIE nói bằng hai cách

`kie.pairs` là danh sách cặp **có hộp** — đúng thứ cần để chấm định vị. Nhưng
một mô hình sinh JSON có ràng buộc (vLLM/xgrammar, structured outputs) không
ăn danh sách cặp: nó ăn một **schema**, rồi trả về một **instance**. Nên cùng
một KIE được viết thành cả hai, không cái nào thay cái nào:

```
records/<loại>/<stem>.json
  └─ kie
     ├─ pairs         cặp CÓ HỘP, mọi nhãn (§6b)
     ├─ coverage      thống kê phủ
     ├─ schema        JSON Schema của CẢ TÀI LIỆU
     ├─ value         giá trị khớp `schema`
     ├─ page_schema   JSON Schema chỉ của TỜ NÀY
     └─ page_value    giá trị khớp `page_schema`

kie_schemas/<loại>.json   schema gộp cho cả loại chứng từ (32 file)
```

**Vì sao cần cả bản theo TỜ.** Bản ghi được chép bên cạnh từng tờ, nên một
hoá đơn ba tờ có ba file json giống hệt nhau. Bản tả-cả-tài-liệu nằm trong
file của tờ một sẽ kể 32 dòng hàng trong khi tờ ấy chỉ in 1 — huấn luyện một
mô hình nhìn MỘT ảnh bằng cặp ấy là dạy nó bịa ra thứ không có trong ảnh.
Đo trên `hoa_don_gtgt_00014`: cả tài liệu 32 dòng, ba tờ lần lượt 1 / 17 / 14,
cộng lại đúng 32.

Ba quyết định khi đổi:

* **Bảng thành một mảng, không thành trăm trường.** Hoá đơn bốn mươi dòng có
  hơn hai trăm ô; đổ thành `qty_r1`, `qty_r2`, … là schema hai trăm trường mà
  mỗi tờ một khác. `line_items: array of object` thì schema chỉ phụ thuộc BỘ
  CỘT, số dòng là chuyện của dữ liệu.
* **Kiểu suy từ NGHĨA, không từ hình dạng chuỗi.** `"0909954657"` trông như số
  nhưng là số điện thoại; `"4.551.901.200 đ"` trông như chữ nhưng là tiền. Nên
  `number` chỉ dành cho `kind` vốn là số, và chuỗi nào không đọc ra số vẫn tụt
  về `string` (`"Không chịu thuế"` là giá trị hợp lệ của dòng thuế).
* **Bỏ phần khung của bảng.** `column_heading`, `column_number`, `row_group` là
  chữ in để NGƯỜI đọc bảng, không phải trường để trích. Chúng vẫn nằm đủ trong
  `pairs` kèm hộp.

Kiểm: 400 file ngẫu nhiên, **400/400 có `value` khớp `schema`**, và **4 746
dòng hàng thoả `số lượng × đơn giá = thành tiền`** sau khi đổi sang `number`,
0 sai — phép đọc số không lệch chỗ nào.

`required` trong schema một-tờ bằng cả danh sách trường (schema tả đúng tờ ấy
nên mọi trường đều có mặt). Chỗ `required` phân biệt được trường luôn có với
trường thỉnh thoảng là `kie_schemas/<loại>.json`: bắt buộc khi có mặt trên
≥ 90% số tờ của loại ấy.

---

## 7. Bộ kiểm

```bash
python synthgen/check.py <thư mục> [--sample N] [--show 4]
```

Chín điều, mỗi điều là một cách tập dữ liệu có thể sai mà nhìn ảnh thì không
thấy: đủ file · kích thước ảnh khớp bản ghi · hộp nằm trong trang · hộp có chữ
· chỉ số trỏ đúng · **số học tiền khớp** (thành tiền = số lượng × đơn giá,
cộng tiền hàng = tổng cột thành tiền) · **luật 80%** · **một file không nói hai
câu khác nhau về cùng một trường** (`kie.pairs` so với `entity_annotations`) ·
**mô tả cột trong schema là mô tả của cặp**, không phải câu gốc đọc lại từ
`design.COLUMNS`.

Hai điều cuối được thêm sau khi chúng xảy ra thật. Bảng cách nói
(`phrasing.py`) làm cho `kie.pairs` mỗi tài liệu một giọng, nhưng
`kie_schema.build` vẫn đọc câu gốc từ `design.COLUMNS`, nên
`line_items.qty` y hệt nhau trên cả 20 099 trang — và `entity_annotations`,
do `pipeline/kie.py` ghi lúc vẽ, thì còn lệch hẳn với `kie.pairs` nằm cạnh nó.
Không gì báo; người dùng mở hai file ra so mới thấy. Trên 300 trang chưa vá,
hai phép kiểm này báo 2042 ca.

Đường dẫn lấy từ chính `manifest.jsonl` chứ không ghép lại từ `stem`: một bộ
kiểm tự ghép đường dẫn là một bộ kiểm sẽ có lúc kiểm nhầm chỗ mà vẫn báo sạch.

---

## 7b. Làm cũ: nối vào `degradation/` của pipeline chính

```bash
python synthgen/augment.py data/09-09-26-synthetics-document          # -> ...-aug/
python synthgen/augment.py <bộ> --variants 2 --workers 8              # nhân đôi bộ
python synthgen/augment.py <bộ> --warp all --force photocopy --limit 40
```

Bộ sinh vẽ giấy **sạch**. Pipeline chính thì không — nó bốc một giá trị
`augmentation` cho mỗi trang rồi cho trang đi qua `degradation/`, nên ảnh của
nó là ảnh chụp lại, photocopy lại, gấp lại. `augment.py` là chỗ hai nửa gặp
nhau: **đúng cái hàm `degradation.pipeline.apply_recipe` mà mọi bộ vẽ của kho
này gọi**, cộng `degradation.warp.warp_regions` cho phần hình học.

Là bước **sau**, không phải một cờ trong `draw.py`: làm cũ là phép biến đổi
trên ẢNH, không cần biết trang được dàn ra sao, nên bắt Chromium vẽ lại 20 099
trang để lấy nó là trả một cái giá không mua gì. Và bộ sạch còn nguyên — **từ
sạch luôn dựng được bẩn, từ bẩn thì không bao giờ quay lại sạch.**

Ba điều phải đúng:

1. **Chuỗi làm cũ không được đổi kích thước ảnh.** Một phép resize lẻn vào sẽ
   xê dịch mọi cái hộp mà ảnh thì trông vẫn thế. So hình dạng trước/sau, y như
   `generators/html/render.py`.
2. **Cong giấy thì hộp phải đi theo, bằng CÙNG MỘT trường dịch chuyển.** Bảy
   danh sách (`word_annotations`, `layout_annotations`, `entity_annotations`,
   `blocks`, dòng của thực thể, hộp khoá và hộp giá trị của cặp KIE) vào một
   lần gọi `warp_regions`. Gọi bảy lần là bảy tờ giấy khác nhau cho một trang.
   Ba hình dạng hộp khác nhau trong cùng một bản ghi — `polygon` vòng kín,
   `bbox` danh sách, `bbox` dict — và mỗi loại ghi lại theo hình dạng của nó.
3. **Một tài liệu, một cái máy.** Recipe bốc theo TÀI LIỆU, hạt giống bốc theo
   TỜ: ba tờ của một hoá đơn cũ theo cùng một *kiểu* mà không cùng một *vết*.
   Tờ hai mang đúng nếp gấp của tờ một là dấu hiệu lộ cả bộ chỉ bằng một cái
   nhìn.

`--warp fast` (mặc định) bỏ những giá trị mà warp của nó chạy qua Blender —
vài giây tới hơn một phút một trang, tức là 6–36 giờ trên bộ này. Engine đọc
từ chính `degradation/warp.py`, không liệt kê tên, nên thêm một engine là file
này tự biết. Giá trị nào bị bỏ đều in ra kèm lý do.

`html/`, `markdown/`, `kie_schemas/` nối bằng **symlink**: chúng là chữ, làm
cũ không đụng tới, và chép 40 000 file để có hai bản của cùng một chữ là phí.

### Hoặc làm cũ ngay lúc vẽ

```bash
python synthgen/run.py -o <bộ> -n 10000 --augment fast
```

Cho lượt chạy **mới**: `Studio` gọi thẳng `augment.age()` trên những danh sách
hộp nó vừa đo trong trình duyệt, ngay sau khi đo và ngay trước khi mã hoá JPEG.
Rẻ hơn hẳn — không phải đọc rồi ghi lại 39 GB — nhưng không giữ bản sạch, nên
hai đường tồn tại song song chứ không thay nhau. **Một hàm làm việc cho cả
hai**: hai bản của cùng một phép làm cũ là hai phép làm cũ tình cờ trùng tên.

Mặc định là `off`. Bộ nào cũng có `settings.augmentation` ghi lại giá trị,
hạt giống, chuỗi model và tên warp — bộ dữ liệu nào không nói được ảnh của nó
đã bị làm gì thì không lọc được theo điều ấy.

---

## 8. Chạy lại, và chạy tiếp

Ngắt giữa chừng thì chạy **lại đúng lệnh ấy**: mỗi shard để lại một tệp trong
`.shards/`, và shard đã xong được bỏ qua.

Cờ đáng chỉnh:

| Cờ | Mặc định | Ý nghĩa |
| :--- | ---: | :--- |
| `-n` | 10000 | số **chứng từ**; một chứng từ nhiều tờ ra nhiều ảnh |
| `--workers` | CPU − 2 | mỗi tiến trình một trình duyệt. Trên máy 16 lõi, **11** là chỗ nhanh nhất mà chưa quá tải |
| `--shard` | 100 | số chứng từ mỗi tiến trình |
| `--scale` | 2.0 | device scale factor lúc chụp: vẽ to rồi thu nhỏ |
| `--indent` | 0 | thụt lề JSON nhãn; 0 = gọn. Bản ghi ra đĩa một lần cho mỗi **trang** |
| `--dry-run` | | chọn seed và in phân bố, không mở trình duyệt |

---

## 9. Một ghi chú về lịch sử file này

Ngày 2026-09-10, bảy file nguồn của gói này biến mất khỏi đĩa và chỉ còn
bytecode trong `__pycache__`. Chúng được dựng lại từ chính bytecode ấy và kiểm
bằng hai cách: mọi code object biên dịch ra khớp bytecode gốc, và dựng lại ba
chứng từ đầu của lượt chạy 10k cho ra **ảnh JPEG và JSON trùng từng byte**.

Hành vi thì đúng; **comment thì không phải chữ gốc** — bytecode giữ docstring
nhưng không giữ comment, nên comment trong `design.py`, `content.py`,
`corpus.py`, `paginate.py`, `check.py`, `descriptions.py`, `run.py` là bản
viết lại theo đúng cái code làm. Bytecode gốc còn ở
`~/synthgen_pyc_backup_2026-09-10/`.
