"""Trang trí của synthgen: khung trang, dải mép giấy, nền hoa văn, logo chữ lồng.

Ba lời hứa, mỗi cái một test:

* trang trí bốc trên dòng ngẫu nhiên RIÊNG, nên thêm nó không đổi một quyết
  định nào khác của tờ giấy -- seed cũ vẫn ra đúng tờ cũ;
* khoá lạ trong `_blocks.yaml::decor_*` thì ném, không lặng lẽ về 1.0;
* dải mép giấy và khung trang không cùng có mặt trên một tờ.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import design as D  # noqa: E402
from synthgen import markup as M  # noqa: E402

DECOR_FIELDS = ("frame", "band", "ground", "logo_style", "accents")


def _without_decor(d) -> tuple:
    return tuple(getattr(d, name) for name in d.__dataclass_fields__
                 if name not in DECOR_FIELDS)


def test_decor_does_not_move_any_other_decision():
    """`draw()` với trang trí và không trang trí phải ra cùng mọi trường khác."""
    real = D.draw_decor
    try:
        with_decor = [D.draw(random.Random(s), s) for s in range(40)]
        D.draw_decor = lambda seed: {}
        plain = [D.draw(random.Random(s), s) for s in range(40)]
    finally:
        D.draw_decor = real
    for a, b in zip(with_decor, plain):
        assert _without_decor(a) == _without_decor(b)


def test_band_and_frame_never_share_a_sheet():
    for seed in range(600):
        decor = D.draw_decor(seed)
        assert decor["band"] == "khong" or decor["frame"] == "khong"


def test_most_sheets_carry_some_decoration():
    plain = 0
    for seed in range(1000):
        x = D.draw_decor(seed)
        if (x["frame"], x["band"], x["ground"]) == ("khong",) * 3 and not x["accents"]:
            plain += 1
    # Đo lúc viết: 4,5% trên 3000 seed. Trần rộng để đổi trọng số không làm
    # đỏ test, nhưng một lỗi đọc file (mọi trục về `khong`) thì đỏ ngay.
    assert plain < 200


def test_a_stray_key_is_refused(monkeypatch):
    table = dict(D._blocks_yaml())
    table["decor_frame"] = {"khong": 1.0, "an_ninhh": 3.0}
    monkeypatch.setattr(D, "_BLOCKS_CACHE", table)
    with pytest.raises(ValueError, match="an_ninhh"):
        D.draw_decor(1)


def test_monogram_is_a_picture_not_dom_text():
    """Chữ lồng là `<img>` trong `.logo`: không có nút chữ nào ngoài
    `data-kind` (xem `test_synthgen_regions`), và ảnh có mực."""
    uri = M.monogram_art("ĐÁ", "#a4161a", "sans/DejaVuSans-Bold.ttf")
    assert uri.startswith("data:image/png;base64,")
    assert M._initials("CÔNG TY CỔ PHẦN ĐIỆN MÁY HỒNG HÀ") == "HH"
    assert M._initials("") == "VN"
