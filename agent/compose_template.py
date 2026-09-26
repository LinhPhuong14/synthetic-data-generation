#!/usr/bin/env python3
"""Pha 1: xin model soạn một PHÔI -- HTML mang `{{chỗ.trống}}`, không giá trị.

    python -m agent.compose_template --want 200 -o data/phoi-v1
    python -m agent.compose_template --want 12 --no-draw -o /tmp/thu

Đây là nửa đầu của đường sinh thứ ba. Nửa sau là `synthgen/run_fill.py`, và
nó không gọi model một lần nào.

## Ba đường, cùng một bản ghi ở cuối

| đường | ai viết HTML | lời gọi model cho 10 000 ảnh |
| --- | --- | --- |
| luật (`synthgen/run.py`) | `synthgen/markup.py` | 0 |
| model viết từng trang (`agent/compose_page.py`) | model, mỗi trang một lần | ~45 000 (tỉ lệ đạt 22%) |
| **model viết phôi** (file này) | model, mỗi PHÔI một lần | ~900 (200 phôi / 22%) |

Bảng đầy đủ, có giây và token đo được, ở `docs/duong-sinh-phoi.md`.

## Vì sao cổng ở đây CHẶT HƠN cổng của `agent/compose_page.py`

`compose_page` cố ý không ép `data-path` phải thuộc sổ đóng: một tên lạ ở đó
hỏng đúng một tờ, và `synthgen/field_tier.py` hạ nó xuống `staging` mà không
mất tờ nào. Cái tính toán ấy đảo ngược hoàn toàn ở đây. Một phôi được điền
hàng trăm tới hàng nghìn lần, nên một đường dẫn sai TRONG PHÔI là cùng một
lỗi nhân lên chừng ấy lần, và không sửa được sau khi ảnh đã vẽ.

Nên ba lớp, không một:

1. `enum` trong `response_format` -- bộ giải mã có ràng buộc KHÔNG THỂ sinh
   một đường dẫn ngoài sổ ở mảng `slots`.
2. `synthgen/template.py::problems()` -- gác chính HTML, vì `html` là một
   `string` tự do và `enum` không với tới bên trong nó.
3. Một lần ĐIỀN THỬ rồi chạy `synthgen/llm_page.py::problems()` trên kết quả.
   Cổng ấy đếm chữ IN RA, nên nó không chạy được trên phôi chưa điền: một
   phôi chưa điền chưa in gì cả. Điền thử là cách duy nhất hỏi được "trang
   này, khi có giá trị thật, có đo được không".

Lớp 3 là lớp bắt được nhiều nhất, và nó cũng là lớp rẻ nhất: một lần điền tốn
chừng một phần nghìn giây.

## Đa dạng ở đây đo trên PHÔI, không trên trang

Hai phôi khác nhau mà điền ra hai tờ trông y hệt là một lỗi đắt gấp N lần một
cặp trang trùng. Nên mỗi phôi qua cổng chữ được điền thử MỘT lần, dàn ra để
đo (`Artist.measure`), và dấu vân hình học của nó đi qua đúng
`agent/diversity.py::DiversityWarden` mà `compose_page` dùng -- cùng ngưỡng
Jaccard 0,60, cùng cửa sổ 24. Trùng thì xin lại phôi kèm câu nhắc nói rõ khối
nào đang ngồi đúng chỗ khối cũ.

Tầng thứ hai -- "hai lần điền CÙNG một phôi đừng ra cùng một tổ hợp giá trị"
-- không thuộc file này; nó ở `synthgen/fill.py::Filler`.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import json
import os
import random
import sys
import threading
import time
from pathlib import Path

if __package__ in (None, ""):                   # `python compose_template.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import diversity as DIV
from agent import document_plan as DP
from agent import geometry_distance as GD
from agent import grammar as G
from agent.client import LLMError, from_env
from agent.compose_page import (
    FAMILY_HINT,
    REGION_SLOT,
    Artist,
    _close,
    _coined_pattern,
    base_rules,
    describe_plan,
    family_of,
    inspiration,
    region_table,
)
from agent.fingerprint import geometry_fingerprint
from agent.promptbook import prompt
from pipeline import failures
from synthgen import field_tier as FT
from synthgen import fill as FILL
from synthgen import template as T
from synthgen.llm_page import REGIONS
from synthgen.llm_page import problems as page_problems
from synthgen.repair import runify

PROMPT = "template"

# Bao nhiêu tờ điền thử cho mỗi phôi ở pha 1. Một là đủ để trả lời "phôi này
# điền ra có đo được không"; ba là đủ để trả lời "số dòng đổi thì trang có còn
# đo được không", và đó mới là câu hỏi thật -- một phôi qua cổng với 8 dòng
# rồi vỡ bố cục ở 24 dòng là một phôi hỏng mà một lần thử không thấy.
SMOKE_FILLS = 3


def system_prompt() -> str:
    """Base rules cộng `template.md`, bảng nhãn vùng đã dán vào.

    Dùng lại `base_rules()` của `agent/compose_page.py` nguyên văn: phần "vì
    sao bộ dữ liệu phải đa dạng và thật" đúng y như thế cho một model viết
    phôi. Thứ KHÔNG dùng lại là `page.md` -- nó dạy viết GIÁ TRỊ (cây `data`,
    mảng `rows`, số học từng dòng), và mọi câu ấy sai ở đây: giá trị không
    phải việc của model nữa."""
    base = base_rules()
    page = prompt(PROMPT)
    if REGION_SLOT not in page:
        raise LLMError(f"{PROMPT}.md không còn chỗ dán {REGION_SLOT!r}; "
                       "bảng nhãn vùng sẽ không tới model")
    page = page.replace(REGION_SLOT, region_table())
    return f"{base}\n\n---\n\n{page}" if base else page


def schema() -> dict:
    """Hình dạng câu trả lời. `path` là `enum` -- xem docstring module.

    Khác `agent/compose_page.py::schema()` ở đúng ba chỗ, và cả ba đều là hệ
    quả của việc model không còn cầm giá trị:

    * `data` (cây giá trị) BIẾN MẤT. Giá trị do `synthgen/values.py` sinh.
    * `rows` (dòng bảng) BIẾN MẤT. Bảng là một `<tr data-repeat>`, và số dòng
      là quyết định của lần ĐIỀN, không của phôi. Đây cũng là chỗ bỏ được
      phép kiểm số học tốn kém nhất của đường cũ: đo trên 48 tài liệu,
      22 tài liệu khai nhiều dòng hơn vẽ, tệ nhất khai 129 vẽ 18. Không còn
      hai nguồn thì không còn chỗ để chúng lệch.
    * `slots` THAY `field_plan`. Cùng vai trò (bắt model đối chiếu tên trường
      với một danh sách đóng trước khi viết HTML) nhưng ép bằng `enum` thật
      trên `path`, không phải `pattern` -- vì ở đây không có cửa thoát đặt
      tên mới. Một cái tên mới trong phôi là một cái tên mới trên nghìn tờ.
    """
    paths = list(FT.closed_enum(FT.PATH))
    return _close({
        "type": "object",
        "properties": {
            "plan": {
                "type": "object",
                "properties": {
                    "doc_kind": {"type": "string"},
                    "doc_title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "issuer": {"type": "string"},
                    "layout_idea": {"type": "string"},
                    "reasoning": {
                        "type": "object",
                        "properties": {
                            "why_this_document": {"type": "string"},
                            "why_this_layout": {"type": "string"},
                            "what_stays_literal": {
                                "type": "string",
                                "description": "Which text you kept as fixed "
                                               "form text and why -- the one "
                                               "judgement this job turns on.",
                            },
                        },
                        "required": ["why_this_document", "why_this_layout",
                                     "what_stays_literal"],
                    },
                },
                "required": ["doc_kind", "doc_title", "purpose", "issuer",
                             "layout_idea", "reasoning"],
            },
            "slots": {
                "type": "array",
                "description": "One entry per DISTINCT placeholder used in "
                               "the HTML.",
                "items": {
                    "type": "object",
                    "properties": {
                        # ENUM, KHÔNG `pattern`. Đây là khác biệt lớn nhất
                        # giữa file này và `compose_page.schema()`, và lý do
                        # nằm ở chỗ một phôi được dùng lại: `pattern` cho
                        # model ĐẶT TÊN MỚI, và một tên mới trong phôi là
                        # cùng một tên lạ in trên nghìn tờ giấy.
                        "path": {"type": "string", "enum": paths},
                        # `kind` thì VẪN có cửa thoát: nó là nhãn lớp của
                        # chữ, không phải danh tính trường, và từ vựng
                        # `kinds()` nhặt từ HTML engine nên nó thiếu đúng
                        # những khối mà một loại giấy mới mang. Hai không gian
                        # tên, hai chính sách -- `synthgen/field_tier.py` xếp
                        # tầng riêng cho từng cái.
                        "kind": {
                            "anyOf": [
                                {"type": "string",
                                 "enum": list(FT.closed_enum(FT.KIND))},
                                {"type": "string",
                                 "pattern": _coined_pattern()},
                            ],
                        },
                        "label": {
                            "type": "string",
                            "description": "The fixed caption printed next to "
                                           "this placeholder on the blank "
                                           "form, e.g. 'Mã số thuế:'. Empty "
                                           "when the value stands alone.",
                        },
                    },
                    "required": ["path", "kind", "label"],
                },
            },
            "html": {"type": "string"},
        },
        "required": ["plan", "slots", "html"],
    })


def ask_for(index: int, made: list[str], plan: DP.DocumentPlan,
            lang: str = "en", avoid: str = "") -> str:
    """Lời nhờ cho MỘT phôi.

    Khác `compose_page.ask_for()` ở chỗ KHÔNG xin số ký tự và KHÔNG xin số
    dòng bảng: cả hai là quyết định của lần ĐIỀN, không của phôi. Xin chúng ở
    đây là khoá mọi tờ ra từ phôi này vào cùng một độ dày -- và độ dày giống
    nhau là đúng thứ làm dấu vân hình học của chúng trùng nhau."""
    hint = FAMILY_HINT.get(plan.family, plan.family)
    every = ", ".join(FT.closed_enum(FT.KIND))
    paths = ", ".join(FT.closed_enum(FT.PATH))
    seen = ", ".join(made[-14:]) if made else "nothing yet"
    table = "table" in plan.assignment
    return (
        "## Step 1 -- decide WHICH Vietnamese document this template is for\n\n"
        f"Field: **{hint}** (`{plan.family}`).\n\n"
        "### Structure -- decided by the engine, not by you\n\n"
        f"{describe_plan(plan)}\n\n"
        + (f"{avoid}\n\n" if avoid else "")
        + f"{inspiration(index, plan.family, lang, table=table)}"
        "Invent a specific document of that family -- a real kind of paper a "
        "Vietnamese organisation issues, not a generic one. Templates already "
        f"written this run: {seen}. Write a different one.\n\n"
        "## Step 2 -- decide what is FIXED FORM TEXT and what is a PLACEHOLDER\n\n"
        "This is the judgement the whole job turns on; section 0 of your "
        "instructions has the rule. Captions, titles, column headings, "
        "signature-block wording: literal. Names, numbers, dates, amounts, "
        "addresses: placeholders.\n\n"
        "### The placeholder paths you may use -- this list is CLOSED\n\n"
        f"{paths}\n\n"
        "Anything not on that list is either fixed text or left out. Do not "
        "invent a path.\n\n"
        "### The `data-kind` vocabulary for the runs\n\n"
        f"{every}\n\n"
        f"### Region labels\n\n{', '.join(REGIONS)}\n\n"
        "## Step 3 -- write the template\n\n"
        + ("The table body is ONE `<tr data-repeat=\"line_items\">`. The "
           "filler clones it; you never write a second row.\n\n" if table
           else "This document has no item table. Do not write one.\n\n")
        + "Return `plan`, `slots` (one entry per distinct placeholder), and "
        "`html`. No values, no filled example.\n"
    )


# --------------------------------------------------------------------- cổng gác

def slot_problems(slots, html: str) -> list[str]:
    """`slots` model tự khai có khớp HTML nó vừa viết không.

    Hai chiều, và cả hai đều đáng kể:

    * chỗ trống CÓ trong HTML mà KHÔNG khai -- lời khai thiếu, nên bảng
      `kinds` mà `synthgen/run_fill.py` đọc để gắn nhãn sẽ thiếu đúng chỗ ấy;
    * chỗ trống KHAI mà HTML không dùng -- vô hại cho trang vẽ ra, nhưng nó
      là dấu hiệu model đã đổi ý giữa chừng, và đo được ở đường cũ là dấu
      hiệu đi kèm những tờ hỏng khác.

    Chỉ chiều thứ nhất làm trượt phôi; chiều thứ hai ghi ra để đếm."""
    declared = {str(s.get("path") or "") for s in (slots or [])
                if isinstance(s, dict)}
    used = set(T.paths(html))
    found = []
    for path in sorted(used - declared):
        found.append(f"chỗ trống `{{{{{path}}}}}` có trong HTML mà không có "
                     "trong `slots`; bảng nhãn của phôi sẽ thiếu đúng chỗ ấy")
    return found


def smoke(template: T.Template, seed: int,
          fills: int = SMOKE_FILLS) -> tuple[list[str], list[str], dict]:
    """Điền thử rồi chạy cổng chữ trên KẾT QUẢ. `(html thử, lý do trượt, số đo)`.

    Ba lần điền với số dòng khác nhau, không một: một phôi qua cổng ở 8 dòng
    rồi vỡ ở 24 dòng là một phôi hỏng, và một lần thử không thấy điều ấy.
    Trượt ở BẤT KỲ lần nào là trượt cả phôi -- phôi sẽ được điền hàng nghìn
    lần và ta không chọn được số dòng cho từng lần."""
    filler = FILL.Filler(template)
    pages: list[str] = []
    found: list[str] = []
    rows: list[int] = []
    for i in range(max(1, fills)):
        got = filler.draw(random.Random(seed + 7919 * i))
        if got.missing:
            found.append(f"điền thử: {len(got.missing)} chỗ trống không có giá "
                         f"trị ({', '.join(got.missing[:3])}); "
                         "`synthgen/values.py` không sinh được chúng")
        html, _mended, _stamped, _signed = FILL.prepare(got.html, seed + i)
        pages.append(html)
        rows.append(got.counts.get("line_items", 0))
        for why in page_problems(html):
            found.append(f"điền thử {got.counts.get('line_items', 0)} dòng: {why}")
    return pages, found, {"smoke_rows": rows}


def one(client, index: int, made: list[str], seed: int, lang: str = "en",
        plan: DP.DocumentPlan | None = None, avoid: str = "",
        attempt: int = 1) -> dict:
    """Một phôi: hỏi, gác ba lớp, trả bản ghi. Không ném -- lỗi là một kết quả."""
    started = time.time()
    if plan is None:
        plan = DP.sample(G.FAMILIES[family_of(index)], random.Random(seed + index))
    brief = ask_for(index, made, plan, lang, avoid=avoid)
    try:
        answer, usage = client.decide_with_usage(
            system_prompt(), brief, schema(),
            # PHÔI NGẮN HƠN TRANG. Không có giá trị nào trong đó -- chỗ một
            # tên công ty 45 ký tự đứng thì phôi viết 17 ký tự `{{issuer.
            # name}}` -- và bảng là MỘT dòng mẫu thay vì N dòng, mà thân bảng
            # là 21% số ký tự đầu ra của một trang (`docs/kiem-soat-llm.md`
            # mục 1). 6 000 token là rộng rãi; nó chỉ chặn ca model lan man.
            max_tokens=int(os.environ.get("VLM_TEMPLATE_MAX_TOKENS", 6000)),
            timeout=float(os.environ.get("VLM_TEMPLATE_TIMEOUT", 0) or 0) or 0.0)
    except LLMError as error:
        spent = round(time.time() - started, 1)
        text = str(error)
        return {"index": index, "family": plan.family, "ok": False,
                "seconds": spent,
                "timed_out": "timed out" in text.lower() or "timeout" in text.lower(),
                "tokens_in": 0, "tokens_out": 0,
                "why": [f"model không trả lời: {text[:120]}"],
                "html": "", "slots": [], "plan": {},
                "attempt": attempt, "brief": brief}
    spent = round(time.time() - started, 1)
    html = str(answer.get("html") or "")
    declared = dict(answer.get("plan") or {})
    slots = list(answer.get("slots") or [])

    # CHỮA TRƯỚC KHI GÁC -- cùng luật `agent/compose_page.py::one()` đã đặt
    # ra ("cổng vẫn y nguyên, chạy sau, và vẫn loại mọi thứ nó vẫn loại; chỉ
    # là thôi bắt model làm một việc mười dòng mã làm đúng mọi lần").
    #
    # CHỈ `runify`, không phải cả `repair()`. Hai lý do, và cả hai đều về thứ
    # tự:
    #
    # * `repair.grid()` đánh `data-row`/`data-col` cho ô bảng, và nó PHẢI chạy
    #   sau khi khối lặp đã bung (xem `synthgen/fill.py::prepare`). Chạy trên
    #   phôi thì nó đánh số cho đúng một dòng mẫu.
    # * `repair.rows_out`/`breaks`/`unclash` đọc CHỮ ĐÃ IN để quyết, và chữ
    #   trên phôi là `{{…}}` -- chúng sẽ quyết trên một chuỗi không bao giờ ra
    #   giấy.
    #
    # `runify` thì thuần cấu trúc: nó chuyển hai thuộc tính vào một span bên
    # trong và không đọc chữ nào. Phần chữa còn lại vẫn chạy đủ ở
    # `fill.prepare()`, trên bản ĐÃ điền, như cũ.
    html, moved = runify(html)
    # BỌC CHỖ TRỐNG TRẦN, dùng chính lời khai `slots` của model. Đây là phép
    # ĐỌC, không phải phép đoán -- xem `synthgen/template.py::enclose`. Chỗ
    # trống model KHÔNG khai thì không được bọc: bịa một nhãn cho nó là gắn
    # sai danh tính cho một run, tệ hơn không gắn.
    declared_kinds = {str(s.get("path") or ""): str(s.get("kind") or "")
                      for s in slots if isinstance(s, dict)}
    html, enclosed = T.enclose(html, declared_kinds)
    # ĐÁNH DẤU KHỐI LẶP model quên khai. Suy được vì một nhóm `x[]` chỉ có
    # nghĩa khi nó lặp -- xem `synthgen/template.py::mark_repeats`. Phép suy
    # tự dừng khi một khối ôm hai nhóm: lúc ấy KHÔNG đánh dấu gì, để cổng
    # loại, vì đó là vấn đề cấu trúc thật chứ không phải thiếu một thuộc tính.
    html, marked = T.mark_repeats(html)

    # LỚP 2: cú pháp chỗ trống + sổ đóng, đo trên chính HTML.
    found = T.problems(html) + slot_problems(slots, html)
    template = T.Template(
        template_id=f"{plan.family}_{index:04d}",
        family=plan.family, html=html,
        doc_kind=str(declared.get("doc_kind") or ""),
        doc_title=str(declared.get("doc_title") or ""),
        kinds=dict(declared_kinds),
        meta={"purpose": str(declared.get("purpose") or ""),
              "issuer": str(declared.get("issuer") or ""),
              "engine_plan": dict(plan.assignment),
              "hard_negative_profile": dict(plan.hard_negative_profile)})

    # LỚP 3: điền thử rồi gác trang ĐÃ ĐIỀN. Chỉ chạy khi lớp 2 sạch -- điền
    # một phôi mà cú pháp chỗ trống đã hỏng chỉ sinh ra một tràng lý do thứ
    # hai nói về cùng một lỗi, và người đọc báo cáo phải lần qua cả hai mới
    # thấy lỗi gốc.
    smoke_pages: list[str] = []
    measures: dict = {}
    if not found:
        smoke_pages, smoke_found, measures = smoke(template, seed + index)
        found += smoke_found

    tiers = FT.classify_data(
        [{"path": p} for p in T.paths(html)],
        doc_type=plan.family, doc_title=template.doc_title)
    out_tokens = int(usage.get("completion_tokens") or 0)
    in_tokens = int(usage.get("prompt_tokens") or 0)
    return {
        "index": index, "family": plan.family, "ok": not found,
        "seconds": spent, "why": found,
        "html": html, "slots": slots, "plan": declared,
        "template": template,
        "smoke_html": smoke_pages,
        "doc_kind": template.doc_kind, "doc_title": template.doc_title,
        "engine_plan": dict(plan.assignment),
        "hard_negative_profile": dict(plan.hard_negative_profile),
        "paths": T.paths(html),
        "repeats": template.repeat_names,
        # BAO NHIÊU NHÃN PHẢI CHUYỂN VÀO SPAN. Ghi cho cả phôi đạt lẫn phôi
        # trượt: nếu con số này về 0 sau một lần sửa `template.md` thì lời dặn
        # đã ăn, và luật chữa thành thừa -- không đọc được nó thì không ai
        # biết lúc nào bỏ được.
        "runified": moved,
        "enclosed": enclosed,
        "repeats_marked": marked,
        "field_tiers": FT.tally(tiers),
        "chars": len(html),
        "tokens_in": in_tokens, "tokens_out": out_tokens,
        "tokens_per_second": round(out_tokens / spent, 1) if spent else 0.0,
        "brief": brief, "attempt": attempt, "diversify_hinted": bool(avoid),
        **measures,
    }


def broken(index: int, error: BaseException) -> dict:
    """Bản ghi thay thế cho một lượt gọi VỠ. Hình dạng khớp `one()` từng khoá.

    Cùng lẽ `agent/compose_page.py::broken`: `future.result()` ném lại ngoại
    lệ của worker, và một lỗi lạ ở phôi thứ tư không được làm mất ba phôi đã
    xong."""
    return {"index": index, "family": "", "ok": False, "seconds": 0.0,
            "chars": 0, "tokens_in": 0, "tokens_out": 0,
            "tokens_per_second": 0.0,
            "why": [f"lượt gọi vỡ: {type(error).__name__}: {error}"],
            "html": "", "slots": [], "plan": {}, "template": None,
            "smoke_html": [], "doc_kind": "", "doc_title": "",
            "engine_plan": {}, "hard_negative_profile": {},
            "paths": [], "repeats": [], "field_tiers": {},
            "brief": "", "attempt": 1, "diversify_hinted": False}


# ------------------------------------------------------------------ lượt chạy

def run(want: int, out: Path, *, concurrency: int, seed: int,
        lang: str = "en", no_draw: bool = False, diversity: bool = True,
        steer: bool = True, window: int = GD.WINDOW,
        ceiling: float = GD.JACCARD_CEILING,
        attempts: int = DIV.MAX_ATTEMPTS) -> int:
    client = from_env(timeout=float(os.environ.get("VLM_LLM_TIMEOUT", 600)),
                      max_tokens=int(os.environ.get("VLM_TEMPLATE_MAX_TOKENS", 6000)))
    if client is None:
        print("chưa đặt VLM_LLM_URL. Ví dụ:\n"
              "  export VLM_LLM_URL=http://10.148.20.19:8008/v1\n"
              "  export VLM_LLM_MODEL=Qwen/Qwen3.8-27B-FP8\n"
              "  export NO_PROXY='10.148.20.19,localhost,127.0.0.1'")
        return 1
    if not client.alive():
        print(f"{client.url} không trả lời.\n"
              "Nếu máy có proxy thì mọi kết nối tới IP nội bộ bị chặn -- "
              "`env | grep -i proxy`, rồi đặt NO_PROXY.")
        return 1

    print(f"[phôi] {want} phôi, {concurrency} request song song, "
          f"model {client.model}")
    print(f"[phôi] {len(FT.closed_enum(FT.PATH))} đường dẫn trong sổ đóng "
          f"(enum), {len(G.FAMILIES)} family")
    for name in ("templates", "rejected", "thinking", "smoke"):
        (out / name).mkdir(parents=True, exist_ok=True)

    started = time.time()
    made: list[dict] = []
    kinds_made: list[str] = []
    lock = threading.Lock()
    discarded: list[dict] = []
    warden = DIV.DiversityWarden(enabled=diversity, steer=steer, window=window,
                                 ceiling=ceiling)

    artist: Artist | None = None
    if not no_draw:
        artist = Artist(out)
        artist.start()

    def measure_geometry(html: str, stem: str, family: str):
        if artist is None or not html:
            return None
        record = artist.measure(html, stem, family)
        if not record:
            return None
        return geometry_fingerprint(record.get("layout_annotations") or [])

    def work(index: int) -> dict:
        family = family_of(index)
        grammar = G.FAMILIES[family]
        rng = random.Random(seed + index)
        avoid = ""
        got: dict = {}
        for attempt in range(1, max(1, attempts) + 1):
            with lock:
                seen = list(kinds_made)
            plan, plan_fp = warden.draw(grammar, rng)
            got = one(client, index, seen, seed, lang, plan=plan,
                      avoid=avoid, attempt=attempt)
            if not got["ok"]:
                break
            # ĐO TRÊN TỜ ĐIỀN THỬ, không trên phôi: phôi mang `{{…}}` nên mọi
            # hộp đo trên nó là hộp của một chuỗi không bao giờ in ra.
            stem = f"tpl_{got['family']}_{index:04d}"
            geo = measure_geometry((got.get("smoke_html") or [""])[0], stem,
                                   got["family"])
            collision, taken = warden.judge(
                plan_fp, geo, key=index, attempt=attempt,
                force=attempt >= max(1, attempts))
            if collision is not None:
                got["collision"] = collision.as_dict()
            if not taken:
                avoid = collision.hint
                print(f"  ↻ {index:3d}  {got['family']:22s} phôi điền ra trùng "
                      f"bố cục phôi {collision.against} "
                      f"(J={collision.jaccard:.2f}) -- xin lại", flush=True)
                with lock:
                    discarded.append({"index": index, "attempt": attempt,
                                      "family": got["family"],
                                      "seconds": got.get("seconds", 0.0),
                                      "tokens_in": got.get("tokens_in", 0),
                                      "tokens_out": got.get("tokens_out", 0),
                                      "jaccard": round(collision.jaccard, 4)})
                continue
            break
        with lock:
            if got.get("doc_kind"):
                kinds_made.append(got["doc_kind"])
        return got

    with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(work, i): i for i in range(want)}
        for future in cf.as_completed(futures):
            index = futures[future]
            try:
                got = future.result()
            except Exception as error:                      # noqa: BLE001
                got = broken(index, error)
            made.append(got)
            mark = "✓" if got["ok"] else "✗"
            note = "" if got["ok"] else f"  {got['why'][0][:70]}"
            cost = (f"  {got['tokens_out']}tk" if got.get("tokens_out") else "")
            print(f"  {mark} {len(made):3d}/{want}  {got['family']:22s} "
                  f"{got['seconds']:5.1f}s{cost}  {len(got.get('paths') or [])} "
                  f"chỗ trống{note}", flush=True)
            stem = f"tpl_{got['family']}_{got['index']:04d}"
            template = got.get("template")
            if template is not None:
                folder = "templates" if got["ok"] else "rejected"
                payload = template.as_dict()
                payload.update({"ok": got["ok"], "why": got["why"],
                                "slots": got.get("slots") or [],
                                "paths": got.get("paths") or [],
                                "repeats": got.get("repeats") or []})
                (out / folder / f"{stem}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
            # TỜ ĐIỀN THỬ giữ lại: nó là thứ duy nhất đọc được bằng mắt để
            # biết phôi này in ra cái gì, và khi một phôi trượt ở lớp 3 thì
            # lý do nằm trên tờ ấy chứ không nằm trong phôi.
            for i, page in enumerate(got.get("smoke_html") or []):
                (out / "smoke" / f"{stem}_{i}.html").write_text(
                    page, encoding="utf-8")
            if artist is not None and (got.get("smoke_html") or [""])[0]:
                artist.put(out / "smoke" / f"{stem}_0.html", got["ok"])

    spent = time.time() - started
    if artist is not None:
        artist.close()
        if artist.why:
            print(f"[phôi] thợ vẽ hỏng: {artist.why}")

    kept = [m for m in made if m["ok"]]
    div = warden.metrics(pages=len(kept))
    report = {
        "when": _dt.datetime.now().isoformat(timespec="seconds"),
        "url": client.url, "model": client.model, "lang": lang,
        "asked": want, "kept": len(kept), "concurrency": concurrency,
        "seconds": round(spent, 1),
        "seconds_per_template": round(spent / want, 1) if want else 0.0,
        "tokens_in": sum(m.get("tokens_in", 0) for m in made + discarded),
        "tokens_out": sum(m.get("tokens_out", 0) for m in made + discarded),
        "median_chars": _median([m.get("chars", 0) for m in kept]),
        "slots_per_template": _median([len(m.get("paths") or []) for m in kept]),
        # PHÔI KHÔNG CÓ KHỐI LẶP -- con số quan trọng nhất của lô này sau tỉ
        # lệ đạt. Đo trên 18 phôi (`tools/llm/template_yield.py`): phôi không
        # khối lặp chỉ ra 2-7 bố cục khác nhau dù điền 16 lần, phôi có khối
        # lặp ra 11-14. Không GÁC (một giấy báo một trang là giấy thật), chỉ
        # đếm -- `synthgen/run_fill.py::budget()` hạ hạn mức của chúng.
        "templates_without_repeat": sum(1 for m in kept if not m.get("repeats")),
        "paths_used": sorted({p for m in kept for p in (m.get("paths") or [])}),
        "path_coverage": round(
            len({p for m in kept for p in (m.get("paths") or [])})
            / max(1, len(FT.closed_enum(FT.PATH))), 4),
        "timed_out": sum(1 for m in made if m.get("timed_out")),
        "failure_codes": failures.tally(
            [w for m in made if not m["ok"] for w in m["why"]]),
        "why_tally": _why_tally(made),
        "diversity": div,
        "discarded": discarded,
    }
    (out / "template_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"\n[phôi] {len(kept)}/{want} qua cổng trong {spent:.0f}s  ·  "
          f"{report['tokens_out']} token ra  ·  "
          f"phủ {report['path_coverage']:.0%} sổ đường dẫn")
    print(f"[phôi] phôi đã ghi vào {out / 'templates'}")
    if kept:
        print(f"[phôi] điền chúng bằng:\n"
              f"  python -m synthgen.run_fill {out} --per-template 50")
    return 0 if kept else 1


def _median(values) -> float:
    rows = sorted(v for v in values if v)
    if not rows:
        return 0.0
    mid = len(rows) // 2
    return float(rows[mid] if len(rows) % 2 else (rows[mid - 1] + rows[mid]) / 2)


def _why_tally(made: list[dict]) -> dict:
    out: dict = {}
    for row in made:
        for why in row.get("why") or ():
            head = why.split(";")[0][:70]
            out[head] = out.get(head, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--want", type=int, default=12,
                        help="số phôi (mặc định 12)")
    parser.add_argument("-o", "--out", default="data/phoi",
                        help="thư mục ra")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--no-draw", action="store_true",
                        help="không mở trình duyệt; bỏ tầng gác hình học")
    parser.add_argument("--no-diversity", action="store_true",
                        help="ĐO nhưng không loại phôi trùng (nhánh đối chứng)")
    parser.add_argument("--no-steer", action="store_true",
                        help="rút plan không trí nhớ (nhánh đối chứng)")
    parser.add_argument("--window", type=int, default=GD.WINDOW)
    parser.add_argument("--ceiling", type=float, default=GD.JACCARD_CEILING)
    parser.add_argument("--attempts", type=int, default=DIV.MAX_ATTEMPTS)
    args = parser.parse_args()
    return run(args.want, Path(args.out), concurrency=args.concurrency,
               seed=args.seed, lang=args.lang, no_draw=args.no_draw,
               diversity=not args.no_diversity, steer=not args.no_steer,
               window=args.window, ceiling=args.ceiling,
               attempts=args.attempts)


if __name__ == "__main__":
    raise SystemExit(main())
