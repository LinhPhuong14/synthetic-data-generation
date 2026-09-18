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
from typing import Any


# --------------------------------------------------------------- khổ giấy & lề


@dataclass(frozen=True)
class Paper:
    id: str
    w: float
    h: float


PAPERS: tuple[Paper, ...] = (
    Paper('a4', 210, 297),
    Paper('a4', 210, 297),
    Paper('a4', 210, 297),
    Paper('a5', 148, 210),
    Paper('a5_ngang', 210, 148),
    Paper('letter', 216, 279),
    Paper('legal', 216, 356),
    Paper('b5', 176, 250),
    Paper('phieu_hep', 105, 250),
    Paper('a4_ngang', 297, 210),
)

MARGINS: tuple[tuple[float, float, float, float], ...] = ((18, 15, 15, 20), (20, 18, 18, 25), (14, 12, 12, 14), (12, 10, 10, 12), (25, 20, 20, 30), (16, 16, 16, 16), (10, 8, 10, 8), (22, 16, 14, 28), (15, 20, 15, 20), (8, 6, 8, 6), (28, 22, 22, 22), (13, 11, 16, 18))


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

TABLE_FRAMES = ('khung_day_du', 'chi_ke_ngang', 'khong_ke', 'vien_ngoai', 'ke_ngang_dam_dau', 'khung_day_du_van', 'chi_ke_doc')

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
PAGE_COLUMNS = (1, 1, 1, 2, 2, 3)

ORNAMENTS = ('khong', 'dau_tron', 'dau_vuong', 'ma_vach', 'ma_qr', 'dau_tron_va_ma_vach', 'hoa_van_goc', 'chim_mo')

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
)

# Tầng thứ BA: một nhóm-lớn phủ hai nhóm liền nhau trở lên. Ba tầng là dáng
# của tờ khai hải quan và bảng kê thanh toán viện phí thật -- "Giá trị và
# thuế" phủ "Số lượng, đơn giá" và "Thuế GTGT", mỗi nhóm ấy lại phủ hai cột.
COL_SUPERS = (
    'Giá trị và thuế', 'Chi tiết hàng hoá, dịch vụ', 'Số liệu chi tiết',
    'Phần II - Chi tiết thanh toán', 'Trị giá tính thuế và thuế',
    'Chi tiết khoản mục', 'Số liệu quyết toán',
)

# Cách gộp DÒNG. `khong` là bảng phẳng như cũ; `phan_muc` chèn dòng tiêu đề
# nhóm chạy hết chiều ngang (kiểu thực đơn, kiểu bảng thống kê cốt thép);
# `cot_gom` để một ô `rowspan` bên trái mang tên nhóm, trải qua các dòng của
# nhóm ấy (kiểu bảng xếp hạng vòng bảng).
ROW_GROUPS = ('khong', 'khong', 'khong', 'phan_muc', 'phan_muc', 'cot_gom')

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
    target_pages: int
    seed: int

    # `boost` là hệ số cỡ chữ, và là trường DUY NHẤT đổi được sau khi `draw()`
    # trả về: `paginate.py` chỉnh nó để ép một tờ giấy lấp đủ 80% mà không
    # phải rút lại toàn bộ dáng.
    boost: float = 1.0

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
            self.reverse_title_band, self.lang_en,
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
    A('giay_gioi_thieu', ('GIẤY GIỚI THIỆU', 'GIẤY GIỚI THIỆU CÔNG TÁC'), ('Kính gửi: ....', '', 'Số: ..../GGT'), 'admin', 'state', 0.9, SUBJECT_FIELDS[:1] + SUBJECT_FIELDS[3:5] + SUBJECT_FIELDS[8:10], (3, 5), (('stt', 'name', 'note'),), 'none', False, (('TM. THỦ TRƯỞNG ĐƠN VỊ',), ('NGƯỜI GIỚI THIỆU', 'THỦ TRƯỞNG ĐƠN VỊ')), _NOTE_STATE, (0, 5), optional=('table', 'footer', 'photo'), always=('letterhead', 'doctitle', 'meta', 'fields', 'notes', 'signatures')),
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
        # Điều khoản đánh số: giấy có hai bên ký, tức là một thoả thuận.
        if any(len(s) >= 2 for s in arch.sign_sets):
            add.append("clauses")
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
        # Mục lục: chỉ tài liệu đủ dài để cắt ra nhiều tờ.
        if arch.rows[1] >= 60:
            add.append("toc")
        fresh = tuple(b for b in add
                      if b not in arch.always and b not in arch.optional)

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
        optional = arch.optional + fresh
        if "table" in always and arch.rows[0] <= TABLE_OPTIONAL_FLOOR:
            always = tuple(b for b in always if b != "table")
            optional = optional + ("table",)
            # Bỏ bảng ra thì tờ giấy phải có thứ khác để đọc, nếu không nó
            # thành một cái tiêu đề với hai chữ ký. `fields` là khối tự nhiên
            # nhất cho một biểu mẫu; `notes` và `clauses` cho phần chữ.
            for name in ("fields", "notes", "clauses"):
                if name not in always and name not in optional:
                    optional = optional + (name,)

        if fresh or sets or optional != arch.optional or always != arch.always:
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

_MIDDLE = ('fields', 'notes', 'checks', 'questions', 'clauses', 'formula',
           'figure', 'toc', 'table', 'totals', 'words', 'summary', 'footnote')

_ANCHOR_TAIL = ('signatures', 'footer')

# Mọi tên khối một phôi khai được. `archetypes.schema()` đọc CÁI NÀY chứ không
# đọc những khối các phôi hiện có tình cờ dùng: một khối vừa thêm vào kho mà
# chưa phôi nào khai thì vẫn phải khai được, nếu không phôi đầu tiên dùng nó bị
# cổng từ chối vì chính nó là phôi đầu tiên. Đã xảy ra thật với sáu khối mới.
BLOCKS = _ANCHOR_HEAD + _MIDDLE + _ANCHOR_TAIL + ('table', 'photo')

# Gộp phôi khai bằng file, rồi gắn khối và bộ cột theo tính chất. Phải đứng SAU
# `BLOCKS` vì `_declared()` gọi cổng, và cổng đọc `BLOCKS`.
ARCHETYPES = _widen(ARCHETYPES + _declared())
BY_ID = {a.id: a for a in ARCHETYPES}

_MIDDLE_ORDERS: tuple[tuple[str, ...], ...] = (('fields', 'questions', 'clauses', 'table', 'totals', 'words', 'summary', 'notes', 'checks'), ('fields', 'questions', 'notes', 'toc', 'table', 'totals', 'words', 'summary', 'checks'), ('fields', 'checks', 'questions', 'formula', 'table', 'totals', 'words', 'summary', 'notes'), ('notes', 'fields', 'questions', 'figure', 'table', 'totals', 'words', 'summary', 'checks'), ('fields', 'questions', 'clauses', 'table', 'summary', 'totals', 'words', 'notes', 'checks'), ('table', 'fields', 'questions', 'clauses', 'totals', 'words', 'summary', 'notes', 'checks'), ('fields', 'questions', 'clauses', 'table', 'totals', 'words', 'notes', 'summary', 'checks'), ('checks', 'questions', 'fields', 'formula', 'table', 'totals', 'words', 'summary', 'notes'))


def _pick(rng: random.Random, pool):
    return pool[rng.randrange(len(pool))]


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


def super_in(columns: tuple[str, ...]) -> tuple[int, int] | None:
    """Đoạn cột dài nhất được HAI nhóm liền nhau trở lên phủ kín, nếu có.

    Đó là chỗ duy nhất một tầng thứ ba có nghĩa: nó phải phủ nhiều nhóm, chứ
    phủ đúng một nhóm thì nó chỉ là cái nhóm ấy viết to hơn."""
    groups = groups_in(columns)
    best = None
    index = 0
    while index < len(groups):
        end = index
        reach = groups[index][0]
        while end < len(groups) and groups[end][0] == reach:
            reach += groups[end][1]
            end += 1
        if end - index >= 2:
            span = reach - groups[index][0]
            if best is None or span > best[1]:
                best = (groups[index][0], span)
        index = max(end, index + 1)
    return best


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


def draw(rng: random.Random, seed: int,
         archetype: Archetype | None = None) -> Design:
    """Một tờ giấy, dáng rút ngẫu nhiên từ ngữ pháp trên."""
    arch = archetype or _pick(rng, ARCHETYPES)

    blocks = set(arch.always)
    for name in arch.optional:
        # Khối tuỳ chọn không bốc đều tay: một tờ giấy thật gần như luôn có
        # meta, thường có footer, và hiếm khi có ô dán ảnh.
        chance = {'footer': 0.55, 'notes': 0.5, 'meta': 0.7, 'words': 0.45,
                  'summary': 0.35, 'checks': 0.3, 'questions': 0.5,
                  'legal_basis': 0.45, 'clauses': 0.4, 'formula': 0.3,
                  'figure': 0.25, 'footnote': 0.4, 'toc': 0.2,
                  # Bảng CHỈ 0.35, và đó là chỗ sửa một con số đổi cả bộ. Đo
                  # trước: 77% số tờ vẽ ra có bảng, nên một mô hình học trên bộ
                  # ấy học rằng "chứng từ Việt Nam" nghĩa là "một cái bảng có
                  # chữ quanh nó". Giấy tờ thật không thế: công văn, tờ trình,
                  # biên bản họp, giấy uỷ quyền đều không có bảng nào.
                  'table': 0.35,
                  'fields': 0.6, 'photo': 0.25}.get(name, 0.4)
        if rng.random() < chance:
            blocks.add(name)
    if 'totals' in blocks and 'table' not in blocks:
        blocks.discard('totals')
    if 'words' in blocks and 'totals' not in blocks:
        blocks.discard('words')
    if arch.totals == 'none':
        blocks.discard('totals')
        blocks.discard('words')

    middle = _pick(rng, _MIDDLE_ORDERS)
    # Khối nào được bốc mà thứ tự vừa chọn KHÔNG nhắc tới thì xếp nốt vào cuối
    # khúc giữa, theo thứ tự `_MIDDLE`. Không có dòng này thì một khối biến mất
    # LẶNG LẼ: `blocks` có nó, `order` thì không, và tờ giấy ra thiếu đúng thứ
    # phôi khai là `always`. Nó cũng là lý do thêm một khối mới không phải sửa
    # cả tám tuple thứ tự -- sửa tám chỗ là quên một chỗ.
    tail = tuple(name for name in _MIDDLE
                 if name in blocks and name not in middle)
    order = tuple(name for name in _ANCHOR_HEAD if name in blocks)
    order += tuple(name for name in middle if name in blocks) + tail
    order += tuple(name for name in _ANCHOR_TAIL if name in blocks)

    columns = _pick(rng, arch.column_pool)
    head = _pick(rng, HEAD_LAYOUTS)
    if arch.org_kind == 'state' and head == 'khong_letterhead':
        head = 'chia_doi'

    # Tiêu đề hai tầng chỉ dựng được khi bộ cột có nhóm liền nhau; không có
    # nhóm nào thì tầng trên không có gì để phủ.
    tiers = 1
    if 'table' in blocks and groups_in(columns):
        roll = rng.random()
        tiers = 2 if roll < 0.46 else 1
        if roll < 0.20 and super_in(columns):
            tiers = 3
    # Hàng số thứ tự cột "(1) (2) (3)" -- dấu hiệu của biểu mẫu nhà nước, nên
    # nó theo hạng giấy chứ không bốc đều.
    col_numbers = rng.random() < (0.34 if arch.org_kind in ('state', 'hospital')
                                  else 0.12)
    row_groups = _pick(rng, ROW_GROUPS) if 'table' in blocks else 'khong'
    if row_groups == 'cot_gom' and len(columns) > 7:
        # Thêm một cột gom vào bảng đã tám cột là ép chữ xuống thành sợi.
        row_groups = 'phan_muc'
    nested_detail = ('name' in columns and 'table' in blocks
                     and rng.random() < 0.14)

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

    # Số tờ ĐỊNH nhắm tới. Chỉ là ý định: `paginate.py` đo xong mới chốt, và
    # nó hạ số tờ xuống nếu không tờ nào lấp nổi 80%.
    # Số tờ ĐỊNH nhắm tới, và nó nhắm theo SỨC CHỨA của chính chứng từ ấy:
    # một tờ biên lai tám dòng không có cách nào lấp hai tờ giấy, còn một
    # bảng lương một trăm hai mươi dòng thì hai tờ là ít. Nhắm cao rồi để
    # `paginate.py` hạ xuống là đúng chiều: nó ĐO rồi mới chốt, còn nhắm
    # thấp thì không có gì kéo lên được.
    span = arch.rows[1] - arch.rows[0]
    roll = rng.random()
    if span < 10 or 'table' not in blocks:
        target = 1
    elif span < 30:
        target = 1 if roll < 0.42 else 2
    elif roll < 0.16:
        target = 1
    elif roll < 0.52:
        target = 2
    elif roll < 0.82:
        target = 3
    else:
        target = 4

    # Ước lượng thô "tờ này có bao nhiêu chữ", chỉ để không nhét một bảng
    # sáu mươi dòng vào khổ A5.
    volume = arch.rows[1] + len(chosen) * 2 + (6 if 'notes' in blocks else 0)

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
        # CHỈ khi tờ giấy không có bảng. Một bảng bảy cột nhét vào một cột rộng
        # 8cm thì chữ vỡ ra từng ký tự, và cái hộp đo được của nó không còn tả
        # một cái bảng nào -- đúng thứ luật "hộp phải tả được tấm ảnh" cấm.
        # `blocks` đã chốt ở trên nên chỗ này biết chắc.
        page_columns=(_pick(rng, PAGE_COLUMNS) if 'table' not in blocks else 1),
        ornament=_pick(rng, ORNAMENTS),
        columns=columns,
        sign_captions=sign,
        fields=chosen,
        order=order,
        blocks=frozenset(blocks),
        photo_box='photo' in blocks,
        watermark=rng.random() < 0.12,
        reverse_title_band=rng.random() < 0.1,
        lang_en=arch.en_ok and rng.random() < 0.18,
        target_pages=target,
        seed=seed,
    )
