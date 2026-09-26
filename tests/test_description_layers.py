"""Hai lớp câu tả: câu của sổ, cộng câu nói lần xuất hiện NÀY là cái gì.

Test này canh một lỗi không nhìn thấy được từ ảnh, từ hộp, hay từ tên trường.
Một giấy uỷ quyền in `store.tax_code` hai lần -- một cho bên uỷ quyền, một cho
bên được uỷ quyền. Cả hai khoá đúng, cả hai hộp đúng pixel, cả hai câu tả đọc
trôi chảy. Và chúng GIỐNG HỆT nhau, nên hai trường chỉ còn phân biệt được bằng
chỗ ngồi của cái hộp.

Đo lúc viết (24-09-2026, 785 tệp `data/*/declared`, 11.847 lượt trường):

    authorisation_letter/store.tax_code   1 câu / 20 lượt = 0,050
    authorisation_letter/meta.value       1 câu / 55 lượt = 0,018

Nên bài kiểm ở đây hỏi ba câu mà một bản "gộp câu tả" hời hợt sẽ trả lời sai:

* hai trường cùng khoá, khác `path`, có ra HAI câu khác nhau không;
* câu của SỔ có đứng yên không (gom nhóm và chấm QA đọc nó);
* câu riêng có nối đúng ô mực không, hay nối theo một phép đoán thứ tự.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FT = pytest.importorskip("synthgen.field_tier",
                         reason="cần pyyaml để nạp phôi và cổng mô tả")

OPEN_DOC = "authorisation_letter"


# ------------------------------------------------------------------ A: ghép

def test_compose_joins_the_two_layers():
    got = FT.compose("Tax identification number.", "Of the authorising party")
    assert "Tax identification number." in got
    assert "Of the authorising party" in got


def test_compose_does_not_repeat_one_sentence_twice():
    """Tầng `semi_open`: câu model viết LÀ câu của khoá. Ghép vào chính nó là
    một chuỗi dài gấp đôi mà không thêm một chữ phân biệt nào."""
    assert FT.compose("Một câu", "Một câu") == "Một câu"


def test_compose_survives_either_layer_missing():
    assert FT.compose("chỉ sổ", "") == "chỉ sổ"
    assert FT.compose("", "chỉ riêng") == "chỉ riêng"
    assert FT.compose(None, None) == ""


def test_a_closed_key_now_keeps_the_model_sentence_too():
    """Bản trước VỨT câu model viết ở tầng `closed`. Sổ vẫn không bị ghi đè --
    nó ở `describe`; câu model ở `instance`; `description` là hai lớp đã ghép."""
    got = FT.classify("store.tax_code", describe="Tax code of the agent",
                      doc_type=OPEN_DOC)
    assert got.tier == FT.CLOSED
    assert got.describe == FT.registry().describe("store.tax_code", FT.KIND)
    assert got.instance == "Tax code of the agent"
    assert got.source == "registry+proposed"
    assert got.describe in got.description
    assert "Tax code of the agent" in got.description


def test_a_closed_key_without_a_sentence_is_unchanged():
    """Bản ghi cũ (không có khoá `describe`) phải đi qua y như trước."""
    got = FT.classify("store.tax_code", doc_type=OPEN_DOC)
    assert got.instance is None and got.source == "registry"
    assert got.description == got.describe


def test_the_instance_gate_is_looser_than_the_semi_open_gate():
    """Hai cổng, hai việc. Câu ở tầng `semi_open` phải ĐỨNG MỘT MÌNH làm nghĩa
    của một khoá mới, nên nó có ngưỡng độ dài. Câu riêng đứng CẠNH câu của sổ.

    `MST bên uỷ quyền` là 16 ký tự, dưới `min_useful_chars`, và nó nói đúng
    cái cần nói -- đo trên `data/pilot17`: 5 trên 13 câu model viết ngắn hơn
    ngưỡng ấy."""
    short = "MST bên uỷ quyền"
    assert not FT.usable_description(short)[0]
    assert FT.usable_instance(short)[0]


def test_a_generic_fallback_sentence_is_not_worth_joining():
    ok, why = FT.usable_instance("Value printed on the document.")
    assert not ok and "chung chung" in why


def test_two_fields_sharing_a_closed_key_end_up_distinguishable():
    """Chính ca của giấy uỷ quyền, dựng bằng tay: hai `store.tax_code`, hai
    `path`, hai câu tả riêng."""
    pairs = [
        {"role": "store.tax_code", "path": "issuer.tax_code",
         "description": "Tax identification number of the organisation."},
        {"role": "store.tax_code", "path": "auth.seller_tax",
         "description": "Tax identification number of the organisation."},
    ]
    data = [
        {"path": "issuer.tax_code", "value": "0313872451",
         "describe": "Tax code of the authorising party"},
        {"path": "auth.seller_tax", "value": "0301234567",
         "describe": "Tax code of the authorised agent"},
    ]
    FT.mark_pairs(pairs, doc_type=OPEN_DOC, data=data)
    assert pairs[0]["description"] != pairs[1]["description"]
    # …mà câu của SỔ vẫn là một, vì gom nhóm và chấm QA đọc nó.
    assert pairs[0]["description_canonical"] == pairs[1]["description_canonical"]
    assert pairs[0]["description_instance"] == "Tax code of the authorising party"


def test_layer_two_is_matched_by_path_not_by_order():
    """Nối theo THỨ TỰ là đúng phép đoán mà `field_tier` từ chối làm: đảo thứ
    tự `data` không được đổi câu tả của cặp nào."""
    def run(data):
        pairs = [{"role": "store.tax_code", "path": "issuer.tax_code",
                  "description": "canonical"},
                 {"role": "store.tax_code", "path": "auth.seller_tax",
                  "description": "canonical"}]
        FT.mark_pairs(pairs, doc_type=OPEN_DOC, data=data)
        return [p["description_instance"] for p in pairs]

    forward = [{"path": "issuer.tax_code", "describe": "bên uỷ quyền"},
               {"path": "auth.seller_tax", "describe": "bên được uỷ quyền"}]
    assert run(forward) == run(list(reversed(forward)))


def test_a_pair_with_no_path_gets_no_second_layer():
    """Không `path` thì không nối được về câu nào, và ĐOÁN là thứ file này
    từ chối làm -- cặp `implied` giữ nguyên một lớp."""
    pairs = [{"role": "store.tax_code", "path": "", "description": "canonical"}]
    FT.mark_pairs(pairs, doc_type=OPEN_DOC,
                  data=[{"path": "issuer.tax_code", "describe": "bên A"}])
    assert pairs[0]["description_instance"] is None
    assert pairs[0]["description"] == "canonical"


def test_an_old_record_without_describe_keeps_one_layer():
    """`data` hình cây (mọi `declared/` trước 23-09-2026) không mang câu tả
    nào, và bịa một lớp cho nó là dựng dữ liệu không ai đo được."""
    assert FT.instances({"issuer": {"tax_code": "0313872451"}}) == {}
    assert FT.instances(None) == {}


def test_every_row_of_one_table_column_shares_one_sentence():
    """Bốn mươi dòng của một cột nghĩa như nhau -- một câu là đủ, và bốn mươi
    câu là bốn mươi bản sao."""
    got = FT.instances([
        {"path": "line_items[0].name", "describe": "Tên hàng trên dòng này"},
        {"path": "line_items[7].name", "describe": "Tên hàng trên dòng này"},
    ])
    assert list(got) == ["line_items[].name"]


# ---------------------------------------------------- B: lá cho thùng hứng

def test_the_five_meta_leaves_are_already_accepted():
    """Cơ chế nhận lá KHÔNG phải thứ phải dựng: họ `meta.` quen, nên một lá
    mới kèm câu tả rơi thẳng vào `semi_open` với `in_batch: True`."""
    said = "Number this authorisation letter was issued under, in the margin."
    for leaf in FT.candidate_leaves("meta.value"):
        got = FT.classify(leaf, describe=said, doc_type=OPEN_DOC)
        assert got.tier == FT.SEMI_OPEN, leaf
        assert got.in_batch, leaf


def test_candidate_leaves_are_read_from_policy_not_hardcoded():
    leaves = FT.candidate_leaves("meta.value")
    assert leaves, "chính sách phải khai lá cho `meta.`"
    policy = (FT.policy().get("generic") or {}).get("leaves") or {}
    assert tuple(policy.get("meta.") or ()) == leaves


def test_an_ordinary_key_has_no_candidate_leaves():
    assert FT.candidate_leaves("store.name") == ()


def test_a_catch_all_with_a_sentence_says_it_should_be_split():
    """`meta.value` VẪN vào bộ chính -- hạ nó xuống `staging` là vứt 914 lượt
    đã đo được vì một cái tên. Thứ đổi là bản ghi nói ra rằng nên tách."""
    got = FT.classify("meta.value", describe="Số hiệu của giấy uỷ quyền",
                      doc_type=OPEN_DOC)
    assert got.tier == FT.CLOSED and got.in_batch
    assert got.leaves and "nên tách" in got.reason


def test_classify_never_renames_a_catch_all_to_a_leaf():
    """Đổi hộ là đúng phép 'lấy khoá gần nhất' mà module này từ chối làm."""
    got = FT.classify("meta.value", describe="Ngày ký giấy uỷ quyền",
                      doc_type=OPEN_DOC)
    assert got.key == "meta.value"


# ------------------------------------------------- D: bảng canonical, hai hình

def test_base_key_strips_only_the_occurrence_suffix():
    D = pytest.importorskip("synthgen.descriptions")
    assert D.base_key("dia_chi_3") == "dia_chi"
    assert D.base_key("ma_so_thue") == "ma_so_thue"
    assert D.base_key("so_2_ban") == "so_2_ban"


def test_the_canonical_table_loses_copies_but_no_sentences():
    """Phép kiểm đáng giá nhất của cả phần này: bảng nhỏ đi 99% mà số câu
    KHÁC NHAU không đổi một đơn vị."""
    D = pytest.importorskip("synthgen.descriptions")
    grown, small = D.tables(), D.canonical()
    def said(table):
        return {json.dumps(t, ensure_ascii=False, sort_keys=True)
                for one in table for t in one.values()}
    before = said(grown.values())
    after = said([small["_shared"], *small["layouts"].values()])
    rows_before = sum(len(v) for v in grown.values())
    rows_after = len(small["_shared"]) + sum(len(v) for v in small["layouts"].values())
    assert before == after
    assert rows_after < rows_before / 10


def test_both_ledger_shapes_read_the_same_sentence(monkeypatch):
    """Bộ cũ trên đĩa có thư mục hàng chục GB. Làm một câu tả không đọc được
    ở đó là bắt sinh lại chúng để đọc một chuỗi."""
    kie = pytest.importorskip("pipeline.kie")
    old = {"hoa_don_gtgt": {"ma_so_thue": "Tax number.",
                            "ma_so_thue_2": "Tax number."}}
    new = {"_schema": 2, "_shared": {"ma_so_thue": "Tax number."}, "layouts": {}}
    for shape in (old, new):
        with tempfile.TemporaryDirectory() as box:
            path = Path(box) / "kd.json"
            path.write_text(json.dumps(shape, ensure_ascii=False), encoding="utf-8")
            monkeypatch.setenv("VLM_KIE_DESCRIPTIONS", str(path))
            kie._all_descriptions.cache_clear()
            said, _src = kie.describe("ma_so_thue", layout="hoa_don_gtgt")
            assert said == "Tax number."
    kie._all_descriptions.cache_clear()


def test_the_rule_path_tells_repeated_captions_apart(monkeypatch):
    """Ba `ma_so_thue` trên một hoá đơn: bảng cho chúng một câu, và lớp (ii)
    dựng lại thứ hậu tố `_N` đã đo được từ chính trang."""
    kie = pytest.importorskip("pipeline.kie")
    table = {"_schema": 2, "_shared": {"ma_so_thue": "Tax number."},
             "layouts": {}}
    with tempfile.TemporaryDirectory() as box:
        path = Path(box) / "kd.json"
        path.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv("VLM_KIE_DESCRIPTIONS", str(path))
        kie._all_descriptions.cache_clear()
        said = [kie.describe(f, caption="Mã số thuế", layout="hoa_don_gtgt")[0]
                for f in ("ma_so_thue", "ma_so_thue_2", "ma_so_thue_3")]
    kie._all_descriptions.cache_clear()
    assert len(set(said)) == 3, said
    assert all("Tax number." in one for one in said)


def test_occurrence_is_measured_off_the_field_name():
    kie = pytest.importorskip("pipeline.kie")
    assert kie.occurrence("dia_chi") == 1
    assert kie.occurrence("dia_chi_4") == 4


# ------------------------------------------------------- C: đo đa dạng câu tả

def test_the_diversity_report_finds_a_collapsed_pair():
    report = pytest.importorskip("tools.llm.field_tiers_report")
    ceiling, floor = report.diversity_gate()
    rows = report.diversity(
        [("giay_uy_quyen", "store.tax_code", "một câu")] * (floor + 5)
        + [("giay_uy_quyen", "sign.name", f"câu {i}") for i in range(floor + 5)])
    bad = {r["kind"] for r in rows if r["under"]}
    assert "store.tax_code" in bad
    assert "sign.name" not in bad


def test_a_rarely_used_pair_is_not_scored():
    """Dưới sàn thì tỉ lệ là nhiễu: 4.452 trên 4.482 cặp có dưới 30 lượt, và
    3.163 trong số đó có tỉ lệ đúng 1,0 chỉ vì chúng xuất hiện một hai lần."""
    report = pytest.importorskip("tools.llm.field_tiers_report")
    _ceiling, floor = report.diversity_gate()
    rows = report.diversity([("x", "y", "cùng một câu")] * (floor - 1))
    assert rows[0]["scored"] is False and rows[0]["under"] is False


def test_the_diversity_threshold_comes_from_the_gates_file():
    """Một con số thứ hai nằm trong mã là thứ sẽ lệch khỏi cổng khi ai đó
    siết cổng -- kho này đã hỏng ba lần vì đúng kiểu ấy."""
    report = pytest.importorskip("tools.llm.field_tiers_report")
    yaml = pytest.importorskip("yaml")
    ceiling, floor = report.diversity_gate()
    raw = yaml.safe_load(
        (REPO_ROOT / "rulebase" / "synthgen" / "_kie_gates.yaml")
        .read_text(encoding="utf-8"))["thresholds"]
    assert ceiling == raw["description_diversity"]
    assert floor == raw["description_diversity_floor"]
