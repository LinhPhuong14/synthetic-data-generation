#!/usr/bin/env python3
"""Làm cũ một bộ synthgen đã sinh xong, và di chuyển mọi cái hộp theo.

    python synthgen/augment.py data/09-09-26-synthetics-document
    python synthgen/augment.py <bộ> -o <bộ>-aug --variants 2 --workers 8
    python synthgen/augment.py <bộ> --warp all --force crumpled --limit 40

Bộ sinh vẽ giấy SẠCH: trắng, phẳng, không vết. Pipeline chính thì không -- nó
bốc một giá trị `augmentation` cho mỗi trang và cho trang đi qua
`degradation/`, nên ảnh của nó là ảnh chụp lại, photocopy lại, gấp lại. Hai
nửa ấy chưa gặp nhau, và file này là chỗ gặp: **đúng một hàm
`degradation.pipeline.apply_recipe` mà cả ba bộ vẽ của kho này gọi**, cộng
`degradation.warp.warp_regions` cho phần hình học.

## Vì sao là một bước RIÊNG, chạy ngược trên bộ đã có

Bộ 20 099 trang hiện có mất vài giờ Chromium để vẽ. Bắt vẽ lại tất cả để thêm
một thứ không liên quan gì tới việc vẽ -- làm cũ là phép biến đổi trên ẢNH,
không cần biết trang được dàn ra sao -- là trả một cái giá không mua gì. Nên
bước này chạy ngược, và bộ sạch còn nguyên: **từ sạch luôn dựng được bẩn, từ
bẩn thì không bao giờ quay lại sạch.** `--variants 2` còn nhân bộ lên bằng
cách cho cùng một tờ giấy đi qua hai cái máy khác nhau.

Vẽ một bộ MỚI thì ngược lại -- khi ấy chưa có gì để giữ, và một vòng đọc-ghi
39 GB là phí:

    python synthgen/run.py -o <bộ> -n 10000 --augment fast

`Studio` nhận `augment=` và gọi thẳng `age()` dưới đây trên những danh sách
`{"quad": ...}` nó vừa đo trong trình duyệt -- rẻ hơn hẳn, vì không phải đọc
rồi ghi lại 39 GB. Hai đường vào, MỘT hàm làm việc: hai bản của cùng một phép
làm cũ là hai phép làm cũ tình cờ trùng tên, và chúng chỉ trùng cho tới lần
sửa đầu tiên. Mặc định vẫn là `off` -- bộ sạch là thứ dựng được mọi thứ khác.

## Ba điều phải đúng, không phải hai

1. **Chuỗi làm cũ không được đổi kích thước ảnh.** Mọi model trong
   `degradation/` lọc hoặc trộn tại chỗ; một phép resize lẻn vào sẽ xê dịch mọi
   cái hộp mà ảnh thì trông vẫn thế. `generators/html/render.py` khẳng định
   điều này bằng một phép so hình dạng, và file này so y như vậy.
2. **Cong giấy thì PHẢI di chuyển hộp**, và di chuyển bằng CÙNG MỘT trường dịch
   chuyển. `warp_regions` nhận nhiều danh sách trong một lần gọi đúng vì thế:
   `word_annotations`, `layout_annotations`, `entity_annotations`, `blocks`,
   các dòng của thực thể, và hộp khoá/giá trị của từng cặp KIE đều tả MỘT tờ
   giấy, nên một trường phải động tới cả bảy.
3. **Một tài liệu, một cái máy.** Recipe bốc theo TÀI LIỆU còn hạt giống bốc
   theo TỜ: ba tờ của một hoá đơn cũ theo cùng một KIỂU mà không cũ theo cùng
   một VẾT. Tờ hai mang đúng nếp gấp của tờ một là dấu hiệu lộ cả bộ chỉ bằng
   một cái nhìn. Cùng luật `render.py` viết ra với `page_seed = seed + number - 1`.

## Warp nào được phép

`degradation/warp.py` có ba engine. `paper_photo` đọc trường dịch chuyển từ ảnh
chụp giấy thật -- vài mili-giây. Mười một tên còn lại render thật qua Blender,
**vài giây tới hơn một phút một trang**: trên 20 099 trang và 11% số lần bốc
trúng, đó là từ sáu tới ba mươi sáu giờ. Nên `--warp fast` (mặc định) bỏ những
giá trị mà warp của nó thuộc engine Blender -- đọc engine từ chính
`degradation/warp.py`, không liệt kê tên ở đây, nên thêm một engine là file này
tự biết. `--warp all` cho phép hết; `--warp none` chỉ làm cũ, không cong.

Bộ nào bị bỏ đều được in ra kèm lý do, không bỏ im.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from degradation import warp as W  # noqa: E402
from degradation.pipeline import apply_recipe, chain_of  # noqa: E402
from rulebase import spec  # noqa: E402
from pipeline import record as R  # noqa: E402
from synthgen import overlay as O  # noqa: E402

JPEG_QUALITY = 92

# Những thư mục KHÔNG đổi khi làm cũ: HTML và markdown là chữ, không phải ảnh.
# Nối bằng symlink chứ không chép 40 000 file -- mọi thứ đọc bộ mới đều đi qua
# được, mà đĩa thì không phải chứa hai bản của cùng một chữ.
SHARED = ("html", "markdown", "kie_schemas")


def blender_free(options: list) -> tuple[list, list[str]]:
    """Những giá trị `augmentation` không cần Blender, và tên các giá trị bị bỏ.

    Engine đọc từ `degradation/warp.py` nên một engine mới thêm vào kho là hàm
    này tự phân loại đúng; một danh sách tên viết ở đây sẽ đúng hôm nay và sai
    lần sau."""
    from degradation import blender

    slow = set(blender.names())
    keep, dropped = [], []
    for option in options:
        name = ((option.params.get("warp") or {}).get("name") or "")
        if name in slow:
            dropped.append(option.id)
        else:
            keep.append(option)
    return keep, dropped


def no_warp(options: list) -> list:
    """Cùng những giá trị ấy nhưng gỡ phần cong giấy khỏi mỗi cái.

    Không phải lọc bỏ: `crumpled` còn cả một chuỗi vết bẩn đáng giữ, chỉ riêng
    phần bẻ hình học là bỏ. Lọc bỏ sẽ làm nghèo bộ đi vì một lý do không liên
    quan tới vết bẩn."""
    out = []
    for option in options:
        if not (option.params.get("warp") or {}).get("name"):
            out.append(option)
            continue
        params = {k: v for k, v in option.params.items() if k != "warp"}
        out.append(dataclasses.replace(option, params=params))
    return out


def options_for(mode: str) -> tuple[dict, list[str]]:
    """`({"augmentation": [...]}, bị bỏ)` -- bảng luật rút gọn để bốc recipe.

    CHỈ thuộc tính `augmentation`. Tờ giấy này đã có màu mực, phông, hoa tiết
    và con dấu của riêng nó do `design.py` quyết; bốc cả `visual` với `ornament`
    là dán một tờ giấy thứ hai lên trên tờ đã vẽ. `apply_recipe` đọc
    `visual.paper` bằng `recipe.get(...)` nên thiếu thuộc tính ấy nó lùi về
    `auto` -- đúng thứ cần."""
    rules = spec.load_rules()
    options = list(rules["augmentation"])
    dropped: list[str] = []
    if mode == "fast":
        options, dropped = blender_free(options)
    elif mode == "none":
        options = no_warp(options)
    elif mode != "all":
        raise SystemExit(f"--warp chỉ nhận fast, all hoặc none; không nhận {mode!r}")
    return {"augmentation": options}, dropped


def recipe_for(document: str, variant: int, rules: dict, force: str = ""):
    """Một recipe cho CẢ tài liệu, suy ra từ tên nó.

    `crc32` chứ không `hash()`: `hash()` của Python có muối riêng cho mỗi tiến
    trình, nên cùng một bộ chạy lại trên tám worker sẽ ra tám kết quả khác nhau
    -- và một bộ dữ liệu không dựng lại được thì không so sánh được với gì."""
    seed = zlib.crc32(f"{document}|{variant}".encode("utf-8"))
    return spec.sample_recipe(seed, rules=rules,
                              force={"augmentation": force} if force else None)


# ------------------------------------------------------------------ hình học


def _quad(polygon) -> list[list[float]]:
    """Bốn góc, từ `polygon` (vòng kín năm điểm) hay `quad` (bốn điểm)."""
    points = [[float(x), float(y)] for x, y in polygon]
    return points[:4]


def _bbox(quad) -> list[int]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return [int(round(min(xs))), int(round(min(ys))),
            int(round(max(xs))), int(round(max(ys)))]


def _rect_quad(box: dict) -> list[list[float]]:
    x1, y1 = float(box["x1"]), float(box["y1"])
    x2, y2 = float(box["x2"]), float(box["y2"])
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _list_quad(bbox) -> list[list[float]]:
    """Bốn góc của một `bbox` dạng danh sách `[x1, y1, x2, y2]`."""
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _as_rect(quad) -> dict:
    x1, y1, x2, y2 = _bbox(quad)
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _line_quads(entity: dict) -> list[list[list[float]]]:
    # `lines_px`, cùng lẽ với mọi chỗ khác trong file này: `lines` đã là phần
    # nghìn của cạnh giấy kể từ khi `pipeline/record.py::to_per_mille` chạy.
    lines = entity.get("lines_px") or entity.get("lines") or ()
    return [[[float(x1), float(y1)], [float(x2), float(y1)],
             [float(x2), float(y2)], [float(x1), float(y2)]]
            for x1, y1, x2, y2 in lines]


def _on(items, page: int):
    return [item for item in items or []
            if int(item.get("page_number", 1) or 1) == page]


def warp_record(name: str, params, rng, image, record: dict, page: int):
    """Cong ảnh và MỌI cái hộp của tờ `page` qua một trường dịch chuyển.

    Bảy danh sách trong một lần gọi `warp_regions`, vì đó là điều kiện để
    chúng đi cùng nhau: hàm ấy nối mọi quad thành một mảng, cong một lần, rồi
    tách ra theo đúng số lượng. Gọi bảy lần là bảy trường khác nhau, tức là
    bảy tờ giấy khác nhau cho cùng một trang."""
    words = _on(record.get("word_annotations"), page)
    layout = _on(record.get("layout_annotations"), page)
    entities = _on(record.get("entity_annotations"), page)
    blocks = _on(record.get("blocks"), page)
    pairs = [p for p in (record.get("kie") or {}).get("pairs") or []
             if int(p.get("page_number", 1) or 1) == page]

    # `lines` của thực thể là hộp THEO DÒNG, thẳng trục. Trên trang đã cong thì
    # một dòng nghiêng có hộp thẳng trục rộng hơn chính nét mực của nó -- chuyện
    # `pipeline/record.py` đã ghi rõ -- nên cong bốn góc rồi lấy hộp bao là đúng
    # thứ trường ấy hứa, không phải một phép xấp xỉ lặng lẽ.
    line_index: list[tuple[int, int]] = []
    line_quads: list[dict] = []
    for position, entity in enumerate(entities):
        for order, quad in enumerate(_line_quads(entity)):
            line_index.append((position, order))
            line_quads.append({"quad": quad})

    keys = [p for p in pairs if p.get("key_bbox")]
    values = [p for p in pairs if p.get("value_bbox")]

    # Ba hình dạng hộp, không một: `word`/`layout` mang `polygon` (vòng kín) và
    # `bbox` là danh sách; `entity` KHÔNG có polygon -- chỉ `bbox` danh sách và
    # `lines`; `block` mang `quad` bốn điểm và `bbox` là một dict `{x1..y2}`.
    # Viết sai hình dạng nào thì file vẫn mở được và cái đọc nó thì vỡ, nên
    # từng loại ghi lại theo đúng hình dạng của nó.
    # ĐỌC BẢN PIXEL. Từ khi `pipeline/record.py` chuyển bản ghi sang hệ
    # 0..1000, `polygon`/`bbox`/`quad` là phần nghìn của cạnh giấy; cong một
    # phần nghìn trên trường dịch chuyển tính bằng pixel là cong nhầm hệ, và
    # nó không ném lỗi -- mọi hộp chỉ co về góc trên trái. `*_px` là chính con
    # số đo được, và nó vẫn ở đó cho đúng việc này.
    def px(item, key):
        return item.get(f"{key}_px") or item[key]

    lists = (
        [{"quad": _quad(px(w, "polygon"))} for w in words],
        [{"quad": _quad(px(r, "polygon"))} for r in layout],
        [{"quad": _list_quad(px(e, "bbox"))} for e in entities],
        [{"quad": _quad(px(b, "quad"))} for b in blocks],
        line_quads,
        [{"quad": _rect_quad(px(p, "key_bbox"))} for p in keys],
        [{"quad": _rect_quad(px(p, "value_bbox"))} for p in values],
    )
    aged, *moved = W.warp_regions(name, image, params, rng, *lists)
    new_words, new_layout, new_entities, new_blocks, new_lines, new_keys, new_values = moved

    # GHI LẠI CẢ HAI HỆ. Trang đã cong nên mọi hộp đổi chỗ; ghi pixel mà quên
    # phần nghìn thì bản ghi nói hộp ở chỗ cũ, ghi phần nghìn mà quên pixel
    # thì lần làm cũ sau không còn gì để cong.
    high, wide = aged.shape[:2]
    for items, fresh in ((words, new_words), (layout, new_layout)):
        for item, box in zip(items, fresh):
            quad = box["quad"]
            item["polygon_px"] = [*quad, list(quad[0])]
            item["bbox_px"] = _bbox(quad)
            item.update(R.to_per_mille(
                {"polygon": item["polygon_px"], "bbox": item["bbox_px"]},
                wide, high))
    for entity, box in zip(entities, new_entities):
        entity["bbox_px"] = [float(v) for v in _bbox(box["quad"])]
        entity.update(R.to_per_mille({"bbox": entity["bbox_px"]}, wide, high))
    for block, box in zip(blocks, new_blocks):
        block["quad_px"] = box["quad"]
        block["bbox_px"] = _as_rect(box["quad"])
        block.update(R.to_per_mille(
            {"quad": block["quad_px"], "bbox": block["bbox_px"]}, wide, high))
    for (position, order), box in zip(line_index, new_lines):
        entity = entities[position]
        entity.setdefault("lines_px", [list(v) for v in entity.get("lines") or []])
        entity["lines_px"][order] = _bbox(box["quad"])
    for entity in entities:
        if entity.get("lines_px"):
            entity.update(R.to_per_mille({"lines": entity["lines_px"]},
                                         wide, high))
    for pair, box in zip(keys, new_keys):
        pair["key_bbox_px"] = _as_rect(box["quad"])
        pair.update(R.to_per_mille({"key_bbox": pair["key_bbox_px"]}, wide, high))
    for pair, box in zip(values, new_values):
        pair["value_bbox_px"] = _as_rect(box["quad"])
        pair.update(R.to_per_mille({"value_bbox": pair["value_bbox_px"]},
                                   wide, high))
    return aged


# ------------------------------------------------------------------ một trang


def age(image, recipe, seed: int, boxes, lists):
    """Làm cũ một tấm ảnh và di chuyển những danh sách hộp đi kèm.

    `(ảnh, [danh sách đã dịch], có cong hay không)`. Đây là phần chung của HAI
    đường vào -- `age_page` dưới đây làm việc trên một BẢN GHI đã ghi ra đĩa,
    còn `draw.py` gọi thẳng hàm này trên những danh sách `{"quad": ...}` nó vừa
    đo được trong trình duyệt. Viết một lần vì hai đường phải làm giống hệt
    nhau: hai bản của cùng một phép làm cũ là hai phép làm cũ tình cờ trùng tên,
    và chúng chỉ trùng cho tới lần sửa đầu tiên."""
    before = image.shape[:2]
    aged = apply_recipe(image, recipe, seed=seed, boxes=boxes)
    if aged.shape[:2] != before:
        raise RuntimeError(
            f"một phép làm cũ đã đổi kích thước trang ({before} -> "
            f"{aged.shape[:2]}); mọi cái hộp không còn tả nó nữa")
    warp = recipe.get("augmentation", "warp")
    if not warp:
        return aged, [list(items) for items in lists], False
    aged, *moved = W.warp_regions(warp["name"], aged, warp.get("params"),
                                  random.Random(seed), *lists)
    return aged, moved, True


def age_page(image, record: dict, page: int, recipe, seed: int) -> tuple:
    """`(ảnh đã cũ, có cong hay không)`. `record` bị sửa tại chỗ."""
    words = _on(record.get("word_annotations"), page)
    # `by_box` đặt một model lên vài hộp chữ thay vì lên cả tờ, và hộp là thứ
    # duy nhất nói những chỗ ấy ở đâu. `kind` lấy `field_path` vì đó là thứ
    # `degradation/regions.py::_by_kind` so khớp.
    boxes = [{"kind": str(w.get("field_path") or ""), "quad": _quad(w["polygon"])}
             for w in words]

    before = image.shape[:2]
    aged = apply_recipe(image, recipe, seed=seed, boxes=boxes)
    if aged.shape[:2] != before:
        raise RuntimeError(
            f"một phép làm cũ đã đổi kích thước trang ({before} -> "
            f"{aged.shape[:2]}); mọi cái hộp không còn tả nó nữa")

    warp = recipe.get("augmentation", "warp")
    if warp:
        aged = warp_record(warp["name"], warp.get("params"),
                           random.Random(seed), aged, record, page)
    height, width = aged.shape[:2]
    for sheet in record.get("pages") or []:
        if int(sheet.get("page_number", 1) or 1) == page:
            sheet["width"], sheet["height"] = width, height
    return aged, bool(warp)


def stamp(record: dict, recipe, variant: int) -> None:
    """Ghi vào bản ghi rằng tờ này đã đi qua cái máy nào.

    Bộ dữ liệu nào không nói được ảnh của nó đã bị làm gì thì không lọc được
    theo điều ấy, và "bỏ hết trang photocopy ra khỏi tập kiểm" là việc đầu tiên
    người ta muốn làm."""
    record.setdefault("settings", {})["augmentation"] = {
        "value": recipe.choices["augmentation"].id,
        "seed": recipe.seed,
        "variant": variant,
        "chain": [name for name, _options in chain_of(recipe)],
        "warp": (recipe.get("augmentation", "warp") or {}).get("name") or None,
    }


def suffix(stem: str, variant: int, variants: int) -> str:
    """Tên tệp của bản thứ `variant`. Một bản thì giữ nguyên tên bộ gốc."""
    return stem if variants == 1 else f"{stem}__a{variant + 1}"


def do_document(root: Path, out: Path, rows: list[dict], rules: dict,
                variants: int, force: str, indent: int | None) -> list[dict]:
    """Cả tài liệu, mọi bản. Một recipe cho mỗi bản, một hạt giống cho mỗi tờ."""
    made: list[dict] = []
    document = str(rows[0].get("document") or rows[0]["stem"])
    for variant in range(variants):
        recipe = recipe_for(document, variant, rules, force)
        # Bản ghi đọc lại MỘT LẦN cho cả tài liệu và làm cũ từng tờ trên chính
        # nó, nên file cạnh tờ hai mang hộp đã cong của cả tờ một và tờ ba. Đọc
        # lại cho từng tờ thì mỗi file chỉ đúng về tờ của nó, và một bản ghi
        # đúng một phần là thứ khó phát hiện hơn một bản ghi sai.
        source = rows[0].get("record") or rows[0]["json"]
        record = json.loads((root / source).read_text(encoding="utf-8"))
        images: dict[str, np.ndarray] = {}
        warped = False
        for row in sorted(rows, key=lambda r: int(r.get("page_number", 1) or 1)):
            page = int(row.get("page_number", 1) or 1)
            raw = cv2.imread(str(root / row["images"]), cv2.IMREAD_COLOR)
            if raw is None:
                raise RuntimeError(f"không đọc được ảnh {row['images']}")
            aged, bent = age_page(raw, record, page, recipe,
                                 recipe.seed + page - 1)
            images[row["stem"]] = aged
            warped = warped or bent
        stamp(record, recipe, variant)

        for row in rows:
            page = int(row.get("page_number", 1) or 1)
            kind = str(row.get("archetype") or "khac")
            stem = suffix(row["stem"], variant, variants)
            aged = images[row["stem"]]
            height, width = aged.shape[:2]
            name = f"{stem}.jpg"

            # `filename`/`source_file` phải là tên MỚI: một bản ghi trỏ sang ảnh
            # sạch là một bản ghi tả tờ giấy khác với tờ nằm cạnh nó.
            page_record = json.loads(json.dumps(record))
            page_record["filename"] = name
            for sheet in page_record.get("pages") or []:
                old = suffix(sheet.get("source_file", "").removesuffix(".jpg"),
                             variant, variants)
                sheet["source_file"] = f"{old}.jpg"

            for folder in ("images", "records", "layout_boxes", "word_boxes"):
                (out / folder / kind).mkdir(parents=True, exist_ok=True)
            ok, buffer = cv2.imencode(".jpg", aged,
                                      [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if not ok:
                raise RuntimeError(f"không mã hoá được ảnh {name}")
            (out / "images" / kind / name).write_bytes(buffer.tobytes())
            (out / "records" / kind / f"{stem}.json").write_text(
                json.dumps(page_record, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8")

            kie = O.kie_index(page_record)
            layout_boxes = _on(page_record.get("layout_annotations"), page)
            word_boxes = O.annotate(_on(page_record.get("word_annotations"), page),
                                    kie)
            (out / "layout_boxes" / kind / f"{stem}.json").write_text(
                json.dumps(layout_boxes, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8")
            (out / "word_boxes" / kind / f"{stem}.json").write_text(
                json.dumps(word_boxes, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8")
            # Ảnh vẽ hộp đè lên chính TỜ ĐÃ CŨ, không đè lên tờ sạch: nó tồn tại
            # để người xem tin được rằng hộp còn khớp sau khi giấy cong, và vẽ
            # lên tờ sạch là vẽ một lời khẳng định về tấm ảnh khác.
            for folder, drawing in (("layout_boxes", O.layout(aged.copy(), layout_boxes)),
                                    ("word_boxes", O.words(aged.copy(), word_boxes))):
                cv2.imwrite(str(out / folder / kind / f"{stem}.jpg"), drawing,
                            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

            made.append({**row,
                         "stem": stem, "document": suffix(document, variant, variants),
                         "width": width, "height": height,
                         "images": f"images/{kind}/{name}",
                         "record": f"records/{kind}/{stem}.json",
                         # Không khai `layout_boxes`/`word_boxes` json: hai
                         # file ấy thôi được ghi từ khi `overlay.slice_for`
                         # dựng lại chúng trong một dòng. Khai một đường dẫn
                         # không có file là một manifest nói dối, và mọi thứ
                         # đọc nó đều tin.
                         "layout_boxes_image": f"layout_boxes/{kind}/{stem}.jpg",
                         "word_boxes_image": f"word_boxes/{kind}/{stem}.jpg",
                         "augmentation": recipe.choices["augmentation"].id,
                         "augmentation_variant": variant,
                         "augmentation_warped": warped,
                         "clean_stem": row["stem"]})
    return made


def link_shared(root: Path, out: Path) -> list[str]:
    """Nối `html/`, `markdown/`, `kie_schemas/` bằng symlink thay vì chép."""
    linked = []
    for folder in SHARED:
        source = root / folder
        target = out / folder
        if source.is_dir() and not target.exists():
            target.symlink_to(source.resolve(), target_is_directory=True)
            linked.append(folder)
    return linked


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục đã sinh xong")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="thư mục ra; mặc định là <bộ>-aug")
    parser.add_argument("--variants", type=int, default=1,
                        help="mỗi tờ giấy đi qua mấy cái máy khác nhau")
    parser.add_argument("--warp", default="fast",
                        help="fast (bỏ warp Blender) | all | none")
    parser.add_argument("--force", default="",
                        help="ghim một giá trị augmentation, ví dụ photocopy")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0,
                        help="chỉ làm N tài liệu đầu -- để thử")
    parser.add_argument("--indent", type=int, default=None)
    args = parser.parse_args()

    root = args.run.resolve()
    out = (args.out or root.with_name(root.name + "-aug")).resolve()
    manifest = root / "manifest.jsonl"
    if not manifest.is_file():
        print(f"không có {manifest} — đây có phải thư mục đã sinh xong không?")
        return 1
    if out == root:
        print("thư mục ra phải khác thư mục vào: bộ sạch là thứ không dựng lại "
              "được nếu ghi đè lên.")
        return 1

    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    documents: dict[str, list[dict]] = {}
    for row in rows:
        documents.setdefault(str(row.get("document") or row["stem"]), []).append(row)
    names = sorted(documents)
    if args.limit:
        names = names[:args.limit]

    rules, dropped = options_for(args.warp)
    print(f"[augment] {len(rows)} trang / {len(names)} tài liệu trong {root}")
    print(f"[augment] {len(rules['augmentation'])} giá trị augmentation, "
          f"{args.variants} bản mỗi tờ -> {out}")
    if dropped:
        print(f"[augment] bỏ {len(dropped)} giá trị dùng warp Blender "
              f"(vài giây tới hơn một phút một trang): {', '.join(sorted(dropped))}")
        print("[augment] cần chúng thì --warp all, và tính thời gian trước")
    if args.variants > 1:
        print(f"[augment] {args.variants} bản cùng nội dung: `check` sẽ báo "
              "nội dung lặp, và đó là đúng — cùng tờ giấy, khác cái máy")

    out.mkdir(parents=True, exist_ok=True)
    linked = link_shared(root, out)
    if linked:
        print(f"[augment] symlink (không đổi khi làm cũ): {', '.join(linked)}")

    import concurrent.futures as cf

    made: list[dict] = []
    failed: list[tuple[str, str]] = []
    with cf.ProcessPoolExecutor(max_workers=max(args.workers, 1)) as pool:
        futures = {pool.submit(do_document, root, out, documents[name], rules,
                              args.variants, args.force, args.indent): name
                   for name in names}
        for done, future in enumerate(cf.as_completed(futures), start=1):
            try:
                made += future.result()
            except Exception as error:  # noqa: BLE001 -- báo rồi chạy tiếp
                failed.append((futures[future], str(error)[:160]))
            if done % 200 == 0 or done == len(names):
                print(f"  {done}/{len(names)} tài liệu")

    made.sort(key=lambda r: (r["stem"]))
    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in made),
        encoding="utf-8")

    import collections

    spread = collections.Counter(row["augmentation"] for row in made)
    bent = sum(1 for row in made if row["augmentation_warped"])
    print(f"\n[augment] {len(made)} trang -> {out}")
    print(f"[augment] {bent} trang bị cong (hộp đã đi theo trường dịch chuyển)")
    print("[augment] mười giá trị hay ra nhất: "
          + ", ".join(f"{name}={n}" for name, n in spread.most_common(10)))
    (out / "report.json").write_text(json.dumps({
        "clean_run": str(root),
        "pages": len(made),
        "documents": len(names),
        "variants": args.variants,
        "warp_mode": args.warp,
        "warped_pages": bent,
        "dropped_values": sorted(dropped),
        "spread": dict(spread),
        "failed": [{"document": name, "error": why} for name, why in failed],
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if failed:
        print(f"[augment] {len(failed)} tài liệu lỗi:")
        for name, why in failed[:10]:
            print(f"    {name}: {why}")
        return 1
    print("[augment] XONG — không tài liệu nào lỗi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
