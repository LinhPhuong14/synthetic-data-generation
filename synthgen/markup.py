"""`Doc` + `Design` -> HTML. Mọi chữ in ra nằm trong một `<span data-kind>`.

Hợp đồng nhãn, chép lại từ `generators/html/page.py` vì nó là thứ quyết định
hộp có đúng hay không, và ở đây nó phải đúng y như thế:

* mỗi dòng chữ đo được là MỘT `<span data-kind="...">` chứa **đúng một nút
  văn bản** -- không thẻ con, không `<b>`, không `<sub>`. Đo lấy
  `span.firstElementChild || span`, nên một thẻ lồng bên trong sẽ lặng lẽ trở
  thành cái hộp được ghi lại;
* muốn đậm/nghiêng/màu thì đặt lên CHÍNH cái span ấy bằng CSS, không bọc thêm;
* không chuỗi nào được mang ký tự `<` -- `_t()` escape hết, và đó là hàng rào
  duy nhất cần có.

Nhãn khoá–giá trị (KIE) dựa vào THỨ TỰ DOM: `pipeline/kie.py::pair_fields` ghép
một block có `data-kind` kết thúc bằng `.label` với block ngay sau nó. Nên mọi
cặp khoá:giá trị ở đây phải in liền nhau, khoá trước giá trị sau, không chèn gì
vào giữa.

`markup()` nhận `slices` -- mỗi phần tử là lát dòng hàng của MỘT tờ giấy. Một
tờ là `[(0, n)]`; hai tờ là `[(0, k), (k, n)]`, và chỉ bảng hàng được lặp lại
qua các tờ. `paginate.py` quyết định các lát ấy sau khi ĐO trong trình duyệt.
"""

from __future__ import annotations

import html as _html
from pathlib import Path

from synthgen.content import Doc, fmt_date
from synthgen.design import COLUMNS, Design

REPO_ROOT = Path(__file__).resolve().parents[1]

NATIONAL_1 = "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"
NATIONAL_2 = "Độc lập - Tự do - Hạnh phúc"


def _t(text) -> str:
    """Chữ đưa vào HTML. Escape luôn, không có đường vòng."""
    return _html.escape(str(text), quote=True)


def _span(kind: str, text, cls: str = "", role: str = "", key: str = "") -> str:
    """Một dòng chữ đo được. Rỗng thì không in gì -- một span rỗng là một hộp
    không có chữ, và nhãn của nó sẽ mô tả khoảng trắng."""
    text = "" if text is None else str(text)
    if not text.strip():
        return ""
    attrs = [f'data-kind="{_t(kind)}"']
    if cls:
        attrs.append(f'class="{_t(cls)}"')
    if role:
        attrs.append(f'data-role="{_t(role)}"')
    if key:
        attrs.append(f'data-key="{_t(key)}"')
    return f"<span {' '.join(attrs)}>{_t(text)}</span>"


# --------------------------------------------------------------------- CSS


def _px(pt: float) -> str:
    return f"{pt:.2f}pt"


def stylesheet(d: Design, faces: str) -> str:
    p, pal, f = d.paper, d.palette, d.face
    top, right, bottom, left = d.margins
    base_pt = d.base_pt * d.boost
    gap = (2.2 if d.compact_rows else 3.4) * d.boost
    rule = f"{d.rule_px:.2f}mm"
    track = f"{d.tracking:.2f}pt" if d.tracking else "normal"

    frame = d.table_frame
    cell_border = {
        "khung_day_du": f"border:{rule} solid {pal.rule};",
        "khung_day_du_van": f"border:{rule} solid {pal.rule};",
        "chi_ke_ngang": f"border-bottom:{rule} solid {pal.rule};",
        "ke_ngang_dam_dau": f"border-bottom:{rule} solid {pal.rule};",
        "chi_ke_doc": f"border-left:{rule} solid {pal.rule};border-right:{rule} solid {pal.rule};",
        "vien_ngoai": "",
        "khong_ke": "",
    }[frame]
    table_border = {
        "vien_ngoai": f"border:{d.rule_px * 1.6:.2f}mm solid {pal.rule};",
        "khung_day_du_van": f"border:{d.rule_px * 2.0:.2f}mm solid {pal.rule};",
        "ke_ngang_dam_dau": f"border-top:{d.rule_px * 2.0:.2f}mm solid {pal.rule};"
                            f"border-bottom:{d.rule_px * 2.0:.2f}mm solid {pal.rule};",
    }.get(frame, "")

    head_fill = {
        "dai_mau": f"background:{pal.band_bg};color:{pal.band_fg};",
        "nen_nhat": f"background:{pal.zebra};color:{pal.strong};",
        "khong_nen": f"color:{pal.strong};",
        "gach_doi": f"color:{pal.strong};border-bottom:{d.rule_px * 2.4:.2f}mm double {pal.rule};",
        "chu_dam_gach": f"color:{pal.strong};border-bottom:{d.rule_px * 2:.2f}mm solid {pal.accent};",
    }[d.header_fill]

    title_css = {
        "hoa_dam_giua": "text-align:center;text-transform:uppercase;font-weight:700;",
        "hoa_dam_trai": "text-align:left;text-transform:uppercase;font-weight:700;",
        "hoa_vien_duoi": (f"text-align:center;text-transform:uppercase;font-weight:700;"
                          f"border-bottom:{d.rule_px * 2:.2f}mm solid {pal.accent};"
                          "padding-bottom:1.6mm;"),
        "hoa_trong_khung": (f"text-align:center;text-transform:uppercase;font-weight:700;"
                            f"border:{d.rule_px * 1.6:.2f}mm solid {pal.accent};"
                            "padding:2mm 3mm;"),
        "hoa_gian_chu": ("text-align:center;text-transform:uppercase;font-weight:700;"
                         "letter-spacing:1.6pt;"),
        "thuong_dam_giua": "text-align:center;font-weight:700;",
        "hoa_dam_gach_ngan": "text-align:center;text-transform:uppercase;font-weight:700;",
        "hoa_dam_nen_nhat": (f"text-align:center;text-transform:uppercase;font-weight:700;"
                             f"background:{pal.zebra};padding:1.8mm 2mm;"),
        "hoa_dam_hai_dong": ("text-align:center;text-transform:uppercase;font-weight:700;"
                             "line-height:1.15;"),
    }[d.title_style]
    if d.reverse_title_band:
        title_css += f"background:{pal.accent};color:#ffffff;padding:2mm 3mm;"

    row_pad = "0.5mm 1.2mm" if d.compact_rows else "1.1mm 1.6mm"
    zebra = (f".items tbody tr:nth-child(even) td{{background:{pal.zebra};}}"
             if d.zebra else "")

    return f"""
{faces}
*{{box-sizing:border-box;}}
body{{margin:0;background:#8f8f8f;}}
.sheet{{
  width:{p.w}mm; min-height:{p.h}mm;
  padding:{top}mm {right}mm {bottom}mm {left}mm;
  background:{pal.paper}; color:{pal.ink};
  font-family:{f.body}; font-size:{_px(base_pt)}; line-height:{d.leading};
  letter-spacing:{track};
  position:relative;
  margin:0 auto 6mm;
}}
.blk{{margin:0 0 {gap:.2f}mm;}}
.blk:last-child{{margin-bottom:0;}}

/* ---- letterhead */
.head{{width:100%;}}
.head .org{{display:block;font-family:{f.head};font-weight:700;
  font-size:{_px(base_pt * 1.22)};color:{pal.accent};line-height:1.2;}}
.head .parent{{display:block;font-size:{_px(base_pt * 0.9)};color:{pal.soft};
  text-transform:uppercase;letter-spacing:0.4pt;}}
.head .line{{display:block;font-size:{_px(base_pt * 0.92)};color:{pal.ink};}}
.head .lbl{{color:{pal.soft};}}
.head.center{{text-align:center;}}
.head.right{{text-align:right;}}
.head.boxed{{border:{rule} solid {pal.rule};padding:2.4mm 3mm;}}
.head.band{{background:{pal.band_bg};color:{pal.band_fg};padding:2.6mm 3mm;}}
.head.band .org,.head.band .line,.head.band .parent{{color:{pal.band_fg};}}
.hrow{{display:table;width:100%;}}
.hcell{{display:table-cell;vertical-align:top;}}
.hcell.r{{text-align:center;}}
.logo{{display:inline-block;width:16mm;height:16mm;border-radius:50%;
  background:{pal.accent};opacity:.14;vertical-align:middle;margin-right:3mm;}}
.logo.sq{{border-radius:1mm;}}
.headrule{{border-bottom:{d.rule_px * 1.8:.2f}mm solid {pal.accent};
  margin-top:2mm;}}

/* ---- quốc hiệu */
.natl{{text-align:center;}}
.natl .n1{{display:block;font-weight:700;font-size:{_px(base_pt * 1.0)};
  text-transform:uppercase;}}
.natl .n2{{display:block;font-weight:700;font-size:{_px(base_pt * 1.02)};}}
.natl .nr{{width:34mm;border-top:{rule} solid {pal.ink};margin:1mm auto 0;}}

/* ---- tiêu đề */
.title{{{title_css}}}
.title .t{{display:block;font-family:{f.head};
  font-size:{_px(base_pt * 1.75)};line-height:1.18;}}
.title .s{{display:block;font-weight:400;text-transform:none;
  font-size:{_px(base_pt * 0.94)};color:{pal.soft};margin-top:1mm;
  letter-spacing:normal;}}
.trule{{width:30mm;border-top:{d.rule_px * 1.6:.2f}mm solid {pal.accent};
  margin:1.6mm auto 0;}}

/* ---- dải meta */
.meta{{font-size:{_px(base_pt * 0.94)};}}
.meta.center{{text-align:center;}}
.meta.right{{text-align:right;}}
.meta.boxed{{border:{rule} solid {pal.rule};padding:1.8mm 2.4mm;
  display:inline-block;}}
.meta.band{{border-top:{rule} solid {pal.rule};
  border-bottom:{rule} solid {pal.rule};padding:1.4mm 0;}}
.meta .m{{display:inline-block;margin-right:6mm;}}
.meta .k{{color:{pal.soft};}}
.mcols{{display:table;width:100%;}}
.mcol{{display:table-cell;width:50%;vertical-align:top;}}
.mcol.r{{text-align:right;}}

/* ---- trường khoá:giá trị */
.fields{{width:100%;}}
.frow{{margin-bottom:{1.0 if d.compact_rows else 1.7}mm;}}
.fgrid{{display:table;width:100%;border-spacing:0;}}
.fcell{{display:table-cell;vertical-align:top;padding-right:5mm;
  padding-bottom:{1.0 if d.compact_rows else 1.7}mm;}}
.fields .k{{color:{pal.ink};}}
.fields .kb{{font-weight:700;}}
.fields .v{{color:{pal.ink};}}
.fields .dots{{border-bottom:{d.rule_px * 0.8:.2f}mm dotted {pal.rule};
  display:inline-block;min-width:18mm;}}
.fields .ul{{border-bottom:{d.rule_px * 0.8:.2f}mm solid {pal.rule};
  display:inline-block;min-width:20mm;}}
.fields .stack .k{{display:block;font-weight:700;
  font-size:{_px(base_pt * 0.88)};color:{pal.soft};
  text-transform:uppercase;letter-spacing:0.3pt;}}
.fields .stack .v{{display:block;}}

/* ---- ô đánh dấu */
.checks .q{{display:block;margin-bottom:0.8mm;}}
.checks .a{{display:block;margin-bottom:{1.4 if d.compact_rows else 2.2}mm;
  color:{pal.ink};}}

/* ---- bảng hàng */
.tcap{{display:block;font-weight:700;text-align:center;
  text-transform:uppercase;margin-bottom:1.6mm;
  font-size:{_px(base_pt * 0.98)};}}
table.items{{width:100%;border-collapse:collapse;table-layout:fixed;
  {table_border}}}
table.items th,table.items td{{{cell_border}padding:{row_pad};
  vertical-align:top;word-wrap:break-word;overflow-wrap:anywhere;}}
table.items thead th{{{head_fill}font-weight:700;text-align:center;
  font-size:{_px(base_pt * 0.94)};}}
{zebra}
.al{{text-align:left;}} .ac{{text-align:center;}} .ar{{text-align:right;}}
table.items td span{{display:inline;}}

/* ---- bảng phức: tiêu đề hai tầng, hàng số cột, dòng phân mục, cột gom */
table.items thead tr.tier2 th{{font-size:{_px(base_pt * 0.9)};}}
table.items thead tr.tier3 th{{font-size:{_px(base_pt * 0.88)};}}
table.items tr.colnum th{{text-align:center;font-style:italic;
  font-weight:400;font-size:{_px(base_pt * 0.82)};}}
table.items tr.grouphdr td{{font-weight:700;text-align:left;
  {head_fill}font-size:{_px(base_pt * 0.94)};}}
table.items tr.grouptot td{{font-weight:700;
  border-top:{max(d.rule_px, 0.8):.2f}pt solid {pal.rule};}}
table.items td.rail{{text-align:center;vertical-align:middle;font-weight:700;
  word-wrap:normal;overflow-wrap:normal;hyphens:none;line-height:1.25;
  font-size:{_px(base_pt * 0.86)};{head_fill}}}
table.items table.sub{{width:100%;border-collapse:collapse;
  margin-top:0.8mm;font-size:{_px(base_pt * 0.84)};}}
table.items table.sub td{{border:none;padding:0 0 0 3mm;
  color:{pal.soft};}}

/* ---- tổng */
.totals{{width:100%;}}
.totals .trow{{display:table;width:100%;}}
.totals .tk{{display:table-cell;text-align:right;padding-right:4mm;
  color:{pal.ink};}}
.totals .tv{{display:table-cell;width:34%;text-align:right;font-weight:700;}}
.totals.boxed{{border:{rule} solid {pal.rule};padding:2mm 2.6mm;}}
.totals .grand .tk{{font-weight:700;text-transform:uppercase;
  color:{pal.accent};}}
.totals .grand .tv{{font-size:{_px(base_pt * 1.18)};color:{pal.accent};}}
.totals .grand{{border-top:{d.rule_px * 1.6:.2f}mm solid {pal.rule};
  padding-top:1.4mm;margin-top:1.4mm;}}
.words .wk{{color:{pal.soft};}}
.words .wv{{font-style:italic;}}

/* ---- bảng tóm tắt thuế */
.summary{{width:100%;border-collapse:collapse;}}
.summary td{{border:{rule} solid {pal.rule};padding:1.2mm 2mm;}}
.summary td.k{{color:{pal.soft};width:58%;}}
.summary td.v{{text-align:right;font-weight:700;}}

/* ---- ghi chú */
.notes{{font-size:{_px(base_pt * 0.94)};color:{pal.ink};}}
.notes .n{{display:block;margin-bottom:1.4mm;text-align:justify;}}
.notes.boxed{{border:{rule} solid {pal.rule};padding:2mm 2.6mm;}}
.notes.small .n{{font-size:{_px(base_pt * 0.86)};font-style:italic;
  color:{pal.soft};}}
.notes.two{{column-count:2;column-gap:6mm;}}

/* ---- chữ ký */
.signs{{display:table;width:100%;margin-top:2mm;}}
.scell{{display:table-cell;text-align:center;vertical-align:top;
  padding:0 2mm;}}
.scell .cap{{display:block;font-weight:700;text-transform:uppercase;
  font-size:{_px(base_pt * 0.94)};}}
.scell .hint{{display:block;font-style:italic;color:{pal.soft};
  font-size:{_px(base_pt * 0.84)};margin-top:0.6mm;}}
.scell .who{{display:block;margin-top:{16 if not d.compact_rows else 12}mm;
  font-weight:700;}}
.signs.boxed .scell{{border:{rule} solid {pal.rule};padding:2mm;}}
.signs.ruled .scell .who{{border-top:{rule} solid {pal.rule};
  padding-top:1mm;margin-top:{14 if not d.compact_rows else 10}mm;}}
.signs.right{{margin-left:auto;width:52%;}}
.sdate{{display:block;text-align:right;font-style:italic;
  margin-bottom:1.4mm;}}

/* ---- chân trang */
/* Dòng tổng nằm trong `<tfoot>` của chính bảng hàng. */
.items tfoot td{{border-top:{d.rule_px * 1.6:.2f}mm solid {pal.rule};
  font-weight:600;}}
.items tfoot tr.grand td{{font-size:{_px(base_pt * 1.06)};color:{pal.accent};
  border-top:{d.rule_px * 2.2:.2f}mm double {pal.rule};}}
/* Ô hẹp hơn nội dung: thu chữ lại thay vì ngắt con số làm đôi -- xem `_fit`.
   Phải đứng SAU luật `tfoot tr.grand td` và phải cùng độ ưu tiên với nó, nếu
   không thì dòng tổng cộng -- đúng cái dòng có chuỗi dài nhất tờ giấy -- là
   dòng duy nhất không thu được. Lỗi ấy đã xảy ra: lớp có gắn, chữ không nhỏ. */
table.items tbody td.tight,table.items tfoot td.tight{{
  font-size:{_px(base_pt * 0.88)};letter-spacing:-0.01em;}}
table.items tbody td.tighter,table.items tfoot td.tighter{{
  font-size:{_px(base_pt * 0.76)};letter-spacing:-0.02em;}}
table.items tbody td.tightest,table.items tfoot td.tightest{{
  font-size:{_px(base_pt * 0.62)};letter-spacing:-0.03em;}}
.foot{{border-top:{rule} solid {pal.rule};padding-top:1.4mm;
  font-size:{_px(base_pt * 0.84)};color:{pal.soft};text-align:center;}}

/* ---- hoa văn */
.sealhost{{position:relative;height:0;}}
/* Con dấu là một tấm ảnh đã cắt sát nét mực (`seal_art`), nên hộp trình duyệt
   đo được chính là đường ngoài của dấu. Xoay NHẸ: bản trước xoay 14 độ và một
   con dấu chữ nhật xoay chừng ấy đọc ra hình thoi, không ra con dấu. */
.seal{{position:absolute;opacity:.78;transform:rotate(-4deg);}}
.barcode{{display:block;height:9mm;
  background:repeating-linear-gradient(90deg,{pal.ink} 0 0.35mm,
    transparent 0.35mm 0.7mm,{pal.ink} 0.7mm 1.2mm,transparent 1.2mm 1.9mm);
  margin-bottom:0.8mm;}}
.qr{{display:block;width:16mm;height:16mm;
  background:repeating-conic-gradient({pal.ink} 0 25%,transparent 0 50%)
    0 0/3.2mm 3.2mm;}}
.mark{{text-align:center;font-size:{_px(base_pt * 0.8)};
  color:{pal.soft};}}
.markbox{{position:absolute;right:{right}mm;}}
/* Chữ chìm. Hộp đo trên `.wtext` chứ không trên `.wmark`: `.wmark` rộng 36%
   bề ngang tờ giấy dù chữ trong nó ngắn hơn nhiều, nên hộp cũ bao cả một vùng
   giấy trắng hai bên -- một mô hình học trên hộp ấy học rằng "chữ chìm" là một
   mảng giấy, không phải một dòng chữ. `inline-block` co sát chữ, và
   `getBoundingClientRect` của phần tử đã xoay trả đúng hộp thẳng trục của chữ
   đã xoay. */
.wmark{{position:absolute;top:46%;left:32%;width:36%;text-align:center;
  transform:rotate(-24deg);pointer-events:none;}}
.wtext{{display:inline-block;font-size:{_px(base_pt * 2.1)};
  color:{pal.accent};opacity:.09;font-weight:700;white-space:nowrap;}}
/* Sáu khối không-phải-bảng. Mỗi khối tự khai vùng bằng `data-region`, nên
   hộp của nó là hộp của chính phần tử chứ không phải hợp của mấy mẩu chữ. */
.basis .lb{{margin-bottom:0.5mm;font-style:italic;}}
.clauses .cl{{margin-bottom:{gap * 0.5:.2f}mm;}}
.clauses .ch{{display:block;font-weight:700;}}
.clauses .cb{{display:block;text-align:justify;}}
.fml{{text-align:center;margin:{gap * 0.4:.2f}mm 0;
  padding:{gap * 0.35:.2f}mm 0;border-top:{rule} solid {pal.rule};
  border-bottom:{rule} solid {pal.rule};font-style:italic;}}
.fig{{display:flex;gap:3mm;justify-content:center;align-items:flex-end;
  height:26mm;margin-bottom:1mm;}}
.fig .fbox{{display:block;width:16mm;border:{rule} solid {pal.rule};
  background:{pal.zebra};}}
.fig .fbox:nth-child(1){{height:60%;}}
.fig .fbox:nth-child(2){{height:100%;}}
.fig .fbox:nth-child(3){{height:78%;}}
.fcap{{text-align:center;font-size:{_px(base_pt * 0.86)};color:{pal.soft};
  font-style:italic;margin-bottom:{gap * 0.4:.2f}mm;}}
.fnotes{{margin-top:{gap * 0.4:.2f}mm;font-size:{_px(base_pt * 0.82)};
  color:{pal.soft};}}
.toc .tocrow{{display:flex;align-items:baseline;gap:1.5mm;
  margin-bottom:0.4mm;}}
.toc .dots{{flex:1;border-bottom:{rule} dotted {pal.rule};}}

/* Bảng câu hỏi. Dòng kẻ dưới câu trả lời là `border-bottom` của chính ô chứa
   nó, không phải một hàng dấu chấm: người ta viết ĐÈ lên dòng kẻ, và một dòng
   chấm sẽ chạy qua nét chữ. */
.survey .qitem{{margin-bottom:{1.3 if d.compact_rows else 2.1}mm;}}
.survey .qq{{display:flex;gap:1.6mm;align-items:baseline;}}
.survey .qn{{font-weight:700;}}
.survey .qopts{{display:flex;flex-wrap:wrap;gap:1.2mm 5mm;
  margin:0.6mm 0 0 5mm;}}
.survey .opt{{display:inline-flex;gap:1.2mm;align-items:baseline;
  min-width:26mm;}}
.survey .tk{{font-size:{_px(base_pt * 1.05)};}}
.survey .qsub{{margin-left:5mm;font-style:italic;color:{pal.soft};}}
.survey .qans{{margin:0.4mm 0 0 5mm;border-bottom:{rule} solid {pal.rule};
  min-height:{_px(base_pt * 1.25)};}}
/* Trang nhiều cột. `break-inside:avoid` trên `.blk` là dòng quan trọng nhất
   ở đây: không có nó, trình duyệt cắt một khối làm đôi giữa hai cột, và cái
   hộp đo được của khối ấy trùm cả hai cột lẫn khoảng trắng giữa chúng -- một
   cái hộp không tả được thứ gì trên giấy. */
.cols{{column-count:{d.page_columns};column-gap:{max(d.margins[1] * 0.5, 5):.1f}mm;
  column-fill:balance;}}
.cols .blk{{break-inside:avoid;}}
.cols table{{width:100%;}}
.photo{{float:right;width:26mm;height:34mm;border:{rule} solid {pal.rule};
  margin:0 0 2mm 3mm;text-align:center;padding-top:14mm;color:{pal.soft};
  font-size:{_px(base_pt * 0.8)};}}
/* Số trang. Góc phải cuối tờ, kiểu chứng từ hành chính vẫn in. */
.pgnum{{clear:both;text-align:right;padding-top:2.2mm;
  font-size:{_px(base_pt * 0.8)};color:{pal.soft};}}
.clr{{clear:both;}}
"""


# ------------------------------------------------------------------ khối


def _letterhead(doc: Doc, d: Design) -> str:
    if d.head_layout == "khong_letterhead":
        return ""
    logo = d.head_layout.endswith("co_logo")
    lines = []
    if doc.parent_org:
        lines.append(_span("store.branch", doc.parent_org, "parent"))
    lines.append(_span("store.name", doc.org_name, "org"))
    if doc.org_branch:
        lines.append(_span("store.branch", doc.org_branch, "line"))
    lines.append(_span("store.address.label", "Địa chỉ:", "lbl", role="key"))
    lines.append(_span("store.address", doc.org_address, "line", role="value"))
    lines.append(_span("store.phone.label", "Điện thoại:", "lbl", role="key"))
    lines.append(_span("store.phone", doc.org_phone, "line", role="value"))
    lines.append(_span("store.tax_code.label", "Mã số thuế:", "lbl", role="key"))
    lines.append(_span("store.tax_code", doc.org_tax, "line", role="value"))
    if doc.org_website:
        lines.append(_span("store.website", doc.org_website, "line"))
    body = "".join(lines)
    logo_html = f'<span class="logo{"" if d.ornament != "dau_vuong" else " sq"}"></span>' if logo else ""

    cls = "head"
    if d.head_layout in ("giua", "giua_co_logo"):
        cls += " center"
    if d.head_layout == "khung_vien":
        cls += " boxed"
    if d.head_layout == "dai_mau":
        cls += " band"

    if d.head_layout in ("chia_doi", "chia_doi_co_logo", "hai_cot_cach"):
        right = ""
        if doc.design.archetype.org_kind in ("state", "hospital"):
            # `masthead`, giống hệt `_national` ở dưới. Quốc hiệu in ở HAI
            # chỗ -- ở đây khi letterhead chia đôi, ở `_national` khi không --
            # và lần sửa trước chỉ đổi một chỗ, nên nửa số tờ giấy nhà nước vẫn
            # ra hai vùng `Title`. Một chuỗi in ở hai nhánh là hai lần phải nhớ.
            right = (f'<div class="natl">{_span("masthead", NATIONAL_1, "n1")}'
                     f'{_span("masthead.motto", NATIONAL_2, "n2")}'
                     f'<div class="nr"></div></div>')
        elif not d.has("meta"):
            right = (f'<div class="natl">'
                     f'{_span("meta.label", "Số:", "n2", role="key")}'
                     f'{_span("meta.value", doc.doc_no, "n2", role="value")}</div>')
        return (f'<div class="blk"><div class="hrow">'
                f'<div class="hcell head" style="width:56%">{logo_html}{body}</div>'
                f'<div class="hcell r">{right}</div></div></div>')

    if d.head_layout == "logo_phai":
        return (f'<div class="blk"><div class="hrow">'
                f'<div class="hcell head">{body}</div>'
                f'<div class="hcell r" style="width:22%">{logo_html}</div>'
                f'</div></div>')

    rule = '<div class="headrule"></div>' if d.head_layout != "dai_mau" else ""
    return f'<div class="blk"><div class="{cls}">{logo_html}{body}</div>{rule}</div>'


def _national(doc: Doc, d: Design) -> str:
    if d.head_layout in ("chia_doi", "chia_doi_co_logo", "hai_cot_cach"):
        return ""      # đã in bên phải letterhead
    # `masthead` / `masthead.motto`, KHÔNG phải `title` / `subtitle`. Dùng
    # chung `kind` với tiêu đề tài liệu là nói rằng quốc hiệu và tên chứng từ
    # là cùng một loại chữ -- một trang ra hai `Title`, và không cái nào trả
    # lời được "tờ này là giấy gì". Đây cũng đúng hai `kind`
    # `generators/html/sheets/form.py::_govt_masthead` đã dùng, nên hai bộ sinh
    # nói cùng một từ vựng thay vì mỗi bên một kiểu.
    return (f'<div class="blk"><div class="natl">'
            f'{_span("masthead", NATIONAL_1, "n1")}'
            f'{_span("masthead.motto", NATIONAL_2, "n2")}'
            f'<div class="nr"></div></div></div>')


def _doctitle(doc: Doc, d: Design) -> str:
    parts = [_span("title", doc.title, "t", key="loai_chung_tu")]
    if doc.subtitle:
        parts.append(_span("subtitle", doc.subtitle, "s"))
    rule = '<div class="trule"></div>' if d.title_style == "hoa_dam_gach_ngan" else ""
    return f'<div class="blk"><div class="title">{"".join(parts)}</div>{rule}</div>'


def _meta(doc: Doc, d: Design) -> str:
    if d.meta_style == "khong_co":
        return ""
    items = [("Số:", doc.doc_no), ("Ký hiệu:", doc.doc_serial)]
    if doc.design.archetype.profile in ("invoice", "export", "power", "water"):
        items.append(("Mẫu số:", doc.doc_form))
    place = f"{doc.issued_place}, {fmt_date(doc.issued_date, 1)}"

    def pair(label, value):
        return (f'<span class="m">{_span("meta.label", label, "k", role="key")}'
                f' {_span("meta.value", value, "", role="value")}</span>')

    if d.meta_style == "hai_cot":
        left = "".join(pair(k, v) for k, v in items)
        return (f'<div class="blk"><div class="meta"><div class="mcols">'
                f'<div class="mcol">{left}</div>'
                f'<div class="mcol r">{_span("period", place)}</div>'
                f'</div></div></div>')
    body = "".join(pair(k, v) for k, v in items) + _span("period", place, "m")
    cls = {"duoi_tieu_de_giua": "meta center", "duoi_tieu_de_phai": "meta right",
           "goc_phai_tren": "meta right", "dai_ngang": "meta band",
           "trong_khung_phai": "meta boxed"}[d.meta_style]
    align = ' style="text-align:right"' if d.meta_style == "trong_khung_phai" else ""
    return f'<div class="blk"{align}><div class="{cls}">{body}</div></div>'


def _fields(doc: Doc, d: Design) -> str:
    if not doc.fields:
        return ""
    style = d.field_style
    stack = style == "nhan_dam_tren"
    leader = {"mot_cot_cham_cham": "dots", "hai_cot_cham_cham": "dots",
              "mot_cot_gach_duoi": "ul", "hai_cot_gach_duoi": "ul"}.get(style, "")
    bold = style in ("nhan_dam_tren", "bang_khong_vien")
    columns = 1 if style.startswith("mot_cot") else d.field_columns
    if style.startswith("hai_cot"):
        columns = 2
    if style == "ba_cot_ngan":
        columns = 3

    cells = []
    for fdef, value in doc.fields:
        label = fdef.labels[doc.seed % len(fdef.labels)]
        k = _span("invoice.field.label", f"{label}:", "k kb" if bold else "k",
                  role="key")
        v = _span("invoice.field", value, f"v {leader}".strip(), role="value")
        cells.append((fdef.wide, f'<div class="{"stack" if stack else ""}">{k} {v}</div>'))

    if columns == 1 or stack:
        rows = "".join(f'<div class="frow">{body}</div>' for _wide, body in cells)
        return f'<div class="blk"><div class="fields">{rows}</div></div>'

    out, buffer = [], []
    width = 100 // columns
    for wide, body in cells:
        if wide and buffer:
            out.append(buffer)
            buffer = []
        if wide:
            out.append([(True, body)])
            continue
        buffer.append((False, body))
        if len(buffer) == columns:
            out.append(buffer)
            buffer = []
    if buffer:
        out.append(buffer)
    grid = []
    for group in out:
        span = 100 if len(group) == 1 and group[0][0] else width
        grid.append('<div class="fgrid">' + "".join(
            f'<div class="fcell" style="width:{span}%">{body}</div>'
            for _wide, body in group) + "</div>")
    return f'<div class="blk"><div class="fields">{"".join(grid)}</div></div>'


def _checks(doc: Doc, d: Design) -> str:
    if not doc.checks:
        return ""
    rows = "".join(
        f'{_span("invoice.checks.question", q, "q", role="key")}'
        f'{_span("invoice.checks.answer", a, "a", role="value")}'
        for q, a in doc.checks)
    return f'<div class="blk"><div class="checks">{rows}</div></div>'


def _legal_basis(doc: Doc, d: Design) -> str:
    """Căn cứ pháp lý -- `Bibliography`.

    Đầu mọi quyết định, công văn, tờ trình của cơ quan nhà nước là một chuỗi
    dòng "Căn cứ ...;". Đó đúng là `Bibliography` theo nghĩa từ vựng dùng: một
    danh sách nguồn mà văn bản viện dẫn. Nhãn ấy chưa từng xuất hiện trong bộ
    sinh này, trong khi dạng giấy mang nó thì đầy ngoài đời."""
    if not doc.legal_basis:
        return ""
    rows = "".join(f'<div class="lb">{_span("legal.basis", line)}</div>'
                   for line in doc.legal_basis)
    return (f'<div class="blk"><div class="basis" data-region="Bibliography">'
            f'{rows}</div></div>')


def _clauses(doc: Doc, d: Design) -> str:
    """Điều khoản đánh số -- `List-Group`.

    MỘT vùng cho CẢ danh sách, không phải một vùng cho mỗi điều. Bản trước
    gắn `data-region` lên từng `div.cl`, nên năm điều ra năm vùng
    `List-Group` xếp sát nhau -- đúng thứ tên nhãn ấy KHÔNG có nghĩa.
    `List-Group` trong từ vựng bố cục là NHÓM các mục, tức cả cái danh
    sách; từng mục là `List-Item`, và bảng 19 nhãn của kho này không có
    nhãn ấy.

    Khác khối bảng câu hỏi, và khác có lý do: ở đó mỗi câu là một cụm biểu
    mẫu người ta điền riêng, nên một vùng mỗi câu là đúng. Ở đây các điều
    là các MỤC của cùng một danh sách."""
    if not doc.clauses:
        return ""
    items = []
    for number, (head, body) in enumerate(doc.clauses, start=1):
        items.append(
            f'<div class="cl">'
            f'{_span("clause.head", f"Điều {number}. {head}", "ch")}'
            f'{_span("clause.body", body, "cb")}</div>')
    return (f'<div class="blk"><div class="clauses" data-region="List-Group">'
            f'{"".join(items)}</div></div>')


def _formula(doc: Doc, d: Design) -> str:
    """Công thức tính -- `Formula`. Một dòng đẳng thức bằng chữ, đúng như giấy
    bảo hiểm và viện phí in ra, không phải ký hiệu toán."""
    if not doc.formula:
        return ""
    return (f'<div class="blk"><div class="fml" data-region="Formula">'
            f'{_span("formula", doc.formula)}</div></div>')


def _figure(doc: Doc, d: Design) -> str:
    """Sơ đồ + chú thích -- `Figure` và `Caption`, hai vùng cạnh nhau.

    Khung sơ đồ là mực không phải chữ, nên nó không mang `data-kind` nào; câu
    chú thích bên dưới thì có. Đó là cặp `Figure`/`Caption` mà mọi bộ nhãn bố
    cục đều có và bộ sinh này chưa từng vẽ."""
    if not doc.caption:
        return ""
    return (f'<div class="blk">'
            f'<div class="fig" data-region="Figure" data-graphic="diagram">'
            f'<span class="fbox"></span><span class="fbox"></span>'
            f'<span class="fbox"></span></div>'
            f'<div class="fcap" data-region="Caption">'
            f'{_span("caption.figure", doc.caption)}</div></div>')


def _footnote(doc: Doc, d: Design) -> str:
    """Ghi chú có dấu sao -- `Footnote`. Khác `notes`: ngắn, cuối tờ, và mở
    đầu bằng một dấu trỏ ngược lên chỗ nó chú thích."""
    if not doc.footnotes:
        return ""
    rows = "".join(f'<div class="fn">{_span("footnote", line)}</div>'
                   for line in doc.footnotes)
    return (f'<div class="blk"><div class="fnotes" data-region="Footnote">'
            f'{rows}</div></div>')


def _toc(doc: Doc, d: Design) -> str:
    """Mục lục -- `Table-Of-Contents`. Chỉ in khi tài liệu đủ dài để có mục."""
    if not doc.toc:
        return ""
    rows = "".join(
        f'<div class="tocrow">{_span("toc.title", title, "tt")}'
        f'<span class="dots"></span>{_span("toc.page", page, "tp")}</div>'
        for title, page in doc.toc)
    return (f'<div class="blk"><div class="toc" data-region="Table-Of-Contents">'
            f'{rows}</div></div>')


def _questions(doc: Doc, d: Design) -> str:
    """Bảng câu hỏi: câu đánh số, mỗi câu một kiểu trả lời khác nhau.

    Ô TÍCH VÀ NHÃN CỦA NÓ LÀ HAI RUN RIÊNG. Khối `checks` cũ in cả hàng lựa
    chọn vào MỘT span ("☒ Có ☐ Không"), nên không có hộp nào cho từng ô và
    không mô hình nào học được ô nào đã tích -- nhãn nói đúng chữ in ra mà
    không nói được điều duy nhất tờ giấy ấy muốn nói. Tách ra thì mỗi ô có toạ
    độ riêng, và trạng thái tích nằm trong `data-key`.

    Dáng "phức" là có chủ đích: ba kiểu trả lời xen kẽ không theo quy luật, nên
    không khối nào đoán được khối sau nó cao bao nhiêu. Đó là tờ khai thật --
    xem ảnh mẫu trong `docs/`."""
    if not doc.questions:
        return ""
    out = []
    for number, item in enumerate(doc.questions, start=1):
        rows = [f'<div class="qq">{_span("survey.number", f"{number}.", "qn")}'
                f'{_span("survey.question", item["prompt"], "qt", role="key")}</div>']
        shape = item["shape"]
        if shape == "options":
            boxes = "".join(
                f'<span class="opt">'
                f'{_span("survey.tick", "☒" if o in item["picked"] else "☐", "tk", key=("ticked" if o in item["picked"] else "empty"))}'
                f'{_span("survey.option", o, "ol", role="value")}</span>'
                for o in item["options"])
            rows.append(f'<div class="qopts">{boxes}</div>')
        elif shape == "yesno":
            boxes = "".join(
                f'<span class="opt">'
                f'{_span("survey.tick", "☒" if o == item["ticked"] else "☐", "tk", key=("ticked" if o == item["ticked"] else "empty"))}'
                f'{_span("survey.option", o, "ol", role="value")}</span>'
                for o in item["options"])
            rows.append(f'<div class="qopts">{boxes}</div>')
        if item.get("sub"):
            rows.append(f'<div class="qsub">{_span("survey.prompt", item["sub"], "qs")}</div>')
        if item.get("answer"):
            rows.append(f'<div class="qans">'
                        f'{_span("survey.answer", item["answer"], "qa", role="value")}</div>')
        # MỘT VÙNG CHO MỖI CÂU HỎI, tự khai. Bộ gom mặc định cắt ở chỗ hở
        # ngang, mà máng giữa hai ô tích trên cùng một hàng rộng hơn ngưỡng
        # cắt -- đo được: vài ô lẻ ra thành vùng riêng còn phần còn lại dính
        # thành một hộp khổng lồ trùm gần hết tờ giấy, chồng lên nhau. Một câu
        # hỏi với các ô tích và dòng trả lời của nó là MỘT cụm thông tin, và
        # đó chính là cụm người đọc tờ khai đọc một lần.
        out.append(f'<div class="qitem" data-region="Form">{"".join(rows)}</div>')
    return f'<div class="blk"><div class="survey">{"".join(out)}</div></div>'


def _notes(doc: Doc, d: Design) -> str:
    if not doc.notes:
        return ""
    cls = "notes"
    if d.note_style == "trong_khung":
        cls += " boxed"
    if d.note_style == "chu_nghieng_nho":
        cls += " small"
    if d.note_style == "hai_cot":
        cls += " two"
    marks = {"danh_sach_so": lambda i: f"{i}. ", "danh_sach_gach": lambda i: "- "}
    mark = marks.get(d.note_style, lambda i: "")
    rows = "".join(_span("note", f"{mark(i)}{text}", "n")
                   for i, text in enumerate(doc.notes, start=1))
    return f'<div class="blk"><div class="{cls}">{rows}</div></div>'


def _group_of(doc: Doc, index: int) -> str:
    """Tên nhóm của dòng hàng thứ `index` (đếm theo cả tài liệu).

    Tính từ CHỈ SỐ chứ không giữ sẵn trên từng dòng, nên `refill()` đổi số
    dòng bao nhiêu lần thì nhóm vẫn rơi vào đúng chỗ ấy, và `paginate.py`
    cắt trang ở đâu cũng ra nhóm đúng."""
    if not doc.row_group_size or not doc.row_group_names:
        return ""
    # KHÔNG quay vòng: hết tên thì nhóm cuối ôm nốt phần còn lại. Quay vòng
    # cho ra một tờ giấy in "Tạm ứng" hai lần cách nhau mười dòng, và không
    # tờ giấy thật nào làm thế -- mục cuối dài hơn các mục trước thì có.
    which = min(index // doc.row_group_size, len(doc.row_group_names) - 1)
    return doc.row_group_names[which]


def _head(doc: Doc, d: Design, keys: list[str], rail: bool) -> str:
    """Khối `<thead>`: một, hai hay ba tầng, và hàng số cột nếu có.

    Nhiều tầng dựng bằng `colspan` cho ô gộp và `rowspan` cho ô đứng riêng --
    đúng cách một bảng kê nhà nước hay một tờ khai hải quan in ra, và là dáng
    mà bảng một tầng không dạy được mô hình đọc. Hộp của ô gộp do chính trình
    duyệt đo (`page.py::CELL_REGIONS_JS` đọc `colSpan`/`rowSpan`), nên không
    có gì phải khai thêm.

    Luật xếp, đúng một câu cho cả ba tầng: mỗi cột thuộc về ô hẹp nhất phủ
    nó, và ô nào không có tầng dưới thì `rowspan` xuống tới đáy `<thead>`."""
    tiers = d.head_tiers if doc.col_groups else 1
    if not doc.col_supers:
        tiers = min(tiers, 2)
    offset = 1 if rail else 0

    # `data-row` của tiêu đề đếm ÂM theo tầng: tầng trên cùng là 0 (đúng như
    # bảng một tầng vẫn ghi), tầng dưới là -1, -2, và hàng số cột là -3. Dòng
    # hàng đánh số từ 1 trở lên, nên hai dãy không bao giờ đụng nhau và một
    # trình đọc phân biệt được "ô này ở tầng nào" mà không phải đoán.
    def cell(key: str, col: int, tier: int = 0, span: str = "") -> str:
        title = doc.col_titles.get(key, COLUMNS[key]["titles"][0])
        return (f'<th class="a{COLUMNS[key]["align"][0]}" data-cell="colhdr" '
                f'data-row="{-tier}" data-col="{col}"{span}>'
                f'{_span("colhdr", title)}</th>')

    def gathered(caption: str, col: int, width: int, tier: int = 0,
                 span: str = "") -> str:
        return (f'<th class="ac" data-cell="colhdr" data-row="{-tier}" '
                f'data-col="{col + offset}" colspan="{width}"{span}>'
                f'{_span("colhdr", caption)}</th>')

    lead = ""
    if rail:
        span = f' rowspan="{tiers}"' if tiers > 1 else ""
        lead = (f'<th class="ac" data-cell="colhdr" data-row="0" data-col="0"'
                f'{span}>{_span("colhdr", "Nhóm")}</th>')

    if tiers < 2:
        rows = f'<tr>{lead}{"".join(cell(k, c + offset) for c, k in enumerate(keys))}</tr>'
    else:
        group_at = {first: (caption, width) for caption, first, width in doc.col_groups}
        in_group = {i for _, first, width in doc.col_groups
                    for i in range(first, first + width)}
        super_at = {first: (caption, width) for caption, first, width in doc.col_supers}
        in_super = {i for _, first, width in doc.col_supers
                    for i in range(first, first + width)}

        top, middle, bottom = [], [], []
        col = 0
        while col < len(keys):
            if tiers > 2 and col in super_at:
                caption, width = super_at[col]
                top.append(gathered(caption, col, width))
                inner = col
                while inner < col + width:
                    if inner in group_at:
                        sub_caption, sub_width = group_at[inner]
                        middle.append(gathered(sub_caption, inner, sub_width, 1))
                        for leaf in range(inner, inner + sub_width):
                            bottom.append(cell(keys[leaf], leaf + offset, 2))
                        inner += sub_width
                    else:
                        middle.append(cell(keys[inner], inner + offset, 1,
                                           ' rowspan="2"'))
                        inner += 1
                col += width
                continue
            if col in group_at:
                caption, width = group_at[col]
                deep = ' rowspan="2"' if tiers > 2 else ""
                top.append(gathered(caption, col, width, 0, deep))
                for leaf in range(col, col + width):
                    (bottom if tiers > 2 else middle).append(
                        cell(keys[leaf], leaf + offset, tiers - 1))
                col += width
                continue
            if col not in in_group and col not in in_super:
                top.append(cell(keys[col], col + offset, 0,
                                f' rowspan="{tiers}"'))
            col += 1

        rows = f'<tr>{lead}{"".join(top)}</tr>'
        rows += f'<tr class="tier2">{"".join(middle)}</tr>'
        if tiers > 2:
            rows += f'<tr class="tier3">{"".join(bottom)}</tr>'

    numbers = ""
    if d.col_numbers:
        # Hàng "(1) (2) (3)": chữ in trên giấy tờ nhà nước để các mục phía
        # dưới trỏ ngược lên cột. Nó là một hàng THẬT trong `<thead>`, nên nó
        # được lặp lại ở đầu mỗi tờ đúng như tiêu đề cột.
        cells = ""
        if rail:
            cells += ('<th class="ac" data-cell="colnum" data-row="-3" '
                      f'data-col="0">{_span("colnum", "(0)")}</th>')
        cells += "".join(
            f'<th class="ac" data-cell="colnum" data-row="-3" '
            f'data-col="{col + offset}">{_span("colnum", f"({col + 1})")}</th>'
            for col in range(len(keys)))
        numbers = f'<tr class="colnum">{cells}</tr>'
    return f'<thead>{rows}{numbers}</thead>'


def _sub(row, keys: list[str]) -> str:
    """Bảng con trong ô mô tả: lồng thật, không phải kẻ giả bằng thụt lề."""
    detail = str(row.values.get("detail", "")).strip()
    if not detail:
        return ""
    lines = "".join(
        f'<tr><td>{_span("menu.detail", part.strip())}</td></tr>'
        for part in detail.split("|") if part.strip())
    return f'<table class="sub"><tbody>{lines}</tbody></table>' if lines else ""


# Cột chữ tự do (`name`) được coi là rộng ngần này "ký tự" khi chia phần. Đây
# là con số duy nhất còn chọn thay vì đo, và nó chọn được vì cột ấy ĐƯỢC PHÉP
# xuống dòng: một tên hàng ba dòng là chuyện thường trên chứng từ thật, còn một
# con số bị ngắt làm đôi thì không.
FLEX_CHARS = 26

# Cột hẹp nhất vẫn phải chứa nổi tiêu đề của chính nó khi xuống dòng từng chữ.
MIN_CHARS = 4

# Đệm trái phải của một ô, quy ra ký tự. Đo được: `padding` ngang 4.54px mỗi
# bên và một chữ số rộng ~8px ở cỡ chữ gốc, nên hai bên đệm ăn mất hơn một ký
# tự. Không cộng khoản này thì mọi cột đều hụt đúng ngần ấy, và cột nào sát
# nút -- cột tiền -- là cột vỡ trước.
PAD_CHARS = 1.6

# Một milimét bằng ngần này pixel CSS, và một điểm chữ bằng ngần này pixel.
# Hằng số của CSS, không phải lựa chọn.
MM_PX = 96.0 / 25.4
PT_PX = 96.0 / 72.0

# Bề ngang trung bình một ký tự tiền Việt Nam, theo tỉ lệ cỡ chữ. ĐO trong
# trình duyệt: "465.626.000" (11 ký tự) chiếm 89px ở cỡ 13.6px -> 0.595, và
# "6.984.390.000" (13 ký tự) chiếm 102px -> 0.577. Dấu chấm hẹp hơn chữ số nên
# chuỗi càng dài tỉ lệ càng giảm; lấy 0.60 là nghiêng về phía ƯỚC THỪA, tức là
# thu chữ sớm hơn cần một chút -- sai về phía ấy thì chỉ xấu, sai về phía kia
# thì con số bị ngắt làm đôi.
CHAR_RATIO = 0.60

# Không cột cố định nào được rộng hơn ngần này, dù một giá trị cá biệt có dài
# đến đâu: một ô ghi chú 60 ký tự mà được cấp đủ chỗ sẽ nuốt hết bảng.
MAX_CHARS = 20


def _chars_across(d: Design) -> float:
    """Bề ngang vùng chữ, quy ra số ký tự tiền ở cỡ chữ của tờ giấy này.

    `boost` nằm trong phép tính vì đó chính là thứ `paginate.py` chỉnh để ép
    trang lấp đủ 80%: cùng một bảng ở `boost` 0.9 và 1.1 chứa được số ký tự
    khác nhau, nên một ngưỡng tính sẵn sẽ đúng ở lượt này và sai ở lượt sau."""
    _top, right, _bottom, left = d.margins
    content_px = (d.paper.w - left - right) * MM_PX
    char_px = CHAR_RATIO * d.base_pt * d.boost * PT_PX
    return content_px / max(char_px, 1.0)


def _fit(text: str, budget: float) -> str:
    """Lớp CSS thu nhỏ chữ cho một ô hẹp hơn nội dung của nó.

    Cột đã được chia theo nhu cầu đo được, nhưng một bảng tám cột với những con
    số mười ba chữ số thì không có cách chia nào đủ cho tất cả. Khi ấy chọn
    giữa hai cái xấu: ngắt con số làm đôi, hay in nó nhỏ hơn một chút.

    In nhỏ hơn, và không phải vì đẹp hơn: `446.849.` ở dòng này và `529.000` ở
    dòng dưới là HAI đoạn chữ với hai cái hộp, nên bản ghi có hai nhãn cho một
    con số và không gì nối chúng lại được. Chữ nhỏ đi thì vẫn là một đoạn, một
    hộp, một nhãn -- và chứng từ kế toán thật cũng in đúng như vậy khi con số
    không vừa cột."""
    over = len(text) / max(budget, 1.0)
    if over <= 1.0:
        return ""
    if over <= 1.1:
        return " tight"
    # Bậc thứ ba dành cho DÒNG TỔNG: `1.219.350.587.400 đ` dài hơn mọi thành
    # tiền của từng dòng, nên cột tiền vốn vừa với thân bảng vẫn hụt ở chân
    # bảng. Hai bậc đầu không đủ, đo được: 6/28 trang còn ngắt.
    return " tighter" if over <= 1.3 else " tightest"


def _need(doc: Doc, d: Design, key: str, keys: list[str]) -> int:
    """Cột này phải chứa nổi bao nhiêu ký tự -- ĐO trên nội dung thật.

    `COLUMNS[...]["w"]` là một bảng trọng số viết tay, và nó sai với nội dung
    thật theo cả hai chiều. Đo được trên một tờ bảng kê: `menu.amount` được cấp
    85.9px trong khi chuỗi dài nhất của nó cần 119.8px -- nên 4/4 ô xuống dòng,
    `446.849.` một dòng và `529.000` dòng dưới. Cùng lúc ấy `menu.qty` được cấp
    53.6px cho một chuỗi cần 17.7px. Tổng thừa 41px nằm cạnh tổng thiếu 79px.

    Con số bị ngắt làm đôi là một lỗi nặng hơn nó trông: CSS coi dấu chấm là
    chỗ xuống dòng hợp lệ, nên tiền Việt Nam -- vốn chấm phân cách nghìn -- là
    loại chuỗi dễ vỡ nhất trên tờ giấy, và một mô hình đọc `446.849.` rồi
    `529.000` ở dòng dưới không có cách nào biết chúng là một số.

    Tiêu đề cột chỉ tính theo TỪ DÀI NHẤT, không theo cả câu: tiêu đề được phép
    xuống dòng giữa các từ ("Người bệnh / trả") và vẫn đọc được; cái không được
    phép là vỡ một từ."""
    longest = max((len(str(row.values.get(key, "")))
                   for row in doc.rows), default=0)
    # Dòng tổng in vào CỘT TIỀN, và chúng là những con số dài nhất tờ giấy --
    # `482.597.491.320 đ` dài hơn mọi thành tiền của từng dòng.
    if key == "amount" or (key == keys[-1] and "amount" not in keys):
        for _label, value in doc.totals:
            longest = max(longest, len(str(value)))
        if doc.grand:
            longest = max(longest, len(str(doc.grand)))
    # Đúng tiêu đề TỜ NÀY in ra, không phải tiêu đề mặc định: `doc.col_titles`
    # là thứ `_head` đọc, và "S.Lượng" với "Số lượng" không rộng bằng nhau.
    title = doc.col_titles.get(key, COLUMNS[key]["titles"][0])
    head = max((len(word) for word in str(title).split()), default=0)
    return max(MIN_CHARS, head, min(longest, MAX_CHARS)) + PAD_CHARS


def _tfoot(doc: Doc, d: Design, width: int, after: int, money: int,
           budget: float = 12.0) -> str:
    """Khối tổng, in thành `<tfoot>` CỦA CHÍNH BẢNG HÀNG, không thành một khối
    `<div>` riêng bên dưới.

    Bản trước in nó thành `<div class="trow">`: nhìn thì y hệt một cái bảng --
    nhãn một cột, số một cột, có khung -- mà DOM thì không có ô nào, không cột
    nào. Nên `regions_from_words` đọc đúng như nó thấy và gọi khối ấy là `Text`,
    còn người xem ảnh vẽ hộp thì thấy một cái bảng bị gán nhãn sai. Không bên
    nào sai: hai bên nhìn hai thứ khác nhau, vì HTML nói một đằng còn mắt đọc
    một nẻo.

    Sửa ở chỗ ĐÚNG là sửa cái HTML. Nằm trong `<table>` thì nó LÀ bảng: trình
    duyệt đo được từng ô, `pipeline/record.py` nâng mọi từ trong ô đo được lên
    `Table`, và nhãn khớp hình mà không ai phải khai thêm gì. Tiện thể bảng
    phức tạp hơn thật -- mỗi dòng tổng là một ô `colspan` ôm gần hết bề ngang,
    tức là một kiểu gộp ô mà bảng hàng thuần tuý không có."""
    # Con số phải rơi vào ĐÚNG CỘT TIỀN, không vào cột cuối. Đặt vào cột cuối
    # là đặt một con số mười hai chữ số vào cột "Chú thích" rộng 12%, và nó
    # xuống dòng giữa chừng -- "1.108.500.534" một dòng, ".000" dòng dưới. Cột
    # tiền vốn được tính bề ngang để chứa vừa một con số như thế.
    lead = money if money >= 0 else max(width - 1, 1)
    trail = width - lead - 1

    def row(kind: str, label: str, value: str, number: int, extra: str = "") -> str:
        snug = _fit(str(value), budget)
        cells = (f'<td class="ar" colspan="{max(lead, 1)}" data-cell="cell" '
                 f'data-row="{number}" data-col="0">'
                 f'{_span(f"{kind}.label", label, role="key")}</td>'
                 f'<td class="ar{snug}" data-cell="cell" data-row="{number}" '
                 f'data-col="{max(lead, 1)}">'
                 f'{_span(kind, value, role="value")}</td>')
        if trail > 0:
            cells += (f'<td colspan="{trail}" data-cell="cell" '
                      f'data-row="{number}" data-col="{lead + 1}"></td>')
        return f'<tr class="tfrow{extra}">{cells}</tr>'

    rows = [row("total.line", label, value, after + index + 1)
            for index, (label, value) in enumerate(doc.totals)]
    if doc.grand:
        rows.append(row("total.grand", doc.grand_label, doc.grand,
                        after + len(doc.totals) + 1, " grand"))
    return f'<tfoot>{"".join(rows)}</tfoot>' if rows else ""


def _table(doc: Doc, d: Design, low: int, high: int, part: int,
           foot: bool = False) -> str:
    if not doc.rows:
        return ""
    keys = [k for k in d.columns if k in COLUMNS]
    rail = d.row_groups == "cot_gom" and bool(doc.row_group_size)
    sections = d.row_groups == "phan_muc" and bool(doc.row_group_size)
    offset = 1 if rail else 0
    width = len(keys) + offset
    # Dòng cộng nhóm chỉ in khi bảng CÓ cột thành tiền: cộng một bảng không
    # có tiền là in ra một con số không đứng dưới cột nào.
    money_col = keys.index("amount") if "amount" in keys else -1
    totals = sections and money_col >= 0 and bool(doc.row_group_totals)

    # Bề ngang cột, tính TRỌN VẸN bằng một đơn vị: "ký tự". Cột cố định lấy số
    # ký tự nó thật sự phải chứa, cột chữ tự do lấy `FLEX_CHARS`, rồi cả bộ
    # được quy về phần trăm MỘT LẦN.
    #
    # Bản trước trộn hai đơn vị và tổng vọt lên 122%: `need` đếm ký tự trong
    # khi `max(100 - fixed_total, 18)` coi cùng con số ấy là phần trăm. Với
    # `table-layout:fixed` trình duyệt không báo lỗi -- nó chia lại theo tỉ lệ,
    # nên MỌI cột hẹp đi, và cột `SL` hẹp tới mức "23" xếp dọc thành "2" trên
    # "3". Một lỗi đơn vị trông y hệt một lựa chọn thiết kế tồi.
    need = {k: (FLEX_CHARS if COLUMNS[k]["w"] == 0 else _need(doc, d, k, keys))
            for k in keys}
    total = max(sum(need.values()), 1)
    room = 87.0 if rail else 100.0
    # Bảng CHỨA NỔI bao nhiêu ký tự, thật sự. Không có con số này thì `need`
    # chỉ nói được tỉ lệ giữa các cột chứ không nói được cột nào vỡ: đo trên
    # một tờ bảng kê, bảng rộng 61.6 ký tự trong khi các cột đòi 72.4 -- mọi
    # cột hụt 15%, và cột tiền là cột hụt thành lỗi.
    table_chars = _chars_across(d) * room / 100.0
    cols = []
    if rail:
        cols.append('<col style="width:13.0%">')
    for key in keys:
        cols.append(f'<col style="width:{need[key] * room / total:.1f}%">')

    head = _head(doc, d, keys, rail)

    # Cột gom: một ô `rowspan` cho mỗi ĐOẠN dòng cùng nhóm nằm trên TỜ NÀY.
    # Nhóm bị cắt ngang trang thì mỗi tờ mang phần của mình, vì `rowspan`
    # không vượt được qua một cái bảng khác.
    runs: dict[int, tuple[str, int]] = {}
    if rail:
        index = low
        while index < high:
            name = _group_of(doc, index)
            end = index
            while end < high and _group_of(doc, end) == name:
                end += 1
            runs[index] = (name, end - index)
            index = end

    body = []
    for r_index, row in enumerate(doc.rows[low:high], start=low + 1):
        at = r_index - 1
        # Đầu tờ thì in lại tiêu đề nhóm; giữa tờ thì chỉ in khi nhóm ĐỔI.
        # Không đếm theo `at % size` được: nhóm cuối ôm nốt phần còn lại, nên
        # phép chia dư vẫn kêu ở giữa nó và in ra cùng một cái tên hai lần.
        if sections and (at == low
                         or _group_of(doc, at) != _group_of(doc, at - 1)):
            body.append(
                f'<tr class="grouphdr"><td colspan="{width}" data-cell="cell" '
                f'data-row="{r_index}" data-col="0">'
                f'{_span("colhdr", _group_of(doc, at))}</td></tr>')
        tds = []
        if rail:
            run = runs.get(at)
            if run:
                tds.append(f'<td class="rail" rowspan="{run[1]}" '
                           f'data-cell="cell" data-row="{r_index}" '
                           f'data-col="0">{_span("colhdr", run[0])}</td>')
        for col, key in enumerate(keys):
            value = row.values.get(key, "")
            # `data-cell/-row/-col`: `generators/html/page.py::CELL_REGIONS_JS`
            # đọc đúng ba thuộc tính này để dựng nhãn cấu trúc bảng, và nhờ nó
            # vùng `Table` lấy hộp ĐO ĐƯỢC của từng ô thay vì hợp của các chữ
            # nằm trong ô. Số dòng đếm theo cả tài liệu, không theo từng tờ.
            extra = _sub(row, keys) if (d.nested_detail and key == "name") else ""
            # Cột chữ tự do được phép xuống dòng; cột số thì không.
            snug = ("" if COLUMNS[key]["w"] == 0
                    else _fit(str(value),
                              need[key] / total * table_chars - PAD_CHARS))
            tds.append(f'<td class="a{COLUMNS[key]["align"][0]}{snug}" '
                       f'data-cell="{_t(COLUMNS[key]["kind"])}" '
                       f'data-row="{r_index}" data-col="{col + offset}">'
                       f'{_span(COLUMNS[key]["kind"], value)}{extra}</td>')
        body.append(f'<tr class="itemrow">{"".join(tds)}</tr>')

        # Cộng nhóm in NGAY SAU dòng cuối của nhóm, và chỉ khi dòng cuối ấy
        # nằm trên tờ này: một dòng cộng đứng trước phần nó cộng, hay đứng
        # trên một tờ khác với phần ấy, là một dòng cộng nói dối.
        after = at + 1
        ends = after >= len(doc.rows) or _group_of(doc, after) != _group_of(doc, at)
        if totals and ends:
            which = min(at // doc.row_group_size, len(doc.row_group_names) - 1)
            value = (doc.row_group_totals[which]
                     if which < len(doc.row_group_totals) else "")
            cells = ""
            if money_col + offset > 0:
                cells = (f'<td colspan="{money_col + offset}" class="ar" '
                         f'data-cell="cell" data-row="{r_index}" data-col="0">'
                         f'{_span("total.group", f"Cộng {_group_of(doc, at)}")}</td>')
            cells += (f'<td class="ar" data-cell="total.group_amount" '
                      f'data-row="{r_index}" data-col="{money_col + offset}">'
                      f'{_span("total.group_amount", value)}</td>')
            rest = len(keys) - money_col - 1
            if rest > 0:
                cells += (f'<td colspan="{rest}" data-cell="cell" '
                          f'data-row="{r_index}" '
                          f'data-col="{money_col + offset + 1}"></td>')
            body.append(f'<tr class="grouptot">{cells}</tr>')

    caption = ""
    if doc.table_caption and part == 0:
        caption = _span("caption.table", doc.table_caption, "tcap")
    money_key = keys[money_col] if money_col >= 0 else keys[-1]
    tfoot = (_tfoot(doc, d, width, high,
                    money_col + offset if money_col >= 0 else -1,
                    need.get(money_key, 12.0) / total * table_chars - PAD_CHARS)
             if foot else "")
    return (f'<div class="blk">{caption}'
            f'<table class="items"><colgroup>{"".join(cols)}</colgroup>'
            f'{head}'
            f'<tbody>{"".join(body)}</tbody>{tfoot}</table></div>')


def _totals(doc: Doc, d: Design) -> str:
    if not doc.grand and not doc.totals:
        return ""
    rows = "".join(
        f'<div class="trow">{_span("total.line.label", label, "tk", role="key")}'
        f'{_span("total.line", value, "tv", role="value")}</div>'
        for label, value in doc.totals)
    grand = ""
    if doc.grand:
        grand = (f'<div class="trow grand">'
                 f'{_span("total.grand.label", doc.grand_label, "tk", role="key")}'
                 f'{_span("total.grand", doc.grand, "tv", role="value")}</div>')
    cls = "totals boxed" if d.table_frame in ("khung_day_du", "vien_ngoai") else "totals"
    # `data-region`: khối này là MỘT vùng bố cục, không phải tám. Bộ gom mặc
    # định cắt ở chỗ hở ngang, mà máng giữa nhãn và số rộng hơn ngưỡng cắt --
    # nên nếu không khai, "Tổng cộng tiền thanh toán" và "1.569.081.240 đ"
    # thành hai vùng dù chúng là một dòng của cùng một khung.
    return (f'<div class="blk"><div class="{cls}" data-region="Text">'
            f'{rows}{grand}</div></div>')


def _words(doc: Doc, d: Design) -> str:
    if not doc.words:
        return ""
    return (f'<div class="blk"><div class="words">'
            f'{_span("invoice.words.label", doc.words_label, "wk", role="key")} '
            f'{_span("invoice.words", doc.words, "wv", role="value")}</div></div>')


def _summary(doc: Doc, d: Design) -> str:
    """Khung tổng hợp thuế ở cuối tờ hoá đơn. LÀ một cái bảng, và phải đo được.

    `data-cell`/`data-row`/`data-col` không phải trang trí: `page.py::
    CELL_REGIONS_JS` đọc đúng ba thuộc tính ấy, và không có chúng thì khối này
    tuy in ra bằng `<table>` vẫn không có ô nào ĐO ĐƯỢC -- nên
    `regions_from_words` gom nó bằng luật chữ chạy, cắt ở mỗi chỗ hở ngang, và
    bốn dòng thành tám vùng `Text` rời nhau. Đúng lỗi khối tổng từng mắc, cùng
    một nguyên nhân, chỉ khác chỗ."""
    if not doc.summary:
        return ""
    rows = "".join(
        f'<tr><td class="k" data-cell="cell" data-row="{n}" data-col="0">'
        f'{_span("summary.label", label, role="key")}</td>'
        f'<td class="v" data-cell="cell" data-row="{n}" data-col="1">'
        f'{_span("summary.gross", value, role="value")}</td></tr>'
        for n, (label, value) in enumerate(doc.summary, start=1))
    return (f'<div class="blk"><table class="summary">'
            f'<tbody>{rows}</tbody></table></div>')


def _signatures(doc: Doc, d: Design) -> str:
    if not doc.signatures:
        return ""
    place = f"{doc.issued_place}, {fmt_date(doc.issued_date, 1)}"
    # Khối `meta` đã in "nơi, ngày tháng năm" thì ĐỪNG in lại ở đây. Đo trên
    # lượt 19 trang: `hoa_don_gtgt_00009` in "Bắc Ninh, ngày 22 tháng 06 năm
    # 2026" hai lần, một lần `kind=period` một lần `kind=sign.signedat` -- cùng
    # một dòng chữ, hai thực thể, hai nhãn khác nhau. Một mô hình học trên đó
    # học rằng cùng một chuỗi vừa là `Text` vừa là `Form`.
    printed_by_meta = d.meta_style != "khong_co" and "meta" in d.order
    date_line = _span("sign.signedat", place, "sdate") if (
        d.sign_style in ("trai_phai", "chi_ben_phai", "cot_deu")
        and not printed_by_meta) else ""
    cells = []
    for caption, who in doc.signatures:
        hint = _span("sign.note", "(Ký, ghi rõ họ tên)", "hint")
        name = _span("sign.name", who, "who") if who else _span(
            "sign.note", "", "who")
        cells.append(f'<div class="scell">{_span("sign.title", caption, "cap")}'
                     f'{hint}{name}</div>')
    cls = "signs"
    if d.sign_style == "co_khung":
        cls += " boxed"
    if d.sign_style == "co_dong_ke":
        cls += " ruled"
    if d.sign_style == "chi_ben_phai":
        cls += " right"
        cells = cells[-1:]
    return f'<div class="blk">{date_line}<div class="{cls}">{"".join(cells)}</div></div>'


def _footer(doc: Doc, d: Design) -> str:
    if not doc.footer:
        return ""
    return f'<div class="blk"><div class="foot">{_span("footer", doc.footer)}</div></div>'


# Con dấu lấy từ `textures/ornament/` -- thư viện PNG `tools/make_ornaments.py`
# dựng và `generators/html/ornament.py` dùng, chứ không vẽ lại bằng CSS. Bản CSS
# cũ là một hình chữ nhật bo góc xoay 14 độ: nó đọc ra hình THOI, không ra con
# dấu, và một con dấu oval thì không có thật trên giấy tờ Việt Nam.
#
# Chỉ TRÒN và CHỮ NHẬT. Đó là hai hình con dấu thật sự dùng.
SEALS = {
    "dau_tron": ("seal_round_company", "seal_round_company_double",
                 "seal_round_export", "seal_round_hotel"),
    "dau_vuong": ("seal_square_paid", "seal_square_copy"),
}

_SEAL_CACHE: dict[str, tuple[str, float]] = {}

# Bề ngang con dấu sau khi thu nhỏ, tính bằng pixel. Một con dấu in 24mm trên
# tờ A4 rộng 210mm, chụp ở device scale 2 với ảnh ra ~1113px, ra khoảng 254px --
# nên 256 là cỡ vừa đủ nét, và mỗi bậc to hơn là thêm vài chục KB vào MỌI trang.
SEAL_PX = 256


def seal_art(stem: str) -> tuple[str, float]:
    """`(data URI, tỉ lệ cao/rộng)` của một con dấu, đã CẮT SÁT nét mực.

    Cắt là phần quan trọng: file gốc chừa lề trong suốt -- đo được 55/600 pixel
    mỗi bên ở `seal_round_company`, tức 9% -- nên một `<img>` dùng thẳng file
    sẽ có hộp rộng hơn con dấu 18%. Hộp phải bám ĐƯỜNG NGOÀI của dấu, và cách
    chắc chắn nhất là để chính tấm ảnh không còn gì ngoài đường ấy: khi đó hộp
    trình duyệt đo được LÀ đường ngoài, không phải một phép xấp xỉ.

    Nhớ theo tiến trình: một shard trăm trang dùng lại cùng vài con dấu, và
    giải mã PNG 600x600 rồi mã hoá base64 lại cho từng tờ là trả một cái giá
    cố định một trăm lần."""
    if stem in _SEAL_CACHE:
        return _SEAL_CACHE[stem]
    import base64  # noqa: PLC0415 -- chỉ cần khi trang có dấu

    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    path = REPO_ROOT / "textures" / "ornament" / f"{stem}.png"
    art = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if art is None:
        raise FileNotFoundError(f"không đọc được con dấu {path}")
    if art.ndim == 3 and art.shape[2] == 4:
        alpha = art[:, :, 3]
    else:
        alpha = 255 - cv2.cvtColor(art, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(alpha > 8)
    if len(xs):
        art = art[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    height = max(1, round(art.shape[0] * SEAL_PX / art.shape[1]))
    art = cv2.resize(art, (SEAL_PX, height), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".png", art, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise RuntimeError(f"không mã hoá được con dấu {stem}")
    uri = "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode()
    _SEAL_CACHE[stem] = (uri, height / SEAL_PX)
    return _SEAL_CACHE[stem]


def _seal(d: Design, stem: str, right: float, top: float) -> str:
    uri, ratio = seal_art(stem)
    width = 26.0 if stem.startswith("seal_round") else 30.0
    # `data-graphic` trên chính `<img>`: hộp mà `GRAPHIC_RECTS_JS` đo được là
    # hộp của tấm ảnh, và tấm ảnh đã cắt sát mực -- nên hộp bám đường ngoài của
    # dấu mà không cần ai tính toán gì thêm.
    return (f'<div class="sealhost"><img class="seal" src="{uri}" alt="" '
            f'data-graphic="seal" style="width:{width:.1f}mm;'
            f'height:{width * ratio:.1f}mm;right:{right:.0f}mm;top:{top:.0f}mm">'
            f'</div>')


def _ornament(doc: Doc, d: Design) -> str:
    """Mực không phải chữ chạy: dấu, mã vạch, mã QR. Mỗi thứ vẫn mang một
    `data-kind` riêng, vì mực không có hộp là mực không có nhãn."""
    name = d.ornament
    if name == "khong":
        return ""
    if name in ("ma_vach", "ma_qr"):
        inner = ('<span class="barcode" data-graphic="barcode"></span>'
                 if name == "ma_vach"
                 else '<span class="qr" data-graphic="qr"></span>')
        code = f"{doc.doc_serial}{doc.doc_no}".replace("/", "")
        return (f'<div class="blk mark">{inner}'
                f'{_span("menu.barcode", code)}</div>')
    # Con dấu nào trong nhóm là hàm thuần của seed: cùng tờ giấy thì cùng con
    # dấu, mà hai tờ khác nhau không đóng chung một cái.
    pick = lambda group: group[d.seed % len(group)]  # noqa: E731
    if name == "dau_tron_va_ma_vach":
        code = f"{doc.doc_serial}{doc.doc_no}".replace("/", "")
        return (f'<div class="blk mark">'
                f'<span class="barcode" data-graphic="barcode"></span>'
                f'{_span("menu.barcode", code)}</div>'
                + _seal(d, pick(SEALS["dau_tron"]), 6, -32))
    group = SEALS.get(name) or SEALS["dau_tron" if name == "chim_mo" else "dau_vuong"]
    return _seal(d, pick(group), 8, -34)


def _photo(doc: Doc, d: Design) -> str:
    if not d.photo_box:
        return ""
    return (f'<div class="photo">{_span("photo.placeholder", "ẢNH")}<br>'
            f'{_span("photo.size", "4 x 6")}</div>')


# Khối chạy hết chiều ngang, không bao giờ chảy vào cột. Tiêu đề, quốc hiệu,
# ô ảnh, con dấu là những thứ một tờ giấy in ngang trang; chữ ký và chân trang
# là một dải cuối trang.
FULL_WIDTH = frozenset({"photo", "letterhead", "doctitle", "meta",
                        "signatures", "footer", "ornament"})

# Trong số đó, những khối in SAU phần chảy cột.
_AFTER_FLOW = frozenset({"signatures", "footer", "ornament"})

_BUILDERS = {
    "letterhead": _letterhead,
    "doctitle": _doctitle,
    "meta": _meta,
    "fields": _fields,
    "checks": _checks,
    "questions": _questions,
    "legal_basis": _legal_basis,
    "clauses": _clauses,
    "formula": _formula,
    "figure": _figure,
    "footnote": _footnote,
    "toc": _toc,
    "notes": _notes,
    "totals": _totals,
    "words": _words,
    "summary": _summary,
    "signatures": _signatures,
    "footer": _footer,
}


def markup(doc: Doc, slices: list[tuple[int, int]], faces: str = "") -> str:
    """HTML đầy đủ. `slices` dài bao nhiêu thì có bấy nhiêu tờ `.sheet`."""
    d = doc.design
    order = list(d.order)
    if "table" in order:
        cut = order.index("table")
        head_names, tail_names = order[:cut], order[cut + 1:]
    else:
        head_names, tail_names = order, []
        slices = [(0, 0)]

    # Khối tổng đi VÀO bảng khi có bảng -- xem `_tfoot`. Không có bảng thì nó
    # vẫn phải in ra, và khi ấy `_totals` là chỗ duy nhất in được nó.
    foot_totals = "totals" in tail_names and "table" in order and bool(doc.rows)
    if foot_totals:
        tail_names = [name for name in tail_names if name != "totals"]

    # Quốc hiệu: chỉ tờ giấy của cơ quan nhà nước và bệnh viện in, và nó in
    # NGAY SAU thẩm quyền ban hành. Quyết định một lần, trước vòng lặp -- ở
    # trong vòng lặp nó sẽ phụ thuộc vào tờ nào đang vẽ, mà quốc hiệu thì
    # không.
    wants_national = (d.archetype.org_kind in ("state", "hospital")
                      and d.head_layout not in ("chia_doi", "chia_doi_co_logo",
                                                "hai_cot_cach"))

    sheets: list[str] = []
    pages = max(len(slices), 1)
    for index in range(pages):
        # `(tên khối, html)` chứ không chỉ html: trang nhiều cột phải biết khối
        # nào chảy vào cột và khối nào chạy hết chiều ngang, và biết theo TÊN.
        # Cắt theo vị trí thì sai ngay: `_photo` và quốc hiệu chen vào làm lệch
        # chỉ số, nên tiêu đề bị hút vào cột và "BIÊN BẢN BÀN GIAO" vỡ làm ba
        # dòng hẹp -- thấy được trên ảnh vẽ hộp.
        parts: list[tuple[str, str]] = []
        if index == 0:
            parts.append(("photo", _photo(doc, d)))
            for name in head_names:
                parts.append((name, _BUILDERS[name](doc, d)))
                if name == "letterhead" and wants_national:
                    parts.append(("letterhead", _national(doc, d)))
        if "table" in d.order and index < len(slices):
            low, high = slices[index]
            parts.append(("table", _table(doc, d, low, high, index,
                                          foot=foot_totals and index == pages - 1)))
        if index == pages - 1:
            for name in tail_names:
                parts.append((name, _BUILDERS[name](doc, d)))
            parts.append(("ornament", _ornament(doc, d)))
        water = ""
        if d.watermark:
            # `data-kind`, KHÔNG `data-graphic`. "BẢN SAO" là chữ in ra --
            # mờ, xoay, nhưng đọc được -- nên nó phải có hộp TỪ như mọi chữ
            # khác. Khai là graphic thì nó ra một vùng `Image` không có chữ
            # nào, tức là một tấm ảnh không tồn tại, và chữ thật thì không có
            # nhãn nào. Cùng lý do ô dán ảnh thôi là `Image`.
            # `data-region="Watermark"` trên khối bọc: chữ chìm là MỰC PHỦ,
            # không phải một đoạn trong mạch nội dung. Có nhãn vùng riêng thì
            # người huấn luyện đọc nội dung lọc được nó ra; gộp vào `Text` là
            # bảo họ rằng "BẢN SAO" xoay 25 độ là một đoạn văn của tài liệu.
            water = (f'<div class="wmark" data-region="Watermark">'
                     f'{_span("watermark", "BẢN SAO", "wtext")}</div>')
        # Số trang, kiểu chứng từ thông dụng. Thay cho dòng "(Tiếp theo trang
        # N)" mà bản trước in ở ĐẦU bảng: nó là một ghi chú của riêng cái bảng,
        # trong khi thứ người đọc tìm là tờ này là tờ thứ mấy trong mấy tờ.
        # Chỉ in khi có từ hai tờ -- một tờ giấy một trang không đánh số.
        page_no = ""
        if pages > 1:
            page_no = (f'<div class="pgnum">'
                       f'{_span("footer.page", f"Trang {index + 1}/{pages}")}</div>')
        body = "".join(html for _name, html in parts if html)
        # CHỮ CHẢY THÀNH CỘT. `FULL_WIDTH` ở NGOÀI khung cột -- trên giấy thật
        # tiêu đề, quốc hiệu và dải chữ ký chạy hết chiều ngang, và một cái
        # tiêu đề rơi vào cột trái là thứ không tờ báo nào in.
        if d.page_columns > 1:
            flow = [html for name, html in parts
                    if html and name not in FULL_WIDTH]
            if len(flow) >= 2:
                head = "".join(html for name, html in parts
                               if html and name in FULL_WIDTH
                               and name not in _AFTER_FLOW)
                tail = "".join(html for name, html in parts
                               if html and name in _AFTER_FLOW)
                body = (f'{head}<div class="cols">{"".join(flow)}</div>{tail}')
        sheets.append(f'<div class="sheet">{water}{body}{page_no}'
                      f'<div class="clr"></div></div>')


    style = stylesheet(d, faces)
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f"<style>{style}</style></head><body>{''.join(sheets)}</body></html>")
