"""Nghĩa tiếng Anh của từng trường KIE, viết sẵn cho bộ chứng từ của gói này.

`pipeline/kie.py::describe` tra bốn nguồn, tốt nhất trước: file mà biến môi
trường `VLM_KIE_DESCRIPTIONS` trỏ tới, rồi `rulebase/kie_glossary.py`, rồi
chính chữ in trên giấy, rồi nhãn lớp. File này là nguồn thứ nhất.

Khoá của file là `{layout: {field: mô tả}}`, và `field` là `kie.slug()` của
CHÍNH CHỮ IN trên giấy -- "Họ và tên:" thành `ho_va_ten`. Nên bảng dưới đây
sinh ra từ chính danh sách nhãn mà `design.py` in ra, không phải một danh
sách thứ hai chép tay: thêm một cách viết nhãn ở `design.py` là có mô tả cho
nó ở đây, không phải sửa hai chỗ.

Một trang in "Địa chỉ:" hai lần (bên bán và bên mua) thì `pair_fields` đặt
tên trường thứ hai là `dia_chi_2`, nên mỗi khoá được viết kèm các hậu tố
`_2.._6`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.kie import slug  # noqa: E402
from synthgen.design import ARCHETYPES  # noqa: E402

# Nhãn không đi kèm `FieldDef` nào -- chữ in sẵn trong khối tổng, khối tiêu
# đề, khối tiền bằng chữ. Chúng không có `describe` để lấy, nên viết ở đây.
FIXED: dict[str, str] = {
    'Địa chỉ': 'Registered address of the organisation that issued this document.',
    'Điện thoại': 'Contact telephone number printed in the letterhead.',
    'Mã số thuế': 'Tax identification number of the organisation.',
    'Số': 'Serial number this document was issued under.',
    'Ký hiệu': 'Invoice symbol: the letter-and-digit code identifying the issued form.',
    'Mẫu số': 'Form template code this document was printed from.',
    'Cộng tiền hàng': 'Sum of the line amounts before tax and discount.',
    'Tổng tiền hàng': 'Sum of the line amounts before tax and discount.',
    'Cộng thành tiền': 'Sum of the line amounts before tax and discount.',
    'Chiết khấu thương mại': 'Trade discount deducted from the goods total.',
    'Giảm giá': 'Discount deducted from the goods total.',
    'Thuế GTGT': 'Value-added tax charged on the net amount.',
    'TỔNG CỘNG THANH TOÁN': 'Final amount payable, tax included.',
    'Tổng cộng tiền thanh toán': 'Final amount payable, tax included.',
    'TỔNG TIỀN THANH TOÁN': 'Final amount payable, tax included.',
    'Cộng tiền thanh toán': 'Final amount payable, tax included.',
    'Tổng cộng': 'Total of the rows listed above.',
    'Cộng': 'Total of the rows listed above.',
    'TỔNG SỐ': 'Total of the rows listed above.',
    'Số tiền bằng chữ': 'The payable amount spelled out in Vietnamese words.',
    'Bằng chữ': 'The payable amount spelled out in Vietnamese words.',
    'Số tiền viết bằng chữ': 'The payable amount spelled out in Vietnamese words.',
    'Cộng tiền hàng chưa thuế': 'Net goods total before value-added tax.',
    'Thuế suất GTGT': 'Value-added tax rate applied to the net amount.',
    'Tiền thuế GTGT': 'Value-added tax amount charged.',
    'Tổng tiền thanh toán': 'Final amount payable, tax included.',
}
# Câu hỏi có ô tích: mô tả nói CÂU HỎI là gì, còn câu trả lời là ô đã tích.
CHECKS: dict[str, str] = {
    'Quý khách đánh giá thái độ phục vụ': "Customer's rating of the service attitude; the ticked box is the answer.",
    'Thời gian xử lý hồ sơ': 'How quickly the paperwork was processed; the ticked box is the answer.',
    'Đã nhận đủ hồ sơ kèm theo': 'Whether the accompanying documents were received in full.',
    'Đề nghị cấp lại giấy tờ': 'Whether the applicant is asking for the document to be re-issued.',
    'Hình thức nhận kết quả': 'How the applicant wants to receive the result: in person or by post.',
    'Đã đối chiếu bản chính': 'Whether the copy was checked against the original.',
    'Quý khách có muốn nhận thông báo qua SMS': 'Whether the customer wants notifications by text message.',
    'Mức độ đáp ứng yêu cầu công việc': 'How well the work requirements were met; the ticked box is the answer.',
}
SUFFIXES = ('', '_2', '_3', '_4', '_5', '_6')

# Mô tả cho MỌI chức danh ký. Đọc từ `rulebase/kie_field_glossary.json` để hai
# bộ sinh nói cùng một câu về cùng một thứ; thiếu file thì dùng câu dưới đây.
# MỘT câu, không phải hai. `rulebase/kie_field_glossary.json` tả `sign.title`
# bằng hai câu -- vai, rồi giá trị là gì -- và câu ấy dài 31 từ. Đưa nó vào
# bảng cách nói thì khung đo được (`agent/augment_descriptions.envelopes`) nới
# từ 2-21 lên 2-27 từ, tức là một câu ngoại lệ nới cổng cho MỌI câu khác, và
# cổng thôi bắt được câu dài lê thê mà model hay viết.
#
# Nghĩa giữ nguyên; chỉ bỏ nửa sau, vì nửa ấy nói `value` là gì mà `value` thì
# đã nằm ngay cạnh trong chính file json.
SIGN = ("The role of the person signing on this line, printed above the rule.")

# MÔ TẢ THEO VAI. Một câu chung cho mọi chức danh làm hai trường khác nhau trên
# cùng một tờ mang cùng một mô tả -- `nguoi_khai` và `chuyen_vien_tu_van` đọc
# lên y hệt, và người huấn luyện nhìn hai cái hộp mà không biết hộp nào là hộp
# nào. Đo được: 84% số trang có ít nhất hai trường cùng mô tả.
#
# Tra theo tên đã bỏ dấu và hạ chữ thường, nên "KHÁCH HÀNG" và "Khách hàng" là
# một. Vai nào không có trong bảng thì dựng câu từ chính vai ấy -- vẫn phân
# biệt được, và 95 chức danh của kho thì phần đuôi là những vai hiếm.
ROLES: dict[str, str] = {
    'thu truong don vi': 'Head of the issuing unit, who signs to approve the document.',
    'ke toan truong': 'Chief accountant, who signs off the figures on this document.',
    'giam doc': 'Director of the organisation, signing as its legal representative.',
    'nguoi nop tien': 'Person handing over the money recorded on this receipt.',
    'nguoi thu tien': 'Cashier who took in the money recorded on this receipt.',
    'nguoi lap bang': 'Clerk who drew up this table and signs for its contents.',
    'nguoi lap phieu': 'Clerk who wrote this slip out.',
    'nguoi lap': 'Person who prepared this document.',
    'phu trach bo phan': 'Supervisor of the department the document came from.',
    'khach hang': 'Customer named on this document, signing to acknowledge it.',
    'nguoi de nghi': 'Person making the request this document records.',
    'nguoi nhan tien': 'Person receiving the money paid out here.',
    'thu kho': 'Storekeeper responsible for the goods moving in or out.',
    'thu quy': 'Treasurer holding the cash this document moves.',
    'noi nhan': 'Where copies of this document are sent.',
    'xac nhan cua don vi': "The unit's own confirmation of what is written above.",
    'nguoi duoc bao hiem': 'The insured person this policy or claim is about.',
    'doanh nghiep bao hiem': 'The insurance company party to this document.',
    'bac si dieu tri': 'Doctor who treated the patient and signs the record.',
    'nguoi benh': 'Patient the medical record is about.',
    'nguoi giao hang': 'Person handing the goods over.',
    'nguoi nhan hang': 'Person taking delivery of the goods.',
    'nguoi mua hang': 'Buyer named on this invoice.',
    'nguoi ban hang': 'Seller named on this invoice.',
    'nguoi khai': 'Person who filled in this declaration.',
    'chuyen vien tu van': 'Consultant who advised on this form and witnesses it.',
    'nguoi lam chung': 'Witness who signs to confirm what the document records.',
    'nguoi uy quyen': 'Person granting the authority this letter delegates.',
    'nguoi duoc uy quyen': 'Person receiving the delegated authority.',
    'nguoi cham cong': 'Timekeeper who recorded the attendance in this table.',
    'phong nhan su': 'Human-resources department, signing off the personnel figures.',
    'nguoi kiem tra': 'Person who checked the contents of this document.',
    'nguoi duyet': 'Person who approved the document.',
    'don vi tiep nhan': 'The unit receiving this document.',
    'can bo tiep nhan': 'Officer who received the paperwork at the counter.',
    'nguoi nop': 'Person submitting the paperwork.',
    'nguoi dang ky': 'Person making the registration this form records.',
    'thu truong co quan': 'Head of the issuing authority.',
    'ky ten dong dau': 'Signature and seal of the issuing organisation.',
    'dai dien ben a': 'Representative signing for Party A.',
    'dai dien ben b': 'Representative signing for Party B.',
    'ben giao': 'The handing-over party.',
    'ben nhan': 'The receiving party.',
    'le tan': 'Receptionist who handled this stay.',
    'nhan vien': 'Member of staff who dealt with this document.',
    'quan ly': 'Manager signing off this document.',
    'thu ngan': 'Cashier who rang up this sale.',
    'ky thuat vien': 'Technician who carried out the work recorded here.',
}


def role_description(caption: str) -> str:
    """Mô tả cho MỘT chức danh ký. Có trong bảng thì lấy; không thì dựng."""
    from pipeline.kie import slug as _slug  # noqa: PLC0415

    key = _slug(caption).replace('_', ' ').strip()
    found = ROLES.get(key)
    if found:
        return found
    # Vai hiếm: vẫn nói CÁI VAI, nên hai trường khác vai vẫn khác mô tả.
    name = ' '.join(str(caption or '').split()).rstrip(':').strip()
    return f'The person signing as "{name}" on this document.' if name else SIGN

# Tiêu đề và nội dung điều khoản. Không có hai câu này thì `pipeline/kie.py`
# lấy CHÍNH tiêu đề điều làm mô tả ("2. Quyền và nghĩa vụ của bên B"), tức là
# một mô tả chép lại đúng chữ đã in.
CLAUSE_HEAD = "Heading of one numbered clause in the agreement."
CLAUSE_BODY = "Body of one numbered clause in the agreement."

def table() -> dict[str, str]:
    """`{field: mô tả}` cho mọi nhãn gói này có thể in ra."""
    out: dict[str, str] = {}

    def put(caption: str, description: str) -> None:
        if not caption or not description:
            return
        base = slug(caption)
        for suffix in SUFFIXES:
            out.setdefault(base + suffix, description)

    for archetype in ARCHETYPES:
        for fdef in archetype.field_pool:
            for label in fdef.labels:
                put(label, fdef.describe)
        # CHỨC DANH KÝ. Không có vòng này thì mọi caption chữ ký rơi về bước
        # cuối cùng của `pipeline/kie.py::describe`: lấy CHÍNH CHỮ IN làm mô
        # tả. Đo trên một bộ thật, `nguoi_nop` có `description: "Người nộp"` --
        # một mô tả không nói gì mà chữ in chưa nói, và một mô hình học trên nó
        # học cách chép lại nhãn.
        #
        # Từ vựng caption là MỞ: mỗi phôi tự đặt chức danh của nó, và một phôi
        # mới khai bằng file còn đặt ra những chức danh chưa ai thấy. Nên mô tả
        # ở đây nói cái VAI, không nói cái tên -- tên đã nằm trong `key_text`.
        for signs in archetype.sign_sets:
            for caption in signs:
                put(caption, role_description(caption))

    # Tiêu đề điều khoản. Đọc từ `content.CLAUSES` -- kho điều khoản THẬT mà
    # `_clauses` bốc ra -- chứ không từ phôi: điều khoản là nội dung, không
    # phải một trường của phôi. Vòng trước tôi viết `archetype.clauses`, mà
    # `Archetype` không có trường ấy, nên `hasattr` luôn False và cả vòng là mã
    # chết: tiêu đề điều vẫn rơi về lấy chính chữ in làm mô tả.
    from synthgen.content import CLAUSES  # noqa: PLC0415 -- tránh vòng import

    for head, _body in CLAUSES:
        put(head, CLAUSE_HEAD)

    for caption, description in FIXED.items():
        put(caption, description)
    for caption, description in CHECKS.items():
        put(caption, description)
    return out


def write(path: Path) -> int:
    """Viết file `VLM_KIE_DESCRIPTIONS`. Cùng một bảng cho mọi loại chứng từ:
    "Địa chỉ" trên một hoá đơn và trên một tờ khai nghĩa như nhau, và một bảng
    riêng cho từng loại chỉ là cùng một câu chép ba mươi lần."""
    shared = table()
    payload = {archetype.id: shared for archetype in ARCHETYPES}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n',
                    encoding='utf-8')
    return len(shared)


if __name__ == '__main__':
    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'kie_descriptions.json')
    print(f'{write(target)} trường -> {target}')
