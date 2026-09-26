"""Tờ khai sự thật cho MỘT lần điền phôi -- giá trị thật, không gọi model.

    from synthgen.values import facts, flatten, resolve
    tree = facts(random.Random(7), rows=9, signers=2)
    flat = flatten(tree)                  # {"issuer.name": "...", ...}

Pha 2 của đường "model viết phôi" (`docs/duong-sinh-phoi.md`). Phôi nói CHỖ
NÀO in gì bằng `{{issuer.tax_code}}`; file này trả lời in GÌ, và nó trả lời
bằng đúng những bộ sinh mà nhánh luật (`synthgen/content.py`,
`synthgen/corpus.py`, `rulebase/corpus/vi/`) vẫn dùng cho mọi tờ giấy khác.
Không có kho chữ thứ hai: một cái tên công ty ra từ đây và một cái tên công ty
ra từ `rulebase/` phải là cùng một phân bố, nếu không hai nửa bộ dữ liệu dạy
mô hình hai thứ khác nhau.

## Một TỜ KHAI, không phải sáu mươi lần bốc rời

`facts()` dựng một cây: một bên phát hành, một bên nhận, một tài liệu, N dòng
hàng, M người ký. Mọi chỗ trống đọc ô của cây ấy. Ba cái được:

* `issuer.name` và `issuer.tax_code` thuộc CÙNG một tổ chức. Bốc rời từng
  trường là cách bản trước của `content.address()` in ra "An Hải Bắc, Vũng
  Tàu" -- một phường Đà Nẵng trong một thành phố khác.
* Hai chỗ cùng `{{issuer.name}}` in ra cùng một chữ, nên luật "cùng đường dẫn
  thì cùng giá trị" của `synthgen/llm_page.py::problems()` đúng theo cấu tạo.
  Đo trên `data/pilot16`: 15 tờ trượt cổng đúng vì luật ấy khi model tự viết.
* Số học của bảng đóng kín ở một chỗ: `amount = qty × unit_price`, `vat_amount
  = amount × vat_rate/100`, tổng là tổng cột. `synthgen/check.py` kiểm đúng
  phép ấy trên cả kho.

## Tra theo LÁ, không theo đường dẫn đầy đủ

`_LEAF` khoá trên đoạn cuối (`phone`, `email`, `tax_code`), không trên
`issuer.phone`. Nên một khoá mới trong sổ đăng ký mà lá đã biết --
`supplier.phone`, `payer.email` -- chạy được ngay, không ai phải sửa file này.
`_FAMILY_LEAF` chỉ ghi những chỗ HỌ THẬT SỰ đổi câu trả lời: `name` của
`issuer.` là một tổ chức, của `signers[].` là một con người, của
`line_items[].` là một món hàng.

## Lá chưa biết thì KÊU, không đoán

`missing_paths()` liệt kê mọi khoá trong sổ đăng ký mà file này không sinh
được, và `tests/test_values.py` bắt nó phải rỗng. Đây là chỗ AGENTS.md mục 5
và mục 6 gặp nhau: một bảng tra là thứ khoá thứ 61 sẽ thiếu khỏi, **im lặng**
-- trừ khi có một phép kiểm biến sự im lặng ấy thành một test đỏ. Không có
nhánh mặc định trả chuỗi rỗng, và đặc biệt không có nhánh "lấy lá gần giống
nhất": một `customer.dod` nhận giá trị của `customer.dob` là một tờ giấy
đúng pixel, đọc trôi chảy, và sai nghĩa -- cùng lỗi kép mà
`synthgen/field_tier.py` đã từ chối phép ánh xạ gần đúng để tránh.
"""

from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rulebase.text import money  # noqa: E402
from synthgen import content as C  # noqa: E402
from synthgen import corpus  # noqa: E402

# Ngày mốc của kho, cùng con số `content.a_date()` dùng. Một mốc riêng ở đây
# là hai lịch cho cùng một bộ dữ liệu.
TODAY = dt.date(2026, 9, 10)

CURRENCIES = ("VND", "VND", "VND", "VNĐ", "đồng")
UNITS = ("Cái", "Chiếc", "Bộ", "Hộp", "Thùng", "Kg", "Lít", "Mét", "Gói",
         "Tấm", "Đôi", "Lần", "Suất", "Ngày công", "Tháng")
STATUSES = ("Đã giao", "Chờ giao", "Đã thanh toán", "Còn nợ", "Đã duyệt",
            "Chờ duyệt", "Đang xử lý", "Hoàn thành", "Đã huỷ")
ITEM_TYPES = ("Hàng hoá", "Dịch vụ", "Vật tư", "Thiết bị", "Nguyên liệu",
              "Công cụ", "Phụ tùng", "Văn phòng phẩm")
SIGNER_ROLES = ("Bên A", "Bên B", "Bên giao", "Bên nhận", "Bên bán",
                "Bên mua", "Đại diện đơn vị", "Người lập biểu",
                "Người nộp tiền", "Người kiểm tra")
SIGNER_TITLES = ("NGƯỜI LẬP BIỂU", "KẾ TOÁN TRƯỞNG", "GIÁM ĐỐC",
                 "THỦ TRƯỞNG ĐƠN VỊ", "NGƯỜI NỘP TIỀN", "NGƯỜI NHẬN",
                 "TRƯỞNG PHÒNG", "NGƯỜI KIỂM TRA", "CHỦ TỊCH HỘI ĐỒNG")
SIGNER_NOTES = ("(Ký, ghi rõ họ tên)", "(Ký, đóng dấu)",
                "(Ký, ghi rõ họ tên và đóng dấu)", "(Ký tên)",
                "(Đã ký)", "")
OCCUPATIONS = ("Công nhân", "Giáo viên", "Kỹ sư", "Nhân viên văn phòng",
               "Kinh doanh tự do", "Lái xe", "Y tá", "Kế toán", "Nông dân",
               "Sinh viên", "Hưu trí", "Nội trợ", "Thợ điện", "Bảo vệ")
FORM_CODES = ("01-VT", "02-TT", "C30-BB", "01/GTGT", "S02-DN", "03-TSCĐ",
              "MS-01", "BM.01", "02-VT", "01b-TT", "C41-BB", "05-TNCN")
REFERENCE_KINDS = ("QĐ", "CV", "TB", "HĐ", "BB", "TTr", "KH")


# ------------------------------------------------------------- bộ sinh theo lá

def _org_name(rng: random.Random, ctx: dict) -> str:
    return C._gen("org_name", rng, ctx["date"])


def _person(rng: random.Random, ctx: dict) -> str:
    return C._gen("person", rng, ctx["date"])


def _address(rng: random.Random, ctx: dict) -> str:
    return C.address(rng)


def _tax_code(rng: random.Random, ctx: dict) -> str:
    return C.tax_code(rng)


def _phone(rng: random.Random, ctx: dict) -> str:
    return C.phone(rng)


def _email(rng: random.Random, ctx: dict) -> str:
    return C.email(rng)


def _website(rng: random.Random, ctx: dict) -> str:
    # Tên miền dựng TỪ tên tổ chức đã bốc, không bốc rời: một website
    # `sontung.com.vn` trên giấy của "Công ty TNHH Minh Phát" là chi tiết mà
    # người đọc nhãn thấy ngay còn máy thì không.
    stem = _ascii_stem(ctx.get("org") or "congty")
    return f"www.{stem[:18]}.com.vn"


def _bank(rng: random.Random, ctx: dict) -> str:
    return rng.choice(C.BANKS)


def _account(rng: random.Random, ctx: dict) -> str:
    return "".join(str(rng.randrange(10))
                   for _ in range(rng.choice((10, 12, 13, 14))))


def _org_code(rng: random.Random, ctx: dict) -> str:
    stem = _ascii_stem(ctx.get("org") or "dv").upper()
    return f"{stem[:4]}{rng.randrange(10, 99)}"


def _branch(rng: random.Random, ctx: dict) -> str:
    return f"Chi nhánh {rng.choice(C.CITIES)}"


def _superior(rng: random.Random, ctx: dict) -> str:
    return f"{rng.choice(C.ISSUERS)} {rng.choice(C.CITIES)}"


def _position(rng: random.Random, ctx: dict) -> str:
    return rng.choice(C.POSITIONS)


def _gender(rng: random.Random, ctx: dict) -> str:
    return rng.choice(C.GENDERS)


def _dob(rng: random.Random, ctx: dict) -> str:
    return C._gen("birthdate", rng, ctx["date"])


def _id_number(rng: random.Random, ctx: dict) -> str:
    return C._gen("id_number", rng, ctx["date"])


def _occupation(rng: random.Random, ctx: dict) -> str:
    return rng.choice(OCCUPATIONS)


def _a_date(rng: random.Random, ctx: dict) -> str:
    return C.fmt_date(C.a_date(rng, ctx["date"], 400), rng.choice((0, 0, 2)))


def _ascii_stem(name: str) -> str:
    """Tên tổ chức -> chuỗi ascii chữ thường, để dựng tên miền và mã đơn vị."""
    import re  # noqa: PLC0415
    import unicodedata  # noqa: PLC0415

    plain = unicodedata.normalize("NFD", str(name).lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    plain = plain.replace("đ", "d")
    words = re.sub(r"[^a-z0-9\s]", " ", plain).split()
    # Bỏ những chữ mọi công ty đều có: `cong ty tnhh minh phat` -> `minhphat`.
    skip = {"cong", "ty", "tnhh", "cp", "co", "phan", "doanh", "nghiep",
            "mtv", "thuong", "mai", "dich", "vu", "san", "xuat"}
    keep = [w for w in words if w not in skip] or words or ["donvi"]
    return "".join(keep)


# HỌ ĐỔI CÂU TRẢ LỜI. Chỉ những lá mà nó thật sự đổi -- xem docstring module.
_FAMILY_LEAF = {
    ("issuer", "name"): _org_name,
    ("issuer", "code"): _org_code,
    ("signers", "name"): _person,
    ("signers", "title"): lambda rng, ctx: rng.choice(SIGNER_TITLES),
    ("signers", "role"): lambda rng, ctx: rng.choice(SIGNER_ROLES),
    ("signers", "note"): lambda rng, ctx: rng.choice(SIGNER_NOTES),
    ("signers", "place"): lambda rng, ctx: rng.choice(C.CITIES),
    ("document", "title"): lambda rng, ctx: ctx.get("title") or "BIÊN BẢN",
    ("document", "subtitle"): lambda rng, ctx: ctx.get("subtitle") or "",
    ("document", "code"): lambda rng, ctx: rng.choice(FORM_CODES),
    ("document", "number"): lambda rng, ctx: C._gen("record_no", rng, ctx["date"]),
    ("document", "location"): lambda rng, ctx: rng.choice(C.CITIES),
    ("line_items", "name"): lambda rng, ctx: ctx["row"]["name"],
    ("line_items", "code"): lambda rng, ctx: ctx["row"]["code"],
    ("line_items", "id"): lambda rng, ctx: ctx["row"]["code"],
    ("line_items", "note"): lambda rng, ctx: ctx["row"]["note"],
    ("line_items", "date"): _a_date,
    ("line_items", "type"): lambda rng, ctx: rng.choice(ITEM_TYPES),
    ("clauses", "number"): lambda rng, ctx: ctx["row"]["number"],
    ("clauses", "head"): lambda rng, ctx: ctx["row"]["head"],
    ("clauses", "body"): lambda rng, ctx: ctx["row"]["body"],
}

# LÁ, độc lập với họ. Một khoá mới mang lá đã có ở đây chạy được ngay.
_LEAF = {
    "name": _person,
    "address": _address,
    "tax_code": _tax_code,
    "phone": _phone,
    "email": _email,
    "website": _website,
    "bank": _bank,
    "account": _account,
    "branch": _branch,
    "superior": _superior,
    "code": _org_code,
    "position": _position,
    "gender": _gender,
    "dob": _dob,
    "id_number": _id_number,
    "occupation": _occupation,
    "employer": _org_name,
    "representative": _person,
    "date": _a_date,
    "issue_date": _a_date,
    "effective_date": _a_date,
    "expiry_date": _a_date,
    "period": lambda rng, ctx: C._gen("period", rng, ctx["date"]),
    "currency": lambda rng, ctx: rng.choice(CURRENCIES),
    "reference_number": lambda rng, ctx: (
        f"{rng.randrange(10, 999)}/{rng.choice(REFERENCE_KINDS)}-"
        f"{_ascii_stem(ctx.get('org') or 'dv')[:4].upper()}"),
    "title": lambda rng, ctx: rng.choice(SIGNER_TITLES),
    "subtitle": lambda rng, ctx: ctx.get("subtitle") or "",
    "note": lambda rng, ctx: rng.choice(SIGNER_NOTES),
    "role": lambda rng, ctx: rng.choice(SIGNER_ROLES),
    "place": lambda rng, ctx: rng.choice(C.CITIES),
    "number": lambda rng, ctx: C._gen("record_no", rng, ctx["date"]),
    "description": lambda rng, ctx: ctx["row"]["description"],
    "status": lambda rng, ctx: rng.choice(STATUSES),
    "ref": lambda rng, ctx: (
        f"{rng.randrange(10, 999)}/{rng.choice(REFERENCE_KINDS)}"),
    "stt": lambda rng, ctx: ctx["row"]["stt"],
    "unit": lambda rng, ctx: ctx["row"]["unit"],
    "qty": lambda rng, ctx: ctx["row"]["qty"],
    "unit_price": lambda rng, ctx: ctx["row"]["unit_price"],
    "amount": lambda rng, ctx: ctx["row"]["amount"],
    "vat_rate": lambda rng, ctx: ctx["row"]["vat_rate"],
    "vat_amount": lambda rng, ctx: ctx["row"]["vat_amount"],
    "head": lambda rng, ctx: ctx["row"]["head"],
    "body": lambda rng, ctx: ctx["row"]["body"],
}


def generator(path: str):
    """Bộ sinh cho MỘT đường dẫn, hoặc `None`. Không có nhánh lùi nào."""
    family, _, leaf = str(path).replace("[]", "").partition(".")
    if not leaf:
        return None
    leaf = leaf.rsplit(".", 1)[-1]
    return _FAMILY_LEAF.get((family, leaf)) or _LEAF.get(leaf)


def missing_paths(known=None) -> list[str]:
    """Khoá trong sổ đăng ký mà file này KHÔNG sinh được. Test bắt phải rỗng.

    Đây là chỗ biến một lỗ hổng im lặng thành một test đỏ -- xem docstring
    module. `known` truyền vào được để test không phải dựng sổ (dựng sổ gọi
    `llm_page.kinds()`, thứ cần `cv2`)."""
    if known is None:
        from synthgen import field_tier as FT  # noqa: PLC0415
        known = FT.closed_enum(FT.PATH)
    return sorted(p for p in known if generator(p) is None)


# ------------------------------------------------------------ tờ khai sự thật

def _rows(rng: random.Random, count: int, date: dt.date) -> list[dict]:
    """`count` dòng hàng, số học đóng kín.

    Kho hàng lấy từ `synthgen/corpus.py::catalogue` -- cùng file `rulebase/
    corpus/vi/` mà nhánh luật đọc. Dòng thiếu khoảng giá bị `priced()` bỏ từ
    đầu, nên không dòng nào có giá bịa."""
    pool = (corpus.catalogue("invoice") or corpus.catalogue("market")
            or (("Hàng hoá", 10000, 900000),))
    picked = corpus.sample(rng, list(pool), count) if count else []
    out: list[dict] = []
    for i, entry in enumerate(picked):
        name, lo, hi = entry[0], int(entry[1]), int(entry[2])
        unit_price = int(round(rng.uniform(lo, hi) / 1000.0)) * 1000 or 1000
        qty = rng.randrange(1, 26)
        amount = unit_price * qty
        vat_rate = rng.choice((0, 5, 8, 10, 10))
        # `//100` chứ không `round(... /100)`: thuế trên hoá đơn Việt Nam cắt
        # xuống đồng, và một phép làm tròn lên lệch 1 đồng ở cột tổng là thứ
        # `synthgen/check.py` bắt được còn người đọc thì không.
        vat_amount = amount * vat_rate // 100
        out.append({
            "stt": str(i + 1),
            "name": name,
            "code": f"{_ascii_stem(name)[:3].upper()}{rng.randrange(100, 999)}",
            "unit": rng.choice(UNITS),
            "qty": money(qty, suffix=""),
            "unit_price": money(unit_price, suffix=""),
            "amount": money(amount, suffix=""),
            "vat_rate": f"{vat_rate}%",
            "vat_amount": money(vat_amount, suffix=""),
            "description": f"{name} -- quy cách {rng.randrange(1, 60)} "
                           f"{rng.choice(('kg', 'lít', 'cái', 'hộp'))}/đơn vị",
            "note": rng.choice(("", "", "", "Đã kiểm", "Giao đủ", "Chờ bổ sung")),
            # SỐ NGUYÊN giữ nguyên cạnh bản đã định dạng: `agent/compose_page.
            # py::arithmetic` và `synthgen/check.py` kiểm `qty × unit_price ==
            # amount`, và phân tích ngược chuỗi "1.250.000" để lấy lại số là
            # một phép đoán dấu phân cách mà không ai cần phải đoán.
            "_qty": qty, "_unit_price": unit_price, "_amount": amount,
            "_vat_amount": vat_amount,
        })
    return out


def _clauses(rng: random.Random, count: int) -> list[dict]:
    pool = corpus.clauses("contract") or ()
    out = []
    for i in range(count):
        entry = list(pool[rng.randrange(len(pool))]) if pool else []
        head = entry[0] if entry else "Điều khoản chung"
        body = entry[1] if len(entry) > 1 else (
            "Hai bên cam kết thực hiện đúng các nội dung đã thoả thuận.")
        out.append({"number": f"Điều {i + 1}", "head": head, "body": body})
    return out


def facts(rng: random.Random, *, rows: int = 8, signers: int = 2,
          clauses: int = 0, date: dt.date | None = None,
          overrides: dict | None = None) -> dict:
    """Cây sự thật cho MỘT tờ giấy.

    `overrides` là bảng phẳng ghi đè SAU khi cây đã dựng -- chỗ để phôi áp
    tiêu đề của chính nó (`document.title`) thay vì để bộ sinh bốc một cái
    tên chẳng liên quan gì tới tờ giấy nó vẽ."""
    date = date or C.a_date(rng, TODAY, 700)
    org = _org_name(rng, {"date": date})
    ctx_base = {"date": date, "org": org,
                "title": (overrides or {}).get("document.title", ""),
                "subtitle": (overrides or {}).get("document.subtitle", "")}

    tree: dict = {
        "issuer": _block(rng, "issuer", ctx_base, org=org),
        "customer": _block(rng, "customer", ctx_base),
        "document": _block(rng, "document", ctx_base),
        "line_items": [],
        "signers": [],
        "clauses": [],
    }
    tree["issuer"]["name"] = org

    for row in _rows(rng, rows, date):
        ctx = dict(ctx_base, row=row)
        tree["line_items"].append(_block(rng, "line_items", ctx, row=row))
    for row in _clauses(rng, clauses):
        ctx = dict(ctx_base, row=row)
        tree["clauses"].append(_block(rng, "clauses", ctx, row=row))
    for _ in range(signers):
        tree["signers"].append(_block(rng, "signers", ctx_base))

    # Số thô của bảng, để bản ghi mang được phép kiểm số học mà không phải
    # phân tích ngược chuỗi đã định dạng.
    tree["_rows"] = [{"name": r["name"], "unit": r["unit"],
                      "qty": r["_qty"], "unit_price": r["_unit_price"],
                      "amount": r["_amount"]}
                     for r in _rows_of(tree)]
    for key, value in (overrides or {}).items():
        _set(tree, key, value)
    return tree


def _rows_of(tree: dict) -> list[dict]:
    return [r for r in tree.get("line_items") or [] if "_qty" in r]


def _block(rng: random.Random, family: str, ctx: dict, *, org: str = "",
           row: dict | None = None) -> dict:
    """Mọi lá mà sổ đăng ký biết cho họ này, sinh một lượt.

    Sinh HẾT chứ không sinh theo yêu cầu của phôi: một tờ khai đầy đủ thì hai
    phôi khác nhau điền từ cùng một tờ khai ra cùng một tổ chức, và bản ghi
    `declared/` giữ được cả những trường phôi không in ra -- chúng là
    hard-negative sẵn có cho bước sau."""
    from synthgen import field_tier as FT  # noqa: PLC0415

    out: dict = {}
    if row is not None:
        out.update({k: v for k, v in row.items() if k.startswith("_")})
    prefix = f"{family}[]." if family in _LIST_FAMILIES else f"{family}."
    for key in FT.closed_enum(FT.PATH):
        if not key.startswith(prefix):
            continue
        leaf = key[len(prefix):]
        gen = generator(key)
        if gen is None:
            continue                          # `missing_paths()` là chỗ kêu
        out[leaf] = str(gen(rng, dict(ctx, org=org or ctx.get("org") or "",
                                      row=row or {})))
    return out


_LIST_FAMILIES = frozenset({"line_items", "signers", "clauses"})


def resolve(tree: dict, path: str) -> tuple[bool, str]:
    """`(tìm thấy?, giá trị)` cho một đường dẫn ĐÃ BUNG (`line_items[2].name`).

    Không có nhánh lùi: không tìm thấy thì `False`, và người gọi quyết định.
    Cùng lẽ `field_tier.Registry.describe` đã viết ra."""
    node: object = tree
    for step in str(path).split("."):
        name, _, idx = step.partition("[")
        if not isinstance(node, dict) or name not in node:
            return False, ""
        node = node[name]
        if idx:
            try:
                at = int(idx.rstrip("]"))
            except ValueError:
                return False, ""
            if not isinstance(node, list) or not 0 <= at < len(node):
                return False, ""
            node = node[at]
    return (True, str(node)) if not isinstance(node, (dict, list)) else (False, "")


def _set(tree: dict, path: str, value) -> None:
    node: object = tree
    steps = str(path).split(".")
    for step in steps[:-1]:
        name, _, idx = step.partition("[")
        if not isinstance(node, dict) or name not in node:
            return
        node = node[name]
        if idx:
            try:
                at = int(idx.rstrip("]"))
            except ValueError:
                return
            if not isinstance(node, list) or not 0 <= at < len(node):
                return
            node = node[at]
    if isinstance(node, dict):
        node[steps[-1].partition("[")[0]] = value


def flatten(tree: dict) -> dict:
    """Cây -> bảng phẳng `{"line_items[0].name": "...", ...}`.

    Khoá bắt đầu bằng `_` bị bỏ: chúng là số thô cho phép kiểm số học, không
    phải trường in lên giấy, và một `{{line_items[0]._qty}}` không tồn tại
    trong sổ đăng ký nên không phôi nào xin được nó."""
    flat: dict = {}

    def walk(node, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).startswith("_"):
                    continue
                walk(value, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{prefix}[{i}]")
        else:
            flat[prefix] = str(node)

    walk(tree, "")
    return flat


__all__ = ["TODAY", "facts", "flatten", "generator", "missing_paths", "resolve"]
