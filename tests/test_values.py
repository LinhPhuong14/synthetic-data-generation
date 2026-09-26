"""`synthgen/values.py` -- tờ khai sự thật cho một lần điền phôi.

Phép kiểm quan trọng nhất ở đây là `test_every_registry_path_has_a_generator`:
nó là thứ biến một lỗ hổng IM LẶNG thành một test đỏ. Thêm một khoá vào sổ
đăng ký mà quên bộ sinh thì phôi nào xin khoá ấy in nguyên `{{…}}` lên mặt
giấy, và không có test này thì không gì kêu lên cho tới khi ai đó mở ảnh ra
xem (AGENTS.md mục 5 và 6).
"""

from __future__ import annotations

import random

import pytest

from synthgen import values as V

# Sổ đóng thật cần `cv2` để dựng (`field_tier.registry()` gọi `llm_page.
# kinds()`). Bỏ qua khi thiếu, thay vì để cả tệp đỏ ở job không cài thư viện.
FT = pytest.importorskip("synthgen.field_tier")
pytest.importorskip("cv2")


def test_every_registry_path_has_a_generator():
    """Sổ đăng ký và bộ sinh phải khớp từng khoá một. Không có nhánh mặc
    định trả chuỗi rỗng, và đặc biệt không có 'lấy lá gần giống nhất' -- xem
    docstring `synthgen/values.py`."""
    assert V.missing_paths() == []


def test_a_fact_sheet_answers_every_registry_path():
    tree = V.facts(random.Random(1), rows=3, signers=2, clauses=2)
    flat = V.flatten(tree)
    for key in FT.closed_enum(FT.PATH):
        probe = key.replace("[]", "[0]")
        assert probe in flat, f"{key} không có trong tờ khai"
        assert str(flat[probe]).strip() or key.endswith((".note", ".subtitle")), \
            f"{key} rỗng mà không phải trường được phép rỗng"


def test_table_arithmetic_closes():
    """`qty × unit_price == amount` -- đúng phép `synthgen/check.py` kiểm
    trên cả kho và `agent/compose_page.py::arithmetic` kiểm trên mỗi tờ."""
    tree = V.facts(random.Random(5), rows=12)
    assert len(tree["_rows"]) == 12
    for row in tree["_rows"]:
        assert row["qty"] * row["unit_price"] == row["amount"]


def test_the_same_path_read_twice_gives_the_same_value():
    """Đây là lý do có một TỜ KHAI thay vì sáu mươi lần bốc rời: luật 'cùng
    `data-path` thì cùng giá trị' của `synthgen/llm_page.py` thành đúng theo
    cấu tạo. Đo trên `data/pilot16`: 15 tờ trượt cổng đúng vì luật ấy khi
    model tự viết."""
    tree = V.facts(random.Random(9), rows=2)
    a = V.resolve(tree, "issuer.name")
    b = V.resolve(tree, "issuer.name")
    assert a == b and a[0] is True


def test_the_issuer_is_one_organisation_not_several():
    """Tên tổ chức, tên miền và mã đơn vị phải nói về cùng một nơi."""
    tree = V.facts(random.Random(11), rows=1)
    name = tree["issuer"]["name"]
    stem = V._ascii_stem(name)
    assert tree["issuer"]["website"].startswith("www.")
    assert stem[:4] in tree["issuer"]["website"]
    assert stem[:4].upper() in tree["issuer"]["code"]


def test_overrides_win_over_the_generated_value():
    tree = V.facts(random.Random(3), rows=1,
                   overrides={"document.title": "BIÊN BẢN BÀN GIAO"})
    assert tree["document"]["title"] == "BIÊN BẢN BÀN GIAO"


def test_resolve_refuses_an_unknown_path_instead_of_guessing():
    tree = V.facts(random.Random(2), rows=1)
    assert V.resolve(tree, "patient.bed_no") == (False, "")
    assert V.resolve(tree, "line_items[99].name") == (False, "")


def test_flatten_hides_the_raw_integers_used_for_the_arithmetic_check():
    """`_qty` và bạn bè không phải trường in lên giấy, và không có khoá nào
    như thế trong sổ đăng ký -- nên không phôi nào xin được chúng."""
    flat = V.flatten(V.facts(random.Random(4), rows=2))
    assert not [k for k in flat if "._" in k or k.startswith("_")]


def test_two_seeds_give_two_different_sheets():
    a = V.flatten(V.facts(random.Random(1), rows=4))
    b = V.flatten(V.facts(random.Random(2), rows=4))
    assert a != b
