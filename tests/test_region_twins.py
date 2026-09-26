"""Hai vùng một hộp, và nhãn trường mang nhãn đầu mục -- hai lỗi đo được trên
pilot18, trên những tờ ĐÃ QUA CỔNG, nên chúng đi thẳng vào bộ huấn luyện.

**Hai vùng một hộp.** `ZONE_REGIONS_JS` đo hộp MỰC của từng `[data-region]`,
nên `<section data-region="Section-Header"><h3 data-region="Section-Header">`
cho hai vùng cùng một hộp, từng số một; `<footer data-region="Page-Footer">
<p data-region="Text">` cho `Page-Footer` VÀ `Text` cho cùng một dòng. Đo
trên pilot16-18 (118 tài liệu): 10 cặp, 5 cùng nhãn, 5 khác nhãn --
`llm_insurance_moto_certificate_0020` có 3 trên 20 vùng là bản sao. Luật khung
của `_unwrap` cố ý bỏ qua hộp trùng khít, nên không gì bắt chúng.

**Nhãn trường mang nhãn đầu mục.** Model đặt tên nhãn bằng kind của giá trị
cộng `.label`, nên "Họ và tên:" thành `parties.title.label` và tra tiền tố ra
`Section-Header`; giá trị "Bùi Thanh Hải" là `store.name` -> `Page-Header`.
`regions_from_words` gom vùng theo nhãn của từ, nên mỗi cái thành một vùng đầu
mục/đầu trang riêng giữa khối thông tin (`llm_authorisation_letter_0000`, hai
lần). Đo trên pilot16-18: 11 nhãn trường và 19 giá trị như thế.

Mọi test ở đây gọi thẳng `pipeline.record`, không mở trình duyệt: cả hai luật
nằm ở bước dựng vùng từ hộp đã đo, không ở phép đo.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import record as R  # noqa: E402


def box(kind: str, text: str, field: int, x1: float, y1: float, x2: float, y2: float) -> dict:
    """Một từ như `page.py::CELL_RECTS_JS` trả về."""
    return {"kind": kind, "text": text, "field": field,
            "quad": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}


def zone(label: str, x1: float, y1: float, x2: float, y2: float,
         from_: str = "declared") -> dict:
    """Một khối tự khai vùng như `render.py::zones_from_rects` trả về."""
    return {"label": label, "from": from_,
            "quad": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}


def run(kind: str, text: str, field: int) -> dict:
    """Một run như `page.py`'s `fields` array."""
    return {"field": field, "kind": kind, "text": text}


# --------------------------------------------------------- nhãn trường (lỗi B)


def test_a_field_caption_does_not_inherit_the_heading_label_of_what_it_names():
    """`store.name.label` là "Tên đơn vị:", không phải dòng tên đơn vị trên đầu
    thư; `parties.title.label` là "Họ và tên:", không phải tiêu đề khối."""
    assert R.layout_class_for("parties.title.label") == "Text"
    assert R.layout_class_for("store.name.label") == "Text"
    assert R.layout_class_for("title.label") == "Text"
    # Cái nó đặt tên theo thì vẫn đứng đúng chỗ cũ.
    assert R.layout_class_for("parties.title") == "Section-Header"
    assert R.layout_class_for("store.name") == "Page-Header"
    assert R.layout_class_for("title") == "Title"


def test_a_lettered_heading_prefix_is_still_a_heading():
    """`subhead.label` là chữ cái "A." của đầu mục trong `sheets/insurance.py`
    và `sheets/form.py` -- khai thẳng trong bảng, không thừa kế qua tiền tố,
    nên luật nhãn trường không đụng tới nó. Tách nó ra khỏi đầu mục là chẻ
    một đầu mục của đường luật làm đôi."""
    assert R.layout_class_for("subhead.label") == "Section-Header"


def test_a_value_with_a_printed_caption_is_content_not_a_page_header():
    """Cùng một `store.name`, hai chỗ đứng: tên đơn vị trên đầu thư không nhãn
    -> `Page-Header`; "Bùi Thanh Hải" in sau "Họ và tên:" -> `Text`."""
    words = R.words_from_boxes([
        box("store.name", "CÔNG", 0, 100, 40, 160, 60),
        box("store.name", "TY", 0, 165, 40, 200, 60),
        box("store.name.label", "Họ", 1, 100, 300, 130, 320),
        box("store.name.label", "và", 1, 135, 300, 160, 320),
        box("store.name.label", "tên:", 1, 165, 300, 200, 320),
        box("store.name", "Bùi", 2, 230, 300, 270, 320),
        box("store.name", "Thanh", 2, 275, 300, 330, 320),
        box("store.name", "Hải", 2, 335, 300, 370, 320),
    ])
    entities = R.entities_from_words(words, [
        run("store.name", "CÔNG TY", 0),
        run("store.name.label", "Họ và tên:", 1),
        run("store.name", "Bùi Thanh Hải", 2),
    ])
    by_text = {e["text"]: e for e in entities}
    assert by_text["CÔNG TY"]["layout_class"] == "Page-Header"
    assert by_text["Họ và tên:"]["layout_class"] == "Text"
    assert by_text["Bùi Thanh Hải"]["layout_class"] == "Text"
    assert (by_text["Bùi Thanh Hải"]["key_entity_index"]
            == by_text["Họ và tên:"]["entity_index"]), "phải ghép được với nhãn"
    # Từ đổi theo, vì vùng gom theo nhãn của TỪ.
    assert {w["layout_class"] for w in words if w["entity_index"] == 2} == {"Text"}

    regions = R.regions_from_words(words, page_size=(1000, 1000))
    labels = [r["layout_class"] for r in regions]
    assert labels.count("Page-Header") == 1, "chỉ dòng đầu thư là đầu trang"
    assert "Section-Header" not in labels
    assert labels.count("Text") == 1, "nhãn và giá trị là MỘT dòng, không phải hai vùng"


def test_a_value_without_a_printed_caption_keeps_its_kind_label():
    """Luật chỉ chạm giá trị CÓ nhãn in kèm. Một `store.name` đứng một mình
    -- dòng tên đơn vị -- vẫn là đầu trang như trước."""
    words = R.words_from_boxes([
        box("store.name", "CÔNG", 0, 100, 40, 160, 60),
        box("meta.value", "Số:", 1, 100, 300, 130, 320),
        box("store.name", "ABC", 2, 100, 500, 160, 520),
    ])
    entities = R.entities_from_words(words, [
        run("store.name", "CÔNG", 0), run("meta.value", "Số:", 1),
        run("store.name", "ABC", 2)])
    assert [e["layout_class"] for e in entities] == ["Page-Header", "Text", "Page-Header"]


# ------------------------------------------------------ hai vùng một hộp (lỗi A)


def test_two_declared_zones_on_one_ink_box_make_one_region():
    """`<section data-region="Section-Header"><h3 data-region="Section-Header">`
    -- ba đầu mục của `llm_insurance_moto_certificate_0020`, mỗi cái hai vùng."""
    words = R.words_from_boxes([
        box("section", "MÔ", 0, 100, 100, 150, 130),
        box("section", "TẢ", 0, 155, 100, 200, 130),
    ])
    zones = [zone("Section-Header", 100, 100, 200, 130),
             zone("Section-Header", 100, 100, 200, 130)]
    regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["Section-Header"]
    assert regions[0]["twins_dropped"] == [
        {"layout_class": "Section-Header", "text": "MÔ TẢ", "from": "declared"}]
    assert [w["layout_region_index"] for w in words] == [0, 0]


def test_a_footer_declared_twice_keeps_page_footer_and_says_so():
    """`<footer data-region="Page-Footer"><p data-region="Text">…</p></footer>`:
    `<footer>` LÀ chân trang (`pipeline/tags.py`, `_blocks.yaml`), còn `<p
    data-region="Text">` chỉ nói "trong này có chữ". Giữ cái cụ thể, và KÊU:
    hai nhãn cho một phần tử là model khai chồng."""
    words = R.words_from_boxes([
        box("note", "Giấy", 0, 100, 900, 150, 920),
        box("note", "chứng", 0, 155, 900, 210, 920),
    ])
    zones = [zone("Page-Footer", 100, 900, 210, 920),     # cái ngoài, thứ tự DOM
             zone("Text", 100, 900, 210, 920)]
    with pytest.warns(UserWarning, match="hai vùng một hộp"):
        regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["Page-Footer"]
    assert regions[0]["twins_dropped"][0]["layout_class"] == "Text"
    assert [w["layout_region_index"] for w in words] == [0, 0]


def test_the_specific_label_wins_whichever_element_is_outer():
    """`<div data-region="Text"><ol data-region="List-Group">` (pilot17
    `llm_form_dense_0006`): lần này `Text` là cái NGOÀI, và vẫn thua."""
    words = R.words_from_boxes([box("clause.body", "Đã", 0, 100, 400, 130, 420)])
    zones = [zone("Text", 100, 400, 130, 420), zone("List-Group", 100, 400, 130, 420)]
    with pytest.warns(UserWarning):
        regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["List-Group"]


def test_a_declared_label_beats_a_tag_derived_one_on_the_same_box():
    """Cùng luật khung của `_unwrap`: model nói rõ thì nghe model, kể cả khi
    model nói `Text` và thẻ nói đầu mục."""
    words = R.words_from_boxes([box("note", "Ghi", 0, 100, 400, 130, 420)])
    zones = [zone("Section-Header", 100, 400, 130, 420, from_="tag"),
             zone("Text", 100, 400, 130, 420, from_="declared")]
    with pytest.warns(UserWarning):
        regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["Text"]
    assert regions[0]["from"] == "declared"


def test_two_specific_labels_let_the_words_decide():
    """`Title` đấu `Section-Header`, cả hai khai tay: đếm từ theo nhãn suy từ
    `data-kind` của chính chúng -- `title` -> `Title`."""
    words = R.words_from_boxes([
        box("title", "GIẤY", 0, 100, 100, 160, 130),
        box("title", "ỦY", 0, 165, 100, 200, 130),
    ])
    zones = [zone("Section-Header", 100, 100, 200, 130), zone("Title", 100, 100, 200, 130)]
    with pytest.warns(UserWarning):
        regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["Title"]


def test_a_measured_table_beats_a_declared_block_on_the_same_box():
    """`<div data-region="Complex-Block">` bọc đúng một `<table>`: cái bảng đo
    từ ô thật (`CELL_REGIONS_JS`) đứng trên lời khai, vì bảng là thứ
    `MEASURED_ELSEWHERE` -- lời khai không được đổi nó thành khối phức."""
    words = R.words_from_boxes([
        box("cell", "STT", 0, 100, 100, 150, 130),
        box("cell", "Tên", 1, 200, 100, 250, 130),
    ])
    cells = [{"kind": "cell", "text": "STT", "table": 0, "row": 0, "col": 0,
              "head": True, "colspan": 1, "rowspan": 1,
              "quad": [[100, 100], [150, 100], [150, 130], [100, 130]]},
             {"kind": "cell", "text": "Tên", "table": 0, "row": 0, "col": 1,
              "head": True, "colspan": 1, "rowspan": 1,
              "quad": [[200, 100], [250, 100], [250, 130], [200, 130]]}]
    zones = [zone("Complex-Block", 100, 100, 250, 130)]
    with pytest.warns(UserWarning):
        regions = R.regions_from_words(words, cells=cells, zones=zones,
                                       page_size=(1000, 1000))
    assert [r["layout_class"] for r in regions] == ["Table"]
    assert regions[0]["twins_dropped"][0]["layout_class"] == "Complex-Block"
    assert [w["layout_region_index"] for w in words] == [0, 0]


def test_collapsing_a_twin_renumbers_the_regions_after_it_and_their_words():
    """Gọi thẳng `_unwrap`: cái bị bỏ đứng TRƯỚC vùng khác, nên mọi con trỏ
    sau nó lùi một bậc -- và từ của cái bị bỏ trỏ sang cái ở lại, không phải
    sang một vùng con tình cờ nằm trong hộp."""
    def region(index, label, x1, y1, x2, y2, text="", from_="declared"):
        one = R._region_entry(index, label, text, (x1, y1, x2, y2),
                              "dom_element_perimeter", None)
        one["bbox"] = [x1, y1, x2, y2]
        one["polygon"] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]
        one["from"] = from_
        return one

    regions = [region(0, "Page-Footer", 0, 900, 500, 940, "chân trang"),
               region(1, "Text", 0, 900, 500, 940, "chân trang"),
               region(2, "Text", 0, 100, 500, 200, "đoạn đầu")]
    words = [{"text": "chân", "bbox": [10, 910, 90, 930], "layout_region_index": 0,
              "field_path": "note"},
             {"text": "trang", "bbox": [100, 910, 190, 930], "layout_region_index": 1,
              "field_path": "note"},
             {"text": "đoạn", "bbox": [10, 110, 90, 190], "layout_region_index": 2,
              "field_path": "note"}]
    with pytest.warns(UserWarning):
        kept = R._unwrap(regions, words)
    assert [r["layout_class"] for r in kept] == ["Page-Footer", "Text"]
    assert [r["region_index"] for r in kept] == [0, 1]
    assert [w["layout_region_index"] for w in words] == [0, 0, 1]
    assert "twins_dropped" not in kept[1], "vùng không dính gì thì không mang khoá ấy"


def test_two_distinct_boxes_are_not_twins():
    """Trùng khít mới gộp. Hai hộp lệch nhau một pixel -- không cái nào bao
    trọn cái kia, nên luật khung cũng không đụng -- là hai vùng, như trước."""
    words = R.words_from_boxes([box("section", "MÔ", 0, 100, 100, 150, 130)])
    zones = [zone("Section-Header", 100, 100, 150, 130),
             zone("Section-Header", 101, 100, 151, 130)]
    regions = R.regions_from_words(words, zones=zones, page_size=(1000, 1000))
    assert len(regions) == 2
    assert not any("twins_dropped" in r for r in regions)


# ------------------------------------------------------------ bộ kiểm trên đĩa


def _check_regions():
    spec = importlib.util.spec_from_file_location(
        "check_regions", REPO_ROOT / "tools" / "check_regions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_audit_sees_both_patterns_in_a_record():
    """`tools/check_regions.py` đọc bản ghi đã xuất (hệ 1000), không đọc code:
    nó phải bắt được đúng hai mẫu của pilot18 trên một bản ghi dựng tay."""
    audit = _check_regions()
    record = {"layout_annotations": [
        {"region_index": 0, "page_number": 1, "layout_class": "Section-Header",
         "text": "MÔ TẢ BẢO HIỂM", "bbox": [72, 606, 255, 628]},
        {"region_index": 1, "page_number": 1, "layout_class": "Section-Header",
         "text": "MÔ TẢ BẢO HIỂM", "bbox": [72, 606, 255, 628]},
        {"region_index": 2, "page_number": 2, "layout_class": "Page-Footer",
         "text": "Giấy chứng nhận có hiệu lực", "bbox": [176, 724, 823, 739]},
        {"region_index": 3, "page_number": 2, "layout_class": "Text",
         "text": "Giấy chứng nhận có hiệu lực", "bbox": [176, 724, 823, 739]},
        # cùng hộp, KHÁC tờ: không phải trùng
        {"region_index": 4, "page_number": 3, "layout_class": "Text",
         "text": "Giấy chứng nhận có hiệu lực", "bbox": [176, 724, 823, 739]},
        {"region_index": 5, "page_number": 1, "layout_class": "Section-Header",
         "text": "Họ và tên:", "bbox": [86, 247, 169, 265]},
        {"region_index": 6, "page_number": 1, "layout_class": "Section-Header",
         "text": "I. THÔNG TIN NGƯỜI ỦY QUYỀN", "bbox": [86, 223, 365, 241]},
        {"region_index": 7, "page_number": 1, "layout_class": "Text",
         "text": "Sinh ngày:", "bbox": [86, 268, 172, 285]},
    ]}
    twins = audit.twins(record)
    assert [(t["page_number"], t["labels"]) for t in twins] == [
        (1, ["Section-Header", "Section-Header"]), (2, ["Page-Footer", "Text"])]
    assert [t["conflict"] for t in twins] == [False, True]
    suspects = audit.caption_suspects(record)
    assert [s["text"] for s in suspects] == ["Họ và tên:"]
