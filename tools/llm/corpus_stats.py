#!/usr/bin/env python3
"""Thống kê một lô đã sinh bằng `agent/compose_page.py`.

    python -m tools.llm.corpus_stats data/pilot-llm

Đọc `compose_report.json` (đã có sẵn `pages[]`, `why_tally`, token/giây) và
`html/**/*.html` (để đo `data-path` coverage -- `compose_report.json` không
giữ HTML). Không tự vẽ, không gọi model: script này chạy xong việc `agent.
compose_page` đã làm.

## Phạm vi (task 2.4, cập nhật task 7.3, `docs/ke-hoach-refactor-engine.md`)

Đo được: tần suất document family, tỉ lệ qua cổng, mã lỗi
(`pipeline.failures`), tỉ lệ `data-path` coverage, tỉ lệ trang xin bảng
(`table_asked`), **document diversity** (Phase 7.2 -- `distinct coarse/mid/
fine` và khoảng cách trung bình theo cặp, đọc lại từ `engine_plan`/
`hard_negative_profile` mỗi trang, KHÔNG đọc hình học -- xem `agent.
document_distance`), và **hard-negative coverage** (Phase 6 -- bao nhiêu
trang được hỏi có mồi giả, bao nhiêu trang thật sự khai `data-decoy-for`).

KHÔNG đo missing-box rate / text-table confusion rate / duplicate-render
rate ở đây -- những số đó cần ẢNH đã vẽ và `records/` của `synthgen/
draw_llm.py::Drawer` (chạy khi `agent.compose_page` không có `--no-draw`),
và công cụ đo là `synthgen/check.py` chạy trên thư mục ấy, không phải script
này (script này chỉ đọc `compose_report.json` + HTML thô). Xem Phase 8
(`docs/ke-hoach-refactor-engine.md`).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.document_distance import corpus_diversity        # noqa: E402
from agent.document_plan import DocumentPlan                # noqa: E402
from agent.fingerprint import fingerprint                   # noqa: E402
from pipeline import failures as F                         # noqa: E402
from synthgen.llm_page import coined, path_coverage         # noqa: E402


def _family_counts(pages: list[dict]) -> Counter:
    return Counter(str(p.get("archetype") or "?") for p in pages)


def _document_diversity(pages: list[dict]) -> dict:
    """Phase 7.2/7.3: diversity ĐỌC LẠI TỪ `engine_plan`/`hard_negative_
    profile` mỗi trang trong `compose_report.json` -- không cần `DocumentPlan`
    gốc, `agent/compose_page.py::one()` đã ghi đủ hai trường ấy để dựng lại
    một `DocumentPlan` tương đương rồi tính fingerprint (Phase 4.2)."""
    fps = [
        fingerprint(DocumentPlan(family=str(p.get("archetype") or ""),
                                 assignment=dict(p.get("engine_plan") or {}),
                                 hard_negative_profile=dict(
                                     p.get("hard_negative_profile") or {})))
        for p in pages
    ]
    return corpus_diversity(fps)


_DECOY_ATTR = re.compile(r'data-decoy-for="([^"]+)"')


def _hard_negative_coverage(pages: list[dict], html_dir: Path) -> dict:
    """Phase 6: bao nhiêu trang được ENGINE hỏi có mồi giả (`hard_negative_
    profile` khác rỗng trong `DocumentPlan`), và bao nhiêu trang MODEL thật
    sự khai `data-decoy-for` trong HTML nó viết ra. Hai con số khác nhau
    có chủ đích -- số đầu là engine YÊU CẦU, số sau là model THỰC HIỆN, và
    khoảng cách giữa chúng là thứ Phase 8.2 cần theo dõi.

    Đếm bằng regex trên chính thuộc tính, không qua `kie_full.
    hard_negative_spans` -- hàm ấy ghép span với `entity_annotations` thật
    (Phase 6.2), thứ script này không có (chỉ đọc HTML thô, không đọc
    `record.json`). Đếm SỰ CÓ MẶT của `data-decoy-for` không cần ghép gì."""
    asked = [p for p in pages if p.get("hard_negative_profile")]
    realized_pages = 0
    realized_decoys = 0
    for page in asked:
        stem = f"llm_{page.get('archetype', '?')}_{int(page.get('index', 0)):04d}"
        html_path = html_dir / f"{stem}.html"
        if not html_path.is_file():
            continue
        found = _DECOY_ATTR.findall(
            html_path.read_text(encoding="utf-8", errors="replace"))
        if found:
            realized_pages += 1
            realized_decoys += len(found)
    return {
        "pages_asked": len(asked),
        "pages_realized": realized_pages,
        "decoys_realized": realized_decoys,
        "realization_rate": (round(realized_pages / len(asked), 4)
                             if asked else None),
    }


def _path_coverage_stats(html_files: list[str]) -> dict:
    covered = [path_coverage(Path(f).read_text(encoding="utf-8", errors="replace"))
              ["coverage"] for f in html_files]
    if not covered:
        return {"pages": 0, "min": None, "max": None, "mean": None}
    return {"pages": len(covered), "min": round(min(covered), 3),
           "max": round(max(covered), 3),
           "mean": round(sum(covered) / len(covered), 3)}


def _coined_kinds(html_files: list[str]) -> dict:
    """Tên `data-kind` model TỰ ĐẶT: bao nhiêu tên, bao nhiêu trang, tên nào.

    Từ vựng kind đã mở (`synthgen/llm_page.py::_COINED`), và mở là một quyết
    định có giá: `synthgen/kie_schema.groups()` khoá theo TIỀN TỐ kind, nên
    hai tờ gọi cùng một khái niệm bằng hai cái tên sẽ nằm ở hai nhóm schema.
    Không đếm thì không ai biết điều ấy đang tới đâu.

    Đọc ngược lại: một danh sách dài toàn tên dùng ĐÚNG MỘT LẦN là dấu hiệu
    model đang đặt tên tuỳ hứng; vài tên lặp lại nhiều trang là nó đang đặt
    tên cho khái niệm thật mà từ vựng engine thiếu -- và đó là lúc thêm chúng
    vào `rulebase/kie_groups.json`."""
    from collections import Counter                              # noqa: PLC0415

    tally: Counter = Counter()
    pages_with = 0
    for path in html_files:
        fresh = coined(Path(path).read_text(encoding="utf-8", errors="replace"))
        if fresh:
            pages_with += 1
        tally.update(fresh)
    return {
        "pages": len(html_files),
        "pages_with_coined_kinds": pages_with,
        "distinct": len(tally),
        "used_once": sum(1 for n in tally.values() if n == 1),
        "top": dict(tally.most_common(15)),
    }


def stats(out: Path) -> dict:
    report_path = out / "compose_report.json"
    if not report_path.exists():
        raise SystemExit(f"không thấy {report_path} -- đây có phải thư mục "
                         "`-o` của agent.compose_page không?")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pages = report.get("pages") or []
    kept = [p for p in pages if p.get("ok")]

    all_reasons = [why for p in pages for why in (p.get("why") or [])]
    codes = report.get("failure_codes") or F.tally(all_reasons)

    return {
        "asked": report.get("asked"),
        "kept": len(kept),
        "pass_rate": round(len(kept) / max(len(pages), 1), 4),
        "family_counts": dict(_family_counts(pages).most_common()),
        "table_asked_rate": round(
            sum(1 for p in pages if p.get("table_asked")) / max(len(pages), 1), 4),
        "failure_codes": codes,
        "data_path_coverage_on_kept_pages": _path_coverage_stats(
            sorted(glob.glob(str(out / "html" / "*" / "*.html")))),
        "data_path_coverage_on_rejected_pages": _path_coverage_stats(
            sorted(glob.glob(str(out / "rejected" / "*.html")))),
        "coined_kinds": _coined_kinds(
            sorted(glob.glob(str(out / "html" / "*" / "*.html")))),
        # PHASE 7.3: hai bảng số RIÊNG -- "dressing diversity" là việc của
        # `agent/distance.py` (track 1, hình học, không chạy được trên track
        # 3 -- xem Phase 7.1) nên không có mặt ở đây. Bảng dưới đây CHỈ đo
        # document diversity (family/density/table-morphology/field-hoá,
        # đọc từ `DocumentPlan`, Phase 4.2/7.2), tách bạch khỏi mọi thứ liên
        # quan tới hình dáng trang.
        "document_diversity": _document_diversity(kept),
        "hard_negative_coverage": _hard_negative_coverage(kept, out / "html"),
        "not_measurable_here": {
            "missing_box_rate": "cần ảnh đã vẽ + records/ -- chạy "
                "`synthgen/check.py` trên thư mục này (Phase 8.2), không "
                "phải script chỉ đọc compose_report.json/HTML này",
            "text_table_confusion_rate": "cùng lý do trên",
            "duplicate_or_near_duplicate_rate": "cùng lý do trên",
            "dressing_diversity": "không áp dụng cho track 3 -- track 3 "
                "không có phôi để so trước/sau dressing (xem Phase 7.1)",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path, help="thư mục `-o` của agent.compose_page")
    args = parser.parse_args()
    result = stats(args.out.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
