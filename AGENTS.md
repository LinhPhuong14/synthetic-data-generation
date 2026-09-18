# AGENTS.md — dặn cho mọi coding agent làm việc trong kho này

Đọc file này trước khi sửa bất cứ thứ gì. Bản đồ chi tiết kèm số đo:
[`docs/ban-do-repo.md`](docs/ban-do-repo.md). Môi trường và quy ước đóng góp:
[`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 1. Kho này là gì

Một **bộ sinh dữ liệu**, không phải một mô hình. Nó dựng ảnh chứng từ Việt Nam
**kèm nhãn khớp pixel** — chữ gì, hộp nào, trường nào, loại giấy gì — để đem đi
huấn luyện VLM/OCR/KIE ở nơi khác.

Hai đường sinh, đổ về **cùng một bản ghi** (`pipeline/record.py`):

- **Đường luật** — `rulebase/` bốc 11 thuộc tính → `generators/html/sheets/` vẽ
  → `pipeline/run.py` điều phối.
- **Đường LLM** — phôi `rulebase/synthgen/*.yaml` → model viết nội dung + HTML
  → `synthgen/run.py`, `synthgen/draw_llm.py` vẽ.

Pixel chỉ do **một** thứ vẽ: Chromium qua Playwright.

---

## 2. Sáu luật không được phá

1. **Hộp do engine dàn chữ sinh ra.** Đọc từ DOM Chromium. Không bộ dò nào,
   không mô hình nào, không con số viết tay nào được sinh hộp.
2. **Hộp sinh một lần, sau đó chỉ *biến đổi*, không bao giờ *đo lại*.** Làm cũ
   không đổi kích thước; warp chiếu lại bốn góc; thu nhỏ thì hộp co theo.
3. **Thứ gì in mực lên trang thì phải khai vào nhãn.** Chữ ký, con dấu, chữ
   chìm đều có vùng riêng. Đặt một thứ vẽ chữ vào chuỗi `degradation/` là cách
   chắc chắn có mực mà nhãn không biết.
4. **Loại chứng từ là DỮ LIỆU, không phải CODE.** Thêm một loại giấy = thêm một
   file YAML. Không renderer nào phải sửa.
5. **Không bảng tra viết tay theo từng loại chứng từ.** Một bảng phẳng là thứ
   mà loại giấy mới sẽ thiếu khỏi, im lặng. Luật phải đọc từ dữ liệu trang đã
   có (`data-kind`, tiêu đề in trên giấy, cấu trúc markup). Bảng tay chỉ được
   làm **chỗ đỡ** (tên đẹp hơn, câu tả kỹ hơn), không được làm **cổng gác**.
6. **Lỗi phải kêu.** Kho này nhiều lần bị cắn vì một giá trị sai lặng lẽ chạy
   tiếp theo mặc định. Khoá lạ thì từ chối, không bỏ qua.

---

## 3. Sửa cái gì thì vào đâu

| muốn đổi | vào |
| --- | --- |
| tờ giấy **nói gì** (nội dung, trường, số liệu) | `rulebase/content.py`, `rulebase/corpus/`, `rulebase/documents/*.yaml` |
| tờ giấy **xếp thế nào** | `rulebase/layout.py`, `rulebase/layouts/*.yaml` |
| tờ giấy **trông thế nào** | `generators/html/sheets/*.py`, `generators/html/page.py` |
| phôi & trang cho **nhánh LLM** | `rulebase/synthgen/*.yaml`, `synthgen/design.py`, `synthgen/markup.py` |
| **lời dặn model**, cổng gác trang model viết | `agent/prompts/`, `synthgen/llm_page.py`, `synthgen/repair.py` |
| **làm cũ** | `degradation/` (26 mô hình; 3 đang tắt trong `SWITCHED_OFF`) |
| **hình dạng bản ghi & nhãn** | `pipeline/record.py` — nguồn sự thật, sửa ở đây thì mọi bộ đều đổi |
| **KIE** | `pipeline/kie.py` (cặp có nhãn in kèm) + `synthgen/kie_full.py` (bảng, mồ côi, ngầm định) |
| **một lượt chạy** | `pipeline.yaml`, `pipeline/plan.py`, `pipeline/worker.py` |

Điểm vào duy nhất cho mọi việc: **`tasks.py`**. `make` chỉ là vỏ bọc mỏng —
đừng thêm việc vào `Makefile` mà không thêm vào `tasks.py`.

---

## 4. Nhãn của một trang — biết trước khi đụng vào

Một bản ghi (`schema_version: 8`) mang **bốn hạt nhãn cho cùng một chỗ mực**:

| tầng | một phần tử là | hình học |
| --- | --- | --- |
| `layout_annotations` | một **vùng** (19 nhãn lớp) | `bbox` |
| `blocks` | một **dòng** của một run | `bbox`, `quad`, `bbox_1000` |
| `word_annotations` | một **từ** | `bbox`, `polygon` 4 góc (đã theo warp) |
| `entity_annotations` | **cả run** — trường là chuỗi trọn vẹn | `bbox` bao ngoài, **`lines`** hộp từng dòng, `key_entity_index` |

`kie.pairs` ngồi trên `entity_annotations`, **bốn nguồn cặp**:

| `source` | khoá là gì | `key_bbox` |
| --- | --- | --- |
| `label` | nhãn in ngay trước giá trị, cùng trang, kề nhau | có |
| `table` | tiêu đề cột phủ ô (tầng sâu nhất), đọc chỗ ngồi từ markup | có |
| `family` | khoá mồ côi ghép với giá trị mồ côi cùng họ `kind` | có |
| `implied` | không có nhãn in — tên & câu tả suy từ `kind` | **`null`** |

Toạ độ xuất ra ngoài (`data/*/json/`) đổi sang lưới 0–1000: `round(x / bề_rộng × 1000)`.

---

## 5. Chạy và kiểm

```bash
python tasks.py                       # liệt kê mọi việc (không cần make)
make check                            # mọi .py parse được, không cần thư viện
make lint                             # ruff: đúng sai và import, không format
make check-rules                      # giá trị luật không với tới được, thẻ sai
make preflight                        # mọi phép kiểm trước khi vẽ ảnh đầu tiên
python -m pytest tests/ -q            # 48 file test
make dataset N=3 DATASET=data/thu     # ba ảnh mỗi backend
make check-boxes DATASET=data/thu     # hộp có còn nằm trên chữ không
```

**`make check-rules` là cái hay bị quên.** Thẻ gõ sai không ném lỗi — giá trị
mang nó chỉ đơn giản không bao giờ được bốc, và hàng tuần sau mới phát hiện.

**Preflight chậm theo số phôi.** Đầu một lượt gen im lặng 40 phút là bình
thường, không phải treo. Đừng giết tiến trình rồi báo là hỏng.

**Nhánh LLM cần model chạy local, ngoài sandbox.** Agent **đưa lệnh cho người
dùng chạy**, không tự kết luận "không có server" khi gọi không tới.

---

## 6. Quy ước viết

- **Khớp file xung quanh.** Code cũ dùng chung (`pipeline/`, `rulebase/`,
  `degradation/`) viết comment tiếng Anh; code mới ở `synthgen/` và nhánh KIE
  viết tiếng Việt. Theo file đang sửa, đừng đổi giọng giữa chừng.
- **Comment nói VÌ SAO, kèm số đo.** Quy ước rõ nhất của kho: gần như mỗi khối
  comment giải thích một lỗi đã đo được, kèm con số ("đo trên `data/test1`: 35
  trường như vậy"). Viết luật mới thì đo trước, rồi ghi số vào comment.
- **Python 3.9** là sàn (`target-version = py39`). `ruff` cấu hình trong
  `pyproject.toml`; nó không format lại code chuyển thể từ upstream.
- **Mọi font phải phủ tiếng Việt.** Thiếu glyph thì in ra ô trống trong khi
  nhãn vẫn khai là đã in chữ. Kiểm bằng `tools/check_fonts.py`.
- **Corpus giữ nguyên dấu.** Bỏ dấu là phép một chiều, quyết định lúc render.
- **Thứ tự trong chuỗi làm cũ không giao hoán.** Mực mòn rồi nhoè ≠ nhoè rồi mực mòn.

### Commit

- Thông điệp **tiếng Việt, chữ thường**, thường có tiền tố miền:
  `kie: ô trải cột là nhãn dòng, và nhãn phải kề giá trị mới ghép`.
  Thân commit kể lỗi đã đo, số tờ dính, và luật mới — không kể diff.
- Tác giả **chỉ `LinhPhuong14`**. **Không** thêm dòng `Co-Authored-By`, không
  thêm `Generated with …`.
- Chỉ commit khi người dùng bảo commit.

---

## 7. Không đụng vào

- `generators/html/.venv/` — 782 MB, môi trường riêng của renderer.
- `data/*` đã sinh — có thư mục 40 GB. Đừng sinh lại để "thử"; sinh vào thư mục
  mới trong `data/` và nói rõ đã sinh cái gì.
- `degradation/augmentations/` — code vendor, `ruff` loại trừ hẳn.
- `.gitignore` — Git không có comment cuối dòng trong file này; `# …` đuôi dòng
  bị đọc thành một phần của pattern. Kiểm bằng `git check-ignore -v <path>`.

---

## 8. Đọc thêm

| tài liệu | trả lời câu gì |
| --- | --- |
| [`docs/ban-do-repo.md`](docs/ban-do-repo.md) | bản đồ hiện trạng kèm số đo |
| [`docs/muc-tieu.md`](docs/muc-tieu.md) | vì sao dự án tồn tại, "xong" nghĩa là gì |
| [`docs/duong-ong.md`](docs/duong-ong.md) | một tờ giấy đi qua hệ thống ra sao, ai sở hữu toạ độ |
| [`docs/huong-dan-va-giai-thich.md`](docs/huong-dan-va-giai-thich.md) | renderer, từng hàm một |
| [`rulebase/README.md`](rulebase/README.md) | ngữ pháp của luật |
| [`degradation/README.md`](degradation/README.md) | 26 mô hình làm cũ |

> `docs/` là **thiết kế**, có phần chưa hiện thực. Khi tài liệu và code đá nhau,
> code đúng — và sửa lại tài liệu là một phần của việc.
