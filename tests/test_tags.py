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


# ------------------------------------------------------------------ zones()
#
# Model lẫn HAI TRỤC: `masthead` là một `data-kind` CÓ THẬT của engine -- tên
# một khối chữ -- chứ không phải tên một vùng bố cục. Đo trên
# `data/23-09-llm-b` (10 tờ, gpt-4.1-mini): 3 tờ trượt cổng chỉ vì ba cái tên
# `Masthead`, `masthead`, `Note`.


def test_the_alias_table_only_names_real_labels():
    """Một bí danh trỏ tới nhãn không có thật là một phép chữa đổi lỗi này
    lấy lỗi khác -- và lỗi mới thì im lặng hơn, vì cổng vẫn loại tờ ấy nhưng
    giờ với một cái tên không ai gõ ra."""
    from synthgen.design import region_alias
    from synthgen.llm_page import REGIONS

    unreal = {k: v for k, v in region_alias().items() if v not in REGIONS}
    assert not unreal, f"bí danh trỏ tới nhãn không có thật: {unreal}"


def test_a_misnamed_region_is_straightened_and_a_strange_one_is_not():
    from synthgen.repair import zones

    for html, want in (
        ('<div data-region="Masthead">x</div>', 'data-region="Page-Header"'),
        ("<div data-region='masthead'>x</div>", "data-region='Page-Header'"),
        ('<div data-region="Note">x</div>', 'data-region="Text"'),
        # Nhãn ĐÚNG viết sai hoa thường cũng được nắn: `Page-header` và
        # `Page-Header` là cùng một vùng với mắt người, hai thứ với cổng gác.
        ('<div data-region="page-header">x</div>', 'data-region="Page-Header"'),
    ):
        out, fixed = zones(html)
        assert fixed == 1 and want in out, f"{html} -> {out}"

    # Nhãn đã đúng thì không đụng; nhãn thật sự lạ thì KHÔNG đoán.
    for html in ('<div data-region="Text">x</div>',
                 '<div data-region="Hoàn toàn lạ">x</div>'):
        assert zones(html) == (html, 0)


def test_every_gate_ceiling_falls_back_to_not_gating():
    """Thiếu khoá trong YAML phải nghĩa là KHÔNG LOẠI, không phải loại sạch --
    một cổng không có gì để so mà vẫn loại là cổng hỏng câm."""
    from synthgen.design import gate_ceiling

    assert gate_ceiling("khong_bao_gio_co_khoa_nay", 1.0) == 1.0
    for name in ("orphan_share", "plan_drop_share"):
        assert 0.0 < gate_ceiling(name, 1.0) <= 1.0


def test_stripping_the_plural_s_never_renames_a_real_label():
    """`repair.zones()` bỏ chữ `s` cuối khi tra TRƯỢT, để `Signatures` về
    `Signature` rồi về `Text`.

    Bất biến không phải "không nhãn nào kết thúc bằng s" -- `Table-Of-Contents`
    có, và nó vô hại vì nhãn thật tra TRÚNG trước khi tới nhánh bỏ `s`. Bất
    biến thật là: phép bỏ `s` không bao giờ biến một nhãn ĐÚNG thành một nhãn
    ĐÚNG KHÁC. Nếu có, một trang khai đúng sẽ bị nắn sang vùng khác và vẫn vẽ
    ra bình thường -- hỏng câm."""
    from synthgen.design import region_alias
    from synthgen.llm_page import REGIONS
    from synthgen.repair import zones

    table = {k.lower(): v for k, v in region_alias().items()}
    table.update({r.lower(): r for r in REGIONS})
    for label in REGIONS:
        out, fixed = zones(f'<div data-region="{label}">x</div>')
        assert fixed == 0, f"{label} bị nắn thành {out}"


def test_a_plural_region_name_is_straightened_too():
    from synthgen.repair import zones

    for html, want in (
        ('<div data-region="Signatures">x</div>', 'data-region="Text"'),
        ('<div data-region="Notes">x</div>', 'data-region="Text"'),
        ('<div data-region="Headers">x</div>', 'data-region="Page-Header"'),
    ):
        out, fixed = zones(html)
        assert fixed == 1 and want in out, f"{html} -> {out}"


# ---------------------------------------------------------------- unnest()
#
# `CELL_RECTS_JS` đo `span.firstElementChild || span`: một thẻ lồng trong run
# có nhãn LẶNG LẼ trở thành cái hộp được ghi. `dress()` lo ca thẻ trang trí là
# con DUY NHẤT; model viết hình khác -- một span đánh số đứng TRƯỚC chữ. Đo
# trên `data/23-09-llm-f`: 5 trên 12 tờ trượt vì đúng hình ấy.
#
# Hai ca `<strong>`/`<b>` dưới đây đo trên `data/pilot16`: cả 9 tờ trượt vì
# "thẻ lồng" của lượt ấy đều là một nhãn ngắn bọc `<strong>`/`<b>` đứng
# TRƯỚC phần chữ còn lại -- hình `_SPAN_TAG` (chỉ khớp `<span>`) không thấy.

UNNEST_CASES = (
    ("span trần trước chữ",
     '<span data-kind="note"><span class="n">1.</span> Nội dung</span>', 1,
     '<span data-kind="note">1. Nội dung</span>'),
    ("nhãn bọc <strong> đứng trước chữ (data/pilot16, idx 8)",
     '<span data-kind="note"><strong>Bên giao thầu:</strong> Công ty CP '
     'Thiết bị Y khoa Minh Đức</span>', 1,
     '<span data-kind="note">Bên giao thầu: Công ty CP Thiết bị Y khoa '
     'Minh Đức</span>'),
    ("nhãn bọc <b> đứng trước chữ (data/pilot16, idx 17)",
     '<span data-kind="note"><b>Điều 1.</b> Bảo hiểm không chi trả</span>',
     1, '<span data-kind="note">Điều 1. Bảo hiểm không chi trả</span>'),
    ("chữ thuần không đụng",
     '<span data-kind="a.b">chữ thuần</span>', 0, None),
    ("span CÓ nhãn lồng thì để yên -- hai trường, không đoán",
     '<span data-kind="a.b"><span data-kind="a.c">x</span></span>', 0, None),
    ("ngoài run có nhãn thì không phải việc của hàm này",
     '<span class="x">ngoài</span>', 0, None),
    ("lồng hai tầng bóc cả hai",
     '<span data-kind="k"><span><span class="y">hai tầng</span></span></span>',
     2, '<span data-kind="k">hai tầng</span>'),
)


def test_a_bare_span_inside_a_labelled_run_is_unwrapped():
    from synthgen.repair import unnest

    for name, html, want_n, want_out in UNNEST_CASES:
        out, count = unnest(html)
        assert count == want_n, f"{name}: {count} chỗ, mong {want_n} -- {out}"
        if want_out:
            assert out == want_out, f"{name}: {out}"


def test_unwrapping_never_loses_the_text():
    """Bóc thẻ, GIỮ CHỮ. Một phép chữa làm mất chữ là một phép chữa đổi lỗi
    nhãn lấy lỗi nội dung, và lỗi nội dung thì nhìn ảnh mới thấy."""
    import re as _re
    from synthgen.repair import unnest

    for _name, html, _n, _out in UNNEST_CASES:
        before = _re.sub(r"<[^>]+>", "", html)
        after = _re.sub(r"<[^>]+>", "", unnest(html)[0])
        assert before == after, f"{before!r} -> {after!r}"
