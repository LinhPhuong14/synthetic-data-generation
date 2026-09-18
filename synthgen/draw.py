"""Vẽ một chứng từ: đo, cắt trang theo luật 80%, chụp, ghi nhãn.

Ba thứ ở đây dùng lại của kho, và cả ba đều là phép ĐO chứ không phải bố cục:

* `generators/html/page.py::CELL_RECTS_JS` -- hộp của từng chữ, từng dòng,
  từng trường, đo bằng `Range` trong chính trình duyệt vừa dàn trang;
* `generators/html/render.py::quads_from_rects` và hai anh em của nó -- đổi
  toạ độ CSS sang toạ độ ảnh, hai phép nhân dễ quên;
* `pipeline/record.py::build` -- dựng bản ghi: `blocks`, `word_annotations`,
  `entity_annotations`, `layout_annotations`, và `kie` kèm mô tả trường.

Không có bước làm cũ nào. Lượt chạy này in giấy sạch: người dùng đã nói
"không cần augment", và một bước làm cũ vắng mặt phải vắng mặt HẲN chứ không
phải chạy với tham số rỗng -- một chuỗi rỗng vẫn đọc, vẫn sao chép, vẫn có
chỗ để hỏng.
"""

from __future__ import annotations

import json
import os
import random
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from page import (  # noqa: E402
    CELL_RECTS_JS,
    CELL_REGIONS_JS,
    GRAPHIC_RECTS_JS,
    ZONE_REGIONS_JS,
    font_faces,
    served,
)
from render import (  # noqa: E402
    _on_page,
    clip_to_page,
    graphics_from_rects,
    quads_from_rects,
    regions_from_rects,
    zones_from_rects,
)

from pipeline import record as R  # noqa: E402
from synthgen import content as C  # noqa: E402
from synthgen import design as D  # noqa: E402
from synthgen import markup as M  # noqa: E402
from synthgen import overlay as O  # noqa: E402
from synthgen import paginate as P  # noqa: E402

# Bù trừ giữa hai dòng ngẫu nhiên. Dáng rút từ `Random(seed)`, nội dung rút
# từ `Random(seed ^ CONTENT_SALT)`, nên chữ ký dáng là hàm THUẦN của seed và
# `run.py` tính trước được nó cho cả mười nghìn trang trước khi mở trình
# duyệt. Trộn chung một dòng thì không tính trước được, và khử trùng dáng sẽ
# phải chờ tới lúc đã vẽ xong.
CONTENT_SALT = 0x9E3779B9
REFILL_SALT = 0x51ED2701

MEASURE_JS = """() => {
  const out = [];
  for (const sheet of document.querySelectorAll('.sheet')) {
    const rect = sheet.getBoundingClientRect();
    const cs = getComputedStyle(sheet);
    const padTop = parseFloat(cs.paddingTop) || 0;
    const padBottom = parseFloat(cs.paddingBottom) || 0;
    // `min-height` là KHỔ GIẤY; `rect.height` là chiều cao thật. Hai số bằng
    // nhau nghĩa là chữ còn nằm trong tờ giấy; số sau lớn hơn nghĩa là tờ
    // giấy đã phải cao lên để chứa hết -- tức là tràn.
    const paper = parseFloat(cs.minHeight) || rect.height;
    let bottom = rect.top + padTop;
    for (const child of sheet.children) {
      if (getComputedStyle(child).position === 'absolute') continue;
      const box = child.getBoundingClientRect();
      if (box.height <= 0 && box.width <= 0) continue;
      if (box.bottom > bottom) bottom = box.bottom;
    }
    const table = sheet.querySelector('table.items');
    const thead = table ? table.querySelector('thead') : null;
    const rows = [...sheet.querySelectorAll('tr.itemrow')]
        .map(tr => tr.getBoundingClientRect().height);
    out.push({
      paper: paper,
      used: (bottom - rect.top) + padBottom,
      height: rect.height,
      rows: rows,
      thead: thead ? thead.getBoundingClientRect().height : 0,
      padTop: padTop, padBottom: padBottom,
      tableTop: table ? table.getBoundingClientRect().top - rect.top : 0,
      tableBottom: table ? table.getBoundingClientRect().bottom - rect.top : 0,
    });
  }
  return out;
}"""


@dataclass
class Drawn:
    stem: str
    markup: str
    record: dict
    images: list[bytes]
    names: list[str]
    fills: list[float]
    pages: int
    rows: int
    design_signature: tuple
    content_signature: str
    note: str
    rounds: int


def _extracted(doc: C.Doc) -> dict:
    """Nhãn lồng của cả tài liệu -- `record.build(extracted=...)`.

    Không phải bản sao của `blocks`: đây là câu trả lời "tờ giấy này NÓI gì",
    ở dạng cây, và `record.field_paths` đọc nó ra danh sách trường mà một
    trình trích xuất được yêu cầu lấy."""
    d = doc.design
    out: dict = {
        "doc_type": d.archetype.id,
        "title": doc.title,
        "store": {
            "name": doc.org_name,
            "branch": doc.org_branch,
            "address": doc.org_address,
            "phone": doc.org_phone,
            "tax_code": doc.org_tax,
            "website": doc.org_website,
        },
        "invoice": {
            "number": doc.doc_no,
            "serial": doc.doc_serial,
            "subtitle": doc.subtitle,
            "issued_place": doc.issued_place,
            "issued_date": doc.issued_date.isoformat(),
            "fields": {f.key: value for f, value in doc.fields},
        },
        "menu": [
            {key: row.values.get(key, "") for key in d.columns
             if key in D.COLUMNS}
            for row in doc.rows
        ],
    }
    if doc.totals or doc.grand:
        out["total"] = {label: value for label, value in doc.totals}
        if doc.grand:
            out["total"][doc.grand_label or "Tổng cộng"] = doc.grand
    if doc.words:
        out["invoice"]["words"] = doc.words
    if doc.summary:
        out["summary"] = {label: value for label, value in doc.summary}
    if doc.checks:
        out["checks"] = [{"question": q, "answer": a} for q, a in doc.checks]
    if doc.signatures:
        out["signatures"] = [{"title": cap, "name": who}
                             for cap, who in doc.signatures]
    if doc.notes:
        out["note"] = list(doc.notes)
    if doc.footer:
        out["footer"] = [doc.footer]
    return out


class Studio:
    """Một trình duyệt, dùng lại cho cả shard.

    Mở Chromium tốn khoảng bảy phần mười giây; mở nó một lần cho một trăm
    trang thay vì một trăm lần là toàn bộ khác biệt giữa một lượt chạy vài
    chục phút và một lượt chạy vài giờ -- cùng lý do `pipeline/shard.py`
    dựng đúng một tiến trình cho mỗi shard."""

    def __init__(self, *, scale: float = 2.0,
                 short_size: tuple[int, int] = (980, 1560),
                 jpeg_quality: int = 92, augment: str = "off",
                 handwriting: str = "off", hand_share: float = 1.0):
        self.scale = scale
        self.short_size = short_size
        self.jpeg_quality = jpeg_quality
        # `off` (mặc định) vẽ giấy sạch, y như trước khi có dòng này. Bật lên
        # thì trang đi qua ĐÚNG chuỗi `degradation/` mà pipeline chính dùng,
        # ngay sau khi đo hộp và ngay trước khi mã hoá JPEG -- xem
        # `synthgen/augment.py` về thứ tự ấy và về ba điều phải đúng.
        #
        # Có hai đường vào cùng một việc, và đó là có chủ đích: bật ở đây tiết
        # kiệm một vòng đọc-ghi 39 GB khi vẽ một bộ MỚI; `synthgen/augment.py`
        # chạy ngược trên bộ ĐÃ CÓ và giữ lại bản sạch. Không đường nào thay
        # được đường kia, và cả hai gọi chung một hàm `augment.age`.
        self.augment = augment
        self._rules = None
        # Bút mở MỘT LẦN cho mỗi tiến trình: `Hand` (WriteViT) nạp checkpoint,
        # và nạp lại cho từng tờ trong một shard trăm trang là trả cái giá ấy
        # một trăm lần. `FontHand` thì rẻ, nhưng giữ một đường cho cả hai.
        self.handwriting = handwriting
        self.hand_share = hand_share
        self._pen = None
        self._play = None
        self._browser = None
        self._page = None
        self._faces = ""

    def __enter__(self) -> "Studio":
        from playwright.sync_api import sync_playwright

        self._play = sync_playwright().start()
        self._browser = self._play.chromium.launch(args=["--font-render-hinting=none"])
        self._page = self._browser.new_page(device_scale_factor=self.scale)
        self._faces = font_faces()
        return self

    def __exit__(self, *_exc) -> None:
        for closer in (getattr(self._page, "close", None),
                       getattr(self._browser, "close", None),
                       getattr(self._play, "stop", None)):
            if closer:
                try:
                    closer()
                except Exception:                            # noqa: BLE001
                    pass

    # ------------------------------------------------------------- vẽ một tờ

    def _load(self, markup: str) -> None:
        # Hạn chờ rộng hơn mặc định của Playwright (30 giây): mười mấy
        # Chromium chạy cùng lúc trên mười sáu lõi thì một trang bảng hai
        # trăm dòng có lúc mất hơn ba mươi giây để dàn xong, và mỗi lần quá
        # hạn là MẤT HẲN một chứng từ. Đo trên 600 chứng từ ở mười bốn tiến
        # trình: 18 trang hỏng, tất cả đều là quá hạn `goto`, không phải lỗi
        # dàn trang.
        with served(markup) as uri:
            self._page.goto(uri, wait_until="load", timeout=120_000)
        self._page.wait_for_timeout(35)   # để phông nhúng kịp ổn định

    _warned_writevit = False

    def _ink(self, markup: str, seed: int, state: dict,
             always: bool = False) -> str:
        """Rót chữ viết tay vào những ô người ta điền. Tắt thì trả nguyên.

        Gọi Ở ĐÂY, trong vòng đo phân trang, chứ không sau khi chốt trang:
        nét chữ tay CAO HƠN chữ in (font tay đặt ở 1,42 lần cỡ chữ), nên một tờ
        giấy rót mực xong là một tờ giấy khác về chiều cao. Rót sau khi chốt là
        đo luật 80% trên tờ giấy KHÔNG phải tờ sẽ chụp.

        Dùng thẳng `generators/html/handwriting.py` mà pipeline chính dùng --
        cùng ba `kind` (`invoice.field`, `invoice.words`, `sign.name`) mà
        `markup.py` vốn đã in ra, nên không phải sửa một dòng markup nào. Đó là
        chỗ hai bộ sinh thật sự dùng chung một cái bút."""
        if self.handwriting in ("", "off"):
            return markup
        # Tờ NÀY có được điền tay không -- hàm thuần của seed, nên cùng seed thì
        # cùng câu trả lời, và một tờ giấy không đổi số phận giữa hai lượt
        # chạy. `crc32` chứ không `hash()`: `hash()` có muối riêng mỗi tiến
        # trình, nên tám worker sẽ ra tám bộ khác nhau.
        # `always`: tờ khai mà câu trả lời in bằng máy chữ thì không phải tờ
        # khai. Với những phôi mà cả tờ giấy TỒN TẠI để được điền tay, tỉ lệ
        # của lượt chạy không áp -- chỉ `--handwriting off` mới tắt được, và
        # đó là lúc người ta cố ý muốn một bộ sạch.
        if not always and zlib.crc32(f"{seed}|hand".encode("utf-8")) % 10000 >= \
                int(self.hand_share * 10000):
            return markup
        import handwriting  # noqa: PLC0415 -- tuỳ chọn, chỉ nạp khi bật

        if self._pen is None:
            self._pen = handwriting.source(self._ink_source()).open()
        # `survey.answer` thêm vào bộ `kind` mặc định: dòng trả lời của một tờ
        # khai là chỗ người ta VIẾT, đúng như `invoice.field` trên một hoá đơn.
        # Không thêm thì bút bỏ qua nó và tờ khai ra với câu trả lời đánh máy.
        filled, report = handwriting.fill(
            markup, self._pen, seed=seed,
            kinds=handwriting.HAND_KINDS + ("survey.answer",))
        state["hand"] = report
        return filled

    def _ink_source(self) -> str:
        """Nguồn mực thật sự dùng được. `model`/`both` cần WriteViT.

        Không import `agent/rules.py` dù nó có sẵn hàm này: `tests/test_llm.py`
        cấm `synthgen` với tay sang `agent/`, và một phép kiểm thư mục ba dòng
        không đáng để phá ranh giới ấy.

        Thiếu WriteViT thì lùi về `font` chứ không tắt hẳn: bộ dữ liệu vẫn có
        chữ viết tay, chỉ là mọi chữ cùng một nét. Và nói ra, vì "font" với
        "model" là hai bộ dữ liệu khác nhau -- `record["handwriting"]["source"]`
        ghi lại cái nào đã viết."""
        if self.handwriting not in ("model", "both"):
            return self.handwriting
        root = Path(os.environ.get("WRITEVIT_DIR")
                    or REPO_ROOT.parent / "WriteViT")
        if root.is_dir():
            return self.handwriting
        if not Studio._warned_writevit:
            Studio._warned_writevit = True
            print(f"[synthgen] không có WriteViT tại {root} — chữ viết tay lùi "
                  f"về `font`; chạy `python tools/writevit/setup.py` để bật lại")
        return "font"

    def _recipe(self, document: str):
        """Recipe làm cũ cho một tài liệu, hoặc `None` khi tắt.

        Bảng luật đọc MỘT LẦN cho mỗi tiến trình và giữ lại: `load_rules()` mở
        tám file YAML, và mở lại chúng cho từng tờ trong một shard trăm trang
        là trả một cái giá cố định một trăm lần."""
        if self.augment in ("", "off"):
            return None
        from synthgen.augment import options_for, recipe_for  # noqa: PLC0415

        if self._rules is None:
            self._rules, _dropped = options_for(self.augment)
        return recipe_for(document, 0, self._rules)

    def document(self, seed: int, index: int, naming: str) -> Drawn:
        design = D.draw(random.Random(seed), seed)
        rng = random.Random(seed ^ CONTENT_SALT)
        arch = design.archetype

        probe = max(min(8, arch.rows[1]), 1) if design.has("table") else 0
        doc = C.build(design, rng, probe)

        # `drawn` là thứ trình duyệt ĐANG hiển thị, không phải thứ vừa được
        # yêu cầu. Hai cái ấy lệch nhau bất cứ khi nào `paginate.py` chọn một
        # lần đo trước đó làm kế hoạch: nó đặt lại hệ số cỡ chữ trên đối
        # tượng `Design`, nhưng trang trong trình duyệt vẫn là lần dàn cuối.
        # Chụp lúc ấy là chụp một tờ giấy khác với nhãn sắp ghi -- đúng lỗi
        # đã đo được: bản ghi nói tờ giấy lấp 122% mà `grown` vẫn báo không.
        state = {"markup": "", "rows": probe, "drawn": None}

        def refill(count: int) -> None:
            if count == state["rows"]:
                return
            C.refill(doc, random.Random(seed ^ REFILL_SALT ^ (count * 2654435761)),
                     count)
            state["rows"] = count

        def set_boost(value: float) -> None:
            design.boost = float(value)

        # Thang khổ giấy của chính tài liệu này: mọi khổ đủ rộng cho số cột
        # nó có, xếp từ thấp lên cao. `set_paper()` bước lên một bậc và nói
        # còn bậc nào không -- `paginate.py` gọi nó khi thu cỡ chữ hết mức
        # mà chữ vẫn tràn ra ngoài mép giấy.
        rungs = D.ladder(40 + 22 * len(design.columns))
        state["rung"] = next((index for index, paper in enumerate(rungs)
                              if paper.id == design.paper.id), 0)

        def set_paper() -> bool:
            if state["rung"] + 1 >= len(rungs):
                return False
            state["rung"] += 1
            design.paper = rungs[state["rung"]]
            return True

        def measure(slices: list[tuple[int, int]]) -> list[P.Sheet]:
            markup = self._ink(M.markup(doc, list(slices), self._faces), seed,
                               state, always=design.has("questions"))
            self._load(markup)
            state["markup"] = markup
            state["drawn"] = (tuple(slices), state["rows"], design.boost,
                              design.paper.id)
            raw = self._page.evaluate(MEASURE_JS)
            return [P.Sheet(paper=s["paper"], used=s["used"], height=s["height"],
                            rows=list(s["rows"]), thead=s["thead"],
                            pad_top=s["padTop"], pad_bottom=s["padBottom"],
                            table_top=s["tableTop"], table_bottom=s["tableBottom"])
                    for s in raw]

        plan = P.plan(measure, rows_probe=probe,
                      target_pages=design.target_pages,
                      rows_floor=arch.rows[0], rows_ceiling=arch.rows[1],
                      refill=refill, set_boost=set_boost, set_paper=set_paper)

        # Trang đang nạp có đúng là trang của kế hoạch không. Thường là có --
        # lần đo cuối chính là lần kế hoạch chấp nhận -- nhưng khi `plan()`
        # phải lùi về một phương án đo trước đó thì không, và chụp cái đang
        # nạp lúc ấy là chụp một tờ giấy khác với nhãn sắp ghi.
        set_boost(plan.boost)
        wanted = (tuple(plan.slices), plan.rows_total, plan.boost,
                  design.paper.id)
        if state["drawn"] != wanted:
            refill(plan.rows_total)
            markup = self._ink(M.markup(doc, plan.slices, self._faces), seed,
                               state, always=design.has("questions"))
            self._load(markup)
            state["markup"] = markup
            state["drawn"] = wanted

        rects = self._page.evaluate(CELL_RECTS_JS)
        regions = self._page.evaluate(CELL_REGIONS_JS)
        graphics = self._page.evaluate(GRAPHIC_RECTS_JS)
        zones = self._page.evaluate(ZONE_REGIONS_JS)
        elements = self._page.query_selector_all(".sheet")
        if not elements:
            raise RuntimeError("không có phần tử .sheet nào để chụp")
        shots = [element.screenshot(type="png") for element in elements]

        stem = naming.format(document=arch.id, index=index, seed=seed)
        names = R.page_names(f"{stem}.jpg", len(shots))

        pages: list[dict] = []
        images: list[bytes] = []
        factor = 1.0
        # Một recipe cho CẢ tài liệu, hạt giống riêng cho từng tờ: ba tờ của
        # một hoá đơn cũ theo cùng một KIỂU mà không cùng một VẾT.
        recipe = self._recipe(stem)
        for number, shot in enumerate(shots, start=1):
            image = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
            if number == 1:
                target = random.Random(seed).randint(*self.short_size)
                factor = min(target / min(image.shape[:2]), 1.0)
            if factor < 1.0:
                image = cv2.resize(
                    image,
                    (max(int(image.shape[1] * factor), 1),
                     max(int(image.shape[0] * factor), 1)),
                    interpolation=cv2.INTER_AREA)
            height, width = image.shape[:2]
            boxes = quads_from_rects(_on_page(rects["cells"], number),
                                     self.scale, factor)
            words = quads_from_rects(_on_page(rects["words"], number),
                                     self.scale, factor)
            cells = regions_from_rects(_on_page(regions, number),
                                       self.scale, factor)
            marks = graphics_from_rects(_on_page(graphics, number),
                                        self.scale, factor)
            areas = zones_from_rects(_on_page(zones, number), self.scale, factor)
            if recipe is not None:
                from synthgen.augment import age  # noqa: PLC0415 -- tuỳ chọn

                # `words` làm `boxes` cho `by_box`: nó là danh sách hộp chữ mịn
                # nhất, và `by_box` đặt model lên vài hộp chứ không lên cả tờ.
                # `fields` không vào đây -- nó KHÔNG mang hình học, xem
                # `page.py`.
                image, moved, _bent = age(
                    image, recipe, seed + number - 1, words,
                    (boxes, words, cells, marks, areas))
                boxes, words, cells, marks, areas = moved
                height, width = image.shape[:2]
            pages.append({
                "filename": names[number - 1],
                "width": width, "height": height,
                "boxes": clip_to_page(boxes, width, height),
                "words": clip_to_page(words, width, height),
                "cells": clip_to_page(cells, width, height),
                "graphics": clip_to_page(marks, width, height),
                "zones": clip_to_page(areas, width, height),
                "fields": _on_page(rects.get("fields") or [], number),
            })
            ok, buffer = cv2.imencode(
                ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            if not ok:
                raise RuntimeError(f"không mã hoá được ảnh {names[number - 1]}")
            images.append(buffer.tobytes())

        item = R.build(
            filename=names[0], width=pages[0]["width"], height=pages[0]["height"],
            parser="html", ink="print", extracted=_extracted(doc),
            seed=seed, layout=arch.id, sheets=pages)
        if state.get("hand"):
            # Một tờ giấy nói mình được điền tay mà chỉ có ba ô có mực là một
            # sự thật về cái bút, không phải sai số -- nên nó nằm trong NHÃN,
            # không nằm trong một dòng log không ai giữ. Cùng lý do
            # `generators/html/render.py` cất `hand_report` vào bản ghi.
            item["handwriting"] = state["hand"]
        if recipe is not None:
            # Bộ dữ liệu nào không nói được ảnh của nó đã bị làm gì thì không
            # lọc được theo điều ấy, và "bỏ hết trang photocopy ra khỏi tập
            # kiểm" là việc đầu tiên người ta muốn làm.
            from synthgen.augment import stamp  # noqa: PLC0415 -- tuỳ chọn

            stamp(item, recipe, 0)

        return Drawn(
            stem=stem, markup=state["markup"], record=item, images=images,
            names=names, fills=[round(f, 4) for f in plan.fills],
            pages=len(shots), rows=plan.rows_total,
            design_signature=design.signature(),
            content_signature=doc.content_signature(),
            note=plan.note, rounds=plan.rounds)


# ------------------------------------------------------------------ ghi ra


# `records/` chứ không `json/`: đây là BẢN GHI ĐẦY ĐỦ của một TỜ -- mọi
# hộp từ, mọi vùng, mọi cặp KIE -- thứ `check.py`, `overlay.py`,
# `augment.py` và `derive.py` đọc. Thư mục `json/` để dành cho định dạng
# người dùng đã chốt: MỘT file cho MỘT TÀI LIỆU, khoá `page_1`/`page_2`.
# Hai thứ khác nhau mà cùng tên `json` là chỗ đã làm người dùng mở ra và
# thấy ba file cho một chứng từ ba tờ.
KINDS = ("images", "html", "records", "layout_boxes", "word_boxes")


def write(drawn: Drawn, out: Path, *, indent: int | None = None) -> list[dict]:
    """Trải một tài liệu ra năm thư mục, cùng một cái tên gốc ở cả năm.

    Mỗi thư mục lại chia tiếp THEO LOẠI CHỨNG TỪ (`images/hoa_don_gtgt/...`).
    Hai mươi nghìn file phẳng trong một thư mục là thứ `ls` treo và trình
    duyệt file bỏ cuộc; chia theo loại thì mỗi ngăn còn vài trăm, và câu hỏi
    hay hỏi nhất -- "cho tôi xem hết mấy tờ hoá đơn tiền điện" -- trả lời
    được bằng một đường dẫn chứ không phải bằng một vòng lặp.

    Bản ghi được chép BÊN CẠNH TỪNG TRANG, không phải chỉ trang một: người
    cầm `..._p2.jpg` phải tìm thấy `records/.../..._p2.json` mô tả tài liệu mà
    trang ấy thuộc về, chứ không phải một thư mục 404. Cùng lập luận với
    `tools/export_dataset.py`.

    `layout_boxes/` và `word_boxes/` ra MỘT file cho một trang: `.jpg`, chính
    nhãn ấy vẽ đè lên trang -- xem bằng mắt được mà không phải viết script.
    Bản `.json` của chúng thôi được ghi vì nó là bản chép nguyên văn một lát
    cắt của bản ghi; `overlay.slice_for` dựng lại trong một dòng. Xem chú thích
    ngay trong vòng lặp dưới đây.

    `indent=None` viết JSON gọn, và đó là mặc định vì chính cái chép-bên-cạnh
    ở trên: mỗi bản ghi ra đĩa một lần cho mỗi trang của tài liệu, nên khoảng
    trắng không nhân với số bản ghi mà nhân với số TRANG. Đo trên 408 trang:
    226 MB với `indent=1`, 76 MB khi gọn. Ở mười nghìn chứng từ, khoảng cách
    ấy là năm gigabyte khoảng trắng."""
    rows: list[dict] = []
    record = drawn.record
    kind = str(record.get("extracted", {}).get("doc_type") or "khac")
    kie = O.kie_index(record)
    for number, name in enumerate(drawn.names, start=1):
        stem = Path(name).stem
        blob = drawn.images[number - 1]
        (out / "images" / kind / name).write_bytes(blob)
        (out / "html" / kind / f"{stem}.html").write_text(
            drawn.markup, encoding="utf-8")
        (out / "records" / kind / f"{stem}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=indent) + "\n",
            encoding="utf-8")

        def on_page(items):
            return [item for item in items or []
                    if int(item.get("page_number", 1) or 1) == number]

        # MỘT file json cho mỗi trang, không ba. `layout_boxes/*.json` từng là
        # bản chép NGUYÊN VĂN lát cắt `record["layout_annotations"]` của tờ
        # này, còn `word_boxes/*.json` là lát cắt `word_annotations` cộng ba
        # khoá (`kie_field`, `kie_role`, `kie_description`) ghép từ chính
        # `record["kie"]` -- đo trên bộ 20 099 trang: 5,4 GB + 8,7 GB không
        # mang một bit nào mà bản ghi chưa có. `overlay.slice_for` dựng lại cả
        # hai trong một dòng, nên bỏ file đi là bỏ bản sao, không bỏ dữ liệu.
        #
        # Ảnh `.jpg` của hai thư mục ấy thì GIỮ: chúng phải giải mã ảnh gốc rồi
        # vẽ lại, không dựng lại rẻ được như một lát cắt.
        layout_boxes, word_boxes = O.slice_for(record, number, kie)

        page = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
        for folder, drawing in (("layout_boxes", O.layout(page, layout_boxes)),
                                ("word_boxes", O.words(page, word_boxes))):
            ok, buffer = cv2.imencode(".jpg", drawing,
                                      [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                raise RuntimeError(f"không vẽ được ảnh hộp cho {stem}")
            (out / folder / kind / f"{stem}.jpg").write_bytes(buffer.tobytes())

        meta = (record.get("pages") or [{}])[min(number - 1,
                                                 len(record.get("pages") or [{}]) - 1)]
        rows.append({
            "stem": stem,
            "document": drawn.stem,
            "archetype": kind,
            "page_number": number,
            "pages_in_document": len(drawn.names),
            "fill": drawn.fills[number - 1] if number - 1 < len(drawn.fills) else None,
            "rows_in_document": drawn.rows,
            "width": meta.get("width"),
            "height": meta.get("height"),
            "images": f"images/{kind}/{name}",
            "html": f"html/{kind}/{stem}.html",
            "record": f"records/{kind}/{stem}.json",
            "layout_boxes_image": f"layout_boxes/{kind}/{stem}.jpg",
            "word_boxes_image": f"word_boxes/{kind}/{stem}.jpg",
            "layout_box_count": len(layout_boxes),
            "word_box_count": len(word_boxes),
            "kie_pairs": len((record.get("kie") or {}).get("pairs") or []),
        })
    return rows
