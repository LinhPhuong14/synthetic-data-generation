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
* **`data-kind` phải nằm trong từ vựng.** Một kind lạ không tra được nhãn bố
  cục, nên đoạn chữ ấy rơi về nhãn mặc định và không ai biết.
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
                    "key": str(at.get("data-key") or "")}
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
            found.append(
                f'run `{span["kind"]}` có thẻ lồng bên trong; phép đo lấy '
                "`span.firstElementChild || span` nên thẻ ấy THÀNH cái hộp "
                "được ghi -- run có nhãn phải chỉ chứa chữ")
        if span["kind"] not in known and not _rooted(span["kind"], known):
            found.append(f'`data-kind="{span["kind"]}"` không có trong từ vựng, '
                         "và không có tiền tố nào là một kind thật")
        seen_kind[span["kind"]] = seen_kind.get(span["kind"], 0) + 1
    if not parser.spans:
        found.append("không có run nào mang `data-kind`; trang không có nhãn nào")

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


__all__ = ["FORBIDDEN", "REGIONS", "SAMPLE", "kinds", "problems"]
