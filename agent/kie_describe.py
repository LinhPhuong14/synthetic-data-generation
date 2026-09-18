"""Ask a model for real KIE field descriptions, over a dataset already rendered.

    python -m agent.kie_describe --dataset data/5k_llm
    VLM_KIE_DESCRIPTIONS=data/5k_llm/kie_descriptions.json python tools/agent_dataset.py ...

`pipeline.kie.build_page` writes a fallback description into every page's
`kie.pairs` whether or not this ever runs -- the caption's own printed text,
which is never wrong and never absent, just not as good as a model could do
("TEN NGUOI DUOC UY QUYEN" vs "the person being authorized"). This script is
the "later" that fallback is waiting for: it reads a dataset's own record
files back, collects every field still marked `description_source:
"fallback"`, asks a model for a real English description PER LAYOUT (a
description is a property of what a caption means on that layout, not of one
page's particular draw), and writes the file `pipeline.kie.DESCRIPTIONS_ENV`
names. `agent/prompts/kie.md` is the guide the model answers under.

Nothing here is required for the pipeline to run: a dataset built with no
model configured, or before this script is ever run over it, carries the
exact same fallback description on every page -- see the module docstring on
`pipeline/kie.py` for why that split is the whole point.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import client as llm_client  # noqa: E402
from agent.client import LLMError  # noqa: E402
from pipeline import record as R  # noqa: E402
from pipeline import synthesis  # noqa: E402

PROMPT_PATH = Path(__file__).parent / "prompts" / "kie.md"
SYSTEM = PROMPT_PATH.read_text(encoding="utf-8")

# One model call describes at most this many fields -- a layout with a huge
# field count (the twelve-column medical statement) still fits comfortably
# under any schema's practical size, and a huge call is also a huge retry
# every time one field's answer needs reasking.
MAX_FIELDS_PER_CALL = 40


def collect_fields(dataset: Path) -> dict[str, dict[str, dict[str, str]]]:
    """`{layout: {field: {"key_text": ..., "value_text": ...}}}` -- one
    sample pair per field, over every record under `dataset` whose `kie`
    section still carries the fallback description. A field this dataset
    already had a real description for (`description_source: "llm"`, from a
    `VLM_KIE_DESCRIPTIONS` file the render used) is not asked about again.
    """
    synth = synthesis.read_if_there(synthesis.beside(dataset))
    out: dict[str, dict[str, dict[str, str]]] = {}
    for image in R.images(dataset):
        try:
            item = R.read_one(image)
        except (OSError, json.JSONDecodeError):
            continue
        pairs = (item.get("kie") or {}).get("pairs") or []
        if not pairs:
            continue
        layout = synth.layout(image.name)
        if not layout or layout == "?":
            continue
        bucket = out.setdefault(layout, {})
        for pair in pairs:
            # Anything a model did not write is a candidate: `caption`, `kind`
            # and `label` are all derivations, and a real description beats
            # every one of them. See `pipeline.kie.DESCRIPTION_SOURCES`.
            if pair.get("description_source") == "llm":
                continue
            field = pair.get("field")
            if field and field not in bucket:
                bucket[field] = {"key_text": str(pair.get("key_text", "")),
                                 "value_text": str(pair.get("value_text", ""))}
    return out


def _schema_for(fields: dict[str, dict[str, str]]) -> dict:
    names = sorted(fields)
    return {
        "type": "object",
        "properties": {"descriptions": {
            "type": "object",
            "properties": {name: {"type": "string"} for name in names},
            "required": names, "additionalProperties": False,
        }},
        "required": ["descriptions"], "additionalProperties": False,
    }


def _user_message(layout: str, fields: dict[str, dict[str, str]]) -> str:
    lines = [f"Bố cục: {layout}",
             "Danh sách trường -- field_id | nhãn in trên giấy | một giá trị mẫu:"]
    for field, info in fields.items():
        lines.append(f"- {field} | {info['key_text']!r} | {info['value_text']!r}")
    return "\n".join(lines)


def describe(dataset: Path, llm) -> dict[str, dict[str, str]]:
    """`{layout: {field: description}}` for every field `collect_fields`
    found, or `{}` if `llm` is None -- the caller decides what "no model"
    means for the output file, this function just does no work."""
    if llm is None:
        return {}
    out: dict[str, dict[str, str]] = {}
    for layout, fields in collect_fields(dataset).items():
        items = list(fields.items())
        layout_out: dict[str, str] = {}
        for start in range(0, len(items), MAX_FIELDS_PER_CALL):
            chunk = dict(items[start:start + MAX_FIELDS_PER_CALL])
            try:
                answer = llm.decide(SYSTEM, _user_message(layout, chunk), _schema_for(chunk))
            except LLMError:
                continue
            written = (answer or {}).get("descriptions")
            if not isinstance(written, dict):
                continue
            for field in chunk:
                value = written.get(field)
                if isinstance(value, str) and value.strip():
                    layout_out[field] = value.strip()
        if layout_out:
            out[layout] = layout_out
    return out


def write(descriptions: dict[str, dict[str, str]], out_path: Path) -> dict[str, dict[str, str]]:
    """Merge into whatever `out_path` already holds and write it back.

    Merged rather than overwritten: this script is meant to be run again as a
    dataset grows or a new layout ships, and a later run must not erase a
    description an earlier run over a DIFFERENT dataset already wrote for a
    layout this one never touches.
    """
    existing: dict[str, dict[str, str]] = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    for layout, fields in descriptions.items():
        existing.setdefault(layout, {}).update(fields)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    return existing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="a rendered dataset directory (html_NNN.jpg + .json beside it)")
    parser.add_argument("--out", type=Path, default=None,
                        help="default: <dataset>/kie_descriptions.json")
    args = parser.parse_args()
    out_path = args.out or (args.dataset / "kie_descriptions.json")

    llm = llm_client.from_env()
    if llm is not None and not llm.alive():
        print(f"[kie] {llm.url} không trả lời — dừng, không sinh mô tả")
        llm = None
    if llm is None:
        print("[kie] không có server LLM (VLM_LLM_URL) — không sinh gì; "
              "pipeline vẫn dùng mô tả fallback (nhãn in trên giấy)")
        return 0

    written = describe(args.dataset, llm)
    fields = sum(len(v) for v in written.values())
    if not fields:
        print("[kie] không có trường nào cần mô tả (mọi trường đã có mô tả, "
              "hoặc dataset không có kie.pairs)")
        return 0
    merged = write(written, out_path)
    print(f"[kie] {fields} mô tả mới, {len(written)} bố cục -> {out_path} "
          f"({sum(len(v) for v in merged.values())} mô tả tổng)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
