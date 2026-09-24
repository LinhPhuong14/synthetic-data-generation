"""Tra nghĩa tiếng Anh của một trường, theo QUY TẮC chứ không theo bảng phẳng.

`rulebase/kie_field_glossary.json` là bảng viết tay, khoá theo slug rút ra từ
chữ in trên giấy. Bảng ấy vừa tự chứng minh điểm yếu của mình: trên lượt chạy
200 tờ, 181 slug không có trong bảng — vì slug caption là TỪ VỰNG MỞ. Chữ in ra
là bất cứ tiếng Việt nào tờ giấy muốn, nên không bảng viết tay nào đủ, và mỗi
loại chứng từ mới lại thêm một nắm slug chưa ai viết.

Nên tra hai tầng, và tầng dưới mới là tầng bảo đảm:

  1. SLUG — bảng viết tay, cộng bốn phép chuẩn hoá. Cụ thể nhất khi trúng.
  2. KIND — `data-kind` mà chính `generators/html/sheets/*.py` gắn vào thẻ.
     Đây là TỪ VỰNG ĐÓNG: nó do code sinh, không do chữ in sinh, nên một chứng
     từ mới dùng lại kind cũ. Trên 2220 cặp của lượt chạy ấy, 19 kind phủ 100%.

Bốn phép chuẩn hoá ở tầng 1, mỗi phép trả lời một cách sinh slug có thật:

  hậu tố số   `so_tai_khoan_2` — cùng một chữ in hai lần trên một tờ (hai tài
              khoản ngân hàng). Nghĩa y hệt, chỉ khác lần in.
  bỏ đuôi     `dia_chi_address` — nhãn song ngữ, nửa sau là bản dịch của nửa
              đầu. `so_hop_dong_contract_no` cũng vậy.
  bỏ đầu      `tong_so_tien_bao_hiem` — chữ in dài hơn nhãn chuẩn nhưng phần
              đuôi mới mang nghĩa.
  suất thuế   `thue_8`, `thue_gtgt_5`, `gst_included_10` — con số LÀ suất thuế,
              nên nghĩa sinh ra được chứ không cần một dòng bảng cho mỗi suất.

Tầng 2 không bao giờ trả về rỗng, nên hàm này không có đường thoát về "chép lại
chữ tiếng Việt" — đó đúng là thứ `_fallback_description` làm và là thứ phải bỏ.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parent / "kie_field_glossary.json"

_ORDINAL = {2: "second", 3: "third", 4: "fourth", 5: "fifth"}


def load(path: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """`(theo slug, theo kind)` — hai bảng trong cùng một file."""
    raw = json.loads((path or GLOSSARY_PATH).read_text(encoding="utf-8"))
    by_kind = {k: str(v) for k, v in (raw.get("_by_kind") or {}).items()}
    by_slug = {k: str(v) for k, v in raw.items()
               if not k.startswith("_") and isinstance(v, str)}
    return by_slug, by_kind


def load_paths(path: Path | None = None) -> dict[str, str]:
    """Nửa `data-path` của cùng file -- từ vựng ĐÓNG của không gian đường dẫn.

    Tách khỏi `load()` để hợp đồng hai-giá-trị của nó không đổi: mọi nơi đang
    gọi `load()` vẫn nhận đúng `(theo slug, theo kind)`.

    Khoá viết chỉ số rỗng (`line_items[].name`). `synthgen/field_tier.py` là
    nơi duy nhất chuẩn hoá một đường dẫn thật về hình ấy -- một phép chuẩn hoá
    dựng ở hai chỗ là cách chắc chắn để hai chỗ lệch nhau."""
    raw = json.loads((path or GLOSSARY_PATH).read_text(encoding="utf-8"))
    return {k: str(v) for k, v in (raw.get("_by_path") or {}).items()}


def _rate(field: str) -> str | None:
    """Nghĩa của một trường mang suất thuế trong tên."""
    m = re.match(r"^(thue|thue_gtgt|thue_suat|gst_included|vat)_(\d{1,2})$", field)
    if m:
        return (f"Value added tax charged on this invoice at the {m.group(2)}% rate; "
                f"Vietnamese VAT law sets several rates and each one is totalled "
                f"on its own line.")
    m = re.match(r"^tong_so_tien_thue_gia_tri_gia_tang_(\d{1,2})$", field)
    if m:
        return (f"Total value added tax at the {m.group(1)}% rate across every line "
                f"of the invoice taxed at that rate.")
    m = re.match(r"^hang_hoa_chiu_thue_suat(?:_\d+)?$", field)
    if m:
        return ("Sub-total of the goods and services taxed at one VAT rate, printed "
                "above the tax line that applies to them.")
    return None


def describe(field: str, *, kind: str = "",
             by_slug: dict[str, str] | None = None,
             by_kind: dict[str, str] | None = None) -> tuple[str, str] | None:
    """`(mô tả tiếng Anh, cách tra được)`, hoặc None nếu không tầng nào trả lời."""
    if by_slug is None or by_kind is None:
        loaded_slug, loaded_kind = load()
        by_slug = by_slug if by_slug is not None else loaded_slug
        by_kind = by_kind if by_kind is not None else loaded_kind

    if field in by_slug:
        return by_slug[field], "exact"

    m = re.match(r"^(.*?)_(\d+)$", field)
    if m:
        # Đệ quy: gốc của một lần in lặp cũng được hưởng mọi phép dưới đây.
        base = describe(m.group(1), kind=kind, by_slug=by_slug, by_kind=by_kind)
        if base is not None and base[1] != "kind":
            n = int(m.group(2))
            which = _ORDINAL.get(n, f"{n}th")
            return (f"{base[0]} This is the {which} field on the page carrying "
                    f"that same printed caption."), "repeat"

    rate = _rate(field)
    if rate:
        return rate, "rate"

    # Cắt bớt chỉ hợp lệ khi phần GIỮ LẠI còn mang nghĩa: `dia_chi_address` bỏ
    # `address` là bỏ bản dịch, còn `so_tai_khoan` cắt xuống `so` là đổi hẳn
    # trường — số tài khoản thành số chứng từ. Ngưỡng: giữ ít nhất một nửa số
    # đoạn, và không bao giờ tụt xuống một đoạn khi slug gốc có từ ba đoạn.
    parts = field.split("_")
    floor = max(1, (len(parts) + 1) // 2) if len(parts) < 3 else max(2, len(parts) // 2)
    for cut in range(len(parts) - 1, floor - 1, -1):
        head = "_".join(parts[:cut])
        if head in by_slug:
            return by_slug[head], "tail"
    for cut in range(1, len(parts) - floor + 1):
        tail = "_".join(parts[cut:])
        if tail in by_slug:
            return by_slug[tail], "head"

    if kind and kind in by_kind:
        return by_kind[kind], "kind"
    # Kind cha: `store.account.label` chưa có thì thử `store.account`, rồi `store`.
    while kind and "." in kind:
        kind = kind.rsplit(".", 1)[0]
        if kind in by_kind:
            return by_kind[kind], "kind"
    return None
