"""The shape of one page's record, checked where it is written.

    data/dataset60/html/
        html_000.jpg     html_000.json
        html_001.jpg     html_001.json
        …                synthesis.json

**One file per image, not one index for the set.** A converted page comes back
as one document about one file, so that is what is written here: the record has
the image's name with a `.json` suffix and sits next to it. The images are
therefore the listing -- nothing has to be told which files in a directory are
records, an image with no record beside it is an error `read` raises rather than
skips, and a single page can be handed to somebody without shipping the index of
a set they do not have.

Each renderer builds its own dict, so a key can drift in one of the three and
nothing says so until somebody loads the dataset and finds a field missing for a
fifth of it. This is the one definition: `build` assembles a record, `validate`
is called on the way out, and every reader goes through the accessors at the
bottom rather than reaching for a key by name.

**The shape is the converter's, and only the converter's.** A page produced
here is meant to stand in for a page that came back from the document converter,
so a line carries what a converted line carries and nothing else:

    schema_version  8 -- the converter's schema this shape follows
    job_id          uuid5 of parser|layout|seed|filename: same page, same id
    task            what produced the record: `convert`, or `table_structure`
    parser          which renderer drew it (was `framework`)
    filename        the image, relative to the backend's directory
    source_files    what the job was given; one drawn page, so `[filename]`
    settings        the job's options, spelled as the converter spells them
    documents       segmentation, which a single drawn page has none of: `[]`
    pages           one entry: page number, pixel size, and the sample's blanks
    blocks          one per drawn field, in reading order (was `boxes`)
    markdown        the page as markdown, built from the blocks
    html            the same, as HTML
    extracted       the CORD-style nested label as an object (was `ground_truth`)

**How the page was made is not in here.** The seed, the six sampled attributes
and their params, the flat reading order: none of that is something a converter
could return, and most of it is the same text on every page of a run --
`ornament` and `augmentation` describe a *background*, and twenty pages sharing
one chain wrote that chain out twenty times. It lives in `synthesis.json` in the same
directory instead, params written once per option id, joined back to a page by
its `job_id` or its file name -- one file for the set, because it is a statement
about the set. `pipeline/synthesis.py` is that file, and
`Synthesis.recipe()` hands back exactly the `recipe.to_dict()` the rule-base
produced.

**Why a block keeps `kind`, `text` and `quad` beside `label`, `bbox` and
`content`.** The converter's block is a region of a page and its label is one of
eleven layout classes; this generator's box is one *field* and its kind names
which field (`total.grand.label`, `menu.qty`). Collapsing the second into the
first would throw away what every check in `pipeline/invariants.py` is written
against, and `bbox` cannot hold a quad that follows a curl in the paper -- the
glyph backend draws those, and `tools/check_boxes.py` reads them. So both are
written: `label`/`bbox`/`content` for a converter-shaped consumer, and
`kind`/`text`/`quad` for everything in this repository. `label` is derived from
`kind` by `label_for`, once, here.

**HỆ TOẠ ĐỘ: 0..1000, không phải pixel.** `bbox`, `polygon`, `quad`, `lines`
và mọi khoá `*_bbox` là PHẦN NGHÌN của cạnh tờ giấy (`bbox_mode:
"xyxy_per_mille"`). Số pixel đo được vẫn còn, ở khoá `*_px` bên cạnh.

Vì sao chiều ấy: thứ một mô hình thị giác - ngôn ngữ đọc và sinh ra là hệ
chuẩn hoá -- một hộp pixel chỉ có nghĩa khi kèm kích thước ảnh, mà `--scale`,
phép thu theo `short_size` và phép làm cũ đều đổi kích thước ấy.
`synthgen/export.py` đã xuất hệ 1000 từ lâu, nên trước thay đổi này kho có
HAI hệ toạ độ cho cùng một tờ giấy.

Pixel không bỏ được -- `synthgen/overlay.py` vẽ hộp lên ảnh và
`synthgen/augment.py` chiếu lại từng góc khi làm cong giấy -- nên đổi tên chứ
không xoá. Phép chuyển nằm ở ĐÚNG MỘT CHỖ (`to_per_mille`, gọi trong
`build()`): mọi phép đo hình học trong file này -- gom vùng, đo khoảng hở, xét
kề nhau -- chạy bằng pixel và phải chạy bằng pixel.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from . import kie

# The converter schema these records follow. Bumped only when the converter's
# own schema is, which is why it is a number copied from it rather than one this
# repository owns.
SCHEMA_VERSION = 8

# What produced the record. A drawn document page is a `convert` job; a table
# image is a `table_structure` one, and `generators/html/tables.py` says so --
# their labels are different things and flattening one into the other would lie.
TASK_CONVERT = "convert"
TASK_TABLE = "table_structure"

# `job_id` is a uuid5 rather than a uuid4 because `metadata.jsonl` is hashed:
# `tools/baseline.py` compares every line of a run against a captured one, so a
# random id would make every verification fail and every dataset unreproducible.
# uuid5 of the four things that decide what the page *is* -- see `job_id`.
JOB_NAMESPACE = uuid.UUID("29ede217-1783-5493-a680-21290a740c52")

# --------------------------------------------------------------- block labels

# The converter's layout vocabulary, which is DocLayNet's. Fixed by what reads
# these records, not by this repository: a twelfth label here would be one no
# consumer has a class for. `label_for` may only return one of these, and
# `tests/test_record.py` checks that it does.
PAGE_LABELS = frozenset({
    "Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header",
    "Picture", "Section-header", "Table", "Text", "Title",
})

# kind prefix -> the converter's layout label. Longest prefix wins, so
# `total.grand.label` follows `total.` and `store.address.label` follows
# `store.` without either being listed. `tests/test_record.py` walks every kind
# in every committed dataset through `label_for` and fails on one that lands on
# the fallback, which is what stops a new field kind from being labelled `Text`
# by accident.
LABELS: dict[str, str] = {
    "title": "Title",
    # Dòng phụ dưới tiêu đề: "Số: ..../GUQ", "Mẫu số: 01/BV", "Bộ phận: ....".
    # Là chữ chạy, không phải tiêu đề mục -- xét theo NGHĨA chứ không theo
    # chỗ nó đứng. `generators/html/sheets/` cũng xếp `subtitle` cùng nhóm
    # với `serial`, `form_no`, `period`, tức là cùng một loại dòng.
    # Tiêu đề bảng ("BẢNG KÊ CHI TIẾT") là chuyện khác, và có `kind` riêng
    # là `caption.table`.
    "subtitle": "Text",
    "caption.table": "Section-header",
    "parties.title": "Section-header",
    "store.": "Page-header",
    "invoice.subtitle": "Section-header",
    "invoice.": "Text",
    # Số mã vạch in DƯỚI mã vạch, không phải một ô bảng. Tiền tố dài hơn
    # thắng, nên dòng này lấy lại đúng một `kind` khỏi họ `menu.` -- mọi cột
    # hàng khác vẫn là `Table`.
    "menu.barcode": "Text",
    "menu.": "Table",
    "colhdr": "Table",
    "colnum": "Table",
    # `total.`/`summary.` KHÔNG phải `Table`. Cùng một kho dựng khối tổng bằng
    # hai cách: `sheets/base.py::_item_row` và `sheets/medical.py` in nó thành
    # `<tr><td>` TRONG bảng hàng -- ô bảng thật; còn khối `.totals` của
    # `sheets/base.py` và `synthgen/markup.py::_totals` in nó thành
    # `<div class="trow">` -- không ô nào, không cột nào, chỉ NHÌN giống lưới.
    # Một bảng tra theo `kind` không phân biệt được hai chuyện ấy, nên nó nói
    # dối ở hai trong ba chỗ.
    #
    # Luật đúng: `Table` là thứ một phần tử LÀ, không phải thứ chữ của nó
    # NGHĨA LÀ. Nên ở đây trả nhãn của một khối chữ thường, còn từ nào thật sự
    # nằm trong `<td>` đo được thì `regions_from_words` nâng lên `Table`.
    "total.": "Text",
    "summary.": "Text",
    "period": "Text",
    "meta": "Text",
    "note": "Text",
    # Sáu khối không-phải-bảng, thêm cùng lúc. Nhãn VÙNG của chúng do
    # `data-region` khai thẳng trong markup; bảng này lo nhãn của từng
    # đoạn chữ bên trong, và chúng đều là chữ chạy.
    "legal.basis": "Text",
    "clause.": "Text",
    "formula": "Text",
    "caption.figure": "Caption",
    "footnote": "Footnote",
    "toc.": "Text",
    "survey.": "Text",
    "sign.": "Text",
    # `Page-Footer` dành cho thứ THẬT SỰ ở chân trang -- số trang. Dòng ghi
    # chú cuối tờ ("Công ty chỉ trả sau khi đối chiếu chữ ký...") là một
    # câu của chứng từ, tình cờ in ở dưới; xét theo nghĩa thì nó là chữ
    # chạy. Tiền tố dài hơn thắng, nên `footer.page` vẫn là chân trang.
    "footer.page": "Page-footer",
    "footer": "Text",
    "cell": "Table",
    # A struck seal is ink, not running text -- `Picture` is the closest thing
    # the converter's own vocabulary has to "not words". See
    # `generators/html/sheets/base.py::seal_mark`.
    "seal.": "Picture",
    # The party block of an invoice. `parties.title` above is the section
    # heading ("THÔNG TIN CÁC BÊN"); everything else under it -- the per-side
    # titles and the field labels -- is running text. Longest prefix wins, so
    # this does not take the heading back.
    "parties.": "Text",

    # ----------------------------------------------------------------------
    # The periodical family: newspapers, magazines, classifieds.
    #
    # These 65 kinds went UNMAPPED for as long as no committed dataset held a
    # periodical page -- the layouts shipped, the fallback quietly labelled
    # every field `Text`, and `test_every_kind_in_every_committed_dataset_is_mapped`
    # had nothing to walk. `data/layouts84` is the first set that draws all 42
    # layouts, which is what turned the hole into a failing test.
    # Quốc hiệu và tiêu ngữ ("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM" /
    # "Độc lập - Tự do - Hạnh phúc"). Là chữ chạy, không phải tiêu đề của
    # tờ giấy: mọi công văn đều in đúng hai dòng ấy, nên chúng không nói
    # tờ này là giấy gì. Gọi là `Title` thì một trang có HAI `Title` và
    # không cái nào là tên chứng từ. Hai bảng dưới đây còn từng nói hai
    # chuyện khác nhau về cùng một `kind`: `Title` ở bảng này,
    # `Section-Header` ở bảng kia.
    # Chữ chìm ("BẢN SAO", "HOÁ ĐƠN MẪU"): mờ và xoay, nhưng vẫn là chữ in
    # ra và vẫn đọc được, nên nó là `Text` chứ không phải một tấm ảnh.
    "watermark": "Text",
    "masthead": "Text",
    "issue_": "Page-header",           # issue_label, issue_no, issue_date
    "slogan": "Page-header",
    "price": "Page-header",            # the cover price, beside the masthead
    "website": "Page-footer",
    "hotline": "Page-footer",
    "page_no": "Page-footer",
    # The lead story, and the ones below the fold.
    "headline": "Title",
    "hero.headline": "Title",
    "hero.kicker": "Section-header",
    "hero.": "Text",                   # byline, teaser, page_no
    "kicker": "Section-header",
    "deck": "Section-header",
    "dateline": "Text",
    "byline": "Text",                  # byline, byline_by, byline_photo
    "body": "Text",
    "jump": "Text",                    # "xem tiếp trang 4"
    "pull_quote": "Text",
    "caption": "Caption",
    "bottom.headline": "Section-header",
    "bottom.caption": "Caption",
    "bottom.": "Text",
    "teaser.kicker": "Section-header",
    "teaser.headline": "Section-header",
    "teaser.": "Text",
    "section": "Section-header",       # section, section.name
    "category": "Section-header",
    # A magazine's table of contents is a LIST, not running text: each entry is
    # a title, a teaser and the page it is on. `List-item` is the one label in
    # the converter's vocabulary that says so.
    "entry.": "List-item",
    # The interview.
    "qa.question": "Section-header",
    "qa.answer": "Text",
    "subject_": "Text",                # subject_name, subject_role
    "bio_title": "Section-header",
    "bio.": "Text",
    "sidebar.title": "Section-header",
    "sidebar.": "Text",
    # Classifieds: small ads, official notices, obituaries.
    "ad.heading": "Section-header",
    "ad.": "Text",
    "notice.title": "Section-header",
    "notice.": "Text",
    "obit.title": "Section-header",
    "obit.": "Text",
    "condolence": "Text",
    "rate": "Text",                    # the line-rate card at the foot

    # ----------------------------------------------------------------------
    # Three kinds this table went without while `DOCSYNTH_LABEL_FOR_KIND`
    # below already had them -- two tables, one vocabulary each, and a kind
    # added to the lower one is easy to leave out of this one. Every page that
    # drew them got `Text` from the fallback: a blank photo box labelled as
    # running text, and a lettered heading ("A. Thông tin dự án") labelled as
    # the paragraph under it.
    # Ô dán ảnh: một khung rỗng có in chữ "ẢNH" và "4 x 6". KHÔNG có tấm
    # ảnh nào trong đó -- chỉ có chữ và một đường viền -- nên gọi nó là
    # ảnh là dạy một bộ nhận dạng rằng khung rỗng có chữ là ảnh.
    "photo.": "Text",
    "subhead": "Section-header",
}

# What a kind nobody has mapped becomes. Deliberately the converter's most
# generic label rather than an error: an unmapped kind must not stop a shard
# halfway through a run. `tests/test_record.py` is where it is caught instead.
DEFAULT_LABEL = "Text"

# Labels that own a whole line of the page, so they are never joined with the
# block beside them when the markdown is built.
STANDALONE = {"Title", "Section-header", "Picture"}

# Labels to a markdown prefix. Everything not listed is written as it stands.
MARKDOWN_PREFIX = {"Title": "# ", "Section-header": "## "}

# The HTML element vocabulary the converter's own HTML consumer accepts.
# `HTML_TAG` below may only pick from here -- checked by
# `test_every_html_tag_is_one_the_converter_allows` rather than left as a
# comment, so a future label cannot quietly pick a tag nothing downstream
# renders.
ALLOWED_TAGS = frozenset({
    "math", "br", "i", "b", "u", "del", "sup", "sub", "table", "tr", "td",
    "p", "th", "div", "pre", "h1", "h2", "h3", "h4", "h5", "ul", "ol", "li",
    "input", "a", "span", "img", "hr", "tbody", "small", "caption", "strong",
    "thead", "big", "code", "chem",
})

# ...and to the HTML element that holds it. The tag names the box's ROLE on
# the page -- what a heading, a footnote, a formula *are* -- never what the
# box happens to say; two "Text" blocks with unrelated content still both get
# `<p>`. `Page-header` and `Page-footer` are page furniture rather than prose,
# not `<p>` with running text, and `ALLOWED_TAGS` has no `<header>`/`<footer>`
# to give them instead, so they get the generic block container, `<div>`.
# Every label in `PAGE_LABELS` has an entry here now, so nothing falls through
# to the `.get(..., "p")` fallback below by accident.
HTML_TAG = {
    "Title": "h1",
    "Section-header": "h2",
    "Caption": "caption",
    "Footnote": "small",
    "Formula": "math",
    "List-item": "li",
    "Page-header": "div",
    "Page-footer": "div",
    "Picture": "div",
    "Table": "table",
    "Text": "p",
}

# ---------------------------------------------------------- docsynth labels
#
# `word_annotations`/`layout_annotations` (below `boxes`/`blocks_from_boxes`)
# write `layout_class` in a SECOND, wider vocabulary -- `docsynth.
# annotations.v1`'s 19 labels, fixed by what reads those two arrays, not by
# this repository. Kept separate from `PAGE_LABELS`/`LABELS` above rather
# than replacing them: those two already carry a lot of judgment about which
# `kind` prefix wins and where -- the periodical family alone maps 65 of
# them -- and redoing that BY HAND against a different vocabulary would be
# throwing that judgment away to re-derive it, not improving it. Translating
# the label `label_for` already computes is cheaper and just as faithful:
# every existing reader of `label_for`/`blocks[]` sees no change at all.
DOCSYNTH_LABELS = frozenset({
    "Caption", "Footnote", "Formula", "List-Group", "Page-Header",
    "Page-Footer", "Image", "Section-Header", "Table", "Text", "Title",
    "Complex-Block", "Code-Block", "Form", "Table-Of-Contents", "Figure",
    "Diagram", "Bibliography", "Blank-Page",
    # MỰC PHỦ, không phải nội dung. Chữ chìm và con dấu nằm ĐÈ lên trang: chúng
    # có toạ độ, có chữ đọc được, nhưng không thuộc mạch nội dung tài liệu.
    # Gộp chúng vào `Text` và `Image` là bảo người huấn luyện rằng "BẢN SAO"
    # xoay 25 độ là một đoạn văn, và con dấu đỏ là một bức ảnh minh hoạ.
    #
    # Tách ra thì lọc được: ai muốn huấn luyện đọc nội dung thì bỏ hai nhãn
    # này, ai muốn huấn luyện phát hiện dấu thì giữ đúng chúng. Một nhãn gộp
    # không cho ai lựa chọn nào cả.
    "Watermark", "Stamp",
})

# kind prefix -> `docsynth.annotations.v1` label, DIRECTLY -- not through
# `label_for`/`PAGE_LABELS`. That two-hop version (kind -> old 11-label ->
# new 19-label) was cheaper to write, but it can only ever hand back
# whichever of the 19 the OLD label happened to translate to, one per old
# label, even when a `kind` deserves a more specific one the eleven-label
# vocabulary had no slot for -- a magazine's `entry.` (its table of
# contents) is `List-item` there and would translate to the generic
# `List-Group`, when the vocabulary has an exact name for what it is:
# `Table-Of-Contents`. This table is seeded from the same prefixes `LABELS`
# already carries -- the judgment about which KIND belongs to which GROUP is
# not redone -- with the target chosen against the 19 directly, prefix by
# prefix, instead of inherited from a different vocabulary's answer.
#
# Same rule as `LABELS`: longest prefix wins. A `kind` this does not cover
# reads as `Text`, `layout_class_for`'s own default -- most of what a
# Vietnamese business document says IS running text, and the nine labels
# actually used below (`Caption`, `Image`, `Page-Footer`, `Page-Header`,
# `Section-Header`, `Table`, `Table-Of-Contents`, `Text`, `Title`) are what
# this repository's content actually is; the other ten (`Formula`,
# `Bibliography`, ...) name things no layout here draws, and forcing a
# `kind` onto one of them would be a label lying about the page, not a use
# of the vocabulary's breadth.
DOCSYNTH_LABEL_FOR_KIND: dict[str, str] = {
    # `section.body` là VĂN XUÔI của một mục, không phải tiêu đề của nó. Tiền
    # tố `section.` một mình đưa cả ba `data-kind` về `Section-Header`, và một
    # đoạn bốn dòng mang nhãn tiêu đề mục là một nhãn nói sai. Tiền tố DÀI HƠN
    # thắng, nên dòng này là đủ.
    "section.body": "Text",
    # The document's own title is its own label, distinct from the page's
    # running header: it reads once per page, largest type, and a
    # layout-detection model loses a real signal if that is folded into
    # `Page-Header` the way it used to be here.
    "title": "Title",
    # Dòng phụ dưới tiêu đề: "Số: ..../GUQ", "Mẫu số: 01/BV", "Bộ phận: ....".
    # Là chữ chạy, không phải tiêu đề mục -- xét theo NGHĨA chứ không theo
    # chỗ nó đứng. `generators/html/sheets/` cũng xếp `subtitle` cùng nhóm
    # với `serial`, `form_no`, `period`, tức là cùng một loại dòng.
    # Tiêu đề bảng ("BẢNG KÊ CHI TIẾT") là chuyện khác, và có `kind` riêng
    # là `caption.table`.
    "subtitle": "Text",
    "caption.table": "Section-Header",
    "parties.title": "Section-Header",
    # Only the org's own name is PAGE-HEADER material -- the running
    # identification a reader expects there, terse and repeated on every
    # page of this business regardless of which document it is. Everything
    # else under `store.*` (branch, address, tax code, phone, bank account,
    # website) is substantive contact/legal/bank DATA a downstream reader
    # extracts precisely, the same kind of content `invoice.field`/
    # `parties.*` carry for the other party on the same page -- and those
    # already read as `Text` below. Left as a blanket `"store.":
    # "Page-Header"`, every one of those detail fields inherited the label
    # too, so a header box built from a company's letterhead block ran five
    # lines tall and carried its tax code and bank account number, while the
    # identical fields for the OTHER party on the same page (typed through
    # `invoice.field` instead of `store.*`) correctly read as `Text` -- the
    # same content, labelled two different ways only because of which side
    # of the transaction printed it.
    "store.name": "Page-Header",
    "store.": "Text",
    "invoice.subtitle": "Section-Header",
    "invoice.": "Text",
    # Số mã vạch in DƯỚI mã vạch, không phải một ô bảng. Tiền tố dài hơn
    # thắng, nên dòng này lấy lại đúng một `kind` khỏi họ `menu.` -- mọi cột
    # hàng khác vẫn là `Table`.
    "menu.barcode": "Text",
    "menu.": "Table",
    "colhdr": "Table",
    "colnum": "Table",
    # Cùng lý do với `LABELS` ở trên: khối tổng dựng bằng `<div>` không phải
    # một cái bảng, và `regions_from_words` mới là chỗ biết một từ có nằm
    # trong `<td>` hay không.
    "total.": "Text",
    "summary.": "Text",
    "period": "Text",
    "meta": "Text",
    "note": "Text",
    # KHỐI CHỮ KÝ LÀ CHỮ, KHÔNG PHẢI BIỂU MẪU.
    #
    # Bản trước gán `Form`, lý lẽ là "dòng chữ ký là một ô người ký điền vào".
    # Nhưng thứ ĐƯỢC ĐO ở đây là chữ ĐÃ IN: "GIÁM ĐỐC", "(Ký, ghi rõ họ tên)",
    # và tên người ký. Không ô nào, không dòng kẻ để điền, không cặp nhãn-giá
    # trị -- chỉ mấy dòng chữ căn giữa dưới đáy trang, đúng như mọi giấy tờ
    # Việt Nam in ra.
    #
    # Và `LABELS`, bảng nhãn còn lại của chính file này, vẫn luôn nói `Text`
    # cho cùng tiền tố ấy. Hai bảng nói khác nhau về cùng một đoạn chữ là một
    # lỗi bất kể bên nào đúng; đây là chọn bên đúng.
    #
    # `sign.signedat` từng phải tách riêng để thoát khỏi `Form`. Giờ cả họ
    # `sign.` đã là `Text`, nên nó không cần đứng riêng nữa.
    # Dòng "nơi, ngày tháng năm" in trên khối chữ ký KHÔNG phải một ô biểu
    # mẫu -- nó là một câu chữ chạy, và người đọc không điền gì vào đó. Tiền tố
    # dài hơn thắng, nên chỉ riêng nó ra khỏi họ `sign.`.
    # Bảng câu hỏi: câu hỏi đánh số, ô tích, dòng kẻ để điền. Cả khối LÀ
    # một biểu mẫu -- người đọc điền vào nó -- nên `Form`, không phải chữ
    # chạy. Ô tích và nhãn của nó là hai run riêng, mỗi cái một hộp.
    # Sáu khối không-phải-bảng, thêm cùng lúc. Nhãn VÙNG của chúng do
    # `data-region` khai thẳng trong markup; bảng này lo nhãn của từng
    # đoạn chữ bên trong, và chúng đều là chữ chạy.
    "legal.basis": "Text",
    "clause.": "Text",
    "formula": "Text",
    "caption.figure": "Caption",
    "footnote": "Footnote",
    "toc.": "Text",
    "survey.": "Form",
    "sign.": "Text",
    # `Page-Footer` dành cho thứ THẬT SỰ ở chân trang -- số trang. Dòng ghi
    # chú cuối tờ ("Công ty chỉ trả sau khi đối chiếu chữ ký...") là một
    # câu của chứng từ, tình cờ in ở dưới; xét theo nghĩa thì nó là chữ
    # chạy. Tiền tố dài hơn thắng, nên `footer.page` vẫn là chân trang.
    "footer.page": "Page-Footer",
    "footer": "Text",
    "cell": "Table",
    "seal.": "Image",
    # A blank placeholder box standing in for a photo the renderer never
    # actually draws (a portrait for an ID, a product shot) -- its own
    # caption ("ẢNH", "4x6") is the one word this repository ever prints
    # inside that box, so it is what marks the region as `Image` rather than
    # `Text`; nothing else about the box is `span()`-worthy on its own.
    # Ô dán ảnh: một khung rỗng có in chữ "ẢNH" và "4 x 6". KHÔNG có tấm
    # ảnh nào trong đó -- chỉ có chữ và một đường viền -- nên gọi nó là
    # ảnh là dạy một bộ nhận dạng rằng khung rỗng có chữ là ảnh.
    "photo.": "Text",
    "parties.": "Text",
    # Quốc hiệu và tiêu ngữ ("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM" /
    # "Độc lập - Tự do - Hạnh phúc"). Là chữ chạy, không phải tiêu đề của
    # tờ giấy: mọi công văn đều in đúng hai dòng ấy, nên chúng không nói
    # tờ này là giấy gì. Gọi là `Title` thì một trang có HAI `Title` và
    # không cái nào là tên chứng từ. Hai bảng dưới đây còn từng nói hai
    # chuyện khác nhau về cùng một `kind`: `Title` ở bảng này,
    # `Section-Header` ở bảng kia.
    # Chữ chìm ("BẢN SAO", "HOÁ ĐƠN MẪU"): mờ và xoay, nhưng vẫn là chữ in
    # ra và vẫn đọc được, nên nó là `Text` chứ không phải một tấm ảnh.
    "watermark": "Watermark",
    "masthead": "Text",
    "issue_": "Page-Header",
    "slogan": "Page-Header",
    "price": "Page-Header",
    "website": "Page-Footer",
    "hotline": "Page-Footer",
    "page_no": "Page-Footer",
    "headline": "Section-Header",
    "hero.headline": "Section-Header",
    "hero.kicker": "Section-Header",
    "hero.": "Text",
    "kicker": "Section-Header",
    "deck": "Section-Header",
    "dateline": "Text",
    "byline": "Text",
    "body": "Text",
    "jump": "Text",
    "pull_quote": "Text",
    "caption": "Caption",
    "bottom.headline": "Section-Header",
    "bottom.caption": "Caption",
    "bottom.": "Text",
    "teaser.kicker": "Section-Header",
    "teaser.headline": "Section-Header",
    "teaser.": "Text",
    "section": "Section-Header",
    "category": "Section-Header",
    # A lettered/numbered heading that introduces one block of a page's own
    # body ("A. Thông tin dự án", "I. Bên mua bảo hiểm...") -- a different
    # thing from `section` above, which names a magazine's editorial
    # category, not a heading's own text.
    "subhead": "Section-Header",
    # The one direct improvement over the two-hop version: a real table of
    # contents, not a generic list.
    "entry.": "Table-Of-Contents",
    "qa.question": "Section-Header",
    "qa.answer": "Text",
    "subject_": "Text",
    "bio_title": "Section-Header",
    "bio.": "Text",
    "sidebar.title": "Section-Header",
    "sidebar.": "Text",
    "ad.heading": "Section-Header",
    "ad.": "Text",
    "notice.title": "Section-Header",
    "notice.": "Text",
    "obit.title": "Section-Header",
    "obit.": "Text",
    "condolence": "Text",
    "rate": "Text",
}


# ---------------------------------------------------------------- KHỐI -> VÙNG
#
# Một SECTION của phôi được phép mang nhãn vùng nào. Bảng này không khai lại
# nhãn -- nó chỉ nói section ấy in ra họ `data-kind` nào, rồi tra ngược
# `DOCSYNTH_LABEL_FOR_KIND` ở trên. Nhờ thế đổi nhãn của một họ kind là cổng
# đi theo, không phải nhớ sửa hai chỗ.
#
# Vì sao có bảng này, bằng một ca thật: `rulebase/layouts/
# gen_dispatch_letter_02.compose.json` khai `{"section": "signatures",
# "region": "Form"}`, trong khi bảng trên đã chốt `sign.` là `Text` và viết
# hẳn lý do ("KHỐI CHỮ KÝ LÀ CHỮ, KHÔNG PHẢI BIỂU MẪU"). Một luật đúng mà chỉ
# một chỗ biết thì chỗ kia vẫn sinh ra dữ liệu sai -- và chỗ kia là một model,
# nên sửa tay file ấy chỉ đúng tới lần sinh sau.
#
# Chỉ khai section nào có họ kind RÕ RÀNG. `footer` in cả chữ chạy lẫn số
# trang nên không khai; khai bừa là dựng một cổng chặn nhầm thứ đúng.
SECTION_KIND: dict[str, str] = {
    "signatures": "sign.",
    "table": "cell",
    "totals": "cell",
}


def region_for_section(section: str) -> str | None:
    """Nhãn vùng đúng cho `section`, hoặc None khi bảng không nói gì."""
    kind = SECTION_KIND.get(str(section or "").strip())
    return DOCSYNTH_LABEL_FOR_KIND.get(kind) if kind else None


def region_conflict(section: str, region: str) -> str | None:
    """Câu giải thích khi `section` không được mang `region`, hoặc None.

    Trả về CÂU chứ không phải bool: cổng gọi nó in thẳng ra cho model đọc, và
    "sai" không dạy được gì, "chữ ký là chữ chạy, không phải biểu mẫu" thì
    có."""
    want = region_for_section(section)
    if not want or not region or region == want:
        return None
    return (f'khối `{section}` khai `region="{region}"` mà `data-kind` của nó '
            f'({SECTION_KIND[section]}...) là `{want}` -- xem bảng '
            f'`DOCSYNTH_LABEL_FOR_KIND` trong pipeline/record.py')



def layout_class_for(kind: str) -> str:
    """The `docsynth.annotations.v1` label for one of this repository's field
    kinds, chosen directly against the 19-label vocabulary -- see
    `DOCSYNTH_LABEL_FOR_KIND`'s own comment for why not through `label_for`.
    """
    kind = str(kind or "")
    best = ""
    for prefix in DOCSYNTH_LABEL_FOR_KIND:
        if (kind == prefix or kind.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return DOCSYNTH_LABEL_FOR_KIND[best] if best else "Text"

# ------------------------------------------------------------------- settings

# The converter's job options, given the values that are true of a drawn page.
# Spelled out rather than left empty because a consumer that reads `settings`
# reads it on every record, and a missing key there is the same bug as a missing
# key anywhere else. `convert_mode` and `extract_fields` are filled in per page
# by `build` -- they name the renderer that drew it and the label it carries, and
# both differ page to page. The rest are constants and each one is a statement
# about the generator:
#
#   end2end             False -- the label comes from the rule-base, not a model
#   skip_preprocess     True  -- there is nothing to deskew, the page is drawn
#   keep_header_footer  True  -- the label carries them, so they are not dropped
#   convert_mode        the renderer, same value as `parser`
#   retry_repeat        False -- a page is drawn once; a repeat is a bug
#   max_pixels          null -- no cap: the page was drawn at the size it is,
#                       not resized to fit one. Its size is in `pages[0]`
#   segment_document_mode  "single" -- one image, one page, no segmentation
#   segment_output_format  "standard"
#   target_language     Vietnamese; the corpus is, including the folded layouts
#   translate_source    "synthetic" -- not scanned, and saying so matters
BASE_SETTINGS: dict[str, Any] = {
    "end2end": False,
    "skip_preprocess": True,
    "keep_header_footer": True,
    "convert_mode": "",
    "retry_repeat": False,
    "max_pixels": None,
    "segment_document_mode": "single",
    "segment_output_format": "standard",
    "target_language": "Vietnamese",
    "translate_source": "synthetic",
    "extract_fields": [],
}

# The two above that `build` fills in per page. Naming them once means `validate`
# and `refresh` cannot disagree about which options are allowed to differ between
# two records of the same set.
PER_PAGE_SETTINGS = ("convert_mode", "extract_fields")

# Top level, in the order the converter writes them. `json.dump` keeps insertion
# order, so a record built here reads down the page the way the sample does.
ORDER = ("schema_version", "job_id", "task", "parser", "filename", "source_files",
         "settings", "documents", "pages", "blocks", "word_annotations",
         "entity_annotations",
         "layout_annotations", "kie", "markdown", "html", "extracted")

# Every key, and there is no second set: a line has these and nothing else, so
# a record that grew one is as wrong as a record that lost one. That is checked
# rather than described -- see `validate`.
REQUIRED = frozenset(ORDER)


class RecordError(ValueError):
    """A metadata line is not what a loader will expect."""


def label_for(kind: str) -> str:
    """The converter's layout label for one of this repository's field kinds."""
    kind = str(kind or "")
    best = ""
    for prefix in LABELS:
        if (kind == prefix or kind.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return LABELS[best] if best else DEFAULT_LABEL


def job_id(parser: str, layout: str, seed: Any, filename: str) -> str:
    """A stable id for the conversion job that produced this page.

    Four things decide it, and all four are recoverable from the record: which
    renderer drew it, from which layout, at which seed, into which file. Two
    runs of the same plan give the same ids, which is what lets
    `tools/baseline.py` compare metadata lines at all; two pages in one dataset
    cannot collide, because the file name is in there and a directory holds one
    of each.
    """
    return str(uuid.uuid5(JOB_NAMESPACE, f"{parser}|{layout}|{seed}|{filename}"))


# --------------------------------------------------------------------- blocks


# ------------------------------------------------------- HỆ TOẠ ĐỘ 0..1000
#
# Mọi `bbox`/`polygon` trong bản ghi là PHẦN NGHÌN của cạnh tờ giấy, không
# phải pixel. Pixel vẫn còn, ở `bbox_px`/`polygon_px`.
#
# Vì sao đổi chiều ấy chứ không thêm một trường thứ ba: thứ người đọc bản ghi
# dùng để huấn luyện là hệ chuẩn hoá -- một hộp ở pixel chỉ có nghĩa khi kèm
# kích thước ảnh, và `--scale`, phép thu nhỏ theo `short_size`, rồi phép làm
# cũ đều đổi kích thước ấy. `synthgen/export.py` đã xuất hệ 1000 từ lâu
# (`bbox_unit: per_mille_of_size`), nên trước thay đổi này một kho có HAI hệ
# toạ độ: bản ghi theo pixel, bản xuất theo phần nghìn.
#
# Pixel KHÔNG bỏ được: `synthgen/overlay.py` vẽ hộp đè lên ảnh và
# `synthgen/augment.py` chiếu lại từng góc khi làm cong giấy -- cả hai cần
# pixel thật. Nên đổi tên chứ không xoá, và đổi ở ĐÚNG MỘT CHỖ: phép gom
# vùng, phép đo khoảng hở, phép xét kề nhau bên dưới đều tính bằng pixel và
# phải giữ nguyên như thế. Chuyển sớm hơn là bắt chúng tính trên số đã làm
# tròn hai lần.
GRID = 1000


def _per_mille(value: float, size: float) -> int:
    """Một toạ độ pixel -> hệ 0..1000, cắt vào khoảng.

    Cắt chứ không để tràn, cùng lẽ `synthgen/export.py::to_grid`: một hộp lệch
    ra ngoài mép giấy vài pixel vì làm tròn là chuyện có thật, còn một toạ độ
    1003 trong hệ 1000 thì mọi thứ đọc nó đều phải tự đoán có nên tin không."""
    if size <= 0:
        return 0
    return max(0, min(GRID, int(round(float(value) / float(size) * GRID))))


def to_per_mille(node: Any, width: float, height: float) -> Any:
    """Đổi mọi `bbox`/`polygon` trong `node` sang hệ 1000, giữ pixel ở `*_px`.

    Đi ĐỆ QUY trên chính cấu trúc đã lắp xong chứ không sửa từng chỗ ghi hộp:
    bản ghi có bốn tầng hạt (`blocks`, `word_annotations`,
    `entity_annotations`, `layout_annotations`) cộng các hộp lồng trong `kie`,
    và một danh sách chỗ-phải-sửa viết tay thì sót đúng cái tầng vừa thêm.

    `bbox` có hai dạng trong file này -- danh sách `[x1,y1,x2,y2]` và dict
    `{x1..y2}` -- nên cả hai đều phải đọc được. Dạng nào vào thì dạng ấy ra.
    """
    if isinstance(node, list):
        return [to_per_mille(item, width, height) for item in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        # Theo HẬU TỐ, không theo danh sách tên: bản ghi mang `bbox`,
        # `polygon`, `key_bbox`, `value_bbox`, và cặp KIE còn thêm tên nữa.
        # Một danh sách tên viết tay sót đúng cái tên vừa thêm, và sót ở đây
        # nghĩa là một trường lẻ loi mang pixel giữa một bản ghi phần nghìn.
        is_box = key == "bbox" or key.endswith("_bbox")
        # `quad` là bốn góc đo được, cùng hình dạng `polygon`. `lines` là một
        # DANH SÁCH hộp -- mỗi dòng của một thực thể nhiều dòng.
        #
        # Hai khoá này không theo hậu tố nào nên phải gọi tên, và cả hai đều
        # đã lọt bản đầu: đo trên một trang thật, `entity.lines[0]` bằng đúng
        # `entity.bbox_px` trong khi `entity.bbox` đã là phần nghìn. Một bản
        # ghi mang hai hệ toạ độ không báo lỗi -- nó chỉ dạy sai.
        is_poly = key in ("polygon", "quad") or key.endswith("_polygon")
        if key == "lines" and isinstance(value, (list, tuple)) and value and all(
                isinstance(v, (list, tuple)) and len(v) == 4 for v in value):
            out["lines_px"] = [[float(c) for c in line] for line in value]
            out[key] = [[_per_mille(line[0], width), _per_mille(line[1], height),
                         _per_mille(line[2], width), _per_mille(line[3], height)]
                        for line in value]
            continue
        if is_box and isinstance(value, (list, tuple)) and len(value) == 4:
            out[f"{key}_px"] = [float(v) for v in value]
            out[key] = [_per_mille(value[0], width), _per_mille(value[1], height),
                        _per_mille(value[2], width), _per_mille(value[3], height)]
        elif is_box and isinstance(value, dict) and "x1" in value:
            out[f"{key}_px"] = dict(value)
            out[key] = {"x1": _per_mille(value["x1"], width),
                        "y1": _per_mille(value["y1"], height),
                        "x2": _per_mille(value["x2"], width),
                        "y2": _per_mille(value["y2"], height)}
        elif is_poly and isinstance(value, (list, tuple)) and value:
            out[f"{key}_px"] = [[float(x), float(y)] for x, y in value]
            out[key] = [[_per_mille(x, width), _per_mille(y, height)]
                        for x, y in value]
        elif key == "bbox_mode":
            out[key] = "xyxy_per_mille"
        else:
            out[key] = to_per_mille(value, width, height)
    return out


def bbox_of(quad: Any) -> dict[str, int]:
    """The axis-aligned box around a quad, which may not be axis-aligned.

    Rounded to whole pixels, as the converter writes them. The quad itself stays
    on the block: this is a summary of it, not a replacement, and a page the
    glyph backend curled has quads no bbox describes.
    """
    xs, ys = [], []
    for corner in quad or []:
        try:
            xs.append(float(corner[0]))
            ys.append(float(corner[1]))
        except (TypeError, ValueError, IndexError):
            continue
    if not xs or not ys:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    return {"x1": int(round(min(xs))), "y1": int(round(min(ys))),
            "x2": int(round(max(xs))), "y2": int(round(max(ys)))}


def block_content(label: str, text: str) -> str:
    """One block as markdown: a heading is marked as one, everything else stands."""
    text = str(text or "").strip()
    return MARKDOWN_PREFIX.get(label, "") + text if text else ""


# ---------------------------------------------------------------- axis 3: ink

# **How the mark got onto the paper**, and the third of the three axes
# `agent/prompts/regions.md` defines: a run IS a region (axis 1,
# `layout_class`), it DOES a role (axis 2, `field_role`), and it was PUT THERE
# somehow -- which is this.
#
# The repository had the first two and not the third, so a reader could tell a
# heading from a table cell and a key from a value, and could not tell printed
# text from a stamp impression or from something a person wrote by hand. That
# distinction is the whole reason `generators/html/handwriting.py` and
# `signature.py` exist, and it was reaching the dataset only as pixels.
#
# Six values, from that document. Fixed by what reads these records, the same
# way `DOCSYNTH_LABELS` is.
INK_VALUES = frozenset({"print", "hand", "stamp", "dotmatrix", "thermal",
                        "reversed"})

# `kind` prefix -> ink, for the marks the renderer does not have to say
# anything about because their kind already does. Longest prefix wins, same
# convention as `LABELS`.
INK_FOR_KIND: dict[str, str] = {
    # A seal impression is `seal_mark`'s own doing and always a stamp; the
    # renderer marks it too (`data-ink`), and this is the belt to that braces
    # -- a record built from a set drawn before that attribute existed still
    # gets it right.
    "seal.": "stamp",
}


def ink_for(kind: str, explicit: str = "", default: str = "print") -> str:
    """Which of `INK_VALUES` this run was laid down with.

    Three sources, in the order of how much each one knows:

    1. **what the renderer said** (`data-ink` on the span). It is the only one
       that can know a run is handwritten or reversed out of a dark band,
       because both are decided while drawing and leave no trace in `kind`.
    2. **what the kind says** -- a `seal.` run is a stamp whatever else is true.
    3. **the page's own default**, from the recipe: a thermal roll prints
       every run thermally, a dot-matrix invoice every run as dots.

    An unknown value from (1) is dropped rather than trusted: the vocabulary is
    closed, and a typo in a family module must not put a seventh ink in a
    dataset a consumer has six classes for.
    """
    if explicit in INK_VALUES:
        return explicit
    for prefix in sorted(INK_FOR_KIND, key=len, reverse=True):
        if kind.startswith(prefix):
            return INK_FOR_KIND[prefix]
    return default if default in INK_VALUES else "print"


# Axis 4 -- WHAT KIND OF WIDGET a run's value answers with. `presence`
# (signature/stamp) is deliberately not in this set: it is not a fact about
# one entity -- it aggregates a signature block with page-wide stamp
# existence -- and is synthesized once at export time instead, the same way
# `synthgen/export.py::_signatures()` already aggregates signature blocks
# today. See `docs/kie-schema-v3.md`.
ENTITY_FIELD_TYPES = frozenset({"text", "boolean_choice", "multi_choice",
                                "digit_sequence", "categorical_matrix",
                                "data_table"})

# `kind` prefix -> field_type, for widgets whose `kind` alone already tells
# them apart from everything else -- no separate tag needed. Longest prefix
# wins, same convention as `INK_FOR_KIND`.
#
# `survey.tick` here is a LONE tick with its own label
# (`sheets/form.py::_checklist`'s rows, `PAIRED`'s `survey.tick.label` entry
# in `synthgen/kie_full.py`) -- a single yes/no answer. A tick that is one
# option INSIDE a `survey.question` group (`synthgen/markup.py::_shape_rows`)
# never reaches this table: the group's own field_type, from `shape` below,
# wins for those, because the group surfaces as ONE field, not one per tick.
FIELD_TYPE_FOR_KIND: dict[str, str] = {
    "survey.tick": "boolean_choice",
    "survey.char": "digit_sequence",
}

# `shape` (`synthgen/markup.py::_shape_rows`'s own `item["shape"]`) ->
# field_type, for the answer GROUP a `survey.question` anchors. Tagged onto
# the question's own span (the one entity every option/tick's
# `key_entity_index` already points back to) since the render step already
# knows this and none of it survives in `kind` -- a `yesno` question and an
# `options` question draw byte-identical `kind` patterns
# (`survey.tick`+`survey.option`) and differ only in whether more than one
# may be picked, which is authorial intent that leaves no trace in the ink.
FIELD_TYPE_FOR_SHAPE: dict[str, str] = {
    "yesno": "boolean_choice",
    "options": "multi_choice",
    "scale": "multi_choice",
    "attachment": "multi_choice",
    "boxchar": "digit_sequence",
    "date_boxes": "digit_sequence",
    "rank": "digit_sequence",
    "grid": "categorical_matrix",
    "table_form": "data_table",
}


def field_type_for(kind: str, shape: str = "", explicit: str = "") -> str:
    """Which of `ENTITY_FIELD_TYPES` this run's value answers with.

    Three sources, most specific first, same shape as `ink_for`:

    1. **what the page declares explicitly** (`explicit`, a future
       `data-field-type` override on the span) -- wins outright.
    2. **the question's own `shape`** (`FIELD_TYPE_FOR_SHAPE`) -- the one
       piece of render-time data this repository otherwise throws away
       before it reaches the DOM.
    3. **`kind`** (`FIELD_TYPE_FOR_KIND`) -- for widgets that need no
       separate tag because their `kind` alone is already unique to them.

    Falls back to `"text"`: nothing is lost by the default, since the box and
    the value are still there -- only the classification is generic. An
    unrecognised `shape`/`explicit` is dropped rather than trusted, same as
    `ink_for`'s closed vocabulary.
    """
    if explicit in ENTITY_FIELD_TYPES:
        return explicit
    if shape in FIELD_TYPE_FOR_SHAPE:
        return FIELD_TYPE_FOR_SHAPE[shape]
    for prefix in sorted(FIELD_TYPE_FOR_KIND, key=len, reverse=True):
        if kind.startswith(prefix):
            return FIELD_TYPE_FOR_KIND[prefix]
    return "text"



def blocks_from_boxes(boxes: Iterable[dict[str, Any]], *,
                      page_number: int = 1) -> list[dict[str, Any]]:
    """One block per drawn field, in the order the renderer drew them."""
    out: list[dict[str, Any]] = []
    for index, box in enumerate(boxes or []):
        if not isinstance(box, dict):
            continue
        kind = str(box.get("kind", ""))
        text = str(box.get("text", ""))
        label = label_for(kind)
        block = {
            "id": f"p{page_number}-b{index}",
            "page_number": page_number,
            "index_in_page": index,
            "label": label,
            "bbox": bbox_of(box.get("quad")),
            "content": block_content(label, text),
            # This repository's half of the block: which field it is, what it
            # says, and where its corners are before they were squared off.
            "kind": kind,
            "text": text,
            "quad": box.get("quad"),
        }
        out.append(block)
    return out


# A run whose `kind` ends in one of these is a CAPTION: it names the field
# printed beside it and holds no content of its own. Named once because three
# things read the convention -- the role guess below, the entity pairing in
# `entities_from_words`, and `pipeline.kie` -- and three copies of a suffix
# tuple is how they would come to disagree.
CAPTION_SUFFIXES = (".label", ".title")


def is_caption(kind: str) -> bool:
    """A run that names a field rather than holding one."""
    return str(kind or "").endswith(CAPTION_SUFFIXES)


def is_column_head(kind: str) -> bool:
    """A column heading -- a caption for a whole column instead of one field.

    Kept apart from `is_caption` because the two claim their values by
    different relations: a caption claims the run drawn next to it, and a
    column head claims the cells UNDER it, which adjacency cannot see.
    """
    kind = str(kind or "")
    return kind == "colhdr" or kind.startswith("colhdr.")


# MƯỜI BA VAI CẤU TRÚC — trục thứ hai của nhãn.
#
# `field_role` chỉ có hai giá trị, và đo được thì 96% số run mang `value` --
# một nhãn không nói gì. Bộ nhãn tham chiếu phân mười ba vai, và mỗi vai trả
# lời cùng một câu: *đoạn mực này LÀM GÌ trên tờ giấy*.
#
# Vì sao vai chứ không phải `kind`: `kind` nói NGÀNH (`menu.amount`,
# `store.tax_code`), nên một tờ giấy ngoài ngành hoá đơn không có tên nào
# đúng -- đúng bệnh đo được ở pilot12, tên học sinh mang `survey.prompt`. Vai
# nói CẤU TRÚC (`cell`, `value`, `heading`), và cấu trúc thì mọi tờ giấy đều
# có. NGHĨA của một `value` đến từ cái `key`/`colhdr` nó cặp với, in ngay trên
# giấy -- không từ bảng tra nào.
#
# Cả mười ba suy từ tín hiệu ĐÃ ĐO. Không thêm một phép đo nào.
RUN_ROLES = ("heading", "subheading", "body", "item", "key", "value", "total",
             "colhdr", "rowhdr", "cell", "caption", "note", "mark")


def run_role(kind: str, layout_class: str = "", *, in_table: bool = False,
             head_cell: bool = False, column: int | None = None,
             explicit: str = "") -> str:
    """Vai cấu trúc của một run. Một trong `RUN_ROLES`.

    Thứ tự xét đi từ tín hiệu CHẮC nhất tới tín hiệu suy đoán nhất: chỗ ngồi
    trong bảng biết chắc hơn `kind`, và `kind` biết chắc hơn nhãn vùng.

    `explicit` là câu trả lời của chính trang (`data-role` trên span) và nó
    thắng tất -- cùng lối `_word_field_role` vẫn làm."""
    if explicit in RUN_ROLES:
        return explicit
    name, label = str(kind or ""), str(layout_class or "")

    # 0. DÒNG TỔNG xét trước chỗ ngồi. Một hàng tổng nằm TRONG `<table>` vẫn
    # là dòng tổng -- và bản trước xét chỗ ngồi trước, nên mọi `total.*` in
    # thành `<tfoot><td>` đều mất vai `total`, thành `cell` hoặc `rowhdr`.
    # Đo trên pilot15: 33 thực thể, 1,3%.
    if not head_cell and str(kind or "").startswith(("total.", "summary.")):
        return "total"

    # 1. CHỖ NGỒI trong bảng. Trình duyệt đã dàn xong, không gì chắc hơn.
    if head_cell:
        return "colhdr"
    if in_table:
        # Cột 0 của thân bảng là cột số thứ tự -- nó ĐÁNH DẤU dòng, không mang
        # giá trị của dòng. Đó là `rowhdr`.
        return "rowhdr" if column == 0 else "cell"
    if name == "colhdr":
        return "colhdr"

    # 2. `kind`, khi nó nói về CẤU TRÚC chứ không về ngành.
    if name.startswith("total.") or name.startswith("summary."):
        return "total"
    if name.startswith("caption."):
        return "caption"
    if name in ("note", "footnote", "sign.note", "photo.size"):
        return "note"
    if name in ("watermark",) or label in ("Stamp", "Watermark", "Image"):
        return "mark"
    if name in ("title", "section", "masthead"):
        return "heading"
    if name in ("subtitle", "masthead.motto"):
        return "subheading"
    if name.startswith("clause.head") or name.startswith("toc.title"):
        return "item"
    if name.startswith(("clause.", "toc.", "legal.basis")):
        return "item"

    # 3. Nhãn VÙNG, tín hiệu thô nhất.
    if label in ("List-Group", "Table-Of-Contents", "Bibliography"):
        return "item"
    if _word_field_role(name) == "key":
        return "key"
    if label in ("Text", "Complex-Block", "Footnote"):
        return "body"
    return "value"


def _word_field_role(kind: str, explicit: str = "") -> str:
    """`"key"` for a field's own caption, `"unbound"` for page furniture that
    is not really a document field (a title, a footer line), `"value"` for
    everything else -- the three roles `docsynth.annotations.v1` uses.

    `explicit` is the renderer's own answer (`data-role` on the span), and it
    wins when it is one of the two roles a page can assert. Nothing writes it
    today; it exists so a composed page can state what the suffix convention
    below can only guess, and so that guess stays the answer for every page
    drawn by the ten families, which all follow it.

    `colhdr` (every `sheets/*.py` column heading -- "Đơn giá", "Nội dung")
    is a caption too, just for a whole column instead of one row's field:
    it names what the cells under it hold and holds no content itself, the
    same relationship a `.label` run has to its `.value` -- so it reads as
    `key`, not the fallthrough `value` it landed on before this line existed.

    **`unbound` survives here and not on an entity.** A word is classified for
    a reader of `word_annotations` alone, and "this is page furniture" is a
    true and useful thing to say there. `entities_from_words` then overrides
    it, because at entity level there IS an answer: a page title is the value
    of "which kind of document is this", printed with its caption left off.
    """
    if explicit in ("key", "value"):
        return explicit
    if is_caption(kind) or is_column_head(kind):
        return "key"
    if kind in ("title", "footer", "note") or kind.startswith(("footer", "note")):
        return "unbound"
    return "value"


def words_from_boxes(boxes: Iterable[dict[str, Any]],
                     ink: str = "print") -> list[dict[str, Any]]:
    """One `docsynth.annotations.v1` `word_annotations` entry per word --
    `boxes` here is `page.py::CELL_RECTS_JS`'s `words` array, already one
    entry per whitespace-separated word (or, for an inked run with no text
    node to split, one entry for the whole run -- see that function's own
    comment for why).

    `field_path`/`relation_path`/`field_pattern` all read the same as `kind`
    on purpose: `kind` already IS the dotted field path every `sheets/*.py`
    family writes (`"store.name"`, `"total.grand"`), so there is nothing this
    function would compute that `kind` does not already say -- three names
    for callers written against the target schema's own vocabulary, not
    three different derivations.
    """
    out: list[dict[str, Any]] = []
    for index, box in enumerate(boxes or []):
        if not isinstance(box, dict):
            continue
        kind = str(box.get("kind", ""))
        quad = box.get("quad")
        bbox = bbox_of(quad)
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        corners = [[float(x), float(y)] for x, y in quad] if quad and len(quad) == 4 \
            else [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        # Which labelled RUN this word came out of -- the tie that was missing.
        # `None` rather than `-1` off a backend with no DOM to index, same
        # convention as `layout_region_index` right below it.
        field = int(box.get("field", -1))
        out.append({
            "word_index": index,
            "text": str(box.get("text", "")),
            "layout_region_index": None,   # filled in by `regions_from_words`
            # Filled in for real by `entities_from_words`, which is also what
            # shifts it into whole-record numbering. Present here so a reader
            # of one page's words never meets a word without the key.
            "entity_index": field if field >= 0 else None,
            # Set from `kind` directly, not left null: a reader needs every
            # word classified into the 19-label vocabulary, not only the ones
            # that happened to land inside a named region -- `layout_class_for`
            # already knows what EVERY `kind` this repository writes means.
            "layout_class": layout_class_for(kind),
            "field_role": _word_field_role(kind),
            # TRỤC VAI CẤU TRÚC. `field_role` chỉ nói key hay không; `role` nói
            # đoạn mực này LÀM GÌ. Xem `run_role`.
            #
            # Bối cảnh bảng điền sau, ở `regions_from_words`, vì chỗ ngồi của
            # một ô chỉ biết được khi đã gom xong vùng bảng.
            "role": run_role(kind, layout_class_for(kind)),
            # Axis 3. See `ink_for`.
            "ink": ink_for(kind, str(box.get("ink", "")), ink),
            "field_path": kind,
            "relation_path": kind,
            "field_pattern": kind,
            "field_name": kind.rsplit(".", 1)[-1] if kind else "",
            "bbox": [x1, y1, x2, y2],
            "bbox_mode": "xyxy_pixel",
            # `visible_content_perimeter`, not `bbox`: `augmentation.warp`
            # (`degradation/warp.py` -- `paper_photo`'s displacement field or
            # a real Blender render) DOES re-project every box after it is
            # measured, moving each of the four corners independently, so a
            # warped page's `quad` is genuinely not a rectangle. `polygon`
            # below is that quad, closed into a ring; `bbox` stays the
            # axis-aligned summary `bbox_of` computes over the same corners,
            # for a reader that only wants "roughly where."
            "bbox_strategy": "visible_content_perimeter",
            "polygon": [*corners, corners[0]],
        })
    return out


# ------------------------------------------------------------------ entities
#
# One entry per labelled RUN, carrying the whole string.
#
# `blocks` cuts a run into lines and `word_annotations` cuts each line into
# words, so a field printed as "Công ty cổ phần TNHH A" reached a reader as
# five boxes with the same `field_path` and nothing saying they were one
# value. For OCR that is right -- a word box is what a detector is trained on.
# For KIE it is not: an extractor is asked for the field, and the field is the
# whole string.
#
# So this is the third grain, and it is DERIVED rather than measured. Its
# geometry comes from the words that survived the scale, the warp and the clip
# (`generators/html/render.py`), so it cannot disagree with them; only the
# text, the run index and the two optional attributes come from the browser
# (`page.py`'s `fields` array, which carries no geometry for exactly this
# reason).

# How much two boxes' vertical spans must overlap, as a share of the shorter,
# before they count as the same printed line. Generous on purpose: a line of
# mixed sizes (a unit after a number, a superscript) still reads as one line,
# and the alternative -- a fixed pixel tolerance -- breaks the moment the page
# is rendered at a different scale.
LINE_OVERLAP = 0.5


def _entity_lines(boxes: list[list[float]]) -> list[list[int]]:
    """`boxes` grouped into printed lines, each line one bounding box.

    A run that wrapped is several lines, and the union of them is NOT a box
    round the text -- it is a box round both lines and the blank paper between
    their ragged ends, which is the trap `page.py::CELL_RECTS_JS` already
    documents at two other grain sizes. So the entity keeps its lines.

    On a warped page a line's axis-aligned box is still larger than the ink in
    it (a sheared line's box always is). The exact ink is in each word's own
    `polygon`, which the warp re-projected corner by corner; this is the
    axis-aligned summary, and says so in `bbox_strategy`.
    """
    lines: list[dict[str, float]] = []
    for box in sorted(boxes, key=lambda b: (b[1], b[0])):
        x1, y1, x2, y2 = box
        for line in lines:
            overlap = min(line["y2"], y2) - max(line["y1"], y1)
            shorter = min(line["y2"] - line["y1"], y2 - y1)
            if shorter > 0 and overlap > LINE_OVERLAP * shorter:
                line["x1"] = min(line["x1"], x1)
                line["y1"] = min(line["y1"], y1)
                line["x2"] = max(line["x2"], x2)
                line["y2"] = max(line["y2"], y2)
                break
        else:
            lines.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
    return [[int(round(line["x1"])), int(round(line["y1"])),
             int(round(line["x2"])), int(round(line["y2"]))] for line in lines]


_HAS_VALUE = re.compile(r":\s*\S{2,}")


def _self_contained(text: str) -> bool:
    """Run này đã chứa cả nhãn lẫn giá trị của chính nó."""
    return bool(_HAS_VALUE.search(str(text or "")))


def _adjacent(key_box: Any, value_box: Any) -> bool:
    """Hai hộp có kề nhau như nhãn và giá trị trên giấy không.

    Hai thế đứng, và chỉ hai: giá trị NGAY BÊN PHẢI nhãn trên cùng một dòng,
    hoặc NGAY DƯỚI nhãn trong cùng một cột. Mọi thế khác là hai trường khác
    nhau tình cờ đứng cạnh nhau trong cây DOM.

    Đo bằng chiều cao chữ của chính cái nhãn, nên nó co giãn theo cỡ chữ mà
    không cần một con số điểm ảnh viết cứng."""
    try:
        kx1, ky1, kx2, ky2 = (float(v) for v in key_box)
        vx1, vy1, vx2, vy2 = (float(v) for v in value_box)
    except (TypeError, ValueError):
        return True                    # không đo được thì đừng chặn
    line = max(ky2 - ky1, 1.0)
    # Cùng dòng, bên phải: tâm dọc lệch dưới nửa dòng, và khe ngang không quá
    # tám lần chiều cao chữ -- xa hơn thế là sang cột khác của trang.
    same_row = (abs((ky1 + ky2) / 2 - (vy1 + vy2) / 2) < line * 0.6
                and vx1 >= kx2 - line * 0.5 and vx1 - kx2 < line * 8)
    # Ngay dưới, cùng cột: cách chưa tới một dòng rưỡi, và có chồng ngang.
    below = (0 <= vy1 - ky2 < line * 1.5
             and min(kx2, vx2) - max(kx1, vx1) > 0)
    return same_row or below


def entities_from_words(words: list[dict[str, Any]],
                        fields: Iterable[dict[str, Any]] = (),
                        *, layout: str = "") -> list[dict[str, Any]]:
    """One entity per run, and the words back-filled to point at it.

    `words` is `words_from_boxes`' output for ONE page and is MUTATED: each
    word's `field_role` is set from the entity it belongs to, so one record
    cannot say two things about the same mark. `fields` is `page.py`'s
    metadata array for the same page.

    **No entity is ever `unbound`.** A word can be -- "this is page furniture"
    is a true thing to say about a word. An entity has somewhere to put the
    answer instead: a page title is the value of "which kind of document is
    this", printed with its caption left off, so it becomes a `value` with a
    VIRTUAL key -- a field name and a description, and no box, because no
    caption was printed. That is what `key_source` records:

        printed   the caption drawn beside it, and `key_entity_index` points
                  at the entity for that caption
        declared  the renderer said so itself (`data-key` on the span)
        implied   neither: the name comes from the run's own `layout_class`,
                  which every run already has

    Returns [] when the backend measured no runs (the character grid), so a
    caller can stay one code path.
    """
    by_run: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        run = word.get("entity_index")
        if isinstance(run, int):
            by_run.setdefault(run, []).append(word)

    entities: list[dict[str, Any]] = []
    # RUN index -> ENTITY index. Two different numbering schemes, and the
    # difference is not cosmetic. A word carries the index of the RUN it came
    # out of (`page.py`'s `field`, which counts every labelled span in the
    # whole document, across every sheet); an entity carries its own position
    # in THIS PAGE's list. The two agree only on a first sheet where every
    # single run produced an entity -- and they stop agreeing the moment one
    # run is skipped (clipped off the paper, whitespace only) or the document
    # runs onto a second sheet, where the run counter carries on and the
    # entity list starts again at zero.
    #
    # Measured on the committed sets before this map existed: 300 of
    # `data/llm200_v3`'s `hospital_bill_002` words pointed past the end of its
    # own 385-entity list, and `form_roster_091` 90 of them. Every one of
    # those words claimed to belong to an entity that is not there.
    index_of_run: dict[int, int] = {}
    for entry in fields or ():
        if not isinstance(entry, dict):
            continue
        run = int(entry.get("field", -1))
        mine = by_run.get(run) or []
        if not mine:
            # Every word of this run was clipped off the paper, or the run
            # printed nothing but whitespace. Either way there is no ink to
            # point at, and an entity with no box is a label with no mark.
            continue
        kind = str(entry.get("kind", ""))
        boxes = [[float(value) for value in word["bbox"]] for word in mine]
        lines = _entity_lines(boxes)
        role = _word_field_role(kind, str(entry.get("role", "")))
        index_of_run[run] = len(entities)
        entities.append({
            "entity_index": len(entities),
            "text": str(entry.get("text", "")),
            "kind": kind,
            "layout_class": layout_class_for(kind),
            # `unbound` is resolved below, once the captions are known.
            "field_role": role,
            # VAI CẤU TRÚC, lấy từ chính những từ làm nên thực thể này.
            #
            # Không tính lại từ `kind`: các từ ĐÃ biết chỗ ngồi của mình trong
            # bảng (`colhdr`/`rowhdr`/`cell`), thứ `kind` không nói được. Mọi
            # từ của một run luôn cùng một vai, nên lấy vai của từ đầu là lấy
            # vai của cả run.
            "role": str(mine[0].get("role") or run_role(kind, layout_class_for(kind))),
            "ink": mine[0].get("ink", "print"),
            # Axis 4. `shape` is the answer-group's own render-time signal
            # (`synthgen/markup.py::_shape_rows`'s `item["shape"]`, tagged
            # onto the question span it anchors) -- see `field_type_for`.
            "field_type": field_type_for(kind, str(entry.get("shape") or "")),
            "word_indices": [int(word["word_index"]) for word in mine],
            "bbox": [min(box[0] for box in boxes), min(box[1] for box in boxes),
                     max(box[2] for box in boxes), max(box[3] for box in boxes)],
            "bbox_mode": "xyxy_pixel",
            "bbox_strategy": "visible_content_perimeter",
            "lines": lines,
            # Filled in by `_bind_entities` right below.
            "key_entity_index": None,
            "key_source": "",
            "field_name": "",
            "description": "",
            "description_source": "",
            "_declared_key": str(entry.get("key", "")),
        })

    _bind_entities(entities, layout=layout)

    # The words are re-pointed HERE, after `_bind_entities` has settled every
    # role, and through `index_of_run` rather than by assuming the two
    # numbering schemes line up. A word whose run produced no entity loses the
    # pointer rather than keeping a stale one: "this word belongs to no
    # entity" is a true thing to say about page furniture, and an index into
    # nothing is not.
    for word in words:
        run = word.get("entity_index")
        index = index_of_run.get(run) if isinstance(run, int) else None
        word["entity_index"] = index
        if index is not None:
            word["field_role"] = entities[index]["field_role"]
    return entities


def _bind_entities(entities: list[dict[str, Any]], *, layout: str = "") -> None:
    """Which key each value belongs to, what to call it, and what it means.

    Adjacency in draw order is the pairing rule, and `pipeline.kie`'s module
    docstring is where it is argued: every `sheets/*.py` call site writes a
    caption and its value into the same small piece of markup, back to back,
    so a caption claims the next run that is not itself a caption. What is new
    here is that it runs over ENTITIES, so a caption or a value that wrapped
    onto two lines is one thing rather than two -- on blocks, a wrapped
    caption paired its own second line with the value's first.

    A column head claims nothing: its values are the cells UNDER it, a
    relation adjacency cannot see, and pairing it with the next run would say
    "Đơn giá" captions the first item's name.
    """
    claimed: dict[int, int] = {}          # value entity -> key entity
    for position, entity in enumerate(entities):
        if entity["field_role"] != "key" or not is_caption(entity["kind"]):
            continue
        if not entity["text"].strip():
            continue
        # NHÃN ĐÃ TỰ CHỨA GIÁ TRỊ THÌ KHÔNG ĐI TÌM GIÁ TRỊ.
        #
        # "Số:" là một nhãn. "Số: 12/BB-HĐSP" là một dòng đã trọn nghĩa -- dấu
        # hai chấm có chữ theo sau, tức giá trị nằm ngay trong chính run ấy.
        # Bản trước vẫn cho nó đi tìm, và nó vớ lấy run kế tiếp: đo được trên
        # `data/test1`, `so_12_bb_hdsp` nhận value "TP. Hồ Chí Minh, ngày 25
        # tháng 6 năm 2024" -- một trường khác nằm bên phải cùng dòng.
        #
        # Xét DẤU CÂU chứ không xét nghĩa: "Người mua:" kết thúc bằng hai chấm
        # và không có gì sau, nên nó vẫn là nhãn đi tìm giá trị.
        if _self_contained(entity["text"]):
            continue
        for other in entities[position + 1:]:
            if other["field_role"] == "key":
                break                      # two captions running: no value here
            if not other["text"].strip():
                continue
            # PHẢI KỀ NHAU TRÊN GIẤY, không chỉ kề nhau trong cây DOM.
            #
            # Thứ tự DOM một mình nói "cái tiếp theo", và cái tiếp theo có thể
            # nằm ở cột bên kia trang hay dòng dưới thuộc khối khác -- đo được:
            # `ha_noi_ngay_15_thang_5_nam_2025` nhận value "Kính gửi: Hội đồng
            # Quản trị", một dòng khác hẳn. Giấy thật đặt giá trị NGAY BÊN PHẢI
            # nhãn trên cùng dòng, hoặc NGAY DƯỚI nhãn trong cùng cột.
            if not _adjacent(entity.get("bbox"), other.get("bbox")):
                break
            if other["entity_index"] not in claimed:
                claimed[other["entity_index"]] = entity["entity_index"]
            break

    used: dict[str, int] = {}

    def _unique(base: str) -> str:
        used[base] = used.get(base, 0) + 1
        return base if used[base] == 1 else f"{base}_{used[base]}"

    # A caption and the value it captions are ONE field with two boxes, so
    # they get ONE name -- naming them separately made "Người mua:" the field
    # `nguoi_mua` and its own value `nguoi_mua_2`, which reads as two
    # different fields that happen to be spelled alike. Allocated in document
    # order so a caption repeated down a page gets `_2`, `_3` in the order it
    # was printed, which is the rule `pipeline.kie.pair_fields` has always
    # used and the one a reader can follow down the paper.
    value_of = {key: value for value, key in claimed.items()}
    for entity in entities:
        if entity["field_name"]:
            continue
        index = entity["entity_index"]
        declared = entity.get("_declared_key") or ""
        if entity["field_role"] == "key":
            name = _unique(kie.slug(entity["text"]))
            entity["field_name"], entity["key_source"] = name, "printed"
            partner = value_of.get(index)
            if partner is not None:
                mate = entities[partner]
                mate["field_name"], mate["key_source"] = name, "printed"
                mate["field_role"] = "value"
                mate["key_entity_index"] = index
        elif index in claimed:
            # Its caption comes later in the list only if the page drew the
            # value first, which no family does; handled anyway so the name is
            # never left empty.
            key_index = claimed[index]
            name = _unique(kie.slug(entities[key_index]["text"]))
            entity["field_name"] = entities[key_index]["field_name"] = name
            entity["key_source"] = entities[key_index]["key_source"] = "printed"
            entity["field_role"], entity["key_entity_index"] = "value", key_index
        elif declared:
            entity["field_role"] = "value"
            entity["field_name"] = _unique(kie.slug(declared))
            entity["key_source"] = "declared"
        else:
            # The virtual key. `kind` first, because it IS the dotted field
            # path every `sheets/*.py` family writes and it is specific --
            # `item.name` names the field, where the 19-label class only says
            # `Text` and would number every unnamed run on the page `text_2`,
            # `text_3`. The class is the floor for a run whose kind is empty,
            # so this can neither need a per-kind table nor come out blank.
            entity["field_role"] = "value"
            entity["field_name"] = _unique(
                kie.slug(entity["kind"] or entity["layout_class"]))
            entity["key_source"] = "implied"

    for entity in entities:
        entity.pop("_declared_key", None)
        key_index = entity["key_entity_index"]
        # A caption describes ITSELF with its own printed text -- it is the
        # name of the field, so "Người mua" is exactly what it means. A value
        # is described by the caption that claims it, and by its own `kind`
        # when none was printed.
        caption = (entity["text"] if entity["field_role"] == "key"
                   else (entities[key_index]["text"] if key_index is not None else ""))
        entity["description"], entity["description_source"] = kie.describe(
            entity["field_name"], caption=caption, kind=entity["kind"],
            layout_class=entity["layout_class"], layout=layout)

# Added to every region's word-derived bbox -- a region is a BLOCK a reader
# would point at ("the header", "the signature line"), and a box drawn exactly
# to the ink inside it reads as a crop, not the block. Small and fixed rather
# than proportional to the page: the point is "this box has the breathing room
# a component has," not a second wear knob.
REGION_PAD_PX = 6

# What a graphic region is called. `Image` rather than `Picture` because
# `layout_annotations` speaks `DOCSYNTH_LABELS`, and the two vocabularies spell
# the same idea differently -- `PAGE_LABELS`, which `blocks` speaks, calls it
# `Picture`. A graphic gets a region and NOT a block, and that distinction is
# the point: a block promises a reader some text to read, and a logo has none.
GRAPHIC_LABEL = "Image"

# Mực-không-chữ nào là CON DẤU. `GRAPHIC_RECTS_JS` đã trả về `kind` của mỗi
# hình -- `el.dataset.graphic`, tức `data-graphic="seal"` mà `synthgen/markup.py`
# đặt lên chính `<img>` con dấu -- nhưng bản trước vứt nó đi và gán `Image` cho
# tất cả. Nên con dấu đỏ, mã vạch, QR và sơ đồ cùng một nhãn, và không ai lọc
# nổi cái nào ra khỏi cái nào.
STAMP_GRAPHICS = frozenset({"seal", "stamp", "dau", "seal_round", "seal_square"})
STAMP_LABEL = "Stamp"

# Mực-không-chữ nào là SƠ ĐỒ, và vì sao nó không phải `Image`.
#
# `Figure` trong từ vựng nhãn bố cục là một hình CÓ CHÚ THÍCH -- cặp
# `Figure`/`Caption` mà mọi bộ nhãn đều có. `Image` là một mảng mực không hứa
# gì với người đọc: logo, hoa văn, nền.
#
# Đo được vì sao phải phân biệt: `synthgen/markup.py::_figure` in ra `<div
# class="fig" data-region="Figure" data-graphic="diagram">` cùng một câu chú
# thích bên dưới. Vùng `Figure` khai tay thì bị luật "khung rỗng thì bỏ" loại
# (hình SVG không có từ nào bên trong), còn `data-graphic` gán nó thành
# `Image` -- nên bộ dữ liệu ra `Caption` 8% số trang mà `Figure` 0%: một câu
# chú thích không chú thích cho cái gì. So với pilot LLM: `Figure` 27%.
DIAGRAM_GRAPHICS = frozenset({"diagram", "chart", "figure", "graph", "plan",
                              "sketch", "so_do"})
DIAGRAM_LABEL = "Figure"


def graphic_label(mark: dict[str, Any]) -> str:
    """Nhãn cho một mảng mực-không-chữ: `Stamp`, `Figure`, hay `Image`.

    Quyết theo `kind` -- tức `data-graphic` mà markup tự khai -- chứ không
    theo hình học: chỉ tác giả trang biết một mảng mực là con dấu, một sơ đồ,
    hay một hoa văn nền."""
    kind = str(mark.get("kind") or "").strip().lower()
    head = kind.split()[0] if kind else ""
    if (kind in STAMP_GRAPHICS or head in STAMP_GRAPHICS
            or "seal" in kind or "stamp" in kind):
        return STAMP_LABEL
    if kind in DIAGRAM_GRAPHICS or head in DIAGRAM_GRAPHICS:
        return DIAGRAM_LABEL
    return GRAPHIC_LABEL

# Nhãn của MỰC ĐÈ: vùng nằm chồng lên nội dung chứ không chứa nội dung.
#
# Phép gán chữ vào vùng ở `regions_from_words` là phép chứa HÌNH HỌC, và với
# mọi vùng khác thì đó đúng là câu hỏi cần hỏi. Với chữ chìm thì không: nó in
# đè lên tờ giấy, nên mọi từ nằm dưới nó đều lọt vào khung của nó. Vùng phủ
# chỉ nhận những từ MANG CHÍNH NHÃN ẤY.
OVERLAY_LABELS = frozenset({"Watermark"})


# Nhãn được phép chứa vùng khác: định nghĩa của chúng LÀ "một khối gồm nhiều
# thứ nhỏ hơn". `Figure` ôm `Caption`, `Table` ôm bảng lồng, `Complex-Block` ôm
# nhiều khối nhãn-giá trị.
#
# MỘT bản, đọc từ hai chỗ. Trước đây đây là hai `frozenset` giống hệt nhau --
# một cái tên `GROUPING` nằm trong thân `regions_from_words`, một cái tên
# `GROUPING_LABELS` ở tầng module -- và thêm một nhãn vào một bên là để bên kia
# cũ đi lặng lẽ, đúng cái bệnh `pipeline/tags.py` được viết ra để chữa.
GROUPING_LABELS = frozenset({"Complex-Block", "Table", "Figure"})

# Hộp ngoài có bao TRỌN hộp trong, và có rộng hơn hẳn không.
#
# `slack` là mức "rộng hơn hẳn": 1.0 nghĩa là chỉ cần lớn hơn, 1.05 đòi lớn
# hơn 5%. Hai chỗ gọi đòi hai mức khác nhau và cả hai đều có lý -- xem chỗ gọi
# -- nhưng phép xét thì phải là MỘT, vì hai bản chép của cùng một bất đẳng
# thức bốn vế là hai cơ hội gõ nhầm một dấu.
def _encloses(outer: tuple[float, float, float, float],
              inner: tuple[float, float, float, float],
              slack: float = 1.0) -> bool:
    if not (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3]):
        return False
    wide = (outer[2] - outer[0]) * (outer[3] - outer[1])
    small = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return wide > small * slack


# How many word-heights of vertical gap end a region and start the next one,
# when grouping by `layout_class` -- see `regions_from_words`.
REGION_GAP_HEIGHTS = 1.6

# How many word-heights of HORIZONTAL gap end a region and start the next one,
# for two words that sit on the *same* line. Wider than `REGION_GAP_HEIGHTS`
# on purpose: a column gutter -- the space between a date field and a serial
# number field printed side by side in one header row -- reads as several
# word-heights of blank paper, while the space between two words IN one
# phrase is a fraction of one. Any layout that prints unrelated same-class
# content side by side needs this, not just the one that first exposed it.
REGION_GAP_WIDTHS = 3.0


def _pad_bbox(bbox: tuple[float, float, float, float], page_size) -> list[int]:
    x1, y1, x2, y2 = bbox
    x1, y1 = x1 - REGION_PAD_PX, y1 - REGION_PAD_PX
    x2, y2 = x2 + REGION_PAD_PX, y2 + REGION_PAD_PX
    if page_size:
        width, height = page_size
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def _region_entry(region_index: int, layout_class: str, text: str,
                  bbox: tuple[float, float, float, float], strategy: str,
                  page_size) -> dict[str, Any]:
    x1, y1, x2, y2 = _pad_bbox(bbox, page_size)
    return {
        "region_index": region_index,
        "tag": "div",
        "layout_class": layout_class,
        "text": text,
        "bbox": [x1, y1, x2, y2],
        "bbox_mode": "xyxy_pixel",
        "bbox_strategy": strategy,
        "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]],
    }


def _region_gap_ok(current_bbox: list[float], word_bbox: list[float],
                   gap_y: float, gap_x: float) -> bool:
    """Whether `word_bbox` continues the run `current_bbox` is the union of,
    rather than starting a new region.

    One test, on both axes at once -- not "same line, judge only by the
    horizontal gap" versus "different line, judge only by the vertical gap."
    An earlier version split on that distinction and it does tell a phrase
    from an unrelated field beside it (a date at the left of a header, a
    serial number at the right, sharing a line), but checking only the
    vertical gap for two words on different lines has its own failure: a
    checklist's Yes/No answer column sits far to the right of the question
    text it answers, so once that answer starts a region of its own -- correct,
    it is not close horizontally to the question beside it -- the *next*
    question below, on a new line, was still judged only by the vertical
    gap to that isolated answer and got pulled into its region, dragging
    every question after it in behind it.

    Testing both axes against the RUNNING UNION avoids this without a special
    case for either shape: the union grows to cover the column a wrapped
    paragraph actually occupies, so a later line that starts back at that
    same left margin has zero horizontal gap to it however far below the
    line above it sits -- ordinary paragraphs and stacked lists still merge
    across their own vertical gap exactly as before. A one-word fragment far
    to the side (that answer column) keeps a narrow union bbox of its own, so
    the next line's horizontal distance to it stays large and the wrong
    merge no longer happens.
    """
    ax1, ay1, ax2, ay2 = current_bbox
    bx1, by1, bx2, by2 = word_bbox
    dx = max(0.0, bx1 - ax2, ax1 - bx2)
    dy = max(0.0, by1 - ay2, ay1 - by2)
    return dx <= gap_x and dy <= gap_y


# Chữ VẼ ĐÈ lên trang, không nằm trong dòng chảy của nó: chữ chìm. Nó
# `position:absolute` giữa tờ giấy, nên hộp của nó chồng lên bất cứ thứ gì
# tình cờ nằm dưới -- thường là bảng hàng. Phép xét "nằm trong ô nào" không
# nói được gì về nó: nó nằm TRÊN cái ô ấy chứ không ở TRONG. Đo được: "BẢN
# SAO" ra nhãn `Table` vì tâm chữ rơi đúng vào một ô.
FLOATING = {"watermark"}


def _floating(word: dict[str, Any]) -> bool:
    return str(word.get("field_path") or "").split(".")[0] in FLOATING


def regions_from_words(words: list[dict[str, Any]], *,
                       cells: Iterable[dict[str, Any]] = (),
                       zones: Iterable[dict[str, Any]] = (),
                       graphics: Iterable[dict[str, Any]] = (),
                       page_size: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    """Every `layout_annotations` region on the page, covering EVERY word --
    not only the ones that happen to sit in an obviously named block. As a
    side effect, sets `layout_region_index` on every word (already carrying
    its own `layout_class` from `words_from_boxes`).

    Two passes:

    1. **A real `<table>`, if the page drew one** (`cells`, from `page.py::
       CELL_REGIONS_JS` -- empty for the character-grid backend, which has no
       `<table>` element to measure: its rules are painted marks, not cells).
       The region's box is the union of the measured `<td>` boxes -- the
       table's own border and padding, which is what "the table" means to a
       reader, not a crop of whichever cell's text happens to run furthest
       in each direction. Multiple real tables on one page (an invoice's
       items table and its separate tax-summary table) are folded into one
       Table region rather than told apart: both ARE tables, and telling them
       apart needs geometry this function does not have reason to compute
       twice when `words_from_boxes` already means both count as one label.

    2. **Everything else**, grouped by `layout_class` in reading order, split
       into a new region wherever the next word is not "close" to the run so
       far -- see `_region_gap_ok` for what "close" means. This is what gives
       every remaining word a region: there is no third bucket.

    3. **Ink that is not a word** (`graphics`, from `page.py::
       GRAPHIC_RECTS_JS` -- empty for the character-grid backend, which draws
       none): the logo, the rosette, the barcode, the watermark, the
       signature. Every one of them puts ink on the paper and none of them is
       a run, so before this they appeared in no annotation at all -- a proof
       image showed the "C" logo at the top of every `modern` invoice with no
       box round it. Appended rather than interleaved, which matches what the
       Table region already does: reading order is not what `region_index`
       has ever meant here.
    """
    cells = list(cells or [])
    regions: list[dict[str, Any]] = []
    covered = [False] * len(words)

    # MỘT VÙNG CHO MỖI `<table>`, không phải một vùng cho cả trang. Trước đây
    # đây là hợp của MỌI ô đo được -- đúng khi trang chỉ có bảng hàng, sai ngay
    # khi có cái thứ hai: hoá đơn in bảng hàng rồi "Bằng chữ: ..." rồi khung
    # tổng hợp thuế, và một vùng trùm từ bảng đầu tới bảng cuối nuốt luôn dòng
    # chữ ở giữa -- nó thành `Table` dù không nằm trong ô nào.
    #
    # `cell["table"]` là số thứ tự `<table>` gần nhất, do
    # `page.py::CELL_REGIONS_JS` đọc thẳng từ DOM. Hai ô cùng một `<table>` thì
    # cùng một bảng; không phải suy từ toạ độ, nên hai bảng sát nhau cũng không
    # dính vào nhau.
    by_table: dict[int, list[dict[str, Any]]] = {}
    for cell in cells:
        by_table.setdefault(int(cell.get("table", 0) or 0), []).append(cell)
    for _which, group in sorted(by_table.items()):
        x1 = min(c["quad"][0][0] for c in group)
        y1 = min(c["quad"][0][1] for c in group)
        x2 = max(c["quad"][2][0] for c in group)
        y2 = max(c["quad"][2][1] for c in group)
        text = " ".join(str(c.get("text", "")) for c in group if c.get("text"))
        regions.append(_region_entry(len(regions), "Table", text,
                                     (x1, y1, x2, y2),
                                     "dom_element_perimeter", page_size))
        index = regions[-1]["region_index"]
        # Thuộc bảng là nằm trong một Ô THẬT, không phải nằm trong hộp bao của
        # bảng. Hai chuyện ấy khác nhau khi có thứ gì nổi đè lên: chữ chìm "BẢN
        # SAO" vẽ giữa trang, phủ lên bảng hàng, và xét theo hộp bao thì nó
        # thành chữ trong bảng -- đo được, nó ra nhãn `Table`. Xét theo ô thì
        # không, vì nó không nằm trong ô nào cả.
        # Giữ lại CHÍNH cái ô đã khớp, không chỉ biết "có khớp hay không":
        # `role` của một từ trong bảng phụ thuộc chỗ ngồi của nó -- đầu bảng,
        # cột số thứ tự, hay ô thường -- và chỗ ngồi ấy nằm trên ô.
        boxes = [((c["quad"][0][0], c["quad"][0][1],
                   c["quad"][2][0], c["quad"][2][1]), c) for c in group]
        for i, word in enumerate(words):
            if covered[i] or _floating(word):
                continue
            cx = (word["bbox"][0] + word["bbox"][2]) / 2
            cy = (word["bbox"][1] + word["bbox"][3]) / 2
            seat = next((c for (cx1, cy1, cx2, cy2), c in boxes
                         if cx1 <= cx <= cx2 and cy1 <= cy <= cy2), None)
            if seat is not None:
                covered[i] = True
                word["layout_region_index"] = index
                # `Table` là một chuyện của DOM, không của chữ nghĩa. Một từ
                # nằm trong `<td>` đo được LÀ chữ trong bảng, dù `kind` của nó
                # nói gì -- và đó là cách khối tổng in thành `<tr><td>` (bộ
                # sinh cũ) vẫn đọc là `Table`, trong khi khối tổng in thành
                # `<div class="trow">` (cùng `kind`, khác DOM) thì không.
                # Không có dòng này thì hai chỗ ấy phải tranh nhau một ô trong
                # bảng tra, và bên nào thắng thì bên kia mang nhãn sai.
                word["layout_class"] = "Table"
                # Chỗ ngồi đã biết: `colhdr` nếu ở `<thead>`, `rowhdr` nếu cột
                # 0 của thân bảng, còn lại là `cell`. Ba vai này chắc hơn mọi
                # phép suy từ `kind`, nên chúng ghi đè.
                word["role"] = run_role(
                    str(word.get("field_path") or ""), "Table",
                    in_table=not bool(seat.get("head")),
                    head_cell=bool(seat.get("head")),
                    column=seat.get("col"))

    # 1b. **Khối tự khai vùng** (`zones`, từ `page.py::ZONE_REGIONS_JS`). Bộ
    #     gom ở bước 2 nối từ theo nhãn rồi cắt ở chỗ hở rộng -- đúng cho chữ
    #     chạy, sai cho một khối "nhãn ... giá trị", vì máng giữa hai cột rộng
    #     hơn ngưỡng cắt. Một tờ bảng kê cho ra TÁM vùng rời ở khối tổng, mỗi
    #     nhãn và mỗi số một vùng. Khối nào biết mình là một khối thì tự khai,
    #     và hộp lấy của chính phần tử -- kể cả viền và lề, đúng thứ người đọc
    #     gọi là "cái khung tổng".
    # TRONG RA NGOÀI. Bản trước đi theo thứ tự DOM và bỏ vùng nào không còn chữ
    # chưa ai nhận (`if not member: continue`) -- nên một vùng BỌC xử lý trước
    # nuốt hết chữ của các vùng con, và mọi vùng con biến mất. Đo trên một tờ
    # hợp đồng: `tighten` trả 31 vùng, bản ghi giữ 8.
    #
    # Xếp theo diện tích tăng dần thì vùng nhỏ nhất -- tức vùng SÂU nhất -- nhận
    # chữ trước, và mỗi chữ thuộc về đúng cái vùng sát nó nhất. Vùng bọc vẫn
    # được ghi, với hộp của chính nó, vì nó vẫn là một vùng người đọc thấy.
    def _area(z: dict[str, Any]) -> float:
        q = z.get("quad") or []
        if len(q) != 4:
            return 0.0
        return abs(q[2][0] - q[0][0]) * abs(q[2][1] - q[0][1])

    def _span(zone: dict[str, Any]) -> tuple[float, float, float, float] | None:
        q = zone.get("quad") or []
        return (q[0][0], q[0][1], q[2][0], q[2][1]) if len(q) == 4 else None

    def _wraps(outer: dict, others: list[dict]) -> int:
        """Đếm vùng khác nằm TRỌN trong `outer`. Phép xét là `_encloses` ở
        tầng module -- cùng bất đẳng thức `_unwrap` dùng."""
        box = _span(outer)
        if box is None:
            return 0
        return sum(1 for other in others
                   if other is not outer and _span(other) is not None
                   and _encloses(box, _span(other)))

    # KHUNG GÓI KHÔNG PHẢI MỘT VÙNG.
    #
    # Một `<div data-region="Page-Header">` trùm mười bốn vùng khác -- kể cả
    # một `Page-Footer` -- là một cái khung model dùng để gói rồi lỡ gắn nhãn
    # lên. Cây DOM của `llm_house_handover_minutes_0010` đúng là như thế: hình
    # học không nói dối, markup nói dối.
    #
    # Xét SỐ VÙNG BỊ TRÙM, không xét việc nó có chữ lạc của riêng nó hay không:
    # một cái khung vẫn có thể ôm vài chữ rơi ngoài mọi vùng con, và bản sửa
    # trước dừng ở đó nên tám cái `Page-Header ⊃ Key-Value` vẫn lọt.
    #
    # MỘT vùng bị trùm là đã đủ. Thử ngưỡng hai trước: `house_handover` sạch
    # nhưng vẫn còn 55 ca `Page-Header ⊃ Text`, `Text ⊃ Text` -- khung chỉ gói
    # đúng một vùng. Gói một vẫn là gói.
    #
    # Ba nhãn trong `GROUPING_LABELS` miễn trừ, vì định nghĩa của chúng LÀ chứa thứ
    # nhỏ hơn: `Figure` ôm `Caption`, `Table` ôm bảng lồng, `Complex-Block` ôm
    # nhiều khối nhãn-giá trị.
    all_zones = [z for z in (zones or []) if len(z.get("quad") or []) == 4]
    wrappers = {id(z) for z in all_zones
                if str(z.get("label") or "") not in GROUPING_LABELS
                and _wraps(z, all_zones) >= 1}

    for zone in sorted(list(zones or []), key=_area):
        if id(zone) in wrappers:
            continue
        quad = zone.get("quad") or []
        if len(quad) != 4:
            continue
        zx1, zy1 = quad[0][0], quad[0][1]
        zx2, zy2 = quad[2][0], quad[2][1]
        # MỌI chữ trong khung, kể cả chữ vùng con đã nhận: một vùng bọc có nội
        # dung thì nó tồn tại, dù nội dung ấy thuộc về vùng con.
        #
        # TRỪ VÙNG PHỦ. `Watermark` là MỰC ĐÈ lên tờ giấy, không phải một
        # khung chứa chữ: phép chứa hình học ở đây đúng cho mọi vùng khác,
        # nhưng với chữ chìm nó gán cho watermark mọi từ nằm DƯỚI nó. Đo trên
        # `so_lien_lac_00007`: vùng `Watermark` mang chữ
        # `'BẢN SAO quy Lao Điều 5. Các bên thi hành định kỳ. cấp đầu'` --
        # "BẢN SAO" là của nó, phần còn lại là điều khoản bị nó nằm chồng lên.
        #
        # Chữ của vùng phủ nhận ra bằng chính `layout_class` của từ: mỗi từ đã
        # mang nhãn suy từ `data-kind` của nó (`watermark` -> `Watermark`), và
        # đó là sự thật về từ ấy THUỘC VỀ ai, không phải về nó NẰM Ở ĐÂU.
        label_here = str(zone.get("label") or "")
        overlay = label_here in OVERLAY_LABELS
        inside, fresh = [], []
        for i, word in enumerate(words):
            cx = (word["bbox"][0] + word["bbox"][2]) / 2
            cy = (word["bbox"][1] + word["bbox"][3]) / 2
            if not (zx1 <= cx <= zx2 and zy1 <= cy <= zy2):
                continue
            if overlay and str(word.get("layout_class") or "") != label_here:
                continue
            inside.append(i)
            if not covered[i]:
                fresh.append(i)
        if not inside:
            continue
        # VÙNG BỌC KHÔNG PHẢI MỘT VÙNG.
        #
        # Nếu MỌI chữ trong khung đã thuộc về một vùng nhỏ hơn bên trong, thì
        # cái khung này không có nội dung của riêng nó -- nó chỉ là một thẻ
        # `<div>` model dùng để gói, rồi lỡ gắn `data-region` lên.
        #
        # Đo trên `llm_house_handover_minutes_0010`: cây DOM thật sự lồng
        # MƯỜI BỐN vùng trong một `Page-Header`, và cái `Page-Header` ấy chứa
        # cả một `Page-Footer`. Hình học không nói dối -- markup nói dối. Vẽ ra
        # thì một hộp `Page-Header` khổng lồ trùm gần hết tờ giấy, và mười bốn
        # hộp thật nằm lọt trong nó.
        #
        # Bỏ cái khung, giữ mười bốn vùng con: mỗi chữ vẫn có đúng một vùng, và
        # vùng ấy là vùng SÁT nó nhất. Đây là nới lại đúng chỗ tôi đã nới quá
        # tay khi chữa lỗi "vùng bọc nuốt vùng con" -- lần ấy tôi cho vùng bọc
        # được ghi vô điều kiện.
        # Luật "khung rỗng thì bỏ" KHÔNG áp cho vùng model khai tay.
        #
        # Vùng suy từ thẻ nằm trong nó đã nhận hết chữ trước (xếp theo diện
        # tích, nhỏ trước), nên cái khai tay còn `fresh` rỗng và bị bỏ. Đo trên
        # pilot14: 8 trên 16 tài liệu mất một vùng đã khai -- `Title` thành
        # `Section-Header` vì `<div data-region="Title"><h2>` cho hai vùng và
        # cái `<h2>` thắng.
        #
        # Model khai tay là model NÓI RÕ khối này là gì. Một phép suy từ tên
        # thẻ không được quyền ghi đè lời ấy.
        #
        # Nhãn nào có phép đo RIÊNG (`Table`/`Image`/`Stamp`, `pipeline/
        # tags.py::MEASURED_ELSEWHERE`) không bao giờ tới được vòng lặp này để
        # mà cần một ngoại lệ nữa -- `generators/html/page.py::ZONE_REGIONS_JS`
        # đã lọc chúng khỏi `zones` từ trước khi hàm này nhận được danh sách,
        # dù model khai `data-region` trực tiếp lên đúng phần tử phép đo riêng
        # ấy đo (`<table data-region="Table">`). Từng có một ngoại lệ vá ở
        # đây cho riêng `Table`, đo trên `llm_export_invoice_0003.json`
        # (bốn vùng `Table` thay vì hai) -- bỏ đi sau khi sửa tận gốc ở JS,
        # để một sự thật chỉ nằm ở một chỗ.
        if not fresh and str(zone.get("from") or "declared") != "declared":
            continue
        label = str(zone.get("label") or "Text")
        text = " ".join(words[i]["text"] for i in inside if words[i]["text"])
        regions.append(_region_entry(len(regions), label, text,
                                     (zx1, zy1, zx2, zy2),
                                     "dom_element_perimeter", page_size))
        regions[-1]["from"] = str(zone.get("from") or "declared")
        # Chỉ chữ CHƯA ai nhận mới đổi chủ: vùng con đã nhận thì giữ nguyên.
        for i in fresh:
            covered[i] = True
            words[i]["layout_region_index"] = regions[-1]["region_index"]
            words[i]["layout_class"] = label

    graphics = list(graphics or [])

    heights = [w["bbox"][3] - w["bbox"][1] for i, w in enumerate(words) if not covered[i]]
    median_height = sorted(heights)[len(heights) // 2] if heights else 12.5
    gap_y = median_height * REGION_GAP_HEIGHTS
    gap_x = median_height * REGION_GAP_WIDTHS

    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        member = current["members"]
        x1, y1, x2, y2 = current["bbox"]
        text = " ".join(w["text"] for w in member if w["text"])
        regions.append(_region_entry(len(regions), current["layout_class"], text,
                                     (x1, y1, x2, y2), "visible_content_union_perimeter",
                                     page_size))
        for w in member:
            w["layout_region_index"] = regions[-1]["region_index"]
        current = None

    for i, word in enumerate(words):
        if covered[i]:
            flush()
            # Mọi từ đã `covered` đều được gán vùng của nó ngay lúc phủ -- ô
            # bảng ở bước 1, `zone` ở bước 1b. Dòng này từng gán cứng số 0 vì
            # "vùng Table luôn là số 0", và điều ấy thôi đúng từ khi mỗi
            # `<table>` có vùng riêng: một trang hai bảng thì bảng thứ hai là
            # vùng số 1, và gán 0 là trỏ mọi từ của nó sang bảng thứ nhất.
            if word.get("layout_region_index") is None:
                word["layout_region_index"] = 0
            continue
        cls = word["layout_class"]
        # Họ của `kind` -- `store`, `note`, `invoice`, `sign`. Cùng nhãn mà
        # khác họ thì là hai CỤM THÔNG TIN khác nhau, và một bộ nhận dạng học
        # theo cụm cần chúng rời nhau: khối ghi chú và khối trường "Số đơn bảo
        # hiểm / Tên người tham gia / Chủ hợp đồng" đều là `Text`, in sát nhau,
        # và gộp làm một thì cái hộp ấy không dạy được gì về cụm nào cả.
        #
        # Cắt theo HỌ chứ không theo `kind` đầy đủ: `invoice.field.label` và
        # `invoice.field` là nhãn và giá trị của cùng một dòng, tách chúng ra
        # là tách một dòng làm đôi.
        family = str(word.get("field_path") or "").split(".")[0]
        wb = word["bbox"]
        if (current is not None and current["layout_class"] == cls
                and current["family"] == family
                and _region_gap_ok(current["bbox"], wb, gap_y, gap_x)):
            current["members"].append(word)
            current["bbox"] = [min(current["bbox"][0], wb[0]), min(current["bbox"][1], wb[1]),
                               max(current["bbox"][2], wb[2]), max(current["bbox"][3], wb[3])]
        else:
            flush()
            current = {"layout_class": cls, "family": family,
                       "members": [word], "bbox": list(wb)}
    flush()

    # Pass 3: ink that is not a word. `text` stays empty and that is not an
    # omission -- a region's `text` is what a reader reads off it, and there is
    # nothing to read off a logo. What it is instead rides in `bbox_strategy`,
    # which already distinguishes a measured element from a union of words.
    for mark in graphics:
        quad = mark.get("quad") or []
        if len(quad) < 4:
            continue
        xs = [float(point[0]) for point in quad[:4]]
        ys = [float(point[1]) for point in quad[:4]]
        regions.append(_region_entry(len(regions), graphic_label(mark), "",
                                     (min(xs), min(ys), max(xs), max(ys)),
                                     "dom_element_perimeter", page_size))
    return _unwrap(regions, words)


def _unwrap(regions: list[dict[str, Any]],
            words: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Bỏ vùng chỉ đóng vai cái KHUNG bọc vùng khác.

    ## Vì sao ở cuối, không ở lúc đọc `zones`

    Thử lọc lúc duyệt `zones` trước: `llm_house_handover_minutes_0010` sạch --
    cái `Page-Header` trùm mười bốn vùng biến mất. Nhưng tổng số hộp lồng
    không nhúc nhích: 55 trên 557, y nguyên.

    Vì phần lớn hộp lồng KHÔNG phải vùng model khai. Chúng do bước gom-từ tạo
    ra SAU đó, từ những chữ chưa vùng nào nhận -- nên lúc quyết "cái nào là
    khung" chúng chưa tồn tại. Một `Page-Header` khai đúng vẫn có thể ôm trọn
    một vùng `Text` sinh ra sau.

    Ở cuối thì mọi vùng đã có mặt, bất kể nó đến từ đường nào.

    ## Vì sao bỏ CÁI NGOÀI chứ không bỏ cái trong

    Hộp trong bám sát chữ; hộp ngoài là cái khung dàn trang. Với người huấn
    luyện layout-detection, hai hộp chồng nhau mà một cái chỉ là khung là hai
    nhãn tranh nhau cùng một điểm ảnh -- và cái đáng giữ là cái ôm sát mực.

    Chỉ bỏ khi bao TRỌN và RỘNG HƠN hẳn: hai hộp trùng khít là chuyện khác,
    và bỏ một trong hai thì mất thật.

    ## Vì sao cần `words`

    Hai việc, và cả hai đều về CON TRỎ `layout_region_index`, thứ bản trước
    không hề biết tới:

    1. **Vùng có chữ của riêng nó không phải cái khung.** Luật bỏ-cái-ngoài
       chỉ xét hình học, nên một đoạn văn bị con dấu đóng đè lên giữa trang
       cũng "bao trọn" cái dấu và bị vứt -- đoạn văn mất hộp, còn chữ của nó
       thì không còn vùng nào. Đo trên `data/`: 592 từ mang nhãn `List-Group`
       trỏ vào một vùng `Stamp`, đúng cái ca ấy.
    2. **Đánh số lại thì phải đổi cả con trỏ.** `region_index` được đánh lại
       từ 0 sau khi bỏ, nhưng `word["layout_region_index"]` đã ghi số CŨ, và
       không ai ánh xạ nó. Đo trên 1105 bản ghi trong `data/`: 30 tờ (3%) và
       4231 từ (0,6%) trỏ vào một vùng không chứa chúng; 66% số ấy có một
       vùng khác thật sự chứa chúng, tức trỏ nhầm chứ không phải không có
       vùng nào. `synthgen/check.py` chỉ kiểm chỉ số có nằm trong mảng hay
       không, nên lỗi này im lặng suốt."""
    if len(regions) < 2:
        return regions

    def box(region: dict[str, Any]) -> tuple[float, float, float, float] | None:
        quad = region.get("polygon") or region.get("quad") or []
        if len(quad) >= 4:
            xs = [float(p[0]) for p in quad[:4]]
            ys = [float(p[1]) for p in quad[:4]]
            return min(xs), min(ys), max(xs), max(ys)
        bbox = region.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return tuple(float(v) for v in bbox)
        return None

    boxes = [box(r) for r in regions]
    drop: set[int] = set()
    for i, outer in enumerate(boxes):
        if outer is None or str(regions[i].get("layout_class") or "") in GROUPING_LABELS:
            continue
        for j, inner in enumerate(boxes):
            if i == j or inner is None or j in drop:
                continue
            # `1.05`: hai hộp trùng khít là chuyện khác, và bỏ một trong
            # hai thì mất thật. Bộ lọc khung ở `regions_from_words` xét cùng
            # phép này với `slack=1.0` -- ở đó hai vùng KHAI TAY trùng khít
            # vẫn là hai vùng khai tay, không phải một cái khung.
            if _encloses(outer, inner, 1.05):
                # KHAI TAY THẮNG SUY TỪ THẺ.
                #
                # `ZONE_REGIONS_JS` phát cả phần tử `[data-region]` lẫn thẻ
                # ngữ nghĩa bên trong nó, và phép kiểm "twice" ở đó chỉ bỏ khi
                # tổ tiên cho ra ĐÚNG nhãn ấy. Model viết
                # `<div data-region="Title"><h2>…` thì `h2` cho `Section-Header`
                # -- khác nhãn, nên cả hai cùng ra, rồi luật bỏ-cái-ngoài ở đây
                # vứt đúng cái model khai tay.
                #
                # Đo trên pilot14: 8 trên 16 tài liệu mất một vùng đã khai --
                # `Title`, `Page-Header`, `Figure`, `Caption`, `Watermark`,
                # `Stamp`. Chú thích trong chính `page.py` viết "`data-region`
                # viết tay THẮNG"; đo được thì nó thua.
                if (str(regions[i].get("from") or "declared") == "declared"
                        and str(regions[j].get("from") or "") == "tag"):
                    drop.add(j)
                    continue
                drop.add(i)
                break

    # CHỮ CỦA RIÊNG NÓ THÌ NÓ KHÔNG PHẢI CÁI KHUNG.
    #
    # Luật trên chỉ nhìn hình học, và hình học không phân biệt "cái khung bọc
    # một khối" với "một đoạn văn bị đóng dấu đè lên giữa". Cả hai đều bao
    # trọn một vùng nhỏ hơn. Bỏ cái thứ hai là bỏ đúng cái hộp ôm sát mực --
    # ngược hẳn với lý do luật này tồn tại.
    #
    # Phân biệt được vì không cần đoán: chữ nào thuộc vùng nào đã gán xong ở
    # trên. Vùng nào còn chữ không vùng SỐNG SÓT nào chứa thì nó có nội dung
    # của riêng nó, và nó ở lại.
    #
    # Vùng bọc do model khai đã bị `wrappers` lọc từ bước 1b nên không tới
    # đây; thứ tới đây phần lớn là vùng gom-từ sinh sau. Một vùng gom-từ
    # không bao giờ rỗng, nên phép xét này chỉ giữ lại đúng những vùng mà
    # việc bỏ đi sẽ để chữ mồ côi.
    held: dict[int, list[dict[str, Any]]] = {}
    for word in words or ():
        where = word.get("layout_region_index")
        if isinstance(where, int):
            held.setdefault(where, []).append(word)

    def _homed(word: dict[str, Any], among: list[int]) -> bool:
        """Có vùng nào trong `among` chứa tâm hộp của từ này không."""
        bbox = word.get("bbox") or []
        if len(bbox) != 4:
            return True
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        return any(boxes[k] is not None
                   and boxes[k][0] <= cx <= boxes[k][2]
                   and boxes[k][1] <= cy <= boxes[k][3] for k in among)

    for i in sorted(drop):
        mine = held.get(int(regions[i].get("region_index", i)) , ())
        if not mine:
            continue
        others = [k for k in range(len(regions)) if k != i and k not in drop]
        if not all(_homed(word, others) for word in mine):
            drop.discard(i)

    if not drop:
        return regions
    survivors = [k for k in range(len(regions)) if k not in drop]
    # Số CŨ -> số MỚI, dựng trước khi đánh lại: sau khi `region_index` bị ghi
    # đè thì không còn đường nào tìm lại con trỏ của từ.
    remap = {int(regions[k].get("region_index", k)): number
             for number, k in enumerate(survivors)}
    kept = [regions[k] for k in survivors]
    for number, region in enumerate(kept):
        region["region_index"] = number

    kept_boxes = [box(r) for r in kept]

    def _host(word: dict[str, Any]) -> int | None:
        """Vùng còn lại NHỎ NHẤT chứa từ này -- cùng lẽ với thứ tự xếp vùng
        theo diện tích ở `regions_from_words`: nhỏ nhất là sát nó nhất."""
        bbox = word.get("bbox") or []
        if len(bbox) != 4:
            return None
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        inside = [(( rb[2] - rb[0]) * (rb[3] - rb[1]), number)
                  for number, rb in enumerate(kept_boxes)
                  if rb is not None and rb[0] <= cx <= rb[2] and rb[1] <= cy <= rb[3]]
        return min(inside)[1] if inside else None

    for word in words or ():
        where = word.get("layout_region_index")
        if not isinstance(where, int):
            continue
        # Vùng còn sống thì chỉ đổi số. Vùng đã bỏ thì tìm nhà mới, và phép
        # xét ngay trên đã bảo đảm có nhà -- `None` chỉ xảy ra với từ không
        # có hộp, thứ `words_from_boxes` không sinh ra.
        word["layout_region_index"] = (remap[where] if where in remap
                                       else _host(word))
    return kept


def rows(blocks: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Blocks grouped into the lines they were printed on.

    A receipt line is three boxes -- name, quantity, amount -- and writing each
    on its own markdown line turns a table into a column. Two adjacent blocks
    share a row when their boxes overlap vertically by more than half the
    shorter one's height, which is the same test a person makes by eye and does
    not need the grid the renderer has already thrown away. Headings never join
    a row: a title beside a date is still a title.

    **Down the page, then across it -- not the order the renderer drew in.**
    `synthesis.json` keeps the canonical `text_sequence` the label is built in,
    which is a different thing and stays a different thing: a form draws its
    left column and then its right, so drawn order puts every label in one run
    and every value in another, and the markdown would read as two lists rather
    than as the page. Sorting by the top edge and then the left one is what a
    converter reading the pixels would do, and it is what puts
    `(1) Họ tên người bệnh: ...` and `Ngày, tháng, năm sinh: ...` back on the
    one line they are printed on.
    """
    grouped: list[list[dict[str, Any]]] = []
    ordered = sorted(
        (block for block in blocks if str(block.get("content", "")).strip()),
        key=lambda block: (float((block.get("bbox") or {}).get("y1", 0)),
                           float((block.get("bbox") or {}).get("x1", 0))))
    for block in ordered:
        box = block.get("bbox") or {}
        top, bottom = float(box.get("y1", 0)), float(box.get("y2", 0))
        alone = block.get("label") in STANDALONE
        if grouped and not alone:
            last = grouped[-1][-1]
            if last.get("label") not in STANDALONE:
                other = last.get("bbox") or {}
                o_top, o_bottom = float(other.get("y1", 0)), float(other.get("y2", 0))
                overlap = min(bottom, o_bottom) - max(top, o_top)
                shorter = min(bottom - top, o_bottom - o_top)
                if shorter > 0 and overlap > shorter / 2:
                    grouped[-1].append(block)
                    continue
        grouped.append([block])
    # Left to right inside a row, which is the order it was read in and not
    # necessarily the order it was drawn in. A stable sort, so two boxes that
    # start at the same x keep the renderer's own order between them.
    return [sorted(row, key=lambda block: float((block.get("bbox") or {}).get("x1", 0)))
            for row in grouped]


def markdown_of(blocks: Iterable[dict[str, Any]]) -> str:
    """The page as markdown: one paragraph per printed line."""
    lines = ["  ".join(block["content"] for block in row) for row in rows(blocks)]
    return "\n\n".join(line for line in lines if line.strip())


def html_of(blocks: Iterable[dict[str, Any]]) -> str:
    """The same page as HTML, one element per printed line."""
    out: list[str] = []
    for row in rows(blocks):
        tag = HTML_TAG.get(row[0].get("label", ""), "p")
        text = " ".join(str(block.get("text", "")).strip() for block in row)
        out.append(f"<{tag}>{_escape(text)}</{tag}>")
    return "\n".join(out) + ("\n" if out else "")


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def field_paths(extracted: Any, prefix: str = "") -> list[str]:
    """Every leaf path in the nested label, which is what `extract_fields` names.

    `settings.extract_fields` is empty on a converter run that was asked for
    nothing in particular. Here the label is always produced, so the honest
    value is the list of fields it carries.
    """
    out: list[str] = []
    if isinstance(extracted, dict):
        for key, value in extracted.items():
            out += field_paths(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(extracted, list):
        for value in extracted:
            out += field_paths(value, prefix)
    elif prefix:
        out.append(prefix)
    return sorted(dict.fromkeys(out))


# ---------------------------------------------------------------------- build


def build(*, filename: str, width: int, height: int, parser: str,
          boxes: Iterable[dict[str, Any]] = (), words: Iterable[dict[str, Any]] = (),
          cells: Iterable[dict[str, Any]] = (),
          graphics: Iterable[dict[str, Any]] = (),
          fields: Iterable[dict[str, Any]] = (), ink: str = "print",
          extracted: Any = None, seed: Any = "",
          layout: str = "", task: str = TASK_CONVERT,
          settings: dict[str, Any] | None = None,
          sheets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """One metadata line, assembled once so the three renderers cannot drift.

    `seed` and `layout` are not written down -- they are in `synthesis.json` --
    but the `job_id` is a function of both, so they are asked for here and again
    in `stamp`, which is the only other place that id is derived.

    `words`: `page.py::CELL_RECTS_JS`'s `words` array (one box per
    whitespace-separated word), separate from `boxes` (one box per field,
    the same as it always was) because they feed two DIFFERENT arrays here --
    `blocks` stays exactly what every existing reader already expects;
    `word_annotations`/`layout_annotations` are additive, in the
    `docsynth.annotations.v1` shape (`layout_class` from `DOCSYNTH_LABELS`,
    not `PAGE_LABELS`) -- see `words_from_boxes`/`regions_from_words`.

    `cells`: `generators/html/render.py::regions_from_rects`'s table-cell
    list (empty off the character-grid backend, which draws no `<table>`) --
    lets the Table region use the cells' own measured boxes instead of a
    union of the words inside them. See `regions_from_words`.

    `graphics`: `generators/html/render.py::graphics_from_rects`'s list of
    everything that puts ink on the page without being a run -- the logo, the
    rosette, the barcode, the watermark, the signature. Each becomes one
    `Image` region and NO block: a block promises text to read, and none of
    these has any. Empty off the character-grid backend, which draws none.

    `fields`: `page.py::CELL_RECTS_JS`'s `fields` array -- one entry per
    labelled RUN, with the whole string and NO geometry, which is what makes
    `entity_annotations` derivable rather than a fifth set of boxes to keep in
    step. Empty off the character-grid backend, whose cells are one line each
    and never wrap, so a word already is its field.
    """
    # One document, however many printed sides it took. `sheets` is the list of
    # them -- `{filename, width, height, boxes, words, cells, graphics}` each,
    # from `generators/html/render.py` when the layout declared a `page_order`.
    # Left None it is built from the scalar arguments, so the single-page call
    # every caller has always made walks the SAME loop and comes out byte for
    # byte what it came out before: one page, `source_file: ""`, indices from
    # zero. That equality is not cosmetic -- `tools/baseline.py` fingerprints
    # these records, and a second code path for the common case is how the two
    # would drift.
    if sheets is None:
        sheets = [{"filename": filename, "width": width, "height": height,
                   "boxes": boxes, "words": words, "cells": cells,
                   "graphics": graphics, "fields": fields}]
    if not sheets:
        raise ValueError("build() needs at least one sheet")

    blocks: list[dict[str, Any]] = []
    word_annotations: list[dict[str, Any]] = []
    entity_annotations: list[dict[str, Any]] = []
    layout_annotations: list[dict[str, Any]] = []
    pages_meta: list[dict[str, Any]] = []
    multipage = len(sheets) > 1

    for number, sheet in enumerate(sheets, start=1):
        page_width, page_height = int(sheet["width"]), int(sheet["height"])
        # `blocks` cũng phải chuyển, và nó gom SỚM hơn ba tầng kia nên dễ
        # sót đúng ở đây -- bản đầu của thay đổi này sót thật, và một tầng
        # mang pixel lẫn giữa ba tầng mang phần nghìn là bản ghi tự nói hai
        # chuyện về cùng một tờ giấy.
        blocks.extend(to_per_mille(
            blocks_from_boxes(sheet.get("boxes") or (), page_number=number),
            page_width, page_height))
        page_words = words_from_boxes(sheet.get("words") or (), ink)
        # Before the regions, because it MUTATES `page_words`: an entity owns
        # the role, and its words inherit it so one record cannot say two
        # things about the same mark. See `entities_from_words`.
        page_entities = entities_from_words(page_words, sheet.get("fields") or (),
                                            layout=layout)
        page_regions = regions_from_words(
            page_words, cells=sheet.get("cells") or (),
            zones=sheet.get("zones") or (),
            graphics=sheet.get("graphics") or (),
            page_size=(page_width, page_height))
        # Luật "DOM thắng" phải áp cho CẢ thực thể, không riêng từ.
        # `entities_from_words` chạy TRƯỚC `regions_from_words` (nó phải chạy
        # trước, vì nó gán vai trò cho từ), nên lúc nó lấy nhãn thì chưa ai
        # biết từ nào nằm trong `<td>` đo được -- nó chỉ có `kind` để tra. Kết
        # quả đo được: trong khung tổng hợp thuế của `hoa_don_gtgt_00013`, 19
        # từ mang nhãn `Table` còn 8 thực thể gồm đúng những từ ấy mang nhãn
        # `Text`. Cùng một tờ giấy, một bản ghi, hai câu trả lời.
        #
        # Mọi từ đều `Table` thì thực thể là `Table`: một phần thì không, vì
        # một thực thể vắt nửa trong nửa ngoài bảng là thứ không nên im lặng
        # gán về bên nào.
        by_index = {int(w["word_index"]): w for w in page_words}
        for entity in page_entities:
            mine = [by_index.get(i) for i in entity.get("word_indices") or []]
            mine = [w for w in mine if w is not None]
            if mine and all(w.get("layout_class") == "Table" for w in mine):
                entity["layout_class"] = "Table"
            # VAI cũng vậy, và cùng một lẽ. `regions_from_words` nâng vai của
            # từ khi biết chỗ ngồi trong bảng (`colhdr`/`rowhdr`/`cell`) --
            # thứ `kind` không nói được. Thực thể dựng trước nên nó chưa thấy.
            #
            # Đo trên pilot14: ở tầng TỪ có đủ 13 vai, ở tầng THỰC THỂ chỉ 11
            # -- `cell` và `rowhdr` biến mất, và 52% thực thể rơi về `value`.
            seats = {w.get("role") for w in mine if w.get("role")}
            if len(seats) == 1:
                entity["role"] = seats.pop()

        # NHÃN VÙNG CỦA THỰC THỂ LẤY TỪ VÙNG BAO NÓ, không suy từ `kind`.
        #
        # `layout_class_for(kind)` đọc một bảng tra theo tiền tố, nên nó trả
        # lời "một run kiểu này THƯỜNG nằm ở vùng nào" -- không phải "run này
        # ĐANG nằm ở vùng nào". Hai câu khác nhau, và đo trên pilot15 thì
        # 34,6% thực thể trả lời khác nhau: `menu.date` ở dòng đầu thư mang
        # `Table` trên một trang không có bảng nào; `legal.basis` mang `Text`
        # trong khi nó nằm gọn trong một vùng `Bibliography` đã khai.
        #
        # Hệ quả nặng hơn con số ấy: nhánh xét nhãn vùng trong `run_role`
        # thành mã chết. 100% thực thể mang vai `item` có `layout_class:
        # Text`, vì `clause.body` tra ra `Text` -- dù chúng nằm trong
        # `List-Group`.
        #
        # Vùng NHỎ NHẤT bao thực thể, không phải vùng đầu tiên: vùng nhỏ nhất
        # là vùng sát nó nhất, cùng lẽ với thứ tự xếp vùng theo diện tích ở
        # `regions_from_words`.
        boxed = [r for r in page_regions if r.get("bbox")]
        for entity in page_entities:
            box = entity.get("bbox")
            if not box:
                continue
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            hosts = [r for r in boxed
                     if r["bbox"][0] <= cx <= r["bbox"][2]
                     and r["bbox"][1] <= cy <= r["bbox"][3]]
            if not hosts:
                continue
            host = min(hosts, key=lambda r: ((r["bbox"][2] - r["bbox"][0])
                                             * (r["bbox"][3] - r["bbox"][1])))
            label = str(host.get("layout_class") or "")
            if not label:
                continue
            entity["layout_class"] = label
            # Vai tính lại theo nhãn vùng THẬT -- trừ vai do chỗ ngồi trong
            # bảng quyết định, thứ chắc hơn mọi phép suy.
            if entity.get("role") not in ("colhdr", "rowhdr", "cell"):
                entity["role"] = run_role(str(entity.get("kind") or ""), label)
        # `word_index` and `region_index` are positions in THIS record, not in
        # this page, and `layout_region_index` is a pointer between the two
        # arrays. Built per page and then shifted, because the alternative --
        # asking the two helpers to start counting from an offset -- puts the
        # same arithmetic in two more places and leaves the single-page call
        # carrying an argument it never needs.
        word_offset, region_offset = len(word_annotations), len(layout_annotations)
        entity_offset = len(entity_annotations)
        for word in page_words:
            word["word_index"] += word_offset
            if isinstance(word.get("layout_region_index"), int):
                word["layout_region_index"] += region_offset
            if isinstance(word.get("entity_index"), int):
                word["entity_index"] += entity_offset
            word["page_number"] = number
        for entity in page_entities:
            entity["entity_index"] += entity_offset
            entity["word_indices"] = [index + word_offset
                                      for index in entity["word_indices"]]
            if isinstance(entity.get("key_entity_index"), int):
                entity["key_entity_index"] += entity_offset
            entity["page_number"] = number
        for region in page_regions:
            region["region_index"] += region_offset
            region["page_number"] = number
        # CHUYỂN HỆ TOẠ ĐỘ, ở đây và chỉ ở đây. Mọi phép đo hình học bên
        # trên -- gom vùng, đo khoảng hở, xét kề nhau -- chạy bằng pixel và
        # phải chạy bằng pixel; chuyển sớm hơn là bắt chúng tính trên số đã
        # làm tròn. `page_width/page_height` là cạnh của CHÍNH tờ này, nên
        # tài liệu nhiều tờ khổ khác nhau vẫn đúng từng tờ.
        page_words = to_per_mille(page_words, page_width, page_height)
        page_entities = to_per_mille(page_entities, page_width, page_height)
        page_regions = to_per_mille(page_regions, page_width, page_height)

        word_annotations.extend(page_words)
        entity_annotations.extend(page_entities)
        layout_annotations.extend(page_regions)
        pages_meta.append({
            "page_number": number,
            "width": page_width,
            "height": page_height,
            # Blank on a single-page record, where the page IS the file named
            # at the top level and every reader already knows it. Named once
            # there are several, because that is the only place saying which
            # image carries page 3.
            "source_file": str(sheet["filename"]) if multipage else "",
            "document_index": None,
            "html": "",
        })

    options = {**BASE_SETTINGS, **(settings or {})}
    options["convert_mode"] = parser
    options["extract_fields"] = field_paths(extracted)

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id(parser, layout, seed, filename),
        "task": task,
        "parser": parser,
        "filename": filename,
        # Every image this record describes, page order. One page, one file --
        # the shape `validate()` insisted on before a document could span
        # sheets, and still the shape it insists on for a single page.
        "source_files": [str(sheet["filename"]) for sheet in sheets],
        "settings": options,
        # A drawn page is one page of one document, so there is nothing for the
        # converter's segmentation to say. `source_file` and `html` are blank
        # for the same reason they are blank in a converter's own single-page
        # output: the page came from the image itself, and the markup is at the
        # top level rather than repeated per page.
        "documents": [],
        "pages": pages_meta,
        "blocks": blocks,
        "word_annotations": word_annotations,
        # One entry per labelled RUN, carrying the whole string -- the grain
        # KIE reads. `word_annotations` stays one entry per word, and every
        # word points here through `entity_index`. See `entities_from_words`.
        "entity_annotations": entity_annotations,
        "layout_annotations": layout_annotations,
        # KIE, the OCR record's answer to "which value belongs to which
        # caption, and what does that caption mean" -- see `pipeline.kie`
        # for the pairing rule and the fallback/override split.
        "kie": kie.build_page(blocks, entities=entity_annotations, layout=layout),
        "markdown": markdown_of(blocks),
        "html": html_of(blocks),
        "extracted": extracted,
    }


def page_names(name: str, count: int) -> list[str]:
    """The file name of each printed side of one document, given the first.

    Page 1 keeps the name it was given, so a single-page document is named
    exactly as it always was and every index-to-file rule outside this module
    -- `pipeline/plan.py::image_name`, `agent/planner.py::audit_drawn`, the
    proof drawings that walk the image directory -- keeps working untouched.
    The sides after it hang a `_pN` off the same stem, which sorts beside it
    and reads as what it is.

    Here rather than in the renderer because two callers need the same answer:
    the renderer naming what it just drew, and `pipeline/worker.py` renaming
    it out of staging. One of them holding its own copy is how a page 2 ends
    up orphaned under the staging name.
    """
    stem, dot, suffix = name.rpartition(".")
    stem = stem or name
    return [name] + [f"{stem}_p{number}{dot}{suffix}"
                     for number in range(2, int(count) + 1)]


def stamp(item: dict[str, Any], *, parser: str, layout: str, seed: Any,
          filename: str,
          source_files: Iterable[str] | None = None) -> dict[str, Any]:
    """Say again whose page this is, in place, and re-derive the id from it.

    A shard renames every image as it moves it out of staging and attaches the
    layout the plan asked for, and four fields follow: `parser`,
    `settings.convert_mode`, `filename` with its `source_files`, and the
    `job_id`, which is a function of all four.

    All four are arguments rather than read back off the record, because two of
    them -- the layout and the seed -- are not on it: they are in
    `synthesis.json`, and the caller renaming a page is the caller that has
    them.
    """
    item["parser"] = parser
    item.setdefault("settings", {})["convert_mode"] = parser
    item["filename"] = filename
    # A multi-page record names one image per printed side, and only the caller
    # doing the renaming knows what the others became. Given `source_files`, it
    # says so; left out, this is the single-page rename it always was.
    item["source_files"] = list(source_files) if source_files else [filename]
    # `pages[]` is built in the same order the renderer emitted the sides
    # (`record.build`'s own `sheets=` argument), which is the same order
    # `source_files` names them in -- so page 1 gets `source_files[0]`, page 2
    # `source_files[1]`, and so on by position. Left unset here, a renamed
    # multi-page record would keep the staging name (`html_016_p2.jpg`) on
    # every `pages[i].source_file` after the move, pointing at a file that no
    # longer exists under that name -- a mismatch `source_files` itself
    # never had, because it is written fresh above rather than carried over.
    for page, name in zip(item.get("pages") or [], item["source_files"]):
        page["source_file"] = name
    item["job_id"] = job_id(parser, layout, seed, filename)
    return item


# ------------------------------------------------------------------- checking


def validate(record: dict[str, Any], *, strict: bool = True) -> list[str]:
    """Everything wrong with one record, most important first.

    A key that is *not* in the schema is as wrong as one that is missing.
    That is the whole point of the shape: a line is what a converted page
    looks like, and a generator that quietly appended its own key to it would
    put this repository's business back in a file that is meant to be free of
    it. `strict=False` is kept for a caller checking a record still being
    assembled, and today relaxes nothing else.
    """
    problems: list[str] = []
    for key in sorted(REQUIRED - set(record)):
        problems.append(f"missing key {key!r}")
    for key in sorted(set(record) - REQUIRED):
        problems.append(f"{key!r} is not in the converter's schema; how a page "
                        f"was made belongs in synthesis.json")

    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}, "
                        f"got {record.get('schema_version')!r}")

    name = record.get("filename")
    if name is not None:
        if not isinstance(name, str) or not name:
            problems.append("filename must be a non-empty string")
        elif Path(name).is_absolute() or ".." in Path(name).parts:
            # An absolute path here would make the dataset unmovable, and would
            # differ between two machines that produced identical images.
            problems.append(f"filename must be relative and simple, got {name!r}")
        else:
            # One entry per printed side, page order, and the first is the file
            # this record is named after. A single-page record is the `[name]`
            # this used to demand literally; a document that took three sheets
            # names three images, because `pages[]` has carried a page number
            # since schema 1 and nothing else says which image is page 3.
            sources = record.get("source_files")
            pages = record.get("pages")
            if not isinstance(sources, list) or not sources or sources[0] != name:
                problems.append("source_files must start with filename")
            elif not all(isinstance(item, str) and item for item in sources):
                problems.append("source_files must be non-empty strings")
            elif isinstance(pages, list) and len(pages) != len(sources):
                problems.append(
                    f"source_files names {len(sources)} image(s) but pages has "
                    f"{len(pages)} — one file per printed side")

    pages = record.get("pages")
    if pages is not None:
        # One entry per printed side, numbered from 1 without a gap. It used to
        # be "exactly one", which was true of every page this repository drew
        # and not of the schema: `pages[]` is the converter's own list, and a
        # document that needs two sheets of A4 is two entries in it rather than
        # one sheet twice as tall (see `sheets/base.py::page_order`).
        if not isinstance(pages, list) or not pages:
            problems.append("pages must hold at least one page")
        else:
            for position, page in enumerate(pages):
                missing = {"page_number", "width", "height"} - set(page or {})
                if missing:
                    problems.append(
                        f"pages[{position}] needs {', '.join(sorted(missing))}")
                    break
                if not (int(page["width"]) > 0 and int(page["height"]) > 0):
                    problems.append(
                        f"pages[{position}] has no size, so no bbox can be checked")
                    break
                if int(page["page_number"]) != position + 1:
                    problems.append(
                        f"pages[{position}].page_number is "
                        f"{page['page_number']!r}; pages are numbered from 1 in "
                        "print order")
                    break

    if not record.get("parser"):
        problems.append("parser is empty; nothing said which renderer drew it")

    # `settings` was described as exact and never checked, which is how
    # `max_pixels` drifted: it held the page's own pixel count until `dabf19f`
    # made it null -- it is a *cap*, none was applied, and the size is already
    # in `pages[0]` -- and 295 already-written records kept the old value. The
    # data then described a cap the generator had stopped applying, and nothing
    # said so. Checked here rather than described in a comment, so the next
    # option to move takes the records with it or fails loudly.
    settings = record.get("settings")
    if settings is not None:
        if not isinstance(settings, dict):
            problems.append("settings must be an object")
        else:
            for key in sorted(set(BASE_SETTINGS) - set(settings)):
                problems.append(f"settings is missing {key!r}")
            for key in sorted(set(settings) - set(BASE_SETTINGS)):
                problems.append(f"settings.{key} is not one of the converter's "
                                f"job options")
            for key, value in BASE_SETTINGS.items():
                if key in PER_PAGE_SETTINGS or key not in settings:
                    continue
                # Type as well as value: `False` and `0` compare equal in
                # Python, and a record that said `end2end: 0` would be a record
                # written by something that did not know it was a flag.
                if settings[key] != value or type(settings[key]) is not type(value):
                    problems.append(f"settings.{key} must be {value!r}, "
                                    f"got {settings[key]!r}")
            if "convert_mode" in settings:
                mode, drew = settings["convert_mode"], record.get("parser")
                if mode != drew:
                    problems.append(f"settings.convert_mode must be the parser "
                                    f"{drew!r}, got {mode!r}")

    # A drawn document page carries a nested label; a table image does not, and
    # `generators/html/tables.py` says so with its own `task`. Asking a table
    # for a `total` it has no notion of is how a shared envelope turns into a
    # lie, so the two are checked for different things.
    if record.get("task") == TASK_CONVERT:
        value = record.get("extracted")
        if not isinstance(value, dict) or not value:
            problems.append("extracted must be the nested label, as an object")

    blocks = record.get("blocks")
    if blocks is not None:
        if not isinstance(blocks, list):
            problems.append("blocks must be a list")
        else:
            for position, block in enumerate(blocks):
                wanted = {"id", "page_number", "index_in_page", "label", "bbox",
                          "content", "kind", "text", "quad"}
                if not isinstance(block, dict) or wanted - set(block):
                    problems.append(
                        f"blocks[{position}] needs {', '.join(sorted(wanted))}")
                    break
                quad = block["quad"]
                if not isinstance(quad, list) or len(quad) != 4:
                    problems.append(f"blocks[{position}].quad must be four corners")
                    break
                if set(block["bbox"] or {}) != {"x1", "y1", "x2", "y2"}:
                    problems.append(f"blocks[{position}].bbox needs x1, y1, x2, y2")
                    break

    word_annotations = record.get("word_annotations")
    if word_annotations is not None:
        if not isinstance(word_annotations, list):
            problems.append("word_annotations must be a list")
        else:
            wanted = {"word_index", "text", "layout_region_index", "layout_class",
                     "field_role", "field_path", "relation_path", "field_pattern",
                     "field_name", "bbox", "bbox_mode", "bbox_strategy", "polygon",
                     "ink"}
            for position, word in enumerate(word_annotations):
                if not isinstance(word, dict) or wanted - set(word):
                    problems.append(
                        f"word_annotations[{position}] needs {', '.join(sorted(wanted))}")
                    break
                if word["ink"] not in INK_VALUES:
                    problems.append(
                        f"word_annotations[{position}].ink must be one of "
                        f"{', '.join(sorted(INK_VALUES))}")
                    break
                if word["field_role"] not in ("key", "value", "unbound"):
                    problems.append(
                        f"word_annotations[{position}].field_role must be key/value/unbound")
                    break

    entity_annotations = record.get("entity_annotations")
    if entity_annotations is not None:
        if not isinstance(entity_annotations, list):
            problems.append("entity_annotations must be a list")
        else:
            wanted = {"entity_index", "text", "kind", "layout_class", "field_role",
                      "ink", "word_indices", "bbox", "bbox_mode", "bbox_strategy",
                      "lines", "key_entity_index", "key_source", "field_name",
                      "description", "description_source"}
            words_total = len(record.get("word_annotations") or [])
            for position, entity in enumerate(entity_annotations):
                if not isinstance(entity, dict) or wanted - set(entity):
                    problems.append(
                        f"entity_annotations[{position}] needs "
                        f"{', '.join(sorted(wanted))}")
                    break
                # The one rule this array exists to keep. A WORD may be
                # `unbound` -- "page furniture" is a true thing to say about a
                # word. An entity has somewhere to put the answer instead: a
                # title is the value of "which kind of document is this", with
                # its caption left off the paper. See `entities_from_words`.
                if entity["field_role"] not in ("key", "value"):
                    problems.append(
                        f"entity_annotations[{position}].field_role must be "
                        f"key or value -- an entity is never unbound")
                    break
                if entity["key_source"] not in ("printed", "declared", "implied"):
                    problems.append(
                        f"entity_annotations[{position}].key_source must be "
                        f"printed, declared or implied")
                    break
                if entity["description_source"] not in kie.DESCRIPTION_SOURCES:
                    problems.append(
                        f"entity_annotations[{position}].description_source must "
                        f"be one of {', '.join(kie.DESCRIPTION_SOURCES)}")
                    break
                if not entity["description"]:
                    problems.append(
                        f"entity_annotations[{position}] has no description; "
                        f"`kie.describe` has four sources and cannot return one")
                    break
                if not isinstance(entity["word_indices"], list) or not entity["word_indices"]:
                    problems.append(
                        f"entity_annotations[{position}].word_indices must name "
                        f"at least one word -- an entity with no ink is a label "
                        f"with no mark")
                    break
                if any(not isinstance(index, int) or not 0 <= index < words_total
                       for index in entity["word_indices"]):
                    problems.append(
                        f"entity_annotations[{position}].word_indices points "
                        f"outside word_annotations")
                    break
                key_index = entity["key_entity_index"]
                if key_index is not None and not (
                        isinstance(key_index, int)
                        and 0 <= key_index < len(entity_annotations)):
                    problems.append(
                        f"entity_annotations[{position}].key_entity_index points "
                        f"outside entity_annotations")
                    break

    layout_annotations = record.get("layout_annotations")
    if layout_annotations is not None:
        if not isinstance(layout_annotations, list):
            problems.append("layout_annotations must be a list")
        else:
            wanted = {"region_index", "tag", "layout_class", "text", "bbox",
                     "bbox_mode", "bbox_strategy", "polygon"}
            for position, region in enumerate(layout_annotations):
                if not isinstance(region, dict) or wanted - set(region):
                    problems.append(
                        f"layout_annotations[{position}] needs {', '.join(sorted(wanted))}")
                    break
                if region["layout_class"] not in DOCSYNTH_LABELS:
                    problems.append(
                        f"layout_annotations[{position}].layout_class "
                        f"{region['layout_class']!r} is not one of the 19 docsynth labels")
                    break

    kie_block = record.get("kie_block")
    if kie_block is not None:
        if not isinstance(kie_block, dict) or {"schema", "pairs"} - set(kie_block):
            problems.append("kie_block needs schema, pairs")
        else:
            schema = kie_block["schema"]
            properties = schema.get("properties") if isinstance(schema, dict) else None
            if (not isinstance(schema, dict) or schema.get("type") != "object"
                    or not isinstance(properties, dict)):
                problems.append("kie_block.schema must be {type: object, properties: {...}}")
                properties = {}
            pairs = kie_block["pairs"]
            if not isinstance(pairs, list):
                problems.append("kie_block.pairs must be a list")
            else:
                wanted = {"field", "key_text", "value_text", "key_bbox", "value_bbox",
                         "description", "description_source"}
                for position, pair in enumerate(pairs):
                    if not isinstance(pair, dict) or wanted - set(pair):
                        problems.append(
                            f"kie_block.pairs[{position}] needs {', '.join(sorted(wanted))}")
                        break
                    if pair["field"] not in properties:
                        problems.append(
                            f"kie_block.pairs[{position}].field {pair['field']!r} is not in "
                            f"kie_block.schema.properties")
                        break
                    if pair["description_source"] not in kie_block.DESCRIPTION_SOURCES:
                        problems.append(
                            f"kie_block.pairs[{position}].description_source must be "
                            f"one of {', '.join(kie_block.DESCRIPTION_SOURCES)}")
                        break
    return problems


def check(record: dict[str, Any], *, strict: bool = True, where: str = "") -> dict[str, Any]:
    """Return the record, or raise naming what is wrong with it."""
    problems = validate(record, strict=strict)
    if problems:
        prefix = f"{where}: " if where else ""
        raise RecordError(prefix + "; ".join(problems))
    return record


# ------------------------------------------------------- the shape before this
#
# `metadata.jsonl` -- one index holding every page, the renderer's own keys, and
# the whole recipe repeated per line -- is what the datasets under `data/` were
# written in before this module followed the converter's schema. Every one of
# them has been brought forward and none is left in the repository, so this is
# here for a set someone generated earlier and kept elsewhere.
#
# It lives in this file rather than in a tool of its own because a record has
# exactly one definition, `build` above, and both callers reach it: a renderer
# with pixels in hand, and this, with an old line in hand. A second module would
# be a second place for that definition to drift to. `python -c "from pipeline
# import record; record.migrate(Path('data/old'))"` is the whole interface.
#
# Nothing here re-renders. Every value is already in the old record, except the
# page size, which the old shape never carried and which is read from the JPEG
# header beside it.


def _jpeg_size(path):
    from pipeline.invariants import jpeg_size  # noqa: PLC0415 -- avoids a cycle

    return jpeg_size(path)


# What a table's cell becomes on the way to a block. `tables.py` writes a cell
# as a list of single-character tokens and a list of quads, because that is what
# the PPStructure label wants; a block wants the word and one quad.
CELL_KIND = "cell"


def framework_of(item: dict, directory: Path) -> str:
    """Which renderer drew it: what the record says, or what the name says.

    A record written by a direct renderer run has no `framework` -- the shard is
    what used to attach it -- but every renderer names its files after itself,
    and `data/hand12/` is a whole set of them.
    """
    named = item.get("framework")
    if named:
        return str(named)
    stem = Path(str(item.get("file_name", ""))).name
    for backend in ("synthdog", "genalog", "html"):
        if stem.startswith(backend + "_"):
            return backend
    return directory.name


def _legacy_page_size(path: Path) -> tuple[int, int]:
    size = _jpeg_size(path)
    if size is None:
        raise SystemExit(f"{path}: cannot read the image size, so no page can be built")
    return size


def convert_page(item: dict, directory: Path) -> tuple[dict, dict]:
    """One drawn document page, old shape to (index line, provenance entry)."""
    name = str(item["file_name"])
    width, height = _legacy_page_size(directory / name)
    parser = framework_of(item, directory)
    recipe = item.get("recipe") or {}
    layout = str(item.get("layout") or "")
    if not layout:
        layout = str(((recipe.get("attributes") or {}).get("layout") or {}).get("id", ""))

    truth = item.get("ground_truth")
    extracted = {}
    if isinstance(truth, str):
        try:
            extracted = json.loads(truth).get("gt_parse") or {}
        except (json.JSONDecodeError, AttributeError):
            extracted = {}

    # Everything the old record carried beside the five renderer keys. It went
    # in additively then and it goes to `synthesis.json` now: `handwriting` is
    # what the checkpoint wrote and what it refused, `cells` and `structure` are
    # the structure half of a template render, and dropping either would lose a
    # label nothing else holds.
    extras = {key: value for key, value in item.items()
              if key not in {"file_name", "ground_truth", "text_sequence",
                             "recipe", "boxes", "framework", "layout"}}
    built = build(
        filename=name, width=width, height=height, parser=parser,
        boxes=item.get("boxes") or [], extracted=extracted,
        seed=recipe.get("seed", ""), layout=layout,
    )
    return built, {"job_id": built["job_id"], "layout": layout, "recipe": recipe,
                   "text_sequence": str(item.get("text_sequence", "")),
                   "extra": extras}


def convert_table(item: dict, directory: Path) -> tuple[dict, dict]:
    """One table image, old shape to new.

    A table's label is its structure, so the HTML *is* the ground truth and goes
    where the converter puts a page's markup. There is no faithful markdown for
    a table with merged cells, so `markdown` is left empty rather than filled
    with something a reader would have to un-guess. The border style is in the
    file name, which is where `tables.py` put it, and it is the nearest thing a
    table has to a layout.
    """
    name = str(item["file_name"])
    width, height = _legacy_page_size(directory / name)
    border = Path(name).stem.rsplit("_", 1)[0]
    boxes = []
    for cell in item.get("cells") or []:
        quads = cell.get("bbox") or []
        boxes.append({
            "kind": CELL_KIND,
            "text": "".join(cell.get("tokens") or []),
            "quad": quads[0] if quads else None,
        })
    built = build(
        filename=name, width=width, height=height, parser="html",
        boxes=boxes, extracted=None, task=TASK_TABLE, layout=border,
    )
    built["html"] = str(item.get("ground_truth", ""))
    built["markdown"] = ""
    return built, {"job_id": built["job_id"], "layout": border,
                   "recipe": {"seed": None, "attributes": {}, "tags": []},
                   "extra": {"n_cells": item.get("n_cells", len(boxes))}}


def table_border(name: str) -> str:
    """A table image's border style, which `tables.py` put in its file name.

    The nearest thing a table has to a layout, and the axis a table set is
    actually reported along -- so it is recovered rather than left blank.
    """
    return Path(name).stem.rsplit("_", 1)[0]


def split_synthesis(item: dict, directory: Path) -> tuple[dict, dict]:
    """A converter-shaped line that still carries its provenance inside it.

    A shape this repository did ship, between moving to the converter's schema
    and moving the provenance out of it. Nothing is read from disk here: every
    value is already in the line, under `synthesis`.
    """
    item = dict(item)
    name = str(item.get("filename", ""))
    inside = item.pop("synthesis", None) or {}
    recipe = inside.pop("recipe", None) or {}
    layout = str(inside.pop("layout", ""))
    extras = {key: value for key, value in inside.items() if key != "framework"}

    if item.get("task") == TASK_TABLE:
        layout = layout or table_border(name)
        # A table's structure tokens and cell boxes are its *label*, and
        # `gt.txt` beside the index is the file that holds them, in the format
        # other tools read. Carried in the record as well while the provenance
        # rode inside it; dropped here, but only once that file is there to
        # point at.
        if (directory / "gt.txt").exists():
            extras.pop("structure_tokens", None)
            extras.pop("cells", None)

    return item, {"job_id": str(item.get("job_id", "")), "layout": layout,
                  "recipe": recipe, "text_sequence": str(inside.get("text_sequence", "")
                                                         or extras.pop("text_sequence", "")),
                  "extra": extras}


def convert(item: dict, directory: Path) -> tuple[dict, dict]:
    if item.get("schema_version") == SCHEMA_VERSION:
        return split_synthesis(item, directory)
    if item.get("task") == TASK_TABLE and "cells" in item:
        return convert_table(item, directory)
    return convert_page(item, directory)


def refresh(record: dict[str, Any]) -> bool:
    """Reset one record's constant job options to the current definition.

    Only the constants: `convert_mode` names the renderer and `extract_fields`
    names the label, and `build` already fills both in per page. Returns whether
    anything moved, so a caller can leave a file it would rewrite byte for byte
    alone.

    A record does not have to be re-rendered to be brought forward when an
    option changes meaning -- `max_pixels` went from the page's own pixel count
    to null and the pixels never moved, only what the record claimed about them.
    That is the whole difference between this and re-drawing the set.
    """
    settings = record.get("settings")
    if not isinstance(settings, dict):
        return False
    moved = False
    for key, value in BASE_SETTINGS.items():
        if key in PER_PAGE_SETTINGS:
            continue
        if (key not in settings or settings[key] != value
                or type(settings[key]) is not type(value)):
            settings[key] = value
            moved = True

    # `word_annotations`/`layout_annotations` are additive: a page drawn
    # before they existed was never wrong, it just has nothing to put there --
    # an empty list is the honest answer, not a re-render.
    for key in ("word_annotations", "entity_annotations", "layout_annotations"):
        if key not in record:
            record[key] = []
            moved = True
    return moved


def migrate(directory: Path | str, *, write: bool = True) -> tuple[int, int]:
    """An older set, brought forward. Returns (pages, sets).

    Two things can be out of date, and a set can have either or both:

    * **the shape** -- one `metadata.jsonl` for a set instead of one record per
      image, with how the page was made mixed into the same line;
    * **a value** -- a record already in the converter's schema, but written
      when one of the constant job options meant something else.

    Neither re-renders anything. Idempotent, which is what makes running it over
    a whole tree safe: a directory with no index and no stale option reports
    zero.
    """
    from pipeline import synthesis  # noqa: PLC0415 -- avoids a cycle

    directory = Path(directory)
    pages = sets = 0
    for index in sorted(directory.rglob("metadata.jsonl")):
        here = index.parent
        lines = [json.loads(line) for line in
                 index.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            continue
        # An index whose lines are ALREADY the converter's schema, with the
        # provenance already beside it, has only the shape of the set out of
        # date: the lines are exploded into a file each and nothing is rebuilt.
        split_only = (lines[0].get("schema_version") == SCHEMA_VERSION
                      and "synthesis" not in lines[0]
                      and synthesis.beside(here).exists())
        built_all: list[dict[str, Any]] = []
        entries: list[tuple[str, dict[str, Any]]] = []
        framework = ""
        for item in lines:
            if split_only:
                built, entry = item, None
            elif (item.get("schema_version") == SCHEMA_VERSION
                    and "synthesis" not in item):
                raise RecordError(
                    f"{index}: the index is already in the converter's schema "
                    f"but carries no provenance, and there is no "
                    f"{synthesis.NAME} beside it -- so how these {len(lines)} "
                    f"pages were made is gone and cannot be rebuilt from here")
            else:
                built, entry = convert(item, here)
            refresh(built)
            name = file_name(built)
            check(built, where=f"{index}:{name}")
            built_all.append(built)
            if entry is not None:
                entries.append((name, entry))
            framework = framework or built["parser"]
        if write:
            for built in built_all:
                write_one(built, here)
            if entries:
                synthesis.write(synthesis.beside(here), framework, entries)
            # Both halves are on disk, so the index is now a second answer to
            # the same question -- and the stale one would still parse.
            index.unlink()
        pages += len(built_all)
        sets += 1

    # Second pass: sets that are already one record per image, but were written
    # when a constant option meant something else. The first pass cannot see
    # them -- it looks for an index, and these have none -- and they are the
    # common case now that every committed set is exploded. A record the first
    # pass just wrote is read back here, does not move, and is not counted.
    touched: set[Path] = set()
    for image in images(directory):
        path = beside(image)
        if not path.exists():
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise RecordError(f"{path}: not readable as JSON -- {error}") from error
        if not refresh(item):
            continue
        check(item, where=str(path))
        if write:
            # `write_one` resolves the record's own `filename` against the
            # directory it is handed, and that name is not always a bare one:
            # `generators/html/tables.py` keeps its pages in `img/` and says so
            # in the record. Handing it `image.parent` would write
            # `img/img/border_0001.json`, so the directory the name is relative
            # *to* is walked back out of the image's path instead.
            depth = len(Path(str(item.get("filename", ""))).parts)
            write_one(item, image.parents[depth - 1])
        pages += 1
        touched.add(image.parent)
    # No double count: a set the first pass handled was written through `build`,
    # so `refresh` finds nothing to move in it and it never reaches `touched`.
    sets += len(touched)
    return pages, sets


# ------------------------------------------------- one file, beside its image

# What a picture is, for the purpose of finding the record next to it. The
# generator writes JPEG; the other two are here because a dataset that arrives
# with PNGs should be readable rather than silently empty.
IMAGES = (".jpg", ".jpeg", ".png")
SUFFIX = ".json"


def beside(image: Path | str) -> Path:
    """The record for one image: the same path, `.json`.

    Not an index and not a subdirectory. A converted page comes back as one
    document about one file, so that is what is written -- `html_000.jpg` and
    `html_000.json`, side by side. It also means the *images* are the listing:
    nothing has to be told which files in a directory are records, and a file
    like `synthesis.json`, which no image is named after, is never mistaken for
    one.
    """
    return Path(image).with_suffix(SUFFIX)


# `page_names`' name for a document's page 2+: the same stem with `_pN` hung
# off it. Matched against `source_files` (never against the name alone,
# below) because a document could legitimately be named ending `_p2` on its
# own -- only the record that actually claims this exact filename makes it a
# continuation of that one.
_CONTINUATION = re.compile(r"_p\d+$")


def _is_continuation(path: Path) -> bool:
    """Whether `path` is a page 2+ side of ANOTHER file's record, per
    `page_names`/`stamp`'s `source_files` -- the one signal that is not a
    guess. See `images`."""
    if not _CONTINUATION.search(path.stem):
        return False
    first = path.with_name(_CONTINUATION.sub("", path.stem) + path.suffix)
    record_path = beside(first)
    if not record_path.exists():
        return False
    try:
        names = json.loads(record_path.read_text(encoding="utf-8")).get("source_files") or []
    except (OSError, json.JSONDecodeError):
        return False
    return path.name in {str(name) for name in names}


def images(directory: Path | str) -> list[Path]:
    """Every image under a dataset directory, in name order -- one per
    DOCUMENT, not one per printed side.

    A multi-page document's page 2+ files (`page_names`'s `_pN` names) carry
    no `.json` of their own: the one record its page 1 carries already names
    every side, through `source_files`, which is where a caller wanting every
    physical file should read them from (`read()` does exactly that). Without
    this filter, `beside(image)` on a page 2+ file a caller reached through
    `images()` finds nothing there -- the bug `tools/proof_boxes.py::pairs`
    hit, and the reason `read()` below carries its own `claimed` tracking as
    a second line of defence.

    Recursive, because `generators/html/tables.py` keeps its pages in `img/`.
    """
    directory = Path(directory)
    found = [path for path in directory.rglob("*")
             if path.suffix.lower() in IMAGES and path.is_file()
             and not _is_continuation(path)]
    return sorted(found, key=lambda path: path.relative_to(directory).as_posix())


def write_one(record: dict[str, Any], directory: Path | str, *,
              strict: bool = True, fsync: bool = False) -> Path:
    """Write one record beside its image, validating on the way out.

    `fsync` is for the shard, which must not write its `DONE` in front of a
    record that is not yet on disk: resume would skip a shard that is short.
    """
    directory = Path(directory)
    name = str(record.get("filename", ""))
    check(record, strict=strict, where=name or "?")
    path = beside(directory / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")
        if fsync:
            handle.flush()
            os.fsync(handle.fileno())
    return path


def write(records: Iterable[dict[str, Any]], directory: Path | str, *,
          strict: bool = True) -> int:
    """Write a record per image. Streamed: nothing is held but the one in hand."""
    written = 0
    for record in records:
        write_one(record, directory, strict=strict)
        written += 1
    return written


def read_one(path: Path | str) -> dict[str, Any]:
    """One record, given its own path or its image's."""
    return json.loads(beside(path).read_text(encoding="utf-8"))


def read(directory: Path | str) -> list[dict[str, Any]]:
    """Every record under a directory, in the order of the images they describe.

    An image with no record beside it stops this rather than being skipped: a
    dataset that is quietly short is the failure the whole shard contract exists
    to prevent, and a loader that shrugs at it moves that failure downstream.

    ONE record per DOCUMENT, not per image. A document printed on two sheets
    (`sheets/base.py::page_order`) writes `html_001.json`, `html_001.jpg` and
    `html_001_p2.jpg` -- the second sheet has no record of its own because it
    is not a second document, and `source_files` on the first is what says so.
    So a continuation image is accounted for by the record that NAMES it, and
    only an image no record names at all is the short dataset this refuses.
    Returned once per record, in image order, because every caller downstream
    walks this list against the job list one page at a time.
    """
    directory = Path(directory)
    out: list[dict[str, Any]] = []
    claimed: set[str] = set()
    for image in images(directory):
        name = image.name
        if name in claimed:
            continue                    # a later sheet of a document already read
        path = beside(image)
        if not path.exists():
            raise RecordError(
                f"{image.relative_to(directory).as_posix()} has no "
                f"{path.name} beside it")
        item = json.loads(path.read_text(encoding="utf-8"))
        claimed.update(str(each) for each in (item.get("source_files") or []))
        out.append(item)
    return out


# ------------------------------------------------------------------ accessors
#
# One place that knows where a value lives. Everything in this repository that
# reads a metadata line goes through these, so the next time the shape moves it
# moves here and nowhere else -- which is the change that made this file worth
# having when three renderers each spelled the same keys by hand.


def file_name(item: dict[str, Any]) -> str:
    return str(item.get("filename", ""))


def source_files(item: dict[str, Any]) -> list[str]:
    """Every image this record describes, print order.

    One name for a single-page document; one per sheet for a document that
    took several (`sheets/base.py::page_order`). Every caller counting IMAGES
    rather than DOCUMENTS wants this, not `file_name` -- counting by
    `file_name` is how a continuation sheet became an unexplained extra file
    and took its whole shard down with it."""
    names = [str(name) for name in (item.get("source_files") or []) if name]
    return names or [file_name(item)]


def boxes(item: dict[str, Any]) -> list[dict[str, Any]]:
    """The blocks, which carry `kind`, `text` and `quad` as the old boxes did."""
    return list(item.get("blocks") or [])


def word_annotations(item: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per word -- see `words_from_boxes`."""
    return list(item.get("word_annotations") or [])


def layout_annotations(item: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per layout region -- see `regions_from_words`."""
    return list(item.get("layout_annotations") or [])


def extracted(item: dict[str, Any]) -> dict[str, Any]:
    """The nested label, as an object."""
    value = item.get("extracted")
    return value if isinstance(value, dict) else {}


def ground_truth(item: dict[str, Any]) -> str:
    """The nested label as the JSON *string* a Donut-style loader reads."""
    return json.dumps({"gt_parse": extracted(item)}, ensure_ascii=False)


def framework(item: dict[str, Any]) -> str:
    """Which renderer drew it. The recipe, the layout and the reading order are
    not here any more -- they are in `synthesis.json`, and
    `pipeline/synthesis.py` reads them by file name."""
    return str(item.get("parser", ""))


def page_size(item: dict[str, Any]) -> tuple[int, int]:
    pages = item.get("pages") or [{}]
    page = pages[0] if pages else {}
    return int(page.get("width", 0) or 0), int(page.get("height", 0) or 0)


__all__ = [
    "BASE_SETTINGS",
    "DEFAULT_LABEL",
    "DOCSYNTH_LABELS",
    "DOCSYNTH_LABEL_FOR_KIND",
    "JOB_NAMESPACE",
    "LABELS",
    "ORDER",
    "PAGE_LABELS",
    "PER_PAGE_SETTINGS",
    "REGIONS",
    "REQUIRED",
    "IMAGES",
    "SCHEMA_VERSION",
    "SUFFIX",
    "TASK_CONVERT",
    "TASK_TABLE",
    "RecordError",
    "bbox_of",
    "beside",
    "blocks_from_boxes",
    "block_content",
    "boxes",
    "build",
    "check",
    "extracted",
    "field_paths",
    "file_name",
    "framework",
    "ground_truth",
    "html_of",
    "images",
    "job_id",
    "label_for",
    "layout_annotations",
    "layout_class_for",
    "markdown_of",
    "migrate",
    "page_size",
    "read",
    "read_one",
    "refresh",
    "GRAPHIC_LABEL",
    "STAMP_LABEL",
    "graphic_label",
    "INK_FOR_KIND",
    "INK_VALUES",
    "ink_for",
    "regions_from_words",
    "stamp",
    "rows",
    "validate",
    "word_annotations",
    "words_from_boxes",
    "write",
    "write_one",
]
