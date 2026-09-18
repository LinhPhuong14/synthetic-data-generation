# LLM engine cho layout & KIE — tài liệu kiến thức

> Tài liệu này gộp lại **mọi chỗ một LLM thật sự được gọi** trong kho, thu hẹp
> vào hai việc: **quyết định/soạn bố cục (layout)** và **sinh mô tả trường
> trích xuất thông tin (KIE)**. Viết cho hai người đọc: Claude Code ở phiên
> sau, và người cùng làm domain này. Mọi khẳng định dưới đây đọc từ code hiện
> tại (2026-09-18) — không chép lại từ các doc thiết kế cũ trong `docs/` mà
> không đối chiếu, vì một vài trong số đó (`docs/README.md`, `docs/tu-dong-
> hoa-bang-llm.md`) mô tả một giai đoạn *trước khi* phần lớn code này tồn tại.

---

## 0. Có HAI hệ thống dùng LLM, không phải một

Kho này có hai bộ sinh dữ liệu độc lập, và cả hai đều có một lớp LLM riêng:

| | pipeline chính | `synthgen/` |
| :--- | :--- | :--- |
| bố cục lấy từ | `rulebase/layouts/*.yaml`, người viết tay + agent biến đổi | một **ngữ pháp** trong `synthgen/design.py` (32 phôi), tự dựng dáng mới mỗi lần |
| vẽ bằng | `generators/html/render.py` | `synthgen/draw.py` |
| lớp LLM cho layout | `agent/variants.py` (đổi mực) → `agent/redesign.py`/`augment_layout.py` (dựng lại 1 phôi) → `agent/compose_layout.py` (soạn phôi mới) → `agent/compose_archetype.py` (soạn cả loại chứng từ mới, ghi vào `rulebase/synthgen/`) | `agent/compose_page.py` + `synthgen/llm_page.py` + `synthgen/draw_llm.py` — model viết **cả trang HTML**, không qua ngữ pháp |
| lớp LLM cho KIE | `agent/kie_describe.py` — mô tả trường tốt hơn, theo layout | `agent/augment_descriptions.py` — thêm **cách nói** (paraphrase) cho mô tả đã có |
| ai chọn thuộc tính mỗi trang | `agent/planner.py` (7 trục: document, layout, variant, augmentation, ornament, handwriting, ...) | `synthgen/design.py` tự bốc + khử trùng theo chữ ký dáng, không qua planner |
| dùng chung | `agent/client.py` (endpoint OpenAI, dùng cho các bước đưa vào lượt chạy chính) và `agent/ollama.py` (Ollama, dùng cho các bước tăng cường ngoại tuyến — `augment_content`, `augment_layout`, `compose_archetype`, `augment_descriptions`, `compose_page`) | |

Cả hai hệ thống tuân theo **đúng một bất biến** (§1), và không hệ thống nào
gọi model lúc vẽ ảnh.

`synthgen/` từng mất mã nguồn (2026-09-10) và được dựng lại từ bytecode —
hành vi đúng, comment thì viết lại. Xem memory `synthgen-recovered-from-
bytecode` nếu nghi một dòng comment trong đó không phải chữ gốc.

---

## 1. Bất biến nền tảng: quyết định TRƯỚC, vẽ SAU

Lời hứa của toàn kho: **cùng seed thì ra cùng byte** (`tools/baseline.py` vân
tay ảnh, `tests/test_worklist.py` so sha256, `pipeline/run.py` so
`manifest.json` giữa 1 worker và 8 worker). Gọi model **lúc vẽ** phá lời hứa
này một cách **im lặng** — ảnh vẫn ra, chỉ là không dựng lại được nữa.

Nên kiến trúc là:

> **Model quyết định trước khi vẽ. Quyết định được ghi ra file. Lúc vẽ chỉ đọc
> file — không phân biệt được file do model viết hay do người viết.**

Ranh giới này được một assertion giữ, không phải một quy ước bằng miệng:
`tests/test_llm.py::test_the_render_path_cannot_reach_the_generator` cấm
`generators/`, `pipeline/`, `rulebase/`, `degradation/`, `components/` import
bất cứ thứ gì dưới `agent/`. `tools/` không nằm trong danh sách đó — nó được
import `agent.planner`/`agent.client`/`agent.compose*` trực tiếp, vì `tools/`
chính là **bước quyết định**, chạy như một tiến trình riêng (hoặc import
trực tiếp từ driver `tools/agent_dataset.py`) trước khi renderer mở lên.

Model chỉ chạm vào pipeline qua các đường đã có sẵn, không đường nào đòi sửa
renderer:

| Model muốn | Nó viết ra | Ai đọc lại |
| :--- | :--- | :--- |
| trang này dùng biến thể bố cục khác | file YAML trong `rulebase/layouts/` (hoặc `out/.rules/layouts/`) + `force: {layout: <id>}` | `rulebase` đọc như một layout thường |
| trang này làm cũ kiểu khác | `force: {augmentation, ornament, handwriting, ...}` | cơ chế `--force` đã có từ trước |
| trang này điền nội dung khác | một dòng trong `content_overrides.json` | `rulebase/content.py` qua biến môi trường `VLM_CONTENT_OVERRIDES` |
| trường KIE này nghĩa là gì | một dòng trong `kie_descriptions.json` | `pipeline/kie.py` qua biến môi trường `VLM_KIE_DESCRIPTIONS` |

Tất cả đều theo mẫu "một biến môi trường trỏ tới một file JSON, đọc lười, cache
một lần" — giống `VLM_RULES_ROOT` đã có từ trước khi có agent. Không CLI flag
mới, không sửa chữ ký hàm nào của `rulebase.make()`/`content.build()`.

**Không server thì không phải là lỗi, là một MODE.** `agent/client.py::from_env()`
trả `None` khi `VLM_LLM_URL` rỗng, và mọi bước quyết định chạy sang nhánh
`coverage` (offline). Mỗi trang ghi lại **ai quyết** (`by: "llm"` hay
`by: "coverage"`) — một lượt chạy tụt hạng thầm lặng là kết cục xấu; một lượt
chạy nói rõ từng trang do ai quyết thì không.

---

## 2. LLM cho LAYOUT — bốn mức, bốn câu hỏi khác nhau

Bốn mức không phải bốn phiên bản thay nhau — chúng trả lời bốn câu khác nhau
về **cùng một tờ giấy**, và ba mức đầu nằm trong pipeline chính; mức 4 và
nhánh phụ ở cuối thuộc về `synthgen/`.

### 2.0 — Trước cả bốn mức: `planner.py` chọn 7 trục mỗi trang

`agent/planner.py` là thứ quyết định **document/layout/variant/augmentation/
ornament/handwriting/...** cho từng trang — nó không tự viết bố cục mới, nó
**chọn trong không gian luật đã có**, nhưng nó chọn *có nhớ*, khác hẳn
`rulebase.sample_recipe` (bốc độc lập mỗi trang).

* Vì sao cần nhớ: bốc độc lập bỏ sót đuôi không gian — tổ hợp hiếm không bao
  giờ xuất hiện, tổ hợp phổ biến xuất hiện hàng trăm lần. Đo được:
  `test_coverage_beats_independent_draws_on_the_tail` — 400 lượt độc lập bỏ
  sót nhiều giá trị, 400 lượt của agent phủ hết.
* Công thức điểm mỗi giá trị hợp lệ: `weight / (1 + số lần đã dùng) ** pressure`.
  `pressure=0` là bộ bốc gốc; `pressure=1` gần như phủ đều; `0.72` (mặc định)
  giữ được thực tế do người viết luật cân mà vẫn đẩy lượt chạy ra các góc.
* **Legality không bao giờ giả định**: mỗi thuộc tính chọn trong đúng tập
  `Option.allowed()` cho phép theo thẻ đã gom, cùng thứ tự bốc của
  `sample_recipe`. `planner.verify()` bốc lại từng quyết định qua chính
  `sample_recipe` để chứng minh không kế hoạch nào chứa tổ hợp luật cấm.
* **Hai mode**, ghi theo từng trang: `llm` (có server, id nó trả hợp lệ) và
  `coverage` (không có server, hoặc id không hợp lệ) — nhánh offline chính là
  công thức hoá mục tiêu mà prompt đưa cho model, không phải một cơ chế
  chống-cháy gắn thêm.
* Trang thuộc chính sách `locked`/`livery` (§3) không được đổi dáng, nên được
  đẩy mạnh ra khỏi "không hoạ tiết" (`BARE_PENALTY`) — đó là chỗ duy nhất
  chúng còn đa dạng được.
* `Chooser` còn nhận `penalty`/`ban` từ **vòng phản hồi của critic** (§6): giá
  trị đã làm hỏng trang bị vẽ ít hơn, cặp giá trị chỉ hỏng khi đi cùng nhau bị
  cấm hẳn.
* Có thanh tiến độ, tự lưu checkpoint mỗi khối trang (`--resume` đọc tiếp
  chứ không hỏi lại model những trang đã có), và `concurrency` bắn nhiều khối
  cùng lúc — áp dụng bước quyết định vào chooser luôn **tuần tự**, dù mạng trả
  lời không theo thứ tự, để giữ đúng luồng RNG.

### 2.1 — Mức 1 (`variants.py`, `redesign.py`): đổi mực, KHÔNG đổi hình học

Không gọi model tại đây — đây là **kho biến thể** mà planner (và model khi có
server) chọn từ. Bảy trục (`stock`, `rule`, `band`, `zebra`, `type`, `density`,
`mark`) ghép lại thành 648–77 760 cách phối, mỗi cái chỉ đổi CSS (mực, nền,
hoạ tiết `::before`/`::after`), không đổi bố cục. `redesign.py` thêm 22 cách
**dựng lại** phôi (thứ tự khối, số cột) trên cùng bộ chọn.

Ranh giới không được vượt: hộp nhãn đo từ DOM đã dàn xong, nên CSS di chuyển
chữ là an toàn (hộp dịch theo) nhưng `text-transform` (DOM giữ chuỗi gốc, pixel
hiện chuỗi khác) và `content:` mang chữ (glyph không hộp nào tả) thì không —
`sheets/variant.py::forbidden` kiểm từng chuỗi trước khi dán vào trang.

### 2.2 — Mức 2 (`agent/augment_layout.py`): model SỬA một file layout

```bash
python -m agent.augment_layout --from market_vat --id market_vat_b          # xem trước
python -m agent.augment_layout --from market_vat --id market_vat_b --write  # qua hàng rào rồi ghi
```

Đọc một layout viết tay, xin model viết một **biến thể** (cùng chứng từ, khác
cách in), giữ nếu qua đúng **sáu cửa** một layout viết tay phải qua: là YAML
hợp lệ → mọi key path có trong layout viết tay, đúng kiểu, trong dải đã đo →
mọi khoảng `[min, max]` đúng thứ tự → có đủ key mọi layout viết tay đều có →
`rulebase.make()` dựng được qua nhiều seed → `pipeline/preflight.py` sạch trên
toàn bộ rule base. Hỏng ở đâu thì file bị xoá và ba đăng ký liên quan
(`rules/layout.yaml`, `blanks.yaml`, `sheets.FAMILIES`) được hoàn nguyên —
không có "layout đăng ký nửa vời".

Prompt (`agent/prompts/layout.md`) đã được sửa hai lần theo đúng lỗi thật đo
được: model hay viết khoảng đảo ngược (`[48, 42]`, vì nó nghĩ "rộng hơn" nên
để số lớn trước) và `rule_char` không hợp lệ — prompt nay nói thẳng hai điều
đó.

### 2.3 — Mức 3 (`agent/compose_layout.py`): model SOẠN MỚI, không sửa phôi nào

```bash
python -m agent.compose_layout --document invoice_detailed --explain
python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk --write
python -m agent.compose_layout --document invoice_detailed --distance invoice_kiosk
python -m agent.compose_layout --document invoice_detailed --id invoice_thu --proof 12
```

Nhận **k phôi thật** làm bằng chứng về một loại chứng từ, cộng đặc tả trường
(`constraints.yaml`), rồi viết ra một cấu trúc **không có trong phôi nào**
— câu hỏi khác mức 2 ("tờ này, in mực khác?"/"bày khác đi?" so với "một nhà in
KHÁC sẽ làm ra tờ gì?").

Điểm thiết kế quan trọng nhất: **model trả về CẤU TRÚC (`Composition`: khối,
cột, khổ giấy, `reasoning`), không bao giờ trả về markup**. `to_layout()` —
code, không phải model — biến nó thành file YAML mà `sheets/` render như mọi
layout khác. Đó là hợp đồng nhãn: mỗi run phải là một `<span>` chứa đúng chữ
đã escape, và model viết HTML thì hợp đồng ấy phụ thuộc vào việc model không
quên trên 5000 trang; bộ dựng viết thì đúng theo cấu trúc.

Ba lớp của phân tích (bất biến pháp lý, quy ước ngành, lựa chọn nhà in) được
**tính** từ *k* phôi (`layers()`), không được khai tay — và đo được chỉ
**9/33** chứng từ trong kho hiện có đủ bằng chứng (≥ 2 phôi thật, khác nhau
trên ít nhất một trong sáu chiều: khối, thứ tự khối, cột, thuộc tính cột, tuỳ
chọn khối, khổ giấy) để mức 3 hoạt động — không phải giới hạn của bộ soạn, mà
là kho chưa có đủ phôi làm bằng chứng.

Hai cửa vào đều **từ chối thay vì mặc định**: `policy.yaml` (§3 dưới) nói được
dựng lại dáng không, `constraints.yaml` nói được thì trong khoảng nào — chứng
từ chưa có mục đã duyệt bị từ chối kèm tên file phải sửa.

Bảy cửa ải (chạy trong `--write`, trừ cửa 7 cần ảnh thật nên là lệnh
`--proof`): guided decoding theo schema → trọng tài số học → chữ in ra →
schema bố cục → hợp đồng nhãn → dựng + preflight → `agent/critic.py` đọc ảnh
proof (13 mã lỗi).

Bài học lặp lại hai lần trong quá trình làm mức này: **cửa 1 phải làm cái sai
thành BẤT KHẢ (không đánh vần được), không phải thành BỊ TỪ CHỐI.** Một schema
mời một câu trả lời rồi cửa sau phạt nó là cửa hỏng, không phải model hỏng —
đo được 9/13, 12/14, 7/11 lỗi liên tiếp đều từ nguyên nhân này trước khi sửa.

**Bố cục mức 2 và mức 3 sinh ra hiện CHƯA được commit vào kho chính** — chúng
qua hết hàng rào, nhưng thêm vào làm hỏng golden baseline / coverage test hiện
có (một lỗi có sẵn cần sửa trước).

### 2.4 — Mức 4, nhánh riêng (`agent/compose_archetype.py`): soạn cả LOẠI CHỨNG TỪ

```bash
python -m agent.compose_archetype --want 3 --write
python -m agent.compose_archetype --about "giấy ra viện" --write
```

Mảnh cuối nối LLM vào `synthgen/`. Trước file này, model viết được bố cục cho
pipeline chính (`rulebase/layouts/*.yaml`, mức 2–3) nhưng không với tới
`synthgen/` được vì ngữ pháp của bộ ấy nằm thẳng trong Python
(`synthgen/design.py::ARCHETYPES`, 34 phôi viết cứng) — và model không sửa mã
nguồn. `synthgen/archetypes.py` mở đường bằng cách cho phôi khai được bằng
YAML (`rulebase/synthgen/*.yaml`, 57 file hiện có); `compose_archetype.py` là
thứ viết ra YAML ấy.

Cổng dùng lại đúng `synthgen/archetypes.py::problems` — cổng `design.py` dùng
lúc nạp — cộng ba phép đo riêng cho *bộ sưu tập* (không phải một phôi): phôi
mới phải khác mọi phôi đang có ở nhiều hơn cái tên (đo bằng bộ khối + bộ cột
trùng nhau), `titles` đủ nhiều để nghìn tờ không ra cùng tên, id phải là slug
ASCII (vì nó thành tên thư mục). **`--write` ghi vào ngữ pháp của bộ sinh** —
chặt hơn `augment_content.py` vì một phôi hỏng làm hỏng mọi tờ rút ra từ nó,
không chỉ một dòng corpus.

### 2.5 — Nhánh thí nghiệm riêng: model viết CẢ TRANG (`compose_page.py`)

```bash
python -m agent.compose_page --want 30 -o data/pilot-llm --concurrency 4
python synthgen/draw_llm.py data/pilot-llm
python synthgen/draw_llm.py data/pilot-llm --only rejected
```

Đây là phép thử "LLM tự vẽ bố cục" theo nghĩa triệt để nhất trong kho: model
**tự nghĩ ra trường gì có trên trang, ai ký, bày thế nào**, rồi viết ra chính
HTML+CSS của trang — không qua ngữ pháp `design.py`, không qua `rulebase/
layouts/`. Vẫn tách hai bước: `compose_page.py` viết `<stem>.html` +
`<stem>.json` (không mở trình duyệt); `synthgen/draw_llm.py` mới là bước vẽ
thật (Chromium, đo hộp bằng đúng phép đo mọi trang khác dùng).

Vì sao tách: **hộp vẫn phải đến từ engine đã dàn chữ** — luật này không đổi
khi model viết HTML, Chromium vẫn dàn, `CELL_RECTS_JS` vẫn đo. Thứ đổi là *ai
hứa trang ấy đo được* — trước là `markup.py` (đúng theo cấu tạo, vì là code);
giờ là model, nên phải **kiểm**. `synthgen/llm_page.py::problems()` là cổng
đó, năm luật:

1. **Run có nhãn chỉ chứa chữ** — không thẻ lồng trong `<span data-kind>`.
   Không phải sở thích: `CELL_RECTS_JS` đo `span.firstElementChild || span`,
   nên một `<sub>` lồng trong span làm hộp co lại 5,3px thay vì 310,6px, và
   nhãn vẫn "đúng" theo nghĩa máy không báo lỗi.
2. Mọi giá trị đã khai trong JSON nội dung phải in ra HTML đúng một lần
   (so chữ, không tin lời hứa).
3. `data-kind` phải nằm trong từ vựng đóng — từ vựng này **đo từ engine thật**
   (dựng 300 mẫu, nhặt kind, không liệt kê tay), vì liệt kê tay từng loại sạch
   40/40 trang do chính `markup.py` sinh ra.
4. Không tài nguyên ngoài (`<script>`, ảnh http, `@import`) — trang phải vẽ
   được offline.
5. Phải có phần tử `.sheet` để `draw.py` chụp.

`plan` là bước model **tự nghĩ trước khi viết HTML** (bản đầu đưa phôi khai
sẵn khiến 30 tờ ra cùng một khuôn — đúng kiến trúc "N phôi" mà người dùng đã
bác), và bắt model tự **ánh xạ** trường nó vừa nghĩ ra sang `data-kind` có
thật — đúng chỗ nó hỏng nhiều nhất ở lượt thử đầu (`patient.name`,
`project.code`, `admission.date`: tên tự đặt chưa từng đối chiếu với từ vựng).

**Trang trượt cổng vẫn được vẽ** (`draw_llm.py`, ảnh vào `rejected_boxes/`
riêng, không lẫn với `layout_boxes/`) — vì đó là những trang đáng nhìn nhất:
một trang qua cổng nói "model làm đúng"; một trang trượt nói **model hiểu sai
cái gì**, và đó là thứ sửa được bằng cách sửa prompt. Đo trên 30 trang đầu:
21 trượt, tất cả đều biến mất (không lưu lại) ở bản chưa có `draw_llm.py`
lưu cả trang trượt.

Bốn số phải trả lời (chưa phải bản án, là phép đo khói): số học sai bao nhiêu
(`qty × unit_price` so `amount`), giây mỗi trang (~44s/3000 token trên
Qwen3.8-27B-FP8 → `--concurrency` bắt buộc từ đầu), bao nhiêu trang qua cổng,
đa dạng so với engine (`agent/distance.py`).

Cái cổng máy **không** tự sửa: nội dung có thật hay không ("Công ty TNHH Mặt
Trời Mọc" là tên hợp lệ, có thể không tồn tại) — cổng máy bắt cái đo được,
người đọc diff bắt phần còn lại. Đây cũng là giới hạn chung cho **mọi** nội
dung do model viết trong kho, không riêng nhánh này.

### 2.6 — Chính sách chặn: `agent/policy.yaml` + `agent/policy.py`

Xuyên suốt các mức 1–3, một tầng riêng quyết định **chứng từ nào được phép
đổi dáng chút nào**:

| Hạng | Được làm gì | Ví dụ |
| :--- | :--- | :--- |
| `locked` | chỉ ornament — không variant, không nét kẻ, không nền | `vat_invoice_form`, `hospital_bill` |
| `livery` | đổi mực/nền, hình học giữ nguyên | `export_invoice`, `utility_power`, `utility_water` |
| `free` | đổi tất cả, sinh thêm hoạ tiết mới | 10 chứng từ thương mại còn lại |

Lý do: hoá đơn GTGT theo mẫu có **một** dáng hợp lệ do quy định ban hành, tự
bịa dáng thứ hai là dạy model rằng tờ giả cũng là tờ thật. **Mặc định là mức
chặt nhất** — chứng từ chưa phân loại bị coi là lỗi, không mặc định `free`
(`Policy.klass()` raise `PolicyError`, không đoán). Chính bộ luật là bên chặn
— mỗi document mang thẻ `aug_locked`/`aug_livery`/`aug_free`, mỗi variant khai
`requires`/`excludes` theo thẻ đó, nên một lỗi trong planner **không thể**
dựng lại một tờ giấy nhà nước dù có cố tình.

Có hai file chính sách khác nhau nói về cùng ~41 chứng từ, và chúng có thể lệch
mà không gì báo: `rulebase/augmentable.yaml` (nếu còn) nói bộ **sinh** (corpus)
được đề xuất tới đâu; `agent/policy.yaml` nói bộ **quyết định** (layout) được
dựng lại tới đâu.

---

## 3. LLM cho KIE — thiết kế "fallback trước, model sau"

Nguyên tắc xuyên suốt: **mọi trang luôn có description cho mọi trường KIE,
có hay không có model** — model chỉ làm mô tả *tốt hơn*, không làm nó *tồn
tại*.

### 3.1 — Pipeline chính: `pipeline/kie.py`

`pipeline/kie.py::build_page()` dựng phần `"kie"` của bản ghi một trang:
`pair_fields()`/`pair_entities()` ghép nhãn với giá trị theo **thứ tự vẽ liền
kề** (một caption `kind` kết thúc bằng `.label`/`.title` đứng ngay trước giá
trị nó chú thích — quy ước mọi `sheets/*.py` tuân theo, không phải bảng tra
theo từng loại chứng từ), rồi `describe()` chọn mô tả theo **bốn nguồn, tốt
nhất trước**:

1. `llm` — file `VLM_KIE_DESCRIPTIONS` (do `agent/kie_describe.py` viết), khoá
   theo `layout` rồi `field`.
2. `caption` — chính chữ in cạnh giá trị trên giấy ("Người mua" → mô tả dựng
   từ đó). Không bao giờ sai, không bao giờ thiếu.
3. `kind` — `data-kind` chính run đó mang (`store.name`, `total.grand`) —
   dùng khi KHÔNG có caption in kèm.
4. `label` — nhãn lớp 19-label của layout, khi `kind` cũng không nói gì hơn.

Không có bảng chuỗi-theo-từng-loại-chứng-từ nào trong file này — mọi nguồn là
DỮ LIỆU trang đã mang sẵn, để một loại chứng từ mới không bao giờ "thiếu" khỏi
một bảng tra cứu.

Một quyết định đáng nhớ: chữ in sẵn giống nhau trên mọi tờ ("(Ký, ghi rõ họ
tên)") mang **0 bit thông tin** dù có hộp — `FURNITURE` loại nó khỏi cặp KIE
(đo được: 2/3 cặp họ `sign.` từng là câu in sẵn này, tức bộ dữ liệu "dạy" model
rằng tên người ký là câu nhắc in sẵn).

Và một biến đổi hình dạng: đường dẫn có chỉ số (`items[0].name`, `items[1].
name`, ...) được **gộp thành một mục kiểu mảng** trong `kie.schema` (không
gộp trong `kie.pairs` — mỗi ô vẫn giữ hộp riêng) — tránh một bảng 13 dòng × 6
cột biến thành 78 thuộc tính phẳng không ai đọc hết.

### 3.2 — Bước LLM: `agent/kie_describe.py` + `agent/prompts/kie.md`

```bash
python -m agent.kie_describe --dataset data/5k_llm
VLM_KIE_DESCRIPTIONS=data/5k_llm/kie_descriptions.json python tools/agent_dataset.py ...
```

Đọc lại một dataset **đã vẽ xong**, gom mọi trường còn mang
`description_source: "fallback"`, hỏi model một mô tả tiếng Anh **theo từng
layout** (một mô tả là thuộc tính của layout in ra nó, không phải của một
trang riêng), rồi ghi file `kie_descriptions.json`. Chạy lại thì **gộp**, không
đè — một layout dataset sau không đụng tới vẫn giữ mô tả dataset trước đã
viết cho nó.

Prompt (`agent/prompts/kie.md`) chỉ được cho `key_text` (nhãn in trên giấy) và
**một** `value_text` mẫu — không ảnh, không toàn trang — và bị dặn: ngắn một
câu, không lặp lại nhãn dịch máy móc, dùng giá trị mẫu để suy kiểu dữ liệu khi
nhãn mơ hồ, và nếu một nhãn lặp lại (`_2`, `_3`) phải nói rõ khác lần trước ở
đâu. Không có server thì lệnh không sinh gì và in ra lý do — pipeline vẫn chạy
đúng bằng mô tả fallback.

### 3.3 — KIE riêng của `synthgen/`: phủ MỌI nhãn, không chỉ cặp label:value

`pipeline/kie.py` chỉ thấy được nơi **có nhãn in kèm** — đo trên 400 trang
`synthgen`: 91 396 đoạn chữ có hộp, chỉ 11,2% nằm trong một cặp KIE. Toàn bộ ô
bảng, tiêu đề cột, con dấu, dòng cộng nhóm có hộp, có nhãn lớp, mà không có
mặt trong KIE. `synthgen/kie_full.py` lấp nốt bằng ba loại cặp: **ô bảng**
(khoá là tiêu đề cột, kèm `column_path` cho bảng nhiều tầng), **cặp mới**
(`total.group` → `total.group_amount`), và **không có nhãn in** (`key_bbox:
null`, `key_source: "implied"` — tiêu đề, con dấu, tên nhóm dòng). Sau khi lấp:
100% trên 250 file thử.

`synthgen/kie_schema.py` viết CÙNG KIE ấy thành JSON Schema + instance khớp
nó — vì một model sinh JSON có ràng buộc (vLLM/xgrammar) ăn schema, không ăn
danh sách cặp. Ba quyết định đáng nhớ: bảng thành **một mảng** (`line_items:
array of object`), không thành hàng trăm trường phẳng; kiểu suy từ **nghĩa**
chứ không từ hình dạng chuỗi (số điện thoại không thành `number` dù toàn chữ
số); và bỏ phần khung bảng (tiêu đề cột, số cột) ra khỏi schema — chúng vẫn có
trong `pairs` kèm hộp, chỉ không phải thứ một extractor cần được HỎI.

**Đây KHÔNG phải bước LLM** — cả hai file trên là hình học + suy luận thuần
trên bản ghi đã có, không gọi model.

### 3.4 — Mô tả và cách nói: `descriptions.py` (viết tay) vs `phrasing.py` (hash) vs `augment_descriptions.py` (LLM)

Ba file dễ nhầm là "LLM sinh mô tả", nhưng chỉ một trong ba thực sự gọi model:

* **`synthgen/descriptions.py`** — từ điển tiếng Anh **viết tay**, khoá theo
  chính nhãn `design.py` in ra (không phải bảng thứ hai chép tay riêng — thêm
  một cách viết nhãn ở `design.py` là có mô tả ở đây luôn). Không gọi model.
* **`synthgen/phrasing.py`** — mỗi mô tả có 2 cách nói tiếng Anh + 2 tiếng
  Việt, chọn theo `crc32(seed | trường | câu gốc)` — **hàm thuần, xác định**,
  không gọi model lúc chạy. Lý do tồn tại: một mô tả lặp y hệt 7920 lần/250
  file dạy model học thuộc câu chứ không học nghĩa.
* **`agent/augment_descriptions.py`** — **bước LLM thật**, chạy ngoại tuyến,
  đề xuất THÊM cách nói mới cho `POOL` của `phrasing.py`, ghi vào
  `rulebase/kie_phrasings.json` (gộp, không đè). Cổng dùng đúng nguyên tắc của
  `agent/corpus_rules.py`: mọi ngưỡng đo từ cách nói người đã viết trong
  `POOL`, hỏi riêng từng thứ tiếng (một lượt tiếng Việt mà câu không dấu thì
  loại, một lượt tiếng Anh mà câu có dấu cũng loại).

```bash
python -m agent.augment_descriptions --want 6            # xem trước
python -m agent.augment_descriptions --want 6 --write    # ghi vào rulebase/kie_phrasings.json
python -m agent.augment_descriptions --only qty,amount --want 12 --write
```

---

## 4. Nội dung do model viết: `agent/compose.py` (nuôi cả layout lẫn KIE)

`agent/planner.py` quyết định **loại giấy**; `agent/compose.py` quyết định
**vài trường TEXT trên giấy đó nói gì** — `store.name`, tên một mặt hàng,
chẩn đoán bệnh viện — thay cho `rulebase/content.py` bốc từ
`rulebase/corpus/vi/*.txt`. Nhắc lại vì §3 phụ thuộc vào nó: giá trị field mà
`compose.py` viết ra chính là `key_text`/`value_text` mà `kie_describe.py` sau
đó đọc lại để hỏi mô tả.

Cùng khung với `planner.py` (`decide()`, `concurrency`, `pin`, byte-giống-nhau
bất kể bao nhiêu luồng) nhưng chia khối theo **profile** (`market`, `medical`,
...) vì schema khác nhau giữa các loại, không theo chỉ số trang.

Nguyên tắc "rulebase là kim chỉ nam, không phải bộ sinh": mọi giới hạn gửi cho
model đều **đo được**, không bịa — độ dài `store.name` đo từ
`agent.corpus_rules.envelopes()` trên đúng corpus mà đường rule-based sẽ dùng;
chẩn đoán bệnh viện bị ép chọn đúng cặp `(mã, tên)` đã có trong `diagnoses:`
của `rulebase/documents/hospital_bill.yaml`, không tự bịa mã ICD.

**Số học không giao cho model** — tiền, thuế, tổng vẫn do `rulebase/content.py`
tính, vì `pipeline/invariants.py` kiểm lại và một model cộng sai làm hỏng cả
shard lặng lẽ.

Gác cổng: `agent.corpus_rules.check_name()` (đúng hàm gác `augment_content.py`)
**cộng thêm** `pipeline.drift.has_diacritics()` — giá trị model viết cho
`content_overrides` PHẢI còn dấu tiếng Việt (điều kiện này không thêm vào
`check_name` dùng chung, vì dòng corpus người viết hợp lệ mà không dấu vẫn có
— "iPad", "Natri Clorid 0,9%"). Một giá trị bị loại thì chỉ mất TRƯỜNG đó,
trang vẫn dựng, trường ấy quay về corpus như chưa từng có override.

Ghi hai file: `compose.jsonl` (sổ cái đầy đủ, kể cả giá trị bị từ chối và vì
sao) và `content_overrides.json` (file gọn `rulebase/content.py` thực sự đọc).

---

## 5. Vòng phản hồi: đọc lại bộ đã vẽ để dạy lượt sau

`agent/planner.py` không tự biết nó vừa đặt một QR code đè lên tiêu đề — cả
hai quyết định (`layout=form_dense`, `ornament=qr_dau_trang`) đều hợp lý một
mình, chỉ sai khi đứng cạnh nhau, và chỉ thấy được **sau khi trình duyệt đã
chạy**.

```bash
python tools/critic_review.py --dataset data/5k_llm
python tools/critic_review.py --dataset data/5k_llm --guideline agent/guideline
```

* **`agent/critic.py`** — đọc lại bản ghi (hộp chồng lấn, hộp ngoài trang, hộp
  không chữ) và đọc lại ẢNH (mực có đúng chỗ nhãn nói không, đủ tương phản để
  đọc không) — 13 mã lỗi, mỗi lỗi gắn lại với tám giá trị thuộc tính đã vẽ ra
  trang đó qua `synthesis.json`. `rank()` biến "trang hỏng" thành "giá trị nào
  hỏng" (`ornament=qr_dau_trang` hỏng 40% so với nền 3%), và `penalties()`
  biến số đó thành thứ `agent/planner.py::Chooser` đọc được (§2.0).
* **`agent/guideline.py`** — sinh lại `agent/guideline/{SYSTEM_PROMPT,
  KNOWLEDGE,CHECKLIST}.md` **từ chính repo** (chính sách từ `policy.yaml`,
  thuộc tính từ rules đã hợp nhất, kiến trúc trang từ `redesign.py`, lỗi cần
  tránh từ `critic.py` trên một lượt chạy thật kèm tỉ lệ đo được) — không phải
  viết tay, vì một guideline trôi khỏi luật nó tả còn tệ hơn không có, do
  người ta sẽ TIN nó. Ba file vì đọc vào ba lúc khác nhau: `SYSTEM_PROMPT.md`
  vào mỗi lượt gọi, `KNOWLEDGE.md` một model ngữ cảnh dài đọc trọn, `CHECKLIST.
  md` model tự soát câu trả lời của mình trước khi trả về.

Vòng này opt-in (`--feedback`) — một lượt chạy đầu tiên, chưa có review nào,
hành xử đúng như trước khi có reviewer.

---

## 6. Hạ tầng gọi model

Hai client khác nhau, dùng cho hai nhóm việc khác nhau:

| | `agent/client.py` | `agent/ollama.py` |
| :--- | :--- | :--- |
| API | OpenAI-compatible (`/v1/chat/completions`) | Ollama (`/api/chat`) |
| dùng cho | các bước vào LƯỢT CHẠY: `planner.py`, `compose.py`, `compose_layout.py`, `compose_archetype.py`, `compose_page.py`, `kie_describe.py` | các bước TĂNG CƯỜNG ngoại tuyến, chạy tay: `augment_content.py`, `augment_layout.py`, `augment_descriptions.py` |
| ép JSON | `response_format: json_schema` + constrained decoding (vLLM `xgrammar`) — enum ID hợp lệ **theo cấu tạo**, không theo hy vọng | prompt yêu cầu, không constrained decoding |
| biến môi trường | `VLM_LLM_URL`, `VLM_LLM_MODEL`, `VLM_LLM_KEY`, `VLM_LLM_TIMEOUT` | `VLM_LLM_HOST` (mặc định loopback), `VLM_LLM_MODEL`, `VLM_LLM_TOKEN` |
| không server | `from_env()` trả `None` — nhánh gọi chuyển sang `coverage`/xem-trước | script in ra và dừng, không ghi gì |

`Client._post()` (agent/client.py) có mấy chi tiết đáng nhớ vì đã đo được thật
trên server của team: `max_tokens` mặc định `0` (để vLLM tự quyết) nhưng có
thể set — một trang lan man từng chạy 360 giây/5000+ token vì không có trần;
`enable_thinking: false` gửi qua `chat_template_kwargs` vì `reasoning_effort`
riêng KHÔNG đủ để tắt suy luận ẩn của Qwen3 (đo được: từ 38s "nghĩ" xuống 0.4s
cho cùng câu hỏi ba từ); lỗi HTTP giữ lại **thân lỗi** của server (một schema
grammar backend không dịch được, hay một chat-template kwarg model từ chối) vì
đó thường là cả lời giải; 4xx không retry (là bản án về payload, gửi lại không
đổi gì) còn 5xx/lỗi mạng thì retry có backoff.

---

## 7. Chạy — lệnh và biến môi trường

```bash
# Không cần server — mọi bước quyết định chạy chế độ coverage
python tools/agent_dataset.py -o data/5k_llm -n 5000 --workers 3

# Có server (vLLM / SGLang / llama.cpp / bất kỳ endpoint OpenAI nào)
vllm serve Qwen/Qwen3.5-9B --port 8000 --served-model-name planner \
     --structured-outputs-config.backend xgrammar \
     --structured-outputs-config.enable_in_reasoning=True

export VLM_LLM_URL=http://127.0.0.1:8000/v1
export VLM_LLM_MODEL=planner
python tools/agent_dataset.py -o data/5k_llm -n 5000 --workers 3 \
  --llm-concurrency 4      # cấp bài lập kế hoạch VÀ compose cùng lúc
  --content-llm            # BẮT BUỘC gõ riêng — có VLM_LLM_URL không tự bật
                            # đổi nội dung, vì đó là thay đổi lớn hơn chọn thuộc tính
```

Sau khi có dataset, sinh mô tả KIE tốt hơn rồi dùng lại cho lượt sau:

```bash
python -m agent.kie_describe --dataset data/5k_llm
export VLM_KIE_DESCRIPTIONS=data/5k_llm/kie_descriptions.json
python tools/agent_dataset.py -o data/5k_llm_v2 -n 5000 ...
```

Cờ đáng chỉnh của `tools/agent_dataset.py`: `--dressings` (kho biến thể to bao
nhiêu, mặc định 48), `--pressure` (0 = bốc gốc, 1 = đuổi phủ, mặc định 0.72),
`--shard`, `--plan-only` (chỉ quyết định, không vẽ), `--resume`.

Nhánh `synthgen/`:

```bash
python -m agent.compose_page --want 30 -o data/pilot-llm --concurrency 4
python synthgen/draw_llm.py data/pilot-llm
python -m agent.compose_archetype --want 3 --write
python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk --write
```

Server không trả lời thì `Client.alive()` bắt được và lượt chạy nói ra rồi
chuyển sang coverage — không đứng chờ hàng nghìn lần timeout.

---

## 8. Bản đồ file — mọi nơi LLM được gọi hoặc phục vụ việc gọi LLM

**Quyết định / soạn layout**

| File | Việc |
| :--- | :--- |
| `agent/planner.py` | chọn 7 trục mỗi trang, có nhớ; hai mode `llm`/`coverage` |
| `agent/policy.yaml`, `agent/policy.py` | chứng từ nào được đổi dáng tới đâu — dữ liệu, chặn cứng |
| `agent/variants.py` | 7 trục mực → kho biến thể |
| `agent/redesign.py` | 22 cách dựng lại phôi, trên bộ chọn của `variants.py` |
| `agent/augment_layout.py` | model sửa MỘT file layout — 6 cửa |
| `agent/compose_layout.py` | model soạn MỚI bố cục từ *k* phôi — 7 cửa |
| `agent/compose_archetype.py` | model soạn cả LOẠI CHỨNG TỪ mới cho `synthgen/` |
| `agent/compose_page.py` | model viết CẢ TRANG (HTML+content) cho `synthgen/` |
| `synthgen/llm_page.py` | cổng 5 luật cho trang model viết, trước khi vẽ |
| `synthgen/draw_llm.py` | vẽ trang model viết, kể cả trang trượt cổng |
| `agent/distance.py` | "bố cục này khác gì phôi cha" — vẽ 2 lần, đếm run đã dịch |
| `agent/critic.py` | đọc bộ đã vẽ, 13 mã lỗi, gắn lại với thuộc tính đã chọn |
| `agent/guideline.py` | sinh guideline cho model từ chính rules + policy + critic |
| `agent/rules.py`, `agent/layout_schema.py`, `agent/constraints.yaml`/`.py` | hạ tầng luật/schema mà các mức 2–3 kiểm qua |

**Sinh nội dung / KIE**

| File | Việc |
| :--- | :--- |
| `agent/compose.py` | model viết giá trị TEXT của vài trường (`store.name`, tên hàng, chẩn đoán) |
| `pipeline/kie.py` | ghép nhãn-giá trị + chọn mô tả, 4 nguồn, luôn có fallback |
| `agent/kie_describe.py` + `agent/prompts/kie.md` | model viết mô tả trường tốt hơn, theo layout |
| `synthgen/kie_full.py` | lấp KIE cho MỌI nhãn in ra, không chỉ cặp có label (không LLM) |
| `synthgen/kie_schema.py` | JSON Schema + instance từ cùng KIE đó (không LLM) |
| `synthgen/descriptions.py` | từ điển mô tả viết tay (không LLM) |
| `synthgen/phrasing.py` | chọn 1-trong-4 cách nói theo hash xác định (không LLM) |
| `agent/augment_descriptions.py` | model đề xuất THÊM cách nói vào `rulebase/kie_phrasings.json` |
| `agent/augment_content.py`, `agent/corpus_rules.py` | model viết thêm dòng corpus mới, qua gác cổng — nuôi cả nội dung rule-based lẫn compose.py |

**Hạ tầng chung**

| File | Việc |
| :--- | :--- |
| `agent/client.py` | client OpenAI-compatible, dùng cho các bước vào lượt chạy |
| `agent/ollama.py` | client Ollama, dùng cho các bước tăng cường ngoại tuyến |
| `agent/provenance.py` | đóng dấu `# >>> llm ...` quanh khối corpus do model viết |
| `agent/prompts/*.md` | mọi prompt hệ thống — file markdown, không phải chuỗi trong code |

---

## 9. Những gì CHƯA làm (theo `docs/llm-in-pipeline.md` §9, đối chiếu code hiện tại)

* Bước "compose sinh biến thể bố cục THEO LÔ, có ngân sách cân bằng tự động"
  vẫn chạy tay, từng bố cục một (`augment_layout.py`) — chưa có driver tự gọi
  theo lô như `compose.py` đã có cho nội dung.
* `pipeline/run.py` chưa tự gọi pha sinh biến thể bố cục.
* Bố cục do mức 2/3 sinh ra qua được hết hàng rào nhưng **chưa commit** vào
  `rulebase/layouts/` chính — cần chụp lại golden baseline trước, và việc đó
  đang bị một lỗi có sẵn chặn (`invoice_export` seed 6026).
* Hai file chính sách (`policy.yaml` cho layout, `augmentable.yaml` cho corpus
  nếu còn tồn tại) nói về cùng nhóm chứng từ mà có thể bất đồng — gộp lại là
  việc còn treo.

---

## 10. Tài liệu liên quan trong `docs/` và `agent/`

* [`agent/README.md`](../agent/README.md) — tài liệu gốc, chi tiết nhất, cho
  các mức 1–3 của layout và toàn bộ nửa "sinh" cũ (`tools/llm/` trước khi gộp).
* [`docs/llm-in-pipeline.md`](llm-in-pipeline.md) — thiết kế ban đầu của
  `compose`/`content_overrides` (phần lớn ✅ đã làm, khác đôi chỗ so với bản vẽ
  — đọc kèm code, đừng tin bản vẽ khi hai bên lệch).
* [`docs/kiem-soat-llm.md`](kiem-soat-llm.md) — số đo thời gian/lỗi thật của
  nhánh `compose_page.py`.
* [`synthgen/README.md`](../synthgen/README.md) — toàn cảnh `synthgen/`, phần
  lớn KHÔNG dùng LLM (ngữ pháp `design.py` tự bốc + khử trùng theo chữ ký
  dáng) — chỉ §mục về `compose_page`/`compose_archetype` là lớp LLM.
* memory `vlm-ocr-synthetic-project`, `synthgen-recovered-from-bytecode` —
  bối cảnh dự án và lịch sử mất/khôi phục mã nguồn `synthgen/`.
