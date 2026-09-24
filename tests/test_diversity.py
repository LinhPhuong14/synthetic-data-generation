"""`agent/diversity.py` -- trí nhớ đa dạng dùng chung cả lô.

Phần này là NGƯỜI GỌI còn thiếu của `agent/coverage.py` + `agent/
fingerprint.py`, nên phần lớn test dưới đây kiểm đúng một điều: nó gọi
đúng, nhớ đúng, và an toàn khi nhiều luồng cùng gọi. Không test nào vẽ ảnh
hay gọi model.
"""

from __future__ import annotations

import random
import threading

from agent.diversity import Collision, DiversityWarden, diversify_hint
from agent.fingerprint import GRID_ROWS, geometry_fingerprint
from agent.grammar import FAMILIES


def box(label, x0, y0, x1, y1, page=1):
    return {"layout_class": label, "bbox": [x0, y0, x1, y1],
            "page_number": page}


SHEET = [box("Page-Header", 0, 0, 1000, 80), box("Title", 200, 100, 800, 180),
         box("Table", 0, 250, 1000, 700), box("Text", 0, 750, 1000, 900)]
OTHER = [box("Text", 0, 0, 500, 400)]


# ----------------------------------------------------------------------- rút plan


def test_draw_returns_a_plan_and_the_fingerprint_that_was_already_computed():
    """`sample_with_coverage` đã tính dấu vân; gọi `fingerprint()` lần nữa ở
    caller là dựng lại một thứ vừa có."""
    from agent.fingerprint import fingerprint

    warden = DiversityWarden()
    plan, fp = warden.draw(FAMILIES["hospital_bill"], random.Random(0))
    assert plan.family == "hospital_bill"
    assert fingerprint(plan) == fp


def test_drawing_feeds_the_shared_coverage_memory():
    """Mục đích của cả module: hai tờ liên tiếp KHÔNG còn là hai lần bốc độc
    lập. `plans_drawn` phải tăng theo mỗi lần rút."""
    warden = DiversityWarden()
    rng = random.Random(0)
    for _ in range(5):
        warden.draw(FAMILIES["hospital_bill"], rng)
    assert warden.metrics()["plans_drawn"] >= 5


def test_a_family_with_few_combinations_still_returns_a_plan_not_an_error():
    """Rút cạn `plan_retries` mà vẫn trùng thì GỬI ĐI, chỉ ghi sổ.

    Bỏ hẳn một tờ vì family cạn tổ hợp là để grammar quyết số trang của cả
    lô -- một lô thiếu trang vì quá khó chiều là một lô hỏng theo cách khác."""
    from agent.grammar import Branch, Grammar

    tiny = Grammar(family="tiny", branches=(Branch("a", ("x",)),), constraints=())
    warden = DiversityWarden(plan_retries=2)
    rng = random.Random(0)
    fps = []
    for _ in range(4):
        # Nhận NGAY sau mỗi lần rút: cửa sổ so trùng của `draw()` là những tờ
        # ĐÃ NHẬN, nên rút cả bốn rồi mới nhận thì không lần nào thấy cái gì
        # đứng trước nó -- đúng như lúc chạy thật, nơi tờ trước đã xong.
        plan, fp = warden.draw(tiny, rng)
        warden.accept(fp, None)
        fps.append(fp)
    assert len({fp.fine for fp in fps}) == 1        # chỉ có một tổ hợp
    assert warden.metrics()["plan_collisions"] >= 1  # và nó đã được ghi sổ


# ------------------------------------------------------------------ gác hình học


def test_a_page_that_lands_where_a_recent_one_landed_is_a_collision():
    warden = DiversityWarden()
    first = geometry_fingerprint(SHEET)
    assert warden.inspect(first) is None            # chưa có gì để trùng
    warden.accept(None, first, key=0)
    hit = warden.inspect(geometry_fingerprint(SHEET))
    assert hit is not None
    assert hit.against == 0 and hit.jaccard == 1.0 and hit.hint


def test_a_page_that_lands_elsewhere_is_not_a_collision():
    warden = DiversityWarden()
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    assert warden.inspect(geometry_fingerprint(OTHER)) is None


def test_inspect_changes_nothing_so_it_can_be_asked_twice():
    """Tách `inspect` khỏi `accept` để caller chọn giữa sinh lại và nhận mà
    không phải lùi lại một lần ghi."""
    warden = DiversityWarden()
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    target = geometry_fingerprint(SHEET)
    assert warden.inspect(target).jaccard == warden.inspect(target).jaccard
    assert warden.metrics()["pages_measured"] == 1


def test_a_rejected_page_never_enters_the_window():
    """Tờ bị loại không được chiếm chỗ: tờ sau phải so với tờ ĐÃ NHẬN."""
    warden = DiversityWarden()
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    hit = warden.inspect(geometry_fingerprint(SHEET))
    warden.reject(1, hit, attempt=1)
    got = warden.metrics(pages=1)
    assert got["rejected_for_collision"] == 1
    assert got["pages_measured"] == 1               # vẫn chỉ một tờ trong cửa sổ


def test_a_page_beyond_the_window_is_forgotten():
    warden = DiversityWarden(window=2)
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    for i in (1, 2):
        warden.accept(None, geometry_fingerprint(OTHER + [box("X", i, i, 900, 900)]),
                     key=i)
    assert warden.inspect(geometry_fingerprint(SHEET)) is None


def test_an_unmeasured_page_is_accepted_and_counted_separately():
    """`geo=None` (không vẽ được, hết hạn chờ, `--no-draw`) KHÔNG được lẫn
    vào "không tờ nào trùng": nó là một phép đo thiếu, và nó phải đọc được."""
    warden = DiversityWarden()
    warden.accept(None, None, key=0)
    warden.accept(None, geometry_fingerprint([]), key=1)
    got = warden.metrics(pages=2)
    assert got["geometry_unavailable"] == 2
    assert got["pages_measured"] == 0
    assert warden.inspect(None) is None


def test_disabled_still_measures_everything_it_would_have_measured():
    """Nhánh đối chứng của phép thử A/B: cùng một thước, khác ở chỗ có hành
    động theo số đo hay không. `enabled=False` mà thôi đo là hai lượt chạy
    không so được với nhau."""
    off = DiversityWarden(enabled=False)
    off.accept(None, geometry_fingerprint(SHEET), key=0)
    hit = off.inspect(geometry_fingerprint(SHEET))
    assert hit is not None and hit.jaccard == 1.0   # vẫn ĐO
    assert off.metrics(pages=1)["enabled"] is False


# ------------------------------------------------------------------- câu nhắc


def test_the_hint_names_the_blocks_that_actually_overlapped():
    """Câu nhắc dựng TỪ ô chồng nhau, không phải một câu viết sẵn."""
    a = geometry_fingerprint(SHEET)
    hint = diversify_hint(a, a, GRID_ROWS)
    assert "`Table`" in hint
    assert "sheet 1" in hint
    assert hint.count("`") <= 8                     # nhiều nhất ba khối


def test_two_pages_that_share_no_cell_get_no_hint():
    a, b = geometry_fingerprint(SHEET), geometry_fingerprint(OTHER)
    assert diversify_hint(a, b, GRID_ROWS) == "" or a.cells & b.cells


def test_the_hint_mentions_a_sheet_number_so_multipage_repeats_read_right():
    later = [box("Table", 0, 250, 1000, 700, page=3)]
    fp = geometry_fingerprint(later)
    assert "sheet 3" in diversify_hint(fp, fp, GRID_ROWS)


# ------------------------------------------------------------------- nhiều luồng


def test_the_warden_survives_every_thread_drawing_at_once():
    """`run()` sinh trên `ThreadPoolExecutor`, nên trí nhớ này bị chạm bởi
    `concurrency` luồng cùng lúc. Không mất lần rút nào, không ném."""
    warden = DiversityWarden()
    names = sorted(FAMILIES)[:8]
    errors: list = []

    def churn(seed: int) -> None:
        rng = random.Random(seed)
        try:
            for i in range(20):
                plan, fp = warden.draw(FAMILIES[names[i % len(names)]], rng)
                geo = geometry_fingerprint(
                    [box("Text", 0, seed * 7 % 900, 500, 999)])
                warden.accept(fp, geo, key=(seed, i))
                warden.inspect(geo)
        except Exception as error:                  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=churn, args=(s,)) for s in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    got = warden.metrics(pages=120)
    assert got["plans_drawn"] >= 120
    assert got["pages_measured"] == 120


# --------------------------------------------------------------------- báo cáo


def test_metrics_has_every_key_the_report_and_performance_page_read():
    """`_write_performance` đọc thẳng những khoá này; thiếu một khoá thì ta
    đổi một con số sai lấy một `KeyError` giữa lúc ghi báo cáo."""
    warden = DiversityWarden()
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    got = warden.metrics(pages=1)
    for key in ("enabled", "window", "jaccard_ceiling", "pages_measured",
                "plans_drawn", "plan_collisions", "rejected_for_collision",
                "rejected_share", "kept_despite_collision",
                "geometry_unavailable", "plan_fingerprints", "geometry",
                "collisions"):
        assert key in got, key
    assert set(got["geometry"]) >= {"nearest_jaccard", "nearest_hamming",
                                    "jaccard_histogram", "over_ceiling", "grid"}


def test_the_rejection_share_is_out_of_calls_that_reached_the_gate():
    """"13% số lượt bị loại" và "15% số tờ nhận từng bị loại" là hai câu khác
    nhau, và câu đầu mới là cái giá phải trả.

    Mẫu số là tờ ĐO ĐƯỢC cộng tờ bị loại: một tờ không dàn ra được chưa bao
    giờ tới cổng này, nên nó không phải một lượt cổng ấy cho qua."""
    warden = DiversityWarden()
    warden.accept(None, geometry_fingerprint(SHEET), key=0)
    hit = warden.inspect(geometry_fingerprint(SHEET))
    warden.reject(1, hit, attempt=1)
    warden.accept(None, None, key=2)            # không đo được -- ngoài mẫu số
    got = warden.metrics(pages=3)
    assert got["pages_measured"] == 1 and got["geometry_unavailable"] == 1
    assert got["rejected_share"] == round(1 / 2, 4)
    assert got["pages_kept"] == 3


def test_a_collision_serialises_to_something_json_can_hold():
    import json

    hit = Collision(against=7, jaccard=0.8123, hamming=0.05, hint="x")
    assert json.loads(json.dumps(hit.as_dict())) == {
        "against": 7, "jaccard": 0.8123, "hamming": 0.05}


# ----------------------------------------------------------------- judge()


def test_judge_accepts_a_fresh_page_and_puts_it_in_the_window():
    warden = DiversityWarden()
    geo = geometry_fingerprint(SHEET)
    collision, taken = warden.judge(None, geo, key=0)
    assert collision is None and taken is True
    assert warden.metrics()["pages_measured"] == 1


def test_judge_rejects_a_repeat_and_keeps_it_out_of_the_window():
    warden = DiversityWarden()
    warden.judge(None, geometry_fingerprint(SHEET), key=0)
    collision, taken = warden.judge(None, geometry_fingerprint(SHEET), key=1)
    assert taken is False
    assert collision is not None and collision.against == 0
    got = warden.metrics()
    assert got["rejected_for_collision"] == 1
    assert got["pages_measured"] == 1           # tờ bị loại không chiếm chỗ


def test_judge_with_force_takes_the_repeat_anyway_and_says_so():
    """Lượt gọi cuối: vẫn đo, vẫn ghi là trùng, nhưng NHẬN."""
    warden = DiversityWarden()
    warden.judge(None, geometry_fingerprint(SHEET), key=0)
    collision, taken = warden.judge(None, geometry_fingerprint(SHEET), key=1,
                                    force=True)
    assert taken is True and collision is not None
    got = warden.metrics()
    assert got["kept_despite_collision"] == 1
    assert got["rejected_for_collision"] == 0
    assert got["pages_measured"] == 2


def test_judge_with_the_gate_disabled_takes_everything_but_still_measures():
    off = DiversityWarden(enabled=False)
    off.judge(None, geometry_fingerprint(SHEET), key=0)
    collision, taken = off.judge(None, geometry_fingerprint(SHEET), key=1)
    assert taken is True
    assert collision is not None and collision.jaccard == 1.0   # vẫn ĐO
    assert off.metrics()["rejected_for_collision"] == 0
    # ...và số "còn vượt ngưỡng" vẫn đếm được, vì cả hai tờ đều vào cửa sổ:
    # đó là con số nhánh đối chứng phải giao ra.
    assert off.metrics()["geometry"]["over_ceiling"] == 1


def test_judge_lets_no_two_simultaneous_twins_both_through():
    """Cuộc đua mà `judge()` sinh ra để đóng.

    `inspect()` rồi `accept()` là hai lần khoá: hai luồng xong cùng lúc đều
    nhìn một cửa sổ CHƯA có tờ kia, đều thấy sạch, đều được nhận. Ở đây tám
    luồng cùng nộp một tờ giống hệt nhau -- đúng một tờ được nhận."""
    warden = DiversityWarden()
    taken: list = []
    barrier = threading.Barrier(8)

    def submit(i: int) -> None:
        geo = geometry_fingerprint(SHEET)
        barrier.wait()                          # nộp cùng một lúc
        _hit, ok = warden.judge(None, geo, key=i)
        if ok:
            taken.append(i)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(taken) == 1
    assert warden.metrics()["rejected_for_collision"] == 7


def test_judge_never_rejects_a_page_it_could_not_measure():
    """Không đo được là CHƯA BIẾT, không phải "không trùng" -- và tuyệt đối
    không phải "trùng". Loại một tờ vì phép đo hỏng là đổi một lỗi lặng lẽ
    lấy một lỗi lặng lẽ đắt hơn."""
    warden = DiversityWarden()
    warden.judge(None, geometry_fingerprint(SHEET), key=0)
    for blank in (None, geometry_fingerprint([])):
        collision, taken = warden.judge(None, blank, key=9)
        assert collision is None and taken is True
    assert warden.metrics()["geometry_unavailable"] == 2
