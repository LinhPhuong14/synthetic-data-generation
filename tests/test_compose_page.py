"""`agent/compose_page.py::resolve_path`/`data_path_mismatches`.

Không mở trình duyệt, không gọi model -- cả hai hàm chỉ đi qua một dict
Python và một chuỗi HTML, nên file này chạy trong CI không phụ thuộc.

## Vì sao file này tồn tại

`schema()` bắt model viết cây `data` TRƯỚC khi viết HTML (xem docstring của
`schema()`), nhưng cây ấy chỉ được ghi ra `declared/*.json` rồi không ai đọc
lại -- xác nhận qua audit và qua chính comment tại chỗ đọc nó ra
(`agent/compose_page.py` quanh dòng khai `answer.get("data")`). Đo trên
`data/pilot12` thật (4 tài liệu có `data` không rỗng -- `data/pilot10` sinh
trước khi việc đọc ra được sửa, nên `data` luôn `null`): 2/4 khớp hoàn toàn,
2/4 lệch nhưng đều là khác biệt ĐỊNH DẠNG lành tính (`"1583000000"` trong
`data` so với `"1.583.000.000"` in trên giấy; `"452/BB-SYT"` trong `data` so
với `"Số: 452/BB-SYT"` in kèm nhãn) -- không phải mâu thuẫn ngữ nghĩa. Đây là
lý do `data_path_mismatches` là hàm ĐO cho việc gỡ lỗi, không phải hàm GATE:
xem docstring của nó.
"""

from __future__ import annotations

from agent.compose_page import data_path_mismatches, resolve_path


def test_a_simple_dotted_path_resolves():
    data = {"issuer": {"tax_code": "0312345678"}}
    assert resolve_path(data, "issuer.tax_code") == (True, "0312345678")


def test_an_array_index_resolves():
    data = {"line_items": [{"name": "Máy in"}, {"name": "Mực in"}]}
    assert resolve_path(data, "line_items[1].name") == (True, "Mực in")


def test_a_bare_digit_segment_resolves_as_an_index_too():
    """`[N]` không còn là hình DUY NHẤT hợp lệ cho chỉ số -- `synthgen/
    llm_page.py::_PATH` giờ chấp nhận `clause.1.body` (Phase 8, đo trên
    pilot16: 16 đường bị cổng cũ loại một tờ đúng mọi luật khác chỉ vì thiếu
    ngoặc vuông). `resolve_path` phải đọc được hình này để không âm thầm bỏ
    qua đoạn số, trỏ nhầm sang trường khác."""
    data = {"clause": [{"body": "Điều khoản một"}, {"body": "Điều khoản hai"}]}
    assert resolve_path(data, "clause.1.body") == (True, "Điều khoản hai")


def test_a_missing_key_fails_cleanly():
    data = {"issuer": {"tax_code": "x"}}
    assert resolve_path(data, "issuer.address") == (False, None)


def test_an_out_of_range_index_fails_cleanly():
    data = {"rows": [1]}
    assert resolve_path(data, "rows[5]") == (False, None)


def test_indexing_into_something_that_is_not_a_list_fails_cleanly():
    data = {"issuer": "not a list"}
    assert resolve_path(data, "issuer[0]") == (False, None)


def test_a_matching_value_has_no_mismatch():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.name">'
           "CÔNG TY ABC</span></div>")
    assert data_path_mismatches(data, html) == []


def test_a_different_printed_value_is_reported():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.name">'
           "CÔNG TY XYZ</span></div>")
    found = data_path_mismatches(data, html)
    assert len(found) == 1
    assert "issuer.name" in found[0]


def test_a_path_the_data_tree_never_declared_is_reported():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet"><span data-kind="x" data-path="issuer.ghost">'
           "nope</span></div>")
    found = data_path_mismatches(data, html)
    assert any("không tra được" in line for line in found)


def test_a_span_with_no_data_path_is_ignored():
    data = {}
    html = '<div class="sheet"><span data-kind="x">bất kỳ chữ gì</span></div>'
    assert data_path_mismatches(data, html) == []


def test_the_same_path_printed_twice_with_the_same_value_is_fine():
    data = {"issuer": {"name": "CÔNG TY ABC"}}
    html = ('<div class="sheet">'
           '<span data-kind="x" data-path="issuer.name">CÔNG TY ABC</span>'
           '<span data-kind="x" data-path="issuer.name">CÔNG TY ABC</span>'
           "</div>")
    assert data_path_mismatches(data, html) == []


# ===========================================================================
# LỜI NHỜ PHẢI CO GIÃN THEO SỐ TỜ
#
# Đo trên `data/23-09-llm-d`: 7 trên 12 tờ trượt cổng với "xin N tờ nhưng dàn
# trang thật chỉ ra M<N tờ". Không phải trần token -- tờ xin 8 chỉ dùng
# 8 333/16 384. Lời nhờ xin `10 + sheets*4` dòng bảng, tức 8 tờ mà chỉ 42
# dòng, trong khi một tờ A4 dày bảng chứa chừng ấy MỘT MÌNH: bảng không dài
# ra thì không có gì để cắt sang tờ sau.
#
# Ngược lại, số ký tự thì xin QUÁ NHIỀU: `sheets * 8000`, gấp bảy lần tờ giấy
# thật (58 tài liệu nhánh luật, trung vị 1 175 ký tự chữ mỗi tờ).
# ===========================================================================

import random as _random
import re as _re


def _brief(sheets: int, index: int = 0):
    from agent import document_plan as DP, grammar as G
    from agent.compose_page import ask_for

    family = sorted(G.FAMILIES)[index % len(G.FAMILIES)]
    plan = DP.sample(G.FAMILIES[family], _random.Random(index))
    return plan, ask_for(index, [], plan, sheets, "en")


def _rows_asked(brief: str):
    """Số dòng CHÍNH XÁC lời nhờ đòi, hoặc `None` nếu tờ này không có bảng.

    Lời nhờ từng nói một KHOẢNG ("83-93 rows") và model đọc nó như một lời
    tả. Giờ nó nói một con số và ra lệnh đếm -- đo được: cùng phôi cùng seed,
    câu tả cho 1 `<tr>`, câu lệnh cho 63."""
    found = _re.search(r"exactly (\d+) `<tr>` rows", brief)
    return int(found.group(1)) if found else None


def test_a_longer_document_asks_for_a_longer_table():
    """Số dòng phải nhân theo số tờ, không cộng thêm một ít.

    Tám tờ mà xin 42 dòng là xin một cái bảng vừa đúng một trang, rồi trách
    model không cắt ra tám trang."""
    seen = {}
    for index in range(len(__import__("agent.grammar", fromlist=["FAMILIES"]).FAMILIES)):
        plan, brief = _brief(4, index)
        if "table" in plan.assignment and _rows_asked(brief):
            seen[index] = plan
            break
    assert seen, "không tìm được family nào có bảng"
    index = next(iter(seen))
    one = _rows_asked(_brief(1, index)[1])
    eight = _rows_asked(_brief(8, index)[1])
    assert one and eight
    assert eight >= one * 5, (
        f"1 tờ xin {one} dòng, 8 tờ xin {eight} -- không co giãn theo số tờ")


def test_the_character_target_matches_a_real_sheet_not_a_guess():
    """`sheets * 8000` là con số chưa ai đo. Nhánh luật -- thứ đã chạy và đã
    được soi bằng mắt -- có trung vị 1 175 ký tự chữ mỗi tờ, và p75 là 1 661.
    Một mục tiêu gấp bảy lần thực tế không dạy model viết dày hơn; nó dạy
    model rằng mục tiêu ấy không nghiêm túc."""
    for sheets in (2, 4, 8):
        _, brief = _brief(sheets, 0)
        # Lời nhờ nói THẲNG số mỗi tờ (con số đầu) rồi mới tới tổng. Đọc con
        # số đầu, không chia tổng cho số tờ: phép chia ấy đúng chỉ khi hai vế
        # đã nhất quán, và chính sự nhất quán ấy là thứ test kế bên kiểm.
        numbers = [int(x.replace(",", "")) for x in
                   _re.findall(r"\*\*([\d,]+) characters", brief)]
        assert numbers, brief[:200]
        per_sheet = numbers[0]
        assert 700 <= per_sheet <= 2600, (
            f"{per_sheet} ký tự/tờ nằm ngoài khoảng đo được của nhánh luật "
            f"(p25 854, trung vị 1 175, p75 1 661)")


def test_every_density_level_is_declared_in_the_rule_base():
    """`agent/grammar.py` rút một trong bốn mức; thiếu một mức trong YAML thì
    tài liệu mức ấy lặng lẽ lùi về mặc định, và không ai thấy."""
    from synthgen.design import llm_density

    for level in ("sparse", "medium", "dense", "very_dense"):
        got = llm_density(level)
        assert got.get("chars") and got.get("rows"), f"{level}: {got}"
    order = [llm_density(l)["chars"] for l in
             ("sparse", "medium", "dense", "very_dense")]
    assert order == sorted(order), f"mức dày hơn phải xin nhiều chữ hơn: {order}"


def test_the_brief_never_states_two_different_densities_in_one_breath():
    """Hai con số trong CÙNG một câu phải nhân ra nhau.

    Câu `n_sheets` từng ghi "(about 8,000 characters per A4 sheet)" viết
    cứng trong mẫu. Khi tổng chuyển sang tính theo `density`, model nhận
    "9600 ký tự tổng" cho 8 tờ -- tức 1 200 mỗi tờ -- đứng ngay cạnh "8 000
    mỗi tờ". Hai con số cãi nhau thì model nghe con số nhỏ: đo trên
    `data/23-09-llm-e`, 8 trên 12 tờ trượt vì "xin N tờ, dàn ra 1 tờ".

    Một lời dặn tự mâu thuẫn không hỏng to -- nó hỏng câm, và chỗ hỏng hiện
    ra cách đó ba bước dưới dạng "model không nghe lời"."""
    for sheets in (2, 4, 8):
        _, brief = _brief(sheets, 0)
        numbers = [int(x.replace(",", "")) for x in
                   _re.findall(r"\*\*([\d,]+) characters", brief)]
        assert len(numbers) == 2, f"{sheets} tờ: tìm thấy {numbers}"
        per, total = numbers
        assert per * sheets == total, (
            f"{sheets} tờ: {per}/tờ nhưng tổng ghi {total} "
            f"(phải là {per * sheets})")


def test_the_table_instruction_is_an_order_to_count_not_a_description():
    """Ba điều kiện của một phép đếm, và câu cũ thiếu cả ba.

    Đo thật trên `gpt-4.1-mini`, cùng phôi cùng seed, chỉ khác cách nói:

        "HAS an item table, 83-93 rows"  ->  4 613 token, **1** `<tr>`
        "exactly 80 `<tr>` … count them" -> 22 172 token, **63** `<tr>`

    Vế đầu còn khai 64 dòng trong `rows` JSON rồi viết đúng một `<tr>` --
    model tưởng đã làm xong việc khi kể ra con số."""
    for index in range(len(__import__("agent.grammar",
                                      fromlist=["FAMILIES"]).FAMILIES)):
        plan, brief = _brief(6, index)
        if "table" not in plan.assignment:
            continue
        assert _rows_asked(brief), "không nói con số chính xác nào"
        assert "Count them as you write" in brief, "không ra lệnh đếm"
        assert "rejected" in brief, "không nói hậu quả của việc thiếu"
        return
    raise AssertionError("không tìm được family nào có bảng")


def test_a_broken_call_still_produces_a_record_shaped_like_the_others():
    """`future.result()` ném lại ngoại lệ của worker. Không ai bắt thì một
    lỗi lạ ở tờ thứ tư làm mất CẢ LƯỢT -- đo được: lô 12 tờ chết vì
    `http.client.IncompleteRead`, ba tờ đã vẽ xong cũng mất theo.

    Nhưng bắt rồi trả về một dict THIẾU KHOÁ thì chỉ đổi ngoại lệ lấy một
    `KeyError` ở vòng in ngay sau -- cùng hậu quả, khó lần hơn. Nên kiểm hình
    dạng, không kiểm việc bắt."""
    from agent.compose_page import broken

    got = broken(4, RuntimeError("đứt"))
    # Đúng những khoá vòng in và `_why_tally` đọc.
    for key in ("index", "archetype", "ok", "seconds", "why", "chars",
                "rows_wrong", "rows_total", "tokens_out", "tokens_per_second",
                "sheets_asked", "mended", "html", "rows", "plan"):
        assert key in got, f"thiếu khoá {key!r}"
    assert got["ok"] is False
    assert got["why"] and "RuntimeError" in got["why"][0]
    assert got["index"] == 4
    # Vòng in thật sự chạy được trên nó.
    assert f"{got['seconds']:5.1f}s" and got["why"][0][:70]
