#!/usr/bin/env python3
"""Thống kê một lô đã sinh bằng `agent/compose_page.py`.

    python -m tools.llm.corpus_stats data/pilot-llm

Đọc `compose_report.json` (đã có sẵn `pages[]`, `why_tally`, token/giây) và
`html/**/*.html` (để đo `data-path` coverage -- `compose_report.json` không
giữ HTML). Không tự vẽ, không gọi model: script này chạy xong việc `agent.
compose_page` đã làm.

## Phạm vi (task 2.4, `docs/ke-hoach-refactor-engine.md`)

Đo được NGAY BÂY GIỜ: tần suất document family (`doc_slug`), tỉ lệ qua cổng,
mã lỗi (`pipeline.failures`), tỉ lệ `data-path` coverage, và tỉ lệ trang xin
bảng (`table_asked`). KHÔNG đo table morphology / layout topology / density
profile / hard-negative profile -- những khái niệm ấy chưa tồn tại trong
code (Phase 3 chưa viết grammar, Phase 4 chưa viết `DocumentPlan`, Phase 6
chưa viết hard-negative record). In rõ "chưa đo được" cho từng mục thay vì
suy diễn số liệu không có nguồn.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import failures as F                         # noqa: E402
from synthgen.llm_page import path_coverage                # noqa: E402


def _family_counts(pages: list[dict]) -> Counter:
    return Counter(str(p.get("archetype") or "?") for p in pages)


def _path_coverage_stats(html_files: list[str]) -> dict:
    covered = [path_coverage(Path(f).read_text(encoding="utf-8", errors="replace"))
              ["coverage"] for f in html_files]
    if not covered:
        return {"pages": 0, "min": None, "max": None, "mean": None}
    return {"pages": len(covered), "min": round(min(covered), 3),
           "max": round(max(covered), 3),
           "mean": round(sum(covered) / len(covered), 3)}


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
        "not_measurable_yet": {
            "table_morphology": "chưa có khái niệm -- Phase 3 (grammar) chưa viết",
            "layout_topology": "chưa có khái niệm -- Phase 3/4 chưa viết",
            "density_profile": "chưa có khái niệm -- Phase 4 (DocumentPlan) chưa viết",
            "hard_negative_profile": "không tồn tại trong code -- Phase 6 chưa viết",
            "structural_diversity_fingerprint": "chưa có -- Phase 4.2 (coarse/mid/fine)",
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
