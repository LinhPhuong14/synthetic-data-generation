# Kế hoạch refactor engine — LLM là Realizer, không phải người quyết

> Nguồn: "Engine Refactor Summary — Dynamic LLM Control & Diversity" (tư duy
> gốc của người dùng, 20 mục, dán nguyên trong lịch sử trò chuyện dẫn tới tài
> liệu này). Tài liệu này chia nó thành task có thứ tự, có file đích, có
> definition of done — và ghép thêm những gì audit + lịch sử code đã bắt được
> mà bản tư duy gốc chưa biết.
>
> Đọc cùng: [`llm-in-pipeline.md`](llm-in-pipeline.md) (ba track hiện có),
> [`kiem-soat-llm.md`](kiem-soat-llm.md) (số đo thật), `agent/compose_page.py`
> và `agent/prompts/page.md` (track 3 — track tài liệu này refactor),
> `agent/guideline/SYSTEM_PROMPT.md` (base rules đã nối vào track 3).
>
> Phạm vi: **chỉ track 3** (`agent/compose_page.py` → `synthgen/draw_llm.py`
> → `synthgen/derive.py`). Track 1 (`agent/planner.py` + rulebase) và track 2
> (`synthgen/run.py`, không LLM) không thuộc phạm vi trừ khi ghi rõ.

---

## 0. Ba bài học đã trả giá — đừng lặp lại

Đọc trước khi làm bất kỳ phase nào bên dưới. Cả ba đều nằm trong code hiện tại
dưới dạng docstring, không phải suy đoán.

### G1 — Archetype/Planner không được là "N phôi", kể cả khi trông giống combinatorial

`agent/compose_page.py::schema()` (dòng 75-90) ghi lại: bản trước đưa model
một "phôi đã khai sẵn: trường nào, ai ký, ghi chú gì", model chỉ điền vào —
kết quả **"ba mươi tờ đi ra từ cùng một khuôn"**, và người dùng đã bác kiến
trúc đó. Ví dụ YAML `DocumentPlan` ở mục 4 trong tư duy gốc (`structure:
header: two_column, item_table: {morphology: grouped, columns: 7, rows: 14}`)
đọc y hệt kiểu phôi đã bị bác nếu triển khai literal — mỗi field bị khoá cứng
một giá trị cụ thể. **Planner phải chọn NGẪU NHIÊN CÓ TRỌNG SỐ trong một
không gian tổ hợp lớn, không phải điền vào một mẫu cố định.** Xem Phase 3.

### G2 — Rate-matching hiện có (`wants_table`, `sheets`) có lý do đo được, không phải bug

`wants_table()` (dòng 367-383) tồn tại vì để model tự quyết bảng từng cho
**60% trang có bảng** trong khi kho rulebase thật chỉ 18-46% — người dùng đã
phản hồi "các layout llm nghĩ đang bị nhiều bảng" và đây là bản sửa. Đừng xoá
cơ chế này để "LLM tự quyết hoàn toàn" theo nghĩa đen của mục 16 (page.md);
**mở rộng cùng triết lý** (round-robin khớp tỉ lệ đo được) sang các trục khác
(density, table morphology, layout topology) thay vì thay thế nó bằng LLM tự
do hoàn toàn hay bằng planner khoá cứng.

### G3 — Hai (thực ra ba) cơ chế KIE từng chồng nhau; **đã vá, và mất hai lần đo sai mới tìm đúng con số**

`pipeline/record.py::entities_from_words`/`_bind_entities` (suy theo thứ tự
DOM), `synthgen/kie_full.py::declared_pairs` (đọc thẳng `data-path`), và
`table_pairs`/`extra_pairs` (chỗ ngồi bảng, cặp muộn) từng cùng gán nhãn một
entity — đo trên `data/pilot10`: **57/77 entity bị đếm trùng hai lần**
(`docs/kie-cau-hoi-kiem-schema.md` dòng 357-404, 17-09 15:13).
`synthgen/kie_full.py::complete()` (dòng 694-801) đã có logic hợp nhất
("Chữa 3"), nhưng nó chỉ hợp nhất `declared` với `label`/`table` — không
hợp nhất `table` với `label`/`pair` khi CẢ HAI đều không có `data-path`.

Xác minh mất **ba lần đo**, không phải một (kể đầy đủ ở Phase 1, vì cách sai
quan trọng không kém con số đúng): lần một dùng nhầm `record["html"]` (đã bị
rút gọn, không còn span nào) → 0 trùng giả; lần hai đếm cả `key_entity_index`
trùng (một tiêu đề cột dùng chung cho nhiều dòng — đúng cấu trúc bảng, không
phải trùng) → 52/1337 giả; lần ba chỉ đếm `value_entity_index` → **4/1337**
thật, tất cả cùng một hình (dòng TỔNG CỘNG của bảng trùng nhãn "TỔNG CỘNG:"
đứng trước nó). Vá bằng `_dedup_by_value()` (xếp hạng nguồn, chạy sau
`extra_pairs`): **0/1337** sau khi vá.

Bài học giữ nguyên giá trị dù con số ban đầu (57/77) không còn đúng nguyên
xi: **đừng tin một con số trong tài liệu lịch sử mà không chạy lại code hiện
tại để xác minh còn tái hiện hay không** — và khi chạy lại, tự hỏi luôn
phương pháp đo (nguồn dữ liệu đúng chưa, đếm đúng thứ chưa) trước khi tin số
ra. Phase 1 đã xong — cả `FieldRecord`, cả bản vá `_dedup_by_value`, cả
regression test. Xem Phase 1.

---

## 0b. Bốn điểm sửa theo review (chốt trước khi code Phase 3+)

Người dùng approve có điều kiện: đúng hướng, nhưng 4 điểm sau phải sửa trong
kế hoạch trước khi bắt đầu code, vì nếu không rất dễ refactor xong rồi vẫn
dính đúng G1.

1. **Phase 3 — grammar phải có ràng buộc điều kiện, không phải tích Descartes.**
   `3 nhánh × 3 lựa chọn × 4 nhánh = 81` vẫn chỉ là "81 template ẩn" nếu các
   nhánh độc lập với nhau. Yêu cầu: *"Grammar must define a compositional
   constraint space with conditional dependencies, rather than a finite
   Cartesian product of predefined visual variants."* Áp dụng ở 3.1-3.2.
2. **Phase 4 — coverage phải phân tầng (coarse/mid/fine), không phải một
   tuple phẳng.** Đếm `family × density × table × layout` bỏ lọt trường hợp
   trùng bốn trục đó nhưng khác field composition, hoặc ngược lại. Áp dụng
   ở 4.2-4.3.
3. **Phase 5 — `DocumentPlan` của engine là authoritative, LLM không tự
   sinh một plan thứ hai để so sánh.** Nếu `plan` vẫn còn trong structured
   output vì lý do protocol/debug, nó chỉ là execution summary — validator
   so HTML thật với `DocumentPlan` gốc, không so hai plan với nhau. Áp
   dụng ở 5.2-5.3.
4. **Hard-negative compatibility phải khai từ Phase 3/4, không đợi Phase 6.**
   Grammar phải biết field/context nào hợp lệ với strategy nào; planner rút
   `hard_negative_profile` tương thích ngay khi rút `DocumentPlan`. Phase 6
   chỉ còn implementation (record type, gate, test). Thêm task 3.4, sửa 4.1
   và đầu Phase 6.

Giữ nguyên, không đổi: `wants_table`/`sheets` rate-matching (G2) tổng quát
hoá thành sampler thay vì bị xoá — task 4.4 không đổi.

---

## Nguyên tắc chỉ đạo cho mọi phase

1. Không phá track 1/track 2 trừ khi task nói rõ (`generators/html/page.py`
   là hợp đồng đo lường DÙNG CHUNG cả ba track — sửa cẩn thận).
2. Mỗi phase kết thúc bằng sinh mẫu thật + so đo trước/sau
   (`docs/kiem-soat-llm.md` là nơi ghi số đo, không phải ý kiến).
3. Prompt (`page.md`, `SYSTEM_PROMPT.md`) chỉ diễn đạt cái code đã enforce
   được bằng schema/gate — không dùng prompt để xin cái deterministic được.
4. Mỗi thay đổi giản đồ (`schema()`) là thay đổi giao thức với model đang
   chạy — cần chạy lại `tools/critic_review.py` hoặc tương đương sau mỗi
   phase để không lái mù.
5. Commit riêng theo từng task nhỏ, không gộp nhiều phase vào một commit.
6. **Một phase một lần.** Xong Phase N thì dừng, review, rồi mới bắt đầu
   Phase N+1 — không chạy liên tiếp nhiều phase không dừng. Đây là
   architecture refactor, không phải bugfix đơn lẻ.

---

## Phase 1 — Field Registry & hợp nhất KIE — **XONG**

**Vì sao làm trước:** tưởng có bug thật đã đo được (G3) để bám. Đúng là có
bug thật, nhưng phải qua HAI lần đo sai trước khi tìm ra hình dạng thật của
nó — kể lại dưới đây, vì cách tìm ra quan trọng không kém con số.

**Lần đo thứ nhất (sai):** chạy `kie_full.complete()` trên `record["html"]`
của `data/pilot10`/`data/pilot12` → 0/844 và 0/426 trùng. Kết luận vội "bug
đã vá từ trước". **Sai vì lấy nhầm nguồn**: `record["html"]` trong
`records/*.json` đã bị `derive.py` rút gọn thành văn bản thuần, không còn
`<span data-kind>`/`data-path` nào để `declared_pairs` đọc — phép đo chưa
từng chạm tới đường `data-path` nó tưởng đang kiểm.

**Lần đo thứ hai (sai kiểu khác):** đổi sang HTML thật (`data/*/html/*.html`,
có span) → 52/1337 "trùng". Vẫn sai: phép đếm coi `key_entity_index` bị dùng
lại là trùng, trong khi một tiêu đề cột (`key_entity_index`) làm khoá chung
cho NHIỀU dòng là đúng cấu trúc bảng, không phải hai trường nhận một ô.

**Lần đo thứ ba (đúng):** chỉ đếm `value_entity_index` trùng → **4/1337**.
Cả bốn cùng một hình: dòng TỔNG CỘNG của bảng (`source=table`) trùng với
nhãn "TỔNG CỘNG:" đứng ngay trước nó (`source=label`), hoặc bị `extra_pairs`
khớp lại lần nữa (`source=pair`/`family`) với một chú thích khác trên trang.
`complete()`'s "Chữa 3" (dòng 694-801) đã hợp nhất đường KHAI
(`declared`) với NHÃN/BẢNG, nhưng chỉ so với tập `spoken` gieo từ `declared`
— không so `table` với `label`/`pair` khi CẢ HAI đều không có `data-path`.

**Sửa:** thêm `synthgen/kie_full.py::_dedup_by_value()` — một lượt cuối, sau
`extra_pairs`, xếp hạng nguồn (`declared` > `table` > `label` > `pair` >
`implied`) và giữ đúng một cặp mỗi `value_entity_index`, gộp chữ in của kẻ
thua vào `printed_header` của kẻ thắng. Kiểm lại trên chính 16 tài liệu:
**0/1337**. Test hồi quy: `tests/test_kie_full_dedup.py`.

Bài học giữ nguyên giá trị dù hai lần đầu đo sai: đọc đúng tài liệu lịch sử
không thay được việc chạy lại code hiện tại — và ngay cả khi chạy lại,
phương pháp đo (nguồn dữ liệu nào, đếm cái gì là "trùng") phải tự kiểm trước
khi tin số ra.

| # | Task | File chính | DoD | Trạng thái |
|---|---|---|---|---|
| 1.1 | Định nghĩa `FieldRecord` (path, kind, value, role: positive/ordinary/hard_negative/label) — không phải để sửa bug, mà để Phase 4/6 có một type thống nhất thay vì dict rời rạc | `pipeline/fields.py` | type hoặc dataclass, dùng được từ cả `pipeline/record.py` lẫn `synthgen/kie_full.py` | **Xong** — `registry()` gộp entity+pair; test `tests/test_fields.py` |
| 1.2 | Đọc + CHẠY THẬT để xác minh vì sao/liệu `entities_from_words` và `declared_pairs` có cùng gán nhãn một box không | `pipeline/record.py` dòng 1009-1224, `synthgen/kie_full.py` dòng 309, 694-801 | báo cáo root cause bằng file:line + số đo thật | **Xong** — 4/1337 trước khi vá (xem kể lại ở trên), 0/1337 sau |
| 1.3 | Sửa chính sách hợp nhất: KHÔNG chỉ `data-path` thắng nhãn, mà `table` cũng phải thắng `label`/`pair` khi cả hai không có `data-path` | `synthgen/kie_full.py::_dedup_by_value()` | một box chỉ nhận đúng một entity | **Xong** — xếp hạng nguồn, chạy sau `extra_pairs`, 0/1337 trên dữ liệu thật |
| 1.4 | `data` JSON key hiện ghi ra `declared/*.json` rồi không ai đọc lại — quyết định: bỏ khỏi schema hay dùng để cross-check `data-path` | `agent/compose_page.py::resolve_path`/`data_path_mismatches` | có test cross-check hoặc field bị xoá khỏi schema | **Xong (giữ + cross-check, không gate)** — đo trên `data/pilot12` (4 tài liệu có `data` không rỗng — `pilot10` sinh trước khi việc đọc `data` ra được sửa, luôn `null`): 2/4 khớp hết, 2/4 lệch nhưng đều là khác biệt ĐỊNH DẠNG lành tính (`"1583000000"` so với `"1.583.000.000"`), không phải mâu thuẫn ngữ nghĩa — hàm ĐO cho Phase 2, không GATE |
| 1.5 | Ràng buộc `data-path`: well-formed, cùng đường dẫn thì cùng giá trị | `synthgen/llm_page.py::problems()` | test hồi quy: path sai dạng/xung đột giá trị bị bắt trước render | **Xong (một phần có chủ đích)** — well-formed + same-path-same-value là gate cứng (luôn sai bất kể phiên bản prompt); "có mặt khi data-kind có mặt" HOÃN sang Phase 2 — đo trên dữ liệu thật: chỉ 28% span có `data-path` dưới `page.md` CŨ, ép gate theo số chưa đo lại cho prompt MỚI là đổi tỉ lệ chấp nhận mà không ai biết trước bao nhiêu. `path_coverage()` đo, không gate |
| 1.6 | Regression test khoá lại hành vi hợp nhất đã đúng (1.3) chống hồi quy | `tests/` | test chạy trên record thật (pilot10/pilot12) hoặc fixture rút gọn, khẳng định 0 entity trùng | **Xong** — `tests/test_kie_full_dedup.py` (fixture tối giản + hồi quy trên 16 tài liệu thật, `skipif` khi thiếu `data/`) |

**Kiểm tra live LLM:** `curl` tới `127.0.0.1:8000`/`127.0.0.1:11434` bị từ
chối ngay (đúng -- không có gì chạy ở các cổng mặc định của máy này), nhưng
server thật chạy ở một địa chỉ nội bộ khác (`VLM_LLM_URL`, model
`Qwen/Qwen3.8-27B-FP8`) và người dùng xác nhận nó còn sống. Đã gọi
`python -m agent.compose_page --want 3 --no-draw` thật với `page.md`/
`SYSTEM_PROMPT.md` MỚI -- kết quả ghi ở đầu Phase 2 (mục 2.5) khi chạy xong,
vì lượt gọi này đo trực tiếp cho taxonomy đang xây ở Phase 2, không phải
Phase 1 nữa.

---

## Phase 2 — Failure taxonomy & validation nhiều tầng

**Vì sao làm sớm:** cần có trước để đo "trước/sau" cho mọi phase tiếp theo,
không phải để trước cho đẹp. Tương ứng mục 15, 16.

| # | Task | File chính | DoD | Trạng thái |
|---|---|---|---|---|
| 2.1 | Liệt kê failure code hiện có và map sang taxonomy mục 16 | `pipeline/failures.py` (docstring) | bảng đối chiếu code cũ ↔ taxonomy mới | **Xong** — xem bảng dưới |
| 2.2 | Thêm code còn thiếu: `MISSING_DATA_PATH`, `DUPLICATE_DATA_PATH`, `KIE_FALSE_POSITIVE`/`NEGATIVE`, `PLAN_VIOLATION`, `DIVERSITY_COLLAPSE` | `pipeline/failures.py` | mỗi lần reject có đúng một code, machine-readable | **Xong** — `classify()` + `tally()`, nối vào `agent/compose_page.py::run()` (`report["failure_codes"]`), test `tests/test_failures.py` |
| 2.3 | Validation pre-LLM (plan hợp lệ trước khi gọi model) — hiện không tồn tại vì model tự nghĩ hết; chỉ áp dụng sau khi có Planner (Phase 3-4) | — | hoãn tới Phase 4, ghi chú ở đây để không quên | Hoãn (đúng kế hoạch) |
| 2.4 | Corpus-level stats: tần suất family, tỉ lệ qua cổng, mã lỗi, `data-path` coverage, tỉ lệ xin bảng | `tools/llm/corpus_stats.py` | chạy được trên một batch đã sinh, ra báo cáo | **Xong (phạm vi hiện đo được)** — table morphology/layout topology/density/hard-negative profile CHƯA đo được vì chưa tồn tại trong code (`not_measurable_yet` trong output nói rõ, không suy diễn số liệu giả); chạy thật trên lô 3 trang ở mục 2.5 dưới. Test `tests/test_corpus_stats.py` |

**Bảng đối chiếu (2.1) — phạm vi CHỈ cổng sinh trang (`problems`/
`plan_problems`/`sheet_plan_problems`), không gộp `synthgen/check.py`
(công cụ audit CẢ KHO sau khi vẽ, đối tượng khác, đã có cách nhóm riêng bằng
`Counter` trên nhãn tiếng Việt — trộn hai tầng vào một enum là trộn hai
công cụ khác nhau, ngoài phạm vi Phase 2; xem docstring `pipeline/failures.py`
cho từng nhãn của `check.py` sẽ về đâu NẾU việc gộp đó có ngày xảy ra):**

| Câu lý do thật (rút gọn) | Nguồn | Mã |
|---|---|---|
| `N ô bảng thiếu \`data-cell\`` | `problems()` | `INVALID_TABLE_CELL` |
| `` `data-path=...` không đúng dạng `` | `problems()` | `SCHEMA_VIOLATION` |
| `` `data-path=...` in ra N giá trị khác nhau `` | `problems()` | `DUPLICATE_DATA_PATH` |
| `` `data-region=...` không phải một trong 16 nhãn vùng `` | `problems()` | `WRONG_REGION_TYPE` |
| `có thẻ lồng bên trong` | `problems()` | `MISSING_BOX` |
| `run có nhãn nằm NGOÀI mọi <div class="sheet">` | `problems()` | `MISSING_BOX` |
| `không có <div class="sheet">` / `HTML không đọc được` / `trang rỗng` / forbidden tags | `problems()` | `SCHEMA_VIOLATION` |
| `` `data-kind=...` không có trong từ vựng `` / không có run nào mang `data-kind` | `problems()` | `SCHEMA_VIOLATION` |
| `trường ... khai giá trị ... mà không run nào in ra` | `problems()` | `KIE_FALSE_NEGATIVE` |
| `trường ... in ra N lần` | `problems()` | `DUPLICATE_DATA_PATH` |
| `` `field_plan` đặt tên ... không có trong từ vựng `` | `plan_problems()` | `PLAN_VIOLATION` |
| `trang bỏ N/M kind đã hứa trong kế hoạch` | `plan_problems()` | `PLAN_VIOLATION` |
| `chữ ký mà plan.signers để trống` | `plan_problems()` | `PLAN_VIOLATION` |
| `sheet_plan trống` / `chỉ khai N tờ` / `tờ ... không mục nào` | `sheet_plan_problems()` | `DENSITY_VIOLATION` |
| *(chưa có producer)* | — | `TEXT_TABLE_CONFUSION` |
| *(chưa có producer)* | — | `KIE_FALSE_POSITIVE` |
| *(chỉ ở tầng corpus, không phải per-page)* | — | `DIVERSITY_COLLAPSE` |

`TEXT_TABLE_CONFUSION` và `KIE_FALSE_POSITIVE` cần thông tin cấu trúc DOM mà
các reason-string phẳng không mang theo — việc thật của chúng nằm ở Phase 6
(hard negative — `KIE_FALSE_POSITIVE`) và cần một bộ phân biệt Table-thật
khỏi Table-giả riêng (không thuộc phạm vi Phase 2, xem mục 11 tư duy gốc).

### 2.5 — Lượt gọi LLM thật đầu tiên với `page.md`/`SYSTEM_PROMPT.md` mới

Server sống ở một địa chỉ nội bộ khác các cổng mặc định (`VLM_LLM_URL`,
`Qwen/Qwen3.8-27B-FP8`), không phải "không có server" như suy đoán ban đầu
từ hai cổng mặc định rỗng. `python -m agent.compose_page --want 3 --no-draw`:

```text
0/3 qua cổng. Lý do:
  academic_appeal_letter:   trang bỏ 5/10 kind đã hứa trong kế hoạch -> PLAN_VIOLATION
  contract_decision:        `clause.body` có thẻ lồng bên trong      -> MISSING_BOX
  patient_fees_statement:   trang bỏ 9/15 kind đã hứa trong kế hoạch -> PLAN_VIOLATION
```

`n=3` là quá nhỏ để kết luận tỉ lệ qua cổng chung, nhưng hai điều đáng ghi
lại ngay:

1. **Không có false positive nào từ luật `data-path` mới (1.5).** Một trong
   ba trang bị bắt đúng một lỗi thật do chính luật ấy: `data-path` khai
   trùng nhưng in ra hai giá trị khác nhau (`'QUẬN THANH XUÂN'` và
   `'ỦY BAN NHÂN D...'`) -- không phải gate quá tay, mà bắt đúng một mâu
   thuẫn model tự tạo ra.
2. **`data-path` coverage dưới prompt MỚI dao động rất mạnh, không phải một
   con số ổn định gần 28% (cũ):** `academic_appeal_letter` 0/38 (0%),
   `contract_decision` 41/41 (100%), `patient_fees_statement` 12/20 (60%).
   Xác nhận đúng lý do 1.5 CHƯA ép gate theo tỉ lệ: một gate "≥X% phải có
   `data-path`" đặt ra từ ba mẫu này sẽ loại nhầm ít nhất một trang viết
   đúng (100%) hoặc chấp nhận một trang không dùng cơ chế này chút nào (0%)
   tuỳ chọn X ra sao -- cần nhiều mẫu hơn trước khi định X, đúng như đã ghi.

### 2.6 — Lô 20 trang (vẽ đầy đủ): phát hiện missing-box thật, vá `page.md` ngay tại chỗ

Chạy `--want 20` (có vẽ, không `--no-draw`) để kiểm `_dedup_by_value` trên dữ
liệu MỚI -- dừng ở giữa chừng (11/20) theo yêu cầu người dùng sau khi một
phát hiện quan trọng hơn xuất hiện, không chạy tiếp cho hết. Đo trực tiếp
trên 10 trang đã vẽ xong: **71% chữ hiển thị trong `.sheet` có
`<span data-kind>`, 29% thì không** (dao động 13%-100% tuỳ trang). Mẫu lặp
lại: gần như luôn là khối letterhead/masthead (tên đơn vị, địa chỉ, MST,
điện thoại) bị bỏ ngoài span -- không phải bug đo lường (JS đo hộp hoạt
động đúng), model đơn giản không bọc span quanh khối ấy dù `page.md` đã
dặn. Cổng gác hiện tại (`problems()`) **không bắt được lỗi này** -- nó chỉ
kiểm span ĐÃ có, không kiểm chữ hoàn toàn không có span nào; hai trang thiếu
15% và 8% nội dung vẫn qua cổng (✓).

Đo thêm: 100% trang dùng `color: #000` cho chữ thân, viền toàn màu đen,
100% `font-family: 'Times New Roman'` -- không có biến thiên màu sắc/kiểu
chữ nào giữa các trang dù `page.md` mục 27 đã liệt "border density, line
weight..." là những trục nên biến thiên.

**Vá ngay** (theo yêu cầu người dùng, không chờ Phase 5 viết lại toàn bộ
`page.md`):

- mục 27.1 mới: bắt buộc một quyết định màu có chủ đích cho mỗi tài liệu
  (không mặc định `#000`), có số đo làm bằng chứng ngay trong prompt;
- mục 28.1 mới: letterhead phải tuân mục 6-11 như mọi trường khác, kèm ví
  dụ HTML cụ thể và số đo (87% chữ không span trên trang tệ nhất);
- mục 58 (MISSING-BOX PREVENTION) thêm "chữ có nghĩa không có
  `<span data-kind>` nào" làm nguyên nhân ĐẦU DANH SÁCH, kèm số đo 71%/29%;
- mục 38.1 mới: **luật 80%** -- mọi trang của tài liệu nhiều tờ (kể cả tờ
  cuối) phải lấp ít nhất 80% khổ giấy, cùng ngưỡng `synthgen/check.py::MIN_FILL`
  đã dùng ở tầng audit corpus -- nay nói thẳng ra trong prompt thay vì chỉ
  nằm im ở tầng kiểm sau. Nguyên nhân hay gặp nhất được nêu rõ: dồn chi tiết
  vào các tờ đầu, tờ cuối cùng chỉ có chữ ký rồi bỏ trắng.

**Chưa làm** (do dừng lô sớm theo yêu cầu): đo lại `page.md` mới có thực sự
giảm tỉ lệ chữ-không-span và tăng đa dạng màu hay không. Cần một lô nhỏ mới
sau khi các mục còn lại của kế hoạch được làm tiếp, đúng yêu cầu "sửa nốt
các mục ... rồi check lại sau".

---

## Phase 3 — Archetype/Grammar thành compositional constraint space (KHÔNG code vội)

**Đây là phase rủi ro nhất vì G1.** Tương ứng mục 3. Trước khi viết code,
phải trả lời được: "cơ chế này khác `DOMAINS`/`inspiration()` hiện có
(`agent/compose_page.py` dòng 265-486) ở chỗ nào, và tại sao lần này sẽ không
collapse như lần trước?"

**Sửa theo review (điểm 1):** một cây nhánh độc lập (`header × customer ×
table × signature`, mỗi nhánh 3-4 lựa chọn) vẫn là tích Descartes — dù đếm ra
81 tổ hợp, đó vẫn là "81 template ẩn" nếu không có ràng buộc NỐI các nhánh
với nhau. DoD cũ ("≥4 nhánh × ≥3 lựa chọn") bị loại; grammar phải có
**conditional dependency** giữa các nhánh, ví dụ:

```text
IF table = multi_tier     THEN header ∈ {2-tier, 3-tier}
IF density = sparse       THEN row_count ∈ [3, 8]
IF document = contract    THEN clause_section = repeatable
IF signature_count = 3    THEN signature_layout ∈ {horizontal, approval_chain, stacked}
```

| # | Task | File chính | DoD | Trạng thái |
|---|---|---|---|---|
| 3.1 | Viết grammar cho 3-5 document family thí điểm dưới dạng cây tuỳ chọn CÓ ràng buộc điều kiện giữa nhánh (như ví dụ trên) | `agent/grammar.py` | **"Grammar must define a compositional constraint space with conditional dependencies, rather than a finite Cartesian product of predefined visual variants."** Mỗi family có ít nhất một ràng buộc nối hai nhánh trở lên — liệt kê nhánh độc lập không tính là đạt | **Xong (thí điểm 3 family)** — `invoice`, `contract`, `certificate`, mỗi family 5-6 nhánh, 3 ràng buộc điều kiện nối nhánh |
| 3.2 | Đếm kích thước không gian tổ hợp SAU khi áp ràng buộc (không phải tích Descartes thô trước ràng buộc) | `agent/grammar.py::space_size()` | số liệu ghi vào docstring/doc: tổng tổ hợp thô, tổ hợp còn lại sau ràng buộc, và tổ hợp bị loại — chứng minh ràng buộc thật sự cắt bớt không gian phẳng chứ không chỉ trang trí | **Xong (số liệu sau đối chiếu 3.5)** — `invoice` 1296→435 (cắt 861, 66%), `contract` 972→560 (cắt 412, 42%), `certificate` 48→27 (cắt 21, 44%). Cả 3 family đều `cut > 0`. Test khoá lại: `tests/test_grammar.py::test_every_pilot_family_has_a_real_not_decorative_constraint` |
| 3.3 | Grammar phải xuất được **constraint**, không phải giá trị cụ thể — plan cụ thể do sampler (Phase 4) rút ra khỏi grammar bằng trọng số + giải ràng buộc, không phải grammar tự ấn định | `agent/grammar.py::valid_options()` | grammar không có nhánh nào bị hard-code một giá trị duy nhất | **Xong** — `valid_options(grammar, branch, assignment)` trả tập còn hợp lệ theo assignment đã có, không trả một giá trị cố định; Phase 4 gọi hàm này để rút, không đọc thẳng một field cấu hình sẵn |
| 3.4 | **(điểm 4)** Grammar khai luôn hard-negative-compatible strategies cho từng field/context — field nào hợp lý với decoy dạng lexical/format/contextual/..., field nào không | `agent/grammar.py::FieldCompat` | mỗi field trong field vocabulary có (có thể rỗng) danh sách strategy hợp lệ; Phase 4.1 đọc trực tiếp danh sách này khi rút `hard_negative_profile`, không đợi Phase 6 mới nghĩ tới | **Xong (phạm vi thí điểm)** — 5 field/family khai compat (không phải toàn bộ ~80 kind của từ vựng — mở rộng cùng lúc với 3→30 family); `doc_title`/`sign.name` khai rỗng có chủ đích (không có decoy hợp lý), test khoá lại |

### 3.5 — Đối chiếu 3 family với `rulebase/layouts/*.yaml` (theo yêu cầu, trước khi viết 30 family)

Không suy luận thêm — đọc `sections:` thật của layout track 1. Bắt được
**hai lỗi thật** trong bản grammar đầu tiên:

1. Nhánh `table` của `invoice` từng có `"none"`. **23/23** layout hoá đơn
   gốc trong `rulebase/layouts/invoice_*.yaml` đều có `table` trong
   `sections:` — không layout nào bỏ bảng. Xoá `"none"`.
2. `signature_count` của `invoice` từng bắt buộc ≥1. **6/23 (26%)** layout
   thật (`invoice_dense_table`, `invoice_multipage`, `invoice_brand`,
   `invoice_logo_center`, `invoice_minimalist`, `invoice_tax_en`) không có
   `signatures`. Thêm `0`, cùng hai ràng buộc buộc `signature_layout` phải
   khớp (`0` → `"none"`, `≥1` → khác `"none"`).

Và một chỗ **thiếu hẳn**: `contract` không có nhánh `table` nào trong bản
đầu. Đối chiếu `insurance_property_contract.yaml` (đại diện gần nhất trong
rulebase cho "hợp đồng có phụ lục bảng") thấy `sections:` của nó có cả
`table` lẫn `totals`. Thêm nhánh `table` (`none`/`simple`/`schedule`) và một
ràng buộc: bảng `schedule` kéo theo `density` phải `dense`/`very_dense`.

Và một chỗ **phóng đại**: ràng buộc "certificate sparse → không bảng" dùng
sai trục. Đối chiếu `rulebase/layouts/insurance_*_certificate.yaml` (5
layout gốc): **3/5** (`fire`, `health`, `travel`) CÓ bảng — bảng ở
certificate không hiếm, nó gắn với việc certificate xác nhận NHIỀU khoản
mục (quyền lợi/hạng mục) hay MỘT sự việc đơn (`auto`/`moto`, 2/5, không
bảng). Đổi trục `density` thành `confirms` (`single_fact`/`itemized_list`)
cho đúng nghĩa.

**Giới hạn thật của phép đối chiếu này**, nói rõ để không tưởng đã xong
hoàn toàn: `rulebase/layouts/*.yaml` trả lời tốt câu "khối X có mặt hay
không" (đọc thẳng `sections:`), nhưng nó tham số hoá liên tục
(`width: [88, 100]`, `name_scale: [1.25, 1.45]`), không phải cây quyết định
rời rạc như grammar này — các option CHI TIẾT bên trong một khối đã có mặt
(`header` nên chia mấy kiểu, tên gì) vẫn là từ vựng tự đặt của module này,
chưa tra được từ đâu xa hơn. Khi mở rộng lên 30 family, phần "có khối này
không" nên tiếp tục đối chiếu `sections:` như đã làm; phần "khối này chia
kiểu gì" vẫn cần suy luận có ghi chú, hoặc một nguồn đối chiếu khác chưa
xác định.

**Số liệu sau khi sửa:** `invoice` 1296→435 (cắt 861, 66% — tăng mạnh vì
hai ràng buộc `signature_layout` mới), `contract` 972→560 (cắt 412, 42%),
`certificate` không đổi kích thước (48→27) vì chỉ đổi TÊN trục, không đổi
số lượng option. 14 test cũ vẫn qua nguyên (không phải viết lại, vì
interface `Branch`/`Constraint` không đổi, chỉ nội dung 3 family đổi).

### 3.6 — Mở rộng lên 30 family (theo yêu cầu, sau khi duyệt 3.5)

30 tên thật lấy từ `rulebase/documents/*.yaml` (bộ tham số nội dung track 1,
44 file có sẵn — chọn 30 loại khác biệt nhất về cấu trúc, bỏ các biến thể
gần trùng: `resort_stay`≈`hotel_stay`, `convenience_store`≈`retail_vat_
invoice`, `form_checklist_table`≈`form_checklist`, `bakery_order` không có
`sections:` để đối chiếu). Gồm:

- **2 family giữ nguyên từ 3.5** (`invoice_detailed`, `insurance_property_
  contract`) — đổi tên từ nhãn chung "invoice"/"contract" sang đúng tên
  thật trong `rulebase/documents/`, vì không có file `invoice.yaml` hay
  `contract.yaml` chung chung nào ở đó. "certificate" chung chung của bản
  thí điểm bị bỏ hẳn — tách thành 5 loại cụ thể (`insurance_auto/fire/
  health/moto/travel_certificate`) nằm trong 28 family mới.
- **28 family mới**, dựng bằng `agent/grammar.py::_family()` từ hai con số
  đọc thẳng từ dữ liệu, không suy luận:
  - `sig = len(signature_labels)` trong chính `rulebase/documents/<tên>.yaml`;
  - `table`/`parties` = có mặt `table`/`parties` trong `sections:` của
    layout khớp nhất (`_SOURCE` trong `agent/grammar.py` ghi rõ ánh xạ tên
    document → tên layout, vì hai bên không phải lúc nào cũng trùng tên —
    ví dụ `utility_power` dựng bằng `invoice_power.yaml`).

**Cố tình KHÔNG viết 30 câu chuyện ràng buộc khác nhau** (30 lần suy luận
tay còn tệ hơn 1 lần, đúng bài học từ 3.5) — `_family()` sinh ràng buộc
GENERIC nhưng đúng logic đã dùng ở hai family thí điểm: bảng phức tạp
(`table == "grouped"`) → header phải nhường chỗ (`two_column`/`compact`);
nhiều chữ ký (`signature_count >= 3`) → layout phải xếp chồng (`stacked`/
`approval_chain`), nhánh `signature_layout` chỉ xuất hiện khi có ít nhất
một family-instance đạt ngưỡng đó. `party_block`/`table` chỉ xuất hiện khi
dữ liệu thật xác nhận block ấy có mặt — một family không có `table` trong
`sections:` thật thì KHÔNG có nhánh `table` (không phải nhánh có option
`"none"`, đúng bài học từ lỗi #1 ở 3.5).

**Số đo (task 3.2's DoD) — cả 30 family đều `cut > 0`:**

| Family | Thô | Sau ràng buộc | Cắt |
|---|---:|---:|---:|
| `invoice_detailed` | 1296 | 435 | 861 (66%) |
| `insurance_property_contract` | 972 | 560 | 412 (42%) |
| `hospital_bill`, `hotel_stay`, `insurance_application_form`, `insurance_fire_certificate`, `insurance_life_schedule`, `utility_power`, `utility_water`, `handover_record` | 432 | 288 | 144 (33%) |
| `export_invoice`, `form_sectioned`, `insurance_health_certificate`, `insurance_travel_certificate` | 216 | 144 | 72 (33%) |
| `authorisation_letter`, `cash_receipt_voucher`, `form_symmetric`, `leave_application`, `meeting_minutes` | 216 | 198 | 18 (8%) |
| `form_activity`, `form_roster` | 144 | 108 | 36 (25%) |
| `retail_vat_invoice` | 144 | 108 | 36 (25%) |
| `tax_invoice_en` | 144 | 96 | 48 (33%) |
| `dispatch_letter`, `form_checklist`, `form_dense`, `insurance_auto_certificate`, `insurance_cargo_policy`, `insurance_moto_certificate` | 108 | 99 | 9 (8%) |
| `insurance_health_id_card` | 72 | 66 | 6 (8%) |

Không family nào `cut == 0`. Test khoá lại toàn bộ:
`tests/test_grammar.py::test_every_family_has_a_real_not_decorative_constraint`
(chạy trên tất cả 30, không riêng 2 family cũ).

**Test mới** (7 test, cộng vào 14 test cũ, tổng 21):
`test_thirty_family_pass_plus_the_two_hand_reasoned_pilots`,
`test_every_family_traces_to_a_real_rulebase_source`,
`test_a_family_with_no_signature_data_gets_a_zero_floor_not_negative`,
`test_a_family_without_a_table_in_its_source_has_no_table_branch`,
`test_a_family_with_a_table_in_its_source_has_one`,
`test_a_family_with_no_parties_section_has_no_party_block_branch`,
`test_high_signature_count_families_get_a_layout_branch`,
`test_low_signature_count_families_skip_the_layout_branch`.

**Trạng thái tổng Phase 3:** 30 family — 2 hand-reasoned (đối chiếu ở 3.5)
+ 28 dựng từ dữ liệu (`_family()`, 3.6). Tất cả đã đo `space_size`, tất cả
`cut > 0`, tất cả có nguồn đối chiếu ghi trong `_SOURCE`. **Xong Phase 3.**
Task 2.3 ("validation pre-LLM: plan hợp lệ trước khi gọi model") giờ có đủ
điều kiện để làm ở Phase 4, đúng như đã hoãn.

---

## Phase 4 — Dynamic Planner + Diversity Sampler + Coverage Memory (đa tầng)

Tương ứng mục 4, 5, 13. Chỉ bắt đầu sau khi Phase 3 chứng minh được không
gian đủ lớn.

**Sửa theo review (điểm 2):** coverage không được là một tuple phẳng
(`family × density × table × layout`). Hai tài liệu có thể trùng cả bốn trục
đó mà vẫn khác hẳn về field composition hay component morphology — và tuple
phẳng sẽ không thấy sự trùng lặp đó. Coverage phải theo dõi **ba tầng**:

```text
coarse  -- family, density, table có/không
mid     -- component sequence, table morphology, layout topology
fine    -- field composition, component morphology chi tiết, hard-negative profile
```

| # | Task | File chính | DoD | Trạng thái |
|---|---|---|---|---|
| 4.1 | `DocumentPlan` là kết quả RÚT (sampled) qua grammar (Phase 3), không phải mẫu literal như YAML ví dụ mục 4 gốc — mỗi field trong plan có một phân bố, không một giá trị cố định cho cả family. **(điểm 4)** `hard_negative_profile` được rút TỪ danh sách compatibility mà grammar khai ở 3.4, không rút độc lập | `agent/document_plan.py` | Different plans must be reachable and sampled according to weighted distributions and coverage state; the sampler must not require every consecutive sample to be unique. "Plan sinh ra khác nhau giữa các lần gọi" nghĩa là **có khả năng** khác nhau qua weighted sampler + coverage memory ưu tiên vùng thiếu — KHÔNG phải ép mỗi lần gọi phải khác lần trước (forced novelty); rút lại một plan phổ biến vẫn hợp lệ nếu coverage/trọng số cho phép. hard-negative profile luôn tương thích với field/context đã rút | **Xong, đã kiểm 4 điểm review trước khi commit** — xem 4.1 dưới |
| 4.2 | Fingerprint tài liệu PHÂN TẦNG như trên (mục 13 gốc: family, component_sequence, table_morphology, density, layout_topology, hard_negative_profile...) | `agent/fingerprint.py` | fingerprint trả về ba tầng riêng biệt (coarse/mid/fine), không phải một hash/tuple duy nhất; tính được từ một `DocumentPlan` + kết quả render | **Xong** — `coarse`=(family, density, table/party_block có mặt hay không), `mid`=(table/header/signature_layout GIÁ TRỊ khi có mặt), `fine`=(toàn bộ assignment + hard_negative_profile, + `render_extra` khi có). `render_extra` là chỗ cắm sẵn cho tín hiệu sau vẽ — chưa có nguồn thật để gộp (Phase 5 mới có). Test: `tests/test_fingerprint.py` (8 test) |
| 4.3 | Coverage memory hoạt động ở **cả ba tầng**: đếm riêng theo coarse/mid/fine, ưu tiên tổ hợp thiếu ở tầng đang lệch nhất — **không ép unique**, theo đúng mục 5 | `agent/coverage.py` | test: hai plan trùng coarse+mid nhưng khác fine vẫn được coverage phân biệt; sampler ưu tiên đúng tầng đang thiếu, không chỉ tuple tổng | **Xong (đơn giản hoá có ghi chú)** — `CoverageMemory` giữ 3 `Counter` riêng; `priority()` trả `(coarse_count, mid_count, fine_count)`, so sánh **lexicographic** (coarse quyết trước, mid/fine chỉ phá hoà) thay vì dò "tầng nào đang lệch nhất" bằng thống kê động — đơn giản hơn yêu cầu gốc, nói rõ trong docstring, vẫn thoả đúng test cụ thể DoD nêu (coarse+mid trùng, fine khác → vẫn phân biệt được, ưu tiên đúng). `sample_with_coverage()` rút N candidate, giữ candidate priority thấp nhất — không ép unique (test xác nhận một giá trị phổ biến vẫn CÓ THỂ được rút lại). Test: `tests/test_coverage.py` (9 test) |
| 4.4 | Mở rộng round-robin rate-matching hiện có (G2: `wants_table`, `sheets`) thành một phần của sampler này thay vì cơ chế riêng lẻ — **giữ nguyên hành vi, không xoá** | `agent/rate_match.py` | `wants_table`/`sheets` logic chuyển vào sampler, hành vi rate-matching không đổi (test hồi quy tỉ lệ) | **Xong** — di chuyển byte-identical (không viết lại công thức), `agent/compose_page.py::wants_table` giờ là alias trỏ thẳng vào `agent/rate_match.wants_table` (`compose_page.wants_table is rate_match.wants_table`, test khoá lại). Test hồi quy so cả hai công thức cũ/mới trên 1000 index đầu — khớp tuyệt đối. Test: `tests/test_rate_match.py` (5 test) |

### 4.1 — Bốn điểm review kiểm trước khi commit

1. **`DocumentPlan` không chứa hidden template.** `grep` xác nhận: không có
   `INVOICE_PLANS = [...]` hay literal list plan nào trong
   `agent/document_plan.py`/`agent/grammar.py`. `sample()` dựng `assignment`
   branch-theo-branch qua `valid_options()`, theo thứ tự tô-pô
   (`_topological_order()`) — test `test_sample_builds_the_assignment_it_
   returns_not_a_literal`.
2. **Weight thuộc sampler, không thuộc grammar.** `Branch.__dataclass_
   fields__` chỉ có `name`/`options` — không có `weights=`. `weight_fn` là
   tham số của `sample()`, sống hoàn toàn trong `agent/document_plan.py`.
   Test khoá lại: `test_a_branch_carries_no_weight_field`.
3. **6 000 lần sample (30 family × 200) chỉ chứng minh sampler sinh plan
   hợp lệ, KHÔNG chứng minh coverage memory.** Không claim gì hơn thế —
   4.2/4.3 (fingerprint, coverage) chưa làm, đúng như review yêu cầu.
4. **"Different plans reachable" không phải forced novelty.** `grep` xác
   nhận không có `while ... == previous: resample()` nào trong
   `sample()`. Test `test_repetition_is_reachable_not_forbidden`: grammar
   2 lựa chọn, rút 30 lần, khẳng định CÓ lặp lại (`len(set(seen)) <
   len(seen)`) — nếu sampler cố tránh lặp, test này sẽ fail.

`tests/test_document_plan.py`: 14 test, cả 4 điểm trên đều có test khoá
lại trực tiếp, không chỉ khẳng định bằng lời.

**Phase 4 xong** — `agent/document_plan.py` (4.1), `agent/fingerprint.py`
(4.2), `agent/coverage.py` (4.3), `agent/rate_match.py` (4.4). 46 test mới
(14+8+9+5+... khớp tổng từng file). Chưa có gì trong bốn file này được GỌI
từ `agent/compose_page.py::one()` — track 3 vẫn chạy y nguyên như trước
Phase 1, LLM vẫn tự nghĩ cấu trúc dưới `page.md`. Nối `DocumentPlan` vào
brief thật là việc của Phase 5.

> **Cập nhật 24-09.** Câu "chưa có gì được GỌI" ở trên đúng tới Phase 5:
> Phase 5 nối `document_plan.py` + `rate_match.py` vào `one()`, nhưng
> `fingerprint.py` và `coverage.py` thì **vẫn** không ai gọi — `one()` rút
> plan bằng `DP.sample()` trần trên một RNG riêng cho từng `index`, tức mỗi
> tờ vẫn là một lần bốc độc lập không nhớ gì. `agent/diversity.py` (mục 7.4
> dưới) là người gọi còn thiếu ấy, và nó nối cả hai vào `run()` chứ không
> vào `one()`: trí nhớ phải dùng chung cho cả lô, mà `one()` chạy trong một
> luồng của `ThreadPoolExecutor`.

---

## Phase 5 — LLM Context động & giao thức Planner → LLM

Tương ứng mục 7, và phần "LLM là Realizer" ở mục 1. Đây là chỗ `page.md` và
`schema()` thật sự đổi.

**Sửa theo review (điểm 3):** engine's `DocumentPlan` (Phase 4) là
**authoritative**. LLM không được sinh một `plan` thứ hai rồi đem so hai
plan với nhau — nếu vậy thì rốt cuộc không ai là nguồn sự thật. Flow đúng:

```text
Engine DocumentPlan
        ↓
LLM (nhận plan, hiện thực hoá)
        ↓
HTML
        ↓
Validator so HTML trực tiếp với DocumentPlan của engine
```

không phải:

```text
Engine DocumentPlan → LLM tự tạo plan thứ hai → so hai plan
```

| # | Task | File chính | DoD | Trạng thái |
|---|---|---|---|---|
| 5.1 | Thiết kế lại `ask_for()`/brief để chèn `DocumentPlan` đã rút (Phase 4) thay vì để model tự nghĩ toàn bộ `plan` — nhưng vẫn để model tự do trong phạm vi plan CHO PHÉP (không khoá literal, tránh G1) | `agent/compose_page.py::ask_for()` | brief có đủ: document family, structure đã rút, density, table plan, layout plan, field plan, hard-negative plan (từ 3.4/4.1) | **Xong** — `one()` rút `plan = DP.sample(G.FAMILIES[family], rng)` (family quay vòng qua 30 family, RNG = `seed+index`, an toàn song song); `ask_for()` nhận `plan`, gọi `describe_plan()` mới để đưa family/density/table/party_block/signature/hard-negative vào brief; `table`/`doc_slug` không còn hỏi model (`table = "table" in plan.assignment`, `kind = plan.family`) |
| 5.2 | `schema()` đổi theo: nếu `plan` vẫn còn trong structured output (lý do protocol/debug — `reasoning` đang hữu ích), nó đổi vai trò thành **execution summary / realization metadata**, KHÔNG authoritative, KHÔNG dùng để validate. Validator (Phase 2) so trực tiếp HTML/`data-path` sinh ra với `DocumentPlan` gốc của engine | `agent/compose_page.py::schema()` | test: model lệch `DocumentPlan` gốc bị `PLAN_VIOLATION` bắt được bằng cách so HTML thật với plan gốc — không qua trung gian "plan model tự khai lại" | **Xong** — biến cục bộ đổi tên `plan`→`declared` (model tự khai) vs `plan` (DocumentPlan engine, biến khác hẳn) để không lỡ tay lẫn lộn; `plan_conformance_problems(plan, html)` mới so HTML thật với 2 sự kiện nhị phân của engine plan (có bảng hay không qua `<table>` thật; có chữ ký hay không qua `data-kind` bắt đầu `sign.`) — không đọc `declared` chút nào. `schema()`'s docstring viết lại nói rõ vai trò mới. 8 test trong `tests/test_plan_conformance.py` |
| 5.3 | Cập nhật `page.md`: bỏ phần dạy model "tự phát minh cấu trúc từ đầu" (mục 2-4 hiện tại của `page.md`), thay bằng "hiện thực hoá plan được đưa, trong phạm vi cho phép"; nói rõ `plan` (nếu còn trong schema) chỉ là tóm tắt việc đã làm, không phải nơi model tự quyết cấu trúc | `agent/prompts/page.md` | không còn mâu thuẫn giữa prompt và schema mới; không còn câu nào ngụ ý model "tự nghĩ" cấu trúc từ đầu | **Xong (rà theo trọng điểm, không tuyên bố quét hết 1885 dòng)** — viết lại mục 1-4 (input context, "REALIZE không INVENT", diversity là việc content không phải structure, tránh trùng lặp là việc content không phải structure) đúng 4 mục DoD nêu; quét thêm bắt được 3 chỗ mâu thuẫn khác không nằm trong phạm vi gốc: mục 19 (TABLES — sự có/không của bảng giờ cố định, chỉ còn quyết morphology), mục 24 (LAYOUT — phân biệt CSS-level với structural fact đã cố định), mục 55 (AVOIDING PREVIOUSLY USED STRUCTURES — viết lại thành việc content, structure là việc coverage sampler Phase 4.3) |
| 5.4 | Đo lại token/giây sau khi context động (thường DÀI hơn vì có plan cụ thể) — theo `docs/kiem-soat-llm.md`, prefill không chậm decode đáng kể, nhưng vẫn phải đo lại không suy đoán | — | số đo mới ghi vào `docs/kiem-soat-llm.md` | **BLOCKED** — xem 5.5 dưới, không phải "chưa làm", mà không làm được lúc này vì một phụ thuộc dùng chung đang hỏng |

### 5.5 — Chặn 5.4: `synthgen/llm_page.py::kinds()` hỏng do việc song song trên `synthgen/`

Không phải do phần việc Phase 1-5 ở đây. Phát hiện khi chạy
`tests/test_plan_conformance.py` mới viết: `kinds()` (dùng trong
`ask_for()` để liệt kê từ vựng `data-kind`, và trong `problems()` để gác
cổng) ném `KeyError: 'table'` — `synthgen/markup.py::markup()` tra
`_BUILDERS['table']` cho một khối KHÔNG chảy (head/tail), nhưng `'table'`
chỉ có trong `FLOW_BUILDERS`, không có trong `_BUILDERS`. Xác nhận bằng
`git status`: `synthgen/design.py` (+273/-51 dòng), `synthgen/archetypes.py`,
`synthgen/markup.py`, `synthgen/content.py`, `synthgen/corpus.py`,
`synthgen/draw.py`, `synthgen/overlay.py`, `synthgen/paginate.py`,
`synthgen/phrasing.py`, `synthgen/run.py` đều đang sửa dở (không phải của
phiên này) — rất có thể một archetype mới cho phép `table` xuất hiện ở vị
trí head/tail mà `markup.py` chưa theo kịp.

**Tác động đo được:** chạy `pytest tests/` toàn bộ lúc phát hiện — hàng
trăm test hỏng, trải khắp `test_sheets.py`, `test_signature.py`,
`test_spec.py`, và cả những test Phase 1-2 TỪNG QUA (`test_llm_page.py`,
`test_failures.py`) giờ cũng hỏng vì cùng một `KeyError` — không phải hồi
quy do phần việc ở đây, `git diff` xác nhận các file Phase 1-2 không đổi
từ lúc chúng còn qua. Đây là lỗi TẠM THỜI trên cây làm việc dùng chung,
không phải lỗi trong bất kỳ commit nào ở nhánh Phase 1-5.

**Vì sao không tự sửa:** `synthgen/markup.py`/`synthgen/design.py` đang có
người sửa dở (không phải phiên này) — sửa đè lên sẽ đụng đúng việc đang
làm. Test mới của Phase 5 (`tests/test_plan_conformance.py`) đã cô lập
khỏi lỗi này bằng cách giả lập `kinds()` (`monkeypatch`), nên chạy sạch
độc lập với tình trạng `synthgen/`; các test Phase 1-2 thì KHÔNG cô lập
được theo cách đó (chúng đang kiểm chính `problems()`/`kinds()` thật), nên
tạm thời đỏ cho tới khi việc kia xong.

5.4 (đo token/giây) cần một lượt gọi LLM thật qua trọn `agent.compose_page`
— vô nghĩa khi chạy lúc `kinds()` đang hỏng (mọi trang sẽ hỏng ở cổng
trước khi kịp đo gì). Hoãn tới khi `synthgen/` ổn định lại.

---

## Phase 6 — Hard-negative system thật (implementation; compatibility đã khai từ Phase 3-4)

Tương ứng mục 12. Audit xác nhận: **không tồn tại trong code**, chỉ là văn
xuôi trong `page.md`/`SYSTEM_PROMPT.md`.

**Sửa theo review (điểm 4):** *biết field/context nào hợp lệ với
hard-negative strategy nào* đã xong ở 3.4 (grammar khai compatibility) và
4.1 (planner rút `hard_negative_profile` tương thích). Phase 6 chỉ còn phần
implementation — record type, gate, test — không phải thiết kế lại từ đầu.

| # | Task | File chính | DoD |
|---|---|---|---|
| 6.1 | Đưa `hard_negative_profile` (đã có trong `DocumentPlan` từ 4.1) vào brief LLM đọc được | `agent/compose_page.py::ask_for()` (Phase 5.1) | brief liệt kê rõ strategy nào áp dụng cho field nào, lấy từ compatibility của 3.4 |
| 6.2 | `HardNegativeRecord` (target_kind, negative_kind, strategy, path) — role trong `FieldRecord` (Phase 1) phải phân biệt được `hard_negative` khỏi `positive`/`ordinary` | `pipeline/fields.py` | test: hard negative có box, không có mặt trong danh sách positive KIE |
| 6.3 | Gate: không cho hard-negative bị gán cùng `data-kind` VÀ cùng vai trò positive như target thật trên cùng brief | `synthgen/llm_page.py::problems()` | test hồi quy mục "39 Hard-negative regression" |

**Xong cả ba.**

- **6.1** đã thoả từ Phase 5.1 (`describe_plan()` liệt kê `hard_negative_profile` khi khác rỗng) — không cần đổi gì thêm, chỉ xác nhận lại ở đây.
- **6.2** — quy ước HTML mới: model tự khai mồi giả bằng `data-decoy-for="<target-kind>"` trên chính span mồi (cùng tinh thần `data-path` — model khai, không ai suy). `synthgen/kie_full.py::hard_negative_spans[_all]` đọc thuộc tính ấy, ghép với thực thể theo đúng khuôn `declared_pairs` (`zip`, thứ tự DOM). `pipeline/fields.py::HardNegativeRecord` (target_kind, negative_kind, strategy, path, value, entity_index) + `from_hard_negative()` đổi sang `FieldRecord(role=HARD_NEGATIVE, kind=target_kind, ...)`. `registry()` nhận thêm tham số `hard_negatives=` (mặc định `None`, không đổi hành vi cũ) — thứ tự ưu tiên theo hộp: pair KIE thật thắng mồi giả thắng entity suy thô, để một hộp lỡ mang cả hai không làm mất một giá trị KIE có thật. `strategy` lấy từ `DocumentPlan.hard_negative_profile` khi `target_kind` khớp, `""` nếu model khai một decoy engine không lường trước (vẫn hợp lệ).
- **6.3** — gate mới trong `problems()`: từ chối một span vừa khai `data-decoy-for="X"` vừa tự mang `data-kind="X"` (mồi giả tự nhận luôn là chính target, tức chỉ còn là một positive khai hai lần). Không đụng `generators/html/page.py` (JS đo chung, không sửa) — toàn bộ nằm ở Python post-process, giống `data-path`.
- `agent/prompts/page.md` mục 11.1 (mới) dạy model cách viết `data-decoy-for`; mục 60 cập nhật theo.
- Test: `tests/test_hard_negatives.py` (9 test, kie_full + gate llm_page, dùng lại khuôn `monkeypatch` stub `kinds()` của `tests/test_plan_conformance.py` vì cùng bị Phase 5.5 chặn), `tests/test_fields.py` (+5 test cho `HardNegativeRecord`/`from_hard_negative`/`registry(hard_negatives=)`). Toàn bộ dependency-free suite (trừ `test_failures.py`, vẫn chặn bởi Phase 5.5, không phải lỗi Phase 6) chạy sạch.

---

## Phase 7 — Tách Document Diversity khỏi Dressing Diversity; mở rộng Distance

Tương ứng mục 6, 14. `agent/distance.py` hiện **chỉ đo dressing** (hình học,
track 1, không chạy được trên track 3 — xác nhận từ audit).

| # | Task | File chính | DoD |
|---|---|---|---|
| 7.1 | Giữ nguyên `agent/distance.py` cho dressing distance (đừng thay, extend) | — | không có regression trên track 1 |
| 7.2 | Viết document-diversity distance riêng, đọc fingerprint từ Phase 4.2, không đọc hình học | file mới | test mục 49 (tư duy gốc): 1 document × 100 dressing ≠ 100 document diversity |
| 7.3 | Corpus report tách hai loại diversity ra hai bảng số khác nhau | `tools/` script từ Phase 2.4 | báo cáo có hai section riêng |

**Xong cả ba.**

- **7.1** — không sửa một dòng nào của `agent/distance.py` (`git status` xác
  nhận file sạch suốt Phase 7). Track 1 không có regression từ phía tôi;
  các test track 1 đang FAIL hôm nay (`test_sheets.py`/`test_signature.py`/
  `test_spec.py`, `ModuleNotFoundError`) là việc của nhánh `synthgen/`
  đang sửa song song, không liên quan `agent/distance.py`.
- **7.2** — `agent/document_distance.py` (mới): `distance(a, b)` giữa hai
  `Fingerprint` = số tầng (coarse/mid/fine) khác nhau chia 3 -- không dùng
  trọng số tự chọn, cùng tinh thần `agent/coverage.py` đã chọn thứ tự từ
  điển thay vì tổng có trọng số. `corpus_diversity(fingerprints)` gộp một
  lô: distinct-coarse/mid/fine cộng khoảng cách trung bình theo cặp.
  `tests/test_document_distance.py::
  test_one_document_rendered_a_hundred_ways_is_zero_document_diversity`
  khoá đúng mục 49: fingerprint của CÙNG một `DocumentPlan` không đổi dù
  gọi lại bao nhiêu lần (dressing không đụng `assignment`), trong khi
  100 document THẬT SỰ khác nhau (family khác nhau) đo được diversity > 0
  rõ rệt -- hai trục tách nhau vì cấu trúc code, không phải vì quy ước.
- **7.3** — `tools/llm/corpus_stats.py` thêm `document_diversity` (gọi
  `agent.document_distance.corpus_diversity` trên `Fingerprint` dựng lại từ
  `engine_plan`/`hard_negative_profile` mỗi trang trong `compose_report.
  json` -- không cần `DocumentPlan` gốc) và `hard_negative_coverage`
  (Phase 6: bao nhiêu trang engine HỎI có mồi giả so với bao nhiêu trang
  model THỰC SỰ khai `data-decoy-for`). Đổi tên `not_measurable_yet` ->
  `not_measurable_here`: những khái niệm Phase 3/4/6 hứa trước đây giờ đo
  được rồi, chỉ còn thứ cần ảnh đã vẽ (`synthgen/check.py`, để Phase 8) hoặc
  không áp dụng cho track 3 (dressing diversity) là thật sự ngoài script
  này. Test: `tests/test_document_distance.py` (10 test), `tests/
  test_corpus_stats.py` (+6 test cho hai bảng mới).

---

### 7.4 — Nối coverage + fingerprint vào lượt sinh, và thêm tầng hình học (24-09)

Hai file của Phase 4.2/4.3 viết xong, có test, và **không chỗ nào gọi**.
Mục này là người gọi, cộng một tầng dấu vân thứ hai mà Phase 4 nói là "chưa
có nguồn thật để gộp" (`render_extra`).

| file | việc |
| --- | --- |
| `agent/fingerprint.py` | thêm `geometry_fingerprint()` — lưới 8×12 trên `layout_annotations` ĐÃ VẼ |
| `agent/geometry_distance.py` | mới — Jaccard (quyết) + Hamming (ghi), cửa sổ trượt, `corpus_geometry()` |
| `agent/diversity.py` | mới — `DiversityWarden`: trí nhớ dùng chung cả lô, an toàn nhiều luồng |
| `synthgen/draw_llm.py` | `Drawer.measure()` — dàn trang chỉ để đo, không ghi tệp nào |
| `agent/compose_page.py` | `Artist` nhận thêm việc ĐO; `run()` rút plan qua warden và sinh lại tờ trùng |
| `tools/llm/diversity_report.py` | mới — đo lại từ `records/` trên đĩa, so hai lô |

**Vì sao cần tầng hình học, đo được:** trên 94 tài liệu `data/pilot16` +
`data/pilot17` (4 371 cặp), ba cặp trang giống nhau nhất là

    J=0.895  handover_record_0010   vs  invoice_detailed_0023
    J=0.891  form_roster_0007       vs  invoice_detailed_0023
    J=0.858  form_roster_0007       vs  handover_record_0010

và `agent/document_distance.py::distance` chấm cả ba là **1.000 — khác nhau
tối đa**, vì chúng thuộc ba family khác nhau. Dấu vân plan mù với chuyện này
theo đúng thiết kế (7.2: "không đọc hình học"), nên câu trả lời là một dấu
vân thứ hai với trí nhớ riêng, **không** phải nhét hình học vào `fine` qua
`render_extra` — làm thế thì mọi fingerprint đã quan sát không bao giờ khớp
`fine` của một ứng viên (ứng viên rút TRƯỚC khi vẽ), và phép phá hoà
coarse/mid/fine của `coverage.py` chết lặng lẽ.

**Ngưỡng:** Jaccard ≥ 0,60 trong cửa sổ 24 tờ. Đo trên cùng 94 tài liệu:
ngưỡng 0,70 chỉ bắt 4/94 (4,3%), 0,50 bắt 24/94 (25,5%), 0,60 bắt 14/94
(14,9%). Hamming **không gác**: cả 38 cặp vượt ngưỡng Jaccard đều đã có
Hamming ≤ 0,240, còn 30,7% số cặp KHÔNG trùng cũng có Hamming ≤ 0,25 — một
điều kiện chưa bao giờ đổi được quyết định thì không được viết như thể nó
đổi (AGENTS.md mục 5).

---

## Phase 8 — Tổng kết & kiểm tra ở quy mô

Tương ứng mục 18-20 và "Final Report" trong bản coding-agent task trước đó.

| # | Task | DoD |
|---|---|---|
| 8.1 | Sinh một batch đủ lớn (không phải 1 mẫu) trải nhiều family/density/table morphology | batch sinh ra, lưu lại |
| 8.2 | So trước/sau: missing-box rate, text/table confusion rate, duplicate/near-duplicate rate, hard-negative coverage | số đo ghi vào `docs/kiem-soat-llm.md`, có bảng trước/sau |
| 8.3 | Viết báo cáo cuối theo đúng khung mục 61 của bản coding-agent task (architecture, files changed, root cause box/table, diversity, hard negatives, memory, metrics) | báo cáo mới trong `docs/` |

---

## Thứ tự khuyến nghị và vì sao

```text
Phase 1 (Field Registry)   -- có bug thật, ít rủi ro thiết kế
Phase 2 (Validation/taxonomy) -- cần trước để đo được mọi phase sau
Phase 3 (Grammar space)    -- CHỈ THIẾT KẾ, rủi ro G1 cao nhất
Phase 4 (Planner/Sampler)  -- phụ thuộc Phase 3 đã chứng minh không collapse
Phase 5 (LLM context/schema) -- phụ thuộc Phase 4 có plan để đưa vào brief
Phase 6 (Hard negatives)   -- lồng vào Phase 4-5, làm sau khi khung đã ổn
Phase 7 (Distance/diversity split) -- cần fingerprint từ Phase 4
Phase 8 (Đo & báo cáo)     -- luôn cuối cùng
```

Không bắt đầu bằng sửa `page.md` (đúng câu cuối trong tư duy gốc) — `page.md`
chỉ đổi thật ở Phase 5, sau khi Planner đã tồn tại để nó có gì mà "hiện thực
hoá".
