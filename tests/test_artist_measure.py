"""`agent/compose_page.py::Artist` -- kênh ĐO, và ba cách nó có thể treo.

Lớp `Artist` giờ nhận hai loại việc: vẽ (không ai đợi) và đo (một luồng sinh
đang đứng đợi trên `slot["done"]`). Loại thứ hai là loại nguy hiểm: quên
`set()` một lần là một luồng sinh đứng đủ `timeout` giây, và với mười tờ còn
trong hàng đợi thì đó là gần một giờ im lặng.

Không test nào dưới đây mở Chromium -- chúng thay `Drawer` bằng một bản giả,
vì thứ đang kiểm là GIAO THỨC HÀNG ĐỢI, không phải phép dàn trang.
"""

from __future__ import annotations

import threading
import time

from agent.compose_page import Artist


class FakeDrawer:
    """Đủ hình dạng cho vòng lặp của `Artist`, không mở trình duyệt nào."""

    def __init__(self, record=None, blow_up: bool = False, slow: float = 0.0):
        self.record = record if record is not None else {"layout_annotations": []}
        self.blow_up = blow_up
        self.slow = slow
        self.rows: list = []
        self.measured: list = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def measure(self, html, stem, archetype="llm"):
        if self.slow:
            time.sleep(self.slow)
        if self.blow_up:
            raise RuntimeError("chromium đã chết")
        self.measured.append((html, stem, archetype))
        return self.record

    def draw(self, path, passed):
        return f"  vẽ {path.stem}", True


def artist_with(monkeypatch, drawer):
    """Một `Artist` đã chạy, với `synthgen.draw_llm.Drawer` bị thay."""
    import synthgen.draw_llm as draw_llm

    monkeypatch.setattr(draw_llm, "Drawer", lambda out: drawer)
    art = Artist(out=None)
    art.start()
    return art


def test_a_measurement_comes_back_with_the_record_the_drawer_built(monkeypatch):
    drawer = FakeDrawer(record={"layout_annotations": [{"layout_class": "Title"}]})
    art = artist_with(monkeypatch, drawer)
    try:
        got = art.measure("<p>x</p>", "stem0", "invoice_detailed")
        assert got == drawer.record
        assert drawer.measured == [("<p>x</p>", "stem0", "invoice_detailed")]
    finally:
        art.close()


def test_a_drawer_that_throws_mid_measurement_still_wakes_the_waiter(monkeypatch):
    """Ngoại lệ trong lúc đo KHÔNG được để luồng sinh đứng tới hết `timeout`.

    `try/finally` quanh `slot["done"].set()` là chỗ duy nhất luật này đọc
    được, và một test là chỗ duy nhất nó không lặng lẽ biến mất."""
    art = artist_with(monkeypatch, FakeDrawer(blow_up=True))
    try:
        started = time.time()
        assert art.measure("<p>x</p>", "stem0", timeout=30) is None
        assert time.time() - started < 5          # trả lời ngay, không đợi hết hạn
    finally:
        art.close()


def test_a_measurement_that_runs_past_its_deadline_returns_none(monkeypatch):
    art = artist_with(monkeypatch, FakeDrawer(slow=2.0))
    try:
        assert art.measure("<p>x</p>", "stem0", timeout=0.2) is None
    finally:
        art.close()


def test_a_dead_artist_answers_none_instead_of_blocking(monkeypatch):
    """Thợ vẽ chưa chạy (hay đã chết) thì `measure` phải trả `None` NGAY.

    Không có nhánh này thì một lượt chạy trên máy thiếu `playwright` đứng
    `timeout` giây cho MỖI tờ."""
    art = Artist(out=None)                        # chưa `start()`
    assert art.measure("<p>x</p>", "stem0") is None


def test_draining_a_dead_artist_wakes_every_measurement_still_queued(monkeypatch):
    """`_drain()` nuốt hàng đợi khi thợ vẽ chết -- nó cũng phải ĐÁNH THỨC.

    Nuốt mà không `set()` là đúng cái treo `_drain` sinh ra để tránh."""
    art = Artist(out=None)
    art.why = ""                                   # còn "sống" với `measure`
    slots = []
    for i in range(3):
        slot = {"record": "chưa đụng tới", "done": threading.Event()}
        slots.append(slot)
        art.queue.put(("measure", "<p></p>", f"s{i}", "llm", slot))
    art.queue.put(None)
    art._drain()
    assert all(slot["done"].is_set() for slot in slots)


def test_drawing_and_measuring_share_one_queue_in_order(monkeypatch):
    """Hai loại việc, một hàng đợi, thứ tự nhận là thứ tự làm."""
    from pathlib import Path

    drawer = FakeDrawer()
    art = artist_with(monkeypatch, drawer)
    try:
        art.put(Path("/tmp/llm_x_0001.html"), True)
        assert art.measure("<p>y</p>", "stem1") == drawer.record
    finally:
        art.close()
    assert drawer.measured == [("<p>y</p>", "stem1", "llm")]
