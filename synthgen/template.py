"""Phôi `{{đường.dẫn}}` -- cú pháp, cổng gác, và phép bung ra trang thật.

    from synthgen.template import Template, problems, fill_html

Đây là phần CHUNG của hai pha trong đường sinh "model viết phôi":

    pha 1  `agent/compose_template.py`  model viết HTML mang chỗ trống
    pha 2  `synthgen/fill.py`           mã điền giá trị thật, KHÔNG gọi model

## Vì sao chỗ trống nằm trong CHỮ, không nằm trong thuộc tính

Một run có nhãn trong kho này đã mang sẵn hai thứ:

    <span data-kind="store.tax_code" data-path="issuer.tax_code">0312...</span>

`data-path` là lời khai danh tính, chữ bên trong là thứ in ra giấy. Phôi chỉ
đổi **chữ** thành `{{issuer.tax_code}}` và giữ nguyên `data-path`. Ba cái được
cùng lúc:

1. `data-path` vẫn đúng dạng `synthgen/llm_page.py::_PATH`, nên cổng chữ chạy
   được trên CẢ phôi lẫn trang đã điền, không cần một cổng thứ hai.
2. Luật "cùng đường dẫn thì cùng giá trị" (`llm_page.problems`) trở thành
   ĐÚNG THEO CẤU TẠO: hai chỗ cùng `{{issuer.name}}` đọc cùng một ô của tờ
   khai sự thật, nên không thể in ra hai chữ khác nhau. Đo trên `data/pilot16`:
   15 tờ trượt cổng đúng vì luật ấy, tất cả đều là một sự thật in hai kiểu chữ.
   Đường phôi không thể sinh ra ca ấy.
3. Không có bước "bơm dữ liệu vào khuôn" nào phải đoán chỗ: chỗ đã có tên.

## Vì sao đường dẫn phải nằm trong sổ ĐÓNG, gác cứng

Cổng của `agent/compose_page.py` (một trang một lời gọi) cố ý KHÔNG ép
`data-path` phải thuộc sổ: một tên lạ ở đó làm hỏng đúng một tờ, và
`synthgen/field_tier.py` hạ nó xuống `staging` mà không mất tờ nào.

Ở đây cái giá khác hẳn. Một phôi được điền hàng trăm tới hàng nghìn lần, nên
một đường dẫn viết sai TRONG PHÔI là cùng một lỗi nhân lên chừng ấy lần --
và nó không sửa được sau khi ảnh đã vẽ. Nên sổ đóng
(`synthgen/field_tier.py::closed_enum("path")`, 60 khoá, 6 họ) là HÀNG RÀO ở
pha 1, không phải gợi ý. Cùng con số ấy đi vào `enum` của `response_format`,
nên bộ giải mã có ràng buộc không sinh nổi một tên ngoài sổ ngay từ đầu; cổng
này là lớp thứ hai, cho backend không ép được schema.

## Dòng lặp: một `<tr>` mẫu, `data-repeat`

Bảng hàng không thể viết sẵn N dòng trong phôi -- số dòng phải đổi giữa các
lần điền, nếu không mọi tờ ra từ một phôi đều cao bằng nhau và dấu vân hình
học của chúng trùng khít. Nên phôi viết ĐÚNG MỘT dòng mẫu:

    <tr data-repeat="line_items">
      <td data-cell><span data-kind="menu.name"
                          data-path="line_items[].name">{{line_items[].name}}</span></td>
      ...
    </tr>

`fill_html()` nhân nó ra N dòng và thay `[]` bằng `[0]`, `[1]`, ... ở CẢ thuộc
tính lẫn chữ. `[]` rỗng là cách viết mà `field_tier.normalise()` đã gom về
(`line_items[3].name` -> `line_items[].name`), nên phôi nói đúng thứ tiếng mà
sổ đăng ký nói.

## Cái này KHÔNG kiểm

Phôi có đẹp không, có giống giấy tờ Việt Nam không, nhãn in trên giấy có hợp
với `data-path` gắn cho nó không (`{{issuer.tax_code}}` nằm sau chữ "Số điện
thoại:" là một phôi hợp lệ và sai). Cổng máy bắt cái đo được; ảnh vẽ ra và
người đọc diff bắt phần còn lại -- cùng giới hạn `synthgen/llm_page.py` đã
viết ra cho trang model viết thẳng.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# `{{ ... }}` -- KHÔNG nuốt khoảng trắng, không cho lồng nhau.
#
# Bắt cả dạng viết sai (`{{ issuer.name }}`, `{{Issuer.Name}}`) rồi mới chê ở
# `problems()`: một mẫu chỉ bắt dạng ĐÚNG thì phôi viết sai trông như phôi
# không có chỗ trống nào, và cổng im lặng cho qua một tờ giấy in nguyên chữ
# `{{ issuer.name }}` lên mặt giấy.
SLOT = re.compile(r"\{\{([^{}]*)\}\}")

# Đường dẫn HỢP LỆ trong một chỗ trống: `họ.trường` hoặc `họ[].trường`, chữ
# thường, snake_case. Hẹp hơn `llm_page._PATH` đúng một chỗ -- ở đây chỉ số
# phải RỖNG (`[]`), vì phôi nói về "một dòng bất kỳ", còn `[3]` là một dòng cụ
# thể và chỉ có nghĩa sau khi đã bung.
SLOT_PATH = re.compile(r"^[a-z][a-z0-9_]*(\[\])?(\.[a-z][a-z0-9_]*)+$")

REPEAT_ATTR = "data-repeat"

# Thẻ mở/đóng bất kỳ, để đếm độ sâu khi tìm thẻ đóng của khối lặp. Cùng lối
# `llm_page.outside_sheet` đã chọn: đếm thẻ chứ không dựng cây, vì một bộ phân
# tích trượt lặng lẽ ở thẻ rỗng còn một phép đếm thì đọc được và sửa được.
_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>", re.DOTALL)

# Thẻ rỗng HTML5: không bao giờ có thẻ đóng, nên không được cộng vào độ sâu.
# Thiếu danh sách này thì một `<br>` trong dòng mẫu làm phép đếm không bao giờ
# về 0 và khối lặp nuốt nốt phần còn lại của bảng.
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                  "link", "meta", "param", "source", "track", "wbr"})


def slots(html: str) -> list[str]:
    """Mọi chỗ trống trang này viết, THEO THỨ TỰ, kể cả viết sai và trùng lặp.

    Trả nguyên văn phần trong ngoặc -- `problems()` là chỗ chê, không phải
    đây. Một hàm ĐỌC im lặng bỏ qua thứ nó không hiểu là cách một lỗi đi
    thẳng vào bộ dữ liệu."""
    return [m.group(1) for m in SLOT.finditer(str(html or ""))]


def paths(html: str) -> list[str]:
    """Chỗ trống ĐÚNG DẠNG, đã bỏ trùng, đã sắp."""
    return sorted({s for s in slots(html) if SLOT_PATH.match(s)})


def families(html: str) -> set[str]:
    """Họ của mọi chỗ trống đúng dạng -- `issuer.`, `line_items[].`, ..."""
    return {p.split(".", 1)[0].replace("[]", "") + "." for p in paths(html)}


def repeat_blocks(html: str) -> list[tuple[str, int, int]]:
    """`(tên nhóm, vị trí mở, vị trí sau thẻ đóng)` cho mỗi khối `data-repeat`.

    Khối lồng nhau KHÔNG được hỗ trợ và `problems()` từ chối chúng: một dòng
    lặp trong một dòng lặp là N×M dòng mà không ai khai N với M ở đâu, và
    `fill_html()` bung lớp ngoài trước thì lớp trong đi theo nguyên văn `[]`
    -- một chỗ trống chưa bung lọt ra giấy."""
    body = str(html or "")
    out: list[tuple[str, int, int]] = []
    for opener in re.finditer(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?\b"
                              + REPEAT_ATTR + r"\s*=\s*[\"']?([^\"'\s>]+)",
                              body, re.IGNORECASE):
        tag = opener.group(1).lower()
        name = opener.group(2)
        end = _close_at(body, tag, opener.start())
        if end is None:                      # thẻ không đóng -- `problems` chê
            continue
        out.append((name, opener.start(), end))
    return out


def _close_at(body: str, tag: str, start: int) -> int | None:
    """Vị trí NGAY SAU thẻ đóng khớp với thẻ mở ở `start`. `None` khi thiếu."""
    depth = 0
    for m in _TAG.finditer(body, start):
        if m.group(2).lower() != tag:
            continue
        if m.group(1):                       # </tag>
            depth -= 1
            if depth == 0:
                return m.end()
        elif not m.group(3) and tag not in VOID:
            depth += 1
        # `<tag/>` tự đóng ngay tại chỗ mở: chỉ đáng kể khi nó LÀ thẻ mở.
        elif m.start() == start:
            return m.end()
    return None


@dataclass(frozen=True)
class Template:
    """Một phôi đã qua cổng. KHÔNG mang hộp nào.

    Không có trường `bbox`, `layout_annotations` hay bất cứ toạ độ nào ở đây,
    và đó là một quyết định chứ không phải thiếu sót: giá trị thật dài ngắn
    khác chỗ trống, nên mọi hộp đo trên phôi đều SAI cho trang đã điền. Cách
    chắc chắn nhất để không ai lỡ tay dùng lại chúng là không bao giờ đo
    chúng. Hộp sinh đúng một lần, ở `synthgen/draw_llm.py`, trên trang ĐÃ
    ĐIỀN (AGENTS.md luật 1 và 2)."""

    template_id: str
    family: str                  # family của `agent/grammar.py` đã rút
    html: str
    doc_kind: str = ""
    doc_title: str = ""
    kinds: dict[str, str] = field(default_factory=dict)   # path -> data-kind
    meta: dict = field(default_factory=dict)

    @property
    def scalar_paths(self) -> list[str]:
        return [p for p in paths(self.html) if "[]" not in p]

    @property
    def repeat_names(self) -> list[str]:
        return sorted({name for name, _s, _e in repeat_blocks(self.html)})

    def as_dict(self) -> dict:
        return {"template_id": self.template_id, "family": self.family,
                "doc_kind": self.doc_kind, "doc_title": self.doc_title,
                "kinds": dict(self.kinds), "meta": dict(self.meta),
                "html": self.html}

    @classmethod
    def from_dict(cls, raw: dict) -> "Template":
        return cls(template_id=str(raw.get("template_id") or ""),
                   family=str(raw.get("family") or ""),
                   html=str(raw.get("html") or ""),
                   doc_kind=str(raw.get("doc_kind") or ""),
                   doc_title=str(raw.get("doc_title") or ""),
                   kinds=dict(raw.get("kinds") or {}),
                   meta=dict(raw.get("meta") or {}))


# ------------------------------------------------------- chữa trước khi gác

def enclose(html: str, kinds: dict) -> tuple[str, int]:
    """Bọc mọi chỗ trống TRẦN vào một run có nhãn. `(html, số chỗ đã bọc)`.

    ## Vì sao việc này chữa được, và vì sao nó KHÔNG phải đoán

    Một chỗ trống phải ngồi trong `<span data-kind data-path>` để có hộp --
    `generators/html/page.py::CELL_RECTS_JS` chọn `.sheet span[data-kind]` và
    không thẻ nào khác. Model thì viết nó trần khá thường xuyên.

    Thứ làm phép chữa này thành phép ĐỌC chứ không phải phép đoán là `slots`:
    model đã tự khai `path -> kind` cho từng chỗ trống nó dùng, và cổng
    (`agent/compose_template.py::slot_problems`) đã đối chiếu lời khai ấy với
    HTML. Nên `kinds[path]` là chính cái nhãn model chọn, không phải một cái
    nhãn ta suy ra hộ nó. Không có khai thì KHÔNG bọc -- để cổng loại, đúng
    luật "hỏng thì đóng, không ánh xạ về khoá gần nhất" của
    `synthgen/field_tier.py`.

    ## Ba hình đã đo được, và cả ba đều là hình này

    Đo trên `data/24-09-phoi-v1` (60 phôi, Qwen3.8-27B-FP8), 12 phôi trượt
    đầu lượt:

        <div class="org-name">{{issuer.name}}</div>        thẻ không nhãn
        <h1 data-region="Title">{{document.title}}</h1>    thẻ ngữ nghĩa
        ...</span>/TB-{{issuer.code}}                      dính sau một run

    Hình thứ ba đáng nói riêng: model dựng một chuỗi ghép (`Số: X/TB-Y`) từ
    hai đường dẫn, và chỗ trống thứ hai rơi ra ngoài span của chỗ thứ nhất.
    Bọc nó thành run RIÊNG là đúng -- hai đường dẫn là hai trường, nên hai
    hộp, và một hộp chung cho cả `X/TB-Y` là một hộp không nhãn nào tả đúng.

    Chỉ bọc chỗ trống nằm NGOÀI mọi span có nhãn. Chỗ trống ngồi trong một
    span khai đường dẫn KHÁC là mâu thuẫn thật -- `problems()` vẫn loại nó, và
    bọc thêm một span vào trong là dựng đúng cái run-có-thẻ-lồng mà cổng cấm.
    """
    body = str(html or "")
    place = _Placement(body)
    wrapped = 0
    out: list[str] = []
    last = 0
    for m in SLOT.finditer(body):
        name = m.group(1)
        if not SLOT_PATH.match(name) or place.holding(m.start()) is not None:
            continue
        kind = str((kinds or {}).get(name) or "")
        if not kind:
            continue                      # không có lời khai -- để cổng loại
        out.append(body[last:m.start()])
        out.append(f'<span data-kind="{kind}" data-path="{name}">'
                   f"{m.group(0)}</span>")
        last = m.end()
        wrapped += 1
    out.append(body[last:])
    return "".join(out), wrapped


def mark_repeats(html: str) -> tuple[str, int]:
    """Đánh `data-repeat` cho khối bao trọn một nhóm `x[]`. `(html, số khối)`.

    ## Ca này trông thế nào

    Model viết đúng cú pháp dòng lặp -- `{{signers[].title}}`,
    `{{signers[].name}}` -- rồi quên đánh dấu khối bao chúng:

        <div class="sig">
          <span data-path="signers[].title">{{signers[].title}}</span>
          <span data-path="signers[].name">{{signers[].name}}</span>
        </div>

    Không ai bung nó, nên `[]` đi thẳng ra giấy. Đo trên lượt thứ hai
    (`data/25-09-phoi-v2`, đã có `runify` + `enclose`): đây là hình trội,
    trong khi hình "chỗ trống trần" của lượt trước đã biến mất.

    ## Vì sao suy được, và giới hạn của phép suy

    Một nhóm `x[]` chỉ có nghĩa khi nó LẶP, nên khối bao trọn nó là khối phải
    nhân bản -- không có cách đọc thứ hai. Thứ phải cẩn thận là chọn ĐÚNG
    khối: lấy khối NHỎ NHẤT chứa trọn mọi chỗ trống của nhóm và KHÔNG chứa
    chỗ trống của nhóm khác. Lấy khối lớn hơn là nhân bản nửa tờ giấy.

    Điều kiện thứ hai ("không chứa nhóm khác") là chỗ phép suy tự dừng: một
    `<div>` ôm cả bảng hàng lẫn khối chữ ký thì không khối nào bung được mà
    không kéo khối kia theo, và lúc ấy KHÔNG đánh dấu gì -- để cổng loại, và
    để người đọc thấy phôi ấy thật sự có vấn đề cấu trúc chứ không phải chỉ
    thiếu một thuộc tính."""
    body = str(html or "")
    groups = {p.split("[]", 1)[0] for p in paths(body) if "[]" in p}
    already = {name for name, _s, _e in repeat_blocks(body)}
    marks: list[tuple[int, str]] = []
    for group in sorted(groups - already):
        spot = _smallest_holding(body, group, groups)
        if spot is not None:
            marks.append((spot, group))
    # Chèn TỪ CUỐI VỀ ĐẦU: mỗi lần chèn đẩy mọi vị trí phía sau lệch đi.
    for at, group in sorted(marks, reverse=True):
        end = body.index(">", at)
        body = f'{body[:end]} {REPEAT_ATTR}="{group}"{body[end:]}'
    return body, len(marks)


def _smallest_holding(body: str, group: str, groups) -> int | None:
    """Vị trí thẻ mở của khối nhỏ nhất ôm trọn `group[]` và không nhóm khác."""
    mine = [m.start() for m in SLOT.finditer(body)
            if m.group(1).startswith(f"{group}[].")]
    if len(mine) < 1:
        return None
    others = [m.start() for m in SLOT.finditer(body)
              if SLOT_PATH.match(m.group(1))
              and not m.group(1).startswith(f"{group}[].")
              and any(m.group(1).startswith(f"{g}[].") for g in groups)]
    best = None
    for m in _TAG.finditer(body):
        if m.group(1) or m.group(3):          # thẻ đóng / tự đóng
            continue
        tag = m.group(2).lower()
        # `<span>` KHÔNG BAO GIỜ là khối lặp. Một run có nhãn chỉ chứa chữ, nên
        # nhân bản nó ra N bản là N lần in CÙNG một trường, không phải N dòng.
        # Thiếu điều kiện này thì ca "một khối ôm hai nhóm" -- đáng lẽ phải từ
        # chối -- lại tìm ra `<span>` của chính chỗ trống làm khối nhỏ nhất
        # "không chứa nhóm khác", và đánh dấu nó.
        if tag in VOID or tag == "span":
            continue
        end = _close_at(body, tag, m.start())
        if end is None:
            continue
        if not all(m.start() < at < end for at in mine):
            continue
        if any(m.start() < at < end for at in others):
            continue
        if best is None or (end - m.start()) < (best[1] - best[0]):
            best = (m.start(), end)
    return best[0] if best else None


# ------------------------------------------------------------------ cổng gác

def problems(html: str, known_paths=None) -> list[str]:
    """Mọi lý do phôi này chưa dùng được. Rỗng là dùng được.

    `known_paths` là sổ đóng; `None` thì đọc
    `synthgen/field_tier.py::closed_enum("path")`. Truyền vào được để test
    chạy không cần dựng sổ (dựng sổ gọi `llm_page.kinds()`, thứ cần `cv2`).

    Cổng này KHÔNG thay `llm_page.problems()`: nó kiểm phần CHỖ TRỐNG, cổng
    kia kiểm phần HTML. `agent/compose_template.py` chạy cả hai -- cái thứ
    hai trên một bản đã điền thử, vì `llm_page.problems` đếm chữ in ra và
    một phôi chưa điền thì chưa in gì."""
    found: list[str] = []
    body = str(html or "")
    if not body.strip():
        return ["phôi rỗng"]

    if known_paths is None:
        from synthgen import field_tier as FT  # noqa: PLC0415
        known_paths = set(FT.closed_enum(FT.PATH))
    known = {str(p) for p in known_paths}

    raw = slots(body)
    if not raw:
        found.append("phôi không có chỗ trống `{{...}}` nào; một phôi không "
                     "có chỗ trống chỉ sinh lại đúng một tờ giấy")

    # 1. DẠNG. Một chỗ trống viết sai in nguyên ngoặc nhọn lên mặt giấy, và
    #    tờ ấy vẫn qua mọi cổng khác -- `{{ issuer.name }}` là chữ hợp lệ.
    for name in sorted(set(raw)):
        if not SLOT_PATH.match(name):
            found.append(
                f"chỗ trống `{{{{{name}}}}}` không đúng dạng: mong đợi "
                "`họ.trường` hoặc `họ[].trường`, chữ thường, snake_case, "
                "không khoảng trắng")

    # 2. SỔ ĐÓNG, gác CỨNG -- xem docstring module về vì sao ở đây cứng mà ở
    #    `agent/compose_page.py` thì không.
    for name in sorted({s for s in raw if SLOT_PATH.match(s)}):
        if _normalise(name) not in known:
            found.append(
                f"chỗ trống `{{{{{name}}}}}` không có trong sổ đường dẫn đóng "
                f"({len(known)} khoá); một phôi được điền hàng trăm lần nên "
                "một tên lạ ở đây là cùng một lỗi nhân lên chừng ấy lần")

    # 3. CHỖ TRỐNG PHẢI NGỒI TRONG MỘT RUN CÓ NHÃN, và `data-path` của run ấy
    #    phải là chính nó. Ngoài run có nhãn thì chữ vẫn in ra mà KHÔNG có hộp
    #    nào -- mất lặng lẽ, đúng thứ `llm_page.outside_sheet` đã đo được (một
    #    tờ 221 run mất 215).
    found += _slot_placement(body)

    # 4. KHỐI LẶP.
    found += _repeat_rules(body)
    return found


def _normalise(name: str) -> str:
    """`line_items[].name` là dạng sổ đăng ký đã gom về, nên chỗ trống dùng
    thẳng được. Hàm này tồn tại để chỗ so sánh có MỘT cái tên, không phải để
    biến đổi gì -- `field_tier.normalise()` gom `[3]`, ta không bao giờ có
    `[3]` trong phôi (mục 1 đã chặn)."""
    return name


class _Placement:
    """Vị trí mỗi chỗ trống so với run có nhãn gần nhất bao nó.

    Quét bằng thẻ chứ không bằng `HTMLParser`: cần BIÊN của mỗi `<span>` để
    biết một chỗ trống nằm trong hay ngoài, và `HTMLParser` cho sự kiện chứ
    không cho vị trí ký tự của thẻ đóng."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.spans: list[tuple[int, int, str, str]] = []     # mở, đóng, path, kind
        for m in re.finditer(r"<span\b[^>]*>", body, re.IGNORECASE):
            tag = m.group(0)
            path = _attr(tag, "data-path")
            kind = _attr(tag, "data-kind")
            end = _close_at(body, "span", m.start())
            if end is None:
                continue
            self.spans.append((m.end(), end, path, kind))

    def holding(self, at: int) -> tuple[str, str] | None:
        """`(data-path, data-kind)` của run TRONG CÙNG bao vị trí `at`."""
        best = None
        for start, end, path, kind in self.spans:
            if start <= at < end and (best is None or start > best[0]):
                best = (start, path, kind)
        return (best[1], best[2]) if best else None


def _attr(tag: str, name: str) -> str:
    m = re.search(name + r"\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))", tag,
                  re.IGNORECASE)
    if not m:
        return ""
    return m.group(2) or m.group(3) or m.group(4) or ""


def _slot_placement(body: str) -> list[str]:
    found: list[str] = []
    place = _Placement(body)
    for m in SLOT.finditer(body):
        name = m.group(1)
        if not SLOT_PATH.match(name):
            continue                         # mục 1 đã chê rồi
        held = place.holding(m.start())
        if held is None:
            found.append(
                f"chỗ trống `{{{{{name}}}}}` không nằm trong `<span data-kind>` "
                "nào; chữ ngoài run có nhãn vẫn in ra giấy mà không có hộp "
                "nào -- mất lặng lẽ")
            continue
        path, kind = held
        if not kind:
            found.append(f"run mang `{{{{{name}}}}}` thiếu `data-kind`; "
                         "phép đo chỉ ghi run CÓ nhãn")
        if path != name:
            found.append(
                f"chỗ trống `{{{{{name}}}}}` ngồi trong run khai "
                f"`data-path=\"{path}\"`; hai thứ ấy phải là một, nếu không "
                "lời khai danh tính nói về một trường còn chữ in ra là "
                "trường khác")
    return found


def _repeat_rules(body: str) -> list[str]:
    found: list[str] = []
    blocks = repeat_blocks(body)
    spans = [(s, e) for _n, s, e in blocks]

    # Thẻ mở có `data-repeat` mà `repeat_blocks` không dựng được khối = thẻ
    # không đóng. Nói ra, đừng im: `fill_html` sẽ bỏ qua nó và bảng ra đúng
    # một dòng mẫu mang nguyên `{{line_items[].name}}`.
    openers = len(re.findall(r"\b" + REPEAT_ATTR + r"\s*=", body, re.IGNORECASE))
    if openers > len(blocks):
        found.append(f"{openers - len(blocks)} khối `{REPEAT_ATTR}` không có "
                     "thẻ đóng khớp")

    for i, (name, start, end) in enumerate(blocks):
        for j, (other, ostart, oend) in enumerate(blocks):
            if i != j and ostart > start and oend <= end:
                found.append(f"khối `{REPEAT_ATTR}=\"{other}\"` lồng trong "
                             f"`{REPEAT_ATTR}=\"{name}\"`; khối lặp lồng nhau "
                             "không bung được")
        inner = [s for s in slots(body[start:end]) if SLOT_PATH.match(s)]
        mine = [s for s in inner if s.startswith(f"{name}[].")]
        if not mine:
            found.append(f"khối `{REPEAT_ATTR}=\"{name}\"` không có chỗ trống "
                         f"`{name}[].…` nào; nhân bản nó ra N lần chỉ được N "
                         "dòng giống hệt nhau")
        for other in sorted(set(inner) - set(mine)):
            found.append(
                f"chỗ trống `{{{{{other}}}}}` nằm trong khối lặp "
                f"`{name}` mà không thuộc nhóm ấy; nó sẽ in ra N lần và cổng "
                "chữ loại tờ vì 'mỗi giá trị phải có đúng một hộp'")

    # Chỗ trống có `[]` mà NGOÀI mọi khối lặp: không ai bung nó, và `[]` đi
    # thẳng ra giấy.
    for m in SLOT.finditer(body):
        name = m.group(1)
        if "[]" not in name or not SLOT_PATH.match(name):
            continue
        if not any(s <= m.start() < e for s, e in spans):
            found.append(
                f"chỗ trống `{{{{{name}}}}}` là chỗ trống dòng lặp mà không "
                f"nằm trong khối `{REPEAT_ATTR}` nào; không ai bung nó")
    return found


# ------------------------------------------------------------------- bung ra

def fill_html(html: str, values: dict, counts: dict | None = None) -> tuple[str, list[str]]:
    """Phôi + tờ khai sự thật -> HTML thật. `(html, chỗ trống không điền được)`.

    `values` là bảng PHẲNG đã bung chỉ số: `{"issuer.name": "...",
    "line_items[0].name": "...", ...}` -- `synthgen/fill.py::flatten()` dựng
    nó từ cây sự thật. `counts` là số dòng cho mỗi nhóm lặp
    (`{"line_items": 7}`); thiếu thì suy từ chính `values`.

    Không ném khi thiếu một giá trị: trả tên nó ra ở vế thứ hai và để nguyên
    `{{…}}` trên trang. Người gọi quyết định loại tờ hay điền mặc định --
    nhưng chỗ trống CÒN NGUYÊN trên giấy thì `problems()` của bước sau nhìn
    thấy ngay, còn một chuỗi rỗng lặng lẽ thay vào thì không ai thấy."""
    body = str(html or "")
    counts = dict(counts or {})
    body = _expand(body, values, counts)
    missing: list[str] = []

    def one(m: re.Match) -> str:
        name = m.group(1)
        if name in values:
            return _escape(str(values[name]))
        missing.append(name)
        return m.group(0)

    return SLOT.sub(one, body), sorted(set(missing))


def _expand(body: str, values: dict, counts: dict) -> str:
    """Nhân mỗi khối `data-repeat` ra N bản, thay `[]` bằng `[i]`.

    Bung TỪ CUỐI VỀ ĐẦU: mỗi lần thay đổi độ dài chuỗi thì mọi vị trí phía
    sau lệch đi, và `repeat_blocks()` đã đo vị trí trên bản CŨ."""
    for name, start, end in sorted(repeat_blocks(body), key=lambda b: -b[1]):
        n = counts.get(name)
        if n is None:
            n = _count_from(values, name)
        n = max(0, int(n))
        block = body[start:end]
        # Bỏ chính `data-repeat` khỏi bản đã bung: giữ nó lại thì một lần
        # `fill_html` thứ hai trên cùng chuỗi (ai đó điền hai lần) nhân bản
        # tiếp, và số dòng nhân lên theo luỹ thừa mà không ai kêu.
        block = re.sub(r"\s*\b" + REPEAT_ATTR + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
                       "", block, count=1, flags=re.IGNORECASE)
        body = body[:start] + "".join(_index(block, name, i)
                                      for i in range(n)) + body[end:]
    return body


def _index(block: str, name: str, i: int) -> str:
    """`line_items[]` -> `line_items[3]` trong CẢ thuộc tính lẫn chữ.

    Một phép thay chuỗi trên cả khối, không hai phép riêng: `data-path` và
    `{{…}}` phải mang cùng chỉ số, và hai phép riêng là hai chỗ để chúng
    lệch nhau."""
    return block.replace(f"{name}[]", f"{name}[{i}]")


def _count_from(values: dict, name: str) -> int:
    """Số dòng suy từ chính `values` khi caller không nói.

    Đếm chỉ số LỚN NHẤT + 1 chứ không đếm số khoá: một tờ khai có
    `line_items[0].name` và `line_items[2].name` (thiếu dòng 1) mà đếm khoá
    thì ra 2 dòng, và dòng `[2]` không bao giờ được in."""
    top = -1
    prefix = f"{name}["
    for key in values:
        if not key.startswith(prefix):
            continue
        close = key.find("]", len(prefix))
        if close < 0:
            continue
        try:
            top = max(top, int(key[len(prefix):close]))
        except ValueError:
            continue
    return top + 1


def _escape(text: str) -> str:
    """Chữ thật đi vào HTML. `&` trước, nếu không nó đá chính hai phép sau.

    Không escape `"` và `'`: giá trị chỉ vào phần CHỮ, không vào thuộc tính
    (`data-path` mang đường dẫn, không mang giá trị), và escape thừa thì một
    dấu nháy trong tên công ty in ra `&#39;` trên mặt giấy."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


__all__ = ["REPEAT_ATTR", "SLOT", "SLOT_PATH", "Template", "families",
           "fill_html", "paths", "problems", "repeat_blocks", "slots"]
