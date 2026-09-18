"""KIE cho MỌI nhãn in trên giấy, không riêng mấy cặp "nhãn: giá trị".

`pipeline/kie.py` ghép một trường với cái nhãn in ngay trước nó, và làm việc
ấy tốt -- nhưng nó chỉ thấy được những chỗ có nhãn in kèm. Đo trên 400 trang
lấy ngẫu nhiên khắp 32 loại chứng từ: **91 396 đoạn chữ có hộp, chỉ 10 220
(11,2%) nằm trong một cặp KIE**. Phần còn lại -- toàn bộ ô bảng, tiêu đề cột,
ghi chú, tiêu đề tài liệu, con dấu, dòng cộng nhóm -- có hộp, có nhãn lớp, mà
không có mặt trong `kie`.

File này lấp nốt, và chia làm ba loại cặp:

1. **Ô bảng** -- khoá là TIÊU ĐỀ CỘT, giá trị là ô. Với bảng tiêu đề nhiều
   tầng thì khoá mang cả đường dẫn ("Giá trị và thuế › Số lượng và đơn giá ›
   Đơn giá"), vì cái tên lá một mình ("Đơn giá") không nói nó là đơn giá của
   cái gì.
2. **Cặp mới** -- `total.group ↔ total.group_amount` (dòng cộng nhóm) và
   `checks.question ↔ checks.answer` (câu hỏi có ô tích). Cả hai đều là
   khoá-giá trị thật, chỉ là `pipeline/kie.py` chưa biết mặt.
3. **Trường không có nhãn in** -- tiêu đề tài liệu, ghi chú, con dấu, tên đơn
   vị. Chúng vẫn là trường, vẫn phải có hộp trong `kie`, chỉ là `key_bbox`
   bằng `null` và `key_source` ghi `implied`. Bỏ chúng ra ngoài thì một
   trình đọc `kie` không bao giờ thấy tiêu đề của tờ giấy nó đang đọc.

Lưới bảng dựng lại bằng HÌNH HỌC từ chính `entity_annotations`, không đọc lại
DOM: ô cùng một cột thì cùng dải hoành độ, ô cùng một dòng thì chồng nhau theo
tung độ. Cách dựng ấy được đối chiếu với `extracted.menu` -- bản ghi nội dung
mà bộ sinh đã chốt trước khi vẽ -- và khớp 600/600 tài liệu thử.
"""

from __future__ import annotations

import sys
import re
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.kie import FURNITURE, slug  # noqa: E402
from synthgen.design import COLUMNS  # noqa: E402

# `kind` của một cột KHÔNG phải cứ `menu.` + tên cột: cột `discount` in ra
# `menu.discountprice`. Cắt chuỗi mà đoán thì cột ấy rơi ra ngoài KIE và
# không gì báo -- đã đo được: 86 ô mất trong 200 trang thử.
BY_KIND = {str(spec["kind"]): key for key, spec in COLUMNS.items()}

# Trường không có nhãn in kèm. Mô tả viết ở đây vì không có chữ nào trên giấy
# để suy ra -- đúng chỗ `pipeline/kie.py` phải bỏ cuộc.
# Kind KHÔNG bao giờ thành trường: khung của trang, không phải thông tin.
# Ô bảng đã vào `line_items`; chữ chìm và số trang do máy sinh.
NEVER = frozenset({"watermark", "footer.page", "colhdr"})

# Tên người đọc được cho từng ĐOẠN của một `kind`, để dựng câu tả khi bảng tay
# không có mục nào. Ngắn và chung: đây là chỗ đỡ, không phải chỗ tả kỹ.
_WORDS = {
    "clause": "numbered clause", "legal": "legal ground", "basis": "",
    "sign": "signature block", "title": "title", "name": "name",
    "note": "note", "body": "body", "head": "heading", "signedat": "place and date",
    "footnote": "footnote", "formula": "formula", "caption": "caption",
    "figure": "figure", "table": "table", "toc": "table of contents",
    "page": "page number", "survey": "questionnaire", "question": "question",
    "answer": "answer", "option": "option", "tick": "tick box",
    "total": "total", "grand": "grand", "line": "line", "group": "group",
    "label": "label", "amount": "amount", "words": "amount in words",
    "invoice": "document", "field": "field", "store": "organisation",
    "address": "address", "phone": "telephone", "tax_code": "tax code",
    "masthead": "national heading", "menu": "item", "meta": "reference",
    "value": "value", "subtitle": "subtitle", "period": "period",
    "summary": "summary", "gross": "gross", "branch": "branch",
    "website": "website", "photo": "photograph", "placeholder": "box",
    "size": "size", "barcode": "barcode", "detail": "detail",
    "stt": "row number", "unit": "unit", "qty": "quantity", "ref": "reference",
    "date": "date", "vat": "VAT", "rate": "rate", "colnum": "column number",
}


def implied_for(kind: str) -> tuple[str, str] | None:
    """`(tên trường, câu tả)` cho một run KHÔNG có nhãn in kèm.

    `IMPLIED` là bảng viết tay, và một bảng viết tay bỏ sót thì run rơi khỏi
    KIE mà không gì báo. Đo trên tờ biên bản kiểm tra thuế: bốn điều khoản, ba
    căn cứ pháp lý, ba chức danh người ký và dòng tổng đều vắng mặt -- tất cả
    vì `kind` của chúng không có trong bảng.

    Nên bảng ấy thành chỗ ĐỠ, không phải cổng: kind nào có mục thì lấy mục
    (tên đẹp hơn, câu tả viết kỹ hơn), kind nào không thì suy thẳng từ chính
    nó. `kind` vốn là từ vựng ĐÓNG do bộ dựng trang phát ra, nên nó đã mang
    nghĩa -- `legal.basis` là căn cứ pháp lý ở mọi tờ giấy, không riêng tờ này.

    `None` chỉ cho những thứ thật sự không phải trường."""
    kind = str(kind or "")
    if not kind or kind in NEVER or kind.startswith("menu."):
        return None
    if kind in IMPLIED:
        return IMPLIED[kind]
    parts = [w for w in re.split(r"[._]+", kind) if w]
    words = [_WORDS.get(w, w.replace("_", " ")) for w in parts]
    phrase = " ".join(w for w in words if w).strip() or kind
    return slug(kind), f"{phrase[:1].upper()}{phrase[1:]} printed on the document."


IMPLIED: dict[str, tuple[str, str]] = {
    "title": ("doc_title", "Main title of the document."),
    "subtitle": ("doc_subtitle", "Subtitle printed under the main title."),
    "note": ("note", "Note or condition printed on the document."),
    "footer": ("footer", "Footer line printed at the bottom of the page."),
    "period": ("period", "Billing or reporting period this document covers."),
    "masthead": ("masthead", "National heading printed above the title."),
    "store.name": ("org_name",
                   "Legal name of the organisation that issued this document."),
    "store.branch": ("org_branch",
                     "Branch or department of the issuing organisation."),
    "store.website": ("org_website", "Website of the issuing organisation."),
    "parent_org": ("parent_org",
                   "Parent body the issuing organisation reports to."),
    "sign.name": ("signer_name",
                  "Printed name of the person who signs at this place."),
    "sign.signedat": ("signed_at",
                      "Place and date the document was signed."),
    "seal.round": ("seal", "Round stamp impressed on the document."),
    "seal.oval": ("seal", "Oval stamp impressed on the document."),
    "seal.square": ("seal", "Rectangular stamp impressed on the document."),
    "colnum": ("column_number",
               "Column reference number printed under the table header."),
    "menu.barcode": ("barcode", "Barcode value printed on the document."),
    "menu.detail": ("item_detail",
                    "Detail line nested inside this item's description cell."),
    "photo.placeholder": ("photo", "Box reserved for a photograph."),
    "photo.size": ("photo_size", "Size printed inside the photograph box."),
    "invoice.subtitle": ("doc_subtitle",
                         "Subtitle printed under the main title."),
}

# Cặp mới: (kind của khoá, kind của giá trị, tên trường, mô tả).
PAIRED = (
    ("total.group", "total.group_amount", None,
     "Subtotal of the group of rows printed directly above this line."),
    ("invoice.checks.question", "invoice.checks.answer", None,
     "Answer ticked for the question printed beside it."),
)


class _Spans(HTMLParser):
    """Bối cảnh Ô BẢNG của từng `<span data-kind>`, theo đúng thứ tự DOM.

    Mỗi span in ra một đoạn chữ, và `pipeline/record.py` dựng đúng một thực
    thể cho mỗi đoạn -- đo trên 60 tài liệu: 60/60 khớp một-một, cùng thứ tự.
    Nên chỗ ngồi thật của một ô (`data-row`, `data-col`, `colspan`, tầng thứ
    mấy trong `<thead>`) gắn được vào từng hộp mà không phải suy từ toạ độ.

    Vì sao không suy từ toạ độ: đã thử hai lối và hỏng cả hai. Đòi dải hoành
    độ của ô GIAO với dải của tiêu đề thì cột số căn phải mất tiêu đề; nới ra
    so tâm gần nhất thì cột `qty` cướp tiêu đề "Đơn giá" của cột bên. Trình
    duyệt đã biết ô nào ở cột nào rồi, và markup còn giữ nguyên câu trả lời."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sheet = 0
        self.in_head = False
        self.head_row = -1
        self.cell: dict | None = None
        self.out: list[dict] = []
        # LƯỚI TỰ TÍNH, cho trang model viết.
        #
        # `markup.py` của engine phát `data-row`/`data-col` lên từng ô, nên chỗ
        # ngồi đọc thẳng từ thuộc tính. Model thì chỉ viết `<td data-cell>` --
        # đó là tất cả những gì lời dặn đòi, và `repair.cells()` thêm vào cũng
        # chỉ thế. Hậu quả đo được trên pilot9: `col=None` trên MỌI ô, và
        # `table_pairs` gạt sạch 92 ô của một tờ vì `cell["col"] is not None`.
        # Thân bảng -- phần dày đặc thông tin nhất tờ giấy -- vắng mặt hoàn
        # toàn khỏi KIE, im lặng.
        #
        # Nên tính lấy, đúng cách trình duyệt tính: con trỏ cột chạy theo
        # `colspan`, và `rowspan` của ô hàng trên chiếm chỗ sẵn ở hàng dưới.
        # Không cần model đặt tên gì, không cần bảng tra nào -- chỗ ngồi là
        # thuộc tính của CẤU TRÚC, và cấu trúc thì đã nằm sẵn trong markup.
        self._row = -1          # chỉ số hàng trong bảng đang mở
        self._col = 0           # con trỏ cột của hàng đang mở
        self._held: dict[int, int] = {}   # cột -> còn mấy hàng bị rowspan chiếm
        self._table = 0         # bảng thứ mấy trên trang

    def _seat(self, span: int, rows: int) -> int:
        """Cột trống đầu tiên từ con trỏ, rồi giữ chỗ cho `rowspan`."""
        while self._held.get(self._col, 0) > 0:
            self._col += 1
        at = self._col
        for i in range(at, at + max(1, span)):
            if rows > 1:
                self._held[i] = rows
        self._col = at + max(1, span)
        return at

    def handle_starttag(self, tag, attrs):
        table = dict(attrs)
        if tag == "div" and "sheet" in (table.get("class") or "").split():
            self.sheet += 1
            self.in_head = False
            self.head_row = -1
        elif tag == "table":
            self._row, self._col, self._held = -1, 0, {}
            self._table += 1
        elif tag == "thead":
            self.in_head = True
            self.head_row = -1
        elif tag in ("tbody", "tfoot"):
            self.in_head = False
        elif tag == "tr":
            if self.in_head:
                self.head_row += 1
            self._row += 1
            self._col = 0
            # Một hàng trôi qua: mọi chỗ đang bị giữ giảm một.
            self._held = {c: n - 1 for c, n in self._held.items() if n > 1}
        elif tag in ("td", "th"):
            span = _int(table.get("colspan")) or 1
            rows = _int(table.get("rowspan")) or 1
            at = self._seat(span, rows)
            self.cell = {
                "kind": table.get("data-cell"),
                # Thuộc tính THẮNG khi có: engine biết chỗ ngồi thật của nó,
                # kể cả khi bảng bị cắt sang tờ sau và chỉ số hàng đánh lại.
                "row": _int(table.get("data-row"))
                if table.get("data-row") is not None else self._row,
                "col": _int(table.get("data-col"))
                if table.get("data-col") is not None else at,
                "colspan": span,
                "rowspan": rows,
                "head": self.in_head,
                "tier": self.head_row if self.in_head else -1,
                # BẢNG NÀO. `heads` gom theo trang thì một tờ có hai bảng sẽ
                # lấy tiêu đề của bảng này gán cho cột của bảng kia -- đo được
                # trên pilot9: cột "Loại hình" nhận key "Mã hồ sơ" của bảng
                # dưới. Cột số 1 của hai bảng khác nhau là hai cột khác nhau.
                "table": self._table,
            }
        elif tag == "span" and "data-kind" in table:
            self.out.append({"page": self.sheet, "cell": self.cell,
                             "kind": table["data-kind"], "text": "",
                             # ĐƯỜNG DẪN MODEL TỰ KHAI. Có nó thì KIE không
                             # phải suy trường nào đi với nhãn nào -- xem
                             # `declared_pairs`.
                             "path": table.get("data-path", "")})
            self._open = self.out[-1]

    def handle_data(self, data):
        # CHỮ của span, để ghép với thực thể theo NỘI DUNG thay vì theo số
        # lượng. Xem `table_pairs`.
        if getattr(self, "_open", None) is not None:
            self._open["text"] += data

    def handle_endtag(self, tag):
        if tag == "thead":
            self.in_head = False
        elif tag in ("td", "th"):
            self.cell = None
        elif tag == "span":
            self._open = None


def _slug_col(text: str) -> str:
    """Tên trường từ tiêu đề cột in trên giấy. ASCII, snake_case, gọn."""
    import unicodedata                                       # noqa: PLC0415

    plain = _tight(text).lower().replace("đ", "d")
    plain = unicodedata.normalize("NFD", plain)
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")[:34]


def _tight(text: str) -> str:
    """Chữ đã chuẩn hoá khoảng trắng, để so hai nguồn."""
    return " ".join(str(text or "").split())


def _int(value) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def seats(markup: str) -> list[dict]:
    """Chỗ ngồi của từng span, cùng thứ tự với `entity_annotations`."""
    parser = _Spans()
    parser.feed(markup)
    parser.close()
    return parser.out


def _overlap(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _on(record: dict, page: int) -> list[dict]:
    return [e for e in record.get("entity_annotations") or []
            if int(e.get("page_number", 1) or 1) == page]


def _described(kind) -> str:
    """Câu tả cho một `kind`, lấy đúng phần câu tả của `implied_for`."""
    found = implied_for(str(kind or ""))
    if isinstance(found, (tuple, list)):
        return str(found[-1]) if found else ""
    return str(found or "")


def declared_pairs(record: dict, markup: str, page: int) -> list[dict]:
    """Cặp KIE lấy từ `data-path` model tự khai. Không suy gì cả.

    ## Vì sao đường này tồn tại

    Mọi lỗi KIE đo được trên `data/test1` đều nằm ở phép SUY: ô trải bốn cột
    nhận tên cột đầu tiên nó chạm (`stt_r9` mang "TỔNG CỘNG"), nhãn vớ lấy run
    kế tiếp trong cây DOM ("Số: 12/BB-HĐSP" nhận ngày tháng ở góc phải). Và đo
    được rằng phép suy KHÔNG THỂ đúng hết: 30% run mang vai key không có tín
    hiệu cấu trúc nào tách chúng khỏi một dòng đã trọn nghĩa.

    Bộ `pair_prompt100` tránh hẳn chuyện ấy bằng cách để model khai đường dẫn
    ngay trên thẻ -- 96 điểm khai trên một tờ biên lai. Model biết chắc giá trị
    nào thuộc trường nào, vì chính nó vừa nghĩ ra cả hai.

    ## Quan hệ với đường suy

    Đây là đường ƯU TIÊN, không phải đường thay thế. Run nào có `data-path` thì
    lấy tên từ đó và không ai suy nữa; run nào không có thì đường cũ vẫn chạy.
    Model quên khai vài chỗ không làm hỏng cả tờ.

    Tên trường lấy NGUYÊN đường dẫn, chỉ đổi dấu chấm và ngoặc thành gạch dưới:
    `merchant.tax_id` -> `merchant_tax_id`, `items[0].amount` ->
    `items_0_amount`. Giữ nguyên hình dạng cây để người đọc lần ngược về `data`
    được."""
    spans = seats(markup)
    ents = _on(record, page)
    out = []
    for span, entity in zip(spans, ents):
        path = str(span.get("path") or "").strip()
        if not path:
            continue
        out.append({
            "field": re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_"),
            "path": path,
            "key_text": "", "value_text": str(entity.get("text") or ""),
            "key_bbox": None, "value_bbox": _box(entity["bbox"]),
            "key_entity_index": None,
            "value_entity_index": entity["entity_index"],
            "page_number": page, "source": "declared",
            # VAI, engine khai. `path` là danh tính máy, `printed_header` là
            # nghĩa lấy từ giấy, `role` là vai -- ba tên cho ba mục đích, đúng
            # hình dạng `docs/kie-thiet-ke-nhan.md` §F4 chốt. Thiếu nó thì
            # `role` ra `null` trên mọi cặp khai.
            "role": str(entity.get("kind") or "") or None,
            "description_source": "declared",
            # `implied_for` trả về TUPLE `(tên, câu tả)`. Dùng thẳng thì câu tả
            # in ra `"('period', 'Billing or reporting period...')"` -- đo được
            # trên mọi trường khai của pilot12.
            "description": (_described(entity.get("kind"))
                            or f"Value bound to `{path}` in the document's own "
                               f"data tree."),
        })
    return out


def table_pairs(record: dict, markup: str) -> list[dict]:
    """Một cặp cho mỗi ô bảng: tiêu đề cột → ô, dùng CHỖ NGỒI THẬT.

    Cột, dòng, `colspan` và tầng đều đọc từ markup mà trình duyệt đã dàn, nên
    không có chỗ nào để đoán sai. Tiêu đề của một ô là ô tiêu đề ở tầng SÂU
    nhất phủ cột ấy; đường dẫn là tất cả các tầng phủ nó, từ trên xuống."""
    ents = record.get("entity_annotations") or []
    seat_list = seats(markup)

    # GHÉP THEO CHỮ, không theo SỐ LƯỢNG.
    #
    # Bản trước bỏ cuộc im lặng khi `len(seat_list) != len(ents)` -- và với
    # trang model viết thì hai con số gần như không bao giờ bằng nhau: một
    # `<span data-kind="menu.note"></span>` rỗng là một chỗ ngồi nhưng không
    # sinh thực thể nào. Đo trên tờ biên bản thuế: 129 span, 126 thực thể, lệch
    # đúng ba ô ghi chú để trống -- và cả bảng năm mươi sáu ô mực ra khỏi KIE
    # vì ba ô rỗng ấy.
    #
    # Bỏ chỗ ngồi không có chữ trước, rồi đi song song hai danh sách và chỉ
    # nhận cặp khi chữ khớp. Lệch chỗ nào thì trượt chỗ ấy, phần còn lại vẫn
    # ghép được -- thay vì mất cả bảng.
    # Ghép bằng CHỈ MỤC, không đi tuần tự: hai danh sách không cùng thứ tự.
    # `entity_annotations` xếp theo hình học, `seats` theo thứ tự DOM -- và chữ
    # chìm "BẢN LƯU" là span ĐẦU TIÊN trong DOM nhưng là thực thể thứ 29 vì
    # toạ độ y của nó nằm giữa trang. Phép đi một chiều tắc ngay ở đó, và đo
    # được chỉ 29 trên 126 cặp ghép được.
    #
    # Cùng một chữ xuất hiện hai lần (hai ô cùng in "0") thì lấy chỗ ngồi chưa
    # dùng, theo thứ tự DOM -- thứ tự ấy là phỏng đoán tốt nhất còn lại, và hai
    # ô cùng chữ cùng cột thì nhãn của chúng giống nhau nên nhầm cũng vô hại.
    index: dict[str, list[dict]] = {}
    for seat in seat_list:
        text = _tight(seat.get("text", ""))
        if text:
            index.setdefault(text, []).append(seat)
    taken: dict[str, int] = {}
    pairs: list[tuple[dict, dict]] = []
    for entity in ents:
        want = _tight(str(entity.get("text") or ""))
        bucket = index.get(want) or []
        at = taken.get(want, 0)
        if at >= len(bucket):
            continue
        taken[want] = at + 1
        pairs.append((entity, bucket[at]))
    if not pairs:
        return []

    heads: dict[int, list[tuple]] = {}
    cells: list[tuple] = []
    for entity, seat in pairs:
        cell = seat["cell"]
        if not cell:
            continue
        page = int(entity.get("page_number", 1) or 1)
        # Ô TIÊU ĐỀ nhận theo CẤU TRÚC, không theo giá trị thuộc tính.
        #
        # `markup.py` viết `data-cell="colhdr"`; model viết `data-cell` trần --
        # lời dặn chỉ đòi có thuộc tính, không đòi giá trị, và `repair.cells()`
        # thêm vào cũng chỉ thế. So `== "colhdr"` thì mọi ô tiêu đề của trang
        # model rơi xuống làm ô thân bảng: đo được trên pilot9, cột nào cũng
        # `header: {"value": ""}` và hàng đầu thành một "group" mang chữ "STT".
        #
        # Nằm trong `<thead>` LÀ tiêu đề cột. Giữ nguyên phép so cũ khi thuộc
        # tính có giá trị, để trang engine không đổi một li.
        if cell["head"] and cell["kind"] in (None, "", "colhdr") \
                and cell["col"] is not None:
            heads.setdefault((page, cell.get("table", 0)), []).append(
                (cell, entity))
        # Không gác bằng `BY_KIND` nữa: MỌI ô thân bảng có chỉ số cột đều vào
        # KIE. Một cột model tự nghĩ ra vẫn là một cột có mực và có tiêu đề.
        elif not cell["head"] and cell["col"] is not None:
            cells.append((page, cell, entity))

    out = []
    for page, cell, entity in cells:
        column = cell["col"]
        # Ô TRẢI NHIỀU CỘT KHÔNG THUỘC CỘT NÀO.
        #
        # `<td colspan="4">TỔNG CỘNG TIỀN TẠM ỨNG</td>` bắt đầu ở cột 0, và cột
        # 0 là "STT" -- nên bản trước gọi nó là `stt_r9` với giá trị "TỔNG CỘNG
        # TIỀN TẠM ỨNG". Đo trên `data/test1`: 13 trên 32 tài liệu dính, tức
        # 41%, và mọi ca đều là dòng tổng trong `<tfoot>` hoặc dòng tiêu đề
        # nhóm giữa thân bảng.
        #
        # Một ô trải bốn cột không phải giá trị của cột đầu tiên nó chạm vào --
        # nó là NHÃN CỦA CẢ DÒNG. Nên nó lấy tên từ chính `kind` của nó, và
        # không lấy tiêu đề cột làm key: không có tiêu đề cột nào tả được nó.
        #
        # Xét `colspan` chứ không xét chữ: một cái luật dò "TỔNG" trong nội
        # dung là luật đọc tiếng Việt bằng danh sách từ, và nó trượt ngay ở
        # "TIỂU CỘNG KHỐI LƯỢNG THỰC HIỆN" hay một tờ tiếng Anh. `colspan` là
        # cấu trúc, và cấu trúc thì trình duyệt đã dàn xong.
        if (cell.get("colspan") or 1) > 1:
            name = BY_KIND.get(str(entity["kind"])) or _slug_col(
                str(entity["text"])) or "row_label"
            out.append({
                "field": f"{name}_r{cell['row']}",
                "column": None, "row": cell["row"],
                "column_index": column, "column_path": [],
                "key_text": "", "value_text": str(entity["text"]),
                "key_bbox": None, "value_bbox": _box(entity["bbox"]),
                "key_entity_index": None,
                "value_entity_index": entity["entity_index"],
                "page_number": page, "source": "table",
                "description": "Label that runs across the row, naming what "
                               "the figures beside it add up to.",
            })
            continue
        cover = [(h, e) for h, e in heads.get((page, cell.get("table", 0)), [])
                 if h["col"] <= column < h["col"] + h["colspan"]]
        cover.sort(key=lambda pair: pair[0]["tier"])
        head, head_entity = cover[-1] if cover else (None, None)
        key = BY_KIND.get(str(entity["kind"])) or "cell"
        spec = COLUMNS.get(key) or {}
        # TÊN CỘT LẤY TỪ TIÊU ĐỀ IN TRÊN TRANG, không từ bảng tra.
        #
        # `BY_KIND` gộp ba cột "Đơn vị kê khai", "Số đúng", "Chênh lệch" thành
        # một tên `amount`, nên ba ô khác nhau ra cùng `amount_r3` và hai cái
        # sau ghi đè cái đầu. Mà tờ giấy đã in sẵn thứ phân biệt chúng: chính
        # cái tiêu đề cột.
        #
        # Đây cũng là chỗ cột model TỰ NGHĨ RA hoạt động được: một cột "Ghi chú
        # kiểm tra" không có trong `BY_KIND` vẫn có tên, vì tên nó nằm trên
        # giấy. `BY_KIND` giữ lại để viết CÂU TẢ, không để gác cửa.
        named = _slug_col(str(head_entity["text"])) if head_entity else ""
        out.append({
            "field": f"{named or key}_r{cell['row']}",
            "column": key,
            "row": cell["row"],
            "column_index": column,
            "column_path": [str(e["text"]) for _, e in cover],
            "key_text": str(head_entity["text"]) if head_entity else "",
            "value_text": str(entity["text"]),
            "key_bbox": _box(head_entity["bbox"]) if head_entity else None,
            "value_bbox": _box(entity["bbox"]),
            "key_entity_index": head_entity["entity_index"] if head_entity else None,
            "value_entity_index": entity["entity_index"],
            "page_number": page,
            # BẢNG NÀO. `_Spans` đã đếm sẵn (`cell["table"]`) và `heads` đã gom
            # tiêu đề theo nó -- chỉ là con số ấy chưa bao giờ ra khỏi file
            # này. Người đọc cặp không có nó thì hai bảng trên cùng một trang
            # có cùng `(row, column)`, và bảng dưới ĐÈ lên bảng trên: đo trên
            # `data/pilot13`, tờ `insurance_partner_cert_application` mất 69
            # trên 273 cặp đúng vì thế, im lặng.
            "table_id": f"t{int(cell.get('table', 1) or 1)}",
            "description": spec.get("describe") or f"Table column {key}.",
            "description_source": "column",
            "source": "table",
        })
    return out


def _box(bbox) -> dict:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return {"x1": int(round(x1)), "y1": int(round(y1)),
            "x2": int(round(x2)), "y2": int(round(y2))}


def _stacked(key_box, value_box) -> bool:
    """Value có nằm ngay dưới key, cùng cột, không."""
    try:
        kx1, ky1, kx2, ky2 = (float(v) for v in key_box)
        vx1, vy1, vx2, vy2 = (float(v) for v in value_box)
    except (TypeError, ValueError):
        return False
    line = max(ky2 - ky1, 1.0)
    return (vy1 >= ky1 and vy1 - ky2 < line * 8
            and min(kx2, vx2) - max(kx1, vx1) > 0)


def extra_pairs(record: dict, page: int, used: set[int] | None = None) -> list[dict]:
    """Cặp `pipeline/kie.py` chưa biết mặt, và trường không có nhãn in."""
    ents = _on(record, page)
    used = set(used or ())
    out: list[dict] = []

    for key_kind, value_kind, name, description in PAIRED:
        keys = [e for e in ents if e["kind"] == key_kind]
        values = [e for e in ents if e["kind"] == value_kind]
        for k, v in zip(keys, values):
            used.add(k["entity_index"])
            used.add(v["entity_index"])
            out.append({
                "field": name or slug(str(k["text"])) or key_kind,
                "key_text": str(k["text"]),
                "value_text": str(v["text"]),
                "key_bbox": _box(k["bbox"]),
                "value_bbox": _box(v["bbox"]),
                "key_entity_index": k["entity_index"],
                "value_entity_index": v["entity_index"],
                "page_number": page,
                "description": description,
                "description_source": "rule",
                "source": "pair",
            })

    # `colhdr` nào chưa được dùng làm khoá của một ô bảng thì không phải tiêu
    # đề cột: nó là dòng tiêu đề NHÓM chạy hết chiều ngang ("Chi thường
    # xuyên") hoặc ô gom bên trái. Vẫn là chữ in ra, vẫn phải có mặt.
    body = [e for e in ents if str(e["kind"]) in BY_KIND]
    top = min((e["bbox"][1] for e in body), default=0.0)
    for entity in ents:
        if entity["kind"] != "colhdr" or entity["entity_index"] in used:
            continue
        above = body and entity["bbox"][3] <= top + 1
        out.append({
            "field": "column_heading" if above else "row_group",
            "key_text": "",
            "value_text": str(entity["text"]),
            "key_bbox": None,
            "value_bbox": _box(entity["bbox"]),
            "key_entity_index": None,
            "value_entity_index": entity["entity_index"],
            "page_number": page,
            "description": ("Heading of a table column."  if above else
                            "Name of the group of rows printed below it."),
            "description_source": "implied",
            "source": "implied",
        })
        used.add(entity["entity_index"])

    # KEY MỒ CÔI GHÉP VỚI VALUE MỒ CÔI CÙNG HỌ.
    #
    # `sign.title` ("ĐẠI DIỆN NGƯỜI NỘP THUẾ") mang `field_role="key"`, còn
    # `sign.name` ("Phạm Văn Tuấn") mang `field_role="value"` -- nhưng phép
    # ghép theo toạ độ không nối được hai cái, vì giữa chúng có dòng in sẵn
    # "(Ký, ghi rõ họ tên)" và một khoảng trống để ký tay. Kết quả đo được: ba
    # chức danh rơi khỏi KIE, và ba cái tên vào KIE không kèm vai của ai.
    #
    # Ghép ở đây theo HỌ của `kind` chứ không theo bảng tay: `sign.title` và
    # `sign.name` cùng họ `sign`, và trên một tờ giấy số chức danh luôn bằng
    # số người ký. Khi hai bên bằng nhau thì thứ tự đọc là thứ tự ghép -- chức
    # danh thứ nhất thuộc về người ký thứ nhất.
    #
    # Không bằng nhau thì KHÔNG ghép: một tờ có bốn chức danh và hai tên là
    # một tờ hai người chưa ký, và đoán xem ai khớp ai là đoán.
    loose: dict[str, dict[str, list]] = {}
    for entity in ents:
        if entity["entity_index"] in used:
            continue
        role = str(entity.get("field_role") or "")
        if role not in ("key", "value"):
            continue
        family = str(entity.get("kind") or "").split(".")[0]
        if not family:
            continue
        loose.setdefault(family, {"key": [], "value": []})[role].append(entity)
    for family, sides in loose.items():
        keys, values = sides["key"], sides["value"]
        if not keys or len(keys) != len(values):
            continue
        order = (lambda e: (e["bbox"][1], e["bbox"][0]))          # noqa: E731
        for k, v in zip(sorted(keys, key=order), sorted(values, key=order)):
            # CÙNG HỌ CHƯA ĐỦ -- PHẢI CÙNG CHỖ TRÊN GIẤY.
            #
            # `meta.label` và `meta.value` cùng họ `meta`, nên luật họ ghép
            # "Số: 12/BB-HĐSP" ở góc trái với "TP. Hồ Chí Minh, ngày 25 tháng 6
            # năm 2024" ở góc phải -- hai trường khác hẳn, chỉ chung một cái
            # tiền tố kind.
            #
            # Điều kiện: value nằm DƯỚI key và hai hộp CHỒNG NGANG nhau. Cửa sổ
            # dọc rộng (tám dòng) vì khối chữ ký thật có "(Ký, ghi rõ họ tên)"
            # và cả khoảng trống để ký tay chen giữa chức danh và tên.
            if not _stacked(k.get("bbox"), v.get("bbox")):
                continue
            used.add(k["entity_index"])
            used.add(v["entity_index"])
            out.append({
                "field": slug(str(k["text"])) or f"{family}_field",
                "key_text": str(k["text"]),
                "value_text": str(v["text"]),
                "key_bbox": _box(k["bbox"]),
                "value_bbox": _box(v["bbox"]),
                "key_entity_index": k["entity_index"],
                "value_entity_index": v["entity_index"],
                "page_number": page,
                "description": (implied_for(str(v.get("kind") or "")) or
                                ("", "Value printed under the label beside it."))[1],
                "description_source": "family",
                "source": "family",
            })

    for entity in ents:
        kind = str(entity.get("kind") or "")
        # NỬA KEY CỦA MỘT CẶP KHÔNG PHẢI MỘT TRƯỜNG. `meta.label`,
        # `invoice.field.label`, `store.address.label` là chữ nhãn in trước giá
        # trị -- chúng đã nằm trong `key_text` của chính cặp ấy. Dựng thêm
        # trường cho chúng là đếm một chỗ chữ hai lần: đo được `meta_label`
        # hai phần tử đứng cạnh `so_bien_ban` và `ky_kiem_tra` là giá trị của
        # chính hai cái nhãn ấy.
        #
        # Nhận biết bằng `field_role`, thứ `entities_from_words` đã tính --
        # không bằng đuôi `.label`, vì đuôi là hình thức còn vai là nghĩa.
        if str(entity.get("field_role") or "") == "key":
            continue
        # Chữ in sẵn không phải giá trị -- cùng luật `pipeline/kie.py::FURNITURE`
        # đã áp cho cặp có key. "(Ký, ghi rõ họ tên)" có mặt trên mọi tờ, giống
        # hệt nhau, nên nó mang đúng không bit thông tin nào.
        if kind in FURNITURE:
            continue
        if entity["entity_index"] in used or not implied_for(kind):
            continue
        name, description = implied_for(kind)
        out.append({
            "field": name,
            "key_text": "",
            "value_text": str(entity["text"]),
            "key_bbox": None,
            "value_bbox": _box(entity["bbox"]),
            "key_entity_index": None,
            "value_entity_index": entity["entity_index"],
            "page_number": page,
            "description": description,
            "description_source": "implied",
            "source": "implied",
        })
    return out


def declared_pairs_all(record: dict, markup: str) -> list[dict]:
    """`declared_pairs` cho mọi trang của tài liệu, gộp làm một."""
    pages = len(record.get("source_files") or [record.get("filename")]) or 1
    out: list[dict] = []
    for page in range(1, pages + 1):
        out.extend(declared_pairs(record, markup, page))
    return out


def complete(record: dict, markup: str = "") -> tuple[list[dict], dict]:
    """Danh sách cặp KIE ĐẦY ĐỦ cho cả tài liệu, và một bản đếm.

    Giữ nguyên các cặp `pipeline/kie.py` đã dựng -- chúng đúng, chỉ là chưa
    đủ -- rồi thêm phần thiếu. Cặp cũ không có `page_number`, nên nó được suy
    từ hộp từ của chính thực thể ấy."""
    # Chỉ giữ cặp GỐC của `pipeline/kie.py` làm nền. Chạy `derive.py` lần
    # thứ hai trên cùng một bộ mà lấy cả phần đã thêm làm nền thì mỗi ô bảng
    # có hai cặp, lần ba có ba -- và không gì báo, chỉ là file phình ra.
    # ĐƯỜNG KHAI ĐI TRƯỚC. `data-path` model tự khai là DANH TÍNH của trường;
    # nhãn in trên giấy là NGHĨA của nó. Một chỗ mực có cả hai thì nó vẫn là
    # MỘT trường mang hai tên cho hai mục đích -- không phải hai trường.
    #
    # Đo trên pilot12: 147 trên 766 chỗ mực (19%) mang hai trường, và mọi ca
    # đều cùng một hình: `ma_so_thue` (từ nhãn in) đứng cạnh `tax_code` (từ
    # `data-path`), cùng giá trị, cùng hộp. Đúng triệu chứng `F4` trong
    # `docs/kie-thiet-ke-nhan.md` gọi tên.
    #
    # Dựng đường khai trước rồi mới lấy cặp nhãn: cặp nhãn nào trỏ vào một
    # thực thể đã có đường dẫn thì KHÔNG thành trường thứ hai -- chữ in của nó
    # đi vào `printed_header` của chính trường ấy.
    claimed = declared_pairs_all(record, markup) if markup else []
    spoken = {p["value_entity_index"] for p in claimed
              if isinstance(p.get("value_entity_index"), int)}
    label_pairs = [dict(p) for p in (record.get("kie") or {}).get("pairs") or []
                   if p.get("source", "label") == "label"]
    for pair in label_pairs:
        index = pair.get("value_entity_index")
        if index in spoken:
            for owner in claimed:
                if owner.get("value_entity_index") == index:
                    printed = str(pair.get("key_text") or "").strip()
                    if printed:
                        owner.setdefault("printed_header", []).append(printed)
                        owner["key_text"] = printed
                        owner["key_bbox"] = pair.get("key_bbox")
                        owner["key_entity_index"] = pair.get("key_entity_index")
                    break
    pairs = claimed + [p for p in label_pairs
                       if p.get("value_entity_index") not in spoken]
    where: dict[int, int] = {}
    for word in record.get("word_annotations") or []:
        index = word.get("entity_index")
        if isinstance(index, int) and index not in where:
            where[index] = int(word.get("page_number", 1) or 1)
    for pair in pairs:
        pair.setdefault("page_number",
                        where.get(pair.get("key_entity_index"))
                        or where.get(pair.get("value_entity_index")) or 1)
        pair.setdefault("source", "label")

    table = table_pairs(record, markup) if markup else []
    # CÙNG LUẬT CHO Ô BẢNG. Một ô đã có `data-path` thì tiêu đề cột của nó là
    # NGHĨA, không phải một trường thứ hai: `vat_input` (khai) đứng cạnh
    # `don_vi_r2` (bảng) là một chỗ mực hai tên.
    #
    # Tiêu đề cột giàu thông tin hơn nhãn in thường -- nó mang cả đường dẫn
    # nhiều tầng (`column_path`) -- nên chép sang đủ cả.
    rest = []
    for cell in table:
        index = cell.get("value_entity_index")
        if index in spoken:
            for owner in claimed:
                if owner.get("value_entity_index") == index:
                    head = str(cell.get("key_text") or "").strip()
                    if head:
                        owner.setdefault("printed_header", []).append(head)
                        owner.setdefault("key_text", head)
                        owner.setdefault("key_bbox", cell.get("key_bbox"))
                    for carry in ("column", "column_index", "column_path",
                                  "row", "table_id"):
                        if cell.get(carry) is not None:
                            owner.setdefault(carry, cell[carry])
                    break
        else:
            rest.append(cell)
    pairs.extend(rest)
    # `declared_pairs` đã chạy ở đầu hàm và nằm sẵn trong `pairs`.
    # MỌI cặp đã có, không riêng cặp bảng. `extra_pairs` dựng trường cho những
    # run chưa ai nhận, và nó nhận biết "đã ai nhận chưa" qua `used`. Gieo
    # `used` chỉ từ bảng thì mọi run ĐÃ bắt được cặp từ nhãn in trên giấy vẫn
    # lọt vào đường implied lần thứ hai, và một chỗ chữ ra hai trường: đo được
    # `dia_chi` (tên lấy từ nhãn "Địa chỉ:") đứng cạnh `store_address` (tên lấy
    # từ `kind`), cùng một dòng địa chỉ.
    used = {p[k] for p in pairs for k in ("key_entity_index",
                                          "value_entity_index")
            if isinstance(p.get(k), int)}
    pages = len(record.get("source_files") or [record.get("filename")]) or 1
    for page in range(1, pages + 1):
        pairs.extend(extra_pairs(record, page, used))

    seen: set[int] = set()
    for pair in pairs:
        for key in ("key_entity_index", "value_entity_index"):
            if isinstance(pair.get(key), int):
                seen.add(pair[key])
    total = len(record.get("entity_annotations") or [])
    counts = {
        "pairs": len(pairs),
        "entities": total,
        "entities_in_kie": len(seen),
        "coverage": round(len(seen) / total, 4) if total else 0.0,
        "by_source": {},
    }
    for pair in pairs:
        counts["by_source"][pair.get("source", "label")] = \
            counts["by_source"].get(pair.get("source", "label"), 0) + 1
    return pairs, counts


__all__ = ["complete", "extra_pairs", "table_pairs"]
