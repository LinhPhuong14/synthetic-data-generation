#!/usr/bin/env python3
"""Gom chứng từ ra một chỗ, mỗi tài liệu một file JSON phẳng theo trang.

    python synthgen/export.py data/09-09-26-synthetics-document
    python synthgen/export.py <bộ> --min-pages 3 --limit 500
    python synthgen/export.py <bộ> -o <chỗ khác> --rich

Bộ chính chép bản ghi bên cạnh TỪNG TỜ, nên một hoá đơn ba tờ có ba file json
giống hệt nhau và mỗi file tả cả ba tờ. Đúng cho việc huấn luyện một mô hình
nhìn MỘT ảnh, sai cho việc huấn luyện một mô hình nhìn CẢ TẬP ảnh: cái sau cần
biết trường nào nằm trên tờ nào, và cần biết nó MỘT LẦN chứ không ba lần.

Nên ở đây một tài liệu là MỘT file, và `pages` là một MẢNG:

    {
      "doc_type": "bang_luong",
      "doc_id": "llm_bang_luong_0007",
      "page_count": 2,
      "bbox_unit": "per_mille_of_size",
      "pages": [ {
        "page": 1,
        "size": [1101, 1811],
        "fields":     { "so": {"type": "string", "value": "563/2026", ...} },
        "tables":     [ {"type": "table", "table_id": "items", ...} ],
        "signatures": [ {"index": 1, "title": {...}, "name": {...}} ],
        "marks":      [ {"kind": "sign.note", "text": "(Ký, ghi rõ họ tên)"} ]
      } ]
    }

Mảng chứ không phải `page_1`/`page_2`: khoá động thì JSON Schema phải dùng
`patternProperties`, và một bộ sinh CÓ RÀNG BUỘC (vLLM/xgrammar) phải đoán tên
khoá thay vì đi theo một hình dạng cố định. `size` có mặt để quy hệ 1000 ngược
về pixel -- làm tròn là phép một chiều, và một bộ chỉ có số đã làm tròn thì
không ai kiểm lại được.

Bốn khoá của một trang LUÔN có mặt, kể cả khi rỗng, vì cùng một lý do: hình
dạng cố định thì bộ sinh có ràng buộc đi theo được.

## `tables` là MẢNG, không phải một khoá trong `fields`

Một trang có N bảng, và N không cố định -- đúng lập luận đã dựng nên `pages`.
Nhét chúng vào `fields` thì bảng thứ hai phải tên `line_items_2`, tức đánh số
thứ tự làm danh tính, và đó là thứ định dạng này đã bỏ được ở chỗ khác.

Nặng hơn thế: bản trước gộp MỌI ô có `source="table"` của một trang vào MỘT
bảng, khoá theo `(row, column)`. Hai bảng trên cùng trang có cùng toạ độ ô, nên
bảng sau đè bảng trước -- đo trên `data/pilot13`, tờ
`insurance_partner_cert_application` mất 69 trên 273 cặp, không một dòng báo.
`kie_full.table_pairs` giờ phát `table_id`, và ở đây mỗi `table_id` là một
phần tử.

## Hai nguồn bảng, giữ riêng, không đoán để nối

- **Bảng model TỰ KHAI** -- `data-path` dạng `items[3].qty`. Cột mang `path`,
  dòng mang chỉ số của chính đường dẫn. Không có tiêu đề in kèm: model khai tên
  máy, không khai chữ trên giấy.
- **Bảng dựng bằng HÌNH HỌC** -- `source="table"`, cột mang `header` đọc từ ô
  `<thead>` và `path` là đường dẫn tiêu đề nhiều tầng.

Bản trước đổ cả hai vào một chỗ: đường tự khai rơi xuống thành trường phẳng
`items_0_stt`, `items_0_name`, ... **272 trên 814 trường cấp trang (33,4%)** của
`data/pilot13` là ô bảng nằm lẫn với `doc_title`, và trang nặng nhất có 197
trường -- trong khi bảng dựng từ hình học của CHÍNH trang ấy chỉ nhận được hai
cột ("Số lượt", "Ghi chú") trên bảy cột có thật.

Không nối hai nguồn bằng phép đo chồng hộp: `kie_full` đã thử và hỏng hai lần
(cột số căn phải mất tiêu đề; cột bên cạnh cướp tiêu đề). Chúng là hai bảng cho
tới khi bộ sinh khai rằng chúng là một.

## `marks` -- mực có hộp nhưng KHÔNG phải trường

"(Ký, ghi rõ họ tên)" in dưới mọi ô chữ ký, giống hệt nhau trên mọi tờ, nên nó
mang đúng không bit thông tin nào. `pipeline.kie.FURNITURE` đã chặn nó ở đường
có nhãn, nhưng đường `declared` chạy TRƯỚC và không đi qua chỗ chặn ấy: đo trên
`data/pilot13`, 12 cặp lọt, và ba trong số đó còn dính nhầm vào đường dẫn của
một cột bảng (`criteria_3_quota` = "(Ký, ghi rõ họ tên)").

Ở đây chúng không biến mất -- chúng vào `marks`, có hộp, có `kind`, chỉ thôi
giả làm câu trả lời cho một câu hỏi.

## `type` là kiểu dữ liệu, và cũng là discriminator

Mọi entry trong `fields` có `type`, một trong sáu:

    string · integer · number · date · list · table

Bên đọc `switch` trên `type` chứ không đoán theo tên khoá: `list` thì entry có
`items`, còn lại thì có `value`/`bbox`. `table` giờ chỉ xuất hiện ở `tables`,
không còn trong `fields` -- nhưng vẫn mang `type` để một hàm đọc ô dùng được
cho cả hai chỗ.

`period` ("Long Xuyên, ngày 12 tháng 02 năm 2026") và `store.tax_code`
("7159917591") cố ý là `string`: một chuỗi có ngày bên trong không phải một
ngày, và mã số thuế không phải một con số để cộng.

## Bảng là MỘT dãy dòng có kiểu

    group  ->  data x6  ->  subtotal  ->  group  ->  data x4  ->  subtotal
           ->  total x3  ->  grand_total

Đúng thứ tự đọc trên giấy, và một dòng dữ liệu thuộc cụm nào là chuyện của thứ
tự -- không chép tên cụm vào từng dòng. Bản trước chia bảng ra bốn mảng rời và
nối bằng so khớp chuỗi nhãn; hai cụm trùng tên là hỏng.

Kiểu dòng suy từ `entity_annotations[].kind` -- từ vựng ĐÓNG do chính bộ dựng
HTML gắn -- chứ không từ chữ trong nhãn. Phân loại bằng tiền tố ("Tổng",
"Cộng") chết trên chứng từ tiếng Anh, và một trường tên "Tổng giám đốc" cũng
lọt.

Tiêu đề cột có HỘP, kèm `path` cho bảng nhiều tầng. Trước đó chúng không có
mặt ở đâu trong định dạng này.

## Trường in nhiều lần: `list` khi cùng `kind`

Bốn đoạn ghi chú, ba dòng chữ ký -- đó là MỘT trường in nhiều dòng, và
`note_2`/`note_3` là số thứ tự chứ không phải tên. Đo trên 141 tài liệu:
284/308 lượt lặp là cùng `kind`, gộp được. 24 lượt còn lại khác `kind`
(`dien_thoai` của bên bán và của bên mua slug ra cùng tên) -- chúng là hai
trường, giữ hậu tố là đúng. Hậu tố `_N`: **16,6% -> 0,9%**.

## Toạ độ: hệ 1000

`bbox` là `round(x / chiều_rộng * 1000)`, cắt vào `[0, 1000]` -- thứ các mô
hình thị giác - ngôn ngữ đọc và sinh ra, không phụ thuộc ảnh được thu nhỏ bao
nhiêu. `--rich` gắn thêm `bbox_px`/`key_bbox_px` cho ai cần kiểm ngược.

Ô bảng không in trên giấy thì KHOÁ VẮNG, không phải ô rỗng: dựng
`{"value": "", "bbox": []}` là khai một thứ không tồn tại. `columns` đã nói đủ
bộ cột.

## Chọn tài liệu nào

Mặc định: **mọi tài liệu**, một tờ hay nhiều tờ. `--min-pages 2` thì chỉ lấy
nhiều tờ, `--min-pages 3` thì từ ba tờ trở lên.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.kie import FURNITURE  # noqa: E402
from synthgen.kie_schema import (  # noqa: E402
    INTEGER_COLUMNS,
    NUMBER_COLUMNS,
    NUMBER_KINDS,
)

GRID = 1000

# `items[3].qty` -> (`items`, 3, `qty`). Đường dẫn model tự khai cho một Ô BẢNG;
# mọi đường dẫn khác là một trường thường.
ARRAY_PATH = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]\.(.+)$")

# Mực có hộp nhưng không phải trường. `FURNITURE` là chữ nhà in đặt sẵn dưới ô
# ký; hai cái còn lại là dấu và chữ chìm -- chúng có vùng riêng trong
# `layout_annotations` và không trả lời câu hỏi nào.
MARK_KINDS = frozenset(FURNITURE) | {"watermark"}
MARK_PREFIX = ("seal.",)

# Khối chữ ký: chức danh và tên. `sign.note` KHÔNG ở đây -- nó là `marks`.
# `sign.signedat` cũng không: "Hà Nội, ngày 12 tháng 02" là nơi và ngày lập, một
# trường của tờ giấy, không phải một người ký.
SIGN_TITLE = "sign.title"
SIGN_NAME = "sign.name"

# Thứ cần chép sang cùng file JSON để thư mục tự đứng được: ảnh của từng tờ.
# HTML và markdown không chép -- chúng theo TRANG chứ không theo tài liệu, và
# ai cần thì bộ gốc vẫn còn.
IMAGES = "images"


def to_grid(box, width: float, height: float) -> list[int]:
    """`[x1, y1, x2, y2]` pixel -> hệ 1000, cắt vào `[0, 1000]`.

    Cắt chứ không để tràn: một hộp lệch ra ngoài mép giấy vài pixel vì làm
    tròn là chuyện có thật, còn một toạ độ 1003 trong hệ 1000 thì mọi thứ đọc
    nó đều phải tự đoán xem có nên tin không."""
    if not box or width <= 0 or height <= 0:
        return []
    x1, y1, x2, y2 = (float(v) for v in box)
    scale = lambda v, size: max(0, min(GRID, int(round(v / size * GRID))))  # noqa: E731
    return [scale(x1, width), scale(y1, height),
            scale(x2, width), scale(y2, height)]


def _rect(box) -> list[float] | None:
    """`[x1, y1, x2, y2]` từ dict `{x1..y2}` hoặc từ chính một danh sách."""
    if isinstance(box, dict):
        try:
            return [float(box["x1"]), float(box["y1"]),
                    float(box["x2"]), float(box["y2"])]
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(box, (list, tuple)) and len(box) == 4:
        return [float(v) for v in box]
    return None


def _sizes(record: dict) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for sheet in record.get("pages") or []:
        number = int(sheet.get("page_number", 1) or 1)
        out[number] = (float(sheet.get("width") or 0),
                       float(sheet.get("height") or 0))
    return out


def _order(pair: dict) -> tuple:
    """Thứ tự đọc: trên xuống, rồi trái sang. Quyết định hậu tố `_2`, `_3`."""
    box = _rect(pair.get("value_bbox")) or [0.0, 0.0, 0.0, 0.0]
    return (round(box[1]), round(box[0]))


# Kiểu của một entry trong `fields`. Sáu giá trị, ĐÓNG -- và `type` vừa là
# kiểu dữ liệu, vừa là DISCRIMINATOR cho hình dạng: `table` thì entry có
# `columns`/`rows`, `list` thì có `items`, còn lại thì có `value`/`bbox`. Nhờ
# nó mà bảng nằm chung một namespace với trường thường mà bên đọc không phải
# đoán theo tên khoá.
#
# Không khai lại "cái gì là số": `synthgen/kie_schema.py` đã quyết một lần cho
# `kie.schema`, và hai chỗ cùng trả lời một câu hỏi là hai chỗ sẽ lệch nhau.
#
# `period` ("Long Xuyên, ngày 12 tháng 02 năm 2026") và `store.tax_code`
# ("7159917591") cố ý là `string`: một chuỗi có ngày bên trong không phải một
# ngày, và một mã số thuế không phải một con số để cộng. Cùng lập luận
# `kie_schema.py` viết ra cho `_number`.
DATE_COLUMNS = {"date"}
INTEGER_KINDS = {"toc.page", "colnum"}

# Dòng bảng, năm kiểu, suy từ `kind` của thực thể chứ không từ chữ trong nhãn.
# Bản trước phân loại bằng tiền tố ("Tổng", "Cộng", "Thuế") -- chết trên chứng
# từ tiếng Anh, và một trường tên "Tổng giám đốc" cũng lọt.
ROW_KIND = {
    "total.group": "subtotal",
    "total.line": "total",
    "total.grand": "grand_total",
}

# Tên cột ở ĐỊNH DẠNG XUẤT khác tên trong `design.COLUMNS` đúng một chỗ: 26/27
# khoá đã là tiếng Anh, `stt` là chỗ duy nhất còn tiếng Việt.
#
# Dấu chấm không phải để cho đẹp. Trong YAML 1.1, `no` không đặt trong nháy đọc
# ra BOOLEAN FALSE -- đo được: `columns: [[no, name]]` ra `[[False, 'name']]`.
# Phôi và bố cục viết danh sách cột không quoted, và `agent/compose_archetype.py`
# để MODEL viết YAML phôi, nên một khoá tên `no` là cái bẫy sẽ sập lại đều đặn
# và im lặng. `no.` đọc ra chuỗi.
#
# Bảng NGOẠI LỆ, không phải bảng ánh xạ: khoá không có ở đây thì giữ nguyên,
# nên thêm một cột mới không phải thêm một dòng ở đây.
EXPORT_NAME = {"stt": "no."}


def type_of(*, column: str = "", kind: str = "") -> str:
    """Kiểu của một cột hoặc một trường. Một trong sáu giá trị đóng."""
    if column:
        if column in INTEGER_COLUMNS:
            return "integer"
        if column in NUMBER_COLUMNS:
            return "number"
        if column in DATE_COLUMNS:
            return "date"
        return "string"
    if kind in NUMBER_KINDS:
        return "number"
    if kind in INTEGER_KINDS:
        return "integer"
    return "string"


def _cell(value, box, width: float, height: float) -> dict:
    px = _rect(box)
    return {"value": str(value or ""),
            "bbox": to_grid(px, width, height) if px else []}


def _column_key(pair: dict, taken: set[str]) -> str:
    """Tên cột. Tiêu đề IN TRÊN GIẤY thắng khi `column` không nói gì.

    `kie_full.BY_KIND` trả `"cell"` cho mọi cột nó không biết mặt -- đo trên
    `data/pilot13`: 8 trên 70 cột mang tên ấy, và hai cột `cell` trên cùng một
    bảng thì một cái mất. Chữ trên giấy phân biệt được chúng: "Quy cách",
    "Chẩn đoán", "Tình trạng" là ba cột khác nhau."""
    key = EXPORT_NAME.get(str(pair.get("column") or ""),
                          str(pair.get("column") or ""))
    if key and key != "cell" and key not in taken:
        return key
    header = _slug(str(pair.get("key_text") or ""))
    base = header or key or "cell"
    name, suffix = base, 2
    while name in taken:
        name, suffix = f"{base}_{suffix}", suffix + 1
    return name


def _slug(text: str) -> str:
    """Tiêu đề cột in trên giấy -> khoá JSON. Dùng chung phép gấp dấu của kho."""
    from rulebase.text import ascii_fold  # noqa: PLC0415
    return re.sub(r"[^a-z0-9]+", "_", ascii_fold(text).lower()).strip("_")[:34]


def _table(pairs: list[dict], others: list[dict], kinds: dict,
           width: float, height: float, *, table_id: str = "") -> dict | None:
    """Bảng thành MỘT dãy dòng có kiểu, theo đúng thứ tự đọc trên giấy.

    Bản trước chia bảng ra bốn mảng rời (`columns`, `groups`, `rows`,
    `totals`) và nối chúng bằng so khớp chuỗi nhãn -- hai cụm dòng trùng tên là
    hỏng, và tên cụm bị lưu hai nơi. Ở đây cụm dòng LÀ một dòng trong dãy, nên
    một dòng dữ liệu thuộc cụm nào là chuyện của thứ tự, đúng như mắt người đọc
    tờ giấy.

    Tiêu đề cột có HỘP. Trước đó ô bảng chỉ giữ `value`/`bbox` và tiêu đề cột
    không có mặt ở đâu trong định dạng này -- docstring cũ bảo nó "vẫn còn đủ
    hộp trong `json/`", câu ấy viết khi `json/` còn là bản ghi đầy đủ."""
    if not pairs:
        return None

    # Danh tính một cột là CHỖ NGỒI của nó (`column_index`), không phải cái tên
    # `kie_full` tra ra. Bản trước gộp theo tên, nên hai cột cùng tên `cell`
    # thành một và một trong hai mất sạch ô.
    columns: list[dict] = []
    named: dict[int, str] = {}
    taken: set[str] = set()
    for pair in sorted(pairs, key=lambda p: int(p.get("column_index") or 0)):
        index = int(pair.get("column_index") or 0)
        if index in named:
            continue
        key = _column_key(pair, taken)
        taken.add(key)
        named[index] = key
        columns.append({
            "key": key,
            "type": type_of(column=str(pair.get("column") or "")),
            "index": index,
            "header": _cell(pair.get("key_text"), pair.get("key_bbox"),
                            width, height),
            "path": [str(x) for x in (pair.get("column_path") or [])],
            "description": str(pair.get("description") or ""),
        })

    # Khoảng x của mỗi cột, đo trên chính các ô dữ liệu của nó -- để đặt con số
    # của một dòng tổng vào đúng cột nó nằm dưới. Phép ĐO hình học, không phải
    # phỏng đoán theo chữ. Đo được: 263/264 dòng tổng đặt đúng cột.
    span: dict[str, tuple[float, float]] = {}
    for pair in pairs:
        box = _rect(pair.get("value_bbox"))
        if not box:
            continue
        key = named.get(int(pair.get("column_index") or 0))
        if not key:
            continue
        low, high = span.get(key, (box[0], box[2]))
        span[key] = (min(low, box[0]), max(high, box[2]))

    def column_at(box) -> str | None:
        rect = _rect(box)
        if not rect:
            return None
        middle = (rect[0] + rect[2]) / 2
        for key, (low, high) in span.items():
            if low - 2 <= middle <= high + 2:
                return key
        return None

    rows: list[dict] = []
    body: dict[int, dict] = {}
    for pair in pairs:
        number = int(pair.get("row") or 0)
        box = _rect(pair.get("value_bbox")) or [0.0, 0.0, 0.0, 0.0]
        row = body.setdefault(number, {"kind": "data", "index": number,
                                       "_y": box[1], "cells": {}})
        row["_y"] = min(row["_y"], box[1])
        # Ô không in trên giấy thì KHOÁ VẮNG, không phải một ô rỗng: dựng
        # `{"value": "", "bbox": []}` là khai một thứ không tồn tại, đúng cái
        # `kie_full.py` từ chối làm với hộp khoá. `columns` đã nói đủ bộ cột.
        row["cells"][named.get(int(pair.get("column_index") or 0),
                               str(pair.get("column") or "cell"))] = _cell(
            pair.get("value_text"), pair.get("value_bbox"), width, height)
    rows += list(body.values())

    for pair in others:
        value_kind = kinds.get(pair.get("value_entity_index"), "")
        key_kind = kinds.get(pair.get("key_entity_index"), "")
        box = _rect(pair.get("value_bbox")) or [0.0, 0.0, 0.0, 0.0]
        if value_kind == "colhdr" and pair.get("source") == "implied":
            rows.append({"kind": "group", "_y": box[1],
                         "label": _cell(pair.get("value_text"),
                                        pair.get("value_bbox"), width, height)})
            continue
        kind = ROW_KIND.get(key_kind) or ROW_KIND.get(value_kind)
        if not kind:
            continue
        cell = _cell(pair.get("value_text"), pair.get("value_bbox"), width, height)
        column = column_at(pair.get("value_bbox"))
        row = {"kind": kind, "_y": box[1],
               "label": _cell(pair.get("key_text"), pair.get("key_bbox"),
                              width, height)}
        if column:
            row["cells"] = {column: cell}
        else:
            row["value"] = cell
        rows.append(row)

    rows.sort(key=lambda r: (r.get("_y", 0.0), r.get("index", 0)))
    for row in rows:
        row.pop("_y", None)

    boxes = [c["header"]["bbox"] for c in columns if c["header"]["bbox"]]
    boxes += [c["bbox"] for r in rows for c in (r.get("cells") or {}).values()
              if c["bbox"]]
    table: dict = {"type": "table", "table_id": table_id or "t1",
                   "source": "geometry"}
    if boxes:
        table["bbox"] = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                         max(b[2] for b in boxes), max(b[3] for b in boxes)]
    table["columns"] = columns
    table["rows"] = rows
    return table


def _declared_table(name: str, pairs: list[dict],
                    width: float, height: float) -> dict:
    """Bảng model TỰ KHAI, dựng từ `items[3].qty`.

    Không suy gì: tên bảng, chỉ số dòng và tên cột đều đọc thẳng từ đường dẫn.
    Thứ tự cột là thứ tự XUẤT HIỆN của nó ở dòng đầu -- cùng thứ tự model viết
    ra, và cũng là thứ tự in trên giấy vì nó viết theo chiều ngang.

    Không có `header`: model khai tên MÁY (`unit_price`), không khai chữ trên
    giấy ("Đơn giá (đồng)"). Bảng dựng bằng hình học có chữ ấy. Nối hai bên là
    việc của bộ sinh, không phải của chỗ xuất -- xem docstring đầu file."""
    order: list[str] = []
    body: dict[int, dict] = {}
    for pair in pairs:
        found = ARRAY_PATH.match(str(pair.get("path") or ""))
        if not found:
            continue
        index, column = int(found.group(2)), found.group(3)
        if column not in order:
            order.append(column)
        box = _rect(pair.get("value_bbox")) or [0.0, 0.0, 0.0, 0.0]
        row = body.setdefault(index, {"kind": "data", "index": index,
                                      "_y": box[1], "cells": {}})
        row["_y"] = min(row["_y"], box[1])
        row["cells"][column] = _cell(pair.get("value_text"),
                                     pair.get("value_bbox"), width, height)
    rows = sorted(body.values(), key=lambda r: (r["_y"], r["index"]))
    for row in rows:
        row.pop("_y", None)
    columns = [{"key": column, "type": type_of(column=column), "index": at,
                "header": {"value": "", "bbox": []},
                "path": [f"{name}[].{column}"], "description": ""}
               for at, column in enumerate(order)]
    boxes = [c["bbox"] for r in rows for c in r["cells"].values() if c["bbox"]]
    table: dict = {"type": "table", "table_id": name, "source": "declared"}
    if boxes:
        table["bbox"] = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                         max(b[2] for b in boxes), max(b[3] for b in boxes)]
    table["columns"] = columns
    table["rows"] = rows
    return table


def _mark_kind(kind: str) -> bool:
    return kind in MARK_KINDS or kind.startswith(MARK_PREFIX)


def _marks(pairs: list[dict], kinds: dict,
           width: float, height: float) -> list[dict]:
    """Mực có hộp mà không phải trường: chữ nhà in, con dấu, chữ chìm."""
    out = []
    for pair in sorted(pairs, key=_order):
        kind = kinds.get(pair.get("value_entity_index"), "")
        box = _rect(pair.get("value_bbox"))
        out.append({"kind": kind or "mark",
                    "text": str(pair.get("value_text", "")),
                    "bbox": to_grid(box, width, height) if box else []})
    return out


def _signatures(pairs: list[dict], kinds: dict,
                width: float, height: float) -> list[dict]:
    """Khối chữ ký: chức danh ĐI VỚI tên, theo thứ tự đọc.

    Cặp `family` mà `kie_full` dựng đã nối sẵn `sign.title` với `sign.name` --
    ở đây chỉ gói lại. Chức danh lẻ và tên lẻ vẫn thành khối riêng, mang đúng
    nửa nó có: một tờ bốn chức danh và hai tên là một tờ hai người chưa ký, và
    đoán xem ai khớp ai là đoán."""
    blocks: list[dict] = []
    for pair in sorted(pairs, key=_order):
        value_kind = kinds.get(pair.get("value_entity_index"), "")
        key_kind = kinds.get(pair.get("key_entity_index"), "")
        block: dict = {}
        if key_kind == SIGN_TITLE:
            block["title"] = _cell(pair.get("key_text"), pair.get("key_bbox"),
                                   width, height)
        if value_kind == SIGN_NAME:
            block["name"] = _cell(pair.get("value_text"),
                                  pair.get("value_bbox"), width, height)
        elif value_kind == SIGN_TITLE:
            block["title"] = _cell(pair.get("value_text"),
                                   pair.get("value_bbox"), width, height)
        if block:
            blocks.append(block)
    for at, block in enumerate(blocks, start=1):
        block["index"] = at
        block["signed"] = bool((block.get("name") or {}).get("value"))
    return [{"index": b.pop("index"), **b} for b in blocks]


def is_table_row(pair: dict, kinds: dict) -> bool:
    """Cặp này thuộc về BẢNG chứ không phải một trường của tờ giấy.

    Tiêu đề cụm dòng, dòng cộng nhóm, dòng cộng cuối bảng. Trước đây chúng nằm
    phẳng ngang hàng `doc_title` -- và tệ hơn, cùng một thứ mang hai tên:
    `column_heading` khi nó nằm trên dòng dữ liệu đầu tiên, `row_group` khi
    không. Đo được 52 tờ mang cả hai tên cho cùng một loại thứ. Cả hai đều là
    `kind == "colhdr"`, và đó là thứ dùng để nhận ra chúng."""
    value_kind = kinds.get(pair.get("value_entity_index"), "")
    key_kind = kinds.get(pair.get("key_entity_index"), "")
    if value_kind == "colhdr" and pair.get("source") == "implied":
        return True
    return bool(ROW_KIND.get(key_kind) or ROW_KIND.get(value_kind))


def _split(on_page: list[dict], kinds: dict) -> dict[str, list]:
    """Chia cặp của một trang về đúng chỗ của nó trong hình dạng v2.

    Thứ tự xét là thứ tự ƯU TIÊN, và nó có lý do ở từng bậc:

    1. `marks` trước hết -- chữ nhà in lọt vào qua đường `declared`, và đường
       ấy không đi qua chỗ chặn của `pipeline/kie.py`.
    2. rồi chữ ký, để `sign.name` thôi nằm lẫn trong `fields` mà không kèm
       chức danh của ai.
    3. rồi ô bảng: tự khai trước (có đường dẫn), hình học sau (có tiêu đề).
    4. rồi dòng nhóm / dòng cộng -- chúng thuộc về bảng, không phải về trang.
    5. còn lại mới là trường của tờ giấy."""
    out: dict[str, list] = {"marks": [], "signs": [], "declared": [],
                            "cells": [], "extra": [], "plain": []}
    for pair in on_page:
        value_kind = kinds.get(pair.get("value_entity_index"), "")
        key_kind = kinds.get(pair.get("key_entity_index"), "")
        if _mark_kind(value_kind):
            out["marks"].append(pair)
        elif value_kind in (SIGN_TITLE, SIGN_NAME) or key_kind == SIGN_TITLE:
            out["signs"].append(pair)
        elif pair.get("source") == "table":
            out["cells"].append(pair)
        elif ARRAY_PATH.match(str(pair.get("path") or "")):
            out["declared"].append(pair)
        elif is_table_row(pair, kinds):
            out["extra"].append(pair)
        else:
            out["plain"].append(pair)
    return out


def _tables(bucket: dict[str, list], kinds: dict,
            width: float, height: float) -> list[dict]:
    """Mọi bảng của một trang, mỗi bảng một phần tử. Xem docstring đầu file."""
    tables: list[dict] = []
    arrays: dict[str, list[dict]] = {}
    for pair in bucket["declared"]:
        found = ARRAY_PATH.match(str(pair.get("path") or ""))
        arrays.setdefault(found.group(1), []).append(pair)
    for name in sorted(arrays):
        tables.append(_declared_table(name, arrays[name], width, height))

    groups: dict[str, list[dict]] = {}
    for pair in bucket["cells"]:
        groups.setdefault(str(pair.get("table_id") or "t1"), []).append(pair)
    for name in sorted(groups):
        # Dòng nhóm và dòng cộng chưa mang `table_id` -- chúng đến từ đường
        # `implied`, chỗ không biết nó đứng trong bảng nào. Một trang một bảng
        # thì không có gì để nhầm; nhiều bảng thì chúng về bảng đầu, và đó là
        # phỏng đoán DUY NHẤT còn lại trong hàm này.
        extra = bucket["extra"] if name == min(groups) else []
        table = _table(groups[name], extra, kinds, width, height,
                       table_id=name)
        if table:
            tables.append(table)
    return tables


def document(record: dict, kind: str, *, doc_id: str = "",
             rich: bool = False) -> dict:
    """Một tài liệu, một dict -- đúng hình dạng ở đầu file."""
    sizes = _sizes(record)
    pairs = (record.get("kie") or {}).get("pairs") or []
    kinds = {e.get("entity_index"): str(e.get("kind") or "")
             for e in record.get("entity_annotations") or []}
    by_page: dict[int, list[dict]] = {}
    for pair in pairs:
        by_page.setdefault(int(pair.get("page_number", 1) or 1), []).append(pair)

    pages: list[dict] = []
    for number in sorted(set(by_page) | set(sizes)):
        width, height = sizes.get(number, (0.0, 0.0))
        bucket = _split(by_page.get(number, []), kinds)

        fields: dict[str, dict] = {}
        seen_kind: dict[str, str] = {}
        for pair in sorted(bucket["plain"], key=_order):
            name = str(pair.get("field") or pair.get("column") or "").strip()
            if not name:
                continue
            value_kind = kinds.get(pair.get("value_entity_index"), "")
            value_px = _rect(pair.get("value_bbox"))
            key_px = _rect(pair.get("key_bbox"))
            entry = {
                "value": str(pair.get("value_text", "")),
                "bbox": to_grid(value_px, width, height) if value_px else [],
                "key_text": str(pair.get("key_text", "")),
                "key_bbox": to_grid(key_px, width, height) if key_px else [],
            }
            if rich:
                entry["bbox_px"] = ([int(round(v)) for v in value_px]
                                    if value_px else [])
                entry["key_bbox_px"] = ([int(round(v)) for v in key_px]
                                        if key_px else [])
            # Trường in NHIỀU LẦN trên một tờ: gộp thành `list` khi các lần in
            # cùng `kind`, tách thành hai trường khi khác `kind`.
            #
            # Đo trên 141 tài liệu: 284/308 lượt lặp là cùng kind -- bốn đoạn
            # ghi chú, ba dòng chữ ký. Chúng là MỘT trường in nhiều dòng, và
            # `note_2`/`note_3` là số thứ tự chứ không phải tên; một mô hình
            # học `note_3` là học một thứ tự. 24 lượt còn lại khác kind:
            # `dien_thoai` của bên bán và của bên mua slug ra cùng tên nhưng là
            # hai trường. Phân biệt bằng TỪ VỰNG ĐÓNG, không bằng tên.
            if seen_kind.get(name) == value_kind:
                old = fields[name]
                if old["type"] != "list":
                    keep = [k for k in old if k not in ("type", "description")]
                    fields[name] = {"type": "list", "item_type": old["type"],
                                    "items": [{k: old[k] for k in keep}],
                                    "description": old["description"]}
                fields[name]["items"].append(entry)
                continue
            unique, suffix = name, 2
            while unique in fields:
                unique, suffix = f"{name}_{suffix}", suffix + 1
            seen_kind[unique] = value_kind
            fields[unique] = {"type": type_of(kind=value_kind), **entry,
                              "description": str(pair.get("description", ""))}

        # Bốn khoá LUÔN có mặt, kể cả rỗng: hình dạng cố định là điều kiện để
        # một bộ sinh có ràng buộc đi theo được, và là lý do `pages` đã là mảng.
        pages.append({
            "page": number,
            "size": [int(width), int(height)],
            "fields": fields,
            "tables": _tables(bucket, kinds, width, height),
            "signatures": _signatures(bucket["signs"], kinds, width, height),
            "marks": _marks(bucket["marks"], kinds, width, height),
        })
    # ĐƠN VỊ NÓI RA TRONG CHÍNH TỆP. `bbox` là hệ 1000, `size` là pixel để quy
    # ngược -- thiết kế có chủ ý, ghi ở đầu file này. Nhưng hai khoá cạnh nhau
    # mang hai đơn vị khác nhau mà không chỗ nào trong tệp nói điều đó, và một
    # người đọc thạo việc hiểu nhầm ngay lần đầu: tưởng `bbox` cũng là pixel,
    # rồi vẽ hộp dồn hết vào góc trên trái. Một khoá tám ký tự chặn được cả
    # lớp hiểu nhầm ấy.
    return {"doc_type": kind or None,
            "doc_id": doc_id or None,
            "page_count": len(pages),
            "bbox_unit": "per_mille_of_size", "pages": pages}


def _slots(page: dict) -> int:
    """Số Ô GIÁ TRỊ trên một trang -- thứ có thể đem so với số cặp KIE.

    Đếm khoá cấp trang thì bảng, chữ ký và `marks` biến mất khỏi con số, và
    một bộ mất dữ liệu đọc lên giống hệt một bộ không mất."""
    count = 0
    for entry in (page.get("fields") or {}).values():
        count += (len(entry.get("items") or []) if entry.get("type") == "list"
                  else 1)
    for table in page.get("tables") or []:
        for row in table.get("rows") or []:
            count += len(row.get("cells") or {})
            count += sum(1 for key in ("value", "label") if key in row)
    for block in page.get("signatures") or []:
        count += sum(1 for key in ("title", "name") if key in block)
    return count + len(page.get("marks") or [])


def run(root: Path, out: Path, *, min_pages: int, limit: int,
        with_images: bool, indent: int | None, rich: bool = False,
        by_kind: bool = False) -> int:
    manifest = root / "manifest.jsonl"
    if not manifest.is_file():
        print(f"không có {manifest} — đây có phải thư mục đã sinh xong không?")
        return 1
    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines() if line.strip()]

    documents: dict[str, list[dict]] = {}
    for row in rows:
        documents.setdefault(str(row.get("document") or row["stem"]), []).append(row)

    # TRANG TRƯỢT CỔNG GÁC KHÔNG RA BẢN XUẤT.
    #
    # `synthgen/derive.py` đã lọc `llm_passed_gate` từ trước, nhưng nó lọc cho
    # PHẦN CỦA NÓ -- `markdown/`, `visualize_kie/`, `kie_schemas/`, `sample/`.
    # `export` đọc lại CHÍNH `manifest.jsonl` ấy và không lọc gì, nên `json/`
    # và `index.jsonl` -- thứ người ta thật sự đem đi huấn luyện -- vẫn nhận
    # đủ. Đo trên pilot15: derive giữ 24 trang / 11 loại, export ghi ra 33
    # trang / 15 loại, và 4 trong 5 tài liệu cổng gác đã loại nằm trong đó.
    #
    # Rơi cả TÀI LIỆU khi một tờ trượt, không chỉ rơi tờ ấy: `draw_llm` gác
    # theo tài liệu (`passed` dùng chung cho mọi tờ của một trang HTML), nên
    # một tài liệu có tờ trượt là một tài liệu trượt. Giữ lại các tờ còn lại
    # là phát ra một chứng từ thủng giữa.
    #
    # Mặc định `True` để lượt chạy rulebase -- không có khoá này -- không đổi.
    walked = len(documents)
    documents = {name: group for name, group in documents.items()
                 if all(r.get("llm_passed_gate", True) for r in group)}
    if len(documents) < walked:
        print(f"[export] {walked - len(documents)} tài liệu trượt cổng gác, "
              f"không đưa vào bản xuất")

    chosen = [name for name, group in documents.items()
              if int(group[0].get("pages_in_document", 1) or 1) >= min_pages]
    chosen.sort()
    if limit:
        chosen = chosen[:limit]
    if not chosen:
        print(f"không có tài liệu nào từ {min_pages} tờ trở lên")
        return 1

    # `by_kind`: ghi thẳng vào `json/<loại>/<tài liệu>.json` của CHÍNH lượt
    # chạy, chia ngăn theo loại chứng từ như mọi thư mục khác. Đó là đường mặc
    # định giờ đây: `json/` LÀ định dạng người dùng đọc, và bản ghi đầy đủ từng
    # tờ nằm ở `records/`. Không chép ảnh -- ảnh đã nằm sẵn trong `images/`, và
    # chép lại là nhân đôi 39 GB để không được gì.
    if not by_kind:
        (out / "json").mkdir(parents=True, exist_ok=True)
    if with_images:
        (out / IMAGES).mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    pages = 0
    for name in chosen:
        group = sorted(documents[name],
                       key=lambda r: int(r.get("page_number", 1) or 1))
        kind = str(group[0].get("archetype") or "")
        source = group[0].get("record") or group[0]["json"]
        record = json.loads((root / source).read_text(encoding="utf-8"))
        payload = document(record, kind, doc_id=name, rich=rich)
        target = ((out / "json" / kind / f"{name}.json") if by_kind
                  else (out / "json" / f"{name}.json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
            encoding="utf-8")
        if with_images:
            for row in group:
                source = root / row["images"]
                if source.is_file():
                    shutil.copy2(source, out / IMAGES / Path(row["images"]).name)
        pages += len(group)
        index.append({
            "document": name, "archetype": kind, "pages": len(group),
            # Đếm mọi Ô GIÁ TRỊ, không chỉ khoá cấp trang: từ v2 bảng ra khỏi
            # `fields`, nên đếm khoá là đếm thiếu cả bảng và báo một con số
            # tụt hẳn mà không ai biết vì sao.
            "fields": sum(_slots(pg) for pg in payload["pages"]),
            "json": (f"json/{kind}/{name}.json" if by_kind
                     else f"json/{name}.json"),
            "images": [Path(row["images"]).name for row in group],
        })

    (out / "index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in index),
        encoding="utf-8")
    kinds = len({row["archetype"] for row in index})
    fields = sum(row["fields"] for row in index)
    print(f"[export] {len(index)} tài liệu / {pages} trang / {kinds} loại "
          f"chứng từ -> {out}")
    extra = " + bbox_px/description" if rich else ""
    print(f"[export] {fields} trường, toạ độ hệ {GRID}{extra}")
    spread: dict[int, int] = {}
    for row in index:
        spread[row["pages"]] = spread.get(row["pages"], 0) + 1
    print("[export] số tờ: "
          + ", ".join(f"{n} tờ={k}" for n, k in sorted(spread.items())))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục đã sinh xong")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="thư mục ra; mặc định là <bộ>/documents")
    parser.add_argument("--min-pages", type=int, default=1,
                        help="chỉ lấy tài liệu từ ngần này tờ trở lên; "
                             "mặc định 1 = mọi tài liệu, một tờ hay nhiều tờ")
    parser.add_argument("--rich", action="store_true",
                        help="gắn thêm so_trang, kich_thuoc, bbox_px, description")
    parser.add_argument("--limit", type=int, default=0,
                        help="chỉ lấy N tài liệu đầu -- để thử")
    parser.add_argument("--no-images", action="store_true",
                        help="không chép ảnh sang, chỉ ghi json")
    parser.add_argument("--indent", type=int, default=1)
    args = parser.parse_args()

    root = args.run.resolve()
    out = (args.out or root / "documents").resolve()
    return run(root, out, min_pages=args.min_pages, limit=args.limit,
               with_images=not args.no_images, indent=args.indent or None,
               rich=args.rich)


__all__ = ["EXPORT_NAME", "GRID", "ROW_KIND", "document",
           "is_table_row", "to_grid", "type_of"]


if __name__ == "__main__":
    raise SystemExit(main())
