"""The KIE (key information extraction) half of a page's record.

    item["kie"] = kie.build_page(blocks, layout=recipe.layout.id)

OCR only needs `blocks`/`word_annotations` -- a box and what class it belongs
to. KIE needs one more thing neither carries: which KEY box a VALUE box
belongs to, and what that field actually MEANS -- the schema a downstream
extractor is asked to fill in, shaped like the one this module's docstring
below matches:

    {"type": "object", "properties": {
        "nguoi_uy_quyen": {"type": "string", "description": "..."}}}

Pairing without a per-field `kind`
-----------------------------------

`pipeline.record._word_field_role` already knows a run whose `kind` ends
`.label`/`.title` is a caption. For a field with its own semantic `kind`
(`store.account.label` next to `store.account`) that caption alone would
already say which value it captions. Most fields do not get that: `sheets/
modern.py`, `statement.py`, `statutory.py`, `medical.py` and `form.py` all
print a whole LIST of unrelated fields ("Số HĐ:", "Ngày:", "Người mua:")
through one shared generic kind, `invoice.field.label` / `invoice.field` --
so five different captions on one page can carry the exact same `kind`, and
`kind` alone cannot say which value belongs to which caption.

What DOES say it, on every one of those call sites without exception: the
label span and its value span are written into the SAME small piece of
markup, back to back --

    f'<div>{span(f"{kind}.label", label)} {span(kind, value)}</div>'

-- so `blocks_from_boxes`' draw order (`pipeline.record.build`'s own
guarantee: "one block per drawn field, in the order the renderer drew them")
already puts a caption immediately before the value it captions. `pair_fields`
below is exactly that adjacency, nothing more: a block ending `.label`/
`.title`, followed by a block that is not itself another caption. General
across every layout this repository ships, because it reads a convention
every `sheets/*.py` file already follows -- not a table keyed by document id.

The field's NAME, in the schema and in each pair, is not `kind` either (too
often generic) -- it is the caption's own printed text, slugified
(`rulebase.text.ascii_fold`, already this repository's one diacritics-folding
function). "Người mua:" becomes `nguoi_mua`. A caption repeated on one page
("KM:" on three discount lines) gets `_2`, `_3` appended in the order it
occurs, so every field in one page's schema has a distinct name.

Fallback, and where the real description comes from later
-------------------------------------------------------------

The description every page gets FOR FREE, with no model involved, is the
caption's own printed text -- "Người mua" is a worse description than an
English "Full legal name of the buyer" would be, but it is never wrong and
never absent, which is what `not hardcode` plus `must have a fallback` means
together: nothing here is a lookup table of per-document strings, and no page
is missing a description because a model was never run over its document
type. `VLM_KIE_DESCRIPTIONS` -- same mechanism as `rulebase.content.
CONTENT_OVERRIDES_ENV`, one env var naming a JSON file, read once and cached
-- lets a better, model-written description replace the fallback, keyed by
`layout` (a description of what a caption MEANS is a property of the layout
that prints it, not of one seed's draw) and then by the same slug. See
`agent/prompts/kie.md` for the guide a model is given when writing that file,
and `agent/kie_describe.py` for the script that calls it.
"""

from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path
from typing import Any

from rulebase.text import ascii_fold

# Same pattern as `rulebase.content.CONTENT_OVERRIDES_ENV`: unset means every
# description is the fallback (the caption's own printed text), exactly as if
# this file never existed.
DESCRIPTIONS_ENV = "VLM_KIE_DESCRIPTIONS"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """A field name a JSON Schema `properties` key can be: ASCII, `_`-joined,
    never empty. "Người mua:" -> `nguoi_mua`. One-way, like `ascii_fold`
    itself -- nothing reads a slug back into the text it came from."""
    folded = _SLUG_RE.sub("_", ascii_fold(text).lower()).strip("_")
    return folded or "field"


@functools.lru_cache(maxsize=1)
def _all_descriptions() -> dict[str, dict[str, str]]:
    path = os.environ.get(DESCRIPTIONS_ENV, "").strip()
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A run must not fail because a ledger written moments ago is
        # unreadable -- every field falls back to its caption text, exactly
        # as when no descriptions file was ever given.
        return {}


def _written_entry(field: str, layout: str) -> Any:
    """The raw `VLM_KIE_DESCRIPTIONS` entry for one field, str or dict.

    Two shapes, because one caption on one document type can be claimed by
    two roles -- "Địa chỉ" belongs to both the seller and the buyer on an
    invoice. `synthgen/descriptions.py::tables` writes a plain string when
    the claim is unambiguous (measured: 1717 of 1730 layout/field pairs,
    99.2%) and `{description, guidelines}` for the thirteen that are not.

    A dict entry used to fall straight through the `isinstance(..., str)`
    guard below and land on the caption fallback, silently -- the value was
    there and unread. Unknown keys are refused instead: a ledger shape
    nobody reads is the failure this repository has been bitten by before.
    """
    if not layout:
        return None
    entry = _all_descriptions().get(layout, {}).get(field)
    if entry is None or isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        extra = set(entry) - {"description", "guidelines"}
        if extra:
            raise ValueError(
                f"VLM_KIE_DESCRIPTIONS[{layout!r}][{field!r}] carries unknown "
                f"keys {sorted(extra)}; expected 'description'/'guidelines'")
        return entry
    raise TypeError(
        f"VLM_KIE_DESCRIPTIONS[{layout!r}][{field!r}] is {type(entry).__name__}, "
        f"expected a string or a {{description, guidelines}} object")


def guidelines_for(field: str, layout: str = "") -> str:
    """Annotation guidance for one field, or `""` when it needs none.

    Kept apart from the description on purpose, after SLIMER (arXiv
    2407.01272): one sentence says what the field IS, a second says how to
    tell it from the field next to it. The paper measures the split as worth
    up to +35 F1 on polysemous labels, and polysemous is exactly what the
    thirteen contested captions here are.
    """
    entry = _written_entry(field, layout)
    if isinstance(entry, dict):
        return str(entry.get("guidelines") or "").strip()
    return ""


def _is_caption(kind: str) -> bool:
    return kind.endswith(".label") or kind.endswith(".title")


def pair_fields(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`(field, key_text, value_text, key_bbox, value_bbox)` for every
    caption in `blocks` that is immediately followed by the value it
    captions -- see the module docstring for why adjacency in draw order is
    the general signal, not `kind`.
    """
    pairs: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    index = 0
    total = len(blocks)
    while index < total:
        block = blocks[index]
        kind = str(block.get("kind", ""))
        key_text = str(block.get("text", "")).strip()
        value = blocks[index + 1] if index + 1 < total else None
        value_kind = str(value.get("kind", "")) if value else ""
        value_text = str(value.get("text", "")).strip() if value else ""
        # A multi-page record (`pipeline.record.build`'s `sheets=` argument)
        # concatenates every side's blocks into one flat list, so the last
        # caption on page 1 sits immediately before the first block of page
        # 2 with nothing between them -- adjacency alone would pair them
        # across a page break that has no visible relationship at all. Absent
        # on either side (a record built before pages existed), both read as
        # the same page and nothing here changes.
        same_page = (value is None
                    or block.get("page_number", 1) == value.get("page_number", 1))
        if (_is_caption(kind) and key_text and value_text
                and not _is_caption(value_kind) and same_page):
            base = slug(key_text)
            counts[base] = counts.get(base, 0) + 1
            field = base if counts[base] == 1 else f"{base}_{counts[base]}"
            pairs.append({
                "field": field,
                "key_text": key_text,
                "value_text": value_text,
                "key_bbox": block.get("bbox"),
                "value_bbox": value.get("bbox"),
                # The pixel twins, carried beside the per-mille pair. Since
                # `pipeline/record.py::to_per_mille` every `bbox` on a record
                # is 0..1000; the measured pixels live in `bbox_px`. Anything
                # drawing on the image itself -- `synthgen/overlay.py` -- needs
                # the pixels, and without these it falls back to the per-mille
                # numbers and paints them as pixels: measured on
                # `giay_chung_nhan_tot_nghiep_00004_p2`, every key box piled
                # into the top-left corner while the value boxes sat right.
                "key_bbox_px": block.get("bbox_px"),
                "value_bbox_px": value.get("bbox_px"),
                # The caption's own `data-kind`, carried so `describe` has the
                # closed half of the vocabulary on this path too. `pair_entities`
                # supplies it through `key_entity_index`; blocks have no index
                # to point with, so the kind rides along.
                "key_kind": kind,
            })
            index += 2
            continue
        index += 1
    return pairs


def _fallback_description(key_text: str) -> str:
    """Câu tả dựng từ nhãn in trên giấy, khi từ điển không có mục nào.

    Bản trước trả về CHÍNH cái nhãn, bỏ dấu hai chấm -- nên trường `cccd` có
    câu tả "CCCD" và trường `ngay_de_nghi` có "Ngày đề nghị". Một câu tả lặp
    lại tên trường không nói thêm gì: người đọc `kie.schema` đã thấy tên rồi.
    Đo trên `data/test1`: 35 trường như vậy.

    Không bịa ra nghĩa -- ta KHÔNG biết "CCCD" nghĩa là gì ngoài chữ in. Thứ
    ta biết chắc là VỊ TRÍ: nó là giá trị in cạnh cái nhãn ấy. Nói đúng chừng
    ấy, thành một câu, và `description_source` vẫn ghi `caption` để người đọc
    biết câu này dựng từ giấy chứ không phải ai viết ra."""
    label = str(key_text or "").rstrip(":：").strip()
    if not label:
        return ""
    return f"Value printed on the sheet beside the caption \u201c{label}\u201d."


# Where a description came from, best first. `fallback` is the name the
# caption-derived one has always had and stays valid so records written before
# this split still read; new pages say `caption`, which means the same thing
# and says it precisely.
DESCRIPTION_SOURCES = ("llm", "caption", "kind", "label", "fallback")


def describe(field: str, *, caption: str = "", kind: str = "",
             layout_class: str = "", layout: str = "") -> tuple[str, str]:
    """`(description, source)` for one field. Four sources, best first.

    Every one of them is DATA the page already carries -- there is no table of
    per-document strings anywhere in this file, and there must not be, because
    a table is a thing a new document type is missing from:

    1. `llm` -- a model-written description out of the `VLM_KIE_DESCRIPTIONS`
       file, keyed by layout then field. The only one a person or a model
       wrote; the other three are derivations.
    2. `caption` -- the caption printed beside the value. Never wrong, never
       absent when a caption was printed, and the reason no page needs a model
       to have been run over it.
    3. `kind` -- the run's own `data-kind`, which IS the dotted field path
       every `sheets/*.py` family writes (`store.name`, `total.grand`). The
       answer when NO caption was printed: a page title has no "Loại chứng
       từ:" beside it, and `title` still says what it is.
    4. `label` -- the 19-label `layout_class`, for a run whose kind says
       nothing more than its class does.

    Nothing here can return empty: `field` itself is the floor, and `slug`
    already guarantees that is non-empty.
    """
    written = _written_entry(field, layout)
    if isinstance(written, dict):
        written = written.get("description")
    if isinstance(written, str) and written.strip():
        return written.strip(), "llm"
    # `rulebase/kie_glossary.py`: bảng nghĩa tiếng Anh viết sẵn, tra theo slug
    # rồi theo `kind`. Nó không phải "bảng chuỗi cho từng loại chứng từ" mà
    # docstring trên cấm -- tầng dưới của nó khoá theo `data-kind`, thứ chính
    # `sheets/*.py` sinh ra, nên một loại chứng từ mới không thiếu khỏi bảng.
    try:
        from rulebase import kie_glossary
        found = kie_glossary.describe(field, kind=kind)
    except Exception:                                   # noqa: BLE001
        found = None
    if found:
        return found[0], "llm"
    printed = _fallback_description(caption) if caption else ""
    if printed:
        return printed, "caption"
    if kind:
        return str(kind), "kind"
    if layout_class:
        return str(layout_class), "label"
    return field, "label"


# Kind KHÔNG thành trường KIE dù không có key: chúng là bộ khung của trang,
# không phải thông tin trích được.
#
# `colhdr`/`colnum` đã có `STRUCTURE` lo, `menu.*` đã đi vào `line_items`; ba
# cái dưới đây là phần còn lại: chữ chìm không thuộc nội dung, chân trang là
# mẫu số hiệu in sẵn, và số trang do máy cắt sinh ra.
KEYLESS_SKIP = frozenset({"watermark", "footer.page", "colnum"})


def _slug_kind(kind: str) -> str:
    """`clause.body` -> `clause_body`. Tên trường khi run không có key in kèm."""
    return re.sub(r"[^a-z0-9]+", "_", str(kind or "").lower()).strip("_")


def pair_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same `(field, key, value)` pairs as `pair_fields`, read off entities.

    `pipeline.record.entities_from_words` has already done the pairing -- a
    value entity carries `key_entity_index` and `field_name` -- so this only
    reshapes it into the `kie.pairs` a reader already expects.

    Why that is better than doing it here on blocks: a block is one LINE of a
    run, so a caption that wrapped onto two lines paired its own second line
    with the value, and a value that wrapped contributed only its first line's
    text. An entity is the whole run, and neither can happen.
    """
    by_index = {entity.get("entity_index"): entity for entity in entities}
    pairs: list[dict[str, Any]] = []
    for entity in entities:
        key_index = entity.get("key_entity_index")
        key = by_index.get(key_index)
        kind = str(entity.get("kind") or "")
        if entity.get("field_role") != "value":
            continue
        if kind in FURNITURE:
            continue
        if key is None:
            # Run không có nhãn in kèm KHÔNG dựng cặp ở đây. Nó vẫn vào KIE,
            # nhưng qua `synthgen/kie_full.py` -- chỗ có `kind` đầy đủ và biết
            # đặt tên lẫn câu tả. Dựng cặp ở cả hai nơi thì một chỗ chữ ra hai
            # trường: đo được `title` và `doc_title` cùng ba phần tử.
            continue
        pairs.append({
            "field": str(entity.get("field_name") or "field"),
            "key_text": str(key.get("text", "")).strip(),
            "value_text": str(entity.get("text", "")).strip(),
            "key_bbox": _bbox_dict(key.get("bbox")),
            "value_bbox": _bbox_dict(entity.get("bbox")),
            # Pixel twins -- see the note on the other construction site.
            "key_bbox_px": _bbox_dict(key.get("bbox_px")),
            "value_bbox_px": _bbox_dict(entity.get("bbox_px")),
            # The two boxes as entities, so a reader can get back to the
            # words, the lines and the polygon without matching on text.
            "key_entity_index": key_index,
            "value_entity_index": entity.get("entity_index"),
        })
    return pairs


# CHỮ IN SẴN KHÔNG PHẢI GIÁ TRỊ.
#
# "(Ký, ghi rõ họ tên)" là lời nhắc nhà in đặt dưới mỗi ô chữ ký -- nó có mặt
# trên mọi tờ, giống hệt nhau, dù ai ký hay không ai ký. `markup.py` phát nó
# dưới `kind="sign.note"`, và cùng `kind` ấy cũng được dùng cho ô tên BỎ TRỐNG
# khi tờ giấy không ghi sẵn tên người ký.
#
# Hệ quả đo được trên `data/14-09-test2`: 281 trên 421 cặp thuộc họ `sign.`
# -- HAI PHẦN BA -- có `value_text` là "(Ký, ghi rõ họ tên)". Tức bộ dữ liệu
# đang dạy mô hình rằng người chấm công tên là "(Ký, ghi rõ họ tên)".
#
# Luật: một giá trị KIE phải là thứ THAY ĐỔI giữa các tờ. Chữ in sẵn giống
# nhau trên mọi tờ mang đúng không bit thông tin nào -- nó vẫn nằm đủ trong
# `word_annotations` và `entity_annotations` kèm hộp, nên không mất gì cả;
# chỉ là nó thôi giả làm câu trả lời cho một câu hỏi.
#
# Tên người ký THẬT vẫn vào KIE bình thường: `kie_full.IMPLIED` bắt
# `sign.name` và dựng cặp `signer_name` cho nó.
# `masthead.motto` ĐÃ RA KHỎI ĐÂY. "Độc lập - Tự do - Hạnh phúc" là dòng thứ
# hai của tiêu ngữ quốc gia, không phải lời nhắc nhà in: người hỏi "tiêu ngữ
# trên tờ này là gì" muốn cả hai dòng. Nó cũng không giống `sign.note` ở chỗ
# `sign.note` là chỉ dẫn cho NGƯỜI ĐIỀN, còn dòng này là nội dung đã in.
#
# Hệ quả đo được khi nó còn ở đây: 66 dòng có hộp đầy đủ trong
# `entity_annotations` mà không vào một cặp KIE nào, và cũng không vào `marks`
# -- vì `marks` dựng từ CẶP, mà nó bị loại trước khi thành cặp. Mực trên giấy
# biến mất khỏi bản xuất.
FURNITURE = frozenset({"sign.note"})


def _bbox_dict(bbox: Any) -> dict[str, int] | None:
    """An entity's `[x1, y1, x2, y2]` as the `{x1, y1, x2, y2}` a pair has
    always carried. Same shape blocks give, so nothing reading `kie.pairs`
    has to learn a second one."""
    if isinstance(bbox, dict):
        return bbox
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return {"x1": int(bbox[0]), "y1": int(bbox[1]),
                "x2": int(bbox[2]), "y2": int(bbox[3])}
    return None


def build_page(blocks: list[dict[str, Any]], *,
               entities: list[dict[str, Any]] | None = None,
               layout: str = "") -> dict[str, Any]:
    """The `"kie"` section of one page's record: a JSON-Schema `properties`
    object plus the box pair behind every property in it.

    Always populated, LLM or not -- see the module docstring's "Fallback"
    section. `description_source` on each pair says which one a field got,
    so a later pass can tell a real description from a placeholder without
    re-deriving it.

    `entities` is `record.entity_annotations` for this page and is preferred
    when it is there, because a run that wrapped is one entity and two blocks
    -- see `pair_entities`. Blocks stay the path for a backend that measures
    no DOM (the character grid), so this has one answer for every page either
    way.

    **The schema is the captioned pairs, not every entity.** Every entity has
    a `field_name` and a `description` of its own; a reader that wants all of
    them reads `entity_annotations`. What goes in `kie.schema` is what an
    extractor is sensibly ASKED for, and two hundred table-cell properties is
    not that.
    """
    if entities:
        pairs = pair_entities(entities)
        described = {str(entity.get("field_name")): entity
                     for entity in entities if entity.get("description")}
    else:
        pairs = pair_fields(blocks)
        described = {}
    properties: dict[str, Any] = {}
    out_pairs: list[dict[str, Any]] = []
    for pair in pairs:
        field = pair["field"]
        already = described.get(field)
        if already:
            # `entities_from_words` already resolved this one through
            # `describe`, and asking twice is how the two would disagree.
            description = str(already.get("description") or "")
            source = str(already.get("description_source") or "caption")
        else:
            index = pair.get("key_entity_index")
            kind = str(pair.get("key_kind") or "")
            if isinstance(index, int) and 0 <= index < len(entities or []):
                kind = str((entities[index] or {}).get("kind") or "")
            description, source = describe(field, caption=pair["key_text"],
                                           kind=kind, layout=layout)
        # Only the contested captions carry one, so the key is absent rather
        # than empty on the other 99.2%: a reader can tell "no guidance
        # needed" from "guidance that says nothing".
        guide = guidelines_for(field, layout)
        prop: dict[str, Any] = {"type": "string", "description": description}
        extra: dict[str, Any] = {}
        if guide:
            prop["guidelines"] = guide
            extra["guidelines"] = guide
        properties[field] = prop
        out_pairs.append({**pair, "description": description,
                          "description_source": source, **extra})
    return {"schema": {"type": "object",
                       "properties": _folded(properties, pairs)},
            "pairs": out_pairs}


# `items[0].name` -> `("items", "name")`. Chỉ số nào cũng được, kể cả nhiều
# tầng: `sections[2].rows[7].amount` -> `("sections", "rows", "amount")`.
_INDEXED = re.compile(r"\[\d+\]|\.\d+(?=\.|$)")


def _folded(properties: dict[str, Any],
            pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Gộp đường dẫn có chỉ số thành MỘT mục kiểu mảng.

    ## Triệu chứng

    Model khai `items[0].name`, `items[1].name`, `items[2].name`... và mỗi cái
    thành một thuộc tính phẳng `items_0_name`, `items_1_name`. Một bảng mười
    ba dòng sáu cột cho bảy mươi tám thuộc tính, và `kie.schema` -- thứ đem
    HỎI một VLM -- thành một danh sách không ai đọc hết.

    `docs/kie-thiet-ke-nhan.md` §F4 đo được đỉnh điểm 113 thuộc tính một
    trang, và chốt hình dạng đúng: `items: {"type": "array", ...}` -- một mục
    cho cả bảng.

    ## Vì sao gộp ở ĐÂY chứ không lúc đặt tên

    `pairs` vẫn phải giữ từng ô một: mỗi ô có hộp riêng, và hộp là thứ không
    được gộp. Chỉ `schema` -- bản khai "tài liệu này có những trường nào" --
    mới nói về mảng. Hai thứ khác nhau, và gộp nhầm chỗ thì mất toạ độ.

    Đường dẫn không có chỉ số thì không đụng tới: `tax_code` vẫn là
    `tax_code`."""
    by_field = {str(p.get("field")): p for p in pairs if p.get("field")}
    folded: dict[str, Any] = {}
    members: dict[str, list[str]] = {}
    for name, spec in properties.items():
        path = str((by_field.get(name) or {}).get("path") or "")
        if not path or not _INDEXED.search(path):
            folded.setdefault(name, spec)
            continue
        root = path.split("[")[0].split(".")[0]
        leaf = _INDEXED.sub("", path).split(".")[-1] if "." in path else root
        slot = folded.setdefault(root, {
            "type": "array",
            "description": f"Every row of `{root}` printed on the sheet.",
            "items": {"type": "object", "properties": {}},
        })
        if slot.get("type") != "array":
            continue
        props = slot["items"]["properties"]
        if leaf not in props:
            props[leaf] = {"type": "string",
                           "description": str(spec.get("description") or "")}
        members.setdefault(root, []).append(name)
    return folded


__all__ = ["DESCRIPTIONS_ENV", "DESCRIPTION_SOURCES", "build_page", "describe",
           "pair_entities", "pair_fields", "slug"]
