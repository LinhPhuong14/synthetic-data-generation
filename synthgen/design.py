"""Ngữ pháp bố cục -- soạn mới, không đọc `rulebase/layouts/`.

Một `Design` là MỘT tờ giấy đã quyết định xong mọi thứ nhìn thấy được: khổ
giấy, lề, cặp phông, cỡ chữ, giãn dòng, mực, màu nhấn, kiểu tiêu đề, kiểu
letterhead, kiểu bảng, số cột trường, thứ tự khối, khối nào có khối nào
không, dấu và hoa văn. `signature()` gói toàn bộ quyết định ấy thành một
tuple -- hai tờ giấy trùng chữ ký là trùng DÁNG, và `compose.py` từ chối cái
thứ hai. Đó là cách "không trùng bố cục giữa các ảnh" được bảo đảm bằng
kiểm tra chứ không bằng lời hứa.

Ba trục tách rời nhau có chủ đích:

* `Archetype` -- chứng từ ấy NÓI gì: tên gọi, trường nào, cột nào, ai ký.
  Ngữ nghĩa, và nó quyết định `data-kind` của từng dòng chữ.
* `Skin` (Paper/Palette/Face + các cờ kiểu) -- tờ giấy ấy TRÔNG thế nào.
  Không trục nào ở đây được phép đổi chữ trên giấy.
* `Frame` -- khối nào có mặt và xếp theo thứ tự nào.

Tách ra vì một nhà in đổi mực không đổi nội dung, và một chứng từ đổi nội
dung không đổi mực. Trộn hai thứ vào một bảng là cách một tập dữ liệu có
mười nghìn dáng mà chỉ có ba mươi kiểu chữ.
"""
from __future__ import annotations

import dataclasses as _dc
import random
import sys as _sys
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Any, Sequence

import yaml as _yaml

_REPO_ROOT = _Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- khổ giấy & lề


@dataclass(frozen=True)
class Paper:
    id: str
    w: float
    h: float


# TRỌNG SỐ THEO ĐỜI THẬT, không bốc đều.
#
# Chứng từ hành chính Việt Nam gần như chỉ dùng A4 DỌC. Bản trước liệt kê 10
# khổ và `_pick` bốc đều, nên 7/10 lượt ra khổ mà đời thật hiếm gặp -- đo trên
# `data/review100`: 7/12 tờ sai khổ hoặc sai hướng, trong đó một tờ ra dải
# 105x250mm làm tên công ty vỡ bốn dòng. Người Việt loại tờ giấy ấy trong nửa
# giây đầu, trước cả khi đọc chữ.
#
# CHỈ A4 DỌC VÀ A4 NGANG. Bản trước còn giữ A5, letter, legal, B5 ở trọng số
# thấp cho đa dạng, nhưng chúng là khổ KHÔNG theo quy chuẩn văn bản hành chính
# Việt Nam -- và một bộ dữ liệu dạy mô hình rằng chứng từ có thể là khổ legal
# thì dạy sai. Đa dạng phải đến từ bố cục bên trong tờ giấy, không từ việc đổi
# khổ giấy. 9/10 dọc, 1/10 ngang (bảng rộng, thời khoá biểu, bản vẽ).
PAPERS: tuple[Paper, ...] = (
    *[Paper('a4', 210, 297)] * 9,
    Paper('a4_ngang', 297, 210),
)

# Thể thức văn bản hành chính VN: trên 20-25mm, dưới 20-25mm, trái 30-35mm,
# phải 15-20mm. Bản trước có `(8,6,8,6)` và `(10,8,10,8)` -- dải nền tiêu đề
# chạm gần mép giấy, đo được lề 3% bề ngang trên `bang_ke_quyen_loi`. Bỏ hai bộ
# chật nhất, nâng sàn lề trái vì đó là chỗ đóng ghim và kẹp hồ sơ.
MARGINS: tuple[tuple[float, float, float, float], ...] = (
    (20, 18, 18, 25), (25, 20, 20, 30), (22, 16, 14, 28), (18, 15, 15, 20),
    (28, 22, 22, 22), (20, 15, 20, 30), (24, 18, 18, 32), (16, 16, 16, 20),
    (15, 20, 15, 22), (14, 12, 12, 18))


# ------------------------------------------------------------------------ mực


@dataclass(frozen=True)
class Palette:
    id: str
    ink: str
    strong: str
    accent: str
    rule: str
    band_bg: str
    band_fg: str
    zebra: str
    soft: str
    paper: str


PALETTES: tuple[Palette, ...] = (
    Palette('den_trang', '#161616', '#000000', '#161616', '#333333', '#e8e8e8', '#111111', '#f6f6f6', '#5a5a5a', '#ffffff'),
    Palette('den_trang_dam', '#0a0a0a', '#000000', '#000000', '#000000', '#000000', '#ffffff', '#f0f0f0', '#4a4a4a', '#ffffff'),
    Palette('xanh_hanh_chinh', '#14213d', '#0b1a33', '#1d3f7a', '#3d5a8a', '#dce6f5', '#12294d', '#f2f6fc', '#5a6b85', '#ffffff'),
    Palette('xanh_ngan_hang', '#10243a', '#071a2c', '#0f6ab0', '#4a7fa8', '#0f6ab0', '#ffffff', '#eef6fc', '#587085', '#ffffff'),
    Palette('do_hoa_don', '#1c1c1c', '#111111', '#a4161a', '#a4161a', '#fbe3e3', '#7a0f12', '#fdf3f3', '#6b5555', '#fffdfa'),
    Palette('do_quoc_huy', '#151515', '#000000', '#c1121f', '#8d0801', '#ffffff', '#c1121f', '#fdf6f6', '#5b5b5b', '#fffefb'),
    Palette('luc_y_te', '#12231c', '#08170f', '#1b7a4b', '#3f8a68', '#dff0e6', '#0f4a2c', '#f2faf5', '#527062', '#ffffff'),
    Palette('luc_dam', '#14251c', '#0a1a11', '#2d6a4f', '#40916c', '#2d6a4f', '#ffffff', '#f0f7f3', '#4e6b5c', '#fcfffd'),
    Palette('nau_giay_cu', '#2b2118', '#1a130c', '#6b4423', '#8a6b4f', '#efe3d3', '#4a3018', '#f8f2e8', '#7a6a55', '#fdf8f0'),
    Palette('tim_dich_vu', '#1d1830', '#100c22', '#4b3f8f', '#6b5fa8', '#e6e2f5', '#332a63', '#f5f3fc', '#5f5a7a', '#ffffff'),
    Palette('cam_ban_le', '#231a12', '#140e08', '#c05621', '#c98a5a', '#fbe9da', '#7a3510', '#fdf6f0', '#7a6250', '#fffdf9'),
    Palette('xam_ky_thuat', '#1f1f1f', '#0d0d0d', '#4a4a4a', '#8a8a8a', '#4a4a4a', '#ffffff', '#f4f4f4', '#6e6e6e', '#fcfcfc'),
    Palette('nhiet_quay', '#111111', '#000000', '#111111', '#555555', '#ffffff', '#111111', '#ffffff', '#666666', '#fdfdfa'),
    Palette('xanh_bien_bao_hiem', '#0f2233', '#06131f', '#00668c', '#3f7f9c', '#dceef5', '#054458', '#f1f8fb', '#4f6a78', '#ffffff'),
    Palette('vang_dat_phong', '#241f10', '#141005', '#8a6d00', '#b09330', '#faf0cf', '#5a4600', '#fdfaef', '#6f6547', '#fffef8'),
    Palette('hong_nhat_khai_sinh', '#22161a', '#120a0d', '#8a3b52', '#b06d80', '#f7e4ea', '#5e2334', '#fdf5f8', '#715c62', '#fffdfd'),
)


# ------------------------------------------------------------------ bộ chữ


@dataclass(frozen=True)
class Face:
    id: str
    head: str
    body: str
    mono: str


_SERIF = "'Liberation Serif', 'Times New Roman', serif"

_SANS = "'Liberation Sans', Arial, sans-serif"

_ARIMO = "Arimo, 'Liberation Sans', sans-serif"

_DEJAVU = "'DejaVu Sans', 'Liberation Sans', sans-serif"

_NOTO = "'Noto Sans', 'DejaVu Sans', sans-serif"

# Kệ serif từng chỉ có MỘT họ (Liberation Serif), nên mọi tờ giấy serif của cả
# bộ dữ liệu đều cùng một nét chữ. DejaVu Serif cùng giấy phép với DejaVu Sans
# mà kho đã nhúng, và `tools/check_fonts.py` xác nhận nó phủ đủ tiếng Việt --
# không phải chuyện hình thức: Caveat, lựa chọn hiển nhiên cho `hand/`, thiếu
# 80 ký tự và sẽ in ra ô vuông rỗng dưới một cái nhãn nói rằng đó là chữ.
_DEJAVU_SERIF = "'DejaVu Serif', 'Liberation Serif', serif"

_MONO = "'Liberation Mono', 'Courier New', monospace"

_COUSINE = "Cousine, 'Liberation Mono', monospace"

_NOTOMONO = "'Noto Mono', 'Liberation Mono', monospace"

FACES: tuple[Face, ...] = (
    Face('serif_thuan', _SERIF, _SERIF, _MONO),
    Face('serif_tren_sans', _SERIF, _SANS, _MONO),
    Face('sans_thuan', _SANS, _SANS, _MONO),
    Face('sans_tren_serif', _SANS, _SERIF, _MONO),
    Face('arimo', _ARIMO, _ARIMO, _COUSINE),
    Face('arimo_tren_serif', _ARIMO, _SERIF, _COUSINE),
    Face('dejavu', _DEJAVU, _DEJAVU, _NOTOMONO),
    Face('dejavu_tren_serif', _DEJAVU, _SERIF, _MONO),
    Face('noto', _NOTO, _NOTO, _NOTOMONO),
    Face('noto_tren_serif', _NOTO, _SERIF, _COUSINE),
    Face('mono_quay', _COUSINE, _COUSINE, _COUSINE),
    Face('mono_bang_ke', _NOTOMONO, _NOTOMONO, _NOTOMONO),
    Face('serif_tren_noto', _SERIF, _NOTO, _NOTOMONO),
    Face('sans_tren_dejavu', _SANS, _DEJAVU, _MONO),
    Face('dejavu_serif', _DEJAVU_SERIF, _DEJAVU_SERIF, _MONO),
    Face('dejavu_serif_tren_sans', _DEJAVU_SERIF, _SANS, _MONO),
    Face('sans_tren_dejavu_serif', _SANS, _DEJAVU_SERIF, _COUSINE),
    Face('noto_tren_dejavu_serif', _NOTO, _DEJAVU_SERIF, _NOTOMONO),
    Face('dejavu_serif_tren_noto', _DEJAVU_SERIF, _NOTO, _MONO),
    Face('serif_tren_dejavu_serif', _SERIF, _DEJAVU_SERIF, _COUSINE),
)

HEAD_LAYOUTS = ('trai', 'giua', 'chia_doi', 'trai_co_logo', 'giua_co_logo', 'chia_doi_co_logo', 'khung_vien', 'dai_mau', 'hai_cot_cach', 'logo_phai', 'khong_letterhead')

TITLE_STYLES = ('hoa_dam_giua', 'hoa_dam_trai', 'hoa_vien_duoi', 'hoa_trong_khung', 'hoa_gian_chu', 'thuong_dam_giua', 'hoa_dam_gach_ngan', 'hoa_dam_nen_nhat', 'hoa_dam_hai_dong')

META_STYLES = ('duoi_tieu_de_giua', 'duoi_tieu_de_phai', 'goc_phai_tren', 'dai_ngang', 'hai_cot', 'trong_khung_phai', 'khong_co')

FIELD_STYLES = ('mot_cot_hai_cham', 'hai_cot_hai_cham', 'mot_cot_cham_cham', 'hai_cot_cham_cham', 'ba_cot_ngan', 'bang_khong_vien', 'nhan_dam_tren', 'hai_cot_gach_duoi', 'mot_cot_gach_duoi')

# `khong_ke` và `chi_ke_doc` đã BỎ. Một bảng không đường kẻ nào thì nhãn cột
# lơ lửng không thuộc cột nào -- đo trên `bang_cham_cong_00050`; còn "chỉ kẻ
# dọc" đúng định nghĩa nửa nọ nửa kia mà chứng từ thật không có. `vien_ngoai`
# giữ lại vì biểu mẫu kê khai có dùng, nhưng một vé.
TABLE_FRAMES = ('khung_day_du', 'khung_day_du', 'khung_day_du',
                'chi_ke_ngang', 'chi_ke_ngang',
                'ke_ngang_dam_dau', 'khung_day_du_van', 'vien_ngoai')

HEADER_FILLS = ('dai_mau', 'nen_nhat', 'khong_nen', 'gach_doi', 'chu_dam_gach')

SIGN_STYLES = ('cot_deu', 'trai_phai', 'chi_ben_phai', 'ba_cot', 'co_khung', 'co_dong_ke', 'bon_cot')

NOTE_STYLES = ('doan_thuong', 'danh_sach_so', 'danh_sach_gach', 'trong_khung', 'chu_nghieng_nho', 'hai_cot')

RULE_WEIGHTS = (0.2, 0.25, 0.3, 0.4, 0.5, 0.7)

LEADINGS = (1.15, 1.22, 1.28, 1.34, 1.4, 1.48, 1.55)

BASE_SIZES = (7.6, 8.0, 8.4, 8.8, 9.2, 9.6, 10.2, 10.8, 11.4)

TRACKING = (0.0, 0.0, 0.0, 0.15, 0.3, -0.1)

# Chỉ dấu TRÒN và CHỮ NHẬT. `dau_oval` đã bỏ: con dấu oval không có trên
# giấy tờ Việt Nam, và bản CSS cũ vẽ nó thành một hình bo góc xoay nghiêng
# đọc ra hình thoi. Xem `markup.SEALS`.
# Số cột của cả trang. Một nghiêng về một cột vì phần lớn chứng từ hành chính
# vẫn in một cột; hai và ba có mặt vì báo, tạp chí, tờ rơi và đơn nhiều mục thì
# không.
# Một cột là mặc định. Bản trước `(1,1,1,2,2,3)` cho 50% ra cột báo, nên biên
# lai thu tiền, uỷ nhiệm chi và phiếu chi đều bị dàn 2-3 cột -- ở uỷ nhiệm chi,
# cột giữa hẹp làm số tài khoản ngắt ba dòng trong khi nửa phải trang bỏ trắng.
# Cột báo có thật trên tờ rơi và bản tin, nên giữ, nhưng còn 2/12 = 17%.
PAGE_COLUMNS = (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3)

ORNAMENTS = ('khong', 'dau_tron', 'dau_vuong', 'ma_vach', 'ma_qr', 'dau_tron_va_ma_vach', 'hoa_van_goc', 'chim_mo')

# ------------------------------------------------------------------ trang trí
#
# PHẦN TRANG TRÍ KHÔNG MANG CHỮ: khung trang, dải màu mép giấy, nền hoa văn,
# kiểu logo, và mấy điểm nhấn màu trên khối có sẵn. Lấy từ ảnh của pipeline
# chính (`data/layouts_all/html/`): hoá đơn GTGT điện tử có khung an ninh hai
# lớp, hoá đơn khách sạn có dải màu tràn mép, giấy chứng nhận bảo hiểm có logo
# chữ lồng "MH" trên ô màu và cột nhãn tô nền. Đặt cạnh ảnh synthgen
# (`data/22-09-26-synthetics-multipage/`), khác biệt nhìn thấy ngay là synthgen
# gần như toàn chữ đen trên giấy trắng: logo là một hình tròn mờ 14%, không
# tờ nào có khung trang, không tờ nào có dải màu mép giấy.
#
# Mỗi trục là MỘT tên, trọng số đọc từ `_blocks.yaml` (mục `decor_*`), không
# viết trong mã. Không trục nào đẻ ra chữ: thứ gì in chữ đều đã có `data-kind`
# ở `markup.py`, và logo chữ lồng nằm trong `.logo` -- selector mà
# `page.py::GRAPHIC_RECTS_JS` đã đo thành vùng hình, đúng như "MH" của
# `generators/html/sheets/insurance.py`.
#
# `khong` đứng ĐẦU mỗi trục vì nó là giá trị của mọi tờ dựng trước khi có
# trục ấy -- `Design` mặc định về đó, nên `agent/redesign.py` và mọi chỗ khác
# dựng `Design` bằng tay không đổi dáng.
PAGE_FRAMES = ('khong', 'don', 'doi', 'an_ninh', 'goc', 'bo_tron')

# Dải màu ở MÉP giấy, nằm trọn trong lề: cao/rộng chỉ bằng một phần lề, nên
# không đè lên chữ nào. Loại trừ với khung trang -- khung đứng ở giữa lề, dải
# ở mép lề, hai thứ chồng lên nhau đọc ra một vệt bẩn chứ không ra trang trí.
EDGE_BANDS = ('khong', 'tren', 'tren_duoi', 'trai', 'tren_song')

# Nền giấy có hoa văn -- kiểu giấy chứng nhận, phôi in sẵn chống giả. Rất nhạt
# (pha 6-9% màu nhấn vào màu giấy): đủ để thấy là giấy in hoa văn, không đủ để
# thành nhiễu dưới nét chữ.
GROUNDS = ('khong', 'hoa_van', 'ke_cheo', 'cham_luoi')

# Logo của letterhead khi `head_layout` có logo. `mo` là hình tròn mờ cũ.
LOGO_STYLES = ('mo', 'o_chu', 'vong_chu', 'chu_mau')

# Điểm nhấn trên khối CÓ SẴN, mỗi cái bốc độc lập theo xác suất ở
# `_blocks.yaml::decor_accent`. Không đổi thứ tự, không đổi chữ -- chỉ màu,
# nền và viền.
ACCENTS = ('tieu_de_mau', 'ghi_chu_the', 'tong_noi_bat', 'nhan_mau')

# Trang trí bốc bằng MỘT dòng ngẫu nhiên riêng, tách khỏi `rng` của `draw()`.
# Chèn thêm phép bốc vào giữa `draw()` là xê dịch mọi phép bốc sau nó, tức là
# mọi seed đã vẽ ra một tờ KHÁC -- các bộ `data/` cũ thôi tái hiện được. Dòng
# riêng thì seed cũ vẫn ra đúng tờ cũ, chỉ thêm phần trang trí lên trên.
DECOR_SALT = 0x5D3C0A7

# Nhóm cột cho tiêu đề HAI TẦNG: tầng trên in tên nhóm với `colspan`, tầng
# dưới in tên từng cột, còn cột không thuộc nhóm nào thì `rowspan="2"` xuyên
# cả hai tầng. Đúng dáng bảng kê nhà nước, bảng lương và tờ khai hải quan --
# và là thứ một bảng một tầng không dạy được mô hình đọc.
#
# Một nhóm chỉ dùng được khi các cột của nó nằm LIỀN NHAU trong bộ cột đã
# bốc: `colspan` không nhảy cóc được, nên nhóm rời rạc là nhóm sai.
COL_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (('Số lượng và đơn giá', 'Số lượng, đơn giá', 'Khối lượng và đơn giá'),
     ('qty', 'unit_price')),
    (('Thuế GTGT', 'Thuế giá trị gia tăng', 'Thuế suất và tiền thuế'),
     ('vat_rate', 'vat_amount')),
    (('Bảo hiểm y tế', 'Nguồn thanh toán', 'Phân bổ chi trả'),
     ('copay', 'fund')),
    (('Thành tiền', 'Giá trị thanh toán', 'Số tiền phải trả'),
     ('amount', 'discount')),
    (('Chứng từ gốc', 'Hồ sơ kèm theo', 'Tham chiếu'), ('ref', 'date')),
    (('Đơn giá và thành tiền', 'Giá trị hàng hoá'), ('unit_price', 'amount')),
    (('Hàng hoá, dịch vụ', 'Nội dung chi tiết', 'Khoản mục'), ('name', 'unit')),
    (('Tiền thuế và thành tiền', 'Cộng có thuế'), ('vat_amount', 'amount')),
    # Thêm theo TỔ HỢP CỘT CÓ THẬT trong `column_pool`, không theo phỏng đoán:
    # đo trên 900 lượt bốc, 44 bộ từ năm cột trở lên không khớp một nhóm nào,
    # và chúng dồn vào mấy hình dưới đây. Bộ cột không có nhóm thì tiêu đề chỉ
    # một tầng -- tức là cái bảng rộng nhất lại có cấu trúc nghèo nhất.
    (('Đơn vị bảo hiểm', 'Phần bảo hiểm chi trả', 'Bên bảo hiểm'),
     ('price_bh', 'amount_bh')),
    (('Đơn vị thụ hưởng', 'Phần người bệnh trả', 'Bên tự trả'),
     ('price_bv', 'amount_bv')),
    (('Định danh hàng hoá', 'Mã và tên', 'Nhận dạng'), ('ref', 'name')),
    (('Thời gian và chứng từ', 'Ngày và số hiệu'), ('date', 'ref')),
    (('Quy cách', 'Số lượng và đơn vị', 'Khối lượng'), ('qty', 'unit')),
    (('Diễn giải', 'Nội dung và ghi chú'), ('name', 'note')),
    (('Thời điểm phát sinh', 'Ngày và nội dung'), ('date', 'name')),
    # Vòng đo thứ hai, 1500 lượt bốc: đếm CẶP CỘT LIỀN NHAU thật sự xuất hiện
    # rồi trừ đi cặp đã có nhóm. Cái lọt ra nhiều nhất là `unit, qty` -- 109
    # lần, và nhóm "Quy cách" ĐÃ CÓ cho đúng cặp ấy, chỉ khai ngược thứ tự
    # `('qty', 'unit')`. `groups_in` đòi các cột liền nhau ĐÚNG THỨ TỰ, nên
    # một nhóm khai ngược là một nhóm không bao giờ khớp: nó nằm trong bảng
    # như thể đang chạy. Khai cả hai chiều thay vì nới luật khớp -- luật khớp
    # đúng, chỉ bản khai thiếu.
    (('Quy cách', 'Đơn vị và số lượng'), ('unit', 'qty')),
    (('Đơn giá và thuế suất', 'Giá và thuế'), ('unit_price', 'vat_rate')),
    (('Thuế và tổng cộng', 'Cộng có thuế'), ('vat_rate', 'amount_with_vat')),
    (('Đơn giá theo nguồn', 'Giá dịch vụ'), ('price_bv', 'price_bh')),
    (('Thành tiền theo nguồn', 'Chia theo nguồn chi'), ('amount_bv', 'amount_bh')),
    (('Tỷ lệ và phần tự trả', 'Người bệnh cùng chi trả'), ('rate_bhyt', 'self_pay')),
    (('Định danh hàng hoá', 'Mã vạch và tên'), ('barcode', 'name')),
)

# Tầng thứ BA: một nhóm-lớn phủ hai nhóm liền nhau trở lên. Ba tầng là dáng
# của tờ khai hải quan và bảng kê thanh toán viện phí thật -- "Giá trị và
# thuế" phủ "Số lượng, đơn giá" và "Thuế GTGT", mỗi nhóm ấy lại phủ hai cột.
COL_SUPERS = (
    'Giá trị và thuế', 'Chi tiết hàng hoá, dịch vụ', 'Số liệu chi tiết',
    'Trị giá tính thuế và thuế', 'Chi tiết khoản mục', 'Số liệu quyết toán',
    'Nguồn kinh phí và thanh toán', 'Chi tiết theo từng khoản mục',
    'Số liệu đối chiếu', 'Cơ cấu chi phí', 'Phân tích theo nguồn',
)

# Tầng THỨ TƯ: một dải chạy hết chiều ngang bảng, nằm TRONG khung, trên mọi
# tầng tiêu đề. Không phải cái nhan đề đặt trên bảng -- nó là một hàng thật
# của `<thead>`, nên nó lặp lại ở đầu mỗi tờ đúng như tiêu đề cột.
#
# Vì sao không dựng tầng bốn bằng đúng luật lồng như tầng ba: đo 1500 lượt
# bốc, KHÔNG MỘT bộ cột nào có hai đoạn nhóm liền nhau tách rời -- điều kiện
# cần để một dải phủ được hai dải dưới nó. Bộ cột rộng nhất chỉ tám cột và
# nhiều nhất ba nhóm, nên tầng bốn theo luật ấy là 0%, và nới luật để ép nó
# nổ sẽ đẻ ra những cái phủ vô nghĩa. Giấy thật giải bài này theo cách khác,
# và đây đúng là cách bảng kê chi phí khám chữa bệnh 01/BV và tờ khai hải
# quan in ra: một dòng "Phần ..." chạy ngang trên đầu bảng.
COL_BANNERS = (
    'Phần II - Chi tiết thanh toán', 'Phần A - Kê khai chi tiết',
    'Phần B - Chi tiết phát sinh trong kỳ', 'Chi tiết theo từng khoản mục',
    'Phần I - Bảng kê chi tiết', 'Phụ lục - Số liệu chi tiết kèm theo',
    'Bảng kê chi tiết kèm theo', 'Phần C - Tổng hợp số liệu',
)

# Cách gộp DÒNG. `khong` là bảng phẳng như cũ; `phan_muc` chèn dòng tiêu đề
# nhóm chạy hết chiều ngang (kiểu thực đơn, kiểu bảng thống kê cốt thép);
# `cot_gom` để một ô `rowspan` bên trái mang tên nhóm, trải qua các dòng của
# nhóm ấy (kiểu bảng xếp hạng vòng bảng).
# Nhóm dòng ("Chi thường xuyên", "Chi đầu tư") là cấu trúc thật của bảng kê và
# bảng cân đối. Bản trước để 50% không nhóm; giờ 25% -- bảng phẳng vẫn có, chỉ
# thôi là đa số.
ROW_GROUPS = ('khong', 'khong', 'phan_muc', 'phan_muc', 'phan_muc', 'cot_gom',
              'cot_gom', 'phan_muc')

# Tên nhóm dòng, theo hồ sơ. Bốc theo `profile` của chứng từ chứ không bốc
# chung: "Móng / Cột / Dầm" trên một thực đơn là vô nghĩa.
ROW_GROUP_NAMES: dict[str, tuple[str, ...]] = {
    'invoice': ('Hàng hoá chịu thuế', 'Hàng hoá không chịu thuế', 'Dịch vụ kèm theo', 'Vật tư phụ', 'Chi phí vận chuyển', 'Khoản mục khác'),
    'market': ('Thực phẩm tươi', 'Hàng khô', 'Đồ uống', 'Hoá phẩm', 'Đồ gia dụng', 'Hàng đông lạnh'),
    'eatery': ('Món khai vị', 'Món chính', 'Món tráng miệng', 'Đồ uống', 'Món thêm', 'Phụ thu'),
    'menu': ('KHAI VỊ', 'MÓN CHÍNH', 'MÓN NƯỚNG', 'LẨU', 'TRÁNG MIỆNG', 'ĐỒ UỐNG'),
    'bakery': ('Bánh mì', 'Bánh ngọt', 'Bánh kem', 'Bánh trung thu', 'Đồ uống', 'Quà tặng'),
    'hotel': ('Tiền phòng', 'Dịch vụ ăn uống', 'Dịch vụ giặt là', 'Dịch vụ khác', 'Phụ thu', 'Thuế và phí'),
    'export': ('Nhóm hàng A', 'Nhóm hàng B', 'Nhóm hàng C', 'Bao bì đóng gói', 'Cước vận chuyển', 'Phụ phí'),
    'admin': ('Chi thường xuyên', 'Chi đầu tư', 'Chi nghiệp vụ', 'Chi khác', 'Tạm ứng', 'Hoàn ứng'),
    'power': ('Bậc 1 - 50 kWh đầu', 'Bậc 2 - 50 kWh tiếp theo', 'Bậc 3 - 100 kWh tiếp theo', 'Bậc 4 trở lên', 'Phụ thu', 'Thuế GTGT'),
    'water': ('Sinh hoạt bậc 1', 'Sinh hoạt bậc 2', 'Sinh hoạt bậc 3', 'Kinh doanh', 'Phí bảo vệ môi trường', 'Thuế GTGT'),
    'medical': ('Tiền khám bệnh', 'Tiền thuốc', 'Xét nghiệm - chẩn đoán hình ảnh', 'Vật tư y tế', 'Tiền giường'),
    'insurance': ('Quyền lợi nội trú', 'Quyền lợi ngoại trú', 'Quyền lợi nha khoa', 'Quyền lợi thai sản', 'Quyền lợi bổ sung', 'Điểm loại trừ'),
}


# ------------------------------------------------------------ một tờ đã chốt


@dataclass
class Design:
    """Một tờ giấy đã chốt xong dáng. Bất biến sau khi `draw()` trả về."""

    archetype: 'Archetype'
    paper: Paper
    margins: tuple[float, float, float, float]
    palette: Palette
    face: Face
    base_pt: float
    leading: float
    tracking: float
    rule_px: float
    head_layout: str
    title_style: str
    meta_style: str
    field_style: str
    field_columns: int
    page_columns: int
    table_frame: str
    header_fill: str
    zebra: bool
    table_caption: bool
    compact_rows: bool
    head_tiers: int
    col_numbers: bool
    row_groups: str
    nested_detail: bool
    sign_style: str
    sign_count: int
    note_style: str
    ornament: str
    columns: tuple[str, ...]
    sign_captions: tuple[str, ...]
    fields: tuple[FieldDef, ...]
    order: tuple[str, ...]
    blocks: frozenset[str]
    photo_box: bool
    watermark: bool
    reverse_title_band: bool
    lang_en: bool
    # TỜ NÀY CÓ IN QUỐC HIỆU KHÔNG. Bốc theo `archetype.national` -- xác suất
    # mà 137/139 phôi đã khai sẵn nhưng trước đây KHÔNG đường vẽ nào đọc: nó
    # chỉ đi từ YAML qua `archetypes.py` rồi dừng. `markup.py` tự quyết bằng
    # `org_kind`, nên mọi tờ do công ty phát hành mất quốc hiệu (4/12 tờ đo
    # được), còn hoá đơn và thực đơn của cơ quan nhà nước thì lại có.
    national: bool
    target_pages: int
    # KHỐI CHẢY: khối nào quyết định tài liệu này DÀI bao nhiêu, và do đó
    # khối nào bị cắt ra khi nó phải in làm nhiều tờ.
    #
    # Trước đây không có trường này vì câu trả lời luôn là `table`, viết thẳng
    # vào `paginate.py`, `markup.py` và `draw.py`. Hệ quả đo được: mọi tài
    # liệu nhiều trang trong bộ đều là một cái bảng, tức là "nhiều trang" và
    # "có bảng" là CÙNG MỘT THỨ với bất kỳ mô hình nào học trên bộ ấy. Đặt
    # tên cho nó, một lần, ở đây, để ba chỗ kia đọc chứ không đoán -- xem
    # `FLOW_BLOCKS`.
    flow: str
    # CHỖ ĐỨNG của mực không-phải-chữ: dấu, mã vạch, mã QR.
    #
    # Trước đây không có trường này vì câu trả lời luôn là "cuối tờ cuối",
    # viết thẳng trong thân vòng lặp của `markup()`. Giấy thật không thế: hoá
    # đơn siêu thị in mã vạch ngay dưới tên cửa hàng, phiếu gửi xe in mã QR ở
    # góc trên bên phải, còn công văn thì đóng dấu cuối trang. Ba chỗ ấy là ba
    # dáng khác nhau mà một bộ dữ liệu chỉ có một chỗ thì không dạy được.
    mark_place: str
    seed: int

    # `boost` là hệ số cỡ chữ, và là trường DUY NHẤT đổi được sau khi `draw()`
    # trả về: `paginate.py` chỉnh nó để ép một tờ giấy lấp đủ 80% mà không
    # phải rút lại toàn bộ dáng.
    boost: float = 1.0

    # Trang trí -- xem `PAGE_FRAMES` và các trục cạnh nó. Mặc định là "không
    # trang trí", đúng dáng mọi tờ dựng trước khi có các trục này.
    frame: str = 'khong'
    band: str = 'khong'
    ground: str = 'khong'
    logo_style: str = 'mo'
    accents: frozenset = frozenset()

    def signature(self) -> tuple:
        """Mọi quyết định nhìn thấy được, gói lại. Trùng cái này là trùng dáng."""
        return (
            self.archetype.id, self.paper.id, self.margins, self.palette.id,
            self.face.id, self.base_pt, self.leading, self.tracking, self.rule_px,
            self.head_layout, self.title_style, self.meta_style, self.field_style,
            self.field_columns, self.table_frame, self.header_fill, self.zebra,
            self.table_caption, self.compact_rows, self.head_tiers,
            self.col_numbers, self.row_groups, self.nested_detail,
            self.sign_style, self.sign_count,
            self.note_style, self.ornament, self.columns, self.page_columns,
            self.sign_captions,
            tuple(f.key for f in self.fields), self.order,
            tuple(sorted(self.blocks)), self.photo_box, self.watermark,
            self.reverse_title_band, self.lang_en, self.national,
            self.flow, self.mark_place,
            self.frame, self.band, self.ground, self.logo_style,
            tuple(sorted(self.accents)),
        )

    def has(self, block: str) -> bool:
        return block in self.blocks


# ----------------------------------------------------------------- cột bảng


COLUMNS: dict[str, dict[str, Any]] = {
    'stt': {'titles': ('STT', 'TT', 'Số TT', 'No.', 'Stt'), 'kind': 'menu.stt', 'align': 'center', 'w': 6, 'en': 'No.', 'describe': 'Row ordinal within the item table, counted across the whole document.'},
    'name': {'titles': (
    'Tên hàng hoá, dịch vụ',
    'Nội dung',
    'Diễn giải',
    'Tên vật tư',
    'Khoản mục',
    'Tên dịch vụ',
    'Mô tả',
), 'kind': 'menu.name', 'align': 'left', 'w': 0, 'en': 'Description', 'describe': 'Name of the goods or service listed on this line.'},
    'unit': {'titles': ('ĐVT', 'Đơn vị', 'Đ.V.T', 'Đơn vị tính'), 'kind': 'menu.unit', 'align': 'center', 'w': 10, 'en': 'Unit', 'describe': 'Unit of measure for the quantity on this line.'},
    'qty': {'titles': ('Số lượng', 'SL', 'Số lượng', 'S.Lượng'), 'kind': 'menu.qty', 'align': 'right', 'w': 10, 'en': 'Qty', 'describe': 'Quantity of the item on this line.'},
    'unit_price': {'titles': ('Đơn giá', 'Đơn giá (VNĐ)', 'Giá', 'Đơn giá/ĐVT'), 'kind': 'menu.unit_price', 'align': 'right', 'w': 14, 'en': 'Unit price', 'describe': 'Price of one unit of this item, before tax.'},
    'amount': {'titles': ('Thành tiền', 'Thành tiền (VNĐ)', 'Số tiền', 'Tổng'), 'kind': 'menu.amount', 'align': 'right', 'w': 16, 'en': 'Amount', 'describe': 'Line amount: quantity multiplied by unit price, before tax.'},
    'vat_rate': {'titles': ('Thuế suất', 'TS GTGT', '% VAT', 'Thuế suất GTGT'), 'kind': 'menu.vat_rate', 'align': 'center', 'w': 10, 'en': 'VAT rate', 'describe': 'Value-added tax rate applied to this line; KCT means not subject to tax.'},
    'vat_amount': {'titles': ('Tiền thuế', 'Tiền thuế GTGT', 'Thuế GTGT'), 'kind': 'menu.vat_amount', 'align': 'right', 'w': 14, 'en': 'VAT amount', 'describe': 'Value-added tax charged on this line.'},
    'note': {'titles': ('Ghi chú', 'Chú thích', 'Ghi chú thêm'), 'kind': 'menu.note', 'align': 'left', 'w': 16, 'en': 'Remark', 'describe': 'Free-text remark about this line.'},
    'ref': {'titles': ('Mã số', 'Mã hàng', 'Mã vật tư', 'Số hiệu'), 'kind': 'menu.ref', 'align': 'left', 'w': 14, 'en': 'Code', 'describe': 'Item or material code identifying the goods on this line.'},
    'date': {'titles': ('Ngày', 'Ngày thực hiện', 'Ngày phát sinh'), 'kind': 'menu.date', 'align': 'center', 'w': 14, 'en': 'Date', 'describe': 'Date this line item was issued or incurred.'},
    'discount': {'titles': ('Chiết khấu', 'Giảm giá', 'CK'), 'kind': 'menu.discountprice', 'align': 'right', 'w': 12, 'en': 'Discount', 'describe': 'Discount deducted from this line.'},
    'copay': {'titles': ('Người bệnh trả', 'Đồng chi trả', 'BN chi trả'), 'kind': 'menu.copay', 'align': 'right', 'w': 14, 'en': 'Co-pay', 'describe': 'Portion of this line the patient pays out of pocket.'},
    'fund': {'titles': ('BHYT thanh toán', 'Quỹ BHYT trả', 'BHYT chi trả'), 'kind': 'menu.fund', 'align': 'right', 'w': 15, 'en': 'Insurer pays', 'describe': 'Portion of this line the health-insurance fund pays.'},

    # --------------------------------------------------- lấy từ pipeline chính
    # Mười ba cột `rulebase/layouts/*.yaml` đã dùng mà bộ này chưa có. Tiêu đề
    # và căn lề đọc từ chính các file bố cục ấy, không đặt lại: hai bộ sinh in
    # ra cùng một cột thì phải in cùng một chữ, nếu không một mô hình học trên
    # cả hai thấy hai cột khác nhau.
    'price_bv': {'titles': ('Đơn giá BV', 'Giá bệnh viện', 'Đơn giá dịch vụ'), 'kind': 'menu.price_bv', 'align': 'right', 'w': 13, 'en': 'Hospital price', 'describe': 'Unit price the hospital charges for this line.'},
    'price_bh': {'titles': ('Đơn giá BH', 'Giá bảo hiểm', 'Đơn giá BHYT'), 'kind': 'menu.price_bh', 'align': 'right', 'w': 13, 'en': 'Insured price', 'describe': 'Unit price the insurer recognises for this line.'},
    'amount_bv': {'titles': ('Thành tiền BV', 'Tiền bệnh viện'), 'kind': 'menu.amount_bv', 'align': 'right', 'w': 15, 'en': 'Hospital amount', 'describe': 'Line amount at the hospital price.'},
    'amount_bh': {'titles': ('Thành tiền BH', 'Tiền bảo hiểm'), 'kind': 'menu.amount_bh', 'align': 'right', 'w': 15, 'en': 'Insured amount', 'describe': 'Line amount at the price the insurer recognises.'},
    'rate_bhyt': {'titles': ('Tỷ lệ TT BHYT', 'Tỷ lệ BHYT', 'Mức hưởng'), 'kind': 'menu.rate_bhyt', 'align': 'center', 'w': 7, 'en': 'Insured %', 'describe': 'Share of this line the health-insurance fund pays, as a percentage.'},
    'rate_service': {'titles': ('Tỷ lệ TT dịch vụ', 'Tỷ lệ dịch vụ'), 'kind': 'menu.rate_service', 'align': 'center', 'w': 7, 'en': 'Service %', 'describe': 'Share of this line charged at the service rate, as a percentage.'},
    'self_pay': {'titles': ('Người bệnh tự chi trả', 'Tự chi trả', 'BN tự trả'), 'kind': 'menu.self_pay', 'align': 'right', 'w': 14, 'en': 'Self-paid', 'describe': 'Portion of this line the patient pays entirely themselves.'},
    'other_pay': {'titles': ('Khác', 'Nguồn khác', 'Chi khác'), 'kind': 'menu.other_pay', 'align': 'right', 'w': 10, 'en': 'Other', 'describe': 'Portion of this line paid from another source.'},
    'meter_prev': {'titles': ('Số Đọc Tháng Trước', 'Chỉ số cũ', 'CS cũ'), 'kind': 'menu.meter_prev', 'align': 'center', 'w': 14, 'en': 'Previous reading', 'describe': 'Meter reading recorded at the start of the billing period.'},
    'meter_now': {'titles': ('Số Đọc Tháng Này', 'Chỉ số mới', 'CS mới'), 'kind': 'menu.meter_now', 'align': 'center', 'w': 14, 'en': 'Current reading', 'describe': 'Meter reading recorded at the end of the billing period.'},
    'quota': {'titles': ('Định Mức Tiêu Thụ (m3)', 'Định mức', 'Mức tiêu thụ'), 'kind': 'menu.quota', 'align': 'right', 'w': 14, 'en': 'Quota', 'describe': 'Consumption allowance this line is billed against.'},
    'amount_with_vat': {'titles': ('Thành tiền có thuế GTGT', 'Tiền đã có VAT', 'Cộng có thuế'), 'kind': 'menu.amount_with_vat', 'align': 'right', 'w': 15, 'en': 'Amount incl. VAT', 'describe': 'Line amount after value added tax.'},
    'barcode': {'titles': ('Mã vạch', 'Barcode', 'Mã sản phẩm'), 'kind': 'menu.barcode', 'align': 'left', 'w': 14, 'en': 'Barcode', 'describe': 'Barcode printed against this line.'},
}


# -------------------------------------------------------------- trường & phôi


@dataclass(frozen=True)
class FieldDef:
    key: str
    labels: tuple[str, ...]
    gen: str
    en: str = ''
    wide: bool = False
    describe: str = ''


F = FieldDef

SELLER_FIELDS = (
    F('seller_name', ('Đơn vị bán hàng', 'Tên đơn vị bán', 'Bên bán', 'Đơn vị cung cấp'), 'org_name', 'Seller', True, 'Legal name of the selling organisation issuing this document.'),
    F('seller_tax', ('Mã số thuế', 'MST', 'Mã số thuế bên bán'), 'tax_code', 'Tax code', False, 'Tax identification number of the seller.'),
    F('seller_addr', ('Địa chỉ', 'Địa chỉ bên bán', 'Trụ sở'), 'address', 'Address', True, 'Registered address of the seller.'),
    F('seller_phone', ('Điện thoại', 'ĐT', 'Số điện thoại'), 'phone', 'Tel', False, 'Contact telephone of the seller.'),
    F('seller_bank', ('Số tài khoản', 'TK ngân hàng', 'Tài khoản'), 'bank_account', 'Bank account', True, 'Bank account the seller is paid into.'),
)

BUYER_FIELDS = (
    F('buyer_name', (
    'Họ tên người mua hàng',
    'Người mua hàng',
    'Khách hàng',
    'Tên người mua',
), 'person', 'Buyer', True, 'Full name of the individual buyer.'),
    F('buyer_org', ('Tên đơn vị', 'Đơn vị mua hàng', 'Bên mua', 'Tên công ty'), 'org_name', 'Buyer organisation', True, 'Legal name of the purchasing organisation.'),
    F('buyer_tax', ('Mã số thuế', 'MST người mua', 'Mã số thuế bên mua'), 'tax_code', 'Buyer tax code', False, 'Tax identification number of the buyer.'),
    F('buyer_addr', ('Địa chỉ', 'Địa chỉ người mua', 'Địa chỉ bên mua'), 'address', 'Buyer address', True, 'Address of the buyer.'),
    F('payment', ('Hình thức thanh toán', 'HT thanh toán', 'Phương thức TT'), 'payment', 'Payment method', False, 'How the amount was settled: cash, transfer, card or wallet.'),
)

SUBJECT_FIELDS = (
    F('full_name', ('Họ và tên', 'Họ tên', 'Họ và tên (CHỮ IN HOA)'), 'person', 'Full name', True, 'Full name of the person this document concerns.'),
    F('dob', ('Ngày sinh', 'Sinh ngày', 'Năm sinh'), 'birthdate', 'Date of birth', False, 'Date of birth of the person named.'),
    F('gender', ('Giới tính', 'Nam/Nữ'), 'gender', 'Sex', False, 'Sex of the person named.'),
    F('id_no', ('Số CCCD', 'CMND/CCCD', 'Số CCCD/Hộ chiếu', 'Số giấy tờ tuỳ thân'), 'id_number', 'ID number', False, 'National identity card or passport number of the person named.'),
    F('id_issue', ('Ngày cấp', 'Cấp ngày'), 'date', 'Issued on', False, 'Date the identity document was issued.'),
    F('id_place', ('Nơi cấp', 'Cấp tại'), 'issuer', 'Issued by', True, 'Authority that issued the identity document.'),
    F('address_home', ('Địa chỉ thường trú', 'Nơi ở hiện tại', 'Hộ khẩu thường trú', 'Địa chỉ liên hệ'), 'address', 'Residence', True, 'Registered or current residential address of the person named.'),
    F('phone_home', ('Số điện thoại', 'Điện thoại liên hệ', 'ĐT'), 'phone', 'Telephone', False, 'Contact telephone of the person named.'),
    F('unit', ('Đơn vị công tác', 'Bộ phận', 'Phòng ban', 'Đơn vị'), 'department', 'Department', True, 'Department or unit the person belongs to.'),
    F('position', ('Chức vụ', 'Chức danh', 'Vị trí công tác'), 'position', 'Position', False, 'Job title of the person named.'),
)

MEDICAL_FIELDS = (
    F('patient', ('Họ tên người bệnh', 'Họ và tên bệnh nhân', 'Người bệnh'), 'person', 'Patient', True, 'Full name of the patient.'),
    F('record_no', ('Số hồ sơ', 'Mã bệnh án', 'Số vào viện', 'Mã y tế'), 'record_no', 'Record number', False, 'Hospital record number for this episode of care.'),
    F('card_no', ('Số thẻ BHYT', 'Mã thẻ BHYT', 'Thẻ BHYT số'), 'bhyt', 'Health card', True, 'Vietnamese health-insurance card number of the patient.'),
    F('ward', ('Khoa điều trị', 'Khoa/Phòng', 'Khoa'), 'ward', 'Ward', False, 'Hospital ward or department the patient was treated in.'),
    F('admitted', ('Ngày vào viện', 'Vào viện lúc', 'Ngày nhập viện'), 'datetime', 'Admitted', False, 'Date and time the patient was admitted.'),
    F('discharged', ('Ngày ra viện', 'Ra viện lúc', 'Ngày xuất viện'), 'datetime', 'Discharged', False, 'Date and time the patient was discharged.'),
    F('diagnosis', ('Chẩn đoán', 'Chẩn đoán ra viện', 'Chẩn đoán chính'), 'diagnosis', 'Diagnosis', True, 'Clinical diagnosis recorded for this episode.'),
    F('treatment', ('Phương pháp điều trị', 'Hướng điều trị', 'Xử trí'), 'treatment', 'Treatment', True, 'Treatment given to the patient.'),
)

POLICY_FIELDS = (
    F('policy_no', ('Số hợp đồng', 'Số đơn bảo hiểm', 'Số GCN', 'Số hợp đồng bảo hiểm'), 'policy_no', 'Policy number', False, 'Insurance policy or certificate number.'),
    F('insured', ('Người được bảo hiểm', 'Bên được bảo hiểm', 'Tên người tham gia'), 'person', 'Insured', True, 'Person covered by this policy.'),
    F('holder', ('Bên mua bảo hiểm', 'Chủ hợp đồng'), 'org_name', 'Policyholder', True, 'Party that bought the policy.'),
    F('cover_from', ('Thời hạn từ', 'Hiệu lực từ', 'Từ ngày'), 'date', 'Cover from', False, 'First day the cover is in force.'),
    F('cover_to', ('Đến ngày', 'Hiệu lực đến', 'Thời hạn đến'), 'date', 'Cover to', False, 'Last day the cover is in force.'),
    F('sum_insured', ('Số tiền bảo hiểm', 'Mức trách nhiệm', 'Giá trị bảo hiểm'), 'money_big', 'Sum insured', False, 'Maximum amount the insurer will pay under this policy.'),
    F('premium', ('Phí bảo hiểm', 'Tổng phí', 'Phí phải nộp'), 'money_mid', 'Premium', False, 'Premium payable for the cover.'),
    F('object', ('Đối tượng bảo hiểm', 'Tài sản được bảo hiểm', 'Phạm vi bảo hiểm'), 'cover_object', 'Insured object', True, 'What the policy covers: the property, vehicle or risk.'),
)

UTILITY_FIELDS = (
    F('customer_no', ('Mã khách hàng', 'Mã KH', 'Số danh bộ'), 'customer_no', 'Customer code', False, 'Utility customer account code.'),
    F('meter_no', ('Số công tơ', 'Số đồng hồ', 'Mã công tơ'), 'meter_no', 'Meter number', False, 'Serial number of the meter that was read.'),
    F('period', ('Kỳ hoá đơn', 'Kỳ thanh toán', 'Tháng'), 'period', 'Billing period', False, 'Billing period this invoice covers.'),
    F('read_prev', ('Chỉ số cũ', 'CS cũ', 'Chỉ số đầu kỳ'), 'meter_prev', 'Previous reading', False, 'Meter reading at the start of the period.'),
    F('read_now', ('Chỉ số mới', 'CS mới', 'Chỉ số cuối kỳ'), 'meter_now', 'Current reading', False, 'Meter reading at the end of the period.'),
    F('consumed', ('Sản lượng', 'Điện năng tiêu thụ', 'Lượng tiêu thụ'), 'consumed', 'Consumption', False, 'Units consumed during the period.'),
)

STAY_FIELDS = (
    F('room', ('Số phòng', 'Phòng', 'Loại phòng'), 'room', 'Room', False, 'Room number or room type occupied.'),
    F('guest', ('Tên khách', 'Khách hàng', 'Họ tên khách'), 'person', 'Guest', True, 'Name of the guest the folio belongs to.'),
    F('checkin', ('Ngày đến', 'Nhận phòng', 'Check-in'), 'datetime', 'Check-in', False, 'Date and time the guest checked in.'),
    F('checkout', ('Ngày đi', 'Trả phòng', 'Check-out'), 'datetime', 'Check-out', False, 'Date and time the guest checked out.'),
    F('nights', ('Số đêm', 'Số ngày lưu trú'), 'nights', 'Nights', False, 'Number of nights stayed.'),
)

CONTRACT_FIELDS = (
    F('contract_no', ('Số hợp đồng', 'Hợp đồng số', 'Số HĐ'), 'contract_no', 'Contract number', False, 'Reference number of the contract.'),
    F('party_a', ('Bên A', 'Bên giao', 'Bên thuê'), 'org_name', 'Party A', True, 'First party to the contract.'),
    F('party_b', ('Bên B', 'Bên nhận', 'Bên cho thuê'), 'org_name', 'Party B', True, 'Second party to the contract.'),
    F('rep_a', ('Đại diện', 'Người đại diện', 'Đại diện bởi'), 'person', 'Representative', True, 'Person signing on behalf of the party.'),
    F('value', ('Giá trị hợp đồng', 'Tổng giá trị', 'Giá trị'), 'money_big', 'Contract value', False, 'Total value of the contract.'),
    F('term', ('Thời hạn', 'Thời hạn hợp đồng'), 'term', 'Term', False, 'How long the contract runs for.'),
)


@dataclass(frozen=True)
class Archetype:
    id: str
    titles: tuple[str, ...]
    subtitles: tuple[str, ...]
    profile: str
    org_kind: str
    national: float
    field_pool: tuple[FieldDef, ...]
    field_span: tuple[int, int]
    column_pool: tuple[tuple[str, ...], ...]
    totals: str
    words: bool
    sign_sets: tuple[tuple[str, ...], ...]
    notes: tuple[str, ...]
    rows: tuple[int, int]
    optional: tuple[str, ...] = ()
    always: tuple[str, ...] = ()
    en_ok: bool = False
    # Trần số tờ phôi TỰ KHAI. 0 = không khai, sức chứa khối chảy quyết.
    max_pages: int = 0


_SIGN_SALES = (('NGƯỜI MUA HÀNG', 'NGƯỜI BÁN HÀNG'), ('NGƯỜI MUA HÀNG', 'NGƯỜI BÁN HÀNG', 'THỦ TRƯỞNG ĐƠN VỊ'), ('Khách hàng', 'Nhân viên bán hàng'), ('NGƯỜI LẬP PHIẾU', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC'))

_SIGN_STORE = (('NGƯỜI LẬP PHIẾU', 'NGƯỜI GIAO HÀNG', 'THỦ KHO', 'KẾ TOÁN TRƯỞNG'), ('NGƯỜI NHẬN HÀNG', 'THỦ KHO', 'GIÁM ĐỐC'), ('NGƯỜI LẬP', 'THỦ TRƯỞNG ĐƠN VỊ'))

_SIGN_STATE = (('NGƯỜI LÀM ĐƠN', 'XÁC NHẬN CỦA ĐƠN VỊ'), ('NGƯỜI ĐỀ NGHỊ', 'PHỤ TRÁCH BỘ PHẬN', 'THỦ TRƯỞNG ĐƠN VỊ'), ('NƠI NHẬN', 'TM. ĐƠN VỊ'), ('NGƯỜI VIẾT ĐƠN',))

_SIGN_MINUTES = (('THƯ KÝ', 'CHỦ TRÌ'), ('ĐẠI DIỆN BÊN GIAO', 'ĐẠI DIỆN BÊN NHẬN'), ('THƯ KÝ CUỘC HỌP', 'CHỦ TOẠ', 'ĐẠI DIỆN CÁC BÊN'))

_SIGN_MEDICAL = (('BÁC SĨ ĐIỀU TRỊ', 'TRƯỞNG KHOA'), ('NGƯỜI LẬP BẢNG', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC BỆNH VIỆN'), ('NGƯỜI BỆNH', 'NHÂN VIÊN THU NGÂN'))

_SIGN_INSURE = (('BÊN MUA BẢO HIỂM', 'DOANH NGHIỆP BẢO HIỂM'), ('NGƯỜI ĐƯỢC BẢO HIỂM', 'ĐẠI DIỆN CÔNG TY'), ('CÁN BỘ KHAI THÁC', 'GIÁM ĐỐC'))

_NOTE_SALES = (
    'Hoá đơn này được lập theo quy định về hoá đơn điện tử; người mua có trách nhiệm đối chiếu nội dung trước khi thanh toán.',
    'Hàng đã bán được đổi trong 07 ngày kể từ ngày ghi trên hoá đơn, còn nguyên tem nhãn và phiếu này.',
    'Giá trên đã bao gồm thuế giá trị gia tăng theo thuế suất ghi trong bảng kê.',
    'Mọi khiếu nại về số lượng và chất lượng xin gửi trong vòng 03 ngày làm việc kể từ ngày nhận hàng.',
    'Đề nghị quý khách kiểm tra kỹ hàng hoá và giữ lại chứng từ này để đối chiếu khi cần.',
    'Thanh toán chậm quá thời hạn ghi trên chứng từ chịu lãi suất theo thoả thuận giữa hai bên.',
)

_NOTE_STATE = (
    'Kính đề nghị Thủ trưởng đơn vị xem xét, giải quyết theo thẩm quyền.',
    'Đơn vị nhận được văn bản này có trách nhiệm triển khai và báo cáo kết quả trước ngày cuối tháng.',
    'Các nội dung khác không nêu trong văn bản này thực hiện theo quy định hiện hành.',
    'Văn bản này được lập thành 02 bản có giá trị như nhau, mỗi bên giữ 01 bản.',
    'Trong quá trình thực hiện nếu có vướng mắc, đề nghị phản ánh về bộ phận thường trực để được hướng dẫn.',
    'Người khai cam đoan những nội dung ghi trên là đúng sự thật và chịu trách nhiệm trước pháp luật.',
)

_NOTE_MEDICAL = (
    'Bảng kê này là căn cứ thanh toán chi phí khám chữa bệnh giữa người bệnh và cơ sở y tế.',
    'Phần chi phí thuộc phạm vi chi trả của quỹ bảo hiểm y tế được xác định theo mức hưởng ghi trên thẻ.',
    'Người bệnh giữ bảng kê này để đối chiếu khi có yêu cầu giải quyết quyền lợi bảo hiểm.',
    'Thuốc và vật tư ngoài danh mục bảo hiểm y tế do người bệnh tự chi trả toàn bộ.',
    'Đề nghị người bệnh kiểm tra thông tin cá nhân và các khoản chi phí trước khi ký xác nhận.',
)

_NOTE_INSURE = (
    'Giấy chứng nhận này là bộ phận không tách rời của hợp đồng bảo hiểm đã giao kết giữa hai bên.',
    'Quyền lợi bảo hiểm chỉ phát sinh khi phí bảo hiểm đã được thanh toán đầy đủ và đúng hạn.',
    'Các trường hợp loại trừ trách nhiệm bảo hiểm thực hiện theo quy tắc bảo hiểm kèm theo.',
    'Khi xảy ra sự kiện bảo hiểm, người được bảo hiểm phải thông báo cho doanh nghiệp bảo hiểm trong thời hạn quy định.',
    'Mọi sửa đổi, bổ sung hợp đồng phải được lập thành văn bản và có xác nhận của cả hai bên.',
)

_NOTE_TECH = (
    'Thiết bị được bảo hành theo điều kiện của nhà sản xuất kể từ ngày ghi trên chứng từ này.',
    'Không bảo hành các hư hỏng do rơi vỡ, vào nước, sử dụng sai điện áp hoặc tự ý can thiệp phần cứng.',
    'Khách hàng vui lòng mang theo phiếu này khi yêu cầu bảo hành hoặc sửa chữa.',
    'Thời gian xử lý bảo hành tiêu chuẩn là 07 đến 14 ngày làm việc tuỳ mức độ hư hỏng.',
)


A = Archetype

ARCHETYPES: tuple[Archetype, ...] = (
    A('hoa_don_gtgt', ('HOÁ ĐƠN GIÁ TRỊ GIA TĂNG', 'HOÁ ĐƠN GTGT', 'HOÁ ĐƠN BÁN HÀNG'), (
    '(Bản thể hiện của hoá đơn điện tử)',
    'Liên 2: Giao người mua',
    'VAT INVOICE',
    '',
), 'invoice', 'company', 0.05, SELLER_FIELDS + BUYER_FIELDS, (6, 10), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'unit', 'qty', 'unit_price', 'vat_rate', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'unit_price', 'vat_rate', 'vat_amount', 'amount')), 'money', True, _SIGN_SALES, _NOTE_SALES, (3, 100), optional=('notes', 'words', 'meta', 'footer', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures'), en_ok=True),
    A('hoa_don_ban_le', ('PHIẾU TÍNH TIỀN', 'HOÁ ĐƠN BÁN LẺ', 'PHIẾU THANH TOÁN', 'HOÁ ĐƠN'), ('', 'Cảm ơn quý khách', 'Kính chào quý khách'), 'market', 'shop', 0.0, BUYER_FIELDS[:1] + BUYER_FIELDS[4:], (1, 3), (('stt', 'name', 'qty', 'unit_price', 'amount'), ('name', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'amount'), ('ref', 'name', 'qty', 'unit_price', 'amount')), 'money', False, (('Thu ngân',), ('Khách hàng', 'Thu ngân')), _NOTE_SALES, (4, 70), optional=('notes', 'meta', 'footer', 'signatures'), always=('letterhead', 'doctitle', 'table', 'totals')),
    A('phieu_thu', ('PHIẾU THU', 'BIÊN LAI THU TIỀN', 'PHIẾU THU TIỀN MẶT'), ('(Liên 1: Lưu)', '(Liên 2: Giao người nộp tiền)', ''), 'admin', 'company', 0.35, BUYER_FIELDS[:1] + SUBJECT_FIELDS[6:8] + CONTRACT_FIELDS[:1], (3, 5), (('stt', 'name', 'amount'), ('stt', 'name', 'note', 'amount'), ('stt', 'ref', 'name', 'amount')), 'money', True, (('NGƯỜI NỘP TIỀN', 'NGƯỜI THU TIỀN', 'KẾ TOÁN TRƯỞNG'), ('NGƯỜI NỘP TIỀN', 'THỦ QUỸ', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC')), _NOTE_STATE, (1, 14), optional=('notes', 'meta', 'footer', 'words'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('phieu_chi', ('PHIẾU CHI', 'GIẤY ĐỀ NGHỊ THANH TOÁN', 'PHIẾU CHI TIỀN MẶT'), ('(Liên 1: Lưu)', '', 'Quyển số: ....'), 'admin', 'company', 0.35, BUYER_FIELDS[:1] + SUBJECT_FIELDS[6:10], (3, 6), (('stt', 'name', 'amount'), ('stt', 'name', 'unit', 'qty', 'amount')), 'money', True, (('NGƯỜI NHẬN TIỀN', 'THỦ QUỸ', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC'), ('NGƯỜI ĐỀ NGHỊ', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC')), _NOTE_STATE, (1, 18), optional=('notes', 'meta', 'footer', 'words'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('phieu_xuat_kho', ('PHIẾU XUẤT KHO', 'PHIẾU XUẤT KHO KIÊM VẬN CHUYỂN NỘI BỘ'), ('', '(Liên 2: Giao khách hàng)', 'Số:....'), 'invoice', 'company', 0.2, SELLER_FIELDS[:3] + BUYER_FIELDS[1:4] + SUBJECT_FIELDS[8:10], (4, 8), (('stt', 'name', 'ref', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'unit', 'qty', 'note'), ('stt', 'ref', 'name', 'unit', 'qty', 'amount')), 'money', True, _SIGN_STORE, _NOTE_SALES, (4, 130), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('phieu_nhap_kho', ('PHIẾU NHẬP KHO', 'BIÊN BẢN GIAO NHẬN HÀNG HOÁ'), ('', 'Số:....', '(Liên 1: Lưu)'), 'invoice', 'company', 0.2, SELLER_FIELDS[:3] + BUYER_FIELDS[1:3] + SUBJECT_FIELDS[8:10], (4, 8), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'note'), ('stt', 'name', 'unit', 'qty', 'amount', 'note')), 'money', True, _SIGN_STORE, _NOTE_SALES, (4, 120), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('bang_ke_chi_tiet', ('BẢNG KÊ CHI TIẾT', 'BẢNG KÊ HÀNG HOÁ, DỊCH VỤ', 'BẢNG TỔNG HỢP CHI PHÍ'), ('(Kèm theo hoá đơn số ....)', '', 'Kỳ báo cáo: ....'), 'invoice', 'company', 0.15, SELLER_FIELDS[:2] + BUYER_FIELDS[1:4], (2, 5), (('stt', 'date', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'ref', 'name', 'qty', 'unit_price', 'vat_rate', 'vat_amount', 'amount'), ('stt', 'date', 'ref', 'name', 'amount', 'note')), 'money', True, (('NGƯỜI LẬP BẢNG', 'KẾ TOÁN TRƯỞNG'), ('NGƯỜI LẬP BẢNG', 'KẾ TOÁN TRƯỞNG', 'THỦ TRƯỞNG ĐƠN VỊ')), _NOTE_SALES, (12, 240), optional=('notes', 'meta', 'footer', 'words', 'summary', 'fields'), always=('letterhead', 'doctitle', 'table', 'totals', 'signatures')),
    A('bang_luong', ('BẢNG THANH TOÁN TIỀN LƯƠNG', 'BẢNG LƯƠNG', 'BẢNG THANH TOÁN THU NHẬP'), ('Tháng ..../....', '', '(Ban hành kèm Quyết định số ....)'), 'admin', 'company', 0.3, SELLER_FIELDS[:1] + SUBJECT_FIELDS[8:9], (1, 3), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'unit_price', 'discount', 'amount'), ('stt', 'ref', 'name', 'qty', 'amount', 'note')), 'money', True, (('NGƯỜI LẬP BẢNG', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC'), ('NGƯỜI LẬP BẢNG', 'PHÒNG NHÂN SỰ', 'KẾ TOÁN TRƯỞNG', 'GIÁM ĐỐC')), _NOTE_STATE, (10, 200), optional=('notes', 'meta', 'footer', 'words', 'summary', 'fields'), always=('letterhead', 'doctitle', 'table', 'totals', 'signatures')),
    A('bang_cham_cong', ('BẢNG CHẤM CÔNG', 'BẢNG THEO DÕI NGÀY CÔNG', 'BẢNG CHẤM CÔNG THÁNG'), ('Tháng ..../....', 'Bộ phận: ....', ''), 'admin', 'company', 0.35, SELLER_FIELDS[:1] + SUBJECT_FIELDS[8:9], (1, 3), (('stt', 'name', 'qty', 'note'), ('stt', 'ref', 'name', 'qty', 'unit', 'note'), ('stt', 'name', 'date', 'qty', 'note')), 'count', False, (('NGƯỜI CHẤM CÔNG', 'PHỤ TRÁCH BỘ PHẬN', 'THỦ TRƯỞNG ĐƠN VỊ'),), _NOTE_STATE, (8, 170), optional=('notes', 'meta', 'footer', 'fields'), always=('letterhead', 'doctitle', 'table', 'signatures')),
    A('bien_ban_ban_giao', ('BIÊN BẢN BÀN GIAO', 'BIÊN BẢN BÀN GIAO TÀI SẢN', 'BIÊN BẢN GIAO NHẬN THIẾT BỊ'), ('', 'Số: ..../BB-BG', ''), 'invoice', 'company', 0.55, CONTRACT_FIELDS[1:4] + SUBJECT_FIELDS[8:10], (3, 6), (('stt', 'name', 'unit', 'qty', 'note'), ('stt', 'ref', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'note')), 'count', False, _SIGN_MINUTES, _NOTE_STATE, (3, 90), optional=('meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'notes', 'table', 'signatures')),
    A('bien_ban_hop', ('BIÊN BẢN HỌP', 'BIÊN BẢN CUỘC HỌP', 'BIÊN BẢN HỌP GIAO BAN'), ('Số: ..../BB', '', 'V/v triển khai kế hoạch công tác'), 'admin', 'company', 0.6, SUBJECT_FIELDS[8:10] + CONTRACT_FIELDS[1:3], (2, 5), (('stt', 'name', 'note'), ('stt', 'name', 'unit', 'note'), ('stt', 'ref', 'name', 'note')), 'none', False, _SIGN_MINUTES, _NOTE_STATE, (3, 60), optional=('table', 'meta', 'footer'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures')),
    A('cong_van', ('CÔNG VĂN', 'V/v hướng dẫn thực hiện công tác chuyên môn', 'V/v đôn đốc báo cáo định kỳ'), ('Kính gửi: Các đơn vị trực thuộc', 'Kính gửi: Phòng Tài chính - Kế toán', ''), 'admin', 'state', 0.95, SUBJECT_FIELDS[8:10], (0, 2), (('stt', 'name', 'note'), ('stt', 'name', 'date', 'note')), 'none', False, (('NƠI NHẬN', 'TM. THỦ TRƯỞNG ĐƠN VỊ'), ('NƠI NHẬN', 'KT. GIÁM ĐỐC'), ('TM. BAN GIÁM ĐỐC',)), _NOTE_STATE, (0, 28), optional=('table', 'fields', 'questions', 'clauses', 'footer'), always=('letterhead', 'doctitle', 'meta', 'notes', 'signatures')),
    A('to_trinh', ('TỜ TRÌNH', 'TỜ TRÌNH ĐỀ NGHỊ PHÊ DUYỆT', 'GIẤY ĐỀ NGHỊ'), ('V/v đề nghị cấp kinh phí', 'V/v đề nghị mua sắm trang thiết bị', ''), 'admin', 'state', 0.9, SUBJECT_FIELDS[8:10] + CONTRACT_FIELDS[4:5], (1, 3), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'amount'), ('stt', 'name', 'note')), 'money', True, (('NGƯỜI ĐỀ NGHỊ', 'THỦ TRƯỞNG ĐƠN VỊ'), ('NGƯỜI LẬP', 'PHỤ TRÁCH BỘ PHẬN', 'THỦ TRƯỞNG ĐƠN VỊ')), _NOTE_STATE, (2, 64), optional=('table', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'meta', 'fields', 'notes', 'signatures')),
    A('don_xin_nghi_phep', ('ĐƠN XIN NGHỈ PHÉP', 'ĐƠN XIN NGHỈ VIỆC RIÊNG', 'GIẤY XIN PHÉP'), ('Kính gửi: Ban Giám đốc', 'Kính gửi: Trưởng phòng Hành chính - Nhân sự', ''), 'admin', 'state', 0.85, SUBJECT_FIELDS[:1] + SUBJECT_FIELDS[1:2] + SUBJECT_FIELDS[6:10], (4, 7), (('stt', 'date', 'name', 'note'),), 'none', False, _SIGN_STATE, _NOTE_STATE, (0, 6), optional=('table', 'footer', 'meta'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures')),
    A('giay_uy_quyen', ('GIẤY UỶ QUYỀN', 'GIẤY UỶ QUYỀN GIAO DỊCH', 'VĂN BẢN UỶ QUYỀN'), ('', 'Số: ..../GUQ', '(Có giá trị đến hết ngày ....)'), 'admin', 'state', 0.8, SUBJECT_FIELDS[:8], (5, 8), (('stt', 'name', 'note'),), 'none', False, (('BÊN UỶ QUYỀN', 'BÊN ĐƯỢC UỶ QUYỀN'), ('NGƯỜI UỶ QUYỀN', 'NGƯỜI ĐƯỢC UỶ QUYỀN', 'XÁC NHẬN CỦA ĐƠN VỊ')), _NOTE_STATE, (0, 16), optional=('table', 'footer', 'meta'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures')),
    A('giay_gioi_thieu', ('GIẤY GIỚI THIỆU', 'GIẤY GIỚI THIỆU CÔNG TÁC'), ('Kính gửi: ....', '', 'Số: ..../GGT'), 'admin', 'state', 0.9, SUBJECT_FIELDS[:1] + SUBJECT_FIELDS[3:5] + SUBJECT_FIELDS[8:10], (3, 5), (('stt', 'name', 'note'),), 'none', False, (('TM. THỦ TRƯỞNG ĐƠN VỊ',), ('NGƯỜI GIỚI THIỆU', 'THỦ TRƯỞNG ĐƠN VỊ')), _NOTE_STATE, (4, 40), optional=('table', 'footer', 'photo'), always=('letterhead', 'doctitle', 'meta', 'fields', 'notes', 'signatures'), max_pages=1),
    A('don_dang_ky', (
    'ĐƠN ĐĂNG KÝ',
    'PHIẾU ĐĂNG KÝ THÔNG TIN',
    'TỜ KHAI ĐĂNG KÝ',
    'PHIẾU ĐĂNG KÝ DỊCH VỤ',
), ('(Dùng cho cá nhân)', 'Mẫu số 01/ĐK', ''), 'admin', 'state', 0.75, SUBJECT_FIELDS, (6, 10), (('stt', 'name', 'note'), ('stt', 'name', 'unit', 'qty', 'note')), 'none', False, _SIGN_STATE, _NOTE_STATE, (0, 26), optional=('table', 'footer', 'checks', 'photo'), always=('letterhead', 'doctitle', 'meta', 'fields', 'notes', 'signatures')),
    A('bang_cau_hoi_benh', ('BẢNG CÂU HỎI BỆNH KHỚP', 'BẢNG CÂU HỎI SỨC KHOẺ', 'PHIẾU KHAI BÁO TÌNH TRẠNG BỆNH'), ('', '(Dùng cho thẩm định hợp đồng bảo hiểm)', 'Mẫu BH-02'), 'admin', 'company', 0.0, SUBJECT_FIELDS[:1] + CONTRACT_FIELDS[:1], (2, 3), (('stt', 'name', 'note'),), 'none', False, (('NGƯỜI ĐƯỢC BẢO HIỂM', 'NGƯỜI LÀM CHỨNG'), ('Người khai', 'Chuyên viên tư vấn')), _NOTE_STATE, (0, 0), optional=('meta', 'footer', 'notes'), always=('letterhead', 'doctitle', 'fields', 'questions', 'signatures')),
    A('to_khai_tham_dinh', ('TỜ KHAI THẨM ĐỊNH', 'PHIẾU KHAI BÁO THÔNG TIN', 'BẢNG CÂU HỎI THẨM ĐỊNH'), ('(Quý khách vui lòng điền đầy đủ)', '', 'Mẫu TĐ-01'), 'admin', 'company', 0.1, SUBJECT_FIELDS[:3], (2, 4), (('stt', 'name', 'note'),), 'none', False, (('NGƯỜI KHAI', 'CÁN BỘ TIẾP NHẬN'),), _NOTE_STATE, (0, 14), optional=('meta', 'footer', 'notes', 'table', 'checks'), always=('letterhead', 'doctitle', 'fields', 'questions', 'signatures')),
    A('phieu_khao_sat', ('PHIẾU KHẢO SÁT Ý KIẾN', 'PHIẾU ĐÁNH GIÁ CHẤT LƯỢNG DỊCH VỤ', 'PHIẾU LẤY Ý KIẾN KHÁCH HÀNG'), ('(Quý khách vui lòng đánh dấu X vào ô phù hợp)', '', 'Mẫu KS-01'), 'admin', 'company', 0.25, SUBJECT_FIELDS[:1] + SUBJECT_FIELDS[7:10], (2, 4), (('stt', 'name', 'note'),), 'none', False, (('NGƯỜI KHẢO SÁT',), ('Người trả lời', 'Cán bộ khảo sát')), _NOTE_STATE, (0, 24), optional=('table', 'footer', 'meta'), always=('letterhead', 'doctitle', 'fields', 'checks', 'signatures')),
    A('hoa_don_vien_phi', ('BẢNG KÊ CHI PHÍ KHÁM BỆNH, CHỮA BỆNH', 'HOÁ ĐƠN VIỆN PHÍ', 'BẢNG KÊ CHI PHÍ ĐIỀU TRỊ'), ('(Ban hành kèm theo Thông tư của Bộ Y tế)', 'Mẫu số: 01/BV', ''), 'medical', 'hospital', 0.45, MEDICAL_FIELDS, (5, 8), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'qty', 'unit_price', 'fund', 'copay', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'unit_price', 'amount', 'note'), ('stt', 'name', 'qty', 'unit_price', 'amount', 'fund', 'copay')), 'money', True, _SIGN_MEDICAL, _NOTE_MEDICAL, (10, 240), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('don_thuoc', ('ĐƠN THUỐC', 'ĐƠN THUỐC ĐIỀU TRỊ NGOẠI TRÚ', 'PHIẾU LĨNH THUỐC'), ('(Đơn thuốc có giá trị mua thuốc trong 05 ngày)', '', 'Mẫu số 01/ĐT'), 'medical', 'hospital', 0.4, MEDICAL_FIELDS[:1] + MEDICAL_FIELDS[1:3] + MEDICAL_FIELDS[6:8], (4, 6), (('stt', 'name', 'unit', 'qty', 'note'), ('stt', 'name', 'qty', 'note'), ('stt', 'ref', 'name', 'unit', 'qty', 'note')), 'count', False, (('BÁC SĨ KÊ ĐƠN',), ('NGƯỜI BỆNH', 'BÁC SĨ ĐIỀU TRỊ')), _NOTE_MEDICAL, (2, 22), optional=('meta', 'footer', 'notes'), always=('letterhead', 'doctitle', 'fields', 'table', 'signatures')),
    A('giay_ra_vien', ('GIẤY RA VIỆN', 'GIẤY CHỨNG NHẬN NGHỈ VIỆC HƯỞNG BHXH', 'TÓM TẮT BỆNH ÁN'), ('Mẫu số: 01/BV-01', '', '(Ban hành kèm theo Thông tư số 56/2017/TT-BYT)'), 'medical', 'hospital', 0.7, MEDICAL_FIELDS + SUBJECT_FIELDS[6:8], (6, 9), (('stt', 'date', 'name', 'note'), ('stt', 'name', 'unit', 'qty', 'note')), 'none', False, _SIGN_MEDICAL, _NOTE_MEDICAL, (0, 20), optional=('table', 'meta', 'footer'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures')),
    A('giay_chung_nhan_bao_hiem', (
    'GIẤY CHỨNG NHẬN BẢO HIỂM',
    'GIẤY CHỨNG NHẬN BẢO HIỂM XE CƠ GIỚI',
    'ĐƠN BẢO HIỂM',
    'GIẤY CHỨNG NHẬN BẢO HIỂM CHÁY NỔ',
), ('INSURANCE CERTIFICATE', '(Bản dành cho khách hàng)', ''), 'insurance', 'company', 0.1, POLICY_FIELDS + SUBJECT_FIELDS[6:8], (6, 10), (('stt', 'name', 'amount'), ('stt', 'name', 'unit', 'amount', 'note'), ('stt', 'ref', 'name', 'amount')), 'money', False, _SIGN_INSURE, _NOTE_INSURE, (0, 26), optional=('table', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures'), en_ok=True),
    A('bang_ke_quyen_loi', ('BẢNG KÊ QUYỀN LỢI BẢO HIỂM', 'BẢNG TÓM TẮT QUYỀN LỢI', 'PHỤ LỤC QUYỀN LỢI BẢO HIỂM'), ('(Đính kèm hợp đồng bảo hiểm số ....)', '', 'SCHEDULE OF BENEFITS'), 'insurance', 'company', 0.05, POLICY_FIELDS[:6], (3, 6), (('stt', 'name', 'unit', 'amount', 'note'), ('stt', 'ref', 'name', 'amount', 'copay', 'note'), ('stt', 'name', 'qty', 'unit_price', 'amount')), 'money', True, (('NGƯỜI ĐƯỢC BẢO HIỂM', 'DOANH NGHIỆP BẢO HIỂM'),), _NOTE_INSURE, (6, 150), optional=('notes', 'meta', 'footer', 'words', 'summary', 'fields'), always=('letterhead', 'doctitle', 'table', 'totals', 'signatures'), en_ok=True),
    A('hoa_don_tien_dien', ('HOÁ ĐƠN TIỀN ĐIỆN', 'THÔNG BÁO TIỀN ĐIỆN', 'HOÁ ĐƠN GTGT TIỀN ĐIỆN'), ('(Bản thể hiện của hoá đơn điện tử)', 'Kỳ ..../....', ''), 'power', 'company', 0.05, UTILITY_FIELDS + BUYER_FIELDS[:1] + BUYER_FIELDS[3:4], (5, 8), (('stt', 'name', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'unit', 'qty', 'unit_price', 'vat_rate', 'amount'), ('stt', 'ref', 'name', 'qty', 'unit_price', 'amount')), 'money', True, (('NGƯỜI NỘP TIỀN', 'NHÂN VIÊN THU'), ('KHÁCH HÀNG', 'ĐƠN VỊ PHÁT HÀNH')), _NOTE_SALES, (2, 18), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals')),
    A('hoa_don_tien_nuoc', ('HOÁ ĐƠN TIỀN NƯỚC', 'THÔNG BÁO TIỀN NƯỚC', 'HOÁ ĐƠN GTGT TIỀN NƯỚC'), ('(Bản thể hiện của hoá đơn điện tử)', 'Kỳ ..../....', ''), 'water', 'company', 0.05, UTILITY_FIELDS + BUYER_FIELDS[:1] + BUYER_FIELDS[3:4], (5, 8), (('stt', 'name', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'unit', 'qty', 'unit_price', 'vat_rate', 'amount')), 'money', True, (('NGƯỜI NỘP TIỀN', 'NHÂN VIÊN THU'), ('KHÁCH HÀNG', 'ĐƠN VỊ PHÁT HÀNH')), _NOTE_SALES, (2, 18), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals')),
    A('phieu_dat_phong', (
    'HOÁ ĐƠN LƯU TRÚ',
    'PHIẾU THANH TOÁN PHÒNG',
    'GUEST FOLIO',
    'PHIẾU DỊCH VỤ LƯU TRÚ',
), ('', 'Kính chào quý khách', 'HOTEL INVOICE'), 'hotel', 'company', 0.0, STAY_FIELDS + BUYER_FIELDS[3:5], (4, 7), (('stt', 'date', 'name', 'qty', 'unit_price', 'amount'), ('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('date', 'name', 'qty', 'amount')), 'money', True, (('KHÁCH HÀNG', 'LỄ TÂN'), ('Khách hàng', 'Nhân viên', 'Quản lý')), _NOTE_SALES, (3, 72), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals'), en_ok=True),
    A('thuc_don', ('THỰC ĐƠN', 'MENU', 'BẢNG GIÁ MÓN ĂN', 'THỰC ĐƠN NHÀ HÀNG'), ('Giá đã bao gồm VAT', '', 'Phục vụ từ 10:00 đến 22:00'), 'menu', 'shop', 0.0, BUYER_FIELDS[:0], (0, 1), (('stt', 'name', 'unit_price'), ('name', 'unit', 'unit_price'), ('stt', 'name', 'unit', 'unit_price', 'note')), 'none', False, (), _NOTE_SALES, (8, 160), optional=('notes', 'footer', 'meta', 'totals'), always=('letterhead', 'doctitle', 'table')),
    A('bao_gia', ('BÁO GIÁ', 'BẢNG BÁO GIÁ', 'THƯ CHÀO GIÁ', 'QUOTATION'), ('(Báo giá có hiệu lực trong 15 ngày)', 'Số: ..../BG', ''), 'invoice', 'company', 0.05, SELLER_FIELDS + BUYER_FIELDS[1:4], (5, 9), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'unit_price', 'vat_rate', 'amount'), ('stt', 'name', 'qty', 'unit_price', 'discount', 'amount')), 'money', True, (('NGƯỜI LẬP BÁO GIÁ', 'GIÁM ĐỐC'), ('BÊN BÁO GIÁ', 'BÊN NHẬN BÁO GIÁ')), _NOTE_SALES, (3, 110), optional=('notes', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures'), en_ok=True),
    A('phieu_bao_hanh', ('PHIẾU BẢO HÀNH', 'THẺ BẢO HÀNH', 'PHIẾU TIẾP NHẬN BẢO HÀNH'), ('(Vui lòng giữ phiếu này khi bảo hành)', '', 'WARRANTY CARD'), 'invoice', 'shop', 0.0, BUYER_FIELDS[:1] + BUYER_FIELDS[3:4] + SUBJECT_FIELDS[7:8] + CONTRACT_FIELDS[:1] + CONTRACT_FIELDS[5:6], (4, 6), (('stt', 'ref', 'name', 'qty', 'note'), ('stt', 'name', 'unit', 'qty', 'date', 'note')), 'none', False, (('KHÁCH HÀNG', 'ĐẠI DIỆN CỬA HÀNG'), ('Khách hàng', 'Kỹ thuật viên')), _NOTE_TECH, (1, 18), optional=('table', 'meta', 'footer', 'checks'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures'), en_ok=True),
    A('bien_lai_thu_phi', ('BIÊN LAI THU PHÍ', 'BIÊN LAI THU LỆ PHÍ', 'BIÊN LAI THU TIỀN'), ('(Liên 2: Giao người nộp)', 'Mẫu: C300-BL', ''), 'admin', 'state', 0.65, SUBJECT_FIELDS[:1] + SUBJECT_FIELDS[6:8] + CONTRACT_FIELDS[:1], (3, 5), (('stt', 'name', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'amount')), 'money', True, (('NGƯỜI NỘP TIỀN', 'NGƯỜI THU TIỀN'), ('NGƯỜI NỘP TIỀN', 'NGƯỜI THU TIỀN', 'THỦ TRƯỞNG ĐƠN VỊ')), _NOTE_STATE, (1, 16), optional=('notes', 'meta', 'footer', 'words'), always=('letterhead', 'doctitle', 'fields', 'table', 'totals', 'signatures')),
    A('danh_sach_hoc_vien', ('DANH SÁCH HỌC VIÊN', 'DANH SÁCH CÁN BỘ THAM DỰ', 'DANH SÁCH ĐỀ NGHỊ PHÊ DUYỆT'), ('(Kèm theo Quyết định số ....)', 'Khoá ..../....', ''), 'admin', 'state', 0.7, SELLER_FIELDS[:1] + SUBJECT_FIELDS[8:9], (1, 3), (('stt', 'name', 'date', 'unit', 'note'), ('stt', 'ref', 'name', 'unit', 'note'), ('stt', 'name', 'unit', 'qty', 'note')), 'count', False, (('NGƯỜI LẬP DANH SÁCH', 'THỦ TRƯỞNG ĐƠN VỊ'),), _NOTE_STATE, (10, 200), optional=('notes', 'meta', 'footer', 'fields'), always=('letterhead', 'doctitle', 'table', 'signatures')),
    A('hop_dong_kinh_te', ('HỢP ĐỒNG KINH TẾ', 'HỢP ĐỒNG MUA BÁN HÀNG HOÁ', 'HỢP ĐỒNG CUNG CẤP DỊCH VỤ'), ('Số: ..../HĐKT', '(Trích Điều 1 - Điều 3)', ''), 'invoice', 'company', 0.75, CONTRACT_FIELDS + SELLER_FIELDS[1:3], (5, 8), (('stt', 'name', 'unit', 'qty', 'unit_price', 'amount'), ('stt', 'ref', 'name', 'unit', 'qty', 'unit_price', 'vat_rate', 'amount')), 'money', True, (('ĐẠI DIỆN BÊN A', 'ĐẠI DIỆN BÊN B'), ('BÊN A', 'BÊN B'), ('ĐẠI DIỆN BÊN A', 'ĐẠI DIỆN BÊN B', 'XÁC NHẬN')), _NOTE_SALES, (2, 80), optional=('table', 'meta', 'footer', 'words', 'summary'), always=('letterhead', 'doctitle', 'fields', 'notes', 'signatures')),
)


# Phôi khai bằng FILE, gộp vào danh sách trên. Đây là đường DUY NHẤT một thứ
# không sửa mã nguồn -- một người không viết Python, hay một model -- thêm được
# một loại chứng từ vào bộ sinh này. Xem `synthgen/archetypes.py`.
#
# GỘP chứ không thay: mất thư mục thì 34 phôi viết tay vẫn chạy, nên đây là thứ
# làm giàu chứ không phải thứ bắt buộc. Nạp ở mức module nên nó xảy ra MỘT LẦN
# cho mỗi tiến trình, không phải mỗi tờ giấy.
#
# Lỗi IN RA chứ không ném: một phôi hỏng không được làm chết một lượt chạy vài
# giờ, nhưng cũng không được lặng lẽ biến mất -- "sinh ra ít loại hơn mình
# tưởng" là thứ không ai phát hiện cho tới lúc đếm lại cả bộ dữ liệu.
def _declared() -> tuple:
    from synthgen.archetypes import load  # noqa: PLC0415 -- tránh vòng import

    extra, errors = load()
    for line in errors:
        print(f"[synthgen] phôi khai sai, bỏ qua: {line}", file=_sys.stderr)
    return tuple(extra)


# Sàn dòng mà dưới nó một phôi in ra dạng biểu mẫu cũng hợp lý. Bốn, vì đó là
# chỗ `rows[0]` của kho tách làm hai nhóm rõ rệt: mười ba phôi có sàn 1-4 (phiếu
# thu, đơn thuốc, biên nhận -- một vài khoản mục), tám phôi có sàn 6-12 (bảng
# lương, bảng kê, danh sách -- vốn LÀ bảng).
TABLE_OPTIONAL_FLOOR = 4


# ------------------------------------------------------------- khối chảy


def _question_ceiling(arch: "Archetype") -> int:
    """Bao nhiêu CÂU một tờ khai viết ra được, đếm từ kho câu hỏi.

    Cộng mọi chủ đề, vì `content.questions_of` bốc tràn sang chủ đề khác khi
    một chủ đề cạn câu -- một tờ khai bốn trang không có cách nào chỉ hỏi
    mười hai câu của đúng một chủ đề."""
    from synthgen import content  # noqa: PLC0415

    return sum(len(theme["items"]) for theme in content.QUESTION_THEMES.values())


def _section_ceiling(arch: "Archetype") -> int:
    """Bao nhiêu MỤC văn xuôi một phôi viết ra được, đếm từ kho."""
    from synthgen import corpus  # noqa: PLC0415

    return len(corpus.sections(arch.profile))


def _clause_ceiling(arch: "Archetype") -> int:
    """Bao nhiêu ĐIỀU một phôi viết ra được, ĐẾM TỪ KHO chứ không đoán.

    Đây là chỗ dễ viết cứng nhất trong cả thay đổi này -- một con số 40 gõ
    vào đây chạy đúng hôm nay và sai đúng cái ngày ai đó thêm một file điều
    khoản. Kho là `rulebase/corpus/vi/clauses_*.txt`; thêm dòng vào đó thì
    tài liệu dài ra, không phải sửa file này."""
    from synthgen import corpus  # noqa: PLC0415 -- corpus không nhập ngược

    return len(corpus.clauses(arch.profile))


# Khối nào CHẢY được qua nhiều tờ, và sức chứa của nó lấy ở đâu.
#
# `table` đọc `rows` của phôi -- số dòng hàng phôi ấy cho phép. `clauses` đếm
# kho điều khoản của hồ sơ. Sàn là số mục ít nhất còn ra một khối đọc được:
# một cái bảng một dòng vẫn là bảng, còn một văn bản một điều thì chưa phải
# văn bản có điều khoản.
#
# Thêm một khối chảy mới -- `questions` chẳng hạn -- là thêm MỘT dòng ở đây,
# không phải sửa `paginate.py`, `markup.py` và `draw.py`: ba file ấy hỏi
# `design.flow` chứ không hỏi "có phải bảng không".
FLOW_BLOCKS: dict[str, Any] = {
    "table": {"floor": lambda arch: arch.rows[0],
              "ceiling": lambda arch: arch.rows[1]},
    "clauses": {"floor": lambda arch: 2,
                "ceiling": _clause_ceiling},
    "questions": {"floor": lambda arch: 4,
                  "ceiling": _question_ceiling},
    "sections": {"floor": lambda arch: 2,
                 "ceiling": _section_ceiling},
}


# Ước lượng THÔ "một tờ chứa bao nhiêu mục của khối này", và chỉ để `draw()`
# biết nhắm mấy tờ là hợp lý. Không phải sức chứa thật: sức chứa thật do
# `paginate.py` ĐO trong trình duyệt, và nó hạ số tờ xuống khi đo xong.
#
# Đo lại từ một lượt chạy thật (28 tờ, `rows_in_document / pages_in_document`)
# chứ không đoán: điều khoản ra 10,7 mục một tờ. Con số đoán ban đầu là 7, và
# nó nhắm CAO hơn sức chứa nên gần như tài liệu nào cũng phải hạ số tờ một
# vòng -- xem `plan_note` của lượt ấy, "hạ xuống 3 tờ: 51 dòng cần cho 4 tờ".
# Mực không-phải-chữ đứng ở đâu trên tờ giấy. Bốc theo trọng số đọc từ
# `rulebase/synthgen/_blocks.yaml::mark_place`, nên đổi hình dạng bộ dữ liệu
# không phải sửa file này.
#
#   cuoi        cuối tờ CUỐI -- công văn, quyết định, hợp đồng (dáng cũ)
#   dau         ngay dưới khối tiêu đề, tờ ĐẦU -- hoá đơn bán lẻ, phiếu cân
#   goc_phai    góc trên bên phải tờ đầu -- phiếu gửi xe, vé, thẻ
#   moi_to      cuối MỌI tờ -- sổ, biên bản nhiều trang có đánh dấu từng tờ
MARK_PLACES: tuple[str, ...] = ("cuoi", "dau", "goc_phai", "moi_to")

# `sections` chỉ 3 mỗi tờ: một mục là tiêu đề cộng hai ba đoạn canh đều,
# cao gấp ba bốn lần một điều khoản. Đo trên ảnh pilot16: một tờ A4 chứa
# hai đến ba mục.
# ĐO LẠI 23-09-2026 trên `data/smoke_multipage_v2` (43 trang đã vẽ), bằng
# cách đếm nhãn vùng `Section-Header` / `Form` theo từng `page_number` của
# bản ghi — KHÔNG đếm trong `plan/`, vì con số ở đó là `PROBE_ITEMS = 40`,
# tức nội dung dò đường trước khi `refill` chốt lại.
#
#   sections   đo 7,1 mục/tờ trên 21 trang   (đang để 3)
#   questions  đo 11,3 câu/tờ trên 6 trang   (đang để 8)
#
# Để 3 không phải là an toàn, nó là lãng phí: `flow_reach` = trần kho chia
# cho con số này, nên kho 69 mục ra "với tới 23 tờ", `draw()` nhắm tới 10
# tờ, rồi `paginate.plan` đo xong phải hạ dần 5->4->3->2 và tài liệu nào
# hạ hết đường thì `--multipage-only` loại. Đo trên lượt ấy: 9 lần hạ tờ
# trên 17 tài liệu, và 13/30 tài liệu bị loại.
#
# `questions` lấy 10 chứ không 11: mẫu chỉ có 6 trang, nhắm thấp hơn số đo
# một chút thì sai về phía thừa tờ, mà thừa tờ thì `plan` cắt được.
# `clauses` và `table` GIỮ NGUYÊN: mẫu lần lượt 3 và 4 trang, quá mỏng để
# đổi một con số đã đo trên 28 tờ trước đây.
FLOW_PER_PAGE: dict[str, int] = {"table": 15, "clauses": 11,
                                 "questions": 10, "sections": 7}


def block_boost(name: str) -> float:
    """Hệ số nhân xác suất của KHỐI `name` khi lượt chạy đòi nhiều tờ.

    Theo từng khối, không đều tay, và đó là kết quả của phép đo. Nhân đều thì
    khối vốn hay gặp bão hoà trước khối hiếm: ở hệ số 2.4, `footnote` lên 0.84
    và đo ra `Footnote` có mặt trên 82% số tờ, trong khi `Figure` mới 22% --
    đúng cái lệch mà việc nhân lên sinh ra để xoá, lần thứ ba trong file này.

    Và có một lý do thứ hai, mạnh hơn: thứ làm một TỜ GIỮA hết đơn điệu là
    khối CHIẾM CHỖ -- một cái bảng phụ lục, một khối trường, một sơ đồ. Ghi
    chú dấu sao và dòng "bằng chữ" chỉ thêm một nhãn vùng chứ không đổi hình
    dạng tờ giấy, nên nhân chúng lên là trả giá mà không mua được gì."""
    data = _blocks_yaml()
    rule = data.get("multipage_boost", 1.0)
    if not isinstance(rule, dict):
        try:
            return max(float(rule), 0.0)
        except (TypeError, ValueError):
            return 1.0
    try:
        return max(float(rule.get(name, rule.get("default", 1.0))), 0.0)
    except (TypeError, ValueError):
        return 1.0


def block_cap() -> float:
    """Trần của phép nhân trên. Khối đã cao hơn trần thì giữ nguyên."""
    data = _blocks_yaml()
    try:
        return max(float(data.get("multipage_cap", 0.95)), 0.0)
    except (TypeError, ValueError):
        return 0.95


def item_rules() -> dict:
    """Mục `items:` của `_blocks.yaml`: bảng của phôi nào liệt kê kho nào."""
    data = _blocks_yaml()
    rules = data.get("items") or {}
    return rules if isinstance(rules, dict) else {}


def hand_kinds(arch: "Archetype") -> tuple[str, ...]:
    """Những `data-kind` được điền TAY trên loại giấy này.

    `handwriting.fill()` viết lại chính chữ đã in, nên nội dung vốn khớp tài
    liệu; cái file này quyết là CHỖ ĐẶT BÚT. Một danh sách chung cho mọi loại
    giấy là cách một `BẢNG LƯƠNG` in máy có ô viết tay còn một `SỔ KHO` --
    ngoài đời ghi tay cả quyển -- chỉ được viết mấy ô trường."""
    data = _blocks_yaml().get("hand_kinds") or {}
    for rule in data.get("rules") or ():
        if _allowed_for(rule, arch):
            kinds = rule.get("kinds")
            return tuple(kinds) if kinds else ()
    fallback = data.get("default")
    return tuple(fallback) if fallback else ()


def block_allow() -> dict:
    """Luật `allow:` của `_blocks.yaml`: khối nào gắn được vào phôi nào."""
    data = _blocks_yaml()
    rules = data.get("allow") or {}
    return rules if isinstance(rules, dict) else {}


def _allowed_for(rule: Any, arch: "Archetype") -> bool:
    """Phôi này có khớp một luật `allow:` không.

    Ba vế, và khớp MỘT vế là đủ: tên tài liệu (`title_any`, không phân biệt
    hoa thường), ngành (`profile_any`), loại tổ chức (`org_kind_any`). Tên
    là vế chính xác nhất -- "TỜ KHAI Y TẾ" nói thẳng nó là tờ khai -- còn hai
    vế kia để với tới những phôi đặt tên không theo lệ."""
    rule = rule or {}
    words = rule.get("title_any") or ()
    if words:
        titles = " ".join(arch.titles).lower()
        if any(str(word).lower() in titles for word in words):
            return True
    if arch.profile in (rule.get("profile_any") or ()):
        return True
    return arch.org_kind in (rule.get("org_kind_any") or ())


def flow_reach(flow: str, arch: "Archetype") -> int:
    """Khối chảy `flow` nuôi nổi bao nhiêu TỜ trên phôi này. Ước lượng thô.

    Một chỗ duy nhất tính con số ấy. `draw()` cần nó hai lần -- một lần để
    chọn khối chảy, một lần để chốt số tờ -- và hai phép tính rời nhau cho
    cùng một câu hỏi là đúng hình dạng lỗi kho này hay gặp nhất."""
    lo, hi = flow_span(flow, arch)
    per = FLOW_PER_PAGE.get(flow, 0)
    cap = int(getattr(arch, "max_pages", 0) or 0)
    if not per:
        return 1
    if cap:
        # Phôi tự khai trần thì trần ấy THẮNG sức chứa. Một vé gửi xe có thể
        # chảy bằng điều khoản về mặt kỹ thuật -- kho điều khoản đủ cho mười
        # tờ -- nhưng một cái vé mười trang là tờ giấy không tồn tại.
        return max(min(cap, max(hi // per, 1)), 1)
    if hi - lo < per:
        # Khoảng mục hẹp hơn một tờ: sáu đến tám điều thì sáu đến tám điều,
        # không có gì để dồn sang tờ sau.
        return 1
    return max(hi // per, 1)


def pick_span(rng: random.Random, pages) -> tuple[int, int]:
    """`(sàn, trần)` số tờ cho MỘT tài liệu, từ khai báo `--pages`.

    Nhận ba hình dạng, và trả về cùng một thứ:

        None                      -> `PAGE_SPAN` mặc định
        (2, 10)                   -> đúng khoảng ấy
        [((2, 5), 75), ((7, 10), 25)] -> bốc khoảng theo trọng số, rồi mới
                                          bốc số tờ trong khoảng đã bốc

    Hình thứ ba là thứ một khoảng phẳng không thay được: `--pages 2-10` rải
    đều từ hai tới mười tờ, còn hồ sơ ngoài đời là phần lớn vài tờ và một
    phần nhỏ rất dày. Trọng số KHÔNG cần cộng thành 100 -- chúng được chuẩn
    hoá, nên `3,1` và `75,25` nói cùng một điều."""
    if not pages:
        return PAGE_SPAN
    if (isinstance(pages, (list, tuple)) and len(pages) == 2
            and all(isinstance(v, int) for v in pages)):
        lo, hi = int(pages[0]), int(pages[1])
    else:
        spans = [(tuple(span), float(weight)) for span, weight in pages]
        spans = [(span, w) for span, w in spans if w > 0] or [
            (tuple(span), 1.0) for span, _w in
            [(tuple(sp), 1.0) for sp, _ in pages]]
        picked = random.Random(rng.random()).choices(
            [span for span, _ in spans], weights=[w for _, w in spans])[0]
        lo, hi = int(picked[0]), int(picked[1])
    lo, hi = max(lo, 1), max(hi, 1)
    return (min(lo, hi), max(lo, hi))


def flow_weight(name: str) -> float:
    """Trọng số bốc khối chảy `name`, đọc từ `_blocks.yaml`.

    Vì sao bốc chứ không xếp thứ tự ưu tiên: bản trước xếp `clauses` trước
    mọi khối không-bảng, và kết quả đo được là nhãn `List-Group` có mặt trên
    82% số tờ -- đúng cái lệch mà việc hạ tỉ lệ bảng sinh ra để xoá, chỉ là
    đổi tên nhãn. Một khối chảy được ưu tiên tuyệt đối thì nhãn của nó thành
    nhãn của cả bộ."""
    data = _blocks_yaml()
    weights = data.get("flow_weight") or {}
    try:
        return max(float(weights.get(name, 1.0)), 0.0)
    except (TypeError, ValueError):
        return 1.0


def pick_weighted(rng: random.Random, names, section: str) -> str:
    """Một tên trong `names`, bốc theo trọng số ở mục `section` của
    `_blocks.yaml`. Tên không khai trọng số coi như 1.0.

    Dùng chung cho mọi lựa chọn "bộ này nghiêng về dáng nào": chỗ đứng của
    mã vạch, và những thứ sau nó. Mỗi lựa chọn như thế là một con số sửa là
    đổi cả bộ dữ liệu, nên nó thuộc về file, không thuộc về mã."""
    pool = list(names)
    if not pool:
        return ""
    data = _blocks_yaml().get(section) or {}
    weights = []
    for name in pool:
        try:
            weights.append(max(float(data.get(name, 1.0)), 0.0))
        except (TypeError, ValueError):
            weights.append(1.0)
    if sum(weights) <= 0:
        return pool[0]
    return random.Random(rng.random()).choices(pool, weights=weights)[0]


def block_region(name: str) -> str:
    """Nhãn vùng bố cục của khối `name`, đọc từ `_blocks.yaml::region`.

    Rỗng nghĩa là khối ấy KHÔNG tự khai vùng -- và khi ấy vùng của nó được
    `pipeline/record.py` dựng lại bằng cách gom từ theo ngưỡng khe. Đó là
    hành vi cũ của mọi khối, giữ lại làm lưới đỡ chứ không làm mặc định.

    KHÔNG có bảng dự phòng trong mã. Một `dict` nhãn viết ở đây "cho chắc" là
    người dựng thứ hai của cùng một luật, và kho này đã bị cắn vì đúng chuyện
    ấy nhiều lần -- bảng thẻ HTML từng có hai bản (`page.py` và `repair.py`)
    phủ hai tập thẻ khác nhau, và chỗ hở im lặng theo cả hai chiều. Mất file
    thì mọi khối về lưới đỡ, y như trước khi mục `region:` ra đời: kém hơn,
    nhưng không có bản nào nói khác bản nào."""
    value = (_blocks_yaml().get("region") or {}).get(name)
    return str(value).strip() if isinstance(value, str) else ""


def region_alias() -> dict:
    """`{tên model hay viết nhầm: nhãn vùng thật}`, đọc từ `_blocks.yaml`.

    Khoá chuẩn hoá về chữ thường: model viết `Masthead` và `masthead` trong
    cùng một lô, và hai dòng YAML cho một cái tên là hai người dựng của cùng
    một luật.

    Rỗng khi thiếu file -- và khi ấy mọi tên lạ về đúng hành vi cũ: cổng gác
    loại nguyên tờ. Bí danh là thứ làm giàu, không phải thứ bắt buộc."""
    raw = _blocks_yaml().get("region_alias") or {}
    return {str(k).strip().lower(): str(v).strip()
            for k, v in raw.items() if str(v).strip()}


def llm_density(level: str) -> dict:
    """`{chars, rows}` mỗi TỜ cho một mức `density`, đọc từ `_blocks.yaml`.

    Rỗng khi thiếu khai -- chỗ gọi tự lùi về hành vi cũ. Xem ghi chú trong
    chính file YAML về việc những con số ấy đo ở đâu ra."""
    table = _blocks_yaml().get("llm_density") or {}
    got = table.get(str(level or "").strip().lower())
    return dict(got) if isinstance(got, dict) else {}


def kie_option(name: str, default=""):
    """`_blocks.yaml::kie` tên `name`, hoặc `default`.

    Cùng lẽ `gate_ceiling`: mặc định do CHỖ GỌI nói ra, vì chỗ gọi là nơi biết
    "thiếu cấu hình thì hành vi an toàn là gì". Với `description_lang` thì an
    toàn là RỖNG -- trộn như cũ, không lặng lẽ đổi cả bộ dữ liệu."""
    value = (_blocks_yaml().get("kie") or {}).get(name, default)
    return value if value is not None else default


def gate_ceiling(name: str, default: float) -> float:
    """Ngưỡng `_blocks.yaml::gate` tên `name`, hoặc `default` nếu chưa khai.

    Có `default` ở đây, khác `block_region()` cố tình KHÔNG có: một nhãn vùng
    thiếu thì khối ấy đơn giản không khai vùng -- hành vi cũ, kém hơn nhưng
    vẫn chạy. Còn một NGƯỠNG thiếu thì cổng không có gì để so, và "không có
    gì để so" phải nghĩa là KHÔNG LOẠI, chứ không phải loại sạch. Chỗ gọi nói
    ra con số an toàn ấy, tại chính chỗ nó biết an toàn nghĩa là gì."""
    try:
        return float((_blocks_yaml().get("gate") or {}).get(name, default))
    except (TypeError, ValueError):
        return default


LLM_PATHS = ("rule", "page", "template")


def llm_path(default: str = "page") -> str:
    """Đường sinh mặc định, đọc `_blocks.yaml::llm_path`. Xem ghi chú ở đó.

    TÊN LẠ THÌ NÉM, không lặng lẽ về mặc định. Đây đúng chỗ AGENTS.md mục 6
    nói tới: một `path: templates` gõ thừa chữ `s` mà rơi về `page` là một
    lượt chạy hai mươi nghìn ảnh đi hết đường cũ trong khi báo cáo ghi tên
    đường mới, và không ai biết cho tới lúc đọc `llm_calls` trong báo cáo."""
    value = str((_blocks_yaml().get("llm_path") or {}).get("path", default)
                or default)
    if value not in LLM_PATHS:
        raise ValueError(
            f"`_blocks.yaml::llm_path.path` = {value!r} không phải một đường "
            f"sinh; nhận {', '.join(LLM_PATHS)}")
    return value


def per_template(default: int = 50) -> int:
    """Số tờ mỗi phôi khi chạy đường `template`."""
    try:
        return max(1, int((_blocks_yaml().get("llm_path") or {})
                          .get("per_template", default)))
    except (TypeError, ValueError):
        return default


def region_attr(name: str) -> str:
    """` data-region="..."` cho khối `name`, hoặc chuỗi rỗng.

    Trả cả thuộc tính kèm dấu cách đầu để chỗ gọi dán thẳng vào f-string mà
    không phải tự nhớ dấu cách -- một khoảng trắng thiếu ở đây dán liền hai
    thuộc tính thành một cái tên không ai đọc được, và trang vẫn vẽ ra."""
    label = block_region(name)
    return f' data-region="{label}"' if label else ""


def pick_flow(rng: random.Random, names) -> str:
    """Một khối chảy trong `names`, bốc theo trọng số. Rỗng thì trả ''."""
    pool = [n for n in names if n in FLOW_BLOCKS]
    if not pool:
        return ""
    weights = [flow_weight(n) for n in pool]
    if sum(weights) <= 0:
        return pool[0]
    return random.Random(rng.random()).choices(pool, weights=weights)[0]

# Số tờ mặc định một lượt chạy nhắm tới. `run.py --pages LO-HI` ghi đè.
PAGE_SPAN: tuple[int, int] = (1, 4)


def _blocks_yaml() -> dict:
    """`rulebase/synthgen/_blocks.yaml`, đọc một lần cho mỗi tiến trình.

    Mất file thì về mặc định và chạy tiếp: đây là thứ chỉnh bộ, không phải
    thứ bắt buộc -- cùng lối `archetypes.load()` với phôi khai bằng file."""
    global _BLOCKS_CACHE
    if _BLOCKS_CACHE is not None:
        return _BLOCKS_CACHE
    path = _REPO_ROOT / "rulebase" / "synthgen" / "_blocks.yaml"
    data: dict = {}
    try:
        loaded = _yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, _yaml.YAMLError):
        data = {}
    _BLOCKS_CACHE = data
    return data


_BLOCKS_CACHE: dict | None = None


def block_chance(name: str) -> float:
    """Xác suất khối tuỳ chọn `name` được bốc. Đọc từ file, không viết cứng."""
    data = _blocks_yaml()
    chance = data.get("chance") or {}
    default = data.get("default", 0.4)
    try:
        return float(chance.get(name, default))
    except (TypeError, ValueError):
        return 0.4


def flow_span(flow: str, arch: "Archetype") -> tuple[int, int]:
    """`(sàn, trần)` số mục của khối chảy. `(0, 0)` khi không có khối nào."""
    rule = FLOW_BLOCKS.get(flow)
    if not rule:
        return (0, 0)
    ceiling = int(rule["ceiling"](arch))
    floor = min(int(rule["floor"](arch)), ceiling)
    return (max(floor, 0), max(ceiling, 0))


def _widen(every: tuple) -> tuple:
    """Gắn sáu khối không-phải-bảng vào những phôi hợp với chúng.

    Theo TÍNH CHẤT đo được của phôi, không phải một bảng tên viết tay: thêm
    một phôi thì nó tự được xét, và sửa một luật là sửa một chỗ. Sáu nhãn này
    (`Bibliography`, `List-Group`, `Formula`, `Figure`+`Caption`, `Footnote`,
    `Table-Of-Contents`) chưa từng xuất hiện trong bộ sinh, trong khi giấy tờ
    Việt Nam thì đầy -- và chúng là thứ kéo tỉ lệ DIỆN TÍCH của bảng xuống,
    đo được 81% trước khi có chúng.

    Chỉ thêm vào `optional`: một phôi đang chạy không được đổi dáng bắt buộc
    chỉ vì hôm nay kho có thêm khối mới."""
    out = []
    for arch in every:
        add: list[str] = []
        # Căn cứ pháp lý: đầu mọi văn bản của cơ quan nhà nước và bệnh viện.
        if arch.org_kind in ("state", "hospital"):
            add.append("legal_basis")
        # Điều khoản đánh số, mục lục, tờ khai, ô tích, sơ đồ, ô dán ảnh:
        # đọc luật `allow:` của `rulebase/synthgen/_blocks.yaml` thay vì viết
        # ở đây. Luật cũ cho `clauses` là "giấy có hai bên ký", và nó gắn
        # điều khoản cho 95% số phôi -- "Điều 1." in lên cả thẻ kho. Cân bằng
        # giữa các khối là thứ phải chỉnh đi chỉnh lại sau mỗi lần đo, nên nó
        # thuộc về dữ liệu, không thuộc về mã nguồn.
        rules = block_allow()
        for name, rule in rules.items():
            if name in BLOCKS and _allowed_for(rule, arch):
                add.append(name)
        # Công thức tính: chỗ nào có tiền hoặc có bảo hiểm, y tế, điện nước.
        if arch.totals == "money" or arch.profile in (
                "insurance", "medical", "power", "water"):
            add.append("formula")
        # Sơ đồ kèm chú thích: văn bản hành chính dài.
        if arch.profile == "admin" and arch.rows[1] >= 20:
            add.append("figure")
        # Ghi chú có dấu sao: tờ nào có bảng cũng có thể có.
        if arch.rows[1] > 0:
            add.append("footnote")
        # (Mục lục `toc` chuyển sang luật `allow:` -- luật cũ đòi
        # `rows[1] >= 60`, tức là đòi một cái BẢNG dài, mà "dài" không còn
        # đồng nghĩa với "có bảng" từ khi có `design.FLOW_BLOCKS`.)
        fresh = tuple(b for b in add
                      if b not in arch.always and b not in arch.optional)

        # `replace: true` -- luật THU HẸP, và nó CHỈ gỡ khối mà chính file
        # `_blocks.yaml` gắn vào, không gỡ khối người viết phôi đã khai.
        #
        # Bản trước gỡ cả khối tác giả phôi khai, và đo được hậu quả:
        # `giay_moi.yaml` khai `clauses` trong `optional`, luật `replace` thấy
        # "giấy mời" không khớp danh sách tên và gỡ nó -- nên phôi ấy mất khối
        # chảy duy nhất không phải bảng, rồi `--multipage-only` loại sạch mọi
        # seed của nó. Một file trọng số cãi lại lời khai của phôi là đúng thứ
        # câu "file này nới rộng, không thu hẹp" ở đầu `_blocks.yaml` cấm.
        declared = set(arch.always) | set(arch.optional)
        drop = {name for name, rule in block_allow().items()
                if (rule or {}).get("replace")
                and not _allowed_for(rule, arch)
                and name not in declared}
        pruned = tuple(b for b in arch.optional if b not in drop)

        # Và thêm BỘ CỘT cho những cột vừa lấy từ `rulebase/layouts/`. Cũng
        # theo tính chất phôi: một bảng viện phí có cột giá bảo hiểm, một hoá
        # đơn điện nước có chỉ số công tơ, một hoá đơn siêu thị có mã vạch.
        # Thêm chứ không thay bộ cột cũ -- mỗi lần vẽ bốc một bộ, nên đây là
        # thêm một cách bảng ấy trông ra.
        sets: tuple[tuple[str, ...], ...] = ()
        if arch.profile in ("medical", "insurance") and arch.rows[1] > 0:
            sets += (("stt", "name", "unit", "qty", "price_bv", "amount_bv",
                      "rate_bhyt", "self_pay"),
                     ("stt", "name", "qty", "price_bv", "price_bh",
                      "amount_bv", "amount_bh", "other_pay"))
        if arch.profile in ("power", "water"):
            sets += (("stt", "name", "meter_prev", "meter_now", "quota",
                      "qty", "unit_price", "amount"),
                     ("name", "meter_prev", "meter_now", "qty", "unit_price",
                      "amount_with_vat"))
        if arch.profile == "market" and arch.rows[1] > 0:
            sets += (("stt", "barcode", "name", "qty", "unit_price", "amount"),)
        if arch.profile == "invoice" and arch.totals == "money":
            sets += (("stt", "name", "unit", "qty", "unit_price", "vat_rate",
                      "amount_with_vat"),)
        sets = tuple(s for s in sets if s not in arch.column_pool)

        # BẢNG THÀNH TUỲ CHỌN khi sàn dòng thấp. Một `phieu_thu` có sàn một
        # dòng: tờ giấy ấy in ra dạng biểu mẫu -- "Lý do thu: ... Số tiền: ..."
        # -- cũng hợp lý hệt như in dạng bảng, và giấy thật in cả hai cách.
        # Còn `bang_luong` sàn mười dòng thì nó LÀ một cái bảng, không bàn.
        #
        # Ngưỡng đọc từ chính `rows[0]`, không phải một danh sách tên: thêm một
        # phôi thì nó tự được xét. Đo trước khi sửa: 77% số tờ có bảng.
        always = arch.always
        optional = pruned + fresh
        if "table" in always and arch.rows[0] <= TABLE_OPTIONAL_FLOOR:
            always = tuple(b for b in always if b != "table")
            optional = optional + ("table",)
            # Bỏ bảng ra thì tờ giấy phải có thứ khác để đọc, nếu không nó
            # thành một cái tiêu đề với hai chữ ký. `fields` là khối tự nhiên
            # nhất cho một biểu mẫu; `notes` và `clauses` cho phần chữ.
            for name in ("fields", "notes", "clauses"):
                if name not in always and name not in optional:
                    optional = optional + (name,)

        if (fresh or sets or optional != arch.optional
                or always != arch.always):
            out.append(_dc.replace(arch, always=always, optional=optional,
                                   column_pool=arch.column_pool + sets))
            continue

        out.append(arch)
    return tuple(out)


BY_ID: dict[str, Archetype] = {}   # dựng lại sau khi gộp, ở cuối file

# Thứ tự khối: hai đầu neo cứng, khúc giữa hoán vị. Letterhead-tiêu đề-meta
# luôn ở trên và chữ ký-footer luôn ở dưới vì đó là chỗ của chúng trên mọi
# tờ giấy thật; phần giữa mới là chỗ hai nhà in làm khác nhau.
_ANCHOR_HEAD = ('letterhead', 'doctitle', 'meta', 'legal_basis')

# `sections` ngay sau `fields`: phần THUYẾT MINH của một biên bản đứng sau
# khối thông tin và TRƯỚC bảng số liệu -- đúng mạch `form_sectioned` của
# pilot16 (letterhead, ba dòng nhãn:giá trị, rồi `I.` `II.` `III.`). Khối
# nào `_MIDDLE_ORDERS` không nhắc tới thì rơi vào cuối khúc giữa theo thứ
# tự tuple này, nên vị trí ở đây LÀ vị trí nó in ra.
_MIDDLE = ('fields', 'sections', 'notes', 'checks', 'questions', 'clauses', 'formula',
           'figure', 'toc', 'table', 'totals', 'words', 'summary', 'footnote')

_ANCHOR_TAIL = ('signatures', 'footer')

# Ba nhóm trên, mở ra cho `markup.py` đọc. Nó cần đúng ba nhóm ấy để quyết
# khối nào NEO vào tờ đầu / tờ cuối và khối nào rải được sang các tờ giữa:
# tiêu đề đơn vị in ở tờ đầu vì đó là chỗ của nó trên mọi tờ giấy thật, còn
# một cái bảng phụ lục hay một sơ đồ thì tờ nào cũng in được.
#
# Alias chứ không đổi tên: ba tuple gạch dưới đã được dùng ở vài chỗ trong
# chính file này, và đổi tên chúng là sửa một thứ không hỏng.
ANCHOR_HEAD = _ANCHOR_HEAD
ANCHOR_TAIL = _ANCHOR_TAIL

# Khối phải đi CÙNG một khối khác, không rải riêng ra được. Dòng tổng nằm xa
# cái bảng nó cộng thì nó không cộng gì cả -- và đó là một tờ giấy không tồn
# tại, không phải một biến thể bố cục.
BOUND_GROUPS: tuple[tuple[str, ...], ...] = (
    ('table', 'totals', 'words', 'summary'),
    ('figure',),
)

# Mọi tên khối một phôi khai được. `archetypes.schema()` đọc CÁI NÀY chứ không
# đọc những khối các phôi hiện có tình cờ dùng: một khối vừa thêm vào kho mà
# chưa phôi nào khai thì vẫn phải khai được, nếu không phôi đầu tiên dùng nó bị
# cổng từ chối vì chính nó là phôi đầu tiên. Đã xảy ra thật với sáu khối mới.
# `'table'` ĐÃ CÓ trong `_MIDDLE`; nối thêm lần nữa ở đây thì nó xuất hiện
# SAU `_ANCHOR_TAIL`, tức sau `signatures` -- và đó là lý do khối chữ ký in ra
# GIỮA TRANG, trước bảng và trước dòng tổng cộng (đo trên
# `to_khai_thue_gtgt_00005`). Chữ ký phải là thứ cuối cùng của tờ giấy.
BLOCKS = _ANCHOR_HEAD + _MIDDLE + _ANCHOR_TAIL + ('photo',)

# Gộp phôi khai bằng file, rồi gắn khối và bộ cột theo tính chất. Phải đứng SAU
# `BLOCKS` vì `_declared()` gọi cổng, và cổng đọc `BLOCKS`.
ARCHETYPES = _widen(ARCHETYPES + _declared())
BY_ID = {a.id: a for a in ARCHETYPES}

_MIDDLE_ORDERS: tuple[tuple[str, ...], ...] = (('fields', 'questions', 'clauses', 'table', 'totals', 'words', 'summary', 'notes', 'checks'), ('fields', 'questions', 'notes', 'toc', 'table', 'totals', 'words', 'summary', 'checks'), ('fields', 'checks', 'questions', 'formula', 'table', 'totals', 'words', 'summary', 'notes'), ('notes', 'fields', 'questions', 'figure', 'table', 'totals', 'words', 'summary', 'checks'), ('fields', 'questions', 'clauses', 'table', 'summary', 'totals', 'words', 'notes', 'checks'), ('table', 'fields', 'questions', 'clauses', 'totals', 'words', 'summary', 'notes', 'checks'), ('fields', 'questions', 'clauses', 'table', 'totals', 'words', 'notes', 'summary', 'checks'), ('checks', 'questions', 'fields', 'formula', 'table', 'totals', 'words', 'summary', 'notes'))


def _pick(rng: random.Random, pool):
    return pool[rng.randrange(len(pool))]


def _middle_order(rng: random.Random, blocks: set) -> tuple[str, ...]:
    """Thứ tự các khối THÂN của một tờ, xáo có ràng buộc.

    Bản trước bốc một trong TÁM tuple viết tay, và cả tám đều cùng một dáng:
    `fields` gần đầu, `table/totals/words/summary` liền nhau gần cuối,
    `notes/checks` chốt hậu. Nên hai tờ khác loại chứng từ vẫn đọc lên cùng
    một trình tự -- đo trên 600 lượt bốc, bốn tổ hợp đầu chiếm phần lớn.

    Xáo thì mỗi tờ một trình tự, và không cần ai bảo trì một bảng tám dòng mà
    thêm khối mới là phải sửa tám chỗ (chính chú thích cũ ở đây cũng đã lo
    đúng chuyện ấy).

    HAI ràng buộc giữ nguyên, vì chúng là nghĩa chứ không phải thẩm mỹ:

    * `BOUND_GROUPS` -- dòng cộng phải đi liền cái bảng nó cộng, và đi SAU.
      Một dòng "Cộng" đứng trước bảng là một tờ giấy không tồn tại.
    * `footnote` luôn chốt cuối khúc giữa: chú thích chân khối thì phải ở chân.
    """
    present = [name for name in _MIDDLE if name in blocks]
    units: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for name in present:
        if name in seen:
            continue
        bound = next((g for g in BOUND_GROUPS if name in g), None)
        if bound:
            unit = tuple(n for n in bound if n in blocks)
            seen.update(unit)
        else:
            unit = (name,)
            seen.add(name)
        units.append(unit)
    last = [u for u in units if u == ("footnote",)]
    units = [u for u in units if u != ("footnote",)]
    rng.shuffle(units)
    return tuple(n for unit in units + last for n in unit)


def groups_in(columns: tuple[str, ...]) -> tuple[tuple[int, int, tuple[str, ...]], ...]:
    """Nhóm cột dùng được cho bộ cột này: (cột đầu, số cột, các cách viết).

    Chỉ nhận nhóm có các cột nằm LIỀN NHAU trong bộ cột đã bốc, và không
    chồng lên nhóm đã nhận: `colspan` không nhảy cóc được, và hai nhóm chồng
    nhau thì tầng trên phủ nhiều cột hơn tầng dưới có -- bảng hỏng."""
    taken: set[int] = set()
    out = []
    for captions, keys in COL_GROUPS:
        if any(key not in columns for key in keys):
            continue
        at = [columns.index(key) for key in keys]
        if at != list(range(at[0], at[0] + len(keys))):
            continue
        if any(i in taken for i in at):
            continue
        taken.update(at)
        out.append((at[0], len(keys), captions))
    return tuple(sorted(out))


def runs_over(units: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Các đoạn gồm TỪ HAI dải liền nhau trở lên trong `units` -> `(đầu, rộng)`.

    Một tầng tiêu đề mới chỉ có nghĩa khi nó phủ NHIỀU dải của tầng dưới: phủ
    đúng một dải thì nó chỉ là cái dải ấy viết to hơn, và phủ nửa dải thì
    `colspan` không khớp. Cùng một luật dùng lại cho mọi tầng, nên thêm tầng
    không phải viết thêm phép tìm -- `units` vào là `(đầu, rộng)`, ra cũng
    `(đầu, rộng)`.

    `units` phải đã xếp theo cột và không chồng nhau; `groups_in` trả ra đúng
    thế, và mỗi tầng dựng từ hàm này cũng vậy."""
    out = []
    index = 0
    while index < len(units):
        end = index
        reach = units[index][0]
        while end < len(units) and units[end][0] == reach:
            reach += units[end][1]
            end += 1
        if end - index >= 2:
            out.append((units[index][0], reach - units[index][0]))
        index = max(end, index + 1)
    return tuple(out)


def super_in(columns: tuple[str, ...]) -> tuple[int, int] | None:
    """Đoạn cột dài nhất mà một tầng thứ ba phủ được, nếu có."""
    found = runs_over([(first, span) for first, span, _ in groups_in(columns)])
    return max(found, key=lambda run: run[1]) if found else None


_SMALL = tuple(paper for paper in PAPERS
               if paper.id in ('a5', 'a5_ngang', 'b5', 'phieu_hep'))


def ladder(minimum_width: float) -> tuple[Paper, ...]:
    """Các khổ giấy đủ rộng cho một bảng, xếp từ ÍT chỗ tới NHIỀU chỗ.

    `paginate.py` leo thang này khi phép đo nói nội dung không lọt khổ đã rút.
    Nhà in thật làm đúng thế: một biên bản không vừa A5 thì in A4, chứ không
    in chữ bốn chấm lên A5. Xếp theo DIỆN TÍCH vì cả hai chiều đều là chỗ --
    Xếp theo CHIỀU CAO: thứ đang thiếu khi một tờ giấy tràn là chỗ theo
    chiều dọc, và bề ngang đã được `minimum_width` lo xong."""
    seen = {}
    for paper in PAPERS:
        if paper.w >= minimum_width:
            seen.setdefault(f'{paper.w}x{paper.h}', paper)
    return tuple(sorted(seen.values(), key=lambda paper: (paper.h,
                                                          paper.w * paper.h)))


def _decor_table(section: str, names) -> dict:
    """Mục `section` của `_blocks.yaml`, sau khi kiểm từng khoá.

    KHOÁ LẠ THÌ NÉM, không bỏ qua. `pick_weighted` coi tên không khai là 1.0,
    nên một lỗi gõ -- `an_ninhh: 3` -- im lặng biến thành "trọng số mặc định"
    và trục ấy lệch mà không ai hay. Đây là con số người chỉnh bộ sẽ sửa tay
    nhiều nhất, nên nó phải kêu khi sai."""
    data = _blocks_yaml().get(section) or {}
    if not isinstance(data, dict):
        raise ValueError(f"_blocks.yaml::{section} phải là một bảng tên: số")
    stray = sorted(set(data) - set(names))
    if stray:
        raise ValueError(f"_blocks.yaml::{section} có khoá lạ {stray}; "
                         f"chỉ nhận {list(names)}")
    return data


def draw_decor(seed: int) -> dict:
    """Phần trang trí của tờ `seed`, dưới dạng tham số cho `Design(...)`.

    Hàm thuần của seed và của `_blocks.yaml`, trên dòng ngẫu nhiên riêng --
    xem `DECOR_SALT`."""
    rng = random.Random(seed ^ DECOR_SALT)
    _decor_table("decor_frame", PAGE_FRAMES)
    _decor_table("decor_band", EDGE_BANDS)
    _decor_table("decor_ground", GROUNDS)
    _decor_table("decor_logo", LOGO_STYLES)
    chances = _decor_table("decor_accent", ACCENTS)

    band = pick_weighted(rng, EDGE_BANDS, "decor_band")
    frame = pick_weighted(rng, PAGE_FRAMES, "decor_frame")
    if band != 'khong':
        # Bốc cả hai rồi mới gạt, không bốc có điều kiện: số lần gọi `rng`
        # cố định thì đổi trọng số một trục không xê dịch trục khác.
        frame = 'khong'
    ground = pick_weighted(rng, GROUNDS, "decor_ground")
    logo = pick_weighted(rng, LOGO_STYLES, "decor_logo")
    accents = frozenset(name for name in ACCENTS
                        if rng.random() < float(chances.get(name, 0.0)))
    return {"frame": frame, "band": band, "ground": ground,
            "logo_style": logo, "accents": accents}


def draw(rng: random.Random, seed: int,
         archetype: Archetype | None = None,
         pages: tuple[int, int] | None = None) -> Design:
    """Một tờ giấy, dáng rút ngẫu nhiên từ ngữ pháp trên.

    `pages` là khoảng số tờ lượt chạy này NHẮM tới, `run.py --pages LO-HI`
    đưa vào. Truyền qua tham số chứ không đặt biến toàn cục: `unique_seeds()`
    tính chữ ký dáng ở tiến trình cha còn shard vẽ ở tiến trình con, và một
    biến toàn cục đặt ở cha thì con không thấy -- hai bên sẽ tính ra hai dáng
    khác nhau cho cùng một seed, lặng lẽ."""
    arch = archetype or _pick(rng, ARCHETYPES)

    # Lượt chạy này đòi tài liệu dài tới đâu. Biết được TRƯỚC khi bốc khối,
    # vì nó đến từ `--pages` chứ không từ tờ giấy -- và phải biết trước, xem
    # `boost` ở dưới.
    #
    # `pages` nhận được MỘT khoảng, hoặc một HỖN HỢP khoảng có trọng số --
    # `--pages 2-5:75,7-10:25`. Bốc khoảng trước, rồi mới bốc số tờ trong
    # khoảng ấy: hai phép bốc lồng nhau là cách duy nhất ra được một phân bố
    # hai cụm. Một khoảng phẳng 2-10 không làm được điều đó, và bộ dữ liệu
    # "phần lớn ngắn, một phần tư thật dài" là hình dạng hồ sơ ngoài đời.
    want_lo, want_hi = pick_span(rng, pages)
    long_run = want_hi > 2
    # Nhân MẠNH DẦN theo độ dài lượt xin, chứ không phải một cờ bật/tắt.
    #
    # `long_run` trước đây là `want_hi > 2`, nên một lượt `--pages 2-3` và một
    # lượt `--pages 2-11` nhân y hệt nhau. Nguồn cung không đổi mà số tờ gấp
    # bốn thì phần thiếu hụt đi thẳng vào tờ giữa: đo trên 500 tài liệu
    # `--pages 2-11`, trung bình 3,23 khối tự do rải lên 3,9 tờ, và 46% tờ
    # giữa không có gì ngoài khối chảy -- đúng cái "một màu" phải xoá.
    stretch = 1.0 + max(want_hi - 3, 0) / 4.0
    boost_cap = min(block_cap() * stretch, 0.9) if long_run else 1.0

    blocks = set(arch.always)
    for name in arch.optional:
        # Khối tuỳ chọn không bốc đều tay: một tờ giấy thật gần như luôn có
        # meta, thường có footer, và hiếm khi có ô dán ảnh.
        # Xác suất đọc từ `rulebase/synthgen/_blocks.yaml`, không viết ở
        # đây: một con số sửa là đổi cả bộ dữ liệu không nên nằm trong mã
        # nguồn, vì khi ấy chỉ người sửa mã mới đổi được hình dạng của bộ.
        #
        # NHÂN LÊN khi lượt chạy đòi tài liệu dài. Một tờ giấy bốc được ba
        # khối thì rải lên sáu tờ vẫn còn bốn tờ chỉ có mỗi khối chảy -- đúng
        # cái "trải dài từ đầu tới cuối" phải xoá. Tài liệu dài ngoài đời
        # cũng thế: một hợp đồng sáu trang có phụ lục bảng, có sơ đồ, có mục
        # lục, còn một phiếu thu một trang thì không.
        base = block_chance(name)
        # `stretch` chỉ kéo dài tay của khối mà `_blocks.yaml` ĐÃ xin nhân.
        # Khối khai đúng 1.0 là khai "đừng nhân", và mấy khai ấy có số đo đi
        # kèm -- `table: 1.0` là kết luận sau khi đo bốn mức. Nhân nó lên ở
        # đây là lặng lẽ lật một quyết định đã đo, từ một file khác.
        rule = block_boost(name) if long_run else 1.0
        boost = rule * stretch if rule > 1.0 else rule
        if rng.random() < min(base * boost, max(boost_cap, base)):
            blocks.add(name)
    if 'totals' in blocks and 'table' not in blocks:
        blocks.discard('totals')
    if 'words' in blocks and 'totals' not in blocks:
        blocks.discard('words')
    if arch.totals == 'none':
        blocks.discard('totals')
        blocks.discard('words')

    # KHỐI CHẢY -- khối quyết định tài liệu này dài bao nhiêu, và khối bị cắt
    # ra khi nó phải in làm nhiều tờ.
    #
    # Đoạn này là cả thay đổi. Trước nó, số tờ đọc `'table' not in blocks` và
    # trả về 1 -- nên "nhiều trang" và "có bảng" là cùng một thứ trong toàn
    # bộ dữ liệu, dù xác suất bảng có hạ xuống bao nhiêu.
    #
    # BỐC theo trọng số, không xếp thứ tự ưu tiên. Bản trước xếp `clauses`
    # trước mọi khối không-bảng, và đo ra `List-Group` có mặt trên 82% số tờ:
    # cùng một cái lệch, chỉ đổi tên nhãn. Một khối chảy được ưu tiên tuyệt
    # đối thì nhãn của nó thành nhãn của cả bộ.
    #
    # Phải đứng TRƯỚC `order`: ép thêm một khối sau khi đã xếp thứ tự thì
    # `blocks` có nó mà `order` không, và khối ấy biến mất lặng lẽ -- đúng
    # cái bẫy đoạn `tail` bên dưới sinh ra để chặn.
    here = [n for n in FLOW_BLOCKS if n in blocks]
    if want_lo > 1:
        # CHỈ BỐC KHỐI VỚI TỚI. Một `biên lai thu học phí` có bảng trần mười
        # hai dòng và điều khoản trần một trăm tám mươi điều; bốc trúng bảng
        # là nó tụt về một tờ, rồi `--multipage-only` loại nó. Đo được: 33
        # phôi có tỉ lệ sống dưới 90% chỉ vì phép bốc không nhìn sức chứa.
        #
        # Lọc chứ không sửa từng phôi: nâng trần bảng của ba mươi ba file là
        # ba mươi ba lần nói cùng một điều, và lần thứ ba mươi bốn sẽ quên.
        able = [n for n in here if flow_reach(n, arch) >= want_lo]
        here = able or here
    flow = pick_flow(rng, here)
    if not flow and want_lo > 1:
        # Lượt chạy đòi nhiều tờ mà tờ này không có gì chảy được. Thêm một
        # khối chảy -- nhưng CHỈ khối chính phôi ấy đã khai: ép điều khoản vào
        # một tấm thẻ bảo hiểm y tế là vẽ ra một tờ giấy không tồn tại.
        allowed = set(arch.always) | set(arch.optional)
        names = [n for n in FLOW_BLOCKS if n in allowed]
        able = [n for n in names if flow_reach(n, arch) >= want_lo]
        flow = pick_flow(rng, able or names)
        if flow:
            blocks.add(flow)
    if 'totals' in blocks and 'table' not in blocks:
        blocks.discard('totals')
        blocks.discard('words')

    middle = _middle_order(rng, blocks)
    # Khối nào được bốc mà thứ tự vừa chọn KHÔNG nhắc tới thì xếp nốt vào cuối
    # khúc giữa, theo thứ tự `_MIDDLE`. Không có dòng này thì một khối biến mất
    # LẶNG LẼ: `blocks` có nó, `order` thì không, và tờ giấy ra thiếu đúng thứ
    # phôi khai là `always`. Nó cũng là lý do thêm một khối mới không phải sửa
    # cả tám tuple thứ tự -- sửa tám chỗ là quên một chỗ.
    order = tuple(name for name in _ANCHOR_HEAD if name in blocks)
    order += middle
    order += tuple(name for name in _ANCHOR_TAIL if name in blocks)

    # Bộ cột RỖNG là hợp lệ, và phải hợp lệ: một phôi không bao giờ có bảng --
    # `hop_dong_dich_vu_dai`, `quy_che_noi_bo` -- khai `columns: []`, vì khai
    # cột cho một tờ giấy không có bảng là khai một thứ không in ra. `_pick`
    # trên kho rỗng thì `randrange(0)` ném `ValueError`, và nó ném ở
    # `unique_seeds()` tức là TRƯỚC khi mở trình duyệt, nên cả lượt chạy chết
    # chứ không phải một tờ hỏng.
    # BẢNG CÓ THÌ PHẢI ĐÁNG LÀ MỘT CÁI BẢNG.
    #
    # `column_pool` của một phôi thường có cả bộ ba cột lẫn bộ tám cột, và bốc
    # đều thì 36% số bảng ra dưới năm cột -- một "bảng" ba cột không dạy được
    # mô hình đọc bảng thật: không có nhóm cột, không có tầng tiêu đề, không có
    # ô gộp. Bộ rộng mới là chỗ mọi cấu trúc khó sống được.
    #
    # Bốc HAI LẦN rồi giữ bộ rộng hơn: giữ nguyên mọi bộ cột phôi đã khai (kể
    # cả bộ hẹp, vì biên lai thật đúng là ba cột), chỉ dịch phân bố về phía
    # rộng. Không cần sửa 139 file YAML.
    columns = ()
    if arch.column_pool:
        first = _pick(rng, arch.column_pool)
        second = _pick(rng, arch.column_pool)
        columns = first if len(first) >= len(second) else second
    head = _pick(rng, HEAD_LAYOUTS)
    if arch.org_kind == 'state' and head == 'khong_letterhead':
        head = 'chia_doi'

    # Tiêu đề hai tầng chỉ dựng được khi bộ cột có nhóm liền nhau; không có
    # nhóm nào thì tầng trên không có gì để phủ.
    tiers = 1
    if 'table' in blocks and groups_in(columns):
        # Tiêu đề nhiều tầng là thứ phân biệt một bảng chứng từ thật với một
        # lưới ô: "Giá trị và thuế › Số lượng và đơn giá › Đơn giá". Bản trước
        # cho 1 tầng ở 78% số bảng, nên phần lớn bảng trong bộ không có cấu
        # trúc nào để học. Đảo lại: có nhóm cột thì mặc định hai tầng, ba tầng
        # khi bộ cột có tầng trên nữa.
        roll = rng.random()
        tiers = 2 if roll < 0.85 else 1
        if super_in(columns):
            # Trần của tầng ba KHÔNG phải con số dưới đây, mà là 36% -- tỉ lệ
            # bộ cột thật sự có hai nhóm liền nhau, đo trên 1500 lượt bốc.
            # Nên hai cổng này chia phần BÊN TRONG 36% ấy chứ không chia toàn
            # bộ số bảng, và đặt thấp thì tầng ba thành của hiếm: bản trước để
            # 0.46 và đo ra 11% số bảng có ba tầng.
            if roll < 0.62:
                tiers = 3
            # Tầng BỐN là dải "Phần ..." chạy ngang, nên nó không đòi bộ cột
            # có gì thêm -- chỉ đòi dưới nó đã có ba tầng để đội. Đội lên một
            # bảng hai tầng thì nó đọc ra cái nhan đề đặt nhầm vào trong
            # khung, chứ không ra một tờ khai.
            if roll < 0.28:
                tiers = 4
    # Hàng số thứ tự cột "(1) (2) (3)" -- dấu hiệu của biểu mẫu nhà nước, nên
    # nó theo hạng giấy chứ không bốc đều.
    col_numbers = rng.random() < (0.62 if arch.org_kind in ('state', 'hospital')
                                  else 0.24)
    row_groups = _pick(rng, ROW_GROUPS) if 'table' in blocks else 'khong'
    if row_groups == 'cot_gom' and len(columns) > 7:
        # Thêm một cột gom vào bảng đã tám cột là ép chữ xuống thành sợi.
        row_groups = 'phan_muc'
    nested_detail = ('name' in columns and 'table' in blocks
                     and rng.random() < 0.28)

    sign_sets = arch.sign_sets or ((),)
    sign = _pick(rng, sign_sets)
    if 'signatures' not in blocks:
        sign = ()

    # Số trường lấy trong khoảng của chính chứng từ ấy, rồi bốc KHÔNG lặp và
    # giữ nguyên thứ tự của phôi -- một tờ giấy in trường theo thứ tự mẫu,
    # không theo thứ tự bốc.
    lo, hi = arch.field_span
    want = rng.randint(lo, min(hi, len(arch.field_pool))) if arch.field_pool else 0
    chosen = ()
    if want:
        keep = sorted(rng.sample(range(len(arch.field_pool)), want))
        chosen = tuple(arch.field_pool[i] for i in keep)
    if not chosen:
        blocks.discard('fields')
        order = tuple(name for name in order if name != 'fields')

    floor, ceiling = flow_span(flow, arch)

    # Số tờ ĐỊNH nhắm tới, nhắm theo SỨC CHỨA của chính chứng từ ấy: một tờ
    # biên lai tám dòng không có cách nào lấp hai tờ giấy, còn một bảng lương
    # một trăm hai mươi dòng thì hai tờ là ít. Nhắm cao rồi để `paginate.py`
    # hạ xuống là đúng chiều: nó ĐO rồi mới chốt, còn nhắm thấp thì không có
    # gì kéo lên được.
    lo, hi = want_lo, want_hi
    # Trần THẬT: bao nhiêu tờ khối chảy này nuôi nổi. Ước lượng thô, và nói
    # thẳng là thô -- phép đo trong trình duyệt mới chốt. Đọc `flow_reach`
    # chứ không tính lại: phép bốc khối chảy ở trên đã dùng chính nó, và hai
    # phép tính rời nhau cho cùng một câu hỏi thì sẽ lệch.
    reach = flow_reach(flow, arch) if flow else 0
    hi = max(min(hi, max(reach, 1)), 1)
    lo = max(min(lo, hi), 1)
    # Nghiêng về phía ít tờ trong khoảng: giấy tờ thật phần lớn là một tờ, và
    # một bộ toàn tài liệu mười trang cũng lệch y như một bộ toàn một trang.
    target = min(rng.randint(lo, hi), rng.randint(lo, hi))

    # Ước lượng thô "tờ này có bao nhiêu chữ", chỉ để không nhét một bảng
    # sáu mươi dòng vào khổ A5.
    volume = ceiling + len(chosen) * 2 + (6 if 'notes' in blocks else 0)

    room = [paper for paper in PAPERS if paper.w >= 40 + 22 * len(columns)]
    room = room or [paper for paper in PAPERS if paper.id == 'a4_ngang']
    small = [paper for paper in room if paper.id in
             ('a5', 'a5_ngang', 'b5', 'phieu_hep')]
    paper = _pick(rng, small if small and volume <= 12 and rng.random() < 0.65
                  else room)

    return Design(
        archetype=arch,
        paper=paper,
        margins=_pick(rng, MARGINS),
        palette=_pick(rng, PALETTES),
        face=_pick(rng, FACES),
        base_pt=_pick(rng, BASE_SIZES),
        leading=_pick(rng, LEADINGS),
        tracking=_pick(rng, TRACKING),
        rule_px=_pick(rng, RULE_WEIGHTS),
        head_layout=head,
        title_style=_pick(rng, TITLE_STYLES),
        meta_style=_pick(rng, META_STYLES),
        field_style=_pick(rng, FIELD_STYLES),
        field_columns=_pick(rng, (1, 2, 2, 2, 3)),
        table_frame=_pick(rng, TABLE_FRAMES),
        header_fill=_pick(rng, HEADER_FILLS),
        zebra=rng.random() < 0.28,
        table_caption=rng.random() < 0.3,
        compact_rows=rng.random() < 0.35,
        head_tiers=tiers,
        col_numbers=col_numbers,
        row_groups=row_groups,
        nested_detail=nested_detail,
        sign_style=_pick(rng, SIGN_STYLES),
        sign_count=len(sign),
        note_style=_pick(rng, NOTE_STYLES),
        # Số cột của CẢ TRANG -- khác `columns` (cột bảng) và `field_columns`
        # (khối trường). Đây là dáng báo, tạp chí, tờ rơi, đơn nhiều mục: chữ
        # chảy thành hai hoặc ba cột trên một khổ giấy.
        #
        # Bốc BÌNH THƯỜNG, kể cả khi có khối chảy: quyết định "tờ này in
        # mấy cột" là của cả tài liệu, còn việc một TỜ cụ thể có dùng được
        # hai cột hay không thì `markup.py` xét riêng từng tờ.
        #
        # Bản trước ép về 1 khi có khối chảy, và nó chữa đúng triệu chứng sai
        # chỗ: khối chảy là khối CAO và không cắt ngang được
        # (`.cols .blk{break-inside:avoid}`), nên tờ NÀO CHỨA NÓ mới hỏng --
        # dồn hết vào một cột, bỏ trắng cột kia. Ép ở đây thì mọi tờ của tài
        # liệu ấy mất hai cột, kể cả những tờ chỉ có bảng phụ lục và sơ đồ.
        # `markup.py::markup` tắt cột trên đúng tờ mang lát khối chảy.
        page_columns=_pick(rng, PAGE_COLUMNS),
        ornament=_pick(rng, ORNAMENTS),
        mark_place=pick_weighted(rng, MARK_PLACES, "mark_place"),
        columns=columns,
        sign_captions=sign,
        fields=chosen,
        order=order,
        blocks=frozenset(blocks),
        photo_box='photo' in blocks,
        watermark=rng.random() < 0.12,
        national=rng.random() < float(getattr(arch, "national", 0.0) or 0.0),
        reverse_title_band=rng.random() < 0.1,
        lang_en=arch.en_ok and rng.random() < 0.18,
        target_pages=target,
        flow=flow,
        seed=seed,
        **draw_decor(seed),
    )
