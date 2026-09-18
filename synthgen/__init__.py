"""Một bộ sinh chứng từ tổng hợp soạn từ đầu.

Không đọc `rulebase/layouts/*.yaml` và không kế thừa dáng của phôi nào có
sẵn: dáng ở đây do `synthgen/design.py` dựng ra từ một ngữ pháp bố cục viết
riêng cho gói này. Cái nó DÙNG LẠI của kho là ba thứ không phải bố cục:

* hợp đồng nhãn — mọi chữ in ra nằm trong `<span data-kind="...">` và hộp
  được ĐO trong trình duyệt (`generators/html/page.py::CELL_RECTS_JS`);
* bộ từ vựng nhãn — `pipeline/record.py` dịch `data-kind` sang 11 nhãn của
  `blocks[]` và 19 nhãn `docsynth.annotations.v1`;
* kho chữ tiếng Việt — `rulebase/corpus/vi/*.txt`, và `rulebase/text.py`
  cho tiền bằng chữ.

Ba thứ ấy là thứ bảo đảm "boxes và content phải đúng". Dáng thì mới hoàn toàn.
"""
