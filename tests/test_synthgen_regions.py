"""Mọi chữ `markup.py` in ra phải nằm trong một vùng ĐÃ KHAI.

Trước `_blocks.yaml::region`, mười khối không khai `data-region` gì cả, và
vùng của chúng được `pipeline/record.py` dựng lại bằng cách gom từ theo ngưỡng
khe. Đo trên 25 tờ: **49,6% số run** đi đường ấy. Bộ gom cắt ở chỗ hở ngang,
mà máng giữa nhãn và giá trị thường rộng hơn ngưỡng -- nên "Tổng cộng tiền
thanh toán" và "1.569.081.240 đ" ra hai vùng dù chúng là một dòng. Không gì
báo: nhãn vẫn có, hộp vẫn có, chỉ là sai chỗ.

Sau khi mọi khối khai: **0%**. File này giữ con số ấy.

## Vì sao test đọc CHUỖI chứ không mở trình duyệt

`markup.markup()` là hàm thuần -- vào `Doc`, ra `str` -- nên quan hệ "run này
nằm trong vùng nào" đọc được bằng một bộ phân tích HTML, không cần Chromium.
CI của kho chạy được với `pytest` + `pyyaml`, và một test đòi Playwright là
một test không ai chạy trước khi commit.

Hộp thì vẫn phải đo bằng trình duyệt. Test này không nói gì về hộp.
"""

from __future__ import annotations

import random
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.record import DOCSYNTH_LABELS                    # noqa: E402
from synthgen import content as C                              # noqa: E402
from synthgen import design as D                               # noqa: E402
from synthgen import markup as M                               # noqa: E402

# Thẻ rỗng: đẩy vào ngăn xếp mà không ai lấy ra thì mọi phép hỏi tổ tiên sau
# đó đều sai. Cùng cái bẫy `llm_page.outside_sheet` đã ghi lại.
VOID = frozenset({"br", "img", "hr", "input", "meta", "link", "source", "col"})

# Chữ trong bảng KHÔNG cần `data-region`: `generators/html/page.py::
# CELL_REGIONS_JS` dựng vùng `Table` cho mỗi `<table>` từ chính các ô. Khai
# thêm ở đây là vùng thứ hai chồng lên vùng ấy.
COVERED_BY_OTHER_MEASURE = frozenset({"table"})


class _Orphans(HTMLParser):
    """Những run có `data-kind` mà không tổ tiên nào khai vùng."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.orphans: list[str] = []
        self._pending: str | None = None
        self._text: list[str] = []
        # Độ sâu ngăn xếp lúc run mở ra. Run đóng khi ngăn xếp tụt về lại
        # mức ấy -- không phải ở thẻ đóng ĐẦU TIÊN gặp sau đó. Bản đầu so
        # `len(self.stack)` với một property trả về chính `len(self.stack)`,
        # tức luôn đúng: nó cho ra kết quả đúng trên mọi trang kho này sinh
        # (run có nhãn chỉ chứa chữ, theo luật số một của `llm_page.py`) và
        # sai ngay khi một run bọc thẻ con. Một phép so với chính nó là một
        # phép so không ai đọc lại được.
        self._opened_at = 0

    def _sheltered(self) -> bool:
        return any(region or tag in COVERED_BY_OTHER_MEASURE
                   for tag, region in self.stack)

    def handle_starttag(self, tag: str, attrs) -> None:
        got = dict(attrs)
        if tag in VOID:
            return
        self.stack.append((tag, "data-region" in got))
        if "data-kind" in got and self._pending is None:
            # Chính run này khai vùng cũng tính -- `.wtext` và số dưới mã vạch
            # khai thẳng trên `<span>`, không qua một `<div>` khối nào.
            self._pending = "" if self._sheltered() else str(got["data-kind"])
            self._text = []
            self._opened_at = len(self.stack) - 1

    def handle_data(self, data: str) -> None:
        if self._pending is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        # Run đóng lại: chỉ tính là mồ côi khi nó THẬT SỰ có chữ. Một span
        # rỗng không có hộp, nên nó không có nhãn để mà sai.
        if self._pending is not None and len(self.stack) - 1 <= self._opened_at:
            if self._pending and "".join(self._text).strip():
                self.orphans.append(f"{self._pending}: "
                                    f"{''.join(self._text).strip()[:40]!r}")
            self._pending = None
        while self.stack:
            top, _ = self.stack.pop()
            if top == tag:
                break


def _orphans(html: str) -> list[str]:
    parser = _Orphans()
    parser.feed(html)
    parser.close()
    return parser.orphans


def _pages(count: int = 25) -> list[tuple[int, str]]:
    """`(seed, html)` cho `count` tờ đầu tiên dựng được."""
    out = []
    for seed in range(count * 3):
        if len(out) >= count:
            break
        rng = random.Random(seed)
        design = D.draw(rng, seed)
        doc = C.build(design, rng, rows_wanted=8)
        out.append((seed, M.markup(doc, [(0, 8)])))
    return out


# Bảy ca chứng minh bộ phân tích KHÔNG rỗng. Một test "0 mồ côi" xanh vì bộ
# đếm luôn trả 0 thì tệ hơn không có test: nó nói dối theo chiều yên tâm.
PARSER_CASES = (
    ("run trần trong .blk",
     '<div class="sheet"><div class="blk">'
     '<span data-kind="a.b">xin chao</span></div></div>', 1),
    ("trong vùng đã khai",
     '<div class="sheet"><div data-region="Text">'
     '<span data-kind="a.b">xin chao</span></div></div>', 0),
    ("tự khai trên chính span",
     '<div class="sheet">'
     '<span data-kind="a.b" data-region="Text">xin chao</span></div>', 0),
    ("trong bảng (đo riêng)",
     '<div class="sheet"><table><tr><td>'
     '<span data-kind="a.b">x</span></td></tr></table></div>', 0),
    ("span rỗng thì không tính",
     '<div class="sheet"><div class="blk">'
     '<span data-kind="a.b"></span></div></div>', 0),
    ("hai run, một mồ côi",
     '<div class="sheet"><div data-region="Text">'
     '<span data-kind="a.b">co</span></div><div class="blk">'
     '<span data-kind="c.d">khong</span></div></div>', 1),
    ("thẻ rỗng không đẩy ngăn xếp",
     '<div class="sheet"><div class="blk"><span data-kind="a.b">x</span>'
     '<br><span data-kind="c.d">y</span></div></div>', 2),
)


def test_the_orphan_reader_actually_reads():
    for name, html, want in PARSER_CASES:
        got = _orphans(html)
        assert len(got) == want, f"{name}: mong {want}, được {len(got)} -- {got}"


def test_every_region_label_is_one_the_record_knows():
    """Một nhãn gõ sai trong YAML không ném -- nó đi thẳng vào
    `layout_annotations`, và `validate` mới từ chối, cách đó vài nghìn trang."""
    labels = {D.block_region(name)
              for name in (D._blocks_yaml().get("region") or {})}
    unknown = {label for label in labels if label} - DOCSYNTH_LABELS
    assert not unknown, f"nhãn không có trong bộ nhãn: {sorted(unknown)}"


def test_no_run_falls_outside_every_declared_region():
    """Con số này là 0. Nó từng là 49,6%.

    Hỏng ở đây nghĩa là một khối mới ra đời mà chưa có tên trong
    `_blocks.yaml::region`, hoặc một builder có nhánh trả về thứ hai mà lần
    sửa chỉ vá nhánh đầu -- đo được đúng hai lần khi dựng mục ấy (`_fields`
    một cột, `_photo` không có `.blk` bọc)."""
    loose: dict[int, list[str]] = {}
    for seed, html in _pages():
        found = _orphans(html)
        if found:
            loose[seed] = found
    assert not loose, (
        "run không nằm trong vùng nào đã khai -- thêm khối vào "
        f"`rulebase/synthgen/_blocks.yaml::region`:\n" +
        "\n".join(f"  seed {s}: {', '.join(v[:4])}" for s, v in
                  list(loose.items())[:6]))


def test_the_table_is_not_declared_twice():
    """`table`/`summary` KHÔNG được có tên trong bảng: `CELL_REGIONS_JS` đã
    dựng vùng `Table` cho chúng từ các ô, và một `data-region` nữa là đếm hai
    lần -- đo được trên `llm_export_invoice_0003` (bốn vùng `Table` thay vì
    hai)."""
    declared = D._blocks_yaml().get("region") or {}
    for name in ("table", "summary"):
        assert name not in declared, (
            f"{name!r} có phép đo riêng; khai `data-region` là đếm hai lần")


# ----------------------------------------------------- run ngoài mọi vùng
#
# Cổng đo cái này TRƯỚC khi dàn trang, nên nó chỉ có chuỗi. Đo chéo với phép
# đo thật trên DOM đã dàn (40 tờ model viết): 27 tờ (68%) khớp chính xác, và
# cả sáu tờ lệch nhiều nhất đều là HTML hỏng mà Chromium tự nắn lại. Lệch
# luôn về phía ĐẾM DƯ -- cổng nghiêm hơn thực tế, không lỏng hơn.

ORPHAN_CASES = (
    ("run trần là mồ côi",
     '<div class="sheet"><span data-kind="a.b">x</span></div>', 1, 1),
    ("trong vùng đã khai thì không",
     '<div class="sheet"><div data-region="Text">'
     '<span data-kind="a.b">x</span></div></div>', 0, 1),
    ("tự khai trên chính span",
     '<div class="sheet"><span data-kind="a.b" data-region="Text">x</span></div>',
     0, 1),
    ("trong bảng -- CELL_REGIONS_JS đã đo",
     '<div class="sheet"><table><tr><td>'
     '<span data-kind="a.b">x</span></td></tr></table></div>', 0, 1),
    ("trong [data-graphic] -- GRAPHIC_RECTS_JS đã đo",
     '<div class="sheet"><div data-graphic="seal">'
     '<span data-kind="a.b">x</span></div></div>', 0, 1),
    ("span rỗng không có hộp nên không tính",
     '<div class="sheet"><span data-kind="a.b"></span></div>', 0, 0),
    ("ra khỏi vùng thì lại mồ côi",
     '<div class="sheet"><div data-region="Text">'
     '<span data-kind="a.b">x</span></div>'
     '<span data-kind="c.d">y</span></div>', 1, 2),
    ("nháy đơn cũng phải đọc được",
     "<div class='sheet'><div data-region='Text'>"
     "<span data-kind='a.b'>x</span></div></div>", 0, 1),
    ("ngoài .sheet thì không đếm -- outside_sheet() báo riêng",
     '<div><span data-kind="a.b">x</span></div>', 0, 0),
)


def test_the_orphan_measure_reads_what_it_claims():
    from synthgen.llm_page import orphan_share

    for name, html, want_loose, want_total in ORPHAN_CASES:
        loose, total = orphan_share(html)
        assert (loose, total) == (want_loose, want_total), (
            f"{name}: mong {want_loose}/{want_total}, được {loose}/{total}")


def test_markup_pages_have_no_orphan_runs_by_the_gate_measure():
    """Hai phép đo, một sự thật. `test_no_run_falls_outside_every_declared_
    region` đọc bằng `HTMLParser`, cổng đọc bằng bộ quét regex -- và chúng
    phải nói cùng một câu về cùng một trang, nếu không thì một trong hai đang
    gác một thứ không ai sửa được."""
    from synthgen.llm_page import orphan_share

    for seed, html in _pages(count=8):
        loose, total = orphan_share(html)
        assert loose == 0, f"seed {seed}: {loose}/{total} run ngoài mọi vùng"
        assert total > 0, f"seed {seed}: không đếm được run nào"


def test_a_missing_ceiling_gates_nothing():
    """Thiếu cấu hình phải nghĩa là KHÔNG GÁC THÊM, không phải loại sạch. Một
    mặc định chặt ở đây là một lượt chạy mất trắng vì một tệp YAML gõ sai."""
    assert D.gate_ceiling("khong_co_nguong_nay", 1.0) == 1.0
    # Và ngưỡng đang khai phải là một tỉ lệ đọc được.
    ceiling = D.gate_ceiling("orphan_share", 1.0)
    assert 0.0 < ceiling <= 1.0, f"ngưỡng vô nghĩa: {ceiling}"
