"""`FieldRecord` -- một hình dạng chung cho entity và pair KIE.

    from pipeline.fields import FieldRecord, registry

`pipeline/record.py::entities_from_words` dựng ra ENTITY (hộp, chữ, vai
key/value); `synthgen/kie_full.py::complete` dựng ra PAIR (trường, đường dẫn,
nguồn). Hai hình dạng khác nhau cho cùng một khái niệm -- một trường ngữ
nghĩa -- và Phase 4 (fingerprint) / Phase 6 (hard negative) của
`docs/ke-hoach-refactor-engine.md` cần đọc MỘT hình dạng, không phải hai.

Đây không phải cơ chế KIE thứ ba. Phase 1 đọc lại `synthgen/kie_full.py`
bằng dữ liệu thật trước khi viết file này (xem `docs/ke-hoach-refactor-engine.md`,
mục 0b và Phase 1) và xác nhận: cơ chế hợp nhất hai đường KIE đã đúng (sau
`_dedup_by_value`), chỉ còn thiếu một VIEW đọc-only phía trên. `FieldRecord`
là view ấy -- nó gọi vào `entity_annotations`/`kie.pairs` đã có, không tự
sinh thêm cặp nào."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Bốn vai. `HARD_NEGATIVE` chưa có bộ sinh nào gán -- không tồn tại cơ chế
# hard-negative nào trong code hôm nay, xác nhận qua audit (không một hit nào
# cho `hard_negative`/`decoy` ngoài `page.md`/`SYSTEM_PROMPT.md`). Khai trước
# để Phase 6 (`docs/ke-hoach-refactor-engine.md`) không phải đổi hình dạng
# này khi cơ chế ấy có mặt.
POSITIVE = "positive"              # một KIE target thật, có mặt trong `kie.pairs`
ORDINARY = "ordinary"              # có hộp, có nhãn lớp, không phải KIE target
LABEL = "label"                    # một run đóng vai CAPTION, không phải giá trị
HARD_NEGATIVE = "hard_negative"    # dành cho Phase 6 -- chưa có ai gán vai này

ROLES = frozenset({POSITIVE, ORDINARY, LABEL, HARD_NEGATIVE})


@dataclass(frozen=True)
class FieldRecord:
    """Một trường ngữ nghĩa, nhìn từ MỘT nơi thay vì rải rác entity/pair.

    `path` là "" khi không có `data-path` -- không phải mọi trường đều có
    (đo trên `data/pilot10`+`data/pilot12` thật: 28% dưới `page.md` cũ, xem
    `synthgen/llm_page.py::path_coverage`). `kind` của một `FieldRecord` dựng
    từ pair lấy nguyên `pair["role"]` -- tên gọi bên `kie_full.py` cho
    `data-kind`, KHÔNG phải cùng nghĩa với `FieldRecord.role` ở đây; hai chữ
    trùng tên tình cờ, `from_pair` đã đổi tên rõ khi chuyển sang hình dạng
    này."""

    path: str
    kind: str
    value: str
    role: str
    source: str = ""                    # "declared"|"table"|"label"|"pair"|"implied"|""
    entity_index: int | None = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"FieldRecord.role không hợp lệ: {self.role!r}")


def from_entity(entity: dict[str, Any]) -> FieldRecord:
    """Một entity của `entities_from_words` -> một `FieldRecord`.

    Entity không mang `data-path` -- `pipeline/record.py::entities_from_words`
    không đọc thuộc tính ấy, chỉ `data-key` (xem `_declared_key`). Đường dẫn
    chỉ xuất hiện ở tầng pair (`from_pair`); dùng `registry()` để có cả hai
    khi cả hai đều tồn tại cho cùng một hộp."""
    role = LABEL if entity.get("field_role") == "key" else ORDINARY
    return FieldRecord(
        path="",
        kind=str(entity.get("kind") or ""),
        value=str(entity.get("text") or ""),
        role=role,
        source=str(entity.get("key_source") or ""),
        entity_index=entity.get("entity_index"),
    )


def from_pair(pair: dict[str, Any]) -> FieldRecord:
    """Một cặp của `synthgen/kie_full.py::complete()` -> một `FieldRecord`.

    Mọi cặp `complete()` trả về LÀ một KIE positive theo định nghĩa: nó chỉ
    sinh cặp cho thực thể nó đã quyết là thuộc một trường, và
    `_dedup_by_value` đã chọn đúng một cặp khi nhiều đường cùng nhận một ô."""
    return FieldRecord(
        path=str(pair.get("path") or ""),
        kind=str(pair.get("role") or ""),
        value=str(pair.get("value_text") or ""),
        role=POSITIVE,
        source=str(pair.get("source") or ""),
        entity_index=pair.get("value_entity_index"),
    )


def registry(entities: list[dict[str, Any]],
            pairs: list[dict[str, Any]]) -> list[FieldRecord]:
    """Toàn bộ trường của một tài liệu, một `FieldRecord` cho mỗi hộp.

    Hộp có cặp KIE thì lấy vai/đường dẫn từ pair (`from_pair` -- đáng tin
    hơn: đã qua `_dedup_by_value`); hộp không có cặp thì giữ vai suy từ
    chính entity của nó (`from_entity` -- `ORDINARY`/`LABEL`). Đây là điểm
    đọc DUY NHẤT Phase 4/Phase 6 nên dùng thay vì tự đi bới
    `entity_annotations` và `kie.pairs` riêng từng nơi."""
    by_index: dict[int, FieldRecord] = {}
    for pair in pairs:
        index = pair.get("value_entity_index")
        if isinstance(index, int):
            by_index[index] = from_pair(pair)
    out: list[FieldRecord] = []
    for entity in entities:
        index = entity.get("entity_index")
        if isinstance(index, int) and index in by_index:
            out.append(by_index[index])
        else:
            out.append(from_entity(entity))
    return out


__all__ = ["FieldRecord", "HARD_NEGATIVE", "LABEL", "ORDINARY", "POSITIVE",
          "ROLES", "from_entity", "from_pair", "registry"]
