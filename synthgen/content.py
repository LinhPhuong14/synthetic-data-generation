"""Nội dung một tờ giấy: chữ gì thật sự in ra.

Tách khỏi `design.py` vì hai trục ấy độc lập -- cùng một dáng in hai nội dung
khác nhau, cùng một nội dung in trên hai dáng khác nhau. `build()` nhận một
`Design` và trả về `Doc`, và `Doc` là thứ duy nhất `html.py` đọc.

Số tiền LUÔN do đây tính, không bao giờ do đâu khác: thành tiền là đơn giá
nhân số lượng, cộng dồn ra tổng, thuế tính trên tổng chưa thuế, và "số tiền
bằng chữ" đọc lại đúng con số ấy. Một tập dữ liệu OCR mà cột thành tiền không
khớp với cột đơn giá là một tập dữ liệu dạy mô hình đọc sai số.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rulebase.text import money, words_vi  # noqa: E402
from synthgen import corpus  # noqa: E402
from synthgen.design import (COL_SUPERS, COLUMNS, ROW_GROUP_NAMES,  # noqa: E402
                             Design, FieldDef, groups_in, item_rules,
                             super_in)

CITIES = ('Hà Nội', 'TP. Hồ Chí Minh', 'Đà Nẵng', 'Hải Phòng', 'Cần Thơ', 'Huế', 'Nha Trang', 'Biên Hoà', 'Vũng Tàu', 'Buôn Ma Thuột', 'Quy Nhơn', 'Vinh', 'Thanh Hoá', 'Nam Định', 'Thái Nguyên', 'Hạ Long', 'Bắc Ninh', 'Hải Dương', 'Long Xuyên', 'Rạch Giá', 'Mỹ Tho', 'Bến Tre', 'Pleiku', 'Đà Lạt', 'Phan Thiết', 'Tuy Hoà', 'Quảng Ngãi', 'Tam Kỳ', 'Đồng Hới', 'Lào Cai')

DISTRICTS = ('Quận 1', 'Quận 3', 'Quận 7', 'Quận 10', 'Quận Ba Đình', 'Quận Cầu Giấy', 'Quận Đống Đa', 'Quận Hai Bà Trưng', 'Quận Hoàn Kiếm', 'Quận Thanh Xuân', 'Quận Hải Châu', 'Quận Sơn Trà', 'Huyện Gia Lâm', 'Huyện Đông Anh', 'Thị xã Sơn Tây', 'Quận Bình Thạnh', 'Quận Tân Bình', 'Quận Phú Nhuận', 'Quận Gò Vấp', 'Huyện Bình Chánh', 'Quận Lê Chân', 'Quận Ngô Quyền')

BANKS = ('Vietcombank', 'VietinBank', 'BIDV', 'Agribank', 'Techcombank', 'MB Bank', 'ACB', 'VPBank', 'Sacombank', 'TPBank', 'SHB', 'HDBank', 'SeABank', 'OCB', 'Eximbank', 'LPBank', 'MSB', 'VIB', 'Nam A Bank', 'BVBank')

DEPARTMENTS = (
    'Phòng Hành chính - Tổng hợp',
    'Phòng Tài chính - Kế toán',
    'Phòng Kế hoạch - Đầu tư',
    'Phòng Tổ chức - Nhân sự',
    'Phòng Kinh doanh',
    'Phòng Kỹ thuật',
    'Phòng Vật tư',
    'Phòng Chăm sóc khách hàng',
    'Ban Quản lý dự án',
    'Đội Thi công số 1',
    'Phân xưởng Cơ điện',
    'Trung tâm Dịch vụ khách hàng',
    'Bộ phận Kho vận',
    'Tổ Bảo trì',
    'Phòng Pháp chế',
    'Phòng Đảm bảo chất lượng',
    'Phòng Xuất nhập khẩu',
)

POSITIONS = ('Chuyên viên', 'Nhân viên', 'Trưởng phòng', 'Phó Trưởng phòng', 'Kế toán viên', 'Kế toán trưởng', 'Giám đốc', 'Phó Giám đốc', 'Tổ trưởng', 'Kỹ sư', 'Kỹ thuật viên', 'Thủ kho', 'Thủ quỹ', 'Nhân viên kinh doanh', 'Trợ lý', 'Quản đốc', 'Giám sát', 'Cán bộ phụ trách', 'Điều dưỡng viên', 'Bác sĩ')

WARDS_MED = (
    'Khoa Nội tổng hợp',
    'Khoa Ngoại tổng hợp',
    'Khoa Sản',
    'Khoa Nhi',
    'Khoa Cấp cứu',
    'Khoa Hồi sức tích cực',
    'Khoa Tim mạch',
    'Khoa Tiêu hoá',
    'Khoa Hô hấp',
    'Khoa Chấn thương chỉnh hình',
    'Khoa Mắt',
    'Khoa Răng Hàm Mặt',
    'Khoa Tai Mũi Họng',
    'Khoa Da liễu',
    'Khoa Thần kinh',
    'Khoa Truyền nhiễm',
    'Khoa Khám bệnh',
    'Khoa Ung bướu',
    'Khoa Thận - Tiết niệu',
    'Khoa Nội tiết',
)

DIAGNOSES = (
    'Viêm phổi mắc phải cộng đồng',
    'Tăng huyết áp nguyên phát',
    'Đái tháo đường típ 2',
    'Viêm dạ dày cấp',
    'Sỏi túi mật',
    'Viêm ruột thừa cấp',
    'Gãy kín xương cẳng tay',
    'Viêm phế quản cấp',
    'Thiếu máu cơ tim cục bộ',
    'Rối loạn tiền đình',
    'Viêm khớp dạng thấp',
    'Sốt xuất huyết Dengue',
    'Viêm gan virus B mạn',
    'Suy thận mạn giai đoạn 3',
    'Thoát vị đĩa đệm cột sống thắt lưng',
    'Viêm xoang mạn tính',
    'Loét dạ dày - tá tràng',
    'Rối loạn lipid máu',
    'Viêm amidan cấp',
    'Hen phế quản bậc 2',
    'Nhiễm khuẩn tiết niệu',
    'Trĩ nội độ II',
)

TREATMENTS = (
    'Điều trị nội khoa, kháng sinh đường tĩnh mạch',
    'Phẫu thuật nội soi, hậu phẫu ổn định',
    'Điều trị bảo tồn, theo dõi sát dấu hiệu sinh tồn',
    'Dùng thuốc theo phác đồ, tái khám sau 02 tuần',
    'Truyền dịch, giảm đau, nghỉ ngơi tại giường',
    'Vật lý trị liệu kết hợp thuốc giảm đau chống viêm',
    'Nội soi can thiệp, theo dõi 24 giờ sau thủ thuật',
    'Điều chỉnh liều thuốc, tư vấn chế độ ăn và luyện tập',
)

COVER_OBJECTS = (
    'Xe ô tô con dưới 9 chỗ ngồi',
    'Nhà xưởng và hàng hoá trong kho',
    'Công trình xây dựng dân dụng',
    'Hàng hoá vận chuyển đường bộ',
    'Người lao động trong ca làm việc',
    'Thiết bị điện tử văn phòng',
    'Chuyến đi du lịch quốc tế',
    'Xe máy trên 50 phân khối',
    'Tài sản cố định của doanh nghiệp',
    'Sức khoẻ và tai nạn cá nhân',
)

TERMS = (
    '12 tháng kể từ ngày ký',
    '24 tháng',
    '06 tháng',
    '36 tháng',
    'Từ ngày ký đến hết ngày 31/12',
    '01 năm, gia hạn theo thoả thuận',
    'Theo tiến độ nghiệm thu từng hạng mục',
)

UNITS = ('Cái', 'Chiếc', 'Bộ', 'Hộp', 'Thùng', 'Kg', 'Lít', 'Mét', 'Gói', 'Chai', 'Lọ', 'Tấm', 'Đôi', 'Ống', 'Cuộn', 'Túi', 'Bao', 'Vỉ')

UNITS_BY_PROFILE: dict[str, tuple[str, ...]] = {
    'power': ('kWh',),
    'water': ('m3', 'm³'),
    'medical': ('Lần', 'Viên', 'Ống', 'Ngày', 'Gói', 'Chai', 'Cái', 'Đợt'),
    'insurance': ('Vụ', 'Người', 'Năm', 'Lần', 'Đợt'),
    'hotel': ('Đêm', 'Ngày', 'Lần', 'Suất', 'Phòng'),
    'menu': ('Phần', 'Suất', 'Đĩa', 'Tô', 'Ly', 'Chai'),
    'eatery': ('Phần', 'Suất', 'Đĩa', 'Tô', 'Ly', 'Chai', 'Cái'),
    'market': ('Cái', 'Gói', 'Hộp', 'Chai', 'Kg', 'Vỉ', 'Túi', 'Lon'),
    'bakery': ('Cái', 'Hộp', 'Ổ', 'Chiếc', 'Khay', 'Gói'),
    'admin': ('Người', 'Ngày', 'Công', 'Tháng', 'Bộ', 'Lượt', 'Suất'),
    'export': ('Kg', 'Tấn', 'Thùng', 'Kiện', 'Bộ', 'Chiếc', 'Mét'),
}

ISSUERS = (
    'Cục Cảnh sát QLHC về TTXH',
    'Công an tỉnh',
    'Công an thành phố',
    'Cục Quản lý xuất nhập cảnh',
    'UBND phường',
    'Sở Tư pháp',
)

GENDERS = ('Nam', 'Nữ')

ORIGINS = ('Việt Nam', 'Thái Lan', 'Nhật Bản', 'Hàn Quốc', 'Trung Quốc',
           'Đức', 'Ý', 'Malaysia', 'Indonesia', 'Đài Loan')

ROOMS = (
    'Phòng đơn Standard',
    'Phòng đôi Deluxe',
    'Phòng Superior hướng biển',
    'Phòng Suite',
    'Phòng Twin',
    'Phòng Family',
    'Phòng đơn tiêu chuẩn',
)

@dataclass
class Row:
    """Một dòng trong bảng hàng. Mọi cột đều là CHUỖI đã định dạng xong: định
    dạng số là một quyết định về dáng, và để nó ở đây thì `html.py` không phải
    biết một cột là tiền hay là ngày."""

    values: dict[str, str]


@dataclass
class Doc:
    design: Design
    org_name: str
    org_branch: str
    org_address: str
    org_phone: str
    org_tax: str
    org_website: str
    parent_org: str
    title: str
    subtitle: str
    doc_no: str
    doc_serial: str
    doc_form: str
    issued_place: str
    issued_date: dt.date
    fields: list[tuple[FieldDef, str]]
    rows: list[Row]
    col_titles: dict[str, str]
    totals: list[tuple[str, str]]
    grand_label: str
    grand: str
    grand_amount: int
    words_label: str
    words: str
    summary: list[tuple[str, str]]
    notes: list[str]
    checks: list[tuple[str, str]]
    questions: list[dict]
    legal_basis: list[str]
    clauses: list[tuple[str, str]]
    formula: str
    caption: str
    footnotes: list[str]
    toc: list[tuple[str, str]]
    signatures: list[tuple[str, str]]
    footer: str
    table_caption: str
    seed: int
    unit_pool: list[str] = field(default_factory=list)
    # Tiêu đề hai tầng: (chữ của nhóm, cột đầu, số cột nó phủ). Rỗng nghĩa là
    # bảng một tầng như cũ.
    col_groups: list[tuple[str, int, int]] = field(default_factory=list)
    # Gộp dòng: `row_group_size` dòng hàng thì sang một nhóm mới, tên lấy vòng
    # quanh `row_group_names`. Hai con số này KHÔNG đổi khi `refill()` đổi số
    # dòng -- nhóm tính theo chỉ số dòng, nên trang nào cũng gộp giống trang
    # nào, và `paginate.py` cắt ở đâu cũng ra nhóm đúng.
    row_group_size: int = 0
    row_group_names: list[str] = field(default_factory=list)
    # Tầng thứ ba, nếu có: (chữ, cột đầu, số cột) -- một ô phủ nhiều nhóm.
    col_supers: list[tuple[str, int, int]] = field(default_factory=list)
    # Cộng cột thành tiền của từng nhóm dòng, đã định dạng. Tính lại mỗi lần
    # `refill()` đổi số dòng -- một dòng cộng không khớp phần nó cộng là đúng
    # cái lỗi bộ dữ liệu này tồn tại để không mắc.
    row_group_totals: list[str] = field(default_factory=list)

    def content_signature(self) -> str:
        """Vân tay nội dung. Trùng cái này là trùng CHỮ, kể cả khi dáng khác
        -- `compose.py` từ chối cái thứ hai, nên "không trùng nội dung giữa
        các ảnh" là một tính chất được kiểm tra chứ không phải một hy vọng."""
        parts = [self.org_name, self.title, self.doc_no, self.doc_serial,
                 str(self.issued_date), self.grand]
        parts += [f'{f.key}={v}' for f, v in self.fields]
        parts += ['|'.join(row.values.get(key, '')
                           for key in sorted(row.values))
                  for row in self.rows]
        return hashlib.sha1('␟'.join(parts).encode('utf-8')).hexdigest()


# Bảng câu hỏi, chia theo CHỦ ĐỀ. Một tờ khai chỉ hỏi về một chuyện, nên một
# kho phẳng là sai: trước khi có cái dict này, `cong_van` -- một công văn hành
# chính -- in ra câu hỏi về bệnh khớp, vì nó bốc từ cùng một kho với tờ khai
# bảo hiểm. Chủ đề chọn theo `profile` của phôi (xem `_theme_for`), nên thêm
# một phôi là nó tự rơi vào đúng nhóm câu hỏi.
#
# `shape` quyết câu trả lời trông thế nào: `blank` là một dòng kẻ để viết tay,
# `yesno` là cặp ô Có/Không, `options` là một lưới ô tích. Trộn ba kiểu ấy
# trong một tờ là thứ làm dáng trang "phức" -- không khối nào đoán được khối
# sau nó cao bao nhiêu.
QUESTION_THEMES: dict[str, dict] = {
    'benh_khop': {
        'items': (
            ('Quý khách vui lòng cho biết tên chẩn đoán bệnh khớp?', 'blank', ()),
            ('Quý khách bị ảnh hưởng các khớp nào?', 'blank', ()),
            ('Lần đầu tiên phát hiện bệnh khớp là lúc nào?', 'blank', ()),
            ('Triệu chứng cụ thể là gì?', 'blank', ()),
            ('Đã thực hiện các xét nghiệm nào trong vòng 12 tháng qua?', 'options',
             ('MRI', 'CT-scan', 'Xquang', 'Siêu âm', 'RF', 'Acid Uric', 'Khác')),
            ('Quý khách đang dùng nhóm thuốc nào?', 'options',
             ('Giảm đau', 'Kháng viêm', 'Corticoid', 'Thực phẩm chức năng', 'Khác')),
            ('Hình thức điều trị đã áp dụng', 'options',
             ('Nội khoa', 'Vật lý trị liệu', 'Phẫu thuật', 'Đông y', 'Khác')),
            ('Các triệu chứng này vẫn đang tồn tại?', 'yesno', ()),
            ('Quý khách có bị hạn chế vận động hay biến chứng nào khác không?', 'yesno', ()),
            ('Quý khách có phải sử dụng phương tiện hỗ trợ nào không?', 'yesno', ()),
            ('Quý khách có được bác sĩ yêu cầu cân nhắc phẫu thuật không?', 'yesno', ()),
            ('Trong gia đình có ai mắc bệnh tương tự không?', 'yesno', ()),
        ),
        'answers': ('đau nhẹ khớp gối', 'viêm khớp dạng thấp', 'hoàn toàn bình thường',
                    'không có', 'thoái hoá cột sống thắt lưng', 'đau vai trái khi trở trời',
                    'chưa rõ nguyên nhân', 'đã khỏi sau 2 tháng', 'thỉnh thoảng tê tay',
                    'đau khi vận động mạnh'),
    },
    'tien_su_benh': {
        'items': (
            ('Quý khách đã từng nằm viện trong 5 năm gần đây chưa?', 'yesno', ()),
            ('Quý khách có đang dùng thuốc theo đơn dài ngày không?', 'yesno', ()),
            ('Quý khách có dị ứng thuốc hoặc thức ăn nào không?', 'blank', ()),
            ('Tên bệnh đã được chẩn đoán (nếu có)', 'blank', ()),
            ('Nơi khám và điều trị gần nhất', 'blank', ()),
            ('Quý khách đã từng phẫu thuật chưa?', 'yesno', ()),
            ('Bệnh lý nền hiện có', 'options',
             ('Tăng huyết áp', 'Đái tháo đường', 'Tim mạch', 'Hô hấp', 'Không có')),
            ('Thói quen sinh hoạt', 'options',
             ('Hút thuốc', 'Uống rượu bia', 'Tập thể dục đều', 'Không có thói quen nào')),
            ('Quý khách có đang mang thai không?', 'yesno', ()),
            ('Chiều cao, cân nặng hiện tại', 'blank', ()),
        ),
        'answers': ('không có', 'dị ứng kháng sinh nhóm beta-lactam', 'viêm dạ dày',
                    'Bệnh viện Đa khoa tỉnh, tháng 3/2025', '1m65, 58kg',
                    'huyết áp cao nhẹ', 'đã mổ ruột thừa năm 2019', 'bình thường'),
    },
    'dich_te': {
        'items': (
            ('Trong 14 ngày qua Quý khách có đến vùng có dịch không?', 'yesno', ()),
            ('Quý khách có tiếp xúc với người mắc bệnh truyền nhiễm không?', 'yesno', ()),
            ('Triệu chứng hiện có', 'options',
             ('Sốt', 'Ho', 'Khó thở', 'Đau họng', 'Mất vị giác', 'Không có')),
            ('Quý khách đã tiêm đủ mũi vắc xin chưa?', 'yesno', ()),
            ('Loại vắc xin và ngày tiêm gần nhất', 'blank', ()),
            ('Phương tiện di chuyển đã sử dụng', 'options',
             ('Máy bay', 'Tàu hoả', 'Ô tô khách', 'Xe cá nhân', 'Khác')),
            ('Địa chỉ lưu trú trong 14 ngày tới', 'blank', ()),
            ('Quý khách có đang cách ly theo yêu cầu y tế không?', 'yesno', ()),
        ),
        'answers': ('không', 'sốt nhẹ hai hôm trước', 'đã tiêm đủ ba mũi',
                    'Vero Cell, tháng 8/2024', 'số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội',
                    'hoàn toàn bình thường', 'ho khan về đêm'),
    },
    'dich_vu': {
        'items': (
            ('Quý khách đánh giá thái độ phục vụ của nhân viên', 'options',
             ('Rất hài lòng', 'Hài lòng', 'Bình thường', 'Chưa hài lòng')),
            ('Thời gian xử lý hồ sơ', 'options', ('Nhanh', 'Đúng hẹn', 'Chậm')),
            ('Quý khách biết đến dịch vụ qua kênh nào?', 'options',
             ('Người quen giới thiệu', 'Mạng xã hội', 'Website', 'Báo chí', 'Khác')),
            ('Quý khách có hài lòng với kết quả nhận được không?', 'yesno', ()),
            ('Quý khách có muốn tiếp tục sử dụng dịch vụ không?', 'yesno', ()),
            ('Ý kiến đóng góp để chúng tôi phục vụ tốt hơn', 'blank', ()),
            ('Điều gì khiến Quý khách chưa hài lòng nhất?', 'blank', ()),
            ('Cơ sở vật chất tại nơi tiếp nhận', 'options',
             ('Tốt', 'Khá', 'Trung bình', 'Cần cải thiện')),
            ('Quý khách có phải chờ quá thời gian hẹn không?', 'yesno', ()),
            ('Hình thức nhận kết quả mong muốn', 'options',
             ('Nhận trực tiếp', 'Qua bưu điện', 'Nhận bản điện tử')),
        ),
        'answers': ('nhân viên nhiệt tình', 'chờ hơi lâu', 'không có ý kiến gì thêm',
                    'rất tốt', 'mong có thêm quầy tiếp nhận', 'thủ tục còn rườm rà',
                    'hài lòng', 'cần thêm chỗ ngồi chờ'),
    },
    'nhan_su': {
        'items': (
            ('Mức độ hoàn thành công việc được giao', 'options',
             ('Xuất sắc', 'Tốt', 'Đạt yêu cầu', 'Chưa đạt')),
            ('Tinh thần phối hợp với đồng nghiệp', 'options',
             ('Tốt', 'Khá', 'Trung bình', 'Cần cải thiện')),
            ('Nhân sự có tham gia đầy đủ các khoá đào tạo không?', 'yesno', ()),
            ('Nhiệm vụ nổi bật đã thực hiện trong kỳ', 'blank', ()),
            ('Khó khăn gặp phải trong quá trình công tác', 'blank', ()),
            ('Đề xuất của cá nhân cho kỳ tiếp theo', 'blank', ()),
            ('Nhân sự có vi phạm nội quy trong kỳ không?', 'yesno', ()),
            ('Đề nghị hình thức khen thưởng', 'options',
             ('Giấy khen', 'Thưởng tiền', 'Nâng lương trước hạn', 'Chưa đề nghị')),
            ('Nhân sự có nguyện vọng luân chuyển vị trí không?', 'yesno', ()),
        ),
        'answers': ('hoàn thành đúng tiến độ', 'không có', 'thiếu nhân lực hỗ trợ',
                    'đề nghị bổ sung thiết bị', 'phụ trách dự án mở rộng kho',
                    'cần thêm thời gian bàn giao', 'tốt'),
    },
    'bao_hiem': {
        'items': (
            ('Quý khách có tham gia hợp đồng bảo hiểm nào khác không?', 'yesno', ()),
            ('Nghề nghiệp hiện tại và tính chất công việc', 'blank', ()),
            ('Quý khách có thường xuyên làm việc trên cao hoặc dưới nước không?', 'yesno', ()),
            ('Môn thể thao hoặc hoạt động rủi ro đang tham gia', 'options',
             ('Leo núi', 'Lặn biển', 'Mô tô thể thao', 'Không có')),
            ('Thu nhập bình quân tháng', 'blank', ()),
            ('Quý khách đã từng bị từ chối bảo hiểm chưa?', 'yesno', ()),
            ('Mục đích tham gia bảo hiểm', 'options',
             ('Bảo vệ thu nhập', 'Tích luỹ', 'Chăm sóc sức khoẻ', 'Hưu trí', 'Khác')),
            ('Người thụ hưởng và quan hệ với người được bảo hiểm', 'blank', ()),
            ('Quý khách có hút thuốc lá không?', 'yesno', ()),
        ),
        'answers': ('nhân viên văn phòng', 'không có', 'khoảng 18 triệu đồng',
                    'vợ - Nguyễn Thị Lan', 'kỹ sư xây dựng, làm việc tại công trường',
                    'con trai - Trần Minh Khôi', 'đã ngừng hút từ 2021'),
    },
    'dao_tao': {
        'items': (
            ('Học viên đã từng tham gia khoá đào tạo nào của đơn vị chưa?', 'yesno', ()),
            ('Trình độ chuyên môn hiện tại', 'options',
             ('Trung cấp', 'Cao đẳng', 'Đại học', 'Sau đại học')),
            ('Nội dung mong muốn được đào tạo thêm', 'blank', ()),
            ('Học viên có nhu cầu cấp chứng chỉ không?', 'yesno', ()),
            ('Thời gian học phù hợp', 'options',
             ('Trong giờ hành chính', 'Buổi tối', 'Cuối tuần', 'Trực tuyến')),
            ('Đơn vị công tác và vị trí đảm nhiệm', 'blank', ()),
            ('Học viên có cần bố trí chỗ ở không?', 'yesno', ()),
            ('Hình thức thanh toán học phí', 'options',
             ('Đơn vị chi trả', 'Cá nhân tự túc', 'Hỗ trợ một phần')),
        ),
        'answers': ('nghiệp vụ kế toán nâng cao', 'không có', 'Phòng Kỹ thuật, chuyên viên',
                    'an toàn lao động', 'có, ở ký túc xá', 'đấu thầu qua mạng'),
    },
}

# TÊN của tài liệu nói nó hỏi về chuyện gì, nên chủ đề đọc từ chính `titles`
# trước. `profile` chỉ là lưới hứng: ba phôi hành chính đều `admin`, nên bốc
# theo profile thì "PHIẾU ĐÁNH GIÁ NHÂN SỰ" ra câu hỏi về khoá đào tạo và
# "PHIẾU ĐĂNG KÝ ĐÀO TẠO" ra câu hỏi đánh giá nhân sự -- đo được, đúng hai phôi
# hoán chỗ nhau. Khớp theo tên thì một phôi mới tự rơi vào đúng nhóm mà không
# ai phải thêm một dòng bảng.
# Gộp chủ đề khai bằng FILE (`rulebase/corpus/vi/questions_*.txt`) vào bảy chủ
# đề viết thẳng ở trên. Cùng lối `design.ARCHETYPES + _declared()`: file làm
# giàu, không thay thế -- mất thư mục corpus thì bảy chủ đề cũ vẫn chạy.
#
# File THẮNG khi trùng tên chủ đề: người sửa file là người vừa quyết, còn
# bảng trong mã là cái có sẵn.
def _as_item(entry) -> dict:
    """Một câu hỏi, MỘT hình dạng dữ liệu.

    Bảy chủ đề viết trong file này khai câu hỏi bằng tuple
    `(câu, dạng, lựa chọn)`; chủ đề khai bằng corpus khai bằng dict, vì mười
    hai dạng mới mang tham số khác nhau và một tuple ba ô không chở nổi. Quy
    về dict ngay lúc gộp: để hai hình dạng chạy song song thì mọi hàm phía
    sau phải biết cả hai, và cái quên biết sẽ là cái viết sau."""
    if isinstance(entry, dict):
        return dict(entry)
    prompt, shape, options = entry
    item = {"shape": shape, "prompt": prompt}
    if options:
        item["options"] = tuple(options)
    return item


for _name, _theme in list(QUESTION_THEMES.items()):
    QUESTION_THEMES[_name] = {
        "items": tuple(_as_item(i) for i in _theme["items"]),
        "answers": tuple(_theme.get("answers") or ()),
    }

QUESTION_THEMES.update(corpus.question_themes())

THEME_WORDS: dict[str, tuple[str, ...]] = {
    'nhan_su': ('đánh giá nhân sự', 'đánh giá cán bộ', 'nhận xét cuối kỳ',
                'đánh giá công chức', 'nhận xét đánh giá'),
    'dao_tao': ('đào tạo', 'khoá học', 'bồi dưỡng', 'tập huấn', 'học viên'),
    'dich_te': ('y tế', 'dịch tễ', 'khai báo y tế'),
    'bao_hiem': ('thẩm định', 'giám định', 'bảo hiểm nhân thọ',
                 'yêu cầu bảo hiểm', 'bồi thường'),
    'benh_khop': ('bệnh khớp', 'cơ xương khớp'),
    'tien_su_benh': ('tiền sử', 'bệnh án', 'khám sức khoẻ', 'sức khoẻ'),
    'dich_vu': ('khảo sát', 'đánh giá chất lượng', 'lấy ý kiến', 'góp ý'),
    # Bảy chủ đề khai bằng file. Từ khoá đọc TÊN tài liệu, cùng lối bảy chủ
    # đề trên: tên một tờ giấy nói nó hỏi về chuyện gì.
    'hanh_chinh': ('hành chính', 'một cửa', 'thủ tục', 'công dân', 'cư trú',
                   'hộ khẩu', 'uỷ quyền', 'biên nhận hồ sơ'),
    'tai_chinh': ('tín dụng', 'vay', 'ngân hàng', 'sao kê', 'uỷ nhiệm chi',
                  'thanh toán', 'tài khoản'),
    'giao_duc': ('nhập học', 'dự thi', 'học bạ', 'tuyển sinh', 'học phí',
                 'sinh viên', 'điểm', 'tốt nghiệp'),
    'lao_dong': ('lao động', 'hợp đồng lao động', 'thôi việc', 'chấm công',
                 'lương', 'bổ nhiệm', 'nhân sự'),
    'giao_thong': ('điều xe', 'vận đơn', 'phương tiện', 'giao hàng', 'gửi xe',
                   'vận chuyển'),
    # 'giám định' KHÔNG ở đây: `bien_ban_giam_dinh` là giấy BẢO HIỂM trong kho
    # này (`profile: insurance`), và từ khoá ấy kéo nó sang chủ đề xây dựng --
    # đo được, một trang hỏi "Kết luận nghiệm thu" rồi hỏi tiếp về khớp gối.
    'xay_dung': ('nghiệm thu', 'công trình', 'bản vẽ', 'nhật ký', 'bàn giao',
                 'kiểm kê', 'kỹ thuật'),
    'moi_truong': ('an toàn', 'môi trường', 'vi phạm', 'kiểm tra', 'phòng cháy'),
}

THEMES_BY_PROFILE: dict[str, tuple[str, ...]] = {
    'medical': ('benh_khop', 'tien_su_benh', 'dich_te'),
    'insurance': ('bao_hiem', 'benh_khop', 'tien_su_benh', 'tai_chinh'),
    'admin': ('dich_vu', 'nhan_su', 'dao_tao', 'hanh_chinh', 'lao_dong',
              'giao_duc', 'xay_dung', 'moi_truong'),
    'invoice': ('dich_vu', 'tai_chinh', 'giao_thong'),
    'market': ('dich_vu', 'giao_thong'),
    'menu': ('dich_vu',),
    'hotel': ('dich_vu', 'hanh_chinh'),
    'power': ('dich_vu', 'moi_truong'),
    'water': ('dich_vu', 'moi_truong'),
}


OPTION_FOLLOWS: tuple[str, ...] = (
    'Xin cho biết ngày thực hiện và kết quả',
    'Nếu có, vui lòng ghi rõ chi tiết',
    'Vui lòng cho biết thời gian và nơi thực hiện',
)


# Căn cứ pháp lý: đầu mọi quyết định, công văn, tờ trình của cơ quan nhà nước.
# Đây là `Bibliography` theo đúng nghĩa từ vựng dùng -- một danh sách nguồn mà
# văn bản viện dẫn -- và là dạng `Bibliography` mà giấy tờ Việt Nam thật có.
LEGAL_BASIS: tuple[str, ...] = (
    'Căn cứ Luật Doanh nghiệp số 59/2020/QH14 ngày 17 tháng 6 năm 2020;',
    'Căn cứ Luật Kế toán số 88/2015/QH13 ngày 20 tháng 11 năm 2015;',
    'Căn cứ Luật Bảo hiểm y tế số 25/2008/QH12 và các văn bản sửa đổi, bổ sung;',
    'Căn cứ Luật Khám bệnh, chữa bệnh số 15/2023/QH15;',
    'Căn cứ Nghị định số 123/2020/NĐ-CP ngày 19 tháng 10 năm 2020 của Chính phủ;',
    'Căn cứ Nghị định số 145/2020/NĐ-CP quy định chi tiết một số điều của Bộ luật Lao động;',
    'Căn cứ Thông tư số 78/2021/TT-BTC ngày 17 tháng 9 năm 2021 của Bộ Tài chính;',
    'Căn cứ Thông tư số 200/2014/TT-BTC hướng dẫn chế độ kế toán doanh nghiệp;',
    'Căn cứ Quyết định số 1895/QĐ-BYT của Bộ trưởng Bộ Y tế;',
    'Căn cứ Điều lệ tổ chức và hoạt động của Công ty;',
    'Căn cứ Hợp đồng nguyên tắc đã ký giữa hai bên;',
    'Xét đề nghị của Trưởng phòng Tổ chức - Hành chính;',
    'Xét tờ trình của Phòng Kế hoạch - Tài chính;',
    'Theo đề nghị của Trưởng bộ phận chuyên môn;',
)

# Điều khoản đánh số -- `List-Group`. Mỗi điều một tiêu đề ngắn và một câu.
CLAUSES: tuple[tuple[str, str], ...] = (
    ('Phạm vi áp dụng',
     'Văn bản này áp dụng cho toàn bộ các đơn vị trực thuộc kể từ ngày ký.'),
    ('Trách nhiệm của các bên',
     'Các bên có trách nhiệm thực hiện đầy đủ nội dung đã thoả thuận.'),
    ('Thời hạn thực hiện',
     'Thời hạn thực hiện tính từ ngày ký và kết thúc khi hai bên nghiệm thu.'),
    ('Phương thức thanh toán',
     'Thanh toán bằng chuyển khoản trong vòng mười lăm ngày kể từ ngày nhận đủ hồ sơ.'),
    ('Quyền và nghĩa vụ của bên A',
     'Bên A cung cấp đầy đủ thông tin và tạo điều kiện để bên B thực hiện công việc.'),
    ('Quyền và nghĩa vụ của bên B',
     'Bên B chịu trách nhiệm về chất lượng và tiến độ của phần việc được giao.'),
    ('Bảo mật thông tin',
     'Các bên không tiết lộ thông tin của nhau cho bên thứ ba khi chưa được đồng ý.'),
    ('Xử lý vi phạm',
     'Bên vi phạm chịu phạt theo tỷ lệ đã thoả thuận trên giá trị phần việc vi phạm.'),
    ('Giải quyết tranh chấp',
     'Tranh chấp được giải quyết bằng thương lượng; không thành thì đưa ra Toà án có thẩm quyền.'),
    ('Điều khoản thi hành',
     'Các ông, bà Trưởng các bộ phận chịu trách nhiệm thi hành văn bản này.'),
)

# Công thức tính -- `Formula`. Viết như giấy tờ bảo hiểm, thuế, viện phí in ra:
# một dòng đẳng thức bằng chữ, không phải ký hiệu toán.
# Công thức tính, CHIA THEO NGÀNH. Kho phẳng thì một tờ khai y tế in ra
# "Thành tiền = Số lượng × Đơn giá × (1 − Chiết khấu)" -- đúng lỗi mà kho câu
# hỏi vừa mắc, xuất hiện lại ở chỗ khác. Cùng một bài học: nội dung phải biết
# nó đang nằm trên tờ giấy nào.
FORMULAS: dict[str, tuple[str, ...]] = {
    'medical': (
        'Mức hưởng = Chi phí khám chữa bệnh × Tỷ lệ chi trả của quỹ BHYT',
        'Người bệnh tự trả = Tổng chi phí − Quỹ BHYT chi trả − Nguồn khác',
        'Chi phí ngoài danh mục = Tổng chi phí − Chi phí thuộc phạm vi BHYT',
    ),
    'insurance': (
        'Số tiền bồi thường = Giá trị tổn thất × Tỷ lệ bảo hiểm × (1 − Mức miễn thường)',
        'Phí bảo hiểm = Số tiền bảo hiểm × Tỷ lệ phí × Thời hạn / 12',
        'Quyền lợi chi trả = Số tiền bảo hiểm × Tỷ lệ phần trăm theo bảng quyền lợi',
    ),
    'power': (
        'Tiền điện = (Chỉ số mới − Chỉ số cũ) × Hệ số nhân × Đơn giá bậc thang',
        'Sản lượng tiêu thụ = Chỉ số cuối kỳ − Chỉ số đầu kỳ',
    ),
    'water': (
        'Tiền nước = (Chỉ số mới − Chỉ số cũ) × Đơn giá theo định mức',
        'Lượng vượt định mức = Sản lượng tiêu thụ − Định mức được cấp',
    ),
    'admin': (
        'Tiền lương thực nhận = Lương cơ bản + Phụ cấp − Các khoản khấu trừ',
        'Số ngày công thực tế = Tổng ngày làm việc − Ngày nghỉ không lương',
        'Mức thưởng = Hệ số hoàn thành × Mức thưởng cơ bản',
    ),
    'invoice': (
        'Thành tiền = Số lượng × Đơn giá × (1 − Chiết khấu)',
        'Thuế GTGT phải nộp = Giá tính thuế × Thuế suất',
        'Tổng thanh toán = Tiền hàng + Thuế GTGT − Giảm giá',
    ),
}


# Ghi chú có dấu sao -- `Footnote`. Ngắn, đứng cuối tờ, luôn mở đầu bằng dấu.
FOOTNOTES: tuple[str, ...] = (
    '(*) Đơn giá đã bao gồm thuế giá trị gia tăng.',
    '(*) Số liệu chưa bao gồm các khoản phát sinh ngoài hợp đồng.',
    '(**) Áp dụng cho khách hàng có hợp đồng từ mười hai tháng trở lên.',
    '(*) Chứng từ này chỉ có giá trị khi có đủ chữ ký và dấu của đơn vị.',
    '(*) Tỷ lệ chi trả căn cứ theo mức hưởng ghi trên thẻ bảo hiểm y tế.',
    '(**) Các mục đánh dấu sao do người khai tự kê và tự chịu trách nhiệm.',
)

# Chú thích bảng/hình -- `Caption`. Khác `caption.table`: cái kia là TIÊU ĐỀ
# đứng trên bảng ("BẢNG KÊ CHI TIẾT"), cái này là câu chú đứng DƯỚI, đánh số.
CAPTIONS: tuple[str, ...] = (
    'Bảng 1: Chi tiết các khoản mục phát sinh trong kỳ báo cáo.',
    'Bảng 2: Tổng hợp số liệu theo từng bộ phận.',
    'Hình 1: Sơ đồ quy trình tiếp nhận và xử lý hồ sơ.',
    'Hình 2: Biểu đồ so sánh số liệu giữa hai kỳ liền kề.',
    'Bảng 1: Danh mục hồ sơ, chứng từ kèm theo.',
)


def _theme_for(arch, rng: random.Random) -> str:
    """Bộ câu hỏi hợp với phôi này: theo TÊN trước, `profile` sau.

    Tên tài liệu nói nó hỏi về chuyện gì; `profile` chỉ nói nó thuộc ngành nào,
    và ba phôi hành chính khác hẳn nhau vẫn cùng một `profile`."""
    titles = " ".join(arch.titles).lower()
    for theme, words in THEME_WORDS.items():
        if any(word in titles for word in words):
            return theme
    names = THEMES_BY_PROFILE.get(arch.profile, ('dich_vu',))
    return rng.choice(names)


def _digits(rng: random.Random, n: int) -> str:
    return ''.join(str(rng.randrange(10)) for _ in range(n))


def address(rng: random.Random) -> str:
    street = rng.choice(corpus.streets() or ('Lê Lợi',))
    ward = rng.choice(corpus.wards() or ('Phường 1',))
    return (f'Số {rng.randrange(1, 480)}{rng.choice(("", "", "", "A", "B", "/2"))} '
            f'{street}, {ward}, {rng.choice(DISTRICTS)}, {rng.choice(CITIES)}')


def tax_code(rng: random.Random) -> str:
    base = _digits(rng, 10)
    return f'{base}-{_digits(rng, 3)}' if rng.random() < 0.25 else base


def phone(rng: random.Random) -> str:
    head = rng.choice(('090', '091', '093', '094', '096', '097', '098',
                       '032', '033', '034', '035', '036', '037', '038', '039',
                       '070', '076', '077', '078', '079',
                       '081', '082', '083', '084', '085', '086', '088', '089'))
    tail = _digits(rng, 7)
    if rng.random() < 0.3:
        return f'{head}.{tail[:3]}.{tail[3:]}'
    if rng.random() < 0.3:
        return f'{head} {tail[:3]} {tail[3:]}'
    return head + tail


def bank_account(rng: random.Random) -> str:
    return (f'{_digits(rng, rng.choice((10, 12, 13, 14)))} tại '
            f'{rng.choice(BANKS)} - Chi nhánh {rng.choice(CITIES)}')


def a_date(rng: random.Random, base: dt.date | None = None,
           spread: int = 900) -> dt.date:
    origin = base or dt.date(2026, 9, 10)
    return origin - dt.timedelta(days=rng.randrange(spread))


def fmt_date(value: dt.date, style: int = 0) -> str:
    if style == 1:
        return f'ngày {value.day:02d} tháng {value.month:02d} năm {value.year}'
    if style == 2:
        return value.strftime('%d-%m-%Y')
    if style == 3:
        return value.strftime('%Y/%m/%d')
    return value.strftime('%d/%m/%Y')


def _gen(name: str, rng: random.Random, doc_date: dt.date) -> str:
    """Giá trị cho một `FieldDef.gen`. Bảng tra chứ không phải chuỗi `if`
    dài, để thêm một loại trường là thêm một dòng."""
    if name == 'org_name':
        pool = corpus.shops('invoice')
        return rng.choice(pool)[0] if pool else 'CÔNG TY TNHH THƯƠNG MẠI'
    if name == 'person':
        pool = corpus.people()
        return rng.choice(pool) if pool else 'Nguyễn Văn An'
    if name == 'address':
        return address(rng)
    if name == 'tax_code':
        return tax_code(rng)
    if name == 'phone':
        return phone(rng)
    if name == 'bank_account':
        return bank_account(rng)
    if name == 'payment':
        pool = corpus.payments()
        return rng.choice(pool)[0] if pool else 'Tiền mặt'
    if name == 'birthdate':
        year = rng.randrange(1955, 2008)
        return f'{rng.randrange(1, 29):02d}/{rng.randrange(1, 13):02d}/{year}'
    if name == 'gender':
        return rng.choice(GENDERS)
    if name == 'id_number':
        return _digits(rng, rng.choice((9, 12, 12, 12)))
    if name == 'date':
        return fmt_date(a_date(rng, doc_date, 2000), rng.choice((0, 0, 2)))
    if name == 'datetime':
        moment = a_date(rng, doc_date, 400)
        return (f'{rng.randrange(0, 24):02d}h{rng.randrange(0, 60):02d} '
                f'{fmt_date(moment)}')
    if name == 'issuer':
        return f'{rng.choice(ISSUERS)} {rng.choice(CITIES)}'
    if name == 'department':
        return rng.choice(DEPARTMENTS)
    if name == 'position':
        return rng.choice(POSITIONS)
    if name == 'record_no':
        return f'{_digits(rng, 6)}/{doc_date.year}'
    if name == 'bhyt':
        return (f'{rng.choice(("DN", "HS", "TE", "HT", "BT", "CN"))}'
                f'{rng.randrange(1, 5)}{_digits(rng, 2)}{_digits(rng, 10)}')
    if name == 'ward':
        return rng.choice(WARDS_MED)
    if name == 'diagnosis':
        first = rng.choice(DIAGNOSES)
        if rng.random() < 0.35:
            other = rng.choice([d for d in DIAGNOSES if d != first])
            return f'{first}; theo dõi {other.lower()}'
        return first
    if name == 'treatment':
        return rng.choice(TREATMENTS)
    if name == 'policy_no':
        return (f'{rng.choice(("HD", "GCN", "BH", "PC"))}'
                f'{doc_date.year}{_digits(rng, 6)}')
    if name == 'money_big':
        return money(rng.randrange(50, 4000) * 1000000, suffix=' đồng')
    if name == 'money_mid':
        return money(rng.randrange(300, 9000) * 10000, suffix=' đồng')
    if name == 'cover_object':
        return rng.choice(COVER_OBJECTS)
    if name == 'customer_no':
        return f'P{_digits(rng, 2)}{rng.choice(("EV", "PE", "HN", "HD"))}{_digits(rng, 7)}'
    if name == 'meter_no':
        return _digits(rng, rng.choice((8, 9, 10)))
    if name == 'period':
        return f'Tháng {doc_date.month:02d}/{doc_date.year}'
    if name == 'meter_prev':
        return money(rng.randrange(1000, 60000), suffix='')
    if name == 'meter_now':
        return money(rng.randrange(60001, 120000), suffix='')
    if name == 'consumed':
        return money(rng.randrange(40, 900), suffix=' kWh')
    if name == 'room':
        return f'{rng.randrange(101, 920)} - {rng.choice(ROOMS)}'
    if name == 'nights':
        return f'{rng.randrange(1, 15)} đêm'
    if name == 'contract_no':
        return (f'{_digits(rng, 3)}/{doc_date.year}/HĐ-'
                f'{rng.choice(("KT", "MB", "DV", "XD"))}')
    if name == 'term':
        return rng.choice(TERMS)
    return ''


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step) if step > 1 else int(round(value))


def _rows(rng: random.Random, design: Design, count: int,
          doc_date: dt.date) -> tuple[list[Row], int, list[str]]:
    """`count` dòng hàng, và tổng tiền của chúng.

    Số tiền do đây tính hết: `amount = qty x unit_price`, và tổng là tổng của
    cột `amount`. Không cột nào lấy số từ nơi khác."""
    arch = design.archetype
    # Kho hàng theo PHÔI, không chỉ theo ngành -- xem `_blocks.yaml::items`
    # về việc một tờ học bạ từng liệt kê bình chữa cháy.
    catalogue = corpus.items_for(arch, item_rules())
    picked = corpus.sample(rng, catalogue, count)
    pool = UNITS_BY_PROFILE.get(arch.profile, UNITS)
    units = list(pool) if len(pool) <= 4 else rng.sample(list(pool), 4)
    step = 500 if arch.profile in ('market', 'eatery', 'menu', 'bakery') else 1000
    date_style = rng.choice((0, 0, 2))
    rows = []
    total = 0
    for index, (name, lo, hi) in enumerate(picked, start=1):
        unit_price = _round_to(rng.uniform(lo, hi), step)
        if arch.profile in ('power', 'water'):
            qty_n = rng.randrange(10, 400)
        elif arch.profile == 'export':
            qty_n = rng.randrange(20, 900)
        else:
            qty_n = rng.randrange(1, 26)
        amount = unit_price * qty_n
        total += amount
        vat = rng.choice((0, 5, 8, 10, 10))
        # Dòng chi tiết cho BẢNG CON lồng trong ô mô tả. Chỉ rút số ngẫu
        # nhiên khi dáng có bật bảng con, nên mọi tờ giấy không có nó vẫn
        # rút đúng dãy số như trước -- một trục mới không được làm lệch
        # những trục cũ.
        detail = ''
        if design.nested_detail and rng.random() < 0.45:
            bits = [f'Mã lô: LOT{_digits(rng, 5)}']
            if rng.random() < 0.62:
                bits.append(f'Xuất xứ: {rng.choice(ORIGINS)}')
            if rng.random() < 0.42:
                bits.append(f'Hạn dùng: {rng.randrange(1, 13):02d}/'
                            f'{doc_date.year + rng.randrange(1, 4)}')
            detail = ' | '.join(bits)
        # Chỉ số công tơ đầu kỳ: một số có thật, và chỉ số cuối kỳ là
        # nó cộng lượng tiêu thụ của dòng -- hai cột ấy phải khớp nhau.
        meter_prev = rng.randrange(120, 9800)
        values = {
            'stt': str(index),
            'name': name,
            'ref': f'{rng.choice(("VT", "HH", "DV", "MS"))}{_digits(rng, 5)}',
            'unit': rng.choice(units),
            'qty': money(qty_n, suffix=''),
            'unit_price': money(unit_price, suffix=''),
            'amount': money(amount, suffix=''),
            'vat_rate': f'{vat}%' if vat else 'KCT',
            'vat_amount': money(amount * vat // 100, suffix=''),
            'note': rng.choice(('', '', '', 'Đã kiểm', 'Hàng mới 100%',
                                'Theo hợp đồng', 'Bảo hành 12T', 'Đủ số lượng')),
            'date': fmt_date(a_date(rng, doc_date, 120), date_style),
            'discount': money(amount * rng.choice((0, 0, 5, 10)) // 100, suffix=''),
            'copay': money(amount * rng.choice((0, 20, 20, 100)) // 100, suffix=''),
            'fund': money(amount * rng.choice((100, 80, 80, 0)) // 100, suffix=''),
            # Mười ba cột lấy từ `rulebase/layouts/*.yaml`. Giá trị suy từ
            # `amount`/`unit_price` của CHÍNH dòng này, không bốc rời: một
            # bảng viện phí mà "Thành tiền BH" lớn hơn "Thành tiền BV" là một
            # tờ giấy không ai in ra, và `check.py` cộng lại thì lệch.
            'price_bv': money(unit_price, suffix=''),
            'price_bh': money(unit_price * rng.choice((100, 90, 80)) // 100, suffix=''),
            'amount_bv': money(amount, suffix=''),
            'amount_bh': money(amount * rng.choice((100, 80, 80, 0)) // 100, suffix=''),
            'rate_bhyt': f'{rng.choice((100, 95, 80, 0))}%',
            'rate_service': f'{rng.choice((100, 80, 50))}%',
            'self_pay': money(amount * rng.choice((0, 0, 20, 100)) // 100, suffix=''),
            'other_pay': money(amount * rng.choice((0, 0, 0, 10)) // 100, suffix=''),
            'meter_prev': str(meter_prev),
            'meter_now': str(meter_prev + qty_n),
            'quota': str(rng.choice((4, 6, 10, 15, 20))),
            'amount_with_vat': money(amount + amount * vat // 100, suffix=''),
            'barcode': _digits(rng, 13),
            'detail': detail,
            # KHÔNG phải một cột: `_extracted` và `markup` chỉ đọc các khoá
            # có trong `COLUMNS`, nên số này không bao giờ in ra giấy. Nó ở
            # đây để dòng cộng nhóm cộng lại bằng SỐ chứ không phải bằng cách
            # đọc ngược chuỗi đã định dạng -- đọc ngược là chỗ một dấu chấm
            # phân cách nghìn biến thành một phép cộng sai.
            'amount_n': str(amount),
        }
        rows.append(Row(values))
    return rows, total, units


# Muối riêng cho điều khoản. Cùng lý do `draw.CONTENT_SALT` có muối riêng:
# hai thứ bốc từ cùng một seed mà không muối thì chúng đi cùng nhau, và ở đây
# thứ đi cùng sẽ là "tài liệu nào dài thì tài liệu ấy cũng chọn điều khoản
# giống nhau".
CLAUSE_SALT = 0x0C1A11EF


def clauses_of(seed: int, design: Design, count: int) -> list[tuple[str, str]]:
    """`count` điều khoản của tài liệu ấy: `(tiêu đề, thân)`.

    Bốc TỪ CHÍNH `seed` chứ không từ `rng` đang chạy, và lấy TIỀN TỐ của một
    hoán vị cố định. Nhờ thế `refill(n)` là đơn điệu: xin thêm một điều thì
    được đúng các điều cũ cộng một điều mới, không phải một bộ điều khác
    hẳn. `paginate.py` đo rồi chỉnh số mục vài vòng, và một bộ nội dung đổi
    hẳn sau mỗi vòng thì phép đo vòng trước không nói gì về vòng sau -- nó
    dao động thay vì hội tụ. Dòng hàng của bảng không có tính chất này và đó
    là một điểm yếu sẵn có, không phải một điều đáng bắt chước.

    Số KHOẢN mỗi điều cũng chốt theo chỉ số điều, cùng lý do: điều thứ ba in
    ra hai khoản thì lần đo nào nó cũng hai khoản.
    """
    pool = corpus.clauses(design.archetype.profile)
    if not pool:
        return []
    order = list(range(len(pool)))
    random.Random(seed ^ CLAUSE_SALT).shuffle(order)
    out: list[tuple[str, str]] = []
    for rank in order[:max(int(count), 0)]:
        span = pool[rank]
        head, khoan = span[0], list(span[1:])
        if not khoan:
            out.append((head, ''))
            continue
        # Hạt giống theo CHỈ SỐ trong kho, không theo vị trí trong tài liệu:
        # cùng một điều thì cùng số khoản dù nó rơi vào điều 3 hay điều 17.
        take = random.Random(seed ^ CLAUSE_SALT ^ (rank * 2654435761)).randint(
            1, len(khoan))
        out.append((head, ' '.join(khoan[:take])))
    return out


QUESTION_SALT = 0x5178E31


def questions_of(seed: int, design: Design, count: int) -> list[dict]:
    """`count` câu hỏi của tờ khai ấy, dựng theo cùng lối `clauses_of`.

    Hai chỗ khác bản cũ, và cả hai để khối này CHẢY được qua nhiều tờ:

    * bốc qua NHIỀU chủ đề khi một chủ đề không đủ câu. Một chủ đề có tám
      đến mười hai câu, đủ cho một tờ; một tờ khai y tế bốn trang thì không.
      Chủ đề hợp nhất đứng trước, nên câu đầu tờ vẫn là câu đúng ngành, và
      các chủ đề sau chỉ vào khi đã cạn câu;
    * bốc từ `seed` và lấy TIỀN TỐ của một hoán vị cố định, nên `refill(n)`
      đơn điệu -- xem `clauses_of` về việc vì sao `paginate.py` cần thế.
    """
    arch = design.archetype
    first = _theme_for(arch, random.Random(seed ^ QUESTION_SALT))
    # TRÀN SANG CHỦ ĐỀ HỌ HÀNG TRƯỚC, không sang bất kỳ chủ đề nào.
    #
    # Bản trước nối `first` với MỌI chủ đề còn lại theo thứ tự từ điển, nên
    # một tờ khai dài cạn câu ở chủ đề của nó rồi hỏi tiếp câu của chủ đề
    # khác. Đo trên một trang thật: `bien_ban_giam_dinh` hỏi "Kết luận
    # nghiệm thu" xong hỏi ngay "Quý khách bị ảnh hưởng các khớp nào?" --
    # hai câu không cùng một tờ giấy nào trên đời.
    #
    # `THEMES_BY_PROFILE` đã nói chủ đề nào hợp với hồ sơ nào; dùng chính nó
    # làm vòng thứ hai, rồi mới tới phần còn lại làm vòng cuối. Một tờ khai
    # phải rất dài mới chạm tới vòng cuối, và khi ấy có câu lạc đề vẫn hơn
    # có một trang trắng.
    kin = [n for n in THEMES_BY_PROFILE.get(arch.profile, ())
           if n != first and n in QUESTION_THEMES]
    rest = [n for n in QUESTION_THEMES if n != first and n not in kin]
    names = [first] + kin + rest
    # Kho câu trả lời đi THEO TỪNG CÂU, không gộp chung.
    #
    # Bản trước nối `answers` của mọi chủ đề đã lấy vào một rổ, nên một câu
    # của chủ đề xây dựng bốc trúng câu trả lời của chủ đề bệnh khớp. Đo
    # được trên một trang thật: "Nghiệm thu hạng mục *đã tiêm đủ ba mũi*
    # thuộc gói thầu *đã tiêm đủ ba mũi*". Nhãn KIE vẫn đúng chỗ, nhưng chữ
    # trên giấy là chữ không tờ nào in ra -- và đó là thứ mô hình đọc.
    pool: list[dict] = []
    pool_answers: list[tuple[str, ...]] = []
    for name in names:
        theme = QUESTION_THEMES[name]
        own = tuple(theme['answers']) or ('',)
        pool.extend(theme['items'])
        pool_answers.extend([own] * len(theme['items']))
        if len(pool) >= count:
            break
    if not pool:
        return []
    order = list(range(len(pool)))
    # Xáo TRONG chủ đề đầu trước, rồi mới tới phần thêm: giữ được "câu đầu tờ
    # là câu đúng ngành" mà vẫn không in theo đúng thứ tự khai trong mã.
    head = len(QUESTION_THEMES[first]['items'])
    rng_head = random.Random(seed ^ QUESTION_SALT)
    first_part, rest = order[:head], order[head:]
    rng_head.shuffle(first_part)
    rng_head.shuffle(rest)
    order = first_part + rest

    out: list[dict] = []
    for rank in order[:max(int(count), 0)]:
        # Hạt giống theo CHỈ SỐ trong kho: cùng một câu thì lần đo nào cũng
        # cùng một dáng trả lời, nên chiều cao của nó không nhảy giữa hai
        # vòng đo của `paginate.py`.
        rng = random.Random(seed ^ QUESTION_SALT ^ (rank * 2654435761))
        out.append(_filled(pool[rank], rng, list(pool_answers[rank])))
    return out


def _spread(rng: random.Random, free: list[str], count: int) -> list[str]:
    """`count` câu trả lời KHÁC NHAU khi kho đủ dài, lặp lại khi không."""
    pool = [x for x in free if x]
    if not pool or count <= 0:
        return [''] * max(count, 0)
    if count <= len(pool):
        return rng.sample(pool, count)
    return [rng.choice(pool) for _ in range(count)]


# Tên cột nói CỘT ẤY CHỨA GÌ. Bảng điền tay trên giấy thật có cột "Họ tên",
# "Năm sinh", "Số điện thoại" -- đổ một chuỗi bất kỳ vào mọi cột thì ra những
# ô như `Chức danh: 3853`, đo được trên một trang vẽ thật.
#
# So khớp trên tên cột không dấu-hoá, và tiền tố dài hơn không cần ở đây vì
# các mẫu không lồng nhau. Cột không khớp mẫu nào rơi về câu trả lời tự do --
# đúng thứ một cột "Ghi chú" hay "Nội dung" chứa.
COLUMN_KINDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (('họ tên', 'họ và tên', 'người', 'chủ hộ'), 'person'),
    (('năm sinh',), 'year'),
    (('ngày', 'thời gian', 'thời hạn'), 'date'),
    (('số điện thoại', 'điện thoại'), 'phone'),
    (('số giấy tờ', 'số hiệu', 'mã số', 'số sổ', 'số'), 'digits'),
    (('quan hệ',), 'relation'),
    (('chức danh', 'chức vụ', 'vị trí'), 'position'),
    (('đơn vị', 'trường', 'cơ quan'), 'org'),
    (('giá trị', 'khối lượng', 'số lượng', 'thu nhập'), 'amount'),
    (('xếp loại', 'kết quả'), 'grade'),
    (('loại', 'tên'), 'noun'),
)

RELATIONS = ('Con', 'Vợ', 'Chồng', 'Cha', 'Mẹ', 'Anh', 'Chị', 'Em')
GRADES = ('Giỏi', 'Khá', 'Trung bình', 'Đạt', 'Xuất sắc')


def _column_value(name: str, rng: random.Random, free: list[str]) -> str:
    """Giá trị hợp với CỘT `name` trong một bảng người ta điền tay."""
    low = str(name or '').strip().lower()
    kind = next((k for words, k in COLUMN_KINDS
                 if any(w in low for w in words)), 'free')
    if kind == 'person':
        return rng.choice(corpus.people() or ('Nguyễn Văn An',))
    if kind == 'year':
        return str(rng.randint(1955, 2020))
    if kind == 'date':
        return f'{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(2018, 2026)}'
    if kind == 'phone':
        return '0' + _digits_of(rng, 9)
    if kind == 'digits':
        return _digits_of(rng, rng.choice((8, 10, 12)))
    if kind == 'relation':
        return rng.choice(RELATIONS)
    if kind == 'position':
        return rng.choice(POSITIONS)
    if kind == 'org':
        shops = corpus.shops('admin')
        return rng.choice(shops)[0] if shops else 'Đơn vị trực thuộc'
    if kind == 'amount':
        return f'{rng.randint(1, 900):,}'.replace(',', '.')
    if kind == 'grade':
        return rng.choice(GRADES)
    if kind == 'noun':
        return rng.choice(free) if free else ''
    return rng.choice(free) if free else ''


def _digits_of(rng: random.Random, n: int) -> str:
    """`n` chữ số, không bắt đầu bằng 0 -- số giấy tờ thật không thế."""
    if n <= 0:
        return ''
    return str(rng.randint(1, 9)) + ''.join(str(rng.randrange(10))
                                            for _ in range(n - 1))


def _filled(spec: dict, rng: random.Random, free: list[str]) -> dict:
    """Một câu hỏi ĐÃ ĐIỀN: thêm ô nào tích, số nào viết vào.

    Tách khỏi `questions_of` vì hai việc đổi theo hai thứ khác nhau: định
    dạng câu hỏi là DỮ LIỆU trong `rulebase/corpus/vi/questions_*.txt`, còn
    trạng thái điền là chuyện của từng tờ giấy. Thêm một dạng là thêm một
    nhánh ở đây và một nhánh ở `markup._shape_rows` -- hai chỗ, và chúng phải
    khớp; không có chỗ thứ ba.
    """
    item = dict(spec)
    shape = item.get('shape', 'blank')

    if shape == 'blank':
        item['answer'] = rng.choice(free)
        item.setdefault('options', ())
    elif shape == 'yesno':
        ticked = rng.choice(('Có', 'Không'))
        follow = rng.random() < 0.65
        item.update(ticked=ticked, options=('Có', 'Không'),
                    sub='Nếu có, vui lòng mô tả chi tiết' if follow else '',
                    answer=rng.choice(free) if follow and ticked == 'Có' else '')
    elif shape == 'options':
        options = list(item.get('options') or ())
        item['picked'] = set(rng.sample(options, min(rng.randint(1, 2), len(options)))) if options else set()
        item['sub'] = rng.choice(OPTION_FOLLOWS)
        item['answer'] = rng.choice(free)
    elif shape == 'boxchar':
        cells = max(int(item.get('cells') or 0), 1)
        # Điền THIẾU đôi khi, không phải luôn đầy: tờ khai thật in đủ số ô mà
        # người viết dừng ở đâu là dừng, và một mô hình phải học được ô trống
        # cuối dãy cũng là ô.
        used = cells if rng.random() < 0.75 else rng.randint(max(cells - 4, 1), cells)
        item['value'] = _digits_of(rng, used)
    elif shape == 'date_boxes':
        item.update(day=f'{rng.randint(1, 28):02d}',
                    month=f'{rng.randint(1, 12):02d}',
                    year=str(rng.randint(1960, 2026)))
    elif shape == 'grid':
        cols = list(item.get('cols') or ())
        rows = list(item.get('rows') or ())
        item['picked'] = {i: rng.randrange(len(cols)) for i in range(len(rows))} if cols else {}
    elif shape == 'scale':
        levels = max(int(item.get('levels') or 5), 2)
        item['levels'] = levels
        item['picked'] = rng.randint(1, levels)
    elif shape == 'rank':
        items = list(item.get('items') or ())
        order = list(range(1, len(items) + 1))
        rng.shuffle(order)
        item['order'] = order
    elif shape == 'inline_blank':
        blanks = str(item.get('prompt') or '').count('…')
        # KHÔNG lặp lại: ba chỗ trống trong một câu mà điền cùng một chuỗi là
        # một câu không ai viết ra. Hết kho thì mới cho lặp.
        item['answers'] = _spread(rng, free, blanks)
    elif shape == 'subquestion':
        labels = list(item.get('subs') or ())
        item['subs'] = list(zip(labels, _spread(rng, free, len(labels))))
    elif shape == 'table_form':
        cols = list(item.get('cols') or ())
        lines = max(int(item.get('lines') or 2), 1)
        # Dòng CUỐI để trống: bảng điền tay trên giấy thật luôn thừa dòng, và
        # dòng thừa ấy là thứ phân biệt một bảng ĐỂ ĐIỀN với một bảng số liệu.
        body = []
        for line in range(lines):
            if line == lines - 1 and rng.random() < 0.7:
                body.append([''] * len(cols))
                continue
            body.append([_column_value(name, rng, free) for name in cols])
        item['rows'] = body
    elif shape == 'attachment':
        items = list(item.get('items') or ())
        want = rng.randint(1, len(items)) if items else 0
        item['picked'] = set(rng.sample(items, want)) if items else set()
    return item


def _regroup(doc: Doc) -> None:
    """Tính lại cộng-nhóm cho `doc`, theo đúng cách `markup.py` chia nhóm.

    Chia nhóm là một phép tính trên CHỈ SỐ dòng, và nó nằm ở hai chỗ: đây và
    `markup._group_of`. Hai chỗ ấy phải nói cùng một câu, nên câu ấy viết ra
    đúng một lần ở đây: nhóm thứ `i` là các dòng `[i*size, (i+1)*size)`, trừ
    nhóm cuối ôm nốt phần còn lại."""
    size, names = doc.row_group_size, doc.row_group_names
    if not size or not names:
        doc.row_group_totals = []
        return
    sums = [0] * len(names)
    for index, row in enumerate(doc.rows):
        which = min(index // size, len(names) - 1)
        try:
            sums[which] += int(row.values.get('amount_n') or 0)
        except ValueError:
            pass
    doc.row_group_totals = [money(value, suffix='') for value in sums]


def build(design: Design, rng: random.Random, rows_wanted: int) -> Doc:
    """Một tờ giấy đã có đủ chữ. `rows_wanted` do `paginate.py` quyết định --
    nó là số dòng cần để mỗi tờ đầy 80%, không phải một con số rút ngẫu
    nhiên."""
    arch = design.archetype
    doc_date = a_date(rng)

    shops = corpus.shops(arch.profile)
    org, branch = rng.choice(shops) if shops else ('CÔNG TY TNHH ABC', '')
    if arch.org_kind == 'state':
        parent = rng.choice(('UỶ BAN NHÂN DÂN TỈNH', 'SỞ TÀI CHÍNH', 'BỘ Y TẾ',
                             'TỔNG CỤC THUẾ', 'UỶ BAN NHÂN DÂN THÀNH PHỐ',
                             'SỞ GIÁO DỤC VÀ ĐÀO TẠO',
                             'BẢO HIỂM XÃ HỘI VIỆT NAM', 'SỞ Y TẾ',
                             'CỤC THUẾ TỈNH'))
    elif arch.org_kind == 'hospital':
        parent = rng.choice(('SỞ Y TẾ ' + rng.choice(CITIES).upper(), 'BỘ Y TẾ'))
    else:
        parent = rng.choice(('', '', '', 'TẬP ĐOÀN ĐẦU TƯ VÀ PHÁT TRIỂN',
                             'TỔNG CÔNG TY THƯƠNG MẠI'))

    title = rng.choice(arch.titles)
    subtitle = rng.choice(arch.subtitles) if arch.subtitles else ''

    doc_no = f'{rng.randrange(1, 9999):04d}'
    if rng.random() < 0.4:
        doc_no = f'{rng.randrange(1, 999):03d}/{doc_date.year}'
    serial = (f'{rng.randrange(1, 3)}C{doc_date.year % 100:02d}'
              f'{rng.choice("TKMNPQ")}{rng.choice("ABCDE")}')
    form = f'{rng.randrange(1, 9)}/{rng.randrange(1, 99):03d}-GTGT'

    fields = [(f, _gen(f.gen, rng, doc_date)) for f in design.fields]

    rows = []
    total = 0
    units = []
    if design.has('table'):
        rows, total, units = _rows(rng, design, max(rows_wanted, 1), doc_date)

    totals = []
    grand_label = grand = ''
    grand_amount = 0
    summary = []
    words_label = words = ''
    if design.has('totals') and arch.totals == 'money':
        vat_rate = rng.choice((0, 5, 8, 10, 10, 10))
        discount = total * rng.choice((0, 0, 0, 2, 5)) // 100
        net = total - discount
        vat = net * vat_rate // 100
        grand_amount = net + vat

        lines = [(rng.choice(('Cộng tiền hàng', 'Tổng tiền hàng',
                              'Cộng thành tiền')),
                  money(total, suffix=''))]
        if discount:
            lines.append((rng.choice(('Chiết khấu thương mại', 'Giảm giá')),
                          money(discount, suffix='')))
        if vat_rate:
            lines.append((f'Thuế GTGT ({vat_rate}%)', money(vat, suffix='')))
        else:
            lines.append(('Thuế GTGT', 'Không chịu thuế'))
        totals = lines
        grand_label = rng.choice(('TỔNG CỘNG THANH TOÁN',
                                  'Tổng cộng tiền thanh toán',
                                  'TỔNG TIỀN THANH TOÁN', 'Cộng tiền thanh toán'))
        grand = money(grand_amount, suffix=' đ' if rng.random() < 0.4 else '')
        if design.has('words'):
            words_label = rng.choice(('Số tiền bằng chữ:', 'Bằng chữ:',
                                      'Số tiền viết bằng chữ:'))
            words = words_vi(grand_amount).capitalize() + ' đồng chẵn./.'
        if design.has('summary'):
            summary = [
                ('Cộng tiền hàng chưa thuế', money(net, suffix='')),
                ('Thuế suất GTGT', f'{vat_rate}%'),
                ('Tiền thuế GTGT', money(vat, suffix='')),
                ('Tổng tiền thanh toán', money(grand_amount, suffix='')),
            ]
            # Khung tổng hợp thuế NÓI ĐÚNG những gì khối tổng nói -- cùng tiền
            # hàng, cùng tiền thuế, cùng tổng cộng, chỉ khác chữ. In cả hai là
            # in một con số hai lần dưới hai cái tên, và tờ giấy thật không làm
            # thế: hoá đơn GTGT in cái khung, bảng kê in mấy dòng cộng. Khung
            # đã có thì mấy dòng cộng thôi.
            #
            # `grand_amount` GIỮ: `words` ("Bằng chữ: ...") và
            # `content_signature` đọc nó, và cả hai vẫn đúng -- con số ấy vẫn ở
            # trên giấy, chỉ là in một lần.
            totals = []
            grand_label = grand = ''
    elif design.has('totals') and arch.totals == 'count':
        grand_label = rng.choice(('Tổng cộng', 'Cộng', 'TỔNG SỐ'))
        grand = f'{len(rows)} ' + rng.choice(('dòng', 'khoản mục', 'mục', 'người'))

    notes = []
    if design.has('notes'):
        want = rng.randint(1, min(4, len(arch.notes)))
        notes = rng.sample(list(arch.notes), want)

    checks = []
    if design.has('checks'):
        pool = (
            ('Quý khách đánh giá thái độ phục vụ',
             ('Rất hài lòng', 'Hài lòng', 'Bình thường', 'Chưa hài lòng')),
            ('Thời gian xử lý hồ sơ', ('Nhanh', 'Đúng hẹn', 'Chậm')),
            ('Đã nhận đủ hồ sơ kèm theo', ('Có', 'Không')),
            ('Đề nghị cấp lại giấy tờ', ('Có', 'Không')),
            ('Hình thức nhận kết quả', ('Nhận trực tiếp', 'Qua bưu điện')),
            ('Đã đối chiếu bản chính', ('Có', 'Chưa')),
            ('Quý khách có muốn nhận thông báo qua SMS', ('Có', 'Không')),
            ('Mức độ đáp ứng yêu cầu công việc', ('Tốt', 'Khá', 'Trung bình')),
        )
        for question, answers in rng.sample(list(pool), rng.randint(2, 5)):
            ticked = rng.choice(answers)
            marks = ' '.join(f'{"☒" if a == ticked else "☐"} {a}' for a in answers)
            checks.append((question, marks))

    # ---------------------------------------------------------- bảng câu hỏi
    # Khối "phức" theo nghĩa dáng: câu hỏi đánh số, mỗi câu trả lời một KIỂU
    # khác nhau -- dòng kẻ để viết tay, cặp Có/Không, hoặc một lưới ô tích --
    # và xen kẽ không theo quy luật nào. Đó đúng là thứ một tờ khai bảo hiểm
    # hay bệnh án trông như, và là dáng cả hai bộ sinh chưa có.
    questions = []
    if design.has('questions'):
        want = (rows_wanted if design.flow == 'questions'
                else rng.randint(6, 11))
        questions = questions_of(design.seed, design, want)

    # ------------------------------------------- khối không phải bảng, mới
    # Sáu nhãn bố cục chưa từng xuất hiện trong bộ này, mà giấy tờ Việt Nam
    # thì đầy: căn cứ pháp lý, điều khoản đánh số, công thức tính, sơ đồ kèm
    # chú thích, ghi chú có dấu sao, mục lục. Chúng cũng là thứ kéo tỉ lệ
    # DIỆN TÍCH của bảng xuống -- đo được 81% trước khi có chúng.
    legal_basis = []
    if design.has('legal_basis'):
        legal_basis = rng.sample(list(LEGAL_BASIS), rng.randint(2, 5))
    clauses = []
    if design.has('clauses'):
        # Là khối CHẢY thì số điều do `paginate.py` đặt, qua `rows_wanted` --
        # cùng đường mà số dòng bảng đi. Không phải khối chảy thì nó chỉ là
        # một khối chữ giữa trang, ba đến bảy điều như trước.
        want = (rows_wanted if design.flow == 'clauses'
                else rng.randint(3, 7))
        clauses = clauses_of(design.seed, design, want)
    # Theo `profile`; ngành nào không khai thì lùi về công thức hoá đơn --
    # nó là loại công thức chung nhất trên giấy tờ có tiền.
    formula = ''
    if design.has('formula'):
        formula = rng.choice(FORMULAS.get(design.archetype.profile,
                                          FORMULAS['invoice']))
    # `figure_caption`, KHÔNG phải `caption`: dòng ~836 dưới kia đã dùng tên
    # `caption` cho tiêu đề BẢNG, và đặt trùng tên thì câu chú của sơ đồ bị
    # ghi đè lặng lẽ -- khối `figure` vẽ ra rỗng mà không báo gì.
    figure_caption = rng.choice(CAPTIONS) if design.has('figure') else ''
    footnotes = []
    if design.has('footnote'):
        footnotes = rng.sample(list(FOOTNOTES), rng.randint(1, 2))
    toc = []
    if design.has('toc'):
        heads = rng.sample(list(CLAUSES), rng.randint(3, 6))
        toc = [(f'{n}. {head}', str(n)) for n, (head, _) in enumerate(heads, 1)]

    signatures = []
    people = corpus.people()
    for caption in design.sign_captions:
        named = rng.random() < 0.45 and bool(people)
        signatures.append((caption, rng.choice(people) if named else ''))

    footer = ''
    if design.has('footer'):
        pool = corpus.footers(arch.profile)
        footer = rng.choice(pool) if pool else ''

    col_titles = {key: rng.choice(COLUMNS[key]['titles'])
                  for key in design.columns if key in COLUMNS}
    if design.lang_en:
        col_titles = {key: f'{col_titles[key]} / {COLUMNS[key]["en"]}'
                      for key in col_titles}

    # Tiêu đề hai tầng: chọn CHỮ cho từng nhóm cột mà `design.py` đã tìm
    # được. Dáng do design quyết định, chữ do đây -- cùng ranh giới với mọi
    # trục khác của gói này.
    col_groups: list[tuple[str, int, int]] = []
    col_supers: list[tuple[str, int, int]] = []
    if design.head_tiers > 1 and design.has('table'):
        for first, span, captions in groups_in(design.columns):
            # Tiêu đề nhóm trùng chữ với chính cột nằm dưới nó là một bảng
            # đọc lên vô nghĩa ("Khoản mục" phủ "Khoản mục"), nên loại trước
            # khi bốc chứ không sửa sau.
            under = {col_titles.get(design.columns[i], '')
                     for i in range(first, first + span)}
            free = [c for c in captions if c not in under] or list(captions)
            col_groups.append((rng.choice(free), first, span))
    if design.head_tiers > 2 and col_groups:
        found = super_in(design.columns)
        if found:
            col_supers = [(rng.choice(COL_SUPERS), found[0], found[1])]

    row_group_size = 0
    row_group_names: list[str] = []
    if design.row_groups != 'khong' and design.has('table'):
        pool = ROW_GROUP_NAMES.get(arch.profile) or ROW_GROUP_NAMES['invoice']
        row_group_names = list(pool)
        rng.shuffle(row_group_names)
        row_group_size = rng.randint(4, 9)

    caption = ''
    if design.table_caption and design.has('table'):
        caption = rng.choice(('CHI TIẾT HÀNG HOÁ, DỊCH VỤ', 'DANH MỤC CHI TIẾT',
                              'BẢNG KÊ CHI TIẾT', 'NỘI DUNG CHI TIẾT',
                              'CÁC KHOẢN MỤC'))

    built = Doc(
        design=design, org_name=org, org_branch=branch,
        org_address=address(rng), org_phone=phone(rng), org_tax=tax_code(rng),
        org_website=rng.choice(('', '', f'www.{_digits(rng, 4)}.vn',
                                'www.congty.com.vn', 'https://dichvu.vn')),
        parent_org=parent, title=title, subtitle=subtitle,
        doc_no=doc_no, doc_serial=serial, doc_form=form,
        issued_place=rng.choice(CITIES), issued_date=doc_date,
        fields=fields, rows=rows, col_titles=col_titles,
        totals=totals, grand_label=grand_label, grand=grand,
        grand_amount=grand_amount, words_label=words_label, words=words,
        summary=summary, notes=notes, checks=checks, questions=questions,
        legal_basis=legal_basis, clauses=clauses, formula=formula,
        caption=figure_caption, footnotes=footnotes, toc=toc,
        signatures=signatures,
        footer=footer, table_caption=caption, seed=design.seed, unit_pool=units,
        col_groups=col_groups, row_group_size=row_group_size,
        row_group_names=row_group_names, col_supers=col_supers,
    )
    _regroup(built)
    return built


def refill(doc: Doc, rng: random.Random, rows_wanted: int) -> Doc:
    """Cùng tờ giấy ấy, chỉ đổi SỐ DÒNG bảng hàng -- và tính lại mọi con số
    phụ thuộc vào nó.

    `paginate.py` gọi hàm này khi phép đo trong trình duyệt nói tờ giấy chưa
    đầy tới 80%. Sinh lại cả `Doc` từ đầu thì mất đúng tờ giấy đang đo (tên
    công ty, số hiệu, ngày tháng đều đổi theo), nên nó chỉ được đổi phần
    duy nhất quyết định chiều cao."""
    flow = doc.design.flow
    if flow == 'clauses':
        doc.clauses = clauses_of(doc.seed, doc.design, max(rows_wanted, 1))
        return doc
    if flow == 'questions':
        doc.questions = questions_of(doc.seed, doc.design, max(rows_wanted, 1))
        return doc
    if flow != 'table' or not doc.design.has('table'):
        return doc
    rows, total, _units = _rows(rng, doc.design, max(rows_wanted, 1),
                                doc.issued_date)
    doc.rows = rows
    _regroup(doc)
    if doc.design.has('totals') and doc.design.archetype.totals == 'money':
        # Thuế suất đọc lại từ chính dòng tổng đã in, không rút lại: rút lại
        # là đổi một con số mà tờ giấy đang đo đã hiện.
        rate = 0
        for label, _value in doc.totals:
            if '%' in label:
                try:
                    rate = int(label.split('(')[-1].rstrip('%)').strip())
                except ValueError:
                    rate = 0
        vat = total * rate // 100
        doc.grand_amount = total + vat
        rebuilt = []
        for label, _value in doc.totals:
            if '%' in label:
                rebuilt.append((label, money(vat, suffix='')))
            elif 'thuế' in label.lower():
                rebuilt.append((label, 'Không chịu thuế'))
            else:
                rebuilt.append((label, money(total, suffix='')))
        doc.totals = rebuilt
        suffix = ' đ' if doc.grand.endswith(' đ') else ''
        doc.grand = money(doc.grand_amount, suffix=suffix)
        if doc.words:
            doc.words = words_vi(doc.grand_amount).capitalize() + ' đồng chẵn./.'
        if doc.summary:
            doc.summary = [
                ('Cộng tiền hàng chưa thuế', money(total, suffix='')),
                ('Thuế suất GTGT', f'{rate}%'),
                ('Tiền thuế GTGT', money(vat, suffix='')),
                ('Tổng tiền thanh toán', money(doc.grand_amount, suffix='')),
            ]
    elif doc.design.has('totals'):
        head = doc.grand.split(' ', 1)
        tail = head[1] if len(head) > 1 else 'dòng'
        doc.grand = f'{len(rows)} {tail}'
    return doc
