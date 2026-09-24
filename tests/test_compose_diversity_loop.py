"""`agent/compose_page.py::run` -- vòng sinh lại khi tờ vừa viết trùng bố cục.

`tests/test_diversity.py` kiểm `DiversityWarden` một mình; file này kiểm CHỖ
NỐI: `run()` có thật sự hỏi warden, có thật sự gọi model lần hai với câu nhắc,
và báo cáo có chép đúng số không.

Không có server, không có Chromium: `one()` và `Artist` đều bị thay bằng bản
giả. Thứ đang kiểm là luồng điều khiển, không phải phép dàn trang -- và một
test cần cả hai thứ kia là một test không ai chạy.
"""

from __future__ import annotations

import json

import agent.compose_page as CP


def region(label, x0, y0, x1, y1, page=1):
    return {"layout_class": label, "bbox": [x0, y0, x1, y1],
            "page_number": page}


# Hai bố cục: `SAME` để dựng tờ trùng, `FRESH` để tờ sinh lại thoát ra.
SAME = [region("Page-Header", 0, 0, 1000, 80), region("Table", 0, 200, 1000, 700)]
FRESH = [region("Text", 0, 820, 400, 990)]


class FakeArtist:
    """Đủ hình dạng cho `run()`: `start/put/measure/close/rows/why`.

    `layouts` là hàng đợi bố cục trả về theo thứ tự được hỏi, nên một test
    dựng được đúng kịch bản "tờ thứ hai trùng, tờ sinh lại thì không"."""

    made: list = []

    def __init__(self, out):
        self.out = out
        self.rows: list = []
        self.why = ""
        self.drawn: list = []
        self.asked: list = []
        FakeArtist.made.append(self)

    def start(self):
        return None

    def put(self, path, passed):
        self.drawn.append((path.name, passed))

    def measure(self, html, stem, archetype="llm", timeout=300.0):
        self.asked.append(stem)
        return {"layout_annotations": FakeArtist.layouts.pop(0)}

    def close(self):
        return None


class FakeClient:
    model = "giả"
    url = "http://giả"
    timeout = 1.0

    def alive(self):
        return True


def fake_one(calls):
    """`one()` giả: ghi lại `avoid`/`attempt`, trả một tờ luôn qua cổng."""
    def one(client, index, made, seed, lang="en", plan=None, avoid="",
            attempt=1):
        calls.append({"index": index, "attempt": attempt, "avoid": avoid,
                      "family": plan.family if plan else None})
        return {
            "index": index, "archetype": plan.family if plan else "llm",
            "ok": True, "seconds": 1.0, "why": [],
            "html": f"<p>{index}.{attempt}</p>", "rows": [], "plan": {},
            "data": [], "engine_plan": {}, "hard_negative_profile": {},
            "loai_tai_lieu": f"giấy {index}", "doc_title": "",
            "sheets_asked": 1, "table_asked": False, "chars": 10,
            "rows_wrong": 0, "rows_total": 0,
            "tokens_in": 100, "tokens_out": 200, "tokens_per_second": 1.0,
            "mended": {}, "orphan_runs": 0, "runs": 0, "orphan_share": 0.0,
            "brief": "brief", "stamped": 0, "signed": 0,
            "attempt": attempt, "diversify_hinted": bool(avoid),
            "field_tiers": {}, "field_staging": [], "doc_group": "",
        }
    return one


def drive(tmp_path, monkeypatch, layouts, **kwargs):
    """Chạy `run()` với model giả và thợ vẽ giả. Trả `(báo cáo, lời gọi)`."""
    calls: list = []
    FakeArtist.layouts = list(layouts)
    FakeArtist.made = []
    monkeypatch.setattr(CP, "from_env", lambda **_kw: FakeClient())
    monkeypatch.setattr(CP, "one", fake_one(calls))
    monkeypatch.setattr(CP, "Artist", FakeArtist)
    out = tmp_path / "lô"
    code = CP.run(len(layouts) if "want" not in kwargs else kwargs.pop("want"),
                  out, concurrency=1, seed=7, **kwargs)
    assert code == 0
    return json.loads((out / "compose_report.json").read_text("utf-8")), calls, out


# --------------------------------------------------------------------- sinh lại


def test_a_repeat_is_regenerated_once_with_a_hint_naming_the_overlap(
        tmp_path, monkeypatch):
    """Tờ 1 trùng tờ 0 -> gọi model lần hai, và lần hai PHẢI mang câu nhắc."""
    report, calls, _out = drive(tmp_path, monkeypatch,
                                [SAME, SAME, FRESH], want=2)
    assert [c["attempt"] for c in calls] == [1, 1, 2]
    assert calls[0]["avoid"] == "" and calls[1]["avoid"] == ""
    assert "Do not repeat the last layout" in calls[2]["avoid"]
    assert "`Table`" in calls[2]["avoid"]        # nêu đúng khối đã chồng
    div = report["diversity"]
    assert div["rejected_for_collision"] == 1
    assert div["pages_measured"] == 2            # tờ bị loại không vào cửa sổ
    assert div["kept_despite_collision"] == 0


def test_the_discarded_call_is_still_paid_for_in_the_token_total(
        tmp_path, monkeypatch):
    """Lời gọi bị vứt vẫn tốn token. Cộng token chỉ trên `made` là báo một
    cái giá rẻ hơn cái giá đã trả -- và đúng con số ấy đi thẳng vào phép suy
    "20 000 tờ ≈ N giờ"."""
    report, calls, _out = drive(tmp_path, monkeypatch,
                                [SAME, SAME, FRESH], want=2)
    assert len(calls) == 3
    assert report["tokens_out"] == 3 * 200       # ba lời gọi, không phải hai
    assert report["diversity"]["regeneration"]["calls"] == 1
    assert report["diversity"]["regeneration"]["tokens_out"] == 200


def test_a_repeat_that_runs_out_of_attempts_is_kept_and_marked(
        tmp_path, monkeypatch):
    """Sinh lại mà vẫn trùng thì NHẬN -- nhưng nói ra là đã nhận dù trùng."""
    report, calls, _out = drive(tmp_path, monkeypatch,
                                [SAME, SAME, SAME], want=2)
    assert [c["attempt"] for c in calls] == [1, 1, 2]
    div = report["diversity"]
    assert div["rejected_for_collision"] == 1
    assert div["kept_despite_collision"] == 1
    assert div["pages_measured"] == 2


def test_attempts_one_never_regenerates_but_still_records_the_repeat(
        tmp_path, monkeypatch):
    report, calls, _out = drive(tmp_path, monkeypatch, [SAME, SAME], want=2,
                                attempts=1)
    assert [c["attempt"] for c in calls] == [1, 1]
    assert report["diversity"]["rejected_for_collision"] == 0
    assert report["diversity"]["kept_despite_collision"] == 1


# ------------------------------------------------------------------ đối chứng


def test_the_control_arm_measures_the_repeat_without_rejecting_it(
        tmp_path, monkeypatch):
    """`--no-diversity`: cùng một thước, khác ở chỗ có hành động hay không.

    Nếu nhánh đối chứng thôi đo thì hai lượt chạy A/B không so được với
    nhau, và cả phép thử mất nghĩa."""
    report, calls, _out = drive(tmp_path, monkeypatch, [SAME, SAME], want=2,
                                diversity=False, steer=False)
    assert [c["attempt"] for c in calls] == [1, 1]
    div = report["diversity"]
    assert div["enabled"] is False and div["coverage_steer"] is False
    assert div["rejected_for_collision"] == 0
    # ...nhưng số "còn vượt ngưỡng" vẫn có, và đó là con số nhánh này giao ra
    assert div["geometry"]["over_ceiling"] == 1
    assert div["geometry"]["nearest_jaccard"]["max"] == 1.0


# -------------------------------------------------------------------- báo cáo


def test_performance_md_grows_a_diversity_section(tmp_path, monkeypatch):
    _report, _calls, out = drive(tmp_path, monkeypatch, [SAME, SAME, FRESH],
                                 want=2)
    page = (out / "performance.md").read_text("utf-8")
    assert "## Đa dạng" in page
    assert "Loại vì trùng bố cục" in page
    assert "Khoảng Jaccard" in page


def test_a_run_with_no_drawer_still_finishes_and_says_it_could_not_measure(
        tmp_path, monkeypatch):
    """`--no-draw`: không thợ vẽ, nên không đo được hình học. Tờ vẫn NHẬN --
    phép đo thiếu không được biến thành một lý do loại tờ."""
    report, calls, _out = drive(tmp_path, monkeypatch, [], want=2,
                                no_draw=True)
    assert [c["attempt"] for c in calls] == [1, 1]
    div = report["diversity"]
    assert div["geometry_unavailable"] == 2
    assert div["pages_measured"] == 0
    assert div["rejected_for_collision"] == 0


def test_calls_jsonl_keeps_its_promise_of_one_line_per_call(tmp_path,
                                                            monkeypatch):
    """Tên file hứa "một dòng một lời gọi". Lời gọi bị vứt cũng là một lời
    gọi -- bỏ nó ra thì biểu đồ dựng từ file này vẽ một lượt chạy rẻ hơn lượt
    chạy đã xảy ra."""
    _report, calls, out = drive(tmp_path, monkeypatch, [SAME, SAME, FRESH],
                                want=2)
    lines = [json.loads(line) for line
             in (out / "calls.jsonl").read_text("utf-8").splitlines()]
    assert len(lines) == len(calls) == 3
    dropped = [row for row in lines if row.get("discarded")]
    assert len(dropped) == 1
    assert dropped[0]["ok"] is False and dropped[0]["attempt"] == 1
    assert dropped[0]["jaccard"] == 1.0
