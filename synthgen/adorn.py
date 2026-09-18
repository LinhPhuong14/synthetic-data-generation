"""Điền mực THẬT vào chỗ model đặt sẵn: con dấu, mã vạch, mã QR.

## Ranh giới

Model quyết tờ giấy này CÓ con dấu hay không, và dấu nằm ở đâu. Engine quyết
con dấu ấy TRÔNG RA SAO. Đó đúng là ranh giới `synthgen/markup.py` vẫn giữ, và
nó ở đây vì hai lý do đo được:

* Con dấu model tự vẽ bằng CSS là một vòng tròn có viền. Con dấu Việt Nam thật
  có quốc huy, vành chữ, ngôi sao, và mực lem -- `textures/ornament/` có sẵn
  hai mươi sáu tấm ấy, do `tools/make_ornaments.py` dựng.
* Hộp phải bám ĐƯỜNG NGOÀI của dấu. `seal_art()` cắt ảnh sát mực trước khi
  nhúng, nên hộp `GRAPHIC_RECTS_JS` đo được bám sẵn mà không ai phải tính.
  Một `<div>` CSS thì hộp là hộp của `<div>`, rộng hơn vệt mực -- đúng cái lỗi
  `Stamp` thừa 16% bề ngang đo được ở pilot7.

## Hợp đồng với model

Model viết đúng một thẻ rỗng, không `src`:

    <img data-graphic="seal" data-seal="tron" alt="" class="seal">

`data-seal` nhận `tron` hoặc `vuong`. Engine thay `src` bằng ảnh thật và đặt
`width`/`height` theo đúng tỉ lệ tấm ảnh. Vị trí thì CSS của model tự lo -- đó
là phần bố cục, và bố cục là chỗ model được tự do.

Không có thẻ ấy thì không có gì xảy ra: tờ giấy không đóng dấu là chuyện bình
thường, và hàm này không tự ý thêm dấu vào tờ nào.
"""

from __future__ import annotations

import re

_PLACEHOLDER = re.compile(
    r"<img\b(?=[^>]*\bdata-graphic=[\"']seal[\"'])([^>]*)>", re.IGNORECASE)
_ATTR = lambda name: re.compile(                                # noqa: E731
    rf"\b{name}=[\"']([^\"']*)[\"']", re.IGNORECASE)
_SRC, _SEAL = _ATTR("src"), _ATTR("data-seal")
_STYLE = _ATTR("style")

# Bề ngang in ra, theo mm. Dấu tròn Việt Nam thường 36 mm, dấu vuông rộng hơn.
WIDTH_MM = {"tron": 26.0, "vuong": 30.0}


def _groups() -> dict[str, tuple[str, ...]]:
    from synthgen.markup import SEALS                       # noqa: PLC0415

    return {"tron": SEALS["dau_tron"], "vuong": SEALS["dau_vuong"]}


def seals(html: str, seed: int = 0) -> tuple[str, int]:
    """Điền ảnh dấu thật vào mọi chỗ đặt sẵn. `(html, số dấu đã điền)`."""
    from synthgen.markup import seal_art                    # noqa: PLC0415

    groups, filled = _groups(), 0

    def fill(m: re.Match) -> str:
        nonlocal filled
        attrs = m.group(1)
        got = _SRC.search(attrs)
        if got and got.group(1).strip():
            return m.group(0)          # model đã tự nhúng ảnh -- không đụng
        want = (_SEAL.search(attrs).group(1).lower()
                if _SEAL.search(attrs) else "tron")
        group = groups.get(want) or groups["tron"]
        # Dấu nào trong nhóm là hàm thuần của seed và của thứ tự dấu trên
        # trang: cùng tờ thì cùng dấu, hai tờ khác nhau không đóng chung một
        # cái. Cùng lối `markup._ornament` đã dùng.
        stem = group[(seed + filled) % len(group)]
        uri, ratio = seal_art(stem)
        width = WIDTH_MM.get(want, 26.0)
        size = f"width:{width:.1f}mm;height:{width * ratio:.1f}mm"
        rest = _SRC.sub("", attrs)
        style = _STYLE.search(rest)
        if style:
            rest = _STYLE.sub(f'style="{size};{style.group(1)}"', rest, count=1)
        else:
            rest += f' style="{size}"'
        filled += 1
        return f'<img src="{uri}"{rest}>'

    return _PLACEHOLDER.sub(fill, html), filled


# Nét chữ ký. `fonts/hand/` có ba mươi ba phông viết tay hỗ trợ tiếng Việt có
# dấu -- đó là điều kiện lọc, vì một phông thiếu dấu in ra "Nguyên Văn A" thay
# vì "Nguyễn Văn A" và nhãn nói một đằng, mực một nẻo.
HAND_DIR = "fonts/hand"

# Cỡ chữ ký so với chữ thân. Chữ viết tay thật to hơn chữ in quanh nó.
HAND_SCALE = 1.45


def _hand_faces() -> list:
    from pathlib import Path                                # noqa: PLC0415

    root = Path(__file__).resolve().parents[1] / HAND_DIR
    return sorted(root.glob("*.ttf")) if root.is_dir() else []


def hands(html: str, seed: int = 0) -> tuple[str, int]:
    """Cho `sign.name` một nét viết tay. `(html, số chữ ký đã thay nét)`.

    ## Vì sao engine làm, không phải model

    Model không nhúng được phông: lời dặn cấm tải từ mạng (trang phải vẽ được
    trên máy không có mạng), và nó không đọc được file trên đĩa. Nên nếu để
    model lo, mọi chữ ký in ra bằng chính phông thân bài -- và một tờ giấy mà
    tên người ký cùng nét với chữ in là một tờ giấy không ai ký.

    ## Vì sao `file://` chứ không base64

    Cùng lối `generators/html/page.py::font_faces` đã dùng cho cả kho: trang
    được `served()` đặt trên một `file://` origin chính là để Chromium nạp được
    phông trên đĩa. Bản đầu của hàm này nhúng base64 và một tờ ba chữ ký phồng
    lên một megabyte; cắt phông xuống còn 130 KB, còn `file://` thì còn vài
    trăm byte. Hai mươi nghìn tờ là khác biệt nhiều gigabyte.

    Cái giá: tệp HTML lưu lại trỏ tới đường dẫn tuyệt đối trên máy này. Mở nó ở
    máy khác thì chữ ký rơi về phông thân bài. Chấp nhận được, vì thứ đem đi
    huấn luyện là ẢNH đã vẽ, còn HTML là vết tích để truy lại.

    ## Vì sao mỗi người ký một nét

    Ba người ký cùng một nét là ba người cùng một bàn tay. Chọn theo `seed` nên
    lượt chạy lặp lại được, nhưng lệch nhau trong cùng một tờ."""
    faces = _hand_faces()
    if not faces or 'data-kind="sign.name"' not in html:
        return html, 0

    spots = html.count('data-kind="sign.name"')
    pick = [faces[(seed * 7 + i * 13) % len(faces)] for i in range(spots)]

    rules, used = [], []
    for i, face in enumerate(pick):
        name = f"hand{i}"
        rules.append(f"@font-face{{font-family:'{name}';font-weight:400;"
                     f"src:url('file://{face}') format('truetype');}}")
        used.append(name)

    seen = -1

    def wear(m: re.Match) -> str:
        nonlocal seen
        seen += 1
        family = used[min(seen, len(used) - 1)]
        style = (f"font-family:'{family}';font-size:{HAND_SCALE}em;"
                 f"font-weight:400;font-style:normal")
        attrs = m.group(1)
        had = _STYLE.search(attrs)
        if had:
            return m.group(0).replace(had.group(0),
                                      f'style="{had.group(1)};{style}"')
        return f"<span{attrs} style=\"{style}\">"

    out = re.sub(r'<span\b((?=[^>]*\bdata-kind="sign\.name")[^>]*)>', wear, html)
    head = "<style>" + "".join(rules) + "</style>"
    return (out.replace("</style>", "</style>" + head, 1)
            if "</style>" in out else head + out), spots
