"""Chữa những lỗi HTML mà MÁY chữa được, trước khi đem ra cổng gác.

## Vì sao có file này

Đo trên pilot5 và pilot6: mọi tờ bị loại đều trượt vì **kỷ luật đánh dấu**,
không phải vì model nghĩ sai. Nó nghĩ ra đúng loại chứng từ, đúng cơ quan phát
hành, đúng người ký -- rồi viết `<td class="lbl">` thay vì `<td data-cell>`, và
cả trang ba trăm giây đổ đi.

Hai lỗi ấy có một tính chất chung: **chữa chúng không cần phán đoán**. Một `<td>`
trong `<table>` LUÔN phải có `data-cell`; không có ngữ cảnh nào làm điều ấy sai.
Một `<br>` trong span có nhãn LUÔN phải tách thành hai span; chính lời dặn đã
bảo thế. Không có chỗ nào để đoán, nên không có chỗ nào để đoán sai.

Và khi một việc không cần phán đoán thì **đừng nhờ model làm**: nhờ nó là trả
giá bằng tỉ lệ hỏng cho một việc mười dòng mã làm đúng mọi lần. Đây đúng là
ranh giới kho này vẫn giữ -- `synthgen/markup.py` không "cố gắng" phát
`data-cell`, nó phát theo cấu tạo. File này kéo HTML model viết về cùng chỗ ấy.

## Vì sao KHÔNG chữa nhiều hơn

Chỉ chữa thứ có đúng một cách chữa. Một `data-kind` model tự bịa thì KHÔNG chữa
-- đoán xem nó định nói gì là đoán, và một cái hộp gán nhãn đoán còn tệ hơn một
cái hộp không có. Thứ ấy để cổng gác loại, và để `enum` trong schema chặn từ
đầu.
"""

from __future__ import annotations

import re

# `<td>`/`<th>` chưa có `data-cell`. Bắt cả thẻ không thuộc tính (`<td>`) lẫn
# thẻ có thuộc tính khác (`<td class="lbl">`), nhưng không bắt thẻ đã đúng.
_CELL = re.compile(r"<(t[dh])(?![a-z-])((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
                   re.IGNORECASE)
# Một span có nhãn, lấy trọn tới `</span>` gần nhất.
# Nháy đơn hay nháy kép đều là HTML hợp lệ, và model dùng cả hai. Bản trước
# chỉ bắt nháy kép, nên trang viết `data-kind='...'` không được vá `<br>` --
# nó trượt cổng vì một lỗi máy chữa được, chỉ tại cái regex kén dấu nháy.
# Ba kiểu viết thuộc tính của HTML5 -- `k="v"`, `k='v'`, `k=v` -- và model
# dùng cả ba. Bản trước chỉ bắt nháy kép, nên trang viết nháy đơn hay không
# nháy không được vá `<br>`: nó trượt cổng vì một lỗi máy chữa được, chỉ tại
# cái regex kén dấu nháy. Xem `synthgen/llm_page.py::printed_kinds`.
_SPAN = re.compile(
    r"""<span([^>]*\bdata-kind=(?:"[^"]*"|'[^']*'|[^\s>]+)[^>]*)>(.*?)</span>""",
    re.IGNORECASE | re.DOTALL)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def cells(html: str) -> tuple[str, int]:
    """Thêm `data-cell` vào mọi ô bảng còn thiếu. `(html, số ô đã thêm)`."""
    added = 0

    def fix(m: re.Match) -> str:
        nonlocal added
        attrs = m.group(2)
        if re.search(r"\bdata-cell\b", attrs, re.IGNORECASE):
            return m.group(0)
        added += 1
        return f"<{m.group(1)} data-cell{attrs}>"

    return _CELL.sub(fix, html), added


def breaks(html: str) -> tuple[str, int]:
    """Tách `<br>` trong span có nhãn thành hai span. `(html, số chỗ tách)`.

    `<span data-kind="k">A<br>B</span>` -> `<span data-kind="k">A</span><br>
    <span data-kind="k">B</span>`. Cùng chữ, cùng cách xuống dòng, cùng nhãn --
    khác mỗi chỗ: giờ mỗi hộp đo được ôm đúng một dòng chữ, thay vì một hộp ôm
    cái `<br>` rộng 5,3 px."""
    split = 0

    def fix(m: re.Match) -> str:
        nonlocal split
        attrs, inner = m.group(1), m.group(2)
        if not _BREAK.search(inner):
            return m.group(0)
        parts = [p for p in _BREAK.split(inner)]
        # Chỉ tách khi MỌI mảnh là chữ thuần -- còn thẻ khác thì không phải
        # việc của hàm này, để cổng gác loại.
        if any(_TAG.search(p) for p in parts):
            return m.group(0)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            return m.group(0)
        split += len(parts) - 1
        return "<br>".join(f"<span{attrs}>{p}</span>" for p in parts)

    return _SPAN.sub(fix, html), split


# Ký tự mà sau nó CHẮC CHẮN phải có khoảng trắng, khi một thẻ inline khác nối
# ngay sau mà nguồn không chừa lấy một ký tự trắng nào.
#
# Không rút từ corpus như `PUNCTUATION`: đây là lẽ nhà in chứ không phải thói
# quen của bộ dữ liệu. Dấu hai chấm kết một nhãn, dấu chấm kết một câu, ô vuông
# kết một ô đánh dấu -- sau cả ba, khoảng trắng thuộc về.
#
# Cố tình KHÔNG có `(`, `/`, `-`: sau chúng khoảng trắng là SAI ("12/2024",
# "(BHXH)"). Cũng cố tình không nhận chữ cái: model hay đậm một khúc giữa từ,
# và chèn khoảng trắng vào đấy là xé chữ làm đôi.
BREATH = frozenset(":.,;?!%)]»”’☐☒✓✗")

_INLINE = r"(?:span|b|strong|em|i|u|small)"
_TOUCHING = re.compile(rf">([^<>]{{1,120}})</{_INLINE}>(<{_INLINE}\b)")


def breathe(html: str) -> tuple[str, int]:
    """Trả lại khoảng trắng giữa hai thẻ inline dính nhau.

    Model viết `...khách hàng:</span><span ...>Trần Văn Hùng</span>` -- không
    một ký tự trắng giữa hai thẻ, nên HTML in ra đúng như thế: "khách
    hàng:Trần Văn Hùng". Không phải lỗi hộp, chữ thật sự dính. Đo trên
    pilot15: 486 chỗ dính, và 20% cặp nhãn->giá trị có hộp nhãn kết thúc đúng
    tại toạ độ hộp giá trị bắt đầu -- không một pixel trắng để cắt.

    Chữa ở nguồn chứ không bằng CSS `margin-left`: lề đẩy HỘP ra xa nhau
    nhưng không sinh khoảng trắng nào cho mắt người đọc, nên ảnh vẫn là hai
    chữ dính và chỉ có nhãn trông sạch.
    """
    count = 0

    def space(match: re.Match[str]) -> str:
        left = match.group(1).rstrip()
        if not left or left[-1] not in BREATH:
            return match.group(0)
        nonlocal count
        count += 1
        return f"{match.group(0)[:-len(match.group(2))]} {match.group(2)}"

    return _TOUCHING.sub(space, html), count


# Khe tối thiểu giữa hai run in cạnh nhau, khi khoảng trắng trong nguồn không
# tới được mắt người đọc.
#
# `breathe` trả khoảng trắng vào NGUỒN, và trong dòng chảy thường thế là đủ.
# Nhưng model hay dựng hàng nhãn/giá trị bằng `display:flex` -- pilot15 có
# `.fld{display:flex;margin:2.5mm 0;font-size:8.5pt}`, một quy tắc flex quên
# `gap`, trong khi mọi quy tắc flex của `synthgen/markup.py` đều có. Flex VỨT
# BỎ khoảng trắng giữa các item, nên khoảng trắng `breathe` chèn vào biến mất
# và hai hộp vẫn chạm nhau đúng một toạ độ: hộp nhãn hết ở x=310, hộp giá trị
# bắt đầu ở x=310, không một pixel để cắt.
#
# Không sửa `.fld` vì `.fld` là class MODEL tự đặt, không phải của engine --
# pilot15 chỉ một trang dùng tên ấy. Quy tắc dưới đây không đọc tên class nào,
# cũng không đọc tên `kind` nào: chỉ nói rằng hai run in liền nhau thì phải có
# khe. Đặt cuối `<head>` để thắng CSS model tự viết ở cùng độ đặc hiệu.
_AIR = ("<style>span[data-kind]+span[data-kind]{margin-left:.25em}</style>")
# Neo theo thứ tự ưu tiên `</body>` rồi `</head>`: quy tắc phải nằm SAU
# `<style>` model tự viết mới thắng ở cùng độ đặc hiệu, và cuối `<body>` thì
# chắc chắn sau. Có `</head>` làm nước hai vì 4/11 trang pilot15 model viết
# thành mảnh không có `<head>` nào -- neo vào mỗi `</head>` thì bốn trang ấy
# lặng lẽ không nhận được gì.
_ANCHORS = (re.compile(r"</body\s*>", re.I), re.compile(r"</head\s*>", re.I))


def airy(html: str) -> tuple[str, int]:
    """Chèn khe tối thiểu giữa hai run in cạnh nhau. Xem `_AIR`."""
    if _AIR in html:
        return html, 0
    for anchor in _ANCHORS:
        if anchor.search(html):
            return anchor.sub(lambda m: _AIR + m.group(0), html, count=1), 1
    return html + _AIR, 1


def repair(html: str) -> tuple[str, dict[str, int]]:
    """Chữa hết những gì chữa được. `(html mới, {việc: số lần})`."""
    from synthgen.llm_page import kinds                        # noqa: PLC0415

    # BỌC TRƯỚC, rồi mới chữa. `tagged` dựng run từ thẻ ngữ nghĩa, và những run
    # ấy phải có mặt trước khi `dress` bóc thẻ trang trí và `vocabulary` ánh xạ
    # tên lạ -- ngược thứ tự thì hai bước sau không thấy chúng.
    html, n_tagged = tagged(html)
    html, n_cells = cells(html)
    html, n_breaks = breaks(html)
    html, n_kinds = vocabulary(html, kinds())
    html, n_dress = dress(html)
    html, n_grid = grid(html)
    html, n_air = breathe(html)
    html, n_gap = airy(html)
    return html, {"khoảng trắng trả lại giữa hai thẻ dính": n_air,
                  "khe tối thiểu giữa hai run": n_gap,"run dựng từ thẻ HTML": n_tagged, "data-cell thêm": n_cells, "span tách khỏi <br>": n_breaks,
                  "kind lạ ánh xạ về thật": n_kinds,
                  "thẻ trang trí bóc khỏi span": n_dress,
                  "ô bảng được đánh số hàng/cột": n_grid}


# Đuôi nói rằng đoạn chữ ấy là NHÃN của một trường, không phải giá trị.
# Không đoán bằng ngữ nghĩa -- chỉ nhận đúng những đuôi model thật sự viết ra,
# đo trên `data/pilot*/rejected`.
_LABELLISH = ("label", "lbl", "key", "caption", "heading", "title_label")


def settle(kind: str, known: frozenset[str]) -> str:
    """Kind THẬT gần nhất với cái tên model tự đặt.

    ## Vì sao ánh xạ thay vì loại

    Từ vựng là danh sách NHÃN, không phải danh sách ý tưởng. Khi model nghĩ ra
    một tờ biên lai và viết `data-kind="fee.label"` / `fee.value`, nó không sai
    về tờ giấy -- nó chỉ gọi tên một thứ mà bảng nhãn chưa có tên riêng. Đo
    trên pilot9: 8 lần trượt trên 4 tờ, tất cả là hai cái tên ấy. Bốn tờ đúng
    nội dung, đúng bố cục, đúng mọi luật khác, bị vứt vì hai chữ.

    Và cái giá của việc loại là tuyệt đối: một tờ bị loại cho **không** nhãn
    nào. Một tờ được ánh xạ cho nhãn hơi rộng hơn mức model định nói. Rộng hơn
    vẫn là một nhãn đúng -- `fee.label` LÀ nhãn của một cặp nhãn-giá trị.

    ## Vì sao chỉ hai đích

    `invoice.field` và `invoice.field.label` là chỗ chứa cặp nhãn-giá trị chung
    chung, và chính lời dặn đã nói thế với model. Ánh xạ sang cái gì cụ thể hơn
    -- `menu.qty` chẳng hạn -- là đoán, và một cái hộp mang nhãn đoán còn tệ
    hơn một cái hộp mang nhãn rộng.

    Thứ tự: tên thật giữ nguyên; tên có gốc thật (`_rooted`, ví dụ
    `sign.name2`) giữ nguyên để cổng tự nhận; còn lại về một trong hai."""
    from synthgen.llm_page import _rooted                      # noqa: PLC0415

    name = str(kind or "").strip()
    if not name or name in known or _rooted(name, known):
        return name
    tail = name.rsplit(".", 1)[-1].lower()
    if any(word in tail for word in _LABELLISH):
        return "invoice.field.label"
    return "invoice.field"


def vocabulary(html: str, known: frozenset[str]) -> tuple[str, int]:
    """Viết lại mọi `data-kind` lạ thành kind thật. `(html, số chỗ đổi)`."""
    changed = 0

    def fix(m: re.Match) -> str:
        nonlocal changed
        was = m.group(1)
        now = settle(was, known)
        if now == was:
            return m.group(0)
        changed += 1
        return f'data-kind="{now}"'

    return re.sub(r'data-kind="([^"]*)"', fix, html), changed

# Thẻ trang trí lồng trong span có nhãn, và kiểu dáng tương đương để chuyển lên
# chính cái span. Chỉ những thẻ mà việc bóc ra KHÔNG mất thông tin nào -- chữ
# giữ nguyên, nét đậm/nghiêng/gạch chân giữ nguyên, chỉ khác chỗ khai.
_DRESS = {
    "b": "font-weight:700", "strong": "font-weight:700",
    "i": "font-style:italic", "em": "font-style:italic",
    "u": "text-decoration:underline",
    "small": "font-size:.85em", "span": "",
}
_INNER = re.compile(
    r'<span([^>]*\bdata-kind="[^"]*"[^>]*)>\s*<([a-z]+)(?:\s[^>]*)?>(.*?)</\2>\s*</span>',
    re.IGNORECASE | re.DOTALL)


def dress(html: str) -> tuple[str, int]:
    """Bóc thẻ trang trí ra khỏi span có nhãn, chuyển kiểu lên span.

    `<span data-kind="k"><b>X</b></span>` -> `<span data-kind="k"
    style="font-weight:700">X</span>`. Cùng chữ, cùng nét đậm, khác mỗi chỗ:
    `span.firstElementChild` không còn bắt được thẻ nào, nên hộp được ghi là
    hộp của chữ chứ không phải hộp của `<b>`.

    ## Vì sao không để lời dặn lo

    Lời dặn đã lo, và lo rất kỹ: một mục riêng, chữ in đậm "KHÔNG được lồng thẻ
    vào trong nó", ba ví dụ sai có thật kèm số đo (`<sub>` làm hộp rộng 5,3 px
    thay vì 310,6), và một câu chỉ thẳng cách làm đúng. Rồi khi chính tôi ngồi
    viết một tờ theo đúng lời dặn ấy, tôi vẫn viết `<b>` trong
    `masthead.motto` và `<i>` trong `sign.note` -- ba lần trên một trang.

    Không phải vì lời dặn kém. Vì "in đậm dòng khẩu hiệu" và "để chú thích
    trong ngoặc nghiêng" là phản xạ khi viết HTML, và phản xạ không đọc lời
    dặn. Một luật mà người viết cẩn thận nhất vẫn phạm là luật nên để máy lo.

    Chỉ bóc thẻ trang trí. `<br>` do `breaks()` lo (tách thành hai span, vì
    xuống dòng KHÔNG chuyển được thành kiểu dáng). Thẻ khác -- `<table>`,
    `<div>` -- để cổng loại: bóc chúng ra là đổi cấu trúc trang."""
    changed = 0

    def fix(m: re.Match) -> str:
        nonlocal changed
        attrs, tag, inner = m.group(1), m.group(2).lower(), m.group(3)
        if tag not in _DRESS or _TAG.search(inner):
            return m.group(0)
        changed += 1
        style = _DRESS[tag]
        if not style:
            return f"<span{attrs}>{inner}</span>"
        got = re.search(r'style="([^"]*)"', attrs, re.IGNORECASE)
        if got:
            attrs = attrs.replace(got.group(0),
                                  f'style="{got.group(1).rstrip(";")};{style}"')
        else:
            attrs = f'{attrs} style="{style}"'
        return f"<span{attrs}>{inner}</span>"

    return _INNER.sub(fix, html), changed


_TABLE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
_TR = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
_TDTH = re.compile(r"<(t[dh])\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.IGNORECASE)
_SPAN_N = lambda a, n: int(                                     # noqa: E731
    (re.search(rf'\b{n}=["\']?(\d+)', a, re.IGNORECASE) or ["", 1])[1] or 1)
_THEAD = re.compile(r"<thead\b.*?</thead>", re.IGNORECASE | re.DOTALL)


def grid(html: str) -> tuple[str, int]:
    """Đánh số hàng/cột cho mọi ô bảng. `(html, số ô đã đánh)`.

    ## Vì sao KIE mất sạch thân bảng

    `generators/html/page.py::CELL_REGIONS_JS` đọc `td.dataset.row` và
    `td.dataset.col`. Trang engine có hai thuộc tính ấy vì `markup.py` phát ra
    theo cấu tạo. Trang model viết thì KHÔNG -- lời dặn chỉ đòi `data-cell`, và
    `repair.cells()` cũng chỉ thêm đúng thứ ấy.

    Nên mỗi ô thân bảng ra `col: NaN`, không ô nào ghép được với tiêu đề cột
    của nó, và `synthgen/kie_full.py` bỏ cả bảng. Đo trên tờ biên bản thuế: bảng
    tám hàng bảy cột, năm mươi sáu ô mực, **không một trường nào vào KIE**. Tờ
    hợp đồng thuê cũng vậy với phần điều khoản.

    ## Vì sao máy tính được mà không phải đoán

    Số hàng và số cột của một ô là chuyện HÌNH HỌC của bảng, và `colspan` với
    `rowspan` nói đủ để tính -- đúng thuật toán trình duyệt tự chạy khi dàn
    bảng. Không có chỗ nào để đoán, nên không có chỗ nào để đoán sai.

    Bảng LỒNG thì bỏ qua: ô ngoài đã có số của nó, và một bảng trong một ô là
    một lưới thứ hai không chia trục với lưới ngoài."""
    marked = 0

    def one_table(m: re.Match) -> str:
        nonlocal marked
        body = m.group(0)
        if body.lower().count("<table") > 1:      # bảng lồng: để nguyên
            return body
        heads = {sp.start() for sp in _THEAD.finditer(body)}
        head_ranges = [(sp.start(), sp.end()) for sp in _THEAD.finditer(body)]
        # `busy[col]` = số hàng còn bị một `rowspan` phía trên chiếm.
        busy: dict[int, int] = {}
        row = [0]

        def one_row(rm: re.Match) -> str:
            nonlocal marked
            at = rm.start() + m.start() - m.start()
            in_head = any(a <= rm.start() < b for a, b in head_ranges)
            col = [0]

            def one_cell(cm: re.Match) -> str:
                nonlocal marked
                tag, attrs = cm.group(1), cm.group(2)
                if re.search(r"\bdata-col\b", attrs, re.IGNORECASE):
                    return cm.group(0)
                while busy.get(col[0], 0) > 0:
                    col[0] += 1
                span = _SPAN_N(attrs, "colspan")
                down = _SPAN_N(attrs, "rowspan")
                here = col[0]
                for c in range(here, here + span):
                    if down > 1:
                        busy[c] = down
                col[0] = here + span
                marked += 1
                return (f"<{tag} data-row=\"{row[0]}\" data-col=\"{here}\""
                        f"{attrs}>")

            out = _TDTH.sub(one_cell, rm.group(0))
            row[0] += 1
            for c in list(busy):
                busy[c] -= 1
                if busy[c] <= 0:
                    del busy[c]
            _ = (at, in_head, heads)
            return out

        return _TR.sub(one_row, body)

    return _TABLE.sub(one_table, html), marked


# THẺ HTML NÓI NÓ LÀ GÌ. Ánh xạ từ thẻ ngữ nghĩa sang `data-kind` thật.
#
# Vì sao cần: từ vựng `data-kind` nhặt từ chính HTML engine dựng, nên nó chỉ
# biết những gì engine biết vẽ. Model viết thứ engine không có -- tiêu đề mục,
# đoạn văn trong `<p>`, mục trong `<li>` -- và khi không tìm ra kind nào để
# gắn, nó khai vùng rồi để chữ trần. Đo trên pilot13: **72 trên 72** vùng
# `Section-Header` có chữ mà không một `<span data-kind>` nào. Phép đo chỉ thấy
# chữ trong run có nhãn, nên cả 72 tiêu đề mục mất hộp.
#
# Nhưng model ĐÃ nói nó là gì -- bằng thẻ. `<h2>` là tiêu đề mục, `<li>` là một
# mục danh sách, `<th>` là đầu cột. Đọc cái nó đã nói, thay vì đòi nó nói lại
# bằng một từ vựng nó không có.
#
# Đây cũng đúng cách bộ tham chiếu `pair_prompt100` gán nhãn vùng: `h1` 548
# lần, `p` 443, `li` 221, `h2` 193, `h3` 144, `footer` 87 -- không một
# `data-kind` nào trong cả trăm tờ.
BY_TAG = {
    "h1": "title", "h2": "section", "h3": "section", "h4": "section",
    "h5": "section", "h6": "section",
    "caption": "caption.table", "figcaption": "caption.figure",
    "th": "colhdr", "li": "clause.body", "blockquote": "note", "p": "note",
    "dt": "invoice.field.label", "dd": "invoice.field", "footer": "footer",
}

_BARE = {tag: re.compile(
    rf"<{tag}(?![a-z])((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>((?:(?!<{tag}[\s>])[^<]|<(?!/{tag}>))*?)</{tag}>",
    re.IGNORECASE | re.DOTALL) for tag in BY_TAG}


def tagged(html: str) -> tuple[str, int]:
    """Bọc chữ trần trong thẻ ngữ nghĩa bằng `<span data-kind>`.

    Chỉ chạm thẻ nào có chữ mà KHÔNG có `data-kind` nào bên trong -- thẻ model
    đã gắn nhãn thì để nguyên, vì nó biết rõ hơn cái bảng tra này.

    Giữ nguyên mọi thẻ trang trí bên trong (`<b>`, `<i>`): span bọc NGOÀI chúng
    thì `repair.dress` ở bước sau bóc ra, và thứ tự ấy đúng -- bọc trước, bóc
    sau, chứ không phải ngược lại."""
    wrapped = 0

    def wrap(tag: str, kind: str):
        def fix(m: re.Match) -> str:
            nonlocal wrapped
            attrs, inner = m.group(1), m.group(2)
            if "data-kind" in inner or not _TAG.sub("", inner).strip():
                return m.group(0)
            wrapped += 1
            return f'<{tag}{attrs}><span data-kind="{kind}">{inner}</span></{tag}>'
        return fix

    for tag, kind in BY_TAG.items():
        html = _BARE[tag].sub(wrap(tag, kind), html)
    return html, wrapped
