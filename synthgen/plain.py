"""Lấy HTML TRẦN của một trang: đúng cấu trúc, không một dòng CSS nào.

`markup.py` vẽ ra một tờ giấy: có `<style>` sáu trăm dòng, có `class` trên
từng thẻ, có `<span data-kind>` bọc từng đoạn chữ để đo hộp. Cái ấy cần cho
trình duyệt và cần cho phép đo, nhưng một trình đọc cấu trúc bảng thì phải
lội qua nó.

File này bỏ hết phần trang trí và giữ lại đúng phần CÓ NGHĨA: thẻ nào, lồng
trong thẻ nào, và ô nào gộp mấy cột mấy dòng. `colspan` và `rowspan` là hai
thuộc tính duy nhất được giữ, vì chúng không phải trang trí -- chúng LÀ cấu
trúc, và là thứ một bảng tiêu đề ba tầng khác một bảng phẳng.

Vì sao không dùng `record['html']`: bộ chuyển của `pipeline/record.py` gom
khối theo DÒNG NHÌN THẤY rồi mới gắn thẻ, nên một bảng ba mươi dòng ra ba
mươi thẻ `<table>` mỗi thẻ một dòng chữ, không ô nào, không `colspan` nào.
Đúng cho một trang chữ chạy; mất sạch cho một cái bảng. Ở đây đọc thẳng
markup đã vẽ, nên cấu trúc còn nguyên như trình duyệt đã thấy.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Thẻ không có phần đóng.
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}

# Bỏ HẲN, kể cả chữ bên trong: trang trí thuần tuý hoặc không phải nội dung.
DROP = {"style", "script", "head", "link", "meta", "title", "svg", "img",
        # `<colgroup>` chỉ nói mỗi cột rộng bao nhiêu phần trăm -- đó là kiểu
        # dáng, không phải cấu trúc, và số cột thì đã nằm trong chính các ô.
        "colgroup", "col"}

# `<span data-kind>` đổi thành `<div>`, KHÔNG phải bỏ hẳn. Trong markup các
# span đứng sát nhau không có một khoảng trắng nào -- chúng cách nhau bằng
# CSS (`display:block`), mà CSS thì vừa bị bỏ. Bỏ luôn thẻ thì "TẬP ĐOÀN ĐẦU
# TƯ VÀ PHÁT TRIỂN" và "CÔNG TY TNHH …" dính thành một chuỗi không ai tách
# lại được. Một span là một dòng chữ đo được, nên `<div>` là đúng nghĩa nó.
UNWRAP = {"font", "b", "i"}
ASDIV = {"span"}

# Thuộc tính được giữ. Hai cái, và cả hai đều là cấu trúc chứ không phải kiểu.
KEEP = {"colspan", "rowspan"}

BLOCK = {"div", "p", "h1", "h2", "h3", "h4", "table", "thead", "tbody", "tfoot",
         "tr", "th", "td", "ul", "ol", "li", "section", "header", "footer"}

# Thẻ rỗng được phép bỏ. KHÔNG có `td`/`th` trong này: một ô trống là một ô
# THẬT, và bỏ nó đi thì dòng ấy hụt một cột so với dòng trên -- cấu trúc bảng
# hỏng ngay ở chỗ nó đang cố mô tả.
PRUNABLE = {"div", "p", "section", "header", "footer", "h1", "h2", "h3", "h4"}


class _Sheet(HTMLParser):
    """Bắt lấy tờ thứ `want` trong markup, đã lọc sạch.

    `boxes` là hộp của từng đoạn chữ, theo đúng thứ tự `entity_annotations`.
    Mỗi `<span data-kind>` in ra một đoạn và `pipeline/record.py` dựng đúng
    một thực thể cho nó -- đo trên 60 tài liệu: 60/60 khớp một-một, cùng thứ
    tự. Nên số đếm span chạy suốt CẢ markup (không riêng tờ đang bắt), và
    hộp thứ `n` rơi đúng vào span thứ `n`."""

    def __init__(self, want: int, boxes: list | None = None):
        super().__init__(convert_charrefs=True)
        self.want = want
        self.boxes = boxes or []
        self.span = 0           # số span đã đi qua, tính trên CẢ markup
        self.seen = 0
        self.depth = 0          # độ sâu bên trong tờ đang bắt
        self.on = False
        self.drop = 0           # đang ở trong một thẻ bị bỏ hẳn
        self.out: list[str] = []
        self.stack: list[str] = []
        self.cells: list[dict] = []   # ô bảng đang mở, để gộp hộp con lại

    # -------------------------------------------------------------- thẻ mở

    def _take(self) -> tuple | None:
        """Hộp của span kế tiếp, và đẩy số đếm lên."""
        box = self.boxes[self.span] if self.span < len(self.boxes) else None
        self.span += 1
        if not box or len(box) != 4:
            return None
        return tuple(int(round(float(v))) for v in box)

    def handle_starttag(self, tag, attrs):
        table = dict(attrs)
        classes = (table.get("class") or "").split()

        # Span nào cũng phải đếm, kể cả span của tờ không bắt -- bỏ đếm một
        # cái là mọi hộp phía sau lệch đi một chỗ, và không gì báo.
        if tag == "span" and "data-kind" in table and not self.on:
            self.span += 1

        if not self.on:
            if tag == "div" and "sheet" in classes:
                self.seen += 1
                if self.seen == self.want:
                    self.on = True
                    self.depth = 1
                    self.stack = ["div"]
                    self.out.append("<div>")
            return

        if tag in VOID and tag not in DROP:
            self.out.append(f"<{tag}>")
            return
        if tag in DROP:
            # `<col>`, `<img>`, `<link>` vừa bị bỏ vừa KHÔNG có thẻ đóng. Đếm
            # chúng vào `self.drop` là đếm một cái không bao giờ được trừ đi,
            # và mọi thứ phía sau trong tờ giấy bị nuốt sạch -- đúng lỗi đã đo
            # được: một trang bảng sáu mươi dòng ra đúng ba dòng HTML.
            if tag not in VOID:
                self.drop += 1
            return
        if self.drop:
            return
        if tag in UNWRAP:
            self.stack.append("")          # giữ chỗ, không in thẻ
            return
        if tag in ASDIV:
            # Chỉ span CÓ `data-kind` mới mang chữ và mới có một hộp. Span
            # trang trí -- vạch mã vạch, ô logo -- không có `data-kind` và
            # `pipeline/record.py` không dựng thực thể cho nó. Cho nó lấy một
            # hộp là đẩy lệch mọi hộp phía sau đúng một chỗ, và tấm ảnh vẫn
            # trông đúng nên không gì báo. Đo được: 6 hộp lệch trong 12 trang.
            if "data-kind" not in table:
                self.stack.append("")
                return
            box = self._take()
            self.stack.append("div")
            self.out.append(f'<div bbox="{_bbox(box)}">' if box else "<div>")
            if box:
                for cell in self.cells:
                    cell["box"] = _union(cell["box"], box)
            return

        self.depth += 1 if tag == "div" else 0
        kept = "".join(f' {k}="{table[k]}"' for k in ("colspan", "rowspan")
                       if k in table and table[k] not in ("1", ""))
        self.stack.append(tag)
        # Ô bảng chưa biết hộp của mình cho tới lúc đóng: hộp của nó là hợp
        # của mọi đoạn chữ bên trong. Nên chừa chỗ, đóng ô rồi viết đè.
        if tag in ("td", "th"):
            self.cells.append({"at": len(self.out), "tag": tag,
                               "kept": kept, "box": None})
        self.out.append(f"<{tag}{kept}>")

    # ------------------------------------------------------------- thẻ đóng

    def handle_endtag(self, tag):
        if not self.on:
            return
        if tag in DROP:
            self.drop = max(0, self.drop - 1)
            return
        if self.drop or tag in VOID:
            return
        if tag == "div":
            self.depth -= 1
            if self.depth <= 0:
                self.out.append("</div>")
                self.on = False
                return
        if tag in UNWRAP:
            if self.stack and self.stack[-1] == "":
                self.stack.pop()
            return
        if tag in ASDIV:
            if self.stack and self.stack[-1] == "":
                self.stack.pop()          # span trang trí: không có thẻ nào
                return
            if self.stack and self.stack[-1] == "div":
                self.stack.pop()
            self.out.append("</div>")
            return
        if tag in ("td", "th") and self.cells:
            cell = self.cells.pop()
            if cell["box"]:
                self.out[cell["at"]] = (f'<{cell["tag"]}{cell["kept"]} '
                                        f'bbox="{_bbox(cell["box"])}">')
            if self.cells:
                self.cells[-1]["box"] = _union(self.cells[-1]["box"], cell["box"])
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        self.out.append(f"</{tag}>")

    # ----------------------------------------------------------------- chữ

    def handle_data(self, data):
        if not self.on or self.drop:
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.out.append(_escape(text))


def _bbox(box) -> str:
    return ",".join(str(v) for v in box)


def _union(a, b):
    if not a:
        return b
    if not b:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _prune(html: str) -> str:
    """Bỏ các thẻ khối rỗng còn sót -- hoạ tiết vẽ bằng CSS để lại vỏ không."""
    pattern = re.compile(
        r"<(" + "|".join(sorted(PRUNABLE)) + r")(?: [^>]*)?>\s*</\1>")
    while True:
        stripped = pattern.sub("", html)
        if stripped == html:
            return html
        html = stripped


def _indent(html: str) -> str:
    """Xuống dòng theo thẻ khối. Thuần để người đọc được, không đổi nghĩa."""
    html = re.sub(r"(<(?:" + "|".join(sorted(BLOCK)) + r")(?: [^>]*)?>)",
                  r"\n\1", html)
    html = re.sub(r"(</(?:" + "|".join(sorted(BLOCK)) + r")>)", r"\1\n", html)
    lines = [line.strip() for line in html.splitlines()]
    return "\n".join(line for line in lines if line)


# Một ô bảng chỉ chứa đúng một dòng chữ thì bỏ luôn cái `<div>` bọc: `<td>`
# đã là một ô rồi, thêm một tầng nữa chỉ tổ dài ra mà không nói thêm gì.
_BARE_CELL = re.compile(
    r"<(td|th)((?: [^>]*)?)>\s*<div(?: bbox=\"[^\"]*\")?>([^<]*)</div>\s*</\1>")


def _flatten(lines: list[str]) -> list[str]:
    """Gộp các `<div>` chỉ bọc đúng một `<div>` khác.

    Khối trong `markup.py` lồng bốn năm tầng vì CSS cần chỗ bám. Bỏ CSS rồi
    thì mấy tầng ấy không nói gì nữa -- một `<div>` bọc đúng một `<div>` là
    một tầng rỗng, và một trình đọc phải đi qua nó để tới chỗ có chữ."""
    out: list[str] = []
    for line in lines:
        # `<div>` mở mà dòng trước cũng là `<div>` mở thì gộp -- nhưng chỉ khi
        # cái trước không có anh em nào khác, tức là cái đóng của chúng cũng
        # dính nhau. Kiểm bằng cách dựng lại: đẩy vào, rồi khi gặp `</div>`
        # liền kề thì rút cả hai.
        out.append(line)
    depth: list[int] = []
    kids: list[int] = []
    keep = [True] * len(out)
    for index, line in enumerate(out):
        if line == "<div>":
            if kids:
                kids[-1] += 1
            depth.append(index)
            kids.append(0)
        elif line == "</div>":
            if not depth:
                continue
            start = depth.pop()
            count = kids.pop()
            # Một tầng rỗng: đúng một con, và con ấy là một khối (không phải
            # chữ trần). Chữ trần thì `count` bằng 0 nên không đụng tới.
            if count == 1 and out[start + 1] == "<div>" and out[index - 1] == "</div>":
                keep[start] = keep[index] = False
        else:
            if kids and not line.startswith("</"):
                kids[-1] += 1
    return [line for line, ok in zip(out, keep) if ok]


def sheet_html(markup: str, page: int = 1, boxes: list | None = None) -> str:
    """HTML trần của tờ thứ `page` trong `markup`. Chuỗi rỗng nếu không có.

    `boxes` là hộp từng đoạn chữ theo thứ tự `entity_annotations`; đưa vào
    thì mỗi thẻ mang chữ có thêm `bbox="x1,y1,x2,y2"`, và mỗi ô bảng mang
    hợp của các hộp bên trong nó. Toạ độ tính bằng PIXEL trên chính tấm ảnh
    của trang ấy, cùng hệ với `word_boxes/` và `layout_boxes/`."""
    parser = _Sheet(page, boxes)
    parser.feed(markup)
    parser.close()
    if not parser.out:
        return ""
    html = _prune("".join(parser.out))
    html = _BARE_CELL.sub(r"<\1\2>\3</\1>", html)
    lines = _indent(html).splitlines()
    for _ in range(6):
        shorter = _flatten(lines)
        if len(shorter) == len(lines):
            break
        lines = shorter
    return "\n".join(lines) + "\n"


__all__ = ["sheet_html"]
