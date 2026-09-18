<!-- GIẢI PHẪU CHỨNG TỪ HÀNH CHÍNH VIỆT NAM — kiến thức, không phải số đo.
     `agent/compose_layout.py::user_message()` gửi file này kèm `compose.md` và
     `regions.md`.

     VÌ SAO FILE NÀY VIẾT TAY, VÀ VÌ SAO NÓ KHÔNG SINH RA TỪ KHO

     Mọi file khác quanh đây đo từ dữ liệu: `constraints.yaml` là số người
     duyệt quyết, `layout_schema.py` dẫn xuất từ các phôi đã commit,
     `guideline/` sinh lại từ rules mỗi lần. Cách ấy đúng cho việc kiểm — một
     schema tự đo thì không bao giờ lệch khỏi thứ nó mô tả.

     Nó SAI cho việc soạn. Mức 3 vốn định nghĩa "chỗ được tự do" là chỗ các
     phôi bất đồng với nhau, và hệ quả đo được: 36 trên 46 chứng từ trong kho
     chỉ có ĐÚNG MỘT phôi, nên chúng không bất đồng với gì cả, nên composer
     nhìn vào và thấy tự do bằng không. Một máy soạn mà nguồn sáng tạo là "các
     bản thiết kế cũ khác nhau ở đâu" thì không bao giờ vẽ được thứ chưa ai vẽ
     — nó chỉ nội suy giữa những thứ đã có.

     Nên file này là nguồn tự do THỨ HAI, và nó là kiến thức về giấy tờ ngoài
     đời chứ không phải thống kê về kho. Phôi trong kho từ đây trở thành BẰNG
     CHỨNG ("bộ dựng vẽ được cái này"), không còn là HÀNG RÀO ("chỉ được vẽ
     những gì các phôi bất đồng").

     Cái file này KHÔNG làm: nó không nới từ vựng đóng. Tên khối, tên vùng,
     tên cột, khổ giấy vẫn là danh sách trong lượt người dùng, vì đó là thứ
     giữ cho nhãn khớp pixel. Kiến thức nói CHỌN GÌ TRONG DANH SÁCH ẤY và VÌ
     SAO, không nói thêm tên mới. -->

# Giải phẫu một tờ chứng từ hành chính Việt Nam

Bạn đang dàn trang cho một nhà in Việt Nam. Dưới đây là thứ một người làm nghề
biết mà không phôi nào nói ra được — vì phôi chỉ cho thấy **một** lựa chọn đã
đông cứng, còn nghề thì biết **khoảng** lựa chọn.

Đọc phần dưới như kiến thức nền, rồi mới nhìn phôi. Phôi trả lời "bộ dựng vẽ
được gì"; phần này trả lời "tờ giấy này lẽ ra trông thế nào".

---

## 1. Bốn tầng của mọi tờ chứng từ

Mọi tờ giấy hành chính Việt Nam, không trừ tờ nào, xếp theo bốn tầng dọc. Thứ
tự này không đổi; **cái đổi là mỗi tầng dày bao nhiêu và có tầng nào vắng**.

| tầng | trả lời câu | khối thường dùng |
| :-- | :-- | :-- |
| **định danh** | ai phát hành, tờ này là tờ gì, số mấy | `letterhead`, `header`, `doctitle`, `strip`, `meta` |
| **các bên** | ai với ai | `parties` |
| **nội dung** | việc gì, bao nhiêu | `table`, `items`, `columns`, `notes`, `totals`, `vat_summary`, `words` |
| **xác nhận** | ai chịu trách nhiệm | `signatures`, `footer` |

Ba cách tầng định danh được bày, và ba cách này là **ba nhà in khác nhau**, không
phải ba mức độ đẹp:

* **Quốc hiệu trên đầu** — "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM / Độc lập – Tự do
  – Hạnh phúc" căn giữa, tên cơ quan căn trái cùng dòng. Dáng của mọi tờ do cơ
  quan nhà nước hoặc tổ chức phát hành: công văn, quyết định, biên bản, đơn từ.
* **Măng-sét doanh nghiệp** — tên công ty lớn nhất trang, địa chỉ và mã số thuế
  bên dưới, logo trái hoặc giữa. Dáng của hoá đơn tự thiết kế, phiếu xuất kho,
  bảng kê.
* **Ô góc** — tên tờ giấy chiếm giữa, còn số hiệu/ngày/kỳ dồn vào một hộp góc
  phải. Dáng của biểu mẫu in sẵn theo mẫu ngành, nơi số hiệu quan trọng hơn tên
  người phát hành.

**Chọn một, và để nó quyết phần còn lại.** Tờ mang quốc hiệu thì căn giữa nhiều,
lề rộng, chữ có chân; tờ măng-sét doanh nghiệp thì căn trái, lề hẹp, chữ không
chân. Trộn hai dáng là dấu hiệu rõ nhất của một tờ giấy do máy sinh.

---

## 2. Bảng — chỗ chứng từ Việt Nam khác hẳn chứng từ phương Tây

Đây là phần đáng đọc kỹ nhất, vì đây là chỗ một tờ giấy Việt Nam **phức tạp hơn**
tờ giấy tương đương ở nơi khác, và là chỗ dễ dàn ẩu nhất.

### 2.1 Bảng một tầng — cột phẳng

Sáu cột kinh điển: `stt` · `name` · `unit` · `qty` · `unit_price` · `amount`.
Đây là dáng của hoá đơn bán hàng, phiếu xuất kho, đơn đặt hàng. Bỏ `stt` và
`unit` còn bốn cột là chuyện thường; thêm `vat_rate` thành bảy cột cũng vậy.

### 2.2 Bảng hai tầng tiêu đề — cột gộp

**Dùng khi nhiều cột trả lời chung một câu hỏi.** Tầng trên là câu hỏi, tầng
dưới là các cột trả lời nó. Ví dụ thật:

```
                          │      Nguồn thanh toán (đồng)       │
 Nội dung │ ĐVT │ SL │ ... ├────────┬──────────┬──────┬────────┤
          │     │    │     │ Quỹ BHYT│ Cùng chi trả│ Khác │ Tự trả │
```

Đây là dáng của **bảng kê chi phí khám chữa bệnh, bảng lương, quyết toán thuế,
tờ khai hải quan** — tức là mọi tờ mà một dòng phải chia tiền theo nhiều nguồn.
Nếu chứng từ bạn đang dàn có ý "cùng một khoản, tách theo mấy đường", thì bảng
một tầng là **sai**, không phải là đơn giản hơn.

Ba nhóm gộp hay gặp:

* **theo nguồn tiền** — quỹ bảo hiểm / người bệnh cùng chi trả / tự trả / khác
* **theo kỳ** — kỳ này / kỳ trước / luỹ kế từ đầu năm
* **theo trước–sau** — số đăng ký / số thực hiện / chênh lệch

### 2.3 Nhóm dòng có dòng cộng nhóm

Bảng dài thì **chia mục, mỗi mục một dòng cộng**, đánh số La Mã hoặc số Ả Rập:

```
 1. Khám bệnh                            156.000
    Khám Mắt                    Lần  5    156.000
 2. Ngày giường điều trị nội trú         872.000
    Giường Sản khoa hạng III    Ngày 4    872.000
 ...
 Cộng:                                 7.435.900
```

Dòng đầu mỗi mục **mang tên mục và tổng của mục**, không có đơn vị và số lượng —
vì một tiêu đề mục không có hai thứ đó. Đây là dáng bắt buộc của bảng kê viện
phí, bảng kê vật tư, dự toán. Bảng dài mà không chia mục là bảng người ta không
dò được bằng mắt.

### 2.4 Ô gộp dọc

Một giá trị đúng cho nhiều dòng liền nhau thì viết **một lần**, ô kéo dọc: cột
"Khoa" của bảng kê, cột "Hợp đồng" của bảng thanh toán, cột "Ngày" của sổ nhật
ký. Viết lại giá trị ấy ở mọi dòng là dáng của bảng tính, không phải của chứng
từ in.

### 2.5 Ba luật về bề ngang, đúng cho mọi bảng

* **Cột tên hàng lấy phần còn lại.** Mọi cột khác là số ký tự cố định. Đúng một
  cột được co giãn.
* **Cột số căn phải, cột chữ căn trái, cột đơn vị và số thứ tự căn giữa.** Không
  có ngoại lệ nào đáng làm.
* **Cột tiền rộng hơn bạn nghĩ.** "1.234.567.890" là 13 ký tự, và tờ nào có cột
  tiền cũng sẽ gặp một số như thế.

---

## 3. Mỗi họ chứng từ, và cái làm nên nó

Đây là kiến thức để dàn một tờ mà bạn **chỉ được xem một mẫu** — hoặc không mẫu
nào. Nhìn tờ giấy thuộc họ nào rồi lấy dáng của họ ấy.

**Hoá đơn / phiếu thu** — măng-sét doanh nghiệp, bảng một tầng, khối tổng căn
phải dưới bảng, dòng tiền bằng chữ, hai ô ký (người mua – người bán). Số hiệu và
ngày nằm ở dải trên cùng hoặc ô góc phải.

**Bảng kê / bảng thanh toán** — tờ dày chữ nhất. Bảng hai tầng tiêu đề, chia mục
có dòng cộng, khối quyết toán dưới bảng, ba tới bốn ô ký (người lập – kế toán –
người nhận – thủ trưởng). Khối định danh **mỏng**: tờ này người ta mở ra để dò
số, không phải để biết ai gửi.

**Biểu mẫu điền tay** — quốc hiệu, tên tờ giấy chữ hoa căn giữa, rồi các dòng
`nhãn ..... giá trị` với chấm dẫn hoặc gạch chân. Chỗ trống là **một phần của
thiết kế**, không phải chỗ thừa. Ô ký cuối trang kèm dòng "(Ký, ghi rõ họ tên)".

**Công văn / biên bản / quyết định** — quốc hiệu, số hiệu và trích yếu, rồi thân
văn bản chạy dòng. Không bảng, hoặc một bảng nhỏ chèn giữa. Nơi nhận liệt kê ở
chân trang bên trái, ô ký bên phải.

**Giấy chứng nhận / thẻ** — ngang nhiều hơn dọc, ít chữ, hoa văn bảo an, ảnh
hoặc mã QR, và **một dải thông tin định danh nổi bật hơn mọi thứ khác** (số thẻ,
thời hạn).

**Giấy tính tiền / hoá đơn bán lẻ** — hẹp, một cột, chữ đẳng khoảng, không khung,
mọi thứ căn theo bề ngang giấy cuộn. Đây là họ duy nhất **không** áp dụng phần
lớn những gì viết ở trên.

---

## 4. Bảy quyết định làm nên một phôi khác

Hai nhà in ra cùng một loại chứng từ khác nhau ở bảy chỗ dưới đây. Muốn tờ của
bạn khác tờ mẫu **mà vẫn là cùng loại chứng từ**, đổi ở đây — đừng đổi ở chỗ
tầng 1 và 2 của §1, vì đổi ở đó là ra một loại giấy khác.

1. **Tầng định danh dày hay mỏng** — có logo không, địa chỉ mấy dòng, có dải
   số hiệu riêng không.
2. **Các bên xếp một cột hay hai cột** — bên bán trên bên mua dưới, hay hai cột
   song song.
3. **Bảng có khung hay chỉ có nét kẻ ngang** — khung đầy đủ là dáng biểu mẫu in
   sẵn; chỉ kẻ ngang là dáng hoá đơn laser hiện đại.
4. **Tiêu đề bảng một tầng hay hai tầng** — xem §2.2. Đây là quyết định làm
   thay đổi tờ giấy nhiều nhất trong bảy cái.
5. **Khối tổng nằm trong bảng hay ngoài bảng** — ba dòng cuối của bảng, hay một
   khối riêng căn phải bên dưới.
6. **Ghi chú đặt trên ô ký hay dưới chân trang.**
7. **Mấy ô ký, và xếp ngang hay xếp dọc** — hai ô là tờ thương mại, bốn ô là tờ
   có kế toán và thủ trưởng ký, và bốn ô thì gần như luôn xếp ngang.

---

## 5. Sáu điều một tờ giấy Việt Nam luôn có, kể cả khi phôi không cho thấy

Nếu tờ bạn đang dàn thuộc họ có chúng mà phôi mẫu lại thiếu, **thêm vào** — phôi
thiếu là phôi thiếu, không phải là quyền được bỏ.

1. **Mã số thuế** trên mọi tờ có bên bán là doanh nghiệp — 10 hoặc 13 chữ số.
2. **Số hiệu và ngày** trên mọi tờ. Không tờ hành chính nào không có số.
3. **Dòng tiền bằng chữ** trên mọi tờ có tổng tiền phải trả. Đây là chống sửa
   số, nên nó đi liền với số tiền chứ không phải là trang trí.
4. **Ô ký có chức danh in sẵn** — chức danh in trước, chữ ký viết sau. Ô ký
   không có chức danh là ô ký của một tờ giấy không tồn tại.
5. **Dòng "(Ký, ghi rõ họ tên)"** hoặc tương đương dưới mỗi ô ký.
6. **Đơn vị tiền** nói rõ ở đâu đó — trong tiêu đề cột ("Thành tiền (đồng)"),
   hoặc hậu tố sau số, hoặc một dòng "Đơn vị tính: đồng".

---

## 6. Bốn lỗi làm lộ ngay một tờ do máy sinh

* **Đối xứng hoàn hảo.** Lề bốn phía bằng nhau, hai cột chia đúng 50/50, mọi
  khối cách đều. Tờ giấy thật do người dàn nên không bao giờ như vậy.
* **Mọi khối cùng một trọng lượng.** Tờ thật có một thứ được đọc trước — tổng
  tiền, số thẻ, tên bệnh nhân — và nó to hơn hoặc đứng ở chỗ đắt hơn.
* **Bảng đủ cột nhưng không có ý.** Sáu cột vì hoá đơn thường có sáu cột, chứ
  không phải vì tờ này cần sáu.
* **Chỗ trống bị nhồi.** Còn trống nửa trang thì để trống. Thêm khối cho đầy là
  thứ chỉ máy làm.

---

## 7. Ranh giới không được vượt, dù kiến thức trên nói gì

Phần trên nói tờ giấy **lẽ ra** thế nào. Phần này nói bạn **được nói gì**, và
nó thắng:

* Chỉ dùng tên khối, tên vùng, tên cột, khổ giấy, họ CSS **có trong danh sách ở
  lượt người dùng**. Cần một cách bày mà danh sách chưa có → ghi vào `unmet`,
  không tự đặt tên mới.
* Không viết HTML, không viết CSS.
* Không đụng `key` của cột.
* Trường bắt buộc theo luật và khối có trên mọi phôi: **giữ**. Kiến thức ở đây
  mở rộng chỗ được tự do, không mở rộng chỗ bị cấm.

Phôi mẫu vẫn đáng đọc — nhưng đọc như **bằng chứng bộ dựng vẽ được gì**, không
đọc như giới hạn của cái bạn được nghĩ ra.
