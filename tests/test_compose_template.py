"""`agent/compose_template.py` -- pha 1 xin model soạn phôi.

Không gọi model ở đây: mọi phép kiểm nhìn SCHEMA (thứ đi vào
`response_format`) và CỔNG (thứ chấm câu trả lời). Lượt gọi thật là việc của
người dùng, trên server ngoài sandbox -- xem `AGENTS.md` mục 5.
"""

from __future__ import annotations

import pytest

pytest.importorskip("cv2")

from synthgen import field_tier as FT  # noqa: E402
from synthgen import template as T  # noqa: E402

CT = pytest.importorskip("agent.compose_template")


def test_the_path_enum_comes_from_the_registry_not_from_a_hand_list():
    """Một danh sách chép tay ở đây là người thứ hai dựng cùng một luật, và
    kho này đã đo được ba lần hỏng vì đúng chuyện ấy (`docs/
    bon-muc-kiem-soat-nhan-llm.md` §7b)."""
    path = CT.schema()["properties"]["slots"]["items"]["properties"]["path"]
    assert path["enum"] == list(FT.closed_enum(FT.PATH))
    assert len(path["enum"]) >= 40


def test_the_path_field_has_no_escape_hatch_unlike_kind():
    """`kind` là nhãn LỚP của chữ và từ vựng của nó nhặt từ HTML engine, nên
    một loại giấy mới mang khối engine chưa vẽ bao giờ cần cửa thoát. `path`
    là DANH TÍNH trường, và một tên mới trong phôi là cùng một tên lạ in trên
    nghìn tờ giấy -- không có cửa thoát nào."""
    props = CT.schema()["properties"]["slots"]["items"]["properties"]
    assert "anyOf" not in props["path"] and "pattern" not in props["path"]
    assert "anyOf" in props["kind"]


def test_the_model_is_not_asked_for_any_value():
    """Khác biệt kiến trúc với `agent/compose_page.py::schema()`: cây `data`
    và mảng `rows` biến mất, vì giá trị là việc của `synthgen/values.py`."""
    props = CT.schema()["properties"]
    assert "data" not in props
    assert "rows" not in props
    assert set(props) == {"plan", "slots", "html"}


def test_a_placeholder_in_the_html_that_is_not_declared_fails_the_template():
    """Bảng nhãn của phôi (`kinds`) dựng từ `slots`, nên một chỗ trống không
    khai là một chỗ trống không có nhãn ở mọi tờ điền từ phôi ấy."""
    html = ('<div class="sheet"><span data-kind="store.name" '
            'data-path="issuer.name">{{issuer.name}}</span></div>')
    assert CT.slot_problems([], html)
    assert CT.slot_problems([{"path": "issuer.name", "kind": "store.name"}],
                            html) == []


def test_the_smoke_fill_gate_runs_the_page_gate_on_a_FILLED_page():
    """Cổng chữ đếm chữ IN RA, nên nó không chạy được trên phôi chưa điền --
    một phôi chưa điền chưa in gì cả. Đây là lớp gác thứ ba, và là lớp bắt
    được nhiều nhất."""
    body = (
        '<div class="sheet">'
        '<p><span data-kind="store.name" data-path="issuer.name">'
        "{{issuer.name}}</span></p>"
        "<table><tbody>"
        f'<tr {T.REPEAT_ATTR}="line_items">'
        '<td data-cell><span data-kind="menu.name" '
        'data-path="line_items[].name">{{line_items[].name}}</span></td>'
        "</tr></tbody></table></div>")
    template = T.Template(template_id="s1", family="f", html=body)
    pages, why, measure = CT.smoke(template, seed=3, fills=2)
    assert why == [], why
    assert len(pages) == 2
    assert all("{{" not in page for page in pages)
    # Hai lần điền, hai số dòng: một phôi qua cổng ở 8 dòng rồi vỡ ở 24 dòng
    # là một phôi hỏng mà một lần thử không thấy.
    assert len(measure["smoke_rows"]) == 2


def test_the_smoke_gate_catches_what_the_template_gate_never_looks_at():
    """`synthgen/template.py::problems` kiểm CHỖ TRỐNG; `synthgen/llm_page.py::
    problems` kiểm TRANG. Hai cổng, hai phạm vi, và lớp thứ hai chỉ chạy được
    trên một bản đã điền.

    Phôi dưới đây có `</div>` đóng sớm nên run có nhãn rơi ra ngoài `.sheet`.
    Chữ vẫn vẽ ra trên trình duyệt, KHÔNG vào ảnh, và không có hộp nào -- mất
    lặng lẽ. Cổng chỗ trống không nhìn `.sheet` bao giờ, và `synthgen/
    repair.py` không chữa được (nó không biết `</div>` nào là cái thừa)."""
    body = ('<div class="sheet"><p>PHIẾU THU</p></div>'
            '<span data-kind="store.name" data-path="issuer.name">'
            "{{issuer.name}}</span>")
    assert T.problems(body) == []
    _pages, why, _m = CT.smoke(T.Template(template_id="s2", family="f",
                                          html=body), seed=5, fills=1)
    assert any(".sheet" in w for w in why), why


def test_broken_has_the_same_keys_as_a_real_record():
    """`run()` đọc `archetype`/`seconds`/`why[0]` ngay sau `future.result()`;
    thiếu một khoá thì ta đổi một ngoại lệ lấy một `KeyError`."""
    real = {"index", "family", "ok", "seconds", "why", "html", "slots", "plan",
            "chars", "tokens_in", "tokens_out", "tokens_per_second", "brief",
            "attempt", "paths", "repeats"}
    assert real <= set(CT.broken(0, RuntimeError("thử")))
