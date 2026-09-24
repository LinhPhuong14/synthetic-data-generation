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
import json
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.kie import FURNITURE, describe as say, slug  # noqa: E402
from synthgen.phrasing import unique_says  # noqa: E402
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


@lru_cache(maxsize=1)
def _words_vi() -> dict:
    """`{token: từ tiếng Việt}` từ `rulebase/kie_words_vi.json`.

    Rỗng khi thiếu file: câu lùi về tiếng Anh như trước, kém hơn nhưng không
    hỏng. Cùng lệ `phrasing.POOL` và `design._blocks_yaml`."""
    path = REPO_ROOT / "rulebase" / "kie_words_vi.json"
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}
    table = got.get("words") if isinstance(got, dict) else None
    return {str(k): str(v) for k, v in (table or {}).items() if v}


_WORDS_VI = _words_vi()


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
    # BẢNG TRA ĐI TRƯỚC CỔNG `menu.`. Ô bảng nói chung đã vào `line_items` nên
    # cổng ấy đúng, nhưng `menu.barcode` và `menu.detail` có mục riêng trong
    # `IMPLIED` mà không bao giờ với tới được vì cổng chặn trước -- đo trên
    # `data/thu1k`: 100 mã vạch có hộp mà không vào một cặp KIE nào.
    if kind in IMPLIED:
        return IMPLIED[kind]
    if not kind or kind in NEVER or kind.startswith("menu."):
        return None
    parts = [w for w in re.split(r"[._]+", kind) if w]
    words = [_WORDS.get(w, w.replace("_", " ")) for w in parts]
    phrase = " ".join(w for w in words if w).strip() or kind
    # CÂU SINH RA PHẢI CÙNG THỨ TIẾNG VỚI BỘ DỮ LIỆU.
    #
    # Nhánh này chế một câu cho MỌI `kind` không có trong `IMPLIED`, nên câu
    # nó sinh không bao giờ khớp kho cách nói (`synthgen/phrasing.py`) -- mỗi
    # `kind` một câu riêng. `describe()` chỉ đổi giọng những câu CÓ trong kho,
    # nên câu ở đây đi thẳng ra bộ dữ liệu đúng như nó được viết.
    #
    # Trước bản sửa nó viết tiếng Anh ("Section body printed on the
    # document."), và vì thế `description_lang: vi` không với tới được: đo
    # trên `data/23-09-llm-g`, **66,6% câu tả ra tiếng Anh** và 658 trên 666
    # câu ấy đến từ đúng nhánh này.
    #
    # Dịch TỪNG TOKEN qua `rulebase/kie_words_vi.json` -- dữ liệu, không phải
    # mã. 86 token phủ hết 116 `kind` đã đo; token lạ giữ nguyên, nên câu vẫn
    # đọc được và chỉ lẫn một chữ tiếng Anh thay vì mất mô tả.
    #
    # Bỏ hẳn phần dịch và chỉ in `kind` thô thì câu thành "Giá trị của trường
    # `legal.basis`" -- tiếng Việt nhưng MẤT NGHĨA, trong khi bản tiếng Anh cũ
    # ít ra còn nói "Legal basis". Đổi một bệnh lấy bệnh khác không phải chữa.
    # ĐẢO THỨ TỰ TOKEN. Tiếng Việt là ngôn ngữ CHÍNH-TRƯỚC còn `kind` viết
    # theo lối Anh (`legal.basis` = "legal" bổ nghĩa cho "basis"), nên dịch
    # xuôi ra "Pháp lý căn cứ" -- đúng chữ, sai tiếng. Đảo lại thành "Căn cứ
    # pháp lý", và đó là phép biến đổi ĐÚNG cho mọi danh ngữ ghép chứ không
    # phải một mẹo cho vài ca.
    tail = parts[-1] if parts else ""
    core = parts[:-1] if tail == "label" and len(parts) > 1 else parts
    viet = " ".join(_WORDS_VI.get(w, _WORDS.get(w, w.replace("_", " ")))
                    for w in reversed(core)).strip()
    if not viet:
        return slug(kind), f"{phrase[:1].upper()}{phrase[1:]} in trên tờ giấy."
    # `.label` là NHÃN IN CỦA trường kia, không phải một trường riêng -- đúng
    # điều `agent/prompts/page.md` mục 9 khai. Nói ra quan hệ ấy, đừng dán
    # thêm một chữ "nhãn in" vào cuối danh ngữ ("nhãn in mã thuế đơn vị" đọc
    # như một thứ khác hẳn).
    # CHỈ `.label`. `.title` từng nằm ở đây và nó sai: `sign.title` là CHỨC
    # DANH người ký, không phải nhãn in của chữ ký. Một hậu tố nhập nhằng
    # không được làm luật -- `page.md` mục 9 nói `.label` là caption, và đó là
    # cái duy nhất không có ca ngược.
    if tail == "label" and len(parts) > 1:
        return slug(kind), f"Nhãn in của {viet}, in sẵn trên tờ giấy."
    return slug(kind), f"{viet[:1].upper()}{viet[1:]} in trên tờ giấy."


IMPLIED: dict[str, tuple[str, str]] = {
    "title": ("doc_title", "Main title of the document."),
    "subtitle": ("doc_subtitle", "Subtitle printed under the main title."),
    "note": ("note", "Note or condition printed on the document."),
    "footer": ("footer", "Footer line printed at the bottom of the page."),
    "period": ("period", "Billing or reporting period this document covers."),
    "masthead": ("masthead", "National heading printed above the title."),
    "masthead.motto": ("masthead_motto",
                       "Motto line printed under the national heading."),
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
    # `sheets/form.py::_checklist()` -- ghép theo VỊ TRÍ trong từng danh sách
    # `kind`, không theo thứ tự vẽ trong `ents`, nên tích vẽ TRƯỚC nhãn của nó
    # trên trang (đúng lệ ô tích) vẫn ghép đúng dòng: tích thứ N của trang đi
    # với nhãn thứ N. `name=None` nên trường lấy tên từ CHÍNH DÒNG CHỮ
    # (`slug(k["text"])`), chứ không phải một cái tên chung `survey_tick` --
    # đây chính là ca đo được 0/N cặp trước khi kind riêng này tồn tại.
    ("survey.checklist", "survey.tick", None,
     "Whether this checklist item was ticked."),
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
        self.cells: list[dict] = []
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
        # HAI BIẾN, VÌ CÓ HAI CÂU HỎI KHÁC NHAU.
        #
        # `_table` là bảng ĐANG mở -- phải trả về bảng cha khi một bảng con
        # đóng, nếu không ô còn lại của bảng cha bị gán sang bảng con.
        # `_table_seq` là SỐ HIỆU ĐÃ PHÁT -- không bao giờ trả lại, nếu không
        # bảng anh em thứ hai nhận đúng số hiệu của bảng thứ nhất.
        #
        # Bản trước chỉ có `_table`, và `handle_endtag` khôi phục nó từ ngăn
        # xếp. Hệ quả: mọi bảng ở TẦNG NGOÀI CÙNG đều mang số 1, trên mọi
        # trang. Chú thích ở `table_pairs` hứa "hai bảng trên cùng một trang
        # không đụng nhau vì `table_id` đã nằm trong id" -- lời hứa ấy không
        # được giữ, và 69 trên 273 cặp của
        # `insurance_partner_cert_application` mất đúng vì thế.
        self._table = 0         # bảng ĐANG mở
        self._table_seq = 0     # số hiệu lớn nhất đã phát trên trang này
        self._stack: list[tuple] = []   # bảng cha đang mở, khi có bảng lồng
        self._under = ""        # mặt hàng mà bảng con đang tả

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
            # Số hiệu bảng đánh lại theo TRANG -- `table_key()` đã ghép trang
            # vào id nên tính duy nhất không phụ thuộc chỗ này; đánh lại chỉ
            # để `p2t1` đọc lên đúng nghĩa "bảng đầu của trang 2".
            self._table = self._table_seq = 0
        elif tag == "table":
            # NGĂN XẾP, vì `<table>` LỒNG ĐƯỢC TRONG MỘT Ô.
            #
            # `markup.py` in dòng chi tiết của một mặt hàng bằng một bảng con
            # nằm ngay trong ô tên:
            #
            #     <td data-cell="menu.name" data-row="1" data-col="1">
            #       <span data-kind="menu.name">Tủ chữa cháy vách tường</span>
            #       <table class="sub"> ... menu.detail ... </table>
            #     </td>
            #
            # Bản trước tăng `_table` ở mọi thẻ `<table>` và reset con trỏ, rồi
            # KHÔNG trả lại gì khi `</table>` con đóng -- nên bảng cha mất con
            # trỏ dòng/cột từ mặt hàng đầu tiên có chi tiết trở đi, và mọi ô
            # sau đó bị gán sang bảng con.
            #
            # Đo trên `data/thu1k`: 11 trang có bảng con (86 cái), và trong bản
            # xuất 37/88 bảng (42%) không cột nào có tiêu đề, 212/458 cột
            # (46%) tiêu đề rỗng. Một tờ `bang_ke_chi_tiet` ra 8 bảng trong
            # khi mắt người đếm được 2.
            #
            # Ô ĐANG MỞ cũng phải giữ: bảng con nằm TRONG ô ấy, nên chữ trong
            # nó thuộc về ô cha chứ không phải một chỗ ngồi mới.
            # CHỦ THỂ của bảng con là chữ vừa in trong chính ô cha: span
            # `menu.name` đóng lại ngay trước `<table class="sub">`. Nhờ nó dòng
            # "Mã lô: LOT16433" nói được nó là chi tiết CỦA AI.
            self._under = (self.out[-1]["text"].strip()
                           if self.out and self.cell else self._under)
            self._stack.append((self._row, self._col, dict(self._held),
                                self._table, self.cell, self.in_head,
                                self.head_row, self._under))
            self._row, self._col, self._held = -1, 0, {}
            self._table_seq += 1
            self._table = self._table_seq
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
                # Chữ của chính ô, gom ở `handle_data`. Chỉ `table_structures`
                # đọc; `table_pairs` vẫn ghép qua span như cũ.
                "text": "",
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
                "page": self.sheet,
            }
            # MỘT con trỏ lưới, hai người đọc. `table_structures` cần MỌI ô,
            # `table_pairs` chỉ cần ô có span -- nhưng dựng con trỏ cột thứ
            # hai cho người đọc thứ hai là đúng lỗi nặng nhất kho này có: một
            # luật mà chỉ một chỗ biết. Ghi chung vào đây, cùng một phép tính.
            self.cells.append(self.cell)
        elif tag == "span" and "data-kind" in table:
            self.out.append({"page": self.sheet, "cell": self.cell,
                             # Nằm trong bảng con thì nói rõ của ai. `> 1` chứ
                             # không phải `if self._stack`: bảng NGOÀI CÙNG
                             # cũng đẩy một mục, nên phép thử kia đúng với mọi
                             # ô của mọi bảng -- đo được `menu.unit` "Chiếc"
                             # của bảng cha cũng đội `under`.
                             "under": self._under if len(self._stack) > 1 else "",
                             "kind": table["data-kind"], "text": "",
                             # ĐƯỜNG DẪN MODEL TỰ KHAI. Có nó thì KIE không
                             # phải suy trường nào đi với nhãn nào -- xem
                             # `declared_pairs`.
                             "path": table.get("data-path", ""),
                             # HARD NEGATIVE. `data-kind` của chính field
                             # model GIẢ LÀM -- xem `hard_negative_spans`
                             # dưới và `pipeline/fields.py::HardNegativeRecord`.
                             "decoy_for": table.get("data-decoy-for", "")})
            self._open = self.out[-1]

    def handle_data(self, data):
        # CHỮ của span, để ghép với thực thể theo NỘI DUNG thay vì theo số
        # lượng. Xem `table_pairs`.
        if getattr(self, "_open", None) is not None:
            self._open["text"] += data
        # Chữ của Ô. Một ô chứa span thì cả hai cùng cộng -- đúng: chữ của ô
        # LÀ chữ các span trong nó, và `table_structures` cần ô, không cần span.
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag == "table":
            # Trả con trỏ về bảng cha. Không có nhánh này thì bảng cha tiếp tục
            # đếm dòng/cột từ chỗ bảng con bỏ lại.
            if self._stack:
                (self._row, self._col, self._held, self._table, self.cell,
                 self.in_head, self.head_row, self._under) = self._stack.pop()
        elif tag == "thead":
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


# Ngưỡng gọi một bảng KHÔNG có `<thead>` là bảng dữ liệu. Đọc từ hình lưới,
# không từ chữ: một luật dò "TỔNG"/"STT" trong nội dung là luật đọc tiếng Việt
# bằng danh sách từ, và nó trượt ngay ở một tờ tiếng Anh.
DATA_TABLE_MIN_COLS = 2
DATA_TABLE_MIN_ROWS = 3


def table_structures(markup: str) -> list[dict]:
    """Khai CẤU TRÚC của từng bảng trên trang: vai, hình lưới, và từng ô.

    ## Vì sao cần

    `table_pairs` trả về QUAN HỆ (ô nào dưới tiêu đề nào) nhưng không trả về
    cái BẢNG. Không có bảng thì không chấm được TEDS/GriTS -- cả hai đều so
    hai lưới với nhau, và bên phải phải có một lưới để so.

    ## Vì sao KHÔNG canonicalize như PubTables-1M

    PubTables-1M phải gộp ô vì họ SUY NGƯỢC cấu trúc từ PDF đã in: một ô tiêu
    đề trải bốn cột hiện ra thành bốn ô lưới với ba ô trống, và nhiều cách đọc
    cùng hợp lệ -- ground truth tự mâu thuẫn. Ở đây cấu trúc do chính markup
    khai và Chromium dàn theo, nên không có gì để suy.

    Đo để chắc, trên 400 trang nhánh luật và 118 trang nhánh LLM: **0** ô tiêu
    đề trống, **0** ô tiêu đề `colspan>1`, **0** chuỗi "có chữ rồi trống" cùng
    tầng. Oversegmentation không xảy ra ở kho này.

    ## Cái mập mờ THẬT

    Không phải ô gộp, mà là BẢNG NÀO LÀ BẢNG. Đo bằng chính hàm này trên 400
    trang nhánh luật: **1.877 bảng, 4,7 mỗi trang**, và chỉ **52,2%** có
    `<thead>`. Còn lại **46,9%** là mảnh nối tiếp của một bảng bị cắt trang --
    không có `<thead>` vì tiêu đề nằm ở mảnh trước -- và **1,0%** là bảng dàn
    trang. Chấm TEDS một bảng dàn trang, hay chấm một mảnh nối tiếp như thể
    nó là bảng không tiêu đề, đều cho một con số vô nghĩa.

    Nên mỗi bảng khai `role` KÈM `role_basis` -- chứng cứ dẫn tới kết luận ấy.
    Người đọc không đồng ý với phép phân loại vẫn lọc lại được theo chứng cứ,
    thay vì phải tin một chữ `role` không truy được về đâu.
    """
    parser = _Spans()
    parser.feed(markup)
    parser.close()

    grouped: dict[tuple, list[dict]] = {}
    for cell in parser.cells:
        grouped.setdefault((cell["page"], cell["table"]), []).append(cell)

    out: list[dict] = []
    # Bảng có tiêu đề gần nhất, theo bề rộng: một mảnh nối tiếp giữ nguyên số
    # cột của bảng nó nối tiếp, nên bề rộng là dấu nhận biết rẻ và đúng.
    last_head_by_width: dict[int, str] = {}
    for (page, number), cells in sorted(grouped.items()):
        n_cols = max(c["col"] + c["colspan"] for c in cells)
        n_rows = len({c["row"] for c in cells})
        heads = [c for c in cells if c["head"]]
        if heads:
            role, basis = "data", "thead"
        elif n_cols >= DATA_TABLE_MIN_COLS and n_rows >= DATA_TABLE_MIN_ROWS:
            # Bảng dữ liệu mà tiêu đề ở đâu đó khác -- gần như luôn là mảnh
            # nối tiếp sau khi cắt trang. Vẫn là `data`: mực của nó là dữ
            # liệu, và bỏ nó đi là bỏ phần thân của mọi bảng dài.
            role, basis = "data", "grid"
        else:
            role, basis = "layout", "small"
        table_id = table_key(page, number)
        # MẢNH NỐI TIẾP TRỎ VỀ MẢNH MANG TIÊU ĐỀ.
        #
        # Chấm thì chấm TỪNG MẢNH: một ảnh là một trang, và model đọc trang 2
        # không nhìn thấy tiêu đề in ở trang 1 -- phạt nó vì thiếu tiêu đề là
        # phạt một thứ không có trong ảnh. Nhưng ai muốn dựng lại cả bảng dài
        # ở mức TÀI LIỆU thì phải có đường đi ngược, nếu không thông tin ấy
        # mất hẳn. Khai liên kết, để cả hai cách đọc cùng làm được.
        continues = last_head_by_width.get(n_cols) if basis == "grid" else None
        if basis == "thead":
            last_head_by_width[n_cols] = table_id
        out.append({
            "table_id": table_id,
            "page": page,
            "role": role,
            "role_basis": basis,
            "continues": continues,
            "header_tiers": (max(c["tier"] for c in heads) + 1) if heads else 0,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "cells": [{
                "row": c["row"], "col": c["col"],
                "colspan": c["colspan"], "rowspan": c["rowspan"],
                "is_header": bool(c["head"]),
                "tier": c["tier"],
                "text": _tight(c["text"]),
            } for c in sorted(cells, key=lambda c: (c["row"], c["col"]))],
        })
    return out


def table_key(page, number) -> str:
    """Id của một bảng, DUY NHẤT TRONG CẢ TÀI LIỆU.

    `_Spans` đếm bảng THEO TRANG, nên bảng đầu của mọi trang đều mang số 1.
    Với tài liệu một tờ điều ấy vô hại, và nó đã chạy thế từ đầu. Với tài liệu
    2-10 tờ -- thứ `run.py --pages` sinh ra hàng loạt -- bảng đầu trang 2 mang
    đúng id của bảng đầu trang 1, và `synthgen/export.py` gom theo `table_id`
    (mỗi id là MỘT bảng) nên hai bảng nhập làm một: cột số 1 của bảng dưới đè
    lên cột số 1 của bảng trên. Đo được: `table_structures` trả hai mục cho
    hai bảng hai trang, cả hai `t1`.

    Trang đi VÀO id chứ không đi cạnh id, vì `line_item_id` và `continues` đều
    là chuỗi đứng một mình -- một id không mang trang là một id không truy
    ngược được về đâu.

    Một hàm cho cả bốn chỗ phát id. Bốn bản chép `f"t{...}"` là bốn người dựng
    của cùng một luật, và sửa ba trong bốn là cách hỏng im lặng nhất."""
    return f"p{int(page or 1)}t{int(number or 1)}"


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
            # Cùng lẽ nhánh lùi của `implied_for`: câu lùi phải cùng thứ
            # tiếng với bộ, và nó tả TRƯỜNG chứ không tả cơ chế. "Value bound
            # to `x.y` in the document's own data tree" nói về cây dữ liệu --
            # một thứ không có trên tờ giấy và không giúp gì người đọc nhãn.
            "description": (_described(entity.get("kind"))
                            or f"Giá trị khai ở `{path}`, in trên tờ giấy."),
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

    # NHÃN CỦA TỪNG DÒNG, để câu tả của một ô nói được nó nằm ở dòng nào.
    #
    # Mọi ô của một cột dùng chung một câu tả là đúng cho CỘT nhưng sai cho Ô:
    # đo trên `data/thu1k`, 3 861 trên 3 915 ô bảng (99%) trùng câu với một ô
    # khác cùng trang, và đó là toàn bộ phần lặp còn lại của cả bộ nhãn. Thứ
    # phân biệt hai ô cùng cột đã in sẵn trên giấy: dòng của chúng.
    #
    # Nhãn dòng là ô có CHỮ, không phải số, ở cột trái nhất -- tức cột "tên
    # hàng"/"nội dung" mà mắt người cũng dùng để tìm dòng. Không có ô chữ nào
    # thì lùi về số thứ tự dòng, và cuối cùng là chỉ số.
    label_of: dict[tuple, str] = {}
    for page, cell, entity in cells:
        seat = (page, cell.get("table", 0), cell["row"])
        text = " ".join(str(entity.get("text") or "").split())
        if not text:
            continue
        # HẠNG của một ô làm nhãn dòng. Cao hơn thì thay.
        #
        #   2  CỤM TỪ có chữ -- "Tủ chữa cháy vách tường". Đây là cái tên.
        #   1  một khối có chữ -- "VT29808", "Lọ". Mã hàng hoặc đơn vị tính.
        #   0  toàn số.
        #
        # Không tách hai bậc trên thì bảng nào có cột mã đứng trước cột tên sẽ
        # đọc cả dòng theo mã: đo được 833/3 184 nhãn dòng (26%) là mã, và tệ
        # nhất là chính ô TÊN bị tả thành "Tên dịch vụ của “VT29808”" -- trong
        # khi cái tên nằm ngay trong ô ấy.
        letters = any(c.isalpha() for c in text)
        rank = 2 if letters and " " in text.strip() else (1 if letters else 0)
        old = label_of.get(seat)
        if old is None or rank > _rank_of(old):
            label_of[seat] = text
    # HAI DÒNG TRÙNG TÊN trong cùng một bảng là chuyện thường -- "Máy khoan bê
    # tông" mua hai lần. Khi ấy tên một mình không chỉ được dòng nào, nên nó
    # kèm số thứ tự. Chỉ kèm ở chỗ VA CHẠM: dòng có tên riêng vẫn đọc tự nhiên.
    crowd: dict[tuple, list[tuple]] = {}
    for seat, text in label_of.items():
        crowd.setdefault((seat[0], seat[1], text), []).append(seat)
    # `where` chứ không phải `seats`: `seats()` là HÀM cấp module đọc chỗ ngồi
    # từ markup, và một biến cùng tên trong hàm này che mất nó -- `table_pairs`
    # gọi `seats(markup)` ở ngay trên.
    for (_, _, text), where in crowd.items():
        if len(where) < 2:
            continue
        for seat in where:
            label_of[seat] = f"{text} (dòng {int(seat[2]) + 1})"

    # SỐ DÒNG THEO THỨ TỰ THẬT TRONG BẢNG, không lấy `data-row` cộng một.
    # `markup.py` của engine đánh `data-row` từ 1, còn lưới tự tính cho trang
    # model viết đánh từ 0 -- cộng một là đúng đường này và sai đường kia. Đo
    # được: ô "Camera quan sát ngoài trời" ở dòng đầu bảng mà câu tả ghi
    # "dòng 2". Xếp hạng các dòng của chính bảng ấy thì hai đường ra cùng một
    # con số, và đó cũng là con số mắt người đếm.
    order_of: dict[tuple, int] = {}
    for key in sorted({(p_, c.get("table", 0), c["row"]) for p_, c, _ in cells}):
        same = [k for k in order_of if k[0] == key[0] and k[1] == key[1]]
        order_of[key] = len(same) + 1

    seat_of = {e["entity_index"]: s.get("under", "") for e, s in pairs}

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
            table_id = table_key(page, cell.get('table', 1))
            out.append({
                "field": f"{name}_r{cell['row']}",
                "column": None, "row": cell["row"],
                "column_index": column, "column_path": [],
                "key_text": "", "value_text": str(entity["text"]),
                "key_bbox": None, "value_bbox": _box(entity["bbox"]),
                "key_entity_index": None,
                "value_entity_index": entity["entity_index"],
                "page_number": page, "source": "table",
                "table_id": table_id,
                "colspan": cell.get("colspan") or 1,
                "rowspan": cell.get("rowspan") or 1,
                "tier": cell.get("tier", -1),
                # Nhãn trải cả dòng KHÔNG phải một ô hàng hoá. Nó đặt tên cho
                # nhóm dòng bên dưới, nên nó không mang `line_item_id`: gộp nó
                # vào một dòng hàng là khai một món hàng không có thật.
                "row_kind": "label",
                "line_item_id": None,
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
            "key_bbox_px": _px_of(head_entity),
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
            "key_entity_index": head_entity["entity_index"] if head_entity else None,
            "value_entity_index": entity["entity_index"],
            "page_number": page,
            # BẢNG NÀO. `_Spans` đã đếm sẵn (`cell["table"]`) và `heads` đã gom
            # tiêu đề theo nó -- chỉ là con số ấy chưa bao giờ ra khỏi file
            # này. Người đọc cặp không có nó thì hai bảng trên cùng một trang
            # có cùng `(row, column)`, và bảng dưới ĐÈ lên bảng trên: đo trên
            # `data/pilot13`, tờ `insurance_partner_cert_application` mất 69
            # trên 273 cặp đúng vì thế, im lặng.
            "table_id": table_key(page, cell.get('table', 1)),
            # MẶT HÀNG CHA, khi ô này nằm trong bảng con của một ô. `export.py`
            # dùng nó để gắn dòng chi tiết về đúng dòng hàng, thay vì để bảng
            # con thành một bảng ngang hàng không tiêu đề.
            "under": str(seat_of.get(entity["entity_index"]) or ""),
            # CHỖ NGỒI ĐẦY ĐỦ. `row`/`column_index` một mình chưa đủ tả một ô:
            # `tier` nói ô tiêu đề nào ở tầng nào, `colspan`/`rowspan` nói ô
            # chiếm mấy chỗ. Không có ba khoá này thì người đọc nhãn không
            # dựng lại được cái lưới, và TEDS/GriTS thì so lưới với lưới.
            "tier": cell.get("tier", -1),
            "colspan": cell.get("colspan") or 1,
            "rowspan": cell.get("rowspan") or 1,
            "row_kind": "data",
            # LINE ITEM, theo lối DocILE (arXiv 2302.05658): mọi trường của
            # cùng một dòng hàng hoá mang cùng một id, và việc "gom trường
            # thành dòng hàng" (LIR) chấm được bằng chính id ấy. Ở đây id suy
            # ra từ chỗ ngồi -- không cần ai đặt tên, và hai bảng trên cùng
            # một trang không đụng nhau vì `table_id` đã nằm trong id.
            "line_item_id": f"{table_key(page, cell.get('table', 1))}#r{cell['row']}",
            "description": _detail_says(str(seat_of.get(entity["entity_index"]) or ""),
                                        str(entity["text"]))
            or _cell_says(
                spec.get("describe") or f"Table column {key}.",
                str(head_entity["text"]) if head_entity else "",
                label_of.get((page, cell.get("table", 0), cell["row"])),
                order_of.get((page, cell.get("table", 0), cell["row"]), 1),
                # Tầng trên của tiêu đề nhiều tầng: "Số lượng và đơn giá" bọc
                # "Đơn giá/ĐVT". Lá một mình không nói nó là đơn giá của cái gì.
                group=str(cover[-2][1]["text"]) if len(cover) > 1 else "",
                mine=str(entity["text"])),
            "description_source": "column",
            "source": "table",
        })
    return out


def _rank_of(text: str) -> int:
    """Hạng của một ô khi tranh làm NHÃN DÒNG.

        2  cụm từ có chữ -- "Tủ chữa cháy vách tường". Đây là một cái tên.
        1  một khối có chữ -- "VT29808", "Lọ". Mã hàng hoặc đơn vị tính.
        0  toàn số.

    Không tách hai bậc trên thì bảng nào có cột mã đứng trước cột tên sẽ đọc
    cả dòng theo mã: đo được 833/3 184 nhãn dòng (26%) là mã, và tệ nhất là
    chính ô TÊN bị tả thành "Tên dịch vụ của “VT29808”" -- trong khi cái tên
    nằm ngay trong ô ấy."""
    letters = any(c.isalpha() for c in text)
    return 2 if letters and " " in text.strip() else (1 if letters else 0)


def _detail_says(under: str, text: str) -> str:
    """Câu tả một dòng trong BẢNG CON nằm trong ô -- `""` nếu không phải.

    `markup.py` in chi tiết của một mặt hàng bằng `<table class="sub">` ngay
    trong ô tên, và mỗi dòng có dạng "nhãn: giá trị" -- 188/188 dòng trên
    `data/thu1k` đều thế. Nên câu tả đọc được cả hai vế:

        Chi tiết “Mã lô” của “Tủ chữa cháy vách tường”.

    Không có `under` thì đây không phải bảng con, trả rỗng để người gọi dùng
    câu tả ô bảng thường."""
    if not under:
        return ""
    label = str(text or "").split(":", 1)[0].strip()
    if label and label != str(text or "").strip():
        return f"Chi tiết “{label}” của “{under}”."
    return f"Dòng chi tiết của “{under}”."


def _cell_says(column_says: str, header: str, row_label: str | None,
               row: int, group: str = "", mine: str = "") -> str:
    """Câu tả của MỘT Ô bảng: ⟨nghĩa cột⟩ của ⟨chủ thể dòng⟩.

    Đọc như người nói: `Đơn giá của "Camera quan sát ngoài trời".` Hai vế đều
    lấy từ chữ IN TRÊN GIẤY -- tiêu đề cột và ô tên của dòng -- nên câu đúng ở
    mọi loại chứng từ mà không cần bảng tra nào.

    ## Vì sao thay hẳn, không nối thêm

    Bản trước giữ câu nghĩa cột rồi dán đuôi định danh:

        Name of the goods or service listed on this line.
        Ô này ở cột “Tên vật tư”, dòng “Cung cấp và lắp đặt hệ thống điện nhẹ”.

    Ba cái sai cùng lúc: thân tiếng Anh lẫn đuôi tiếng Việt trong một câu; câu
    dài gấp ba mà nửa sau chỉ để phân biệt; và với chính cột tên thì nhãn dòng
    BẰNG giá trị ô, nên nó đọc thành "tên hàng ... ở dòng ⟨chính nó⟩".

    Nghĩa đầy đủ của cột không mất: nó nằm ở `tables[].columns[].description`
    trong bản xuất, ghi MỘT lần cho cả cột. Chép nó vào bốn mươi ô là chép một
    câu bốn mươi lần.

    ## Bốn ca, bốn cách nói

    * ô thường ......... `Đơn giá của “Camera quan sát ngoài trời”.`
    * ô LÀ chủ thể ..... `Tên vật tư ở dòng 3.` -- không nói "X của X"
    * tiêu đề nhiều tầng `Đơn giá/ĐVT (nhóm “Số lượng và đơn giá”) của “...”.`
    * không có chủ thể . `Đơn giá ở dòng 3.` -- bảng toàn số
    """
    # Không có tiêu đề in thì gọi nó là "Ô", chứ không lấy câu nghĩa tiếng Anh
    # làm tên cột -- "Table column cell. của “Mã lô…”" không phải tiếng người.
    what = (header.strip().rstrip(":：") if header.strip() else "Ô")
    if group and group != what:
        what = f"{what} (nhóm “{group}”)"
    same = row_label and mine and " ".join(mine.split()) == " ".join(row_label.split())
    if row_label and not same:
        return f"{what} của “{row_label}”."
    return f"{what} ở dòng {int(row)}."


def _box(bbox) -> dict:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return {"x1": int(round(x1)), "y1": int(round(y1)),
            "x2": int(round(x2)), "y2": int(round(y2))}


def _px_of(entity) -> dict | None:
    """Bản PIXEL của hộp thực thể, hoặc `None` khi không có.

    `entity["bbox"]` đã ở hệ 0..1000 kể từ `pipeline/record.py::to_per_mille`;
    số pixel nằm ở `bbox_px` bên cạnh. Cặp KIE phải mang CẢ HAI, vì hai bên
    đọc nó hỏi hai câu khác nhau: bộ huấn luyện cần hệ chuẩn hoá, còn mọi thứ
    vẽ đè lên chính tấm ảnh -- `synthgen/overlay.py` -- cần pixel.

    Thiếu nó thì `overlay.py` lùi về `bbox` và vẽ số hệ 1000 như pixel: đo
    trên `bang_cau_hoi_benh_00078`, toàn bộ hộp dồn vào 1000 pixel trên cùng
    của một trang cao 1592. Nhãn vẫn đúng, chỉ tấm ảnh kiểm tra là sai -- và
    đó là tấm ảnh người ta nhìn để tin vào nhãn."""
    if not isinstance(entity, dict):
        return None
    raw = entity.get("bbox_px")
    return _box(raw) if raw else None


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


# Bảng hỏi: một khối là `number, question, (tick, option)*, prompt|answer`,
# phát ra theo đúng thứ tự ấy trong DOM. `SURVEY_UNDER` là những `kind` thuộc
# về câu hỏi gần nhất đứng TRƯỚC chúng.
SURVEY_QUESTION = "survey.question"
SURVEY_UNDER = {
    "survey.tick": "Ô tích",
    "survey.option": "Lựa chọn",
    "survey.answer": "Câu trả lời",
    "survey.prompt": "Lời nhắc",
    "survey.number": "Số thứ tự",
    "survey.colhdr": "Tiêu đề cột",
    "survey.rowhdr": "Tiêu đề dòng",
    "survey.cell": "Ô",
    "survey.char": "Ô ký tự",
}


def survey_pairs(ents: list[dict], page: int,
                 used: set[int] | None = None) -> list[dict]:
    """Ô tích, lựa chọn và câu trả lời, KHOÁ LÀ CÂU HỎI của chúng.

    ## Vì sao cần

    Trước luật này mọi `survey.tick` đi đường `implied` và nhận cùng một câu
    tả suy từ `kind`: đo trên `data/thu1k`, `"Questionnaire tick box printed
    on the document."` xuất hiện **5 477 lần**, và một trang bảng hỏi có 84 ô
    tích chỉ đọc lên được ~38 câu khác nhau -- trần của bảng biến thể. Thứ
    phân biệt hai ô tích không phải giọng văn, mà là **câu hỏi in trên chúng
    và lựa chọn in bên cạnh**; cả hai đều đã có mặt trên giấy.

    ## Ghép theo THỨ TỰ PHÁT, không theo toạ độ

    Một tờ bảng hỏi chia ba cột: câu 5 ở x=102, câu 8 ở x=390, câu 11 ở x=679,
    cả ba cùng y=52. Phép đo hình học phải đoán cột, và `kie_full` đã thử lối
    ấy hai lần rồi hỏng cả hai. Nhưng `entity_index` thì giữ nguyên thứ tự DOM,
    và markup phát trọn một khối câu hỏi rồi mới sang khối sau:

        47 number '5.' · 48 question 'Hình thức điều trị' · 49 tick '☐'
        50 option 'Nội khoa' · 51 tick '☒' · 52 option 'Vật lý trị liệu' ...

    Nên "câu hỏi gần nhất đứng trước" là một phép đọc, không phải một phỏng
    đoán -- cùng tín hiệu `pipeline/kie.py` dùng cho nhãn-kề-giá-trị.

    ## Ô tích lấy TÊN từ lựa chọn bên cạnh

    Khoá là câu hỏi, nhưng năm ô tích của một câu hỏi thì cùng khoá. Cái tách
    chúng là lựa chọn in ngay sau mỗi ô -- `☒` + "Vật lý trị liệu" -- nên tên
    trường và câu tả mang cả hai. Không có lựa chọn kề thì lùi về số thứ tự
    trong câu hỏi: thà một cái tên yếu còn hơn năm trường trùng tên.
    """
    used = set(used or ())
    out: list[dict] = []
    question: dict | None = None
    columns: list[str] = []            # `survey.colhdr` của câu hỏi đang mở
    row = ""                           # `survey.rowhdr` gần nhất
    at_column = 0                      # ô tích thứ mấy trong dòng ấy
    rank: dict[int, int] = {}
    numbered: dict | None = None       # `survey.number` chờ câu hỏi của nó
    deferred: set[int] = set()         # số đã được xếp lại, đừng giữ lần nữa

    order = sorted(ents, key=lambda e: int(e.get("entity_index") or 0))
    kinds = [str(e.get("kind") or "") for e in order]

    # Lựa chọn của một ô tích là `survey.option` phát NGAY SAU nó -- hình dạng
    # DANH SÁCH. Ma trận thì không có, và chỗ ngồi của ô tích ở đó là
    # (dòng, cột); xem vòng dưới.
    beside = {int(e["entity_index"]): str(order[i + 1].get("text") or "")
              for i, e in enumerate(order)
              if kinds[i] == "survey.tick" and i + 1 < len(order)
              and kinds[i + 1] == "survey.option"}
    # Lựa chọn của TỪNG câu hỏi, để biết một chữ có trùng trong phạm vi câu
    # hỏi ấy hay không.
    mates: dict[int, list[str]] = {}
    asked_at: dict | None = None
    for i, e in enumerate(order):
        if kinds[i] == SURVEY_QUESTION:
            asked_at = e
        elif kinds[i] == "survey.tick" and asked_at is not None:
            mates.setdefault(int(asked_at["entity_index"]), []).append(
                beside.get(int(e["entity_index"]), ""))

    # MỘT vòng, và số thứ tự được phát ngay lúc câu hỏi của nó mở -- không hàng
    # đợi, vì bối cảnh (cột, dòng, con trỏ) thuộc về câu hỏi đang mở và một
    # hàng đợi xử sau sẽ dùng bối cảnh của câu hỏi CUỐI CÙNG cho tất cả.
    todo: list[dict] = list(order)
    at = 0
    while at < len(todo):
        entity = todo[at]
        at += 1
        kind = str(entity.get("kind") or "")
        index = int(entity.get("entity_index") or 0)
        if kind == SURVEY_QUESTION:
            # Câu hỏi mới đóng lại mọi bối cảnh của câu trước: cột của bảng ma
            # trận này không phải cột của bảng kia.
            question, columns, row, at_column = entity, [], "", 0
            if numbered is not None:
                # Chèn ngay sau đây, để nó chạy với bối cảnh của CHÍNH câu hỏi
                # vừa mở. `deferred` để vòng sau đừng giữ lại nó lần nữa --
                # không có dấu ấy thì nhánh `survey.number` bắt lại chính nó và
                # số thứ tự không bao giờ ra: đo được 0/11 câu hỏi có số.
                todo.insert(at, numbered)
                deferred.add(int(numbered["entity_index"]))
                numbered = None
            continue
        if kind == "survey.number" and index not in deferred:
            # SỐ THỨ TỰ IN TRƯỚC CÂU HỎI CỦA NÓ: "5." rồi mới tới "Hình thức
            # điều trị đã áp dụng". Gán theo câu hỏi đang mở thì nó rơi vào câu
            # TRƯỚC -- đo được: câu hỏi thứ hai của một tờ đội số "3.".
            numbered = entity
            continue
        if kind not in SURVEY_UNDER or question is None:
            continue
        if kind == "survey.colhdr":
            columns.append(str(entity.get("text") or ""))
        elif kind == "survey.rowhdr":
            row, at_column = str(entity.get("text") or ""), 0

        asked = str(question.get("text") or "").strip()
        qi = int(question["entity_index"])
        rank[qi] = rank.get(qi, 0) + 1

        # CHỖ NGỒI của ô tích, hai hình dạng:
        #   danh sách  -- lựa chọn in ngay sau nó ("☒ Vật lý trị liệu")
        #   ma trận    -- dòng `survey.rowhdr` × cột `survey.colhdr` thứ mấy
        # Cả hai đều đọc từ thứ tự phát, không đoán theo toạ độ.
        seat, where = "", ""
        if kind == "survey.tick":
            seat = beside.get(index, "")
            if not seat and row:
                column = (columns[at_column] if at_column < len(columns)
                          else str(at_column + 1))
                at_column += 1
                seat, where = f"{row}__{column}", f" ở dòng “{row}”, cột “{column}”"
        elif kind == "survey.char":
            # Ô KÝ TỰ: một ô một chữ, "2|7|0|9|2|0|2|6". Thứ phân biệt chúng là
            # CHỖ ĐỨNG, không phải chữ bên trong -- ba ô cùng in "0" thì lấy
            # chữ làm tên là ba trường trùng tên, đo được 102 ca trên bộ.
            at_column += 1
            seat, where = str(at_column), f" thứ {at_column}"
        elif kind == "survey.cell" and row:
            seat = row
        if not seat and kind != "survey.tick":
            seat = str(entity.get("text") or "")
        if seat and not where:
            # Hai lựa chọn in cùng một chữ dưới cùng một câu hỏi ("Đã kiểm" hai
            # lần) thì chữ ấy không tách được chúng -- kèm thứ tự ở ĐÚNG chỗ va
            # chạm, chứ không kèm cho mọi lựa chọn.
            # SO TRONG CÙNG MỘT CÂU HỎI, không so cả trang. Câu tả đã nêu tên
            # câu hỏi, nên "Ô tích “Có” của câu hỏi “X”" chỉ trùng khi "Có" in
            # hai lần DƯỚI CHÍNH X. So cả trang thì mọi câu hỏi Có/Không đều
            # bị kèm số: đo được 1 888/11 115 câu (17%) đội "(thứ N)" trong khi
            # chỉ vài chục chỗ thật sự trùng.
            twice = sum(1 for other in mates.get(qi, []) if other == seat) > 1
            where = f" “{seat}”" + (f" (thứ {rank[qi]})" if twice else "")

        # Ô TÍCH giữ tên trần; mọi thứ khác đeo đuôi VAI của nó. Không có đuôi
        # ấy thì `☒` và chữ "Bảo vệ thu nhập" đứng cạnh nó ra cùng một tên
        # `muc_dich__bao_ve_thu_nhap` -- hai chỗ mực, một trường, và một cái
        # đè cái kia lúc xuất ra `json/`. Ô tích là CÂU TRẢ LỜI nên nó được
        # giữ tên gọn; lựa chọn và tiêu đề là chữ in sẵn của câu hỏi.
        tail = slug(seat)[:28] or str(rank[qi])
        if kind != "survey.tick":
            tail = f"{tail}__{kind.split('.')[-1]}"
        out.append({
            "field": (f"{slug(asked)[:34]}__{tail}" if asked
                      else f"{slug(kind)}_{rank[qi]}"),
            "key_text": asked,
            "value_text": str(entity.get("text") or ""),
            "key_bbox": _box(question["bbox"]),
            "key_bbox_px": _px_of(question),
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
            "key_entity_index": question["entity_index"],
            "value_entity_index": index,
            "page_number": page,
            "description": f"{SURVEY_UNDER[kind]}{where} của câu hỏi “{asked}”.",
            "description_source": "survey",
            "source": "survey",
            # CHỖ NGỒI KHAI RA, không để bên đọc suy ngược từ tên trường.
            # `synthgen/export.py` gom những cặp này thành mảng
            # `questions[].options[]`, và nó chỉ làm được thế nếu biết cặp nào
            # thuộc câu hỏi nào (`group`), đóng vai gì (`role`) và ngồi ở đâu
            # (`seat`). Tách chuỗi từ `field` để lấy lại ba thứ ấy là dựng luật
            # lần thứ hai ở một chỗ khác -- đúng kiểu lỗi kho này hay dính.
            "group": int(question["entity_index"]),
            "role": kind.split(".")[-1],
            "seat": seat,
            "rank": rank[qi],
        })
        used.add(index)
    return out


# Đoạn văn có TIÊU ĐỀ RIÊNG in ngay trước nó: `(kind tiêu đề, kind thân, lời tả)`.
# Cùng hình với `survey.question`, chỉ là một tiêu đề ăn đúng một thân.
HEADED = (("clause.head", "clause.body", "Nội dung điều khoản"),
          # Mục lục: tên mục rồi số trang của nó, phát liền nhau.
          ("toc.title", "toc.page", "Số trang của mục"))

# Đoạn văn TỰ ĐẶT TÊN: không có tiêu đề riêng, nhưng chữ của chính nó đủ phân
# biệt. "Căn cứ Luật Đất đai 2024" khác "Căn cứ Nghị định 43/2014" ngay ở dòng
# đầu, nên tên trường lấy từ đó chứ không phải `legal_basis_2`, `legal_basis_3`.
SELF_NAMED = {"legal.basis": "Căn cứ pháp lý"}


def clause_pairs(ents: list[dict], page: int,
                 used: set[int] | None = None) -> list[dict]:
    """Thân điều khoản, KHOÁ LÀ TIÊU ĐỀ của chính nó.

    Trước luật này `clause.head` và `clause.body` đều đi đường `implied` và
    nhận tên trường suy từ `kind`: mọi điều khoản của mọi tờ đều tên
    `clause_head`/`clause_body`, và câu tả giống hệt nhau. Đo trên `data/thu1k`
    sau khi đã chữa bảng hỏi, hai câu ấy vẫn là hai câu lặp nhiều nhất còn lại
    -- **904 lần mỗi câu**. Một tờ có hai mươi hai điều khoản thì hai mươi hai
    trường trùng tên, và bản xuất giữ lại đúng một.

    Thứ phân biệt chúng đã in sẵn trên giấy: "Điều 1. Thông báo sự kiện bảo
    hiểm" đứng ngay trên thân của nó. Đo trên cả bộ: **584 `clause.head`, mỗi
    cái theo sau đúng một `clause.body`** -- không một ca lệch. Nên phép ghép
    là đọc thứ tự phát, cùng tín hiệu `survey_pairs` dùng, không phải đo toạ độ.

    Tiêu đề KHÔNG thành trường riêng: nó đã nằm trong `key_text` của chính cặp
    này, và dựng thêm một trường cho nó là đếm một chỗ chữ hai lần -- luật
    `pipeline/kie.py` đã đặt cho `meta.label`, `invoice.field.label`.
    """
    used = set(used or ())
    out: list[dict] = []
    order = sorted(ents, key=lambda e: int(e.get("entity_index") or 0))
    kinds = [str(e.get("kind") or "") for e in order]
    taken: set[str] = set()

    def unique(base: str, fallback: str) -> str:
        name = base or fallback
        at = 2
        while name in taken:
            name, at = f"{base or fallback}_{at}", at + 1
        taken.add(name)
        return name

    for head_kind, body_kind, label in HEADED:
        for i, kind in enumerate(kinds):
            if kind != head_kind or i + 1 >= len(order):
                continue
            head, body = order[i], order[i + 1]
            if kinds[i + 1] != body_kind:
                continue
            if int(body["entity_index"]) in used:
                continue
            title = str(head.get("text") or "").strip()
            out.append({
                "field": unique(slug(title)[:44], slug(body_kind)),
                "key_text": title,
                "value_text": str(body.get("text") or ""),
                "key_bbox": _box(head["bbox"]),
                "key_bbox_px": _px_of(head),
                "value_bbox": _box(body["bbox"]),
                "value_bbox_px": _px_of(body),
                "key_entity_index": head["entity_index"],
                "value_entity_index": body["entity_index"],
                "page_number": page,
                "description": f"{label} “{title}”." if title else f"{label}.",
                "description_source": "clause",
                "source": "clause",
                # Cùng lẽ với `survey_pairs`: khai chỗ ngồi để `export.py` gom
                # thành `clauses[]` mà không phải tách chuỗi từ tên trường.
                "group": int(head["entity_index"]),
                "role": "body",
            })
            used.add(int(body["entity_index"]))
            used.add(int(head["entity_index"]))

    for entity in order:
        kind = str(entity.get("kind") or "")
        if kind not in SELF_NAMED or int(entity["entity_index"]) in used:
            continue
        text = str(entity.get("text") or "").strip()
        out.append({
            "field": unique(slug(text)[:44], slug(kind)),
            "key_text": "",
            "value_text": text,
            "key_bbox": None,
            "key_bbox_px": None,
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
            "key_entity_index": None,
            "value_entity_index": int(entity["entity_index"]),
            "page_number": page,
            "description": f"{SELF_NAMED[kind]}: “{text[:80]}”." if text
                           else f"{SELF_NAMED[kind]} in trên tờ giấy.",
            "description_source": "clause",
            "source": "clause",
            "group": int(entity["entity_index"]),
            "role": "basis",
        })
        used.add(int(entity["entity_index"]))
    return out


def label_pairs(ents: list[dict], page: int,
                used: set[int] | None = None, layout_id: str = "") -> list[dict]:
    """Nhãn in `X.label` đứng NGAY TRƯỚC giá trị `X` của nó.

    `pipeline/kie.py` ghép cặp này qua `key_entity_index` mà
    `entities_from_words` tính -- nhưng khi phép ấy không nối được thì nhãn
    thành mồ côi và giá trị vào KIE không kèm chữ in trên giấy. Đo trên
    `data/thu1k`: 43 nhãn mồ côi, và mọi ca đều cùng một hình --

        3 store.address.label 'Địa chỉ:'   ·  4 store.address '386 Nguyễn Trãi...'
        5 store.phone.label   'Điện thoại:' ·  6 store.phone   '0894306424'

    Luật đọc từ chính `kind`: nhãn của `store.address` là `store.address.label`,
    không phải một bảng tra. Đòi hai điều kiện cùng lúc -- ĐÚNG KIND và KỀ NHAU
    trong thứ tự phát -- nên một nhãn không có giá trị đi kèm thì không vớ
    nhầm run kế tiếp, đúng lỗi `80f69a6e` đã chữa cho đường khác."""
    used = set(used or ())
    out: list[dict] = []
    order = sorted(ents, key=lambda e: int(e.get("entity_index") or 0))
    for at, entity in enumerate(order[:-1]):
        kind = str(entity.get("kind") or "")
        if not kind.endswith(".label"):
            continue
        value = order[at + 1]
        if str(value.get("kind") or "") != kind[: -len(".label")]:
            continue
        if int(value["entity_index"]) in used or int(entity["entity_index"]) in used:
            continue
        printed = str(entity.get("text") or "").strip()
        # CÂU TẢ ĐI QUA `pipeline.kie.describe`, không lấy thẳng `implied_for`.
        #
        # `describe` tra bốn nguồn theo thứ tự: file `VLM_KIE_DESCRIPTIONS`
        # (`kie_descriptions.json` mà `synthgen/run.py` ghi đầu mỗi lượt), rồi
        # `rulebase/kie_glossary`, rồi chính chữ in, rồi nhãn lớp. Lấy thẳng
        # `implied_for` là bỏ qua hai nguồn đầu -- đo được: file khai
        # `dia_chi -> "Registered address of the seller."` trong khi cặp thật
        # nhận một câu suy từ `kind`. Một bảng mô tả viết ra rồi không ai đọc.
        named = implied_for(str(value.get("kind") or "")) or ("field", "")
        field_name = slug(printed.rstrip(":：")) or named[0]
        says, whence = say(field_name, caption=printed,
                           kind=str(value.get("kind") or ""),
                           layout=layout_id)
        out.append({
            "field": field_name,
            "key_text": printed,
            "value_text": str(value.get("text") or ""),
            "key_bbox": _box(entity["bbox"]),
            "key_bbox_px": _px_of(entity),
            "value_bbox": _box(value["bbox"]),
            "value_bbox_px": _px_of(value),
            "key_entity_index": entity["entity_index"],
            "value_entity_index": int(value["entity_index"]),
            "page_number": page,
            "description": says or named[1] or f"Giá trị in cạnh nhãn “{printed}”.",
            "description_source": whence or "label",
            "source": "label",
        })
    return out


def sign_pairs(ents: list[dict], page: int,
               used: set[int] | None = None) -> list[dict]:
    """Khối chữ ký: CHỨC DANH là khoá, tên người ký là giá trị.

    ## Vì sao không dùng phép ghép theo họ

    `extra_pairs` có sẵn một luật ghép `sign.title ↔ sign.name` theo họ `kind`,
    nhưng nó đòi HAI BÊN BẰNG NHAU. Một tờ bảng lương có bốn ô ký mà mới ba
    người ký thì luật ấy từ chối cả bốn, và cả ba cái tên rơi xuống đường
    `implied` -- thành ba trường cùng tên `signer_name`, không cái nào biết
    mình là kế toán hay giám đốc. Đo trên `data/thu1k`: mọi khối chữ ký trong
    bản xuất đều chỉ có `name`, không một `title` nào.

    ## Thứ tự phát đã nói đủ

    `markup.py` phát trọn một ô ký rồi mới sang ô sau:

        79 sign.title 'NGƯỜI LẬP BẢNG' · 80 sign.note · 81 sign.name 'Nguyễn Văn Hùng'
        82 sign.title 'PHÒNG NHÂN SỰ'  · 83 sign.note · 84 sign.name 'Ngô Thị Hồng Nhung'
        88 sign.title 'GIÁM ĐỐC'       · 89 sign.note            <- chưa ai ký

    Nên một khối là "từ `sign.title` này tới `sign.title` kế tiếp". Số chức
    danh không cần bằng số tên: ô chưa ký đơn giản là khối không có `sign.name`,
    và đó là một sự thật của tờ giấy chứ không phải một ca phải bỏ qua.

    `sign.note` -- "(Ký, ghi rõ họ tên)" -- không vào đây: nó in giống hệt dưới
    mọi ô ký nên mang đúng không bit thông tin nào, và `FURNITURE` đã nhận nó.
    """
    used = set(used or ())
    out: list[dict] = []
    order = sorted(ents, key=lambda e: int(e.get("entity_index") or 0))
    blocks: list[tuple[dict, list[dict]]] = []
    for entity in order:
        kind = str(entity.get("kind") or "")
        if kind == "sign.title":
            blocks.append((entity, []))
        elif kind == "sign.name" and blocks:
            blocks[-1][1].append(entity)

    taken: set[str] = set()
    for title, names in blocks:
        role = str(title.get("text") or "").strip()
        base = slug(role)[:40] or "signer"
        for at, name in enumerate(names):
            if int(name["entity_index"]) in used:
                continue
            field, suffix = base, 2
            while field in taken:
                field, suffix = f"{base}_{suffix}", suffix + 1
            taken.add(field)
            out.append({
                "field": field,
                "key_text": role,
                "value_text": str(name.get("text") or ""),
                "key_bbox": _box(title["bbox"]),
                "key_bbox_px": _px_of(title),
                "value_bbox": _box(name["bbox"]),
                "value_bbox_px": _px_of(name),
                "key_entity_index": title["entity_index"],
                "value_entity_index": int(name["entity_index"]),
                "page_number": page,
                "description": (f"Họ tên người ký ở ô “{role}”." if role
                                else "Họ tên người ký."),
                "description_source": "sign",
                "source": "sign",
                "group": int(title["entity_index"]),
                "role": "name",
                "rank": at + 1,
            })
        if names:
            continue
        # Ô KÝ CHƯA CÓ NGƯỜI KÝ vẫn là một khối trên giấy: chức danh có in,
        # có hộp. Bỏ nó đi thì bản xuất khai tờ này có ba ô ký trong khi mắt
        # người đếm được bốn.
        if int(title["entity_index"]) in used:
            continue
        field, suffix = base, 2
        while field in taken:
            field, suffix = f"{base}_{suffix}", suffix + 1
        taken.add(field)
        out.append({
            "field": field,
            "key_text": "",
            "value_text": role,
            "key_bbox": None,
            "key_bbox_px": None,
            "value_bbox": _box(title["bbox"]),
            "value_bbox_px": _px_of(title),
            "key_entity_index": None,
            "value_entity_index": int(title["entity_index"]),
            "page_number": page,
            "description": f"Ô ký mang chức danh “{role}”, chưa có tên người ký.",
            "description_source": "sign",
            "source": "sign",
            "group": int(title["entity_index"]),
            "role": "role_only",
            "rank": 1,
        })
    return out



# Nguồn cặp nào gom thành MẢNG thay vì thành trường phẳng.
GROUPED = {"clause", "survey", "sign"}

# Ký tự nói ô ĐÃ ĐƯỢC TÍCH. Đọc từ chính chữ in ra, không từ một cờ bên ngoài:
# mô hình nhìn tờ giấy cũng chỉ có ngần ấy để đọc.
TICKED_MARKS = frozenset("☒☑✔✓x✗X")

# Vai nào trong một câu hỏi bảng hỏi đi vào đâu. `tick` và `option` ghép thành
# MỘT lựa chọn (ô tích + nhãn của nó), nên chúng không có mục riêng ở đây.
SURVEY_SLOT = {"number": "number", "answer": "answers", "prompt": "prompts",
               "colhdr": "columns", "rowhdr": "rows", "cell": "cells",
               "char": "chars"}


def group_lists(pairs: list[dict], render, field_types: dict | None = None
                ) -> dict[str, list]:
    """Những thứ LẶP LẠI trên một tờ, gom thành mảng có cấu trúc.

    ## Vì sao không phải trường phẳng

    Hai mươi hai điều khoản trên một tờ từng thành hai mươi hai trường tên
    `clause_body`, rồi -- sau khi lấy tiêu đề làm khoá -- thành hai mươi hai
    trường tên `dieu_1_thong_bao_su_kien_bao_hiem`, `dieu_2_tam_ung`, ... Cái
    sau đã phân biệt được, nhưng TÊN TRƯỜNG LÀ CHÍNH NỘI DUNG: khoá JSON đổi
    theo từng tờ giấy, nên không mô hình nào học được một hình dạng cố định,
    và một bộ sinh có ràng buộc không biết trước khoá nào sẽ tới.

    Mảng tách hai thứ ấy ra: **tên khoá là VAI** (`title`, `body`, `label`,
    `ticked`) -- đóng, cố định, giống nhau ở mọi tờ -- còn **nội dung nằm ở
    giá trị**. Đúng hình `line_items` đã dùng cho bảng, và đúng luật "lặp thì
    thành mảng" của `docs/kie-schema-v2.md`.

    ## MỘT luật, hai người vẽ

    `render(pair, side)` quyết định một ô trông như thế nào: `synthgen/export.py`
    vẽ `{value, bbox}`, còn `synthgen/kie_schema.py` chỉ lấy chữ -- schema không
    mang toạ độ. Phép GOM thì chỉ có ở đây.

    `field_types` -- tuỳ chọn, `{entity_index: field_type}` từ
    `pipeline/record.py::field_type_for` -- cho MỘT câu hỏi biết nó là
    `boolean_choice` hay `multi_choice`. Tra theo `key_entity_index` của
    chính câu hỏi (thực thể mọi tích/lựa chọn trong nhóm đều trỏ `key_entity_index`
    về), không theo từng ô tích riêng: cả nhóm là MỘT trường, không phải một
    trường cho mỗi lựa chọn. Bỏ trống thì `question` không mang khoá này --
    lùi về `synthgen/kie_schema.py`, nơi chưa cần nó.

    ## Chỗ ngồi đọc từ nhãn, không tách từ tên trường

    Chính file này khai sẵn `group` (thuộc câu hỏi / điều khoản nào),
    `role` (đóng vai gì) và `seat` (ngồi ở đâu trong câu hỏi ấy). Ở đây chỉ
    còn việc xếp chúng lại.
    """
    out: dict[str, list] = {"clauses": [], "questions": [], "legal_basis": [],
                            "signatures": []}
    groups: dict[tuple, list[dict]] = {}
    for pair in pairs:
        groups.setdefault((str(pair.get("source")), pair.get("group")),
                          []).append(pair)

    for (source, _), members in groups.items():
        if source == "clause":
            basis = [p for p in members if p.get("role") == "basis"]
            for pair in basis:
                # Khoá có TÊN (`ground`), không bung ô ra thẳng phần tử:
                # `render` trả dict ở bản xuất nhưng trả chuỗi ở schema, và
                # `**` trên một chuỗi thì vỡ. Mọi mảng khác ở đây đã đặt tên
                # cho ô của nó; chỗ này là chỗ duy nhất quên.
                out["legal_basis"].append({
                    "index": len(out["legal_basis"]) + 1,
                    "ground": render(pair, "value"),
                    "description": str(pair.get("description", "")),
                })
            body = next((p for p in members if p.get("role") == "body"), None)
            if body:
                out["clauses"].append({
                    "index": len(out["clauses"]) + 1,
                    "title": render(body, "key"),
                    "body": render(body, "value"),
                    "description": str(body.get("description", "")),
                })
            continue

        if source == "sign":
            # KHỐI CHỮ KÝ. `role_only` là ô ký chưa ai ký -- chức danh nằm ở
            # nửa GIÁ TRỊ của cặp ấy vì không có tên nào để làm giá trị; ô đã
            # ký thì chức danh là khoá. Không tách hai ca này thì "NGƯỜI LẬP
            # BẢNG" rơi vào `questions` và thành một câu hỏi.
            for pair in sorted(members, key=lambda p: int(p.get("rank") or 0)):
                alone = pair.get("role") == "role_only"
                out["signatures"].append({
                    "index": len(out["signatures"]) + 1,
                    "signer_role": render(pair, "value" if alone else "key"),
                    "signer_name": None if alone else render(pair, "value"),
                    "signed": not alone,
                    "description": str(pair.get("description", "")),
                })
            continue

        # BẢNG HỎI. Ô tích và nhãn của nó cùng một `seat`, nên chúng ghép lại
        # thành MỘT lựa chọn: `{label, ticked, checked}`. `checked` là thứ
        # người ta thật sự hỏi tờ giấy, và nó đọc được từ chính ký tự in ra --
        # `☒` là đã tích, `☐` là chưa.
        question = {"index": len(out["questions"]) + 1,
                    "question": render(members[0], "key"),
                    "options": []}
        if field_types is not None:
            anchor = members[0].get("key_entity_index")
            found = field_types.get(anchor) if isinstance(anchor, int) else None
            if found:
                question["field_type"] = found
        seats: dict[str, dict] = {}
        for pair in sorted(members, key=lambda p: int(p.get("rank") or 0)):
            role = str(pair.get("role") or "")
            cell = render(pair, "value")
            if role in ("tick", "option"):
                seat = seats.setdefault(str(pair.get("seat") or len(seats)),
                                        {"index": len(seats) + 1})
                if role == "tick":
                    seat["ticked"] = cell
                    # `render` vẽ ô theo cách của người gọi -- dict `{value,
                    # bbox}` ở bản xuất, chuỗi trần ở schema. Đọc dấu tích phải
                    # chịu được cả hai.
                    mark = cell.get("value") if isinstance(cell, dict) else cell
                    seat["checked"] = bool(TICKED_MARKS.intersection(str(mark or "")))
                else:
                    seat["label"] = cell
                continue
            slot = SURVEY_SLOT.get(role)
            if not slot:
                continue
            if slot == "number":
                question["number"] = cell
            else:
                question.setdefault(slot, []).append(cell)
        question["options"] = list(seats.values())
        out["questions"].append(question)

    out["questions"].sort(key=lambda q: q["index"])
    return out



def extra_pairs(record: dict, page: int, used: set[int] | None = None,
                layout_id: str = "") -> list[dict]:
    """Cặp `pipeline/kie.py` chưa biết mặt, và trường không có nhãn in."""
    ents = _on(record, page)
    used = set(used or ())
    out: list[dict] = []

    # BẢNG HỎI ĐI TRƯỚC đường `implied`: ô tích nào đã có câu hỏi làm khoá thì
    # không rơi xuống nhánh suy-từ-`kind` để nhận một câu tả dùng chung nữa.
    asked = survey_pairs(ents, page, used)
    for pair in asked:
        used.add(int(pair["value_entity_index"]))
    out.extend(asked)

    # ĐIỀU KHOẢN cũng đi trước đường `implied`, cùng lẽ: thân nào đã có tiêu đề
    # của chính nó làm khoá thì thôi nhận cái tên `clause_body` dùng chung.
    # Tiêu đề bị đánh dấu `used` luôn -- nó là nửa khoá, không phải trường.
    headed = clause_pairs(ents, page, used)
    for pair in headed:
        used.add(int(pair["value_entity_index"]))
        if isinstance(pair.get("key_entity_index"), int):
            used.add(int(pair["key_entity_index"]))
    out.extend(headed)

    # KHỐI CHỮ KÝ đi trước phép ghép theo họ ở dưới: luật kia đòi số chức danh
    # bằng số tên và từ chối cả tờ khi lệch, còn luật này đọc từng khối nên một
    # ô chưa ký không làm hỏng ba ô đã ký.
    beside = label_pairs(ents, page, used, layout_id)
    for pair in beside:
        used.add(int(pair["value_entity_index"]))
        used.add(int(pair["key_entity_index"]))
    out.extend(beside)

    signed = sign_pairs(ents, page, used)
    for pair in signed:
        used.add(int(pair["value_entity_index"]))
        if isinstance(pair.get("key_entity_index"), int):
            used.add(int(pair["key_entity_index"]))
    out.extend(signed)

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
                "key_bbox_px": _px_of(k),
                "value_bbox": _box(v["bbox"]),
                "value_bbox_px": _px_of(v),
                "key_entity_index": k["entity_index"],
                "value_entity_index": v["entity_index"],
                "page_number": page,
                # Câu tả TRÍCH CHỮ IN, cùng lẽ `survey_pairs`/`clause_pairs`:
                # một câu cố định thì mọi cặp `checks` của một trang mang y hệt
                # nhau và không câu nào chỉ được cặp nào.
                "description": (f"{description[:-1]} — “{str(k['text']).strip()}”."
                                if str(k.get("text") or "").strip()
                                and description.endswith(".") else description),
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
            "key_bbox_px": None,
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
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
                "key_bbox_px": _px_of(k),
                "value_bbox": _box(v["bbox"]),
                "value_bbox_px": _px_of(v),
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
            "key_bbox_px": None,
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
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
    layout_id = str((record.get("extracted") or {}).get("doc_type") or "")
    pages = len(record.get("source_files") or [record.get("filename")]) or 1
    out: list[dict] = []
    for page in range(1, pages + 1):
        out.extend(declared_pairs(record, markup, page))
    return out


def hard_negative_spans(record: dict, markup: str, page: int) -> list[dict]:
    """Mọi span model tự khai là DECOY -- `data-decoy-for="<kind mục tiêu>"`.

    Phase 6 (`docs/ke-hoach-refactor-engine.md`). Cùng cách ghép span-với-
    thực-thể như `declared_pairs` (`zip`, theo đúng thứ tự DOM -- track 3
    đã đo 60/60 khớp một-một, xem docstring `synthgen/kie_full.py::_Spans`),
    và cùng lý do không cần đoán: model tự khai đường dẫn, chỗ này tự khai
    "tôi đang giả làm field nào".

    KHÔNG khai `strategy` ở đây -- `data-decoy-for` chỉ cần nói RÕ mục tiêu;
    chiến lược (lexical/format/...) đã có sẵn ở `DocumentPlan.hard_negative_
    profile` (Phase 4.1, engine tự rút trước khi hỏi model) và
    `pipeline/fields.py::hard_negatives()` ghép hai nguồn lại -- không hỏi
    model khai trùng thứ engine đã biết."""
    spans = seats(markup)
    ents = _on(record, page)
    out = []
    for span, entity in zip(spans, ents):
        decoy_for = str(span.get("decoy_for") or "").strip()
        if not decoy_for:
            continue
        out.append({
            "target_kind": decoy_for,
            "negative_kind": str(span.get("kind") or ""),
            "path": str(span.get("path") or ""),
            "text": str(entity.get("text") or ""),
            "value_bbox": _box(entity["bbox"]),
            "value_bbox_px": _px_of(entity),
            "value_entity_index": entity["entity_index"],
            "page_number": page,
        })
    return out


def hard_negative_spans_all(record: dict, markup: str) -> list[dict]:
    """`hard_negative_spans` cho mọi trang, gộp làm một."""
    layout_id = str((record.get("extracted") or {}).get("doc_type") or "")
    pages = len(record.get("source_files") or [record.get("filename")]) or 1
    out: list[dict] = []
    for page in range(1, pages + 1):
        out.extend(hard_negative_spans(record, markup, page))
    return out


# AI THẮNG KHI HAI ĐƯỜNG CÙNG TRỎ VÀO MỘT Ô MỰC. Số nhỏ thắng.
#
# `declared` (đường dẫn model tự khai) đứng đầu vì đó là DANH TÍNH, không
# phải đoán. `table` đứng ngay sau vì nó đọc CHỖ NGỒI THẬT từ markup trình
# duyệt đã dàn -- cũng không đoán. `label`/`pair`/`family` đều là adjacency:
# đoán bằng khoảng cách trên giấy, và tự thân đã đo sai 30%
# (`pipeline/record.py::_bind_entities`). `implied` đứng cuối vì nó chỉ là
# `kind` không có gì để đối chiếu.
_SOURCE_PRIORITY = {"declared": 0, "table": 1, "label": 2, "pair": 3,
                    "family": 3, "implied": 4}


def _dedup_by_value(pairs: list[dict]) -> list[dict]:
    """Một `value_entity_index` -- một cặp. Chữ in của kẻ thua vào `printed_header`.

    ## Vì sao cần, dù `complete()` đã có hai lượt hợp nhất riêng

    Lượt "đường khai đi trước" (dưới) chỉ hợp nhất NHÃN vào cặp ĐÃ KHAI, và
    lượt "ô bảng" chỉ hợp nhất NHÃN vào cặp ĐÃ KHAI qua cùng con đường đó.
    Cả hai đều so với `spoken`, tức TẬP ĐƯỜNG KHAI -- không so với nhau, và
    không so với `extra_pairs` chạy sau cùng. Một ô bảng không có `data-path`
    vẫn có thể bị một nhãn theo sau (`label`) hoặc một cặp `extra_pairs` tìm
    ra sau đó (`pair`/`family`) tranh mất, và không lượt hợp nhất nào ở trên
    thấy được việc ấy.

    Đo trên `data/pilot10` + `data/pilot12` thật (16 tài liệu, 1337 thực thể,
    đếm đúng theo `value_entity_index` -- một tiêu đề cột lặp ở nhiều dòng
    KHÔNG phải trùng, nó là một khoá cho nhiều giá trị, đúng cấu trúc bảng):
    4 thực thể còn bị hai trường nhận trước khi có hàm này, cả bốn cùng một
    hình -- dòng TỔNG CỘNG của bảng (`table`) đứng ngay sau nhãn "TỔNG CỘNG:"
    (`label`) hoặc bị `extra_pairs` khớp lại lần nữa (`pair`) với một chú
    thích khác trên trang. Sau khi thêm hàm này: 0/1337.

    Chạy sau `extra_pairs` -- tức sau khi MỌI nguồn đã góp mặt -- nên không
    bỏ sót cặp nào tới muộn."""
    groups: dict[int, list[dict]] = {}
    for pair in pairs:
        index = pair.get("value_entity_index")
        if isinstance(index, int):
            groups.setdefault(index, []).append(pair)
    drop: set[int] = set()
    for group in groups.values():
        if len(group) <= 1:
            continue
        group.sort(key=lambda p: _SOURCE_PRIORITY.get(p.get("source", ""), 5))
        winner, losers = group[0], group[1:]
        for loser in losers:
            printed = str(loser.get("key_text") or "").strip()
            if printed:
                winner.setdefault("printed_header", []).append(printed)
            drop.add(id(loser))
    return [p for p in pairs if id(p) not in drop]


def _reseat(pairs: list[dict], record: dict) -> int:
    """Lấy lại hộp của mỗi cặp TỪ CHÍNH THỰC THỂ nó trỏ tới. Số hộp đã sửa.

    Hộp của một cặp là dữ liệu DẪN XUẤT: thực thể mới là chỗ đo được. Giữ một
    bản chép riêng bên cạnh là cách chắc chắn hai bản trôi khỏi nhau, và ở đây
    chúng đã trôi.

    Đo trên `data/thu1k`, tờ `sao_ke_tai_khoan_00072`: ba cặp `source="label"`
    ghi lúc vẽ mang `value_bbox` là PHẦN NGHÌN CỦA PHẦN NGHÌN (chia hai lần),
    còn `value_bbox_px` mang chính con số phần nghìn -- trong khi thực thể của
    chúng vẫn đúng cả hai hệ. `complete()` bê nguyên cặp nhãn làm nền nên con
    số sai đi thẳng ra `json/`, và `synthgen/overlay.py` vẽ ba cái hộp ấy lên
    giữa bảng thay vì dưới chân trang.

    Sửa ở đây chứ không ở chỗ ghi: mọi bộ đã sinh cũng được chữa khi chạy lại
    `derive.py`, và đường vẽ lẫn đường dựng lại dùng chung đúng một luật.

    Cặp nào không trỏ tới thực thể nào -- `key_entity_index` rỗng ở nhánh
    `implied` là chuyện thường -- thì giữ nguyên: không có chỗ nào đúng hơn để
    lấy."""
    seats = {e.get("entity_index"): e
             for e in record.get("entity_annotations") or []}
    fixed = 0
    for pair in pairs:
        for side in ("key", "value"):
            entity = seats.get(pair.get(f"{side}_entity_index"))
            if not entity or not entity.get("bbox"):
                continue
            box = _box(entity["bbox"])
            if pair.get(f"{side}_bbox") != box:
                fixed += 1
            pair[f"{side}_bbox"] = box
            pair[f"{side}_bbox_px"] = _px_of(entity)
    return fixed


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
    # CÂU TẢ CỦA NỀN CŨNG PHẢI LÀM MỚI. Nền là cặp `label` mà bản ghi đã mang
    # sẵn; giữ nó để khỏi dựng hai lần, nhưng giữ luôn câu tả cũ thì một bộ
    # derive lại không bao giờ nhận `kie_descriptions.json` vừa ghi -- đo
    # được: `dia_chi` giữ câu suy từ `kind` trong khi file khai
    # "Registered address of the seller.".
    for pair in label_pairs:
        fresh, whence = say(str(pair.get("field") or ""),
                            caption=str(pair.get("key_text") or ""),
                            kind=str(pair.get("key_kind") or ""),
                            layout=str((record.get("extracted") or {}).get("doc_type") or ""))
        if fresh:
            pair["description"] = fresh
            pair["description_source"] = whence
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
                        owner["key_bbox_px"] = pair.get("key_bbox_px")
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
    _reseat(pairs, record)

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
                        owner.setdefault("key_bbox_px", cell.get("key_bbox_px"))
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
    layout_id = str((record.get("extracted") or {}).get("doc_type") or "")
    pages = len(record.get("source_files") or [record.get("filename")]) or 1
    for page in range(1, pages + 1):
        # `layout` là khoá tra của `kie_descriptions.json`: file khai
        # `{phôi: {trường: câu tả}}`, nên không có nó thì tra trượt mọi lần.
        pairs.extend(extra_pairs(record, page, used, layout_id))

    pairs = _dedup_by_value(pairs)

    unique_says(pairs)

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

    # CẤU TRÚC BẢNG GHI THẲNG VÀO BẢN GHI, ở đây chứ không ở hai chỗ gọi.
    #
    # `derive.py` và `draw_llm.py` đều gọi hàm này và đều tự gán
    # `record["kie"]["pairs"]`. Bắt cả hai cùng nhớ gán thêm `tables` là dựng
    # một luật mà hai chỗ phải biết -- đúng lỗi kho này hay bị cắn. Hàm tên là
    # `complete(record, ...)`, nên hoàn thiện bản ghi là việc của nó.
    #
    # Markup rỗng thì KHÔNG ghi khoá: một lượt dựng lại không có markup không
    # được phép xoá cấu trúc mà lượt vẽ đã ghi đúng.
    if markup:
        record.setdefault("kie", {})["tables"] = table_structures(markup)
    return pairs, counts


__all__ = ["complete", "extra_pairs", "table_pairs", "table_structures"]
