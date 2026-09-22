"""`pipeline/tags.py` là MỘT bảng, và ba nơi đọc nó phải không lệch được.

Kho này đã bị cắn nhiều lần vì một luật đúng mà chỉ một chỗ biết. Bảng "thẻ
HTML nghĩa là gì" từng tồn tại hai bản -- một trong chuỗi JS của
`generators/html/page.py`, một trong `synthgen/repair.py` -- phủ hai tập thẻ
khác nhau, và chỗ hở giữa chúng im lặng theo cả hai chiều: `<p>` có chữ mà
khối không có vùng, `<header>` có vùng mà chữ trần không có hộp.

Mỗi test dưới đây là một bản chép mà file này không cho phép tái sinh.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline import tags as T                                  # noqa: E402
from pipeline.record import DOCSYNTH_LABELS                     # noqa: E402


def test_every_region_label_is_one_the_record_knows():
    """Một nhãn gõ sai ở đây không ném -- nó đi thẳng vào `layout_annotations`
    và `validate` mới từ chối, cách đó vài nghìn trang."""
    labels = set(T.region_by_tag().values()) | set(T.MEASURED_ELSEWHERE)
    unknown = labels - DOCSYNTH_LABELS
    assert not unknown, f"nhãn không có trong bảng 21 nhãn: {sorted(unknown)}"
    # `Blank-Page` nói về CẢ TRANG, nên không thẻ nào được khai nó.
    assert "Blank-Page" not in labels


def test_every_kind_is_one_the_engine_actually_prints():
    """`repair.tagged()` bọc chữ trần bằng những kind này. Một kind engine
    không in ra là một kind `llm_page.problems()` sẽ loại cả trang vì."""
    from synthgen.llm_page import _rooted, kinds

    known = kinds()
    for tag, kind in T.kind_by_tag().items():
        assert kind in known or _rooted(kind, known), (
            f"<{tag}> gán kind {kind!r}, thứ không có trong từ vựng engine")


def test_the_zone_measurer_reads_the_table_rather_than_keeping_its_own():
    """Bản chép trong chuỗi JS là bản đã lệch một lần rồi."""
    from page import ZONE_REGIONS_JS

    line = next(l for l in ZONE_REGIONS_JS.splitlines() if "const BY_TAG" in l)
    for tag, label in T.region_by_tag().items():
        assert f'"{tag}": "{label}"' in line, f"<{tag}> không tới được phép đo"
    # Và không có thẻ nào NGOÀI bảng lọt vào.
    in_js = set(re.findall(r'"([a-z0-9]+)":', line))
    assert in_js == set(T.region_by_tag())


def test_the_repairer_reads_the_same_table():
    from synthgen.repair import BY_TAG

    assert BY_TAG == T.kind_by_tag()


def test_a_tag_that_declares_a_region_is_not_also_measured_elsewhere():
    """Hai phép đo cùng nhả một vùng cho một khối là đếm hai lần. `<table>`
    là ca đã xảy ra: `CELL_REGIONS_JS` gộp các ô thành một vùng `Table`, nên
    một `data-region="Table"` nữa chồng lên chính nó."""
    doubled = set(T.region_by_tag().values()) & set(T.MEASURED_ELSEWHERE)
    assert not doubled, f"vừa khai bằng thẻ vừa đo ở nơi khác: {sorted(doubled)}"


def test_the_zone_measurer_also_skips_hand_declared_regions_measured_elsewhere():
    """Bảng `test_a_tag_that_declares_a_region_is_not_also_measured_elsewhere`
    ở trên khoá nhánh SUY TỪ THẺ (`region_by_tag()` không có `Table`/`Image`/
    `Stamp`) -- nhưng model có thể khai `data-region="Table"` THẲNG lên chính
    phần tử một phép đo riêng đã đo (`<table data-region="Table">`), và nhánh
    `[data-region]` của `ZONE_REGIONS_JS` từng không tra `MEASURED_ELSEWHERE`
    trước khi thêm vùng -- đo được trên `data/pilot16/records/export_invoice/
    llm_export_invoice_0003.json`: bốn vùng `Table` thay vì hai. Test này khoá
    đúng CHỖ SỬA (chuỗi JS có tra bảng), test Playwright thật trong
    `tests/test_draw_llm_table_dedup.py` khoá KẾT QUẢ (số vùng đúng sau khi
    dàn trang thật)."""
    from page import ZONE_REGIONS_JS

    line = next(l for l in ZONE_REGIONS_JS.splitlines()
               if "const MEASURED_ELSEWHERE" in l)
    for label in T.MEASURED_ELSEWHERE:
        assert f'"{label}"' in line, f"{label} không tới được vòng lọc"
    # Và không có nhãn nào NGOÀI bảng lọt vào -- một danh sách chép tay ở
    # đây sẽ lệch khỏi `MEASURED_ELSEWHERE` đúng cái bệnh file này chữa.
    in_js = set(re.findall(r'"([A-Za-z][A-Za-z-]*)"', line))
    assert in_js == set(T.MEASURED_ELSEWHERE)
    # Vòng lặp `[data-region]` phải THẬT SỰ tra biến này trước khi thêm vùng
    # -- khai biến mà không dùng là vá cho có, không phải vá cho đúng.
    assert "MEASURED_ELSEWHERE.includes(el.dataset.region)" in ZONE_REGIONS_JS


def test_the_prompt_gets_the_real_label_table_not_a_hand_written_one():
    """Mục 14 của `page.md` từng liệt kê tay mười lăm nhãn, một trong số ấy
    (`TOC`) không tồn tại và sáu nhãn thật thì không được nhắc. Model nghe
    theo lời dặn ấy thì bị chính cổng gác của kho loại trang."""
    from agent.compose_page import REGION_SLOT, region_table, system_prompt
    from synthgen.llm_page import REGIONS

    table = region_table()
    for label in REGIONS:
        assert f"| {label} |" in table, f"{label} không có trong bảng đưa model"
    assert "| TOC |" not in table

    whole = system_prompt()
    assert REGION_SLOT not in whole, "chỗ dán còn nguyên; bảng không tới model"
    assert "| Page-Footer |" in whole


def test_a_prompt_that_lost_its_slot_raises_rather_than_going_out_short():
    """Một `replace` không khớp là một prompt thiếu mất danh sách nhãn, và
    trang model viết sau đó sai ở chỗ không ai ngờ."""
    import agent.compose_page as C
    from agent.client import LLMError

    was = C.prompt
    C.prompt = lambda name: "một lời dặn không có chỗ dán nào"
    try:
        try:
            C.system_prompt()
        except LLMError as error:
            assert "chỗ dán" in str(error)
        else:
            raise AssertionError("prompt thiếu chỗ dán mà không ai kêu")
    finally:
        C.prompt = was


def test_every_hand_written_label_set_in_the_repo_names_real_labels():
    """Ba tập nhãn khác vẫn được viết tay, mỗi tập trả lời một câu khác --
    "cắt trang được ở đây không" (`ATOMIC`), "nhãn nào là mực phủ" (`WASH`).
    Chúng không gộp được vào `tags.py` vì chúng không nói về THẺ. Nhưng một
    cái tên gõ sai trong chúng thì im lặng y hệt: nhãn ấy đơn giản không bao
    giờ khớp, và trang bị cắt sai chỗ suốt cả bộ dữ liệu."""
    from synthgen.draw_llm import ATOMIC, WASH

    assert not (ATOMIC - DOCSYNTH_LABELS)
    assert not (set(WASH) - DOCSYNTH_LABELS)


# ---------------------------------------------------------------- zoned()
#
# Trục VÙNG của bảng, trước đây chỉ có một nơi đọc: nhánh suy-từ-thẻ trong
# `ZONE_REGIONS_JS`. Nhánh ấy là NGƯỜI DỰNG THỨ HAI của vùng -- một cái hộp
# ra từ đó không có `data-region` nào trong markup để mà truy ngược.
#
# `repair.zoned()` đưa phép suy ấy về thành một phép SỬA HTML. Đo trên 40 tờ
# model viết: 521 vùng trước, 521 vùng sau, cùng nhãn cùng hộp -- nhưng
# `from` đổi từ `{declared: 299, tag: 222}` thành `{declared: 521}`.

ZONED_CASES = (
    ("thẻ ngữ nghĩa trần được khai",
     '<ul><li>a</li></ul>', 1, 'data-region="List-Group"'),
    ("nhãn đã có ở tổ tiên thì không khai lại",
     '<div data-region="List-Group"><ul><li>a</li></ul></div>', 0, None),
    ("nhãn KHÁC thì vẫn khai",
     '<figure><figcaption>x</figcaption></figure>', 2, 'data-region="Caption"'),
    ("thẻ tự khai thì để yên",
     '<p data-region="Title">x</p>', 0, 'data-region="Title"'),
    ("thẻ rỗng không đẩy ngăn xếp",
     '<div><p>a</p><br><p>b</p></div>', 2, None),
    ("bảng KHÔNG bị khai -- CELL_REGIONS_JS đã đo",
     '<table><tr><td>x</td></tr></table>', 0, None),
    ("thuộc tính cũ giữ nguyên",
     '<ul class="k" id="z"><li>a</li></ul>', 1, 'class="k" id="z"'),
)


def test_the_zoner_declares_what_the_tag_branch_used_to_infer():
    from synthgen.repair import zoned

    for name, html, want_n, want_sub in ZONED_CASES:
        out, count = zoned(html)
        assert count == want_n, f"{name}: mong {want_n} chỗ, được {count} -- {out}"
        if want_sub:
            assert want_sub in out, f"{name}: thiếu {want_sub!r} trong {out!r}"


def test_the_zoner_reads_the_same_table():
    """Bản chép thứ hai của bảng thẻ->vùng là đúng cái `tags.py` sinh ra để
    xoá. `zoned()` phải đọc bảng, không giữ danh sách riêng."""
    from synthgen.repair import REGION_BY_TAG

    assert REGION_BY_TAG == T.region_by_tag()


def test_the_zoner_never_writes_a_label_measured_elsewhere():
    """`Table`/`Image`/`Stamp` có phép đo riêng. Viết `data-region` cho chúng
    ở đây là dựng vùng thứ hai chồng lên vùng ấy -- đúng lỗi bốn vùng `Table`
    thay vì hai, đo được trên `llm_export_invoice_0003`."""
    written = set(T.region_by_tag().values())
    assert not (written & set(T.MEASURED_ELSEWHERE))
