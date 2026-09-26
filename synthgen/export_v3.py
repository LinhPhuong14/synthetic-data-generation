#!/usr/bin/env python3
"""Schema KIE v3: `field_type` + `provenance`, một JSON một TÀI LIỆU.

    python synthgen/export_v3.py data/review100d
    python synthgen/export_v3.py data/pilot16 -o data/pilot16/documents_v3

Kế thừa `synthgen/export.py` (schema v2, `docs/kie-schema-v2.md`) chứ không
viết lại: bảng, chữ ký, mực-không-trường, gộp thứ lặp lại -- bốn việc khó
nhất -- đã đúng ở đó. File này chỉ thêm hai thứ v2 chưa có:

* **`field_type`** -- ô tích, ma trận, dãy số, chữ ký/con dấu, chứ không chỉ
  "chuỗi". Nguồn: `pipeline/record.py::field_type_for`, tính MỘT LẦN lúc lắp
  bản ghi, đọc lại ở đây qua `entity_annotations[].field_type` -- không suy
  lại từ `kie.pairs` như `kinds` chưa từng suy lại `kind`.
* **`provenance`** -- commit, seed, model, augment. Đọc thẳng từ `report.json`/
  `compose_report.json` của chính lượt chạy, không đoán.

Xem `docs/kie-schema-v3.md` cho bảng đo và những chỗ CHƯA làm (state=blank,
bảng chấm công không nhãn).

## `fields`/`words` là MẢNG, không phải map theo tên

`export.py`'s `fields` là dict (`{ten: {...}}`) vì nó viết TRƯỚC khi
`docs/kie-schema-v2.md` tồn tại. Ở đây `fields` là danh sách các dòng, mỗi
dòng tự mang `key` -- cùng hình `word_annotations`/`entity_annotations` đã
dùng khắp kho, và nó giải quyết luôn cái lẽ khiến v1/v2 phải bịa suffix `_2`/
`_3` hay gói `type:"list"`: hai dòng CÙNG `key` là hợp lệ trong một danh
sách, chỉ là không hợp lệ trong một khoá dict.

## Ba mảnh field_type trong `fields`/`tables`, ba nguồn khác nhau

1. **`text`/`boolean_choice`/`multi_choice`/`digit_sequence`** -- đọc thẳng
   từ `entity_annotations[].field_type` của thực thể GIÁ TRỊ (`bucket["plain"]`)
   hoặc của thực thể CÂU HỎI (`bucket["grouped"]`, nguồn `survey`) qua
   `synthgen/kie_full.py::group_lists`'s tham số `field_types` mới.
2. **`data_table`/`categorical_matrix`** -- KHÔNG có trong
   `ENTITY_FIELD_TYPES` khi bảng dựng từ `<table>` thật: vai của nó đọc từ
   `record["kie"]["tables"]` (đã có sẵn, `synthgen/kie_full.py::table_structures`
   tính lúc `complete()` chạy) -- `role="data"` thì `data_table`, `role=
   "layout"` thì KHÔNG vào `tables[]` (không phải bảng thật). Khi bảng dựng
   từ `grid`/`table_form` (div+CSS grid, không phải `<table>`) thì field_type
   đã nằm sẵn trên câu hỏi qua đường (1).
3. **`presence`** -- không đọc từ đâu cả, TỔNG HỢP tại đây từ khối chữ ký
   (`group_lists`'s `signatures[]`, đã ghép chức danh với tên) cộng sự có mặt
   của bất kỳ thực thể `seal.*` nào trên trang. Không phải một thuộc tính của
   một thực thể -- xem `pipeline/record.py::field_type_for`'s docstring.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen.export import (  # noqa: E402
    _declared_table,
    _marks,
    _order,
    _rect,
    _signatures,
    _sizes,
    _split,
    _table,
    to_grid,
)
from synthgen.kie_full import TICKED_MARKS, group_lists  # noqa: E402

SCHEMA_VERSION = 3

# Field_type có thể xuất hiện trong `fields[]`, đóng -- xem
# `pipeline/record.py::ENTITY_FIELD_TYPES` cho bốn cái đầu; `presence` chỉ
# sinh ở đây.
FIELDS_TYPES = frozenset({"text", "boolean_choice", "multi_choice",
                          "digit_sequence", "presence"})
# Field_type của một phần tử `tables[]`, đóng.
TABLE_TYPES = frozenset({"data_table", "categorical_matrix"})


def _git_commit(root: Path | None = None) -> str:
    """Mã commit ngắn của CHÍNH LẦN CHẠY NÀY -- không phải lần dựng dữ liệu.

    Với một lượt sinh MỚI, hai cái trùng nhau. Với một lượt `--migrate` vá
    lại bộ dữ liệu CŨ, chúng không trùng -- commit sinh ra bộ dữ liệu chưa
    từng được ghi lại ở đâu và không dựng lại được. Hàm này không giả vờ biết
    cái nó không biết; người gọi ở chế độ vá phải tự nói rõ điều đó trong
    thông báo của mình, xem `main()`."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(root or REPO_ROOT), capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout.strip() or "unknown"
    except Exception:                                        # noqa: BLE001
        return "unknown"


def provenance(root: Path) -> dict:
    """`{generator, seed, llm, augment}` của CẢ LƯỢT CHẠY tại `root`.

    Đọc thẳng, không đoán -- ba nguồn, không nguồn nào là bảng tra:

    * `report.json`'s `run.seed`/`run.augment` -- nhánh luật/procedural
      (`synthgen/run.py`) luôn ghi file này. Đo trên `data/review100d`:
      `seed=20260910`, `augment="off"`, cả hai lấy nguyên văn.
    * `compose_report.json`'s `model` -- nhánh LLM/agent (`agent/compose_page.py`)
      ghi file NÀY thay vì `report.json`. Đo trên `data/pilot16`:
      `model="Qwen/Qwen3.8-27B-FP8"`.

    Không có file nào trong hai file trên thì khoá tương ứng là `None` --
    KHÔNG suy đoán. Đo được: nhánh LLM hôm nay không ghi `report.json` ở
    đâu cả, nên `seed`/`augment` của nó luôn `None` cho tới khi
    `agent/compose_page.py` tự ghi ra; đây là một khoảng trống THẬT, không
    phải một lỗi của hàm này."""
    report = {}
    report_path = root / "report.json"
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8")).get("run") or {}
        except (OSError, json.JSONDecodeError):
            report = {}
    llm = None
    compose_path = root / "compose_report.json"
    if compose_path.is_file():
        try:
            llm = json.loads(compose_path.read_text(encoding="utf-8")).get("model")
        except (OSError, json.JSONDecodeError):
            llm = None
    return {
        "generator": f"synthgen@{_git_commit(root)}",
        "seed": report.get("seed"),
        "llm": llm,
        "augment": report.get("augment"),
    }


def _dual(pair: dict, key: str, width: float, height: float) -> tuple[list, list]:
    """`(bbox hệ 1000, bbox pixel)` của `pair[key]` -- cả hai luôn có mặt,
    cùng lệ `pipeline/record.py::to_per_mille` đã đặt cho cả bản ghi."""
    box = _rect(pair.get(key))
    if not box:
        return [], []
    return to_grid(box, width, height), [int(round(v)) for v in box]


def _box_dual(box) -> tuple[list, list]:
    """`(bbox hệ 1000, bbox pixel)` của một hộp ENTITY (đã ở hệ 1000 từ
    `pipeline/record.py::to_per_mille`) -- khác `_dual` ở chỗ không cần
    `width`/`height` để quy đổi, vì thực thể mang cả hai hệ sẵn."""
    if not box:
        return [], []
    return [int(round(v)) for v in box], []


def _union_bbox(boxes: list) -> list:
    """Hộp bao ngoài của một danh sách hộp `[x1,y1,x2,y2]`. `[]` khi rỗng."""
    real = [b for b in boxes if b and len(b) == 4]
    if not real:
        return []
    return [min(b[0] for b in real), min(b[1] for b in real),
            max(b[2] for b in real), max(b[3] for b in real)]


def _handwritten_kinds(record: dict) -> frozenset[str]:
    """`kind` nào trên trang này bị viết tay -- `handwriting.kinds` của
    chính bản ghi. Rỗng thì mọi trường đều `printed` khi có giá trị."""
    return frozenset((record.get("handwriting") or {}).get("kinds") or ())


def _state_for(kind: str, value_text: str, handwritten: frozenset[str]) -> str:
    """`printed` / `handwritten` / `absent`. Xem cảnh báo trong
    `docs/kie-schema-v3.md`: KHÔNG phải trục `blank`/`absent` của
    `docs/kie-schema-v2.md` -- ô trống-nhưng-có-nhãn (`blank`) chưa phân biệt
    được với ô không tồn tại (`absent`), vì `markup.py` chưa phát span rỗng.
    Trục này đo được HÔM NAY; trục kia thì chưa."""
    if not str(value_text or "").strip():
        return "absent"
    return "handwritten" if kind in handwritten else "printed"


def _table_field_type(table_id: str, source: str,
                      table_roles: dict[str, str]) -> str | None:
    """`data_table`/`categorical_matrix`/`None` (không phải bảng thật).

    `source == "declared"` (model tự khai `items[3].qty`) luôn `data_table`
    -- không đường hình học nào lẫn vào để có `role="layout"` ở đó. Bảng
    hình học tra `table_roles` (từ `record["kie"]["tables"]`, đã tính sẵn
    lúc `kie_full.complete()` chạy): `role="data"` -> `data_table`,
    `role="layout"` -> None (mảnh trang trí, không phải bảng)."""
    if source == "declared":
        return "data_table"
    role = table_roles.get(table_id)
    if role == "data":
        return "data_table"
    return None


def _digit_sequence(question: dict, key: str, page: int,
                    handwritten: frozenset[str], kind: str) -> dict | None:
    """`{key, field_type:"digit_sequence", ...}` từ `question["chars"]`.

    `chars` là danh sách `{value, bbox}` ĐÃ ĐÚNG THỨ TỰ (`survey_pairs` phát
    theo `rank`, tăng dần khi vẽ) -- nối chuỗi là đọc lại đúng số đã in,
    không phải đoán theo toạ độ."""
    chars = question.get("chars") or []
    if not chars:
        return None
    value = "".join(str(c.get("value") or "") for c in chars)
    prompt = question.get("question") or {}
    return {
        "key": key, "field_type": "digit_sequence", "page": page,
        "surface_key": str(prompt.get("value") or ""),
        "value": value, "value_norm": value,
        "state": _state_for(kind, value, handwritten),
        "value_bbox": prompt.get("bbox") or [],
        "digit_bboxes": [c.get("bbox") for c in chars],
    }


def _matrix_table(question: dict, table_id: str, field_type: str,
                  page: int) -> dict | None:
    """`categorical_matrix` (`grid`) hay `data_table` (`table_form`) từ MỘT
    câu hỏi bảng hỏi -- không phải từ `<table>` thật.

    `survey_pairs` phát mỗi ô THEO THỨ TỰ VẼ, hàng trước cột sau
    (`synthgen/markup.py::_shape_rows`'s `grid`/`table_form` cùng lặp
    `for row: for col:`) -- nên `options`/`cells` của `group_lists` là một
    danh sách PHẲNG theo đúng thứ tự hàng-chính (row-major), và chia nó
    thành từng khối `len(columns)` phần tử là dựng lại đúng lưới, không cần
    đọc lại `seat` (`"hàng__cột"`) hay đoán theo toạ độ.

    `None` khi số ô không chia hết cho số cột -- một lưới hỏng hình không
    dựng lại được đáng tin hơn một lưới dựng ẩu và không báo gì."""
    columns = [str((c or {}).get("value") or "") for c in (question.get("columns") or [])]
    n_cols = len(columns) or 1
    if field_type == "categorical_matrix":
        rows_hdr = [str((r or {}).get("value") or "") for r in (question.get("rows") or [])]
        cells = question.get("options") or []
        if rows_hdr and len(cells) % len(rows_hdr) != 0:
            return None
        per_row = len(cells) // len(rows_hdr) if rows_hdr else n_cols
        rows_out = []
        for r, label in enumerate(rows_hdr):
            seat = cells[r * per_row:(r + 1) * per_row]
            cell_boxes = [c.get("ticked", {}).get("bbox", []) for c in seat]
            rows_out.append({
                "key": label,
                "row_bbox": _union_bbox(cell_boxes),
                "cell_bboxes": cell_boxes,
                "checked": [bool(c.get("checked")) for c in seat],
            })
        col_defs = columns or [str(i + 1) for i in range(per_row)]
    else:                                                     # data_table
        cells = question.get("cells") or []
        if not cells or len(cells) % n_cols != 0:
            return None
        rows_out = []
        for r in range(len(cells) // n_cols):
            seat = cells[r * n_cols:(r + 1) * n_cols]
            cell_boxes = [c.get("bbox", []) for c in seat]
            rows_out.append({
                "key": str(r + 1), "row_bbox": _union_bbox(cell_boxes),
                "cell_bboxes": cell_boxes,
                "value": [str(c.get("value") or "") for c in seat],
            })
        col_defs = columns
    if not rows_out:
        return None
    return {"table_id": table_id, "field_type": field_type, "page": page,
            "columns": col_defs, "rows": rows_out}


def document_v3(record: dict, kind: str, *, doc_id: str, provenance_of: dict,
                registry_version: str | None) -> dict:
    """Một tài liệu, đúng hình `docs/kie-schema-v3.md`."""
    sizes = _sizes(record)
    pairs = (record.get("kie") or {}).get("pairs") or []
    held = [p for p in pairs if p.get("in_batch") is False]
    if held:
        pairs = [p for p in pairs if p.get("in_batch") is not False]
    entities = record.get("entity_annotations") or []
    kinds = {e.get("entity_index"): str(e.get("kind") or "") for e in entities}
    field_types = {e.get("entity_index"): str(e.get("field_type") or "")
                   for e in entities}
    table_roles = {t.get("table_id"): str(t.get("role") or "")
                   for t in (record.get("kie") or {}).get("tables") or []}
    handwritten = _handwritten_kinds(record)

    by_page: dict[int, list[dict]] = {}
    for pair in pairs:
        by_page.setdefault(int(pair.get("page_number", 1) or 1), []).append(pair)

    pages: list[dict] = []
    fields: list[dict] = []
    tables: list[dict] = []
    words: list[dict] = []
    layout: list[dict] = []

    for number in sorted(set(by_page) | set(sizes)):
        width, height = sizes.get(number, (0.0, 0.0))
        pages.append({"page": number, "size": [int(width), int(height)]})
        on_page = by_page.get(number, [])
        bucket = _split(on_page, kinds)

        # TRƯỜNG PHẲNG. `field_type` đọc từ chính thực thể GIÁ TRỊ -- ô tích
        # đơn (`sheets/form.py::_checklist`'s dòng, PAIRED trong
        # `kie_full.py`) đi qua ĐÚNG nhánh này vì `_split` xếp nó vào
        # `plain` (nguồn `"pair"`, không phải `"survey"`).
        for pair in sorted(bucket["plain"], key=_order):
            name = str(pair.get("field") or pair.get("column") or "").strip()
            if not name:
                continue
            value_index = pair.get("value_entity_index")
            ftype = field_types.get(value_index) or "text"
            key_bbox, key_bbox_px = _dual(pair, "key_bbox", width, height)
            value_bbox, value_bbox_px = _dual(pair, "value_bbox", width, height)
            value_kind = kinds.get(value_index, "")
            if ftype == "boolean_choice":
                checked = bool(TICKED_MARKS.intersection(str(pair.get("value_text") or "")))
                fields.append({
                    "key": name, "field_type": "boolean_choice", "page": number,
                    "value": checked,
                    "options": [{"label": str(pair.get("key_text") or ""),
                                "label_bbox": key_bbox, "label_bbox_px": key_bbox_px,
                                "mark_bbox": value_bbox, "mark_bbox_px": value_bbox_px,
                                "checked": checked}],
                })
                continue
            value_text = str(pair.get("value_text", ""))
            fields.append({
                "key": name, "field_type": ftype if ftype in FIELDS_TYPES else "text",
                "surface_key": str(pair.get("key_text", "")),
                "value": value_text, "value_norm": value_text,
                "state": _state_for(value_kind, value_text, handwritten),
                "page": number,
                "key_bbox": key_bbox, "key_bbox_px": key_bbox_px,
                "value_bbox": value_bbox, "value_bbox_px": value_bbox_px,
            })

        # BẢNG THẬT (`<table>`) -- ô, xây bằng `_table`/`_declared_table` như
        # v2 đã làm đúng; chỉ thêm `field_type` từ `table_roles`, và LOẠI ra
        # khi bảng chỉ là trang trí (`role="layout"`).
        detail = [p for p in bucket["cells"] if p.get("under")]
        cell_pairs = [p for p in bucket["cells"] if not p.get("under")]
        arrays: dict[str, list[dict]] = {}
        for pair in bucket["declared"]:
            found = __import__("re").match(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]\.(.+)$",
                                           str(pair.get("path") or ""))
            if found:
                arrays.setdefault(found.group(1), []).append(pair)
        for tname in sorted(arrays):
            declared = _declared_table(tname, arrays[tname], width, height)
            ftype = _table_field_type(declared["table_id"], "declared", table_roles)
            if ftype:
                tables.append({"table_id": declared["table_id"], "field_type": ftype,
                              "page": number, "columns": declared["columns"],
                              "rows": declared["rows"]})
        groups: dict[str, list[dict]] = {}
        for pair in cell_pairs:
            groups.setdefault(str(pair.get("table_id") or "t1"), []).append(pair)
        for tname in sorted(groups):
            extra = bucket["extra"] if tname == min(groups) else []
            geo = _table(groups[tname], extra, kinds, width, height, table_id=tname)
            if not geo:
                continue
            ftype = _table_field_type(geo["table_id"], "geometry", table_roles)
            if ftype:
                tables.append({"table_id": geo["table_id"], "field_type": ftype,
                              "page": number, "columns": geo["columns"],
                              "rows": geo["rows"]})

        # NHÓM SURVEY/CLAUSE/SIGN -- một luật gom, ba đích khác nhau.
        grouped = group_lists(bucket["grouped"], _cell_render(width, height), field_types)
        for clause in grouped["clauses"]:
            title, body = clause.get("title") or {}, clause.get("body") or {}
            value = str(body.get("value") or "")
            fields.append({
                "key": f"clause_{clause['index']}", "field_type": "text",
                "surface_key": str(title.get("value") or ""),
                "value": value, "value_norm": value,
                "state": "printed" if value else "absent", "page": number,
                "key_bbox": title.get("bbox") or [],
                "value_bbox": body.get("bbox") or [],
            })
        for ground in grouped["legal_basis"]:
            value = str((ground.get("ground") or {}).get("value") or "")
            fields.append({
                "key": f"legal_basis_{ground['index']}", "field_type": "text",
                "value": value, "value_norm": value,
                "state": "printed" if value else "absent", "page": number,
                "value_bbox": (ground.get("ground") or {}).get("bbox") or [],
            })
        for question in grouped["questions"]:
            prompt = question.get("question") or {}
            key = _slug(str(prompt.get("value") or "")) or f"question_{question['index']}"
            ftype = question.get("field_type") or (
                "multi_choice" if question.get("options") else "text")
            if ftype in ("boolean_choice", "multi_choice"):
                seats = question.get("options") or []
                options = [{
                    "label": str((s.get("label") or {}).get("value") or ""),
                    "label_bbox": (s.get("label") or {}).get("bbox") or [],
                    "mark_bbox": (s.get("ticked") or {}).get("bbox") or [],
                    "checked": bool(s.get("checked")),
                } for s in seats]
                picked = [o["label"] for o in options if o["checked"]]
                fields.append({
                    "key": key, "field_type": ftype, "page": number,
                    "surface_key": str(prompt.get("value") or ""),
                    "value": (bool(picked) if ftype == "boolean_choice" else picked),
                    "options": options,
                })
            elif ftype == "digit_sequence":
                built = _digit_sequence(question, key, number, handwritten,
                                        "survey.char")
                if built:
                    fields.append(built)
            elif ftype in TABLE_TYPES:
                built = _matrix_table(question, f"survey_{question['index']}",
                                      ftype, number)
                if built:
                    tables.append(built)
            # `ftype == "text"` (không có options/chars/rows) -- câu hỏi mở,
            # không có ô tích/ký tự nào để gắn: bỏ qua, không bịa một trường
            # rỗng.

        # CHỮ KÝ/CON DẤU -- `presence` TỔNG HỢP, không đọc từ một thực thể.
        page_has_seal = any(
            str(e.get("kind") or "").startswith("seal.")
            for e in entities if int(e.get("page_number", 1) or 1) == number)
        signature_blocks = (grouped["signatures"]
                            + _signatures(bucket["signs"], kinds, width, height))
        for block in signature_blocks:
            role = block.get("signer_role") or {}
            name_cell = block.get("signer_name") or {}
            boxes = [b.get("bbox") for b in (role, name_cell) if b.get("bbox")]
            fields.append({
                "key": _slug(str(role.get("value") or "")) or f"signature_{block['index']}",
                "field_type": "presence", "page": number,
                "surface_key": str(role.get("value") or ""),
                "value": {"signed": bool(block.get("signed")),
                         "stamped": page_has_seal},
                "bbox": (boxes[0] if boxes else []),
            })

        # MỰC KHÔNG PHẢI TRƯỜNG -- có hộp, có `kind`, không giả làm câu trả
        # lời cho câu hỏi nào. Không vào `fields`; `layout`/`words` vẫn thấy.
        claimed = {i for pair in on_page
                  for i in (pair.get("value_entity_index"), pair.get("key_entity_index"))
                  if isinstance(i, int)}
        _marks(bucket["marks"], kinds, width, height, entities, number, claimed)

        for region in record.get("layout_annotations") or []:
            if int(region.get("page_number", 1) or 1) != number:
                continue
            layout.append({"page": number,
                           "layout_class": str(region.get("layout_class") or ""),
                           "bbox": region.get("bbox") or [],
                           "bbox_px": region.get("bbox_px") or []})

        field_of_entity = {i: pair.get("field")
                           for pair in on_page
                           for i in (pair.get("value_entity_index"),)
                           if isinstance(i, int)}
        for word in record.get("word_annotations") or []:
            if int(word.get("page_number", 1) or 1) != number:
                continue
            words.append({"page": number, "text": str(word.get("text") or ""),
                          "bbox": word.get("bbox") or [],
                          "bbox_px": word.get("bbox_px") or [],
                          "field": field_of_entity.get(word.get("entity_index"))})

    return {
        "doc_id": doc_id, "schema_version": SCHEMA_VERSION, "doc_type": kind or None,
        "registry_version": registry_version,
        "provenance": provenance_of,
        "bbox_unit": "per_mille_of_size",
        "pages": pages, "fields": fields, "tables": tables,
        "words": words, "layout": layout,
    }


def _cell_render(width: float, height: float):
    """`render(pair, side)` cho `group_lists` -- `{value, bbox}` hệ 1000,
    đúng lệ `synthgen/export.py::_grouped`'s closure cùng tên."""
    def cell(pair: dict, side: str) -> dict:
        box = _rect(pair.get(f"{side}_bbox"))
        return {"value": str(pair.get(f"{side}_text", "")),
                "bbox": to_grid(box, width, height) if box else []}
    return cell


def _slug(text: str) -> str:
    from pipeline.kie import slug as _s  # noqa: PLC0415
    return _s(text)


def run(root: Path, out: Path, *, min_pages: int, limit: int,
        indent: int | None, migrate: bool) -> int:
    manifest = root / "manifest.jsonl"
    if not manifest.is_file():
        print(f"không có {manifest} — đây có phải thư mục đã sinh xong không?")
        return 1
    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines() if line.strip()]

    documents: dict[str, list[dict]] = {}
    for row in rows:
        documents.setdefault(str(row.get("document") or row["stem"]), []).append(row)
    documents = {name: group for name, group in documents.items()
                if all(r.get("llm_passed_gate", True) for r in group)}
    chosen = [name for name, group in documents.items()
             if int(group[0].get("pages_in_document", 1) or 1) >= min_pages]
    chosen.sort()
    if limit:
        chosen = chosen[:limit]
    if not chosen:
        print(f"không có tài liệu nào từ {min_pages} tờ trở lên")
        return 1

    prov = provenance(root)
    if migrate:
        print(f"[export_v3] --migrate: 'generator' ghi commit của LẦN VÁ NÀY "
              f"({prov['generator']}), không phải commit đã sinh ra {root} — "
              f"commit gốc không được ghi lại ở đâu và không dựng lại được.")

    (out / "json").mkdir(parents=True, exist_ok=True)
    written = 0
    for name in chosen:
        group = sorted(documents[name], key=lambda r: int(r.get("page_number", 1) or 1))
        kind = str(group[0].get("archetype") or "")
        source = group[0].get("record") or group[0]["json"]
        record = json.loads((root / source).read_text(encoding="utf-8"))
        registry_version = group[0].get("design_signature")
        payload = document_v3(record, kind, doc_id=name, provenance_of=prov,
                              registry_version=registry_version)
        target = out / "json" / kind / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
                          encoding="utf-8")
        written += 1
    print(f"[export_v3] {written} tài liệu -> {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục đã sinh xong")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="thư mục ra; mặc định <bộ>/documents_v3")
    parser.add_argument("--min-pages", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--indent", type=int, default=1)
    parser.add_argument("--migrate", action="store_true",
                        help="vá một bộ đã sinh TRƯỚC khi field_type tồn tại — "
                             "chỉ đổi câu in ra `generator`, không đổi cách tính")
    args = parser.parse_args()
    root = args.run.resolve()
    out = (args.out or root / "documents_v3").resolve()
    return run(root, out, min_pages=args.min_pages, limit=args.limit,
              indent=args.indent or None, migrate=args.migrate)


__all__ = ["document_v3", "provenance", "SCHEMA_VERSION"]


if __name__ == "__main__":
    raise SystemExit(main())
