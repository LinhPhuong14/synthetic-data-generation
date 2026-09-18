"""Vẽ hộp nhãn đè lên chính trang giấy nó đọc được.

Một con số ("98,7% hộp nằm trên mực") trả lời được cho một cửa kiểm tự động
nhưng không trả lời được cho người: người muốn NHÌN thấy hộp nào ôm chữ nào.
File này vẽ ra cái ấy -- hai ảnh cho mỗi trang, một cho vùng bố cục và một
cho từng từ.

Chỉ dùng ẢNH và BẢN GHI, đúng thứ người dùng bộ dữ liệu có trong tay. Không
đọc lại DOM, không dùng chung trạng thái với thứ đã vẽ ra trang -- một ảnh
kiểm chứng dùng chung trạng thái với thứ nó kiểm là một ảnh tự chứng minh
mình đúng.

Chữ trên ảnh viết bằng `cv2.putText`, tức là chỉ có Latin không dấu. Nên nhãn
in ra là tên LỚP (`Table`, `Page-Header`) chứ không phải chữ tiếng Việt trong
ô: tên lớp vốn đã không dấu, còn chữ trong ô thì đã nằm ngay dưới hộp rồi.
"""

from __future__ import annotations

import cv2
import numpy as np

# Màu theo lớp bố cục, BGR. Chọn để phân biệt được cả khi in đen trắng: mỗi
# lớp một độ sáng khác nhau, không chỉ khác màu.
def _palette() -> dict[str, tuple[int, int, int]]:
    """Một màu cho MỖI nhãn trong `DOCSYNTH_LABELS`, trải đều vòng màu.

    Bản trước là bảng viết tay mười hai dòng cho hai mươi mốt nhãn, nên mười
    nhãn -- `List-Group`, `Stamp`, `Watermark`, `Figure`, `Bibliography`,
    `Table-Of-Contents`... -- đều vẽ bằng một màu xám chung. Người xem ảnh
    không phân biệt được chúng, mà phân biệt được chúng đúng là việc của ảnh
    này. Và bảng ấy còn giữ `List-item`, một cái tên kho này đã bỏ.

    Phái sinh thì một nhãn thêm vào `pipeline/record.py` có màu ngay, không ai
    phải nhớ sửa hai chỗ. Cùng cách `tools/proof_boxes.py::_docsynth_palette`
    đã làm -- gom về một lối thay vì hai bảng lệch nhau.

    Sắp theo tên rồi trải đều sắc độ, nên màu của một nhãn ỔN ĐỊNH giữa các
    lượt chạy: hai ảnh chụp cách nhau một tuần vẫn so được bằng mắt."""
    from pipeline.record import DOCSYNTH_LABELS               # noqa: PLC0415

    names = sorted(DOCSYNTH_LABELS)
    hues = np.linspace(0, 179, num=len(names), endpoint=False).astype(np.uint8)
    hsv = np.stack([hues,
                    np.full(len(names), 205, dtype=np.uint8),
                    np.full(len(names), 225, dtype=np.uint8)], axis=1)
    bgr = cv2.cvtColor(hsv.reshape(-1, 1, 3), cv2.COLOR_HSV2BGR).reshape(-1, 3)
    return {name: tuple(int(c) for c in colour)
            for name, colour in zip(names, bgr)}


CLASS_COLOURS: dict[str, tuple[int, int, int]] = _palette()
OTHER = (80, 80, 80)

# Hộp từ: ba màu, theo vai trò của từ trong cặp KIE. Một từ không thuộc cặp
# nào vẫn được vẽ -- nó vẫn là một hộp phải đúng.
KEY_COLOUR = (60, 60, 230)
VALUE_COLOUR = (60, 170, 60)
PLAIN_COLOUR = (170, 120, 40)


def _rect(box) -> tuple[int, int, int, int] | None:
    """`[x1,y1,x2,y2]` hoặc `{x1,...}` thành bốn số nguyên. None nếu hỏng."""
    if isinstance(box, dict):
        box = [box.get("x1"), box.get("y1"), box.get("x2"), box.get("y2")]
    if not box or len(box) != 4 or any(v is None for v in box):
        return None
    x1, y1, x2, y2 = (int(round(float(v))) for v in box)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _tag(image, text: str, at: tuple[int, int], colour,
         scale: float | None = None) -> None:
    """Nhãn nhỏ có nền, để chữ đọc được cả trên vùng mực đậm.

    Nhãn nằm NGAY TRÊN hộp, không đè vào nó: cái nó đang chỉ vào là mực trong
    hộp, mà đè lên thì che mất đúng thứ người xem mở ảnh ra để nhìn. Hết chỗ
    phía trên -- hộp sát mép giấy -- thì mới tụt xuống dưới."""
    if scale is None:
        scale = max(image.shape[1] / 2200.0, 0.34)
    thick = 1
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x, y = at
    top = y - h - 5
    if top < 0:
        top = y + 2
    cv2.rectangle(image, (x, top), (x + w + 6, top + h + 5), colour, -1)
    cv2.putText(image, text, (x + 3, top + h + 1), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (255, 255, 255), thick, cv2.LINE_AA)


def layout(image: np.ndarray, regions: list[dict]) -> np.ndarray:
    """Vùng bố cục: khung dày, tô mờ bên trong, tên lớp ở góc trên trái."""
    out = image.copy()
    wash = out.copy()
    for region in regions:
        rect = _rect(region.get("bbox"))
        if not rect:
            continue
        colour = CLASS_COLOURS.get(str(region.get("layout_class", "")), OTHER)
        cv2.rectangle(wash, rect[:2], rect[2:], colour, -1)
    cv2.addWeighted(wash, 0.12, out, 0.88, 0, out)
    for region in regions:
        rect = _rect(region.get("bbox"))
        if not rect:
            continue
        name = str(region.get("layout_class", "") or "?")
        colour = CLASS_COLOURS.get(name, OTHER)
        cv2.rectangle(out, rect[:2], rect[2:], colour, 2)
        _tag(out, name, (rect[0], rect[1]), colour)
    return out


def words(image: np.ndarray, boxes: list[dict]) -> np.ndarray:
    """Hộp từ: khung mảnh, màu theo vai trò KIE.

    Không viết chữ lên: một trang có hàng nghìn từ, và một nhãn cho mỗi từ
    thì che hết chính cái mực nó đang chỉ vào."""
    out = image.copy()
    for box in boxes:
        rect = _rect(box.get("bbox"))
        if not rect:
            continue
        role = str(box.get("kie_role") or "")
        colour = (KEY_COLOUR if role == "key" else
                  VALUE_COLOUR if role == "value" else PLAIN_COLOUR)
        cv2.rectangle(out, rect[:2], rect[2:], colour, 1)
    return out


def kie(image: np.ndarray, pairs: list[dict], page: int = 1) -> np.ndarray:
    """Từng cặp KHOÁ → GIÁ TRỊ, và đường nối giữa hai hộp của nó.

    `word_boxes` tô màu theo vai trò nhưng không nói hộp nào ĐI VỚI hộp nào.
    Trên một tờ giấy có "Địa chỉ:" hai lần -- bên bán và bên mua -- đó chính
    là câu hỏi khó nhất, và một mũi tên trả lời nó nhanh hơn ba cột JSON.

    Nhãn viết bằng tên trường (`dia_chi`, `ma_so_thue`): `kie.slug()` đã bỏ
    dấu sẵn, nên `cv2.putText` in được -- còn chữ tiếng Việt trên giấy thì
    đã nằm ngay trong hộp rồi, không cần in lại.
    """
    out = image.copy()
    for pair in pairs:
        if int(pair.get("page_number", page) or page) != page:
            continue
        # Ô bảng vẽ GỌN: một trang có thể mang hơn hai trăm ô, và hai trăm
        # mũi tên chụm về cùng một ô tiêu đề thì tấm ảnh thành một búi chỉ.
        # Khung vẫn đủ nói ô nào là khoá ô nào là giá trị.
        dense = pair.get("source") == "table"
        key = _rect(pair.get("key_bbox"))
        value = _rect(pair.get("value_bbox"))
        if key:
            cv2.rectangle(out, key[:2], key[2:], KEY_COLOUR, 1)
        if value:
            cv2.rectangle(out, value[:2], value[2:], VALUE_COLOUR, 1)
        if dense:
            continue
        if key and value:
            start = (key[2], (key[1] + key[3]) // 2)
            end = (value[0], (value[1] + value[3]) // 2)
            cv2.arrowedLine(out, start, end, (40, 40, 40), 1,
                            cv2.LINE_AA, tipLength=0.04)
        anchor = key or value
        if anchor:
            # Cỡ chữ theo CHIỀU CAO CỦA HỘP, không theo bề ngang tấm ảnh: một
            # trường cao mười lăm pixel mà đội cái nhãn cao ba mươi thì nhãn
            # che ba dòng chữ quanh nó. Đo trên một phiếu chi: nhãn cỡ cố
            # định phủ kín cả khối letterhead.
            tall = anchor[3] - anchor[1]
            _tag(out, str(pair.get("field", "?")), (anchor[0], anchor[1]),
                 KEY_COLOUR, scale=max(0.26, min(0.42, tall / 44.0)))
    return out


def kie_index(record: dict) -> dict[int, dict[str, str]]:
    """`{entity_index: {field, description, role}}` từ các cặp KIE.

    Từ nối vào cặp qua `entity_index` chứ không qua toạ độ: hai hộp chồng
    nhau vẫn là hai trường khác nhau, còn `entity_index` thì đã do
    `pipeline/kie.py` chốt sẵn."""
    out: dict[int, dict[str, str]] = {}
    for pair in (record.get("kie") or {}).get("pairs") or []:
        field = str(pair.get("field", ""))
        description = str(pair.get("description", ""))
        for role, key in (("key", "key_entity_index"),
                          ("value", "value_entity_index")):
            index = pair.get(key)
            if isinstance(index, int):
                out[index] = {"kie_field": field,
                              "kie_description": description,
                              "kie_role": role}
    return out


def annotate(boxes: list[dict], index: dict[int, dict[str, str]]) -> list[dict]:
    """Chép mô tả KIE vào từng hộp từ.

    `word_boxes/` là file mà một trình huấn luyện đọc MỘT MÌNH, không mở bản
    ghi đầy đủ bên cạnh. Nên mô tả trường phải nằm ngay trong nó, chứ không
    phải một cái khoá trỏ sang file khác."""
    out = []
    for box in boxes:
        row = dict(box)
        extra = index.get(box.get("entity_index"))
        if extra:
            row.update(extra)
        out.append(row)
    return out


def slice_for(record: dict, page: int,
              index: dict[int, dict[str, str]] | None = None
              ) -> tuple[list[dict], list[dict]]:
    """`(hộp vùng, hộp từ)` của MỘT tờ, dựng từ chính bản ghi.

    Đây là thứ thay cho `layout_boxes/*.json` và `word_boxes/*.json`. Hai file
    ấy từng được ghi ra bên cạnh mỗi trang và không mang một bit nào mà bản ghi
    chưa có -- 14,1 GB trên bộ 20 099 trang. Một hàm dựng lại được thì một file
    chép sẵn chỉ là một chỗ nữa để lệch.

    `index` truyền vào khi gọi nhiều lần trên cùng một bản ghi (`kie_index`
    quét cả danh sách cặp, và một tài liệu ba tờ thì quét ba lần là thừa hai).
    """
    if index is None:
        index = kie_index(record)
    on_page = lambda items: [item for item in items or []          # noqa: E731
                             if int(item.get("page_number", 1) or 1) == page]
    return (on_page(record.get("layout_annotations")),
            annotate(on_page(record.get("word_annotations")), index))


__all__ = ["annotate", "kie", "kie_index", "layout", "slice_for", "words"]
