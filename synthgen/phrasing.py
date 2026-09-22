"""Mô tả trường KIE, nhiều cách nói, hai thứ tiếng.

Trước file này mỗi trường có ĐÚNG MỘT câu mô tả, và câu ấy lặp y hệt trên cả
hai mươi nghìn trang: "Name of the goods or service listed on this line."
xuất hiện 7 920 lần trong 250 file. Một mô hình học trên bộ ấy học thuộc câu
chứ không học nghĩa -- đưa cho nó một câu khác cùng nghĩa là nó lạ.

Nên mỗi mô tả ở đây có bốn cách nói: hai tiếng Anh, hai tiếng Việt. Chúng
KHÔNG phải bốn bản dịch của nhau -- chúng là bốn cách một người viết tài liệu
thật sẽ diễn đạt cùng một trường, khác nhau cả về từ lẫn về cấu trúc câu.

Chọn cách nào là hàm THUẦN của `(seed, trường, câu gốc)`, băm bằng `crc32`:

* cùng một seed thì ra cùng một câu -- lượt chạy vẫn dựng lại được;
* hai trường khác nhau trên cùng tờ giấy ra hai câu khác nhau, nên một trang
  không đọc lên như một cái máy đọc thuộc lòng;
* `hash()` của Python KHÔNG dùng được ở đây: nó có muối riêng cho mỗi tiến
  trình, nên cùng seed chạy hai lần ra hai kết quả.

Khoá là CHÍNH CÂU GỐC. Nhờ thế không phải nối thêm đường ống nào: cặp KIE nào
mang một câu có trong bảng thì được đổi, câu lạ thì giữ nguyên -- và một mô tả
mới thêm vào `design.py` mà quên khai ở đây thì mất đa dạng chứ không mất mô
tả.
"""

from __future__ import annotations

import json
import zlib
from functools import lru_cache
from pathlib import Path

POOL: dict[str, tuple[str, ...]] = {
    # ------------------------------------------------- bên bán, bên mua
    "Legal name of the selling organisation issuing this document.": (
        "Legal name of the selling organisation issuing this document.",
        "Registered company name of the seller that issued this document.",
        "Tên pháp nhân của đơn vị bán đã phát hành chứng từ này.",
        "Tên đăng ký kinh doanh của bên bán ghi trên tờ giấy này.",
    ),
    "Tax identification number of the seller.": (
        "Tax identification number of the seller.",
        "The seller's tax code as registered with the tax authority.",
        "Mã số thuế của bên bán.",
        "Mã số thuế do cơ quan thuế cấp cho đơn vị bán.",
    ),
    "Registered address of the seller.": (
        "Registered address of the seller.",
        "Business address the seller is registered at.",
        "Địa chỉ đăng ký kinh doanh của bên bán.",
        "Trụ sở của đơn vị bán ghi trên chứng từ.",
    ),
    "Contact telephone of the seller.": (
        "Contact telephone of the seller.",
        "Phone number to reach the selling organisation.",
        "Số điện thoại liên hệ của bên bán.",
        "Điện thoại của đơn vị bán in trên chứng từ.",
    ),
    "Bank account the seller is paid into.": (
        "Bank account the seller is paid into.",
        "Account number and bank the payment should be transferred to.",
        "Số tài khoản ngân hàng nhận tiền của bên bán.",
        "Tài khoản và ngân hàng để chuyển khoản thanh toán.",
    ),
    "Full name of the individual buyer.": (
        "Full name of the individual buyer.",
        "Name of the person buying, written in full.",
        "Họ và tên người mua hàng.",
        "Tên đầy đủ của cá nhân đứng tên mua.",
    ),
    "Legal name of the purchasing organisation.": (
        "Legal name of the purchasing organisation.",
        "Registered name of the company on the buying side.",
        "Tên đơn vị mua hàng theo đăng ký kinh doanh.",
        "Tên pháp nhân của bên mua.",
    ),
    "Tax identification number of the buyer.": (
        "Tax identification number of the buyer.",
        "Tax code of the party receiving the goods or service.",
        "Mã số thuế của bên mua.",
        "Mã số thuế của đơn vị nhận hàng hoá, dịch vụ.",
    ),
    "Address of the buyer.": (
        "Address of the buyer.",
        "Where the buying party is located.",
        "Địa chỉ của bên mua.",
        "Nơi đặt trụ sở hoặc nơi ở của người mua.",
    ),
    "How the amount was settled: cash, transfer, card or wallet.": (
        "How the amount was settled: cash, transfer, card or wallet.",
        "Payment method used, such as cash, bank transfer or card.",
        "Hình thức thanh toán: tiền mặt, chuyển khoản, thẻ hay ví điện tử.",
        "Cách trả tiền được ghi trên chứng từ.",
    ),
    # ------------------------------------------------------ người trên giấy
    "Registered or current residential address of the person named.": (
        "Registered or current residential address of the person named.",
        "Where the named individual lives or is registered as living.",
        "Địa chỉ thường trú hoặc chỗ ở hiện tại của người có tên.",
        "Nơi cư trú của cá nhân được nêu trong chứng từ.",
    ),
    "Contact telephone of the person named.": (
        "Contact telephone of the person named.",
        "Phone number of the individual this document is about.",
        "Số điện thoại liên hệ của người có tên.",
        "Điện thoại của cá nhân được nêu trên giấy.",
    ),
    "Reference number of the contract.": (
        "Reference number of the contract.",
        "The contract's own identifying number.",
        "Số hiệu của hợp đồng.",
        "Số hợp đồng dùng để tra cứu.",
    ),
    "Department or unit the person belongs to.": (
        "Department or unit the person belongs to.",
        "Which team, division or office the person works in.",
        "Phòng ban hoặc đơn vị công tác của người có tên.",
        "Bộ phận mà cá nhân này trực thuộc.",
    ),
    "Job title of the person named.": (
        "Job title of the person named.",
        "The position this person holds in the organisation.",
        "Chức danh của người có tên.",
        "Vị trí công tác của cá nhân được nêu.",
    ),
    "First party to the contract.": (
        "First party to the contract.",
        "Party A, the side named first in the agreement.",
        "Bên A của hợp đồng.",
        "Bên thứ nhất đứng tên trong hợp đồng.",
    ),
    "Second party to the contract.": (
        "Second party to the contract.",
        "Party B, the side named second in the agreement.",
        "Bên B của hợp đồng.",
        "Bên thứ hai đứng tên trong hợp đồng.",
    ),
    "Person signing on behalf of the party.": (
        "Person signing on behalf of the party.",
        "Authorised representative who puts their signature to this.",
        "Người đại diện ký thay cho bên tham gia.",
        "Cá nhân được uỷ quyền ký vào chứng từ này.",
    ),
    "Total value of the contract.": (
        "Total value of the contract.",
        "Full contract amount agreed by both parties.",
        "Tổng giá trị của hợp đồng.",
        "Số tiền toàn bộ hợp đồng mà hai bên thoả thuận.",
    ),
    "Full name of the person this document concerns.": (
        "Full name of the person this document concerns.",
        "Name of the individual the paperwork is about.",
        "Họ và tên của người mà chứng từ này nói tới.",
        "Tên đầy đủ của cá nhân liên quan trong hồ sơ.",
    ),
    "Date of birth of the person named.": (
        "Date of birth of the person named.",
        "The day, month and year this person was born.",
        "Ngày tháng năm sinh của người có tên.",
        "Ngày sinh của cá nhân được nêu.",
    ),
    "Sex of the person named.": (
        "Sex of the person named.",
        "Whether the individual is recorded as male or female.",
        "Giới tính của người có tên.",
        "Giới tính ghi trong hồ sơ của cá nhân này.",
    ),
    "National identity card or passport number of the person named.": (
        "National identity card or passport number of the person named.",
        "Number on the person's ID card, citizen card or passport.",
        "Số căn cước công dân hoặc hộ chiếu của người có tên.",
        "Số giấy tờ tuỳ thân của cá nhân được nêu.",
    ),
    "Date the identity document was issued.": (
        "Date the identity document was issued.",
        "When the ID card or passport was granted.",
        "Ngày cấp giấy tờ tuỳ thân.",
        "Thời điểm căn cước hoặc hộ chiếu được cấp.",
    ),
    "Authority that issued the identity document.": (
        "Authority that issued the identity document.",
        "Which office granted the ID card or passport.",
        "Nơi cấp giấy tờ tuỳ thân.",
        "Cơ quan đã cấp căn cước hoặc hộ chiếu.",
    ),
    # ---------------------------------------------------------------- y tế
    "Full name of the patient.": (
        "Full name of the patient.",
        "Name of the person receiving treatment.",
        "Họ và tên bệnh nhân.",
        "Tên đầy đủ của người bệnh.",
    ),
    "Hospital record number for this episode of care.": (
        "Hospital record number for this episode of care.",
        "Medical file number opened for this admission.",
        "Số bệnh án của đợt điều trị này.",
        "Số hồ sơ bệnh viện mở cho lần khám chữa này.",
    ),
    "Vietnamese health-insurance card number of the patient.": (
        "Vietnamese health-insurance card number of the patient.",
        "The patient's BHYT card number.",
        "Số thẻ bảo hiểm y tế của bệnh nhân.",
        "Mã thẻ BHYT ghi trong hồ sơ người bệnh.",
    ),
    "Hospital ward or department the patient was treated in.": (
        "Hospital ward or department the patient was treated in.",
        "Clinical unit that looked after the patient.",
        "Khoa điều trị của bệnh nhân.",
        "Khoa phòng đã tiếp nhận và chữa cho người bệnh.",
    ),
    "Date and time the patient was admitted.": (
        "Date and time the patient was admitted.",
        "When the patient was taken into hospital.",
        "Ngày giờ bệnh nhân nhập viện.",
        "Thời điểm người bệnh được tiếp nhận vào viện.",
    ),
    "Date and time the patient was discharged.": (
        "Date and time the patient was discharged.",
        "When the patient left hospital care.",
        "Ngày giờ bệnh nhân ra viện.",
        "Thời điểm người bệnh kết thúc điều trị và xuất viện.",
    ),
    "Clinical diagnosis recorded for this episode.": (
        "Clinical diagnosis recorded for this episode.",
        "What the doctors concluded the illness was.",
        "Chẩn đoán bệnh của đợt điều trị này.",
        "Kết luận chẩn đoán mà bác sĩ ghi trong hồ sơ.",
    ),
    "Treatment given to the patient.": (
        "Treatment given to the patient.",
        "Course of care the patient actually received.",
        "Phương pháp điều trị đã áp dụng cho bệnh nhân.",
        "Cách xử trí mà người bệnh đã được điều trị.",
    ),
    # --------------------------------------------------------------- bảo hiểm
    "Insurance policy or certificate number.": (
        "Insurance policy or certificate number.",
        "Number identifying this insurance contract.",
        "Số hợp đồng hoặc số giấy chứng nhận bảo hiểm.",
        "Số hiệu của đơn bảo hiểm này.",
    ),
    "Person covered by this policy.": (
        "Person covered by this policy.",
        "The insured party the cover applies to.",
        "Người được bảo hiểm theo hợp đồng này.",
        "Cá nhân nằm trong phạm vi được bảo hiểm.",
    ),
    "Party that bought the policy.": (
        "Party that bought the policy.",
        "Whoever pays for and holds this insurance.",
        "Bên mua bảo hiểm.",
        "Người đứng tên và trả phí cho hợp đồng bảo hiểm.",
    ),
    "First day the cover is in force.": (
        "First day the cover is in force.",
        "When the insurance starts protecting the insured.",
        "Ngày bắt đầu có hiệu lực bảo hiểm.",
        "Thời điểm hợp đồng bảo hiểm bắt đầu có hiệu lực.",
    ),
    "Last day the cover is in force.": (
        "Last day the cover is in force.",
        "When the insurance protection ends.",
        "Ngày kết thúc hiệu lực bảo hiểm.",
        "Thời điểm hợp đồng bảo hiểm hết hiệu lực.",
    ),
    "Maximum amount the insurer will pay under this policy.": (
        "Maximum amount the insurer will pay under this policy.",
        "Ceiling on what can be claimed from this cover.",
        "Số tiền bảo hiểm tối đa theo hợp đồng này.",
        "Mức chi trả cao nhất mà bên bảo hiểm phải trả.",
    ),
    "Premium payable for the cover.": (
        "Premium payable for the cover.",
        "What the policyholder pays to keep the cover.",
        "Phí bảo hiểm phải đóng.",
        "Khoản tiền người mua phải trả để duy trì bảo hiểm.",
    ),
    "What the policy covers: the property, vehicle or risk.": (
        "What the policy covers: the property, vehicle or risk.",
        "Subject of the insurance -- the asset or risk protected.",
        "Đối tượng được bảo hiểm: tài sản, phương tiện hay rủi ro.",
        "Thứ mà hợp đồng bảo hiểm này bảo vệ.",
    ),
    # ------------------------------------------------------------- điện nước
    "Utility customer account code.": (
        "Utility customer account code.",
        "Customer number the utility bills under.",
        "Mã khách hàng của đơn vị cung cấp dịch vụ.",
        "Số danh bộ khách hàng dùng để ra hoá đơn.",
    ),
    "Serial number of the meter that was read.": (
        "Serial number of the meter that was read.",
        "Identifying number stamped on the meter.",
        "Số công tơ đã được ghi chỉ số.",
        "Số hiệu của đồng hồ đo ghi trên hoá đơn.",
    ),
    "Billing period this invoice covers.": (
        "Billing period this invoice covers.",
        "The span of time being charged for.",
        "Kỳ hoá đơn mà chứng từ này tính tiền.",
        "Khoảng thời gian được tính cước trên hoá đơn.",
    ),
    "Meter reading at the start of the period.": (
        "Meter reading at the start of the period.",
        "Number showing on the meter when the period opened.",
        "Chỉ số công tơ đầu kỳ.",
        "Số đọc trên đồng hồ tại thời điểm bắt đầu kỳ.",
    ),
    "Meter reading at the end of the period.": (
        "Meter reading at the end of the period.",
        "Number showing on the meter when the period closed.",
        "Chỉ số công tơ cuối kỳ.",
        "Số đọc trên đồng hồ tại thời điểm chốt kỳ.",
    ),
    "Units consumed during the period.": (
        "Units consumed during the period.",
        "How much was used, as the difference between the two readings.",
        "Lượng tiêu thụ trong kỳ.",
        "Sản lượng đã dùng, bằng hiệu hai chỉ số công tơ.",
    ),
    # ---------------------------------------------------------------- lưu trú
    "Room number or room type occupied.": (
        "Room number or room type occupied.",
        "Which room the guest stayed in, or its class.",
        "Số phòng hoặc loại phòng đã ở.",
        "Phòng mà khách lưu trú trong kỳ nghỉ này.",
    ),
    "Name of the guest the folio belongs to.": (
        "Name of the guest the folio belongs to.",
        "Who the hotel bill was opened for.",
        "Tên khách đứng tên phiếu này.",
        "Họ tên của khách lưu trú trên hoá đơn.",
    ),
    "Date and time the guest checked in.": (
        "Date and time the guest checked in.",
        "When the stay began.",
        "Ngày giờ khách nhận phòng.",
        "Thời điểm bắt đầu lưu trú.",
    ),
    "Date and time the guest checked out.": (
        "Date and time the guest checked out.",
        "When the stay ended.",
        "Ngày giờ khách trả phòng.",
        "Thời điểm kết thúc lưu trú.",
    ),
    "Number of nights stayed.": (
        "Number of nights stayed.",
        "How many nights the guest was booked in for.",
        "Số đêm lưu trú.",
        "Tổng số đêm khách ở lại.",
    ),
    "How long the contract runs for.": (
        "How long the contract runs for.",
        "Duration the agreement stays in force.",
        "Thời hạn của hợp đồng.",
        "Khoảng thời gian hợp đồng còn hiệu lực.",
    ),
    # ------------------------------------------------------------ cột bảng
    "Row ordinal within the item table, counted across the whole document.": (
        "Row ordinal within the item table, counted across the whole document.",
        "Line number of this row, running on across every page.",
        "Số thứ tự của dòng trong bảng, đếm liên tục cả tài liệu.",
        "Thứ tự dòng hàng, không đếm lại từ đầu ở tờ sau.",
    ),
    "Name of the goods or service listed on this line.": (
        "Name of the goods or service listed on this line.",
        "What is being sold or supplied on this row.",
        "Tên hàng hoá hoặc dịch vụ ghi ở dòng này.",
        "Nội dung khoản mục của dòng hàng.",
    ),
    "Unit of measure for the quantity on this line.": (
        "Unit of measure for the quantity on this line.",
        "How the quantity is counted: piece, box, kilo, litre.",
        "Đơn vị tính của số lượng ở dòng này.",
        "Cách đo khoản mục: cái, hộp, kg, lít.",
    ),
    "Quantity of the item on this line.": (
        "Quantity of the item on this line.",
        "How many units of this item were supplied.",
        "Số lượng của mặt hàng ở dòng này.",
        "Khối lượng khoản mục được cung cấp trên dòng.",
    ),
    "Price of one unit of this item, before tax.": (
        "Price of one unit of this item, before tax.",
        "Unit price charged, excluding value-added tax.",
        "Đơn giá một đơn vị hàng, chưa có thuế.",
        "Giá của mỗi đơn vị tính, trước thuế GTGT.",
    ),
    "Line amount: quantity multiplied by unit price, before tax.": (
        "Line amount: quantity multiplied by unit price, before tax.",
        "Row total, being quantity times unit price without tax.",
        "Thành tiền của dòng: số lượng nhân đơn giá, chưa thuế.",
        "Giá trị dòng hàng trước thuế, bằng lượng nhân giá.",
    ),
    "Value-added tax rate applied to this line; KCT means not subject to tax.": (
        "Value-added tax rate applied to this line; KCT means not subject to tax.",
        "VAT percentage on this row; KCT marks it as exempt.",
        "Thuế suất GTGT của dòng này; KCT nghĩa là không chịu thuế.",
        "Mức thuế giá trị gia tăng áp cho dòng hàng, KCT là miễn.",
    ),
    "Value-added tax charged on this line.": (
        "Value-added tax charged on this line.",
        "Amount of VAT falling on this row.",
        "Tiền thuế GTGT của dòng này.",
        "Số thuế giá trị gia tăng tính trên dòng hàng.",
    ),
    "Free-text remark about this line.": (
        "Free-text remark about this line.",
        "Any note the issuer added against this row.",
        "Ghi chú thêm cho dòng này.",
        "Lời chú của người lập chứng từ ở dòng hàng.",
    ),
    "Item or material code identifying the goods on this line.": (
        "Item or material code identifying the goods on this line.",
        "Internal code for the product on this row.",
        "Mã hàng hoặc mã vật tư của dòng này.",
        "Mã số dùng để nhận diện khoản mục trên dòng.",
    ),
    "Date this line item was issued or incurred.": (
        "Date this line item was issued or incurred.",
        "When this row's transaction took place.",
        "Ngày phát sinh của dòng này.",
        "Thời điểm khoản mục ở dòng này được thực hiện.",
    ),
    "Discount deducted from this line.": (
        "Discount deducted from this line.",
        "Reduction applied to this row's amount.",
        "Khoản chiết khấu trừ vào dòng này.",
        "Số tiền giảm giá của dòng hàng.",
    ),
    "Portion of this line the patient pays out of pocket.": (
        "Portion of this line the patient pays out of pocket.",
        "Share of this row the patient settles themselves.",
        "Phần tiền người bệnh tự trả ở dòng này.",
        "Khoản đồng chi trả của bệnh nhân trên dòng hàng.",
    ),
    "Portion of this line the health-insurance fund pays.": (
        "Portion of this line the health-insurance fund pays.",
        "Share of this row covered by health insurance.",
        "Phần tiền quỹ bảo hiểm y tế chi trả ở dòng này.",
        "Khoản BHYT thanh toán cho dòng hàng.",
    ),
    # ------------------------------------------------------- letterhead, số
    "Registered address of the organisation that issued this document.": (
        "Registered address of the organisation that issued this document.",
        "Where the issuing body is officially based.",
        "Địa chỉ đăng ký của đơn vị phát hành chứng từ.",
        "Trụ sở của cơ quan đã lập tờ giấy này.",
    ),
    "Contact telephone number printed in the letterhead.": (
        "Contact telephone number printed in the letterhead.",
        "Phone number shown in the header block.",
        "Số điện thoại in ở phần tiêu đề thư.",
        "Điện thoại liên hệ ghi trên đầu chứng từ.",
    ),
    "Tax identification number of the organisation.": (
        "Tax identification number of the organisation.",
        "Tax code the issuing body is registered under.",
        "Mã số thuế của đơn vị.",
        "Mã số thuế đăng ký của tổ chức phát hành.",
    ),
    "Serial number this document was issued under.": (
        "Serial number this document was issued under.",
        "The running number the issuer gave this document.",
        "Số hiệu của chứng từ này.",
        "Số thứ tự phát hành mà đơn vị đặt cho tờ giấy.",
    ),
    "Invoice symbol: the letter-and-digit code identifying the issued form.": (
        "Invoice symbol: the letter-and-digit code identifying the issued form.",
        "Form symbol combining letters and digits for this invoice series.",
        "Ký hiệu hoá đơn: mã chữ và số của mẫu đã phát hành.",
        "Ký hiệu của sê-ri hoá đơn, gồm chữ và số.",
    ),
    "Form template code this document was printed from.": (
        "Form template code this document was printed from.",
        "Which official template this sheet follows.",
        "Mẫu số của biểu mẫu đã dùng để in tờ này.",
        "Mã mẫu biểu mà chứng từ này in theo.",
    ),
    # ---------------------------------------------------------- khối tổng
    "Sum of the line amounts before tax and discount.": (
        "Sum of the line amounts before tax and discount.",
        "Goods total, adding up every row before tax or reduction.",
        "Cộng tiền hàng, trước thuế và trước chiết khấu.",
        "Tổng thành tiền các dòng, chưa trừ giảm giá và chưa thuế.",
    ),
    "Trade discount deducted from the goods total.": (
        "Trade discount deducted from the goods total.",
        "Commercial reduction taken off the goods subtotal.",
        "Chiết khấu thương mại trừ vào tiền hàng.",
        "Khoản giảm trừ thương mại trên tổng tiền hàng.",
    ),
    "Discount deducted from the goods total.": (
        "Discount deducted from the goods total.",
        "Reduction applied to the subtotal of goods.",
        "Khoản giảm giá trừ vào tiền hàng.",
        "Số tiền được giảm trên tổng giá trị hàng hoá.",
    ),
    "Value-added tax charged on the net amount.": (
        "Value-added tax charged on the net amount.",
        "VAT computed on the total after discount.",
        "Tiền thuế GTGT tính trên số tiền sau giảm trừ.",
        "Thuế giá trị gia tăng của phần giá trị thuần.",
    ),
    "Final amount payable, tax included.": (
        "Final amount payable, tax included.",
        "Grand total the payer owes, VAT included.",
        "Tổng cộng tiền thanh toán, đã gồm thuế.",
        "Số tiền cuối cùng phải trả, bao gồm cả thuế GTGT.",
    ),
    "Total of the rows listed above.": (
        "Total of the rows listed above.",
        "Sum across every row printed above this line.",
        "Cộng của các dòng liệt kê ở trên.",
        "Tổng số các dòng phía trên dòng này.",
    ),
    "The payable amount spelled out in Vietnamese words.": (
        "The payable amount spelled out in Vietnamese words.",
        "Amount due written out in words rather than digits.",
        "Số tiền phải trả viết bằng chữ.",
        "Tổng tiền thanh toán ghi bằng chữ tiếng Việt.",
    ),
    "Net goods total before value-added tax.": (
        "Net goods total before value-added tax.",
        "Taxable base: the goods total once VAT is excluded.",
        "Cộng tiền hàng chưa có thuế GTGT.",
        "Giá trị hàng hoá làm căn cứ tính thuế.",
    ),
    "Value-added tax rate applied to the net amount.": (
        "Value-added tax rate applied to the net amount.",
        "VAT percentage charged on the taxable base.",
        "Thuế suất GTGT áp trên phần giá trị chưa thuế.",
        "Mức thuế giá trị gia tăng của tờ chứng từ.",
    ),
    "Value-added tax amount charged.": (
        "Value-added tax amount charged.",
        "Total VAT billed on this document.",
        "Tiền thuế giá trị gia tăng đã tính.",
        "Số thuế GTGT ghi trên chứng từ.",
    ),
    # --------------------------------------------------------------- ô tích
    "Customer's rating of the service attitude; the ticked box is the answer.": (
        "Customer's rating of the service attitude; the ticked box is the answer.",
        "How the customer scored the staff's manner; read the ticked box.",
        "Đánh giá của khách về thái độ phục vụ; ô được tích là câu trả lời.",
        "Mức hài lòng của khách với thái độ nhân viên, xem ô đã tích.",
    ),
    "How quickly the paperwork was processed; the ticked box is the answer.": (
        "How quickly the paperwork was processed; the ticked box is the answer.",
        "Speed of handling the file, given by the ticked option.",
        "Thời gian xử lý hồ sơ; ô được tích là câu trả lời.",
        "Nhanh hay chậm khi giải quyết hồ sơ, xem ô đã tích.",
    ),
    "Whether the accompanying documents were received in full.": (
        "Whether the accompanying documents were received in full.",
        "Confirms if every attachment was handed over.",
        "Đã nhận đủ hồ sơ kèm theo hay chưa.",
        "Xác nhận giấy tờ đính kèm có đầy đủ không.",
    ),
    "Whether the applicant is asking for the document to be re-issued.": (
        "Whether the applicant is asking for the document to be re-issued.",
        "Marks a request for a replacement copy.",
        "Người khai có đề nghị cấp lại giấy tờ hay không.",
        "Đánh dấu yêu cầu cấp lại bản mới.",
    ),
    "How the applicant wants to receive the result: in person or by post.": (
        "How the applicant wants to receive the result: in person or by post.",
        "Chosen delivery route for the outcome: collect or mail.",
        "Hình thức nhận kết quả: nhận trực tiếp hay qua bưu điện.",
        "Cách người khai muốn lấy kết quả.",
    ),
    "Whether the copy was checked against the original.": (
        "Whether the copy was checked against the original.",
        "Confirms the duplicate was compared with the master document.",
        "Đã đối chiếu bản sao với bản chính hay chưa.",
        "Xác nhận việc so bản sao với bản gốc.",
    ),
    "Whether the customer wants notifications by text message.": (
        "Whether the customer wants notifications by text message.",
        "Whether SMS alerts were opted into.",
        "Khách có muốn nhận thông báo qua tin nhắn hay không.",
        "Đăng ký nhận thông báo bằng SMS.",
    ),
    "How well the work requirements were met; the ticked box is the answer.": (
        "How well the work requirements were met; the ticked box is the answer.",
        "Assessment of how far the job met what was asked; see the ticked box.",
        "Mức độ đáp ứng yêu cầu công việc; ô được tích là câu trả lời.",
        "Đánh giá công việc có đạt yêu cầu không, xem ô đã tích.",
    ),
    # ------------------------------------------- trường không có nhãn in kèm
    "Main title of the document.": (
        "Main title of the document.",
        "The heading that names what this sheet is.",
        "Tiêu đề chính của chứng từ.",
        "Dòng tên gọi tờ giấy này là loại gì.",
    ),
    "Subtitle printed under the main title.": (
        "Subtitle printed under the main title.",
        "Secondary heading sitting below the title.",
        "Tiêu đề phụ in dưới tiêu đề chính.",
        "Dòng phụ đề nằm ngay dưới tên chứng từ.",
    ),
    "Note or condition printed on the document.": (
        "Note or condition printed on the document.",
        "A remark or term the issuer printed on the sheet.",
        "Ghi chú hoặc điều kiện in trên chứng từ.",
        "Lời lưu ý mà đơn vị phát hành in kèm.",
    ),
    "Footer line printed at the bottom of the page.": (
        "Footer line printed at the bottom of the page.",
        "The closing line running along the foot of the sheet.",
        "Dòng chân trang in ở cuối tờ giấy.",
        "Câu cuối trang nằm dưới cùng của chứng từ.",
    ),
    "Billing or reporting period this document covers.": (
        "Billing or reporting period this document covers.",
        "Span of time the sheet reports on or charges for.",
        "Kỳ hoặc giai đoạn mà chứng từ này báo cáo.",
        "Khoảng thời gian tờ giấy này tính hoặc tổng hợp.",
    ),
    "National heading printed above the title.": (
        "National heading printed above the title.",
        "The state motto block standing above the document title.",
        "Quốc hiệu in phía trên tiêu đề.",
        "Dòng tiêu ngữ quốc gia đặt trên tên chứng từ.",
    ),
    "Legal name of the organisation that issued this document.": (
        "Legal name of the organisation that issued this document.",
        "Registered name of the body that produced this sheet.",
        "Tên pháp nhân của đơn vị phát hành chứng từ.",
        "Tên đăng ký của cơ quan đã lập tờ giấy này.",
    ),
    "Branch or department of the issuing organisation.": (
        "Branch or department of the issuing organisation.",
        "Which branch or unit of the issuer produced this.",
        "Chi nhánh hoặc phòng ban của đơn vị phát hành.",
        "Bộ phận trực thuộc đã lập chứng từ.",
    ),
    "Website of the issuing organisation.": (
        "Website of the issuing organisation.",
        "Web address printed for the issuing body.",
        "Địa chỉ website của đơn vị phát hành.",
        "Trang web in trên chứng từ của tổ chức.",
    ),
    "Parent body the issuing organisation reports to.": (
        "Parent body the issuing organisation reports to.",
        "The higher authority above the issuing unit.",
        "Cơ quan chủ quản của đơn vị phát hành.",
        "Đơn vị cấp trên mà tổ chức này trực thuộc.",
    ),
    "Printed name of the person who signs at this place.": (
        "Printed name of the person who signs at this place.",
        "Typed name under the signature line.",
        "Họ tên in của người ký ở vị trí này.",
        "Tên người ký ghi rõ dưới chỗ ký.",
    ),
    "Place and date the document was signed.": (
        "Place and date the document was signed.",
        "Where and when the sheet was signed off.",
        "Nơi và ngày ký chứng từ.",
        "Địa điểm cùng thời gian lập và ký tờ giấy.",
    ),
    "Round stamp impressed on the document.": (
        "Round stamp impressed on the document.",
        "Circular seal pressed onto the sheet.",
        "Con dấu tròn đóng trên chứng từ.",
        "Dấu hình tròn in lên tờ giấy.",
    ),
    "Oval stamp impressed on the document.": (
        "Oval stamp impressed on the document.",
        "Elliptical seal pressed onto the sheet.",
        "Con dấu hình bầu dục đóng trên chứng từ.",
        "Dấu ô-van in lên tờ giấy.",
    ),
    "Rectangular stamp impressed on the document.": (
        "Rectangular stamp impressed on the document.",
        "Square or oblong seal pressed onto the sheet.",
        "Con dấu hình chữ nhật đóng trên chứng từ.",
        "Dấu vuông in lên tờ giấy.",
    ),
    "Column reference number printed under the table header.": (
        "Column reference number printed under the table header.",
        "The numbering row beneath the header that names each column.",
        "Hàng số thứ tự cột in dưới tiêu đề bảng.",
        "Dãy số (1)(2)(3) đánh dấu từng cột của bảng.",
    ),
    "Barcode value printed on the document.": (
        "Barcode value printed on the document.",
        "The code encoded in the printed bars.",
        "Chuỗi mã vạch in trên chứng từ.",
        "Giá trị mã hoá trong vạch in.",
    ),
    "Detail line nested inside this item's description cell.": (
        "Detail line nested inside this item's description cell.",
        "Sub-line printed inside the item's own cell.",
        "Dòng chi tiết lồng trong ô mô tả của mặt hàng.",
        "Dòng phụ nằm bên trong ô nội dung hàng hoá.",
    ),
    "Box reserved for a photograph.": (
        "Box reserved for a photograph.",
        "Blank frame kept for a portrait to be affixed.",
        "Ô để dán ảnh.",
        "Khung trống dành cho ảnh chân dung.",
    ),
    "Size printed inside the photograph box.": (
        "Size printed inside the photograph box.",
        "Dimensions written inside the photo frame.",
        "Kích thước in trong ô dán ảnh.",
        "Cỡ ảnh ghi bên trong khung.",
    ),
    "Subtotal of the group of rows printed directly above this line.": (
        "Subtotal of the group of rows printed directly above this line.",
        "Running total for the block of rows just above.",
        "Cộng của nhóm dòng in ngay phía trên.",
        "Tổng phụ cho cụm dòng vừa liệt kê ở trên.",
    ),
    "Answer ticked for the question printed beside it.": (
        "Answer ticked for the question printed beside it.",
        "The option marked in response to the adjacent question.",
        "Đáp án đã tích cho câu hỏi bên cạnh.",
        "Lựa chọn được đánh dấu ứng với câu hỏi kề nó.",
    ),
    "Heading of a table column.": (
        "Heading of a table column.",
        "The caption naming what a column holds.",
        "Tiêu đề của một cột trong bảng.",
        "Chữ đặt tên cho cột của bảng.",
    ),
    "Name of the group of rows printed below it.": (
        "Name of the group of rows printed below it.",
        "Caption for the block of rows that follows.",
        "Tên của nhóm dòng in bên dưới nó.",
        "Tiêu đề cụm dòng nằm ngay sau dòng này.",
    ),
    # Câu tả chính cái MẢNG dòng hàng trong JSON Schema (`kie_schema.ITEMS`).
    # Nó không thuộc cột nào nên không có chỗ trong `design.COLUMNS`, và vì thế
    # là câu cuối cùng trong schema còn y hệt nhau trên mọi trang.
    # --------------------------------------------- chức danh ký, và điều khoản
    # Câu chữ ký dùng chung cho MỌI chức danh (`descriptions.SIGN`): từ vựng
    # chức danh là mở, nên mô tả nói cái VAI chứ không nói cái tên. Nhưng dùng
    # chung thì nó in ra nhiều nhất bộ -- đo được 93 lần trên 60 tài liệu với
    # đúng một câu, tức là chính nó thành chỗ trùng nặng nhất.
    "The role of the person signing on this line, printed above the rule.": (
        "The role of the person signing on this line, printed above the rule.",
        "Which role puts its signature here.",
        "Chức danh của người ký ở dòng này.",
        "Vai người đặt bút ký tại đây, in phía trên nét kẻ.",
    ),
    "Heading of one numbered clause in the agreement.": (
        "Heading of one numbered clause in the agreement.",
        "Title of a numbered article in this document.",
        "Tiêu đề của một điều đánh số trong văn bản.",
        "Tên gọi của điều khoản mang số thứ tự này.",
    ),
    "Body of one numbered clause in the agreement.": (
        "Body of one numbered clause in the agreement.",
        "What the numbered article actually says.",
        "Nội dung của điều khoản đánh số này.",
        "Phần chữ nói rõ điều khoản ấy quy định gì.",
    ),
    # --------------------------------- mười ba cột lấy từ `rulebase/layouts/`
    # Thêm cột vào `design.COLUMNS` mà quên khai ở đây thì mất đa dạng chứ
    # không mất mô tả -- đúng thứ docstring trên đầu file cảnh báo, và đúng thứ
    # đã xảy ra: đo trên một bộ thật, `Line amount after value added tax.` in ra
    # 333 lần với MỘT câu duy nhất.
    "Unit price the hospital charges for this line.": (
        "Unit price the hospital charges for this line.",
        "The hospital's own price for one unit of this line.",
        "Đơn giá bệnh viện thu cho khoản mục này.",
        "Giá một đơn vị theo bảng giá của bệnh viện.",
    ),
    "Unit price the insurer recognises for this line.": (
        "Unit price the insurer recognises for this line.",
        "Unit price the insurance fund accepts for this item.",
        "Đơn giá được bảo hiểm chấp nhận cho khoản mục này.",
        "Mức giá một đơn vị mà quỹ bảo hiểm duyệt.",
    ),
    "Line amount at the hospital price.": (
        "Line amount at the hospital price.",
        "What this line costs at the hospital's own rate.",
        "Thành tiền của dòng theo giá bệnh viện.",
        "Số tiền dòng này tính theo bảng giá viện.",
    ),
    "Line amount at the price the insurer recognises.": (
        "Line amount at the price the insurer recognises.",
        "What this line comes to at the insured rate.",
        "Thành tiền của dòng theo giá bảo hiểm duyệt.",
        "Số tiền dòng này tính theo mức bảo hiểm chấp nhận.",
    ),
    "Share of this line the health-insurance fund pays, as a percentage.": (
        "Share of this line the health-insurance fund pays, as a percentage.",
        "Percentage of this line covered by health insurance.",
        "Tỷ lệ phần trăm quỹ bảo hiểm y tế chi trả cho dòng này.",
        "Mức hưởng bảo hiểm y tế của khoản mục, tính theo phần trăm.",
    ),
    "Share of this line charged at the service rate, as a percentage.": (
        "Share of this line charged at the service rate, as a percentage.",
        "Percentage of this line billed at the service tariff.",
        "Tỷ lệ phần trăm dòng này tính theo giá dịch vụ.",
        "Phần của khoản mục áp mức giá dịch vụ, theo phần trăm.",
    ),
    "Portion of this line the patient pays entirely themselves.": (
        "Portion of this line the patient pays entirely themselves.",
        "The part of this line falling wholly on the patient.",
        "Phần tiền người bệnh tự chi trả hoàn toàn cho dòng này.",
        "Khoản của dòng này do bệnh nhân tự lo, không ai đỡ.",
    ),
    "Portion of this line paid from another source.": (
        "Portion of this line paid from another source.",
        "Part of this line covered by some other payer.",
        "Phần tiền của dòng này do nguồn khác chi trả.",
        "Khoản còn lại lấy từ nguồn kinh phí khác.",
    ),
    "Meter reading recorded at the start of the billing period.": (
        "Meter reading recorded at the start of the billing period.",
        "The meter number read at the beginning of this period.",
        "Chỉ số công tơ đọc ở đầu kỳ.",
        "Số đọc trên đồng hồ vào đầu chu kỳ tính tiền.",
    ),
    "Meter reading recorded at the end of the billing period.": (
        "Meter reading recorded at the end of the billing period.",
        "The meter number read when this period closed.",
        "Chỉ số công tơ đọc ở cuối kỳ.",
        "Số đọc trên đồng hồ vào cuối chu kỳ tính tiền.",
    ),
    "Consumption allowance this line is billed against.": (
        "Consumption allowance this line is billed against.",
        "The quota this line's usage is measured against.",
        "Định mức tiêu thụ dùng để tính dòng này.",
        "Mức khoán mà lượng dùng của dòng được đối chiếu.",
    ),
    "Line amount after value added tax.": (
        "Line amount after value added tax.",
        "What this line costs once VAT is added.",
        "Thành tiền của dòng đã gồm thuế giá trị gia tăng.",
        "Số tiền dòng này sau khi cộng thuế GTGT.",
    ),
    "Barcode printed against this line.": (
        "Barcode printed against this line.",
        "The barcode standing beside this item.",
        "Mã vạch in kèm dòng hàng này.",
        "Dãy mã vạch của khoản mục ở dòng.",
    ),
    "Rows of the item table printed on this document.": (
        "Rows of the item table printed on this document.",
        "One entry per row of the item table on this sheet.",
        "Các dòng của bảng hàng hoá in trên chứng từ này.",
        "Mỗi phần tử là một dòng trong bảng chi tiết của tờ giấy.",
    ),
}


# Cách nói do model viết, nếu có. File này được ghi trong một bước RIÊNG --
# không phải lúc vẽ trang -- rồi người đọc diff trước khi nó vẽ gì; ranh giới
# nằm ở đấy là cố ý. (Bước sinh ra nó là `agent/augment_descriptions.py`, đã
# bỏ cùng Ollama ngày 18-09-2026; file đang có vẫn đọc được.) Không có
# file thì bảng viết tay bên trên vẫn đủ chạy, nên đây là thứ làm giàu, không
# phải thứ bắt buộc.
ADDED = Path(__file__).resolve().parents[1] / "rulebase" / "kie_phrasings.json"


@lru_cache(maxsize=1)
def pool() -> dict[str, tuple[str, ...]]:
    """Bảng viết tay, cộng những cách nói model đã viết (nếu file có).

    Gộp chứ không thay: câu người viết luôn nằm trong danh sách, nên dù file
    kia rỗng hay bị xoá thì mỗi trường vẫn còn bốn cách nói."""
    merged = {canon: list(variants) for canon, variants in POOL.items()}
    try:
        raw = json.loads(ADDED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {canon: tuple(v) for canon, v in merged.items()}
    for canon, variants in raw.items():
        if canon.startswith("_") or not isinstance(variants, list):
            continue
        # Khoá KHÔNG kết thúc bằng dấu chấm không phải một câu mô tả: đó là
        # một NHÃN in trên giấy mà `pipeline/kie.py::_fallback_description`
        # chép vào ô mô tả khi chưa ai chạy model qua bộ ấy ("NGƯỜI LẬP
        # BẢNG"). Nó làm khoá tra cứu thì đúng, làm một lựa chọn thì sai --
        # giữ nó lại là để một phần bảy số tờ vẫn mang đúng cái mô tả rỗng
        # nghĩa mà cả việc này sinh ra để bỏ.
        seed_with = [canon] if canon.rstrip().endswith(".") else []
        have = merged.setdefault(canon, seed_with)
        seen = set(have)
        for variant in variants:
            text = str(variant).strip()
            if text and text not in seen:
                have.append(text)
                seen.add(text)
    return {canon: tuple(v) for canon, v in merged.items()}


@lru_cache(maxsize=1)
def canonical_of() -> dict[str, str]:
    """Cách nói -> câu gốc của nó. Bảng NGƯỢC, và nó phải có.

    `derive.py` chạy được nhiều lần trên cùng một bộ, và lần thứ hai nó đọc
    cái đã ghi lần thứ nhất -- tức là một CÁCH NÓI, không phải câu gốc. Không
    có bảng ngược thì `pool().get(cách_nói)` trả None và câu ấy giữ nguyên:
    mọi cặp KIE mang cách nói đã chọn từ lần trước bị ĐÓNG BĂNG ở đó, và một
    lần mở rộng bảng chữ về sau không với tới chúng nữa.

    Đo được lúc phát hiện: sau khi bảng lên mười cách nói mỗi câu, nhóm cặp
    còn đổi được giọng trùng liên tiếp 15.8% thay vì 10% -- phần chênh là
    những cặp đã đóng băng từ thời bảng còn bốn cách nói."""
    out: dict[str, str] = {}
    for canon, variants in pool().items():
        for variant in variants:
            out.setdefault(variant.strip(), canon)
    return out


def describe(text: str, seed, field: str = "", ordinal: int | None = None) -> str:
    """Một cách nói của `text`, chọn theo `(seed, field, CÂU GỐC)`.

    Băm theo câu GỐC chứ không theo `text` đưa vào, nên chạy lại trên một bộ
    đã đổi giọng vẫn ra đúng cách nói ấy -- hàm này luỹ đẳng, và một bộ dữ
    liệu derive hai lần không được khác một bộ derive một lần.

    Không có trong bảng thì trả lại nguyên câu: một mô tả mới thêm vào
    `design.py` mà quên khai ở đây thì mất đa dạng, không mất mô tả.

    ## `ordinal`: QUAY VÒNG thay vì bốc

    Băm độc lập là bốc ngẫu nhiên: với mười cách nói, hai tài liệu bất kỳ trùng
    nhau một phần mười số lần, và không cách nào hạ thấp hơn ngoài việc viết
    thêm chữ. Đo được trên một lượt 70 tài liệu: 13.8%.

    Đưa SỐ THỨ TỰ của tài liệu vào thì phép chọn thành quay vòng: tài liệu thứ
    n và thứ n+1 của cùng một loại lệch nhau đúng một bước, nên chúng KHÔNG BAO
    GIỜ trùng cho tới lúc hết bảng. Câu gốc vẫn quyết điểm xuất phát, nên hai
    trường khác nhau trên cùng tờ giấy vẫn ra hai câu khác nhau -- một trang
    không đọc lên như một cái máy đọc thuộc lòng.

    Vẫn dựng lại được: `ordinal` suy từ tên file, không từ đồng hồ hay thứ tự
    chạy. Và mọi tờ của MỘT tài liệu dùng chung một `ordinal`, nên ba tờ của
    một hoá đơn vẫn cùng giọng -- đó là một tờ giấy bị cắt, không phải ba
    chứng từ."""
    wanted = str(text or "").strip()
    canon = wanted if wanted in pool() else canonical_of().get(wanted, "")
    choices = pool().get(canon)
    if not choices:
        return text
    # `seed` PHẢI có trong `start`, và việc thiếu nó là lỗi đo được.
    #
    # Quay vòng theo `ordinal` lo việc hai tài liệu LIỀN NHAU lệch nhau một
    # bước. Nhưng nếu `start` chỉ băm `field|canon` thì cả phép chọn thành hàm
    # thuần của `(tên trường, câu gốc, ordinal)`: hai tài liệu cùng `ordinal`
    # nhận y hệt một câu, và khi `ordinal` không đổi trên cả lượt chạy thì MỌI
    # tài liệu về cùng một biến thể.
    #
    # Đo trên một mẻ 50 tài liệu (`ordinal` = 0 ở cả 50 vì tên file không có
    # số đuôi): kho mười biến thể ra ĐÚNG MỘT câu. Và trên chính bản ghi:
    # họ trường có mặt ở >=3 tài liệu, chỉ 7% có hơn một cách viết -- so với
    # 41% ở mẻ mà `ordinal` có thay đổi.
    #
    # Có `seed` thì hai vế cộng lại chứ không trừ nhau: `start` đổi theo TÀI
    # LIỆU, `step` đổi theo hạng của nó. Hai tờ của cùng một tài liệu vẫn
    # chung giọng, vì chúng chung cả `seed` lẫn `ordinal`.
    start = zlib.crc32(f"{seed}|{field}|{canon}".encode("utf-8"))
    if ordinal is None:
        # Không biết số thứ tự thì lùi về cách cũ: bốc theo seed. Vẫn đúng,
        # chỉ là sàn trùng cao hơn.
        return choices[zlib.crc32(f"{seed}|{field}|{canon}".encode("utf-8"))
                       % len(choices)]
    # QUAY VÒNG CÓ TRƯỢT. Quay vòng trần (`start + ordinal`) có chu kỳ đúng
    # bằng cỡ kho, nên hai tài liệu cách nhau đúng một chu kỳ vẫn trùng --
    # `bang_diem_00049` và `bien_ban_nghiem_thu_00039` cách nhau 10 trên một
    # kho 10 câu, đo được trùng thật. Với 60 tài liệu thì mọi khoảng cách
    # 10/20/30/40/50 đều trùng, và đó là rất nhiều cặp.
    #
    # Cộng thêm số VÒNG đã đi (`ordinal // n`) làm chu kỳ dài ra `n * (n+1)`:
    # hai tài liệu liền nhau vẫn lệch đúng một bước (vế đáng giá của quay
    # vòng), còn cặp trùng bị đẩy từ khoảng cách 10 ra 110.
    n = len(choices)
    step = int(ordinal) + int(ordinal) // n
    return choices[(start + step) % n]


def variants_of(text: str) -> tuple[str, ...]:
    """Mọi cách nói của câu này, kể cả khi `text` đã là một cách nói.

    Để người gọi TRÁNH TRÙNG: hai trường khác nhau trên cùng một tờ giấy bốc
    trúng cùng một câu là chuyện thường (bảng bốn cách nói thì một phần tư số
    lần), và khi ấy mô tả mang zero thông tin để phân biệt chúng -- người
    huấn luyện đọc hai cái hộp khác nhau với cùng một câu và không biết hộp
    nào là hộp nào."""
    wanted = str(text or "").strip()
    canon = wanted if wanted in pool() else canonical_of().get(wanted, "")
    return pool().get(canon) or ()


def ordinal_of(stem: str) -> int:
    """Số thứ tự của tài liệu, đọc từ tên file. `hoa_don_gtgt_00014_p2` -> 14.

    Bỏ đuôi `_pN` trước: các tờ của một tài liệu phải ra CÙNG một số, nếu không
    tờ hai đọc lên một giọng khác tờ một. Không có số thì 0 -- mất quay vòng,
    không mất mô tả."""
    import re                                                  # noqa: PLC0415

    name = re.sub(r"_p\d+$", "", str(stem or ""))
    found = re.findall(r"(\d+)$", name)
    return int(found[0]) if found else 0


def voice_record(record: dict, pairs: list[dict], *, stem: str = "",
                 ordinal: int | None = None) -> None:
    """Đổi giọng mô tả cho MỘT bản ghi, tại chỗ. Luỹ đẳng.

    ## Vì sao hàm này tồn tại chứ không nằm trong `derive.py`

    Phép đổi giọng vốn chỉ chạy ở cuối cả lượt, trong `derive.py`. Một lượt
    không tới lượt `derive` -- batch bị ngắt, `finish(skip_derive=True)`, hay
    vẽ tay từng tờ -- thì `records/*.json` nằm lại mãi với câu tả GỐC, và câu
    gốc thì lặp: đo trên `data/thu1k`, **8 564 câu tả chỉ có 171 câu khác
    nhau (2,0%)**, trang nặng nhất 360 câu / 36 khác nhau. "Questionnaire tick
    box printed on the document." một mình xuất hiện 671 lần.

    Nên luật ở đây, và hai nơi gọi nó: `synthgen/draw_llm.py` ngay lúc vẽ, và
    `derive.py` khi nó chạy. Gọi hai lần không sao -- `describe()` băm theo
    CÂU GỐC nên nó luỹ đẳng, và đó là điều kiện để đặt được luật ở một chỗ.

    `seed` lấy từ `job_id` (UUID suy từ chính seed tờ giấy): ổn định, khác
    nhau giữa các tài liệu, giống nhau ở mọi tờ của cùng một tài liệu -- nên
    ba tờ của một hoá đơn đọc lên cùng một giọng.
    """
    seed = record.get("job_id") or record.get("filename", "")
    if ordinal is None:
        ordinal = ordinal_of(stem or str(record.get("filename") or ""))

    for pair in pairs:
        # Khoá theo CỘT chứ không theo ô: `qty_r1` và `qty_r7` là cùng một cột
        # nên phải cùng một giọng trong một tờ giấy. Khoá theo ô thì bảng bốn
        # mươi dòng đọc lên như bốn mươi người khác nhau cùng tả một cột.
        pair["description"] = describe(pair.get("description", ""), seed,
                                       str(pair.get("column")
                                           or pair.get("field", "")),
                                       ordinal=ordinal)

    # MỖI TRƯỜNG MỘT CÂU RIÊNG, trong phạm vi một trang.
    #
    # Đổi giọng theo hạng tài liệu làm hai TÀI LIỆU khác nhau, không làm hai
    # TRƯỜNG trên cùng một tờ khác nhau: `nguoi_khai` và `chuyen_vien_tu_van`
    # cùng gốc "chức danh người ký", bảng bốn cách nói, nên một phần tư số lần
    # chúng bốc trúng cùng một câu. Khi ấy mô tả mang zero thông tin để phân
    # biệt hai cái hộp -- đo được: 84% số trang có ít nhất hai trường cùng mô
    # tả.
    #
    # Ô BẢNG thì KHÔNG áp: mọi ô của một cột phải cùng giọng, và `column` là
    # thứ phân biệt chúng với các cột khác.
    used: dict[int, set[str]] = {}
    for pair in pairs:
        if pair.get("source") == "table":
            continue
        page_no = int(pair.get("page_number", 1) or 1)
        taken = used.setdefault(page_no, set())
        text = str(pair.get("description") or "")
        if text and text in taken:
            for other in variants_of(text):
                if other not in taken:
                    pair["description"] = other
                    text = other
                    break
        if text:
            taken.add(text)

    # `entity_annotations` mang mô tả của RIÊNG nó, do `pipeline/kie.py` ghi
    # lúc vẽ trang, và đổi giọng cho cặp mà bỏ nó lại thì một file tự nói hai
    # câu khác nhau về cùng một trường -- tệ hơn là không đa dạng. Ghép theo
    # CHỈ SỐ THỰC THỂ, không theo tên trường: ô bảng có `field_name` là
    # `qty_r7` trong khi cặp khoá theo cột `qty`, nên so tên là lệch.
    #
    # Bảng giọng dựng SAU khi đã ép duy nhất, không phải trước: lần đầu dựng
    # nó trong vòng đổi giọng rồi mới ép duy nhất, nên `entity_annotations`
    # giữ câu CŨ còn cặp mang câu mới. `check.py` bắt đúng 436 ca ấy.
    voice: dict[int, str] = {}
    for pair in pairs:
        index = pair.get("value_entity_index")
        if isinstance(index, int):
            voice[index] = str(pair.get("description") or "")
    for entity in record.get("entity_annotations") or []:
        index = entity.get("entity_index")
        if index in voice:
            entity["description"] = voice[index]
        elif entity.get("description"):
            entity["description"] = describe(str(entity["description"]), seed,
                                             str(entity.get("field_name", "")),
                                             ordinal=ordinal)


__all__ = ["ADDED", "POOL", "canonical_of", "describe", "ordinal_of", "pool",
           "variants_of", "voice_record"]
