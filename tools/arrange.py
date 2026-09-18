#!/usr/bin/env python3
"""Sắp một lượt chạy của pipeline chính thành thư mục theo LOẠI CHỨNG TỪ.

    python tools/arrange.py data/300_llm
    python tools/arrange.py data/300_llm -o data/300_llm_doc --copy

Pipeline chính ghi ra một thư mục phẳng tên theo bộ vẽ:

    html/html_000.jpg  html_000.json  html_000.html
    proof_layout/html_000.jpg     proof_words/html_000.jpg

`synthgen` ghi ra thư mục chia theo loại chứng từ, tên theo loại:

    images/hoa_don_gtgt/hoa_don_gtgt_00001.jpg
    json/hoa_don_gtgt/hoa_don_gtgt_00001.json

Cùng một bộ dữ liệu, hai cách bày, và bên huấn luyện phải viết hai bộ đọc. Bước
này bày lại cách thứ hai, đọc từ chính lượt đã chạy xong.

## Vì sao là bước SAU, không phải đổi chỗ renderer ghi ra

Ba thứ đang buộc vào đường dẫn hiện tại, và cả ba là những phép kiểm đắt nhất
của kho:

* `tools/baseline.py` vân tay từng ảnh THEO ĐƯỜNG DẪN;
* `tests/test_worklist.py` vẽ một trang hai lần rồi so sha256;
* `manifest.json` phải so được từng byte giữa lượt 1 worker và lượt 8 --
  `pipeline/run.py` mở đầu bằng đúng chuyện ấy.

Đổi chỗ renderer ghi là bỏ cả ba, và bỏ TRONG IM LẶNG: ảnh vẫn ra, chỉ là không
so được với bộ cũ nữa. Một bước sau thì giữ nguyên mọi thứ ấy và vẫn cho ra
đúng cách bày người ta muốn. Cùng lý do `synthgen/derive.py` là bước sau chứ
không phải một cờ trong `draw.py`.

## Ảnh không bị chép hai lần

Mặc định **nối cứng** (hard link): cùng một inode, hai đường dẫn, nên một bộ 40
GB không thành 80 GB. `--copy` khi thư mục đích nằm ở ổ khác (nối cứng không
qua được ranh giới hệ thống tệp) -- và bước này tự lùi về chép khi nối cứng
không được, có báo.

## Tên mới

`<loại>_<số thứ tự>`, số đếm riêng cho từng loại, theo đúng thứ tự lượt chạy đã
vẽ. Tờ thứ hai trở đi giữ hậu tố `_p2`, `_p3` -- cùng quy ước
`pipeline/record.py::page_names` đã dùng, nên một bộ đọc viết cho `synthgen`
đọc được thẳng bộ này.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen.export import document as as_document  # noqa: E402
from synthgen.kie_full import complete as complete_kie  # noqa: E402
from synthgen.phrasing import describe as rephrase  # noqa: E402

# Thư mục nguồn -> thư mục đích. `proof/` (ảnh vẽ khối) không sang: `synthgen`
# không có thứ tương đương, và nó là ảnh để NGƯỜI soi lượt chạy chứ không phải
# nhãn để máy đọc.
OVERLAYS = {"proof_layout": "layout_boxes", "proof_words": "word_boxes"}

_PAGE = re.compile(r"^(?P<stem>.+?)(?:_p(?P<page>\d+))?$")


def split_page(stem: str) -> tuple[str, int]:
    """`html_020_p2` -> `("html_020", 2)`; `html_020` -> `("html_020", 1)`."""
    match = _PAGE.match(stem)
    if not match:
        return stem, 1
    return match["stem"], int(match["page"] or 1)


def doctype_of(synthesis: dict, filename: str) -> str:
    """Loại chứng từ của một ảnh, theo `synthesis.json`.

    `attributes.document` là câu trả lời đúng: nó là giá trị thuộc tính mà bộ
    luật bốc ra, tức là thứ người ta nghĩ tới khi nói "loại chứng từ". `layout`
    chỉ là bố cục -- một loại chứng từ có nhiều bố cục, nên chia theo bố cục là
    chia nhỏ hơn người dùng muốn.
    """
    page = (synthesis.get("pages") or {}).get(filename) or {}
    attributes = page.get("attributes") or {}
    return (str(attributes.get("document") or "").strip()
            or str(page.get("layout") or "").strip()
            or "khong_ro")


def link_or_copy(source: Path, target: Path, copy: bool) -> str:
    """`"link"` hoặc `"copy"` -- cách file đã sang, để báo cáo nói thật."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    if not copy:
        try:
            os.link(source, target)
            return "link"
        except OSError:
            # Khác hệ thống tệp, hoặc hệ thống tệp không cho nối cứng. Chép,
            # và người gọi in ra con số để không ai ngạc nhiên vì chỗ trống đĩa.
            pass
    shutil.copy2(source, target)
    return "copy"


def enrich(record: dict, source: Path, stem: str) -> bool:
    """Lấp KIE cho mọi nhãn in ra, và cho mỗi tài liệu một giọng. `True` nếu sửa.

    Hai thứ `synthgen` có mà pipeline chính chưa: `pipeline/kie.py` chỉ ghép
    được chỗ có nhãn in kèm -- đo trên lượt 24 trang: 12 cặp trên 81 thực thể,
    tức 15% -- còn `kie_full.complete` lấp nốt ô bảng, tiêu đề cột, ghi chú,
    tiêu đề tài liệu, con dấu, lên 87-96%. Và `phrasing.describe` cho mỗi tài
    liệu một cách nói khác nhau thay vì một câu lặp trên cả bộ.

    Cả hai chạy Ở ĐÂY chứ không trong `pipeline/record.py`: sửa bản ghi lúc vẽ
    là đổi byte của mọi lượt chạy cũ, và `tools/baseline.py` so ảnh theo vân
    tay còn `manifest.json` phải so được từng byte. Bước sau thì bản gốc còn
    nguyên, bản giàu nằm cạnh."""
    markup_path = source / f"{stem}.html"
    markup = markup_path.read_text(encoding="utf-8") if markup_path.is_file() else ""
    try:
        pairs, counts = complete_kie(record, markup)
    except Exception as error:                          # noqa: BLE001
        # Một bố cục lạ không được làm hỏng cả lượt sắp xếp: bản ghi gốc vẫn
        # dùng được, chỉ là không giàu thêm. Báo ra để không ai tưởng nó đã lấp.
        print(f"  [kie] {stem}: {type(error).__name__}: {error}")
        return False
    seed = record.get("job_id") or record.get("filename", "")
    voice: dict[int, str] = {}
    for pair in pairs:
        pair["description"] = rephrase(pair.get("description", ""), seed,
                                       str(pair.get("column")
                                           or pair.get("field", "")))
        index = pair.get("value_entity_index")
        if isinstance(index, int):
            voice[index] = pair["description"]
    for entity in record.get("entity_annotations") or []:
        if entity.get("entity_index") in voice:
            entity["description"] = voice[entity["entity_index"]]
    record.setdefault("kie", {})["pairs"] = pairs
    record["kie"]["coverage"] = counts
    return True


def run(root: Path, out: Path, *, backend: str, copy: bool, limit: int,
        indent: int | None, kie_full: bool = True) -> int:
    source = root / backend
    synthesis_path = source / "synthesis.json"
    if not synthesis_path.is_file():
        print(f"không có {synthesis_path} — đây có phải lượt đã chạy xong không?")
        return 1
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))

    images = sorted(p for p in source.glob("*.jpg"))
    if not images:
        print(f"không có ảnh nào trong {source}")
        return 1

    # Gom theo TÀI LIỆU trước, rồi mới đánh số: đánh số theo ảnh thì tờ hai của
    # một tài liệu lại thành một số khác, và hai tờ của cùng một tờ giấy nằm ở
    # hai cái tên không liên quan gì nhau.
    by_document: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    order: list[str] = []
    for path in images:
        stem, page = split_page(path.stem)
        if stem not in by_document:
            order.append(stem)
        by_document[stem].append((page, path))
    if limit:
        order = order[:limit]

    counters: dict[str, int] = defaultdict(int)
    manifest: list[dict] = []
    moved = {"link": 0, "copy": 0}
    for stem in order:
        pages = sorted(by_document[stem])
        first = pages[0][1]
        kind = doctype_of(synthesis, first.name)
        counters[kind] += 1
        name = f"{kind}_{counters[kind]:05d}"

        record_path = source / f"{stem}.json"
        record = (json.loads(record_path.read_text(encoding="utf-8"))
                  if record_path.is_file() else {})
        filled = enrich(record, source, stem) if record and kie_full else False

        for page, image in pages:
            tail = "" if page == 1 else f"_p{page}"
            new = f"{name}{tail}"
            moved[link_or_copy(image, out / "images" / kind / f"{new}.jpg",
                               copy)] += 1
            markup = source / f"{image.stem}.html"
            if markup.is_file():
                moved[link_or_copy(markup, out / "html" / kind / f"{new}.html",
                                   copy)] += 1
            page_record = source / f"{image.stem}.json"
            target = out / "json" / kind / f"{new}.json"
            if filled:
                # Bản ghi đã bị SỬA (thêm cặp KIE, đổi giọng mô tả), nên phải
                # ghi ra file mới. Nối cứng ở đây là ghi đè luôn bản gốc trong
                # `html/` -- cùng một inode, và lượt chạy gốc thì phải giữ
                # nguyên để còn so được với `tools/baseline.py`.
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps(record, ensure_ascii=False, indent=indent) + "\n",
                    encoding="utf-8")
                moved["copy"] += 1
            elif page_record.is_file():
                moved[link_or_copy(page_record, target, copy)] += 1
            for folder, into in OVERLAYS.items():
                drawn = root / folder / f"{image.stem}.jpg"
                if drawn.is_file():
                    moved[link_or_copy(drawn, out / into / kind / f"{new}.jpg",
                                       copy)] += 1
            manifest.append({
                "stem": new, "document": name, "archetype": kind,
                "page_number": page, "pages_in_document": len(pages),
                "images": f"images/{kind}/{new}.jpg",
                "html": f"html/{kind}/{new}.html",
                "json": f"json/{kind}/{new}.json",
                "layout_boxes_image": f"layout_boxes/{kind}/{new}.jpg",
                "word_boxes_image": f"word_boxes/{kind}/{new}.jpg",
                "was": image.name,
            })

        # Bản một-tài-liệu-một-file, đúng định dạng `synthgen/export.py` dựng:
        # `doc_type` + mảng `pages`, mỗi entry trong `fields` mang `type` --
        # một tờ hay nhiều tờ cùng một hình dạng.
        if record:
            payload = as_document(record, kind)
            target = out / "documents" / f"{name}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8")

    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest),
        encoding="utf-8")
    print(f"[arrange] {len(order)} tài liệu / {len(manifest)} trang / "
          f"{len(counters)} loại chứng từ -> {out}")
    print(f"[arrange] {moved['link']} file nối cứng, {moved['copy']} file chép")
    spread = sorted(counters.items(), key=lambda kv: -kv[1])
    print("[arrange] loại nhiều nhất: "
          + ", ".join(f"{k}={n}" for k, n in spread[:6]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục lượt đã chạy xong")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="thư mục ra; mặc định là <lượt>/by_document")
    parser.add_argument("--backend", default="html",
                        help="tên bộ vẽ, tức tên thư mục phẳng (mặc định html)")
    parser.add_argument("--copy", action="store_true",
                        help="chép thay vì nối cứng (khi đích ở ổ khác)")
    parser.add_argument("--limit", type=int, default=0,
                        help="chỉ lấy N tài liệu đầu -- để thử")
    parser.add_argument("--indent", type=int, default=1)
    parser.add_argument("--no-kie-full", action="store_true",
                        help="không lấp KIE và không đổi giọng mô tả; "
                             "bản ghi sang nguyên như lượt chạy đã ghi")
    args = parser.parse_args()

    root = args.run.resolve()
    out = (args.out or root / "by_document").resolve()
    return run(root, out, backend=args.backend, copy=args.copy,
               limit=args.limit, indent=args.indent or None,
               kie_full=not args.no_kie_full)


if __name__ == "__main__":
    raise SystemExit(main())
