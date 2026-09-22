"""Một thẻ HTML nghĩa là gì -- MỘT bảng, hai trục, ba nơi đọc.

    from pipeline.tags import kind_by_tag, region_by_tag, region_by_tag_js

## Vì sao có file này

Cùng một câu hỏi -- "`<li>` là cái gì?" -- trước đây được trả lời ở hai chỗ
không biết nhau:

* `generators/html/page.py::ZONE_REGIONS_JS` giữ một `BY_TAG` trong chuỗi JS,
  ánh xạ thẻ sang **nhãn vùng bố cục**;
* `synthgen/repair.py::BY_TAG` giữ một bảng Python, ánh xạ thẻ sang
  **`data-kind`** để bọc chữ trần.

Hai bảng phủ hai tập thẻ khác nhau, và chỗ hở giữa chúng là một lỗi im lặng
theo cả hai chiều. Đo trên 193 trang HTML model viết trong `data/pilot1[2-6]`:

    <th>      1271   chỉ bảng kind biết
    <p>       1077   chỉ bảng kind biết   -> chữ có hộp, khối KHÔNG có vùng
    <li>       405   chỉ bảng kind biết
    <header>   105   chỉ bảng vùng biết   -> vùng có, chữ trần KHÔNG có hộp
    <ul>        45   chỉ bảng vùng biết
    <section>    2   không bảng nào biết

`<p>` một nghìn lượt là nguồn chính của việc 27,4% số hộp vùng phải dựng bằng
bộ gom-từ theo ngưỡng thay vì đo thẳng phần tử -- không phải vì hình học khó,
mà vì một bảng biết `<p>` còn bảng kia thì không.

## Hai trục, và vì sao không suy trục này ra trục kia

`<footer>` nói **chỗ đứng**; `footer` (kind) nói **nội dung là gì**. Thử suy
nhãn vùng từ kind thì 9 trên 15 thẻ đổ về `Text`:

    li     -> clause.body        -> Text   (đúng phải là List-Group)
    footer -> footer             -> Text   (đúng phải là Page-Footer)
    dt/dd  -> invoice.field*     -> Text

Nên hai trục đứng cạnh nhau trong một hàng, không trục nào phái sinh từ trục
kia. `""` nghĩa là **trục này để chỗ khác lo**, nói rõ ra thay vì vắng mặt:
`<li>` không tự khai vùng vì `<ul>` cha đã khai, `<th>` không tự khai vì
`CELL_REGIONS_JS` đã đo cả bảng theo từng ô.

## Ai đọc bảng này

1. `generators/html/page.py::ZONE_REGIONS_JS` -- qua `region_by_tag_js()`;
2. `synthgen/repair.py::BY_TAG` -- qua `kind_by_tag()`;
3. `agent/compose_page.py` -- lời dặn model, qua `region_by_tag()`.

Thêm một thẻ là sửa một chỗ. `tests/test_tags.py` giữ lời hứa ấy.
"""

from __future__ import annotations

import json
import re

# thẻ -> (`data-kind` để bọc chữ trần, nhãn vùng bố cục)
#
# Nhãn vùng phải nằm trong `record.DOCSYNTH_LABELS`; kind phải là kind engine
# thật sự in ra (`synthgen/llm_page.py::kinds`). Cả hai được kiểm ở
# `tests/test_tags.py` chứ không ở đây -- import ngược lên `pipeline.record`
# từ file này sẽ kéo cả bộ nhãn vào `generators/html/page.py`, thứ cố ý chỉ
# dùng thư viện chuẩn.
TAG_SEMANTICS: dict[str, tuple[str, str]] = {
    # Tiêu đề. `<h1>` là tiêu đề CỦA TỜ GIẤY, `<h2>`..`<h6>` là tiêu đề mục --
    # khác nhau ở nhãn vùng, giống nhau ở chỗ cả hai đều là chữ có nghĩa.
    "h1": ("title", "Title"),
    "h2": ("section", "Section-Header"),
    "h3": ("section", "Section-Header"),
    "h4": ("section", "Section-Header"),
    "h5": ("section", "Section-Header"),
    "h6": ("section", "Section-Header"),

    # Danh sách. Vùng là CẢ cái danh sách, không phải từng mục: `List-Group`
    # trong từ vựng bố cục nghĩa là nhóm các mục. Nên `<li>` mang kind mà
    # không khai vùng -- xem `synthgen/markup.py::_clauses` đã ghi đúng lẽ ấy.
    "ul": ("", "List-Group"),
    "ol": ("", "List-Group"),
    "dl": ("", "List-Group"),
    "li": ("clause.body", ""),
    "dt": ("invoice.field.label", ""),
    "dd": ("invoice.field", ""),

    # Chữ chạy. `Text` cho `<p>` là chỗ hở lớn nhất của bản trước: một nghìn
    # lượt `<p>` trên 193 trang, không lượt nào cho một vùng đo được.
    "p": ("note", "Text"),
    "blockquote": ("note", "Text"),
    "pre": ("", "Code-Block"),

    # Khối bọc có tên. Chúng thường KHÔNG có chữ của riêng mình, và luật
    # bỏ-cái-khung ở `record.py::_unwrap` sẽ bỏ chúng đúng lúc ấy -- nên khai
    # vùng ở đây là an toàn, không phải là hứa rằng vùng ấy sẽ tồn tại.
    "header": ("", "Page-Header"),
    "footer": ("footer", "Page-Footer"),
    "form": ("", "Form"),
    "fieldset": ("", "Form"),
    # Hai thẻ model tự dùng mà trước đây KHÔNG bảng nào biết. Ít gặp (2 lượt
    # trên 193 trang) nên con số tác động chưa đo được; để `Text` vì đó là
    # nhãn rộng nhất không nói dối về nội dung.
    "section": ("", "Text"),
    "article": ("", "Text"),

    # Hình và chú thích. `Figure` được phép ôm `Caption` -- xem `GROUPING`.
    "figure": ("", "Figure"),
    "figcaption": ("caption.figure", "Caption"),
    # `<caption>` là tiêu đề của một `<table>`. Không khai vùng: hộp của nó
    # nằm gọn trong hộp bảng mà `CELL_REGIONS_JS` đã đo, và một vùng nữa ở
    # đây là đếm hai lần.
    "caption": ("caption.table", ""),

    # Bảng. KHÔNG khai vùng cho `<table>`/`<th>`/`<td>`: `CELL_REGIONS_JS` đo
    # bảng theo từng ô thật và gộp mỗi `<table>` thành đúng một vùng.
    "th": ("colhdr", ""),
}


# Nhãn vùng KHÔNG đến từ `data-region` mà từ một phép đo khác, và cách viết
# để phép đo ấy nhìn thấy nó.
#
# Ba nhãn này là chỗ một bảng "thẻ -> nhãn" nói dối nếu để trống: bảo model
# viết `<div data-region="Table">` là bảo nó dựng một vùng thứ hai chồng lên
# vùng `CELL_REGIONS_JS` đã đo từ chính các ô -- đếm hai lần, đúng thứ mục 21
# của `agent/prompts/page.md` cấm. Nên bảng nhãn đưa cho model phải nói cách
# viết THẬT, không phải cách viết mặc định.
MEASURED_ELSEWHERE: dict[str, str] = {
    "Table": '`<table>` with `data-cell` on every `<td>` and `<th>`',
    "Image": "`<img>` or `<svg>`",
    "Stamp": '`<img data-graphic="seal">`',
}


# --------------------------------------------------------- đi trên cây thẻ
#
# Hai chỗ cần hỏi cùng một câu -- "tổ tiên của phần tử này khai vùng gì" --
# và chúng ở hai gói khác nhau: `synthgen/repair.py::zoned` gắn `data-region`
# cho thẻ chưa khai, `synthgen/llm_page.py::orphan_runs` đếm run không nằm
# trong vùng nào. Viết hai bộ quét là dựng lại đúng cái bệnh file này sinh ra
# để chữa -- bảng thẻ từng có hai bản, phủ hai tập thẻ khác nhau, và chỗ hở
# giữa chúng im lặng theo cả hai chiều.
#
# Ở đây chứ không ở `repair.py`: `llm_page.py` cố ý chỉ dùng thư viện chuẩn
# (nó là CỔNG, phải chạy được ở chỗ không có bộ sinh), và bắt nó import bộ
# sửa để mượn một regex là buộc hai thứ không liên quan vào nhau.

# Mọi thẻ mở/đóng, kèm cụm thuộc tính. KHÔNG dùng `html.parser`: bộ phân tích
# chuẩn đẩy thẻ rỗng (`<br>`) vào ngăn xếp mà không ai lấy ra, và từ đó mọi
# phép hỏi tổ tiên lệch một tầng mà không gì báo -- cùng lý do
# `llm_page.outside_sheet` đã ghi khi nó tự đếm độ sâu `<div>`.
OPEN_CLOSE = re.compile(
    r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>")

VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr"})

_REGION_ATTR = re.compile(
    r"""\bdata-region\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_KIND_ATTR = re.compile(r"\bdata-kind\s*=", re.IGNORECASE)


def declared_region(attrs: str) -> str:
    """Nhãn vùng cụm thuộc tính này TỰ khai, hoặc rỗng.

    Nhận cả ba kiểu viết của HTML5 -- `k="v"`, `k='v'`, `k=v` -- vì model
    dùng cả ba, và một regex kén dấu nháy là một trang trượt vì lỗi không
    phải của nó. Cùng bài học `repair._SPAN` đã ghi."""
    got = _REGION_ATTR.search(attrs)
    if not got:
        return ""
    return (got.group(2) or got.group(3) or got.group(4) or "").strip()


def has_kind(attrs: str) -> bool:
    """Cụm thuộc tính này có `data-kind` không."""
    return bool(_KIND_ATTR.search(attrs))


def kind_by_tag() -> dict[str, str]:
    """Thẻ -> `data-kind`, chỉ những thẻ có trục ấy."""
    return {tag: kind for tag, (kind, _) in TAG_SEMANTICS.items() if kind}


def region_by_tag() -> dict[str, str]:
    """Thẻ -> nhãn vùng bố cục, chỉ những thẻ có trục ấy."""
    return {tag: label for tag, (_, label) in TAG_SEMANTICS.items() if label}


def region_by_tag_js() -> str:
    """`region_by_tag()` dưới dạng một object literal nhúng được vào JS.

    `json.dumps` chứ không nối chuỗi tay: một nhãn có dấu nháy trong tên sẽ
    phá cú pháp JS ở đúng chỗ không ai nhìn, và khi ấy `ZONE_REGIONS_JS` ném
    ngay lúc `page.evaluate` chứ không âm thầm trả về mảng rỗng."""
    return json.dumps(region_by_tag(), ensure_ascii=False, sort_keys=True)


def measured_elsewhere_js() -> str:
    """`MEASURED_ELSEWHERE`'s keys, thành một mảng JS -- nhãn nào KHÔNG được
    tới từ `data-region` khai tay, vì đã có một phép đo RIÊNG đo đúng nó
    (`CELL_REGIONS_JS` cho Table, `GRAPHIC_RECTS_JS` cho Image/Stamp).

    Trước bản sửa này, `MEASURED_ELSEWHERE` chỉ đi vào lời dặn cho model đọc
    (`agent/compose_page.py`) và vào `tests/test_tags.py` -- không nơi nào
    trong chính phép đo THỰC THI lời dặn ấy. Đo trên `data/pilot16/records/
    export_invoice/llm_export_invoice_0003.json`: model viết `<table
    data-region="Table">` (đúng cách viết bị cấm) và `ZONE_REGIONS_JS` vẫn
    đo nó -- ra BỐN vùng `Table` (hai mỗi trang) thay vì hai, vì nhánh
    `[data-region]` của chính JS ấy không hề tra bảng này. `region_by_tag_js()`
    ở trên đã tránh đúng lỗi này cho nhánh SUY TỪ THẺ (`<table>` không có
    trong `BY_TAG`) -- hàm này đưa cùng một sự thật sang nhánh KHAI TAY, dùng
    lại đúng một bảng cho cả ba nơi đọc, không thêm một danh sách thứ tư."""
    return json.dumps(sorted(MEASURED_ELSEWHERE), ensure_ascii=False)


__all__ = ["MEASURED_ELSEWHERE", "TAG_SEMANTICS", "kind_by_tag",
           "measured_elsewhere_js", "region_by_tag", "region_by_tag_js"]
