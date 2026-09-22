#!/usr/bin/env python3
"""Sinh thêm CÁCH NÓI cho mô tả trường KIE, bằng LLM, một lần rồi dùng mãi.

    VLM_LLM_URL=http://10.148.20.19:8008/v1 \
    VLM_LLM_MODEL=Qwen/Qwen3.8-27B-FP8 \
    python tools/llm/phrasings.py --limit 5        # thử năm câu trước
    python tools/llm/phrasings.py                  # chạy hết

Vì sao có file này, bằng số. `synthgen/descriptions.py` dựng một bảng MẦM:
2 136 trường, nhưng chỉ 237 câu gốc khác nhau -- nhiều trường dùng chung một
câu. `synthgen/phrasing.py::describe` đã đổi giọng câu ấy theo seed, nên mô
tả ghi vào bản ghi KHÔNG lặp y hệt... với những câu có biến thể. Đo trên một
bộ 158 trang: 564/2 505 trường có hơn một cách viết -- 23%. Phần còn lại chỉ
có đúng một câu, vì kho biến thể (`rulebase/kie_phrasings.json` cộng bảng
viết tay trong `phrasing.POOL`) mới phủ 75/237 câu gốc.

Nên việc ở đây KHÔNG phải sinh mô tả cho từng file: nó là bù 162 câu còn
thiếu. Một lượt chạy, một trăm sáu mươi hai lượt gọi, rồi kho nằm trong
`rulebase/` như mọi dữ liệu khác -- lúc sinh dữ liệu không gọi LLM lần nào.

Ghi THÊM chứ không ghi đè: file đã có gì thì giữ, câu nào đủ biến thể thì bỏ
qua. Chạy lại an toàn, và chạy lại sau khi thêm phôi mới là cách bù phần mới.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import client as llm_client  # noqa: E402
from synthgen import descriptions, phrasing  # noqa: E402

TARGET = REPO_ROOT / "rulebase" / "kie_phrasings.json"

# Bao nhiêu cách nói là đủ cho một câu. Sáu: bảng viết tay trong `phrasing.py`
# dừng ở bốn tới mười, và sáu là chỗ một câu đã đủ để không trang nào đọc lên
# giống trang nào mà vẫn kiểm được bằng mắt.
WANT = 6

SYSTEM = (
    "You rewrite one-sentence field descriptions for a Vietnamese document "
    "dataset. Each rewrite must mean exactly the same thing as the original "
    "and stay one sentence."
)

USER = """Original description of a field on a Vietnamese business/administrative document:

    {text}

Write {n} alternative descriptions of the SAME field. Rules:
- {n_en} in English, {n_vi} in Vietnamese (with proper diacritics).
- Same meaning as the original. Do not add facts the original does not state.
- Vary the wording AND the sentence shape; do not just swap one synonym.
- One sentence each, no numbering, no quotes.
- Do not repeat the original sentence."""

SCHEMA = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 8, "maxLength": 240},
        }
    },
    "required": ["variants"],
    "additionalProperties": False,
}


def from_records(root: Path) -> collections.Counter:
    """Câu mô tả THẬT đã ghi ra đĩa, đếm theo số lần xuất hiện.

    Bảng mầm `descriptions.table()` KHÔNG phải nguồn mô tả duy nhất: đo trên
    một bộ đã sinh, `doc_title`, `org_name`, `org_branch` không có trong bảng
    ấy -- mô tả của chúng tới từ `rulebase/kie_glossary.py` hoặc từ chính chữ
    in trên giấy (`pipeline/kie.py::describe` tra bốn nguồn). Bù theo bảng
    mầm thôi thì ba trường có mặt trên gần như mọi tờ vẫn đúng một câu.

    Nên nguồn đáng tin là ĐẦU RA, không phải một trong các đầu vào. Đọc
    `records/*/*.json` của một bộ đã sinh và đếm mô tả thật."""
    used: collections.Counter = collections.Counter()
    for path in sorted(root.glob("records/*/*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for pair in (data.get("kie") or {}).get("pairs") or []:
            text = str(pair.get("description") or "").strip()
            if text:
                used[text] += 1
    return used


def missing(want: int, root: Path | None = None) -> list[tuple[str, int]]:
    """`(câu gốc, số lần dùng)` cho câu chưa đủ `want` cách nói.

    Xếp theo SỐ LẦN DÙNG, nhiều trước: một câu mười trường dùng chung thì bù
    nó trước trả lại nhiều đa dạng hơn một câu chỉ một trường dùng, và
    `--limit` khi ấy cắt vào đúng phần ít giá trị nhất."""
    # `tables()`, không phải `table()`: từ khi bảng mầm dựng THEO PHÔI, hàm
    # sau chỉ còn trả nền dùng chung (khối tổng, tiêu đề điều, ô tích) và bỏ
    # sót mọi trường của `field_pool` — tức là đúng phần đông câu gốc. Đếm gộp
    # cả 99 bảng, và một câu dùng ở nhiều phôi cộng dồn, nên thứ tự "nhiều lần
    # dùng trước" của `most_common` vẫn nói đúng câu nào bù trước thì lợi nhất.
    used: collections.Counter = collections.Counter()
    for one in descriptions.tables().values():
        for entry in one.values():
            used[entry if isinstance(entry, str) else entry["description"]] += 1
    if root is not None:
        used.update(from_records(root))
    have = phrasing.pool()
    canon_of = phrasing.canonical_of()
    out = []
    for text, n in used.most_common():
        # Câu đã là BIẾN THỂ của một câu khác thì bỏ: thêm nó làm câu gốc thứ
        # hai là chẻ một kho thành hai kho nhỏ hơn cho cùng một nghĩa.
        if text in canon_of and canon_of[text] != text:
            continue
        if len(have.get(text, ())) < want:
            out.append((text, n))
    return out


def load_added() -> dict:
    try:
        raw = json.loads(TARGET.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0,
                    help="chỉ làm N câu đầu (thử trước khi chạy hết)")
    ap.add_argument("--want", type=int, default=WANT,
                    help=f"số cách nói mỗi câu cần có, kể cả đã có (mặc định {WANT})")
    ap.add_argument("--dry-run", action="store_true",
                    help="chỉ liệt kê câu còn thiếu, không gọi LLM")
    ap.add_argument("--from-records", type=Path, default=None, metavar="DIR",
                    help="thu hoạch thêm câu mô tả THẬT từ `DIR/records/`. "
                         "Bảng mầm không phải nguồn duy nhất -- `doc_title`, "
                         "`org_name` tới từ `kie_glossary`, và chỉ đọc bảng "
                         "mầm thì chúng không bao giờ được bù")
    args = ap.parse_args()

    todo = missing(args.want, args.from_records)
    print(f"[phrasings] {len(todo)} câu gốc chưa đủ {args.want} cách nói")
    if args.dry_run:
        for text, n in todo[:40]:
            print(f"   x{n:4d}  {text[:88]}")
        return 0
    if args.limit:
        todo = todo[:args.limit]

    llm = llm_client.from_env()
    if llm is None:
        print("[phrasings] chưa khai VLM_LLM_URL — xem docstring của file này",
              file=sys.stderr)
        return 2

    added = load_added()
    have = phrasing.pool()
    wrote = failed = 0
    started = time.time()
    for index, (text, uses) in enumerate(todo, start=1):
        need = max(args.want - len(have.get(text, ())), 1)
        n_en = -(-need // 2)
        user = USER.format(text=text, n=need, n_en=n_en, n_vi=need - n_en)
        try:
            answer = llm.decide(SYSTEM, user, SCHEMA)
        except Exception as error:                        # noqa: BLE001
            failed += 1
            print(f"  [{index}/{len(todo)}] LỖI {type(error).__name__}: {error}",
                  file=sys.stderr)
            continue
        fresh = []
        seen = set(have.get(text, ())) | {text}
        for variant in answer.get("variants") or []:
            line = " ".join(str(variant).split()).strip()
            if line and line not in seen:
                fresh.append(line)
                seen.add(line)
        if not fresh:
            failed += 1
            continue
        added.setdefault(text, [])
        added[text].extend(v for v in fresh if v not in added[text])
        wrote += len(fresh)
        # Ghi sau MỖI câu, không đợi hết vòng: một lượt chạy trăm sáu mươi
        # lượt gọi bị ngắt giữa chừng mà mất sạch là lý do người ta ngại chạy
        # lại. Ghi từng câu thì lần sau `missing()` bỏ qua phần đã xong.
        TARGET.write_text(json.dumps(added, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"  [{index}/{len(todo)}] +{len(fresh)} cách nói (x{uses} trường)"
              f"  {text[:58]}")
    seconds = time.time() - started
    print(f"[phrasings] thêm {wrote} cách nói, {failed} câu hỏng, "
          f"{seconds:.0f}s -> {TARGET}")
    return 1 if failed and not wrote else 0


if __name__ == "__main__":
    raise SystemExit(main())
