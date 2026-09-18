# Phân tích đề xuất: gộp LLM thành một luồng, bỏ rule-base chưa semantic

> Tài liệu review — không phải kế hoạch đã chốt. Viết theo yêu cầu: phân tích
> đề xuất của bạn đối chiếu với kiến trúc hiện tại, thống kê xem các vấn đề
> bạn nêu có thật trong code hay không (có trích dẫn), và đề xuất cách chỉnh.
> Không có thay đổi code nào được làm khi viết tài liệu này.

---

## 0. Tóm tắt điều hành

**Đề xuất của bạn có hai phần, và chúng đúng ở hai mức độ khác nhau:**

1. **"Bỏ rule-base chưa semantic dynamic (kind lạ → fallback kind gần nhất...)"**
   — **CÓ THẬT**, và nghiêm trọng hơn ví dụ bạn nêu. §4 dưới đây trích dẫn
   đúng đoạn code, kèm ba lỗi thật đã xảy ra vì đúng cơ chế này, đo bằng số
   trên dữ liệu đã commit.

2. **"Gộp thành một luồng: LLM sinh JSON layout+OCR → sinh HTML → capture ảnh
   → LLM khác chấm ngay sau từng ảnh → generate lại nếu chưa đạt"** — khả thi
   một phần, va vào ba bất biến kho này đang giữ (§3), và phần "chấm ngay +
   generate lại" phải trả một chi phí đã có số đo thật trong `docs/kiem-soat-
   llm.md`, không phải suy đoán: tỷ lệ đạt hiện tại của nhánh LLM-viết-cả-trang
   là **22%**, và trang giữ được tốn trung bình **333 giây** (bao gồm phần
   giây đổ vào những lần bị loại trước đó). Thêm một lượt LLM chấm + một vòng
   sinh lại theo đúng nghĩa "ngay sau từng ảnh, đồng bộ" nhân chi phí này lên,
   không cộng thêm.

**Đề xuất chỉnh (chi tiết ở §6):** giữ nguyên tinh thần "sinh data trước, vẽ
sau, kiểm rồi mới dùng", nhưng:
- gộp *hai lời gọi* (planner chọn thuộc tính + compose viết nội dung) thành
  *một* lời gọi JSON layout+content/trang — khả thi, đã có khung sẵn.
- việc "chấm rồi sinh lại" áp dụng ở đúng **một** điểm hẹp, có trần số lần thử,
  và **không** đổi ranh giới "hộp phải đến từ trình duyệt đã dàn trang" — LLM
  chấm bằng cách ĐỌC ảnh+bản ghi đã có (giống `agent/critic.py` đang làm),
  không tự vẽ lại hộp.
- **về đúng góp ý mới nhất của bạn (mapping → guide):** kho này **đã có sẵn**
  guide bạn muốn — `agent/prompts/regions.md`, 169 dòng lý luận ngữ nghĩa
  (region/role/ink), không phải bảng tra — và **đã nối vào 2 trong 4 điểm**
  sinh `kind`/nhãn (`augment_layout.py`, `compose_layout.py`). Chỗ THIẾU dây
  nối là `compose_page.py` (chỉ nhận danh sách tên trần) và toàn bộ
  `sheets/*.py` (rule-based, không khai `data-region` bao giờ, 100% dựa bảng
  tiền tố suy sau — đây mới là nguồn gốc thật của "missing/sai semantic").
  §4.4 và §6.3 viết lại chi tiết phát hiện này, đồng thời trả lời trực tiếp
  câu hỏi "vì sao synthgen không bao giờ missing box còn LLM thì có nguy cơ
  đó": vì `synthgen/markup.py` KHAI vùng ngay lúc viết khối, không suy sau —
  và điều này áp dụng được (không cần LLM, không tốn thêm chi phí) cho cả
  phần rule-based còn lại của kho.

---

## 1. Diễn giải lại đề xuất thành một luồng cụ thể

Để chắc chắn phân tích đúng ý, đây là cách tôi hiểu đề xuất thành các bước kỹ
thuật — nếu sai ở đâu, đó là chỗ cần bạn sửa lại trước khi tôi (hoặc ai) code:

```
Bước 1   LLM-A sinh MỘT file JSON: vừa mô tả BỐ CỤC (khối nào, cột nào, khổ
         giấy) vừa mô tả NỘI DUNG (giá trị từng trường) — một lời gọi, một trang.
Bước 2   Từ JSON đó, sinh ra HTML (không rõ: renderer thuần code đọc JSON rồi
         dựng HTML, hay LLM-A tự viết cả markup?).
Bước 3   Mở trình duyệt, chụp ảnh trang + ảnh layout boxes + ảnh KIE boxes.
Bước 4   LLM-B (khác LLM-A) đọc ba ảnh đó NGAY, chấm: layout ổn không, KIE ổn
         không, HTML/markup ổn không.
Bước 5   Chưa đạt → quay lại bước 1 (hoặc bước 2?), sinh lại — cho TỚI KHI đạt,
         hoặc tới một trần số lần thử.
Bước 6   Bỏ các rule tĩnh "chưa semantic dynamic" — ví dụ nêu: kind lạ thì
         đừng fallback về kind gần nhất theo bảng tra cứu tĩnh; nói rộng ra là
         bỏ những nơi hệ thống "đoán" bằng bảng tra cố định thay vì hiểu nghĩa.
```

Hai điểm mơ hồ cần bạn chốt trước khi bàn tiếp, vì câu trả lời đổi hẳn độ khó:

* **Bước 2, ai viết HTML?** Nếu LLM-A viết cả markup (giống nhánh thí nghiệm
  `agent/compose_page.py` đang có), thì layout không còn là *dữ liệu có cấu
  trúc* nữa — nó là *chữ tự do*, và mọi ràng buộc hình học (độ rộng cột, tràn
  trang, ô gộp) phải được LLM tự giữ đúng trong đầu, việc mà `docs/kiem-soat-
  llm.md` đã đo là nguồn lỗi số một (§3.1–3.3 trong đó). Nếu code đọc JSON rồi
  tự dựng HTML (giống mức 3 — `agent/compose_layout.py`), hình học vẫn do code
  giữ, LLM chỉ chọn cấu trúc — an toàn hơn nhiều, nhưng hẹp hơn: LLM không
  "vẽ" được thứ ngoài các khối/cột mà bộ dựng đã biết cách render.
* **"Generate lại" là lại từ bước nào, và với seed nào?** Nếu retry giữ đúng
  seed thì kết quả retry lần 2 phải khác lần 1 — nghĩa là **quyết định không
  còn là hàm thuần của seed nữa**, phá đúng bất biến §3.1 dưới. Nếu retry đổi
  seed thì dựng lại từ log cần ghi lại "seed nào cuối cùng được chọn" — làm
  được, nhưng phải thiết kế thêm (hiện chưa có cơ chế này ở đâu trong kho).

Phần còn lại của tài liệu giả định câu trả lời "an toàn hơn" cho cả hai (code
dựng HTML từ JSON có cấu trúc; retry đổi seed và ghi log), vì đó là hướng ít
phá vỡ nhất — nhưng đây là giả định, không phải sự thật đã chốt.

---

## 2. Đối chiếu từng bước với hiện trạng

| Bước đề xuất | Có sẵn cái gì gần giống? | Khoảng cách |
| :--- | :--- | :--- |
| 1· LLM sinh JSON layout+content 1 lần | **Không có ở dạng MỘT lời gọi.** `agent/planner.py` chọn ID thuộc tính (layout, variant, ornament...) từ danh mục có sẵn; `agent/compose.py` viết vài giá trị TEXT riêng (`store.name`, tên hàng) — **hai lời gọi, hai schema, hai thời điểm khác nhau** (planner chạy cho mọi trang; compose chỉ chạy khi `--content-llm`). Không lời gọi nào tự do "vẽ hình học mới" cho MỖI trang — hình học nằm trong catalog `rulebase/layouts/*.yaml`, chọn không phải sinh. |
| | Gần nhất về *tinh thần* "LLM tự soạn cấu trúc": `agent/compose_layout.py` (mức 3) — nhưng nó soạn **một layout dùng lại cho nhiều trang** (giống một khuôn in mới), không soạn *lại từ đầu cho từng ảnh*. |
| 2· Từ JSON → HTML | Renderer (`generators/html/render.py`) luôn đọc YAML/JSON đã có sẵn rồi dựng HTML bằng code thuần — **không có model nào ở bước này** trong pipeline chính. Nhánh `agent/compose_page.py` đi khác hẳn: model viết **thẳng ra HTML**, không qua JSON có cấu trúc. |
| 3· Chụp ảnh + layout boxes + kie boxes | Có sẵn, hoạt động tốt, không cần đổi: hộp luôn đo từ chính trình duyệt vừa dàn trang (`CELL_RECTS_JS`/`page.py`), không renderer nào đọc lại ảnh để suy hộp. |
| 4· LLM-B chấm NGAY sau từng ảnh | **Không có.** `agent/critic.py` đọc lại record + ảnh, nhưng chạy **sau khi cả dataset (hoặc một mẻ lớn) đã vẽ xong**, và mục đích là tính `penalty`/`ban` cho **lượt kế tiếp** (`agent/planner.py::Chooser`), không phải để bắt trang X phải vẽ lại. |
| 5· Chưa đạt thì generate lại | **Không có ở mức "một trang", cho toàn bộ trang.** Có ở mức **field**: `agent/compose.py`/`augment_content.py` loại một GIÁ TRỊ bị `corpus_rules` từ chối thì trường đó rơi về corpus — không vẽ lại cả trang. Có ở mức "trang qua cổng hay không" trong nhánh `compose_page.py`/`llm_page.py`, nhưng **trang trượt bị bỏ, không sinh lại** — `draw_llm.py` chỉ vẽ nó ra để NGƯỜI đọc lỗi, không tự động lặp. |
| 6· Bỏ rule tĩnh "chưa semantic" | Đây là **thay đổi ngược hướng** so với phần lớn kho: kho này liên tục SIẾT rule tĩnh chặt hơn (enum + constrained decoding) mỗi khi phát hiện model "xin" mà không "ép" gây lỗi (xem `docs/kiem-soat-llm.md` §3.2: đổi `kind` từ `string` tự do sang `enum` 80 giá trị chính là SIẾT rule tĩnh, và nó SỬA lỗi, không gây lỗi). §4–§5 dưới phân tích vì sao lời giải không phải "bỏ" mà là "gộp/siết" rule tĩnh này. |

---

## 3. Ba bất biến nền tảng đề xuất này chạm vào

Kho này dựng trên ba lời hứa, và cả ba đều có test giữ (không phải quy ước
bằng miệng). Đề xuất của bạn không **sai** khi chạm vào chúng — nhưng phải trả
lời rõ "chấp nhận bỏ lời hứa nào, hay giữ cả ba mà đổi cách hiện thực".

### 3.1 — "Cùng seed thì ra cùng byte"

`tools/baseline.py` vân tay từng ảnh; `tests/test_worklist.py` vẽ một trang
hai đường rồi so sha256; `pipeline/run.py` so `manifest.json` giữa 1 worker và
8 worker. Một vòng "generate lại tới khi LLM-B gật đầu" phá lời hứa này **theo
định nghĩa**, vì kết quả cuối của một seed giờ phụ thuộc vào việc LLM-B trả
lời gì ở lượt gọi thứ N — **không tái lập được kể cả khi biết seed**, trừ khi
số lần retry và câu trả lời của LLM-B ở mỗi lần cũng được ghi lại đầy đủ và
LLM-B cũng tái lập được (mà tài liệu `agent/client.py` đã nói "thường" là xa
nhất một model dám hứa).

→ Không phải không làm được, nhưng cần ĐỔI ĐỊNH NGHĨA "tái lập được": từ
*"cùng seed ra cùng byte"* sang *"cùng (seed, log quyết định LLM-A + LLM-B mọi
lượt thử) ra cùng byte"*. Log đó phải được viết ra và commit — đúng khuôn
`agent_plan.json`/`compose.jsonl` đã có, chỉ dài hơn (mỗi trang N lượt thử,
không phải 1).

### 3.2 — "Hộp đến từ engine đã dàn chữ, không renderer nào đọc lại đầu ra của
chính nó"

Đây là lời hứa quan trọng nhất với đúng câu hỏi bạn đang hỏi (đánh giá layout/
KIE). **Đề xuất của bạn KHÔNG phá lời hứa này**, miễn LLM-B chấm bằng cách đọc
ẢNH + BẢN GHI đã đo (giống `agent/critic.py`), không tự đo lại hộp bằng mắt
mình rồi ghi đè. Đây là điểm tôi đánh giá đề xuất của bạn **khả thi và hợp
lý** — nó chỉ đòi chuyển thời điểm chạy `critic`-như-hiện-có từ "cuối dataset"
sang "ngay sau mỗi ảnh", không đòi đổi CƠ CHẾ đo hộp.

Rủi ro thật duy nhất ở đây: nếu bước 2 (LLM viết thẳng HTML, không qua JSON có
cấu trúc) được chọn, thì hộp vẫn "đến từ engine" (Chromium vẫn đo) nhưng
**nhãn có thể sai một cách hệ thống** nếu model quên đóng span đúng cách —
đây chính là lỗi đã đo trong `synthgen/llm_page.py` docstring: một `<sub>`
lồng trong span làm hộp co từ 310px xuống 5px, và cổng phải kiểm bằng luật,
không phải bằng LLM-B nhìn ảnh (một hộp co lại 5px vẫn NẰM ĐÚNG VỊ TRÍ trên
ảnh, LLM-B nhìn ảnh sẽ không thấy gì sai).

### 3.3 — Ranh giới import: `agent/` không được `generators/`, `pipeline/`,
`rulebase/` import ngược

`tests/test_llm.py::test_the_render_path_cannot_reach_the_generator` (dòng 60)
khẳng định điều này bằng code, không phải bằng review. Một luồng "một lần gọi
LLM-A → LLM-B → generate lại" **vẫn giữ được** ranh giới này nếu toàn bộ vòng
lặp (sinh → chấm → sinh lại) nằm **ở bước quyết định**, trước khi renderer mở
lên — đúng cấu trúc hiện tại của `agent/planner.py::plan()`, chỉ là vòng lặp
bên trong một bước quyết định phức tạp hơn (nó giờ cũng phải MỞ TRÌNH DUYỆT để
chấm, một việc trước đây chỉ renderer làm). Đây là thay đổi kiến trúc thật:
**bước quyết định, lần đầu tiên, phải render** để LLM-B có ảnh mà chấm — nó
không còn là "quyết định rồi mới vẽ" theo nghĩa cũ, mà là "vẽ nhiều lần trong
lúc quyết định, chỉ commit lần cuối". Không phá ranh giới import (renderer vẫn
không biết `agent/` tồn tại), nhưng đổi hẳn chi phí và thời gian của pha quyết
định — hiện nó là network round-trip; giờ nó là network round-trip **cộng**
mở Chromium mỗi lần thử.

---

## 4. Thống kê: rule-base "chưa semantic dynamic" — CÓ THẬT, bằng chứng cụ thể

Bạn nêu một ví dụ ("kind không chuẩn → fallback về kind gần nhất"). Trong code
hiện tại, cơ chế đúng-loại-này tồn tại ở **hai nơi lớn**, và cả hai đã gây lỗi
thật, đo được, tự kho ghi lại trong comment và trong `docs/kiem-soat-llm.md`.

### 4.1 — `pipeline/record.py::LABELS` và `DOCSYNTH_LABEL_FOR_KIND`

Đây chính là cơ chế bạn mô tả, chỉ khác một chữ: không phải "kind gần nhất"
theo nghĩa fuzzy-match, mà là **"tiền tố dài nhất khớp, không khớp gì thì rơi
về nhãn mặc định cố định"**:

```python
# pipeline/record.py:512
def label_for(kind: str) -> str:
    best = ""
    for prefix in LABELS:
        if (kind == prefix or kind.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return LABELS[best] if best else DEFAULT_LABEL   # DEFAULT_LABEL = "Text"
```

Số đo cụ thể trên chính file này (2 898 dòng):

* **`LABELS`** (11-nhãn DocLayNet) và **`DOCSYNTH_LABEL_FOR_KIND`** (19-nhãn
  docsynth) là **hai bảng tra riêng**, cùng thuật toán, cùng ý tưởng, viết tay
  **độc lập** — tổng cộng khoảng **300 dòng khai tiền tố** giữa hai bảng
  (đếm `"..."` xuất hiện trong file: 303 lần, gồm cả comment).
* Cả hai đều rơi về đúng một nhãn cố định khi không khớp: `"Text"`.
* **Ba lỗi thật đã xảy ra chính vì cơ chế này**, ghi lại ngay trong comment
  của chính file và trong `docs/kiem-soat-llm.md`:
  1. **65 kind của họ chứng từ báo/tạp chí "đi không ai biết" cho tới khi có
     dataset đầu tiên vẽ đủ 42 layout** — mọi field của chúng lặng lẽ nhận
     nhãn `Text` cho tới khi một test (`test_every_kind_in_every_committed_
     dataset_is_mapped`, `tests/test_record.py:166`) mới bắt được, vì trước
     đó "chưa có dataset nào đi qua nhánh này để test chạy tới".
  2. **Ô dán ảnh trống (khung "ẢNH", "4x6") từng bị gán nhãn của đoạn văn bên
     dưới nó**, vì `photo.` không có trong bảng — comment ghi rõ: *"một khung
     rỗng có in chữ ẢNH ... KHÔNG có tấm ảnh nào — chỉ có chữ và một đường
     viền — nên gọi nó là ảnh là dạy một bộ nhận dạng rằng khung rỗng có chữ
     là ảnh"*.
  3. **Hai bảng từng NÓI KHÁC NHAU về cùng một `kind`** (`docs/kiem-soat-llm.
     md` §10): `DOCSYNTH_LABEL_FOR_KIND["sign."] = "Form"` (lý lẽ: "dòng chữ
     ký là ô người ký điền vào") còn `LABELS["sign."] = "Text"` cùng lúc —
     **một trong hai chắc chắn sai**, và không gì trong hệ thống tự phát hiện
     ra sự bất đồng đó; người phải đọc và so tay mới thấy.

Đây đúng là điều bạn gọi "sai về semantic": bảng tra không hiểu *"chữ ký đã in
sẵn là văn bản, không phải một biểu mẫu để điền"* — nó chỉ biết tiền tố chuỗi
`sign.` khớp gì trong bảng nào, và hai người viết hai bảng ra hai kết luận
khác nhau về đúng một khái niệm.

### 4.2 — `pipeline/kie.py::describe()` — bốn nguồn, hai nguồn cuối là "đoán
theo cấu trúc" không phải "hiểu nghĩa"

Đã tài liệu hoá ở file `docs/kien-thuc-llm-layout-kie.md` (phiên trước),
nhắc lại đúng phần liên quan: khi một trường KHÔNG có caption in kèm, mô tả
KIE rơi về `kind` (chính chuỗi `data-kind`, ví dụ trả về nguyên văn
`"total.grand"` làm mô tả), rồi nếu vẫn không có gì thì rơi về `layout_class`
(1 trong 19 nhãn) — **cả hai đều là chuỗi kỹ thuật nội bộ, không phải câu mô
tả có nghĩa**, dùng làm `description` trong JSON Schema đưa cho một mô hình
trích xuất đọc. Đây không hẳn "kind gần nhất" nhưng cùng họ: **rule tĩnh trả
về một chuỗi không hiểu ngữ nghĩa khi không có dữ liệu tốt hơn**.

### 4.3 — Lỗ hổng KIE đo được: 15 `kind` KHÔNG BAO GIỜ vào KIE, coverage
82,1% và lệch nặng theo vùng

`docs/kiem-soat-llm.md` §11 (đo trên `data/14-09-test2`, 141 bản ghi):
coverage ở mức vùng bố cục chỉ 82,1%, và cực lệch — `Page-Footer` **7,5%**,
`Bibliography` 20%, `Section-Header` 34,2%, `Caption` 37,5% — vì `pair_fields`
chỉ ghép được nhãn-giá trị đứng NGAY CẠNH nhau theo thứ tự vẽ, và 15 `kind`
(toàn bộ họ `survey.*`, `clause.*`, `caption.*`, cộng `footnote`, `formula`,
`legal.basis`, `masthead.motto`, `footer.page`, `watermark`) không khớp mẫu đó
nên **chưa từng** xuất hiện trong `kie.pairs` — dù chúng vẫn có hộp, có nhãn
lớp. Đây KHÔNG phải lỗi model — là quy tắc ghép cặp cứng ("nhãn liền kề giá
trị") chưa được mở rộng theo kịp các khối mới thêm vào `synthgen/`.

### 4.4 — Bạn đúng: đã có sẵn một "guide", không phải "mapping" — nhưng chỉ
được nối vào 2/4 điểm sinh `kind`. Đây là câu trả lời cho câu hỏi thứ hai
của bạn.

Bạn hỏi hai điều liên quan tới nhau, và câu trả lời cho cả hai nằm ở đúng một
phát hiện: *"chọn docsynth làm guide chứ không phải mapping"* và *"vì sao
synthgen không bao giờ missing box còn LLM thì không đạt được điều đó"*.

**Kho này đã tự xây guide đó rồi — `agent/prompts/regions.md`.** Đây không
phải một bảng tra `kind → label`; nó là 169 dòng lý luận NGỮ NGHĨA: ba trục
tách bạch (region = LÀ gì, role = LÀM gì, ink = in bằng gì), quy tắc *"hỏi nó
LÀM GÌ, không hỏi nó trông ra sao hay đứng ở đâu"*, và một bài test cụ thể cho
đúng ví dụ đã gây lỗi thật ở `pipeline/record.py`:

> **Form vs Text**: trên một bản sao TRẮNG chưa ai điền, chỗ này có RỖNG
> không? Có → Form. Một giá trị đã in sẵn trong letterhead (mã số thuế in ở
> đầu trang) là Text, không phải Form, dù trông giống một ô biểu mẫu — nó
> chưa bao giờ định để trống.

Đây **đúng là bài test** trả lời được câu "chữ ký đã in sẵn là Text hay Form"
— cái mà `LABELS`/`DOCSYNTH_LABEL_FOR_KIND` (§4.1) đã trả lời SAI VÀ KHÁC NHAU
ở hai bảng, vì cả hai bảng chỉ so chuỗi tiền tố `sign.`, không hỏi "chỗ này có
rỗng trên bản sao trắng không". Guide đã biết câu trả lời đúng từ trước —
nó chỉ chưa được nối vào chỗ cần nó.

**Đo lại việc guide này ĐÃ được nối vào đâu, bằng cách đọc code (không đoán):**

| Điểm sinh `kind`/nhãn vùng | Có dùng `regions.md` không? | Cơ chế |
| :--- | :--- | :--- |
| `synthgen/markup.py` (người viết tay) | **Có, 100%** | Người viết tay TỰ khai `data-region="..."` ngay tại dòng code tạo ra khối đó — không suy sau, không bảng tra. 6 họ khối "không-phải-bảng" đều làm vậy. |
| `agent/augment_layout.py` (mức 2 — sửa 1 layout) | **Có** | `build()` dòng 492: `system = prompt("layout") + "\n\n" + prompt("regions")` — gửi thẳng guide cho model. |
| `agent/compose_layout.py` (mức 3 — soạn layout mới) | **Có, và đi xa hơn** | Dòng 1547 gửi guide; VÀ schema của mỗi khối có hẳn field `"region": {"enum": vocab.regions}` (dòng 703) — model **buộc phải khai region ngay khi soạn khối**, được guide hướng dẫn, được enum chặn không cho bịa tên thứ 19. |
| `agent/compose_page.py` (LLM viết cả trang) | **KHÔNG** | Chỉ gửi **danh sách tên** hợp lệ (dòng 416, 518: `"Permitted data-region": ", ".join(REGIONS)`) — không gửi 169 dòng lý luận ngữ nghĩa. Model phải tự đoán nghĩa của "Form" từ đúng một từ tiếng Anh, không có bài test Form-vs-Text. |
| `generators/html/sheets/*.py` (renderer rule-based, KHÔNG LLM) | **KHÔNG, và không bao giờ khai gì cả** | Không một dòng `data-region` nào trong toàn bộ `sheets/*.py` (đã grep xác nhận). 100% dựa vào `pipeline/record.py::label_for`/`layout_class_for` SUY SAU từ chuỗi `kind` — đúng cơ chế lỗi ở §4.1. |

Cơ chế "khai vùng ngay lúc viết, khai xong thì THẮNG, suy từ thẻ HTML chỉ khi
không khai" **đã có sẵn trong chính renderer** — `generators/html/page.py`
dòng ~423: *"`data-region` viết tay THẮNG: tác giả nói rõ thì nghe tác giả.
Suy từ thẻ chỉ khi không có [khai]."*, và `pipeline/record.py::zones_from_
rects`/`regions_from_words` đọc đúng cơ chế "declared" ấy. Đây chính xác là
điều bạn quan sát ở `synthgen`: **nó không bao giờ missing/sai vùng vì vùng
được QUYẾT ĐỊNH bởi đúng người/đúng lúc đang viết ra khối đó — không phải vì
nó "rule-based" theo nghĩa chung, mà vì nó không hoãn quyết định sang một
bước SUY SAU từ một chuỗi tên.**

**Trả lời trực tiếp: "tại sao LLM không đạt được hiệu quả đó?"**

Không phải LLM *không thể* — hai trong ba nhánh LLM đang chạy (`augment_
layout.py`, `compose_layout.py`) **đã** đạt được, bằng đúng cơ chế "khai ngay
lúc quyết định + guide ngữ nghĩa + enum chặn bịa tên", không phải bảng tra.
Nhánh còn thiếu (`compose_page.py`) thiếu vì nó **chưa được nối** vào
`regions.md`, chỉ được cho một danh sách tên trần — một thiếu sót sửa được
trong một dòng code, và nhiều khả năng góp phần vào tỷ lệ đạt 22% đang đo
được (§5 dưới, docs/kiem-soat-llm.md) vì model phải suy nghĩa "Form" từ trực
giác riêng, không từ bài test Form-vs-Text đã viết sẵn.

Còn phần **rule-based hoàn toàn không LLM** (`sheets/*.py`) thì KHÔNG THIẾU
LLM — nó thiếu đúng một kỷ luật: người viết `sheets/*.py` khi thêm một `kind`
mới hoàn toàn có thể (và nên) khai `data-region="..."` ngay tại chỗ, đúng
cách `markup.py` đã làm — không cần gọi model, không tốn một xu, chỉ tốn công
đọc `regions.md` một lần và tự trả lời câu hỏi *"khối này LÀM GÌ"* ngay lúc
viết. Đây là "nợ kỹ thuật", không phải "thiếu năng lực AI".

**Kết luận §4:** hiện tượng bạn nêu là **có thật, đo được, và tự kho đã ba lần
viết lại comment để cảnh báo người sau đừng lặp lại** — nhưng nó không nằm ở
MỘT chỗ, mà ở ít nhất ba tầng khác nhau (nhãn vùng, mô tả KIE, quy tắc ghép
cặp). Và với đúng tầng bạn hỏi (nhãn vùng): **lời giải không phải "mapping →
LLM"; nó là "mapping → khai-ngay-lúc-viết", việc kho này đã làm đúng ở 2/4 chỗ
và đã viết sẵn guide cho chỗ thứ 3, chỉ còn thiếu dây nối** (§6.3 viết lại
theo đúng phát hiện này).

---

## 5. Vì sao "gọi LLM cho mỗi hộp/mỗi kind" không khả thi ở quy mô này

Trước khi đề xuất giải pháp, cần một con số để cân đo — nếu bỏ hẳn bảng tra
tĩnh và thay bằng LLM quyết định nghĩa của TỪNG đoạn chữ:

* Một lượt `synthgen` gần đây: **20 099 trang** (`data/09-09-26-synthetics-
  document`, theo `synthgen/README.md`).
* Mật độ đo được trên 400 trang mẫu: **91 396 đoạn chữ có hộp / 400 trang ≈
  228 đoạn/trang** (`synthgen/README.md` §6b).
* → một lượt 20 099 trang có khoảng **4,6 triệu** đoạn chữ cần gán nhãn nếu
  làm ở mức "mỗi đoạn chữ một lần hỏi LLM".
* Chi phí đo được cho việc GIỮ NGUYÊN mức "một lời gọi cho cả trang" (không
  phải cho từng đoạn chữ) đã là **56–333 giây/trang** tuỳ tỷ lệ đạt
  (`docs/kiem-soat-llm.md` §2) và **~$4 450 cho 50 000 ảnh** ở mức sinh cả
  trang (`docs/README.md` §4, đo cùng thời điểm) — tức khoảng **$0,089/ảnh**
  chỉ riêng bước sinh, chưa tính bước chấm.

Gọi LLM cho từng đoạn chữ (4,6 triệu lần cho một lượt) là chi phí và thời
gian không thực tế so với một bảng tra 300 dòng chạy trong micro-giây. Đây là
đúng lý do kho này chọn kiến trúc "rule tĩnh + test bắt lỗ hổng" cho tầng gán
nhãn, và chọn "LLM, theo LỚP LAYOUT, ngoại tuyến" cho tầng mô tả KIE
(`agent/kie_describe.py` — hỏi MỘT LẦN cho mỗi (layout, field), không phải cho
mỗi lần field đó xuất hiện trên một trang). **Đây chính là mẫu hình nên áp
dụng cho cả `label_for`/`layout_class_for` nếu muốn "semantic hơn mà không vô
hạn tốn kém"** — xem §6.3.

---

## 6. Đề xuất chỉnh cụ thể

### 6.1 — Gộp planner + compose thành một lời gọi JSON/trang (khả thi)

Có thể làm: viết một schema JSON gộp cả `force` (thuộc tính rule-base) và các
trường content hiện `compose.py` phụ trách, hỏi trong MỘT lời gọi thay vì hai.
Lợi: giảm round-trip, cho model thấy toàn cảnh trang khi quyết định nội dung
(hiện `compose.py` không biết `ornament`/`variant` đã được planner chọn khi nó
viết `store.name`). Giá: schema lớn hơn, và hai module hiện chia khối theo
tiêu chí khác nhau (planner theo chỉ số trang cố định; compose theo `profile`,
vì các `profile` khác nhau có field khác nhau) — gộp đòi thiết kế lại cách
chia khối, không phải việc một dòng.

**Không đổi:** hình học/layout vẫn nên là ID chọn từ catalog (`rulebase/
layouts/`), không phải JSON hình học tự do mỗi trang — lý do đúng như mục 3.2
đã nói: hình học tự do đẩy gánh giữ đúng cột/tràn trang lên model, và đó là
nguồn lỗi số 1 đã đo (`docs/kiem-soat-llm.md` §3).

### 6.2 — "Chấm ngay sau ảnh + generate lại": làm ở ĐÚNG một điểm hẹp

Đề xuất cụ thể: KHÔNG áp mặc định cho toàn bộ 5 000–20 000 ảnh của một lượt
chạy thường. Áp cho:

* **Nhánh thí nghiệm `compose_page.py`/`synthgen`** — nơi tỷ lệ đạt đã thấp
  (22%) và một cổng luật đã tồn tại (`llm_page.py::problems()`); "LLM-B chấm
  lại bằng ảnh" là lớp bổ sung SAU cổng luật (cổng luật rẻ, chạy trước; LLM-B
  đắt, chỉ chạy cho trang đã qua cổng luật nhưng còn nghi ngờ về mặt bố cục —
  đúng việc `agent/critic.py` đã làm, chỉ là chạy sớm hơn).
* **Trần số lần thử cứng** (ví dụ 3), và khi hết trần: **rơi về giá trị
  coverage/rule-based** đúng nguyên tắc `planner.py` đã áp dụng khi model đề
  xuất một giá trị không hợp lệ — không bao giờ để một trang treo vô hạn chờ
  LLM-B gật đầu.
* **Ghi log mọi lần thử** (seed, đề xuất, verdict của LLM-B, lý do) vào đúng
  khuôn sổ cái đã có (`agent_plan.json`/`compose.jsonl`) — đây là điều kiện
  để giữ được "dựng lại được", theo cách đã nêu ở §3.1.
* **Đo trước khi bật mặc định**: chạy 50–100 trang, đo tỷ lệ LLM-B đồng ý
  ngay lần 1 so với tỷ lệ `agent/critic.py` hiện tại đang gắn nhãn "hỏng" cho
  cùng batch đó — nếu hai con số gần nhau, LLM-B không thêm giá trị so với
  cổng luật + critic hậu-kỳ đã có, chỉ thêm chi phí.

### 6.3 — Chọn docsynth (19 nhãn) làm nguồn duy nhất, nối `regions.md` làm
GUIDE ở mọi điểm sinh `kind` — không dựng thêm bảng mapping nào

Sửa lại hoàn toàn so với bản trước của tài liệu này theo đúng góp ý của bạn:
KHÔNG đề xuất "LLM viết một dòng mới vào bảng tra mỗi khi gặp kind lạ" nữa —
đó vẫn là mapping, chỉ là mapping do LLM điền thay người, và vẫn "missing"
đúng kiểu cũ cho tới khi có ai chạy bước đó. Thay vào đó, dùng đúng cơ chế
§4.4 vừa đo được đã chạy tốt ở 2/4 nơi — **quyết định + khai NGAY lúc kind đó
được tạo ra**, không hoãn sang một bước tra cứu nào, dù bảng đó tĩnh hay do
LLM viết:

1. **Bỏ `LABELS` (11-nhãn DocLayNet) — chọn docsynth (19/21-nhãn) làm nguồn
   duy nhất**, đúng như bạn chốt. `label_for()` (converter cũ) có thể tính lại
   BẰNG CÁCH DỊCH từ nhãn docsynth đã có (docsynth → DocLayNet là một ánh xạ
   nhiều-về-một, ổn định, không cần suy lại từ `kind`), thay vì duy trì hai
   bảng tiền tố độc lập — đây là điều tự sửa được sự bất đồng `sign.`→`Form`
   vs `Text` đã đo ở §4.1.3: chỉ còn MỘT quyết định về `sign.`, không phải hai.
2. **Với `sheets/*.py` (renderer rule-based, không LLM) — bắt mọi điểm gọi
   `span(kind, text)` mới phải đi kèm một `region=` khai tường minh**, đúng
   cách `synthgen/markup.py` đã làm cho 6 họ khối của nó, dùng `regions.md`
   làm tài liệu tra cứu CHO NGƯỜI viết code (không cho model — đây là code
   rule-based). Đây là việc **không tốn một lệnh gọi LLM nào**: người viết
   `sheets/invoice.py` khi thêm `kind="menu.discount"` chỉ cần tự hỏi đúng câu
   `regions.md` dạy ("khối này LÀM GÌ, không phải trông ra sao") và ghi luôn
   `region="Table"` cạnh đó. `LABELS`/`DOCSYNTH_LABEL_FOR_KIND` (bảng tiền tố
   suy sau) chỉ còn là **lưới an toàn cho code CŨ chưa kịp khai** — không phải
   cơ chế chính — và CI gate biến "kind không khai, rơi về Text" thành lỗi
   build thay vì mặc định âm thầm (đúng cách `test_every_kind_in_every_
   committed_dataset_is_mapped` đã bắt được vụ 65 kind báo/tạp chí, nhưng chạy
   bắt buộc, không chờ ai nhớ ra chạy test).
3. **Với các nhánh LLM tự soạn cấu trúc mới (`compose_layout.py`,
   `compose_archetype.py`, và — cần sửa — `compose_page.py`)** — model khai
   `region=` **ngay lúc nó quyết định khối/kind đó tồn tại**, được `regions.md`
   hướng dẫn nghĩa (guide, đúng ý bạn), bị enum 16–19 giá trị chặn không cho
   bịa nhãn thứ 20 (đã có ở `compose_layout.py`, xem §4.4). Việc cụ thể cần
   làm: **nối `prompt("regions")` vào `agent/compose_page.py`** giống hai
   nhánh kia đã làm — hiện nó chỉ nhận một danh sách tên, không nhận bài
   luận lý giải. Đây là sửa MỘT dòng, chi phí gần như bằng không (prompt dài
   thêm không làm chậm đáng kể — `docs/kiem-soat-llm.md` §1: "đầu vào là
   prefill"), và trực tiếp nhằm vào đúng loại lỗi Form-vs-Text mà bảng tra cũ
   mắc phải — nên đo lại tỷ lệ đạt trước/sau khi nối, đúng nguyên tắc §2 của
   tài liệu đó ("nâng tỉ lệ đạt đáng giá hơn mọi thứ khác").
4. **Không cần và không nên**: gọi LLM để "phân loại lại" mỗi kind đã có sẵn
   trong `sheets/*.py` hiện tại theo kiểu hậu kiểm — đó vẫn là "suy sau", chỉ
   đổi người suy (từ bảng tiền tố sang một lời gọi API), và vẫn phải chạy lại
   mỗi khi có kind mới. Việc ĐÚNG là dời quyết định về đúng thời điểm nó được
   biết chắc nhất: lúc kind đó được tạo ra, bởi người hoặc bởi model đang soạn
   cấu trúc — không phải lúc đọc lại chuỗi tên của nó.

### 6.4 — Vá lỗ hổng KIE (15 kind chưa vào KIE, coverage 82,1%)

Không cần LLM: mở rộng `pair_fields()`/`kie_full.py` để nhận diện các khối
`survey.*`/`clause.*`/`caption.*`/... theo đúng cấu trúc chúng được vẽ ra
(giống cách `kie_full.py` đã lấp ô bảng bằng hình học, không bằng model) — đây
là việc "đo rồi mở rộng luật", đúng nguyên tắc §9 "hàng rào rẻ trước, model
đắt sau" mà `synthgen/llm_page.py` đang áp dụng.

---

## 7. Bảng tổng hợp: giữ / chỉnh / không nên làm

| Ý trong đề xuất | Đánh giá | Vì sao |
| :--- | :--- | :--- |
| Gộp LLM sinh layout-ID + content thành 1 lời gọi/trang | **Giữ, khả thi** | Kỹ thuật rõ ràng, chỉ cần thiết kế lại cách chia khối |
| LLM tự sinh HÌNH HỌC tự do mỗi trang (không qua catalog) | **Không nên làm mặc định** | Đúng nguồn lỗi #1 đã đo (`docs/kiem-soat-llm.md` §3); catalog+chọn rẻ hơn và ít lỗi hơn sinh tự do |
| LLM-B chấm bằng ẢNH+BẢN GHI đã đo (không tự đo lại hộp) | **Giữ, khả thi, đã có nửa cơ chế** (`agent/critic.py`) | Chỉ cần đổi THỜI ĐIỂM chạy, không đổi CƠ CHẾ đo hộp |
| "Generate lại tới khi đạt", không giới hạn | **Không nên làm** | Phá bất biến tái lập (§3.1), rủi ro vòng lặp vô hạn khi bar của LLM-B khắt khe hơn khả năng LLM-A đạt được |
| "Generate lại", có trần số lần thử + log lại mọi lần thử | **Giữ, khả thi, cần thiết kế sổ cái mới** | Giữ được tái lập theo định nghĩa mở rộng; đã có tiền lệ sổ cái (`agent_plan.json`) |
| Bỏ HẲN rule tĩnh, thay bằng LLM hiểu nghĩa cho MỌI quyết định nhỏ | **Không khả thi ở quy mô kho này** | §5: 4,6 triệu đoạn chữ/lượt 20k trang, LLM per-box không thực tế về chi phí/thời gian |
| "Chọn docsynth làm nguồn, làm GUIDE cho LLM chứ không phải mapping" | **Đúng hướng, và đã có sẵn — chỉ thiếu nối dây** (§4.4) | `agent/prompts/regions.md` đã tồn tại, đã nối vào `augment_layout.py`/`compose_layout.py`; thiếu ở `compose_page.py` (sửa 1 dòng) |
| "Rule tĩnh gán nhãn kind→label hiện tại sai semantic, cần sửa" | **Đúng, có bằng chứng** (§4.1) | 3 lỗi thật đã xảy ra đúng vì cơ chế này; sửa bằng "khai region ngay lúc viết kind" (§6.3), không phải LLM-theo-mỗi-hộp, không phải một bảng mapping thứ hai |
| "Vì sao synthgen không bao giờ missing box, LLM thì có nguy cơ đó" | **Đã trả lời, không phải khoảng cách năng lực** (§4.4) | `markup.py` khai vùng NGAY lúc viết khối; 2/4 nhánh LLM đã làm giống vậy và không missing; chỗ thiếu là dây nối (`compose_page.py`) và kỷ luật code (`sheets/*.py`), không phải giới hạn của LLM |
| "KIE coverage/mapping hiện chưa đủ semantic" | **Đúng một phần, nhưng đây là lỗ hổng THIẾU LUẬT, không phải thiếu LLM** (§4.3) | Vá bằng mở rộng luật ghép cặp, không cần model |

---

## 8. Câu hỏi cần bạn chốt trước khi có kế hoạch triển khai

1. **Ngân sách chi phí/thời gian cho một lượt chạy** — thêm LLM-B + retry có
   trần sẽ đội chi phí lên bao nhiêu so với hiện tại là điều PHẢI đo trên một
   mẻ nhỏ trước, không đoán. Bạn muốn đặt trần tỷ lệ (ví dụ "không hơn 2× chi
   phí hiện tại") hay trần tuyệt đối ($, giờ)?
2. **Định nghĩa "tái lập được" có được nới ra không** — từ "cùng seed → cùng
   byte" sang "cùng seed + cùng log quyết định → cùng byte"? Đây là thay đổi
   triết lý, không chỉ kỹ thuật, và ảnh hưởng tới `tools/baseline.py` cùng mọi
   test dùng sha256 hiện có.
3. **Retry hết trần thì rơi về đâu** — về giá trị rule-based/coverage (an
   toàn, giống cách planner xử lý model-đề-xuất-sai hiện nay), hay bỏ hẳn
   trang đó khỏi lượt chạy (mất số lượng, giữ chất lượng)?
4. **LLM-B là model nào, chấm bằng gì** — cùng model với LLM-A (rẻ hơn, dễ
   thiên vị chính đầu ra của mình) hay model khác/lớn hơn (đắt hơn, khách quan
   hơn)? Ảnh có cần multimodal thật hay chấm bằng bản ghi (bbox, text) là đủ
   cho phần lớn lỗi cần bắt?
5. **Phạm vi áp dụng trước** — toàn bộ pipeline chính, hay chỉ nhánh thí
   nghiệm `synthgen`/`compose_page` (nơi đã có số đo nền để so sánh trước/sau)?

---

## 9. Tham chiếu

* [`docs/kien-thuc-llm-layout-kie.md`](kien-thuc-llm-layout-kie.md) — toàn
  cảnh mọi chỗ LLM đang được gọi hiện nay (bối cảnh cho tài liệu này).
* [`docs/kiem-soat-llm.md`](kiem-soat-llm.md) — mọi số đo về chi phí/tỷ lệ đạt
  của nhánh LLM-viết-cả-trang, trích dẫn nhiều nhất ở đây.
* [`docs/llm-in-pipeline.md`](llm-in-pipeline.md) — thiết kế "quyết định trước,
  vẽ sau" mà §3 phân tích đối chiếu.
* `pipeline/record.py` (`LABELS`, `DOCSYNTH_LABEL_FOR_KIND`, `label_for`,
  `layout_class_for`, `zones_from_rects`, `regions_from_words`) — trích dẫn
  chính cho §4.1 và §4.4.
* `pipeline/kie.py` (`describe`) — trích dẫn chính cho §4.2.
* `agent/prompts/regions.md` — guide ngữ nghĩa 3 trục (region/role/ink) đã có
  sẵn, trích dẫn chính cho §4.4 và §6.3.
* `agent/augment_layout.py:492`, `agent/compose_layout.py:703,1547`,
  `agent/compose_page.py:416,518` — ba điểm nối (hoặc chưa nối) guide vào
  lời gọi LLM, đối chiếu trong bảng §4.4.
* `generators/html/page.py` (comment quanh dòng 423, cơ chế "`data-region`
  viết tay THẮNG") và `synthgen/markup.py` (mọi lệnh gọi `data-region="..."`)
  — cơ chế "khai ngay lúc viết" mà §4.4 và §6.3 đề nghị áp dụng rộng hơn.
* `tests/test_record.py:166`, `tests/test_llm.py:60`, `tests/test_llm.py:436`
  — các test giữ ranh giới/vocabulary được nêu trong §3 và §4.
