#!/usr/bin/env python3
"""Ba thứ dựng từ một bộ ĐÃ SINH XONG, không phải một bước của bộ sinh.

    python synthgen/derive.py data/09-09-26-synthetics-document --workers 6

Ra thêm ba thứ, cạnh năm thư mục cũ:

    markdown/      <loại>/<stem>.html   HTML TRẦN: đúng cấu trúc, không CSS
    visualize_kie/ <loại>/<stem>.jpg    từng cặp khoá → giá trị, có mũi tên nối
    sample/                             ~200 trang đã lọc, gom vào một chỗ

Vì sao là bước SAU chứ không sửa `draw.py`: lượt chạy mười nghìn chứng từ nạp
code vào RAM lúc khởi động, nên sửa bộ sinh giữa chừng thì phần đã vẽ không
có, phần vẽ sau lại có -- một bộ dữ liệu nửa nọ nửa kia mà không gì báo. Đọc
lại bộ đã xong thì cả hai mươi nghìn trang đi qua đúng một đường.

Và nó dùng ĐÚNG những gì người dùng bộ dữ liệu có: ảnh, bản ghi, markup. Không
mở trình duyệt, không dựng lại gì.
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

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import record as R  # noqa: E402
from synthgen import overlay as O  # noqa: E402
from synthgen.kie_full import complete  # noqa: E402
from synthgen.kie_schema import build as build_schema  # noqa: E402
from synthgen.kie_schema import merge as merge_schema
from synthgen.phrasing import ordinal_of, voice_record  # noqa: E402
from synthgen.plain import sheet_html  # noqa: E402

# Dấu vết của từng kiểu bảng phức trong markup. Đọc từ markup chứ không dựng
# lại `Design` từ seed: markup là thứ đã thật sự vẽ ra trang, còn dựng lại là
# tin rằng bộ sinh hôm nay vẫn bốc y như hôm nó vẽ.
SHAPES = {
    "tier2": '<tr class="tier2">',
    "tier3": '<tr class="tier3">',
    "tier4": '<tr class="tier4">',
    # Dải "Phần ..." chạy hết chiều ngang, trên mọi tầng tiêu đề cột. Thiếu
    # dòng này thì bảng bốn tầng đếm ra như bảng ba tầng, và một phép đo im
    # lặng đọc thiếu là cách một thay đổi có vẻ không có tác dụng.
    "banner": '<tr class="banner">',
    "colnum": '<tr class="colnum">',
    "phan_muc": '<tr class="grouphdr">',
    "cong_nhom": '<tr class="grouptot">',
    "cot_gom": 'class="rail"',
    "bang_con": '<table class="sub">',
}


def grid_record(record: dict) -> None:
    """Bù hộp hệ 1000 cho bản ghi CŨ. Bản ghi mới thì không làm gì.

    `pipeline/record.py::to_per_mille` chuyển cả bản ghi sang hệ 0..1000 ngay
    lúc lắp, và để lại pixel ở `*_px`. Nên hàm này giờ chỉ còn một việc: một
    bộ dữ liệu vẽ TRƯỚC thay đổi ấy vẫn mang `bbox` pixel và không có `*_px`
    -- chuyển tại chỗ cho nó, để mọi thứ đọc bản ghi chỉ phải biết một hệ.

    Bản trước hàm này ghi vào một khoá RIÊNG là `bbox_1000`, nên một bản ghi
    mang ba cách nói về cùng một cái hộp: `bbox` pixel, `bbox_1000`, rồi
    `synthgen/export.py` chia lần nữa lúc xuất. Bỏ khoá ấy -- `bbox` đã là hệ
    1000, và một tên thứ hai cho cùng một số là một tên sẽ lệch.

    Nhận ra bản ghi mới bằng SỰ CÓ MẶT của `bbox_px`, không bằng cách đoán
    theo độ lớn con số: một trang rộng 1000 pixel thì hai hệ trùng khoảng giá
    trị, và mọi phép đoán theo độ lớn đều sai đúng trên những trang ấy.

    Kích thước lấy theo TỪNG TỜ, không lấy tờ một áp cho cả tài liệu: một
    chứng từ cắt trang có thể đổi khổ giấy giữa chừng (`paginate.py` leo thang
    khổ giấy khi nội dung không vừa), và chia cho chiều rộng sai thì cả trang
    lệch mà không gì báo."""
    sizes = {int(s.get("page_number", 1) or 1):
             (float(s.get("width") or 0), float(s.get("height") or 0))
             for s in record.get("pages") or []}

    def on(item) -> tuple[float, float]:
        return sizes.get(int(item.get("page_number", 1) or 1), (0.0, 0.0))

    for key in ("word_annotations", "layout_annotations", "entity_annotations",
                "blocks"):
        for item in record.get(key) or []:
            if "bbox_px" in item:
                continue                      # bản ghi mới -- đã ở hệ 1000
            width, height = on(item)
            box = item.get("bbox")
            if not (box and width and height):
                continue
            item.update(R.to_per_mille({"bbox": box}, width, height))
    # HỘP CỦA CẶP ĐẶT LẠI TỪ CHÍNH THỰC THỂ NÓ TRỎ TỚI.
    #
    # Một cặp KIE không đo hộp -- nó chỉ trỏ vào hai thực thể và chép hộp của
    # chúng. Hai bản chép của cùng một con số thì sớm muộn lệch nhau, và ở đây
    # đã lệch: đo trên `data/thu1k`, cặp `doc_title` mang `value_bbox_px`
    # {333,197,665,225} -- chính là `entity.bbox` PHẦN NGHÌN bị gọi là pixel --
    # rồi `value_bbox` {221,101,442,116} là phần nghìn của phần nghìn. Pixel
    # thật của thực thể ấy là {501,383,1002,436}. 685/966 hộp trường của cả bộ
    # (71%) dồn về góc trên-trái vì thế, và không gì báo: một hộp 221 vẫn là
    # một hộp hợp lệ.
    #
    # Nên không đoán hộp đang ở hệ nào: chép lại từ thực thể, thứ mang cả hai
    # hệ và khai rõ hệ nào là hệ nào (`bbox`, `bbox_px`). Cặp nào không trỏ
    # được vào thực thể -- bản ghi cũ dựng từ `blocks` -- thì giữ luật cũ.
    entities = {e.get("entity_index"): e
                for e in record.get("entity_annotations") or []}
    for pair in (record.get("kie") or {}).get("pairs") or []:
        width, height = on(pair)
        for name, index in (("value_bbox", pair.get("value_entity_index")),
                            ("key_bbox", pair.get("key_entity_index"))):
            entity = entities.get(index) if isinstance(index, int) else None
            if entity and entity.get("bbox"):
                pair[name] = _as_box(entity["bbox"])
                if entity.get("bbox_px"):
                    pair[f"{name}_px"] = _as_box(entity["bbox_px"])
                continue
            if not (width and height):
                continue
            if f"{name}_px" in pair or not pair.get(name):
                continue
            pair.update(R.to_per_mille({name: pair[name]}, width, height))


def _as_box(box) -> dict:
    """`[x1,y1,x2,y2]` của thực thể thành `{x1..y2}` mà cặp KIE vẫn dùng."""
    if isinstance(box, dict):
        return {k: int(round(float(box[k]))) for k in ("x1", "y1", "x2", "y2")}
    x1, y1, x2, y2 = (float(v) for v in box)
    return {"x1": int(round(x1)), "y1": int(round(y1)),
            "x2": int(round(x2)), "y2": int(round(y2))}


def _pages_of_entity(record: dict) -> dict[int, int]:
    """`{entity_index: số tờ}` -- lấy từ chính hộp từ.

    Cặp KIE không mang số tờ, nhưng mỗi TỪ thì có, và mỗi từ biết nó thuộc
    thực thể nào. Không có bảng này thì mọi cặp của tài liệu bị vẽ lên mọi
    tờ, kể cả tờ không có nó."""
    out: dict[int, int] = {}
    for word in record.get("word_annotations") or []:
        index = word.get("entity_index")
        if isinstance(index, int) and index not in out:
            out[index] = int(word.get("page_number", 1) or 1)
    return out


def _one(job: dict) -> dict | None:
    """Dựng `markdown/` và `visualize_kie/` cho MỘT trang."""
    root = Path(job["root"])
    row = job["row"]
    stem, kind, page = row["stem"], row["archetype"], int(row["page_number"])

    markup_path = root / row["html"]
    image_path = root / row["images"]
    record_path = root / (row.get("record") or row["json"])
    if not (markup_path.is_file() and image_path.is_file() and record_path.is_file()):
        return None

    markup = markup_path.read_text(encoding="utf-8")
    record = json.loads(record_path.read_text(encoding="utf-8"))

    # HTML trần mang luôn hộp: `markdown/` không được là một bản chỉ có chữ.
    # Hộp lấy từ `entity_annotations` theo thứ tự -- cùng HỆ 0..1000 với
    # `word_boxes/` và `layout_boxes/`, nên ba file nói về cùng một tấm ảnh
    # bằng cùng một hệ. (Câu này trước đây nói "cùng hệ toạ độ pixel"; hệ đã
    # đổi ở `pipeline/record.py`, và một chú thích nói hệ cũ còn tệ hơn không
    # có chú thích nào.)
    plain = sheet_html(markup, page,
                       [e.get("bbox") for e in record.get("entity_annotations") or []])
    if plain.strip():
        target = root / "markdown" / kind / f"{stem}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(plain, encoding="utf-8")

    # KIE ĐẦY ĐỦ: `pipeline/kie.py` chỉ ghép được chỗ có nhãn in kèm, và bỏ
    # lại 89% số đoạn chữ có hộp -- toàn bộ ô bảng, tiêu đề cột, ghi chú,
    # tiêu đề tài liệu, con dấu. `kie_full.complete` lấp nốt và ghi lại vào
    # chính bản ghi, nên ai đọc `json/` cũng thấy.
    full, counts = complete(record, markup)

    # Đổi giọng mô tả: luật nằm ở `synthgen/phrasing.py::voice_record`, một
    # chỗ duy nhất, vì `draw_llm.py` cũng phải gọi nó ngay lúc vẽ. Một lượt
    # không tới lượt `derive` thì bản ghi trên đĩa nằm lại với câu tả gốc, và
    # câu gốc thì lặp -- đo trên `data/thu1k`: 8 564 câu tả, 171 câu khác nhau.
    #
    # `rank` của job thắng số đọc từ tên file khi có: nó là hạng THẬT trong
    # lượt chạy, còn tên file chỉ là chỗ đỡ.
    ordinal = job.get("rank")
    if ordinal is None:
        ordinal = ordinal_of(stem)
    voice_record(record, full, stem=stem, ordinal=ordinal)
    record.setdefault("kie", {})["pairs"] = full
    record["kie"]["coverage"] = counts

    # Cùng một KIE, hai cách nói. `pairs` có HỘP -- để chấm định vị. `schema`
    # + `value` là JSON Schema và một instance khớp nó -- để sinh JSON có
    # ràng buộc. Không cái nào thay được cái nào: schema không mang toạ độ,
    # còn danh sách cặp thì không ép được đầu ra của một mô hình.
    schema, value = build_schema(record)
    record["kie"]["schema"] = schema
    record["kie"]["value"] = value
    # Và bản chỉ tả TỜ NÀY. Bản ghi được chép bên cạnh từng tờ, nên file của
    # tờ hai phải trả lời được "trên tấm ảnh này có gì" mà không kéo theo
    # những dòng chỉ có trên tờ một -- (ảnh, nhãn) mà nhãn đòi thứ ngoài ảnh
    # là một cặp không học được.
    page_schema, page_value = build_schema(record, page)
    record["kie"]["page_schema"] = page_schema
    record["kie"]["page_value"] = page_value

    # Toạ độ HỆ 1000 bên cạnh pixel, ở mọi chỗ có hộp. Đó là thứ một mô hình
    # thị giác - ngôn ngữ đọc và sinh ra, và nó không đổi khi tấm ảnh bị thu
    # nhỏ -- cùng một tờ giấy đo 1113 hay 2226 pixel thì hộp vẫn là một dãy
    # số. Pixel KHÔNG bị thay: quy về hệ 1000 là một phép làm tròn, đi ngược
    # lại không ra đúng chỗ cũ, và một bộ dữ liệu chỉ có số đã làm tròn thì
    # không ai kiểm lại được nó.
    grid_record(record)
    record_path.write_text(
        json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    pairs = [p for p in full if int(p.get("page_number", 1) or 1) == page]

    # `word_boxes/` mang mô tả KIE trên từng hộp từ, nên nó phải đi theo bảng
    # cặp mới chứ không giữ bảng cũ -- nếu không, một hộp từ trong bảng vẫn
    # trống mô tả trong khi bản ghi cạnh nó đã có.

    # `layout_boxes/*.json` và `word_boxes/*.json` không còn được ghi ra: cả
    # hai là lát cắt của chính bản ghi vừa lưu, và `overlay.slice_for` dựng lại
    # đúng từng byte. Xem `draw.py::write`.

    image = cv2.imread(str(image_path))
    if image is None:
        return None
    # `{value_entity_index: field_type}` -- cùng lệ tra cứu `kinds` đã dùng
    # khắp `synthgen/export.py`, không đọc lại từ `kie.pairs` (field_type
    # không nằm ở đó, xem `pipeline/record.py::field_type_for`'s docstring).
    field_types = {e.get("entity_index"): str(e.get("field_type") or "")
                  for e in record.get("entity_annotations") or []}
    drawing = O.kie(image, pairs, page, field_types)
    ok, buffer = cv2.imencode(".jpg", drawing, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if ok:
        target = root / "visualize_kie" / kind / f"{stem}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(buffer.tobytes())

    return {
        "stem": stem,
        "archetype": kind,
        "page_number": page,
        "pages_in_document": int(row["pages_in_document"]),
        "kie_on_page": len(pairs),
        "kie_coverage": counts["coverage"],
        "kie_by_source": counts["by_source"],
        "plain_bytes": len(plain),
        "shapes": sorted(name for name, mark in SHAPES.items() if mark in markup),
        # Chỉ trang MỘT mang schema về tiến trình cha: bản ghi tả cả tài liệu
        # nên mọi trang của nó ra cùng một schema, và gửi cả hai mươi nghìn
        # bản sao về là hai mươi nghìn lần chép vô ích.
        "schema": schema if page == 1 else None,
    }


def pick(rows: list[dict], want: int) -> list[dict]:
    """~`want` trang, phủ đủ LOẠI chứng từ và đủ KIỂU BẢNG.

    Bốc ngẫu nhiên `want` trang từ hai mươi nghìn thì ra một tập trông giống
    cả bộ về mặt thống kê và bỏ sót đúng những thứ hiếm -- mà cái hiếm mới là
    cái người xem mẫu muốn nhìn. Nên bốc theo VÒNG: mỗi vòng lấy một trang
    cho mỗi loại chứng từ, ưu tiên trang mang kiểu bảng chưa ai mang, rồi mới
    tới trang nhiều tờ, rồi tới phần còn lại."""
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_kind[row["archetype"]].append(row)

    seen_shapes: set[str] = set()
    picked: list[dict] = []
    taken: set[str] = set()

    def score(row: dict) -> tuple:
        fresh = len(set(row["shapes"]) - seen_shapes)
        return (-fresh, -len(row["shapes"]),
                -min(row["pages_in_document"], 3), -row["kie_on_page"])

    kinds = sorted(by_kind)
    while len(picked) < want:
        added = 0
        for kind in kinds:
            if len(picked) >= want:
                break
            pool = [r for r in by_kind[kind] if r["stem"] not in taken]
            if not pool:
                continue
            best = min(pool, key=score)
            picked.append(best)
            taken.add(best["stem"])
            seen_shapes.update(best["shapes"])
            added += 1
        if not added:
            break
    return picked


# Bảy thứ đi theo một trang vào thư mục mẫu: ảnh, markup gốc, HTML trần, bản
# ghi, hai bộ hộp (mỗi bộ json + ảnh), và ảnh KIE.
SAMPLE_KINDS = (
    ("images", "images", ".jpg"),
    ("html", "html", ".html"),
    ("markdown", "markdown", ".html"),
    ("records", "records", ".json"),
    ("layout_boxes", "layout_boxes", ".json"),
    ("layout_boxes", "layout_boxes", ".jpg"),
    ("word_boxes", "word_boxes", ".json"),
    ("word_boxes", "word_boxes", ".jpg"),
    ("visualize_kie", "visualize_kie", ".jpg"),
)


def write_sample(root: Path, chosen: list[dict], out: Path) -> int:
    """Chép các trang đã chọn vào một chỗ, KHÔNG chia theo loại nữa.

    Thư mục mẫu để NGƯỜI mở ra xem, và người thì mở một thư mục chứ không lội
    ba mươi hai ngăn. Tên gốc vẫn mang tên loại (`hoa_don_gtgt_00123`) nên
    không mất thông tin nào."""
    written = 0
    for row in chosen:
        stem, kind = row["stem"], row["archetype"]
        for source, folder, suffix in SAMPLE_KINDS:
            # `mkdir` khi thật sự có file chép sang, không dựng sẵn mười hai
            # ngăn rồi để rỗng vài cái.
            src = root / source / kind / f"{stem}{suffix}"
            if src.is_file():
                target = out / folder / f"{stem}{suffix}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                written += 1
    (out / "index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in chosen),
        encoding="utf-8")
    return written


def _migrate_layout(root: Path, manifest: Path) -> int:
    """Bộ định dạng cũ (`json/` = bản ghi từng tờ) -> `records/`. Số file dời.

    Đọc khoá `json` trong manifest, dời cây thư mục, rồi ghi lại manifest với
    khoá `record`. Chạy lại lần hai không làm gì -- manifest lúc ấy đã mang
    khoá mới."""
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    rows = [json.loads(line) for line in lines]
    if not rows or "json" not in rows[0] or rows[0].get("record"):
        return 0
    if (root / "records").exists():
        print("[derive] đã có records/ mà manifest vẫn trỏ json/ — dừng, "
              "không đoán bừa cái nào mới hơn")
        raise SystemExit(1)
    (root / "json").rename(root / "records")
    for row in rows:
        where = row.pop("json", "")
        if where:
            row["record"] = where.replace("json/", "records/", 1)
    manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8")
    print(f"[derive] bộ định dạng cũ: dời {len(rows)} bản ghi json/ -> records/ "
          "(json/ giờ dành cho bản gộp theo tài liệu)")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="thư mục đã sinh xong")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--sample", type=int, default=200,
                        help="số trang gom vào thư mục mẫu; 0 = bỏ qua")
    parser.add_argument("--limit", type=int, default=0,
                        help="chỉ xử lý N trang đầu -- để thử")
    parser.add_argument("--documents", type=int, default=1, metavar="N",
                        help="gộp tài liệu từ N tờ trở lên vào json/; "
                             "mặc định 1 = mọi tài liệu; 0 = bỏ qua")
    args = parser.parse_args()

    root = args.run.resolve()
    manifest = root / "manifest.jsonl"
    if not manifest.is_file():
        print(f"không có {manifest} — đây có phải thư mục đã sinh xong không?")
        return 1

    # BẢNG MÔ TẢ CỦA CHÍNH LƯỢT CHẠY, trỏ lại trước khi dựng lại nhãn.
    #
    # `synthgen/run.py` ghi `kie_descriptions.json` vào thư mục lượt chạy rồi
    # đặt `VLM_KIE_DESCRIPTIONS` cho tiến trình vẽ -- đó là nguồn TỐT NHẤT
    # trong bốn nguồn của `pipeline.kie.describe`. Nhưng `derive.py` là một
    # tiến trình khác, chạy sau, và nó không đặt biến ấy: `_all_descriptions()`
    # đọc chuỗi rỗng, trả `{}`, rồi mọi trường tụt xuống nguồn thứ hai.
    #
    # Hệ quả đo được trên `data/thu1k`: file có `dia_chi` -> "Registered
    # address of the seller." nhưng cặp dựng lại mang câu suy từ `kind`, và
    # lượt vẽ với lượt dựng lại nói hai câu khác nhau về cùng một trường. Mười
    # lăm megabyte mô tả viết sẵn nằm cạnh bản ghi mà không ai đọc.
    ledger = root / "kie_descriptions.json"
    if ledger.is_file():
        os.environ["VLM_KIE_DESCRIPTIONS"] = str(ledger)

    # Bộ sinh TRƯỚC ngày đổi tên để bản ghi từng tờ ở `json/`. Bản gộp theo
    # tài liệu cũng muốn ghi vào `json/<loại>/<tài liệu>.json`, mà tên ấy TRÙNG
    # đúng đường dẫn bản ghi của tờ 1 -- nên chạy derive trên một bộ cũ là ghi
    # đè, và tờ 1 mất sạch hộp từ, vùng bố cục, cặp KIE. Đo được: sau một lượt
    # derive, `hoa_don_gtgt_00014.json` thành bản gộp còn `_p2`, `_p3` vẫn là
    # bản ghi.
    #
    # Nên dời trước, một lần, rồi mới làm gì khác. Không hỏi: giữ nguyên là
    # chắc chắn mất dữ liệu, và người chạy lệnh này không có cách nào biết
    # trước điều đó.
    migrated = _migrate_layout(root, manifest)

    rows = [json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    # TRANG TRƯỢT CỔNG KHÔNG VÀO BỘ ĐEM HUẤN LUYỆN.
    #
    # `draw_llm` cố ý vẽ cả `rejected/` -- người sửa lời dặn phải nhìn được tờ
    # hỏng, và ảnh của chúng nằm ở `rejected_boxes/`. Nhưng manifest mang cả
    # hai, nên `json/`, `markdown/`, `visualize_kie/` cũng dựng cho chúng: đo
    # trên pilot10 và pilot11, mỗi bộ một tài liệu đã bị cổng loại vẫn có mặt
    # đủ trong `json/`.
    #
    # Một tài liệu pipeline đã vứt mà vẫn nằm trong bộ giao đi là một tài liệu
    # không ai định đưa vào huấn luyện nhưng ai cũng sẽ đưa. `llm_passed_gate`
    # đã đánh dấu sẵn; chỉ là chưa ai đọc nó.
    kept = [r for r in rows if r.get("llm_passed_gate", True)]
    dropped = len(rows) - len(kept)
    rows = kept
    if args.limit:
        rows = rows[:args.limit]
    print(f"[derive] {len(rows)} trang trong {root}"
          + (f" ({dropped} trang trượt cổng để lại ở rejected_boxes/)"
             if dropped else ""))

    import concurrent.futures as cf

    made: list[dict] = []
    done = 0
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        # HẠNG của tài liệu trong LOẠI của nó, không phải chỉ số toàn cục.
        # Tên file mang chỉ số toàn cục (`hoa_don_gtgt_00014`, rồi `_00148`),
        # nên khoảng cách giữa hai tài liệu liền nhau của một loại là 134 chứ
        # không phải 1 -- quay vòng vẫn tốt hơn bốc, nhưng trùng mỗi khi khoảng
        # cách ấy chia hết cho số cách nói. Đo được: 7.6%.
        #
        # Đánh hạng 0,1,2,... trong từng loại thì hai tài liệu liền nhau lệch
        # đúng một bước, và không trùng cho tới lúc hết bảng. Tính ở đây, một
        # lần, từ manifest -- tiến trình con không thấy được thứ tự của cả bộ.
        rank: dict[str, int] = {}
        seen: dict[str, int] = {}
        for row in rows:
            base = re.sub(r"_p\d+$", "", str(row["stem"]))
            if base not in rank:
                kind = str(row["archetype"])
                rank[base] = seen.get(kind, 0)
                seen[kind] = rank[base] + 1
        jobs = ({"root": str(root), "row": row,
                 "rank": rank.get(re.sub(r"_p\d+$", "", str(row["stem"])), 0)}
                for row in rows)
        for result in pool.map(_one, jobs, chunksize=16):
            done += 1
            if result:
                made.append(result)
            if done % 2000 == 0:
                print(f"  {done}/{len(rows)}", flush=True)

    print(f"[derive] markdown/ + visualize_kie/: {len(made)} trang")
    if len(made) < len(rows):
        print(f"[derive] {len(rows) - len(made)} trang thiếu file, đã bỏ qua")

    shapes: dict[str, int] = defaultdict(int)
    for row in made:
        for name in row["shapes"]:
            shapes[name] += 1
    print("[derive] kiểu bảng trong bộ:",
          ", ".join(f"{k}={v}" for k, v in sorted(shapes.items())))

    # Schema gộp theo LOẠI chứng từ: chỗ duy nhất `required` có nghĩa -- một
    # trường là bắt buộc khi nó có mặt trên gần như mọi tờ của loại ấy.
    by_kind: dict[str, list] = defaultdict(list)
    for row in made:
        if row.get("schema") and len(by_kind[row["archetype"]]) < 400:
            by_kind[row["archetype"]].append(row["schema"])
    folder = root / "kie_schemas"
    folder.mkdir(parents=True, exist_ok=True)
    for kind, schemas in sorted(by_kind.items()):
        (folder / f"{kind}.json").write_text(
            json.dumps(merge_schema(schemas), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
    print(f"[derive] schema theo loại: {len(by_kind)} file -> {folder}")
    for row in made:
        row.pop("schema", None)

    if args.sample:
        chosen = pick(made, args.sample)
        out = root / "sample"
        files = write_sample(root, chosen, out)
        kinds = len({row["archetype"] for row in chosen})
        covered = sorted({s for row in chosen for s in row["shapes"]})
        print(f"[derive] mẫu: {len(chosen)} trang, {kinds} loại chứng từ, "
              f"{files} file -> {out}")
        print(f"[derive] kiểu bảng có trong mẫu: {', '.join(covered)}")

    # Mỗi tài liệu một file phẳng theo trang -- MỘT tờ hay nhiều tờ đều cùng
    # hình dạng ấy, nên bên đọc không phải hỏi file này thuộc loại nào.
    # Ở đây chứ không phải một lệnh thứ hai người phải nhớ: nó đọc cùng cái
    # manifest và cùng những bản ghi vừa ghi xong, nên tách ra chỉ tạo cơ hội
    # cho hai thứ lệch nhau.
    if args.documents:
        from synthgen.export import run as export_run  # noqa: PLC0415

        export_run(root, root, min_pages=args.documents, limit=0,
                   with_images=False, indent=1, by_kind=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
