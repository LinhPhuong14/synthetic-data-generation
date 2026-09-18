# `generators/html/render.py` — câu lệnh và hệ thuộc tính

Lệnh gốc mọi renderer đều chạy 3 bước như nhau:

```python
recipe  = rulebase.sample_recipe(seed=7)                    # bốc một điểm trong không gian luật
receipt = rulebase.build_receipt(recipe)                    # điền chữ vào các trường
grid    = rulebase.build_grid(receipt, recipe.layout.id)    # xếp thành lưới ô (path cũ)
```

`render.py` dùng nhánh CSS/HTML thật (`--template auto`), không qua lưới ký tự:
`rulebase.make_content(seed)` → `sheets.build()` đọc `family:` trong
`rulebase/layouts/<id>.yaml` rồi dựng `<table>`/`colspan` thật, đơn vị milimét.

## Cú pháp cơ bản

```bash
generators/html/.venv/bin/python generators/html/render.py \
    -o <thư mục ra> -c <số ảnh> --seed <số> [--force ATTR=ID ...] [cờ khác]
```

Ví dụ đã dùng: sinh 1 ảnh, ghim `augmentation=pristine` (không làm cũ), tự chọn layout:

```bash
generators/html/.venv/bin/python generators/html/render.py \
    -o /tmp/gpu_source -c 1 --seed 1 --force augmentation=pristine --template auto
```

## Cờ dòng lệnh

| Cờ | Ý nghĩa |
|---|---|
| `-o, --out PATH` | thư mục ghi `html_NNN.jpg` (+ `.json` bbox, + `.html` nếu `--save-html`) |
| `-c, --count N` | số ảnh sinh ra (mặc định 10) |
| `--seed N` | seed khởi đầu; ảnh thứ *n* trong batch luôn là `seed + n`, lặp lại được y hệt |
| `--layout ID` | ghim CỨNG một bố cục (thay vì để sampler bốc), tương đương `--force layout=ID` |
| `--force ATTR=ID` | ghim **bất kỳ thuộc tính nào**, lặp lại được nhiều lần: `--force document=supermarket --force color=faded` |
| `--template [MODEL]` | `auto` (mặc định) = sheet CSS theo `family` của layout; `grid` = lưới ký tự cũ; hoặc tên một layout cụ thể để ép mặc layout đó bất kể recipe bốc gì |
| `--scale F` | hệ số scale ảnh chụp màn hình (mặc định 2.0, tương đương DPI) |
| `--handwriting [model\|font\|both]` | ghim `handwriting=hand_<source>` — điền các ô cần viết tay bằng: model WriteViT thật (không viết được số/HOA), font tay licensed (lặp mẫu chữ), hoặc cả hai. Cần đi kèm `--template` |
| `--signature [font\|model]` | vẽ chữ ký phía trên tên in trong khối ký tên. Cần `--template` |
| `--profile PATH.json` | ghi thời gian từng giai đoạn ra file, để soi hiệu năng |
| `--save-html` | ghi kèm `html_NNN.html` (markup đã dựng, trước khi chụp ảnh) bên cạnh `.jpg` |
| `--jobs PATH.json` | thay vì `--layout/--seed/--count` đơn lẻ, nạp một **danh sách job** để 1 tiến trình vẽ nhiều layout khác nhau, trả chi phí khởi động Chromium đúng 1 lần (xem `worklist.py`) |

### `--jobs` — chạy nhiều layout trong 1 tiến trình

```json
[{"layout": "market_vat", "seed": 2026, "count": 2},
 {"layout": "eatery_ascii", "seed": 2028, "count": 1,
  "force": {"augmentation": "pristine"}}]
```

`force` trong job được merge **đè lên** `--force` ở dòng lệnh (job hẹp hơn nên thắng).

## Hệ thuộc tính (`rulebase/rules/*.yaml`)

`--force ATTR=ID` chỉ hợp lệ với các ATTR có file luật trong `rulebase/rules/`.
Thứ tự bốc — và cũng là thứ tự phụ thuộc — nằm ở `rulebase/rules/_order.yaml`:
mỗi thuộc tính chỉ được `requires`/`excludes` một *tag* do thuộc tính **đứng
trước** nó gắn vào, không được nhìn ngược lại thuộc tính sau.

| # | ATTR | quyết định gì | file luật |
|---|---|---|---|
| 1 | `document` | loại chứng từ: quán ăn, siêu thị, hoá đơn GTGT... | `rules/document.yaml` |
| 2 | `layout` | bố cục cụ thể (cột nào, mấy dòng/mục) — mỗi `id` phải có file cùng tên trong `rulebase/layouts/` | `rules/layout.yaml` |
| 3 | `content` | có dấu hay không, VIẾT HOA, định dạng tiền, có VAT | `rules/content.yaml` |
| 4 | `visual` | font, cỡ chữ, độ đậm mực, lề trắng, sheet, độ cong | `rules/visual.yaml` |
| 5 | `color` | màu mực, tông giấy, màu nhấn tên cửa hàng | `rules/color.yaml` |
| 6 | `ornament` | con dấu, hoa văn — mực không phải chữ | `rules/ornament.yaml` |
| 7 | `handwriting` | ô trống điền bằng bút hay bằng chữ in (đứng TRƯỚC `augmentation` để mực bút cũng bị làm cũ theo) | `rules/handwriting.yaml` |
| 8 | `augmentation` | chuỗi làm cũ chạy SAU khi render xong | `rules/augmentation.yaml` |

Mỗi `id` trong file luật có:
- `weight`: tần suất tương đối khi bốc ngẫu nhiên (không ghim). Muốn ra nhiều
  hoá đơn siêu thị hơn → tăng `weight` ở đó, không sửa code.
- `tags`: nhãn gắn vào cho các thuộc tính SAU dùng để `requires`/`excludes`.
- `requires` / `excludes`: điều kiện tự loại — ví dụ bố cục có cột mã vạch chỉ
  bốc được nếu `document` đã gắn tag `has_barcode`.
- `enabled: false`: giá trị vẫn tồn tại, không bao giờ bị bốc ngẫu nhiên,
  nhưng vẫn dựng được khi gọi đích danh bằng `--force` (dùng cho các hiệu ứng
  mạnh/thử nghiệm như `torn_edges`, hoặc mọi kịch bản Blender trong
  `augmentation.yaml`).

Danh sách `ATTR` không nằm trong code Python — nó tự phát hiện từ tên file
trong `rules/*.yaml`, theo đúng thứ tự khai trong `_order.yaml`. Thêm thuộc
tính mới = thêm 1 file + 1 dòng trong `_order.yaml`, không sửa gì khác.

### Xem giá trị hợp lệ của một thuộc tính

```python
from rulebase import spec
spec.enumerate_valid("augmentation")                # mọi id có thể bốc (bỏ tag)
spec.enumerate_valid("layout", tags=["doc_eatery"])  # chỉ những id hợp với tag này
```

### Sai cú pháp `--force` báo lỗi ngay, không âm thầm bỏ qua

```
--force expects ATTR=ID, got '...'
--force: unknown attribute 'xyz'; have document, layout, content, visual, color, ornament, handwriting, augmentation
```

## Ví dụ tổ hợp

```bash
# Ép supermarket, VAT, không làm cũ, xem đúng layout đo từ ảnh gốc
generators/html/.venv/bin/python generators/html/render.py -o out -c 1 \
  --force document=supermarket_vat --force augmentation=pristine

# Ép một layout cụ thể + giữ lại markup HTML để soi debug
generators/html/.venv/bin/python generators/html/render.py -o out -c 1 \
  --template eatery_menu_full --save-html

# Ghim chữ viết tay bằng model WriteViT thật
generators/html/.venv/bin/python generators/html/render.py -o out -c 3 \
  --template auto --handwriting model
```
