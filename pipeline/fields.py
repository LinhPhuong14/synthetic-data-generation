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

# Bốn vai. `HARD_NEGATIVE` giờ có bộ sinh: `synthgen/kie_full.py::
# hard_negative_spans` đọc `data-decoy-for` model tự khai, `from_hard_negative`
# dưới đây đổi sang hình dạng này, `registry()` gọi nó khi được đưa danh sách
# (Phase 6, `docs/ke-hoach-refactor-engine.md`).
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


@dataclass(frozen=True)
class HardNegativeRecord:
    """Sự kiện thô: một span model tự khai là mồi giả (`data-decoy-for`).

    Đọc trực tiếp từ `synthgen/kie_full.py::hard_negative_spans` -- KHÔNG
    phải view chung với `FieldRecord` (đó là việc của `from_hard_negative`
    bên dưới). `target_kind` là field nó GIẢ LÀM; `negative_kind` là
    `data-kind` nó thực mang trên span (thường "", vì mồi giả không cần khai
    lớp riêng). `strategy` lấy từ `DocumentPlan.hard_negative_profile`
    (Phase 4.1, engine tự rút TRƯỚC khi hỏi model) khi `target_kind` có mặt
    trong đó, "" nếu model khai một decoy engine không lường trước -- vẫn
    hợp lệ, chỉ không gắn nhãn chiến lược."""

    target_kind: str
    negative_kind: str
    strategy: str
    path: str
    value: str = ""
    entity_index: int | None = None


def from_hard_negative(hn: HardNegativeRecord) -> FieldRecord:
    """Một `HardNegativeRecord` -> `FieldRecord` vai `HARD_NEGATIVE`.

    `kind` lấy `target_kind`, không phải `negative_kind` -- người đọc
    `FieldRecord.kind` muốn biết "hộp này giả làm trường nào", cùng câu hỏi
    `kind` trả lời cho `POSITIVE`/`LABEL`. `negative_kind` (thường rỗng)
    và `strategy` gộp vào `source` để không cần thêm cột."""
    source = f"decoy:{hn.strategy}" if hn.strategy else "decoy"
    return FieldRecord(
        path=hn.path,
        kind=hn.target_kind,
        value=hn.value,
        role=HARD_NEGATIVE,
        source=source,
        entity_index=hn.entity_index,
    )


def registry(entities: list[dict[str, Any]],
            pairs: list[dict[str, Any]],
            hard_negatives: list[HardNegativeRecord] | None = None) -> list[FieldRecord]:
    """Toàn bộ trường của một tài liệu, một `FieldRecord` cho mỗi hộp.

    Thứ tự ưu tiên theo hộp (`entity_index`): pair KIE thật (`from_pair`) >
    mồi giả model tự khai (`from_hard_negative`) > suy từ chính entity
    (`from_entity` -- `ORDINARY`/`LABEL`). Pair thật thắng mồi giả có chủ
    đích: gate `synthgen/llm_page.py::problems()` (Phase 6.3) đã chặn một
    span vừa khai `data-decoy-for` vừa khai `data-path` trùng `data-kind`
    của chính nó, nhưng registry() không tin gate đã chạy -- nếu một hộp
    lỡ mang cả hai, giữ pair thật, không để mồi giả che mất một giá trị
    KIE có thật. `hard_negatives=None` (mặc định) giữ hành vi Phase 1 y
    nguyên -- không hộp nào thành `HARD_NEGATIVE` nếu không ai đưa danh
    sách vào.

    Đây là điểm đọc DUY NHẤT Phase 4/Phase 6 nên dùng thay vì tự đi bới
    `entity_annotations` và `kie.pairs` riêng từng nơi."""
    by_index: dict[int, FieldRecord] = {}
    for hn in hard_negatives or ():
        if isinstance(hn.entity_index, int):
            by_index[hn.entity_index] = from_hard_negative(hn)
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


__all__ = ["FieldRecord", "HARD_NEGATIVE", "HardNegativeRecord", "LABEL",
          "ORDINARY", "POSITIVE", "ROLES", "from_entity", "from_hard_negative",
          "from_pair", "registry"]
