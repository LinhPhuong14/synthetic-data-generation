"""`kie.schema` phải tả đúng những trường `kie.pairs` thật sự có.

Lỗi được canh ở đây im lặng một cách đặc biệt khó chịu: bản ghi trông đầy đủ
-- `pairs` 34 mục, `coverage` 1.0, mọi cặp `in_batch: True` -- mà
`schema.properties` là `{}`. Không có ngoại lệ nào ném ra, không có dòng log
nào, và thứ đem đi hỏi một VLM là một object không thuộc tính.

Nguyên do là hai người dựng một luật. `pipeline/kie.py` dựng schema từ
`pair_entities()` -- nhãn in KỀ giá trị. `synthgen/draw_llm.py` rồi thay
`kie.pairs` bằng tập của đường khai (`data-path` model viết), một tập khác
hẳn, mà không dựng lại schema.

Đo trên `data/pilot18` (50 bản ghi, 16 loại giấy) trước khi vá: đúng 2 tài
liệu hỏng, và cả hai vì cùng một lẽ -- chúng không in nhãn kề giá trị ở đâu
cả.

    form_checklist_0005    ô tích, không nhãn kề    34 cặp  ->  0 thuộc tính
    dispatch_letter_0002   đoạn văn, không nhãn kề  26 cặp  ->  0 thuộc tính

Mười bốn loại giấy còn lại có nhãn kề nên không lộ ra -- đó là vì sao lỗi này
sống được qua nhiều lượt chạy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KS = pytest.importorskip("synthgen.kie_schema",
                         reason="cần pyyaml để nạp phôi")

PILOT = REPO_ROOT / "data" / "pilot18" / "records"
REAL = [
    ("form_checklist", "llm_form_checklist_0005"),
    ("dispatch_letter", "llm_dispatch_letter_0002"),
]


def _names(node, out: set) -> set:
    """Mọi tên trường trong schema, kể cả tên nằm trong mảng hay object lồng."""
    if isinstance(node, dict):
        for name, child in (node.get("properties") or {}).items():
            out.add(name)
            _names(child, out)
        if node.get("items"):
            _names(node["items"], out)
    return out


def _a_record_with_no_captions() -> dict:
    """Hình của một checklist: mọi cặp đến từ đường KHAI, không nhãn nào kề.

    Dựng bằng tay chứ không đọc đĩa, nên bài kiểm này vẫn chạy trong một bản
    sao kho không có `data/` -- thư mục ấy có bộ hàng chục GB và không phải
    máy nào cũng giữ."""
    return {
        "filename": "llm_form_checklist_0005",
        "entity_annotations": [
            {"entity_index": 0, "field_name": "checklist_color",
             "kind": "survey.checklist", "text": "Màu sắc đạt yêu cầu"},
            {"entity_index": 1, "field_name": "checklist_smell",
             "kind": "survey.checklist", "text": "Mùi đạt yêu cầu"},
        ],
        "kie": {
            "pairs": [
                {"field": "checklist_color", "path": "checklist.color",
                 "role": "survey.checklist", "source": "declared",
                 "value_text": "Đạt", "key_text": "",
                 "description": "Trạng thái tích của dòng kiểm màu sắc."},
                {"field": "checklist_smell", "path": "checklist.smell",
                 "role": "survey.checklist", "source": "declared",
                 "value_text": "Không đạt", "key_text": "",
                 "description": "Trạng thái tích của dòng kiểm mùi."},
            ],
            # Đúng hình đã thấy trên đĩa: schema rỗng nằm cạnh coverage đầy.
            "schema": {"type": "object", "properties": {}},
            "coverage": {"pairs": 2, "coverage": 1.0},
        },
    }


def test_a_record_whose_pairs_have_no_captions_still_gets_properties():
    """Bài kiểm chính: `pairs` không rỗng thì `properties` không được rỗng."""
    record = _a_record_with_no_captions()
    assert (record["kie"]["schema"]["properties"] == {}), "hình trước khi vá"
    schema, value = KS.build(record)
    assert schema["properties"], "pairs không rỗng mà schema không có thuộc tính nào"
    assert set(value) == set(schema["properties"])


def test_every_flat_pair_reaches_the_schema():
    """Không trường nào được rơi im lặng -- kể cả khi nó đi vào một mảng."""
    record = _a_record_with_no_captions()
    schema, _value = KS.build(record)
    reached = _names(schema, set())
    for pair in record["kie"]["pairs"]:
        assert pair["field"] in reached, pair["field"]


@pytest.mark.parametrize("kind,stem", REAL)
def test_the_two_real_pilot18_records_are_no_longer_empty(kind, stem):
    """Chính hai file đã lộ ra lỗi. Bỏ qua khi máy không giữ `data/pilot18`."""
    path = PILOT / kind / f"{stem}.json"
    if not path.exists():
        pytest.skip(f"máy này không có {path.relative_to(REPO_ROOT)}")
    record = json.loads(path.read_text(encoding="utf-8"))
    pairs = (record.get("kie") or {}).get("pairs") or []
    assert pairs, "file mẫu phải có cặp, nếu không bài kiểm không nói gì"
    schema, value = KS.build(record)
    assert schema["properties"], f"{stem}: pairs={len(pairs)} mà properties rỗng"
    assert value

    # …và mọi trường PHẲNG phải tới được schema.
    #
    # "Phẳng" loại ra ba thứ, và cả ba là THIẾT KẾ chứ không phải mất mát:
    # ô bảng đã vào mảng dòng hàng; khối ký / điều khoản / bảng hỏi
    # (`source` trong `GROUPED`) đã có mảng riêng qua `kie_full.group_lists`;
    # và một `path` mang CHỈ SỐ đã gom thành mảng theo gốc của nó. Đo trên
    # `dispatch_letter_0002`: tám trường `section_1_head` … `section_4_body`
    # đi vào mảng `section` với lá `head`/`body` -- đúng điều
    # `docs/kie-schema-v2.md` đặt ra để một tờ bốn mục thôi đẻ ra tám thuộc
    # tính đánh số.
    from synthgen.kie_full import GROUPED  # noqa: PLC0415

    reached = _names(schema, set())
    want = {str(p.get("field")) for p in pairs
            if p.get("field")
            and p.get("source") not in GROUPED
            and not (p.get("column") and p.get("row") is not None)
            and not KS._INDEX.search(str(p.get("path") or ""))
            and str(p.get("field")) not in KS.STRUCTURE
            and str(p.get("value_text", "")).strip()}
    assert want <= reached, sorted(want - reached)


def test_the_rebuild_uses_the_same_builder_derive_uses():
    """Một luật, MỘT người dựng. `synthgen/draw_llm.py` phải gọi đúng hàm
    `synthgen/derive.py` gọi -- một phép dựng schema thứ hai ở đó là cách
    chắc chắn để hai bản ghi của cùng một lượt chạy nói hai giọng."""
    source = (REPO_ROOT / "synthgen" / "draw_llm.py").read_text(encoding="utf-8")
    assert "from synthgen.kie_schema import build as build_schema" in source
    assert 'record["kie"]["schema"] = schema' in source
