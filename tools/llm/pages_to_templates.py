#!/usr/bin/env python3
"""Trang model đã viết -> PHÔI `{{chỗ.trống}}`. Không gọi model lần nào.

    python -m tools.llm.pages_to_templates data/24-09-div-before -o data/phoi-boot
    python -m tools.llm.pages_to_templates data/pilot17 data/24-09-div-before -o data/phoi-boot

Hai việc, và cả hai đều thật:

1. **Mồi**. Một lô `agent/compose_template.py` tốn một lời gọi model cho mỗi
   phôi. Kho đã có sẵn hàng chục trang model viết, và bố cục của chúng là thứ
   đắt nhất trong đó -- lấy lại được thì bộ phôi đầu tiên gần như miễn phí.
2. **Phép đo**. So ba đường sinh cần bố cục do MODEL viết ở cả hai nhánh LLM,
   nếu không phần "đường phôi kém đa dạng hơn" đo phải là bố cục do người
   viết công cụ này nghĩ ra. Chuyển từ trang thật giữ đúng biến ấy.

## Cái gì thành chỗ trống, cái gì ở lại làm chữ in

Một `<span data-path="X">chữ</span>` thành `{{X}}` khi và chỉ khi `X` (sau khi
gom chỉ số) nằm trong sổ đóng 60 khoá. Mọi span khác GIỮ NGUYÊN CHỮ và bị gỡ
`data-path` -- nó trở thành chữ in sẵn của tờ mẫu.

Đấy không phải một lựa chọn cho tiện, nó là chính sách của pha 1 áp ngược lại:
`agent/compose_template.py` ép `path` bằng `enum` nên model không thể sinh chỗ
trống ngoài sổ. Một công cụ chuyển đổi cho phép nhiều hơn là một cửa sau vào
đúng cái mà cổng kia chặn.

Mất mát ĐO ĐƯỢC, và công cụ in ra: trên `data/24-09-div-before` (8 tệp)
81% lượt `data-path` vào sổ; trên `data/pilot13` chỉ 3%, vì lô ấy sinh trước
khi sổ tồn tại. Chuyển một lô cũ thì phần lớn giá trị đóng băng thành chữ in
-- phôi vẫn hợp lệ, nhưng mọi tờ ra từ nó mang cùng một cái tên công ty. Con
số `slots` mỗi phôi trong báo cáo là chỗ thấy điều đó.

## Bảng hàng: N dòng -> MỘT dòng mẫu

Những `<tr>` liền nhau mang cùng một bộ đường dẫn `line_items[]` là cùng một
dòng lặp lại. Giữ dòng ĐẦU, gắn `data-repeat`, xoá phần còn lại. Không gom thì
phôi cố định đúng số dòng của trang gốc, và mọi tờ ra từ nó cao bằng nhau --
đúng thứ làm dấu vân hình học của chúng trùng khít.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synthgen import field_tier as FT  # noqa: E402
from synthgen import template as T  # noqa: E402

# `<span ...>chữ</span>` KHÔNG lồng span. Trang đã qua `repair.unnest()` nên
# run có nhãn chỉ chứa chữ -- đó là điều kiện cổng của kho vẫn đòi, nên mẫu
# này đúng cho mọi trang đã qua cổng.
_SPAN = re.compile(r"<span\b([^>]*)>(.*?)</span>", re.DOTALL | re.IGNORECASE)
_ROW = re.compile(r"<tr\b[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE)


def _attr(tag: str, name: str) -> str:
    m = re.search(name + r"\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))", tag,
                  re.IGNORECASE)
    if not m:
        return ""
    return m.group(2) or m.group(3) or m.group(4) or ""


def _drop(attrs: str, name: str) -> str:
    return re.sub(r"\s*\b" + name + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "",
                  attrs, flags=re.IGNORECASE)


def _set_path(attrs: str, path: str) -> str:
    return _drop(attrs, "data-path") + f' data-path="{path}"'


def slot_spans(html: str, known: set) -> tuple[str, Counter, Counter]:
    """Đổi span có `data-path` trong sổ thành chỗ trống. `(html, nhận, bỏ)`."""
    took: Counter = Counter()
    left: Counter = Counter()

    def one(m: re.Match) -> str:
        attrs, text = m.group(1), m.group(2)
        raw = _attr(attrs, "data-path")
        if not raw:
            return m.group(0)
        path = FT.normalise(raw)
        if path not in known:
            left[path] += 1
            return f"<span{_drop(attrs, 'data-path')}>{text}</span>"
        took[path] += 1
        return f"<span{_set_path(attrs, path)}>{{{{{path}}}}}</span>"

    return _SPAN.sub(one, html), took, left


_TAG_OPEN = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b", re.IGNORECASE)


def _siblings(html: str, tag: str) -> list[tuple[int, int]]:
    """Mọi phần tử `<tag>` KHÔNG lồng trong một `<tag>` khác, theo thứ tự.

    Lọc bỏ cái lồng nhau là điều kiện để phép gom dưới đây có nghĩa: một khối
    chữ ký bọc trong một khối chữ ký khác thì gom cái ngoài là xoá cả hai."""
    out: list[tuple[int, int]] = []
    for m in re.finditer(rf"<{tag}\b", html, re.IGNORECASE):
        if out and m.start() < out[-1][1]:
            continue                         # lồng trong cái vừa nhận
        end = T._close_at(html, tag.lower(), m.start())
        if end is not None:
            out.append((m.start(), end))
    return out


def collapse_rows(html: str, group: str = "line_items",
                  tags=("tr", "div", "li", "td", "section", "p")) -> tuple[str, int]:
    """Phần tử liền nhau cùng bộ đường dẫn `group[]` -> MỘT `data-repeat`.

    "Cùng bộ" so TẬP đường dẫn, không so chữ: hai dòng của một bảng in hai
    giá trị khác nhau nhưng khai cùng những trường, và đó là định nghĩa của
    một dòng lặp. Một phần tử mang bộ khác (dòng TỔNG CỘNG chẳng hạn) không
    vào nhóm và ở lại nguyên vẹn -- đúng như trên giấy thật.

    Thử NHIỀU THẺ, không chỉ `<tr>`: đo trên 18 trang của `data/pilot17` +
    `data/24-09-div-before`, bảng hàng luôn là `<tr>` nhưng khối chữ ký là
    `<div>` (và một lần là `<td>` của một bảng bố cục hai cột). Chỉ gom `<tr>`
    thì 5 trên 18 phôi trượt cổng vì `{{signers[].title}}` không nằm trong
    khối lặp nào. Dừng ở thẻ ĐẦU TIÊN gom được: gom tiếp bằng một thẻ bao
    ngoài là gom cái đã gom."""
    for tag in tags:
        body, cut = _collapse_one(html, group, tag)
        if cut:
            return body, cut
    return html, 0


def _collapse_one(html: str, group: str, tag: str) -> tuple[str, int]:
    spots = _siblings(html, tag)
    if not spots:
        return html, 0

    def sig(text: str) -> tuple:
        return tuple(sorted({p for p in T.paths(text)
                             if p.startswith(f"{group}[].")}))

    out: list[str] = []
    cut, i, last = 0, 0, 0
    while i < len(spots):
        start, end = spots[i]
        mine = sig(html[start:end])
        if not mine:
            i += 1
            continue
        j = i + 1
        while j < len(spots) and sig(html[spots[j][0]:spots[j][1]]) == mine:
            j += 1
        if j - i >= 2:
            head = re.sub(rf"<{tag}\b", f'<{tag} {T.REPEAT_ATTR}="{group}"',
                          html[start:end], count=1, flags=re.IGNORECASE)
            out.append(html[last:start])
            out.append(head)
            last = spots[j - 1][1]
            cut += j - i - 1
        i = j
    out.append(html[last:])
    return "".join(out), cut


def convert(html: str, known: set, groups=("line_items", "signers", "clauses"),
            rounds: int = 3) -> tuple[str, dict]:
    """Một trang -> một phôi, cộng số đo về việc chuyển đổi đó.

    Chạy tới khi ỔN ĐỊNH, tối đa `rounds` lượt. Một chỗ trống `[]` còn nằm
    ngoài mọi khối lặp sau khi gom là một chỗ trống không ai bung -- `[]` đi
    thẳng ra giấy. Thay vì chữa nó, ĐÓNG BĂNG đường dẫn ấy (bỏ khỏi `known`)
    và dựng lại phôi từ trang GỐC: chữ thật của nó quay lại làm chữ in.

    Dựng lại từ trang gốc chứ không vá phôi dở dang, vì chữ thật chỉ còn ở
    trang gốc -- phôi đã thay nó bằng `{{…}}` rồi. Một vòng lặp ba lượt là
    đủ: mỗi lượt chỉ bỏ đi đường dẫn, không bao giờ thêm, nên nó hội tụ."""
    banned: set = set()
    body, took, left = "", Counter(), Counter()
    for _ in range(max(1, rounds)):
        body, took, left = slot_spans(html, known - banned)
        cut = 0
        for group in groups:
            body, n = collapse_rows(body, group)
            cut += n
        stray = {p for p in T.paths(body) if "[]" in p} - _inside_repeat(body)
        if not stray:
            break
        banned |= stray
    return body, {"slots": len(took), "slot_uses": sum(took.values()),
                  "frozen": sum(left.values()),
                  "frozen_keys": len(left),
                  "rows_collapsed": cut,
                  "froze_stray_repeats": sorted(banned),
                  "top_frozen": [k for k, _ in left.most_common(5)]}


def _inside_repeat(html: str) -> set:
    """Đường dẫn `[]` nằm TRONG một khối `data-repeat` -- tức có người bung."""
    out: set = set()
    for name, start, end in T.repeat_blocks(html):
        out |= {p for p in T.paths(html[start:end])
                if p.startswith(f"{name}[].")}
    return out


def run(sources: list, out: Path) -> int:
    known = set(FT.closed_enum(FT.PATH))
    (out / "templates").mkdir(parents=True, exist_ok=True)
    (out / "rejected").mkdir(parents=True, exist_ok=True)
    kept, dropped = 0, 0
    stats: list[dict] = []
    for source in sources:
        folder = Path(source) / "html"
        if not folder.is_dir():
            print(f"[phôi] {source}: không có thư mục html/, bỏ qua")
            continue
        for path in sorted(folder.glob("*.html")):
            raw = path.read_text(encoding="utf-8")
            body, measure = convert(raw, known)
            declared = _declared(Path(source), path.stem)
            # TÊN LƯỢT CHẠY ĐI KÈM TÊN TỆP. Hai lượt khác nhau đặt tên trang
            # theo cùng một công thức (`llm_<family>_<index>`), nên chuyển hai
            # lượt vào một thư mục thì trang thứ hai ghi đè trang thứ nhất --
            # đo được: 18 trang vào, 16 tệp ra, và không có gì kêu.
            stem = f"{Path(source).name}_{path.stem}"
            template = T.Template(
                template_id=stem,
                family=str(declared.get("archetype") or "llm"),
                html=body,
                doc_kind=str(declared.get("loai_tai_lieu") or ""),
                doc_title=str(declared.get("doc_title") or ""),
                kinds=_kinds(body),
                meta={"from": str(path), **measure})
            why = T.problems(body, known)
            folder_out = "templates" if not why else "rejected"
            kept += int(not why)
            dropped += int(bool(why))
            payload = template.as_dict()
            payload.update({"ok": not why, "why": why,
                            "paths": T.paths(body),
                            "repeats": template.repeat_names})
            (out / folder_out / f"{stem}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
            stats.append({"stem": stem, "ok": not why, **measure,
                          "why": why[:3]})
            mark = "✓" if not why else "✗"
            print(f"  {mark} {path.stem:34s} {measure['slots']:3d} chỗ trống "
                  f"({measure['slot_uses']:4d} lượt), {measure['frozen']:4d} "
                  f"lượt đóng băng thành chữ in, "
                  f"{measure['rows_collapsed']:3d} dòng gom"
                  + ("" if not why else f"  {why[0][:52]}"))
    total_slots = sum(s["slot_uses"] for s in stats)
    total_frozen = sum(s["frozen"] for s in stats)
    share = total_slots / max(1, total_slots + total_frozen)
    (out / "convert_report.json").write_text(
        json.dumps({"sources": [str(s) for s in sources],
                    "templates": kept, "rejected": dropped,
                    "slot_uses": total_slots, "frozen_uses": total_frozen,
                    "slot_share": round(share, 4), "pages": stats},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n[phôi] {kept} phôi, {dropped} trượt cổng  ·  {share:.0%} lượt "
          f"`data-path` thành chỗ trống, phần còn lại đóng băng thành chữ in")
    print(f"[phôi] {out / 'templates'}")
    return 0 if kept else 1


def _declared(source: Path, stem: str) -> dict:
    path = source / "declared" / f"{stem}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}


def _kinds(html: str) -> dict:
    """`{đường dẫn: data-kind}` đọc thẳng từ phôi vừa dựng."""
    out: dict = {}
    for m in _SPAN.finditer(html):
        path = _attr(m.group(1), "data-path")
        kind = _attr(m.group(1), "data-kind")
        if path and kind:
            out.setdefault(path, kind)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="+",
                        help="thư mục lượt chạy `agent.compose_page`")
    parser.add_argument("-o", "--out", type=Path, required=True)
    args = parser.parse_args()
    return run(args.sources, args.out.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
