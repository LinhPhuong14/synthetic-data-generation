"""Ba tầng cho một cái tên trường -- MỘT sổ cho cả `kind` lẫn `data.path`.

    from synthgen.field_tier import classify, CLOSED, SEMI_OPEN, STAGING
    d = classify("store.name")                      # d.tier == CLOSED
    d = classify("issuer.tax_code", space="path")   # d.tier == CLOSED
    d = classify("store.meter_seal", describe="…")  # d.tier == SEMI_OPEN
    d = classify("patient.bed_no")                  # d.tier == STAGING

`field_plan[].kind` đã nửa đóng từ lâu: một từ vựng đo được cộng cửa thoát
`_COINED` (`synthgen/llm_page.py`). `data.path` thì hoàn toàn tự do, và đó là
nguồn trôi nghĩa lớn nhất. Đo trên 394 tệp `data/*/declared/*.json`:

    field_plan.kind   8 555 lượt   338 tên khác nhau    50 họ
    data.path        12 318 lượt  7 841 đường khác nhau  377 họ

377 họ đường dẫn cho cùng chừng ấy khái niệm mà 50 họ `kind` đã gọi tên xong.
Cùng một cái bảng hàng được gọi là `items[]`, `line_items[]`, `rows[]`,
`table.rows[]` -- bốn cái tên, một thứ. Một mô hình học trên bộ ấy học rằng
tên trường không có nghĩa.

## Ba tầng, và điều kiện vào từng tầng

| tầng | điều kiện | câu tả tới từ | vào bộ chính |
| --- | --- | --- | --- |
| `closed` | khoá TRÚNG ĐÚNG một khoá trong sổ | sổ đăng ký | có |
| `semi_open` | họ quen, lá mới, **kèm câu tả model đề xuất** | model, ghi nguyên văn | có |
| `staging` | không họ nào quen, hoặc thiếu câu tả | **không có** | không |
| `reject` | tên không đọc được (sai cả ngữ pháp) | -- | không |

`reject` không phải một tầng mới: nó là đúng điều cổng chữ
(`llm_page.problems`) vẫn làm, gọi tên ra để báo cáo đếm được.

## Luật quan trọng nhất: HỎNG THÌ ĐÓNG, không ánh xạ về khoá gần nhất

Không có phép đo tương tự nào ở đây, và đó là một quyết định chứ không phải
một thiếu sót. Một ngưỡng tương tự là đúng cách một tên trượt biến thành một
khoá SAI: `patient.dob` gần `patient.dod` hơn mọi khoá khác trong sổ, và khi
đã ánh xạ thì **câu tả cũng tra theo cái khoá sai ấy**. Lỗi kép, và nửa sau
không nhìn thấy được -- hộp vẫn đúng pixel, nhãn vẫn đọc trôi chảy, chỉ có
nghĩa là sai.

Nên phép khớp chỉ có hai kết quả: TRÚNG ĐÚNG khoá, hoặc rơi xuống tầng dưới.
Ngưỡng duy nhất trong file này là ngưỡng CHẤT LƯỢNG CÂU TẢ cho tầng
`semi_open`, và nó đọc từ `rulebase/synthgen/_kie_gates.yaml` -- cùng bảng
`synthgen/kie_gate.py` chấm mô tả, không phải một bảng thứ hai.

Điều này KHÁC `synthgen/repair.py::settle()` một cách có chủ ý. Hàm ấy ánh xạ
tên không đọc được về `invoice.field` / `invoice.field.label`, và lý lẽ của nó
("một nhãn rộng hơn vẫn là nhãn đúng") đúng cho `data-kind` trên giấy, nơi cái
giá của việc loại là mất cả tờ. Ở đây cái giá khác hẳn: một trường rơi xuống
`staging` không mất tờ nào, chỉ không vào bộ chính. Đo trên 12 423 tệp HTML,
1 748 010 lượt `data-kind`: nhánh chót của `settle()` chạy **0 lần**, nên hai
luật này không đá nhau trên dữ liệu thật.

## Hai nhóm loại chứng từ

`rulebase/field_tiers.json` xếp mỗi loại giấy vào `closed_by_law` (biểu mẫu do
văn bản pháp quy ấn định tập trường) hay `open_domain` (soạn tự do). Biểu mẫu
luật định **chỉ dùng tầng `closed`**: đặt thêm một trường vào tờ khai thuế là
dựng một tờ giấy tự nhận là mẫu luật định mà mang trường luật không có. Nhóm
chưa xếp (`unreviewed`) áp luật chặt -- xem `_unreviewed_policy_about` trong
file ấy về vì sao chặt chứ không lỏng.

## Sổ đăng ký PHÁI SINH, không chép

`registry()` dựng từ ba nguồn đã có, không từ một danh sách thứ tư:

    synthgen/llm_page.py::kinds()          87 kind đo từ chính HTML engine dựng
    rulebase/kie_field_glossary.json       `_by_kind` 74 · `_by_path` 60, câu tả
    synthgen/design.py::COLUMNS            `describe` sẵn có của 27 cột bảng

Họ (`store.`, `issuer.`, …) KHÔNG khai ở đâu cả -- nó là đoạn đầu của chính
những khoá ấy. Khai riêng là dựng người thứ hai cho một luật, và kho này đã đo
được ba lần hỏng vì đúng chuyện đó (`docs/bon-muc-kiem-soat-nhan-llm.md` §7b).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

POLICY_PATH = REPO_ROOT / "rulebase" / "field_tiers.json"

CLOSED = "closed"
SEMI_OPEN = "semi_open"
STAGING = "staging"
REJECT = "reject"
TIERS = (CLOSED, SEMI_OPEN, STAGING, REJECT)

KIND = "kind"
PATH = "path"
SPACES = (KIND, PATH)

CLOSED_BY_LAW = "closed_by_law"
OPEN_DOMAIN = "open_domain"
UNREVIEWED = "unreviewed"

# `status` ghi vào bản ghi. Rỗng = trường bình thường; mọi giá trị khác là một
# lý do để KHÔNG dùng trường ấy cho bộ huấn luyện chính.
CANDIDATE = "candidate"
DROPPED = "dropped"
REJECTED = "rejected"


@dataclass(frozen=True)
class Decision:
    """Kết quả xếp tầng của MỘT cái tên. Không bao giờ là một cái tên khác.

    `key` là `name` đã xoá chỉ số (`line_items[3].name` -> `line_items[].name`)
    và không đổi gì khác. Nó KHÔNG phải một khoá được ánh xạ tới: nếu tầng là
    `staging` thì `key` vẫn là chính cái tên model viết, chỉ ở dạng đã gom chỉ
    số -- người đọc log phải thấy đúng thứ model đã nói."""

    name: str
    key: str
    space: str
    tier: str
    family: str
    describe: str | None
    source: str          # "registry" | "proposed" | ""
    status: str          # "" | "candidate" | "dropped" | "rejected"
    in_batch: bool
    doc_group: str
    reason: str

    def as_dict(self) -> dict:
        """Hình phẳng để ghi vào `declared/`, `staging/` và báo cáo."""
        return {"name": self.name, "key": self.key, "space": self.space,
                "tier": self.tier, "family": self.family,
                "describe": self.describe, "describe_source": self.source,
                "status": self.status, "in_batch": self.in_batch,
                "doc_group": self.doc_group, "reason": self.reason}


@dataclass(frozen=True)
class Registry:
    """Sổ đăng ký đã dựng xong: khoá đóng, câu tả của chúng, và họ của chúng."""

    closed: dict[str, dict[str, str]]        # space -> {key: describe}
    families: dict[str, frozenset[str]]      # space -> {"store.", …}
    generic: dict[str, frozenset[str]]       # space -> khoá đóng nhưng vô nghĩa

    def describe(self, key: str, space: str) -> str | None:
        """Câu tả của MỘT khoá đóng, tra đúng khoá ấy. None khi không có.

        Không có nhánh lùi nào -- không cắt đuôi, không leo tiền tố, không
        khoá gần nhất. `rulebase/kie_glossary.py::describe` có cả ba phép ấy
        và chúng đúng ở đó (nó tra nghĩa cho một slug rút từ CHỮ IN, từ vựng
        mở); ở đây thì sai, vì đây là chỗ quyết một trường có được nhận hay
        không."""
        return (self.closed.get(space) or {}).get(key)


# Chỉ số: `[7]` và đoạn thuần số (`clause.1.body`) -- cổng chữ nhận cả hai hình
# (`synthgen/llm_page.py::_PATH`, đo trên pilot16), nên chỗ gom cũng phải nhận
# cả hai. Không gom thì `line_items[0].name` và `line_items[1].name` là hai
# khoá khác nhau, và một cái bảng bốn mươi dòng đẻ ra bốn mươi khoá lạ.
_INDEX_BRACKET = re.compile(r"\[\s*\d*\s*\]")
_INDEX_BARE = re.compile(r"(?<=\.)\d+(?=\.|$)")


def normalise(name: str) -> str:
    """Tên đã gom chỉ số. KHÔNG đổi chữ nào khác -- không hạ hoa, không cắt.

    Hạ hoa ở đây sẽ khiến `Issuer.Name` lặng lẽ trở thành một khoá đóng, và
    "lặng lẽ" là thứ mục 6 `AGENTS.md` cấm. Chuẩn hoá hình thức là việc của
    `synthgen/repair.py::settle`, chạy trước và trên HTML; tới lượt hàm này
    thì cái tên đã là cái tên cuối cùng."""
    text = str(name or "").strip()
    if not text:
        return ""
    return _INDEX_BARE.sub("[]", _INDEX_BRACKET.sub("[]", text))


def family_of(key: str) -> str:
    """Họ của một khoá: đoạn ĐẦU kèm dấu chấm (`store.`, `line_items[].`).

    Rỗng khi khoá chỉ có một đoạn -- `title`, `note`, `colhdr` là kind THẬT mà
    không thuộc họ nào, và một tên MỚI một đoạn thì không nói được nó thuộc
    cụm nào (cùng lý lẽ `_COINED` đòi hai đoạn trở lên)."""
    text = str(key or "")
    if "." not in text:
        return ""
    return text.split(".", 1)[0] + "."


@lru_cache(maxsize=1)
def policy() -> dict:
    """`rulebase/field_tiers.json`, đã nạp. Thiếu file là HỎNG TO, không im.

    Mục 6 `AGENTS.md`: khoá lạ thì từ chối, không bỏ qua. Một chính sách
    không nạp được mà vẫn chạy tiếp theo mặc định là đúng cách kho này đã bị
    cắn nhiều lần -- cả lượt sinh đi qua với một cái cổng không gác gì."""
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:                       # noqa: PERF203
        raise RuntimeError(
            f"không đọc được chính sách tầng trường {POLICY_PATH}: {error}") from error


@lru_cache(maxsize=1)
def _describe_gate() -> tuple[tuple[re.Pattern, ...], int]:
    """`(mẫu câu chung chung, số ký tự tối thiểu)` -- ĐỌC từ cổng mô tả đã có.

    `rulebase/synthgen/_kie_gates.yaml` đã liệt kê những câu vô dụng và ngưỡng
    độ dài, và `synthgen/kie_gate.py` đã chấm mô tả bằng chúng. Viết lại một
    bản thứ hai ở đây là hai người dựng một luật; khi ai đó siết cổng kia,
    tầng `semi_open` sẽ vẫn nhận đúng những câu vừa bị cấm.

    Thiếu file thì ngưỡng về 0 và không mẫu nào -- tức `semi_open` chỉ còn đòi
    "có câu tả không rỗng". Đây là chỗ DUY NHẤT trong file này chịu nhánh lùi
    êm, vì cái thiếu là một phép chấm ĐIỂM, không phải một phép quyết khoá."""
    import yaml  # noqa: PLC0415

    gates = REPO_ROOT / "rulebase" / "synthgen" / "_kie_gates.yaml"
    try:
        raw = yaml.safe_load(gates.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return (), 0
    pats = tuple(re.compile(p, re.IGNORECASE)
                 for p in (raw.get("generic") or []) if isinstance(p, str))
    return pats, int(raw.get("min_useful_chars") or 0)


def usable_description(text: str) -> tuple[bool, str]:
    """Câu tả model đề xuất có dùng được không, và vì sao không.

    Ba phép, mọi phép đều đo được trên chính câu chữ: không rỗng, đủ dài theo
    `min_useful_chars`, và không khớp mẫu `generic:` nào. Không phép nào hỏi
    câu ấy có ĐÚNG hay không -- việc ấy người đọc diff làm, cùng ranh giới
    `agent/corpus_rules.py` đã đặt cho corpus."""
    said = " ".join(str(text or "").split())
    if not said:
        return False, "không có câu tả đề xuất"
    pats, floor = _describe_gate()
    if floor and len(said) < floor:
        return False, f"câu tả {len(said)} ký tự, dưới ngưỡng {floor}"
    for pat in pats:
        if pat.search(said):
            return False, f"câu tả khớp mẫu chung chung `{pat.pattern}`"
    return True, ""


@lru_cache(maxsize=1)
def registry() -> Registry:
    """Sổ đăng ký, dựng một lần. Xem docstring module về ba nguồn của nó."""
    from rulebase import kie_glossary  # noqa: PLC0415
    from synthgen import design as D  # noqa: PLC0415
    from synthgen.llm_page import kinds  # noqa: PLC0415

    _, by_kind = kie_glossary.load()
    by_path = kie_glossary.load_paths()

    # Câu tả của cột bảng đã viết sẵn ngay cạnh định nghĩa cột. Lấy ở đó thay
    # vì chép sang JSON: `synthgen/design.py::COLUMNS` là chỗ ai thêm một cột
    # sẽ sửa, nên câu tả cột mới có mặt mà không ai phải nhớ file thứ hai.
    from_columns = {str(col.get("kind") or ""): str(col.get("describe") or "")
                    for col in D.COLUMNS.values()
                    if col.get("kind") and col.get("describe")}

    # MỌI CỘT ĐÃ ĐỊNH NGHĨA, không chỉ cột lượt lấy mẫu chạm phải.
    #
    # `kinds()` nhặt từ 300 trang dựng thật, nên nó bỏ sót cột hiếm: đo được
    # `menu.quota`, `menu.meter_prev`, `menu.meter_now`, `menu.discountprice`,
    # `menu.rate_service` có trong `COLUMNS` mà không có trong mẫu. Chính
    # `llm_page.py` đã viết ra cái bẫy này ("Để ở 60 là nói với model rằng
    # `menu.meter_prev` KHÔNG TỒN TẠI, trong khi engine vẫn in chúng ra") và
    # sửa nó bằng cách nâng cỡ mẫu -- nhưng cỡ mẫu nào cũng còn một cái đuôi.
    # `COLUMNS` thì không phải mẫu: nó là danh sách cột, đầy đủ theo cấu tạo.
    kind_keys = set(kinds()) | set(by_kind) | set(from_columns)
    closed_kind = {k: (by_kind.get(k) or from_columns.get(k) or "")
                   for k in kind_keys}
    closed_path = dict(by_path)

    pol = policy()
    generic = pol.get("generic") or {}
    return Registry(
        closed={KIND: closed_kind, PATH: closed_path},
        families={space: frozenset(f for f in (family_of(k) for k in table)
                                   if f)
                  for space, table in ((KIND, closed_kind), (PATH, closed_path))},
        generic={space: frozenset(generic.get(space) or ())
                 for space in SPACES},
    )


def closed_enum(space: str = KIND) -> tuple[str, ...]:
    """Khoá tầng `closed`, đã sắp -- đúng thứ đi vào `enum` của response_format.

    `agent/compose_page.py::schema()` dán nó vào nhánh đầu của `anyOf`, nên bộ
    giải mã có ràng buộc KHÔNG THỂ sinh một tên tầng-đóng nằm ngoài sổ. Nhánh
    thứ hai (`_COINED`) vẫn để ngỏ cho `semi_open`/`staging`; hai nhánh cộng
    lại đúng bằng ngôn ngữ `kind_pattern()` vẫn mô tả, nên cổng chữ và bộ giải
    mã không lệch nhau -- `tests/test_llm_page.py` canh đúng điều ấy."""
    return tuple(sorted(registry().closed.get(space) or {}))


# ---------------------------------------------------------------- nhóm loại giấy

@lru_cache(maxsize=1)
def _group_rules() -> tuple[tuple[str, str, tuple[re.Pattern, ...], frozenset[str]], ...]:
    """`(nhóm, tên luật, mẫu tiêu đề, tập id)` -- đọc từ chính sách, không chép."""
    out = []
    groups = (policy().get("doc_groups") or {})
    for group in (CLOSED_BY_LAW, OPEN_DOMAIN):
        for name, rule in sorted((groups.get(group) or {}).items()):
            if name.startswith("_") or not isinstance(rule, dict):
                continue
            pats = tuple(re.compile(p, re.IGNORECASE)
                         for p in (rule.get("title_patterns") or []))
            out.append((group, name, pats, frozenset(rule.get("ids") or ())))
    return tuple(out)


@lru_cache(maxsize=1)
def _titles() -> dict[str, str]:
    """`{id phôi: tiêu đề đầu tiên}` -- đọc từ chính phôi đang chạy.

    Không có phôi nào nạp được (thiếu `pyyaml`, chạy trong môi trường trần)
    thì bảng rỗng và luật tiêu đề đơn giản không khớp gì: xếp nhóm lùi về
    `unreviewed`, tức về phía CHẶT. Một nhánh lùi đi về phía lỏng ở đây sẽ mở
    tầng `staging` cho tờ khai thuế mỗi khi một thư viện vắng mặt."""
    try:
        from synthgen import design as D  # noqa: PLC0415
        return {str(a.id): str((a.titles or ("",))[0]) for a in D.ARCHETYPES}
    except Exception:                                            # noqa: BLE001
        return {}


def _title_of(doc_type: str) -> str:
    return _titles().get(doc_type, "")


def doc_group(doc_type: str, title: str = "") -> str:
    """`closed_by_law` | `open_domain` | `unreviewed` cho một loại chứng từ.

    `doc_type` nhận cả hai không gian tên đang chạy: `id` của phôi
    (`hoa_don_gtgt`) và tên family của `agent/grammar.py` (`invoice_detailed`)
    -- hai nhánh sinh gọi loại giấy bằng hai cái tên khác nhau, và một hàm chỉ
    hiểu một nửa là một hàm im lặng trả sai cho nửa kia.

    `overrides` thắng mọi luật; sau đó luật `closed_by_law` được hỏi TRƯỚC
    `open_domain`, vì hướng sai nguy hiểm là xếp một biểu mẫu luật định thành
    tự do."""
    name = str(doc_type or "").strip()
    groups = policy().get("doc_groups") or {}
    override = (groups.get("overrides") or {}).get(name)
    if isinstance(override, str) and override in (CLOSED_BY_LAW, OPEN_DOMAIN,
                                                  UNREVIEWED):
        return override
    # TIÊU ĐỀ TỰ TRA, không bắt nơi gọi đưa vào. Chữ in trên tờ giấy là dữ
    # liệu phôi đã mang sẵn (`synthgen/design.py::BY_ID`), và bắt mỗi nơi gọi
    # nhớ kèm nó là cách chắc chắn để một nửa số nơi gọi quên -- rồi mọi phôi
    # khai bằng YAML im lặng rơi vào `unreviewed` dù luật tiêu đề đọc ra được.
    heading = " ".join(str(title or "").split()) or _title_of(name)
    for group, _rule, pats, ids in _group_rules():
        if name and name in ids:
            return group
        if heading and any(p.search(heading) for p in pats):
            return group
    return str(groups.get("default") or UNREVIEWED)


def effective_group(group: str) -> str:
    """Nhóm sau khi áp `unreviewed_policy`. Chỉ `open_domain` mở cả ba tầng."""
    if group != UNREVIEWED:
        return group
    groups = policy().get("doc_groups") or {}
    fallback = str(groups.get("unreviewed_policy") or CLOSED_BY_LAW)
    return fallback if fallback in (CLOSED_BY_LAW, OPEN_DOMAIN) else CLOSED_BY_LAW


# ------------------------------------------------------------------- xếp tầng

def _grammar_ok(key: str, space: str) -> bool:
    """Cái tên có ĐỌC ĐƯỢC không -- mượn đúng vị từ cổng chữ đang dùng.

    Không viết lại regex ở đây. `_COINED` và `_PATH` là hai luật đã có người
    dựng, đã có test canh, và một bản sao ở file này sẽ lệch khỏi chúng đúng
    vào ngày ai đó nới một trong hai."""
    from synthgen.llm_page import _COINED, _PATH, _rooted, kinds  # noqa: PLC0415

    if space == PATH:
        return bool(_PATH.match(key.replace("[]", "[0]")))
    known = kinds()
    return bool(key in known or _rooted(key, known) or _COINED.match(key))


def classify(name: str, *, space: str = KIND, describe: str = "",
             doc_type: str = "", doc_title: str = "") -> Decision:
    """Xếp MỘT cái tên vào một tầng. Không bao giờ trả về một cái tên khác.

    `describe` là câu tả model đề xuất kèm trong cùng câu trả lời. Nó chỉ có
    tác dụng ở tầng `semi_open`: khoá đóng lấy câu tả từ sổ (lời model khai
    không ghi đè sổ), khoá `staging` không lấy câu tả nào cả -- `None`, chứ
    không phải một câu tả mượn của khoá gần nhất."""
    if space not in SPACES:
        raise ValueError(f"không gian tên lạ: {space!r}; chỉ có {SPACES}")
    raw = str(name or "").strip()
    key = normalise(raw)
    group = doc_group(doc_type, doc_title)
    strict = effective_group(group) != OPEN_DOMAIN

    def made(tier, *, describe_text, source, reason, status="", in_batch=False):
        return Decision(name=raw, key=key, space=space, tier=tier,
                        family=family_of(key), describe=describe_text,
                        source=source, status=status, in_batch=in_batch,
                        doc_group=group, reason=reason)

    if not key:
        return made(REJECT, describe_text=None, source="", status=REJECTED,
                    reason="tên rỗng")

    reg = registry()
    if key in (reg.closed.get(space) or {}):
        said = reg.describe(key, space) or ""
        return made(CLOSED, describe_text=said or None,
                    source="registry", in_batch=True,
                    reason=("khoá có trong sổ" if said else
                            "khoá có trong sổ nhưng sổ chưa có câu tả"))

    if not _grammar_ok(key, space):
        return made(REJECT, describe_text=None, source="", status=REJECTED,
                    reason="tên không đọc được: phải là `họ.trường` chữ "
                           "thường, snake_case, 2-4 đoạn")

    family = family_of(key)
    known_family = bool(family) and family in (reg.families.get(space) or ())
    if not known_family:
        return made(STAGING, describe_text=None, source="", status=CANDIDATE,
                    reason=(f"họ `{family}` không có trong sổ" if family
                            else "tên một đoạn, không nói được nó thuộc họ nào"))

    ok, why = usable_description(describe)
    if not ok:
        # HỌ QUEN MÀ THIẾU CÂU TẢ VẪN LÀ `staging`, không phải `closed`.
        #
        # Đây là chỗ dễ trượt nhất của cả file: `store.meter_seal` có họ thật,
        # và một nhánh lùi "lấy tạm câu tả của `store.`" trông vô hại. Nó
        # chính là lỗi kép đã nói ở đầu module -- khoá mới đội câu tả của khoá
        # khác, và không ai đọc ra được điều đó từ bản ghi.
        return made(STAGING, describe_text=None, source="", status=CANDIDATE,
                    reason=f"họ `{family}` quen nhưng {why}")

    if strict:
        # Biểu mẫu luật định: CHỈ tầng `closed`. Một lá mới, dù có câu tả
        # tử tế, vẫn là một trường mà văn bản pháp quy không có.
        return made(SEMI_OPEN, describe_text=" ".join(describe.split()),
                    source="proposed", status=DROPPED,
                    reason=f"lá mới trong họ `{family}`, nhưng loại chứng từ "
                           f"thuộc nhóm `{group}` -- chỉ nhận tầng `closed`")
    return made(SEMI_OPEN, describe_text=" ".join(describe.split()),
                source="proposed", in_batch=True,
                reason=f"lá mới trong họ quen `{family}`, kèm câu tả đề xuất")


def classify_plan(field_plan, *, doc_type: str = "",
                  doc_title: str = "") -> list[Decision]:
    """Xếp tầng cả `field_plan` model khai. Bỏ qua mục không có `kind`."""
    out: list[Decision] = []
    for item in (field_plan or []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        if not kind:
            continue
        out.append(classify(kind, space=KIND,
                            describe=str(item.get("describe") or ""),
                            doc_type=doc_type, doc_title=doc_title))
    return out


def classify_data(data, *, doc_type: str = "",
                  doc_title: str = "") -> list[Decision]:
    """Xếp tầng cây `data` model khai -- danh sách phẳng `[{path, value}]`.

    Cũng đọc được hình LỒNG của mọi `declared/*.json` ghi trước 23-09-2026,
    cùng lý do `agent/compose_page.py::data_path_mismatches` đọc cả hai: một
    hàm đo mà chỉ đọc được dữ liệu sinh từ hôm nay là hàm không so được
    trước/sau."""
    out: list[Decision] = []

    def one(path: str, describe: str = "") -> None:
        if path:
            out.append(classify(path, space=PATH, describe=describe,
                                doc_type=doc_type, doc_title=doc_title))

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                one(str(item.get("path") or ""), str(item.get("describe") or ""))
        return out
    if isinstance(data, dict):
        def walk(node, prefix=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{prefix}.{key}" if prefix else str(key))
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{prefix}[{i}]")
            else:
                one(prefix)
        walk(data)
    return out


def worst(*decisions: Decision) -> Decision:
    """Quyết định NGHIÊM nhất trong mấy cái. Một cặp KIE có hai cái tên --
    `role` (`data-kind`) và `path` -- và nó chỉ đáng tin bằng cái tên yếu
    hơn: một `role` đóng đi kèm một `path` bịa vẫn là một cặp không tra lại
    được."""
    order = {CLOSED: 0, SEMI_OPEN: 1, STAGING: 2, REJECT: 3}
    got = [d for d in decisions if d is not None]
    if not got:
        raise ValueError("không có quyết định nào để so")
    return max(got, key=lambda d: order.get(d.tier, 3))


def mark_pairs(pairs, *, doc_type: str = "", doc_title: str = "") -> dict:
    """Gắn tầng lên từng cặp KIE, SỬA TẠI CHỖ. Trả bản đếm.

    Mỗi cặp nhận ba khoá mới: `tier`, `status`, `in_batch`. Không khoá nào cũ
    bị đụng -- `description` của một cặp `staging` giữ nguyên chữ nó đang có,
    vì xoá đi thì người soát không còn gì để đọc mà quyết. Thứ đổi là ai được
    TIN nó: `synthgen/export.py::document` bỏ qua cặp `in_batch: False`, nên
    câu tả ấy không vào bộ huấn luyện dù còn nằm trong bản ghi.

    Cặp không có `path` (`source: "implied"`, `label`) chỉ xét `role`. Cặp có
    cả hai lấy vế nghiêm hơn -- xem `worst()`."""
    counts: dict[str, int] = {}
    for pair in (pairs or []):
        if not isinstance(pair, dict):
            continue
        got = [classify(str(pair.get("role") or ""), space=KIND,
                        doc_type=doc_type, doc_title=doc_title)]
        path = str(pair.get("path") or "")
        if path:
            got.append(classify(path, space=PATH,
                                doc_type=doc_type, doc_title=doc_title))
        pick = worst(*got)
        pair["tier"] = pick.tier
        pair["status"] = pick.status
        pair["in_batch"] = pick.in_batch
        counts[pick.tier] = counts.get(pick.tier, 0) + 1
    total = sum(counts.values())
    return {"total": total, "counts": counts,
            "share": {tier: (round(n / total, 4) if total else 0.0)
                      for tier, n in counts.items()}}


def tally(decisions) -> dict:
    """Đếm theo tầng, cộng tỉ lệ. Hình dùng cho `compose_report.json`.

    `generic` đếm riêng và KHÔNG trừ khỏi `closed`: những khoá ấy thật sự
    đóng (engine in chúng ra, và luật cấm xoá khoá đã có trong sổ). Tách ra
    vì tỉ lệ rơi vào chúng mới là thước đo trôi nghĩa -- xem `generic` trong
    `rulebase/field_tiers.json`."""
    seen = list(decisions)
    total = len(seen)
    counts = {tier: 0 for tier in TIERS}
    generic = 0
    reg = registry()
    for got in seen:
        counts[got.tier] = counts.get(got.tier, 0) + 1
        if got.key in (reg.generic.get(got.space) or ()):
            generic += 1
    share = {tier: (round(n / total, 4) if total else 0.0)
             for tier, n in counts.items()}
    return {"total": total, "counts": counts, "share": share,
            "generic": generic,
            "generic_share": round(generic / total, 4) if total else 0.0,
            "in_batch": sum(1 for d in seen if d.in_batch)}


def staging_rows(decisions) -> list[dict]:
    """Chỉ những trường KHÔNG vào bộ chính -- thứ ghi ra `staging/` để soát."""
    return [got.as_dict() for got in decisions if not got.in_batch]


__all__ = ["CANDIDATE", "CLOSED", "CLOSED_BY_LAW", "DROPPED", "Decision",
           "KIND", "OPEN_DOMAIN", "PATH", "REJECT", "REJECTED", "Registry",
           "SEMI_OPEN", "SPACES", "STAGING", "TIERS", "UNREVIEWED",
           "classify", "classify_data", "classify_plan", "closed_enum",
           "doc_group", "effective_group", "family_of", "mark_pairs",
           "normalise", "policy", "registry", "staging_rows", "tally",
           "usable_description", "worst"]
