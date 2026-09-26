"""Hộp đo trên TRANG ĐÃ ĐIỀN, không bao giờ trên phôi.

Đây là luật 1 và luật 2 của `AGENTS.md` áp cho đường sinh phôi: hộp do engine
dàn chữ sinh ra, một lần, và không ai đo lại. Cái bẫy riêng của đường này là
phôi trông như một trang hoàn chỉnh -- nó dàn ra được, đo được, và hộp nó cho
ra SAI cho mọi tờ điền từ nó.

Đo trên chính phôi trong tệp này (`Drawer.measure`, lưới phần nghìn):

    `store.name`      phôi [62, 50, 179, 63]   điền [62, 50, 449, 63]
    bề rộng            117 phần nghìn           387 phần nghìn  -- gấp 3,3 lần

`{{issuer.name}}` là 17 ký tự; "CÔNG TY TNHH KỸ THUẬT VÀ TỰ ĐỘNG HOÁ TÂN PHÁT"
là 45. Dùng lại hộp của phôi là gắn nhãn cho 30% vệt mực.

Cần Chromium thật, nên tệp này bỏ qua khi thiếu `playwright`.
"""

from __future__ import annotations

import random

import pytest

pytest.importorskip("playwright")
pytest.importorskip("cv2")

from agent.fingerprint import geometry_fingerprint  # noqa: E402
from synthgen import fill as FILL  # noqa: E402
from synthgen import template as T  # noqa: E402

BODY = (
    "<style>.sheet{width:794px;min-height:1123px;padding:40px;"
    "font:12pt 'Times New Roman',serif;background:#fff}"
    "table{width:100%;border-collapse:collapse}td,th{border:1px solid #000;"
    "padding:3px}</style>"
    '<div class="sheet">'
    '<p>Đơn vị: <span data-kind="store.name" data-path="issuer.name">'
    "{{issuer.name}}</span></p>"
    '<p>Địa chỉ: <span data-kind="store.address" data-path="issuer.address">'
    "{{issuer.address}}</span></p>"
    "<table><tbody>"
    f'<tr {T.REPEAT_ATTR}="line_items">'
    '<td data-cell><span data-kind="menu.name" data-path="line_items[].name">'
    "{{line_items[].name}}</span></td>"
    '<td data-cell><span data-kind="menu.amount" '
    'data-path="line_items[].amount">{{line_items[].amount}}</span></td>'
    "</tr></tbody></table></div>")


def _template() -> T.Template:
    return T.Template(template_id="m1", family="invoice_detailed", html=BODY)


def _box(record: dict, kind: str):
    for entity in record.get("entity_annotations") or ():
        if entity.get("kind") == kind:
            return entity.get("bbox")
    return None


@pytest.fixture(scope="module")
def drawer(tmp_path_factory):
    from synthgen.draw_llm import Drawer

    with Drawer(tmp_path_factory.mktemp("measure")) as one:
        yield one


def test_the_template_carries_no_geometry_of_its_own(drawer):
    """Cách chắc chắn nhất để không ai lỡ dùng lại hộp của phôi là phôi không
    bao giờ mang hộp nào. `Template` không có trường toạ độ."""
    fields = set(vars(_template()))
    assert not {f for f in fields if "bbox" in f or "box" in f or "geom" in f}


def test_a_real_value_moves_the_box_the_template_would_have_reported(drawer):
    template = _template()
    got = FILL.Filler(template).draw(random.Random(21))
    filled, _m, _s, _g = FILL.prepare(got.html, 21)
    on_template = drawer.measure(BODY, "tpl", "invoice_detailed")
    on_page = drawer.measure(filled, "filled", "invoice_detailed")
    assert on_template and on_page
    a, b = _box(on_template, "store.name"), _box(on_page, "store.name")
    assert a and b
    # Cùng góc trái (khối không dời chỗ), bề rộng khác hẳn (chữ dài ra).
    assert a[0] == b[0]
    assert b[2] - b[0] > 1.5 * (a[2] - a[0]), (a, b)


def test_two_fillings_of_one_template_get_their_own_boxes(drawer):
    """Không có bộ nhớ đệm nào giữa hai lần điền: mỗi tờ đi qua đúng
    `draw_one()` và Chromium đo lại từ đầu."""
    filler = FILL.Filler(_template())
    boxes = []
    for i in range(2):
        got = filler.draw(random.Random(40 + i))
        filled, _m, _s, _g = FILL.prepare(got.html, 40 + i)
        record = drawer.measure(filled, f"two_{i}", "invoice_detailed")
        assert record
        boxes.append(_box(record, "store.name"))
    assert boxes[0] != boxes[1]


def test_more_rows_means_more_measured_regions(drawer):
    """Phép kiểm rằng số dòng THẬT SỰ tới được pixel, không chỉ tới HTML."""
    template = _template()
    counted = {}
    for rows in (3, 26):
        values = {"issuer.name": "CÔNG TY TNHH A", "issuer.address": "Số 1 Lê Lợi"}
        values.update({f"line_items[{i}].name": f"Mặt hàng số {i}"
                       for i in range(rows)})
        values.update({f"line_items[{i}].amount": f"{i + 1}.000.000"
                       for i in range(rows)})
        html, missing = T.fill_html(template.html, values, {"line_items": rows})
        assert missing == []
        record = drawer.measure(html, f"rows_{rows}", "invoice_detailed")
        assert record
        counted[rows] = len(record.get("word_annotations") or ())
    assert counted[26] > counted[3]


def test_geometry_fingerprint_reads_the_filled_page_not_the_template(drawer):
    template = _template()
    got = FILL.Filler(template).draw(random.Random(77))
    filled, _m, _s, _g = FILL.prepare(got.html, 77)
    on_template = geometry_fingerprint(
        (drawer.measure(BODY, "g_tpl", "f") or {}).get("layout_annotations") or [])
    on_page = geometry_fingerprint(
        (drawer.measure(filled, "g_fill", "f") or {}).get("layout_annotations") or [])
    assert on_page.cells != on_template.cells
    assert on_page.regions >= on_template.regions
