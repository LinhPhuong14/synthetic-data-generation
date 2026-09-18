#!/usr/bin/env python3
"""Fan one finished run out into a folder per kind, same stem everywhere.

    python tools/export_dataset.py data/llm200_v2 -o data/llm200_v2_export

    images/        <stem>.jpg    the page
    html/          <stem>.html   the markup it was drawn from
    json/          <stem>.json   the whole record, unchanged
    layout_boxes/  <stem>.json   `layout_annotations` alone
    word_boxes/    <stem>.json   `word_annotations` alone
    manifest.jsonl               one line per page, naming all five

A step AFTER the run, not a change to it. `pipeline/record.py::beside` puts a
record next to its image on purpose -- "the images are the listing, and a file
named after one of them should sit next to it" -- and every reader in this
repository, `tools/check_boxes.py` and `tools/ocr_proof.py` included, is built
on that. Splitting the directories inside the pipeline would mean teaching all
of them a second layout to keep the same promise; splitting them here means
the promise is kept once, by the stem.

A multi-page document (`sheets/base.py::page_order`) has one record and several
images. `source_files` names them in print order, so each page is exported
under its own stem and the record is copied beside EACH of them -- a reader
holding `bang_ke_007_p2.jpg` finds `json/bang_ke_007_p2.json` describing the
document that page belongs to, with `pages[].source_file` saying which page it
is. The alternative -- exporting the record once, under page 1's stem -- leaves
every continuation image with no label file at all.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KINDS = ("images", "html", "json", "layout_boxes", "word_boxes")


def pages_of(record: dict) -> list[str]:
    """Every image this record describes, in print order."""
    sources = [str(name) for name in (record.get("source_files") or []) if name]
    return sources or [str(record.get("filename") or "")]


def export(source: Path, out: Path, *, backend: str = "html",
           link: bool = False) -> dict[str, int]:
    """Write the fanned-out copy. Returns what it wrote, by kind."""
    flat = source / backend
    if not flat.is_dir():
        raise SystemExit(f"{flat} is not there; is {source} a finished run?")

    for kind in KINDS:
        (out / kind).mkdir(parents=True, exist_ok=True)
    written = {kind: 0 for kind in KINDS}
    manifest = []

    place = (lambda src, dst: dst.hardlink_to(src)) if link else shutil.copy2

    for record_path in sorted(flat.glob("*.json")):
        if record_path.name == "synthesis.json":
            continue
        record = json.loads(record_path.read_text(encoding="utf-8"))
        images = pages_of(record)
        for number, image_name in enumerate(images, start=1):
            stem = Path(image_name).stem
            image = flat / image_name
            if not image.exists():
                print(f"[export] thiếu ảnh {image_name}, bỏ qua")
                continue
            target = out / "images" / image_name
            target.unlink(missing_ok=True)
            place(image, target)
            written["images"] += 1

            # One document is ONE markup file holding N `.sheet` elements, so
            # page 2 has no `<stem>_p2.html` of its own. Copy the document's
            # markup under the page's stem anyway, for the same reason the
            # record is copied beside every page: a folder that answers for
            # page 1 and 404s for page 2 is a folder a loader has to special
            # case, and the promise here is that the stem answers everywhere.
            markup = image.with_suffix(".html")
            if not markup.exists():
                markup = record_path.with_suffix(".html")
            if markup.exists():
                dst = out / "html" / f"{stem}.html"
                dst.unlink(missing_ok=True)
                place(markup, dst)
                written["html"] += 1

            # The record goes beside EVERY page of its document -- see the
            # module docstring for why page 2 must not be left label-less.
            (out / "json" / f"{stem}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
            written["json"] += 1

            # Only this page's own boxes: both arrays carry `page_number` on a
            # multi-page record (and nothing on a single-page one, where every
            # box is page 1 by construction).
            def on_page(rows):
                return [r for r in rows or []
                        if int(r.get("page_number", 1) or 1) == number]

            (out / "layout_boxes" / f"{stem}.json").write_text(
                json.dumps(on_page(record.get("layout_annotations")),
                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            written["layout_boxes"] += 1
            (out / "word_boxes" / f"{stem}.json").write_text(
                json.dumps(on_page(record.get("word_annotations")),
                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            written["word_boxes"] += 1

            page_meta = (record.get("pages") or [{}])[min(number - 1,
                                                          len(record.get("pages") or [{}]) - 1)]
            manifest.append({
                "stem": stem,
                "document": stem.rsplit("_", 1)[0] if "_" in stem else stem,
                "page_number": number,
                "pages_in_document": len(images),
                "width": page_meta.get("width"),
                "height": page_meta.get("height"),
                "images": f"images/{image_name}",
                "json": f"json/{stem}.json",
                "layout_boxes": f"layout_boxes/{stem}.json",
                "word_boxes": f"word_boxes/{stem}.json",
                "layout_box_count": len(on_page(record.get("layout_annotations"))),
                "word_box_count": len(on_page(record.get("word_annotations"))),
            })

    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest),
        encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="a finished run directory")
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument("--backend", default="html")
    parser.add_argument("--link", action="store_true",
                        help="hard-link the images instead of copying them -- "
                             "same bytes, no second copy on disk. Only safe on "
                             "one filesystem, and only while nothing edits "
                             "either copy in place.")
    args = parser.parse_args()

    written = export(args.run.resolve(), args.out.resolve(),
                     backend=args.backend, link=args.link)
    print(f"[export] {args.run} -> {args.out}")
    for kind in KINDS:
        print(f"  {kind:14s} {written[kind]:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
