#!/usr/bin/env python3
"""Vì sao một lô LLM trượt cổng -- gộp theo NGUYÊN NHÂN, và so hai lô.

    python -m tools.llm.gate_reasons data/pilot18
    python -m tools.llm.gate_reasons data/pilot17 data/pilot18
    python -m tools.llm.gate_reasons data/pilot18 --pages   # từng tờ một

## Vì sao script này tồn tại

Lý do trượt ĐÃ được ghi sẵn: `compose_report.json` có `pages[i].why`, và
`performance.md` có bảng "Vì sao trượt". Không thiếu dữ liệu -- thiếu một
chỗ ĐỌC nó.

Cái giá của việc thiếu chỗ đọc đo được thật: một lượt soát lô `data/pilot17`
đã mở `rejected/*.html` với ảnh hộp trong `rejected_boxes/` ra đọc bằng mắt,
rồi rút ra ba nguyên nhân -- và **cả ba đều không phải lý do cổng đã loại**:

  đọc bằng mắt kết luận            cổng thật sự nói
  ------------------------------   ---------------------------------------
  header bị gán hai vùng chồng     0 `data-region`, 100% run mồ côi
  `data-path` trùng y nguyên chữ   `unclash()` CỐ Ý cho phép; không tờ
                                   nào trượt vì nó
  bảng mất hộp hàng thứ 4          thiếu `data-kind` họ `sign.`

Và tỉ lệ qua cổng bị đọc thành 85% trong khi số thật là 17%. Đọc HTML thô
bằng mắt là một phép đo tệ; `why` thì nói thẳng. Một dòng lệnh thay cho một
buổi đọc.

## Gộp thế nào

`why` mang số cụ thể trong câu ("xin 8 tờ nhưng dàn trang thật chỉ ra 3 tờ"),
nên gộp thô theo chuỗi thì mỗi tờ một nhóm. `_family()` thay mọi con số bằng
`N` để những câu cùng LOẠI về chung một dòng, và giữ một ví dụ nguyên văn cho
mỗi loại -- tổng hợp mà không mất chỗ để mổ.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

# Mọi cụm số -- kể cả `8`, `100%`, `0,99` -- về một dấu `N`, để "xin 8 tờ ...
# ra 3 tờ" và "xin 2 tờ ... ra 1 tờ" là CÙNG một nguyên nhân.
_NUM = re.compile(r"\d+([.,]\d+)?%?")
# Tên phôi trong ngoặc: "engine plan (invoice_detailed) yêu cầu ...". Nó là
# TỜ NÀO, không phải LỖI GÌ -- để nguyên thì cùng một lỗi thiếu `sign.` tách
# thành ba dòng một tờ, và cột `Δ` khi so hai lô không nói được gì.
_FAMILY_IN = re.compile(r"\((?!dưới|cho phép|không )[a-z0-9_]+\)")


def _family(why: str) -> str:
    """Câu `why` bỏ hết con số và tên phôi -- tên của LOẠI nguyên nhân."""
    # Phần sau dấu `:` của "model không trả lời: <nguyên văn reply>" là nội
    # dung tờ ấy, không phải tên nguyên nhân. Cắt đi, nếu không mỗi tờ một
    # nhóm.
    head = why.split(": ", 1)[0] if why.startswith("model không trả lời") else why
    return _FAMILY_IN.sub("(F)", _NUM.sub("N", head)).strip()


def read(run: Path) -> dict:
    report = run / "compose_report.json"
    if not report.exists():
        raise SystemExit(f"{report} không có -- lô này chưa chạy xong?")
    return json.loads(report.read_text(encoding="utf-8"))


def tally(got: dict) -> tuple[collections.Counter, dict]:
    """`(đếm theo loại, một ví dụ nguyên văn mỗi loại)`."""
    count: collections.Counter = collections.Counter()
    sample: dict = {}
    for page in got.get("pages") or []:
        if page.get("ok"):
            continue
        # Một tờ có thể trượt vì nhiều lý do. Đếm CẢ, vì sửa một lý do
        # không cứu được tờ còn mắc lý do kia -- đếm "tờ" thay vì "lý do"
        # là cách tự hứa hẹn quá mức với chính mình.
        for why in page.get("why") or []:
            kind = _family(str(why))
            count[kind] += 1
            sample.setdefault(kind, (page.get("index"),
                                    page.get("archetype"), str(why)))
    return count, sample


def show(run: Path, got: dict, pages: bool) -> None:
    asked = int(got.get("asked") or 0)
    kept = int(got.get("kept") or 0)
    print(f"\n=== {run}  ({got.get('when', '?')}) ===")
    print(f"model {got.get('model', '?')} @ {got.get('url', '?')}, "
          f"song song {got.get('concurrency', '?')}")
    print(f"xin {asked} tờ · qua cổng {kept} "
          f"({kept / max(asked, 1):.0%}) · trượt {asked - kept}")
    count, sample = tally(got)
    if not count:
        print("không tờ nào trượt.")
        return
    print(f"\n{'tờ':>4}  nguyên nhân")
    for kind, n in count.most_common():
        print(f"{n:>4}  {kind[:92]}")
        idx, arch, why = sample[kind]
        print(f"      ví dụ: tờ {idx} ({arch}) -- {why[:100]}")
    if pages:
        print(f"\n{'tờ':>4} {'archetype':<30} lý do")
        for page in got.get("pages") or []:
            if page.get("ok"):
                continue
            first = (page.get("why") or ["?"])[0]
            print(f"{page.get('index'):>4} {str(page.get('archetype'))[:30]:<30} "
                  f"{str(first)[:80]}")


def compare(a: tuple[Path, dict], b: tuple[Path, dict]) -> None:
    """Hai lô, cùng một thước. Cột `Δ` là số tờ mỗi nguyên nhân tăng/giảm."""
    (path_a, got_a), (path_b, got_b) = a, b
    count_a, _ = tally(got_a)
    count_b, _ = tally(got_b)
    rate_a = int(got_a.get("kept") or 0) / max(int(got_a.get("asked") or 0), 1)
    rate_b = int(got_b.get("kept") or 0) / max(int(got_b.get("asked") or 0), 1)
    print(f"\n=== SO {path_a.name} -> {path_b.name} ===")
    print(f"qua cổng {rate_a:.0%} -> {rate_b:.0%}  "
          f"({rate_b - rate_a:+.0%} điểm)")
    print(f"\n{'trước':>6} {'sau':>5} {'Δ':>5}  nguyên nhân")
    for kind in sorted(set(count_a) | set(count_b),
                      key=lambda k: -(count_b[k] - count_a[k])):
        before, after = count_a[kind], count_b[kind]
        mark = "" if before == after else ("  <-- xấu đi" if after > before
                                          else "  <-- đỡ hơn")
        print(f"{before:>6} {after:>5} {after - before:>+5}  "
              f"{kind[:70]}{mark}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path,
                        help="một lô để xem, hoặc hai lô để so (trước sau)")
    parser.add_argument("--pages", action="store_true",
                        help="in thêm từng tờ trượt một")
    args = parser.parse_args()
    loaded = [(run, read(run)) for run in args.runs]
    for run, got in loaded:
        show(run, got, args.pages)
    if len(loaded) == 2:
        compare(loaded[0], loaded[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
