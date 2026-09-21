"""`synthgen/draw_llm.py::Drawer.draw()` phải LƯU LẠI `kie.pairs` đầy đủ vào
`records/*.json`, không chỉ dùng để vẽ `visualize_kie/` rồi bỏ.

## Vì sao file này tồn tại

Người dùng hỏi trực tiếp trên `data/rerun-unwrap` (một lô đã sinh, chưa chạy
`derive.py`): "TC1 của Nguyễn Văn Hùng là bao nhiêu, JSON hiện tại có trả lời
được không". Kiểm thì thấy KHÔNG -- `records/llm/
llm_annual_performance_rating_summary_0009.json` lúc đó chỉ có 4 `kie.pairs`
(MST/ĐT/Số hiệu/Ngày), không cặp nào cho bảng, dù `synthgen/kie_full.py::
complete()` chạy tay trên đúng record+HTML ấy ra 153 cặp, bao gồm
`{"field": "tc1_r1", "row": 1, "column_path": ["TC1"], "value_text": "23"}`
khớp thẳng dòng "Nguyễn Văn Hùng".

Nguyên nhân: `Drawer.draw()` (`synthgen/draw_llm.py`) đã gọi `kie_complete()`
để vẽ `visualize_kie/` (thêm ở Phase 8, `docs/ke-hoach-refactor-engine.md`)
nhưng chỉ dùng kết quả trong bộ nhớ cho MỘT tấm ảnh rồi bỏ -- `records/
*.json` ghi ra đĩa vẫn giữ `kie.pairs` NGHÈO của `pipeline/record.py::
build()` cho tới khi `derive.py` chạy (một bước RIÊNG, cuối cả lô, có thể
không bao giờ chạy nếu lô bị ngắt hoặc gọi `draw_llm` đơn).

## Không cần trình duyệt

Test dưới đây không gọi `Drawer.draw()` (cần Playwright) -- nó khoá lại đúng
HỢP ĐỒNG `Drawer.draw()` phải giữ: record đọc từ đĩa (dạng `pipeline/
record.py::build()` sinh ra, `kie.pairs` nghèo) + HTML thật -> sau khi áp
đúng logic `Drawer.draw()` giờ làm (`record.setdefault("kie", {})["pairs"]
= kie_complete(record, html)[0]`), `kie.pairs` phải giàu lên và có đúng cặp
TC1 kia. Nếu `data/rerun-unwrap` không có ở máy này thì bỏ qua, không giả
lập -- đây là hồi quy trên CHÍNH ca đã đo, giống `tests/
test_kie_full_dedup.py`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synthgen.kie_full import complete

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = (REPO_ROOT / "data/rerun-unwrap/records/llm/"
              "llm_annual_performance_rating_summary_0009.json")
HTML_PATH = (REPO_ROOT / "data/rerun-unwrap/html/llm/"
            "llm_annual_performance_rating_summary_0009.html")


def _persist_like_drawer(record: dict, html: str) -> dict:
    """Đúng logic `Drawer.draw()` giờ làm, tách ra để test không cần
    Playwright -- xem docstring module."""
    full_pairs, counts = complete(record, html)
    record.setdefault("kie", {})["pairs"] = full_pairs
    if counts:
        record["kie"]["coverage"] = counts
    return record


@pytest.mark.skipif(not (RECORD_PATH.is_file() and HTML_PATH.is_file()),
                    reason="data/rerun-unwrap không có ở máy này")
def test_the_sparse_pre_derive_record_is_missing_the_table_pairs():
    """Xác nhận lại đúng cái đã đo được: TRƯỚC khi áp logic mới, record trên
    đĩa nghèo hơn thực tế nhiều -- không có bất kỳ cặp nào cho bảng."""
    record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    before = record.get("kie", {}).get("pairs") or []
    assert len(before) == 4
    assert all(p.get("source") != "table" for p in before)


@pytest.mark.skipif(not (RECORD_PATH.is_file() and HTML_PATH.is_file()),
                    reason="data/rerun-unwrap không có ở máy này")
def test_persisting_like_drawer_recovers_tc1_for_nguyen_van_hung():
    record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    html = HTML_PATH.read_text(encoding="utf-8")
    fixed = _persist_like_drawer(record, html)

    pairs = fixed["kie"]["pairs"]
    assert len(pairs) > 100                                # 153 lúc đo

    hung_row = [e for e in fixed["entity_annotations"]
               if e.get("text") == "Nguyễn Văn Hùng"]
    assert len(hung_row) == 1
    row_index = hung_row[0].get("entity_index")

    tc1 = [p for p in pairs if p.get("column_path") == ["TC1"]
          and p.get("row") == 1]
    assert len(tc1) == 1
    assert tc1[0]["value_text"] == "23"
    # Cặp TC1 phải nằm CÙNG HÀNG với entity "Nguyễn Văn Hùng" -- entity_index
    # của giá trị TC1 phải lớn hơn entity của tên (cùng row, in ra sau tên
    # trong thứ tự DOM), không phải trùng số ngẫu nhiên "23" ở hàng khác.
    assert tc1[0]["value_entity_index"] > row_index
