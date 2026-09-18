#!/usr/bin/env python3
"""Xin model soạn một LOẠI CHỨNG TỪ mới cho `synthgen/`.

    python -m agent.compose_archetype --want 3              # xem trước
    python -m agent.compose_archetype --want 3 --write      # ghi ra file
    python -m agent.compose_archetype --about "giấy ra viện" --write

Đây là mảnh cuối nối LLM vào `synthgen/`. Trước nó, model viết được bố cục cho
pipeline chính (`agent/compose_layout.py` -> `rulebase/layouts/*.yaml`) mà
không với tới `synthgen/` được, vì ngữ pháp của bộ ấy nằm trong Python:
`design.py::ARCHETYPES` là 34 phôi viết thẳng vào mã nguồn, và một model thì
không sửa mã nguồn.

`synthgen/archetypes.py` mở đường: phôi khai được bằng YAML. File này là thứ
viết ra YAML ấy.

## Vẫn là bước RIÊNG, không phải lúc vẽ

Cùng lý do `agent/ollama.py` mở đầu và `tests/test_llm.py` giữ bằng một
assertion: model chạy ở đây, thứ nó tạo ra là một file thường trong git, người
đọc diff trước khi nó vẽ gì. Đường vẽ vẫn chỉ đọc file, và vẫn cùng seed ra
cùng byte.

Khác `augment_content.py` một điểm, và khác có chủ đích: **`--write` ghi vào
`rulebase/synthgen/` là ghi vào ngữ pháp của bộ sinh.** Một phôi hỏng không chỉ
làm xấu một dòng corpus, nó làm hỏng mọi tờ giấy rút ra từ nó. Nên cổng ở đây
chặt hơn, và vẫn không thay được việc người đọc diff.

## Cổng

`synthgen/archetypes.py::problems` -- cùng cái cổng `design.py` dùng lúc nạp,
gọi ở đây để model biết nó sai gì TRƯỚC khi file được ghi. Không có cổng thứ
hai viết riêng cho bước này: hai cái cổng cho cùng một thứ là hai cái cổng sẽ
lệch nhau.

Thêm ba phép đo mà `problems` không lo, vì chúng nói về BỘ SƯU TẬP chứ không về
một phôi:

* phôi mới phải khác mọi phôi đang có ở nhiều hơn cái tên -- đo bằng số khối
  và bộ cột trùng nhau;
* `titles` phải đủ nhiều để nghìn tờ không ra cùng một tên;
* id phải là slug ASCII, vì nó thành tên thư mục.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import re
import sys
import unicodedata
from pathlib import Path

import yaml

if __package__ in (None, ""):                  # `python compose_archetype.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ollama import LLMError, Model, prompt
from synthgen import archetypes as A
from synthgen import design as D

PROMPT = "archetype"

# Ít hơn ngần này cách đặt tên thì nghìn tờ giấy ra gần như cùng một tiêu đề.
# Đo trên 34 phôi viết tay: ít nhất 2, trung vị 3.
MIN_TITLES = 2

# Hai phôi coi là quá giống nhau khi chúng dùng chung ngần này phần khối VÀ
# chung ít nhất một bộ cột. Không phải một ngưỡng chọn bừa: hai phôi cùng bộ
# khối là chuyện thường (`letterhead`+`doctitle`+`table`+`signatures` có ở gần
# hết), nên chỉ riêng nó không đủ để gọi là trùng.
SAME_BLOCKS = 1.0


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFD", str(text).lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")


def context() -> str:
    """Schema, hai phôi thật, và danh sách id đang có -- gửi kèm mỗi lần hỏi."""
    rules = A.schema()
    lines = ["## Schema: 17 trường, và giá trị hợp lệ của từng trường", ""]
    for key, rule in rules.items():
        bit = f"* `{key}` — {rule['type']}"
        if rule.get("values"):
            bit += f"; chỉ nhận: {', '.join(rule['values'])}"
        if rule.get("min"):
            bit += f"; ít nhất {rule['min']} mục"
        lines.append(bit)

    # Hai phôi THẬT, không phải ví dụ bịa: một có bảng và tiền, một không.
    # Model nhỏ bắt chước định dạng tốt hơn nhiều so với đọc mô tả định dạng.
    show = [a for a in D.ARCHETYPES if a.id in ("bang_ke_chi_tiet", "giay_uy_quyen")]
    lines += ["", "## Hai phôi thật, đang chạy", ""]
    for arch in show or D.ARCHETYPES[:2]:
        lines.append(yaml.safe_dump(A.as_spec(arch), allow_unicode=True,
                                    sort_keys=False).rstrip())
        lines.append("")
    lines += ["## Đã có những phôi này, ĐỪNG soạn lại chúng", "",
              ", ".join(sorted(a.id for a in D.ARCHETYPES))]
    return "\n".join(lines)


def ask(model: Model, about: str, seed: int):
    """Một lượt. Trả về `Reply` để người gọi đóng dấu."""
    want = (f"Soạn một phôi cho loại chứng từ: **{about}**."
            if about else
            "Soạn MỘT phôi cho một loại chứng từ Việt Nam thông dụng mà danh "
            "sách dưới đây CHƯA có.")
    user = f"{want}\n\n{context()}\n"
    return model.chat(prompt(PROMPT), user, seed=seed, num_predict=1200)


def parse(text: str) -> tuple[dict | None, str]:
    """`(phôi, lý do hỏng)`. Cắt rào ``` nếu model vẫn thêm dù đã dặn."""
    body = str(text or "").strip()
    fence = re.search(r"```(?:ya?ml)?\s*(.+?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    try:
        spec = yaml.safe_load(body)
    except yaml.YAMLError as error:
        return None, f"không đọc được YAML: {str(error)[:120]}"
    if not isinstance(spec, dict):
        return None, "trả về không phải một ánh xạ khoá-giá trị"
    return spec, ""


def collection_problems(spec: dict, have: list) -> list[str]:
    """Cái mà `archetypes.problems` không lo: phôi này so với BỘ đang có."""
    found: list[str] = []
    name = str(spec.get("id", "?"))
    if name != _slug(name) or not name:
        found.append(f"{name}: id phải là slug ascii (a-z, 0-9, gạch dưới)")
    if len(spec.get("titles") or []) < MIN_TITLES:
        found.append(f"{name}: cần ít nhất {MIN_TITLES} cách đặt tiêu đề, "
                     "không thì nghìn tờ ra cùng một tên")

    blocks = set(spec.get("always") or []) | set(spec.get("optional") or [])
    columns = {tuple(c) for c in (spec.get("columns") or ())}
    for arch in have:
        theirs = set(arch.always) | set(arch.optional)
        if not blocks or not theirs:
            continue
        shared = len(blocks & theirs) / max(len(blocks | theirs), 1)
        if shared >= SAME_BLOCKS and columns & {tuple(c) for c in arch.column_pool}:
            found.append(f"{name}: trùng `{arch.id}` -- cùng bộ khối và chung "
                         "một bộ cột; phôi mới phải khác về CẤU TRÚC")
    return found


def run(*, want: int, about: str, rounds: int, seed: int, write: bool,
        model_name: str, today: str) -> int:
    model = Model(model_name)
    if not model.available():
        print(f"model {model_name!r} chưa nạp trên {model.host}.\n"
              f"  ollama serve &\n  ollama pull {model_name}\n"
              "Hoặc trỏ VLM_LLM_HOST sang máy có GPU.")
        return 1

    print(f"[phôi] {len(D.ARCHETYPES)} phôi đang có, xin thêm {want}, "
          f"model {model_name}\n")
    kept: list[dict] = []
    have = list(D.ARCHETYPES)
    taken = {a.id for a in have}
    for index in range(want):
        for attempt in range(rounds):
            try:
                reply = ask(model, about, seed + index * 17 + attempt)
            except LLMError as error:
                print(f"  {error}")
                return 1
            spec, why = parse(reply.text)
            if spec is None:
                print(f"  {index + 1}.{attempt + 1} ✗ {why}")
                continue
            found = (A.problems(spec, taken=taken)
                     + collection_problems(spec, have))
            if found:
                print(f"  {index + 1}.{attempt + 1} ✗ {spec.get('id', '?')} "
                      f"({reply.seconds:.0f}s)")
                for line in found[:6]:
                    print(f"        {line}")
                continue
            kept.append(spec)
            taken.add(str(spec["id"]))
            have.append(A.build(spec))
            print(f"  {index + 1}.{attempt + 1} ✓ {spec['id']} — "
                  f"{len(spec.get('always') or [])} khối luôn có, "
                  f"{len(spec.get('columns') or [])} bộ cột, "
                  f"{len(spec.get('titles') or [])} tiêu đề ({reply.seconds:.0f}s)")
            break

    if not kept:
        print("\n[phôi] không phôi nào qua cổng; không ghi gì")
        return 1
    print(f"\n[phôi] {len(kept)} phôi qua cổng")
    if not write:
        for spec in kept:
            print("\n" + yaml.safe_dump(spec, allow_unicode=True,
                                        sort_keys=False).rstrip())
        print("\n[phôi] xem trước; thêm --write để ghi")
        return 0

    A.ARCHETYPE_DIR.mkdir(parents=True, exist_ok=True)
    for spec in kept:
        path = A.ARCHETYPE_DIR / f"{spec['id']}.yaml"
        stamp = (f"# {A.MARK[2:]} {model.name}@{model.digest()} "
                 f"prompt={PROMPT} seed={seed} {today}")
        path.write_text(
            f"{A.MARK}\n{stamp}\n"
            + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        print(f"[phôi] -> {path.relative_to(A.REPO_ROOT)}")
    print("[phôi] đọc diff trước khi chạy: một phôi hỏng làm hỏng MỌI tờ giấy "
          "rút ra từ nó.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--want", type=int, default=3, help="số phôi muốn thêm")
    parser.add_argument("--about", default="",
                        help="gợi ý loại chứng từ, vd 'giấy ra viện'")
    parser.add_argument("--rounds", type=int, default=3,
                        help="hỏi lại tối đa mấy lần cho mỗi phôi")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--model", default=None, help="tag ollama")
    parser.add_argument("--write", action="store_true",
                        help="ghi vào rulebase/synthgen/; không có thì chỉ in")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    from agent.ollama import MODEL

    return run(want=args.want, about=args.about, rounds=args.rounds,
               seed=args.seed, write=args.write,
               model_name=args.model or MODEL,
               today=args.date or _datetime.date.today().isoformat())


if __name__ == "__main__":
    raise SystemExit(main())
