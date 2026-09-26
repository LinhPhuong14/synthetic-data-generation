"""`synthgen/template.py` -- cú pháp chỗ trống và cổng gác phôi.

Không mở trình duyệt, không gọi model, không đọc `data/`: chạy được ở job CI
không cài thư viện nào. Sổ đường dẫn truyền vào tay ở mỗi phép kiểm, vì
`field_tier.closed_enum()` dựng sổ thật và việc đó cần `cv2`.
"""

from __future__ import annotations

from synthgen import template as T

KNOWN = {"issuer.name", "issuer.tax_code", "customer.name", "document.title",
         "document.number", "line_items[].name", "line_items[].qty",
         "line_items[].amount", "signers[].name", "signers[].title"}


def wrap(body: str) -> str:
    return f'<div class="sheet">{body}</div>'


def run(path: str, text: str = "", kind: str = "store.name") -> str:
    return (f'<span data-kind="{kind}" data-path="{path}">'
            f'{text or "{{" + path + "}}"}</span>')


GOOD = wrap(
    "<p>Đơn vị: " + run("issuer.name") + "</p>"
    "<p>MST: " + run("issuer.tax_code", kind="store.tax_code") + "</p>"
    "<table><tbody>"
    f'<tr {T.REPEAT_ATTR}="line_items">'
    "<td data-cell>" + run("line_items[].name", kind="menu.name") + "</td>"
    "<td data-cell>" + run("line_items[].qty", kind="menu.qty") + "</td>"
    "</tr></tbody></table>")


def test_a_well_formed_template_passes():
    assert T.problems(GOOD, KNOWN) == []


def test_paths_and_repeats_are_read_back():
    assert T.paths(GOOD) == ["issuer.name", "issuer.tax_code",
                             "line_items[].name", "line_items[].qty"]
    assert [name for name, _s, _e in T.repeat_blocks(GOOD)] == ["line_items"]


def test_a_path_outside_the_closed_registry_fails_the_template():
    """Cổng CỨNG ở đây, khác `agent/compose_page.py` cố ý để mở: một phôi được
    điền hàng trăm lần, nên một tên lạ trong phôi là cùng một lỗi nhân lên
    chừng ấy lần."""
    bad = wrap("<p>" + run("patient.bed_no") + "</p>")
    why = T.problems(bad, KNOWN)
    assert any("sổ đường dẫn đóng" in w for w in why), why


def test_a_misspelt_placeholder_is_caught_not_ignored():
    """`{{ issuer.name }}` in nguyên ngoặc nhọn lên mặt giấy và qua mọi cổng
    khác -- nó là chữ hợp lệ. Chỉ chỗ này bắt được."""
    bad = wrap('<span data-kind="store.name" data-path="issuer.name">'
               "{{ issuer.name }}</span>")
    assert any("không đúng dạng" in w for w in T.problems(bad, KNOWN))


def test_a_placeholder_outside_a_labelled_run_fails():
    bad = wrap("<p>Đơn vị: {{issuer.name}}</p>")
    assert any("không nằm trong" in w for w in T.problems(bad, KNOWN))


def test_a_placeholder_disagreeing_with_its_own_data_path_fails():
    """Lời khai danh tính nói về một trường, chữ in ra là trường khác."""
    bad = wrap('<span data-kind="store.name" data-path="customer.name">'
               "{{issuer.name}}</span>")
    assert any("ngồi trong run khai" in w for w in T.problems(bad, KNOWN))


def test_a_row_placeholder_outside_any_repeat_block_fails():
    """Không ai bung nó, nên `[]` đi thẳng ra giấy."""
    bad = wrap("<p>" + run("line_items[].name", kind="menu.name") + "</p>")
    assert any("không nằm trong khối" in w for w in T.problems(bad, KNOWN))


def test_a_foreign_placeholder_inside_a_repeat_block_fails():
    """Nó in ra N lần, và cổng chữ loại tờ vì 'mỗi giá trị phải có đúng một
    hộp' -- bắt ở phôi rẻ hơn bắt ở tờ thứ một nghìn."""
    bad = wrap("<table><tbody>"
               f'<tr {T.REPEAT_ATTR}="line_items">'
               "<td data-cell>" + run("line_items[].name", kind="menu.name") + "</td>"
               "<td data-cell>" + run("issuer.name") + "</td>"
               "</tr></tbody></table>")
    assert any("không thuộc nhóm ấy" in w for w in T.problems(bad, KNOWN))


def test_a_repeat_block_with_no_placeholder_of_its_own_fails():
    bad = wrap("<table><tbody>"
               f'<tr {T.REPEAT_ATTR}="line_items">'
               "<td data-cell>" + run("issuer.name") + "</td>"
               "</tr></tbody></table>")
    assert any("không có chỗ trống" in w for w in T.problems(bad, KNOWN))


def test_a_template_with_no_placeholder_at_all_fails():
    assert any("không có chỗ trống" in w
               for w in T.problems(wrap("<p>chỉ chữ in</p>"), KNOWN))


# ------------------------------------------------------------------ bung ra

def test_fill_expands_a_repeat_block_and_indexes_both_attribute_and_text():
    values = {"issuer.name": "CÔNG TY A", "issuer.tax_code": "0101",
              "line_items[0].name": "Bút bi", "line_items[0].qty": "3",
              "line_items[1].name": "Sổ tay", "line_items[1].qty": "5"}
    html, missing = T.fill_html(GOOD, values, {"line_items": 2})
    assert missing == []
    assert "{{" not in html
    assert html.count("<tr") == 2
    assert 'data-path="line_items[0].name"' in html
    assert 'data-path="line_items[1].name"' in html
    assert "Bút bi" in html and "Sổ tay" in html
    # `data-repeat` biến mất khỏi bản đã bung: giữ lại thì một lần điền thứ
    # hai nhân bản tiếp, và số dòng lên theo luỹ thừa mà không ai kêu.
    assert T.REPEAT_ATTR not in html


def test_fill_reports_a_missing_value_instead_of_printing_an_empty_run():
    html, missing = T.fill_html(GOOD, {"issuer.name": "A"}, {"line_items": 0})
    assert "issuer.tax_code" in missing
    # Chỗ trống CÒN NGUYÊN trên trang -- cổng của bước sau nhìn thấy ngay,
    # còn một chuỗi rỗng lặng lẽ thay vào thì không ai thấy.
    assert "{{issuer.tax_code}}" in html


def test_fill_escapes_html_in_a_real_value():
    html, _missing = T.fill_html(wrap(run("issuer.name")),
                                 {"issuer.name": "A & B <Co>"}, {})
    assert "A &amp; B &lt;Co&gt;" in html


def test_row_count_comes_from_the_highest_index_not_the_key_count():
    """Một tờ khai thiếu dòng giữa mà đếm khoá thì dòng cuối không bao giờ in."""
    values = {"line_items[0].name": "a", "line_items[0].qty": "1",
              "line_items[2].name": "c", "line_items[2].qty": "3"}
    html, _missing = T.fill_html(GOOD, values)
    assert html.count("<tr") == 3


# --------------------------------------------- bọc chỗ trống trần trước khi gác

KINDS = {"issuer.name": "store.name", "document.title": "title",
         "issuer.code": "meta.value"}


def test_a_bare_placeholder_is_wrapped_using_the_models_own_declaration():
    """Phép ĐỌC, không phải phép đoán: `slots` là bảng `path -> kind` model tự
    khai, và cổng đã đối chiếu nó với HTML."""
    bad = wrap('<div class="org-name">{{issuer.name}}</div>')
    assert T.problems(bad, KNOWN)                      # trần thì trượt
    fixed, n = T.enclose(bad, KINDS)
    assert n == 1
    assert '<span data-kind="store.name" data-path="issuer.name">' in fixed
    assert T.problems(fixed, KNOWN) == []


def test_a_placeholder_glued_after_a_run_gets_its_own_run():
    """Model dựng chuỗi ghép `Số: X/TB-Y` từ hai đường dẫn, và chỗ trống thứ
    hai rơi ra ngoài span của chỗ thứ nhất. Hai đường dẫn là hai trường, nên
    hai hộp -- một hộp chung cho cả `X/TB-Y` là hộp không nhãn nào tả đúng."""
    bad = wrap("<p>Số: " + run("document.title", kind="title")
               + "/TB-{{issuer.code}}</p>")
    fixed, n = T.enclose(bad, KINDS)
    assert n == 1
    assert fixed.count("data-path=") == 2


def test_a_placeholder_the_model_never_declared_is_left_alone():
    """Bịa một nhãn cho nó là gắn sai danh tính cho một run, tệ hơn không gắn
    -- cùng luật "hỏng thì đóng, không ánh xạ về khoá gần nhất" của
    `synthgen/field_tier.py`. Cổng vẫn loại phôi, và đó là kết cục đúng."""
    bad = wrap("<div>{{customer.name}}</div>")
    fixed, n = T.enclose(bad, KINDS)
    assert n == 0
    assert fixed == bad
    assert T.problems(fixed, KNOWN)


def test_a_placeholder_already_inside_a_run_is_not_wrapped_twice():
    """Bọc thêm một span vào trong là dựng đúng cái run-có-thẻ-lồng mà cổng
    cấm."""
    assert T.enclose(GOOD, KINDS) == (GOOD, 0)


def test_enclose_leaves_a_misspelt_placeholder_for_the_gate():
    bad = wrap("<div>{{ issuer.name }}</div>")
    assert T.enclose(bad, KINDS) == (bad, 0)


# ------------------------------------------- đánh dấu khối lặp model quên khai

def test_a_repeat_group_with_no_marked_block_gets_its_block_inferred():
    """Model viết đúng cú pháp `[]` rồi quên đánh dấu khối bao. Hình trội của
    lượt `data/25-09-phoi-v2`, sau khi `runify`+`enclose` đã dọn hình cũ."""
    bad = wrap('<div class="sig">'
               + run("signers[].title", kind="sign.title")
               + run("signers[].name", kind="sign.name") + "</div>")
    assert T.problems(bad, KNOWN)
    fixed, n = T.mark_repeats(bad)
    assert n == 1
    assert f'<div class="sig" {T.REPEAT_ATTR}="signers">' in fixed
    assert T.problems(fixed, KNOWN) == []


def test_the_smallest_enclosing_block_is_chosen_not_the_page():
    """Lấy khối lớn hơn là nhân bản nửa tờ giấy."""
    bad = wrap('<section><div class="sig">'
               + run("signers[].name", kind="sign.name") + "</div></section>")
    fixed, _n = T.mark_repeats(bad)
    assert f'<div class="sig" {T.REPEAT_ATTR}="signers">' in fixed
    assert f'<section {T.REPEAT_ATTR}' not in fixed


def test_a_block_holding_two_groups_is_refused_not_guessed():
    """Không khối nào bung được mà không kéo khối kia theo. Để cổng loại, và
    để người đọc thấy phôi thật sự có vấn đề cấu trúc."""
    bad = wrap('<div class="all">'
               + run("line_items[].name", kind="menu.name")
               + run("signers[].name", kind="sign.name") + "</div>")
    assert T.mark_repeats(bad) == (bad, 0)


def test_a_labelled_run_is_never_chosen_as_the_repeat_block():
    """Một run chỉ chứa chữ, nên nhân bản nó là N lần in CÙNG một trường."""
    bad = wrap("<div>" + run("signers[].name", kind="sign.name") + "</div>")
    fixed, n = T.mark_repeats(bad)
    assert n == 1
    assert f'<span data-kind="sign.name" data-path="signers[].name" {T.REPEAT_ATTR}' not in fixed
    assert f'<div {T.REPEAT_ATTR}="signers">' in fixed


def test_a_group_that_already_has_its_block_is_left_alone():
    assert T.mark_repeats(GOOD) == (GOOD, 0)
