"""Lời nhờ phải xin ĐỦ CHỮ để Chromium cắt ra đúng số tờ đã xin.

Dựng từ ca trượt thật: `data/pilot17` (60 tờ, seed 0) có **23 tờ** trượt vì
`xin N tờ nhưng dàn trang thật chỉ ra M tờ (dưới 60% số đã xin)` -- lý do
trượt CỔNG lớn nhất của lô. `SHORTFALL_PILOT17` dưới đây là đúng 23 cặp
(xin, thật) đọc từ `compose_report.json`.

## Vì sao đây KHÔNG phải cổng siết quá tay

Dấu hiệu của một ngưỡng siết quá tay là một cụm nằm SÁT dưới ngưỡng -- xin 6
ra 5 (83%), xin 10 ra 5 (50%) lẫn lộn quanh 0,6. Thực đo thì khác hẳn:
không một tờ nào trong 23 tờ chạm quá **0,50**, và cả cụm trải từ 0,14 tới
0,50. Một khoảng trống sạch giữa 0,50 và ngưỡng 0,60 nghĩa là số tờ thiếu
theo cơ chế, không theo mép ngưỡng.

Cơ chế ấy đo được: ở nhánh LLM model viết đúng MỘT `.sheet` (mục 40
`agent/prompts/page.md`) rồi Chromium cắt theo chiều cao A4, và một tờ A4
thật chứa 1 527--2 002 ký tự chữ -- trong khi lời nhờ chỉ xin 850--1 650.
Xin ít hơn sức chứa thì tuân thủ hoàn hảo vẫn ra thiếu tờ. Xem
`rulebase/synthgen/_blocks.yaml::llm_density`.

Không gọi model, không mở trình duyệt: chỉ dựng lời nhờ và đọc con số."""

from __future__ import annotations

import random as _random
import re as _re

import pytest

from synthgen.design import llm_density

# (xin, dàn ra thật) của đúng 23 tờ pilot17 trượt vì thiếu tờ.
SHORTFALL_PILOT17 = [
    (2, 1), (2, 1), (2, 1), (2, 1), (2, 1), (2, 1),
    (3, 1), (3, 1), (3, 1),
    (4, 1), (4, 1), (4, 2), (4, 2),
    (5, 2), (5, 2), (5, 2), (5, 2),
    (6, 2),
    (7, 1), (7, 2), (7, 3),
    (8, 3), (8, 4),
]

# Sức chứa THẬT của một tờ A4 ở nhánh LLM, đo trên pilot17:
# `visible_chars()` chia cho số tờ Chromium cắt ra thật.
CAPACITY_PILOT17 = {"sparse": 1527, "medium": 1852, "dense": 2002}

# Model giao được bao nhiêu so với số đã xin -- trung vị 42 lời gọi trả
# lời được của cùng lô.
COMPLIANCE_PILOT17 = 0.57

LEVELS = ("sparse", "medium", "dense", "very_dense")


def _brief(sheets: int, index: int = 0):
    from agent import document_plan as DP
    from agent import grammar as G
    from agent.compose_page import ask_for

    family = sorted(G.FAMILIES)[index % len(G.FAMILIES)]
    plan = DP.sample(G.FAMILIES[family], _random.Random(index))
    return plan, ask_for(index, [], plan, sheets, "en")


# ------------------------------------------------ ca thật: khoảng trống 0,50


def test_the_pilot17_shortfall_is_a_gap_not_a_threshold_edge():
    """Không tờ nào chạm 0,51: cụm dừng hẳn dưới ngưỡng, không bám mép nó."""
    ratios = [real / asked for asked, real in SHORTFALL_PILOT17]
    assert max(ratios) == 0.5, f"cao nhất đo được: {max(ratios)}"
    # Hạ ngưỡng xuống ngay trên cụm (0,51) cũng không cứu được tờ nào -- nên
    # chữa bằng cách hạ ngưỡng là chữa vào chỗ không có bệnh.
    assert not [r for r in ratios if 0.5 < r < 0.6]


# -------------------------------------- lời nhờ phải xin hơn sức chứa một tờ


def _capacity(level: str) -> int:
    """Sức chứa một tờ A4 của mức `level`.

    `very_dense` không có tờ nào trong pilot17 (n=0), nên nó mượn mức dày
    nhất ĐÃ đo được -- một cận dưới, không phải một con số bịa: mức dày hơn
    không thể chứa ít chữ hơn."""
    return CAPACITY_PILOT17.get(level, max(CAPACITY_PILOT17.values()))


@pytest.mark.parametrize("level", LEVELS)
def test_each_density_asks_for_more_than_one_real_sheet_holds(level):
    """Xin ít hơn sức chứa thì model TUÂN THỦ HOÀN HẢO vẫn ra thiếu tờ.

    Đây là phép kiểm không phụ thuộc model: nó chỉ so hai con số ta tự đặt
    -- mục tiêu ký tự, và sức chứa đã đo -- nên nó bắt được lỗi ngay cả khi
    không có server nào để chạy thử."""
    asked = llm_density(level).get("chars")
    assert asked, f"{level} chưa khai trong `_blocks.yaml`"
    assert asked >= _capacity(level), (
        f"{level}: xin {asked} ký tự/tờ, nhưng một tờ A4 thật chứa tới "
        f"{_capacity(level)} -- thiếu tờ là chắc chắn, không phải rủi ro")


@pytest.mark.parametrize("level", LEVELS)
def test_each_density_also_covers_how_little_the_model_actually_delivers(level):
    """Sức chứa mới là một nửa bài toán; nửa kia là model giao thiếu.

    Đo trên pilot17: giao được 57% số ký tự đã xin. Nhân hai hiệu ứng lại
    thì mục tiêu phải là `sức chứa / 0,57`, nếu không tỉ lệ tờ rơi về
    0,65 x 0,57 = 0,37 -- đúng con số 23 tờ kia đã rơi vào (trung vị 0,41)."""
    asked = llm_density(level).get("chars")
    need = _capacity(level) / COMPLIANCE_PILOT17
    assert asked >= need, (
        f"{level}: xin {asked}, cần chừng {need:.0f} để bù cả sức chứa lẫn "
        "mức tuân thủ 57%")


@pytest.mark.parametrize("level,old", [("sparse", 850), ("medium", 1200),
                                       ("dense", 1650)])
def test_the_old_rule_branch_numbers_would_fail_this(level, old):
    """Chốt lại CHÍNH các con số cũ để không ai lặng lẽ khôi phục chúng.

    `{sparse 850, medium 1200, dense 1650}` đo từ nhánh luật, nơi engine tự
    đặt mỗi `.sheet` là một tờ -- một đại lượng khác, và cả ba đều thấp hơn
    sức chứa của chính mức ấy.

    `very_dense` (cũ 2 200) KHÔNG có mặt ở đây: pilot17 không có tờ nào mức
    ấy để đo, nên không có phép đo nào chứng minh 2 200 là sai. Khẳng định
    nó sai thì chỉ là đoán -- và đoán đúng cái kiểu đã đẻ ra lỗi này."""
    assert old < CAPACITY_PILOT17[level], (
        f"{level}: {old} vốn đã thấp hơn sức chứa {CAPACITY_PILOT17[level]}")


# ------------------------------------------- hai con số trong brief không cãi nhau


def test_the_row_target_scales_with_the_character_target():
    """"Viết 3 250 ký tự" đứng cạnh "11 dòng bảng" là hai con số chỏi nhau,
    và đo trên `data/23-09-llm-e` thì model nghe con số NHỎ. Mức dày hơn
    phải xin cả nhiều chữ HƠN lẫn nhiều dòng HƠN."""
    chars = [llm_density(lvl)["chars"] for lvl in LEVELS]
    rows = [llm_density(lvl)["rows"] for lvl in LEVELS]
    assert chars == sorted(chars), chars
    assert rows == sorted(rows), rows


def test_the_brief_states_the_bigger_per_sheet_target(monkeypatch):
    """Con số mới phải đi tới tận LỜI NHỜ, không dừng ở YAML."""
    _, brief = _brief(4, 0)
    numbers = [int(x.replace(",", "")) for x in
               _re.findall(r"\*\*([\d,]+) characters", brief)]
    assert numbers, brief[:200]
    assert numbers[0] >= max(CAPACITY_PILOT17.values()), (
        f"lời nhờ vẫn xin {numbers[0]} ký tự/tờ")


# ------------------------------- `sheet_plan`: đếm chính xác, không "xấp xỉ"

# 3 tờ pilot17 trượt vì `sheet_plan` khai thiếu mục: (xin, đã khai).
PLAN_SHORT_PILOT17 = [(3, 2), (8, 3), (3, 1)]


@pytest.mark.parametrize("asked,declared", PLAN_SHORT_PILOT17)
def test_a_short_sheet_plan_is_still_refused(asked, declared):
    """Tái dựng cả ba ca: cổng phải từ chối, y như pilot17 đã từ chối."""
    from agent.compose_page import sheet_plan_problems

    plan = {"sheet_plan": [{"sheet": i + 1, "sections": ["x"]}
                           for i in range(declared)]}
    found = sheet_plan_problems(plan, asked)
    assert found, f"khai {declared}/{asked} mà cổng im"
    assert f"chỉ khai {declared} tờ" in found[0]


def test_the_brief_calls_the_sheet_plan_count_exact_not_about():
    """Hai con số, hai độ chính xác -- và câu cũ gộp chúng.

    Số tờ CẮT RA có dung sai (`SHEET_SHORTFALL_RATIO`, tới 0,6 lần). Số mục
    `sheet_plan` thì không: `sheet_plan_problems()` loại thẳng khi thiếu một
    mục. Câu cũ mở đầu "runs to about **N A4 sheets**" nên chữ "about" phủ
    lên cả hai, và model khai một `sheet_plan` xấp xỉ -- 3 tờ pilot17 trượt
    đúng vì thế (khai 2/3, 3/8, 1/3)."""
    _, brief = _brief(8, 0)
    assert "exactly 8 entries" in brief, brief[-700:]
    assert '"About" applies to how much you write' in brief


@pytest.mark.parametrize("asked,real", SHORTFALL_PILOT17)
def test_every_pilot17_shortfall_case_is_explained_by_the_capacity_gap(asked,
                                                                      real):
    """Mỗi ca thật một phép kiểm.

    Mô hình: `tờ dàn ra ~= xin x (ký tự mỗi tờ x tuân thủ) / sức chứa`. Với
    con số CŨ (medium 1 200) mô hình dự đoán 0,37 tờ cho mỗi tờ đã xin; mọi
    ca thật đều nằm dưới ngưỡng 0,6, và cái đã đo được trung vị 0,41.

    Phép kiểm này gác MÔ HÌNH, không gác con số: nếu ai đổi `llm_density` về
    một giá trị làm mô hình dự đoán lại rơi xuống dưới ngưỡng, nó kêu."""
    from agent.compose_page import SHEET_SHORTFALL_RATIO

    old_predicts = 1200 * COMPLIANCE_PILOT17 / CAPACITY_PILOT17["medium"]
    assert real / asked <= SHEET_SHORTFALL_RATIO, "ca này vốn không trượt"
    assert old_predicts < SHEET_SHORTFALL_RATIO, (
        "mục tiêu cũ lẽ ra phải dự đoán được chính cú trượt này")
    # Và con số MỚI phải đưa mô hình lên trên ngưỡng -- nếu không thì sửa
    # YAML xong vẫn trượt y như cũ.
    now = llm_density("medium")["chars"]
    assert now * COMPLIANCE_PILOT17 / CAPACITY_PILOT17["medium"] >= 1.0, (
        f"xin {now} ký tự/tờ vẫn chưa đủ dàn ra đủ số tờ")


# ------------------------------- trần token và hạn chờ phải cùng đọc một chỗ


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("sheets", [1, 2, 4, 8])
def test_the_token_ceiling_covers_the_character_target(sheets, level):
    """Mục tiêu ký tự tăng mà trần token không biết thì cả lô cụt JSON.

    Tính thử trước khi chạy đã chặn đúng một lượt sinh vô ích: mục tiêu mới
    cần 11 115 token cho MỘT tờ medium, trong khi trần cũ (`2 600 +
    sheets * 5 200`) cho một tờ là 7 800 -- và cả tám mức số tờ đều thiếu.
    Đó là 60 tờ cụt thay cho 23 tờ thiếu tờ."""
    from agent.compose_page import TOKENS_PER_VISIBLE_CHAR, budget

    need = sheets * llm_density(level)["chars"] * TOKENS_PER_VISIBLE_CHAR
    assert budget(sheets, level) >= need, (
        f"{sheets} tờ {level}: trần {budget(sheets, level)} < cần {need:.0f}")


def test_the_timeout_is_bounded_even_for_the_biggest_document():
    """Trần token lớn KHÔNG được biến thành hạn chờ vô hạn.

    `budget(8, "very_dense")` = 105 048 token, chia 15 tok/s ra 7 003 giây một
    lần thử, và `Client._post` thử lại 3 lần. Đo trên `data/pilot18`: tờ thứ
    20 treo 14,2 giờ khi máy chủ tắt."""
    from agent.compose_page import PATIENCE_CEILING, patience

    worst = patience(8, 120.0, "very_dense")
    assert worst <= PATIENCE_CEILING, worst
    # Và vẫn phải rộng hơn lời gọi chậm nhất từng đo được (pilot18 2 344s).
    assert worst >= 2344, worst
