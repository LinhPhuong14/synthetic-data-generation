"""Failure taxonomy for the track-3 (LLM-writes-HTML) per-page gate.

    from pipeline.failures import CODES, classify

`agent/compose_page.py::one()` rejects a page on the first non-empty `found`
list, assembled from several free-text-string producers:
`synthgen/llm_page.py::problems()`, and `agent/compose_page.py::
plan_problems()`, `sheet_plan_problems()`, and `plan_conformance_problems()`.
A separate, later producer -- `agent/compose_page.py::
_reconcile_sheet_count()`, run in `run()` AFTER real A4 pagination, not
inside `one()` -- can also flip an already-`ok` page back to rejected and
append its own reason string; see that function's docstring for why this
one check needed to move after rendering instead of joining the others
above. That is real, working signal -- `_why_tally()` already groups it by
shape for reporting -- but it answers "generation failed" with a sentence,
not a code a downstream script can `groupby`. `classify()` maps each reason
string to one of the twelve codes from `docs/ke-hoach-refactor-engine.md`
Phase 2 (mục 16 of the original design note) WITHOUT changing what any of
those functions return -- every existing caller keeps working unchanged.

## Scope

Only the per-page generation gate. `synthgen/check.py::check_record` is a
separate, post-render, whole-corpus audit tool with its own Vietnamese
`kind` labels (`'hộp từ diện tích 0'`, `'thành tiền != số lượng x đơn giá'`,
...) already grouped by exact string match in a `Counter` -- migrating those
into this enum too is out of scope for Phase 2 and would blur two different
tools with two different audiences (a generation-time gate vs. a
corpus-time audit). See the mapping table in the module docstring below for
where each of `check.py`'s labels WOULD land if that migration ever happens.

## Two codes have no producer yet

`TEXT_TABLE_CONFUSION` and `KIE_FALSE_POSITIVE` are in the taxonomy because
the design doc calls for them, but nothing in the current gate can tell
"text wrongly boxed as Table" from "a genuine table" (needs the DOM
structure, not just the flat reason strings `classify()` sees), and nothing
flags a KIE pair that resolved to the WRONG entity but still looks
well-formed. `DIVERSITY_COLLAPSE` is corpus-level by definition and will
never come from a per-page reason string. `classify()` returns them for
`UNCLASSIFIED` never `None` -- see `SCHEMA_VIOLATION`'s role as the
catch-all below.
"""

from __future__ import annotations

import re

MISSING_BOX = "MISSING_BOX"
WRONG_REGION_TYPE = "WRONG_REGION_TYPE"
TEXT_TABLE_CONFUSION = "TEXT_TABLE_CONFUSION"        # chưa có producer
MISSING_DATA_PATH = "MISSING_DATA_PATH"
DUPLICATE_DATA_PATH = "DUPLICATE_DATA_PATH"
INVALID_TABLE_CELL = "INVALID_TABLE_CELL"
KIE_FALSE_POSITIVE = "KIE_FALSE_POSITIVE"            # chưa có producer
KIE_FALSE_NEGATIVE = "KIE_FALSE_NEGATIVE"
PLAN_VIOLATION = "PLAN_VIOLATION"
DENSITY_VIOLATION = "DENSITY_VIOLATION"
SCHEMA_VIOLATION = "SCHEMA_VIOLATION"                # catch-all
DIVERSITY_COLLAPSE = "DIVERSITY_COLLAPSE"            # chỉ ở tầng corpus

CODES = frozenset({
    MISSING_BOX, WRONG_REGION_TYPE, TEXT_TABLE_CONFUSION, MISSING_DATA_PATH,
    DUPLICATE_DATA_PATH, INVALID_TABLE_CELL, KIE_FALSE_POSITIVE,
    KIE_FALSE_NEGATIVE, PLAN_VIOLATION, DENSITY_VIOLATION, SCHEMA_VIOLATION,
    DIVERSITY_COLLAPSE,
})

# THỨ TỰ CÓ NGHĨA: mẫu đầu khớp trước. `data-path` phải đi trước `data-kind`
# vì "không đúng dạng" xuất hiện trong cả hai câu -- kiểm tra hẹp trước, rộng
# sau, cùng nguyên tắc `_rooted` dùng khi tra `data-kind`.
_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    # -- problems() -------------------------------------------------------
    (re.compile(r"ô bảng thiếu `data-cell`"), INVALID_TABLE_CELL),
    (re.compile(r"data-path=.*không đúng dạng"), SCHEMA_VIOLATION),
    (re.compile(r"data-path=.*giá trị khác nhau"), DUPLICATE_DATA_PATH),
    (re.compile(r"`data-region="), WRONG_REGION_TYPE),
    (re.compile(r"có thẻ lồng bên trong"), MISSING_BOX),
    (re.compile(r"nằm NGOÀI mọi <div"), MISSING_BOX),
    (re.compile(r"không có <div class=\"sheet\">"), SCHEMA_VIOLATION),
    (re.compile(r"`data-kind=.*không có trong từ vựng"), SCHEMA_VIOLATION),
    (re.compile(r"không có run nào mang `data-kind`"), SCHEMA_VIOLATION),
    (re.compile(r"mà không run nào in ra"), KIE_FALSE_NEGATIVE),
    (re.compile(r"in ra \d+ lần; mỗi giá trị"), DUPLICATE_DATA_PATH),
    (re.compile(r"trang rỗng"), SCHEMA_VIOLATION),
    (re.compile(r"<script|<iframe|<object|<embed|sự kiện|tài nguyên ngoài|"
               r"@import"), SCHEMA_VIOLATION),
    (re.compile(r"HTML không đọc được"), SCHEMA_VIOLATION),
    # -- plan_problems() ---------------------------------------------------
    (re.compile(r"`field_plan` đặt tên"), PLAN_VIOLATION),
    (re.compile(r"trang bỏ \d+/\d+ kind đã hứa"), PLAN_VIOLATION),
    (re.compile(r"chữ ký mà `plan\.signers`"), PLAN_VIOLATION),
    # -- sheet_plan_problems() ----------------------------------------------
    (re.compile(r"`sheet_plan` trống"), DENSITY_VIOLATION),
    (re.compile(r"`sheet_plan` chỉ khai"), DENSITY_VIOLATION),
    (re.compile(r"khai trong `sheet_plan` mà không mục nào"), DENSITY_VIOLATION),
    # -- _reconcile_sheet_count() (đo SAU khi dàn trang thật) --------------
    (re.compile(r"nhưng dàn trang thật chỉ ra \d+ tờ"), DENSITY_VIOLATION),
)


def classify(reason: str) -> str:
    """Một câu lý do (từ `problems`/`plan_problems`/`sheet_plan_problems`)
    -> một trong `CODES`. Không khớp mẫu nào thì `SCHEMA_VIOLATION` --
    catch-all có chủ đích, không phải lỗ hổng: một câu lý do mới xuất hiện
    (gate vừa thêm luật) nên VẪN có một mã, để `tally()` dưới không âm thầm
    bỏ sót nó, và người đọc báo cáo sẽ thấy `SCHEMA_VIOLATION` phình lên --
    dấu hiệu `_PATTERNS` cần một dòng mới, không phải một lỗi che giấu."""
    text = str(reason or "")
    for pattern, code in _PATTERNS:
        if pattern.search(text):
            return code
    return SCHEMA_VIOLATION


def tally(reasons: list[str]) -> dict[str, int]:
    """Đếm theo mã, cho một lô lý do trượt cổng (`why` của nhiều trang gộp
    lại). Dùng cho Phase 2.4 (thống kê corpus) và cho báo cáo `run()`."""
    counts: dict[str, int] = {}
    for reason in reasons:
        code = classify(reason)
        counts[code] = counts.get(code, 0) + 1
    return counts


__all__ = ["CODES", "DENSITY_VIOLATION", "DIVERSITY_COLLAPSE",
          "DUPLICATE_DATA_PATH", "INVALID_TABLE_CELL", "KIE_FALSE_NEGATIVE",
          "KIE_FALSE_POSITIVE", "MISSING_BOX", "MISSING_DATA_PATH",
          "PLAN_VIOLATION", "SCHEMA_VIOLATION", "TEXT_TABLE_CONFUSION",
          "WRONG_REGION_TYPE", "classify", "tally"]
