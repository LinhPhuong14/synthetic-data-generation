"""`synthgen/kie_full.py::_dedup_by_value` -- một `value_entity_index`, một cặp.

Nothing below renders an image or starts a model -- `_dedup_by_value` works
off a plain list of pair dicts, so this runs in the dependency-free CI job,
same as `test_kie.py` and `test_record.py`.

## Vì sao file này tồn tại

Đo trên `data/pilot10` (nơi bug được đo lần đầu, 57/77) và `data/pilot12`
(nơi 147/766 được đo): cả hai số đo lịch sử ấy hoá ra đã được sửa từ trước
bởi "Chữa 3" trong `complete()` -- nhưng chỉ sửa xung đột giữa đường KHAI
(`data-path`) và NHÃN (adjacency). Chạy lại `complete()` trên chính hai bộ
đó với HTML thật (không phải `record["html"]`, đã bị rút gọn thành text
thuần) lộ ra 4/1337 thực thể vẫn bị hai trường nhận -- luôn cùng một hình:
dòng TỔNG CỘNG của bảng (`table`) trùng với nhãn "TỔNG CỘNG:" đứng ngay
trước nó (`label`), hoặc bị `extra_pairs` khớp lại lần nữa (`pair`) với một
chú thích khác trên trang. `_dedup_by_value` là bản vá, chạy SAU `extra_pairs`
nên không bỏ sót cặp tới muộn.

Test dưới đây khoá lại đúng ba điều đã học được khi đi tìm bug này:

1. `table` phải thắng `label`/`pair` khi cùng trỏ một ô (không phải xoá đường
   nào, mà XẾP HẠNG rồi giữ đường có căn cứ cấu trúc hơn).
2. Một `key_entity_index` bị dùng lại ở nhiều cặp KHÔNG phải là trùng -- một
   tiêu đề cột là khoá chung của nhiều dòng, đúng cấu trúc bảng. Chỉ
   `value_entity_index` trùng mới là hai trường nhận một ô mực.
3. Trên dữ liệu thật, sau khi vá: 0 thực thể trùng.
"""

from __future__ import annotations

import glob
import json
import os

import pytest

from synthgen import kie_full


def a_pair(value_index, source, key_text="", **kw):
    out = {"value_entity_index": value_index, "source": source,
           "key_text": key_text, "value_text": kw.pop("value_text", "x")}
    out.update(kw)
    return out


# --------------------------------------------------------- _dedup_by_value


def test_table_beats_label_when_both_claim_the_same_value():
    pairs = [
        a_pair(7, "table", key_text="SỐ TIỀN (ĐỒNG)", value_text="110.000.000"),
        a_pair(7, "label", key_text="TỔNG CỘNG", value_text="110.000.000"),
    ]
    kept = kie_full._dedup_by_value(pairs)
    assert len(kept) == 1
    assert kept[0]["source"] == "table"
    assert "TỔNG CỘNG" in kept[0]["printed_header"]


def test_table_beats_pair_from_extra_pairs_too():
    """`pair`/`family` đến từ `extra_pairs`, chạy SAU cả `label`."""
    pairs = [
        a_pair(55, "table", key_text="", value_text="500.000.000"),
        a_pair(55, "pair", key_text="Quyền lợi bệnh hiểm nghèo",
              value_text="500.000.000"),
    ]
    kept = kie_full._dedup_by_value(pairs)
    assert len(kept) == 1
    assert kept[0]["source"] == "table"
    assert kept[0]["printed_header"] == ["Quyền lợi bệnh hiểm nghèo"]


def test_declared_beats_everything():
    pairs = [
        a_pair(3, "implied", value_text="0312345678"),
        a_pair(3, "label", key_text="Mã số thuế", value_text="0312345678"),
        a_pair(3, "table", key_text="MST", value_text="0312345678"),
        a_pair(3, "declared", key_text="", value_text="0312345678"),
    ]
    kept = kie_full._dedup_by_value(pairs)
    assert len(kept) == 1
    assert kept[0]["source"] == "declared"
    assert sorted(kept[0]["printed_header"]) == ["MST", "Mã số thuế"]


def test_unrelated_pairs_are_left_alone():
    pairs = [a_pair(1, "table", value_text="a"), a_pair(2, "label", value_text="b")]
    kept = kie_full._dedup_by_value(pairs)
    assert kept == pairs


def test_a_shared_column_header_is_not_a_duplicate():
    """Một tiêu đề cột là KHOÁ của nhiều dòng -- lặp `key_entity_index` là
    đúng cấu trúc bảng, không phải hai trường nhận một ô mực."""
    pairs = [
        {"key_entity_index": 25, "value_entity_index": 28, "source": "table",
         "key_text": "HẠNG MỤC", "value_text": "Lương tháng"},
        {"key_entity_index": 25, "value_entity_index": 31, "source": "table",
         "key_text": "HẠNG MỤC", "value_text": "Thu nhập phụ"},
    ]
    kept = kie_full._dedup_by_value(pairs)
    assert kept == pairs                # cả hai cặp đều giữ nguyên


def test_a_pair_with_no_value_entity_index_is_never_touched():
    pairs = [{"source": "family", "key_text": "x", "value_text": "y"}]
    assert kie_full._dedup_by_value(pairs) == pairs


# ------------------------------------------------------- hồi quy trên dữ liệu thật


def _html_for(record_path: str, dataset: str) -> str:
    doc, name = record_path.split("/")[-2:]
    stem = name.rsplit(".", 1)[0]
    return f"data/{dataset}/html/{doc}/{stem}.html"


PILOT_RECORDS = [
    (dataset, path)
    for dataset in ("pilot10", "pilot12")
    for path in sorted(glob.glob(f"data/{dataset}/records/*/*.json"))
    if not path.endswith(("_p2.json", "_p3.json"))
    and os.path.exists(_html_for(path, dataset))
]


@pytest.mark.skipif(not PILOT_RECORDS, reason="data/pilot10 hoặc data/pilot12 không có ở máy này")
def test_no_real_entity_is_claimed_by_two_fields():
    """Số đo đã dẫn tới `_dedup_by_value`: 4/1337 trước khi vá, 0/1337 sau.

    Chạy trên chính hai bộ đã đo bug lần đầu, bằng HTML thật (`data/*/html`,
    có `<span data-kind>`) -- không phải `record["html"]`, vốn đã bị rút gọn
    thành văn bản thuần không còn thẻ nào để `declared_pairs` đọc."""
    total_entities = 0
    total_duplicated = 0
    for dataset, path in PILOT_RECORDS:
        record = json.load(open(path, encoding="utf-8"))
        html = open(_html_for(path, dataset), encoding="utf-8").read()
        pairs, _ = kie_full.complete(record, html)
        seen: dict[int, int] = {}
        for pair in pairs:
            index = pair.get("value_entity_index")
            if isinstance(index, int):
                seen[index] = seen.get(index, 0) + 1
        total_entities += len(record.get("entity_annotations") or [])
        total_duplicated += sum(1 for n in seen.values() if n > 1)
    assert total_entities > 0
    assert total_duplicated == 0, (
        f"{total_duplicated} thực thể vẫn bị hai trường nhận trên "
        f"{total_entities} thực thể của {len(PILOT_RECORDS)} tài liệu thật")
