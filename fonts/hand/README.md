# Mặt chữ viết tay

Dùng cho **chữ ký** (`generators/html/signature.py`) và cho chữ điền tay
(`generators/html/handwriting.py`, `sheets/notebook.py`).

`signature.py` **đọc cả thư mục** — thêm một tệp `.ttf` vào đây là thêm một nét
chữ ký. `notebook.py` thì liệt kê tên cố ý, vì trang vở của nó phải trông y hệt
qua từng lượt chạy.

## Vì sao ba mươi hai chứ không phải hai

Hai mặt chữ là hai chữ ký. Một bộ hai mươi nghìn tờ chỉ có hai nét thì mô hình
học được "chữ ký trông như PatrickHand hoặc IndieFlower" — không học được "chữ
ký là nét tay của một người".

## Cách chọn

Google Fonts khai **99 họ viết tay** có subset `vietnamese`. Khai có không bằng
có thật: mỗi tệp được kiểm bằng `cmap` của chính nó, phải phủ **đủ 59 ký tự
tiếng Việt không nằm trong Latin-1** (`ăâđêôơư` + toàn bộ tổ hợp dấu). Thiếu một
glyph là một chữ ký có ô vuông giữa tên người.

Ba mươi mặt chữ thêm vào trải đều ba dáng, không phải ba mươi cái nhẹ nhất —
nhẹ nhất đều là script bay bướm, và bộ dữ liệu sẽ chỉ có một kiểu chữ ký:

* **chữ ký bay bướm, nét liền** — Alex Brush, Allura, Great Vibes, Pinyon
  Script, Italianno, Corinthia, MonteCarlo, Imperial Script, Qwigley, Ms Madi,
  Carattere, Arizonia, Ephesis
* **chữ tay thường, đọc được** — Mali, Itim, Charm, Charmonman, Mansalva, Grape
  Nuts, Fuzzy Bubbles, Sedgwick Ave, Mynerve, Bad Script, Borel, Patrick Hand SC
* **bút dạ, nét dày** — Kolker Brush, Water Brush, Hurricane, Moon Dance, Smooch

## Giấy phép

Tất cả đều là **SIL Open Font License 1.1** (thư mục `ofl/` của kho
`google/fonts`). OFL cho phép dùng, sửa và phân phối lại, kể cả trong sản phẩm
thương mại; điều kiện là không bán riêng bản thân mặt chữ và giữ nguyên thông
báo bản quyền trong tệp. Bản quyền của từng mặt chữ nằm trong bảng `name` của
chính tệp `.ttf`.

Nguồn: `https://github.com/google/fonts/tree/main/ofl/<tên-viết-liền-thường>`
