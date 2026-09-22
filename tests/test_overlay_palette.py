"""Bảng màu của `synthgen/overlay.py`: đo, chứ không nhìn.

Tấm ảnh hộp nhãn sinh ra để trả lời một câu bằng MẮT -- hộp nào ôm chữ nào,
hộp nào là khoá hộp nào là giá trị. Câu ấy chỉ trả lời được nếu hai lớp khác
nhau ra hai màu MẮT tách được. Mà "mắt tách được" thì không ai mở hai mươi mốt
tấm ảnh ra kiểm mỗi lần sửa, nên nó phải thành một con số ở đây.

Con số ấy là dE trong CIE-Lab: khoảng cách giữa hai màu đo theo thước xấp xỉ
cái mắt thấy. Bản trước trải đều sắc độ và tụt xuống dE 8,4 -- ba lớp ra hồng,
ba lớp ra lam -- mà không một test nào đỏ. Đó là lý do file này tồn tại: cái
hỏng ở đấy không phải một ngoại lệ ném ra, nó là một tấm ảnh vẫn ghi được, vẫn
mở được, và không trả lời được câu nó sinh ra để trả lời.

Không test giá trị màu cụ thể. Màu nào là màu nào là việc của thuật toán chọn;
thứ phải giữ là TÍNH CHẤT -- xa nhau, đủ tương phản, và giống nhau giữa các
lượt chạy.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy", reason="overlay.py imports numpy")
pytest.importorskip("cv2", reason="overlay.py imports OpenCV")

import numpy as np                                              # noqa: E402

from pipeline.record import DOCSYNTH_LABELS                      # noqa: E402
from synthgen import overlay as O                                # noqa: E402

# Sàn dE. Bảng màu hiện tại đo được 34,1 giữa hai lớp gần nhau nhất và 35,3
# giữa một lớp với màu vai trò KIE gần nhất. Sàn đặt ở 25 để còn chỗ cho
# `DOCSYNTH_LABELS` dài thêm vài nhãn -- càng nhiều nhãn thì càng chật -- mà
# vẫn đỏ ngay nếu ai đó quay về lối trải đều sắc độ (8,4).
FLOOR = 25.0

# Sàn tỉ số tương phản của chữ trên nhãn. 4,3:1 là mức TỆ NHẤT có thể có khi
# đã chọn đen hay trắng theo cái nào hơn: hai tỉ số ấy cắt nhau ở đó. Nên test
# này đỏ chỉ khi `_ink_on` chọn sai bên, không phải khi bảng màu đổi.
CONTRAST_FLOOR = 4.3


def dE(left, right) -> np.ndarray:
    """Ma trận khoảng cách Lab giữa hai danh sách màu BGR."""
    a, b = O._lab(left), O._lab(right)
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def test_every_label_in_the_record_vocabulary_has_a_colour():
    """Không nhãn nào rơi vào `OTHER`.

    `OTHER` là màu của "kho này chưa biết lớp đó". Một nhãn có trong
    `DOCSYNTH_LABELS` mà vẫn ra xám nghĩa là bảng màu đã tụt lại sau bảng
    nhãn -- đúng cái mà lối dựng bảng từ chính `DOCSYNTH_LABELS` sinh ra để
    không bao giờ xảy ra nữa."""
    assert set(O.CLASS_COLOURS) == set(DOCSYNTH_LABELS)
    assert O.OTHER not in set(O.CLASS_COLOURS.values())


def test_no_two_layout_classes_wear_colours_the_eye_reads_as_one():
    names = sorted(O.CLASS_COLOURS)
    colours = [O.CLASS_COLOURS[name] for name in names]
    grid = dE(colours, colours)
    np.fill_diagonal(grid, np.inf)
    i, j = np.unravel_index(int(np.argmin(grid)), grid.shape)
    assert grid[i, j] >= FLOOR, (
        f"{names[i]} và {names[j]} chỉ cách nhau dE {grid[i, j]:.1f}")


def test_no_layout_class_wears_a_kie_role_colour():
    """Màu khung nói được mình thuộc lớp ảnh nào, không cần đọc tên thư mục.

    `words()` và `kie()` dùng cam cho khoá, lam cho giá trị. Một lớp bố cục
    trùng vào đấy là một tấm `layout_boxes/` trông như một tấm
    `visualize_kie/`."""
    roles = [O.KEY_COLOUR, O.VALUE_COLOUR, O.PLAIN_COLOUR, O.LINK_COLOUR]
    assert dE(list(O.CLASS_COLOURS.values()), roles).min() >= FLOOR


def test_no_frame_colour_hides_in_the_paper_or_in_the_ink():
    """Giấy trắng và mực đen cũng là hai màu phải tránh.

    Một khung vàng chanh là một màu riêng theo mọi phép đo, và vẫn vô hình
    trên trang."""
    everything = list(O.CLASS_COLOURS.values()) + [
        O.KEY_COLOUR, O.VALUE_COLOUR, O.PLAIN_COLOUR, O.LINK_COLOUR, O.OTHER]
    assert dE(everything, [O.PAPER, O.INK]).min() >= FLOOR


def test_the_same_labels_always_get_the_same_colours():
    """Hai lượt chạy cách nhau một tuần vẫn so được bằng mắt."""
    assert O._palette() == O.CLASS_COLOURS == O._palette()


def test_adding_a_label_leaves_the_labels_before_it_alone():
    """Thêm nhãn thì chỉ các nhãn sắp SAU nó đổi màu.

    Lối trải đều sắc độ chia vòng màu cho tổng số nhãn, nên thêm một nhãn là
    đổi cả hai mươi mốt màu và mọi ảnh đã chụp thành vô dụng để so. Lối
    xa-nhất-trước thì màu thứ k chỉ phụ thuộc k-1 màu trước nó."""
    grown = sorted(set(DOCSYNTH_LABELS) | {"Zebra-Crossing"})
    before = [O.CLASS_COLOURS[name] for name in sorted(DOCSYNTH_LABELS)]
    after = _palette_for(grown)
    keep = [after[name] for name in sorted(DOCSYNTH_LABELS)]
    assert keep[:len(before)] == before


def _palette_for(names: list[str]) -> dict[str, tuple[int, int, int]]:
    """`_palette()` nhưng trên một danh sách nhãn tự đặt.

    Chép đúng vòng lặp của `_palette` chứ không vá `DOCSYNTH_LABELS`: vá một
    frozenset ở module khác trong lúc test thì cái đỏ lên sau đó không nói
    được là lỗi của bảng màu hay của bản vá."""
    grid = O._candidates()
    lab = O._lab(grid)
    taken = O._lab([O.PAPER, O.INK, O.OTHER, O.KEY_COLOUR, O.VALUE_COLOUR,
                    O.PLAIN_COLOUR, O.LINK_COLOUR])
    out = {}
    for name in sorted(names):
        far = np.linalg.norm(lab[:, None, :] - taken[None, :, :], axis=2).min(axis=1)
        pick = int(np.argmax(far))
        out[name] = tuple(int(c) for c in grid[pick])
        taken = np.vstack([taken, lab[pick]])
    return out


def test_tag_text_is_readable_on_every_chip_it_sits_on():
    """Chữ trên nhãn chọn đen hay trắng theo TỈ SỐ, không theo ngưỡng.

    Ngưỡng độ chói sai đúng ở màu bão hoà: `Bibliography` #0bc30b chói 119
    trên 255 nên mọi ngưỡng hợp lý trả về chữ trắng, mà trắng trên lục ấy chỉ
    được 2,4:1."""
    def luminance(bgr) -> float:
        out = []
        for raw in (bgr[2], bgr[1], bgr[0]):
            value = raw / 255.0
            out.append(value / 12.92 if value <= 0.04045
                       else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    chips = list(O.CLASS_COLOURS.items()) + [
        ("key", O.KEY_COLOUR), ("value", O.VALUE_COLOUR), ("other", O.OTHER)]
    for name, chip in chips:
        pair = sorted([luminance(chip), luminance(O._ink_on(chip))])
        ratio = (pair[1] + 0.05) / (pair[0] + 0.05)
        assert ratio >= CONTRAST_FLOOR, f"{name}: chữ trên nhãn chỉ {ratio:.2f}:1"


def test_a_region_covering_the_page_washes_fainter_than_a_small_one():
    """Diện tích càng lớn, lớp tô càng nhạt.

    Một `Watermark` phủ kín trang mà tô cùng một mức với một `Title` cao bốn
    mươi pixel thì nó nhuộm màu mọi vùng nằm dưới, và bản thân nó không nói
    thêm được gì -- vùng ấy vốn đã là cả trang."""
    page = np.full((400, 300, 3), 255, np.uint8)
    whole = [{"bbox": [0, 0, 300, 400], "layout_class": "Text"}]
    small = [{"bbox": [0, 0, 60, 40], "layout_class": "Text"}]
    # Đo ở giữa vùng, chỗ chỉ có lớp tô -- không dính khung, không dính nhãn.
    covered = O.layout(page, whole)[200, 150]
    tight = O.layout(page, small)[20, 30]
    assert np.abs(covered.astype(int) - 255).sum() < np.abs(tight.astype(int) - 255).sum()


def test_a_pair_with_no_key_box_gets_a_value_coloured_tag():
    """Nhãn mang màu của chính hộp nó đậu lên.

    Có trường suy ra được mà trên giấy không in tên khoá (`doc_title`,
    `masthead`) -- cặp ấy chỉ có hộp giá trị. Bản trước vẫn tô nhãn màu khoá,
    nên cả một tờ `llm_certificate_request_form_0013` đội nhãn cam trên khung
    lam."""
    page = np.full((200, 400, 3), 255, np.uint8)
    pairs = [{"field": "doc_title", "value_bbox": [40, 60, 300, 90],
              "page_number": 1}]
    drawn = O.kie(page, pairs, 1)
    tinted = drawn.reshape(-1, 3)
    tinted = tinted[np.any(tinted != 255, axis=1)]
    assert len(tinted) > 0
    assert dE([O.KEY_COLOUR], [tuple(int(c) for c in row) for row in tinted]).min() > \
        dE([O.VALUE_COLOUR], [tuple(int(c) for c in row) for row in tinted]).min()
