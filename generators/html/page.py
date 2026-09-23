"""What every page this backend renders needs, and nothing that needs a browser.

Two producers now sit on this backend -- `render.py` for receipts and invoices,
`tables.py` for table-structure pages -- and both need the same three things: a
Chromium to launch, the repository's fonts embedded so the browser cannot
substitute, and the snippet that reads boxes off the laid-out DOM. Keeping them
here means a change to any of the three happens once.

This module imports nothing heavy on purpose. `render.py` pulls in Playwright
and OpenCV at import time, so anything that wanted `find_chromium` had to pay
for a browser stack it was not going to use -- including the tests, which check
the markup and the labels and never open a page.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_ROOT = REPO_ROOT / "fonts"

# Bảng "thẻ HTML nghĩa là gì" sống ở `pipeline/tags.py`, không ở đây. Nó thuần
# thư viện chuẩn, nên dòng này không phá lời hứa ở đầu file -- và nó là cách
# `ZONE_REGIONS_JS` dưới kia thôi giữ một bản chép riêng lệch với bản mà
# `synthgen/repair.py` đọc. Xem chú thích của chính `pipeline/tags.py`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.tags import measured_elsewhere_js, region_by_tag_js  # noqa: E402

# Linux containers that ship a browser system-wide, this repository's own
# included. Elsewhere -- Windows, macOS, a plain `pip install playwright` --
# there is nothing here and Playwright resolves its own download instead.
CHROMIUM_CANDIDATES = [
    Path("/opt/pw-browsers/chromium/chrome-linux/chrome"),
    Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
]


def find_chromium() -> str | None:
    """A browser to launch, or None to let Playwright pick its own.

    Returning None is not a failure: `launch(executable_path=None)` is the
    normal path, and the only reason to override it is a container that already
    has a build and must not download a second one.
    """
    for path in CHROMIUM_CANDIDATES:
        if path.exists():
            return str(path)
    for path in sorted(Path("/opt/pw-browsers").glob("chromium*/chrome-linux/chrome")):
        return str(path)
    return None


def font_faces() -> str:
    """Embed the repo's fonts so the browser cannot silently substitute.

    A CSS stack that falls through to whatever the container happens to have
    is how a receipt ends up rendered in a font with no Vietnamese diacritics,
    with the label still claiming they were printed.

    The family name is the file stem: `LiberationMono-Regular.ttf` is
    `LiberationMono`, with no space. A stack that asks for "Liberation Mono"
    matches none of these and falls straight through to the system.
    """
    faces = []
    # `hand` belongs here for the same reason as the other three: a sheet that
    # asks for a handwriting face and does not get it falls through to whatever
    # the machine has, and the page still renders -- in type, while its label
    # says handwriting. That is the substitution this function exists to stop,
    # and leaving the group out made it certain rather than possible.
    for group in ("mono", "sans", "serif", "hand"):
        directory = FONT_ROOT / group
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.ttf")):
            family = path.stem.replace("-Regular", "").replace("-Bold", "")
            weight = "700" if path.stem.endswith("-Bold") else "400"
            faces.append(
                "@font-face{font-family:'%s';font-weight:%s;src:url('file://%s') format('truetype');}"
                % (family.replace("-", " "), weight, path)
            )
    return "\n".join(faces)


@contextmanager
def served(markup: str):
    """The markup as a `file://` page, so its `@font-face` sources actually load.

    `set_content` puts the page on an `about:blank` origin, and Chromium will
    not fetch a `file://` subresource from there. It fails *silently*: the rule
    parses, the face is registered, `document.fonts` lists it as `unloaded`
    forever, and the text is drawn in whatever the machine happens to have
    installed under a matching name. Which is exactly the substitution
    `font_faces` exists to prevent -- and it was measurable, not theoretical:
    the container's fallback draws `tố` as `tô` with a spacing acute after it,
    eating the following space, while the repo's own faces draw it correctly.
    """
    directory = tempfile.mkdtemp(prefix="vlm-page-")
    try:
        path = Path(directory) / "page.html"
        path.write_text(markup, encoding="utf-8")
        yield path.as_uri()
    finally:
        shutil.rmtree(directory, ignore_errors=True)


# Boxes are measured in the browser, off the page that was laid out, and both
# snippets return every rect in one `evaluate` rather than one round trip per
# element -- which is the whole speed difference between this and driving the
# same browser through Selenium.
#
# THREE granularities out of the same walk: `cells` (one box per LINE of a run
# -- feeds `blocks[]`/`quads_from_rects`, unchanged shape), `words` (one box
# per WHITESPACE-separated word inside each line -- feeds `word_annotations`),
# and `fields` (one entry per RUN, carrying the whole string and no geometry
# at all -- feeds `entity_annotations`).
#
# The third exists because the first two both CUT a run up, and KIE needs it
# whole: "Công ty cổ phần TNHH A" was five word boxes that nothing tied back
# together. Every `cells`/`words` entry now carries `field`, the index of the
# run it came out of, which is that tie.
#
# Both are measured with a `Range`, character by character, ALWAYS -- not
# only when a run wraps to two or more lines. A `<span>` is inline by default
# and shrinks to its own text, but a family's CSS can (and does, for
# heading-style kinds) set `display:block`, and a block box is exactly as
# wide as its CONTAINER regardless of how little text is in it. Measuring the
# span's own `getBoundingClientRect()` in that case gives a box round the
# whole row, not round the words -- Range measurement is immune to this: it
# reads where the glyphs actually painted, never the element's box.
#
# The union rectangle of a run that broke over two lines is not a box round
# the text either: it is a box round both lines *and the blank paper between
# their ragged ends*, which on a full-width block swallows whatever sits at
# the start of the first line. Measured: an invoice's "Số tiền bằng chữ:"
# label came out 100% inside the amount's box, and the overlap detector was
# right to call it. Splitting by line, and now within a line by whitespace,
# is the same fix at two grain sizes.
#
# The character grid never takes this path -- its cells are `white-space:pre`
# and always one line -- so nothing about it changes.
CELL_RECTS_JS = """() => {
  // Every printed side of this document, and the box each one occupies. A
  // layout with no `page_order` has exactly one, so this is the single sheet
  // it always was; a layout with one gets several, and a rect has to be
  // measured against the sheet it LANDS ON rather than against the first --
  // otherwise page 2's boxes come back offset by the height of page 1 and
  // every label on them points into white space.
  const SHEETS = [...document.querySelectorAll('.sheet')];
  const BOXES = new Map(SHEETS.map(
      (el, i) => [el, {rect: el.getBoundingClientRect(), page: i + 1}]));
  const FALLBACK = {rect: {left: 0, top: 0}, page: 1};
  const own = (el) => BOXES.get(el.closest('.sheet')) || FALLBACK;
  // A rotated/vertical header (`table.header_style: vertical|diagonal`) puts
  // its `transform`/`writing-mode` on an ANCESTOR of the span, never the span
  // itself -- the label contract still owns the span (see the module
  // docstring's three contracts). The per-character path below assumes
  // horizontal, unrotated glyphs: consecutive characters' `top` stays within
  // 1px of each other on an ordinary line, and under a rotated ancestor it
  // does not, so the "same line" test fires on almost every character and
  // splits one header into a dozen one-glyph boxes instead of one box round
  // the run. Detected once per span (walking to `#sheet`, never more than a
  // handful of elements) and routed through the SAME single-box path already
  // used for a hand-filled/sealed run's `<img>`, which is exactly what a
  // rotated run needs too: one `getBoundingClientRect()` of the whole thing,
  // not an attempt to line-group it.
  const isTransformed = (el) => {
    while (el && !(el.classList && el.classList.contains('sheet'))) {
      const t = getComputedStyle(el);
      if ((t.transform && t.transform !== 'none') ||
          (t.writingMode && t.writingMode !== 'horizontal-tb')) return true;
      el = el.parentElement;
    }
    return false;
  };
  const cells = [];
  const words = [];
  // Third grain, and the one KIE actually wants: ONE entry per labelled run,
  // carrying the whole string. `cells` splits a run by line and `words` splits
  // it by whitespace, so "Công ty cổ phần TNHH A" arrived downstream as five
  // boxes that nothing tied back together -- five words each carrying the same
  // `field_path` and no way to say they were one value.
  //
  // Deliberately carries NO GEOMETRY. Every box on this page is scaled by the
  // device ratio, scaled again by the downsample, re-projected by a warp and
  // clipped to the paper (`render.py`), and a fifth array riding through all
  // four is a fifth chance for the five to disagree. The entity's geometry is
  // therefore DERIVED from its own words in `pipeline/record.py`, after all of
  // that has happened to them -- so it is correct by construction rather than
  // by four more multiplications kept in step by hand.
  const fields = [];
  // `ink` is axis 3 (`pipeline/record.py::ink_for`): how the mark got onto the
  // paper. Absent on an ordinary printed run -- the page's own default covers
  // that -- and set only where the renderer knows something `kind` cannot say,
  // which is handwriting, a stamp impression, and type reversed out of a dark
  // band.
  // `at` is the owning sheet's `{rect, page}`, resolved once per span below.
  let at = FALLBACK;
  // `field` is the index of the run these came out of, so a word can be tied
  // back to the whole value it is one word of. Set once per span below.
  let field = -1;
  const pushCell = (kind, ink, text, box) => {
    if (!text.trim()) return;
    cells.push({kind, ink, text, field, page: at.page,
                x: box.left - at.rect.left, y: box.top - at.rect.top,
                w: box.width, h: box.height});
  };
  const pushWord = (kind, ink, text, box) => {
    if (!text.trim()) return;
    words.push({kind, ink, text, field, page: at.page,
                x: box.left - at.rect.left, y: box.top - at.rect.top,
                w: box.width, h: box.height});
  };
  const range = document.createRange();
  for (const span of document.querySelectorAll('.sheet span[data-kind]')) {
    at = own(span);
    field += 1;
    const kind = span.dataset.kind;
    // `closest`, not `span.dataset.ink`: a family marks a whole reversed BAND
    // once rather than every run inside it, and a hand-filled field wraps its
    // ink in an element of its own.
    const inked = span.closest('[data-ink]');
    const ink = inked ? inked.dataset.ink : '';
    // Two OPTIONAL attributes a family (or a composed page) may write to say
    // what `kind` cannot. Neither is required and no layout writes them today,
    // so every existing page comes out of here exactly as it did:
    //   data-role  "key" | "value" -- overrides the guess in
    //              `pipeline/record.py::_word_field_role`, which reads the
    //              `.label`/`.title` suffix convention and is right about
    //              every run this repository draws so far.
    //   data-key   the field name this run is the VALUE of, when the caption
    //              is not printed on the paper at all. A page title has no
    //              "Loại chứng từ:" beside it and is still the answer to that
    //              question -- see `entities_from_words`' virtual keys.
    const role = span.dataset.role || '';
    const key = span.dataset.key || '';
    const node = span.firstChild;
    const simple = node && node.nodeType === 3 && span.childNodes.length === 1
                   && !isTransformed(span);
    // A hand-filled or sealed run holds an <img> of ink, not a text node, so
    // its text rides on `data-text`. There is no glyph run to split by word
    // here -- the ink is shaped like the whole run -- so it becomes one cell
    // AND one word, same box, rather than being dropped from `words`.
    if (!simple) {
      const text = span.dataset.text ?? span.textContent;
      const box = (span.firstElementChild || span).getBoundingClientRect();
      if (text.trim()) fields.push({field, kind, ink, role, key, text,
                                    page: at.page});
      pushCell(kind, ink, text, box);
      pushWord(kind, ink, text, box);
      continue;
    }
    const text = node.data;
    // The whole run, before it is cut into lines and words below. `text` is
    // the text node's own data, so this is verbatim -- collapsing whitespace
    // by re-joining the words would not give it back.
    if (text.trim()) fields.push({field, kind, ink, role, key, text,
                                  page: at.page});
    let line = null;   // accumulates the whole line, for `cells`
    let word = null;   // accumulates since the last whitespace, for `words`
    const flushLine = () => {
      if (!line) return;
      pushCell(kind, ink, text.slice(line.from, line.to),
               {left: line.left, top: line.top, width: line.right - line.left,
                height: line.bottom - line.top});
    };
    const flushWord = () => {
      if (!word) return;
      pushWord(kind, ink, text.slice(word.from, word.to),
               {left: word.left, top: word.top, width: word.right - word.left,
                height: word.bottom - word.top});
      word = null;
    };
    for (let i = 0; i < text.length; i++) {
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      const r = range.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;   // a collapsed break
      if (line === null || Math.abs(r.top - line.top) > 1) {
        flushLine();
        flushWord();
        line = {top: r.top, left: r.left, right: r.right, bottom: r.bottom,
                from: i, to: i + 1};
      } else {
        line.left = Math.min(line.left, r.left);
        line.right = Math.max(line.right, r.right);
        line.bottom = Math.max(line.bottom, r.bottom);
        line.to = i + 1;
      }
      if (/\\s/.test(text[i])) {
        flushWord();
      } else if (word === null) {
        word = {top: r.top, left: r.left, right: r.right, bottom: r.bottom,
                from: i, to: i + 1};
      } else {
        word.left = Math.min(word.left, r.left);
        word.right = Math.max(word.right, r.right);
        word.bottom = Math.max(word.bottom, r.bottom);
        word.to = i + 1;
      }
    }
    flushLine();
    flushWord();
  }
  return {cells, words, fields};
}"""

# One box per table cell, with its position and span. A merged cell -- a totals
# row spanning six columns, a stub running down four -- has a text box that says
# nothing about the span, so the cell rect and the span are collected too. The
# idea and the token format come from TIES_DataGeneration by way of PaddleOCR.
CELL_REGIONS_JS = """() => {
  // Every printed side of this document, and the box each one occupies. A
  // layout with no `page_order` has exactly one, so this is the single sheet
  // it always was; a layout with one gets several, and a rect has to be
  // measured against the sheet it LANDS ON rather than against the first --
  // otherwise page 2's boxes come back offset by the height of page 1 and
  // every label on them points into white space.
  const SHEETS = [...document.querySelectorAll('.sheet')];
  const BOXES = new Map(SHEETS.map(
      (el, i) => [el, {rect: el.getBoundingClientRect(), page: i + 1}]));
  const FALLBACK = {rect: {left: 0, top: 0}, page: 1};
  const own = (el) => BOXES.get(el.closest('.sheet')) || FALLBACK;
  // `textContent`, except that a hand-filled run contributes its `data-text`
  // instead of the nothing an <img> contributes. Written as a walk rather than
  // as "the first data-text in the cell" because a cell can hold a printed
  // caption AND an inked value -- taking either one alone loses the other.
  //
  // No layout puts an inked value in a table cell today: checked over all
  // sixteen layouts and twelve seeds, every field a person fills in sits
  // outside the item table. This is here so that the first one that does not
  // fails visibly rather than by reporting an empty cell into the structure
  // label. With no `data-text` anywhere it is `textContent.trim()` exactly.
  const cellText = (root) => {
    let out = '';
    const walk = (node) => {
      if (node.nodeType === 3) { out += node.data; return; }
      if (node.nodeType !== 1) return;
      if (node.dataset && node.dataset.text !== undefined) {
        out += node.dataset.text;
        return;
      }
      for (const child of node.childNodes) walk(child);
    };
    walk(root);
    return out.trim();
  };
  // Ô thuộc BẢNG NÀO. Một trang có thể in hai bảng thật -- bảng hàng và khung
  // tổng hợp thuế -- và gộp chúng làm một vùng thì vùng ấy trùm luôn mấy dòng
  // chữ nằm giữa hai bảng. Số thứ tự của `<table>` gần nhất là câu trả lời rẻ
  // nhất và đúng: hai ô cùng một `<table>` thì cùng một bảng, khác thì khác.
  const TABLES = [...document.querySelectorAll('.sheet table')];
  return [...document.querySelectorAll('.sheet [data-cell]')].map(td => {
    const box = td.getBoundingClientRect();
    const at = own(td);
    const host = td.closest('table');
    return {
      kind: td.dataset.cell,
      text: cellText(td),
      table: host ? TABLES.indexOf(host) : -1,
      row: Number(td.dataset.row), col: Number(td.dataset.col),
      // Ô ở `<thead>` là ĐẦU CỘT. Đây là chuyện của DOM -- trình duyệt đã dàn
      // xong -- nên nó chắc hơn mọi phép suy từ `kind`, và `run_role` dùng nó
      // để trả `colhdr`. Bản trước không đo, nên `colhdr` ra 0 trên 17 882 run.
      head: !!td.closest('thead') || td.tagName.toLowerCase() === 'th',
      colspan: td.colSpan || 1, rowspan: td.rowSpan || 1,
      page: at.page,
      x: box.left - at.rect.left, y: box.top - at.rect.top,
      w: box.width, h: box.height,
    };
  });
}"""


# Every element that puts INK on the page and is not already a labelled run:
# a logo monogram, a rosette, a barcode, a watermark, a signature.
#
# `CELL_RECTS_JS` walks `span[data-kind]` and nothing else, so a page's
# pictorial furniture was invisible to the record -- a proof image showed the
# "C" logo circle at the top of every `modern` invoice with no box round it at
# all. Ink with no box is ink with no label, which is the one thing
# `pipeline/invariants.py` exists to refuse.
#
# **A list of selectors here rather than a `data-graphic` attribute in nine
# family modules.** Adding an attribute at every call site means the tenth
# family forgets, silently, and the failure looks exactly like this one did.
# `data-graphic` is still honoured first, for anything a family wants to mark
# explicitly.
#
# Three exclusions, and each of them is a real element on a real page:
#
# * **contains a `span[data-kind]`** -- `.flag` on a newspaper masthead and
#   `.brand` on an invoice are CONTAINERS of labelled runs, not pictures. Their
#   box would swallow the runs inside them and claim the whole block was an
#   image.
# * **inside a `span[data-kind]`** -- a hand-filled field is an `<img>` of ink
#   inside a labelled span, and `CELL_RECTS_JS` already boxes it as that run.
#   Boxing it again would put two labels on one mark.
# * **inside another candidate** -- `statement.py` draws `<svg class="mark">`,
#   which matches twice. The outer element is the picture.
_ZONE_REGIONS_TEMPLATE = """() => {
  // Khối tự khai mình là MỘT vùng bố cục: `<div data-region="Text">`.
  //
  // Bộ gom vùng mặc định nối các từ cùng nhãn lại và cắt ở chỗ hở rộng. Luật
  // ấy đúng cho chữ chạy và sai cho một khối "nhãn ... giá trị": máng giữa
  // hai cột rộng hơn ngưỡng cắt, nên "Tổng cộng tiền thanh toán" và
  // "1.569.081.240 đ" rơi ra hai vùng dù chúng là một dòng của cùng một khối.
  // Đo được trên một tờ bảng kê: khối tổng ra TÁM vùng rời.
  //
  // Không đoán lại bằng hình học: chính DOM đã biết đâu là một khối, và hộp
  // của khối là hộp của phần tử -- kể cả viền và lề của nó, đúng thứ người
  // đọc gọi là "cái khung tổng", chứ không phải hợp các mẩu chữ bên trong.
  const SHEETS = [...document.querySelectorAll('.sheet')];
  const BOXES = new Map(SHEETS.map(
      (el, i) => [el, {rect: el.getBoundingClientRect(), page: i + 1}]));
  const FALLBACK = {rect: {left: 0, top: 0}, page: 1};
  const own = (el) => BOXES.get(el.closest('.sheet')) || FALLBACK;
  // THẺ HTML CŨNG KHAI VÙNG, không chỉ `data-region`.
  //
  // `<ul>` LÀ một danh sách, `<figcaption>` LÀ một chú thích, `<h2>` LÀ một
  // tiêu đề mục -- chuẩn HTML đã nói thế, và một model viết trang bằng thẻ
  // đúng nghĩa thì không có lý do gì bắt nó khai thêm một lần nữa bằng thuộc
  // tính. Đo trên pilot9: nhiều khối ra ảnh không có hộp nào chỉ vì model
  // dùng `<ul>` mà quên `data-region="List-Group"`.
  //
  // `data-region` viết tay THẮNG: tác giả nói rõ thì nghe tác giả. Suy từ thẻ
  // chỉ là lưới đỡ cho khối chưa khai.
  //
  // KHÔNG suy cho `<table>`: `CELL_REGIONS_JS` đã đo bảng theo từng ô, và
  // thêm một vùng `Table` nữa ở đây là đếm hai lần.
  const BY_TAG = __BY_TAG__;
  const TAGS = Object.keys(BY_TAG).join(',');
  const seen = new Set();
  const out = [];
  // HỘP BÁM MỰC, không bám thẻ.
  //
  // `getBoundingClientRect()` của một thẻ KHỐI là hết bề ngang dòng, kể cả
  // khi chữ trong nó là một dòng tiêu đề căn giữa dài một phần tám tờ giấy.
  // Đo trên một lượt vẽ: 37 trên 62 vùng có chữ rộng hơn hẳn chữ trong
  // chúng, nặng nhất là `Title` -- hộp 843 phần nghìn bề ngang cho một dòng
  // chữ rộng 124. Một cái hộp như thế không tả được thứ gì trên giấy, và đó
  // đúng là luật `pipeline/record.py` đặt ra cho mọi hộp khác.
  //
  // `Range.getBoundingClientRect()` trả về bao lồi của các HỘP DÒNG bên
  // trong -- tức đúng vùng có mực. Dùng nó thay hộp thẻ, TRỪ khi chính thẻ
  // vẽ ra cái gì: có viền, có nền, hoặc là ô ảnh. Khi ấy khung mới là thứ
  // người đọc thấy, và hộp phải ôm khung chứ không ôm chữ trong khung.
  const paints = (el) => {
    const cs = getComputedStyle(el);
    if (cs.backgroundImage && cs.backgroundImage !== 'none') return true;
    const bg = cs.backgroundColor || '';
    if (bg && bg !== 'transparent' && !bg.startsWith('rgba(0, 0, 0, 0')) return true;
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      if (parseFloat(cs['border' + side + 'Width']) > 0.01
          && cs['border' + side + 'Style'] !== 'none') return true;
    }
    return false;
  };
  const inkBox = (el) => {
    const box = el.getBoundingClientRect();
    if (paints(el)) return box;
    let range;
    try {
      range = document.createRange();
      range.selectNodeContents(el);
    } catch (e) { return box; }
    const ink = range.getBoundingClientRect();
    range.detach && range.detach();
    if (!(ink.width > 0 && ink.height > 0)) return box;
    // Không bao giờ NỚI RA: bao lồi của hộp dòng có thể tràn khỏi thẻ khi
    // con của nó nổi hoặc định vị tuyệt đối, và một hộp rộng hơn cả thẻ thì
    // sai theo chiều ngược lại.
    const left = Math.max(box.left, ink.left);
    const right = Math.min(box.right, ink.right);
    const top = Math.max(box.top, ink.top);
    const bottom = Math.min(box.bottom, ink.bottom);
    if (!(right > left && bottom > top)) return box;
    return {left: left, top: top, width: right - left, height: bottom - top};
  };
  const add = (el, label, from_) => {
    if (seen.has(el)) return;
    seen.add(el);
    const box = inkBox(el);
    if (!(box.width > 0 && box.height > 0)) return;
    const at = own(el);
    out.push({
      label: label, page: at.page, from: from_,
      x: box.left - at.rect.left, y: box.top - at.rect.top,
      w: box.width, h: box.height,
    });
  };
  // NHÃN ĐÃ CÓ PHÉP ĐO RIÊNG THÌ KHÔNG QUA ĐÂY, kể cả khi tác giả khai tay
  // `data-region`. `MEASURED_ELSEWHERE` (`pipeline/tags.py`) là bảng DUY
  // NHẤT nói "nhãn này KHÔNG đến từ `data-region`" -- nhánh SUY TỪ THẺ dưới
  // kia đã tra bảng ấy từ trước (`<table>` không có mặt trong `BY_TAG`);
  // nhánh KHAI TAY này trước bản sửa này thì KHÔNG, và một `<table
  // data-region="Table">` (đúng cách một model từng viết thật, xem
  // `data/pilot16/records/export_invoice/llm_export_invoice_0003.json`) lọt
  // thẳng qua, ra một vùng `Table` thứ hai chồng lên vùng `CELL_REGIONS_JS`
  // đã đo từ chính các ô. Cùng MỘT bảng, hai nhánh đều tra nó -- không phải
  // hai danh sách chép tay có thể lệch nhau.
  const MEASURED_ELSEWHERE = __MEASURED_ELSEWHERE__;
  for (const el of document.querySelectorAll('.sheet [data-region]')) {
    if (MEASURED_ELSEWHERE.includes(el.dataset.region)) continue;
    add(el, el.dataset.region, 'declared');
  }
  for (const el of document.querySelectorAll('.sheet ' + TAGS.split(',').join(', .sheet '))) {
    const label = BY_TAG[el.tagName.toLowerCase()];
    // Bỏ qua khi một tổ tiên đã cho ra ĐÚNG nhãn ấy: `<ul>` trong một
    // `<div data-region="List-Group">` là cùng một vùng nói hai lần.
    let parent = el.parentElement, twice = false;
    while (parent && parent !== document.body) {
      if (parent.dataset && parent.dataset.region === label) { twice = true; break; }
      if (BY_TAG[parent.tagName.toLowerCase()] === label) { twice = true; break; }
      parent = parent.parentElement;
    }
    if (!twice) add(el, label, 'tag');
  }
  return out;
}"""

# Dán bảng vào khuôn một lần, lúc nạp module. `replace` chứ không f-string:
# thân hàm JS đầy `{`/`}` và một f-string ở đây là một bãi mìn dấu ngoặc.
ZONE_REGIONS_JS = (_ZONE_REGIONS_TEMPLATE
                   .replace("__BY_TAG__", region_by_tag_js())
                   .replace("__MEASURED_ELSEWHERE__", measured_elsewhere_js()))


GRAPHIC_RECTS_JS = """() => {
  // Every printed side of this document, and the box each one occupies. A
  // layout with no `page_order` has exactly one, so this is the single sheet
  // it always was; a layout with one gets several, and a rect has to be
  // measured against the sheet it LANDS ON rather than against the first --
  // otherwise page 2's boxes come back offset by the height of page 1 and
  // every label on them points into white space.
  const SHEETS = [...document.querySelectorAll('.sheet')];
  const BOXES = new Map(SHEETS.map(
      (el, i) => [el, {rect: el.getBoundingClientRect(), page: i + 1}]));
  const FALLBACK = {rect: {left: 0, top: 0}, page: 1};
  const own = (el) => BOXES.get(el.closest('.sheet')) || FALLBACK;
  const SELECTOR = '[data-graphic],.logo,.mark,.bars,.wm,.sig,svg,img';
  const all = [...document.querySelectorAll('.sheet ' + SELECTOR)];
  // HAI LƯỢT, và thứ tự là cả vấn đề. Lượt một bỏ những phần tử KHÔNG phải
  // mực-không-chữ: thứ có `span[data-kind]` bên trong là một khối chữ, thứ
  // nằm trong một `span[data-kind]` là một phần của chữ ấy.
  const inked = all.filter(el => {
    if (el.querySelector('span[data-kind]')) return false;
    if (el.closest('span[data-kind]')) return false;
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });
  // Lượt hai giữ cái NGOÀI CÙNG -- nhưng chỉ so với những cái đã SỐNG SÓT
  // lượt một. So với `all` là lỗi đã xảy ra: mã vạch của `synthgen` là
  // `<span class="barcode" data-graphic>` nằm trong `<div class="blk mark">`,
  // cái div ấy khớp `.mark` nên có trong `all`, bị lượt một loại vì chứa
  // `span[data-kind]` (số mã vạch in dưới) -- rồi vẫn kéo theo mã vạch xuống
  // cùng. Kết quả: mã vạch không có hộp nào trên cả bộ dữ liệu, và không gì
  // báo, vì "không có hộp" trông y hệt "không có hình".
  const keep = inked.filter(
      el => !inked.some(other => other !== el && other.contains(el)));
  return keep.map(el => {
    const box = el.getBoundingClientRect();
    const at = own(el);
    return {
      kind: el.dataset.graphic || el.className.baseVal || el.className || el.tagName.toLowerCase(),
      page: at.page,
      x: box.left - at.rect.left, y: box.top - at.rect.top,
      w: box.width, h: box.height,
    };
  });
}"""

__all__ = [
    "CELL_RECTS_JS", "CELL_REGIONS_JS", "CHROMIUM_CANDIDATES", "FONT_ROOT",
    "GRAPHIC_RECTS_JS", "ZONE_REGIONS_JS",
    "REPO_ROOT", "find_chromium", "font_faces", "served",
]
