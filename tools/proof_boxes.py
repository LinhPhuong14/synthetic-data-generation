"""One proof image per generated image: the page with its own label drawn on it.

    python tools/proof_boxes.py --dataset data/5k_llm
    python tools/proof_boxes.py --dataset data/5k_llm --mode layout
    python tools/proof_boxes.py --dataset data/5k_llm --mode words

`tools/check_boxes.py` answers "do the boxes land on ink" with a number, which
is the right shape for a gate and the wrong shape for a person. This writes the
picture instead: every labelled run outlined on the page it was read off,
coloured by what the label calls it, with a legend. Two minutes with a handful
of these says more about whether a set is usable than any coverage percentage,
and at 5000 images the ones worth looking at are the ones you can only find by
looking.

Deliberately not part of the renderer. A proof is a *reading* of a finished
dataset -- it uses only the image and the record beside it, exactly what a
consumer of the set has -- so it cannot accidentally prove itself right by
sharing state with the thing that drew the page.

Three `--mode`, three arrays, three colourings:

- `blocks` (default): `item["blocks"]`, one box per field. Colours group by
  the FAMILY a `kind` belongs to rather than by the kind itself: `menu.name`,
  `menu.qty` and `menu.amount` are one table and read as one colour, which is
  what makes a missing column visible at a glance. This table is specific to
  this repository's own `kind` vocabulary.
- `layout`: `item["layout_annotations"]`, one box per region. Coloured by
  `layout_class` -- the 19-label `docsynth.annotations.v1` vocabulary in
  `pipeline.record.DOCSYNTH_LABELS` -- so the palette is DERIVED from that
  set (`_docsynth_palette`) rather than hand-picked: a label added there gets
  a colour for free, and this file never grows a matching entry to keep up.
- `words`: `item["word_annotations"]`, one box per word. Coloured AND tagged
  by `field_role` (key/value/unbound, `FIELD_ROLE_COLOURS`) rather than the
  19-label `layout_class`: a viewer reading word-by-word wants to see which
  of a pair is the label at a glance, and three hand-picked colours read
  faster for that than three of nineteen hue-wheel slices would.
- `kie`: `item["kie"]["pairs"]`, TWO boxes and a line per entry rather than
  one box per entry like the other three modes -- the whole point of this
  mode is showing the LINK `pipeline.kie.pair_fields` drew between a caption
  and the value it captions, which no single box can show. Tagged by the
  pair's own `field` (the slug `pipeline.kie.slug` derived from the printed
  caption), not by `kind`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import record as schema  # noqa: E402

# BGR, because OpenCV. Ordered widest-family-first; `family` takes the first
# prefix that matches, so `total.grand.label` lands on `total` and not on a
# catch-all.
FAMILIES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("menu", (60, 170, 60)),          # the item table
    ("total", (40, 90, 220)),         # money at the bottom
    ("invoice", (200, 120, 40)),      # serial block and form fields
    ("store", (190, 60, 180)),        # who issued it
    ("colhdr", (150, 150, 150)),      # column titles
    ("sign", (30, 190, 220)),         # signature captions
    ("title", (30, 30, 210)),         # the doc title and subtitle
    ("subtitle", (30, 30, 210)),
    ("period", (120, 90, 200)),
    ("note", (110, 110, 110)),
    ("footer", (110, 110, 110)),
)
OTHER = (80, 80, 80)
LEGEND_HEIGHT = 26

# BGR, `--mode words` only. Three fixed colours rather than a slice of
# `_docsynth_palette()` -- there are only ever three `field_role` values
# (`pipeline.record._word_field_role`), and a viewer scanning key/value pairs
# wants the same two colours everywhere on the page, not a colour that shifts
# with which of the 19 `layout_class` regions a word happens to sit in.
FIELD_ROLE_COLOURS: dict[str, tuple[int, int, int]] = {
    "key": (30, 140, 230),      # the caption half of a pair -- warm, stands out
    "value": (170, 120, 40),    # the content half -- cool, the bulk of the page
    "unbound": (110, 110, 110), # page furniture bound to no field
}


def family(kind: str) -> tuple[str, tuple[int, int, int]]:
    head = str(kind or "").split(".")[0]
    for name, colour in FAMILIES:
        if head == name:
            return name, colour
    return "khác", OTHER


def _docsynth_palette() -> dict[str, tuple[int, int, int]]:
    """One colour per `pipeline.record.DOCSYNTH_LABELS`, spread round the hue
    wheel rather than picked by hand -- a label added or renamed there changes
    this palette with it, with nothing here to keep in sync.
    """
    import cv2
    import numpy as np

    names = sorted(schema.DOCSYNTH_LABELS)
    hues = np.linspace(0, 179, num=len(names), endpoint=False, dtype=np.uint8)
    hsv = np.stack([hues, np.full(len(names), 200, dtype=np.uint8),
                    np.full(len(names), 220, dtype=np.uint8)], axis=1)
    bgr = cv2.cvtColor(hsv.reshape(-1, 1, 3), cv2.COLOR_HSV2BGR).reshape(-1, 3)
    return {name: tuple(int(c) for c in colour) for name, colour in zip(names, bgr)}


def _tag(overlay, text: str, x: int, y: int, colour, scale: float = 0.32) -> None:
    """The box's own `kind`, written where it will still be readable on ink.

    Drawn on a filled chip rather than straight onto the page: a proof sheet is
    read over printed text and half of these labels would otherwise land on a
    table rule. The chip is the box's own colour so the tag and its outline are
    obviously the same thing.
    """
    import cv2

    (width, height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    top = max(0, y - height - 4)
    cv2.rectangle(overlay, (x, top), (x + width + 4, top + height + 4), colour, -1)
    cv2.putText(overlay, text, (x + 2, top + height + 1),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


MODES = ("blocks", "layout", "words", "kie")

# `--mode kie` only: the line joining a pair's two boxes together, and the
# fallback colour for a pair whose `key_bbox`/`value_bbox` is missing one
# side (should not happen -- `pipeline.kie.pair_fields` always writes both --
# but a proof must not crash on a record a future bug wrote wrong).
KIE_LINK_COLOUR = (0, 170, 0)


def _page_of(item: dict, image_name: str) -> int:
    """1-based page number the file named `image_name` is, within `item`.

    `source_files` is written fresh on every rename (`pipeline.record.stamp`)
    in print order, so its position IS the page number -- page 1 is index 0,
    same convention `page.py::CELL_RECTS_JS` stamps on every box it measures.
    Not found (a record with no `source_files`, or a name that is not in it)
    reads as page 1, which is every single-page record's only page.
    """
    names = [str(name) for name in (item.get("source_files") or [])]
    try:
        return names.index(image_name) + 1
    except ValueError:
        return 1


def _on_page(entries: list[dict], page: int) -> list[dict]:
    """`entries` restricted to one printed side.

    A multi-page record's `blocks`/`word_annotations`/`layout_annotations`
    are ONE flat list for the whole document (`pipeline.record.build`'s
    `sheets=` argument concatenates every side), each entry carrying its own
    `page_number` -- see `generators/html/page.py::CELL_RECTS_JS`'s own
    reasoning for why a box is measured against the sheet it lands on.
    Without this filter, drawing a proof for page 1's image walks page 2's
    boxes too, and every one of them lands on ink page 1 never had -- the
    exact confusion a person comparing `foo.jpg` against `foo.json` hits on
    a multi-page document. Absent on every entry (a record with one page, or
    written before pages existed) is the same as page 1 on all of them, so a
    single-page record is untouched by this filter.
    """
    return [entry for entry in entries if int(entry.get("page_number", 1)) == page]


def _entries(item: dict, mode: str, page: int) -> list[tuple[str, tuple, dict]]:
    """`(tag text, colour, entry)` for every box `mode` draws, on `page` only.

    One function per mode kept together here, rather than three near-copies
    of `draw`, because the three differ only in which array they read and
    what they colour/tag by -- the drawing below is identical either way.
    """
    if mode == "blocks":
        out = []
        for box in _on_page(schema.boxes(item), page):
            kind = str(box.get("kind", "") or "?")
            _name, colour = family(kind)
            out.append((kind, colour, box))
        return out
    if mode == "layout":
        palette = _docsynth_palette()
        return [(str(region.get("layout_class", "?")),
                 palette.get(region.get("layout_class"), OTHER), region)
                for region in _on_page(schema.layout_annotations(item), page)]
    # "words": coloured AND tagged by field_role -- key/value/unbound -- so
    # every "key" on the page is the same colour wherever it sits, rather
    # than shifting with the layout_class of whatever region it is in.
    return [(str(word.get("field_role", "?")),
             FIELD_ROLE_COLOURS.get(word.get("field_role"), OTHER), word)
            for word in _on_page(schema.word_annotations(item), page)]


def _kie_box(overlay, bbox, colour) -> tuple[int, int] | None:
    """Draw one side of a pair, return its centre -- `None` if `bbox` is
    unusable, so the caller can skip the link rather than crash on it."""
    import cv2

    if not (isinstance(bbox, dict) and {"x1", "y1", "x2", "y2"} <= set(bbox)):
        return None
    x1, y1, x2, y2 = (int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"]))
    cv2.rectangle(overlay, (x1, y1), (x2, y2), colour, 1)
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def _kie_page_of(item: dict, pair: dict) -> int:
    """Which printed side one `kie.pairs` entry is on.

    `kie.pairs` carries no `page_number` of its own -- it is two box
    references, not a box -- so this reads it off `entity_annotations`
    (`pipeline.kie.pair_entities`' source), the same array `value_entity_index`
    already points into. No entities on this record (the `pair_fields`
    fallback, a character-grid page) means one page, so everything matches.
    """
    index = pair.get("value_entity_index", pair.get("key_entity_index"))
    for entity in item.get("entity_annotations") or []:
        if entity.get("entity_index") == index:
            return int(entity.get("page_number", 1))
    return 1


def _draw_kie(overlay, item: dict, tags: bool, page: int) -> dict[str, tuple[int, int, int]]:
    """Every pair in `item["kie"]["pairs"]` that lands on `page`: key box,
    value box, the line joining their centres, and (once per field) the
    field's own tag. Returns the legend dict the caller's shared legend-strip
    code expects."""
    import cv2

    key_colour = FIELD_ROLE_COLOURS["key"]
    value_colour = FIELD_ROLE_COLOURS["value"]
    pairs = [pair for pair in (item.get("kie") or {}).get("pairs") or []
            if _kie_page_of(item, pair) == page]
    for pair in pairs:
        key_centre = _kie_box(overlay, pair.get("key_bbox"), key_colour)
        value_centre = _kie_box(overlay, pair.get("value_bbox"), value_colour)
        if key_centre and value_centre:
            cv2.line(overlay, key_centre, value_centre, KIE_LINK_COLOUR, 1, cv2.LINE_AA)
        if tags and key_centre:
            _tag(overlay, str(pair.get("field", "?")), key_centre[0], key_centre[1],
                KIE_LINK_COLOUR)
    return {"key": key_colour, "value": value_colour, "link": KIE_LINK_COLOUR}


def draw(image_path: Path, record_path: Path, out_path: Path,
         legend: bool = True, tags: bool = True, mode: str = "blocks") -> bool:
    """Write the proof for one page. False when the image could not be read."""
    import cv2
    import numpy as np

    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return False
    try:
        item = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    overlay = image.copy()
    page = _page_of(item, image_path.name)

    if mode == "kie":
        seen = _draw_kie(overlay, item, tags, page)
        proof = cv2.addWeighted(overlay, 0.88, image, 0.12, 0)
        if legend and seen:
            strip = np.full((LEGEND_HEIGHT, proof.shape[1], 3), 245, dtype=np.uint8)
            x = 8
            for name, colour in sorted(seen.items()):
                cv2.rectangle(strip, (x, 8), (x + 14, 18), colour, -1)
                cv2.putText(strip, name, (x + 19, 18), cv2.FONT_HERSHEY_SIMPLEX,
                            0.38, (40, 40, 40), 1, cv2.LINE_AA)
                x += 34 + 8 * len(name)
            proof = np.vstack([proof, strip])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), proof, [cv2.IMWRITE_JPEG_QUALITY, 86])
        return True

    seen: dict[str, tuple[int, int, int]] = {}
    labels: list[tuple[str, int, int, tuple]] = []
    for tag, colour, box in _entries(item, mode, page):
        seen[tag] = colour
        quad = box.get("quad")
        if isinstance(quad, list) and len(quad) >= 4:
            points = np.array([[int(round(x)), int(round(y))] for x, y in quad[:4]],
                              dtype=np.int32)
            cv2.polylines(overlay, [points], True, colour, 1, cv2.LINE_AA)
            labels.append((tag, int(points[:, 0].min()), int(points[:, 1].min()), colour))
            continue
        bbox = box.get("bbox")
        # `blocks[]` writes bbox as a dict; `layout_annotations`/
        # `word_annotations` write it as `[x1, y1, x2, y2]` -- see
        # `pipeline/record.py::regions_from_words`/`words_from_boxes`.
        if isinstance(bbox, dict) and {"x1", "y1", "x2", "y2"} <= set(bbox):
            x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        elif isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            continue
        cv2.rectangle(overlay, (int(x1), int(y1)), (int(x2), int(y2)), colour, 1)
        labels.append((tag, int(x1), int(y1), colour))

    # Tags last, so a chip is never overdrawn by the outline of the next box.
    # A page carries hundreds of runs and most of them repeat a kind down a
    # column, so only the first of each kind in a neighbourhood is written:
    # labelling all 431 of a hospital bill's cells makes the sheet unreadable
    # and says nothing the first one did not.
    if tags:
        written: dict[str, list[tuple[int, int]]] = {}
        for kind, x, y, colour in labels:
            near = written.setdefault(kind, [])
            if any(abs(x - px) < 140 and abs(y - py) < 34 for px, py in near):
                continue
            near.append((x, y))
            _tag(overlay, kind, x, y, colour)

    # The boxes stay legible over dark ink without hiding the ink itself: the
    # whole point is to see whether the outline sits on the glyphs.
    proof = cv2.addWeighted(overlay, 0.88, image, 0.12, 0)

    if legend and seen:
        strip = np.full((LEGEND_HEIGHT, proof.shape[1], 3), 245, dtype=np.uint8)
        x = 8
        for name, colour in sorted(seen.items()):
            cv2.rectangle(strip, (x, 8), (x + 14, 18), colour, -1)
            cv2.putText(strip, name, (x + 19, 18), cv2.FONT_HERSHEY_SIMPLEX,
                        0.38, (40, 40, 40), 1, cv2.LINE_AA)
            x += 34 + 8 * len(name)
            if x > proof.shape[1] - 60:
                break
        proof = np.vstack([proof, strip])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), proof, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return True


def _one(job: tuple) -> bool:
    image, item, out, tags, mode = job
    return draw(Path(image), Path(item), Path(out), tags=tags, mode=mode)


# `pipeline.record.page_names`' name for a document's page 2+: the same
# stem with `_pN` hung off it. Only page 1 gets a `.json` beside it -- the
# one record already names every side through `source_files` -- so page 2's
# own image has no record UNDER ITS OWN NAME, only under page 1's.
_CONTINUATION = re.compile(r"_p\d+$")


def _record_for(image: Path) -> Path:
    """The `.json` beside `image`, or the page-1 record a page 2+ image is
    described inside, if `image`'s own name never had one."""
    direct = image.with_suffix(".json")
    if direct.exists():
        return direct
    stem = _CONTINUATION.sub("", image.stem)
    return image.with_name(stem + ".json")


def pairs(dataset: Path, framework: str = "html") -> list[tuple[Path, Path]]:
    """(image, record) for every page of a framework, in file order.

    A multi-page document's page 2+ image resolves to its page-1 record via
    `_record_for` -- see that function and `_page_of`/`_on_page` in `draw()`,
    which is what then keeps only the boxes that actually landed on THIS
    image out of that shared record's flat, whole-document lists.
    """
    directory = dataset / framework
    out = []
    for image in sorted(directory.glob("*.jpg")):
        item = _record_for(image)
        if item.exists():
            out.append((image, item))
    return out


# `mode` -> the subdirectory its proof lands in, beside the original
# `dataset/proof` -- a run with more than one `--mode` writes each into its
# own folder rather than one overwriting the last.
OUT_DIRNAME = {"blocks": "proof", "layout": "proof_layout", "words": "proof_words",
              "kie": "proof_kie"}


def run(dataset: Path, framework: str = "html", workers: int = 1,
        out_dir: Path | None = None, tags: bool = True,
        mode: str = "blocks") -> tuple[int, int]:
    """Draw every proof. Returns (written, attempted)."""
    out_dir = out_dir or dataset / OUT_DIRNAME[mode]
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(str(image), str(item), str(out_dir / image.name), tags, mode)
            for image, item in pairs(dataset, framework)]
    if not jobs:
        return 0, 0
    if workers <= 1:
        return sum(_one(job) for job in jobs), len(jobs)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return sum(pool.map(_one, jobs, chunksize=16)), len(jobs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--framework", default="html")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--mode", choices=MODES, default="blocks",
                        help="which array to draw from -- see this file's own docstring")
    parser.add_argument("--out", type=Path, default=None,
                        help="default: <dataset>/proof, .../proof_layout or .../proof_words")
    parser.add_argument("--no-tags", action="store_true",
                        help="outline the boxes without writing each one's kind")
    args = parser.parse_args()
    written, total = run(args.dataset, args.framework, args.workers, args.out,
                         tags=not args.no_tags, mode=args.mode)
    print(f"{written}/{total} ảnh proof ({args.mode}) -> "
          f"{args.out or args.dataset / OUT_DIRNAME[args.mode]}")
    return 0 if written == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
