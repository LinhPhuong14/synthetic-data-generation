"""Phôi chứng từ khai bằng FILE, để thứ gì không phải người cũng thêm được.

    from synthgen.archetypes import load, problems, schema
    extra = load()                      # rulebase/synthgen/*.yaml
    print(problems(spec))               # cái gì sai trong một phôi, từng cái một

`synthgen/design.py::ARCHETYPES` là 34 phôi viết thẳng bằng Python. Đó là chỗ
duy nhất quyết "bộ này vẽ được những loại chứng từ nào", và vì nó là mã nguồn
nên **chỉ người sửa mã mới thêm được một loại**. Một model không sửa mã --
ranh giới ấy là cố ý -- nên bao lâu ngữ pháp còn
nằm trong Python thì LLM còn không với tới dáng của bộ sinh này, dù nó đã viết
được bố cục cho pipeline chính từ lâu.

File này mở đường ấy: phôi khai được bằng YAML, `design.py` đọc và GỘP vào
`ARCHETYPES`. Cùng lối `synthgen/phrasing.py` gộp `rulebase/kie_phrasings.json`
-- mất file thì 34 phôi viết tay vẫn chạy, nên đây là thứ làm giàu chứ không
phải thứ bắt buộc.

## Từ vựng đóng, nên phôi khai bằng TÊN

Một phôi không mang `FieldDef` hay hàm nào; nó gọi TÊN những thứ `design.py`
đã định nghĩa:

    fields:  26 khoá trường   (`seller_name`, `buyer_tax`, `dob`, ...)
    columns: 14 khoá cột      (`stt`, `qty`, `vat_rate`, ...)
    blocks:  14 tên khối      (`letterhead`, `table`, `questions`, ...)
    profile: 9 · org_kind: 4 · totals: 3

Nhờ thế một phôi viết sai tên bị bắt ngay lúc nạp, chứ không vẽ ra một tờ giấy
thiếu khối rồi không ai biết.

## Schema SUY RA, không khai

`schema()` đọc chính 34 phôi đang chạy để biết mỗi trường nhận kiểu gì và
những giá trị nào là hợp lệ. Khai tay thì nó cũ đi vào đúng ngày ai đó thêm một
cột, và một schema cũ từ chối một phôi đúng. Cùng lý do
`agent/layout_schema.py` suy schema từ các bố cục đã commit, và
`agent/corpus_rules.py` đo ngưỡng từ chính những dòng người đã viết.

## `problems()` kể HẾT, không dừng ở lỗi đầu

Một model sinh ra mười phôi thì thứ đáng giá là danh sách mười lý do, không
phải cái ngoại lệ đầu tiên. Cùng hình dạng `rulebase/blanks.py::problems`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



def _design():
    """`synthgen.design`, nhập MUỘN.

    Hai module này cần nhau: `design` gọi `load()` ở cuối để gộp phôi khai bằng
    file, còn ở đây cần `design.COLUMNS` và `design.Archetype` để dựng. Nhập ở
    đầu file thì ai nhập `archetypes` TRƯỚC sẽ kéo `design` chạy, `design` lại
    nhập ngược vào một module mới đi được nửa đường -- `ImportError`. Nhập
    muộn thì lúc hàm nào ở đây chạy, `design` đã dựng xong `ARCHETYPES`.
    """
    from synthgen import design  # noqa: PLC0415 -- đúng chỗ, xem docstring

    return design

# Cạnh `rulebase/layouts/` của pipeline chính, và vì cùng một lý do: phôi là
# DỮ LIỆU của bộ sinh, không phải mã của nó, nên nó nằm cùng chỗ với mọi dữ
# liệu khác thay vì lẫn trong package.
ARCHETYPE_DIR = REPO_ROOT / "rulebase" / "synthgen"

# Dòng đầu của một phôi do model viết. Là comment nên `yaml.safe_load` không
# thấy, và mọi bộ đọc sẵn có không đổi -- cùng mẹo `agent/layout_schema.MARK`.
MARK = "# llm-generated"


def _fields_by_key() -> dict[str, Any]:
    """26 `FieldDef` của `design.py`, tra theo khoá."""
    out: dict[str, Any] = {}
    D = _design()
    for name in dir(D):
        if not name.endswith("_FIELDS"):
            continue
        for field in getattr(D, name) or ():
            out.setdefault(field.key, field)
    return out


def schema() -> dict[str, Any]:
    """Mỗi trường của một phôi nhận gì, đọc từ 34 phôi đang chạy."""
    D = _design()
    every = D.ARCHETYPES
    # Từ vựng khối đọc từ `design.BLOCKS` -- MỌI tên khối dựng được -- chứ
    # không từ những khối các phôi hiện có tình cờ dùng. Đọc cách sau thì
    # phôi đầu tiên dùng một khối mới bị từ chối vì chính nó là phôi đầu
    # tiên dùng khối ấy.
    blocks = sorted(D.BLOCKS)
    return {
        "id": {"type": "str", "unique": True},
        "titles": {"type": "list[str]", "min": 1},
        "subtitles": {"type": "list[str]", "min": 1},
        "profile": {"type": "str", "values": sorted({a.profile for a in every})},
        "org_kind": {"type": "str", "values": sorted({a.org_kind for a in every})},
        "national": {"type": "float", "range": [0.0, 1.0]},
        "fields": {"type": "list[str]", "values": sorted(_fields_by_key())},
        "field_span": {"type": "pair[int]"},
        "columns": {"type": "list[list[str]]", "values": sorted(D.COLUMNS)},
        "totals": {"type": "str", "values": sorted({a.totals for a in every})},
        "words": {"type": "bool"},
        # KHÔNG có `min`: `thuc_don` là một tờ thực đơn, không ai ký vào thực
        # đơn, và nó khai `sign_sets` rỗng. Một luật loại bỏ một phôi người đã
        # viết là luật sai, không phải phôi sai -- cùng câu `agent/corpus_rules.py`
        # đặt ra cho corpus. Ràng buộc thật nằm ở dưới: CÓ khối `signatures`
        # thì mới phải có bộ chữ ký.
        "sign_sets": {"type": "list[list[str]]"},
        "notes": {"type": "list[str]", "min": 1},
        "rows": {"type": "pair[int]"},
        # TRẦN SỐ TỜ phôi tự khai. Không khai thì sức chứa khối chảy quyết --
        # đó là hành vi cũ và vẫn đúng cho hầu hết phôi.
        #
        # Có khoá này vì trước đó một phôi KHÔNG CÓ CÁCH NÀO nói "tôi là giấy
        # một trang": `allow:` gắn `clauses`/`sections` theo TÊN, nên một
        # `QUYẾT ĐỊNH` dù ngắn tới đâu cũng với tới mười tờ. Đo trên kho 471
        # phôi: 69% với tới 10+ tờ, còn bậc 2-4 tờ chỉ có 7 phôi.
        "max_pages": {"type": "int"},
        "always": {"type": "list[str]", "values": blocks, "min": 1},
        "optional": {"type": "list[str]", "values": blocks},
        "en_ok": {"type": "bool"},
    }


def _pairs(value: Any) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, int) for v in value))


def problems(spec: dict, *, taken: set[str] | None = None) -> list[str]:
    """Mọi chỗ sai trong một phôi, mỗi chỗ một dòng. Rỗng là dùng được."""
    found: list[str] = []
    rules = schema()
    name = str(spec.get("id", "?"))

    for key in rules:
        if key not in spec and key not in ("optional", "subtitles", "max_pages"):
            found.append(f"{name}: thiếu `{key}`")
    for key in spec:
        if key not in rules:
            found.append(f"{name}: `{key}` không phải trường của một phôi; "
                         f"có {', '.join(sorted(rules))}")

    if taken is not None and name in taken:
        found.append(f"{name}: đã có một phôi mang id ấy")

    for key, rule in rules.items():
        if key not in spec:
            continue
        value = spec[key]
        kind = rule["type"]
        if kind == "bool" and not isinstance(value, bool):
            found.append(f"{name}.{key}: phải là true/false")
        elif kind == "float" and not isinstance(value, (int, float)):
            found.append(f"{name}.{key}: phải là một số")
        elif kind == "int" and not isinstance(value, int):
            found.append(f"{name}.{key}: phải là một số nguyên")
        elif kind == "pair[int]" and not _pairs(value):
            found.append(f"{name}.{key}: phải là hai số nguyên [thấp, cao]")
        elif kind.startswith("list") and not isinstance(value, list):
            found.append(f"{name}.{key}: phải là một danh sách")
        elif kind == "str" and not isinstance(value, str):
            found.append(f"{name}.{key}: phải là một chuỗi")

        allowed = rule.get("values")
        if allowed and isinstance(value, str) and value not in allowed:
            found.append(f"{name}.{key}: {value!r} không có; "
                         f"có {', '.join(allowed)}")
        if allowed and isinstance(value, list):
            flat = [v for item in value
                    for v in (item if isinstance(item, list) else [item])]
            for v in flat:
                if isinstance(v, str) and v not in allowed and kind != "list[list[str]]":
                    found.append(f"{name}.{key}: {v!r} không có; "
                                 f"có {', '.join(allowed)}")
                elif (isinstance(v, str) and v not in allowed
                        and kind == "list[list[str]]" and key == "columns"):
                    found.append(f"{name}.columns: cột {v!r} không có; "
                                 f"có {', '.join(allowed)}")
        if rule.get("min") and isinstance(value, list) and len(value) < rule["min"]:
            found.append(f"{name}.{key}: cần ít nhất {rule['min']} mục")

    # Ràng buộc GIỮA các trường -- schema kiểu không nói được những điều này.
    always = list(spec.get("always") or [])
    optional = list(spec.get("optional") or [])
    both = set(always) & set(optional)
    if both:
        found.append(f"{name}: {sorted(both)} vừa `always` vừa `optional`; "
                     "một khối hoặc luôn có, hoặc thỉnh thoảng")
    if "signatures" in always + optional and not spec.get("sign_sets"):
        found.append(f"{name}: có khối `signatures` mà `sign_sets` rỗng")
    if "table" in always + optional and not spec.get("columns"):
        found.append(f"{name}: có khối `table` mà không khai `columns`")
    # KHÔNG có luật "khối `totals` mà `totals: none`": `thuc_don` khai đúng
    # thế, và `markup._totals` trả rỗng khi không có số nào để cộng -- khối ấy
    # in ra không gì cả, vô hại. Luật thứ hai của tôi loại một phôi người đã
    # viết, lần này vì một điều không có hậu quả nào. Bỏ.
    rows = spec.get("rows")
    if _pairs(rows) and rows[0] > rows[1]:
        found.append(f"{name}.rows: {rows[0]} > {rows[1]}")
    span = spec.get("field_span")
    if _pairs(span) and span[0] > span[1]:
        found.append(f"{name}.field_span: {span[0]} > {span[1]}")
    if _pairs(span) and spec.get("fields") is not None:
        have = len(spec["fields"])
        if span[0] > have:
            found.append(f"{name}.field_span: đòi ít nhất {span[0]} trường mà "
                         f"`fields` chỉ có {have}")
    return found


def build(spec: dict):
    """Một `design.Archetype` từ phôi đã khai. Gọi SAU `problems()`."""
    by_key = _fields_by_key()
    return _design().Archetype(
        id=str(spec["id"]),
        titles=tuple(spec["titles"]),
        subtitles=tuple(spec.get("subtitles") or ("",)),
        profile=str(spec["profile"]),
        org_kind=str(spec["org_kind"]),
        national=float(spec["national"]),
        field_pool=tuple(by_key[k] for k in spec["fields"]),
        field_span=tuple(spec["field_span"]),
        column_pool=tuple(tuple(c) for c in (spec.get("columns") or ())),
        totals=str(spec["totals"]),
        words=bool(spec["words"]),
        sign_sets=tuple(tuple(s) for s in spec["sign_sets"]),
        notes=tuple(spec["notes"]),
        rows=tuple(spec["rows"]),
        max_pages=int(spec.get("max_pages") or 0),
        optional=tuple(spec.get("optional") or ()),
        always=tuple(spec["always"]),
        en_ok=bool(spec["en_ok"]),
    )


def load(directory: Path | None = None) -> tuple[list, list[str]]:
    """`(phôi dựng được, mọi lỗi gặp phải)` từ `rulebase/synthgen/*.yaml`.

    Không ném ngoại lệ: một phôi hỏng không được làm chết cả lượt chạy, nhưng
    cũng không được lặng lẽ biến mất. Người gọi in danh sách lỗi ra."""
    directory = directory or ARCHETYPE_DIR
    if not directory.is_dir():
        return [], []
    taken = {a.id for a in _design().ARCHETYPES}
    out, errors = [], []
    for path in sorted(directory.glob("*.yaml")):
        # Gạch dưới đầu tên = không phải một phôi. `_blocks.yaml` là bảng xác
        # suất khối, đọc ở `design.py`; đọc nó như một phôi thì mỗi lượt chạy
        # in ra một trang lỗi cho một file hoàn toàn đúng. Cùng lệ
        # `rulebase/rules/_order.yaml`.
        if path.name.startswith("_"):
            continue
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            errors.append(f"{path.name}: không đọc được YAML -- {error}")
            continue
        if not isinstance(spec, dict):
            errors.append(f"{path.name}: file phải là một ánh xạ khoá-giá trị")
            continue
        found = problems(spec, taken=taken)
        if found:
            errors.extend(f"{path.name}: {line}" for line in found)
            continue
        try:
            out.append(build(spec))
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{path.name}: dựng không được -- {error}")
            continue
        taken.add(str(spec["id"]))
    return out, errors


def as_spec(arch) -> dict:
    """Chiều ngược: một `Archetype` đang chạy viết thành phôi khai được.

    Để `agent/` đưa được phôi THẬT làm ví dụ cho model, và để kiểm rằng định
    dạng file tả đủ một phôi -- `tests/` cho một phôi đi vòng qua YAML rồi so
    lại với bản gốc."""
    return {
        "id": arch.id,
        "titles": list(arch.titles),
        "subtitles": list(arch.subtitles),
        "profile": arch.profile,
        "org_kind": arch.org_kind,
        "national": arch.national,
        "fields": [f.key for f in arch.field_pool],
        "field_span": list(arch.field_span),
        "columns": [list(c) for c in arch.column_pool],
        "totals": arch.totals,
        "words": arch.words,
        "sign_sets": [list(s) for s in arch.sign_sets],
        "notes": list(arch.notes),
        "rows": list(arch.rows),
        **({"max_pages": arch.max_pages} if arch.max_pages else {}),
        "always": list(arch.always),
        "optional": list(arch.optional),
        "en_ok": arch.en_ok,
    }


__all__ = ["ARCHETYPE_DIR", "MARK", "as_spec", "build", "load", "problems",
           "schema"]
