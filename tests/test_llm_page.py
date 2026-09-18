"""Cổng cho trang HTML model viết: nhận trang engine viết, loại trang hỏng.

Không mở trình duyệt, không gọi model -- `markup.py` là chuỗi thuần và
`llm_page.problems` đọc chuỗi ấy. Nên file này chạy trong CI không phụ thuộc,
cùng chỗ `test_record.py` và `test_synthgen_kie.py`.

Cái khiến nó tồn tại: khi model viết HTML, lời hứa "run có nhãn chỉ chứa chữ"
thôi đúng theo cấu tạo và phải được KIỂM. Mà một cái cổng chỉ đáng tin khi nó
đúng ở CẢ HAI chiều -- lần đầu tôi viết từ vựng bằng tay và nó loại sạch 60/60
trang do chính engine sinh ra.
"""

from __future__ import annotations

import random

import pytest

from synthgen import content as C
from synthgen import design as D
from synthgen import markup as M
from synthgen.llm_page import kinds, path_coverage, problems

SHEET = ('<div class="sheet">'
         '<span data-kind="title">HOÁ ĐƠN</span>'
         '<span data-kind="invoice.field">0312345678</span>'
         '</div>')


def a_page(seed: int) -> str:
    design = D.draw(random.Random(seed), seed)
    doc = C.build(design, random.Random(seed ^ 0x5A), 6)
    return M.markup(doc, [(0, len(doc.rows))])


# ------------------------------------------------------- chiều nhận


@pytest.mark.parametrize("seed", range(12))
def test_a_page_the_engine_wrote_passes_the_gate(seed):
    """Cổng nào loại một trang engine viết là cổng sai, không phải trang sai.

    Cùng bất biến `agent/corpus_rules.py` đặt ra cho corpus, và nó bắt được lỗi
    thật: bản đầu liệt kê `data-kind` bằng tay, thiếu mọi biến thể `.label`
    (`store.address.label`), nên 60/60 trang bị loại."""
    assert problems(a_page(seed)) == []


def test_the_vocabulary_is_read_off_the_engine_not_written_by_hand():
    """Thêm một cột vào `design.py` thì từ vựng phải tự rộng theo."""
    every = kinds()
    assert len(every) > 60
    assert "store.address.label" in every        # biến thể `.label`
    assert any(k.startswith("menu.") for k in every)


# -------------------------------------------------------- chiều loại


def test_a_nested_tag_inside_a_labelled_run_is_refused():
    """Đây là luật chịu lực: phép đo lấy `span.firstElementChild || span`, nên
    một thẻ lồng THÀNH cái hộp được ghi. Trang vẫn vẽ ra, nhãn vẫn có, nhãn
    sai -- `agent/compose_layout.py` đo được 5,3 px thay vì 310,6."""
    bad = '<div class="sheet"><span data-kind="title">HOÁ <b>ĐƠN</b></span></div>'
    assert any("thẻ lồng" in line for line in problems(bad))


def test_a_self_closing_tag_inside_a_run_is_refused_too():
    bad = '<div class="sheet"><span data-kind="title">HOÁ<br/>ĐƠN</span></div>'
    assert any("thẻ lồng" in line for line in problems(bad))


@pytest.mark.parametrize("html,mark", [
    ('<div class="sheet"><span data-kind="hoa_don.so">1</span></div>', "từ vựng"),
    ('<div><span data-kind="title">X</span></div>', "sheet"),
    (SHEET + "<script>x()</script>", "script"),
    (SHEET + '<img src="https://a.com/x.png">', "tài nguyên ngoài"),
    (SHEET + '<div style="background:url(//a.com/b.png)"></div>', "tài nguyên ngoài"),
    (SHEET + '<div onclick="x()"></div>', "sự kiện"),
    ('<div class="sheet"><div data-region="Bang">'
     '<span data-kind="title">X</span></div></div>', "nhãn vùng"),
    ('<div class="sheet"><p>không nhãn nào</p></div>', "không có run"),
    ("", "rỗng"),
])
def test_each_way_a_page_breaks_has_its_own_reason(html, mark):
    found = problems(html)
    assert any(mark in line for line in found), (mark, found)


# ------------------------------------------- nội dung khai phải in ra


def test_a_declared_value_that_no_run_prints_is_refused():
    """Model viết JSON nội dung RỒI viết HTML; hai thứ lệch nhau là bộ dữ liệu
    dạy mô hình đọc ra thứ không có trên giấy."""
    found = problems(SHEET, {"mst": "0312345678", "ten": "CÔNG TY A"})
    assert any("không run nào in ra" in line for line in found)


def test_a_value_printed_twice_is_refused():
    """Mỗi giá trị một hộp. In hai lần thì hộp nào là hộp của trường ấy?"""
    twice = ('<div class="sheet"><span data-kind="title">A</span>'
             '<span data-kind="note">A</span></div>')
    found = problems(twice, {"x": "A"})
    assert any("2 lần" in line for line in found)


def test_a_value_wrapped_inside_a_longer_run_still_counts():
    """Nhãn và giá trị hay nằm chung một run ("Số: 0312"); đòi khớp nguyên vẹn
    sẽ loại một trang đúng."""
    page = '<div class="sheet"><span data-kind="note">Số: 0312345678</span></div>'
    assert problems(page, {"so": "0312345678"}) == []


def test_a_long_flow_is_cut_into_full_A4_sheets():
    """Giấy sang trang vì chữ chảy hết tờ, không vì người viết quyết định.

    Đo trên pilot8, khi model tự mở `.sheet` mới: sáu tờ ra
    [150, 43, 48, 13, 17, 23] từ, đầy 80% rồi 18% 16% 14% 17% 15%. Tờ thứ tư
    mười ba từ. Cắt theo chiều cao thì tờ nào cũng gần đầy."""
    from synthgen.draw_llm import cut_lines, gaps_between

    page_h = 1123.0
    # Ba khối, khoảng trống đúng chỗ sang trang.
    boxes = [(0.0, 1080.0), (1120.0, 2230.0), (2270.0, 3300.0)]
    cuts = cut_lines(3300.0, page_h, gaps_between(boxes))
    assert len(cuts) == 2, cuts
    edges = [0.0, *cuts, 3300.0]
    heights = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    # Không tờ nào vượt khổ, và không tờ nào là một mẩu vụn.
    assert all(h <= page_h * 1.05 for h in heights), heights
    assert all(h >= page_h * 0.5 for h in heights), heights


def test_a_flow_that_fits_one_sheet_is_not_cut():
    """Một tờ vừa khổ thì không có nhát cắt nào -- kể cả khi nó hơi tràn."""
    from synthgen.draw_llm import cut_lines

    assert cut_lines(1100.0, 1123.0, []) == []
    assert cut_lines(1200.0, 1123.0, []) == []      # trong khoảng dung sai


def test_a_cut_never_runs_backwards():
    """Nhát cắt trượt về khoảng trống gần nhất, nhưng không được lùi lên trên
    nhát trước -- một tờ có chiều cao âm là một tấm ảnh rỗng."""
    from synthgen.draw_llm import cut_lines

    # Khoảng trống dồn cả về đầu trang: chỗ hấp dẫn nhất nằm phía sau.
    gaps = [(80.0, 120.0), (150.0, 190.0)]
    cuts = cut_lines(4000.0, 1000.0, gaps)
    assert cuts == sorted(cuts), cuts
    assert all(b - a > 0 for a, b in zip(cuts, cuts[1:])), cuts


def test_a_run_outside_every_sheet_is_caught():
    """Ta chỉ chụp ảnh phần tử `.sheet`. Chữ ngoài nó vẫn vẽ ra trên trình
    duyệt nhưng không vào ảnh và không có hộp -- mất lặng lẽ.

    Đo trên pilot13: một tờ có 221 run mà 215 nằm ngoài, vì model đóng một
    `</div>` sớm hơn một nhịp. Tờ ấy xin bốn trang, cắt ra một, và trang ấy cao
    181 điểm ảnh. Cổng cũ chỉ hỏi "có `.sheet` không" nên nó qua sạch."""
    from synthgen.llm_page import outside_sheet, problems

    good = ('<div class="sheet"><span data-kind="title">A</span>'
            '<div><span data-kind="note">B</span></div></div>')
    early = ('<div class="sheet"><span data-kind="title">A</span></div>'
             '<span data-kind="note">B</span>')
    two = ('<div class="sheet"><span data-kind="title">A</span></div>'
           '<div class="sheet"><span data-kind="note">B</span></div>')
    assert outside_sheet(good) == 0
    assert outside_sheet(two) == 0, "nhiều .sheet vẫn phải đếm đủ"
    assert outside_sheet(early) == 1
    assert any("NGOÀI" in why for why in problems(early))
    assert not any("NGOÀI" in why for why in problems(good))


# ----------------------------------------------------------------- data-path


def test_a_malformed_data_path_is_refused():
    bad = ('<div class="sheet"><span data-kind="invoice.field" '
          'data-path="Issuer TaxCode!">0312345678</span></div>')
    assert any("không đúng dạng" in line for line in problems(bad))


@pytest.mark.parametrize("path", [
    "issuer.tax_code", "line_items[0].name", "items[].print_qty",
    "recipient.address", "invoice.total",
    "clause.1.body", "section.4", "conclusion.1.head",
])
def test_well_formed_data_paths_pass(path):
    good = (f'<div class="sheet"><span data-kind="invoice.field" '
           f'data-path="{path}">x</span></div>')
    assert not any("data-path" in line for line in problems(good))


def test_bare_digit_segments_are_accepted_not_just_bracket_indices():
    """Phase 8: đo trên pilot16, một tờ khai 16 đường dạng `clause.1.body`/
    `section.4` bị cổng cũ loại nguyên trang -- đúng cấu trúc, đúng nội
    dung, chỉ khác hình thức chỉ số. `resolve_path()` (`agent/
    compose_page.py`) đọc được cả `[N]` lẫn `.N.`, nên cổng không cần đòi
    một hình duy nhất."""
    bad_before = ('<div class="sheet"><span data-kind="invoice.field" '
                 'data-path="clause.1.body">Điều khoản một</span></div>')
    assert problems(bad_before) == []


def test_the_same_path_printing_two_different_values_is_refused():
    """Cùng một danh tính mà in ra hai giá trị khác nhau là mâu thuẫn nội tại
    của chính trang đó -- không phải một tỉ lệ cần đo trước rồi mới gác."""
    conflict = (
        '<div class="sheet">'
        '<span data-kind="invoice.field" data-path="issuer.tax_code">0312345678</span>'
        '<span data-kind="invoice.field" data-path="issuer.tax_code">0312345679</span>'
        '</div>')
    found = problems(conflict)
    assert any("giá trị khác nhau" in line for line in found)


def test_the_same_path_printing_the_same_value_twice_is_fine():
    """Một trường được in nhiều lần (mục 48 `page.md`) không phải lỗi, miễn
    cùng đường dẫn thì cùng chữ."""
    repeated = (
        '<div class="sheet">'
        '<span data-kind="invoice.field" data-path="issuer.name">CÔNG TY ABC</span>'
        '<span data-kind="invoice.field" data-path="issuer.name">CÔNG TY ABC</span>'
        '</div>')
    assert not any("data-path" in line for line in problems(repeated))


def test_a_span_without_data_path_is_not_refused_for_that_alone():
    """Đo trên `data/pilot10`+`data/pilot12` thật: chỉ 28% run mang
    `data-path` dưới `page.md` cũ. Ép cổng theo một con số chưa đo lại cho
    prompt mới là việc của Phase 2 (`docs/ke-hoach-refactor-engine.md`), sau
    khi có số đo -- không phải ở đây."""
    no_path = SHEET  # spans trong SHEET không có data-path
    assert not any("data-path" in line for line in problems(no_path))


def test_path_coverage_counts_without_gating():
    mixed = (
        '<div class="sheet">'
        '<span data-kind="title" data-path="doc.title">A</span>'
        '<span data-kind="note">B</span>'
        '</div>')
    cov = path_coverage(mixed)
    assert cov == {"spans": 2, "with_path": 1, "coverage": 0.5}
    assert problems(mixed) == []          # thiếu path một mình không loại trang
