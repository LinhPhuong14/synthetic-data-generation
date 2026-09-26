#!/usr/bin/env python3
"""Xin model soạn MỘT TỜ GIẤY: nội dung và HTML vẽ ra nó.

    python -m agent.compose_page --want 30 -o data/pilot-llm
    python -m agent.compose_page --want 30 -o data/pilot-llm --concurrency 4

Đây là bước sinh của phép thử "LLM tự vẽ bố cục". Nó KHÔNG vẽ ảnh: nó viết ra
những cặp `<stem>.html` + `<stem>.json` đã qua cổng, để `synthgen` vẽ chúng
bằng đúng Chromium và đúng phép đo đang dùng cho mọi trang khác.

## Vì sao tách làm hai bước

Hộp vẫn đến từ engine đã dàn chữ -- luật ấy không đổi khi model viết HTML. Thứ
đổi là ai hứa trang ấy ĐO ĐƯỢC, và câu trả lời là `synthgen/llm_page.py`: một
cổng chín luật, đo được cả hai chiều (60/60 trang engine viết qua, chín cách
trang hỏng đều bị bắt).

Nên model chạy ở đây, ra file, cổng gác, rồi mới tới lượt vẽ. Trang nào trượt
thì in lý do và bỏ -- không sửa hộ, vì một cái cổng biết vá là một cái cổng cho
qua thứ nó vừa vá.

## Bốn con số phép thử này phải trả lời

1. **Số học sai bao nhiêu.** Model tự viết `qty`, `unit_price`, `amount`; ở đây
   đếm số dòng mà `qty x unit_price != amount`. Đây là con số quyết định model
   có được cầm những con số hay không -- `synthgen/check.py` kiểm đúng phép ấy
   trên mọi tờ giấy của kho.
2. **Giây mỗi trang.** Đo được: một request 3 000 token mất 44 giây trên
   `Qwen3.8-27B-FP8`. Nhân 20 000 là 244 giờ đơn luồng, nên `--concurrency`
   có mặt từ đầu.
3. **Bao nhiêu trang qua cổng.**
4. **Đa dạng so với engine.** Đo ở bước sau, bằng `agent/distance.py` và phân
   bố nhãn bố cục.

## Chống trùng: hai tầng, và tầng thứ hai đọc PIXEL

Từ 24-09, mỗi tờ đi qua hai phép so trước khi được nhận:

1. **Plan** -- `agent/diversity.py` rút plan qua `sample_with_coverage`
   (`agent/coverage.py`) trên một trí nhớ dùng chung cả lô, nên tổ hợp đã
   bão hoà thì ít được rút lại. Miễn phí: chưa gọi model.
2. **Hình học** -- tờ đã viết được dàn ra để ĐO (`Artist.measure`), lấy
   `layout_annotations` thật, băm thành lưới 8x12 rồi so Jaccard với 24 tờ
   gần nhất. Trùng thì SINH LẠI kèm câu nhắc nói rõ khối nào đang ngồi đúng
   chỗ khối cũ.

Tầng hai có mặt vì tầng một mù với đúng thứ nó phải bắt: ba cặp tờ giống
nhau nhất trong `data/pilot16`+`pilot17` đều được `agent/document_distance.py`
chấm **1.000 -- khác nhau tối đa**, vì chúng thuộc ba family khác nhau.
Bảng số ở `agent/geometry_distance.py`.

## Cái này không tự sửa

Nội dung có thật hay không. Một hoá đơn của "Công ty TNHH Mặt Trời Mọc" là hợp
lệ và có thể chẳng tồn tại; cổng máy bắt cái đo được, người đọc diff bắt phần
còn lại. Cùng giới hạn `agent/corpus_rules.py` đã viết ra cho corpus.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import json
import os
import queue
import random
import re
import sys
import threading
import time
import unicodedata
from pathlib import Path

if __package__ in (None, ""):                   # `python compose_page.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.client import LLMError, from_env
from agent.promptbook import prompt
from agent import diversity as DIV
from agent import document_plan as DP
from agent import geometry_distance as GD
from agent import grammar as G
from agent import rate_match
from agent.fingerprint import geometry_fingerprint
from pipeline import failures
from synthgen import design as D
from synthgen import field_tier as FT
from synthgen.adorn import hands, seals
from synthgen.llm_page import (
    REGIONS,
    acceptable_kind,
    declared_paths,
    kinds,
    orphan_share,
    printed_kinds,
    problems,
)
from synthgen.repair import repair, rows_out

PROMPT = "page"
GUIDELINE_DIR = Path(__file__).resolve().parent / "guideline"


def base_rules() -> str:
    """The base-rules layer that used to sit unused in `agent/guideline/`.

    `agent/guideline.py::write()` composes `SYSTEM_PROMPT.md` from
    `agent/policy.yaml` for a DIFFERENT track (the one that picks rulebase
    attribute IDs, `agent/planner.py`) and nobody ever sent it here -- this
    call went straight to `prompt("page")` and nothing else. The role,
    diversity/balancing philosophy, and known-failure-pattern sections of
    that file apply just as much to a model that writes the whole page
    itself, so it belongs in this track's system turn too.

    Read fresh on every call, same as `prompt()` above: a hand edit or a
    `tools/critic_review.py --guideline` regeneration takes effect on the
    next request, no restart. Missing file is not fatal -- an empty string
    just leaves `system_prompt()` to fall back to `page.md` alone."""
    path = GUIDELINE_DIR / "SYSTEM_PROMPT.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


# Chỗ trong `page.md` nơi bảng nhãn vùng được dán vào.
REGION_SLOT = "{{REGION_TABLE}}"


def region_table() -> str:
    """Mọi nhãn `data-region` hợp lệ, kèm thẻ HTML đã ngầm khai nhãn ấy.

    ## Vì sao sinh chứ không chép

    Mục 14 của `page.md` từng liệt kê tay mười lăm nhãn. Đo lúc thay: một
    trong số ấy là `TOC`, thứ KHÔNG có trong bảng nhãn thật -- tên đúng là
    `Table-Of-Contents` -- nên model nào nghe theo lời dặn thì bị chính cổng
    gác của kho loại cả trang. Sáu nhãn hợp lệ thì không được nhắc tên:
    `Code-Block`, `Complex-Block`, `Diagram`, `Image`, `Page-Footer`,
    `Table-Of-Contents`.

    ## Vì sao kèm cột thẻ

    Một model viết `<ul>` là đã nói "đây là một danh sách" -- `pipeline/
    tags.py` đọc đúng điều ấy và `synthgen/repair.py::zoned()` biến nó thành
    `data-region` thật, nên không phải đòi model khai thêm lần nữa. Nói ra
    cột ấy rẻ hơn nhiều so với việc model học thuộc hai mươi cái tên trừu
    tượng, và nó đẩy trang về phía HTML ngữ nghĩa -- thứ đo được: 337 trên
    926 run mồ côi (36%) vá được chỉ nhờ tổ tiên là thẻ ngữ nghĩa."""
    from pipeline.tags import MEASURED_ELSEWHERE, region_by_tag  # noqa: PLC0415

    tags: dict[str, list[str]] = {}
    for tag, label in region_by_tag().items():
        tags.setdefault(label, []).append(f"`<{tag}>`")
    rows = ["| region label | write it as |", "| --- | --- |"]
    for label in REGIONS:
        # Nhãn do phép đo khác sinh ra thì cách viết cũng khác -- xem
        # `MEASURED_ELSEWHERE`. Nói `<div data-region="Table">` ở đây là dạy
        # model đếm cái bảng hai lần.
        if label in MEASURED_ELSEWHERE:
            rows.append(f"| {label} | {MEASURED_ELSEWHERE[label]} |")
            continue
        how = ", ".join(tags.get(label, []))
        fallback = f'`<div data-region="{label}">`'
        rows.append(f"| {label} | {how + ', or ' + fallback if how else fallback} |")
    return "\n".join(rows)


def system_prompt() -> str:
    """What actually goes in the system turn.

    Two files answer two different questions, so both go in, base rules
    first: `SYSTEM_PROMPT.md` says WHY the corpus should end up varied and
    realistic (role, diversity, balancing, failure patterns); `page.md` says
    HOW to draw one sheet (data tree, data-kind/data-path, tables, KIE,
    hard negatives, HTML mechanics). Concatenating roughly doubles the
    system-prompt token cost of every call -- worth watching against
    `budget()`/`patience()` if per-page latency regresses once this runs at
    scale."""
    base = base_rules()
    page = prompt(PROMPT)
    # BẢNG NHÃN DÁN VÀO, KHÔNG PHẢI CHÉP TAY. Thiếu chỗ dán thì HỎNG TO
    # chứ không đi tiếp: một prompt không có bảng nhãn là một prompt bảo
    # model tự nhớ hai mươi cái tên, và trang nó viết sau đó sai ở chỗ
    # không ai ngờ -- đúng ca `TOC` đã đo được.
    if REGION_SLOT not in page:
        raise LLMError(f"{PROMPT}.md không còn chỗ dán {REGION_SLOT!r}; "
                       "bảng nhãn vùng sẽ không tới model")
    page = page.replace(REGION_SLOT, region_table())
    return f"{base}\n\n---\n\n{page}" if base else page


def kind_pattern() -> str:
    """Ngữ pháp `field_plan[].kind` cho BỘ GIẢI MÃ -- cùng một luật với cổng.

    ## Vì sao `pattern` chứ không `enum`

    `enum` khiến bộ giải mã có ràng buộc KHÔNG THỂ sinh tên ngoài danh sách.
    Chặt hơn cổng, và chặt SAI CHỖ: cổng (`synthgen/llm_page.py`) cho model
    ĐẶT TÊN MỚI miễn theo ngữ pháp `họ.trường[.nhãn]` -- xem `_COINED` ở đó.
    Với `enum`, model viết một loại giấy engine chưa từng vẽ thì nó không khai
    nổi trường mới vào kế hoạch, dù HTML (một `string` tự do) vẫn in ra được.

    ## Vì sao HAI VẾ

    Cổng nhận một tên khi: nó CÓ trong từ vựng, hoặc tiền tố của nó là một
    kind thật (`_rooted`), hoặc nó theo ngữ pháp đặt tên mới. Vế đầu không suy
    ra từ vế sau -- `title` và `note` là kind THẬT mà chỉ có một đoạn, nên
    ngữ pháp đặt tên mới (2-4 đoạn) loại chúng.

    Hai chỗ ép một luật, và lệch nhau thì model sinh được cái tên mà cổng ngay
    sau đó loại -- đốt trọn một lượt gọi để bị từ chối. `tests/test_llm_page.
    py::test_the_gate_and_the_decoder_agree_on_what_a_name_may_look_like` so
    từng tên qua cả hai đường và đòi chúng trả lời giống nhau."""
    literal = "|".join(re.escape(k) for k in sorted(kinds()))
    return f"^(?:{literal}|{_coined_pattern()})$"


def _coined_pattern() -> str:
    """Nửa ĐẶT TÊN MỚI của `kind_pattern()`, tách ra để `schema()` dùng lại.

    `schema()` viết hai nhánh ra rõ (`enum` khoá đã duyệt, cạnh ngữ pháp này)
    thay vì dán nguyên chuỗi gộp. Cùng một ngôn ngữ, nhưng hai nơi phải lấy
    vế `_COINED` từ đúng một chỗ -- chép nó lần thứ hai là mời hai nhánh lệch
    nhau, đúng lỗi "một luật, nhiều người dựng" mà `acceptable_kind()` sinh ra
    để dọn."""
    from synthgen.llm_page import _COINED  # noqa: PLC0415

    return _COINED.pattern.lstrip("^").rstrip("$")


def _close(node):
    """Đóng mọi object trong schema: `additionalProperties: false` và
    `required` liệt kê ĐỦ mọi khoá. Sửa tại chỗ, trả lại chính nó.

    Đây là điều kiện `agent/client.py::closed()` kiểm và OpenAI Structured
    Outputs đòi. Sinh ra bằng phép đi cây chứ không viết tay vào từng nhánh:
    schema này có mười hai object lồng nhau, và một nhánh quên đóng thì
    `closed()` trả `False` cho CẢ schema -- ép tắt lặng lẽ, và ta quay lại
    đúng 812 token không có `html`.

    `required` đủ mọi khoá là luật của OpenAI, không phải lựa chọn: trường
    nào thật sự tuỳ chọn thì để model trả chuỗi rỗng / mảng rỗng, chứ không
    để nó vắng mặt."""
    if not isinstance(node, dict):
        return node
    if node.get("type") == "object":
        props = node.get("properties")
        if isinstance(props, dict) and props:
            node["additionalProperties"] = False
            node["required"] = list(props)
            for value in props.values():
                _close(value)
    elif node.get("type") == "array":
        _close(node.get("items") or {})
    return node


# Cây nội dung, PHẲNG -- `[{path, value}]`, không phải object tự do.
#
# Vì sao đổi hình: một object không khai `properties` là schema MỞ, và schema
# mở thì `strict: true` bị OpenAI từ chối. Không ép thì đo được ngay
# (23-09-2026, `gpt-4.1-mini`): 812 token, không `data`, không `rows`, không
# `html` -- model trả các khoá con của `plan` ở mức gốc rồi dừng.
#
# Phẳng KHÔNG mất gì: `data-path` in trên giấy vốn đã là một chuỗi phẳng
# (`issuer.tax_code`, `line_items[0].name`), và `data_path_mismatches` so đúng
# chuỗi ấy. Cây lồng phải đi từng đoạn mới tra được cùng một thứ.
def _catchall_advice() -> str:
    """Lời khuyên về khoá HỨNG CHUNG, dựng từ `rulebase/field_tiers.json`.

    Viết cứng danh sách lá vào đây là dựng người thứ hai cho một luật: ai
    thêm một lá vào chính sách sẽ sửa một chỗ và quên chỗ này, rồi tuần sau
    không hiểu vì sao model không bao giờ viết lá mới ấy. Đọc thẳng từ
    `field_tier.candidate_leaves` thì lá mới có mặt trong lời dặn ngay.

    Vì sao cần lời dặn này: cơ chế nhận lá đã chạy từ Task 3 -- `meta.doc_date`
    kèm một câu tả rơi thẳng vào `semi_open`, `in_batch: True`, không cần một
    dòng mã nào thêm. Nhưng đo trên toàn bộ `data/*/declared` (24-09-2026):
    `meta.value` 914 lượt và các lá ấy ĐÚNG 0 lượt. Model không viết chúng vì
    chưa ai nói chúng đáng viết, và `meta.value` thì nằm ngay trong `enum`."""
    lines = []
    for key in sorted(set(FT.registry().generic[FT.KIND])):
        leaves = FT.candidate_leaves(key)
        if leaves:
            lines.append(f"`{key}` -> " + ", ".join(f"`{x}`" for x in leaves))
    if not lines:
        return ""
    return ("\n**Catch-all keys are a last resort.** These keys are listed, so "
            "they are accepted, but they name nothing: one authorisation "
            "letter was measured carrying `meta.value` five times for five "
            "different things (document number, document date, signing place, "
            "validity start, validity end). When you know which one it is, "
            "coin the leaf instead -- it is route (2) above, it needs only "
            "your one sentence, and it is NOT rejected:\n"
            + "\n".join(lines))


DATA_ITEMS = {
    "type": "array",
    "description": "Every value printed on the sheet, keyed by the exact "
                   "data-path written in the HTML.",
    "items": {
        "type": "object",
        "properties": {
            # HỌ ĐÃ DUYỆT, nói thẳng trong schema.
            #
            # `path` không ép được bằng `enum` như `kind`: một đường dẫn mang
            # chỉ số (`line_items[7].name`) nên tập của nó vô hạn. Nhưng HỌ
            # thì hữu hạn, và nói ra chúng ở đây là chỗ rẻ nhất -- đo trên
            # 12 318 lượt `data-path` của 394 tệp `declared/`: 377 họ khác
            # nhau cho chừng ấy khái niệm mà 25 họ `data-kind` đã gọi tên
            # xong. Riêng `items[]` 3 033 lượt là cách viết khác của
            # `line_items[]` (2 038 lượt) -- cùng một cái bảng hàng, hai tên.
            "path": {
                "type": "string",
                "description": (
                    "Same string as the data-path attribute. Prefer a listed "
                    "family: " + ", ".join(sorted(
                        FT.registry().families[FT.PATH])) + ". A path outside "
                    "them is kept for review and left out of the training "
                    "set; never spell a listed family a second way."),
            },
            "value": {"type": "string",
                      "description": "Exactly the text the HTML prints."},
            # CÂU TẢ ĐI CẠNH `path`, KHÔNG CẠNH `kind`.
            #
            # `field_plan[].describe` đã có từ Task 3, nhưng nó không nối
            # được về ô mực nào. Đo trên `data/pilot17` (42 tờ, 966 trường),
            # bốn cách nối `field_plan` với cặp KIE:
            #
            #     `kind` + bội số hai bên bằng nhau   61,3%  (còn phải đoán thứ tự)
            #     `label` == `key_text`               12,0%
            #     `slug(label)` == `field`             5,0%
            #     `label` == `path`                    4,8%
            #
            # `label` hoá ra phần lớn là CHỮ IN trên giấy ("Mã số thuế"),
            # không phải tên trường. Nối theo bội số rồi khớp theo thứ tự là
            # đúng một nửa cho cặp bên uỷ quyền / bên được uỷ quyền -- đúng
            # lỗi kép mà `synthgen/field_tier.py` từ chối phép "khoá gần
            # nhất" để tránh.
            #
            # `path` thì nối 1-1 theo cấu tạo: nó LÀ `data-path` trên span,
            # và `pipeline/record.py` đọc hộp từ chính span ấy. Hai
            # `store.tax_code` của một giấy uỷ quyền mang hai path khác nhau
            # (`issuer.tax_code`, `auth.seller_tax`), nên câu tả đi cạnh path
            # là câu tả đi cạnh đúng ô mực, không qua một phép đoán nào.
            "describe": {
                "type": "string",
                "description": (
                    "One short sentence saying what THIS value is, in this "
                    "document. It sits beside the registry's own sentence "
                    "for the field's kind, so do not restate that: say what "
                    "distinguishes this occurrence -- whose value, which "
                    "party, which date. Two fields on one page can share a "
                    "kind, and this sentence is the only thing that tells "
                    "them apart. Do not copy the printed caption."),
            },
        },
        "required": ["path", "value", "describe"],
        "additionalProperties": False,
    },
}


def schema() -> dict:
    """Hình dạng câu trả lời. vLLM ép theo nó bằng constrained decoding.

    ## `plan` KHÔNG còn là nơi model quyết cấu trúc -- đó là việc của engine

    Bản trước-trước đưa model một phôi đã khai sẵn: trường nào, ai ký, ghi
    chú gì. Model chỉ còn việc bày chúng ra. Kết quả là ba mươi tờ đi ra từ
    cùng một khuôn -- đúng thứ kiến trúc "N phôi" mà người dùng đã bác.

    Bản kế (trước Phase 5) để model tự quyết HOÀN TOÀN, và `plan` bắt nó
    nói quyết định ấy ra trước khi viết HTML. Đúng hướng ở chỗ model không
    còn điền vào khuôn cố định -- nhưng sai ở chỗ "quyết định" đó không ai
    kiểm, nên không khác gì model tự tạo ra plan RỒI TỰ CHẤM cho chính nó.

    Phase 5 (`docs/ke-hoach-refactor-engine.md`, điểm 3 review): cấu trúc
    -- có bảng hay không, mấy chữ ký, family nào -- giờ do
    `agent/grammar.py` + `agent/document_plan.py` RÚT TRƯỚC, đưa vào brief
    qua `describe_plan()`. `plan` trong JSON trả về đây vẫn giữ (protocol
    ổn định, `reasoning` vẫn hữu ích để gỡ lỗi), nhưng đổi vai trò thành
    **tóm tắt việc model đã làm**, không phải nguồn quyết cấu trúc --
    `agent/compose_page.py::plan_conformance_problems()` so HTML với
    `DocumentPlan` của ENGINE, không so với `plan` model tự khai ở đây.

    `field_plan` vẫn buộc model ÁNH XẠ trường nó viết sang `data-kind` có
    thật trong từ vựng đóng -- đây là chỗ nó hỏng nhiều nhất khi còn được
    hỏi (sáu tờ trượt vì `patient.name`, `project.code`, `admission.date`:
    tên model tự đặt cho trường mà nó chưa bao giờ phải đối chiếu với danh
    sách), và việc đó không đổi dù cấu trúc trang không còn do model quyết.
    """
    return _close({
        "type": "object",
        "properties": {
            "plan": {
                "type": "object",
                "properties": {
                    "doc_kind": {"type": "string"},
                    # TÊN FILE, do model tự đặt, bằng tiếng Anh ASCII.
                    #
                    # Trước đây tên thư mục chuyển ngữ từ `doc_kind` tiếng
                    # Việt, và mỗi bước chuyển ngữ là một chỗ hỏng: `đ` bị
                    # xoá ("hoạt động" -> `hoat_ong`), dấu gạch chéo cắt
                    # đường dẫn làm đôi, và khi lời dặn bằng tiếng Anh thì
                    # model trả về lẫn lộn -- khi thì câu tiếng Việt, khi thì
                    # một slug nó tự bịa, khi thì bảy mươi ký tự có ngoặc.
                    #
                    # `pattern` khiến bộ giải mã có ràng buộc KHÔNG THỂ sinh
                    # ra thứ khác. Tên file thôi là thứ phải đoán.
                    "doc_slug": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]{2,47}$",
                        # TIẾNG ANH. `pattern` ép được hình dạng nhưng không ép
                        # được ngôn ngữ, và pilot9 cho thấy chênh lệch: model
                        # chuyển ngữ tiếng Việt không dấu rồi nuốt chữ --
                        # `phiexacnhansohuyentranduy`,
                        # `biau_phan_loai_quan_ly_chung_cu`,
                        # `ho_so_hanh_hang`. Tên file thành thứ không đọc
                        # được, và hai tài liệu khác nhau dễ đụng tên.
                        #
                        # Tiếng Anh thì không có bước chuyển ngữ nào để hỏng.
                        # Nội dung TỜ GIẤY vẫn tiếng Việt -- `doc_kind` giữ
                        # tên tiếng Việt, cái này chỉ là tên thư mục.
                        "description": "ENGLISH snake_case document type, "
                                       "e.g. vat_declaration, tuition_notice, "
                                       "warehouse_issue_note. Never Vietnamese.",
                    },
                    "doc_title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "issuer": {"type": "string"},
                    "signers": {"type": "array", "items": {"type": "string"}},
                    "field_plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                # ENUM, không phải `string`. Đây là khác biệt
                                # lớn nhất giữa xin và ép.
                                #
                                # Lời dặn "đừng tự đặt tên mới" là một lời
                                # xin, và pilot5 cho thấy nó không đủ: model
                                # viết `seal.round` vì prompt bảo thế, viết
                                # `patient.name` vì nó hợp lý. Cả hai đều đi
                                # qua `{"type": "string"}` không vướng gì, rồi
                                # chết ở cổng sau khi đã đốt 300 giây.
                                #
                                # `pattern` thì bộ giải mã có ràng buộc vẫn
                                # KHÔNG THỂ sinh ra tên sai ngữ pháp -- vẫn là
                                # ép, không phải xin. Khác `enum` ở đúng một
                                # chỗ: nó cho ĐẶT TÊN MỚI theo ngữ pháp
                                # `họ.trường[.nhãn]`, y như cổng cho phép.
                                # Xem `kind_pattern()` về hai vế của nó.
                                #
                                # HAI NHÁNH VIẾT RÕ RA, thay cho một `pattern`
                                # gộp. Ngôn ngữ nhận được y hệt -- nhánh đầu
                                # là chính những chữ `kind_pattern()` vẫn nối
                                # bằng `|` -- nhưng bộ giải mã (và người đọc
                                # schema) giờ THẤY tầng `closed`: một `enum`
                                # tên khoá đã duyệt, cạnh cửa thoát đặt tên
                                # mới. `synthgen/field_tier.py` xếp tầng theo
                                # đúng danh sách ấy, nên nơi ép và nơi xếp
                                # đọc chung một sổ.
                                "kind": {
                                    "anyOf": [
                                        {"type": "string",
                                         "enum": list(FT.closed_enum(FT.KIND))},
                                        {"type": "string",
                                         "pattern": _coined_pattern()},
                                    ],
                                },
                                # CÂU TẢ, và nó là ĐIỀU KIỆN của tầng
                                # `semi_open`. Tên ngoài sổ mà không kèm câu
                                # tả thì `field_tier` đẩy xuống `staging` --
                                # nó KHÔNG mượn câu tả của khoá gần nhất, vì
                                # khoá sai cộng câu tả tra theo khoá sai là
                                # một lỗi kép mà bản ghi không tự kêu lên
                                # được.
                                #
                                # KHOÁ ĐÓNG CŨNG PHẢI CÓ CÂU TẢ. Bản trước
                                # dặn "để rỗng khi `kind` đã có trong sổ", và
                                # luật ấy đúng phần nó nói -- sổ không bị ghi
                                # đè -- nhưng nó bỏ trống đúng thứ phân biệt
                                # hai lần xuất hiện của một khoá trên MỘT tờ.
                                # Đo trên 785 tệp `data/*/declared`:
                                # `authorisation_letter/store.tax_code` 20
                                # lượt / 1 câu tả, `meta.value` 55 lượt / 1
                                # câu. Câu của sổ vẫn là câu của sổ; câu ở
                                # đây ghép vào sau nó (`field_tier.compose`).
                                "describe": {
                                    "type": "string",
                                    "description": "Never empty. When you coin "
                                                   "a new name, this sentence "
                                                   "IS its meaning. When `kind` "
                                                   "is a listed key, say which "
                                                   "occurrence THIS one is -- "
                                                   "whose value, which party, "
                                                   "which date -- because two "
                                                   "fields sharing a listed key "
                                                   "on one page are told apart "
                                                   "by nothing else. Do not "
                                                   "restate the registry "
                                                   "sentence and do not copy "
                                                   "the printed caption.",
                                },
                            },
                            "required": ["label", "kind", "describe"],
                        },
                    },
                    "table_columns": {"type": "array",
                                      "items": {"type": "string"}},
                    # MỘT MỤC CHO MỖI TỜ ĐƯỢC XIN.
                    #
                    # Đo trên pilot13: model viết 1 951 token cho mỗi tờ được
                    # xin -- đúng MỘT NỬA mức 3 900 lời dặn yêu cầu -- và
                    # 14/16 tài liệu ra ít tờ hơn xin. Càng xin nhiều càng
                    # hụt: xin hai tờ thì gần đủ, xin tám tờ thì được ba.
                    #
                    # Lời dặn đã nói "nhân lượng chữ theo số tờ" và model
                    # không nghe. Thứ từng ép được nó nghe là RÀNG BUỘC CẤU
                    # TRÚC, không phải câu chữ: `field_plan` bắt nó mở danh
                    # sách kind ra đối chiếu, `enum` chặn nó bịa tên.
                    #
                    # `sheet_plan` bắt nó nghĩ RIÊNG cho từng tờ trước khi
                    # viết. Một mảng đúng tám mục cho tám tờ là tám lần nó
                    # phải trả lời "tờ này in cái gì" -- khó bỏ trống hơn
                    # nhiều so với một câu dặn chung.
                    "sheet_plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet": {"type": "integer"},
                                "sections": {"type": "array",
                                             "items": {"type": "string"}},
                                "rows_here": {"type": "integer"},
                            },
                            "required": ["sheet", "sections"],
                        },
                    },
                    "layout_idea": {"type": "string"},
                    # TƯ DUY, viết ra thành lời.
                    #
                    # `layout_idea` nói model ĐỊNH làm gì. `reasoning` nói VÌ
                    # SAO -- và đó mới là thứ đọc được khi một tờ hỏng. Một tờ
                    # trượt cổng hiện chỉ để lại HTML và câu báo lỗi: ta thấy
                    # nó sai ở đâu, không thấy nó nghĩ gì mà ra sai.
                    #
                    # Ba câu hỏi, vì ba chỗ hay hỏng nhất đo được: chọn loại
                    # chứng từ (model bịa ra loại không có thật), ánh xạ kind
                    # (bịa tên kind), và bày trang (dồn mọi thứ vào `Text`).
                    "reasoning": {
                        "type": "object",
                        "properties": {
                            "why_this_document": {"type": "string"},
                            "why_this_layout": {"type": "string"},
                            "hardest_choice": {"type": "string"},
                        },
                        "required": ["why_this_document", "why_this_layout",
                                     "hardest_choice"],
                    },
                },
                "required": ["doc_kind", "doc_slug", "doc_title", "purpose",
                             "issuer", "signers", "field_plan", "layout_idea",
                             "reasoning", "sheet_plan"],
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "unit": {"type": "string"},
                        "qty": {"type": "integer"},
                        "unit_price": {"type": "integer"},
                        "amount": {"type": "integer"},
                    },
                    "required": ["name", "qty", "unit_price", "amount"],
                },
            },
            # CÂY DỮ LIỆU, viết TRƯỚC HTML.
            #
            # Đây là chỗ đảo kiến trúc. Bản trước: model viết HTML, rồi pipeline
            # SUY ra cặp nhãn-giá trị từ toạ độ -- và mọi lỗi KIE đo được hôm
            # nay nằm đúng ở phép suy ấy (`stt_r9` nhận "TỔNG CỘNG" vì ô trải
            # bốn cột bắt đầu ở cột STT; "Số: 12/BB-HĐSP" nhận ngày tháng ở góc
            # phải vì nó là run kế tiếp trong cây DOM). Đo được: 30% run mang
            # vai key không có tín hiệu cấu trúc nào tách chúng khỏi một dòng
            # đã trọn nghĩa -- tức phép suy KHÔNG THỂ đúng hết.
            #
            # Bộ `pair_prompt100` của người dùng làm ngược lại: `data/*.json`
            # là cây dữ liệu viết trước, HTML là khuôn mang điểm ràng buộc
            # `value-path-value="merchant.tax_id"` -- 96 điểm trên một tờ biên
            # lai. KIE không phải suy gì cả: đường dẫn nằm sẵn trên thẻ.
            #
            # Ta lấy đúng ý ấy, bớt một bước: model viết CẢ giá trị lẫn đường
            # dẫn vào cùng một span (`data-path="merchant.tax_id"`), nên không
            # cần bước bơm dữ liệu vào khuôn. Trang vẽ ra ngay, và KIE đọc
            # thẳng `data-path`.
            #
            # Không ép hình dạng cây: mỗi loại chứng từ có cây riêng, và ép nó
            # là quay lại lối phôi cố định. Chỉ ép rằng nó PHẢI CÓ.
            "data": DATA_ITEMS,
            "html": {"type": "string"},
        },
        "required": ["plan", "data", "rows", "html"],
    })


# MƯỜI HAI LĨNH VỰC, không phải chín mươi bảy phôi. Đây là chỗ duy nhất còn
# viết cứng, và nó viết cứng ở mức "giấy tờ Việt Nam có những ngành nào" chứ
# không ở mức "tờ giấy này có những trường nào" -- model tự nghĩ ra loại chứng
# từ trong ngành, tự quyết trường, người ký, ghi chú, cột.
#
# Vì sao vẫn cần lĩnh vực: bỏ trắng thì model viết hoá đơn ba mươi lần. Một
# lĩnh vực là cái đẩy nó ra khỏi chỗ quen, không phải cái khuôn nó phải điền.
DOMAINS = (
    ("y tế", "bệnh viện, phòng khám, trạm y tế, bảo hiểm y tế"),
    ("giáo dục", "trường học, trung tâm đào tạo, phòng giáo dục"),
    ("hành chính nhà nước", "uỷ ban, sở ngành, công an, toà án"),
    ("thuế và kế toán", "cơ quan thuế, phòng kế toán doanh nghiệp"),
    ("ngân hàng và tài chính", "ngân hàng, quỹ tín dụng, công ty chứng khoán"),
    ("bảo hiểm", "doanh nghiệp bảo hiểm nhân thọ và phi nhân thọ"),
    ("xây dựng", "ban quản lý dự án, nhà thầu, tư vấn giám sát"),
    ("vận tải và kho bãi", "hãng vận tải, kho hàng, cảng, chuyển phát"),
    ("thương mại và bán lẻ", "siêu thị, cửa hàng, nhà phân phối"),
    ("nhân sự và lao động", "phòng nhân sự, trung tâm giới thiệu việc làm"),
    ("nhà đất", "sàn bất động sản, ban quản lý toà nhà, văn phòng đăng ký đất đai"),
    ("báo chí và xuất bản", "toà soạn báo, tạp chí, nhà xuất bản"),
)

# BA BẢN NGÔN NGỮ CHO CÙNG MỘT LUẬT.
#
# Server chạy Qwen, và Qwen được tinh chỉnh theo lệnh mạnh nhất ở tiếng Anh và
# tiếng Trung. Prompt tiếng Việt có thể đang bắt nó làm việc ở chỗ nó yếu nhất
# -- nhưng "có thể" không phải là kết luận, nên ba bản cùng tồn tại và `--lang`
# chọn bản nào. Nội dung tờ giấy thì LUÔN là tiếng Việt: ngôn ngữ của lời dặn
# và ngôn ngữ của sản phẩm là hai chuyện khác nhau, và cả ba bản đều nói rõ
# điều ấy ngay đầu file.
#
# Token nạp: ĐO ĐƯỢC cho `zh` là 3 633 mỗi lời gọi (pilot7, server tự báo
# trong `usage.prompt_tokens`, tức tokenizer thật của Qwen). `vi` và `en` chưa
# có lượt nào kịp ghi báo cáo nên chưa đo -- và ước lượng cũ của tôi ở đây
# (zh ~2 485) lệch 32% so với số thật, nên đừng dùng ước lượng ký-tự-chia-N
# thay cho `usage`: tokenizer của Qwen không chia đều theo ký tự, nhất là với
# tiếng Việt có dấu.
PROMPT_OF = {"en": "page"}

# Tên lĩnh vực dịch sang hai thứ tiếng kia. Để nguyên tiếng Việt trong một
# prompt tiếng Anh thì model phải chuyển ngữ trước khi nghĩ -- thêm một bước
# không ai cần, và đúng cái bước mà bản tiếng Anh sinh ra để bỏ đi.
DOMAINS_EN = (
    ("healthcare", "hospitals, clinics, health stations, health insurance"),
    ("education", "schools, training centres, education departments"),
    ("public administration", "people's committees, departments, police, courts"),
    ("tax and accounting", "tax offices, corporate accounting departments"),
    ("banking and finance", "banks, credit funds, securities firms"),
    ("insurance", "life and non-life insurers"),
    ("construction", "project management boards, contractors, supervision consultants"),
    ("transport and warehousing", "carriers, warehouses, ports, courier firms"),
    ("trade and retail", "supermarkets, shops, distributors"),
    ("human resources and labour", "HR departments, employment service centres"),
    ("property", "real-estate agencies, building management, land registries"),
    ("press and publishing", "newspaper and magazine offices, publishers"),
)
DOMAINS_ZH = (
    ("医疗", "医院、诊所、卫生站、医疗保险"),
    ("教育", "学校、培训中心、教育局"),
    ("国家行政", "人民委员会、各厅局、公安、法院"),
    ("税务与会计", "税务机关、企业会计部门"),
    ("银行与金融", "银行、信用基金、证券公司"),
    ("保险", "寿险与非寿险公司"),
    ("建筑", "项目管理委员会、承包商、监理顾问"),
    ("运输与仓储", "运输公司、仓库、港口、快递"),
    ("贸易与零售", "超市、商店、经销商"),
    ("人事与劳动", "人事部门、就业服务中心"),
    ("房地产", "房产交易中心、楼宇管理处、土地登记处"),
    ("新闻与出版", "报社、杂志社、出版社"),
)
DOMAINS_OF = {"en": DOMAINS_EN}

# Cầu nối giữa hai từ vựng độc lập: mười hai lĩnh vực ở trên, và tên phôi trong
# `rulebase/synthgen/`. Không có trường nào trong phôi nói nó thuộc lĩnh vực
# nào -- `profile` quá thô (44 trên 97 phôi là `admin`), nên khớp bằng gốc từ
# trong CHÍNH cái `id`.
#
# Vì sao cần: `inspiration()` quay theo `index`, `ask_for` quay lĩnh vực cũng
# theo `index`, nhưng hai chu kỳ khác nhau -- nên một tờ "thuế và kế toán"
# nhận ba phôi y tế (`don_thuoc`, `giay_chuyen_tuyen`, `the_bhyt`). Model phải
# tự bắc cầu, và nó bắc sai: pilot9 có tờ thuế in ra khối chẩn đoán.
#
# Gốc từ chứ không phải tên đầy đủ, nên phôi mới thêm vào tự rơi đúng nhóm mà
# không ai phải sửa bảng này.
DOMAIN_STEMS = {
    0: ("benh", "vien_phi", "kham", "thuoc", "bhyt", "y_te", "suc_khoe", "dieu_tri"),
    1: ("hoc", "sinh_vien", "dao_tao", "diem", "truong", "tot_nghiep", "giao_duc"),
    2: ("cong_van", "quyet_dinh", "to_trinh", "giay_moi", "don_", "xac_nhan",
        "bien_ban", "uy_quyen", "cong_chung", "ho_khau", "khai_sinh"),
    3: ("thue", "gtgt", "tncn", "tndn", "hoa_don", "quyet_toan", "so_sach",
        "ke_toan", "phieu_thu", "phieu_chi", "bang_can_doi"),
    4: ("ngan_hang", "tin_dung", "tai_khoan", "sao_ke", "vay", "chuyen_tien",
        "the_atm", "chung_khoan", "lai_suat"),
    5: ("bao_hiem", "bhxh", "boi_thuong", "quyen_loi", "giam_dinh", "hop_dong_bh"),
    6: ("xay_dung", "nghiem_thu", "thi_cong", "cong_trinh", "khoi_luong",
        "du_toan", "giam_sat", "vat_tu"),
    7: ("van_don", "van_chuyen", "kho", "xuat_kho", "nhap_kho", "giao_nhan",
        "logistics", "cang", "container"),
    8: ("ban_le", "sieu_thi", "don_hang", "bao_gia", "menu", "hang_hoa",
        "khuyen_mai", "bakery", "shop"),
    9: ("luong", "nhan_su", "lao_dong", "cham_cong", "tuyen_dung", "nghi_viec",
        "danh_gia_nhan_su", "bang_luong"),
    10: ("nha", "dat", "can_ho", "chung_cu", "thue_nha", "bat_dong_san",
         "ban_giao_can_ho", "toa_nha"),
    11: ("bao", "tap_chi", "xuat_ban", "ban_thao", "in_an", "phat_hanh",
         "ban_quyen", "toa_soan"),
}

# TÊN THẬT tiếng Việt cho 30 family của `agent/grammar.py` (Phase 3-4,
# `docs/ke-hoach-refactor-engine.md`). Model không còn cần đoán tên chứng từ
# từ một lĩnh vực rồi tự bịa `doc_slug` -- family ĐÃ LÀ một slug snake_case
# hợp lệ (`one()` gán thẳng `doc_slug = plan.family`, không hỏi model), và
# gợi ý ở đây chỉ để model biết gọi gì bằng tiếng Việt (`doc_kind`) và viết
# nội dung gì cho đúng loại giấy tờ. Một câu ngắn, không phải định nghĩa đầy
# đủ -- phần "loại giấy tờ này thật sự trông ra sao" là việc của
# `agent/grammar.py`, không phải việc lặp lại ở đây.
FAMILY_HINT = {
    "authorisation_letter": "giấy uỷ quyền",
    "cash_receipt_voucher": "phiếu thu/chi tiền mặt",
    "dispatch_letter": "công văn hoặc thông báo hành chính",
    "export_invoice": "hoá đơn xuất khẩu",
    "form_activity": "biên bản hoạt động có xác nhận chữ ký",
    "form_checklist": "phiếu kiểm tra dạng checklist",
    "form_dense": "phiếu đăng ký hoặc hồ sơ khai chi tiết",
    "form_roster": "bảng chấm công hoặc phân công theo lịch",
    "form_sectioned": "biểu mẫu nhiều mục có bảng dữ liệu",
    "form_symmetric": "biểu mẫu hai cột đối xứng",
    "handover_record": "biên bản bàn giao",
    "hospital_bill": "bảng kê chi phí khám chữa bệnh",
    "hotel_stay": "hoá đơn lưu trú khách sạn",
    "insurance_application_form": "giấy yêu cầu bảo hiểm",
    "insurance_auto_certificate": "giấy chứng nhận bảo hiểm ô tô",
    "insurance_cargo_policy": "đơn bảo hiểm hàng hoá",
    "insurance_fire_certificate": "giấy chứng nhận bảo hiểm cháy nổ",
    "insurance_health_certificate": "giấy chứng nhận bảo hiểm sức khoẻ",
    "insurance_health_id_card": "thẻ bảo hiểm y tế",
    "insurance_life_schedule": "bảng quyền lợi bảo hiểm nhân thọ",
    "insurance_moto_certificate": "giấy chứng nhận bảo hiểm xe máy",
    "insurance_property_contract": "hợp đồng bảo hiểm tài sản",
    "insurance_travel_certificate": "giấy chứng nhận bảo hiểm du lịch",
    "invoice_detailed": "hoá đơn bán hàng chi tiết",
    "leave_application": "đơn xin nghỉ phép",
    "meeting_minutes": "biên bản họp",
    "retail_vat_invoice": "hoá đơn bán lẻ có thuế GTGT",
    "tax_invoice_en": "hoá đơn thuế song ngữ Anh-Việt",
    "utility_power": "hoá đơn tiền điện",
    "utility_water": "hoá đơn tiền nước",
}


# FAMILY -> khoá của `DOMAIN_STEMS`, để `inspiration()` lọc phôi tham khảo
# đúng lĩnh vực của family đã chọn -- không phải theo `index % 12` như bản
# cũ. Hai chu kỳ khác độ dài (30 family, 12 domain) drift ra khỏi nhau nếu
# cứ lấy chung một `index`, đúng lớp lỗi mà chính comment ở `DOMAIN_STEMS`
# phía trên đã kể lại (pilot9: tờ thuế in khối chẩn đoán y tế). Ánh xạ
# tường minh ở đây tránh lặp lại đúng lỗi ấy dưới hình dạng khác.
FAMILY_DOMAIN = {
    "hospital_bill": 0, "insurance_health_certificate": 0,
    "insurance_health_id_card": 0,
    "form_dense": 1, "form_checklist": 1,
    "authorisation_letter": 2, "dispatch_letter": 2, "form_activity": 2,
    "form_sectioned": 2, "form_symmetric": 2, "handover_record": 2,
    "leave_application": 2, "meeting_minutes": 2,
    "cash_receipt_voucher": 3, "retail_vat_invoice": 3, "tax_invoice_en": 3,
    "invoice_detailed": 3, "export_invoice": 3,
    "insurance_application_form": 5, "insurance_auto_certificate": 5,
    "insurance_cargo_policy": 5, "insurance_fire_certificate": 5,
    "insurance_life_schedule": 5, "insurance_moto_certificate": 5,
    "insurance_property_contract": 5, "insurance_travel_certificate": 5,
    "form_roster": 9,
    "utility_power": 8, "utility_water": 8, "hotel_stay": 8,
}


def describe_plan(plan: DP.DocumentPlan) -> str:
    """`DocumentPlan` -> đoạn brief mô tả CẤU TRÚC engine đã quyết -- đây
    là chỗ mục 5.1 (Phase 5) thật sự đổi: model không còn được mời "tự
    nghĩ" cấu trúc, chỉ hiện thực hoá cái đã có.

    Không nêu GIÁ TRỊ nội dung (tên công ty, số tiền...) -- chỉ nêu HÌNH
    DẠNG (có bảng hay không, mấy chữ ký, bố cục nào). Nội dung vẫn của
    model, đúng "không khoá literal" (điểm 1 review, tránh G1)."""
    a = plan.assignment
    lines = [f"- family: `{plan.family}` (đã chọn sẵn -- KHÔNG đổi sang loại "
            "chứng từ khác)"]
    if "density" in a:
        lines.append(f"- density: {a['density']}")
    if "header" in a:
        lines.append(f"- header/letterhead layout: {a['header']}")
    if "party_block" in a:
        lines.append(f"- customer/party block layout: {a['party_block']}")
    if "table" in a:
        lines.append(f"- table: CÓ, kiểu {a['table']} (không phải \"none\")")
    else:
        lines.append("- table: KHÔNG -- đừng vẽ bảng nào trên trang này")
    if "signature_count" in a:
        n = a["signature_count"]
        # NÓI LUÔN CÁCH KHAI, không chỉ SỐ LƯỢNG.
        #
        # Cổng (`plan_conformance`) hỏi `"sign." in html` -- một phép tìm
        # chuỗi. Câu cũ chỉ nói "đúng N người ký" và không nói khai bằng gì,
        # nên model dựng khối chữ ký bằng tên class của chính nó. Đo trên
        # `data/pilot17`: 3 tờ trượt vì "yêu cầu N chữ ký nhưng HTML không có
        # `data-kind` nào bắt đầu bằng `sign.`", và mở HTML ra thì khối chữ ký
        # có đủ mực -- `llm_invoice_detailed_0023` viết `<div class="role">
        # NGƯỜI MUA HÀNG</div><div class="name">Ths. Trần Thị Mai</div>`,
        # `llm_form_symmetric_0009` dùng `parties.receive.representative`.
        # Mực có, nhãn không: đúng luật số ba của `AGENTS.md` bị phá.
        lines.append(f"- signatures: đúng {n} người ký"
                     + (" (không chữ ký nào)" if n == 0 else
                        " -- mỗi người phải mang `data-kind` họ `sign.` "
                        "(`sign.name`, `sign.title`, `sign.date`, "
                        "`sign.place`); tên class tự đặt KHÔNG tính"))
    if "signature_layout" in a:
        lines.append(f"- signature layout: {a['signature_layout']}")
    if plan.hard_negative_profile:
        decoys = "; ".join(f"{k} (chiến lược {v})"
                           for k, v in plan.hard_negative_profile.items())
        lines.append(f"- hard negatives bắt buộc cho: {decoys}")
    return "\n".join(lines)


# CHUYỂN VÀO `agent/rate_match.py` (Phase 4 task 4.4, docs/ke-hoach-refactor-
# engine.md) -- cùng lý do `sheets` dưới `one()` cũng chuyển: sampler cần
# gọi được hai hàm này mà không phải biết chúng từng sống ở callsite nào.
# Alias giữ TÊN CŨ để không phải sửa mọi chỗ gọi trong file này, và để
# không phá bất kỳ ai từng `from agent.compose_page import wants_table`.
wants_table = rate_match.wants_table


SAY = {
    "en": {
        "after_table": "Read them for how real Vietnamese paper words things "
                       "(labels, signature block wording, section order) -- "
                       "not for whether to have a table. This document's own "
                       "table decision is already fixed above; use these only "
                       "for wording and tone.",
        "shapes": "Three real Vietnamese documents, reduced to their SHAPE "
                  "(not their content):",
        "blocks": "blocks", "signs": "signed by", "nosign": "nobody signs",
        "after": "Read them for how real Vietnamese paper words things -- not "
                 "for structure. This document's own structure is already "
                 "fixed above.",
        "step1": "## Step one: REALIZE the document the engine already planned",
        "field": "Reference field (for wording/tone only -- not a menu to "
                 "pick a new document type from)", "invent":
            "The structure below is DECIDED, not a suggestion -- table "
            "presence, signature count, layout topology are the engine's "
            "call, not yours. Your job: invent a document `doc_title` and "
            "content that plausibly NEEDS exactly this structure, then "
            "realize it. Answer for yourself: given this structure, what is "
            "this sheet for, which body issues it, what does it print -- "
            "not whether to have a table or how many people sign, which are "
            "already fixed.",
        "planfirst": "Put your answers in the `plan` block. **Write `plan` "
                     "first, `html` second** -- and the HTML must match both "
                     "the `plan` you just wrote AND the structure fixed "
                     "above. `plan` here is your OWN summary of how you "
                     "realized the fixed structure, not a second, competing "
                     "source of truth -- the structure above is authoritative "
                     "and the validator checks the HTML against IT, not "
                     "against your `plan`.\n\nWrite `doc_kind` in VIETNAMESE "
                     "(the sheet's real name, matching the document family "
                     "above). `doc_slug` is filled in for you from the "
                     "family -- do not worry about it.",
        "done": "Already made this run", "nothing": "nothing yet",
        "other": "Invent a plausible DIFFERENT reason/content for the same "
                 "fixed structure -- not a different document type.",
        "step2": "## Step two: map each field to a `data-kind`",
        # "TAKE THE NEAREST" ĐÃ BỊ BỎ, và đó là sửa chính của mục này.
        #
        # Câu cũ dặn: "If none fits, take the nearest in meaning". Model làm
        # đúng lời dặn ấy, và đo được trên 394 tệp `declared/`: 1 352 trên
        # 8 555 lượt (15,8%) rơi vào ba khoá hứng chung `meta.value`,
        # `invoice.field`, `invoice.field.label` -- `meta.value` một mình 547
        # lượt, nhiều nhất bộ. "Gần nhất" không phải một phép ánh xạ, nó là
        # một cái thùng: `patient.bed_number` và `contract.penalty_rate` cùng
        # thành `invoice.field`, rồi câu tả tra theo khoá ấy nói cả hai là
        # "một trường có nhãn ở khối đầu trang".
        #
        # Thay bằng ba tầng của `synthgen/field_tier.py`. Cái giá của việc
        # đặt tên mới giờ là một câu tả, không phải cả tờ giấy: không có tên
        # nào ở đây làm trang bị loại.
        "map": "Every field you just invented must be named in `field_plan` "
               "as a `label` -> `kind` pair. Three ways a name is accepted, "
               "in this order:\n"
               "1. **Use a listed key.** If one of the keys below means what "
               "your field means, use it. Its general meaning is on file, but "
               "`describe` is still required: say which occurrence THIS one "
               "is. An authorisation letter carries `store.tax_code` twice -- "
               "authorising party and authorised agent -- and your sentence "
               "is the only thing that tells them apart.\n"
               "2. **Coin a name inside a listed family.** If no key fits but "
               "the family does (`store.`, `sign.`, `total.`, `menu.`, "
               "`clause.`, `survey.`, `meta.`, `section.`, `toc.`), write "
               "`family.your_leaf` AND one English sentence in `describe` "
               "saying what the value IS -- not what the caption says.\n"
               "3. **Coin a name outside every family** only when the concept "
               "belongs to no family above. It is kept for review and left "
               "out of the training set, so prefer (2) when a family fits.\n"
               "Never stretch a listed key to cover something it does not "
               "mean. A coined name with a sentence is worth more than a "
               "listed key used wrongly, and no choice here rejects the page."
               + _catchall_advice(),
        "regions": "Permitted `data-region`",
        "step3": "## Step three: write the sheet",
        "one_sheet": "This document is **one sheet**.",
        # CON SỐ MỖI TỜ LÀ THAM SỐ, không phải chữ viết cứng.
        #
        # Câu này từng ghi "(about 8,000 characters per A4 sheet)" ngay trong
        # mẫu, và khi tổng chuyển sang tính theo `density` thì hai con số
        # trong CÙNG một câu chỏi nhau: "9600 ký tự tổng" cho 8 tờ, tức 1 200
        # mỗi tờ, đứng cạnh "8 000 mỗi tờ". Model đọc hai con số cãi nhau thì
        # nghe con số nhỏ, và viết đúng một tờ. Đo trên `data/23-09-llm-e`:
        # 8 trên 12 tờ trượt vì "xin N tờ, dàn ra 1 tờ".
        # HAI CON SỐ, HAI ĐỘ CHÍNH XÁC KHÁC NHAU -- và câu cũ gộp chúng.
        #
        # Số tờ CẮT RA có dung sai: `SHEET_SHORTFALL_RATIO` cho tới 0,6 lần.
        # Số mục `sheet_plan` thì KHÔNG: `sheet_plan_problems()` loại thẳng
        # khi `len(sheet_plan) < n`. Câu cũ mở đầu bằng "runs to about **{n}
        # A4 sheets**" rồi mới nhắc `sheet_plan` ở cuối, nên chữ "about" phủ
        # lên cả hai, và model khai một `sheet_plan` "xấp xỉ". Đo trên
        # `data/pilot17`: 3 tờ trượt vì đúng chuyện ấy -- khai 2/3, 3/8, 1/3.
        "n_sheets": "This document runs to about **{n} A4 sheets**: write "
                    "ONE `<div class=\"sheet\">` holding enough content for "
                    "that many -- the machine cuts it to A4 height. Target "
                    "roughly **{per} characters of visible text per sheet**, "
                    "so about **{chars} characters in total** -- a "
                    "sheet that gets cut to fewer pages than asked is "
                    "treated as a FAILURE, not a shorter valid document. "
                    "Your `sheet_plan` must list **exactly {n} entries**, "
                    "one per sheet: that count is checked exactly, and a "
                    "plan with fewer entries is rejected before the page is "
                    "even drawn. \"About\" applies to how much you write, "
                    "never to how many entries you plan. Do not open a new "
                    "`.sheet`, and do not number the pages yourself.",
        # ĐẾM, KHÔNG MÔ TẢ.
        #
        # Câu cũ -- "This one HAS an item table, {lo}-{hi} rows." -- model đọc
        # như một lời TẢ tờ giấy, không phải một yêu cầu đếm. Đo thật trên
        # `gpt-4.1-mini`, cùng phôi cùng seed, chỉ khác cách nói:
        #
        #   câu cũ ............. 4 613 token ra · **1** `<tr>` · 467 ký tự chữ
        #   ép thẳng "đúng 80" . 22 172 token ra · **63** `<tr>` · 2 760 ký tự
        #
        # Vế đầu còn khai 64 dòng trong `rows` JSON rồi viết đúng một `<tr>`:
        # nó tưởng đã làm xong việc khi kể ra con số.
        #
        # Nên nói ba thứ câu cũ thiếu: con số CHÍNH XÁC (không phải khoảng),
        # lệnh ĐẾM trong lúc viết, và hậu quả của việc thiếu. Đây không phải
        # "viết prompt hay hơn" -- ba thứ ấy là ba điều kiện của một phép đếm.
        "table": "This one HAS an item table. Write **exactly {hi} `<tr>` "
                 "rows inside `<tbody>`** -- not {lo}, not half of {hi}: "
                 "{hi}. Count them as you write them. The table is what makes "
                 "this document {n} sheets long; a `<tbody>` with fewer rows "
                 "cuts to fewer sheets and the page is rejected.",
        "notable": "This one has **no item table at all**. Lay it out some "
                   "other way: two-column field blocks, prose, numbered "
                   "clauses, tick boxes, a captioned figure frame, a footer "
                   "note.",
        "return": "Return JSON matching the schema: `plan`, `rows` {rows}, and "
                  "`html`.",
        "rows_y": "(one entry per table row, for the arithmetic check)",
        "rows_n": "(an EMPTY list)",
    },
}


def inspiration(index: int, family: str, lang: str = "en", how_many: int = 3,
                table: bool = False) -> str:
    """Vài phôi THẬT của kho, đưa cho model ĐỌC HIỂU chứ không phải ĐIỀN.

    Người dùng hỏi thẳng: "có cách nào đưa các phôi trước đó vào để llm đọc
    hiểu không". Có, và nó giải đúng cái bệnh nhiều bảng.

    Đo trên 97 phôi trong `rulebase/synthgen/`: chỉ **18%** bắt buộc có bảng
    hàng. Còn nhánh LLM đang ép 60%. Chênh lệch ấy không phải do model thích
    bảng -- mà do nó chưa bao giờ được thấy giấy tờ Việt Nam bày bằng cách
    nào khác. Một tờ phiếu chi thật là `fields + totals + signatures`, không
    có lấy một dòng bảng.

    Nên đưa **hình dạng** chứ không đưa nội dung: danh sách khối, một bộ chữ
    ký, khoảng số dòng. Model thấy `phieu_chi` bày ra sao rồi tự nghĩ ra tờ
    khác của riêng nó. Đây không phải quay lại lối "N phôi" người dùng đã bác
    -- phôi ở đây là VÍ DỤ ĐỂ HIỂU, không phải khuôn để điền, và mỗi lượt gọi
    thấy một bộ ví dụ khác nhau.

    Tên phôi và tên chức danh giữ nguyên tiếng Việt ở cả ba bản: chúng là DỮ
    LIỆU về giấy tờ Việt Nam, không phải lời dặn. Dịch "THỦ QUỸ" sang
    "treasurer" là bỏ đi đúng thứ model cần thấy.

    Rẻ: ba phôi rút gọn tốn chừng 120 token nạp, đổi lấy việc model thôi vẽ
    bảng ở chỗ giấy thật không có bảng."""
    pool = D.ARCHETYPES
    if not pool:
        return ""
    say = SAY["en"]
    # Lọc theo lĩnh vực TRƯỚC khi quay vòng. Không đủ ba phôi khớp thì bù bằng
    # cả kho -- thà một ví dụ lệch còn hơn không có ví dụ nào. Tra qua
    # `FAMILY_DOMAIN`, không qua `index % len(DOMAINS)` -- xem lý do ở chỗ
    # khai `FAMILY_DOMAIN`.
    stems = DOMAIN_STEMS.get(FAMILY_DOMAIN.get(family, -1), ())
    near = [a for a in pool if any(s in a.id for s in stems)]
    if len(near) >= how_many:
        pool = near
    # Quay vòng theo `index` bằng bước nguyên tố cùng nhau với độ dài: mỗi
    # lượt thấy một bộ khác, và sau nhiều lượt thì cả kho đều được thấy.
    step = max(1, len(pool) // max(1, how_many))
    picked = [pool[(index * 7 + i * step) % len(pool)] for i in range(how_many)]
    lines = []
    for a in picked:
        blocks = ", ".join(a.always or ())
        signs = " / ".join((a.sign_sets or [()])[0][:3]) or say["nosign"]
        lines.append(f"* `{a.id}` -- {say['blocks']}: {blocks}; "
                     f"{say['signs']}: {signs}")
    # Câu đóng phải khớp với việc tờ này CÓ bảng hay không. Bản trước luôn nói
    # "phần lớn giấy tờ không có bảng hàng nào" rồi bước ba nói ngay "Tờ này CÓ
    # bảng hàng, 7-18 dòng" -- hai câu chỏi nhau trong cùng một lời nhờ.
    close = say["after_table"] if table else say["after"]
    return f"{say['shapes']}\n\n" + "\n".join(lines) + f"\n\n{close}\n\n"


def ask_for(index: int, made: list[str], plan: DP.DocumentPlan, sheets: int,
           lang: str = "en", avoid: str = "") -> str:
    """Lời nhờ cho MỘT tờ.

    Phase 5 (task 5.1, `docs/ke-hoach-refactor-engine.md`): trước đây
    không có phôi nào ở đây, model tự nghĩ toàn bộ cấu trúc. Giờ `plan`
    (rút từ `agent/grammar.py` qua `agent/document_plan.py`) CỐ ĐỊNH cấu
    trúc -- có bảng hay không, mấy chữ ký, bố cục nào -- và model chỉ còn
    tự do ở nội dung: `doc_title` cụ thể, lý do tài liệu này tồn tại, chữ
    trên trang. Đây đúng ranh giới "LLM là Realizer" (mục 1 tư duy gốc),
    không phải nới lỏng ngược lại G1.

    `made` là những loại chứng từ lượt này đã làm. Đưa vào để đẩy sang chỗ
    khác, không phải để cấm: cùng lối `agent/planner.py` dùng `pressure` để
    phủ đuôi phân phối thay vì bốc độc lập và bỏ trống những góc hiếm.

    `avoid` là câu nhắc đa dạng của `agent/diversity.py`, chỉ có mặt ở lượt
    SINH LẠI: tờ trước đã viết xong, đã dàn ra, và rơi đúng vào chỗ một tờ
    gần đây đã chiếm. Nó đứng NGAY SAU khối cấu trúc chứ không ở cuối lời
    nhờ, vì nó nói về cùng một thứ (trang này bày ra sao) và phải được đọc
    trong lúc model còn đang nghĩ về bố cục, không phải sau khi đã nghĩ
    xong. Rỗng ở lượt đầu -- không có gì để tránh thì không nói gì."""
    say = SAY["en"]
    hint = FAMILY_HINT.get(plan.family, plan.family)
    # DANH SÁCH DÁN VÀO BRIEF PHẢI LÀ DANH SÁCH `enum` ÉP, không phải một
    # danh sách hẹp hơn. `kinds()` nhặt từ 300 trang mẫu nên nó thiếu 14 khoá
    # mà sổ đăng ký có thật -- `sidebar.label`, `entry.title`, `menu.quota`,
    # `menu.meter_prev`... Dán bản hẹp là nói với model rằng chúng KHÔNG TỒN
    # TẠI, rồi model đặt tên mới cho khái niệm đã có tên: đúng cái bẫy
    # `llm_page.py::EXTRA` đã viết ra cho `section`, chỉ khác chỗ xảy ra.
    every = ", ".join(FT.closed_enum(FT.KIND))
    seen = (", ".join(made[-14:]) if made else say["nothing"])
    table = "table" in plan.assignment
    # Số dòng bảng theo SỐ TỜ, không theo chỉ số lượt. Bản trước cho tới 30
    # dòng trên một tờ giấy duy nhất: bảng nuốt hết trang (đúng cái đã sửa ở
    # `1e6b114`), và thân bảng là 21% số ký tự model phải viết ra, tức 21%
    # thời gian. Tài liệu bốn tờ thì cần nhiều dòng để có cớ sang trang; tài
    # liệu một tờ thì không.
    # SỐ DÒNG VÀ SỐ KÝ TỰ ĐỀU THEO MỖI TỜ, nhân lên bằng số tờ đã xin.
    #
    # Bản trước: `10 + sheets*4` dòng, và `sheets * 8000` ký tự. Cả hai sai,
    # và sai ngược chiều nhau.
    #
    # `8000` gấp bảy lần tờ giấy thật -- đo trên 58 tài liệu nhánh luật,
    # trung vị 1 175 ký tự chữ mỗi tờ. Giấy tờ hành chính Việt Nam không phải
    # văn xuôi dày; một tờ biên bản có chừng một nghìn ký tự và nhiều khoảng
    # trắng. Xin gấp bảy là xin một thứ model không có cớ để viết ra.
    #
    # `10 + sheets*4` thì ngược lại, QUÁ ÍT: tám tờ chỉ xin 42 dòng, trong khi
    # một tờ A4 dày bảng chứa chừng ấy MỘT MÌNH. Bảng không dài ra thì không
    # có gì để cắt sang tờ sau, và đó đúng là cách 7/12 tờ lô `d` trượt cổng
    # "xin N tờ, dàn ra M<N".
    #
    # Số mỗi mức đọc từ `rulebase/synthgen/_blocks.yaml::llm_density`, đo từ
    # nhánh luật -- xem ghi chú trong chính file ấy.
    level = str(plan.assignment.get("density") or "medium")
    profile = D.llm_density(level) or {"chars": 1200, "rows": 11}
    per_sheet_rows = max(int(profile.get("rows") or 11), 1)
    per_sheet_chars = max(int(profile.get("chars") or 1200), 1)
    low = max(per_sheet_rows * sheets - per_sheet_rows // 2, 3)
    high = per_sheet_rows * sheets + per_sheet_rows // 2
    shape = (say["table"].format(lo=low, hi=high, n=sheets) if table
             else say["notable"])
    many = (say["one_sheet"] if sheets == 1
            else say["n_sheets"].format(n=sheets, per=per_sheet_chars,
                                        chars=sheets * per_sheet_chars))
    return (
        f"{say['step1']}\n\n"
        f"{say['field']}: **{hint}** (`{plan.family}`).\n\n"
        "### Structure -- decided by the engine, not by you\n\n"
        f"{describe_plan(plan)}\n\n"
        + (f"{avoid}\n\n" if avoid else "")
        + f"{inspiration(index, plan.family, lang, table=table)}"
        f"{say['invent']}\n\n"
        f"{say['planfirst']}\n\n"
        f"{say['done']}: {seen}. {say['other']}\n\n"
        f"{say['step2']}\n\n"
        f"{say['map']}\n\n"
        f"{every}\n\n"
        f"{say['regions']}: {', '.join(REGIONS)}\n\n"
        f"{say['step3']}\n\n"
        f"{many}\n\n{shape}\n\n"
        + say["return"].format(rows=say["rows_y"] if table else say["rows_n"])
        + "\n"
    )


def arithmetic(rows: list[dict]) -> tuple[int, int]:
    """`(số dòng sai, tổng số dòng)` -- `qty x unit_price` có bằng `amount` không."""
    bad = 0
    for row in rows:
        try:
            if int(row["qty"]) * int(row["unit_price"]) != int(row["amount"]):
                bad += 1
        except (KeyError, TypeError, ValueError):
            bad += 1
    return bad, len(rows)


# Ngoặc vuông TUỲ CHỌN quanh chỉ số: `[0]` VÀ `0` trần (`clause.1.body`) đều
# là chỉ số -- `synthgen/llm_page.py::_PATH` giờ chấp nhận cả hai hình (Phase
# 8, đo trên pilot16), nên đường đọc cây `data` ở đây phải hiểu cả hai, không
# chỉ hình có ngoặc.
_PATH_STEP = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)|\[?(\d+)\]?")


def resolve_path(data: dict, path: str) -> tuple[bool, object]:
    """Đi theo một `data-path` (`issuer.tax_code`, `line_items[0].name`,
    `clause.1.body`) vào cây `data`. `(True, giá trị)` nếu đi hết đường;
    `(False, None)` nếu gãy ở đâu đó -- đường dẫn có đoạn không khớp
    khoá/chỉ số nào trong cây."""
    node: object = data
    for match in _PATH_STEP.finditer(path):
        name, index = match.group(1), match.group(2)
        if name is not None:
            if not isinstance(node, dict) or name not in node:
                return False, None
            node = node[name]
        else:
            if not isinstance(node, list) or int(index) >= len(node):
                return False, None
            node = node[int(index)]
    return True, node


def data_path_mismatches(data: dict, html: str) -> list[str]:
    """Mỗi `data-path` HTML in ra, đối chiếu với chính cây `data` model đã
    viết TRƯỚC đó -- cây ấy vào `schema()` từ bản sửa architecture cũ (suy
    KIE từ toạ độ), giờ được ghi ra `declared/*.json` rồi không ai đọc lại
    (xem `docs/ke-hoach-refactor-engine.md`, task 1.4). Đây là cách dùng nó:
    không phải nguồn KIE thứ hai -- `data-path` trong HTML đã là nguồn --
    mà một phép đối chiếu NỘI TẠI, bắt đúng lúc model tự mâu thuẫn với chính
    mình giữa hai phần của cùng một câu trả lời.

    KHÔNG gate -- cùng lý do `synthgen/llm_page.py::problems()` chưa ép
    `data-path` phải có mặt: chưa đo được tỉ lệ khớp trên `page.md` mới, và
    ép theo một con số chưa đo là đổi tỉ lệ chấp nhận mà không ai biết trước
    bao nhiêu. Đây là hàm ĐO, để `thinking()`/Phase 2 dùng, không phải hàm
    LOẠI."""
    # HAI HÌNH, MỘT PHÉP TRA. `schema()` giờ xin danh sách phẳng
    # `[{path, value}]` -- xem `DATA_ITEMS` về việc vì sao. Nhưng mọi
    # `declared/*.json` đã ghi ra đĩa trước hôm nay mang cây LỒNG, và chúng
    # vẫn phải đọc được: một hàm đo mà chỉ đọc được dữ liệu sinh từ hôm nay
    # là một hàm không so được trước/sau.
    flat = {str(item.get("path") or ""): item.get("value")
            for item in data if isinstance(item, dict)} \
        if isinstance(data, list) else None

    found: list[str] = []
    for path, printed in declared_paths(html):
        if flat is not None:
            ok = path in flat
            value = flat.get(path)
        else:
            ok, value = resolve_path(data, path)
        if not ok:
            found.append(f'`data-path="{path}"` không tra được trong cây `data` '
                         "model tự viết")
            continue
        wanted = " ".join(str(value).split())
        if wanted and wanted != printed:
            found.append(f'`data-path="{path}"`: `data` ghi {wanted!r}, HTML in '
                         f"ra {printed!r}")
    return found


def _slug(text: str) -> str:
    """Tên thư mục an toàn từ loại chứng từ model tự đặt."""
    plain = str(text).lower()
    # `đ` KHÔNG phân rã được. `unicodedata.normalize("NFD", ...)` tách dấu ra
    # khỏi `ộ` thành `o` + dấu, nhưng `đ` là một CHỮ CÁI riêng trong bảng chữ
    # cái tiếng Việt, không phải `d` có dấu -- NFD để nguyên, rồi bộ lọc
    # `[^a-z0-9]` xoá sạch. Kết quả đo trên pilot6: "hoạt động" -> `hoat_ong`,
    # "đăng ký" -> `ang_ky`. Đổi trước khi phân rã.
    plain = plain.replace("đ", "d").replace("Đ", "d")
    plain = unicodedata.normalize("NFD", plain)
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")[:40] or "llm"


def sheet_plan_problems(plan: dict, sheets: int) -> list[str]:
    """Kế hoạch từng tờ có đủ số tờ được xin không.

    Cổng này không chấm nội dung -- nó chỉ đếm. Model khai bốn mục cho tám tờ
    nghĩa là nó chưa nghĩ về bốn tờ còn lại, và bốn tờ ấy sẽ không có chữ.

    Vì sao đếm chứ không đo chữ: lượng chữ đo được SAU khi dàn trang, còn cổng
    chạy TRƯỚC. Thứ cổng nhìn thấy là lời khai, nên nó gác lời khai."""
    plan_rows = plan.get("sheet_plan")
    if not isinstance(plan_rows, list) or not plan_rows:
        return [f"`sheet_plan` trống; tài liệu này xin {sheets} tờ"]
    if len(plan_rows) < sheets:
        return [f"`sheet_plan` chỉ khai {len(plan_rows)} tờ, tài liệu xin "
                f"{sheets} tờ -- {sheets - len(plan_rows)} tờ chưa ai nghĩ tới"]
    empty = [r.get("sheet") for r in plan_rows
             if not (r.get("sections") or [])]
    if empty:
        return [f"tờ {empty} khai trong `sheet_plan` mà không mục nào"]
    return []


# Dưới ngưỡng này thì coi là THIẾU RÕ RỆT, không phải một tờ hụt nhẹ. Đo
# trên pilot16 (Phase 8, `docs/ke-hoach-refactor-engine.md`): "xin 6 -> cắt
# ra 5" (83%) là một tờ gần đủ, không đáng loại; "xin 4 -> cắt ra 2" (50%),
# "xin 8 -> cắt ra 1" (12%) là thiếu thật. 0.6 nằm giữa hai nhóm ấy trên
# đúng dữ liệu đã đo, không phải một số chọn khơi khơi.
SHEET_SHORTFALL_RATIO = 0.6


def _reconcile_sheet_count(made: list[dict],
                           actual_pages: dict[str, int]) -> list[str]:
    """Sửa lại `ok`/`why` của những trang đã qua cổng CHỮ nhưng dàn trang
    THẬT ra ít tờ hơn hẳn số đã xin. Đổi tại chỗ trên `made`; trả về danh
    sách `stem` vừa bị lật, để gọi nơi rời file khỏi `html/` sang
    `rejected/`.

    ## Vì sao đây là một hàm RIÊNG, chạy SAU `one()`, không phải một dòng
    ## nữa trong `found` của `one()`

    Đã thử đúng cách "một dòng nữa trong `found`" trước: đo `visible_chars()`
    (`synthgen/llm_page.py`) trên `html`, so với một hằng số "8 000 ký tự mỗi
    tờ A4", gác TRƯỚC khi dàn trang. Chạy thật trên pilot16 lộ ngay sai lầm:
    `authorisation_letter` (bố cục key-value xếp dọc, mỗi trường một dòng)
    đo được ~1 150 ký tự MỖI TỜ THẬT -- so với 8 000 ước lượng từ văn xuôi/
    bảng dày, chênh bảy lần -- và trang ấy bị gác SAI dù nó xin 2 tờ mà dàn
    ra tới 3 tờ THẬT (nhiều hơn xin, không phải thiếu). Không hằng số ký tự
    nào đúng cho mọi kiểu bố cục mà track 3 cố tình đa dạng ra.

    Số tờ THẬT chỉ trình duyệt biết chắc (`synthgen/draw_llm.py`, cắt theo
    chiều cao A4 thật qua Playwright) -- và phép đo ấy chạy trong luồng
    `Artist`/`Drawer`, SONG SONG với vòng lặp sinh trang trong `run()`, xong
    SAU khi `one()` đã quyết `ok`. Nên việc GÁC THẬT phải là một bước riêng,
    chạy sau khi `Artist.close()` đã có đủ `artist.rows`, không thể nhét vào
    `found` của `one()` được."""
    flipped: list[str] = []
    for made_page in made:
        if not made_page.get("ok"):
            continue
        asked = int(made_page.get("sheets_asked") or 1)
        if asked <= 1:
            continue
        stem = f"llm_{made_page['archetype']}_{made_page['index']:04d}"
        actual = actual_pages.get(stem)
        if actual is None or actual >= asked * SHEET_SHORTFALL_RATIO:
            continue
        made_page["ok"] = False
        made_page["why"] = [
            *(made_page.get("why") or []),
            f"xin {asked} tờ nhưng dàn trang thật chỉ ra {actual} tờ "
            f"(dưới {SHEET_SHORTFALL_RATIO:.0%} số đã xin)"]
        flipped.append(stem)
    return flipped


def plan_problems(plan: dict, html: str) -> list[str]:
    """Kế hoạch model tự viết có khớp với trang nó vẽ không.

    Cổng này KHÔNG có ở bản trước, vì bản trước model không tự quyết gì. Giờ
    nó quyết, nên phải kiểm rằng nó làm đúng thứ mình vừa nói -- một kế hoạch
    không ai đối chiếu là một kế hoạch để trang trí.

    Chỉ kiểm hai điều, và cả hai đo được trên chính HTML:

    * `field_plan` ánh xạ sang `data-kind` THẬT. Đây là chỗ lượt trước hỏng
      nhiều nhất -- `patient.name`, `project.code` là tên model tự đặt.
    * `kind` nào đã hứa trong kế hoạch thì phải có mặt trên trang. Hứa mà
      không in là kế hoạch nói một đằng trang làm một nẻo.

    KHÔNG kiểm `purpose`, `issuer`, `layout_idea`: chúng là suy nghĩ, và một
    cái cổng chấm điểm suy nghĩ là một cái cổng đoán."""
    known = kinds()
    found: list[str] = []
    # NHÁY ĐƠN CŨNG LÀ HTML. Bản trước so chuỗi `f'data-kind="{kind}"'`, nên
    # một trang model viết `data-kind='store.name'` trượt SẠCH mọi kind nó đã
    # hứa -- đo trên pilot8: ba tờ báo 0/29, 0/37, 0/38, trong khi phép đo thật
    # (`querySelectorAll('span[data-kind]')`) đếm được 216 hộp từ trên chính
    # một trong ba tờ ấy. Trình duyệt đọc được, cổng gác thì không.
    #
    # Bảy mươi mốt lời than "kế hoạch hứa `…` mà trang không in nó ra" ở lượt
    # pilot8 gần như toàn bộ từ đây, và chúng loại những trang viết đúng.
    printed = printed_kinds(html)
    planned = {k for k in (str(f.get("kind") or "")
                           for f in (plan.get("field_plan") or [])) if k}
    for kind in sorted(planned):
        # MỘT vị từ cho cả ba nơi ép luật -- xem `llm_page.acceptable_kind`.
        # Bản trước quên vế `_COINED` ở đây, nên nó loại `menu.number` và
        # `contract.party_a`: tên lời dặn CHO PHÉP, bộ giải mã sinh được, cổng
        # chữ chấp nhận -- rồi chết ở đây.
        if not acceptable_kind(kind, known):
            found.append(f"`field_plan` đặt tên `{kind}` không có trong từ vựng")

    # HỨA-MÀ-KHÔNG-IN: đo theo TỈ LỆ, không bắt từng cái một.
    #
    # Luật cũ loại trang ngay khi MỘT kind đã hứa vắng mặt. Đo trên pilot8 sau
    # khi sửa lỗi dấu nháy: mười bảy trên hai mươi hai tờ in đúng 100% kế
    # hoạch, hai tờ thiếu đúng một kind (96% và 97%), một tờ thiếu năm (80%),
    # một tờ thiếu quá nửa (47%). Cái đuôi 96-97% là người ta soạn giấy tờ:
    # lên danh sách rồi bỏ bớt một mục lúc bày trang. Loại nó là loại một tờ
    # viết đúng.
    #
    # Phần từ vựng -- việc THẬT của `field_plan` -- đã do `enum` trong schema
    # lo, và lo chặt hơn mọi lời dặn: bộ giải mã không sinh nổi tên ngoài danh
    # sách. Thứ còn lại cho luật này là bắt trang BỎ HẲN kế hoạch, và một
    # ngưỡng tỉ lệ bắt đúng thứ ấy.
    if planned:
        missing = sorted(k for k in planned if k not in printed)
        # Tha tối đa một phần mười kế hoạch, và ít nhất một kind -- NHƯNG
        # không bao giờ tha cả kế hoạch. Cái sàn "ít nhất một" mà đứng một
        # mình thì với kế hoạch chỉ có một kind, nó tha đúng 100% số bị bỏ:
        # trang vứt sạch kế hoạch vẫn đi qua.
        # MỘT PHẦN NĂM, không phải một phần mười. Đo trên pilot9 sau khi
        # `repair.vocabulary` ánh xạ kind lạ: 23 trên 24 tờ bỏ tối đa 20% kế
        # hoạch, một tờ bỏ 60%. Khe giữa 20% và 60% là khe thật, không phải
        # chỗ tôi chọn cho tiện -- ngưỡng 10% loại 6 tờ nằm trong cụm 8-12%,
        # tức loại đúng cái đuôi "soạn danh sách rồi bỏ bớt một mục", còn
        # ngưỡng 20% vẫn bắt tờ duy nhất thật sự vứt kế hoạch.
        #
        # NGƯỠNG TỪ YAML, không phải hằng số trong mã. Con số 1/5 ở trên đo
        # trên pilot9 với Qwen3-27B. Chạy `gpt-4.1-mini` ngày 23-09-2026 thì
        # phân bố khác hẳn: 5/14, 6/11, 8/14, 10/15, 11/12 -- tám trên mười
        # tờ trượt vì đúng luật này, và cả tám có nhãn ĐÚNG PIXEL ở mọi hộp
        # chúng có. Một ngưỡng đo trên model này áp cho model kia là một
        # ngưỡng sai, và nó sai theo hướng vứt dữ liệu tốt.
        #
        # `field_plan` không vào bộ huấn luyện: ảnh, hộp và KIE mới vào. Nó
        # là BẢN NHÁP của model, nên trang in ít hơn nháp là trang nhỏ hơn,
        # không phải trang sai. Chiều nguy hiểm -- `kie` khai giá trị không
        # có trên giấy -- do phép kiểm khác lo.
        share = D.gate_ceiling("plan_drop_share", 0.2)
        allowed = min(max(1, int(len(planned) * share)), len(planned) - 1)
        if len(missing) > allowed:
            found.append(
                f"trang bỏ {len(missing)}/{len(planned)} kind đã hứa trong kế "
                f"hoạch (cho phép {allowed}): {', '.join(missing[:6])}")
    if not plan.get("signers") and "sign." in html:
        found.append("trang có chữ ký mà `plan.signers` để trống")
    return found


_HTML_TABLE = re.compile(r"<table\b", re.IGNORECASE)


def plan_conformance_problems(plan: DP.DocumentPlan, html: str) -> list[str]:
    """So HTML THẬT với `DocumentPlan` của ENGINE -- không qua `plan` model
    tự khai lại trong câu trả lời (điểm 3 review, Phase 5 task 5.2):
    `DocumentPlan` là nguồn sự thật, `plan_problems()` ở trên vẫn hữu ích
    (bắt model khai `field_plan` sai từ vựng, hoặc bỏ sót phần đã hứa
    trong CHÍNH câu trả lời của nó) nhưng không được dùng để nói "cấu trúc
    trang đúng" -- việc đó là của hàm này.

    Chỉ kiểm hai điều đo được chắc chắn từ HTML mà không cần đoán: có bảng
    hay không (thẻ `<table>` thật), có chữ ký hay không (`data-kind` bắt
    đầu bằng `sign.`) -- cả hai đều là nhị phân trong `DocumentPlan`
    (`"table" in assignment`, `signature_count == 0` hay `> 0`), nên so
    được thẳng, không cần suy luận số lượng chính xác."""
    found: list[str] = []
    has_table = bool(_HTML_TABLE.search(html))
    wants_table_plan = "table" in plan.assignment
    if wants_table_plan and not has_table:
        found.append(f"engine plan ({plan.family}) yêu cầu có bảng "
                     "(`table` trong DocumentPlan) nhưng HTML không có thẻ "
                     "`<table>` nào")
    elif not wants_table_plan and has_table:
        found.append(f"engine plan ({plan.family}) không có nhánh `table` "
                     "(gia đình này không dùng bảng) nhưng HTML có `<table>`")

    sig_count = plan.assignment.get("signature_count")
    has_signature = "sign." in html
    if sig_count == 0 and has_signature:
        found.append(f"engine plan ({plan.family}) yêu cầu 0 chữ ký nhưng "
                     "HTML có `data-kind` bắt đầu bằng `sign.`")
    elif isinstance(sig_count, int) and sig_count > 0 and not has_signature:
        found.append(f"engine plan ({plan.family}) yêu cầu {sig_count} chữ "
                     "ký nhưng HTML không có `data-kind` nào bắt đầu bằng "
                     "`sign.`")
    return found


# Bao nhiêu token đầu ra cho MỘT ký tự chữ hiển thị.
#
# Không phải một ký tự HTML -- một ký tự CHỮ, thứ `llm_density` đang đếm. Hai
# đại lượng chênh nhau gần bảy lần, và nhầm chúng là cách chắc chắn nhất để
# đặt sai trần. Đo trên `data/pilot17`, 42 lời gọi trả lời được:
#
#   ký tự HTML / ký tự chữ : trung vị 6,7   (mỗi run là một `<span
#                                            data-kind=… data-path=…>`)
#   token ra   / ký tự HTML: trung vị 0,49
#   token ra   / ký tự chữ : trung vị 3,37  (min 0,99 · max 9,71)
#
# Markup nở ra gần bảy lần vì chính cái làm nên giá trị của kho này: mỗi run
# chữ mang nhãn của nó ngay trong thẻ. Đó là chi phí bắt buộc, không phải mỡ.
TOKENS_PER_VISIBLE_CHAR = 3.37


def budget(sheets: int, level: str = "medium") -> int:
    """Trần token đầu ra cho một tài liệu `sheets` tờ ở mức dày `level`.

    Trần CỐ ĐỊNH 9 000 không khớp với chính lời dặn của mình: prompt cho mỗi tờ
    8 000 ký tự, và đo được 2,05 ký tự mỗi token, nên một tờ tốn chừng 3 900
    token. Ba tờ đã cần 11 700 -- vượt trần. Đo trên pilot8: hai lời gọi duy
    nhất trả về "reply was not JSON" là đúng hai tài liệu 4 tờ và 6 tờ, cụt
    giữa chừng vì chạm trần sau 168 giây.

    ## Vì sao trần tính TỪ mục tiêu ký tự, không còn là một hằng số riêng

    Bản trước là `2 600 + sheets * 5 200`, một con số ĐỘC LẬP với số ký tự lời
    nhờ đang xin. Hai con số độc lập nói về cùng một thứ là cái bẫy `AGENTS.md`
    gọi là "một luật, hai người dựng": khi `llm_density` được đo lại và mục
    tiêu ký tự tăng 2,7 lần, trần token không biết gì cả.

    Tính thử trước khi chạy, và nó chặn đúng một lượt sinh vô ích: mục tiêu
    mới (medium 3 300 ký tự/tờ) cần 11 115 token cho MỘT tờ, trong khi trần cũ
    cho một tờ là 7 800 -- và cả tám mức số tờ đều thiếu, 8 tờ cần 88 923 so
    với trần 44 200. Tức toàn bộ lô sẽ cụt JSON: 23 tờ trượt vì thiếu tờ được
    đổi thành 60 tờ trượt vì cụt. Nay trần đọc CÙNG `llm_density` mà
    `ask_for()` đọc, nên hai con số không thể lệch nhau nữa."""
    profile = D.llm_density(level) or {}
    per_sheet = max(int(profile.get("chars") or 3300), 1)
    need = max(1, sheets) * per_sheet * TOKENS_PER_VISIBLE_CHAR
    # 2 600 token cho `plan` và `rows` -- phần không phải chữ trên giấy.
    #
    # Trần trên 150 000, không 60 000: mục tiêu mới cho 8 tờ `very_dense` cần
    # 8 x 3 800 x 3,37 = 102 448. Cửa sổ ngữ cảnh máy chủ là 262 144 và prompt
    # đo được ~26 500 token, nên 150 000 vẫn còn dư chỗ. Trần chỉ để một lời
    # gọi LẠC LỐI hỏng nhanh thay vì ăn hết cửa sổ -- nó không được là thứ
    # chặn một tài liệu viết đúng độ dài đã xin.
    return int(min(150_000, 2_600 + need))


# Hạn chờ TỐI ĐA cho MỘT lần thử, dù trần token lớn tới đâu.
#
# Vì sao phải có trần cứng ở đây: `budget()` giờ tính từ mục tiêu ký tự, và
# `budget(8, "very_dense")` = 105 048 token, chia 15 tok/s ra **7 003 giây một
# lần thử**. `Client._post` thử lại `retries + 1` = 3 lần, nên một tờ giữ chỗ
# hơn năm giờ TRƯỚC KHI bỏ cuộc.
#
# Đo được, và đo bằng một lượt chạy mất trắng: `data/pilot18` 24-09-2026, máy
# chủ vLLM tắt giữa lô, và tờ thứ 20 treo **51 025,9 giây (14,2 giờ)** rồi mới
# báo `URLError`. 19 tờ đầu đã xong, 41 tờ còn lại thành rác. Một hạn chờ rộng
# không cứu được tờ nào khi máy chủ đã chết -- nó chỉ đổi "hỏng nhanh, biết
# ngay" thành "treo qua đêm, sáng ra mới biết".
#
# 3 600 giây là 1,5 lần lời gọi CHẬM NHẤT từng đo được (pilot17 1 942s,
# pilot18 2 344s), nên nó không cắt ngang một tờ đang viết thật, mà chặn được
# một máy chủ không trả lời ở ba giờ thay vì mười bốn.
PATIENCE_CEILING = 3600.0


def patience(sheets: int, floor: float, level: str = "medium") -> float:
    """Hạn chờ cho một tài liệu `sheets` tờ, tính từ trần token.

    Trần co giãn thì hạn chờ phải co giãn theo, nếu không ta chỉ đổi kiểu hỏng:
    tờ sáu trang thôi cụt JSON mà chuyển sang hết hạn chờ. 23 400 token ở 24
    tok/s -- tốc độ đo được lúc máy chủ bận -- là 975 giây, vượt hạn 600.

    Lấy 15 tok/s làm đáy: chậm hơn mọi lượt đã đo (pilot7 24, pilot8 52), nên
    hạn rộng mà vẫn hữu hạn. Không bao giờ ngắn hơn `floor` người dùng đặt, và
    không bao giờ dài hơn `PATIENCE_CEILING` -- xem ghi chú ở đó."""
    want = min(budget(sheets, level) / 15.0, PATIENCE_CEILING)
    return max(floor, want)


def thinking(got: dict, brief: str) -> str:
    """Một trang đọc được, ghép mọi thứ cần để mổ một tờ hỏng.

    Vì sao cần: một tờ trượt cổng hiện để lại HTML trong `rejected/`, một câu
    báo lỗi trong `declared/`, và một tấm ảnh trong `rejected_boxes/` -- ba chỗ
    khác nhau, và không chỗ nào nói model NGHĨ GÌ. Người sửa lời dặn phải tự
    ghép lại, và ghép sai thì sửa nhầm.

    Gộp bốn thứ vào một tệp: lời nhờ nó nhận, kế hoạch nó viết, lý lẽ nó nêu,
    và phán quyết của cổng. Đọc từ trên xuống là thấy chỗ suy nghĩ rẽ sai.

    Viết cho MỌI tờ, không riêng tờ hỏng: một tờ ĐẠT cũng đáng đọc, vì so nó
    với tờ hỏng cạnh bên là cách nhanh nhất thấy khác biệt."""
    plan = got.get("plan") or {}
    why = plan.get("reasoning") or {}
    ok = got.get("ok")
    lines = [
        f"# {got.get('loai_tai_lieu') or got['archetype']}",
        "",
        f"* **Kết quả**: {'ĐẠT' if ok else 'TRƯỢT CỔNG'}",
        f"* **Thư mục**: `{got['archetype']}`  ·  chỉ số {got['index']}",
        f"* **Thời gian**: {got.get('seconds')}s  ·  "
        f"{got.get('tokens_out')} token ra / {got.get('tokens_in')} vào",
        f"* **Xin**: {got.get('sheets_asked')} tờ  ·  "
        f"bảng: {'có' if got.get('table_asked') else 'không'}",
        "",
        "## Model nghĩ gì",
        "",
        f"**Vì sao chọn loại chứng từ này** — {why.get('why_this_document') or '(không nói)'}",
        "",
        f"**Vì sao bày trang như vậy** — {why.get('why_this_layout') or '(không nói)'}",
        "",
        f"**Chỗ khó nhất** — {why.get('hardest_choice') or '(không nói)'}",
        "",
        "## Model định làm gì",
        "",
        f"* mục đích: {plan.get('purpose') or '—'}",
        f"* cơ quan phát hành: {plan.get('issuer') or '—'}",
        f"* người ký: {', '.join(plan.get('signers') or []) or '—'}",
        f"* ý bố cục: {plan.get('layout_idea') or '—'}",
        "",
    ]
    fields = plan.get("field_plan") or []
    if fields:
        lines += [f"### {len(fields)} trường đã ánh xạ", "",
                  "| nhãn trên giấy | `data-kind` |", "|---|---|"]
        lines += [f"| {f.get('label','')} | `{f.get('kind','')}` |" for f in fields]
        lines += [""]
    if got.get("attempt", 1) > 1 or got.get("collision"):
        # SINH LẠI VÌ TRÙNG là một sự kiện phải đọc được cạnh chính tờ giấy
        # ấy, không chỉ trong `compose_report.json`: người mở `thinking/` ra
        # là người đang hỏi "vì sao tờ này trông như vậy", và "vì tờ trước
        # rơi đúng chỗ tờ 12" là một câu trả lời.
        hit = got.get("collision") or {}
        lines += ["## Chống trùng bố cục", "",
                  f"* lượt gọi thứ **{got.get('attempt', 1)}** cho tờ này",
                  f"* đã nhận câu nhắc tránh trùng: "
                  f"{'có' if got.get('diversify_hinted') else 'không'}"]
        if hit:
            lines += [f"* vẫn gần tờ {hit.get('against')}: "
                      f"Jaccard {hit.get('jaccard')}, Hamming {hit.get('hamming')}"]
        lines += [""]
    mended = {k: v for k, v in (got.get("mended") or {}).items() if v}
    if mended:
        lines += ["## Bản vá máy đã chữa trước khi ra cổng", ""]
        lines += [f"* {k}: {v}" for k, v in mended.items()]
        lines += [""]
    if not ok:
        lines += ["## Vì sao cổng loại", ""]
        lines += [f"* {w}" for w in (got.get("why") or [])]
        lines += [""]
    lines += ["## Lời nhờ nó nhận", "", "```", brief.strip(), "```", ""]
    return "\n".join(lines)


def family_of(index: int) -> str:
    """Family của tờ thứ `index` -- quay vòng đều qua cả 30 family.

    MỘT chỗ duy nhất biết luật này. `one()` cần nó để rút plan khi không ai
    đưa sẵn, và `run()` cần nó để rút plan qua `agent/diversity.py` TRƯỚC
    khi gọi `one()`. Hai chỗ tự viết lại `sorted(G.FAMILIES)[index % ...]`
    là đúng cái lỗi AGENTS.md gọi tên: một luật, hai người dựng, và khi hai
    bên lệch thì brief nói một family còn bản ghi khai một family khác."""
    return sorted(G.FAMILIES)[index % len(G.FAMILIES)]


def one(client, index: int, made: list[str], seed: int,
        lang: str = "en", plan: DP.DocumentPlan | None = None,
        avoid: str = "", attempt: int = 1) -> dict:
    """Một tờ: hỏi, đo, gác cổng. Không ném -- lỗi là một kết quả.

    `plan` đưa từ ngoài vào là đường của `run()`: `agent/diversity.py` rút
    nó qua `sample_with_coverage` trên một trí nhớ DÙNG CHUNG cả lô, thứ mà
    một hàm chạy trong một luồng không thể tự có. `None` thì rút tại chỗ
    như cũ -- mọi caller cũ (và mọi test) vẫn chạy y nguyên.

    `avoid` là câu nhắc đa dạng cho lượt sinh lại; `attempt` là lượt thứ
    mấy, ghi vào bản ghi để báo cáo đếm được cái giá của việc sinh lại."""
    started = time.time()
    # Số tờ vẫn quay vòng qua `agent/rate_match.py` (Phase 4 task 4.4) --
    # khái niệm "mấy trang" không nằm trong grammar (Phase 3), độc lập với
    # family đã rút.
    sheets = rate_match.sheet_count(index)
    # PHASE 5 (task 5.1): family + cấu trúc rút từ `agent/grammar.py` qua
    # `agent/document_plan.py`, KHÔNG để model tự nghĩ nữa. `seed + index`
    # giống hệt cách `seals()`/`hands()` bên dưới seed -- an toàn khi chạy
    # song song (`ThreadPoolExecutor` trong `run()`), mỗi `index` một RNG
    # riêng, không có state dùng chung.
    if plan is None:
        rng = random.Random(seed + index)
        plan = DP.sample(G.FAMILIES[family_of(index)], rng)
    # MỰC KHÁC CHO LƯỢT SINH LẠI. `seals()`/`hands()` dưới đây seed bằng
    # `ink_seed`; để nguyên `seed + index` thì tờ sinh lại mang đúng con dấu
    # và đúng nét chữ ký của tờ vừa bị loại vì trùng -- sửa bố cục rồi chép
    # lại mực là sửa một nửa.
    ink_seed = seed + index + 100003 * (attempt - 1)
    brief = ask_for(index, made, plan, sheets, lang, avoid=avoid)
    try:
        answer, usage = client.decide_with_usage(
            system_prompt(),
            brief, schema(),
            # CÙNG mức dày mà `ask_for()` vừa dùng để xin số ký tự -- nếu hai
            # chỗ đọc hai mức khác nhau thì trần lại lệch khỏi mục tiêu, đúng
            # cái `budget()` vừa được sửa để không thể xảy ra nữa.
            max_tokens=budget(sheets, density),
            timeout=patience(sheets, client.timeout, density))
    except LLMError as error:
        spent = round(time.time() - started, 1)
        text = str(error)
        # Phân biệt HẾT HẠN CHỜ với lỗi khác: log tổng hợp phải đếm riêng hai
        # thứ ấy, vì cách chữa khác hẳn nhau -- một bên nới hạn hoặc giảm số
        # request song song, một bên sửa prompt hoặc schema.
        timed_out = "timed out" in text.lower() or "timeout" in text.lower()
        return {"index": index, "archetype": "llm", "ok": False,
                "seconds": spent, "timed_out": timed_out,
                "tokens_in": 0, "tokens_out": 0,
                "why": [f"model không trả lời: {text[:120]}"]}
    spent = round(time.time() - started, 1)
    out_tokens = int(usage.get("completion_tokens") or 0)
    in_tokens = int(usage.get("prompt_tokens") or 0)

    html = str(answer.get("html") or "")
    # `declared` là model TỰ TÓM TẮT nó đã làm gì -- KHÔNG phải nguồn sự
    # thật (điểm 3 review, Phase 5 task 5.2). Đặt tên khác `plan` (biến ở
    # trên, `DocumentPlan` của engine) có chủ đích: hai biến trùng tên từng
    # là cách dễ nhất để lỡ tay validate nhầm bằng bản model tự khai thay vì
    # bản engine đã quyết.
    declared = dict(answer.get("plan") or {})
    # CÂY DỮ LIỆU. Bản trước khai nó trong schema rồi vứt đi -- đo được 0/12 tờ
    # có `data` trong `declared/`, không phải vì model không viết mà vì không
    # ai đọc ra khỏi câu trả lời.
    #
    # `isinstance(tree, dict)` đúng cho SCHEMA CŨ (`"data": {"type": "object"}`,
    # trước 23-09) nhưng sai cho schema hiện tại: `DATA_ITEMS` xin một MẢNG
    # `[{path, value}]` (xem docstring `schema()`), nên `answer["data"]` giờ
    # LUÔN là `list`, không bao giờ là `dict` -- và dòng kiểm cũ âm thầm biến
    # nó thành `{}` trên MỌI tờ kể từ khi schema đổi hình, tái lập đúng cái
    # lỗi 0/12 mà comment trên vừa kể, chỉ khác lý do. `data_path_mismatches`
    # (dưới) đã đọc được cả hai hình từ lâu; chỗ này thì chưa theo kịp.
    tree = answer.get("data")
    tree = tree if isinstance(tree, list) else []
    rows = list(answer.get("rows") or [])
    wrong, total = arithmetic(rows)
    # CHỮA TRƯỚC KHI GÁC. Đo trên pilot6: sáu tờ bị loại, năm tờ trượt vì hai
    # lỗi mà máy chữa được không cần đoán -- `<td>` thiếu `data-cell`, và
    # `<br>` nằm trong span có nhãn. Tỉ lệ đạt 3/9 lên 8/9.
    #
    # Đây không phải nới lỏng cổng gác: cổng vẫn y nguyên, chạy sau, và vẫn
    # loại mọi thứ nó vẫn loại. Chỉ là thôi bắt model làm một việc mười dòng
    # mã làm đúng mọi lần -- đúng ranh giới `synthgen/markup.py` vẫn giữ.
    html, mended = repair(html)
    # DỰNG NỐT DÒNG BẢNG MODEL ĐÃ KHAI.
    #
    # Chạy SAU `repair`: dòng mẫu phải có `data-row`/`data-col` (do
    # `repair.grid` đánh) trước khi nhân bản, nếu không dòng mới thiếu chỗ
    # ngồi và `kie_full` gạt chúng.
    #
    # Model trả hai thứ cho cùng một cái bảng -- mảng `rows` trong JSON và các
    # `<tr>` trong HTML -- và chúng lệch rất xa: đo trên 48 tài liệu, 22 tài
    # liệu khai nhiều dòng hơn vẽ, tệ nhất khai 129 vẽ 18. Chữ đưa vào đây là
    # chữ MODEL ĐÃ VIẾT, không phải chữ engine bịa: xem `repair.rows_out`.
    html, n_rows = rows_out(html, rows)
    if n_rows:
        mended["dòng bảng dựng từ `rows` đã khai"] = n_rows
    # MỰC THẬT vào chỗ model đặt sẵn. Phải chạy TRƯỚC cổng gác: cổng đo trên
    # HTML cuối cùng, không đo trên bản nháp.
    html, stamped = seals(html, seed=ink_seed)
    # Nét chữ ký sau con dấu, cùng một lẽ: model đặt CHỖ, engine điền MỰC.
    html, signed = hands(html, seed=ink_seed)
    mended["dấu thật đã điền"] = stamped
    # `plan_conformance_problems` so HTML với `plan` (ENGINE, authoritative).
    # `plan_problems`/`sheet_plan_problems` vẫn so với `declared` (model tự
    # khai) -- vẫn hữu ích để bắt model tự mâu thuẫn với chính lời nó vừa
    # nói, nhưng không còn là nơi quyết "cấu trúc trang có đúng không".
    # `content_length_problems` gác CHỮ THẬT SỰ có trên trang, không qua lời
    # khai -- `sheet_plan_problems` ở trên chỉ gác `sheet_plan` model tự
    # viết, và đo trên pilot16 (Phase 8) thấy lời khai đủ mà chữ vẫn thiếu.
    found = (problems(html) + plan_problems(declared, html)
             + sheet_plan_problems(declared, sheets)
             + plan_conformance_problems(plan, html))
    # CHỮ NGOÀI MỌI VÙNG BỐ CỤC: đo cho MỌI tờ, loại chỉ khi vượt ngưỡng.
    #
    # Ghi số cho cả tờ qua cổng là chủ ý. Đo trên 40 tờ model viết, tờ ĐÃ QUA
    # cổng có trung vị 10,5% run mồ côi và phân vị 90 là 83,3% -- tệ hơn tờ
    # trượt (4,1% / 83,8%). Không phép kiểm nào đang chạy có tương quan với
    # lỗi này, nên chỉ ghi số cho tờ bị loại thì không ai thấy nó bao giờ.
    #
    # Ngưỡng đọc từ `rulebase/synthgen/_blocks.yaml::gate`, mặc định 1.0 =
    # KHÔNG LOẠI: thiếu file cấu hình phải là "cổng không gác thêm gì", chứ
    # không phải "cổng loại sạch". Siết dần là hạ con số trong YAML sau khi
    # đọc báo cáo -- kho này đã một lần siết luật kế hoạch mà không đo trước,
    # và nó giết 4 trên 6 tờ.
    loose, runs = orphan_share(html)
    share = loose / runs if runs else 0.0
    ceiling = D.gate_ceiling("orphan_share", 1.0)
    if runs and share > ceiling:
        found = found + [
            f"{loose}/{runs} run ({share:.0%}) không nằm trong vùng bố cục nào "
            f"đã khai; ngưỡng {ceiling:.0%}"]
    # `doc_slug` giờ LÀ `plan.family` -- engine đã quyết, không hỏi model
    # nữa (điểm 3 review). `declared.get("doc_slug")` không còn dùng để
    # đặt tên thư mục, chỉ còn trong `declared` để đọc lại lúc gỡ lỗi.
    kind = plan.family
    # XẾP TẦNG, KHÔNG GÁC. Ba tầng của `synthgen/field_tier.py` quyết một
    # TRƯỜNG có vào bộ chính hay không; chúng không quyết một TỜ có được nhận
    # hay không, và `found` ở trên không nhận thêm dòng nào từ đây.
    #
    # Tách hai việc ấy có chủ ý. `field_plan` vốn không vào bộ huấn luyện
    # (xem `plan_problems`), nên loại cả tờ vì một cái tên lạ là trả giá cao
    # nhất cho lỗi rẻ nhất -- đúng cái bẫy `settle()` đã viết ra. Trường lạ
    # rơi xuống `staging`: còn nguyên trên giấy, ghi riêng ra để soát, không
    # đi vào bộ chính, và KHÔNG bao giờ mượn câu tả của một khoá khác.
    doc_title = str(declared.get("doc_title") or "")
    tiers = (FT.classify_plan(declared.get("field_plan"),
                              doc_type=kind, doc_title=doc_title)
             + FT.classify_data(tree, doc_type=kind, doc_title=doc_title))
    return {
        "index": index, "archetype": kind, "ok": not found,
        "seconds": spent, "why": found,
        "field_tiers": FT.tally(tiers),
        "field_staging": FT.staging_rows(tiers),
        "doc_group": FT.doc_group(kind, doc_title),
        "html": html, "rows": rows, "plan": declared,
        "engine_plan": dict(plan.assignment),
        "hard_negative_profile": dict(plan.hard_negative_profile),
        "data": tree,
        "loai_tai_lieu": str(declared.get("doc_kind") or kind),
        "doc_title": str(declared.get("doc_title") or ""),
        "sheets_asked": sheets, "table_asked": "table" in plan.assignment,
        "chars": len(html), "rows_wrong": wrong, "rows_total": total,
        "tokens_in": in_tokens, "tokens_out": out_tokens,
        "tokens_per_second": round(out_tokens / spent, 1) if spent else 0.0,
        "mended": {k: v for k, v in mended.items() if v},
        "orphan_runs": loose, "runs": runs,
        "orphan_share": round(share, 3),
        "brief": brief,
        "stamped": stamped, "signed": signed,
        "attempt": attempt, "diversify_hinted": bool(avoid),
    }



def _tier_tally(made: list[dict]) -> dict:
    """Ba tầng cộng lại cả bộ, cộng phân bố nhóm loại chứng từ.

    Cộng từ `field_tiers` của từng tờ thay vì xếp tầng lại lần nữa: xếp lại là
    người thứ hai dựng cùng một luật, và nếu hai bên lệch thì báo cáo nói một
    đằng bản ghi một nẻo -- không có cách nào nhìn ra điều đó từ con số."""
    counts: dict[str, int] = {}
    total = generic = in_batch = 0
    groups: dict[str, int] = {}
    for m in made:
        got = m.get("field_tiers") or {}
        for tier, n in (got.get("counts") or {}).items():
            counts[tier] = counts.get(tier, 0) + int(n)
        total += int(got.get("total") or 0)
        generic += int(got.get("generic") or 0)
        in_batch += int(got.get("in_batch") or 0)
        group = str(m.get("doc_group") or "")
        if group:
            groups[group] = groups.get(group, 0) + 1
    return {"total": total, "counts": counts,
            "share": {tier: (round(n / total, 4) if total else 0.0)
                      for tier, n in counts.items()},
            "generic": generic,
            "generic_share": round(generic / total, 4) if total else 0.0,
            "in_batch": in_batch,
            "in_batch_share": round(in_batch / total, 4) if total else 0.0,
            "doc_groups": groups}


def _mend_tally(made: list[dict]) -> dict[str, int]:
    """Bản vá máy đã chữa những gì, tổng cộng bao nhiêu chỗ."""
    tally: dict[str, int] = {}
    for m in made:
        for k, v in (m.get("mended") or {}).items():
            tally[k] = tally.get(k, 0) + v
    return tally


def _why_tally(made: list[dict]) -> dict[str, int]:
    """Lý do trượt, gộp theo DẠNG chứ không theo câu chữ.

    "10 ô bảng thiếu `data-cell`" và "14 ô bảng thiếu `data-cell`" là MỘT lỗi.
    Đếm chúng riêng ra thì bảng xếp hạng nói về số ô, không nói về số lỗi -- và
    thứ cần sửa là cái lỗi."""
    tally: dict[str, int] = {}
    for m in made:
        for why in (m.get("why") or []):
            key = re.sub(r"\d+", "N", str(why)).split(";")[0][:70]
            tally[key] = tally.get(key, 0) + 1
    return dict(sorted(tally.items(), key=lambda kv: -kv[1]))


def _diversity_lines(div: dict) -> list[str]:
    """Phần "Đa dạng" của `performance.md`.

    Tách khỏi `_write_performance` vì nó trả lời một câu khác hẳn phần còn
    lại của file ấy: không phải "lượt này chạy nhanh chậm ra sao" mà "lô này
    có đang tự lặp lại không". Con số cần đọc được khi NHÂN LÊN -- một lô 30
    tờ hơi lặp và một lô 20 000 tờ hơi lặp là hai chuyện khác nhau -- nên
    mọi dòng dưới đây là tỉ lệ hoặc phân vị, không phải số đếm trần.

    Rỗng khi không có khoá `diversity` (báo cáo của một lượt chạy cũ đọc lại
    bằng mã mới): thiếu số không phải lỗi, nhưng bịa số thì là."""
    if not div:
        return []
    geo = div.get("geometry") or {}
    plans = div.get("plan_fingerprints") or {}
    near = geo.get("nearest_jaccard") or {}
    regen = div.get("regeneration") or {}
    pages = div.get("pages_measured", 0)
    lines = [
        "## Đa dạng", "",
        f"Gác: {'BẬT' if div.get('enabled') else 'TẮT (chỉ đo, không loại)'}"
        f"  ·  cửa sổ {div.get('window')} tờ"
        f"  ·  ngưỡng Jaccard {div.get('jaccard_ceiling')}"
        f"  ·  lưới {geo.get('grid')}",
        "",
        "| | |", "|---|---|",
        f"| Tờ đo được hình học | {pages} |",
        f"| Loại vì trùng bố cục | **{div.get('rejected_for_collision', 0)}** "
        f"({100 * div.get('rejected_share', 0.0):.1f}% số lượt sinh) |",
        f"| Nhận dù vẫn trùng (hết lượt) | {div.get('kept_despite_collision', 0)} |",
        f"| Chưa đo được hình học | {div.get('geometry_unavailable', 0)} |",
        f"| Plan đã rút (kể cả rút lại) | {div.get('plans_drawn', 0)} |",
        f"| Plan rút cạn vẫn trùng `fine` | {div.get('plan_collisions', 0)} |",
        "",
        "### Tờ gần nhất trong cửa sổ",
        "",
        "Jaccard trên tập ô `(tờ, nhãn lớp, cột, hàng)`. 1,0 là trùng khít.",
        "",
        "| | |", "|---|---|",
        f"| Trung vị | {near.get('median')} |",
        f"| Phân vị 90 | {near.get('p90')} |",
        f"| Lớn nhất | {near.get('max')} |",
        f"| Còn vượt ngưỡng sau khi gác | {geo.get('over_ceiling')} / "
        f"{geo.get('documents')} ({100 * geo.get('over_ceiling_share', 0.0):.1f}%) |",
        f"| Tập ô khác nhau | {geo.get('distinct_cell_sets')} / "
        f"{geo.get('documents')} |",
        "",
    ]
    histogram = geo.get("jaccard_histogram") or {}
    if any(histogram.values()):
        widest = max(histogram.values())
        lines += ["| Khoảng Jaccard | Số tờ | |", "|---|---|---|"]
        lines += [f"| {k} | {v} | {'█' * round(18 * v / max(widest, 1))} |"
                 for k, v in histogram.items()]
        lines += [""]
    lines += [
        "### Dấu vân plan (coarse/mid/fine)",
        "",
        f"* {plans.get('distinct_coarse')} coarse / {plans.get('distinct_mid')} "
        f"mid / {plans.get('distinct_fine')} fine khác nhau trên "
        f"{plans.get('documents')} tờ",
        f"* khoảng cách trung bình mỗi cặp: "
        f"{plans.get('mean_pairwise_distance')} (1,0 = khác cả ba tầng)",
        "",
    ]
    if regen.get("calls"):
        lines += [
            "### Cái giá của việc sinh lại", "",
            f"{regen['calls']} lời gọi bị vứt, {regen['seconds']}s và "
            f"{regen['tokens_out']} token ra -- "
            f"{100 * regen.get('share_of_seconds', 0.0):.1f}% tổng thời gian "
            "model làm việc.", ""]
    return lines


def _write_performance(out: Path, report: dict, made: list[dict]) -> None:
    """`performance.md` -- một trang đọc được bằng mắt, và `calls.jsonl`.

    `compose_report.json` đã có đủ số, nhưng nó là JSON: mở ra để trả lời "lượt
    này chạy thế nào" thì phải tự cộng trong đầu. File này trả lời sẵn, và nó
    tồn tại vì người dùng hỏi đúng câu ấy -- vào/ra, token vào/ra, thời gian,
    số lần hết hạn chờ, số ca hỏng.

    `calls.jsonl` là một dòng một lời gọi: dùng khi cần so hai lượt với nhau
    hoặc dựng biểu đồ, thứ mà một file markdown không làm được."""
    pages = sorted(made, key=lambda m: m["index"])
    # MỘT DÒNG MỘT LỜI GỌI -- kể cả lời gọi đã bị VỨT vì tờ trùng bố cục.
    # Tên file hứa "một dòng một lời gọi", và một lượt sinh lại là một lời
    # gọi thật, tốn thật; bỏ nó ra thì ai dựng biểu đồ từ file này thấy một
    # lượt chạy rẻ hơn lượt chạy đã xảy ra. `discarded: true` để lọc ra được.
    dropped = ((report.get("diversity") or {}).get("regeneration") or {}
              ).get("discarded") or []
    with (out / "calls.jsonl").open("w", encoding="utf-8") as fh:
        for m in pages:
            fh.write(json.dumps(
                {k: v for k, v in m.items() if k not in ("html", "rows", "plan")},
                ensure_ascii=False) + "\n")
        for row in sorted(dropped, key=lambda r: (r["index"], r["attempt"])):
            fh.write(json.dumps(dict(row, discarded=True, ok=False),
                               ensure_ascii=False) + "\n")

    secs = sorted(m.get("seconds", 0) for m in pages)
    outs = sorted(m.get("tokens_out", 0) for m in pages if m.get("tokens_out"))
    mid = lambda v: v[len(v) // 2] if v else 0                    # noqa: E731
    kept = [m for m in pages if m["ok"]]
    lines = [
        f"# Hiệu năng lượt sinh -- {report['when']}",
        "",
        f"* **Model** `{report['model']}` tại `{report['url']}`",
        f"* **Lời dặn** bằng `{report.get('lang')}`"
        f" (`agent/guideline/SYSTEM_PROMPT.md` +"
        f" `agent/prompts/{PROMPT_OF.get(report.get('lang'), 'page')}.md`)",
        f"* **Song song** {report['concurrency']} request",
        "",
        "## Kết quả",
        "",
        "| | |",
        "|---|---|",
        f"| Xin | {report['asked']} tờ |",
        f"| Qua cổng | **{report['kept']}** "
        f"({100 * report['kept'] / max(report['asked'], 1):.0f}%) |",
        f"| Trượt cổng | {len(pages) - len(kept) - report['timed_out']} |",
        f"| Hết hạn chờ / không trả lời | {report['timed_out']} |",
        f"| Chưa chạy tới | {report['asked'] - len(pages)} |",
        "",
        "## Thời gian",
        "",
        "| | |",
        "|---|---|",
        f"| Tổng | {report['seconds']}s |",
        f"| Mỗi tờ (gộp cả song song) | {report['seconds_per_page']}s |",
        f"| Một lời gọi, trung vị | {mid(secs)}s |",
        f"| Một lời gọi, nhanh nhất / chậm nhất | "
        f"{secs[0] if secs else 0}s / {secs[-1] if secs else 0}s |",
        "",
        "## Token",
        "",
        "| | |",
        "|---|---|",
        f"| Vào, tổng | {report['tokens_in']} |",
        f"| Ra, tổng | {report['tokens_out']} |",
        f"| Ra, mỗi tờ trung vị | {mid(outs)} |",
        f"| Ra, nhỏ nhất / lớn nhất | "
        f"{outs[0] if outs else 0} / {outs[-1] if outs else 0} |",
        f"| Tốc độ gộp | {report['tokens_per_second']} tk/s |",
        f"| Ký tự HTML, trung vị | {report['median_chars']} |",
        "",
    ]
    if report["tokens_per_second"]:
        hours = (report["tokens_out_per_page"] * 20000
                 / report["tokens_per_second"] / 3600)
        lines += [f"Suy ra: **20 000 tờ ≈ {hours:.1f} giờ** ở tốc độ và mức "
                  f"song song này.", ""]
    if report["mended"]:
        lines += ["## Bản vá máy đã chữa", "",
                  "Những lỗi này KHÔNG tính là trượt -- `synthgen/repair.py` "
                  "sửa xong trước khi ra cổng.", "", "| Việc | Số chỗ |",
                  "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in report["mended"].items()]
        lines += [""]
    if report["why_tally"]:
        lines += ["## Vì sao trượt", "", "| Lý do | Số tờ |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in report["why_tally"].items()]
        lines += [""]
    lines += _diversity_lines(report.get("diversity") or {})
    kinds_made = [m.get("loai_tai_lieu") or m["archetype"] for m in pages]
    lines += ["## Loại chứng từ model tự nghĩ ra", "",
              f"{len(set(kinds_made))} loại khác nhau trên {len(pages)} tờ.", ""]
    lines += [f"* {'✓' if m['ok'] else '✗'} `{m['archetype']}` -- "
              f"{m.get('loai_tai_lieu') or ''}" for m in pages]
    (out / "performance.md").write_text("\n".join(lines) + "\n",
                                        encoding="utf-8")



class Artist(threading.Thread):
    """Thợ vẽ: một luồng, một trình duyệt, vẽ ngay khi HTML vừa ghi ra đĩa.

    Bản trước vẽ ở CUỐI lượt, sau khi hai mươi tư tờ đã xong. Hai cái giá:
    tấm ảnh đầu tiên phải đợi cả lượt (pilot7 mất mười chín phút), và một lượt
    gãy giữa chừng không để lại tấm nào -- đúng cái đã xảy ra ở pilot5.

    Vẽ xen kẽ còn KHÔNG tốn thêm thời gian: lượt sinh dành gần hết thời gian
    ngồi đợi server trả lời, nên vẽ (khoảng một giây một tờ) lấp vào chỗ trống
    ấy. Xong tờ cuối là xong cả ảnh.

    MỘT luồng, không phải bốn: `playwright` bản đồng bộ gắn với luồng tạo ra
    nó, nên nhiều luồng cùng vẽ là hỏng. Một luồng là đủ -- vẽ nhanh hơn sinh
    hai trăm lần."""

    def __init__(self, out: Path) -> None:
        super().__init__(daemon=True)
        self.out = out
        self.queue: queue.Queue = queue.Queue()
        self.rows: list[dict] = []
        self.started_ok = False
        self.why = ""

    def put(self, path: Path, passed: bool) -> None:
        self.queue.put(("draw", path, passed))

    def measure(self, html: str, stem: str, archetype: str = "llm",
                timeout: float = 300.0) -> dict | None:
        """Dàn tờ này CHỈ ĐỂ ĐO, trả bản ghi. Gọi từ luồng sinh, chặn tới khi
        thợ vẽ xong.

        ## Vì sao đi qua thợ vẽ chứ không tự mở trình duyệt

        `playwright` bản đồng bộ gắn trình duyệt với LUỒNG đã tạo ra nó (đúng
        lý do lớp này chỉ có một luồng vẽ). Một `ThreadPoolExecutor` sáu
        luồng sinh mà mỗi luồng tự mở Chromium là sáu trình duyệt, chừng
        900 MB, cho một việc tốn một tới ba giây một tờ. Nên hỏi thợ vẽ, và
        thợ vẽ trả lời theo thứ tự nhận được.

        Chặn KHÔNG phải là nút thắt: một tờ mất 110-430 giây để model viết ra
        và một tới ba giây để dàn, nên ở mức song song 3-8 request thì thợ vẽ
        rảnh gần như suốt.

        `None` -- không có thợ vẽ, thợ vẽ đã chết, dàn không ra, hay quá hạn
        chờ. Caller PHẢI đọc nó là "chưa đo được", không phải "không trùng":
        loại một tờ vì phép đo hỏng là đánh đổi một lỗi lặng lẽ lấy một lỗi
        lặng lẽ khác, đắt hơn."""
        if not self.is_alive() or self.why:
            return None
        slot: dict = {"record": None, "done": threading.Event()}
        self.queue.put(("measure", html, stem, archetype, slot))
        if not slot["done"].wait(timeout):
            return None
        return slot["record"]

    def close(self) -> None:
        """Báo hết việc rồi đợi vẽ nốt."""
        self.queue.put(None)
        self.join()

    def run(self) -> None:                                  # noqa: D102
        from synthgen import draw_llm  # noqa: PLC0415

        try:
            drawer_cm = draw_llm.Drawer(self.out)
        except Exception as error:                          # noqa: BLE001
            self.why = f"{type(error).__name__}: {error}"
            self._drain()
            return
        try:
            with drawer_cm as drawer:
                self.started_ok = True
                while True:
                    job = self.queue.get()
                    if job is None:
                        break
                    # ĐO XONG MỚI TRẢ LỜI, và trả lời BẰNG MỌI GIÁ: một luồng
                    # sinh đang đứng đợi `slot["done"]`. Ngoại lệ ở đây mà
                    # không `set()` thì luồng ấy treo tới hết `timeout` --
                    # `try/finally` là chỗ duy nhất luật ấy đọc được.
                    if job[0] == "measure":
                        _kind, html, stem, archetype, slot = job
                        try:
                            slot["record"] = drawer.measure(html, stem, archetype)
                        except Exception:                   # noqa: BLE001
                            slot["record"] = None
                        finally:
                            slot["done"].set()
                        continue
                    _kind, path, passed = job
                    try:
                        line, _ok = drawer.draw(path, passed)
                    except Exception as error:              # noqa: BLE001
                        line = f"  ✗ {path.stem}: {type(error).__name__}: {error}"
                    print(f"[vẽ]{line}", flush=True)
                self.rows = drawer.rows
        except Exception as error:                          # noqa: BLE001
            # Vẽ hỏng KHÔNG được làm hỏng lượt sinh: HTML và báo cáo đã nằm
            # trên đĩa rồi, và chúng là thứ đắt. Nói ra rồi đi tiếp.
            self.why = f"{type(error).__name__}: {error}"
            self._drain()

    def _drain(self) -> None:
        """Nuốt nốt hàng đợi để `close()` không treo khi thợ vẽ đã chết.

        Việc đo cũng phải được ĐÁNH THỨC, không chỉ nuốt: một luồng sinh
        đang `wait()` trên `slot["done"]` của một việc chưa ai làm sẽ đứng
        đủ `timeout` giây rồi mới đi tiếp, và với mười tờ còn lại trong hàng
        đợi thì đó là năm mươi phút im lặng sau khi thợ vẽ đã chết."""
        while True:
            job = self.queue.get()
            if job is None:
                return
            if job[0] == "measure":
                job[-1]["done"].set()


def _draw(out: Path) -> None:
    """Vẽ ảnh hộp bố cục và KIE cho lượt vừa sinh.

    Chạy bằng SUBPROCESS chứ không `import`: trình thông dịch có `playwright`
    thường không phải trình thông dịch đang chạy hàm này."""
    exe = drawing_python()
    if exe is None:
        print("[trang] không môi trường nào có `playwright`, nên không vẽ "
              "được ảnh. Cài vào một môi trường rồi chạy:\n"
              f"  <python có playwright> -m synthgen.draw_llm {out}")
        return
    print(f"\n[trang] vẽ ảnh kiểm tra (hộp bố cục + KIE) bằng {exe}...")
    done = subprocess.run([exe, "-m", "synthgen.draw_llm", str(out)],
                          cwd=str(Path(__file__).resolve().parents[1]),
                          check=False)
    if done.returncode:
        # Vẽ hỏng KHÔNG được làm hỏng lượt sinh: HTML và báo cáo đã nằm trên
        # đĩa rồi, và chúng là thứ đắt. Nói ra rồi đi tiếp.
        print(f"[trang] vẽ hỏng (mã {done.returncode}); HTML vẫn còn -- "
              f"chạy lại bằng:\n  {exe} -m synthgen.draw_llm {out}")


def broken(index: int, error: BaseException) -> dict:
    """Bản ghi thay thế cho một tờ mà lượt gọi VỠ, không chỉ trượt cổng.

    Hình dạng phải khớp `one()` từng khoá một: vòng in ngay sau đó đọc
    `archetype`, `seconds`, `tokens_out`, `rows_total`, `why[0]`, và
    `_why_tally`/`failures.tally` đọc tiếp. Thiếu một khoá thì ta đổi một
    ngoại lệ lấy một `KeyError` -- cùng hậu quả, khó lần hơn.

    Vì sao cần: `future.result()` ném lại đúng ngoại lệ worker đã gặp. Không
    ai bắt thì một lỗi lạ ở tờ thứ tư làm mất CẢ LƯỢT, kể cả những tờ đã vẽ
    xong. Đo được: một lô 12 tờ chết vì `http.client.IncompleteRead` ở tờ thứ
    tư, và ba tờ sinh trước đó mất theo vì `run()` không bao giờ tới bước ghi
    báo cáo.

    Lỗi đường truyền ĐÃ BIẾT thì `agent/client.py` chắn. Hàm này chắn lỗi
    CHƯA BIẾT -- và đó mới là việc của nó."""
    return {
        "index": index, "archetype": "llm", "ok": False,
        "seconds": 0.0, "chars": 0,
        "why": [f"lượt gọi vỡ: {type(error).__name__}: {error}"],
        "html": "", "rows": [], "plan": {}, "data": [],
        "engine_plan": {}, "hard_negative_profile": {},
        "loai_tai_lieu": "", "doc_title": "",
        "sheets_asked": 1, "table_asked": False,
        "rows_wrong": 0, "rows_total": 0,
        "tokens_in": 0, "tokens_out": 0, "tokens_per_second": 0.0,
        "mended": {}, "orphan_runs": 0, "runs": 0, "orphan_share": 0.0,
        "brief": "", "stamped": 0, "signed": 0,
        "attempt": 1, "diversify_hinted": False,
    }


def run(want: int, out: Path, *, concurrency: int, seed: int,
        lang: str = "en", no_draw: bool = False,
        diversity: bool = True, steer: bool = True,
        window: int = GD.WINDOW,
        ceiling: float = GD.JACCARD_CEILING,
        attempts: int = DIV.MAX_ATTEMPTS) -> int:
    # Sáu trăm giây cho MỘT tờ. Viết một trang HTML là việc dài nhất kho này
    # nhờ model làm: đo được 5 400 token ở 15 tok/s khi bốn request chạy cùng
    # lúc, tức 360 giây -- vượt hạn mặc định 120 giây, và `_post` thử lại ba
    # lần nên một tờ nghẹn mất 364 giây rồi vẫn hỏng.
    # Trần 9 000 token đầu ra. Trung vị một tờ là 4 685 token HTML cộng `plan`
    # và `rows`, nên 9 000 là rộng rãi cho cả tờ sáu trang -- nó chỉ chặn ca
    # model lan man, thứ vốn tiêu 360 giây rồi vẫn hỏng.
    client = from_env(timeout=float(os.environ.get("VLM_LLM_TIMEOUT", 600)),
                      max_tokens=int(os.environ.get("VLM_LLM_MAX_TOKENS", 9000)))
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

    print(f"[trang] {want} tờ, {concurrency} request song song, "
          f"model {client.model}")
    print(f"[trang] engine chọn family + cấu trúc ({len(G.FAMILIES)} family, "
          "agent/grammar.py); model hiện thực hoá nội dung (Phase 5)")
    out.mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(exist_ok=True)
    (out / "rejected").mkdir(exist_ok=True)
    (out / "thinking").mkdir(exist_ok=True)
    (out / "declared").mkdir(exist_ok=True)

    started = time.time()
    made: list[dict] = []
    # Những loại đã làm, để lời nhờ tiếp theo đẩy model sang chỗ khác. Dùng
    # chung giữa các luồng nên có khoá -- danh sách này đọc ở mỗi lần hỏi.
    kinds_made: list[str] = []
    lock = threading.Lock()
    # Lời gọi đã VỨT vì tờ trùng bố cục. Giữ giá của chúng (giây, token) để
    # báo cáo không nói dối về chi phí: `made` chỉ còn tờ cuối cùng của mỗi
    # chỉ số, nên cộng token trên `made` một mình là bỏ quên đúng phần mà
    # phép chống trùng lặp bắt lượt chạy trả thêm.
    discarded: list[dict] = []

    # TRÍ NHỚ ĐA DẠNG CỦA CẢ LÔ, không của một luồng.
    #
    # `agent/coverage.py` + `agent/fingerprint.py` viết xong từ Phase 4, có
    # test, và cho tới đây KHÔNG CHỖ NÀO GỌI: `one()` rút plan bằng
    # `DP.sample()` trần trên một RNG riêng cho mỗi `index`, nên mỗi tờ là
    # một lần bốc độc lập và không gì trong lượt chạy nhớ những tờ trước đã
    # dùng cấu hình nào. `agent/diversity.py` là người gọi còn thiếu ấy.
    warden = DIV.DiversityWarden(enabled=diversity, steer=steer, window=window,
                                ceiling=ceiling)
    if not diversity or not steer:
        print(f"[đa dạng] rút có trí nhớ: {'BẬT' if steer else 'TẮT'}  ·  "
              f"loại tờ trùng: {'BẬT' if diversity else 'TẮT'}  -- vẫn ĐO đủ "
              "mọi con số (nhánh đối chứng của phép thử A/B)")
    if no_draw:
        print("[đa dạng] `--no-draw`: không có thợ vẽ nên không đo được hình "
              "học; chỉ còn tầng plan (coverage + fingerprint) gác")

    def measure_geometry(html: str, stem: str, archetype: str):
        """Dấu vân hình học của tờ vừa viết, hoặc `None` khi chưa đo được.

        `None` KHÔNG phải "không trùng" -- xem `Artist.measure`. Caller nhận
        tờ giấy khi chưa đo được, và `metrics()` đếm riêng ở
        `geometry_unavailable` để con số ấy không lẫn vào tỉ lệ trùng."""
        if artist is None or not html:
            return None
        record = artist.measure(html, stem, archetype)
        if not record:
            return None
        return geometry_fingerprint(record.get("layout_annotations") or [])

    def work(index: int) -> dict:
        family = family_of(index)
        grammar = G.FAMILIES[family]
        # MỘT RNG cho cả chuỗi lượt của tờ này, không một RNG mỗi lượt: lượt
        # sinh lại phải rút được một plan KHÁC, và một RNG dựng lại từ cùng
        # `seed + index` thì rút lại đúng cái vừa bị loại.
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
                # Trượt cổng chữ thì chưa bao giờ tới phép đo hình học, nên
                # không ghi vào trí nhớ nào: một tờ không vào bộ không được
                # quyền chiếm một chỗ trong cửa sổ so trùng.
                break
            stem = f"llm_{got['archetype']}_{index:04d}"
            geo = measure_geometry(got.get("html") or "", stem, got["archetype"])
            # XEM VÀ GHI TRONG MỘT NHỊP. Hỏi rồi mới ghi là chỗ hai tờ xong
            # cùng lúc cùng nhìn một cửa sổ chưa có tờ kia -- xem
            # `DiversityWarden.judge`. Lượt cuối thì `force`: vẫn đo, vẫn ghi
            # lại là trùng, nhưng nhận -- một lô thiếu trang vì quá khó chiều
            # là một lô hỏng theo cách khác.
            collision, taken = warden.judge(
                plan_fp, geo, key=index, attempt=attempt,
                force=attempt >= max(1, attempts))
            if collision is not None:
                got["collision"] = collision.as_dict()
            if not taken:
                avoid = collision.hint
                print(f"  ↻ {index:3d}  {got['archetype']:22s} trùng bố cục "
                      f"tờ {collision.against} (J={collision.jaccard:.2f}, "
                      f"H={collision.hamming:.2f}) -- sinh lại", flush=True)
                with lock:
                    discarded.append({
                        "index": index, "attempt": attempt,
                        "archetype": got["archetype"],
                        "seconds": got.get("seconds", 0.0),
                        "tokens_in": got.get("tokens_in", 0),
                        "tokens_out": got.get("tokens_out", 0),
                        "jaccard": round(collision.jaccard, 4),
                        "hamming": round(collision.hamming, 4),
                        "against": collision.against})
                continue
            break
        with lock:
            if got.get("loai_tai_lieu"):
                kinds_made.append(got["loai_tai_lieu"])
        return got

    artist: Artist | None = None
    if not no_draw:
        for name in ("html", "rejected", "declared", "thinking"):
            (out / name).mkdir(parents=True, exist_ok=True)
        artist = Artist(out)
        artist.start()

    with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(work, i): i for i in range(want)}
        for future in cf.as_completed(futures):
            # MỘT TỜ HỎNG KHÔNG ĐƯỢC GIẾT MƯỜI MỘT TỜ KIA.
            #
            # `future.result()` ném lại đúng ngoại lệ worker đã gặp, và ở đây
            # nó không có ai bắt -- nên một lỗi lạ ở tờ thứ tư làm mất cả lượt
            # chạy, kể cả những tờ đã vẽ xong. Đo được: một lô 12 tờ chết vì
            # `http.client.IncompleteRead` ở tờ thứ tư, và ba tờ đã sinh trước
            # đó cũng mất theo vì `run()` không bao giờ tới bước ghi báo cáo.
            #
            # `client.py` đã chắn những lỗi đường truyền ĐÃ BIẾT. Nhánh này
            # chắn những lỗi CHƯA BIẾT, và đó mới là việc của nó: lỗi đã biết
            # thì sửa ở chỗ nó sinh ra, lỗi chưa biết thì phải không được làm
            # mất phần việc đã xong.
            index = futures[future]
            try:
                got = future.result()
            except Exception as error:                       # noqa: BLE001
                got = broken(index, error)
            made.append(got)
            mark = "✓" if got["ok"] else "✗"
            note = "" if got["ok"] else f"  {got['why'][0][:70]}"
            arith = (f"  số học {got['rows_wrong']}/{got['rows_total']} sai"
                     if got.get("rows_total") else "")
            cost = (f"  {got['tokens_out']}tk {got['tokens_per_second']}tk/s"
                    if got.get("tokens_out") else "")
            print(f"  {mark} {len(made):3d}/{want}  {got['archetype']:22s} "
                  f"{got['seconds']:5.1f}s{cost}{arith}{note}", flush=True)
            # GIỮ CẢ TRANG TRƯỢT. Bản đầu chỉ lưu trang qua cổng, nên 21
            # trang hỏng biến mất cùng lý do của chúng -- không soi được model
            # sai ở đâu, không sửa được lời dặn, và không chạy lại cổng trên
            # chúng sau khi cổng đổi. Một phép thử vứt đi mọi ca hỏng là một
            # phép thử chỉ nhìn thấy cái nó đã đúng.
            #
            # `html/` là trang qua cổng, `rejected/` là trang trượt: tách thư
            # mục chứ không tách bằng tên, để `synthgen/draw_llm.py` vẽ cả hai
            # mà `synthgen/run.py` chỉ lấy thư mục đầu.
            stem = f"llm_{got['archetype']}_{got['index']:04d}"
            # `.get`, không `[...]`. Một tờ mà model KHÔNG trả lời (hết hạn
            # chờ) không có khoá `html` nào, và bản trước lấy `got["html"]`
            # thẳng tay -- nên một request hết hạn ở tờ thứ mười lăm giết cả
            # lượt chạy, và mười bốn tờ đã xong đi theo. Một lượt sinh phải
            # sống sót qua một lần server nghẹn.
            folder = "html" if got["ok"] else "rejected"
            if got.get("html"):
                (out / folder / f"{stem}.html").write_text(got["html"],
                                                          encoding="utf-8")
            # NHẬT KÝ TƯ DUY, một tệp một tờ. Viết cho cả tờ đạt lẫn tờ
            # trượt: so hai cái cạnh nhau là cách nhanh nhất thấy khác biệt.
            if got.get("brief"):
                (out / "thinking" / f"{stem}.md").write_text(
                    thinking(got, got["brief"]), encoding="utf-8")
            (out / "declared" / f"{stem}.json").write_text(
                json.dumps({"loai_tai_lieu": got.get("loai_tai_lieu", ""),
                            # KẾ HOẠCH model tự viết, giữ nguyên. Đây là chỗ
                            # đọc được nó NGHĨ gì trước khi vẽ -- và khi một
                            # trang trượt, so kế hoạch với HTML nói ngay nó
                            # hiểu sai ở bước nào.
                            "plan": got.get("plan") or {},
                            # Cây dữ liệu model viết TRƯỚC khi bày trang. Giữ
                            # nguyên: nó là sự thật của tờ giấy, và `data-path`
                            # trong HTML trỏ về đây.
                            "data": got.get("data") or {},
                            "doc_title": got.get("doc_title", ""),
                            # `archetype` là SLUG do ta chọn, không phải tên
                            # model tự đặt: `loai_tai_lieu` nó trả về là chữ
                            # tự do tiếng Việt ("Tờ khai báo y tế / Phiếu khai
                            # báo dịch tễ"), và dùng nó làm tên thư mục thì
                            # dấu gạch chéo cắt đường dẫn làm đôi.
                            "archetype": got["archetype"],
                            # SỐ TỜ ĐÃ XIN. Từ khi máy cắt theo bề dài A4,
                            # model không quyết số tờ nữa -- nó quyết LƯỢNG
                            # CHỮ. Ghi con số đã xin để bước vẽ nói được "xin 4
                            # -> cắt ra 2": cách duy nhất thấy model viết thiếu.
                            "sheets_asked": got.get("sheets_asked", 1),
                            # SỐ TỜ ĐÃ XIN. Từ khi máy cắt theo bề dài A4,
                            # model không quyết số tờ nữa -- nó quyết LƯỢNG
                            # CHỮ. Ghi con số đã xin ở đây để bước vẽ nói được
                            # "xin 4 tờ, cắt ra 2": đó là cách duy nhất thấy
                            # model viết thiếu, vì trang nào cũng qua cổng dù
                            # ngắn hay dài.
                            "sheets_asked": got.get("sheets_asked", 1),
                            "rows": got.get("rows") or [],
                            "ok": got["ok"], "why": got["why"]},
                           ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
            # VẼ NGAY. `declared/` phải ghi TRƯỚC: `Drawer.draw` đọc nó để lấy
            # `archetype` làm tên thư mục và `why` để in kèm.
            if artist is not None and got.get("html"):
                artist.put(out / folder / f"{stem}.html", got["ok"])

    spent = time.time() - started

    # ĐÓNG THỢ VẼ TRƯỚC KHI CHỐT BÁO CÁO, không sau. `artist.rows` chỉ đầy đủ
    # sau khi luồng vẽ xử lý xong toàn bộ hàng đợi (`Artist.close()` gọi
    # `join()`), và `_reconcile_sheet_count` cần đúng dữ liệu ấy để sửa `made`
    # TRƯỚC khi `kept`/`report` được tính từ nó -- tính trước rồi sửa sau thì
    # báo cáo đã chốt sai số liệu, sửa `made` xong cũng vô nghĩa.
    if artist is not None:
        artist.close()
        actual_pages: dict[str, int] = {}
        for row in artist.rows:
            doc = row.get("document")
            if doc:
                actual_pages[doc] = max(actual_pages.get(doc, 0),
                                        int(row.get("pages_in_document") or 1))
        flipped = _reconcile_sheet_count(made, actual_pages)
        for stem in flipped:
            src = out / "html" / f"{stem}.html"
            if src.is_file():
                (out / "rejected").mkdir(parents=True, exist_ok=True)
                src.rename(out / "rejected" / f"{stem}.html")
        if flipped:
            print(f"[trang] {len(flipped)} tờ qua cổng chữ nhưng dàn trang "
                  f"thật thiếu hẳn -- chuyển sang rejected/: "
                  + ", ".join(flipped[:5])
                  + (" ..." if len(flipped) > 5 else ""))

    kept = [m for m in made if m["ok"]]
    wrong = sum(m.get("rows_wrong", 0) for m in made)
    total = sum(m.get("rows_total", 0) for m in made)
    # TOKEN CỦA CẢ NHỮNG LỜI GỌI ĐÃ VỨT. `made` chỉ giữ lượt cuối của mỗi
    # chỉ số, nên cộng riêng nó là báo cáo một cái giá rẻ hơn cái giá đã trả
    # -- và đúng con số ấy đi thẳng vào phép suy "20 000 tờ ≈ N giờ".
    out_tokens = (sum(m.get("tokens_out", 0) for m in made)
                 + sum(d["tokens_out"] for d in discarded))
    in_tokens = (sum(m.get("tokens_in", 0) for m in made)
                + sum(d["tokens_in"] for d in discarded))
    report = {
        "asked": want, "kept": len(kept),
        "seconds": round(spent, 1),
        "seconds_per_page": round(spent / max(want, 1), 1),
        # TOKEN, không chỉ giây. Giây một mình không ước lượng được một lượt
        # hai mươi nghìn trang: cùng một khoảng thời gian che cả một trang ngắn
        # lúc server rảnh lẫn một trang dài lúc server bận. Token thì không.
        "tokens_out": out_tokens,
        "tokens_in": in_tokens,
        # Mẫu số là số tờ GIAO RA, không số lời gọi: câu hỏi "20 000 tờ mất
        # bao lâu" hỏi về tờ giao ra, và một tờ tốn hai lời gọi thì nó tốn
        # gấp đôi -- đúng cái con số này phải nói.
        "tokens_out_per_page": round(out_tokens / max(len(made), 1)),
        "tokens_per_second": round(out_tokens / max(spent, 1e-6), 1),
        "concurrency": concurrency,
        "model": client.model, "url": client.url,
        "rows_wrong": wrong, "rows_total": total,
        "arithmetic_error_rate": round(wrong / total, 4) if total else None,
        "median_chars": sorted(m.get("chars", 0) for m in made)[len(made) // 2]
        if made else 0,
        "when": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages": [{k: v for k, v in m.items() if k not in ("html", "rows")}
                  for m in sorted(made, key=lambda m: m["index"])],
    }
    report["lang"] = lang
    report["timed_out"] = sum(1 for m in made if m.get("timed_out"))
    report["mended"] = _mend_tally(made)
    # ĐO THEO TRANG, KHÔNG CHỈ THEO BỘ. Một con số cả bộ che mất hình dạng:
    # đo trên 39 tờ, tỉ lệ mồ côi cả bộ là 11,6% trong khi trung vị từng tờ là
    # 4% và phân vị 90 là 83% -- phân bố lưỡng cực, một phần ba số tờ sạch
    # tuyệt đối còn một phần tư hỏng nặng. Con số cả bộ một mình nói rằng mọi
    # tờ hơi kém, và đó là câu sai.
    shares = sorted(m.get("orphan_share", 0.0) for m in made if m.get("runs"))
    if shares:
        loose = sum(m.get("orphan_runs", 0) for m in made)
        runs = sum(m.get("runs", 0) for m in made)
        report["orphan"] = {
            "runs_loose": loose, "runs_total": runs,
            "share_corpus": round(loose / runs, 4) if runs else 0.0,
            "share_median": shares[len(shares) // 2],
            "share_p90": shares[min(int(0.9 * len(shares)), len(shares) - 1)],
            "pages_clean": sum(1 for s in shares if s == 0.0),
            "ceiling": D.gate_ceiling("orphan_share", 1.0),
        }
    report["why_tally"] = _why_tally(made)
    # MÃ, không chỉ CÂU. `why_tally` gộp theo câu (đã bỏ số) -- đọc được bằng
    # mắt nhưng không `groupby` được giữa các lượt chạy nếu câu đổi chữ.
    # `pipeline.failures.classify` gán mỗi câu một trong 12 mã cố định
    # (`docs/ke-hoach-refactor-engine.md` Phase 2), nên script so sánh
    # nhiều lượt chạy đọc `failure_codes`, người đọc bằng mắt vẫn đọc
    # `why_tally`.
    report["failure_codes"] = failures.tally(
        [why for m in made for why in (m.get("why") or [])])
    # ĐA DẠNG, đo trên tờ ĐÃ QUA CỔNG. Một tờ trượt cổng không vào bộ, nên nó
    # không nằm trong mẫu số của "bao nhiêu phần trăm bị loại vì trùng" --
    # trộn hai loại loại-bỏ vào một tỉ lệ là làm cả hai con số hết đọc được.
    report["diversity"] = warden.metrics(pages=len(kept))
    report["diversity"]["regeneration"] = {
        "calls": len(discarded),
        "seconds": round(sum(d["seconds"] for d in discarded), 1),
        "tokens_out": sum(d["tokens_out"] for d in discarded),
        "share_of_seconds": round(
            sum(d["seconds"] for d in discarded)
            / max(sum(m.get("seconds", 0.0) for m in made)
                 + sum(d["seconds"] for d in discarded), 1e-6), 4),
        "discarded": discarded,
    }
    # BA TẦNG, cộng lại cả bộ -- và trường bị giữ lại ghi ra một file RIÊNG.
    #
    # Riêng, vì `staging/` là hàng đợi soát của người, không phải một mục
    # trong báo cáo máy: mỗi dòng là một cái tên chờ được duyệt vào sổ
    # (`rulebase/kie_field_glossary.json`) hoặc bị bác. Trộn nó vào
    # `compose_report.json` là chôn nó dưới ba chục khoá thống kê, và một
    # hàng đợi không ai nhìn thấy là một hàng đợi không ai xử lý.
    #
    # Chỉ đếm tờ ĐÃ QUA cổng: một tờ bị loại không có mực nào vào bộ, nên
    # tên trường của nó không phải thứ cần duyệt.
    report["field_tiers"] = _tier_tally(kept)
    staged = [dict(row, page=m["index"], archetype=m["archetype"],
                   doc_group=m.get("doc_group", ""))
              for m in kept for row in (m.get("field_staging") or [])]
    if staged:
        (out / "staging").mkdir(parents=True, exist_ok=True)
        (out / "staging" / "field_candidates.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in staged),
            encoding="utf-8")
        print(f"[tầng] {len(staged)} trường vào staging/field_candidates.jsonl "
              "-- chờ soát, không vào bộ chính")
    # BAO NHIÊU TỜ ĐANG BỊ SIẾT VÌ CHƯA AI XẾP NHÓM -- in ra, không để nằm im
    # trong JSON.
    #
    # `unreviewed_policy: closed_by_law` (`rulebase/field_tiers.json`) siết một
    # loại giấy chưa xếp nhóm y như biểu mẫu luật định: `semi_open` bị hạ
    # xuống `dropped`, `staging` cũng vậy. Đó là mặc định ĐÚNG -- xếp nhầm một
    # biểu mẫu luật định thành tự do thì sinh nhãn sai, và nhãn sai không tự
    # kêu. Nhưng cái giá của nó phải đếm được: 178 trên 471 phôi hiện chưa xếp
    # nhóm, và nếu con số ấy chỉ nằm trong `compose_report.json` thì không ai
    # thấy mình đang trả giá gì. Một dòng ở đây là dòng nhắc soát tiếp.
    strict = (report["field_tiers"].get("doc_groups") or {}).get("unreviewed", 0)
    if strict:
        print(f"[tầng] {strict}/{len(kept)} tờ thuộc loại chứng từ CHƯA XẾP "
              "NHÓM, nên bị siết như biểu mẫu luật định (chỉ tầng `closed`) "
              "-- xếp nhóm ở `rulebase/field_tiers.json` để mở lại")
    (out / "compose_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _write_performance(out, report, made)

    print(f"\n[trang] {len(kept)}/{want} qua cổng  ({100*len(kept)/max(want,1):.0f}%)")
    if report["tokens_out"]:
        print(f"[trang] token: {report['tokens_out']} ra / "
              f"{report['tokens_in']} vào, "
              f"{report['tokens_out_per_page']} tk mỗi tờ, "
              f"{report['tokens_per_second']} tk/s gộp")
        rate = report["tokens_per_second"]
        if rate:
            hours = report["tokens_out_per_page"] * 20000 / rate / 3600
            print(f"[trang] suy ra: 20 000 tờ ≈ {hours:.1f} giờ "
                  f"ở tốc độ và mức song song này")
    print(f"[trang] {spent:.0f}s, {report['seconds_per_page']}s mỗi tờ, "
          f"{concurrency} song song")
    if total:
        print(f"[trang] SỐ HỌC: {wrong}/{total} dòng sai "
              f"({100*wrong/total:.1f}%) -- `qty x đơn giá != thành tiền`")
    why: dict[str, int] = {}
    for m in made:
        for line in m["why"]:
            key = re.sub(r"`[^`]*`", "`…`", line)[:64]
            why[key] = why.get(key, 0) + 1
    if why:
        print("[trang] lý do bị loại:")
        for line, n in sorted(why.items(), key=lambda kv: -kv[1]):
            print(f"    {n:3d}  {line}")
    div = report["diversity"]
    near = (div.get("geometry") or {}).get("nearest_jaccard") or {}
    print(f"[đa dạng] {div['rejected_for_collision']} tờ sinh lại vì trùng bố "
          f"cục ({100 * div['rejected_share']:.1f}% số lượt), "
          f"{div['kept_despite_collision']} nhận dù trùng, "
          f"{div['geometry_unavailable']} chưa đo được")
    print(f"[đa dạng] tờ gần nhất trong cửa sổ {div['window']}: trung vị "
          f"J={near.get('median')}, p90={near.get('p90')}, "
          f"còn {(div.get('geometry') or {}).get('over_ceiling')} tờ vượt "
          f"ngưỡng {div['jaccard_ceiling']}")
    if div["geometry_unavailable"] and not no_draw:
        # KÊU. Một lượt mà phần lớn tờ không đo được hình học là một lượt
        # KHÔNG có tầng gác thứ hai, và nó vẫn in ra "0 tờ trùng" y như một
        # lượt sạch thật -- đúng kiểu lỗi lặng lẽ AGENTS.md luật 6 nói tới.
        print(f"[đa dạng] CẢNH BÁO: {div['geometry_unavailable']} tờ không dàn "
              "ra được để đo, nên chúng chưa từng qua tầng gác hình học")
    print(f"[trang] -> {out}")
    # VẼ LUÔN. Người dùng phải xem được chất lượng ngay sau lượt chạy, không
    # phải nhớ chạy thêm một lệnh nữa -- và cái cần xem là ẢNH: hộp bố cục
    # chồng lên trang, và KIE chồng lên trang. Một `compose_report.json` nói
    # trang qua cổng; chỉ con mắt nói trang có DÙNG ĐƯỢC không.
    #
    # `draw_llm` vẽ cả `html/` lẫn `rejected/`, nên tờ trượt cũng có ảnh --
    # đó là cách đọc ra model hiểu sai chỗ nào.
    #
    # `artist.close()` đã gọi Ở TRÊN (trước khi tính `kept`/`report`) --
    # không gọi lại ở đây, chỉ đọc `artist.why`/`artist.rows` nó để lại.
    if artist is not None:
        if artist.why:
            # `playwright` giờ nằm cùng môi trường với bộ sinh (xem
            # `requirements.txt`). Nếu vẫn thiếu thì nói thẳng cách cài, chứ
            # đừng đi tìm một trình thông dịch khác -- hai môi trường cho một
            # đường chạy đúng là chỗ pilot7 mất sạch ảnh.
            print(f"[trang] vẽ hỏng ({artist.why}); HTML vẫn còn.\n"
                  f"  thiếu playwright thì: .venv/bin/pip install -r "
                  f"requirements.txt\n"
                  f"  rồi vẽ lại: .venv/bin/python -m synthgen.draw_llm {out}")
        elif artist.rows:
            from synthgen import draw_llm  # noqa: PLC0415

            print(f"[trang] {len(artist.rows)} tờ đã vẽ; gộp json và KIE...")
            draw_llm.finish(out, artist.rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--want", type=int, default=30, help="số tờ")
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4,
                        help="số request gửi song song")
    parser.add_argument("--seed", type=int, default=0,
                        help="chọn phôi nào -- để phép thử lặp lại được")
    # Mặc định `en`: người dùng chốt "sửa prompt thành default tiếng anh".
    # Server chạy Qwen, tinh chỉnh theo lệnh mạnh nhất ở tiếng Anh và Trung;
    # `--lang vi` vẫn còn để so, và chỉ phép đo mới nói được bản nào hơn.
    parser.add_argument("--no-draw", action="store_true",
                        help="chỉ sinh HTML, không vẽ ảnh hộp bố cục và KIE")
    # ĐỐI CHỨNG, không phải công tắc tiện tay. `--no-diversity` vẫn ĐO đủ mọi
    # con số và chỉ bỏ quyền loại tờ, nên hai lượt chạy A/B so được với nhau
    # bằng cùng một thước -- xem `agent/diversity.py::DiversityWarden`.
    parser.add_argument("--no-diversity", action="store_true",
                        help="ĐỐI CHỨNG: rút plan như trước khi nối dây (bốc "
                             "độc lập) và không sinh lại tờ trùng -- vẫn đo đủ")
    parser.add_argument("--no-coverage-steer", action="store_true",
                        help="chỉ tắt phần rút có trí nhớ, vẫn loại tờ trùng "
                             "-- để tách đóng góp của hai tầng")
    parser.add_argument("--diversity-window", type=int, default=GD.WINDOW,
                        help=f"so với mấy tờ gần nhất (mặc định {GD.WINDOW})")
    parser.add_argument("--diversity-jaccard", type=float,
                        default=GD.JACCARD_CEILING,
                        help="Jaccard từ mức này trở lên là trùng "
                             f"(mặc định {GD.JACCARD_CEILING})")
    parser.add_argument("--attempts", type=int, default=DIV.MAX_ATTEMPTS,
                        help="tối đa mấy lời gọi model cho một tờ "
                             f"(mặc định {DIV.MAX_ATTEMPTS})")
    args = parser.parse_args()
    return run(args.want, args.out.resolve(),
               concurrency=args.concurrency, seed=args.seed,
               no_draw=args.no_draw,
               diversity=not args.no_diversity,
               steer=not (args.no_diversity or args.no_coverage_steer),
               window=args.diversity_window,
               ceiling=args.diversity_jaccard,
               attempts=args.attempts)


if __name__ == "__main__":
    raise SystemExit(main())
