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


def diversity_gate() -> tuple[float, int]:
    """`(trần tỉ lệ, sàn số lượt)` -- ĐỌC từ `rulebase/synthgen/_kie_gates.yaml`.

    Không viết cứng ở đây: cùng file ấy đã giữ mọi trần khác của mô tả KIE, và
    một con số thứ hai nằm trong mã là thứ sẽ lệch khỏi nó khi ai đó siết
    cổng. Thiếu file thì trả `(0.0, 0)` -- báo cáo vẫn in tỉ lệ, chỉ không
    cảnh báo, vì cái thiếu là một phép chấm ĐIỂM chứ không phải một phép đo."""
    import yaml  # noqa: PLC0415

    try:
        raw = yaml.safe_load(
            (REPO_ROOT / "rulebase" / "synthgen" / "_kie_gates.yaml")
            .read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return 0.0, 0
    limit = raw.get("thresholds") or {}
    return (float(limit.get("description_diversity") or 0.0),
            int(limit.get("description_diversity_floor") or 0))


def diversity(rows) -> list[dict]:
    """Đa dạng CÂU TẢ cho từng cặp `(loại giấy, kind)`: duy nhất / tổng lượt.

    Vì sao đo ở mức cặp chứ không ở mức bộ: một con số cho cả bộ trộn lẫn hai
    chuyện khác hẳn nhau. `store.name` lặp một câu trên hai trăm tờ là ĐÚNG --
    tên đơn vị phát hành nghĩa như nhau ở mọi tờ. `store.tax_code` lặp một câu
    trong khi nó in HAI LẦN trên cùng một tờ là sai, vì hai lần ấy là hai bên
    khác nhau. Chỉ khi tách theo cặp thì hai chuyện ấy mới nằm ở hai dòng.

    Đo lúc viết (24-09-2026, 785 tệp `data/*/declared`, 11.847 lượt): tỉ lệ
    toàn cục 0,3785 -- và nó giấu mất `authorisation_letter/meta.value` 1/55
    = 0,018 nằm bên trong. Đó là cùng hình dạng lỗi mà
    `data/review100d/kie_descriptions.json` mang: 63.060 cặp khoá→câu tả gom
    lại còn 247 câu khác nhau."""
    per: dict[tuple[str, str], dict] = {}
    for doc_type, key, text in rows:
        cell = per.setdefault((doc_type, key), {"n": 0, "said": set()})
        cell["n"] += 1
        cell["said"].add(text)
    ceiling, floor = diversity_gate()
    out = []
    for (doc_type, key), cell in per.items():
        uniq, total = len(cell["said"]), cell["n"]
        out.append({"doc_type": doc_type, "kind": key, "unique": uniq,
                    "total": total, "ratio": round(uniq / total, 4),
                    "scored": total >= floor,
                    "under": bool(floor and total >= floor
                                  and ceiling and uniq / total < ceiling)})
    out.sort(key=lambda r: (r["ratio"], -r["total"]))
    return out


def measure(docs) -> dict:
    """Đếm theo tầng cho cả hai không gian tên, cộng phần 'trước'."""
    generic = {space: set(FT.registry().generic.get(space) or ())
               for space in FT.SPACES}
    counts = {space: collections.Counter() for space in FT.SPACES}
    before = {space: collections.Counter() for space in FT.SPACES}
    staged = {space: collections.Counter() for space in FT.SPACES}
    families = {space: collections.Counter() for space in FT.SPACES}
    groups = collections.Counter()
    said: list[tuple[str, str, str]] = []
    catchall = collections.Counter()
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
            if got.space == FT.KIND:
                # CÂU TẢ ĐÃ GHÉP HAI LỚP, không câu của sổ: đây là chuỗi thật
                # sự đi ra bộ huấn luyện, nên nó mới là thứ đáng đo đa dạng.
                said.append((kind, got.key, got.description))
                if got.leaves:
                    catchall[f"{got.key} ({kind})"] += 1
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
            "families": families, "groups": groups, "docs": len(docs),
            "diversity": diversity(said), "catchall": catchall}


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

    # ------------------------------------------- đa dạng câu tả, theo cặp
    rows = got["diversity"]
    ceiling, floor = diversity_gate()
    scored = [r for r in rows if r["scored"]]
    under = [r for r in rows if r["under"]]
    total_n = sum(r["total"] for r in rows)
    total_u = sum(r["unique"] for r in rows)
    lines += ["", "## Đa dạng câu tả -- câu duy nhất / lượt trường", "",
              f"Toàn cục **{total_u}/{total_n} = "
              f"{(total_u / total_n if total_n else 0):.4f}** trên "
              f"{len(rows)} cặp `(loại giấy, kind)`. Chấm điểm "
              f"{len(scored)} cặp có từ {floor} lượt (trần {ceiling:.2f}); "
              f"phần còn lại quá ít lượt để tỉ lệ nói được gì -- xem "
              "`description_diversity_floor` trong `_kie_gates.yaml`.", ""]
    if under:
        # CẢNH BÁO, một dòng một cặp. Không gộp thành một con số: cái phải
        # sửa là một cặp cụ thể, và một tỉ lệ trung bình thì không sửa được.
        lines += [f"**{len(under)} cặp dưới trần {ceiling:.2f}** -- câu tả sập "
                  "về khuôn dù nội dung tờ giấy đổi:", ""]
        for r in under:
            lines.append(
                f"- ⚠ `{r['doc_type']}/{r['kind']}` -- {r['unique']} câu cho "
                f"{r['total']} lượt ({r['ratio']:.4f})")
        lines.append("")
    else:
        lines += [f"Không cặp nào dưới trần {ceiling:.2f}.", ""]
    worst = [r for r in scored][:12]
    if worst:
        lines += ["Thấp nhất trước, trong các cặp được chấm:", "",
                  "| loại giấy | kind | duy nhất | lượt | tỉ lệ |",
                  "| --- | --- | ---: | ---: | ---: |"]
        lines += [f"| `{r['doc_type']}` | `{r['kind']}` | {r['unique']} | "
                  f"{r['total']} | {r['ratio']:.4f} |" for r in worst]
        lines.append("")

    # ------------------------------------------------ khoá hứng chung còn lại
    catch = got["catchall"].most_common(10)
    if catch:
        lines += ["## Khoá hứng chung kèm câu tả riêng -- ca nên tách", "",
                  "Mỗi dòng là một chỗ model đã BIẾT trường ấy là gì (nó viết "
                  "được câu tả) mà vẫn gọi tên bằng thùng hứng. Lá thay thế "
                  "nằm ở `generic.leaves` trong `rulebase/field_tiers.json`; "
                  "tầng `semi_open` nhận chúng sẵn, không cần mã mới.", "",
                  "| khoá (loại giấy) | lượt |", "| --- | ---: |"]
        lines += [f"| `{name}` | {n} |" for name, n in catch]
        lines.append("")
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
             "groups": dict(got["groups"]),
             "diversity": got["diversity"],
             "catchall": dict(got["catchall"])}, ensure_ascii=False, indent=1))
    else:
        print(report(got))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
