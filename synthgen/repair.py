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

from pipeline.tags import kind_by_tag as _kind_by_tag
from pipeline.tags import OPEN_CLOSE as _OPEN_CLOSE
from pipeline.tags import VOID_TAGS as _VOID_TAGS
from pipeline.tags import declared_region as _declared_region
from pipeline.tags import region_by_tag as _region_by_tag

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


REGION_BY_TAG = _region_by_tag()

def zoned(html: str) -> tuple[str, int]:
    """Gắn `data-region` lên thẻ ngữ nghĩa chưa khai vùng.

    ## Vì sao việc này chuyển từ phép đo sang đây

    `generators/html/page.py::ZONE_REGIONS_JS` từng có hai nhánh: vùng KHAI
    TAY, và vùng SUY TỪ THẺ (`<ul>` LÀ một danh sách, nên không bắt model khai
    thêm lần nữa). Hai nhánh nghĩa là hai đường tạo ra vùng, và một cái hộp
    không ai biết đến từ đường nào là một cái hộp không sửa được.

    Đưa phép suy về đây thì nó thành **một phép sửa HTML**, không còn là một
    phép đo song song: sau bước này, mọi vùng trên trang đều đến từ đúng một
    chỗ -- thuộc tính `data-region` nằm trong chính markup. Trang sửa xong
    đọc lên giống hệt trang model viết đủ ngay từ đầu, và `data/*/html/` lưu
    lại đúng thứ đã được đo.

    ## Nhãn đã có ở tổ tiên thì KHÔNG khai lại

    `<ul>` trong `<div data-region="List-Group">` là cùng một vùng nói hai
    lần. Nhánh suy-từ-thẻ cũ đã giữ đúng luật ấy; giữ nguyên nó ở đây, không
    phải vì tương thích mà vì nó đúng -- và vì đổi luật cùng lúc với đổi chỗ
    là hai thay đổi trong một, không tách được cái nào gây ra cái gì.

    ## Vá được bao nhiêu

    Đo trên 40 tờ model viết (`data/kind-mo3`, `kind-mo-vllm`, `pilot16`):
    926 run không nằm trong vùng nào, và **337 (36%) có tổ tiên là thẻ ngữ
    nghĩa** -- `<p>` 113, `<section>` 94, `<header>` 46, `<ol>` 28. Đó là
    phần hàm này lấy về.

    589 run còn lại (64%) nằm trong `<div class="field-row">`,
    `"checklist-item"`, `"field-value"` -- tên class do model tự đặt. Suy
    nhãn vùng từ những cái tên ấy là ĐOÁN, và file này không đoán: một cái
    hộp mang nhãn đoán còn tệ hơn một cái hộp không có nhãn. Phần ấy phải do
    model khai, và do cổng gác đòi."""
    stack: list[str] = []
    inserts: list[tuple[int, str]] = []
    for match in _OPEN_CLOSE.finditer(html):
        closing, tag = match.group(1), match.group(2).lower()
        attrs, selfclose = match.group(3), match.group(4)
        if tag in _VOID_TAGS:
            continue
        if closing:
            while stack:
                if stack.pop() == f"/{tag}":
                    break
            continue
        if selfclose:
            continue
        declared = _declared_region(attrs)
        label = REGION_BY_TAG.get(tag, "")
        if not declared and label and label not in stack:
            # Chèn ngay sau tên thẻ: `<ul class="x">` -> `<ul data-region=.. class="x">`.
            # Không chèn trước `>` cuối, vì một thẻ tự đóng viết `<x/>` sẽ
            # thành `<x data-region=".."/>` ở chỗ khác mất dấu gạch.
            inserts.append((match.start() + 1 + len(match.group(2)),
                            f' data-region="{label}"'))
            declared = label
        stack.append(f"/{tag}")
        if declared:
            stack.append(declared)
    if not inserts:
        return html, 0
    out = []
    at = 0
    for where, text in inserts:
        out.append(html[at:where])
        out.append(text)
        at = where
    out.append(html[at:])
    return "".join(out), len(inserts)


def zones(html: str) -> tuple[str, int]:
    """Đổi `data-region` model viết nhầm thành nhãn thật. `(html, số chỗ)`.

    Bảng ở `rulebase/synthgen/_blocks.yaml::region_alias` -- DỮ LIỆU, xem ghi
    chú trong chính file ấy. Ở đây chỉ có phép thay.

    Khớp KHÔNG PHÂN BIỆT HOA THƯỜNG, và một nhãn ĐÚNG viết sai hoa thường
    cũng được nắn: model viết `Masthead` và `masthead` trong cùng một lô, và
    `Page-header` với `Page-Header` là cùng một vùng đối với mắt người mà là
    hai thứ khác nhau đối với cổng gác.

    KHÔNG đoán ngoài bảng: tên lạ không có trong bí danh thì để nguyên, và
    cổng loại tờ ấy. Đúng nguyên tắc đầu file -- chỉ chữa thứ có đúng một
    cách chữa."""
    from synthgen.design import region_alias                   # noqa: PLC0415
    from synthgen.llm_page import REGIONS                      # noqa: PLC0415

    table = dict(region_alias())
    # Nhãn THẬT cũng vào bảng, để phép nắn hoa thường chạy cho chúng.
    table.update({label.lower(): label for label in REGIONS})
    if not table:
        return html, 0
    fixed = 0

    def swap(match: "re.Match") -> str:
        nonlocal fixed
        quote, name = match.group(1), match.group(2)
        key = name.strip().lower()
        # SỐ NHIỀU TRA VỀ SỐ ÍT. Model viết `Signatures`, `Notes`, `Figures`
        # -- cùng khái niệm, thêm một chữ `s`. Kê từng dạng vào YAML là kê một
        # quy tắc chính tả bằng danh sách; bỏ `s` khi trượt là nói ra quy tắc.
        #
        # An toàn vì KHÔNG nhãn thật nào trong hai mươi nhãn kết thúc bằng
        # `s` -- `tests/test_tags.py` giữ điều đó, nên phép bỏ `s` không bao
        # giờ biến một nhãn đúng thành nhãn khác.
        real = table.get(key) or (table.get(key[:-1]) if key.endswith("s")
                                  else None)
        if not real or real == name:
            return match.group(0)
        fixed += 1
        return f'data-region={quote}{real}{quote}'

    out = re.sub(r"""data-region=(["'])([^"']*)\1""", swap, html)
    return out, fixed


_SPAN_TAG = re.compile(r"<(/?)span\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
                       re.IGNORECASE)
# CÙNG bảng thẻ trang trí `_DRESS` (dưới) chấp nhận, cộng `span`. `dress()`
# chỉ bóc được khi thẻ lồng là con DUY NHẤT; `unnest()` là nước hai, nên nó
# phải nhận đúng những thẻ mà `dress()` coi là "trang trí, bóc không mất gì"
# -- khác bảng thì một thẻ `dress()` từ chối (vì không phải con duy nhất) lại
# lọt qua `unnest()` chưa từng nghe tên nó, và ngược lại.
#
# Bản trước chỉ khớp `<span>`. Đo trên `data/pilot16`: chín tờ trượt vì
# `<strong>`/`<b>` bọc một nhãn ngắn đứng TRƯỚC phần chữ còn lại của run --
# `<span data-kind="note"><strong>Bên giao thầu:</strong> Công ty…</span>` --
# và bản trước không thấy thẻ đó, vì nó không phải `<span>`. Vòng lặp bên
# dưới đếm ĐỘ SÂU thẻ, không đọc tên thẻ khi đóng (xem `unnest()`), nên gộp
# thêm những thẻ này vào cùng một biểu thức là đủ -- không có gì khác trong
# thân hàm phải đổi.
_INLINE_TAG = re.compile(
    r"<(/?)(?:span|b|strong|em|i|u|small)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
    re.IGNORECASE)
_HAS_KIND = re.compile(r"\bdata-kind\s*=", re.IGNORECASE)


def unnest(html: str) -> tuple[str, int]:
    """Bóc thẻ trang trí KHÔNG nhãn nằm trong `<span data-kind>`. `(html, số chỗ)`.

    `CELL_RECTS_JS` đo `span.firstElementChild || span`: một thẻ bất kỳ lồng
    trong run có nhãn LẶNG LẼ trở thành cái hộp được ghi. Trang vẫn vẽ ra,
    nhãn vẫn có, và nhãn sai.

    `dress()` ngay trên đã lo ca ấy, nhưng chỉ khi thẻ lồng là con DUY NHẤT
    (`_INNER` đòi `<span k><b>X</b></span>`). Model viết hai kiểu khác:

    * một span TRẦN đứng TRƯỚC chữ -- `<span data-kind="note"><span
      class="clause-number">1.</span> Nội dung…</span>`. Đo trên
      `data/23-09-llm-f`: 5 trên 12 tờ trượt vì đúng hình này.
    * một nhãn ngắn bọc `<strong>`/`<b>` đứng TRƯỚC phần chữ còn lại --
      `<span data-kind="note"><strong>Bên giao thầu:</strong> Công ty…
      </span>`. Đo trên `data/pilot16`: 9 trên 9 tờ trượt vì "thẻ lồng" đều
      đúng hình này (label bọc `<strong>`/`<b>`, hoặc bilingual bọc `<span>`
      không nhãn) -- không tờ nào là ca `dress()` với tới (con duy nhất).

    Cả hai đều là MỘT ĐOẠN chữ đứng trước phần còn lại, không phải toàn bộ
    run -- `dress()` không khớp vì `_INNER` đòi `</span>` ngay sau thẻ đóng.

    Một thẻ trang trí (`_INLINE_TAG`: `b`, `strong`, `em`, `i`, `u`, `small`,
    hoặc `span` không mang `data-kind`) thì THEO ĐỊNH NGHĨA không phải một
    trường -- nó không khai mình là gì. Bóc thẻ, giữ chữ: hộp trở lại đúng
    chữ, và cái mất là kiểu dáng của riêng mẩu ấy (không chuyển được lên
    `style` như `dress()`, vì nó không phải con duy nhất). Đổi một chút hình
    thức lấy một cái hộp đúng là đổi đúng chiều; trang bị loại thì mất cả
    hai.

    KHÔNG đụng span có nhãn lồng trong span có nhãn: đó là hai trường, và gộp
    chúng là đoán xem trường nào thắng."""
    out: list[str] = []
    at = 0
    depth = 0          # độ sâu thẻ inline đang mở (span HOẶC thẻ trang trí)
    labelled: list[int] = []   # độ sâu của những span CÓ nhãn đang mở
    drop: list[int] = []       # độ sâu của những thẻ đang bị bóc
    removed = 0
    # KHÔNG đọc tên thẻ lúc đóng, chỉ đọc ĐỘ SÂU -- `<strong>` mở tại độ sâu
    # 2 thì `</strong>` cũng đóng đúng độ sâu 2, bất kể đó là thẻ gì. Đây là
    # lý do gộp thêm `b`/`strong`/`em`/`i`/`u`/`small` vào `_INLINE_TAG`
    # không cần sửa gì dưới đây: thân vòng lặp vốn đã không phân biệt tên thẻ.
    for match in _INLINE_TAG.finditer(html):
        closing, attrs = match.group(1), match.group(2)
        if closing:
            if drop and drop[-1] == depth:
                drop.pop()
                out.append(html[at:match.start()])
                at = match.end()
                removed += 1
            if labelled and labelled[-1] == depth:
                labelled.pop()
            depth = max(depth - 1, 0)
            continue
        depth += 1
        has_kind = bool(_HAS_KIND.search(attrs))
        if has_kind:
            labelled.append(depth)
        elif labelled:
            # span trần BÊN TRONG một run có nhãn -> bóc
            drop.append(depth)
            out.append(html[at:match.start()])
            at = match.end()
    out.append(html[at:])
    return ("".join(out), removed) if removed else (html, 0)


_PATH_SPAN = re.compile(
    r'<span([^>]*\bdata-path\s*=\s*("([^"]*)"|\'([^\']*)\')[^>]*)>(.*?)</span>',
    re.IGNORECASE | re.DOTALL)
_PATH_ATTR = re.compile(r"""\s*\bdata-path\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""",
                        re.IGNORECASE)


def unclash(html: str) -> tuple[str, int]:
    """Bỏ `data-path` khỏi những run CÙNG đường dẫn mà KHÁC chữ.

    Cổng đòi "cùng `data-path` thì cùng giá trị", và đòi đúng: một đường dẫn
    là một DANH TÍNH, nên hai chữ khác nhau dưới một danh tính là bản ghi tự
    mâu thuẫn. Nhưng nó loại cả tờ, và cái mâu thuẫn ấy nằm ở một thuộc tính
    mà **chỉ 28% run có** -- `data-kind` (trục nhãn thật) và cái hộp thì vẫn
    đúng cả.

    Đo trên `data/23-09-llm-f`: 4 trên 12 tờ trượt vì đúng chuyện này, và
    nhìn HTML thì thấy model dùng lại `document.number` cho cả tiêu đề lẫn số
    hiệu -- hai `meta.value` khác chữ, một đường dẫn.

    ## Vì sao bỏ CẢ HAI chứ không giữ một

    Giữ cái đầu là đoán rằng cái đầu mới là chủ của đường dẫn. Đoán sai thì
    một run mang danh tính của run khác -- một nhãn SAI, im lặng, và nhãn sai
    tệ hơn nhãn thiếu. Bỏ cả hai thì không run nào mang danh tính sai; cái
    mất chỉ là một lời khai, và `data_path_mismatches` vốn là hàm ĐO chứ
    không phải hàm GÁC.

    Đường dẫn dùng lại mà CÙNG chữ thì để yên: đó là một giá trị in hai chỗ,
    và lời dặn cho phép -- xem mục 7 của `page.md`."""
    texts: dict[str, set[str]] = {}
    for match in _PATH_SPAN.finditer(html):
        path = match.group(3) if match.group(3) is not None else match.group(4)
        body = " ".join(_TAG.sub("", match.group(5)).split())
        if body:
            texts.setdefault(str(path), set()).add(body)
    clashing = {p for p, seen in texts.items() if len(seen) > 1}
    if not clashing:
        return html, 0
    dropped = 0

    def strip(match: "re.Match") -> str:
        nonlocal dropped
        attrs = match.group(1)
        path = match.group(3) if match.group(3) is not None else match.group(4)
        if str(path) not in clashing:
            return match.group(0)
        dropped += 1
        return f"<span{_PATH_ATTR.sub('', attrs, count=1)}>{match.group(5)}</span>"

    return _PATH_SPAN.sub(strip, html), dropped


_TBODY = re.compile(r"(<tbody\b[^>]*>)(.*?)(</tbody>)", re.IGNORECASE | re.DOTALL)
_TR = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
_ITEM_PATH = re.compile(r"\b(\w+)\[(\d+)\]\.(\w+)")
_DATA_ROW = re.compile(r'(\bdata-row=")(\d+)(")', re.IGNORECASE)
_CELL_SPAN = re.compile(
    r'(<span[^>]*\bdata-path="([^"]*)"[^>]*>)([^<]*)(</span>)', re.IGNORECASE)
# Con số TRONG một ô, kèm phần chữ hai bên (`6.720 USD`, `đ 1.250.000`).
_NUMBER_IN = re.compile(r"^(?P<head>\D*?)(?P<num>\d[\d.,]*)(?P<tail>\D*)$")
_GROUPED = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")


def _like(sample: str, value) -> str:
    """`value` viết theo ĐÚNG kiểu `sample` đang viết.

    Kiểu số lấy từ chính ô mẫu, không từ một quy ước đoán: ô đang in
    `1.250.000` thì dòng mới cũng in `1.250.000`; ô in `1250000` thì giữ
    nguyên thế. Ô mẫu là lời khai của model về cách tờ giấy này viết số, và
    đó là lời khai duy nhất có.

    ## Phần chữ hai bên cũng là kiểu

    Bản đầu chỉ nhận ô số THUẦN, nên `6.720 USD` không khớp `_GROUPED` và
    dòng mới in `6720`: mất cả dấu nhóm lẫn đơn vị. Đo trên `data/23-09-llm-h`:
    18 tờ trượt vì `('6.720 USD', '6720')`, `('30', '30 USD')` -- cùng một
    đường dẫn, hai cách viết, và cổng loại cả tờ.

    Giữ nguyên phần không phải số, thay đúng phần số: `6.720 USD` ->
    `7.200 USD`. Không đoán đơn vị nào cả -- nó đã có sẵn trong ô mẫu."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value if value is not None else "")
    number = int(value)
    body = " ".join(str(sample or "").split())
    got = _NUMBER_IN.match(body)
    if not got:
        return str(number)
    head, digits, tail = got.group("head"), got.group("num"), got.group("tail")
    if _GROUPED.match(digits):
        sep = "." if "." in digits else ","
        fresh = f"{number:,}".replace(",", sep)
    else:
        fresh = str(number)
    return f"{head}{fresh}{tail}"


def rows_out(html: str, rows) -> tuple[str, int]:
    """Dựng nốt những dòng bảng model đã KHAI mà không vẽ. `(html, số dòng)`.

    ## Vì sao việc này tồn tại

    Model trả về hai thứ cho cùng một cái bảng: mảng `rows` trong JSON, và các
    `<tr>` trong HTML. Chúng lệch nhau, và lệch rất xa. Đo trên 48 tài liệu
    (`data/23-09-llm-d..g`): **22 tài liệu khai nhiều dòng hơn vẽ**, tệ nhất
    là khai 129 dòng và vẽ 18.

    Hệ quả đo được là cái cổng "xin N tờ, dàn ra M<N" -- 11 trên 12 tờ của lô
    `g` trượt vì đúng nó, và mọi lỗi markup khác đã hết. Bảng không dài ra thì
    không có gì để cắt sang tờ sau.

    ## Vì sao KHÔNG phải bịa nội dung

    Chữ của dòng mới là chữ MODEL ĐÃ VIẾT, nằm sẵn trong `rows`. Engine không
    nghĩ ra một mặt hàng nào, không tra corpus nào. Nó chỉ đưa vào HTML thứ đã
    có trong câu trả lời -- và `rows` chính là mảng mà phép kiểm số học
    (`qty × unit_price == amount`) vẫn chấm, nên nội dung ấy đã được soi.

    ## Vì sao không cần đoán cột nào là cột nào

    Dòng mẫu mang sẵn câu trả lời: `data-path="line_items[13].name"` nói cả
    CHỈ SỐ lẫn TÊN TRƯỜNG. Nhân bản dòng cuối rồi thay chỉ số và giá trị là
    một phép chép, không phải một phép suy. Kiểu viết số cũng lấy từ ô mẫu
    (xem `_like`), nên dòng mới không lạc kiểu với dòng cũ.

    Không có `<tbody>`, không có `<tr>` nào, hay dòng cuối không mang
    `data-path` dạng `x[i].y` -- thì KHÔNG làm gì: không có mẫu nào để chép,
    và dựng một dòng từ hư không là đúng thứ file này không làm."""
    items = [r for r in (rows or []) if isinstance(r, dict)]
    if len(items) < 2:
        return html, 0
    # ĐÚNG MỘT BẢNG MANG ĐƯỜNG DẪN `x[i].y`, nếu không thì không làm gì.
    #
    # `rows` tả MỘT cái bảng. Tờ giấy có thể có nhiều: đo trên 18 tài liệu,
    # **6 tờ có từ hai `<tbody>` trở lên** -- bảng dàn trang ở đầu tờ, bảng
    # tổng ở cuối, bảng con trong một ô. Bơm dòng vào cái ĐẦU TIÊN là đoán
    # rằng `rows` tả cái ấy, và đoán sai thì một bảng dài ra bằng nội dung
    # của bảng khác.
    #
    # Lọc theo đường dẫn chứ không theo thứ tự: bảng dàn trang không mang
    # `line_items[i].name` nào, nên nó tự rơi ra. Còn lại đúng một cái thì
    # không có gì để đoán; hai cái thì có, và khi ấy dừng.
    bodies = [m for m in _TBODY.finditer(html) if _ITEM_PATH.search(m.group(2))]
    if len(bodies) != 1:
        return html, 0
    found = bodies[0]
    body = found.group(2)
    drawn = _TR.findall(body)
    if not drawn:
        return html, 0
    template = drawn[-1]
    seats = _ITEM_PATH.findall(template)
    if not seats:
        return html, 0
    root, at, _field = seats[0]
    at = int(at)
    if at + 1 >= len(items):
        return html, 0

    # NẮN CHÍNH DÒNG MẪU TRƯỚC. Một dòng có MỘT danh tính, nên mọi ô của nó
    # phải mang một chỉ số. Model viết lệch -- `line_items[0].name` cạnh
    # `line_items[10].muc` trong cùng một `<tr>` -- và nếu để nguyên thì bản
    # nhân ở chỉ số 10 đụng đúng ô lệch ấy: một đường dẫn, hai chữ, cổng loại
    # cả tờ.
    seat_now = re.compile(rf"\b{re.escape(root)}\[\d+\]\.")
    fixed_template = seat_now.sub(f"{root}[{at}].", template)
    if fixed_template != template:
        body = body.replace(template, fixed_template, 1)
        template = fixed_template

    row_no = _DATA_ROW.search(template)
    base_row = int(row_no.group(2)) if row_no else at

    made: list[str] = []
    for step, item in enumerate(items[at + 1:], start=1):
        index = at + step

        def swap(match: "re.Match", item=item, index=index) -> str:
            head, path, text, tail = match.groups()
            got = _ITEM_PATH.search(path)
            if not got or got.group(1) != root:
                return match.group(0)
            field = got.group(3)
            # Cột số thứ tự đếm theo CHỖ NGỒI, không có trong `rows`.
            value = (index + 1 if field in ("stt", "no", "index", "num")
                     else item.get(field))
            if value is None:
                return match.group(0)
            fresh = head.replace(f"{root}[{at}].", f"{root}[{index}].")
            return f"{fresh}{_like(text, value)}{tail}"

        clone = _CELL_SPAN.sub(swap, template)
        # MỌI chỉ số trong dòng nhân bản về `index`, không chỉ chỉ số của ô
        # ĐẦU TIÊN.
        #
        # Bản trước thay chuỗi `root[at].` -- tức giả định mọi ô trong dòng
        # mẫu dùng chung một chỉ số. Model không nhất quán thế: một ô mang
        # `line_items[6].quantity` cạnh một ô `line_items[16].muc`. Ô lệch
        # giữ nguyên chỉ số cũ ở MỌI dòng nhân ra, nên một đường dẫn mang hai
        # chữ khác nhau và cổng loại cả tờ -- đo được trên `xin 8 -> cắt ra 4
        # tờ`, một tờ 433 cặp KIE mất trắng vì đúng chuyện này.
        clone = re.sub(rf"\b{re.escape(root)}\[\d+\]\.",
                       f"{root}[{index}].", clone)
        clone = _DATA_ROW.sub(
            lambda m: f"{m.group(1)}{base_row + step}{m.group(3)}", clone)
        made.append(clone)

    if not made:
        return html, 0
    filled = found.group(1) + body + "".join(made) + found.group(3)
    return html[:found.start()] + filled + html[found.end():], len(made)


def repair(html: str) -> tuple[str, dict[str, int]]:
    """Chữa hết những gì chữa được. `(html mới, {việc: số lần})`."""
    from synthgen.llm_page import kinds                        # noqa: PLC0415

    # BỌC TRƯỚC, rồi mới chữa. `tagged` dựng run từ thẻ ngữ nghĩa, và những run
    # ấy phải có mặt trước khi `dress` bóc thẻ trang trí và `vocabulary` ánh xạ
    # tên lạ -- ngược thứ tự thì hai bước sau không thấy chúng.
    html, n_tagged = tagged(html)
    html, n_zoned = zoned(html)
    # NẮN TÊN VÙNG TRƯỚC khi đếm vùng: `zoned` chỉ thêm vùng cho thẻ
    # CHƯA khai, nên một thẻ khai sai tên vẫn coi là đã khai và không
    # được vá -- nắn sau thì nó đã lỡ chặn `zoned` rồi.
    html, n_zones = zones(html)
    html, n_cells = cells(html)
    html, n_kinds = vocabulary(html, kinds())
    html, n_dress = dress(html)
    # SAU `dress`: nó chuyển được kiểu dáng lên span khi thẻ lồng là con
    # duy nhất, và đó là cách chữa TỐT HƠN. `unnest` là nước hai, cho
    # những hình `dress` không với tới.
    html, n_unnest = unnest(html)
    # `breaks` SAU `dress`/`unnest`, không phải TRƯỚC như bản cũ.
    #
    # `breaks` chỉ tách khi MỌI mảnh giữa các `<br>` là chữ thuần -- gặp thẻ
    # nào khác thì bỏ qua, để cổng loại. Chạy trước `unnest` thì một run kiểu
    # `<span data-kind="colhdr">Tên hàng<br><span class="en">Name</span>
    # </span>` vẫn còn thẻ `<span class="en">` lúc `breaks` nhìn vào, nên nó
    # bỏ qua -- rồi `unnest` bóc cái span con ấy NGAY SAU, nhưng `breaks` đã
    # chạy xong, không còn lượt hai. Đo trên `data/pilot16`: cả 5 chỗ `colhdr`
    # trượt cổng đều đúng hình này -- `unnest` (bản cũ) đã bóc được `<span
    # class="en">`, để lại đúng một `<br>` trần mà không ai tách nữa.
    #
    # Đổi chỗ thì `unnest` bóc thẻ trang trí TRƯỚC, nên tới lượt `breaks` mọi
    # mảnh đã là chữ thuần và tách được.
    html, n_breaks = breaks(html)
    # SAU `breaks`: một run tách theo `<br>` giữ NGUYÊN `data-path` của run
    # gốc trên MỌI mảnh (xem `breaks()`), nên hai mảnh chữ khác nhau có thể
    # vừa mới được gán chung một đường dẫn -- đúng thứ `unclash` sinh ra để
    # bắt. Không chạy sau thì `breaks` tự tạo ra một tờ mắc đúng lỗi
    # `unclash` đáng lẽ đã dọn.
    html, n_unclash = unclash(html)
    html, n_grid = grid(html)
    html, n_air = breathe(html)
    html, n_gap = airy(html)
    return html, {"khoảng trắng trả lại giữa hai thẻ dính": n_air,
                  "khe tối thiểu giữa hai run": n_gap,"run dựng từ thẻ HTML": n_tagged,
                  "vùng khai từ thẻ HTML": n_zoned,
                  "tên vùng nắn lại": n_zones, "data-cell thêm": n_cells, "span tách khỏi <br>": n_breaks,
                  "kind lạ ánh xạ về thật": n_kinds,
                  "thẻ trang trí bóc khỏi span": n_dress,
                  "span trần bóc khỏi run": n_unnest,
                  "data-path đụng nhau đã bỏ": n_unclash,
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

    ## Từ vựng đã mở -- hàm này còn làm gì

    Cổng (`llm_page.problems`) không còn đòi kind nằm trong từ vựng: một tên
    tự đặt đúng ngữ pháp `họ.trường` được nhận nguyên văn, vì đó chính là
    model đặt tên cho khái niệm engine chưa có. Nên việc còn lại ở đây hẹp
    hơn hẳn: **chuẩn hoá HÌNH THỨC**, không đổi NGHĨA.

    `Hoa_Don.So` và `hoa-don.so` là cùng một cái tên viết sai kiểu chữ; ép
    chúng về `hoa_don.so` giữ nguyên ý model muốn nói. Chỉ cái tên vẫn không
    đọc được sau khi chuẩn hoá -- một đoạn duy nhất, không họ, hoặc có ký tự
    ngoài bảng chữ -- mới về hai kind chung, vì khi ấy không còn gì để giữ.

    Thứ tự: tên thật giữ nguyên; tên có gốc thật (`_rooted`, ví dụ
    `sign.name2`) giữ nguyên để cổng tự nhận; tên tự đặt đọc được thì giữ
    nguyên hình đã chuẩn hoá; còn lại về một trong hai."""
    from synthgen.llm_page import _COINED, _rooted              # noqa: PLC0415

    name = str(kind or "").strip()
    if not name or name in known or _rooted(name, known):
        return name
    tidy = re.sub(r"[\s-]+", "_", name).lower()
    if _COINED.match(tidy):
        return tidy
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


# THẺ HTML NÓI NÓ LÀ GÌ -- và câu trả lời sống ở `pipeline/tags.py`, một bảng
# cho cả hai trục.
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
#
# Bảng này TỪNG là một bản chép riêng ở đây, và bản chép kia -- trong chuỗi JS
# của `generators/html/page.py` -- phủ một tập thẻ khác. Chỗ hở giữa hai bản
# là một lỗi im lặng theo cả hai chiều; xem số đo trong `pipeline/tags.py`.
BY_TAG = _kind_by_tag()

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
