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
import random
import unicodedata
from pathlib import Path

from synthgen import design as D
from synthgen.content import Doc, fmt_date
from synthgen.design import COLUMNS, Design

REPO_ROOT = Path(__file__).resolve().parents[1]

NATIONAL_1 = "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"
NATIONAL_2 = "Độc lập - Tự do - Hạnh phúc"


def _t(text) -> str:
    """Chữ đưa vào HTML. Escape luôn, không có đường vòng."""
    return _html.escape(str(text), quote=True)


def _span(kind: str, text, cls: str = "", role: str = "", key: str = "",
          region: str = "", shape: str = "") -> str:
    """Một dòng chữ đo được. Rỗng thì không in gì -- một span rỗng là một hộp
    không có chữ, và nhãn của nó sẽ mô tả khoảng trắng.

    `shape` -- `item["shape"]` của chính câu hỏi (`_shape_rows`'s 12 dạng),
    gắn lên span câu hỏi vì đây là chỗ DUY NHẤT giá trị ấy còn nằm trong tay
    trước khi bị bỏ đi: một câu hỏi `yesno` và một câu `options` vẽ ra đúng
    một khuôn `kind` (`survey.tick`+`survey.option`), và chỉ khác nhau ở việc
    được chọn MỘT hay NHIỀU -- thứ không để lại dấu vết nào trên mực. Xem
    `pipeline/record.py::field_type_for`."""
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
    if region:
        attrs.append(f'data-region="{_t(region)}"')
    if shape:
        attrs.append(f'data-shape="{_t(shape)}"')
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
.head .val{{font-size:{_px(base_pt * 0.92)};color:{pal.ink};}}
.head.center{{text-align:center;}}
.head.right{{text-align:right;}}
.head.boxed{{border:{rule} solid {pal.rule};padding:2.4mm 3mm;}}
.head.band{{background:{pal.band_bg};color:{pal.band_fg};padding:2.6mm 3mm;}}
/* `.lbl` và `.val` PHẢI có mặt ở đây. Chúng giữ `pal.soft`/`pal.ink` -- hai
   màu chọn cho nền GIẤY -- nên trên một dải nền đậm thì chữ xám đậm nằm trên
   nền đen: đo trên `bang_ke_quyen_loi_00003`, nhãn "Địa chỉ:/Điện thoại:/Mã
   số thuế:" màu #4a4a4a trên #000000, không đọc được. Bốn trên mười sáu bảng
   màu có cặp `soft`/`band_bg` tương phản dưới ngưỡng đọc.

   Nhãn mờ hơn giá trị một chút vẫn giữ được bằng `opacity`, thứ ăn theo màu
   nền chứ không chống lại nó. */
.head.band .org,.head.band .line,.head.band .parent,
.head.band .val{{color:{pal.band_fg};}}
.head.band .lbl{{color:{pal.band_fg};opacity:0.78;}}
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
.fields .fpair{{display:flex;align-items:baseline;gap:1.5mm;}}
.fgrid{{display:table;width:100%;border-spacing:0;}}
.fcell{{display:table-cell;vertical-align:top;padding-right:5mm;
  padding-bottom:{1.0 if d.compact_rows else 1.7}mm;}}
.fields .k{{color:{pal.ink};}}
.fields .kb{{font-weight:700;}}
.fields .v{{color:{pal.ink};}}
/* DÒNG CHẤM CHẠY TỚI LỀ, không dừng sau chữ.
   `min-width` làm dòng chấm dài đúng bằng giá trị, nên mỗi dòng một độ dài và
   không dòng nào thẳng cột -- trên giấy thật người ta in sẵn dòng chấm tới
   lề rồi mới viết vào. Đo trên `giay_chung_nhan_qsdd`: "Sinh ngày: 19/12/1985"
   có dòng chấm dừng ngay sau chữ số.

   Mẫu đúng ĐÃ có sẵn trong chính file này ở `.toc .dots{{flex:1}}` -- cùng một
   ý đồ hình ảnh, hai cách làm, và cách sai là cách được dùng nhiều hơn. */
.fields .dots{{border-bottom:{d.rule_px * 0.8:.2f}mm dotted {pal.rule};
  display:inline-block;flex:1;min-width:18mm;}}
.fields .ul{{border-bottom:{d.rule_px * 0.8:.2f}mm solid {pal.rule};
  display:inline-block;flex:1;min-width:20mm;}}
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
/* KHÔNG đặt `text-align` ở đây. `design.COLUMNS[key]['align']` là luật, và
   bộ phát `<th>` đã gắn đúng class `al`/`ac`/`ar` -- nhưng selector này
   (đặc tả 0-1-2) thắng `.al/.ac/.ar` (0-1-0) nên mọi tiêu đề cột bị ép canh
   giữa trong khi ô dữ liệu canh trái/phải. Đo trên `data/review100`: 5/6 tờ
   có bảng lệch nhãn-dữ liệu, chỗ nặng nhất 280px.

   Một luật, hai người dựng: `COLUMNS` khai, bộ phát HTML tuân, bảng CSS phủ
   quyết mà không ai báo. */
table.items thead th{{{head_fill}font-weight:700;
  font-size:{_px(base_pt * 0.94)};}}
{zebra}
.al{{text-align:left;}} .ac{{text-align:center;}} .ar{{text-align:right;}}
table.items td span{{display:inline;}}

/* ---- bảng phức: tiêu đề hai tầng, hàng số cột, dòng phân mục, cột gom */
table.items thead tr.tier2 th{{font-size:{_px(base_pt * 0.9)};}}
table.items thead tr.tier3 th{{font-size:{_px(base_pt * 0.88)};}}
table.items thead tr.tier4 th{{font-size:{_px(base_pt * 0.86)};}}
table.items thead tr.banner th{{font-size:{_px(base_pt * 0.98)};
  letter-spacing:.02em;text-transform:none;}}
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
/* CHỖ KÝ CHỪA BẰNG CHIỀU CAO CỦA Ô, không bằng margin của một span RỖNG.
   `.who` rỗng khi tờ chưa có tên người ký, và margin của một span rỗng không
   chiếm chiều cao ô table-cell -- nên khối ký không còn chỗ ký, chân trang
   bám ngay dưới "(Ký, ghi rõ họ tên)". Đo được trên 3/12 tờ. */
.scell{{padding-bottom:{16 if not d.compact_rows else 12}mm;}}
.scell .who{{display:block;margin-top:{4 if not d.compact_rows else 3}mm;
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
/* Mã vạch RỘNG BAO NHIÊU. `display:block` không kèm bề rộng thì nó kéo hết
   chiều ngang khối -- trên khổ A4 là 19cm, trong khi EAN-13 in thật rộng
   37,3mm và Code-128 trên phiếu kho hiếm khi quá 60mm. Một mô hình học trên
   bộ cũ học rằng mã vạch là một dải chạy suốt trang.
   Bề rộng theo seed (`--bw`), nên hai tờ khác nhau không cùng một dải. */
/* Mã vạch THẬT (EAN-13), vẽ bằng SVG nội tuyến -- xem `synthgen/barcode.py`.
   Bản trước là `repeating-linear-gradient`: bốn vạch lặp đúng một chu kỳ, một
   dáng duy nhất cho cả bộ, và dãy vạch không mã hoá con số in dưới nó.
   `color` cho `currentColor` trong SVG bám mực của trang. */
.barcode{{display:block;height:9mm;width:{d.seed % 22 + 38}mm;max-width:100%;
  margin:0 auto 0.8mm;color:{pal.ink};}}
.barcode svg{{display:block;width:100%;height:100%;}}
/* Góc trên bên phải: phiếu gửi xe, vé, thẻ in mã QR ở đây. `position:absolute`
   trong `.sheet` (đã `position:relative`), nên nó không đẩy khối nào xuống. */
.markcorner{{position:absolute;top:{max(d.margins[0] * 0.45, 4):.1f}mm;
  right:{max(d.margins[1] * 0.5, 5):.1f}mm;text-align:center;z-index:2;}}
.markcorner .barcode{{width:32mm;height:7mm;}}
/* Mã QR THẬT, vẽ bằng SVG nội tuyến -- xem `synthgen/qr.py`. Bản trước là
   `repeating-conic-gradient`: một ô bàn cờ đều tăm tắp, không máy nào quét
   được, và chỉ có đúng một dáng cho cả bộ dữ liệu.
   `color` cho `currentColor` trong SVG bám mực của trang. */
.qr{{display:block;width:22mm;height:22mm;color:{pal.ink};}}
.qr svg{{display:block;width:100%;height:100%;}}
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
/* MỤC VĂN XUÔI. Bốn kiểu tiêu đề, lấy từ ảnh thật của `data/pilot16`:
   `vach_mau` là vạch màu dọc bên trái (`I. THÀNH PHẦN THAM DỰ`), `dam_tron`
   là in đậm trơn (`ĐIỀU 1: ĐỐI TƯỢNG ỦY QUYỀN`), thêm gạch dưới và khung.
   Kiểu chốt theo dáng tờ giấy, không bốc lại từng mục -- một văn bản đánh số
   `I.` ở mục đầu thì mục nào cũng thế. */
.sect{{margin-bottom:{gap * 0.85:.2f}mm;}}
.shead{{display:flex;gap:2mm;align-items:baseline;font-weight:700;
  margin-bottom:{gap * 0.35:.2f}mm;}}
.shead .snum{{white-space:nowrap;}}
.shead.vach_mau{{border-left:{max(d.rule_px * 2.4, 0.7):.2f}mm solid {pal.rule};
  padding-left:2.2mm;}}
.shead.gach_duoi{{border-bottom:{rule} solid {pal.rule};padding-bottom:0.6mm;}}
.shead.trong_khung{{border:{rule} solid {pal.rule};padding:0.8mm 1.6mm;
  background:{pal.zebra};}}
/* Đoạn văn: CANH ĐỀU và thụt dòng đầu. Đó là dáng một văn bản hành chính
   thật, và là thứ phân biệt khối này với `notes` (ghi chú ngắn, canh trái). */
.sbody .spara{{text-align:justify;text-indent:{6 if d.compact_rows else 8}mm;
  margin-bottom:{gap * 0.4:.2f}mm;}}
.sbody .spara:last-child{{margin-bottom:0;}}
.fml{{text-align:center;margin:{gap * 0.4:.2f}mm 0;
  padding:{gap * 0.35:.2f}mm 0;border-top:{rule} solid {pal.rule};
  border-bottom:{rule} solid {pal.rule};font-style:italic;}}
/* `color` là cả cách hình SVG đi theo bảng màu của tờ giấy: mọi nét trong
   `textures/figure/*.svg` dùng `currentColor`, nên đặt màu ở đây là đổi cả
   hình mà không sửa một file SVG nào. */
.fig{{display:flex;gap:3mm;justify-content:center;align-items:flex-end;
  height:26mm;margin-bottom:1mm;color:{pal.rule};}}
.fig svg{{height:100%;width:auto;max-width:100%;}}
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
/* CHÍN DẠNG BIỂU MẪU THÊM VÀO. Hình dựng bằng div và CSS grid, không bằng
   `<table>`: `pipeline/tags.py` gắn `<table>` thành vùng `Table`, nên một ma
   trận ô tích in bằng thẻ bảng sẽ đổi nhãn cả cụm từ `Form` sang `Table` --
   mà thứ người ta làm với nó là ĐIỀN, không phải đọc số. */
.survey .qboxes{{display:flex;flex-wrap:wrap;gap:1.4mm 3mm;margin:0.6mm 0 0 5mm;
  align-items:center;}}
.survey .bx{{display:inline-block;min-width:{_px(base_pt * 1.15)};
  height:{_px(base_pt * 1.35)};border:{rule} solid {pal.rule};
  text-align:center;line-height:{_px(base_pt * 1.35)};margin-right:0.5mm;}}
.survey .dgrp{{display:inline-flex;align-items:center;gap:1.2mm;}}
.survey .dlab{{color:{pal.soft};}}
.survey .qgrid{{margin:0.8mm 0 0 5mm;}}
.survey .grow{{display:grid;grid-template-columns:1.6fr repeat(var(--gcols), 1fr);
  align-items:center;border-bottom:{rule} solid {pal.rule};}}
.survey .qtform .grow{{grid-template-columns:repeat(var(--gcols), 1fr);}}
.survey .ghead{{font-weight:700;border-bottom:{max(d.rule_px, 0.3):.2f}mm solid {pal.rule};}}
.survey .gh,.survey .gc,.survey .gv{{text-align:center;padding:0.5mm 0.8mm;}}
.survey .gr{{padding:0.5mm 1.2mm 0.5mm 0;}}
.survey .qtform .gv{{min-height:{_px(base_pt * 1.5)};}}
.survey .qscale{{display:flex;flex-wrap:wrap;align-items:center;gap:1.2mm 2.4mm;
  margin:0.6mm 0 0 5mm;}}
.survey .sc{{display:inline-flex;gap:0.8mm;align-items:baseline;}}
.survey .sl{{color:{pal.soft};font-style:italic;}}
.survey .qrank{{display:flex;flex-wrap:wrap;gap:1mm 4mm;margin:0.6mm 0 0 5mm;}}
.survey .rk{{display:inline-flex;gap:1.2mm;align-items:center;}}
.survey .qinline{{margin:0 0 0 5mm;}}
.survey .iblank{{display:inline-block;min-width:24mm;
  border-bottom:{rule} solid {pal.rule};text-align:center;}}
.survey .qsubq{{display:flex;gap:1.6mm;align-items:baseline;margin:0.4mm 0 0 8mm;}}
.survey .sa{{flex:1;border-bottom:{rule} solid {pal.rule};
  min-height:{_px(base_pt * 1.2)};}}
.survey .qatt{{margin:0.6mm 0 0 5mm;}}
.survey .att{{display:flex;gap:1.2mm;align-items:baseline;}}
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
{_decor_css(d, base_pt)}
"""


# ------------------------------------------------------------------ trang trí


def _mix(color: str, paper: str, share: float) -> str:
    """`share` phần `color` pha vào `paper`, ra một mã hex.

    Tính ở đây chứ không dùng `color-mix()` của CSS: màu nhạt của khung và nền
    hoa văn phải là MỘT con số ghi được trong markup đã lưu, không phải một
    phép tính mà trình duyệt khác có thể làm khác đi."""
    def rgb(code: str) -> tuple[int, int, int]:
        code = code.lstrip("#")
        if len(code) != 6:
            raise ValueError(f"màu phải là #rrggbb, nhận {code!r}")
        return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))

    a, b = rgb(color), rgb(paper)
    return "#" + "".join(f"{round(x * share + y * (1 - share)):02x}"
                         for x, y in zip(a, b))


def _initials(name: str) -> str:
    """Hai chữ cái cho logo chữ lồng, lấy từ mấy chữ CUỐI của tên đơn vị.

    Cùng luật với `generators/html/sheets/base.py::initials` -- "CÔNG TY CỔ
    PHẦN ĐIỆN MÁY HỒNG HÀ" ra "HH", vì mấy chữ đầu chỉ nói đó là một công ty.
    Chép chứ không import: `sheets/base.py` kéo theo `components.table` và chỉ
    nạp được khi `generators/html` nằm trong `sys.path`, còn `markup.py` phải
    nạp được ở mọi chỗ `design.py` nạp được (lượt `--dry-run` không mở trình
    duyệt nào)."""
    skip = {"CONG", "TY", "CO", "PHAN", "TNHH", "MTV", "DOANH", "NGHIEP",
            "TAP", "DOAN", "CHI", "NHANH", "VA", "-", "TONG", "UY", "BAN",
            "NHAN", "DAN", "SO", "PHONG", "TRUONG", "BENH", "VIEN"}
    words = []
    for word in str(name or "").replace("-", " ").split():
        plain = "".join(c for c in unicodedata.normalize("NFD", word)
                        if not unicodedata.combining(c)).upper()
        plain = plain.replace("Đ", "D")
        if plain and plain not in skip and plain[0].isalpha():
            words.append(word)
    picked = words[-2:] if len(words) >= 2 else words
    return "".join(word[0] for word in picked).upper()[:2] or "VN"


_MONOGRAM_CACHE: dict[tuple[str, str, str], str] = {}


def monogram_art(letters: str, color: str, font: str) -> str:
    """Chữ lồng của logo, vẽ thành ẢNH PNG cắt sát nét, trả về data URI.

    Ảnh chứ không phải chữ DOM, vì hai lời hứa của kho này kéo về hai phía:
    `tests/test_synthgen_regions.py` giữ "mọi chữ DOM nằm trong một
    `data-kind`" ở con số 0, còn logo thì là một cái HÌNH -- bọc nó vào
    `data-kind` là khai "HL" thành một dòng chữ của tài liệu, lọt vào markdown
    và KIE. Con dấu đã giải đúng bài này theo cùng cách: vành chữ "CÔNG TY
    ..." nằm trong ảnh (`seal_art`), và cả tấm được đo thành vùng `Stamp`. Ở
    đây `<img>` nằm trong `.logo`, và `page.py::GRAPHIC_RECTS_JS` đo `.logo`
    thành vùng `Image`.

    Cắt sát nét mực vì cùng lý do với `seal_art`: hộp đo được phải là hộp của
    mực, không phải của khoảng trong suốt quanh nó."""
    key = (letters, color, font)
    if key in _MONOGRAM_CACHE:
        return _MONOGRAM_CACHE[key]
    import base64  # noqa: PLC0415 -- chỉ cần khi trang có logo chữ lồng
    import io  # noqa: PLC0415

    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    path = REPO_ROOT / "fonts" / font
    face = ImageFont.truetype(str(path), 180)
    canvas = Image.new("RGBA", (600, 320), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 60), letters, font=face, fill=color)
    box = canvas.getbbox()
    if box is None:
        # Phông không có nét nào cho mấy chữ này: in một logo rỗng là khai
        # một vùng `Image` không có mực -- luật 3 theo chiều ngược lại.
        raise ValueError(f"chữ lồng {letters!r} không ra nét nào với {font}")
    buffer = io.BytesIO()
    canvas.crop(box).save(buffer, format="PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    _MONOGRAM_CACHE[key] = uri
    return uri


def _logo(doc: Doc, d: Design) -> str:
    """Logo của letterhead. `mo` là hình tròn mờ cũ; ba kiểu kia in chữ lồng
    -- xem `monogram_art` về vì sao chữ lồng là ảnh."""
    square = " sq" if d.ornament == "dau_vuong" else ""
    if d.logo_style == "mo":
        return f'<span class="logo{square}"></span>'
    # Nét chữ lồng theo phông TIÊU ĐỀ của tờ: serif thì chữ chân, còn lại
    # chữ không chân. Cả hai tệp đều phủ tiếng Việt (`tools/check_fonts.py`).
    serif = "serif" in d.face.head.lower() and "sans" not in d.face.head.lower()
    font = "serif/DejaVuSerif-Bold.ttf" if serif else "sans/DejaVuSans-Bold.ttf"
    ink = "#ffffff" if d.logo_style == "o_chu" else d.palette.accent
    art = monogram_art(_initials(doc.org_name), ink, font)
    return (f'<span class="logo {d.logo_style}{square}">'
            f'<img src="{art}" alt=""></span>')


def _decor_layer(d: Design) -> str:
    """Lớp trang trí nằm DƯỚI chữ: khung trang và dải màu mép giấy.

    `position:absolute`, nên `draw.py::MEASURE_JS` bỏ qua nó khi đo tờ giấy
    đã đầy tới đâu -- đúng như với dấu và chữ chìm. Không phần tử nào ở đây
    mang chữ, không cái nào khớp selector của `GRAPHIC_RECTS_JS`: một khung
    viền in trên giấy là đường kẻ, cùng loại với đường kẻ bảng, không phải
    một vùng hình."""
    parts = []
    if d.frame != "khong":
        parts.append('<i class="fr"></i>')
        if d.frame in ("an_ninh", "bo_tron", "doi"):
            parts.append('<i class="fr2"></i>')
    if d.band in ("tren", "tren_duoi", "tren_song"):
        parts.append('<i class="bt"></i><i class="bt2"></i>')
    if d.band == "tren_song":
        parts.append('<i class="bw"></i>')
    if d.band == "tren_duoi":
        parts.append('<i class="bb"></i><i class="bb2"></i>')
    if d.band == "trai":
        parts.append('<i class="bl"></i><i class="bl2"></i>')
    if not parts:
        return ""
    return f'<div class="deco" aria-hidden="true">{"".join(parts)}</div>'


def _decor_css(d: Design, base_pt: float) -> str:
    """CSS của năm trục trang trí -- xem `design.PAGE_FRAMES`.

    Mọi kích thước đọc từ LỀ của chính tờ giấy: khung đứng ở 42% lề, dải màu
    cao 36% lề trên. Một con số mm cố định sẽ đè lên chữ ở bộ lề hẹp nhất
    `(14, 12, 12, 18)` trong khi lọt thỏm ở bộ lề rộng nhất."""
    pal = d.palette
    top, right, bottom, left = d.margins
    out = []

    # `isolation:isolate` cho `.sheet` một ngữ cảnh xếp lớp riêng, để lớp
    # trang trí `z-index:-1` nằm TRÊN nền giấy mà DƯỚI chữ. Không có nó thì
    # `z-index:-1` chui xuống dưới cả nền `.sheet` và không thấy gì, còn
    # `z-index` dương thì khung phủ lên chữ.
    out.append(".sheet{isolation:isolate;}"
               ".deco{position:absolute;inset:0;z-index:-1;pointer-events:none;}"
               ".deco i{position:absolute;display:block;}"
               # Mã QR/mã vạch góc phải đứng trên nền giấy riêng, để dải màu
               # hay nền hoa văn không chạy qua các ô mã.
               f".markcorner{{background:{pal.paper};padding:0.8mm;}}")

    inset = round(min(d.margins) * 0.42, 1)
    line = max(d.rule_px, 0.3)
    tint = _mix(pal.accent, pal.paper, 0.22)
    if d.frame == "don":
        out.append(f".deco .fr{{inset:{inset}mm;"
                   f"border:{line:.2f}mm solid {pal.rule};}}")
    elif d.frame == "doi":
        out.append(f".deco .fr{{inset:{inset}mm;"
                   f"border:{line * 1.8:.2f}mm solid {pal.accent};}}"
                   f".deco .fr2{{inset:{inset + 1.4:.1f}mm;"
                   f"border:{line * 0.6:.2f}mm solid {pal.accent};}}")
    elif d.frame == "an_ninh":
        # Khung hoá đơn điện tử: dải rộng in hoa văn chéo nhạt, một đường
        # mảnh bên trong. Hoa văn là `border-image`, nên nó chỉ nằm trên viền.
        band = min(3.2, inset * 0.7)
        deep = _mix(pal.accent, pal.paper, 0.38)
        out.append(f".deco .fr{{inset:{inset - band / 2:.1f}mm;"
                   f"border:{band:.1f}mm solid {tint};"
                   f"border-image:repeating-linear-gradient(45deg,{tint} 0 0.7mm,"
                   f"{deep} 0.7mm 0.9mm,{tint} 0.9mm 1.6mm) 12;}}"
                   f".deco .fr2{{inset:{inset + band / 2 + 0.8:.1f}mm;"
                   f"border:{line * 0.7:.2f}mm solid {pal.accent};}}")
    elif d.frame == "goc":
        # Bốn góc chữ L, vẽ bằng tám dải gradient trên MỘT phần tử.
        arm, w = 11, max(line * 1.6, 0.5)
        c = pal.accent
        g = f"linear-gradient({c},{c})"
        out.append(
            f".deco .fr{{inset:{inset}mm;background:"
            f"{g} left top/{arm}mm {w:.2f}mm,{g} left top/{w:.2f}mm {arm}mm,"
            f"{g} right top/{arm}mm {w:.2f}mm,{g} right top/{w:.2f}mm {arm}mm,"
            f"{g} left bottom/{arm}mm {w:.2f}mm,{g} left bottom/{w:.2f}mm {arm}mm,"
            f"{g} right bottom/{arm}mm {w:.2f}mm,{g} right bottom/{w:.2f}mm {arm}mm;"
            f"background-repeat:no-repeat;}}")
    elif d.frame == "bo_tron":
        out.append(f".deco .fr{{inset:{inset}mm;border-radius:4mm;"
                   f"border:{line * 1.4:.2f}mm solid {pal.accent};}}"
                   f".deco .fr2{{inset:{inset + 1.2:.1f}mm;border-radius:3mm;"
                   f"border:{line * 0.5:.2f}mm solid {tint};}}")

    high = round(top * 0.36, 1)
    if d.band in ("tren", "tren_duoi", "tren_song"):
        tall = high * (0.8 if d.band == "tren_song" else 1.0)
        out.append(f".deco .bt{{top:0;left:0;right:0;height:{tall:.1f}mm;"
                   f"background:{pal.accent};}}"
                   f".deco .bt2{{top:{tall + 1.0:.1f}mm;left:0;right:0;"
                   f"height:0.6mm;background:{tint};}}")
        if d.band == "tren_song":
            # Mép dưới lượn sóng: nửa hình tròn treo dưới dải, lặp theo chiều
            # ngang -- dải "wave" dưới tiêu đề hoá đơn khách sạn.
            out.append(f".deco .bw{{top:{tall - 0.1:.1f}mm;left:0;right:0;height:2.4mm;"
                       f"background:radial-gradient(circle at 50% 0,{pal.accent} 0 1.2mm,"
                       f"transparent 1.25mm) 0 0/4.8mm 2.4mm repeat-x;}}"
                       f".deco .bt2{{top:{tall + 2.8:.1f}mm;}}")
    if d.band == "tren_duoi":
        low = round(bottom * 0.28, 1)
        out.append(f".deco .bb{{bottom:0;left:0;right:0;height:{low:.1f}mm;"
                   f"background:{pal.accent};}}"
                   f".deco .bb2{{bottom:{low + 1.0:.1f}mm;left:0;right:0;"
                   f"height:0.6mm;background:{tint};}}")
    if d.band == "trai":
        wide = round(left * 0.3, 1)
        fade = _mix(pal.accent, pal.paper, 0.55)
        out.append(f".deco .bl{{top:0;bottom:0;left:0;width:{wide:.1f}mm;"
                   f"background:linear-gradient(180deg,{pal.accent},{fade});}}"
                   f".deco .bl2{{top:0;bottom:0;left:{wide + 1.0:.1f}mm;"
                   f"width:0.6mm;background:{tint};}}")

    # Nền hoa văn: pha 7-10% màu nhấn vào màu giấy. Nhạt có chủ đích -- nó
    # nằm DƯỚI mọi nét chữ, và một nền đủ đậm để thấy rõ trên ảnh thu nhỏ là
    # một nền đủ đậm để ăn vào nét chữ nhỏ nhất.
    faint = _mix(pal.accent, pal.paper, 0.10)
    if d.ground == "hoa_van":
        ring = (f"{faint} 0 0.18mm,transparent 0.18mm 1.5mm")
        out.append(f".sheet{{background-image:"
                   f"repeating-radial-gradient(circle at 22% 28%,{ring}),"
                   f"repeating-radial-gradient(circle at 78% 72%,{ring});}}")
    elif d.ground == "ke_cheo":
        out.append(f".sheet{{background-image:repeating-linear-gradient(45deg,"
                   f"{_mix(pal.accent, pal.paper, 0.08)} 0 0.2mm,"
                   f"transparent 0.2mm 2.4mm);}}")
    elif d.ground == "cham_luoi":
        out.append(f".sheet{{background-image:radial-gradient("
                   f"{_mix(pal.accent, pal.paper, 0.14)} 0.28mm,transparent 0.34mm);"
                   f"background-size:3mm 3mm;}}")

    # Logo chữ lồng. `opacity:1` phải có: `.logo` gốc mờ 14%, và một ô màu
    # mờ 14% với chữ trắng trên nó là chữ không đọc được.
    out.append(
        ".logo.o_chu,.logo.vong_chu,.logo.chu_mau{opacity:1;"
        "display:inline-flex;align-items:center;justify-content:center;"
        "width:14mm;height:14mm;}"
        ".logo img{display:block;max-width:72%;max-height:46%;}"
        f".logo.o_chu{{background:{pal.accent};border-radius:1.8mm;}}"
        f".logo.vong_chu{{background:transparent;"
        f"border:0.7mm solid {pal.accent};}}"
        ".logo.vong_chu.sq{border-radius:1.2mm;}"
        ".logo.vong_chu img{max-width:62%;max-height:40%;}"
        ".logo.chu_mau{background:transparent;width:auto;height:auto;"
        "border-radius:0;}"
        f".logo.chu_mau img{{max-width:none;max-height:none;"
        f"height:{_px(base_pt * 1.9)};}}")

    # Điểm nhấn trên khối có sẵn.
    if "tieu_de_mau" in d.accents and not d.reverse_title_band:
        # Tiêu đề đã nằm trên dải màu nhấn thì tô chữ màu nhấn là xoá chữ.
        out.append(f".title .t{{color:{pal.accent};}}")
    if "ghi_chu_the" in d.accents:
        # Ghi chú thành một "thẻ": nền nhạt, vạch màu bên trái -- khung "Hỗ trợ
        # khẩn cấp" của giấy chứng nhận bảo hiểm du lịch ở pipeline chính.
        out.append(f".notes,.notes.boxed{{background:{_mix(pal.accent, pal.paper, 0.08)};"
                   f"border:none;border-left:1.1mm solid {pal.accent};"
                   f"padding:2mm 3mm;border-radius:0 1.2mm 1.2mm 0;}}"
                   f".shead{{color:{pal.accent};}}"
                   f".shead.vach_mau{{border-left-color:{pal.accent};}}"
                   f".shead.trong_khung{{border-color:{pal.accent};"
                   f"background:{_mix(pal.accent, pal.paper, 0.1)};}}")
    if "tong_noi_bat" in d.accents:
        # Dòng tổng cộng thành một dải màu nhấn, chữ trắng -- hộp "TỔNG TIỀN
        # THANH TOÁN" của hoá đơn khách sạn. Mọi màu nhấn trong
        # `design.PALETTES` đủ đậm cho chữ trắng.
        out.append(f".totals .grand{{background:{pal.accent};border-top:none;"
                   f"padding:1.6mm 2.4mm;}}"
                   f".totals .grand .tk,.totals .grand .tv{{color:#ffffff;}}"
                   f".items tfoot tr.grand td{{background:{pal.accent};"
                   f"color:#ffffff;}}")
    if "nhan_mau" in d.accents:
        # Nhãn trường màu nhấn, cột nhãn của bảng tóm tắt tô nền -- cột "Chủ xe
        # cơ giới / Biển số xe" của giấy chứng nhận bảo hiểm xe.
        out.append(f".fields .k,.fields .stack .k,.meta .k{{color:{pal.accent};}}"
                   f".summary td.k{{background:{_mix(pal.accent, pal.paper, 0.1)};"
                   f"color:{pal.strong};}}")
    return "\n".join(out)


# ------------------------------------------------------------------ khối


def _letterhead(doc: Doc, d: Design) -> str:
    if d.head_layout == "khong_letterhead":
        return ""
    # `logo_phai` CŨNG có logo -- tên nó nói thế, và nhánh của nó bên dưới dành
    # hẳn một ô 22% bề ngang cho logo. Bản trước chỉ nhận `*co_logo`, nên ô ấy
    # luôn rỗng: một cột trắng bên phải letterhead trên 1/11 số tờ.
    logo = d.head_layout.endswith("co_logo") or d.head_layout == "logo_phai"
    lines = []
    if doc.parent_org:
        lines.append(_span("store.branch", doc.parent_org, "parent"))
    lines.append(_span("store.name", doc.org_name, "org"))
    if doc.org_branch:
        lines.append(_span("store.branch", doc.org_branch, "line"))
    # NHÃN VÀ GIÁ TRỊ CÙNG MỘT DÒNG. `.head .line` là `display:block`, nên khi
    # cả nhãn lẫn giá trị đều mang class ấy thì "Địa chỉ:" xuống một dòng rồi
    # địa chỉ xuống dòng nữa -- giấy thật in liền. Đo trên `data/review100`:
    # 12/12 tờ mắc, và đó là dấu hiệu nhận diện template rõ nhất của cả bộ.
    #
    # Bọc cặp trong một `<div class="line">` thay vì đổi class của span: hai
    # span vẫn là hai run riêng, nên `key_entity_index` và cặp KIE không đổi
    # một li.
    for kind, label, value in (("store.address", "Địa chỉ:", doc.org_address),
                               ("store.phone", "Điện thoại:", doc.org_phone),
                               ("store.tax_code", "Mã số thuế:", doc.org_tax)):
        lines.append(
            '<div class="line">'
            + _span(f"{kind}.label", label, "lbl", role="key")
            + " " + _span(kind, value, "val", role="value")
            + "</div>")
    if doc.org_website:
        lines.append(_span("store.website", doc.org_website, "line"))
    body = "".join(lines)
    logo_html = _logo(doc, d) if logo else ""

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
        return (f'<div class="blk"><div class="hrow"{D.region_attr("letterhead")}>'
                f'<div class="hcell head" style="width:56%">{logo_html}{body}</div>'
                f'<div class="hcell r">{right}</div></div></div>')

    if d.head_layout == "logo_phai":
        return (f'<div class="blk"><div class="hrow"{D.region_attr("letterhead")}>'
                f'<div class="hcell head">{body}</div>'
                f'<div class="hcell r" style="width:22%">{logo_html}</div>'
                f'</div></div>')

    rule = '<div class="headrule"></div>' if d.head_layout != "dai_mau" else ""
    return (f'<div class="blk"><div class="{cls}"{D.region_attr("letterhead")}>'
            f'{logo_html}{body}</div>{rule}</div>')


def _national(doc: Doc, d: Design) -> str:
    if d.head_layout in ("chia_doi", "chia_doi_co_logo", "hai_cot_cach"):
        return ""      # đã in bên phải letterhead
    # `masthead` / `masthead.motto`, KHÔNG phải `title` / `subtitle`. Dùng
    # chung `kind` với tiêu đề tài liệu là nói rằng quốc hiệu và tên chứng từ
    # là cùng một loại chữ -- một trang ra hai `Title`, và không cái nào trả
    # lời được "tờ này là giấy gì". Đây cũng đúng hai `kind`
    # `generators/html/sheets/form.py::_govt_masthead` đã dùng, nên hai bộ sinh
    # nói cùng một từ vựng thay vì mỗi bên một kiểu.
    return (f'<div class="blk"><div class="natl"{D.region_attr("national")}>'
            f'{_span("masthead", NATIONAL_1, "n1")}'
            f'{_span("masthead.motto", NATIONAL_2, "n2")}'
            f'<div class="nr"></div></div></div>')


def _doctitle(doc: Doc, d: Design) -> str:
    parts = [_span("title", doc.title, "t", key="loai_chung_tu")]
    if doc.subtitle:
        parts.append(_span("subtitle", doc.subtitle, "s"))
    rule = '<div class="trule"></div>' if d.title_style == "hoa_dam_gach_ngan" else ""
    return (f'<div class="blk"><div class="title"{D.region_attr("doctitle")}>'
            f'{"".join(parts)}</div>{rule}</div>')


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
        return (f'<div class="blk"><div class="meta"{D.region_attr("meta")}>'
                f'<div class="mcols">'
                f'<div class="mcol">{left}</div>'
                f'<div class="mcol r">{_span("period", place)}</div>'
                f'</div></div></div>')
    body = "".join(pair(k, v) for k, v in items) + _span("period", place, "m")
    cls = {"duoi_tieu_de_giua": "meta center", "duoi_tieu_de_phai": "meta right",
           "goc_phai_tren": "meta right", "dai_ngang": "meta band",
           "trong_khung_phai": "meta boxed"}[d.meta_style]
    align = ' style="text-align:right"' if d.meta_style == "trong_khung_phai" else ""
    return (f'<div class="blk"{align}><div class="{cls}"{D.region_attr("meta")}>'
            f'{body}</div></div>')


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
        # `fpair` là FLEX, để dòng chấm (`flex:1`) chạy tới lề. `stack` xếp
        # nhãn trên giá trị nên vẫn là block như cũ.
        cells.append((fdef.wide,
                      f'<div class="{"stack" if stack else "fpair"}">{k} {v}</div>'))

    if columns == 1 or stack:
        rows = "".join(f'<div class="frow">{body}</div>' for _wide, body in cells)
        return (f'<div class="blk"><div class="fields"{D.region_attr("fields")}>'
                f'{rows}</div></div>')

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
    return (f'<div class="blk"><div class="fields"{D.region_attr("fields")}>'
            f'{"".join(grid)}</div></div>')


def _checks(doc: Doc, d: Design) -> str:
    if not doc.checks:
        return ""
    rows = "".join(
        f'{_span("invoice.checks.question", q, "q", role="key")}'
        f'{_span("invoice.checks.answer", a, "a", role="value")}'
        for q, a in doc.checks)
    return (f'<div class="blk"><div class="checks"{D.region_attr("checks")}>'
            f'{rows}</div></div>')


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
    return (f'<div class="blk"><div class="basis"{D.region_attr("legal_basis")}>'
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
    return _clauses_slice(doc, d, 0, len(doc.clauses), 0)


# Cách đánh số một mục, và cách in tiêu đề của nó. Bốn kiểu số và bốn kiểu
# trình bày, bốc theo dáng tờ giấy -- lấy từ ảnh thật của `data/pilot16`:
# `I. THÀNH PHẦN THAM DỰ` có vạch màu bên trái, `ĐIỀU 1: ĐỐI TƯỢNG` in đậm
# trơn, và bản báo cáo dùng `1.` `2.` `3.`.
ROMAN = ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
         'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX')
SECTION_NUMBERS = ('roman', 'arabic', 'letter', 'dieu')
SECTION_HEADS = ('vach_mau', 'dam_tron', 'gach_duoi', 'trong_khung')


def _section_label(style: str, index: int) -> str:
    """Số thứ tự của mục thứ `index` (đếm từ 0), theo kiểu `style`."""
    if style == 'roman':
        return f'{ROMAN[index] if index < len(ROMAN) else index + 1}.'
    if style == 'letter':
        return f'{chr(ord("A") + index % 26)}.'
    if style == 'dieu':
        return f'ĐIỀU {index + 1}:'
    return f'{index + 1}.'


def _sections_slice(doc: Doc, d: Design, low: int, high: int,
                    part: int, foot: bool = False, groups: int = 1) -> str:
    """Các MỤC từ `low` đến `high`: tiêu đề có số thứ tự + các đoạn văn xuôi.

    Vì sao khối này tồn tại, bằng phép đo. Đối chiếu nhãn vùng giữa 291 trang
    `data/pilot13..16` (LLM viết) và 899 trang synthgen:

        Section-Header   pilot 48%   synthgen 5%
        Text             pilot 72%   synthgen 60%

    Và nhìn ảnh thì rõ hơn con số: trang pilot là một VĂN BẢN -- `I. THÀNH
    PHẦN THAM DỰ`, `II. NỘI DUNG NGHIỆM THU`, mỗi mục hai ba đoạn canh đều --
    còn trang synthgen không bảng vẫn đọc như một BIỂU MẪU, vì khối chữ dài
    nhất nó có là `clauses`: một dòng tiêu đề cộng một câu.

    Tiêu đề mang `Section-Header`, các đoạn mang `Text`. Đánh số TIẾP qua các
    tờ, cùng luật `_clauses_slice`: một văn bản thật đánh số mục theo cả văn
    bản, tờ sau không quay về `I.`
    """
    chunk = doc.sections[low:high]
    if not chunk:
        return ""
    # Kiểu số và kiểu tiêu đề chốt theo DÁNG tờ giấy, không bốc lại từng mục:
    # một văn bản đánh số `I.` ở mục đầu thì mục nào cũng `I.`-`II.`-`III.`.
    number = SECTION_NUMBERS[d.seed % len(SECTION_NUMBERS)]
    head_style = SECTION_HEADS[(d.seed // 7) % len(SECTION_HEADS)]
    out = []
    for offset, (head, paras) in enumerate(chunk):
        index = low + offset
        label = _section_label(number, index)
        body = "".join(
            f'<div class="spara">{_span("section.body", para, "sb")}</div>'
            for para in paras)
        shell = ""
        if body:
            wrap = D.region_attr("section_body")
            shell = f'<div class="sbody"{wrap}>{body}</div>'
        out.append(
            f'<div class="sect" data-flow-item="1">'
            f'<div class="shead {head_style}"'
            f'{D.region_attr("section_header")}>'
            f'{_span("section.number", label, "snum")}'
            f'{_span("section.head", head, "stext", role="key")}</div>'
            f'{shell}'
            f'</div>')
    return "".join(
        f'<div class="blk" data-flow="sections">{"".join(part_items)}</div>'
        for part_items in _chunks(out, groups) if part_items)


def _sections(doc: Doc, d: Design) -> str:
    """Cả khối mục trên MỘT tờ, cho khi `sections` không phải khối chảy."""
    return _sections_slice(doc, d, 0, len(doc.sections), 0)


def _chunks(items: list[str], groups: int) -> list[list[str]]:
    """Chia `items` thành `groups` phần gần bằng nhau, giữ thứ tự.

    Dùng cho khối chảy trên trang NHIỀU CỘT. `.cols .blk{break-inside:avoid}`
    giữ một khối không bị cắt ngang giữa hai cột -- đó là luật đúng, vì một
    cái hộp trùm cả hai cột lẫn máng giữa chúng không tả được gì trên giấy.
    Hệ quả là một khối chảy dài đổ hết vào MỘT cột và bỏ trắng cột kia. Chia
    sẵn thành mấy khối thì mỗi khối lọt một cột, và mỗi khối vẫn là một vùng
    `List-Group` trọn vẹn -- một danh sách mục, đúng nghĩa cái nhãn ấy."""
    groups = max(int(groups), 1)
    if groups == 1 or len(items) <= 1:
        return [items]
    size = -(-len(items) // groups)
    return [items[i:i + size] for i in range(0, len(items), size)]


def _clauses_slice(doc: Doc, d: Design, low: int, high: int,
                   part: int, foot: bool = False, groups: int = 1) -> str:
    """Các điều từ `low` đến `high`, đánh số TIẾP chứ không quay về 1.

    Cùng luật với bảng chạy qua hai tờ (`_table`): tờ sau in "Điều 12." chứ
    không in lại "Điều 1.", vì một văn bản thật đánh số điều theo cả văn bản.
    `foot` không dùng ở đây -- khối tổng chỉ đi với bảng -- nhưng vẫn nhận, để
    mọi bộ dựng khối chảy có cùng một chữ ký và `markup()` gọi chúng như nhau.
    """
    chunk = doc.clauses[low:high]
    if not chunk:
        return ""
    items = []
    for offset, (head, body) in enumerate(chunk):
        number = low + offset + 1
        items.append(
            f'<div class="cl" data-flow-item="1">'
            f'{_span("clause.head", f"Điều {number}. {head}", "ch")}'
            f'{_span("clause.body", body, "cb")}</div>')
    return "".join(
        f'<div class="blk" data-flow="clauses">'
        f'<div class="clauses"{D.region_attr("clauses")}>'
        f'{"".join(part_items)}</div></div>'
        for part_items in _chunks(items, groups) if part_items)


def _formula(doc: Doc, d: Design) -> str:
    """Công thức tính -- `Formula`. Một dòng đẳng thức bằng chữ, đúng như giấy
    bảo hiểm và viện phí in ra, không phải ký hiệu toán."""
    if not doc.formula:
        return ""
    return (f'<div class="blk"><div class="fml"{D.region_attr("formula")}>'
            f'{_span("formula", doc.formula)}</div></div>')


FIGURE_DIR = REPO_ROOT / "textures" / "figure"
_FIGURE_CACHE: dict[str, str] = {}


def figure_art(seed: int) -> str:
    """Một hình SVG trong `textures/figure/`, bốc theo seed. Rỗng nếu kho rỗng.

    ĐỌC THƯ MỤC chứ không kê tên trong mã: thêm một file .svg vào đó là bộ dữ
    liệu có thêm một dáng hình, không phải sửa file này. Cùng lệ
    `rulebase/corpus/` và `rulebase/synthgen/`.

    Mọi nét trong kho dùng `currentColor`, nên hình đi theo màu của tờ giấy
    mà không cần sửa file SVG nào -- xem `mk_figures.py` và `.fig{color:…}`.

    Nhớ theo tiến trình: một shard trăm trang dùng lại cùng mười hai file, và
    đọc đĩa cho từng tờ là trả một cái giá cố định một trăm lần. Cùng lý do
    `seal_art()` có `_SEAL_CACHE`."""
    if not _FIGURE_CACHE:
        if not FIGURE_DIR.is_dir():
            return ""
        for path in sorted(FIGURE_DIR.glob("*.svg")):
            try:
                _FIGURE_CACHE[path.stem] = path.read_text(encoding="utf-8")
            except OSError:
                continue
        if not _FIGURE_CACHE:
            return ""
    names = sorted(_FIGURE_CACHE)
    return _FIGURE_CACHE[names[seed % len(names)]]


def _figure(doc: Doc, d: Design) -> str:
    """Sơ đồ + chú thích -- `Figure` và `Caption`, hai vùng cạnh nhau.

    Khung sơ đồ là mực không phải chữ, nên nó không mang `data-kind` nào; câu
    chú thích bên dưới thì có. Đó là cặp `Figure`/`Caption` mà mọi bộ nhãn bố
    cục đều có và bộ sinh này chưa từng vẽ.

    Hình lấy từ `textures/figure/`. Bản trước vẽ ĐÚNG BA HỘP RỖNG cho mọi tờ
    giấy, nên nhãn `Figure` có mặt trên bộ dữ liệu mà thứ nằm dưới nhãn ấy
    chỉ là một dáng duy nhất -- một mô hình học được "Figure nghĩa là ba hình
    chữ nhật". Mười hai hình trong kho là biểu đồ cột, đường, tròn, sơ đồ tổ
    chức, mặt bằng, sơ đồ vị trí, dòng chảy quy trình, mặt cắt.

    Ba hộp rỗng GIỮ LẠI làm đường lùi: mất thư mục `textures/figure/` thì tờ
    giấy vẫn có một khối `Figure` để đo, không phải một khối rỗng."""
    if not doc.caption:
        return ""
    art = figure_art(doc.seed)
    inner = art or ('<span class="fbox"></span><span class="fbox"></span>'
                    '<span class="fbox"></span>')
    return (f'<div class="blk">'
            f'<div class="fig"{D.region_attr("figure")} data-graphic="diagram">'
            f'{inner}</div>'
            f'<div class="fcap"{D.region_attr("figure_caption")}>'
            f'{_span("caption.figure", doc.caption)}</div></div>')


def _footnote(doc: Doc, d: Design) -> str:
    """Ghi chú có dấu sao -- `Footnote`. Khác `notes`: ngắn, cuối tờ, và mở
    đầu bằng một dấu trỏ ngược lên chỗ nó chú thích."""
    if not doc.footnotes:
        return ""
    rows = "".join(f'<div class="fn">{_span("footnote", line)}</div>'
                   for line in doc.footnotes)
    return (f'<div class="blk"><div class="fnotes"{D.region_attr("footnote")}>'
            f'{rows}</div></div>')


def _toc(doc: Doc, d: Design) -> str:
    """Mục lục -- `Table-Of-Contents`. Chỉ in khi tài liệu đủ dài để có mục."""
    if not doc.toc:
        return ""
    rows = "".join(
        f'<div class="tocrow">{_span("toc.title", title, "tt")}'
        f'<span class="dots"></span>{_span("toc.page", page, "tp")}</div>'
        for title, page in doc.toc)
    return (f'<div class="blk"><div class="toc"{D.region_attr("toc")}>'
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
    return _questions_slice(doc, d, 0, len(doc.questions), 0)


def _tickbox(on: bool) -> str:
    """Một ô tích. Ô và NHÃN của nó luôn là hai run riêng -- xem `_questions`."""
    return _span("survey.tick", "☒" if on else "☐", "tk",
                 key=("ticked" if on else "empty"))


def _shape_rows(item: dict) -> list[str]:
    """Phần thân của một câu hỏi, theo dạng của nó.

    MƯỜI HAI DẠNG, không ba. Bản trước có `blank`/`yesno`/`options`, và ba
    dạng ấy vẽ ra ba hình rất giống nhau: một dòng hỏi, một dòng kẻ hoặc một
    hàng ô tích. Một mô hình học trên bộ ấy gặp một tờ khai thật -- dãy ô
    vuông từng ký tự cho số căn cước, ma trận tích chéo hàng-cột, thang điểm
    năm mức, bảng người ta điền tay -- thì không thấy thứ nào quen.

    Chín dạng thêm vào đều là thứ giấy tờ Việt Nam thật in ra, và đều giữ
    đúng lệ nhãn của khối này: mọi run mang `data-kind` họ `survey.`, nên
    `pipeline/record.py` gọi cả khối là `Form`; ô tích và nhãn của nó là hai
    run riêng, để toạ độ nói được ô NÀO đã tích.

    KHÔNG dùng thẻ `<table>` cho `grid` và `table_form`, dù chúng trông như
    bảng: `pipeline/tags.py` gắn `<table>` thành vùng `Table`, nên một ma
    trận ô tích in bằng `<table>` sẽ đổi nhãn cả cụm từ `Form` sang `Table`
    -- và thứ người ta làm với nó là ĐIỀN, không phải đọc số. Dựng bằng div
    và CSS grid thì hình vẫn là bảng mà nhãn vẫn đúng.
    """
    shape = item["shape"]
    rows: list[str] = []

    if shape in ("options", "yesno"):
        picked = item.get("picked") or set()
        if shape == "yesno":
            picked = {item.get("ticked")}
        boxes = "".join(
            f'<span class="opt">{_tickbox(o in picked)}'
            f'{_span("survey.option", o, "ol", role="value")}</span>'
            for o in item["options"])
        rows.append(f'<div class="qopts">{boxes}</div>')

    elif shape == "boxchar":
        # Dãy ô vuông, mỗi ô MỘT ký tự -- số căn cước, mã số thuế, số tài
        # khoản. Ô trống ở cuối vẫn in ra: tờ khai in đủ số ô dù người điền
        # viết ngắn hơn, và một mô hình phải học được chỗ trống cũng là ô.
        value = str(item.get("value") or "")
        cells = max(int(item.get("cells") or len(value)), len(value))
        boxes = "".join(
            f'<span class="bx">'
            f'{_span("survey.char", value[i] if i < len(value) else "", "bc", role="value")}'
            f'</span>' for i in range(cells))
        rows.append(f'<div class="qboxes">{boxes}</div>')

    elif shape == "date_boxes":
        parts = []
        for label, text, width in (("Ngày", item.get("day"), 2),
                                   ("Tháng", item.get("month"), 2),
                                   ("Năm", item.get("year"), 4)):
            text = str(text or "")
            boxes = "".join(
                f'<span class="bx">'
                f'{_span("survey.char", text[i] if i < len(text) else "", "bc", role="value")}'
                f'</span>' for i in range(width))
            parts.append(f'<span class="dgrp">'
                         f'{_span("survey.prompt", label, "dlab")}{boxes}</span>')
        rows.append(f'<div class="qboxes">{"".join(parts)}</div>')

    elif shape == "grid":
        cols = list(item.get("cols") or ())
        head = "".join(_span("survey.colhdr", c, "gh") for c in cols)
        body = []
        picked = item.get("picked") or {}
        for index, label in enumerate(item.get("rows") or ()):
            cells = "".join(f'<span class="gc">{_tickbox(picked.get(index) == j)}</span>'
                            for j in range(len(cols)))
            body.append(f'<div class="grow">'
                        f'{_span("survey.rowhdr", label, "gr", role="key")}{cells}</div>')
        rows.append(f'<div class="qgrid" style="--gcols:{len(cols)}">'
                    f'<div class="grow ghead"><span class="gr"></span>{head}</div>'
                    f'{"".join(body)}</div>')

    elif shape == "scale":
        levels = max(int(item.get("levels") or 5), 2)
        picked = int(item.get("picked") or 0)
        marks = "".join(
            f'<span class="sc">{_tickbox(picked == n)}'
            f'{_span("survey.option", str(n), "ol", role="value")}</span>'
            for n in range(1, levels + 1))
        rows.append(f'<div class="qscale">'
                    f'{_span("survey.prompt", str(item.get("low_label") or ""), "sl")}'
                    f'{marks}'
                    f'{_span("survey.prompt", str(item.get("high_label") or ""), "sl")}'
                    f'</div>')

    elif shape == "rank":
        order = list(item.get("order") or ())
        marks = "".join(
            f'<div class="rk">'
            f'<span class="bx">{_span("survey.char", str(order[i]) if i < len(order) else "", "bc", role="value")}</span>'
            f'{_span("survey.option", text, "ol", role="key")}</div>'
            for i, text in enumerate(item.get("items") or ()))
        rows.append(f'<div class="qrank">{marks}</div>')

    elif shape == "inline_blank":
        # Điền GIỮA câu. Câu gốc mang dấu `…`; mỗi chỗ trống thành một run
        # riêng có gạch chân, nên hộp của nó tả đúng chỗ người ta viết vào
        # chứ không trùm cả câu.
        answers = list(item.get("answers") or ())
        chunks = str(item.get("prompt") or "").split("…")
        line = []
        for i, chunk in enumerate(chunks):
            if chunk:
                line.append(_span("survey.prompt", chunk, "ib"))
            if i < len(chunks) - 1:
                line.append(_span("survey.answer",
                                  answers[i] if i < len(answers) else "",
                                  "iblank", role="value"))
        rows.append(f'<div class="qinline">{"".join(line)}</div>')

    elif shape == "subquestion":
        for label, answer in item.get("subs") or ():
            rows.append(f'<div class="qsubq">'
                        f'{_span("survey.prompt", label, "sq", role="key")}'
                        f'{_span("survey.answer", answer, "sa", role="value")}</div>')

    elif shape == "table_form":
        cols = list(item.get("cols") or ())
        head = "".join(_span("survey.colhdr", c, "gh") for c in cols)
        body = []
        for line in item.get("rows") or ():
            cells = "".join(
                _span("survey.cell", line[j] if j < len(line) else "", "gv",
                      role="value") for j in range(len(cols)))
            body.append(f'<div class="grow">{cells}</div>')
        rows.append(f'<div class="qgrid qtform" style="--gcols:{len(cols)}">'
                    f'<div class="grow ghead">{head}</div>{"".join(body)}</div>')

    elif shape == "attachment":
        picked = item.get("picked") or set()
        marks = "".join(
            f'<div class="att">{_tickbox(text in picked)}'
            f'{_span("survey.option", text, "ol", role="value")}</div>'
            for text in item.get("items") or ())
        rows.append(f'<div class="qatt">{marks}</div>')

    return rows


def _questions_slice(doc: Doc, d: Design, low: int, high: int,
                     part: int, foot: bool = False, groups: int = 1) -> str:
    """Các câu từ `low` đến `high`, đánh số TIẾP. Xem `_clauses_slice`."""
    chunk = doc.questions[low:high]
    if not chunk:
        return ""
    out = []
    for number, item in enumerate(chunk, start=low + 1):
        # `inline_blank` KHÔNG in dòng hỏi riêng: cả câu hỏi nằm trong chính
        # dòng có chỗ trống ("Tôi tên là …, sinh ngày …"), nên in thêm một
        # dòng hỏi là in câu ấy hai lần.
        if item["shape"] == "inline_blank":
            rows = [f'<div class="qq">'
                    f'{_span("survey.number", f"{number}.", "qn")}</div>']
        else:
            question = _span("survey.question", item["prompt"], "qt",
                             role="key", shape=item["shape"])
            rows = [f'<div class="qq">{_span("survey.number", f"{number}.", "qn")}'
                    f'{question}</div>']
        rows.extend(_shape_rows(item))
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
        out.append(f'<div class="qitem"{D.region_attr("questions")} data-flow-item="1">'
                   f'{"".join(rows)}</div>')
    return "".join(
        f'<div class="blk" data-flow="questions">'
        f'<div class="survey">{"".join(part_items)}</div></div>'
        for part_items in _chunks(out, groups) if part_items)


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
    return (f'<div class="blk"><div class="{cls}"{D.region_attr("notes")}>'
            f'{rows}</div></div>')


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
    """Khối `<thead>`: bao nhiêu tầng cũng được, cộng hàng số cột nếu có.

    Nhiều tầng dựng bằng `colspan` cho ô gộp và `rowspan` cho ô đứng riêng --
    đúng cách một bảng kê nhà nước hay một tờ khai hải quan in ra, và là dáng
    mà bảng một tầng không dạy được mô hình đọc. Hộp của ô gộp do chính trình
    duyệt đo (`page.py::CELL_REGIONS_JS` đọc `colSpan`/`rowSpan`), nên không
    có gì phải khai thêm.

    LUẬT XẾP, đúng một câu cho mọi tầng: **mỗi ô bắt đầu ngay dưới dải hẹp
    nhất bao nó, và kéo dài xuống tới khi gặp dải đầu tiên nằm trong nó** --
    tức tới đáy `<thead>` nếu nó không chứa gì.

    Bản trước dựng ba danh sách `top/middle/bottom` viết tay, nên ba tầng là
    trần cứng và tầng thứ tư nghĩa là viết lại cả ba. Câu luật trên không đếm
    tầng, nên nó dựng được bốn tầng bằng đúng số dòng đã dựng ba."""
    offset = 1 if rail else 0

    # Cắt mọi dải về số cột THẬT của bảng trước khi tính gì: `keys` đã lọc bỏ
    # khoá không có trong `COLUMNS`, còn các dải dựng theo `design.columns`,
    # nên một dải có thể thò ra ngoài mép bảng. Một `colspan` thò ra là một
    # hàng tiêu đề rộng hơn thân bảng -- trình duyệt vẫn vẽ, và cái bảng lệch
    # ấy đi thẳng vào nhãn.
    bands: list[list[tuple[str, int, int]]] = []
    for tier in doc.col_bands:
        kept = [(caption, first, min(width, len(keys) - first))
                for caption, first, width in tier if first < len(keys)]
        kept = [band for band in kept if band[2] >= 1]
        if kept:
            bands.append(kept)
    rows_n = len(bands) + 1

    # `data-row` của tiêu đề đếm ÂM theo tầng: tầng trên cùng là 0 (đúng như
    # bảng một tầng vẫn ghi), rồi -1, -2, -3, và hàng số cột tiếp ngay sau
    # tầng cuối. Dòng hàng đánh số từ 1 trở lên, nên hai dãy không bao giờ
    # đụng nhau và một trình đọc phân biệt được "ô này ở tầng nào" mà không
    # phải đoán. Hàng số cột KHÔNG còn đóng cứng ở -3: với bảng bốn tầng, -3
    # đã là một tầng tiêu đề thật.
    def cell(key: str, col: int, tier: int, down: int) -> str:
        title = doc.col_titles.get(key, COLUMNS[key]["titles"][0])
        span = f' rowspan="{down}"' if down > 1 else ""
        return (f'<th class="a{COLUMNS[key]["align"][0]}" data-cell="colhdr" '
                f'data-row="{-tier}" data-col="{col}"{span}>'
                f'{_span("colhdr", title)}</th>')

    def gathered(caption: str, col: int, width: int, tier: int, down: int) -> str:
        span = f' rowspan="{down}"' if down > 1 else ""
        return (f'<th class="ac" data-cell="colhdr" data-row="{-tier}" '
                f'data-col="{col + offset}" colspan="{width}"{span}>'
                f'{_span("colhdr", caption)}</th>')

    if rows_n < 2:
        lead = ""
        if rail:
            lead = ('<th class="ac" data-cell="colhdr" data-row="0" '
                    f'data-col="0">{_span("colhdr", "Nhóm")}</th>')
        rows = (f'<tr>{lead}'
                + "".join(cell(k, c + offset, 0, 1) for c, k in enumerate(keys))
                + '</tr>')
    else:
        # Tầng SÂU NHẤT phủ mỗi cột. Ô lá của cột ấy bắt đầu ngay dưới nó.
        under = [-1] * len(keys)
        for tier, level in enumerate(bands):
            for _, first, width in level:
                for col in range(first, first + width):
                    under[col] = max(under[col], tier)

        def opens_at(first: int, tier: int) -> int:
            """Hàng mà một ô ở tầng `tier`, bắt đầu ở cột `first`, mở ra."""
            above = [t for t in range(tier)
                     if any(f <= first < f + w for _, f, w in bands[t])]
            return max(above) + 1 if above else 0

        at: list[list[tuple[int, str]]] = [[] for _ in range(rows_n)]
        for tier, level in enumerate(bands):
            for caption, first, width in level:
                row = opens_at(first, tier)
                at[row].append(
                    (first, gathered(caption, first, width, row, tier - row + 1)))
        for col, key in enumerate(keys):
            row = under[col] + 1
            at[row].append((col, cell(key, col + offset, row, rows_n - row)))

        lead = ""
        if rail:
            lead = (f'<th class="ac" data-cell="colhdr" data-row="0" '
                    f'data-col="0" rowspan="{rows_n}">'
                    f'{_span("colhdr", "Nhóm")}</th>')
        # Dải chạy hết chiều ngang được gọi tên riêng: nó không phải một
        # tầng tiêu đề CỘT, nó là một dòng phân mục nằm trong khung bảng, và
        # trên giấy thật nó in đậm hơn chứ không nhỏ dần như các tầng dưới.
        banner = (len(bands[0]) == 1 and bands[0][0][1] == 0
                  and bands[0][0][2] >= len(keys))
        rows = ""
        for row in range(rows_n):
            cls = f' class="tier{row + 1}"' if row else ""
            if row == 0 and banner:
                cls = ' class="banner"'
            line = "".join(html for _, html in sorted(at[row]))
            rows += f'<tr{cls}>{lead if row == 0 else ""}{line}</tr>'

    numbers = ""
    if d.col_numbers:
        # Hàng "(1) (2) (3)": chữ in trên giấy tờ nhà nước để các mục phía
        # dưới trỏ ngược lên cột. Nó là một hàng THẬT trong `<thead>`, nên nó
        # được lặp lại ở đầu mỗi tờ đúng như tiêu đề cột.
        cells = ""
        if rail:
            cells += ('<th class="ac" data-cell="colnum" '
                      f'data-row="{-rows_n}" '
                      f'data-col="0">{_span("colnum", "(0)")}</th>')
        cells += "".join(
            f'<th class="ac" data-cell="colnum" data-row="{-rows_n}" '
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
           foot: bool = False, groups: int = 1) -> str:
    # `groups` nhận mà KHÔNG dùng, để ba bộ dựng khối chảy cùng một chữ ký.
    # Một cái bảng bảy cột nhét vào cột rộng 8cm thì chữ vỡ ra từng ký tự,
    # nên bảng không bao giờ được chia cột -- `markup()` giữ tờ mang bảng ở
    # một cột, xem `COLUMN_SAFE_FLOWS`.
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
        body.append(f'<tr class="itemrow" data-flow-item="1">'
                    f'{"".join(tds)}</tr>')

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
        # CHÚ THÍCH BẢNG PHẢI TỰ KHAI VÙNG, vì `<table>` cố tình không khai.
        # Vùng `Table` do `CELL_REGIONS_JS` dựng TỪ CHÍNH CÁC Ô, nên câu chú
        # thích -- nằm NGOÀI `<table>` -- không tổ tiên nào ôm. Đo được: seed
        # 20, run `caption.table: 'NỘI DUNG CHI TIẾT'` rơi khỏi mọi vùng.
        # Cùng cặp `Figure`/`Caption` mà `_figure` đã dựng ngay trên.
        caption = (f'<div{D.region_attr("table_caption")}>'
                   f'{_span("caption.table", doc.table_caption, "tcap")}</div>')
    money_key = keys[money_col] if money_col >= 0 else keys[-1]
    tfoot = (_tfoot(doc, d, width, high,
                    money_col + offset if money_col >= 0 else -1,
                    need.get(money_key, 12.0) / total * table_chars - PAD_CHARS)
             if foot else "")
    # `data-flow` / `data-flow-item`: chỗ DUY NHẤT `draw.MEASURE_JS` tìm khối
    # chảy và các mục của nó. Trước đây nó tìm `table.items` và `tr.itemrow`,
    # tức là tên của một khối cụ thể viết trong JavaScript -- nên thêm một
    # khối chảy khác là phải sửa cả câu truy vấn ấy, và quên sửa thì phép đo
    # im lặng trả về sức chứa bằng không.
    return (f'<div class="blk" data-flow="table">{caption}'
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
    return (f'<div class="blk"><div class="{cls}"{D.region_attr("totals")}>'
            f'{rows}{grand}</div></div>')


def _words(doc: Doc, d: Design) -> str:
    if not doc.words:
        return ""
    return (f'<div class="blk"><div class="words"{D.region_attr("words")}>'
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
    date_line = _span("sign.signedat", place, "sdate",
                      region=D.block_region("sign_date")) if (
        d.sign_style in ("trai_phai", "chi_ben_phai", "cot_deu")
        and not printed_by_meta) else ""
    cells = []
    for caption, who in doc.signatures:
        hint = _span("sign.note", "(Ký, ghi rõ họ tên)", "hint")
        name = _span("sign.name", who, "who") if who else _span(
            "sign.note", "", "who")
        # VÙNG KHAI Ở TỪNG Ô KÝ, không ở khung bọc.
        #
        # Trước đây `data-region` nằm trên `div.signs` -- khung bọc mọi ô -- nên
        # cả cụm chữ ký ra MỘT vùng. Thấy được trên
        # `data/smoke_inkbox2/sample/layout_boxes/cv_dao_tao_boi_duong_00010_p2.jpg`:
        # một hộp `Text` trải từ "NƠI NHẬN" sang tận "TM. THỦ TRƯỞNG ĐƠN VỊ",
        # gộp tiêu đề của hai người ký khác nhau vào cùng một khung.
        #
        # Một tờ giấy có hai người ký là hai chỗ ký RIÊNG: hai chức danh, hai
        # chữ ký, hai con người. Gộp lại thì không tách được ai ký chỗ nào, và
        # hộp ấy cũng rỗng ở khoảng giữa hai ô.
        cells.append(f'<div class="scell"{D.region_attr("signatures")}>'
                     f'{_span("sign.title", caption, "cap")}'
                     f'{hint}{name}</div>')
    cls = "signs"
    if d.sign_style == "co_khung":
        cls += " boxed"
    if d.sign_style == "co_dong_ke":
        cls += " ruled"
    if d.sign_style == "chi_ben_phai":
        cls += " right"
        cells = cells[-1:]
    return (f'<div class="blk">{date_line}<div class="{cls}">'
            f'{"".join(cells)}</div></div>')


def _footer(doc: Doc, d: Design) -> str:
    if not doc.footer:
        return ""
    return (f'<div class="blk"><div class="foot"{D.region_attr("footer")}>'
            f'{_span("footer", doc.footer)}</div></div>')


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

# Con dấu nào CHỈ dùng cho hồ sơ nào. Hai file trong kho có TÊN PHÁP NHÂN in
# sẵn trong ảnh -- `seal_round_hotel` đóng chữ "CÔNG TY TNHH KHÁCH SẠN THÁI
# AN" -- nên bốc mù theo seed thì một hoá đơn viện phí mang con dấu khách
# sạn. Đo được trên một trang vẽ thật.
#
# Dấu không có tên trong danh sách này dùng được cho mọi hồ sơ: `company` và
# `company_double` chỉ có vành chữ chung chung, `square_paid` là "ĐÃ THANH
# TOÁN", `square_copy` là "BẢN SAO".
SEAL_ONLY_FOR: dict[str, tuple[str, ...]] = {
    "seal_round_hotel": ("hotel",),
    "seal_round_export": ("export", "invoice"),
    # "ĐÃ THU TIỀN / PAID" là con dấu của bên NHẬN tiền. Không có cổng thì nó
    # đóng lên phiếu CHI (ngược nghĩa: phiếu chi là lúc trả tiền ra), lên thẻ
    # bảo hành (bảo hành không thu tiền) và lên hợp đồng -- 3/12 tờ đo được
    # trên `data/review100`. Một con dấu sai nghĩa tệ hơn không có dấu: nó dạy
    # mô hình rằng dấu ấy xuất hiện ở đâu cũng được.
    "seal_square_paid": ("invoice", "export", "shop", "menu", "hotel",
                         "power", "water"),
}


def seals_for(name: str, profile: str) -> tuple[str, ...]:
    """Nhóm dấu `name`, đã bỏ những con dấu không hợp hồ sơ `profile`.

    Lọc hết thì trả về nhóm gốc: một tờ giấy có dấu sai còn hơn một tờ giấy
    lẽ ra có dấu mà không có -- và trường hợp ấy chỉ xảy ra nếu ai đó thu hẹp
    `SEAL_ONLY_FOR` tới mức không còn con dấu chung nào."""
    group = SEALS.get(name) or ()
    kept = tuple(stem for stem in group
                 if profile in SEAL_ONLY_FOR.get(stem, (profile,)))
    return kept or group

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


def _barcode_art(doc: Doc) -> str:
    """SVG mã vạch của tờ giấy, hoặc chuỗi rỗng khi không dựng được.

    Cùng lẽ `_qr_art`: nuốt lỗi ở đây chứ không để nó lan, vì một tờ mất mã
    vạch vẫn là một tờ dùng được, còn một lượt vẽ chết vì một số hiệu lạ thì
    mất cả shard. Ô `.barcode` vẫn giữ chỗ và vẫn khai `data-graphic`, nên
    thiếu SVG là thiếu MỰC -- thứ `make check-boxes` thấy được.
    """
    try:
        from synthgen import barcode  # noqa: PLC0415 -- chỉ cần khi có mã
        return barcode.svg(barcode.payload_for(doc))
    except Exception:  # noqa: BLE001 -- xem docstring
        return ""


def _qr_art(doc: Doc, d: Design) -> str:
    """SVG mã QR của tờ giấy này, hoặc rỗng nếu mã hoá không được.

    Rỗng chứ không ném: một tờ giấy thiếu mã QR vẫn là một tờ giấy dùng được,
    còn một lượt vẽ chết vì một chuỗi lạ thì mất cả shard. Ô `.qr` vẫn giữ
    kích thước nên bố cục không xô lệch."""
    try:
        from synthgen import qr  # noqa: PLC0415 -- chỉ cần khi tờ giấy có mã

        return qr.svg(qr.payload_for(doc, d))
    except Exception:                                        # noqa: BLE001
        return ""


def _ornament(doc: Doc, d: Design, corner: bool = False) -> str:
    """Mực không phải chữ chạy: dấu, mã vạch, mã QR. Mỗi thứ vẫn mang một
    `data-kind` riêng, vì mực không có hộp là mực không có nhãn.

    `corner` in mã vào GÓC TRÊN BÊN PHẢI thay vì thành một khối trong mạch
    nội dung -- phiếu gửi xe, vé, thẻ in ở đấy. Con dấu không đổi chỗ theo cờ
    này: dấu vốn đã `position:absolute` và có chỗ riêng của nó."""
    name = d.ornament
    if name == "khong":
        return ""
    if name in ("ma_vach", "ma_qr"):
        # KHÔNG DỰNG ĐƯỢC MÃ THÌ KHÔNG KHAI VÙNG.
        #
        # `_barcode_art`/`_qr_art` nuốt lỗi và trả chuỗi rỗng, để một số hiệu lạ
        # không giết cả shard. Nhưng nếu vẫn in cái span mang `data-graphic` thì
        # ra một vùng `Image` KHÔNG CÓ MỰC -- luật 3 của `AGENTS.md` theo chiều
        # ngược lại, và là thứ không ai phát hiện vì "vùng rỗng" trông y hệt
        # "vùng có hình nhạt". Đã dính đúng một lần: bỏ gradient CSS của
        # `.barcode` mà quên nối SVG cho nhánh `dau_tron_va_ma_vach`, ra 12 ô
        # trắng trên 20 ô của `data/smoke_inkbox2`.
        art = _barcode_art(doc) if name == "ma_vach" else _qr_art(doc, d)
        if not art:
            return ""
        inner = (f'<span class="barcode" data-graphic="barcode">{art}</span>'
                 if name == "ma_vach"
                 else f'<span class="qr" data-graphic="qr">{art}</span>')
        code = f"{doc.doc_serial}{doc.doc_no}".replace("/", "")
        cls = "markcorner mark" if corner else "blk mark"
        return (f'<div class="{cls}">{inner}'
                f'{_span("menu.barcode", code, region=D.block_region("barcode"))}'
                f'</div>')
    # Con dấu nào trong nhóm là hàm thuần của seed: cùng tờ giấy thì cùng con
    # dấu, mà hai tờ khác nhau không đóng chung một cái. Nhóm đã lọc theo hồ
    # sơ trước -- xem `SEAL_ONLY_FOR`.
    profile = d.archetype.profile
    pick = lambda group: group[d.seed % len(group)]  # noqa: E731
    if name == "dau_tron_va_ma_vach":
        code = f"{doc.doc_serial}{doc.doc_no}".replace("/", "")
        # EMITTER THỨ HAI của ô mã vạch, và nó từng bị bỏ quên.
        #
        # Khi `.barcode` còn vẽ bằng `repeating-linear-gradient` thì nhánh này
        # in ra một span RỖNG mà vẫn có vạch, vì vạch do CSS vẽ. Bỏ gradient đi
        # rồi mà chỉ nối SVG ở nhánh `ma_vach` thì nhánh này ra một ô hoàn toàn
        # TRẮNG -- mà vẫn khai `data-graphic="barcode"`, tức một vùng `Image`
        # không có lấy một hạt mực. Thấy được trên
        # `data/smoke_inkbox2/sample/layout_boxes/bk_to_chuc_can_bo_00009.jpg`:
        # khung `Image` rỗng ngay dưới tiêu đề. Đếm cả bộ: 12 ô rỗng / 20 ô.
        art = _barcode_art(doc)
        seal = _seal(d, pick(seals_for("dau_tron", profile)), 6, -32)
        if not art:
            # Mất mã vạch thì còn con dấu; khai một ô mã trắng thì không.
            return seal
        return (f'<div class="blk mark">'
                f'<span class="barcode" data-graphic="barcode">{art}</span>'
                f'{_span("menu.barcode", code, region=D.block_region("barcode"))}'
                f'</div>' + seal)
    fallback = "dau_tron" if name == "chim_mo" else "dau_vuong"
    group = seals_for(name, profile) or seals_for(fallback, profile)
    return _seal(d, pick(group), 8, -34)


def _photo(doc: Doc, d: Design) -> str:
    if not d.photo_box:
        return ""
    return (f'<div class="photo"{D.region_attr("photo")}>'
            f'{_span("photo.placeholder", "ẢNH")}<br>'
            f'{_span("photo.size", "4 x 6")}</div>')


# Khối chạy hết chiều ngang, không bao giờ chảy vào cột. Tiêu đề, quốc hiệu,
# ô ảnh, con dấu là những thứ một tờ giấy in ngang trang; chữ ký và chân trang
# là một dải cuối trang.
FULL_WIDTH = frozenset({"photo", "letterhead", "doctitle", "meta",
                        "signatures", "footer", "ornament"})

# Trong số đó, những khối in SAU phần chảy cột.
_AFTER_FLOW = frozenset({"signatures", "footer", "ornament"})

def _table_whole(doc: Doc, d: Design) -> str:
    """Cả cái bảng trên MỘT tờ, cho khi bảng KHÔNG phải khối chảy.

    Từ khi khối chảy tách khỏi bảng, một tờ giấy có thể vừa có bảng vừa chảy
    bằng điều khoản: bảng khi ấy là một khối bình thường giữa trang, in trọn,
    và `markup()` tra nó trong `_BUILDERS` như mọi khối khác. Không có hàm
    này thì nó tra trượt -- `KeyError: 'table'` trên 150/1500 tờ, và lỗi ấy
    nằm im cho đến khi phép đo chịu kể ra số tờ hỏng.

    Không có `foot`: khối tổng chỉ chui vào chân bảng khi bảng là khối chảy
    và nó là khối cuối (`markup()::foot_totals`). Ở đây `totals` đứng riêng
    trong `_BUILDERS`, và in nó hai lần là in một con số hai lần."""
    return _table(doc, d, 0, len(doc.rows), 0)


_BUILDERS = {
    # `_photo` trả rỗng khi tờ giấy không có ô ảnh, nên tên này nằm trong kế
    # hoạch trang của MỌI tài liệu mà chỉ in ra ở tài liệu thật sự có ảnh --
    # cùng lối mọi bộ dựng khác ở đây.
    "photo": _photo,
    "table": _table_whole,
    "letterhead": _letterhead,
    "doctitle": _doctitle,
    "meta": _meta,
    "fields": _fields,
    "checks": _checks,
    "questions": _questions,
    "legal_basis": _legal_basis,
    "clauses": _clauses,
    "sections": _sections,
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


# Bộ dựng của MỘT LÁT khối chảy: `(doc, design, low, high, part, foot=)`.
# `markup()` tra bảng này chứ không viết tên khối vào thân vòng lặp, nên thêm
# một khối chảy là thêm một dòng ở đây và một dòng ở `design.FLOW_BLOCKS`.
# Khối chảy nào CHIA CỘT được. Điều khoản và câu hỏi thì được -- chúng là
# danh sách mục, và `_chunks` cắt chúng thành mấy khối vừa một cột. Bảng thì
# không: bảy cột bảng nhét vào một cột rộng 8cm thì chữ vỡ ra từng ký tự, và
# cái hộp đo được của nó không còn tả một cái bảng nào.
# `sections` KHÔNG chia cột: một đoạn văn canh đều dài bốn năm dòng nhét
# vào cột rộng 8cm thì mỗi dòng còn ba bốn từ, và đó không phải dáng một
# văn bản nào in ra.
COLUMN_SAFE_FLOWS = frozenset({"clauses", "questions"})

FLOW_BUILDERS = {
    "sections": _sections_slice,
    "table": _table,
    "clauses": _clauses_slice,
    "questions": _questions_slice,
}


# Muối cho phép rải khối. Riêng, vì nó phải KHÔNG đi cùng bất cứ thứ gì khác
# bốc từ `seed` -- xem `draw.CONTENT_SALT`.
PAGE_PLAN_SALT = 0x9A6E12D


def _page_plan(seed: int, head_names: list[str], tail_names: list[str],
               pages: int) -> list[tuple[list[str], list[str]]]:
    """Khối nào in ra TỜ NÀO: `[(trước khối chảy, sau khối chảy)]`, một cặp
    mỗi tờ.

    Vì sao có hàm này. Bản trước dồn MỌI khối đầu vào tờ một và MỌI khối đuôi
    vào tờ cuối, nên một tài liệu sáu tờ ra:

        tờ 1: tiêu đề + điều khoản   tờ 2..5: điều khoản   tờ 6: điều khoản + chữ ký

    -- bốn tờ giữa chỉ có đúng một nhãn vùng chạy từ mép trên xuống mép dưới.
    Một mô hình học trên bộ ấy học rằng trang giữa của tài liệu dài thì không
    có gì ngoài `List-Group`, và giấy thật không thế: hợp đồng dài có phụ lục
    bảng ở giữa, có sơ đồ, có mục lục, có trang ký riêng.

    NEO thì không rải: tiêu đề đơn vị, quốc hiệu, tên văn bản ở tờ đầu và chữ
    ký, chân trang ở tờ cuối, vì đó là chỗ của chúng trên mọi tờ giấy thật.
    Phần còn lại rải đều rồi xê dịch một tờ -- chia đều không thôi thì mọi
    tài liệu cùng số tờ có cùng bố cục, còn rải ngẫu nhiên hết thì thứ tự đọc
    vỡ (dòng tổng trôi lên trước cái bảng nó cộng).

    Nhóm phải đi cùng nhau (`design.BOUND_GROUPS`) được gom lại thành MỘT mục
    trước khi rải, nên bảng và dòng tổng của nó không bao giờ rơi hai tờ.
    """
    plan: list[tuple[list[str], list[str]]] = [([], []) for _ in range(pages)]
    # Ô dán ảnh đi qua kế hoạch như mọi khối khác. Bản trước neo nó vào tờ một
    # trong chính thân vòng lặp, nên nó là khối DUY NHẤT không rải được, và
    # phép đo trên tờ giữa đọc ra 0% -- một con số không ai đặt mà cũng không
    # ai thấy. Hồ sơ dày ngoài đời dán ảnh ở trang lý lịch, không nhất thiết
    # trang bìa.
    head_names = ["photo"] + [n for n in head_names if n != "photo"]
    anchor_head = [n for n in head_names if n in D.ANCHOR_HEAD]
    anchor_tail = [n for n in tail_names if n in D.ANCHOR_TAIL]
    free_head = [n for n in head_names if n not in D.ANCHOR_HEAD]
    free_tail = [n for n in tail_names if n not in D.ANCHOR_TAIL]

    def finish(built):
        # Ô dán ảnh lên ĐẦU tờ nó rơi vào. `.photo{float:right}` -- nó nổi
        # sang phải của thứ đứng SAU nó trong DOM, nên đặt nó sau khối tiêu
        # đề là đẩy nó tụt xuống giữa trang. Bản trước nó luôn là con đầu
        # tiên của tờ giấy; rải nó đi thì phải mang theo tính chất ấy, không
        # thì một thay đổi về TRANG lặng lẽ thành một thay đổi về CHỖ ĐỨNG.
        #
        # Hàm chứ không phải một vòng lặp ở cuối: nhánh tài liệu MỘT TỜ trả
        # về sớm, nên một vòng lặp đặt sau nó bỏ sót đúng cái trường hợp
        # thường gặp nhất -- và bỏ sót im lặng.
        for before, _after in built:
            if "photo" in before:
                before.remove("photo")
                before.insert(0, "photo")
        return built

    plan[0][0].extend(anchor_head)
    plan[pages - 1][1].extend(anchor_tail)
    if pages <= 1:
        plan[0][0].extend(free_head)
        plan[0][1].extend(free_tail)
        return finish(plan)

    rng = random.Random(seed ^ PAGE_PLAN_SALT ^ (pages * 2654435761))

    def units(names: list[str]) -> list[list[str]]:
        """Gom khối phải đi cùng nhau thành một mục, giữ thứ tự đọc."""
        taken: set[str] = set()
        out: list[list[str]] = []
        for name in names:
            if name in taken:
                continue
            group = next((g for g in D.BOUND_GROUPS if name in g), (name,))
            together = [n for n in names if n in group]
            taken.update(together)
            out.append(together)
        return out

    def spread(groups: list[list[str]], side: int) -> None:
        """Rải theo TỜ, không theo khối.

        Bản trước chia đều số khối lên số tờ -- `(k * pages) // len(groups)`.
        Với ba khối và chín tờ chúng rơi vào tờ 0, 3, 6 và SÁU tờ còn lại
        trắng, dù ba khối ấy thừa sức xoá ba tờ trắng nếu đứng đúng chỗ. Phép
        chia ấy tối ưu cho khoảng cách ĐỀU giữa các khối, trong khi thứ phải
        tối ưu là số tờ KHÔNG trắng.

        Đảo lại: chọn chỗ ngồi ở các tờ GIỮA trước -- tờ đầu và tờ cuối đã có
        neo, nên một khối tự do rơi vào đó không xoá được tờ trắng nào. Chọn
        xong mới xếp theo thứ tự tăng dần rồi phát lần lượt, nên THỨ TỰ ĐỌC
        giữ nguyên: chỉ chỗ đứng đổi, không phải trình tự."""
        if not groups:
            return
        where = list(range(1, pages - 1))
        rng.shuffle(where)
        where = where[:len(groups)]
        # Nhiều khối hơn tờ giữa thì phần thừa bốc đều cả tờ đầu lẫn tờ cuối:
        # tới đây mọi tờ giữa đã có ít nhất một khối, nên chồng thêm là đúng.
        while len(where) < len(groups):
            where.append(rng.randrange(pages))
        for group, page in zip(groups, sorted(where)):
            plan[page][side].extend(group)

    spread(units(free_head), 0)
    spread(units(free_tail), 1)
    return finish(plan)


def markup(doc: Doc, slices: list[tuple[int, int]], faces: str = "") -> str:
    """HTML đầy đủ. `slices` dài bao nhiêu thì có bấy nhiêu tờ `.sheet`."""
    d = doc.design
    order = list(d.order)
    # Khối CHẢY của tài liệu này -- khối bị cắt ra giữa các tờ. `design.flow`
    # là chỗ duy nhất trả lời câu ấy; ở đây chỉ kiểm rằng nó thật sự có mặt
    # trong thứ tự khối, vì một khối `blocks` có mà `order` không có thì
    # không in ra gì để mà cắt.
    flow = d.flow if d.flow in FLOW_BUILDERS and d.flow in order else ""
    if flow:
        cut = order.index(flow)
        head_names, tail_names = order[:cut], order[cut + 1:]
    else:
        head_names, tail_names = order, []
        slices = [(0, 0)]

    # Khối tổng đi VÀO bảng khi có bảng -- xem `_tfoot`. Không có bảng thì nó
    # vẫn phải in ra, và khi ấy `_totals` là chỗ duy nhất in được nó.
    foot_totals = (flow == "table" and "totals" in tail_names
                   and bool(doc.rows))
    if foot_totals:
        tail_names = [name for name in tail_names if name != "totals"]

    # Quốc hiệu: chỉ tờ giấy của cơ quan nhà nước và bệnh viện in, và nó in
    # NGAY SAU thẩm quyền ban hành. Quyết định một lần, trước vòng lặp -- ở
    # trong vòng lặp nó sẽ phụ thuộc vào tờ nào đang vẽ, mà quốc hiệu thì
    # không.
    # QUỐC HIỆU KHÔNG PHẢI CHUYỆN CỦA RIÊNG CƠ QUAN NHÀ NƯỚC.
    #
    # Cổng cũ đòi `org_kind in ("state","hospital")`, nên mọi tờ do một công ty
    # phát hành -- biên bản họp, giấy uỷ quyền, thông báo tuyển dụng -- in ra
    # KHÔNG có quốc hiệu nào. Đo trên `data/review100`: 4/12 tờ nhóm hành chính
    # mất hẳn quốc hiệu. Trên giấy thật, doanh nghiệp Việt Nam vẫn in quốc hiệu
    # ở mọi văn bản có số hiệu và con dấu; thứ phân biệt không phải loại pháp
    # nhân mà là LOẠI GIẤY: hoá đơn, thực đơn, thẻ bảo hành thì không.
    #
    # `national` là cờ của chính phôi (`rulebase/synthgen/*.yaml`) -- chỗ biết
    # mình là loại giấy gì. Dùng nó, và chỉ lùi về `org_kind` khi phôi không
    # khai.
    # `d.national` do `design.draw()` bốc từ `archetype.national` -- xác suất
    # của chính phôi, thứ biết mình là loại giấy gì. Hoá đơn và thực đơn khai
    # 0.08-0.1, công văn và quyết định khai 0.9-0.95.
    wants_national = d.national and d.head_layout not in (
        "chia_doi", "chia_doi_co_logo", "hai_cot_cach")

    sheets: list[str] = []
    pages = max(len(slices), 1)
    plan = _page_plan(doc.seed, list(head_names), list(tail_names), pages)
    for index in range(pages):
        before, after = plan[index]
        # `(tên khối, html)` chứ không chỉ html: trang nhiều cột phải biết khối
        # nào chảy vào cột và khối nào chạy hết chiều ngang, và biết theo TÊN.
        # Cắt theo vị trí thì sai ngay: `_photo` và quốc hiệu chen vào làm lệch
        # chỉ số, nên tiêu đề bị hút vào cột và "BIÊN BẢN BÀN GIAO" vỡ làm ba
        # dòng hẹp -- thấy được trên ảnh vẽ hộp.
        parts: list[tuple[str, str]] = []
        for name in before:
            parts.append((name, _BUILDERS[name](doc, d)))
            if name == "letterhead" and wants_national:
                parts.append(("letterhead", _national(doc, d)))
        has_flow = bool(flow) and index < len(slices)
        # Tờ này in mấy cột. Khác `d.page_columns` ở chỗ nó xét TỜ: một tờ
        # mang cái bảng thì một cột dù cả tài liệu khai hai.
        sheet_columns = d.page_columns
        if has_flow and flow not in COLUMN_SAFE_FLOWS:
            sheet_columns = 1
        if has_flow:
            low, high = slices[index]
            parts.append((flow, FLOW_BUILDERS[flow](
                doc, d, low, high, index,
                foot=foot_totals and index == pages - 1,
                groups=sheet_columns)))
        for name in after:
            parts.append((name, _BUILDERS[name](doc, d)))
        # MỰC KHÔNG-PHẢI-CHỮ đứng theo `design.mark_place`, không phải luôn ở
        # cuối tờ cuối. Bốn chỗ, và chúng là bốn dáng giấy khác nhau -- xem
        # `design.MARK_PLACES`.
        place = getattr(d, "mark_place", "cuoi")
        if place == "goc_phai" and index == 0:
            parts.append(("ornament", _ornament(doc, d, corner=True)))
        elif place == "dau" and index == 0:
            # Ngay SAU khối tiêu đề, trước phần thân: chèn vào đầu `parts` thì
            # nó lên trên cả letterhead, mà hoá đơn bán lẻ in nó DƯỚI tên cửa
            # hàng. `head_names` đã nằm trong `before`, nên chèn sau chúng.
            cut = len(before) + (1 if wants_national and "letterhead" in before else 0)
            parts.insert(min(cut, len(parts)), ("ornament", _ornament(doc, d)))
        elif place == "moi_to":
            parts.append(("ornament", _ornament(doc, d)))
        elif index == pages - 1:
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
            # `data-region` trên `.wtext`, KHÔNG trên `.wmark`.
            #
            # Chú thích ở `stylesheet()` đã nói phải đo trên `.wtext`, nhưng
            # thuộc tính lại nằm trên thẻ ngoài -- nên phép đo lấy đúng cái
            # `.wmark` rộng 36% bề ngang tờ giấy, và hộp `Watermark` bao cả
            # một mảng giấy trắng hai bên chữ. Một luật đúng mà chỉ một trong
            # hai chỗ biết là hình dạng lỗi hay gặp nhất của kho này.
            #
            # `.wtext` là `inline-block` nên nó co sát chữ, và
            # `getBoundingClientRect` của phần tử nằm trong một thẻ đã xoay
            # trả về hộp THẲNG TRỤC của chữ đã xoay -- đúng thứ cần.
            water = (f'<div class="wmark">'
                     f'<span class="wtext"{D.region_attr("watermark")}>'
                     f'{_span("watermark", "BẢN SAO")}</span></div>')
        # Số trang, kiểu chứng từ thông dụng. Thay cho dòng "(Tiếp theo trang
        # N)" mà bản trước in ở ĐẦU bảng: nó là một ghi chú của riêng cái bảng,
        # trong khi thứ người đọc tìm là tờ này là tờ thứ mấy trong mấy tờ.
        # Chỉ in khi có từ hai tờ -- một tờ giấy một trang không đánh số.
        page_no = ""
        if pages > 1:
            page_no = (f'<div class="pgnum"{D.region_attr("pagenum")}>'
                       f'{_span("footer.page", f"Trang {index + 1}/{pages}")}</div>')
        body = "".join(html for _name, html in parts if html)
        # CHỮ CHẢY THÀNH CỘT. `FULL_WIDTH` ở NGOÀI khung cột -- trên giấy thật
        # tiêu đề, quốc hiệu và dải chữ ký chạy hết chiều ngang, và một cái
        # tiêu đề rơi vào cột trái là thứ không tờ báo nào in.
        # HAI CỘT, xét theo TỜ chứ theo tài liệu. Tờ nào mang lát khối chảy
        # thì một cột: khối chảy cao và `.cols .blk{break-inside:avoid}` giữ
        # nó không cắt ngang được, nên nó dồn hết vào một cột và bỏ trắng cột
        # kia -- đo được trên ảnh. Tờ chỉ có bảng phụ lục, sơ đồ, ghi chú thì
        # hai cột vẫn đúng, và đó chính là những tờ giữa mà bản trước để
        # trống.
        if sheet_columns > 1:
            # `column_flow`, KHÔNG `flow`: `flow` ở hàm này đã là tên của KHỐI
            # CHẢY của tài liệu. Đặt trùng thì tờ đầu gán đè nó thành một
            # danh sách html, và tờ thứ hai tra `FLOW_BUILDERS[flow]` với một
            # danh sách -- tài liệu một tờ chạy đúng, tài liệu nhiều tờ chết.
            column_flow = [html for name, html in parts
                           if html and name not in FULL_WIDTH]
            if len(column_flow) >= 2:
                head = "".join(html for name, html in parts
                               if html and name in FULL_WIDTH
                               and name not in _AFTER_FLOW)
                tail = "".join(html for name, html in parts
                               if html and name in _AFTER_FLOW)
                body = (f'{head}<div class="cols">'
                        f'{"".join(column_flow)}</div>{tail}')
        elif d.page_columns > 1:
            # Tài liệu khai nhiều cột mà TỜ này không dùng được (mang bảng).
            # Không làm gì -- `body` đã là một cột. Nhánh viết ra để câu
            # `sheet_columns` ở trên đọc được là có chủ đích, không phải sót.
            pass
        sheets.append(f'<div class="sheet">{_decor_layer(d)}{water}{body}{page_no}'
                      f'<div class="clr"></div></div>')


    style = stylesheet(d, faces)
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f"<style>{style}</style></head><body>{''.join(sheets)}</body></html>")
