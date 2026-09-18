#!/usr/bin/env python3
"""Phân phối của một `agent_plan.json`, trước khi có ảnh nào được vẽ.

    python tools/plan_distribution.py data/llm200/agent_plan.json

Kế hoạch được quyết xong trong vài giây; vẽ nó mất hàng chục phút. Đây là cái
nhìn giữa hai mốc đó: mỗi thuộc tính bốc ra gì, bao nhiêu lần, lệch bao nhiêu
so với TỶ LỆ MỤC TIÊU mà `--profile` khai (nếu lượt chạy dùng
`tools/mock_llm.py`), và giá trị nào chưa bao giờ tới lượt.

Không thuộc tính nào, không id nào được viết trong file này: bảng đọc thẳng từ
`force` của từng quyết định, thứ tự cột đọc từ thứ tự khoá của kế hoạch. Thêm
một thuộc tính vào rulebase thì nó tự có mặt ở đây.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path

BAR = "█"


def bar(fraction: float, width: int = 22) -> str:
    filled = int(round(fraction * width))
    return BAR * filled + "·" * (width - filled)


def families(ids, patterns) -> dict[str, str]:
    """id -> glob đầu tiên khớp nó, "" nếu không glob nào khớp."""
    out = {}
    for one in ids:
        out[one] = next((str(p) for p in patterns if fnmatchcase(one, str(p))), "")
    return out


def table(title: str, counts: Counter, total: int, targets: dict | None,
          limit: int, defined: int | None = None) -> None:
    head = f"── {title} ── {len(counts)} giá trị được dùng"
    if defined:
        head += f"/{defined} có thể bốc"
    print(f"\n{head}")
    rows = counts.most_common()
    shown = rows if limit <= 0 else rows[:limit]
    family = families([one for one, _ in rows], (targets or {}).keys())
    for one, number in shown:
        share = number / total
        want = ""
        if targets:
            pattern = family.get(one, "")
            if pattern:
                want = f"  [họ {pattern}]"
        print(f"  {one:<32} {number:>4}  {share:6.1%}  {bar(share / max(0.001, rows[0][1] / total))}{want}")
    if len(rows) > len(shown):
        rest = sum(number for _, number in rows[len(shown):])
        print(f"  {'… ' + str(len(rows) - len(shown)) + ' giá trị nữa':<32} "
              f"{rest:>4}  {rest / total:6.1%}")
    if targets:
        roll = Counter()
        for one, number in rows:
            roll[family.get(one, "(còn lại)")] += number
        print(f"  {'':<32} ── theo họ, thực tế vs mục tiêu ──")
        for pattern, number in roll.most_common():
            want = targets.get(pattern)
            note = f"mục tiêu {want:.0%}" if want is not None else ""
            drift = ""
            if want:
                delta = number / total - want
                drift = f"  {'+' if delta >= 0 else ''}{delta:.1%}"
            print(f"    {pattern or '(còn lại)':<30} {number:>4}  "
                  f"{number / total:6.1%}  {note}{drift}")


def cost(decisions: list, rules_root: Path, blender_seconds: float,
         plain_seconds: float) -> None:
    """Ước lượng thời gian vẽ, tách theo ĐỘNG CƠ warp chứ không theo tên.

    Một giá trị `augmentation` đắt khi `params.warp.name` là một mesh của
    `degradation.blender.meshes.MESHES` — lúc ấy một tờ giấy được dựng thành
    mặt 3D và render thật. Đọc từ params, nên một warp mới thêm vào rulebase
    tự vào đúng cột mà không phải kể tên ở đây.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rulebase.spec import load_rules

    try:
        from degradation.blender.meshes import MESHES
    except Exception:                                   # noqa: BLE001
        print("\n(không import được degradation.blender.meshes — bỏ ước lượng)")
        return
    rules = load_rules(rules_root)
    engine = {}
    for option in rules.get("augmentation", ()):
        warp = (option.params or {}).get("warp") or {}
        name = str(warp.get("name") or "")
        engine[option.id] = ("blender" if name in MESHES
                             else ("warp" if name else ""))
    heavy = [d for d in decisions
             if engine.get(d["force"].get("augmentation", ""), "") == "blender"]
    counts = Counter(d["force"]["augmentation"] for d in heavy)
    seconds = len(heavy) * blender_seconds + (len(decisions) - len(heavy)) * plain_seconds
    print(f"\n── ước lượng thời gian vẽ ──")
    print(f"  {len(heavy)}/{len(decisions)} trang ({len(heavy) / len(decisions):.0%}) "
          f"dựng mặt 3D và render bằng Blender ≈ {blender_seconds:.0f}s/trang: "
          + ", ".join(f"{k}×{v}" for k, v in counts.most_common()))
    print(f"  còn lại ≈ {plain_seconds:.0f}s/trang")
    print(f"  tổng CPU ≈ {seconds / 60:.0f} phút — chia cho --workers, "
          f"cộng thời gian vẽ proof")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="<out>/agent_plan.json")
    parser.add_argument("--profile", type=Path, default=None,
                        help="tools/mock_llm.yaml — để in kèm tỷ lệ mục tiêu")
    parser.add_argument("--report", type=Path, default=None,
                        help="<out>/agent_report.json — nguồn DUY NHẤT cho "
                             "'chưa bao giờ bốc': nó do planner.unused() viết "
                             "trên bộ luật đã compose, nên biết giá trị nào bị "
                             "tắt cố ý. `<out>/rules` trên đĩa KHÔNG biết: "
                             "materialise_rules không ghi `enabled: false`")
    parser.add_argument("--rules", type=Path, default=None,
                        help="<out>/rules — chỉ để đọc params.warp, ước lượng "
                             "thời gian vẽ")
    parser.add_argument("--sec-blender", type=float, default=98.0,
                        help="giây mỗi ảnh có warp hình học dựng bằng Blender; "
                             "mặc định đo từ data/page_curl20/batch_report.json")
    parser.add_argument("--sec-plain", type=float, default=2.0,
                        help="giây mỗi ảnh còn lại")
    parser.add_argument("--limit", type=int, default=12,
                        help="số dòng mỗi thuộc tính, 0 = tất cả")
    parser.add_argument("--pairs", type=int, default=10)
    args = parser.parse_args()

    decisions = json.loads(args.plan.read_text(encoding="utf-8"))
    if not decisions:
        print("kế hoạch rỗng")
        return 1
    total = len(decisions)
    order = list(decisions[0]["force"].keys())

    share = {}
    if args.profile:
        import yaml

        share = (yaml.safe_load(args.profile.read_text(encoding="utf-8"))
                 or {}).get("share") or {}

    report = args.report
    if report is None:
        candidate = args.plan.parent / "agent_report.json"
        report = candidate if candidate.exists() else None
    defined: dict[str, int] = {}
    never: dict[str, list] = {}
    if report is not None:
        payload = json.loads(Path(report).read_text(encoding="utf-8"))
        defined = {name: spec.get("defined", 0) for name, spec
                   in ((payload.get("coverage") or {}).get("attributes") or {}).items()}
        never = payload.get("never_drawn") or {}

    rules_root = args.rules
    if rules_root is None:
        candidate = args.plan.parent / "rules"
        rules_root = candidate if candidate.exists() else None

    by = Counter(d.get("by", "?") for d in decisions)
    triples = {tuple(d["force"].get(k, "") for k in ("document", "layout", "variant"))
               for d in decisions}
    print(f"KẾ HOẠCH {args.plan} — {total} trang")
    print(f"  quyết bởi: " + ", ".join(f"{k}={v}" for k, v in by.most_common()))
    print(f"  tổ hợp document|layout|variant khác nhau: {len(triples)}/{total}")
    refused = [d for d in decisions if d.get("note")]
    if refused:
        print(f"  luật từ chối đề xuất ở {len(refused)} trang "
              f"(ví dụ: {refused[0]['note']})")

    for attribute in order:
        counts = Counter(d["force"][attribute] for d in decisions)
        table(attribute, counts, total, share.get(attribute),
              args.limit, defined.get(attribute))

    if rules_root is not None:
        cost(decisions, rules_root, args.sec_blender, args.sec_plain)

    if report is not None:
        print("\n── chưa bao giờ được bốc (giá trị bị tắt cố ý không tính) ──")
        listed = {a: v for a, v in never.items() if v}
        for attribute, missing in listed.items():
            print(f"  {attribute:<14} {len(missing):>3}: {', '.join(missing[:14])}"
                  + (" …" if len(missing) > 14 else ""))
        if not listed:
            print("  (không — mọi giá trị bốc được đều đã có mặt)")

    pairs = Counter((d["force"]["document"], d["force"]["layout"]) for d in decisions)
    print(f"\n── document × layout ── {len(pairs)} cặp khác nhau")
    for (document, layout), number in pairs.most_common(args.pairs):
        print(f"  {document:<32} {layout:<30} {number:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
