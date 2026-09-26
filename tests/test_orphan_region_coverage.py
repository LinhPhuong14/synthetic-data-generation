"""Trang dựng toàn `<div>`/`<span>`: mọi run mực nằm ngoài mọi vùng bố cục.

Dựng từ ca trượt thật. `data/pilot17` (60 tờ, seed 0) có **4 tờ** trượt vì
`N/N run (100%) không nằm trong vùng bố cục nào đã khai; ngưỡng 99%`:

    tờ  5  llm_form_checklist_0005      119/119 run
    tờ 18  llm_insurance_health_id_card  36/36  run
    tờ 25  llm_meeting_minutes_0025      23/23  run
    tờ 54  llm_leave_application_0054    29/29  run

`SOUP_PILOT17` dưới đây trích NGUYÊN VĂN đầu tờ 5, theo đúng lối
`tests/test_repair.py` dựng ca pilot16 -- không phải ví dụ tự nghĩ.

## Vì sao 100%, và vì sao `repair.zoned()` không vá được

Đo trên cả 42 tờ có HTML của lô: **cả bốn tờ 100% mồ côi có đúng 0
`data-region` VÀ đúng 0 thẻ ngữ nghĩa**; mọi tờ qua cổng có ít nhất một
trong hai. Phân tách sạch, không một ca chồng lấn.

`repair.zoned()` suy vùng từ THẺ (`<p>`, `<section>`, `<header>`, `<ul>`...)
và cố tình KHÔNG suy từ tên class -- xem docstring của nó: tên class do model
tự đặt, suy nhãn vùng từ đó là đoán, và một cái hộp mang nhãn đoán tệ hơn một
cái hộp không nhãn. Tờ 5 viết `<div class="header">` chứ không viết
`<header>`, nên không có gì để `zoned()` bám vào. Phần ấy, đúng như docstring
`zoned()` đã định, "phải do model khai, và do cổng gác đòi" -- nên chỗ chữa
là LỜI DẶN, không phải thêm một phép đoán vào `repair.py`."""

from __future__ import annotations

import re

import pytest

from synthgen.llm_page import orphan_runs, orphan_share
from synthgen.repair import zoned

# Trích nguyên văn `data/pilot17/rejected/llm_form_checklist_0005.html`
# (đã bỏ khối <style>, giữ y nguyên markup phần thân).
SOUP_PILOT17 = """<div class="sheet">
  <div class="header">
    <div class="issuer">
      <div><span data-kind="store.name">SỞ Y TẾ THÀNH PHỐ HỒ CHÍ MINH</span></div>
      <div><span data-kind="store.address" data-path="issuer.address">127 Điện Biên Phủ, Quận Bình Thạnh, TP.HCM</span></div>
      <div><span data-kind="store.phone" data-path="issuer.phone">(028) 3899 1234</span></div>
      <div><span data-kind="store.tax_code" data-path="issuer.tax_code">0312345678</span></div>
    </div>
    <div class="meta">
      <div><span data-kind="meta.label">Số hiệu:</span> <span data-kind="meta.value" data-path="document.reference_number">KT-ATTP/2024/0123</span></div>
      <div><span data-kind="meta.label">Ngày:</span> <span data-kind="meta.value" data-path="document.issue_date">15/03/2024</span></div>
    </div>
  </div>
  <div class="title"><span data-kind="title">PHIẾU KIỂM TRA ĐIỀU KIỆN AN TOÀN THỰC PHẨM</span></div>
  <div class="section">
    <div class="section-title"><span data-kind="section.title">I. THÔNG TIN ĐƠN VỊ KIỂM TRA</span></div>
    <div class="field"><span data-kind="store.name.label">Tên đơn vị:</span> <span data-kind="store.name">Sở Y tế Thành phố Hồ Chí Minh</span></div>
  </div>
</div>"""


# --------------------------------------------- ca thật: cổng phải từ chối nó


def test_the_real_div_soup_leaves_every_run_orphaned():
    """Y như pilot17 đã từ chối thật: 100%, không phải 99% hay 60%."""
    loose, total = orphan_share(SOUP_PILOT17)
    assert total > 0, "không đếm được run nào -- phép đo hỏng, không phải trang"
    assert loose == total, f"{loose}/{total}"
    assert loose / total == 1.0


def test_the_real_div_soup_declares_no_region_and_no_semantic_tag():
    """Hai điều kiện cùng lúc -- đó là dấu vân tay của cả bốn tờ."""
    assert "data-region" not in SOUP_PILOT17
    tags = {t.lower() for t in re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)",
                                         SOUP_PILOT17)}
    assert tags == {"div", "span"}, tags


def test_repair_cannot_rescue_it_because_there_is_no_tag_to_read():
    """Chốt lại ranh giới của `zoned()`: nó KHÔNG đoán từ tên class.

    `class="header"`, `class="section"`, `class="field"` -- ba cái tên nghe
    như vùng bố cục, và không cái nào được đọc thành vùng. Nếu một ngày ai
    nới `zoned()` ra đọc tên class, test này đổi màu và buộc người ấy đọc
    docstring giải thích vì sao luật cũ là cố ý."""
    mended, n = zoned(SOUP_PILOT17)
    assert n == 0, f"zoned() đã khai {n} vùng từ tên class"
    loose, total = orphan_share(mended)
    assert loose == total, "vá xong vẫn phải còn mồ côi hết"


# ------------------------------------------- và yêu cầu ấy phải thoả mãn được


def test_one_semantic_tag_is_enough_to_shelter_the_block():
    """`<header>` thay cho `<div class="header">` -- đúng một chữ, và cả khối
    thoát mồ côi. Đây là lý do lời dặn ưu tiên thẻ ngữ nghĩa: rẻ hơn nhiều so
    với bắt model học thuộc hai mươi cái tên vùng."""
    fixed = SOUP_PILOT17.replace('<div class="header">', "<header>", 1)
    fixed = fixed.replace("  </div>\n  <div class=\"title\">",
                          "  </header>\n  <div class=\"title\">", 1)
    mended, n = zoned(fixed)
    assert n >= 1, "zoned() phải đọc được `<header>`"
    loose_after, total = orphan_share(mended)
    loose_before, _ = orphan_share(SOUP_PILOT17)
    assert loose_after < loose_before, f"{loose_after} vs {loose_before}"


def test_an_explicit_data_region_also_shelters_the_block():
    """Đường thứ hai lời dặn cho phép, cho chỗ không thẻ nào mang nghĩa."""
    fixed = SOUP_PILOT17.replace('<div class="meta">',
                                 '<div class="meta" data-region="Text">', 1)
    loose_after, total = orphan_share(fixed)
    loose_before, _ = orphan_share(SOUP_PILOT17)
    assert loose_after < loose_before, f"{loose_after} vs {loose_before}"


def test_the_orphans_are_reported_with_kind_and_text_for_review():
    """Danh sách trả về phải đủ để mổ tờ hỏng mà không mở lại HTML thô."""
    loose = orphan_runs(SOUP_PILOT17)
    assert loose
    assert any("store.name" in item for item in loose)
    assert any("SỞ Y TẾ" in item for item in loose)


# ------------------------------------ lời dặn và cổng gác phải nói cùng một luật


def test_the_prompt_now_demands_what_the_gate_measures():
    """Trước bản này hai bên nói ngược nhau.

    Mục 14 dặn "do not create regions merely to satisfy a numeric target" --
    một câu CAN model đừng thêm vùng -- trong khi cổng loại thẳng tờ có >99%
    run ngoài vùng. Model nghe lời dặn thì trượt cổng. Không phép đo nào bắt
    được chuyện ấy vì nó không phải lỗi mã: nó là hai câu luật cãi nhau."""
    from agent.compose_page import system_prompt

    prompt = system_prompt()
    assert "EVERY RUN OF INK MUST SIT INSIDE A REGION" in prompt
    # Và phải nói rõ hai thẻ vô nghĩa kia, vì đó đúng là thứ model đã dùng.
    assert "`<div>` and `<span>` declare nothing" in prompt


def test_the_prompt_still_warns_against_inflating_the_region_count():
    """Luật mới KHÔNG được xoá luật cũ: đòi phủ kín mà không nói gì về số
    lượng thì model wrap mỗi dòng một vùng, và `pipeline/record.py` nhận một
    tờ toàn vùng một dòng -- đổi một lỗi lấy một lỗi."""
    from agent.compose_page import system_prompt

    prompt = system_prompt()
    assert "Do not create regions merely to satisfy a numeric target" in prompt
    assert "not one per line" in prompt


# ------------------- khối chữ ký: cổng hỏi `sign.`, lời dặn phải nói `sign.`

# Trích nguyên văn cuối tờ `data/pilot17/rejected/llm_invoice_detailed_0023
# .html` -- khối chữ ký đủ mực mà không một `data-kind` nào.
SIGS_PILOT17 = (
    '<div class="sigs"><div class="sig-block">'
    '<div class="role">NGƯỜI MUA HÀNG</div>'
    '<div class="name">Ths. Trần Thị Mai</div>'
    '<div class="date">Vinh, ngày 15 tháng 8 năm 2024</div></div>'
    '<div class="sig-block"><div class="role">NGƯỜI BÁN HÀNG</div>'
    '<div class="name">Nguyễn Văn Bình</div>'
    '<div class="date">Vinh, ngày 15 tháng 8 năm 2024</div></div></div>')


def test_the_real_signature_block_carries_no_kind_at_all():
    """Mực có, nhãn không -- luật số ba của `AGENTS.md` bị phá lặng lẽ.

    Tờ 23 in ra hai tên người, hai vai, hai ngày, và không khai một chữ nào.
    Cổng bắt được nó chỉ nhờ `plan` đòi 2 chữ ký."""
    assert "data-kind" not in SIGS_PILOT17
    assert "sign." not in SIGS_PILOT17
    # Mà mực thì có thật, và nhiều.
    assert "Ths. Trần Thị Mai" in SIGS_PILOT17


def test_the_gate_still_refuses_that_block():
    """Tái dựng phép gác đã loại tờ 23."""
    import random

    from agent import document_plan as DP
    from agent import grammar as G
    from agent.compose_page import plan_conformance_problems

    plan = DP.sample(G.FAMILIES["invoice_detailed"], random.Random(23))
    if not plan.assignment.get("signature_count"):
        pytest.skip("phôi này không đòi chữ ký")
    found = plan_conformance_problems(
        plan, f'<div class="sheet">{SIGS_PILOT17}</div>')
    assert any("sign." in f for f in found), found


def test_the_brief_now_names_the_kind_family_not_just_the_count():
    """Câu cũ nói "đúng N người ký" và im về CÁCH KHAI, nên model dựng khối
    chữ ký bằng tên class của chính nó -- 3 tờ pilot17 trượt vì thế."""
    import random

    from agent import document_plan as DP
    from agent import grammar as G
    from agent.compose_page import describe_plan

    for family in sorted(G.FAMILIES):
        plan = DP.sample(G.FAMILIES[family], random.Random(0))
        if not plan.assignment.get("signature_count"):
            continue
        text = describe_plan(plan)
        assert "`sign." in text, text
        assert "tên class tự đặt KHÔNG tính" in text
        return
    pytest.skip("không phôi nào đòi chữ ký")
