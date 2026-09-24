#!/usr/bin/env python3
"""Đo TRÙNG BỐ CỤC trên một lô đã vẽ xong, và so hai lô với nhau.

    python -m tools.llm.diversity_report data/24-09-div-after
    python -m tools.llm.diversity_report data/24-09-div-before data/24-09-div-after

Đọc `records/**/*.json` -- tức `layout_annotations` THẬT do Chromium đo, sau
khi `synthgen/draw_llm.py` đã vẽ -- rồi chấm từng tờ bằng khoảng cách tới
láng giềng gần nhất trong cửa sổ (`agent/geometry_distance.py`).

## Vì sao không gộp vào `tools/llm/corpus_stats.py`

Docstring của file ấy nói thẳng phạm vi của nó: `compose_report.json` + HTML
thô, và "KHÔNG đo ... những số đó cần ẢNH đã vẽ và `records/`". Đây đúng là
loại số ấy. Giữ ranh giới đó nghĩa là `corpus_stats` vẫn chạy được trên một
lô `--no-draw` không có `records/` nào, còn script này thì nói thẳng là
không có gì để đọc.

## Vì sao nó tồn tại song song với số trong `compose_report.json`

`agent/diversity.py` đã ghi đúng những con số này trong lúc chạy. Script này
đo LẠI từ bản ghi trên đĩa, và đó là chủ ý: hai lượt chạy so được với nhau
chỉ khi chúng được chấm bằng cùng một thước ĐỘC LẬP với thứ đang được thử.
Một lô sinh bằng mã cũ (không có khoá `diversity`) vẫn chấm được ở đây, và
đó là cách duy nhất có một con số "trước" thật.

Số ở đây và số trong `compose_report.json` KHÔNG buộc phải bằng nhau, và chỗ
chúng lệch là chỗ đọc được:

- cổng hình học chỉ nhìn tờ đã qua cổng CHỮ, còn `--only all` ở đây nhìn cả
  tờ trượt;
- `_reconcile_sheet_count` lật vài tờ từ đạt sang trượt SAU khi cổng hình
  học đã chạy, nên một tờ từng nằm trong cửa sổ lúc chạy có thể không còn
  nằm trong `html/` lúc đo lại.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.fingerprint import geometry_fingerprint          # noqa: E402
from agent.geometry_distance import (JACCARD_CEILING,       # noqa: E402
                                     WINDOW, corpus_geometry, nearest)


def _document(stem: str) -> str:
    """`llm_x_0003_p2` -> `llm_x_0003`. Mọi tờ của một tài liệu ghi CÙNG một
    bản ghi, nên đếm từng tệp là đếm một tài liệu nhiều lần."""
    head, _, tail = stem.rpartition("_p")
    return head if head and tail.isdigit() else stem


def order_of(root: Path) -> dict:
    """Thứ tự SINH của từng stem, đọc từ `compose_report.json`.

    Cửa sổ trượt theo thứ tự sinh, nên thứ tự là một phần của phép đo, không
    phải chuyện trình bày. Không có báo cáo (lô cũ, hay vẽ tay bằng
    `draw_llm` đơn) thì rơi về thứ tự tên tệp -- `llm_<family>_<NNNN>` có số
    chỉ mục ở cuối nên nó xấp xỉ đúng thứ tự ấy."""
    path = root / "compose_report.json"
    if not path.is_file():
        return {}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for page in report.get("pages") or []:
        stem = f"llm_{page.get('archetype')}_{int(page.get('index', 0)):04d}"
        out[stem] = int(page.get("index", 0))
    return out


def load(root: Path, only: str = "kept") -> list:
    """`[(stem, GeometryFingerprint)]` theo thứ tự sinh.

    `only="kept"` chỉ lấy tài liệu còn nằm trong `html/` -- tức bộ thật sự
    giao ra. `only="all"` lấy mọi tài liệu đã vẽ, kể cả tờ trượt cổng chữ:
    mẫu lớn hơn, và nó trả lời một câu khác ("model có tự lặp không", không
    phải "bộ giao ra có lặp không")."""
    kept = {p.stem for p in (root / "html").glob("*.html")}
    ranks = order_of(root)
    seen: dict = {}
    for path in sorted((root / "records").glob("*/*.json")):
        doc = _document(path.stem)
        if doc in seen:
            continue
        if only == "kept" and kept and doc not in kept:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        layout = record.get("layout_annotations") or []
        if not layout:
            continue
        seen[doc] = geometry_fingerprint(layout)
    return sorted(seen.items(), key=lambda kv: (ranks.get(kv[0], 10**6), kv[0]))


def worst_pairs(items: list, window: int, how_many: int = 5) -> list:
    """Mấy cặp gần nhau nhất trong cửa sổ -- để đọc bằng MẮT, không bằng số.

    Một tỉ lệ nói có bao nhiêu tờ lặp; chỉ hai cái tên cạnh nhau nói lặp cái
    gì, và chỉ hai tấm ảnh nói tỉ lệ ấy có đáng tin không."""
    out = []
    for i in range(1, len(items)):
        stem, fingerprint = items[i]
        best = nearest(fingerprint, items[max(0, i - window):i])
        if best is not None:
            out.append((best[1], best[2], stem, best[0]))
    return sorted(out, key=lambda row: -row[0])[:how_many]


def measure(root: Path, only: str, window: int, ceiling: float) -> dict:
    items = load(root, only)
    summary = corpus_geometry([fp for _, fp in items], window, ceiling)
    summary["root"] = str(root)
    summary["only"] = only
    summary["worst"] = [
        {"jaccard": round(j, 4), "hamming": round(h, 4), "page": a, "against": b}
        for j, h, a, b in worst_pairs(items, window)]
    return summary


def show(summary: dict) -> None:
    near = summary["nearest_jaccard"]
    print(f"\n== {summary['root']}  ({summary['only']})")
    print(f"   {summary['documents']} tài liệu, cửa sổ {summary['window']}, "
          f"ngưỡng {summary['ceiling']}, lưới {summary['grid']}")
    print(f"   láng giềng gần nhất: trung vị {near['median']}  "
          f"p90 {near['p90']}  lớn nhất {near['max']}")
    print(f"   vượt ngưỡng: {summary['over_ceiling']}/{summary['documents']} "
          f"({100 * summary['over_ceiling_share']:.1f}%)")
    print(f"   tập ô khác nhau: {summary['distinct_cell_sets']}/"
          f"{summary['documents']}")
    widest = max(summary["jaccard_histogram"].values() or [1])
    for label, count in summary["jaccard_histogram"].items():
        print(f"     {label}  {count:4d}  "
              f"{'█' * round(30 * count / max(widest, 1))}")
    if summary["worst"]:
        print("   gần nhau nhất:")
        for row in summary["worst"]:
            print(f"     J={row['jaccard']:.3f} H={row['hamming']:.3f}  "
                  f"{row['page']}  ~  {row['against']}")


def compare(before: dict, after: dict) -> None:
    """Bảng "trước / sau" cho đúng bốn con số, và phần trăm giảm.

    Phần trăm giảm tính trên TỈ LỆ, không trên số đếm: hai lô hiếm khi giao
    ra đúng bằng nhau số tờ (tỉ lệ qua cổng chữ dao động), và so hai số đếm
    trên hai mẫu số khác nhau là một cách nói dối rất dễ."""
    def drop(a: float, b: float) -> str:
        if not a:
            return "   —  " if not b else "  tăng"
        return f"{100 * (a - b) / a:+6.1f}%"

    rows = [
        ("tờ vượt ngưỡng (tỉ lệ)", before["over_ceiling_share"],
         after["over_ceiling_share"]),
        ("láng giềng gần nhất, trung vị", before["nearest_jaccard"]["median"],
         after["nearest_jaccard"]["median"]),
        ("láng giềng gần nhất, p90", before["nearest_jaccard"]["p90"],
         after["nearest_jaccard"]["p90"]),
        ("láng giềng gần nhất, lớn nhất", before["nearest_jaccard"]["max"],
         after["nearest_jaccard"]["max"]),
    ]
    print("\n== TRƯỚC / SAU")
    print("   cột cuối là phần trăm GIẢM: số dương là bớt trùng, số âm là "
          "trùng thêm")
    print(f"   {'':32s} {'trước':>8s} {'sau':>8s}   giảm")
    for label, a, b in rows:
        a = 0.0 if a is None else a
        b = 0.0 if b is None else b
        print(f"   {label:32s} {a:8.4f} {b:8.4f}  {drop(a, b)}")
    print(f"   {'số tài liệu đo được':32s} {before['documents']:8d} "
          f"{after['documents']:8d}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("roots", nargs="+", type=Path,
                        help="thư mục `-o` của agent.compose_page (1 hoặc 2)")
    parser.add_argument("--only", choices=("kept", "all"), default="kept",
                        help="`kept`: chỉ tài liệu còn trong html/ (mặc định)")
    parser.add_argument("--window", type=int, default=WINDOW)
    parser.add_argument("--ceiling", type=float, default=JACCARD_CEILING)
    parser.add_argument("--json", type=Path, default=None,
                        help="ghi kết quả đầy đủ ra tệp JSON")
    args = parser.parse_args()

    summaries = [measure(root, args.only, args.window, args.ceiling)
                 for root in args.roots]
    for summary in summaries:
        show(summary)
        if not summary["documents"]:
            print("   (không bản ghi nào có `layout_annotations` -- lô này đã "
                  "chạy `--no-draw`, hay `records/` chưa được vẽ?)")
    if len(summaries) == 2:
        compare(summaries[0], summaries[1])
    if args.json:
        args.json.write_text(
            json.dumps(summaries, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        print(f"\n-> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
