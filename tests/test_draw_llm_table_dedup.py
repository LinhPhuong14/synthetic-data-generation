"""`pipeline/record.py::regions_from_words` không được đếm MỘT cái bảng
thành HAI vùng `Table`.

## Vì sao file này tồn tại

Người dùng chỉ ra một ca thật, đã sinh trong `data/pilot16`:
`records/export_invoice/llm_export_invoice_0003.json` (và cặp trang hai
`_p2.json`) có BỐN vùng mang `layout_class == "Table"` -- hai trên mỗi tờ --
trong khi HTML gốc chỉ có ĐÚNG MỘT `<table>` và ĐÚNG MỘT
`data-region="Table"` (`grep -c 'data-region="Table"'` ra 1 cho cả hai file
`.html`, vì `Drawer.draw()` ghi cùng một chuỗi HTML nguồn cho mọi trang).

Đo trực tiếp bốn vùng ấy (`llm_export_invoice_0003.json`):

    region 0: page_number=1, không có khoá "from", bbox [146,764,1744,2486]
    region 5: page_number=1, from="declared",       bbox [187,782,1727,2466]
    region 6: page_number=2, không có khoá "from",  bbox [146,56,1744,1120]
    region 10: page_number=2, from="declared",       bbox [290,140,1727,1101]

Vùng 0/6 đến từ bước 1 của `regions_from_words` (hợp các ô `<td>` đo bằng
`CELL_REGIONS_JS`, nhóm theo `cell["table"]`). Vùng 5/10 đến từ bước 1b
(vùng model tự khai `data-region`, đo bằng `ZONE_REGIONS_JS`) -- HTML thật
viết `<table data-region="Table">` (thuộc tính nằm THẲNG trên thẻ
`<table>`, xem `data/pilot16/html/export_invoice/llm_export_invoice_0003.
html` dòng 59), nên vòng lặp `[data-region]` của `ZONE_REGIONS_JS` đo lại
đúng cái bảng ấy lần thứ hai.

`ZONE_REGIONS_JS` (`generators/html/page.py`) đã tự né trường hợp này cho
nhánh SUY TỪ THẺ -- `<table>` không có trong `BY_TAG`, đúng lời chú thích ở
đó: "CELL_REGIONS_JS đã đo bảng theo từng ô, thêm một vùng Table nữa ở đây
là đếm hai lần" -- nhưng lời né ấy không áp cho nhánh `data-region` viết tay:
vòng lặp `[data-region]` thêm vùng ngay khi thấy thuộc tính, không tra xem
nhãn ấy có phải một trong ba nhãn đã có phép đo riêng
(`pipeline/tags.py::MEASURED_ELSEWHERE` -- Table/Image/Stamp) hay không.

## Sửa ở đâu

**Sửa tận gốc, ở `generators/html/page.py::ZONE_REGIONS_JS`** (bản đầu vá ở
`pipeline/record.py` -- giữ hộp từng `<table>` rồi so chồng lấp để bỏ vùng
khai tay trùng -- đã bị thay bằng cách này khi người dùng yêu cầu "gộp hai
bộ đo làm một thay vì vá downstream"): vòng lặp `[data-region]` giờ tra
`MEASURED_ELSEWHERE` (nhúng vào JS qua `pipeline/tags.py::
measured_elsewhere_js()`, cùng cách `BY_TAG` đã nhúng cho nhánh suy từ thẻ)
và bỏ qua hẳn phần tử mang nhãn nằm trong đó -- vùng `Table`/`Image`/`Stamp`
khai tay không bao giờ được TẠO RA nữa, thay vì tạo ra rồi lọc lại ở tầng
sau. Một bảng, ba nơi đọc (`region_by_tag_js` cho nhánh suy từ thẻ,
`measured_elsewhere_js` giờ cho nhánh khai tay, và `agent/compose_page.py`
cho lời dặn model) -- xem `tests/test_tags.py::
test_the_zone_measurer_also_skips_hand_declared_regions_measured_elsewhere`
cho test khoá đúng chỗ sửa này (không cần trình duyệt).

## Không tái tạo chuyện gán sai trang

Giả thuyết ban đầu còn ngờ có một vùng bị gán NHẦM trang (chữ của tờ hai lại
mang `page_number: 1`). Đo lại bằng `pages` trong chính record thì không
thấy: bbox của vùng `page_number=1` (`y` tới 2486) nằm gọn trong chiều cao
tờ một (`height: 2673`), và bbox của vùng `page_number=2` (`y` từ 56) là chữ
KHÁC hẳn (bắt đầu "Hồ tiêu đen" dòng 25, không phải chữ đã có ở tờ một).
Không có bằng chứng cho nhánh gán-sai-trang -- test này chỉ khoá lại đúng
cái đã đo: đếm vùng trùng, không sửa cái chưa thấy.

## Cần trình duyệt thật

`ZONE_REGIONS_JS`/`CELL_REGIONS_JS` đọc DOM thật, nên cần Chromium để chạy
đúng như model sẽ thấy. Test dưới gọi thẳng `synthgen.draw_llm.draw_one()`
trên HTML thật của `data/pilot16`, giống cách `tests/test_table_bbox.py`
xác nhận `CELL_REGIONS_JS` bằng pixel thật chứ không đoán DOM. Bỏ qua
(không giả lập) khi thiếu Playwright/Chromium hoặc khi `data/pilot16`
không có ở máy này -- lô có thể vẫn đang sinh ở nơi khác, và test không
được coi thư mục liệt kê được là đầy đủ."""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

HTML_PATH = (REPO_ROOT / "data/pilot16/html/export_invoice/"
            "llm_export_invoice_0003.html")
DECLARED_PATH = (REPO_ROOT / "data/pilot16/declared/"
                 "llm_export_invoice_0003.json")

pytestmark = pytest.mark.slow


@functools.lru_cache(maxsize=1)
def _browser_ready() -> bool:
    """Xem `tests/test_table_bbox.py::_browser_ready` -- phải THẬT SỰ mở
    trình duyệt lên mới biết được, `find_chromium() is not None` báo sai."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    from page import find_chromium

    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch(executable_path=find_chromium()).close()
    except Exception:                        # noqa: BLE001
        return False
    return True


def _draw() -> dict:
    from playwright.sync_api import sync_playwright

    from synthgen.draw_llm import draw_one

    declared = (json.loads(DECLARED_PATH.read_text(encoding="utf-8"))
               if DECLARED_PATH.is_file() else {})
    html = HTML_PATH.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--font-render-hinting=none"])
        try:
            page = browser.new_page(device_scale_factor=2.0)
            got = draw_one(page, html, "llm_export_invoice_0003", declared)
        finally:
            browser.close()
    assert got is not None
    return got["record"]


@pytest.mark.skipif(not HTML_PATH.is_file(), reason="data/pilot16 không có ở máy này")
@pytest.mark.skipif(not _browser_ready(), reason="không mở được Chromium")
def test_exactly_one_table_per_page_when_the_tag_itself_declares_it():
    """`<table data-region="Table">` phải ra ĐÚNG MỘT vùng `Table` cho mỗi
    tờ nó xuất hiện, không phải hai -- xem docstring module để biết vì sao
    hai vùng từng xuất hiện."""
    record = _draw()
    tables = [a for a in record["layout_annotations"]
             if a.get("layout_class") == "Table"]
    by_page: dict[int, list[dict]] = {}
    for region in tables:
        by_page.setdefault(int(region.get("page_number", 1) or 1), []).append(region)

    assert set(by_page) == {1, 2}                # tài liệu này cắt ra đúng hai tờ
    for page_number, regions in by_page.items():
        assert len(regions) == 1, (
            f"tờ {page_number} có {len(regions)} vùng Table, "
            f"muốn đúng 1: {regions}")

    # Chữ của bảng vẫn phải còn nguyên -- sửa trùng lặp không được ăn mất nội
    # dung: vùng còn lại phải là vùng ĐO ĐƯỢC NHIỀU CHỮ HƠN (hộp theo ô thật),
    # không phải hộp rỗng.
    assert len(by_page[1][0]["text"]) > 500
    assert len(by_page[2][0]["text"]) > 500
    # Hai tờ phải mang chữ KHÁC NHAU -- không phải cùng một khối bị lặp lại
    # (xem phần "Không tái tạo chuyện gán sai trang" ở docstring module).
    assert by_page[1][0]["text"] != by_page[2][0]["text"]
