#!/usr/bin/env python3
"""Ba tầng tên trường, đo trên bộ đã sinh: TRƯỚC và SAU, cùng một mẫu.

    python3 tools/llm/field_tiers_report.py data/23-09-llm-i data/pilot16
    python3 tools/llm/field_tiers_report.py --all          # mọi data/*/declared

"Trước" ở đây không phải một lượt chạy cũ -- nó là **chính những tên model đã
viết**, đọc lại từ `declared/*.json`, chấm bằng luật cũ. Luật cũ có đúng một
đích cho một cái tên không tra được: khoá hứng chung (`meta.value`,
`invoice.field`, `invoice.field.label`), vì lời dặn bảo model "take the nearest"
và `synthgen/repair.py::settle` ánh xạ nốt phần còn lại. "Sau" là cùng những cái
tên ấy đi qua `synthgen/field_tier.py`.

So trên cùng một mẫu, không trên hai lượt chạy khác nhau: hai lượt chạy khác
nhau thì mọi con số đổi vì mọi lý do, và kho này đã một lần kết luận sai vì đo
bộ sinh ra trước bản vá (`docs/bon-muc-kiem-soat-nhan-llm.md` §1.2).
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import field_tier as FT  # noqa: E402


def declared(roots: list[Path]) -> list[tuple[Path, dict]]:
    """Mọi `declared/*.json` dưới các thư mục đã cho."""
    out = []
    for root in roots:
        for path in sorted(root.glob("declared/*.json")):
            try:
                out.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
    return out


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:6.1%}" if whole else "     -"


def measure(docs) -> dict:
    """Đếm theo tầng cho cả hai không gian tên, cộng phần 'trước'."""
    generic = {space: set(FT.registry().generic.get(space) or ())
               for space in FT.SPACES}
    counts = {space: collections.Counter() for space in FT.SPACES}
    before = {space: collections.Counter() for space in FT.SPACES}
    staged = {space: collections.Counter() for space in FT.SPACES}
    families = {space: collections.Counter() for space in FT.SPACES}
    groups = collections.Counter()
    for _path, doc in docs:
        kind = str(doc.get("archetype") or "")
        title = str(doc.get("doc_title") or "")
        groups[FT.doc_group(kind, title)] += 1
        decisions = (
            FT.classify_plan((doc.get("plan") or {}).get("field_plan"),
                             doc_type=kind, doc_title=title)
            + FT.classify_data(doc.get("data"), doc_type=kind, doc_title=title))
        for got in decisions:
            counts[got.space][got.tier] += 1
            before[got.space]["generic" if got.key in generic[got.space]
                              else "named"] += 1
            if got.tier == FT.STAGING:
                # HAI LOẠI `staging`, và chúng đòi hai việc khác nhau.
                #
                # Mọi `declared/*.json` đã có trên đĩa sinh ra TRƯỚC khi schema
                # có khoá `describe`, nên một lá mới trong họ quen không thể
                # mang câu tả -- nó rơi xuống `staging` vì thiếu câu tả, không
                # vì cái tên. Đếm gộp hai loại ấy làm một là nói rằng tầng
                # `semi_open` không dùng được, trong khi thật ra nó chưa được
                # HỎI lần nào. Tách ra thì con số đọc được: cột `chờ câu tả`
                # là thứ lượt chạy tới tự thu, cột `họ lạ` là thứ người phải
                # soát.
                bucket = ("needs_sentence"
                          if got.family
                          and got.family in FT.registry().families[got.space]
                          else "unknown_family")
                staged[got.space][f"#{bucket}"] += 1
            if not got.in_batch:
                staged[got.space][got.key] += 1
                if got.family:
                    families[got.space][got.family] += 1
    return {"counts": counts, "before": before, "staged": staged,
            "families": families, "groups": groups, "docs": len(docs)}


def report(got: dict) -> str:
    lines = [f"# Ba tầng tên trường -- {got['docs']} tệp `declared/`", ""]
    for space in FT.SPACES:
        counts = got["counts"][space]
        total = sum(counts.values())
        if not total:
            continue
        lines += [f"## Không gian `{space}` -- {total} lượt", "",
                  "| tầng | lượt | phần |", "| --- | ---: | ---: |"]
        for tier in FT.TIERS:
            lines.append(f"| `{tier}` | {counts[tier]} | {_pct(counts[tier], total)} |")
        in_batch = counts[FT.CLOSED] + counts[FT.SEMI_OPEN]
        lines += [f"| **vào bộ chính** | {in_batch} | {_pct(in_batch, total)} |", ""]
        # `declared/` cũ không có khoá `describe`, nên tầng `semi_open` chưa
        # được hỏi lần nào trên mẫu này -- xem lời giải thích ở `measure()`.
        wait = got["staged"][space].pop("#needs_sentence", 0)
        alien = got["staged"][space].pop("#unknown_family", 0)
        if wait or alien:
            lines += [
                f"Trong {counts[FT.STAGING]} lượt `staging`: **{wait}** "
                f"({_pct(wait, total).strip()}) là lá mới trong HỌ QUEN, chờ "
                "đúng một câu tả -- lượt chạy tới tự thu được vì schema mới đã "
                f"xin `describe`; **{alien}** ({_pct(alien, total).strip()}) là "
                "họ lạ, phải người soát.", ""]
        gen = got["before"][space]["generic"]
        lines += [f"Trước: {gen} lượt ({_pct(gen, total).strip()}) rơi vào khoá "
                  f"hứng chung ({', '.join(sorted(FT.registry().generic[space])) or 'không có'}).",
                  ""]
        fam = got["families"][space].most_common(12)
        if fam:
            lines += ["Họ chờ soát, nhiều nhất trước:", "",
                      "| họ | lượt |", "| --- | ---: |"]
            lines += [f"| `{name}` | {n} |" for name, n in fam]
            lines.append("")
        top = got["staged"][space].most_common(12)
        if top:
            lines += ["Khoá chờ soát, nhiều nhất trước:", "",
                      "| khoá | lượt |", "| --- | ---: |"]
            lines += [f"| `{name}` | {n} |" for name, n in top]
            lines.append("")
    lines += ["## Nhóm loại chứng từ của mẫu này", "",
              "| nhóm | tài liệu |", "| --- | ---: |"]
    lines += [f"| `{name}` | {n} |" for name, n in got["groups"].most_common()]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true",
                    help="mọi thư mục data/* có declared/")
    ap.add_argument("--json", action="store_true", help="in JSON thay vì bảng")
    args = ap.parse_args()

    roots = list(args.roots)
    if args.all or not roots:
        roots = sorted(p.parent for p in (REPO_ROOT / "data").glob("*/declared"))
    docs = declared(roots)
    if not docs:
        print("không có `declared/*.json` nào dưới: "
              + ", ".join(str(r) for r in roots), file=sys.stderr)
        return 1
    got = measure(docs)
    if args.json:
        print(json.dumps(
            {"docs": got["docs"],
             "counts": {s: dict(c) for s, c in got["counts"].items()},
             "before": {s: dict(c) for s, c in got["before"].items()},
             "groups": dict(got["groups"])}, ensure_ascii=False, indent=1))
    else:
        print(report(got))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
