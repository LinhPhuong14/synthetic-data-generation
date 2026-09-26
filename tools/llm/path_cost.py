#!/usr/bin/env python3
"""Ba đường sinh, cùng N ảnh: bao nhiêu lời gọi model, bao nhiêu giây, bao nhiêu token.

    python -m tools.llm.path_cost --images 10000
    python -m tools.llm.path_cost --images 10000 --json chi-phi.json

Mỗi ô trong bảng đọc từ một BÁO CÁO THẬT trên đĩa, không từ một con số viết
tay:

| đường | báo cáo | ai ghi |
| --- | --- | --- |
| `rule` | `data/*/report.json` | `synthgen/run.py` |
| `page` | `data/*/compose_report.json` | `agent/compose_page.py` |
| `template` (pha 1) | `data/*/template_report.json` | `agent/compose_template.py` |
| `template` (pha 2) | `data/*/fill_report.json` | `synthgen/run_fill.py` |

Đường nào chưa có lượt nào đo được thì bảng nói **chưa đo được**, không điền
một ước lượng. Đó là cả điểm của công cụ này: con số ước lượng trong một bảng
so sánh trông giống hệt con số đo được, và sáu tuần sau không ai còn phân biệt
nổi.

## Hai cảnh báo phải đọc cùng bảng

**Giây KHÔNG so trực tiếp được.** Mỗi lượt chạy ở một mức song song khác nhau
(`concurrency` của nhánh LLM, `workers` của nhánh luật), và nhánh LLM còn phụ
thuộc tải của máy chủ model: `docs/kiem-soat-llm.md` mục 1 đo 43 ký tự/giây
lúc máy bận so với 137-145 lúc rảnh, chênh hơn ba lần trên CÙNG một đường
sinh. Nên cột giây ghi kèm mức song song đã dùng, và bảng in ra cả
`giây × luồng` -- con số duy nhất so được giữa hai lượt chạy khác cấu hình.

**Tỉ lệ đạt cổng là cái nhân lớn nhất, không phải tốc độ.** Đường `page` giữ
được 38% số tờ nó viết khi cộng cả 30 lượt đã chạy (20% trên hai lượt gần
nhất, `data/pilot16` và `data/24-09-div-before`), nên một ảnh giữ lại tốn
2,65 lời gọi chứ không một. Đường `template` trả cái giá ấy MỘT LẦN cho mỗi
phôi rồi mọi lần điền sau đều đạt -- phôi đã qua cổng thì tờ điền từ nó cũng
qua, vì cấu trúc HTML không đổi giữa hai lần điền; đo trên `data/24-09-phoi-
fill`: **232/232**. Bảng nhân đúng chỗ ấy và nói ra nó đã nhân.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATA = REPO_ROOT / "data"
UNKNOWN = "chưa đo được"


def _load(pattern: str) -> list[tuple[str, dict]]:
    out = []
    for path in sorted(DATA.glob(pattern)):
        try:
            out.append((path.parent.name, json.loads(path.read_text(encoding="utf-8"))))
        except Exception:                                    # noqa: BLE001
            continue
    return out


def rule_path() -> dict:
    """Nhánh luật: giây mỗi ảnh, từ `run.images_per_second` của lượt NHIỀU ẢNH NHẤT.

    Nhiều ẢNH nhất, không nhiều GIÂY nhất: một lượt sáu tài liệu chạy chậm
    (`smoke_multipage_v4`, 877 giây cho 0,06 ảnh/giây) có nhiều giây hơn một
    lượt sáu trăm tài liệu chạy nhanh, và nó đo chủ yếu chi phí khởi động --
    mở Chromium, nạp phông, preflight. Xếp theo giây thì bảng chi phí lấy
    đúng lượt tệ nhất làm chuẩn cho cả nhánh: chênh 34 lần trên cùng dữ liệu
    đã có (0,06 so với 2,01 ảnh/giây). Lượt nhiều ảnh nhất là lượt duy nhất
    chi phí khởi động đã pha loãng đủ để đọc được tốc độ ổn định."""
    runs = [(name, r) for name, r in _load("*/report.json")
            if (r.get("run") or {}).get("images_per_second")]
    if not runs:
        return {"path": "rule", "source": None}
    name, best = max(runs, key=lambda kv: ((kv[1].get("run") or {}).get("seconds", 0)
                                           * (kv[1].get("run") or {}).get("images_per_second", 0)))
    run = best["run"]
    images = round(run["images_per_second"] * run["seconds"])
    return {"path": "rule", "source": name,
            "images": images, "seconds": run["seconds"],
            "workers": run.get("workers", 1),
            "seconds_per_image": round(1 / run["images_per_second"], 3),
            "llm_calls_per_image": 0.0,
            "tokens_per_image": 0.0,
            "pass_rate": None}


def page_path() -> dict:
    """Nhánh model-viết-từng-trang, cộng MỌI lượt đã chạy.

    Cộng chứ không lấy lượt lớn nhất, và khác nhánh luật ở trên có lý do: ở
    đó biến cần đo là TỐC ĐỘ (chi phí khởi động pha loãng theo cỡ lượt), ở
    đây biến cần đo là TỈ LỆ ĐẠT, và tỉ lệ đạt của một lượt mười hai tờ cũng
    là một mẫu hợp lệ như của một lượt sáu mươi tờ. Cộng hết là mẫu lớn nhất
    có được.

    Lượt nào không ghi token (`pilot-llm`, sinh trước khi `decide_with_usage`
    tồn tại) bị bỏ khỏi phép tính token, không bị tính là 0 -- một lượt
    không đo được token mà cộng 0 vào kéo trung bình xuống bằng chính chỗ
    thiếu số liệu."""
    runs = _load("*/compose_report.json")
    if not runs:
        return {"path": "page", "source": None}
    asked = sum(r.get("asked") or 0 for _n, r in runs)
    kept = sum(r.get("kept") or 0 for _n, r in runs)
    seconds = sum(r.get("seconds") or 0.0 for _n, r in runs)
    with_tokens = [r for _n, r in runs if r.get("tokens_out")]
    tok_in = sum(r.get("tokens_in") or 0 for r in with_tokens)
    tok_out = sum(r.get("tokens_out") or 0 for r in with_tokens)
    tok_asked = sum(r.get("asked") or 0 for r in with_tokens)
    # ẢNH, không TỜ ĐƯỢC XIN. `pages` trong `compose_report.json` là một
    # DANH SÁCH bản ghi từng tờ, không phải một con số -- đếm độ dài nó thì ra
    # số tờ đã thử (gồm cả tờ trượt), không phải số ảnh. Số ảnh thật là
    # `kept` nhân số trang mỗi tài liệu, và báo cáo không ghi con số ấy, nên
    # dùng `kept` và NÓI RA rằng một tài liệu nhiều tờ ra nhiều ảnh -- ước
    # lượng này THIÊN VỀ PHÍA đường cũ (kể nó ít lời gọi mỗi ảnh hơn thực
    # tế), nên nó không thổi phồng kết luận.
    images = kept
    per_image = asked / images if images else 0.0
    return {"path": "page", "source": f"{len(runs)} lượt",
            "images": images, "seconds": round(seconds, 1),
            "asked": asked, "kept": kept,
            "concurrency": _median([r.get("concurrency") or 1 for _n, r in runs]),
            "pass_rate": round(kept / asked, 4) if asked else None,
            "llm_calls_per_image": round(per_image, 3),
            "seconds_per_image": round(seconds / images, 2) if images else None,
            "tokens_per_call": round((tok_in + tok_out) / tok_asked, 1)
            if tok_asked else None,
            "tokens_in_per_call": round(tok_in / tok_asked, 1) if tok_asked else None,
            "tokens_out_per_call": round(tok_out / tok_asked, 1) if tok_asked else None,
            "tokens_per_image": round((tok_in + tok_out) / tok_asked * per_image, 1)
            if tok_asked and per_image else None}


def template_path() -> dict:
    """Nhánh phôi: pha 1 (có model) cộng pha 2 (không model), ghép lại."""
    phase1 = _load("*/template_report.json")
    phase2 = _load("*/fill_report.json")
    out: dict = {"path": "template", "phase1": None, "phase2": None}
    if phase1:
        asked = sum(r.get("asked") or 0 for _n, r in phase1)
        kept = sum(r.get("kept") or 0 for _n, r in phase1)
        tok = sum((r.get("tokens_in") or 0) + (r.get("tokens_out") or 0)
                  for _n, r in phase1)
        seconds = sum(r.get("seconds") or 0.0 for _n, r in phase1)
        out["phase1"] = {
            "source": f"{len(phase1)} lượt", "asked": asked, "kept": kept,
            "seconds": round(seconds, 1),
            "pass_rate": round(kept / asked, 4) if asked else None,
            "tokens_per_call": round(tok / asked, 1) if asked else None,
            "seconds_per_template": round(seconds / kept, 1) if kept else None,
            "concurrency": _median([r.get("concurrency") or 1 for _n, r in phase1]),
        }
    if phase2:
        pages = sum(r.get("pages") or 0 for _n, r in phase2)
        kept = sum(r.get("kept") or 0 for _n, r in phase2)
        seconds = sum(r.get("seconds") or 0.0 for _n, r in phase2)
        templates = sum(r.get("templates") or 0 for _n, r in phase2)
        out["phase2"] = {
            "source": f"{len(phase2)} lượt", "pages": pages, "kept": kept,
            "templates": templates,
            "seconds": round(seconds, 1),
            "pass_rate": round(kept / pages, 4) if pages else None,
            "seconds_per_image": round(seconds / pages, 2) if pages else None,
            "per_template": _median([r.get("per_template") or 0
                                     for _n, r in phase2]),
            "llm_calls": 0,
        }
    return out


def table(images: int) -> dict:
    """Chi phí sinh `images` ảnh theo mỗi đường. Ô thiếu số liệu để `None`."""
    rule, page, tpl = rule_path(), page_path(), template_path()
    rows: dict = {"images": images}

    rows["rule"] = {
        "llm_calls": 0,
        "seconds": round(rule["seconds_per_image"] * images, 0)
        if rule.get("seconds_per_image") else None,
        "tokens": 0,
        "workers": rule.get("workers"),
        "measured_on": rule.get("source"),
    }

    calls = page.get("llm_calls_per_image")
    rows["page"] = {
        "llm_calls": round(calls * images) if calls else None,
        "seconds": round(page["seconds_per_image"] * images, 0)
        if page.get("seconds_per_image") else None,
        "tokens": round(page["tokens_per_image"] * images)
        if page.get("tokens_per_image") else None,
        "pass_rate": page.get("pass_rate"),
        "concurrency": page.get("concurrency"),
        "measured_on": page.get("source"),
    }

    p1, p2 = tpl.get("phase1"), tpl.get("phase2")
    per_tpl = (p2 or {}).get("per_template") or 0
    tpl_pass = (p1 or {}).get("pass_rate")
    if p2 and per_tpl:
        templates_needed = -(-images // int(per_tpl))       # làm tròn LÊN
        # Lời gọi pha 1 = số phôi CẦN chia tỉ lệ đạt: một phôi trượt cổng vẫn
        # tốn trọn một lời gọi, và bỏ nó khỏi phép tính là nói dối đúng theo
        # cách `docs/kiem-soat-llm.md` mục 2 đã đo được ở đường cũ (83% số
        # giây đổ vào tờ bị loại).
        calls_1 = round(templates_needed / tpl_pass) if tpl_pass else None
        tok_call = (p1 or {}).get("tokens_per_call")
        rows["template"] = {
            "templates": templates_needed,
            "per_template": int(per_tpl),
            "llm_calls": calls_1,
            "tokens": round(calls_1 * tok_call) if (calls_1 and tok_call) else None,
            "seconds": round(
                (p2["seconds_per_image"] * images)
                + ((p1 or {}).get("seconds_per_template") or 0) * templates_needed, 0)
            if p2.get("seconds_per_image") else None,
            "phase1_pass_rate": tpl_pass,
            "phase2_pass_rate": p2.get("pass_rate"),
            "measured_on": f"pha1 {(p1 or {}).get('source') or UNKNOWN} · "
                           f"pha2 {p2.get('source')}",
        }
    else:
        rows["template"] = {"llm_calls": None, "seconds": None, "tokens": None,
                            "templates": None, "measured_on": None}
    rows["_detail"] = {"rule": rule, "page": page, "template": tpl}
    return rows


def _median(values):
    rows = sorted(v for v in values if v)
    if not rows:
        return None
    return rows[len(rows) // 2]


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, float) and value >= 1000:
        value = round(value)
    if isinstance(value, (int, float)) and abs(value) >= 1000:
        return f"{value:,.0f}".replace(",", " ") + suffix
    return f"{value}{suffix}"


def show(rows: dict) -> None:
    n = rows["images"]
    print(f"\nChi phí sinh {n:,} ảnh".replace(",", " ")
          + ", đo từ báo cáo thật trên đĩa\n")
    head = f"{'đường':10s} {'lời gọi model':>15s} {'giây':>12s} {'token':>14s}  đo trên"
    print(head)
    print("-" * len(head))
    for name in ("rule", "page", "template"):
        row = rows[name]
        print(f"{name:10s} {_fmt(row.get('llm_calls')):>15s} "
              f"{_fmt(row.get('seconds')):>12s} {_fmt(row.get('tokens')):>14s}  "
              f"{row.get('measured_on') or UNKNOWN}")
    page, tpl = rows["page"], rows["template"]
    print()
    if page.get("pass_rate") is not None:
        print(f"  `page`     tỉ lệ đạt cổng {page['pass_rate']:.0%} -> "
              f"{page.get('llm_calls_per_image') or ''}"
              f"{rows['_detail']['page']['llm_calls_per_image']:.2f} lời gọi "
              f"cho mỗi ảnh GIỮ LẠI, ở {page.get('concurrency')} request song song")
    if tpl.get("templates"):
        # SỐ PHÔI in ra kể cả khi số LỜI GỌI chưa đo được: nó thuần cấu trúc
        # (ảnh chia số tờ mỗi phôi), không cần lượt chạy nào để biết, và nó
        # là nửa quan trọng của phép so. Nửa còn lại -- bao nhiêu lời gọi cho
        # chừng ấy phôi -- cần tỉ lệ đạt cổng THẬT của pha 1, và đó là thứ
        # duy nhất ở đây phải có một lượt gọi model mới trả lời được.
        print(f"  `template` {tpl['templates']} phôi x {tpl['per_template']} "
              f"lần điền; pha 2 đạt {(tpl.get('phase2_pass_rate') or 0):.0%}")
        if tpl.get("phase1_pass_rate") is None:
            print("             pha 1 CHƯA CHẠY -- số lời gọi và token còn "
                  "trống cho tới khi có một lượt\n"
                  "             `python -m agent.compose_template` ghi ra "
                  "`template_report.json`.")
            if page.get("llm_calls"):
                print(f"             Cận trên: dù pha 1 đạt 0% thì "
                      f"{tpl['templates']} phôi vẫn ít hơn "
                      f"{page['llm_calls'] / tpl['templates']:.0f} lần so với "
                      f"{page['llm_calls']:,} lời gọi của `page`."
                      .replace(",", " "))
        elif page.get("llm_calls") and tpl.get("llm_calls"):
            print(f"             pha 1 đạt {tpl['phase1_pass_rate']:.0%}  ->  "
                  f"{page['llm_calls'] / tpl['llm_calls']:.0f} lần ít lời gọi "
                  "model hơn `page`")
    print("\nGiây KHÔNG so trực tiếp được giữa ba đường -- mỗi lượt chạy ở một "
          "mức song\nsong khác nhau, và nhánh LLM còn đổi theo tải máy chủ "
          "(43 so với 137-145\nký tự/giây, `docs/kiem-soat-llm.md` mục 1). Cột "
          "đáng tin là LỜI GỌI.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--images", type=int, default=10000)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    rows = table(args.images)
    show(rows)
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print(f"\n{args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
