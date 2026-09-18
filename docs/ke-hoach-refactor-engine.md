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

**Kiểm tra live LLM:** người dùng cho phép gọi thẳng LLM để test (2026), nhưng
`curl` tới `127.0.0.1:8000`/`127.0.0.1:11434` bị từ chối kết nối ngay (không
phải treo/timeout) — dấu hiệu không có server nào đang chạy ở máy này lúc
này, không phải sandbox chặn (chặn thường treo, không từ chối ngay). Chưa
kiểm được toàn bộ pipeline với `page.md`/`SYSTEM_PROMPT.md` mới bằng dữ liệu
thật sinh MỚI; mọi số đo Phase 1 ở trên đều trên dữ liệu CŨ (`pilot10`/`12`,
sinh dưới `page.md` cũ). Cần người dùng khởi động server
(`vllm serve ... --port 8000` hoặc `ollama serve`, xem `agent/README.md`)
để chạy `python -m agent.compose_page --want N` thật cho Phase 2 trở đi.

---

## Phase 2 — Failure taxonomy & validation nhiều tầng

**Vì sao làm sớm:** cần có trước để đo "trước/sau" cho mọi phase tiếp theo,
không phải để trước cho đẹp. Tương ứng mục 15, 16.

| # | Task | File chính | DoD |
|---|---|---|---|
| 2.1 | Liệt kê failure code hiện có (`synthgen/llm_page.py::problems`, `plan_problems`, `sheet_plan_problems`, `synthgen/check.py`) và map sang taxonomy mục 16 | các file trên | bảng đối chiếu code cũ ↔ taxonomy mới |
| 2.2 | Thêm code còn thiếu: `MISSING_DATA_PATH`, `DUPLICATE_DATA_PATH`, `KIE_FALSE_POSITIVE`/`NEGATIVE`, `PLAN_VIOLATION`, `DIVERSITY_COLLAPSE` | `synthgen/llm_page.py`, nơi Field Registry (Phase 1) sống | mỗi lần reject có đúng một code, machine-readable |
| 2.3 | Validation pre-LLM (plan hợp lệ trước khi gọi model) — hiện không tồn tại vì model tự nghĩ hết; chỉ áp dụng sau khi có Planner (Phase 3-4) | — | hoãn tới Phase 4, ghi chú ở đây để không quên |
| 2.4 | Corpus-level stats: tần suất family/structure/table morphology/density/hard-negative, duplicate rate | script mới dưới `tools/` | chạy được trên một batch đã sinh, ra báo cáo |

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

| # | Task | File chính | DoD |
|---|---|---|---|
| 3.1 | Viết grammar cho 3-5 document family thí điểm dưới dạng cây tuỳ chọn CÓ ràng buộc điều kiện giữa nhánh (như ví dụ trên) | file mới, ví dụ `agent/grammar.py` | **"Grammar must define a compositional constraint space with conditional dependencies, rather than a finite Cartesian product of predefined visual variants."** Mỗi family có ít nhất một ràng buộc nối hai nhánh trở lên — liệt kê nhánh độc lập không tính là đạt |
| 3.2 | Đếm kích thước không gian tổ hợp SAU khi áp ràng buộc (không phải tích Descartes thô trước ràng buộc) | cùng file | số liệu ghi vào docstring/doc: tổng tổ hợp thô, tổ hợp còn lại sau ràng buộc, và tổ hợp bị loại — chứng minh ràng buộc thật sự cắt bớt không gian phẳng chứ không chỉ trang trí |
| 3.3 | Grammar phải xuất được **constraint**, không phải giá trị cụ thể — plan cụ thể do sampler (Phase 4) rút ra khỏi grammar bằng trọng số + giải ràng buộc, không phải grammar tự ấn định | cùng file | grammar không có nhánh nào bị hard-code một giá trị duy nhất |
| 3.4 | **(điểm 4)** Grammar khai luôn hard-negative-compatible strategies cho từng field/context — field nào hợp lý với decoy dạng lexical/format/contextual/..., field nào không | cùng file | mỗi field trong field vocabulary có (có thể rỗng) danh sách strategy hợp lệ; Phase 4.1 đọc trực tiếp danh sách này khi rút `hard_negative_profile`, không đợi Phase 6 mới nghĩ tới |

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

| # | Task | File chính | DoD |
|---|---|---|---|
| 4.1 | `DocumentPlan` là kết quả RÚT (sampled) qua grammar (Phase 3), không phải mẫu literal như YAML ví dụ mục 4 gốc — mỗi field trong plan có một phân bố, không một giá trị cố định cho cả family. **(điểm 4)** `hard_negative_profile` được rút TỪ danh sách compatibility mà grammar khai ở 3.4, không rút độc lập | file mới, ví dụ `agent/document_plan.py` | Different plans must be reachable and sampled according to weighted distributions and coverage state; the sampler must not require every consecutive sample to be unique. "Plan sinh ra khác nhau giữa các lần gọi" nghĩa là **có khả năng** khác nhau qua weighted sampler + coverage memory ưu tiên vùng thiếu — KHÔNG phải ép mỗi lần gọi phải khác lần trước (forced novelty); rút lại một plan phổ biến vẫn hợp lệ nếu coverage/trọng số cho phép. hard-negative profile luôn tương thích với field/context đã rút |
| 4.2 | Fingerprint tài liệu PHÂN TẦNG như trên (mục 13 gốc: family, component_sequence, table_morphology, density, layout_topology, hard_negative_profile...) | file mới hoặc `agent/distance.py` (extend, không thay) | fingerprint trả về ba tầng riêng biệt (coarse/mid/fine), không phải một hash/tuple duy nhất; tính được từ một `DocumentPlan` + kết quả render |
| 4.3 | Coverage memory hoạt động ở **cả ba tầng**: đếm riêng theo coarse/mid/fine, ưu tiên tổ hợp thiếu ở tầng đang lệch nhất — **không ép unique**, theo đúng mục 5 | file mới | test: hai plan trùng coarse+mid nhưng khác fine vẫn được coverage phân biệt; sampler ưu tiên đúng tầng đang thiếu, không chỉ tuple tổng |
| 4.4 | Mở rộng round-robin rate-matching hiện có (G2: `wants_table`, `sheets`) thành một phần của sampler này thay vì cơ chế riêng lẻ — **giữ nguyên hành vi, không xoá** | `agent/compose_page.py` | `wants_table`/`sheets` logic chuyển vào sampler, hành vi rate-matching không đổi (test hồi quy tỉ lệ) |

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

| # | Task | File chính | DoD |
|---|---|---|---|
| 5.1 | Thiết kế lại `ask_for()`/brief để chèn `DocumentPlan` đã rút (Phase 4) thay vì để model tự nghĩ toàn bộ `plan` — nhưng vẫn để model tự do trong phạm vi plan CHO PHÉP (không khoá literal, tránh G1) | `agent/compose_page.py::ask_for()` | brief có đủ: document family, structure đã rút, density, table plan, layout plan, field plan, hard-negative plan (từ 3.4/4.1) |
| 5.2 | `schema()` đổi theo: nếu `plan` vẫn còn trong structured output (lý do protocol/debug — `reasoning` đang hữu ích), nó đổi vai trò thành **execution summary / realization metadata**, KHÔNG authoritative, KHÔNG dùng để validate. Validator (Phase 2) so trực tiếp HTML/`data-path` sinh ra với `DocumentPlan` gốc của engine | `agent/compose_page.py::schema()` | test: model lệch `DocumentPlan` gốc bị `PLAN_VIOLATION` bắt được bằng cách so HTML thật với plan gốc — không qua trung gian "plan model tự khai lại" |
| 5.3 | Cập nhật `page.md`: bỏ phần dạy model "tự phát minh cấu trúc từ đầu" (mục 2-4 hiện tại của `page.md`), thay bằng "hiện thực hoá plan được đưa, trong phạm vi cho phép"; nói rõ `plan` (nếu còn trong schema) chỉ là tóm tắt việc đã làm, không phải nơi model tự quyết cấu trúc | `agent/prompts/page.md` | không còn mâu thuẫn giữa prompt và schema mới; không còn câu nào ngụ ý model "tự nghĩ" cấu trúc từ đầu |
| 5.4 | Đo lại token/giây sau khi context động (thường DÀI hơn vì có plan cụ thể) — theo `docs/kiem-soat-llm.md`, prefill không chậm decode đáng kể, nhưng vẫn phải đo lại không suy đoán | — | số đo mới ghi vào `docs/kiem-soat-llm.md` |

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

---

## Phase 7 — Tách Document Diversity khỏi Dressing Diversity; mở rộng Distance

Tương ứng mục 6, 14. `agent/distance.py` hiện **chỉ đo dressing** (hình học,
track 1, không chạy được trên track 3 — xác nhận từ audit).

| # | Task | File chính | DoD |
|---|---|---|---|
| 7.1 | Giữ nguyên `agent/distance.py` cho dressing distance (đừng thay, extend) | — | không có regression trên track 1 |
| 7.2 | Viết document-diversity distance riêng, đọc fingerprint từ Phase 4.2, không đọc hình học | file mới | test mục 49 (tư duy gốc): 1 document × 100 dressing ≠ 100 document diversity |
| 7.3 | Corpus report tách hai loại diversity ra hai bảng số khác nhau | `tools/` script từ Phase 2.4 | báo cáo có hai section riêng |

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
