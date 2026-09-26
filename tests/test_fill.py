"""`synthgen/fill.py` -- hai tầng chống trùng của pha 2.

Tầng TRONG MỘT PHÔI ở đây (không cần trình duyệt). Tầng CẢ LÔ -- hình học sau
khi vẽ -- ở `tests/test_fill_measure.py`, vì nó phải mở Chromium thật.
"""

from __future__ import annotations

import random

import pytest

from agent.fingerprint import Fingerprint
from synthgen import template as T

pytest.importorskip("cv2")
FILL = pytest.importorskip("synthgen.fill")


def _template() -> T.Template:
    body = (
        '<div class="sheet">'
        '<p>Đơn vị: <span data-kind="store.name" data-path="issuer.name">'
        "{{issuer.name}}</span></p>"
        '<p>MST: <span data-kind="store.tax_code" data-path="issuer.tax_code">'
        "{{issuer.tax_code}}</span></p>"
        "<table><tbody>"
        f'<tr {T.REPEAT_ATTR}="line_items">'
        '<td data-cell><span data-kind="menu.name" '
        'data-path="line_items[].name">{{line_items[].name}}</span></td>'
        '<td data-cell><span data-kind="menu.qty" '
        'data-path="line_items[].qty">{{line_items[].qty}}</span></td>'
        "</tr></tbody></table></div>")
    return T.Template(template_id="t1", family="invoice_detailed", html=body,
                      doc_title="HOÁ ĐƠN")


def test_a_filling_leaves_no_placeholder_on_the_page():
    got = FILL.Filler(_template()).draw(random.Random(1))
    assert got.missing == []
    assert "{{" not in got.html


def test_the_row_count_changes_between_fillings():
    """Cả lý do một phôi không sinh ra N bản sao: số dòng đổi thì chiều cao
    đổi, chiều cao đổi thì khối rơi vào ô lưới khác."""
    filler = FILL.Filler(_template())
    counts = {filler.draw(random.Random(i)).counts["line_items"]
              for i in range(12)}
    assert len(counts) > 1


def test_the_same_combination_is_never_filled_twice_into_one_template():
    """Câu CẤM, không phải câu nghiêng -- `CoverageMemory` hạ ưu tiên, tập
    `_used` thì chặn hẳn."""
    filler = FILL.Filler(_template())
    fines = [filler.draw(random.Random(i)).fingerprint.fine for i in range(40)]
    assert len(fines) == len(set(fines))


def test_a_filler_that_has_run_out_of_combinations_says_so_instead_of_hanging():
    """Phôi một chỗ trống trên một từ vựng hữu hạn thì tổ hợp cạn thật. Lúc
    ấy vẫn TRẢ một tờ và cộng `exact_collisions`: bỏ hẳn một tờ vì phôi nghèo
    là để cái phôi nghèo nhất quyết số trang của cả lô."""
    body = ('<div class="sheet"><p><span data-kind="meta.value" '
            'data-path="document.currency">{{document.currency}}</span></p></div>')
    filler = FILL.Filler(T.Template(template_id="t2", family="f", html=body),
                         candidates=2, exact_retries=2)
    for i in range(30):
        filler.draw(random.Random(i))
    assert filler.metrics()["exact_collisions"] > 0


def test_the_value_fingerprint_is_the_three_tier_class_not_a_flat_tuple():
    """Dùng lại `agent/fingerprint.py::Fingerprint` nguyên văn, nên
    `agent/coverage.py::CoverageMemory` và `agent/document_distance.py` chạy
    trên nó không sửa một dòng."""
    got = FILL.Filler(_template()).draw(random.Random(1))
    assert isinstance(got.fingerprint, Fingerprint)


def test_mid_does_not_carry_the_template_id_so_it_compares_across_templates():
    """Cùng bất đối xứng cố ý của `agent/fingerprint.py`: `mid` không mang
    `family` để trả lời được 'bao nhiêu tờ TRONG CẢ LÔ ra đúng dáng này'."""
    printed = {"issuer.name": "A"}
    counts = {"line_items": 5, "signers": 2}
    a = FILL.value_fingerprint("t1", printed, counts)
    b = FILL.value_fingerprint("t2", printed, counts)
    assert a.mid == b.mid
    assert a.coarse != b.coarse
    assert a.fine != b.fine


def test_two_row_counts_in_the_same_band_share_coarse():
    """`coarse` đọc NHÓM số dòng: bảy dòng và tám dòng là cùng một dáng tờ
    giấy, bảy dòng và bốn mươi thì không."""
    printed = {"issuer.name": "A"}
    same = FILL.value_fingerprint("t", printed, {"line_items": 5})
    near = FILL.value_fingerprint("t", printed, {"line_items": 7})
    far = FILL.value_fingerprint("t", printed, {"line_items": 40})
    assert same.coarse == near.coarse
    assert same.coarse != far.coarse


def test_the_fingerprint_reads_only_what_the_template_prints():
    """`facts()` sinh đủ 60 khoá cho mọi lần điền, nên một dấu vân đọc cả tờ
    khai sẽ coi hai tờ khác nhau ở đúng cái trường KHÔNG in là hai tờ khác
    nhau. Trên giấy chúng giống hệt."""
    filler = FILL.Filler(_template())
    got = filler.draw(random.Random(1))
    assert set(got.printed) <= set(got.values)
    assert len(got.printed) < len(got.values)
    assert all(p.split(".")[0].split("[")[0] in {"issuer", "line_items"}
               for p in got.printed)


def test_prepare_numbers_the_table_grid_after_the_rows_were_cloned():
    """`repair.grid()` phải chạy SAU khi bung, không trên phôi: đánh trên
    phôi thì mọi dòng nhân bản mang cùng một số hàng, và `synthgen/
    kie_full.py` đọc chỗ ngồi từ hai thuộc tính ấy nên cả bảng thành một
    dòng lặp lại N lần."""
    got = FILL.Filler(_template()).draw(random.Random(3))
    html, _mended, _stamped, _signed = FILL.prepare(got.html, 3)
    rows = {m for m in __import__("re").findall(r'data-row="(\d+)"', html)}
    assert len(rows) == got.counts["line_items"], (rows, got.counts)


# ------------------------------------------- hạn mức và thứ tự của cả lô

RF = pytest.importorskip("synthgen.run_fill")


def _plain(tid: str) -> T.Template:
    """Phôi KHÔNG có khối lặp -- chỉ đổi được độ dài chữ giữa hai lần điền."""
    body = ('<div class="sheet"><p><span data-kind="store.name" '
            'data-path="issuer.name">{{issuer.name}}</span></p></div>')
    return T.Template(template_id=tid, family="f", html=body)


def test_a_template_with_no_repeat_block_gets_a_smaller_budget():
    """Đo trên 18 phôi (`tools/llm/template_yield.py`): phôi không khối lặp
    ra trung vị 3 bố cục khác nhau trên 16 lần điền, và 100% số cặp vượt
    ngưỡng trùng 0,60. Điền nó 24 lần là ghi 21 bản sao -- và chúng QUA CỔNG,
    nên không gì kêu."""
    assert RF.budget(_plain("a"), 24) == RF.NO_REPEAT_FILLS
    assert RF.budget(_template(), 24) == 24


def test_the_budget_never_exceeds_what_was_asked_for():
    assert RF.budget(_plain("a"), 2) == 2


def test_the_schedule_interleaves_templates_instead_of_draining_one_at_a_time():
    """Cửa sổ so trùng hình học chỉ nhìn 24 tờ gần nhất. Chạy hết một phôi
    rồi mới sang phôi kia thì cửa sổ lúc nào cũng toàn tờ cùng một phôi, và
    nó báo trùng liên tục cho những tờ mà cả lô coi là bình thường."""
    templates = [_template(), _template(), _template()]
    order = RF.schedule(templates, per_template=3)
    assert order[:3] == [0, 1, 2]
    assert len(order) == 9


def test_the_schedule_skips_a_template_that_has_used_up_its_budget():
    """Chia đều là quay lại đúng chuyện điền một phôi không khối lặp 24 lần."""
    templates = [_template(), _plain("thin")]
    order = RF.schedule(templates, per_template=10)
    assert order.count(0) == 10
    assert order.count(1) == RF.NO_REPEAT_FILLS
