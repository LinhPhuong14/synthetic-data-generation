# Bản đồ kho — `vlm-ocr-synthetic` làm gì, và cái hộp sinh ra ở đâu

> Ghi ngày 17-09-2026, đọc thẳng từ cây thư mục và từ hai bộ dữ liệu mới nhất
> (`data/pilot9`, `data/test1`). Mọi con số dưới đây là đo, không chép lại.
> Đây là **bản đồ hiện trạng** để vào buổi bàn về logic sinh hộp cho KIE —
> phần "vì sao" nằm ở [`muc-tieu.md`](muc-tieu.md), phần "ai sở hữu toạ độ"
> nằm ở [`duong-ong.md`](duong-ong.md).

---

## 1. Một câu

Kho này **không huấn luyện mô hình nào**. Nó là một **bộ sinh**: từ một hạt
giống (hoặc từ một lượt gọi LLM) dựng ra ảnh chứng từ Việt Nam **kèm nhãn khớp
pixel** — chữ gì, nằm ở hộp nào, thuộc trường nào, và tờ giấy là loại gì — để
đem đi huấn luyện VLM/OCR/KIE ở nơi khác.

Nguyên tắc chịu lực nhất của cả kho: **hộp do engine đã dàn chữ sinh ra, không
bao giờ do mô hình đoán, và sinh một lần rồi chỉ *biến đổi* chứ không *đo lại***.

---

## 2. Hai đường sinh, không phải một

| | **Đường A — luật** | **Đường B — LLM** |
| --- | --- | --- |
| Vào | `seed` + 11 thuộc tính bốc từ `rulebase/rules/*.yaml` | phôi trong `rulebase/synthgen/*.yaml` + model viết nội dung & HTML |
| Dàn trang | `rulebase/layout.py` → `generators/html/sheets/*.py` | `synthgen/design.py` + `synthgen/markup.py` (hoặc HTML model tự viết) |
| Điều phối | `pipeline/run.py` (shard, song song, resume được) | `synthgen/run.py`, `synthgen/draw_llm.py` |
| Cổng gác | `pipeline/preflight.py`, `pipeline/invariants.py` | `synthgen/llm_page.py`, `synthgen/repair.py` |
| Bộ ra mới nhất | `data/09-09-26-*`, `data/14-09-test*` | **`data/pilot9`, `data/test1`** |
| Loại giấy | 118 file YAML trong `rulebase/layouts/`, 47 `rulebase/documents/` | 63 phôi trong `rulebase/synthgen/` |

Cả hai đường **đổ về cùng một bản ghi** (`pipeline/record.py`, 2 598 dòng) —
nên nhãn của một trang model viết và một trang luật vẽ đọc lên giống hệt nhau.

Chỗ vẽ pixel chỉ có một: **Chromium qua Playwright**. Hộp đọc từ chính DOM vừa
dàn, không từ một bộ dò nào.

---

## 3. Bản đồ thư mục

| thư mục | việc | file trụ cột |
| --- | --- | --- |
| `rulebase/` | *Tờ giấy nói gì* — 11 thuộc tính có trọng số, nội dung, lưới ô chữ | `spec.py`, `content.py` (1 727 d), `layout.py` (1 449 d) |
| `generators/html/` | *Tờ giấy trông thế nào* — CSS thật, chụp, đọc hộp từ DOM | `render.py`, `page.py`, `sheets/*.py` |
| `synthgen/` | Bộ sinh soạn mới cho chứng từ hành chính, **có cả nhánh LLM** | `markup.py` (1 432 d), `draw.py`, `kie_full.py`, `export.py` |
| `agent/` | Mô hình **chọn tham số / soạn phôi / soạn trang**, không vẽ pixel | `planner.py`, `compose_layout.py` (2 317 d), `critic.py` |
| `degradation/` | 26 mô hình làm cũ (DocCreator, Augraphy, tự viết) + warp Blender | `pipeline.py`, `warp.py` |
| `pipeline/` | Một lượt chạy: khai báo → shard → chạy → kiểm → ghi | `record.py`, `invariants.py` (855 d), `kie.py` |
| `tools/` | Việc lẻ: kiểm hộp, OCR chấm ngược, gallery, backfill KIE | `check_boxes.py`, `ocr_proof.py`, `kie_backfill.py` |
| `tests/` | 48 file test, chạy được chỉ với `pytest` + `pyyaml` | `test_kie.py`, `test_synthgen_kie.py`, `test_record.py` |
| `docs/` | **Thiết kế, không phải hiện thực** — 27 tài liệu `.md` | `muc-tieu.md`, `duong-ong.md`, `ke-hoach.md` |
| `data/` | Bộ đã sinh. Nặng: hai bộ tháng 9 chiếm 40 G và 43 G | `pilot9/`, `test1/` |

Điểm vào duy nhất cho mọi việc: **`tasks.py`** (`make` chỉ là vỏ bọc mỏng).

---

## 4. Bốn tầng nhãn của một trang — chỗ quyết định mọi thứ về KIE

Một bản ghi (`records/*.json`, `schema_version: 8`) mang **bốn hạt nhãn khác
nhau cho cùng một chỗ mực**. Số trong ngoặc là một tờ biên bản thật:

| tầng | hạt | một phần tử là | có gì về hình học |
| --- | ---: | --- | --- |
| `layout_annotations` | 13 | một **vùng** (19 nhãn lớp: Text, Table, Watermark…) | `bbox` |
| `blocks` | 54 | một **dòng** của một run | `bbox`, `quad` |
| `word_annotations` | 404 | một **từ** | `bbox`, `polygon` (4 góc, đã theo warp) |
| `entity_annotations` | 45 | **cả run** — trường là chuỗi trọn vẹn | `bbox` (bao ngoài), **`lines`** (hộp từng dòng), `key_entity_index` |
| `kie.pairs` | 17 | một **cặp khoá–giá trị** | `key_bbox`, `value_bbox` — *mỗi bên đúng một hình chữ nhật* |

> **Hệ toạ độ: 0..1000.** Mọi `bbox`, `polygon`, `quad`, `lines` và khoá
> `*_bbox` là PHẦN NGHÌN của cạnh tờ giấy (`bbox_mode: "xyxy_per_mille"`).
> Số pixel đo được nằm ở khoá `*_px` bên cạnh. Phép chuyển ở đúng một chỗ:
> `pipeline/record.py::to_per_mille`. Khoá `bbox_1000` của bản cũ đã bỏ —
> `bbox` chính là nó.

Hai điều đáng nhớ trước khi bàn:

1. **Entity đã giữ `lines`** — run xuống dòng thì hộp bao ngoài của nó ôm cả
   giấy trắng ở hai đầu so le, nên `record.py` giữ thêm hộp từng dòng. Nhưng
   `kie.pairs` **làm phẳng mất `lines`**: chỉ còn một `value_bbox` duy nhất.
2. **`bbox_strategy: visible_content_perimeter`** — hộp là chu vi mực nhìn
   thấy, và sau warp thì `polygon` mới là hình thật, `bbox` chỉ là bản tóm
   tắt vuông góc trục.

Toạ độ xuất ra ngoài (`json/`) đổi sang **lưới 0–1000**: `round(x / bề_rộng × 1000)`.

---

## 5. Vòng đời một cái hộp

```
Chromium dàn chữ  →  đọc rect từ DOM  →  làm cũ (KHÔNG đổi kích thước)
      →  warp (chiếu lại 4 góc từng hộp)  →  thu nhỏ ảnh (hộp co theo)
      →  record.validate + invariants  →  .json
```

Không chặng nào **đo lại** hộp. Đó là lý do nhãn khớp pixel theo định nghĩa,
chứ không theo may rủi.

---

## 6. KIE hôm nay: hai file, bốn nguồn cặp

| file | lo phần nào |
| --- | --- |
| [`pipeline/kie.py`](../pipeline/kie.py) | cặp có **nhãn in ngay trước giá trị** (`source: label`), và câu tả cho từng trường (4 nguồn: `llm` → `caption` → `kind` → `label`) |
| [`synthgen/kie_full.py`](../synthgen/kie_full.py) | phần còn lại: **ô bảng** (khoá = tiêu đề cột, `source: table`), **cặp theo luật** (`total.group`, `checks`), **ghép mồ côi cùng họ** (`source: family`), và **trường không có nhãn in** (`source: implied`, `key_bbox = null`) |

Đo trên hai bộ mới nhất:

| bộ | bản ghi | cặp | `label` | `table` | `implied` | phủ thực thể |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/pilot9` (16-09, 15:17) | 25 | 1 024 | 181 | 573 | 270 | 0,684 TB (0,19–0,96) |
| `data/test1` (mới hơn) | 32 | 1 199 | 235 | 727 | 237 | 0,623 TB (0,23–0,95) |

Một khác biệt đáng chú ý giữa hai bộ: trong `pilot9` **cả 573 cặp bảng đều có
`key_bbox = null` và `column_path = []`** — tiêu đề cột không gắn được. Trong
`test1` thì **727/727 cặp bảng có đủ `key_bbox`**. Không phải lỗi đang sống:
`pilot9` ghi lúc 15:17 ngày 16-09, còn commit `12ee1340` *"tên cột lấy từ tiêu
đề in trên giấy"* là 17:26 cùng ngày. `pilot9` sinh trước bản vá.

Hai commit mới nhất (`12ee1340`, `80f69a6e`) đều nằm trên đường KIE: tên cột
lấy từ tiêu đề in trên giấy chứ không từ bảng tra; nửa-khoá thôi thành trường;
`sign.title ↔ sign.name` ghép theo họ; **ô trải nhiều cột là nhãn của cả dòng**,
không phải giá trị của cột đầu tiên nó chạm (13/32 tài liệu dính, còn 0/32); và
nhãn phải **kề** giá trị mới được ghép — trước đó "Số: 12/BB-HĐSP" ở góc trái
vớ lấy ngày tháng ở góc phải chỉ vì hai run kề nhau trong DOM.

Schema trong `kie.schema` cố tình **không** gồm mọi thực thể: trung bình 10,1
thuộc tính một trang (3–16). Ô bảng đi đường riêng (`line_items` / `kie_schemas/`).

---

## 7. Một bộ ra trông thế nào (`data/pilot9`)

| chỗ | là gì |
| --- | --- |
| `images/` | ảnh `.jpg` — thứ đem đi train |
| `records/` | bản ghi đầy đủ 4 tầng nhãn (nguồn sự thật) |
| `json/` | bản xuất gọn theo trang: `fields → {value, bbox 0–1000, key_text, key_bbox, description}` |
| `kie_schemas/` | JSON Schema **lồng nhau** cho cả loại chứng từ (có `required`) |
| `html/`, `markdown/` | trang đã vẽ, và bản chữ của nó |
| `word_boxes/`, `layout_boxes/`, `visualize_kie/` | ảnh vẽ đè hộp để mắt người soát |
| `declared/` | nội dung model **khai trước khi vẽ** — để đối chiếu với thứ đọc lại được |
| `rejected/`, `rejected_boxes/` | trang trượt cổng gác, giữ lại để xem vì sao |
| `calls.jsonl`, `compose_report.json`, `performance.md` | mỗi lượt gọi LLM: thời gian, token, lý do trượt |
| `manifest.jsonl`, `index.jsonl` | một dòng mỗi trang / mỗi tài liệu |

---

## 8. Lệnh hay dùng

```bash
python tasks.py                       # liệt kê mọi việc
make preflight                        # mọi phép kiểm phải qua trước khi vẽ
make dataset N=auto DATASET=data/thu  # đường A: một ảnh cho mỗi bố cục
make run                              # đường A: chạy trọn pipeline.yaml
make check-boxes DATASET=data/thu     # hộp có còn nằm trên chữ không
make proof DATASET=data/thu           # Tesseract đọc ngược và chấm điểm
```

---

## 9. Ghi chú hiện trạng (chỗ tài liệu lệch thực tế)

- `data/README.md` **đã cũ**: nó mô tả `dataset60/`, `invoices54/`, `forms16/`,
  `hand12/`, `layouts_all/` — không thư mục nào trong số đó còn trong `data/`.
- `docs/README.md` tự khai rõ: các tài liệu trong `docs/` là **thiết kế**, có
  thứ chưa hiện thực. Đọc code trước khi tin một câu trong đó.
- `generators/html/.venv/` **nặng 782 MB** và nằm ngay trong cây mã nguồn.
- Nhánh hiện tại: `llm-integration`.
