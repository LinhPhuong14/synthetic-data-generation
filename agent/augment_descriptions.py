#!/usr/bin/env python3
"""Xin model viết thêm CÁCH NÓI cho các câu mô tả trường KIE đã có.

    python -m agent.augment_descriptions --want 6            # xem trước
    python -m agent.augment_descriptions --want 6 --write    # ghi ra file
    python -m agent.augment_descriptions --only qty,amount --want 12 --write

Cùng lối với `agent/augment_content.py`, và cùng lý do. Thiết kế hấp dẫn là gọi
model NGAY LÚC VẼ để mỗi trang một câu mới; cái giá của nó là lời hứa cả kho
này dựng lên -- cùng seed thì ra cùng byte. `agent/ollama.py` mở đầu bằng đúng
chuyện ấy, `tools/baseline.py` vân tay từng ảnh, `tests/test_worklist.py` vẽ một
trang hai lần rồi so sha256, và `tests/test_llm.py` giữ ranh giới bằng một
assertion: không gì dưới `agent/` được `generators/` hay `pipeline/` import.

Nên model chạy **ở đây**, một bước riêng, và thứ nó tạo ra là một file thường
trong git: `rulebase/kie_phrasings.json`. `synthgen/phrasing.py` đọc file ấy lúc
chạy và bốc theo `crc32(seed | trường | câu gốc)` -- vẫn dựng lại được, mà kho
chữ thì rộng ra bao nhiêu tuỳ số lần chạy bước này. Chạy lại là cách lấy THÊM
cách nói: file được GỘP, không bị ghi đè.

## Câu gốc lấy ở đâu

Không có danh sách nào viết cứng trong file này. Câu gốc đọc từ chính những chỗ
đang dùng chúng:

* `synthgen/phrasing.py::POOL` -- câu gốc của bộ synthgen;
* `synthgen/design.py::COLUMNS[*]["describe"]` -- mô tả từng cột bảng;
* `rulebase/kie_field_glossary.json` -- 272 slug + 19 `data-kind` của pipeline
  chính, tức là nửa còn lại của kho.

Thêm một loại chứng từ mới là thêm mô tả mới, và bước này tự thấy chúng.

## Gác cổng

Mọi ngưỡng ĐO từ những cách nói người đã viết trong `POOL`, không phải chọn.
Cùng luật với `agent/corpus_rules.py`:

> **Luật nào loại một câu người đã viết là luật sai, không phải câu sai.**

Đo riêng từng thứ tiếng, vì cùng một nghĩa thì tiếng Việt dài hơn tiếng Anh:
tiếng Anh 4-14 từ, tiếng Việt 4-16 từ. Rồi nới ra bằng `corpus_rules.SLACK` --
một con số cho cả kho, không phải hai.

Hỏi riêng từng thứ tiếng nữa, một lượt tiếng Anh một lượt tiếng Việt, nên "trả
lời sai thứ tiếng" kiểm được thật chứ không chỉ đếm lại: lượt tiếng Việt mà câu
không có dấu là loại, lượt tiếng Anh mà câu có dấu cũng loại.

## Giá

Một 7B 4-bit trên CPU viết cỡ năm token một giây, nên hai lượt cho một câu gốc
là khoảng một phút, và cả kho (~390 câu) là một buổi. `--only` chia việc ra
được. Tiến độ in theo từng câu gốc vì thế.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):                   # `python augment_descriptions.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.corpus_rules import SLACK
from agent.ollama import LLMError, Model, prompt
from synthgen.design import COLUMNS
from synthgen.phrasing import POOL

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "rulebase" / "kie_phrasings.json"
GLOSSARY = REPO_ROOT / "rulebase" / "kie_field_glossary.json"
PROMPT = "describe"

# Một lượt hỏi một thứ tiếng. `vi` / `en` là khoá nội bộ; chữ đi vào prompt nằm
# ở `ASK`, vì một prompt nói "viết bằng vi" thì được câu nói về chữ "vi".
ASK = {"en": "TIẾNG ANH", "vi": "TIẾNG VIỆT (có dấu)"}


def _plain(text: str) -> str:
    """Bỏ dấu, hạ chữ thường -- để so trùng không phụ thuộc dấu và hoa thường."""
    stripped = unicodedata.normalize("NFD", str(text).lower())
    return "".join(ch for ch in stripped if unicodedata.category(ch) != "Mn")


def vietnamese(text: str) -> bool:
    """Có dấu thì là tiếng Việt. Đủ dùng: một câu mô tả tiếng Việt không dấu
    cũng là một câu phải loại, nên nhầm về phía loại là nhầm đúng chiều."""
    return _plain(text) != str(text).lower()


@dataclass(frozen=True)
class Envelope:
    """Một câu mô tả dài bao nhiêu thì còn giống câu người viết.

    Đo theo TỪNG THỨ TIẾNG và đo trên `POOL` -- tức là trên những câu người
    viết, không trên những câu lượt trước sinh ra. Nếu tính cả câu đã sinh thì
    mỗi lượt nới khung một chút và lượt thứ mười được kiểm bằng sai số của lượt
    thứ chín: một cái gác cổng từ từ phê duyệt chính nó."""

    words: tuple[int, int]
    chars: tuple[int, int]
    ratio: tuple[float, float]      # dài gấp mấy lần câu gốc
    sampled: int

    def fits(self, line: str, canon: str) -> str:
        """Rỗng là qua; không rỗng là lý do loại."""
        words = len(line.split())
        low, high = (max(1, int(self.words[0] / SLACK)), int(self.words[1] * SLACK))
        if not low <= words <= high:
            return f"{words} từ, ngoài {low}-{high} đo được"
        low, high = (max(1, int(self.chars[0] / SLACK)), int(self.chars[1] * SLACK))
        if not low <= len(line) <= high:
            return f"{len(line)} ký tự, ngoài {low}-{high} đo được"
        ratio = words / max(len(canon.split()), 1)
        low, high = self.ratio[0] / SLACK, self.ratio[1] * SLACK
        if not low <= ratio <= high:
            return f"dài {ratio:.2f} lần câu gốc, ngoài {low:.2f}-{high:.2f}"
        return ""


def envelopes() -> dict[str, Envelope]:
    """Một khung cho mỗi thứ tiếng, đo trên `POOL`."""
    out: dict[str, Envelope] = {}
    for lang, pick in (("en", lambda t: not vietnamese(t)), ("vi", vietnamese)):
        words: list[int] = []
        chars: list[int] = []
        ratio: list[float] = []
        for canon, variants in POOL.items():
            base = max(len(canon.split()), 1)
            for variant in variants:
                if variant == canon or not pick(variant):
                    continue
                words.append(len(variant.split()))
                chars.append(len(variant))
                ratio.append(len(variant.split()) / base)
        out[lang] = Envelope((min(words), max(words)), (min(chars), max(chars)),
                             (min(ratio), max(ratio)), len(words))
    return out


def canonicals() -> dict[str, str]:
    """`{câu gốc: nó từ đâu ra}` -- gộp từ mọi chỗ đang dùng mô tả KIE."""
    out: dict[str, str] = {}
    for canon in POOL:
        out.setdefault(canon, "phrasing.POOL")
    for key, spec in COLUMNS.items():
        text = str(spec.get("describe") or "").strip()
        if text:
            out.setdefault(text, f"COLUMNS[{key}]")
    if GLOSSARY.is_file():
        raw = json.loads(GLOSSARY.read_text(encoding="utf-8"))
        for key, value in raw.items():
            if key == "_by_kind" and isinstance(value, dict):
                for kind, text in value.items():
                    out.setdefault(str(text).strip(), f"kind:{kind}")
            elif not key.startswith("_") and isinstance(value, str):
                out.setdefault(value.strip(), f"slug:{key}")
    return {k: v for k, v in out.items() if k}


def ask(model: Model, canon: str, lang: str, want: int, have: list[str],
        seed: int):
    """Một lượt, một thứ tiếng. Trả về `Reply` để người gọi đóng dấu."""
    seen = "\n".join(f"- {t}" for t in have[:10])
    user = (f"Câu mô tả đang dùng cho một trường:\n  {canon}\n\n"
            f"Đã có các cách nói sau, ĐỪNG lặp lại chúng:\n{seen}\n\n"
            f"Viết {want} cách nói KHÁC cho ĐÚNG trường ấy, bằng {ASK[lang]}. "
            "Mỗi dòng một câu.")
    return model.chat(prompt(PROMPT), user, seed=seed,
                      num_predict=max(200, want * 45))


def sift(text: str, canon: str, lang: str, have: list[str],
         box: Envelope) -> tuple[list[str], list[tuple[str, str]]]:
    """`(giữ, [(câu, lý do loại)])` cho một lượt trả lời."""
    seen = {_plain(t) for t in have}
    kept: list[str] = []
    thrown: list[tuple[str, str]] = []
    for raw in text.splitlines():
        # Cắt số thứ tự và gạch đầu dòng -- đó là ĐỊNH DẠNG, cùng loại với
        # `ollama.lines_of`. Dấu chấm cuối cũng vậy: một mô tả thiếu dấu chấm
        # là một mô tả đúng viết thiếu một ký tự, không phải một mô tả sai.
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw).strip().strip('"')
        line = " ".join(line.split())
        if not line or line.startswith("```"):
            continue
        line = line.rstrip(".") + "."
        # Model hay mở đầu bằng một câu dẫn; câu ấy nói về CHÍNH NÓ chứ không
        # nói về trường, và luôn mang một trong mấy chữ này.
        if re.search(r"(?i)(sau đây|dưới đây|here are|the following|như sau)", line):
            thrown.append((line, "câu dẫn, không phải mô tả"))
            continue
        if lang == "vi" and not vietnamese(line):
            thrown.append((line, "lượt tiếng Việt mà câu không có dấu"))
            continue
        if lang == "en" and vietnamese(line):
            thrown.append((line, "lượt tiếng Anh mà câu có dấu tiếng Việt"))
            continue
        why = box.fits(line, canon)
        if why:
            thrown.append((line, why))
            continue
        if _plain(line) in seen:
            thrown.append((line, "trùng câu đã có"))
            continue
        kept.append(line)
        seen.add(_plain(line))
    return kept, thrown


def load() -> dict:
    if OUT.is_file():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {}


def run(*, want: int, only: list[str], rounds: int, seed: int, write: bool,
        model_name: str, today: str, show: bool) -> int:
    stored = load()
    box = envelopes()
    every = canonicals()
    canons = [c for c in every
              if not only or any(k in c.lower() or k in every[c].lower()
                                 for k in only)]
    if not canons:
        print(f"không có câu gốc nào khớp {only!r}; có {len(every)} câu")
        return 1

    model = Model(model_name)
    if not model.available():
        print(f"model {model_name!r} chưa nạp trên {model.host}.\n"
              "  ollama serve &\n"
              f"  ollama pull {model_name}\n"
              "Hoặc trỏ VLM_LLM_HOST sang máy có GPU.")
        return 1

    for lang in ("en", "vi"):
        b = box[lang]
        print(f"[{lang}] đo trên {b.sampled} câu người viết: "
              f"{b.words[0]}-{b.words[1]} từ, {b.chars[0]}-{b.chars[1]} ký tự, "
              f"{b.ratio[0]:.2f}-{b.ratio[1]:.2f} lần câu gốc (nới x{SLACK})")
    print(f"[mô tả] {len(canons)} câu gốc / {len(every)} trong kho, "
          f"xin {want} cách nói mỗi thứ tiếng, model {model_name}\n")

    kept_total = 0
    thrown_total: dict[str, int] = {}
    stamps: list[dict] = []
    for index, canon in enumerate(canons):
        have = list(POOL.get(canon, ())) + list(stored.get(canon, []))
        fresh: list[str] = []
        for lang in ("en", "vi"):
            got: list[str] = []
            for attempt in range(rounds):
                try:
                    reply = ask(model, canon, lang, want - len(got) + 3,
                                have + fresh, seed + index * 37 + attempt)
                except LLMError as error:
                    print(f"  {canon[:40]}… [{lang}] {error}")
                    break
                kept, thrown = sift(reply.text, canon, lang, have + fresh + got,
                                    box[lang])
                got += kept
                for line, why in thrown:
                    thrown_total[why] = thrown_total.get(why, 0) + 1
                    if show:
                        print(f"      ✗ {line[:58]:<58}  {why}")
                if show:
                    for line in kept:
                        print(f"      ✓ {line}")
                if not stamps or stamps[-1]["digest"] != reply.digest:
                    stamps.append({"model": reply.model, "digest": reply.digest,
                                   "date": today})
                if len(got) >= want:
                    break
            fresh += got[:want]
        kept_total += len(fresh)
        vi = sum(1 for t in fresh if vietnamese(t))
        print(f"  {index + 1:3d}/{len(canons)}  +{len(fresh):2d} "
              f"({vi} việt / {len(fresh) - vi} anh)  {canon[:56]}")
        if fresh:
            stored.setdefault(canon, []).extend(fresh)

    print(f"\n[mô tả] giữ {kept_total} câu, loại {sum(thrown_total.values())}:")
    for why, n in sorted(thrown_total.items(), key=lambda kv: -kv[1]):
        print(f"    {n:5d}  {why}")
    if not kept_total:
        print("không câu nào qua cổng; file không đổi dù có --write hay không")
        return 1
    if not write:
        print("[mô tả] xem trước; thêm --write để ghi")
        return 0

    # JSON không nhận được dấu rào bằng comment như `provenance.py` dùng cho
    # corpus, nên dấu vết đi vào một khoá `_provenance`. Nó ĐỦ vì file này
    # toàn bộ là chữ model viết: những cách nói người viết nằm trong
    # `synthgen/phrasing.py`, không nằm đây.
    history = list(stored.get("_provenance") or [])
    stored["_provenance"] = history + [{
        "runs": stamps,
        "prompt": f"{PROMPT}:"
                  + hashlib.sha256(prompt(PROMPT).encode("utf-8")).hexdigest()[:4],
        "seed": seed,
        "kept": kept_total,
        "gate": "agent/augment_descriptions.py",
    }]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stored, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    fields = sum(1 for k in stored if not k.startswith("_"))
    lines = sum(len(v) for k, v in stored.items() if not k.startswith("_"))
    print(f"[mô tả] {fields} câu gốc, {lines} cách nói -> {OUT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--want", type=int, default=6,
                        help="số cách nói xin thêm, MỖI THỨ TIẾNG, cho mỗi câu gốc")
    parser.add_argument("--only", default="",
                        help="chỉ làm câu gốc (hoặc nguồn) chứa các chữ này, "
                             "cách nhau bởi dấu phẩy")
    parser.add_argument("--rounds", type=int, default=2,
                        help="hỏi lại tối đa mấy lần khi chưa đủ")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--model", default=None, help="tag ollama")
    parser.add_argument("--write", action="store_true",
                        help="ghi rulebase/kie_phrasings.json; không có thì chỉ in")
    parser.add_argument("--show", action="store_true",
                        help="in từng câu giữ và từng câu loại")
    parser.add_argument("--date", default=None, help="ngày để đóng dấu")
    args = parser.parse_args()

    from agent.ollama import MODEL

    return run(want=args.want,
               only=[k.strip().lower() for k in args.only.split(",") if k.strip()],
               rounds=args.rounds, seed=args.seed, write=args.write,
               model_name=args.model or MODEL,
               today=args.date or _datetime.date.today().isoformat(),
               show=args.show)


if __name__ == "__main__":
    raise SystemExit(main())
