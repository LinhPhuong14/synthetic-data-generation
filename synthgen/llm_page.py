"""Kiểm một trang HTML do model viết, trước khi nó được vẽ.

    from synthgen.llm_page import problems, KINDS
    print(problems(html, fields))      # rỗng là vẽ được

Kho này có một luật, và nó là lý do mọi cái hộp tin được:

> **Hộp đến từ engine đã dàn chữ. Không renderer nào đọc lại đầu ra của chính
> nó.**

Luật ấy KHÔNG đổi khi model viết HTML: Chromium vẫn dàn trang, `CELL_RECTS_JS`
vẫn đo, hộp vẫn là hộp trình duyệt trả về. Thứ đổi là **ai hứa rằng trang ấy đo
được**. Trước đây là `markup.py` -- mã, nên đúng theo cấu tạo. Giờ là một model,
nên phải KIỂM.

## Điều phải kiểm, và vì sao đúng điều ấy

`generators/html/page.py::CELL_RECTS_JS` đo `span.firstElementChild || span`.
Một thẻ lồng trong `<span data-kind>` LẶNG LẼ trở thành cái hộp được ghi --
`agent/compose_layout.py` đo được: một `<sub>` trong công thức làm hộp rộng
5,3 px thay vì 310,6. Trang vẫn vẽ ra, nhãn vẫn có, và nhãn sai.

Đó là vì sao luật số một ở đây là **run có nhãn chỉ chứa chữ**. Không phải một
sở thích về phong cách: nó là điều kiện để con số toạ độ có nghĩa.

Bốn luật còn lại, mỗi luật một cách trang bị hỏng mà nhìn ảnh không thấy:

* **Mọi giá trị đã khai phải in ra đúng một lần.** Model viết JSON nội dung rồi
  viết HTML; hai thứ ấy lệch nhau là bộ dữ liệu dạy mô hình đọc ra thứ không có
  trên giấy. Kiểm bằng cách so chữ, không tin lời hứa.
* **`data-kind` phải đọc được.** Từ vựng engine là GỢI Ý, không phải hàng rào:
  model được đặt tên mới cho khái niệm engine chưa có, miễn cái tên theo ngữ
  pháp `họ.trường[.label]`. Xem `_COINED` bên dưới -- ngữ pháp ấy là thứ giữ
  cho mọi trục suy diễn còn chạy trên một cái tên chưa ai từng thấy.
* **Không tài nguyên ngoài.** `<script>`, `<img src="http…">`, `@import` --
  trang phải vẽ được trên máy không có mạng, và một request ra ngoài là một
  trang vẽ ra khác nhau tuỳ lúc.
* **Phải có `.sheet`.** `draw.py` chụp đúng phần tử ấy; không có thì không có
  trang nào để chụp.

## Cái này KHÔNG kiểm

Nội dung có thật hay không. "Công ty TNHH Mặt Trời Mọc" là một cái tên hợp lệ và
có thể không tồn tại; `agent/corpus_rules.py` đã viết ra giới hạn ấy cho corpus
và nó cũng đúng ở đây. Cổng máy bắt cái đo được; người đọc diff bắt phần còn
lại.
"""

from __future__ import annotations

import re
from functools import lru_cache
from html.parser import HTMLParser

# Từ vựng `data-kind`, ĐO TỪ ENGINE chứ không viết tay.
#
# Lần đầu tôi liệt kê bằng tay 57 kind và cổng loại sạch 40/40 trang do chính
# `markup.py` sinh ra -- nó in cả biến thể `.label` mà danh sách tay không có.
# Một cổng loại trang engine viết là cổng sai, không phải trang sai; cùng câu
# `agent/corpus_rules.py` đặt ra cho corpus.
#
# Nên dựng trang thật rồi nhặt: 60 phôi, 0,5 giây, 79 kind. Không mở trình
# duyệt -- `markup.py` là chuỗi thuần.
# Bao nhiêu mẫu để nhặt ra từ vựng. Đường cong đo được: 60 mẫu -> 68 kind,
# 120 -> 77, 200 -> 80, 300 -> 80, 400 -> 81. Cả bốn trăm mẫu tốn 0,7 giây.
#
# Để ở 60 là nói với model rằng `menu.meter_prev`, `menu.rate_bhyt`,
# `menu.self_pay` KHÔNG TỒN TẠI, trong khi engine vẫn in chúng ra -- rồi loại
# trang nào model dùng chúng. Mười hai cái nhãn bị chối bỏ để tiết kiệm hai
# phần mười giây.
SAMPLE = 300


@lru_cache(maxsize=1)
def kinds() -> frozenset[str]:
    """Mọi `data-kind` engine này in ra, nhặt từ chính HTML nó dựng."""
    import random  # noqa: PLC0415

    from synthgen import content as C  # noqa: PLC0415
    from synthgen import design as D  # noqa: PLC0415
    from synthgen import markup as M  # noqa: PLC0415

    found: set[str] = set()
    for seed in range(SAMPLE):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x5A), 4)
        html = M.markup(doc, [(0, len(doc.rows))])
        found |= set(re.findall(r'data-kind="([^"]+)"', html))
    return frozenset(found | EXTRA)


# KIND MODEL CẦN MÀ ENGINE KHÔNG IN RA.
#
# `kinds()` nhặt từ chính HTML engine dựng, nên nó chỉ biết những gì engine
# biết vẽ. Engine không bao giờ in tiêu đề mục ("I. THÔNG TIN CHỦ SỞ HỮU ĐẤT")
# -- phôi của nó không có khối ấy. Model thì in, và in nhiều.
#
# Hậu quả đo được trên pilot13: 72 trên 72 vùng `Section-Header` model khai đều
# có chữ mà KHÔNG có `<span data-kind>` nào -- model khai đúng vùng rồi không
# tìm ra kind nào để gắn lên chữ, vì từ vựng không có. Phép đo chỉ thấy chữ
# trong run có nhãn, nên cả 72 tiêu đề mục không có hộp, rồi vùng rỗng bị bỏ.
# `Section-Header` ra 0,7 mỗi tờ trong khi bộ tham chiếu có 8.
#
# `pipeline/record.py::DOCSYNTH_LABEL_FOR_KIND` ĐÃ biết `section` ->
# `Section-Header`. Thiếu mỗi việc nói cho model biết cái tên ấy tồn tại.
EXTRA = frozenset({"section"})


def _regions() -> tuple[str, ...]:
    """Vùng bố cục một khối được phép tự khai -- ĐỌC từ bảng nhãn thật.

    Bản trước chép tay mười sáu nhãn vào đây với lời hứa "cùng bảng của
    `pipeline/record.py`". Lời hứa ấy đã sai lúc được viết: danh sách chép tay
    có `Picture`, thứ thuộc bảng nhãn CŨ mười một mục, không có trong
    `DOCSYNTH_LABELS`. Và khi `Watermark` với `Stamp` được thêm vào bảng thật,
    danh sách chép tay không biết gì cả.

    Đây đúng là lối kho này vẫn làm ở chỗ khác -- `synthgen/archetypes.py::
    schema()` đọc phôi đang chạy, `agent/layout_schema.py` đọc bố cục đã chốt.
    Thứ gì phái sinh được thì đừng chép: một bản chép không cũ đi thì thôi,
    còn cũ đi thì cũ lặng lẽ.

    `Blank-Page` bị loại: nó nói về CẢ TRANG, không phải một khối trong trang,
    nên một `<div data-region="Blank-Page">` là câu vô nghĩa."""
    from pipeline.record import DOCSYNTH_LABELS               # noqa: PLC0415

    return tuple(sorted(DOCSYNTH_LABELS - {"Blank-Page"}))


REGIONS = _regions()

# Thứ không được có mặt: mỗi cái là một cách trang vẽ ra khác nhau tuỳ lúc,
# hoặc một cách nó chạy mã.
FORBIDDEN = (
    (re.compile(r"(?i)<\s*script"), "có thẻ <script>"),
    (re.compile(r"(?i)<\s*iframe"), "có thẻ <iframe>"),
    (re.compile(r"(?i)<\s*object|<\s*embed"), "có <object>/<embed>"),
    (re.compile(r"(?i)\son\w+\s*="), "có thuộc tính sự kiện (onclick, onload…)"),
    (re.compile(r"(?i)(src|href)\s*=\s*[\"']?\s*(https?:)?//"), "trỏ tài nguyên ngoài"),
    (re.compile(r"(?i)@import"), "có @import trong CSS"),
    (re.compile(r"(?i)url\(\s*[\"']?\s*(https?:)?//"), "CSS tải tài nguyên ngoài"),
)


# Thẻ HTML rỗng: không có nội dung, không có thẻ đóng. Danh sách của chuẩn
# HTML, không phải danh sách tự nghĩ.
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                  "link", "meta", "param", "source", "track", "wbr"})


class _Spans(HTMLParser):
    """Mọi `<span data-kind>`: kind, chữ bên trong, và CÓ THẺ LỒNG hay không."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.spans: list[dict] = []
        self.regions: list[str] = []
        self.sheets = 0
        self._stack: list[dict | None] = []

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if tag == "div" and "sheet" in str(at.get("class") or "").split():
            self.sheets += 1
        if at.get("data-region"):
            self.regions.append(str(at["data-region"]))
        if tag == "span" and at.get("data-kind") is not None:
            span = {"kind": str(at["data-kind"]), "text": "", "nested": False,
                    "key": str(at.get("data-key") or ""),
                    "path": str(at.get("data-path") or ""),
                    "decoy_for": str(at.get("data-decoy-for") or "")}
            self.spans.append(span)
            self._stack.append(span)
            return
        # Một thẻ mở KHI ĐANG ở trong một span có nhãn là cái thẻ lồng nguy
        # hiểm -- `<br>` cũng tính, vì `firstElementChild` bắt được nó.
        for frame in self._stack:
            if frame is not None:
                frame["nested"] = True
        # THẺ RỖNG KHÔNG ĐƯỢC ĐẨY VÀO NGĂN XẾP.
        #
        # `<br>`, `<meta>`, `<img>` không bao giờ có thẻ đóng, nên đẩy chúng
        # vào là đẩy một thứ không ai lấy ra. Rồi `</div>` kế tiếp lấy nhầm
        # khung của `<br>` thay vì khung của `<div>`, và từ đó ngăn xếp lệch
        # một bậc: một span ĐÃ ĐÓNG vẫn còn nằm trong ngăn xếp, nên mọi thẻ
        # mở sau đó đánh dấu nó "có thẻ lồng".
        #
        # Đo trên pilot6: sáu tờ bị loại, năm tờ vì lý do này, và tương quan
        # tuyệt đối -- mọi tờ bị báo `store.name` có thẻ lồng đều chứa `<br>`
        # hoặc `<meta>`, tờ nào không chứa thì không bị báo. `store.name` là
        # nạn nhân vì nó là span có nhãn ĐẦU TIÊN trên trang, tức nằm sâu
        # nhất dưới đáy cái ngăn xếp đang trôi.
        #
        # HTML của model hoàn toàn đúng: `</span>` đóng rồi mới tới `<br>`.
        # Cổng gác loại một trang người ta viết đúng, và kho này có luật cho
        # chuyện ấy -- một cái luật loại thứ người ta viết đúng là luật sai.
        if tag not in VOID:
            self._stack.append(None)

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_startendtag(self, tag, attrs):
        for frame in self._stack:
            if frame is not None:
                frame["nested"] = True

    def handle_data(self, data):
        for frame in self._stack:
            if frame is not None:
                frame["text"] += data


def printed_kinds(html: str) -> set[str]:
    """Mọi `data-kind` trang này THẬT SỰ in ra.

    Dùng bộ phân tích HTML, KHÔNG dùng regex. HTML5 cho ba kiểu viết thuộc
    tính -- `data-kind="x"`, `data-kind='x'`, `data-kind=x` -- và model dùng
    cả ba. Mỗi cái regex chỉ bắt một kiểu là một cách lặng lẽ kết luận trang
    không in gì.

    Đo trên pilot8: cổng kế hoạch so chuỗi `data-kind="{kind}"` báo ba tờ in
    ra 0/29, 0/37, 0/38 kind đã hứa. Một trong ba tờ ấy viết nháy đơn, một
    viết không nháy, và cả hai đều in đúng gần như toàn bộ kế hoạch -- phép đo
    thật đếm được 216 hộp từ trên tờ đầu. Bảy mươi mốt lời than "kế hoạch hứa
    `…` mà trang không in nó ra" ở lượt ấy gần như toàn bộ từ đây.

    `HTMLParser` đọc thuộc tính đúng như trình duyệt, nên không có kiểu viết
    nào lọt."""
    scan = _Spans()
    try:
        scan.feed(str(html or ""))
        scan.close()
    except Exception:                                           # noqa: BLE001
        return set()
    return {str(s["kind"]) for s in scan.spans if s.get("kind")}


def declared_paths(html: str) -> list[tuple[str, str]]:
    """Mọi `(data-path, chữ đã in)` trang này khai -- span nào không có `data-path`
    thì không xuất hiện ở đây.

    Dùng để đối chiếu cây `data` model viết TRƯỚC html với chữ nó thực sự in
    ra sau đó -- xem `agent/compose_page.py::data_path_mismatches`."""
    scan = _Spans()
    try:
        scan.feed(str(html or ""))
        scan.close()
    except Exception:                                           # noqa: BLE001
        return []
    return [(str(s["path"]), _tight(s.get("text") or ""))
           for s in scan.spans if s.get("path")]


def _tight(text: str) -> str:
    return " ".join(str(text or "").split())


class _Cells(HTMLParser):
    """Ô bảng ở tầng ngoài cùng mà thiếu `data-cell`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.bare: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self.depth += 1
            return
        if tag in ("td", "th") and self.depth == 1:
            if not any(name == "data-cell" for name, _ in attrs):
                shown = " ".join(f'{n}="{v}"' for n, v in attrs if v)
                self.bare.append(f"<{tag} {shown}>".replace(" >", ">"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self.depth = max(0, self.depth - 1)


def _bare_cells(html: str) -> list[str]:
    parser = _Cells()
    try:
        parser.feed(html)
        parser.close()
    except Exception:                                           # noqa: BLE001
        return []
    return parser.bare


def _rooted(kind: str, known: frozenset[str]) -> str | None:
    """Tiền tố dài nhất của `kind` mà CHÍNH NÓ là một kind thật, hoặc None.

    Đo trên 30 trang model viết: 103 lần bị loại vì từ vựng, và **101 lần
    (98%) là một kind thật cộng một hậu tố chỉ rõ trường nào** --
    `invoice.field.label.date` trên nền `invoice.field.label`,
    `invoice.field.meter` trên nền `invoice.field`. Đó không phải bịa tên, đó
    là nói cụ thể hơn mức từ vựng có. Chỉ 2 lần là tên mới thật sự
    (`note-label`, `survey.comment_value`).

    KHÁC `record.label_for`, và khác ở chỗ quan trọng nhất: hàm ấy cũng khớp
    tiền tố dài nhất nhưng có NHÃN MẶC ĐỊNH, nên `bịa.hoàn.toàn` cũng ra
    `Text` -- nó không bao giờ nói không. Ở đây phải tồn tại một kind thật làm
    gốc, nên tên bịa vẫn bị loại.

    Vì sao không hỏi model xem hai tên có cùng nghĩa: cổng là thứ duy nhất
    phải ổn định. Một cổng gọi model là cổng hôm nay nhận, mai loại, cùng một
    trang -- và khi ấy "bộ này qua cổng" thôi là một câu nói được. Chuyện này
    cũng không mơ hồ tới mức cần phán: cái tên đã mang sẵn gốc thật trong nó.
    """
    # Cắt hậu tố của ĐOẠN CUỐI trước: `sign.title_a`, `sign.name2` là
    # `sign.title`/`sign.name` cộng một chữ chỉ rõ bên nào, người thứ mấy --
    # cùng kiểu "nói cụ thể hơn mức từ vựng có" như `invoice.field.label.date`,
    # chỉ khác dấu nối. Đo được: 11/30 tên còn lại của lượt thử hai là kiểu này.
    trimmed = re.sub(r"(_[a-z0-9]+|\d+)$", "", kind) if "." in kind else kind
    for candidate in (kind, trimmed):
        if candidate and candidate != kind and candidate in known:
            return candidate
    parts = kind.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        root = ".".join(parts[:cut])
        if root in known:
            return root
    return None


_DIV = re.compile(r"<(/?)div\b", re.IGNORECASE)
_SHEET_OPEN = re.compile(r'<div\b[^>]*\bclass="[^"]*\bsheet\b', re.IGNORECASE)

# HÌNH DẠNG `data-path`. Đoạn nối bằng `.`, mỗi đoạn snake_case, mỗi đoạn có
# thể mang `[N]` hoặc `[]` -- khớp cả `issuer.tax_code`, `line_items[0].name`,
# và dạng không chỉ số `items[].print_qty` đã thấy trong
# `docs/kie-cau-hoi-kiem-schema.md`. Không đòi biết TRƯỚC cây `data` có hình
# gì -- chỉ đòi cái tên tự nó đọc được, cùng lý do `_rooted` không hỏi model
# xem hai kind có cùng nghĩa: cổng là thứ duy nhất phải ổn định.
#
# ĐOẠN THUẦN SỐ cũng hợp lệ (`clause.1.body`, `section.4`) -- không chỉ
# `[N]`. Đo trên pilot16 (Phase 8): một tờ khai `clause.1.head`, `clause.2.
# body`, `section.1`...`section.4`, `conclusion.1.head`... -- MƯỜI SÁU
# đường bị cổng cũ loại nguyên một tờ đạt mọi luật khác, vì cổng đòi ngoặc
# vuông cho chỉ số lặp mà lời dặn (mục 22 `page.md`) chỉ cho MỘT ví dụ
# (`clauses[0].number`) giữa một tài liệu rất dài. Phạt một tờ đúng cấu trúc,
# đúng nội dung, chỉ vì chọn `.1.` thay vì `[0].` là phạt nhầm hình thức --
# `resolve_path()` (`agent/compose_page.py`) đọc được cả hai hình, nên cổng
# không cần đòi một hình duy nhất nữa.
# NGỮ PHÁP CỦA MỘT `data-kind` MODEL TỰ ĐẶT.
#
# ## Vì sao mở từ vựng
#
# `kinds()` nhặt từ chính engine, nên nó chỉ biết những khái niệm engine biết
# vẽ. Model viết loại giấy engine chưa có -- hợp đồng xây dựng, biên bản giám
# định, đơn xin cấp phép -- và những tờ ấy có trường mà không phôi nào của kho
# từng in. Đo trên 30 trang lượt đầu: 103 lần trượt cổng vì từ vựng, và 98% là
# một kind thật cộng hậu tố (`_rooted` nhận chúng từ lâu). Nhưng 2% còn lại là
# tên MỚI THẬT SỰ, và mỗi lần như thế cổng vứt cả tờ giấy đúng mọi luật khác
# chỉ vì model gọi tên một khái niệm kho chưa đặt tên.
#
# ## Vì sao vẫn có ngữ pháp
#
# Mở tuỳ tiện thì mất hết những trục KHÔNG tra bảng mà đọc HÌNH DẠNG cái tên:
#
#   `record._word_field_role`  hậu tố `.label`/`.title` -> vai `key`
#   `record.regions_from_words` đoạn ĐẦU (`họ`) -> cắt cụm vùng
#   `synthgen/kie_schema.groups` tiền tố -> nhóm trường trong schema
#   `synthgen/kie_full` họ `kind` -> ghép khoá mồ côi với giá trị mồ côi
#
# Cả bốn chạy được trên một cái tên chưa ai từng thấy, MIỄN LÀ nó có họ và
# giữ quy ước hậu tố. Nên cổng đòi đúng chừng ấy: hai tới bốn đoạn snake_case
# nối bằng dấu chấm. Tên một đoạn (`title`, `note`, `colhdr`) vẫn qua vì
# chúng nằm trong từ vựng engine; một tên MỚI một đoạn thì không, vì nó không
# nói được nó thuộc cụm nào.
#
# ĐOẠN THUẦN SỐ hợp lệ ở mọi chỗ trừ đoạn đầu -- `clause.1.body`,
# `section.4`. Cùng lý lẽ đã viết cho `_PATH` ngay dưới: đo trên pilot16, một
# tờ đánh số điều khoản bằng `.1.` thay vì `[0].` bị cổng cũ loại nguyên tờ,
# và phạt hình thức khi nội dung đúng là phạt nhầm. Đoạn ĐẦU thì phải là chữ,
# vì nó là họ và một con số không đặt tên được cho cụm nào.
_COINED = re.compile(r"^[a-z][a-z0-9_]*(\.([a-z][a-z0-9_]*|\d+)){1,3}$")

def acceptable_kind(name: str, known) -> bool:
    """Cổng có nhận cái tên `data-kind` này không -- MỘT vị từ, mọi nơi hỏi.

    Ba chỗ ép cùng luật này và chúng từng lệch nhau:

      `synthgen/llm_page.py::problems`    -- cổng chữ
      `agent/compose_page.py::schema`     -- ngữ pháp bộ giải mã
      `agent/compose_page.py::plan_problems` -- kiểm `field_plan`

    Chỗ thứ ba quên vế `_COINED`, nên nó loại `menu.number` và
    `contract.party_a`: những cái tên lời dặn CHO PHÉP đặt, bộ giải mã sinh
    ra được, và cổng chữ chấp nhận. Model làm đúng mọi điều được dặn rồi mất
    cả tờ ở chỗ thứ ba -- đo được trên `data/23-09-llm-i`.

    Ba vế, và không vế nào suy ra từ vế khác:

    * tên CÓ trong từ vựng -- gồm cả `title`, `note` một đoạn mà `_COINED`
      loại;
    * tiền tố là một kind thật (`menu.name.label` khi `menu.name` có);
    * theo ngữ pháp đặt tên mới `họ.trường[.nhãn]`."""
    name = str(name or "")
    return bool(name) and (name in known or _rooted(name, known)
                           or bool(_COINED.match(name)))


_PATH = re.compile(
    r"^[a-z][a-z0-9_]*(\[\d*\])?"
    r"(\.([a-z][a-z0-9_]*(\[\d*\])?|\d+))*$")


def outside_sheet(html: str) -> int:
    """Số run có nhãn nằm ngoài mọi `.sheet`.

    Ta chỉ chụp ảnh phần tử `.sheet`. Chữ nằm ngoài nó vẫn vẽ ra trên trình
    duyệt nhưng KHÔNG vào ảnh và KHÔNG có hộp -- mất lặng lẽ.

    Đo trên pilot13: một tờ có 221 run mà 215 nằm ngoài, vì model đóng một
    `</div>` sớm hơn một nhịp. Tờ ấy xin bốn trang, cắt ra một, và trang ấy
    cao 181 điểm ảnh. Cổng cũ chỉ hỏi "có `.sheet` không", nên nó qua.

    Đếm độ sâu `<div>` chứ không dùng `HTMLParser`: div trong HTML này luôn
    đóng tường minh, còn bộ phân tích thì từng trượt vì thẻ rỗng (`<br>` đẩy
    vào ngăn xếp mà không ai lấy ra). Một phép đếm hiểu được là một phép đếm
    sửa được."""
    depth, sheet_at, inside = 0, None, []
    pos, marks = 0, []
    for m in _DIV.finditer(html):
        if m.group(1):                       # </div>
            depth -= 1
            # `sheet_at` ghi độ sâu TRƯỚC khi vào `.sheet`, nên thẻ đóng của
            # chính nó đưa `depth` về đúng con số ấy -- bằng, không nhỏ hơn.
            if sheet_at is not None and depth <= sheet_at:
                marks.append((pos, m.end()))
                sheet_at, pos = None, 0
        else:                                 # <div ...>
            if sheet_at is None and _SHEET_OPEN.match(html, m.start()):
                sheet_at, pos = depth, m.start()
            depth += 1
    if sheet_at is not None:                 # `.sheet` chưa đóng tới hết file
        marks.append((pos, len(html)))
    covered = sum(html.count('data-kind="', a, b) for a, b in marks)
    return max(0, html.count('data-kind="') - covered)


def problems(html: str, fields: dict | None = None) -> list[str]:
    """Mọi lý do trang này chưa vẽ được. Rỗng là vẽ được.

    `fields` là `{tên: giá trị}` model đã khai; mỗi giá trị phải in ra đúng
    một lần trong một run có nhãn."""
    found: list[str] = []
    body = str(html or "")
    if not body.strip():
        return ["trang rỗng"]

    for pattern, why in FORBIDDEN:
        if pattern.search(body):
            found.append(why)

    # Ô BẢNG PHẢI CÓ `data-cell`, kể cả ô trong `<thead>`. Đo trên trang
    # model viết: thân bảng `<td data-cell>` đủ, nhưng đầu bảng
    # `<th class="c-stt">` thiếu -- nên vùng `Table` đo được chỉ phủ phần thân,
    # còn SÁU ô tiêu đề rơi ra ngoài và mỗi ô thành một vùng `Table` riêng.
    # Nhìn ảnh vẽ hộp thì thấy ngay; đọc HTML thì không.
    #
    # `CELL_REGIONS_JS` đo `[data-cell]`, nên thiếu thuộc tính ấy là ô không
    # tồn tại với phép đo, dù nó tồn tại với người đọc.
    # Chỉ soi bảng ở TẦNG NGOÀI CÙNG. Một bảng lồng trong một ô đã đo --
    # `markup._sub` in bảng con vào trong ô mô tả -- thì ô ngoài đã phủ nó rồi,
    # và đòi `data-cell` cho từng ô con là đòi một cái hộp cho thứ đã có hộp.
    # Đo được: luật không phân tầng loại 3/40 trang chính engine này viết, và
    # cả ba đều vì bảng con ấy. Luật nào loại một trang engine viết là luật
    # sai, không phải trang sai.
    bare = _bare_cells(body)
    if bare:
        found.append(
            f"{len(bare)} ô bảng thiếu `data-cell` (vd `{bare[0][:40]}`); "
            "`CELL_REGIONS_JS` chỉ đo ô CÓ thuộc tính ấy, nên ô thiếu rơi ra "
            "ngoài vùng bảng và thành một vùng rời")

    parser = _Spans()
    try:
        parser.feed(body)
        parser.close()
    except Exception as error:                              # noqa: BLE001
        return found + [f"HTML không đọc được: {error}"]

    if not parser.sheets:
        found.append('không có <div class="sheet"> nào để chụp')
    else:
        stray = outside_sheet(body)
        if stray:
            found.append(
                f'{stray} run có nhãn nằm NGOÀI mọi <div class="sheet">; '
                "phép đo chỉ chụp `.sheet` nên chúng không có hộp nào -- "
                "thường là một `</div>` đóng sớm")

    known = kinds()
    seen_kind: dict[str, int] = {}
    for span in parser.spans:
        if span["nested"]:
            # CỔNG NÀY KHÔNG ĐƯỢC NỚI. Bất kể model viết gì, một thẻ lồng
            # LUÔN làm hộp đo sai -- đó là kết luận của chính `CELL_RECTS_JS`,
            # không phải một tỉ lệ cần đo trước rồi mới gác.
            #
            # Đo trên `data/pilot16`: 9 tờ trượt đúng đây, và cả 9 đều một
            # trong hai hình -- nhãn ngắn bọc `<strong>`/`<b>` đứng TRƯỚC phần
            # chữ còn lại, hoặc sub-label song ngữ bọc `<span>` sau `<br>`.
            # `synthgen/repair.py::unnest()` (đã tổng quát hoá để bắt cả hai
            # hình, không chỉ span trần) chữa được cả 9 TRƯỚC khi tới đây --
            # xem `tests/test_repair.py`. Cổng vẫn đứng nguyên; thứ đổi là
            # bao nhiêu trang còn tới được đây ở dạng chưa chữa.
            found.append(
                f'run `{span["kind"]}` có thẻ lồng bên trong; phép đo lấy '
                "`span.firstElementChild || span` nên thẻ ấy THÀNH cái hộp "
                "được ghi -- run có nhãn phải chỉ chứa chữ")
        if (span["kind"] not in known and not _rooted(span["kind"], known)
                and not _COINED.match(span["kind"])):
            found.append(
                f'`data-kind="{span["kind"]}"` không đọc được: một tên tự đặt '
                "phải là `họ.trường` hoặc `họ.trường.gì_đó`, chữ thường, "
                "snake_case, 2-4 đoạn")
        seen_kind[span["kind"]] = seen_kind.get(span["kind"], 0) + 1
    if not parser.spans:
        found.append("không có run nào mang `data-kind`; trang không có nhãn nào")

    # `data-path` ĐÚNG DẠNG, VÀ CÙNG ĐƯỜNG DẪN THÌ CÙNG GIÁ TRỊ.
    #
    # Không đòi MỌI `data-kind` phải có `data-path` -- đo trên
    # `data/pilot10`+`data/pilot12` (HTML thật, không phải `record["html"]` đã
    # rút gọn): chỉ 28% run mang thuộc tính ấy dưới `page.md` CŨ, và `page.md`
    # mới (đã đổi ở Phase 5 trước đó trong `docs/ke-hoach-refactor-engine.md`)
    # chưa được đo lại. Ép cổng theo một con số chưa đo là đổi tỉ lệ chấp nhận
    # của cả hệ thống mà không ai biết trước bao nhiêu -- việc đó dành cho
    # Phase 2 (tầng validation) sau khi có số đo thật, không phải ở đây. Xem
    # `path_coverage()` dưới, hàm ĐO chứ không GÁC.
    #
    # Hai điều dưới đây thì khác: một `data-path` viết sai dạng, hoặc hai
    # đoạn văn cùng khai một đường dẫn mà in ra hai giá trị khác nhau, LUÔN
    # sai bất kể phiên bản prompt nào -- đây là mâu thuẫn nội tại của chính
    # trang đó, không phải một tỉ lệ cần đo trước.
    #
    # "Khác nhau" là so CHUỖI, không so Ý -- viết hoa khác, rút gọn khác,
    # hay một nhãn bị bọc vào chữ của một trong hai lần in đều tính. Đo trên
    # `data/pilot16`: 15 tờ trượt đúng đây, và không tờ nào là hai sự thật
    # thật sự mâu thuẫn -- toàn bộ là MỘT sự thật, in hai chữ khác nhau.
    # `synthgen/repair.py::unclash()` bỏ `data-path` khỏi mọi run đụng nhau
    # (giữ `data-kind`, giữ chữ, chỉ mất một lời khai định danh) TRƯỚC khi
    # tới đây, và chữa được cả 15 -- xem `tests/test_repair.py`. Cổng không
    # tự phân xử bên nào "đúng hơn": nó không đủ thông tin để đoán, và đoán
    # sai thì gắn nhầm danh tính cho một run, tệ hơn không gắn.
    by_path: dict[str, set[str]] = {}
    for span in parser.spans:
        path = span.get("path") or ""
        if not path:
            continue
        if not _PATH.match(path):
            found.append(f'`data-path="{path}"` không đúng dạng (mong đợi kiểu '
                         '`issuer.tax_code` hoặc `line_items[0].name`)')
            continue
        text = _tight(span.get("text") or "")
        if text:
            by_path.setdefault(path, set()).add(text)
    for path, values in by_path.items():
        if len(values) > 1:
            shown = ", ".join(repr(v) for v in sorted(values)[:3])
            found.append(f'`data-path="{path}"` in ra {len(values)} giá trị khác '
                         f'nhau ({shown}); cùng một đường dẫn phải là cùng một '
                         "trường")

    # MỒI GIẢ KHÔNG ĐƯỢC TỰ NHẬN LÀ MỤC TIÊU CỦA CHÍNH NÓ.
    #
    # Phase 6.3 (`docs/ke-hoach-refactor-engine.md`): `data-decoy-for="X"`
    # trên một span khai "tôi đang giả làm field X" -- một mồi lexical/format
    # trông giống `store.tax_code` nhưng KHÔNG PHẢI nó. Nếu span đó cũng mang
    # `data-kind="X"` (cùng X), nó vừa giả vừa THẬT SỰ tự nhận là target --
    # không còn là mồi giả nào cả, chỉ là một positive khai hai lần. Gate này
    # không đụng `synthgen/kie_full.py::hard_negative_spans` (đường đọc offline,
    # không gác) -- đây là cổng chặn TRANG, trước khi trang được nhận.
    for span in parser.spans:
        decoy_for = span.get("decoy_for") or ""
        if decoy_for and decoy_for == span["kind"]:
            found.append(
                f'run khai `data-decoy-for="{decoy_for}"` mà chính nó cũng '
                f'mang `data-kind="{decoy_for}"` -- mồi giả không được trùng '
                "kind với mục tiêu nó giả làm")

    for region in parser.regions:
        if region not in REGIONS:
            found.append(f'`data-region="{region}"` không phải một trong 16 nhãn vùng')

    printed = [_tight(s["text"]) for s in parser.spans]
    for name, value in (fields or {}).items():
        wanted = _tight(value)
        if not wanted:
            continue
        times = printed.count(wanted)
        if times == 0:
            # Chữ có thể bị ngắt qua hai run (một nhãn, một giá trị), nên thử
            # tìm nó nằm TRỌN trong một run trước khi kết luận là thiếu.
            if any(wanted in run for run in printed):
                continue
            found.append(f'trường `{name}` khai giá trị {value!r} mà không run '
                         "nào in ra")
        elif times > 1:
            found.append(f'trường `{name}` in ra {times} lần; mỗi giá trị phải '
                         "có đúng một hộp")
    return found


class _Visible(HTMLParser):
    """Đếm ký tự chữ HIỂN THỊ trong mọi `.sheet` -- bỏ `<style>`/`<script>`,
    bỏ khoảng trắng thừa. Không phân biệt có `data-kind` hay không -- đây là
    phép đo LƯỢNG CHỮ, khác `printed_kinds()` (đo NHÃN)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_sheet = 0
        self.skip = 0
        self.chars = 0

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if tag == "div" and "sheet" in str(at.get("class") or "").split():
            self.in_sheet += 1
        if tag in ("style", "script"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.skip > 0:
            self.skip -= 1

    def handle_data(self, data):
        if self.in_sheet and not self.skip:
            self.chars += len(data.strip())


# Thẻ mà chữ bên trong nó ĐÃ có vùng, dù không `data-region` nào khai.
# `<table>`: `CELL_REGIONS_JS` gộp các ô thành đúng một vùng `Table`.
# `<img>`/`<svg>`/`[data-graphic]`: `GRAPHIC_RECTS_JS` đo chúng thành
# `Image`/`Stamp`. Hai phép đo ấy có thật và chạy trên mọi trang, nên đếm chữ
# trong chúng là mồ côi thì con số ra sai theo chiều bi quan.
_SHELTERED_TAGS = frozenset({"table", "img", "svg"})

# Chỉ phần tử `.sheet` được chụp. Run ngoài nó vẫn vẽ trên trình duyệt mà
# KHÔNG vào ảnh và KHÔNG có hộp -- `outside_sheet()` ngay dưới đã báo riêng
# chúng, nên đếm lại ở đây là báo một lỗi hai lần và thổi phồng tỉ lệ mồ
# côi. Đo chéo với phép đo DOM (`'.sheet span[data-kind]'`) trên 40 tờ:
# không lọc thì lệch 184 run và 70 mồ côi; lọc rồi thì khớp.
_SHEET_CLASS = re.compile(r"\bclass\s*=\s*(\"[^\"]*\bsheet\b[^\"]*\"|'[^']*\bsheet\b[^']*'|[^\s>]*\bsheet\b[^\s>]*)", re.IGNORECASE)


def orphan_runs(html: str) -> list[str]:
    """Những run có `data-kind` mà KHÔNG tổ tiên nào khai vùng.

    ## Vì sao đếm cái này

    Một trang có thể qua sạch mọi phép kiểm khác mà phần lớn chữ của nó không
    thuộc vùng bố cục nào. Khi ấy `pipeline/record.py` dựng vùng cho chúng
    bằng cách gom từ theo ngưỡng khe -- và bộ gom cắt ở chỗ hở ngang, mà máng
    giữa nhãn và giá trị thường rộng hơn ngưỡng. Một khối "nhãn ... giá trị"
    ra hai vùng, một khối tổng tám dòng ra tám vùng. Nhãn vẫn có, hộp vẫn có,
    chỉ là chúng mô tả những mảnh không ai vẽ ra.

    Đo trên 40 tờ model viết, SAU `repair.zoned()`, chia theo kết cục cổng:

        đã QUA cổng    trung vị 10,5%   phân vị 75: 41,1%   phân vị 90: 83,3%
        đã trượt cổng  trung vị  4,1%   phân vị 75: 66,3%   phân vị 90: 83,8%

    Trang QUA cổng còn tệ hơn trang trượt. Nghĩa là không phép kiểm nào đang
    chạy có tương quan với lỗi này -- nó lọt hoàn toàn, và lọt vào đúng tập
    được đem đi huấn luyện.

    ## Phép đo chuỗi so với phép đo DOM

    Cổng chạy TRƯỚC khi dàn trang, nên nó chỉ có chuỗi. Đo chéo với phép đo
    thật (`'.sheet span[data-kind]'` trên DOM đã dàn) trên 40 tờ: **27 tờ
    (68%) khớp chính xác**, và cả sáu tờ lệch nhiều nhất đều là trang HTML
    hỏng mà Chromium tự nắn lại -- một tờ chiếm 104 trong 184 run lệch.

    Lệch luôn về phía ĐẾM DƯ, tức cổng nghiêm hơn thực tế chứ không lỏng
    hơn; và những tờ ấy vốn đã trượt vì lỗi cấu trúc. Không nắn lại con số:
    nắn là đoán xem trình duyệt sẽ nắn thế nào, và đoán đúng chuyện ấy thì
    đã chẳng cần trình duyệt.

    ## Hàm này KHÔNG quyết định loại hay giữ

    Nó trả danh sách. Ngưỡng nằm ở `rulebase/synthgen/_blocks.yaml::gate`, và
    `agent/compose_page.py` là chỗ so. Nhốt một con số vào đây là bắt người
    muốn siết dần phải sửa mã -- đúng ranh giới `rulebase/` sinh ra để xoá."""
    from pipeline.tags import (OPEN_CLOSE, VOID_TAGS,                # noqa: PLC0415
                               declared_region, has_kind)

    stack: list[str] = []
    loose: list[str] = []
    for match in OPEN_CLOSE.finditer(html):
        closing, tag = match.group(1), match.group(2).lower()
        attrs, selfclose = match.group(3), match.group(4)
        if tag in VOID_TAGS or selfclose:
            continue
        if closing:
            while stack:
                if stack.pop() == f"/{tag}":
                    break
            continue
        if has_kind(attrs) and _in_sheet(stack) and not stack_shelters(stack) \
                and not declared_region(attrs):
            # Run có nhãn chỉ chứa chữ (luật số một của tệp này), nên chữ của
            # nó là đoạn tới dấu `<` kế tiếp. Run rỗng thì bỏ qua: một span
            # không có chữ thì không có hộp, nên nó không có nhãn để mà sai.
            rest = html[match.end():]
            cut = rest.find("<")
            text = (rest if cut < 0 else rest[:cut]).strip()
            if text:
                kind = re.search(r"data-kind\s*=\s*[\"']?([^\"'\s>]+)", attrs)
                loose.append(f"{kind.group(1) if kind else '?'}: {text[:40]!r}")
        stack.append(f"/{tag}")
        if _SHEET_CLASS.search(attrs):
            stack.append(_SHEET)
        label = declared_region(attrs)
        if label or tag in _SHELTERED_TAGS or "data-graphic" in attrs.lower():
            stack.append(label or f"«{tag}»")
    return loose


# Dấu `.sheet` trong ngăn xếp. Không phải một cái che: chữ trong `.sheet` mà
# ngoài mọi vùng vẫn là mồ côi -- nó chỉ nói "run này có vào ảnh".
_SHEET = "«.sheet»"


def _in_sheet(stack: list[str]) -> bool:
    return _SHEET in stack


def stack_shelters(stack: list[str]) -> bool:
    """Ngăn xếp này có tổ tiên nào che cho run bên trong không.

    Mục nào không bắt đầu bằng `/` là một cái che -- hoặc nhãn vùng đã khai,
    hoặc dấu `«table»`/`«img»` của một phép đo riêng."""
    return any(not item.startswith("/") and item != _SHEET for item in stack)


def orphan_share(html: str) -> tuple[int, int]:
    """`(số run mồ côi, tổng số run có chữ)`. Chia lấy tỉ lệ."""
    from pipeline.tags import (OPEN_CLOSE, VOID_TAGS, has_kind)      # noqa: PLC0415

    total, stack = 0, []
    for match in OPEN_CLOSE.finditer(html):
        closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if tag in VOID_TAGS or match.group(4):
            continue
        if closing:
            while stack:
                if stack.pop() == f"/{tag}":
                    break
            continue
        in_sheet = _in_sheet(stack)
        stack.append(f"/{tag}")
        if _SHEET_CLASS.search(attrs):
            stack.append(_SHEET)
        if not has_kind(attrs) or not in_sheet:
            continue
        rest = html[match.end():]
        cut = rest.find("<")
        if (rest if cut < 0 else rest[:cut]).strip():
            total += 1
    return len(orphan_runs(html)), total


def visible_chars(html: str) -> int:
    """Tổng ký tự chữ hiển thị trong mọi `.sheet` của trang này.

    KHÔNG dùng số này để GÁC theo một hằng số "ký tự mỗi tờ A4" -- đã thử
    (Phase 8, `docs/ke-hoach-refactor-engine.md`) và đo trực tiếp trên
    pilot16 thấy sai: một tài liệu kiểu key-value xếp dọc (`authorisation_
    letter`, mỗi trường một dòng: "Năm sinh: 1952" chiếm nguyên một dòng
    cao dù chỉ vài ký tự) đo được ~1 150 ký tự MỖI TỜ THẬT -- so với 8 000
    ký tự/tờ ước lượng từ tài liệu văn xuôi/bảng dày. Cùng một trang, chênh
    lệch bảy lần. Không có một hằng số nào đúng cho mọi kiểu bố cục mà
    track 3 CỐ TÌNH đa dạng ra. Số tờ THẬT chỉ trình duyệt (`synthgen/
    draw_llm.py`, cắt theo chiều cao A4 thật) mới biết chắc -- xem
    `agent/compose_page.py::_reconcile_sheet_count`, chạy SAU khi dàn
    trang, không phải ước lượng TRƯỚC."""
    parser = _Visible()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:                                         # noqa: BLE001
        return 0
    return parser.chars


def coined(html: str) -> list[str]:
    """Những `data-kind` trang này tự đặt -- không có trong từ vựng engine và
    không có gốc nào trong đó.

    ĐO, không gác. Từ vựng mở là một quyết định có giá: nếu hai tờ nói về
    cùng một khái niệm mà đặt hai tên, `kie_schema.groups()` (khoá theo tiền
    tố) xếp chúng vào hai nhóm và schema phân mảnh. Không có cách nào biết
    điều ấy đang xảy ra tới đâu ngoài việc đếm, nên hàm này tồn tại để
    `tools/llm/corpus_stats.py` và các phép đo bộ dữ liệu gọi được.
    """
    known = kinds()
    parser = _Spans()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:                                             # noqa: BLE001
        return []
    fresh = {s["kind"] for s in parser.spans
             if s["kind"] not in known and not _rooted(s["kind"], known)}
    return sorted(fresh)


def path_coverage(html: str) -> dict:
    """Đo, KHÔNG gác: bao nhiêu phần `data-kind` cũng có `data-path`.

    Tách khỏi `problems()` có chủ đích -- xem lời giải thích tại chỗ gọi
    `_PATH` ở trên. Dùng cho thống kê corpus (Phase 2/8,
    `docs/ke-hoach-refactor-engine.md`), không phải để loại trang."""
    parser = _Spans()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:                                             # noqa: BLE001
        return {"spans": 0, "with_path": 0, "coverage": 0.0}
    total = len(parser.spans)
    with_path = sum(1 for s in parser.spans if s.get("path"))
    return {"spans": total, "with_path": with_path,
           "coverage": round(with_path / total, 4) if total else 0.0}


__all__ = ["FORBIDDEN", "REGIONS", "SAMPLE", "acceptable_kind",
           "coined", "declared_paths",
          "kinds", "path_coverage", "printed_kinds", "problems"]
