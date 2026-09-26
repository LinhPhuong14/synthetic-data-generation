"""`agent/client.py` -- reply CỤT vì chạm trần token, nới trần rồi viết lại.

Dựng từ ca trượt thật, không phải ví dụ bịa: `data/pilot17` (60 tờ,
`Qwen3.8-27B-FP8`, seed 0) có 18 tờ -- 30% cả lô, lý do trượt LỚN NHẤT --
chết với đúng một câu `reply was not JSON`, và không để lại gì để mổ. Chuỗi
`CUT_PILOT17` dưới đây là reply thật của tờ `index 29` (`utility_water`),
chép nguyên từ `compose_report.json::pages[29].why[0]`.

## Vì sao biết chắc là CỤT chứ không phải JSON sai hình

Ba phép đo, cùng chỉ một hướng:

1. Backend ép schema bằng ngữ pháp (`strict: true` + xgrammar) thì reply
   không thể sai hình -- từng token đã bị ngữ pháp ép.
2. Dò thẳng trên server thật (`10.148.20.19:8008`) với `max_tokens=120` và
   `=400`: `finish_reason='length'`, `json.loads` ném "Unterminated string",
   tiền tố `'{\\n  "plan": {\\n    "doc_kind": …'` giống hệt 18 tờ kia.
3. Nếu 18 tờ ấy chạy đúng tới `budget(sheets)` thì tốc độ suy ra là 22--46
   tok/s (trung vị 40,0) -- nằm gọn trong khoảng 10,9--47,9 tok/s đo được
   trên 42 lời gọi trả lời được của CÙNG lô. 18/18 tờ khớp.

Không có socket nào mở ở đây: `Client._post` bị monkeypatch, giống
`tests/test_client.py`."""

from __future__ import annotations

import pytest

from agent.client import Client, LLMError

SCHEMA = {"type": "object", "properties": {"plan": {"type": "object"},
                                           "html": {"type": "string"}}}

# Reply THẬT của `data/pilot17` tờ 29, cắt giữa chừng đúng chỗ nó đứt.
CUT_PILOT17 = ('{\n  "plan": {\n    "doc_kind": "Hóa đơn tiền nước",\n'
               '    "doc_slug": "utility_water",\n    "doc_ti')


def _reply(content: str, finish: str, spent: int = 0) -> dict:
    choice: dict = {"message": {"content": content}}
    if finish:
        choice["finish_reason"] = finish
    return {"choices": [choice], "usage": {"completion_tokens": spent}}


def a_client(**kw) -> Client:
    return Client(url="http://x", model="m", **kw)


def _cut_then_whole(monkeypatch, cuts: int, whole: str = '{"html": "<p>x</p>"}'):
    """`_post` trả reply CỤT `cuts` lần đầu, rồi trả một reply trọn vẹn.

    Trả danh sách payload mỗi lần `_post` nhận được, để kiểm `max_tokens`
    thật sự nới ra giữa các lần -- gửi lại y nguyên trần cũ thì chỉ sinh lại
    đúng một reply cụt như cũ."""
    seen: list[dict] = []
    state = {"n": 0}

    def fake_post(self, payload):
        seen.append(payload)
        state["n"] += 1
        if state["n"] <= cuts:
            return _reply(CUT_PILOT17, "length",
                          spent=payload.get("max_tokens") or 0)
        return _reply(whole, "stop", spent=120)

    monkeypatch.setattr(Client, "_post", fake_post)
    return seen


# ------------------------------------------------- cụt thì nới, không thì thôi


def test_a_cut_reply_is_retried_with_a_wider_ceiling(monkeypatch):
    """Ca pilot17 tờ 29: xin 13 000 (2 tờ), cụt, nới rồi qua."""
    seen = _cut_then_whole(monkeypatch, cuts=1)
    got, usage = a_client().decide_with_usage("sys", "user", SCHEMA,
                                              max_tokens=13_000)
    assert got == {"html": "<p>x</p>"}
    assert len(seen) == 2, "phải gửi lại đúng một lần"
    assert seen[0]["max_tokens"] == 13_000
    assert seen[1]["max_tokens"] > seen[0]["max_tokens"], "trần phải NỚI ra"
    # Token của lần bỏ đi vẫn phải đếm được -- nếu không báo cáo chi phí của
    # lượt chạy nói thấp hơn cái đã thật sự tiêu.
    assert usage["discarded_completion_tokens"] == 13_000
    assert usage["stretches"] == 1


def test_the_timeout_stretches_with_the_ceiling(monkeypatch):
    """Nới trần mà giữ nguyên hạn chờ thì chỉ đổi kiểu hỏng: tờ vừa đủ chỗ
    viết lại hết hạn chờ giữa đường."""
    seen: list[float] = []
    state = {"n": 0}

    def fake_post(self, payload):
        seen.append(self.timeout)
        state["n"] += 1
        if state["n"] == 1:
            return _reply(CUT_PILOT17, "length", spent=13_000)
        return _reply('{"html": "x"}', "stop", spent=10)

    monkeypatch.setattr(Client, "_post", fake_post)
    a_client().decide_with_usage("sys", "user", SCHEMA,
                                 max_tokens=13_000, timeout=866.0)
    assert seen[1] > seen[0], "hạn chờ phải nới cùng nhịp với trần"


def test_a_reply_that_stays_cut_says_CUT_not_not_JSON(monkeypatch):
    """Hết lượt nới mà vẫn cụt thì câu lỗi phải GỌI TÊN nguyên nhân.

    Đây là chỗ pilot17 mất 18 tờ: câu `reply was not JSON` gộp chung "cụt vì
    chạm trần" với "JSON sai hình" -- hai lỗi chữa bằng hai cách trái nhau --
    nên không ai đọc log mà biết được phải nới trần hay phải sửa schema."""
    _cut_then_whole(monkeypatch, cuts=99)
    with pytest.raises(LLMError) as caught:
        a_client().decide_with_usage("sys", "user", SCHEMA, max_tokens=13_000)
    text = str(caught.value)
    assert "cụt vì chạm trần" in text
    assert "đã nới 2 lần" in text, "phải nói đã thử nới mấy lần"


def test_the_stretch_is_bounded_not_unlimited(monkeypatch):
    """Nới có hạn. Một lời gọi lạc lối phải hỏng NHANH, không ăn hết cửa sổ
    ngữ cảnh -- đúng lời hứa `budget()` đang giữ bằng trần 150 000."""
    seen = _cut_then_whole(monkeypatch, cuts=99)
    with pytest.raises(LLMError):
        a_client().decide_with_usage("sys", "user", SCHEMA, max_tokens=13_000)
    assert len(seen) == 3, "một lần đầu + đúng hai lần nới"


def test_the_stretch_never_passes_the_servers_own_real_ceiling(monkeypatch):
    """Trần THẬT đã dò được của server là giới hạn trên cuối cùng: nới quá nó
    thì `_max_tokens_field` kẹp lại và ta chỉ sinh lại một reply cụt y hệt."""
    seen = _cut_then_whole(monkeypatch, cuts=99)
    client = a_client()
    client._max_output_tokens = 16_384
    with pytest.raises(LLMError):
        client.decide_with_usage("sys", "user", SCHEMA, max_tokens=13_000)
    assert all(p["max_tokens"] <= 16_384 for p in seen)


def test_a_malformed_reply_that_is_NOT_cut_is_not_retried(monkeypatch):
    """`finish_reason` khác `length` thì gửi lại y nguyên chỉ tốn thêm một
    lượt sinh: cùng payload, cùng lỗi. Câu lỗi vẫn phải KHAI `finish_reason`
    để lần sau không ai phải đoán lại từ HTML thô."""
    seen = _cut_then_whole(monkeypatch, cuts=0, whole="khong phai JSON")
    with pytest.raises(LLMError) as caught:
        a_client().decide_with_usage("sys", "user", SCHEMA, max_tokens=13_000)
    assert len(seen) == 1, "không cụt thì KHÔNG gửi lại"
    assert "finish_reason='stop'" in str(caught.value)


def test_a_whole_reply_costs_no_extra_call(monkeypatch):
    """Tờ ngắn không trả giá gì cho cơ chế này -- `max_tokens` là cái TRẦN,
    không phải chỗ đã đặt cọc."""
    seen = _cut_then_whole(monkeypatch, cuts=0)
    got, usage = a_client().decide_with_usage("sys", "user", SCHEMA,
                                              max_tokens=13_000)
    assert got == {"html": "<p>x</p>"}
    assert len(seen) == 1
    assert "discarded_completion_tokens" not in usage


# --------------------- hạn chờ có trần: một máy chủ chết không được giữ 14 giờ


def test_the_stretched_timeout_never_passes_its_ceiling(monkeypatch):
    """Nới hạn chờ tự do thì một máy chủ KHÔNG TRẢ LỜI giữ chỗ 1,8^2 lần hạn
    gốc, và `Client._post` còn thử lại 3 lần trên mỗi hạn ấy.

    Đo bằng một lượt chạy mất trắng: `data/pilot18` 24-09-2026, máy chủ vLLM
    tắt giữa lô, tờ thứ 20 treo **51 025,9 giây (14,2 giờ)** rồi mới báo
    `URLError`; 41 tờ sau thành rác. Hạn rộng không cứu được tờ nào khi máy
    chủ đã chết -- nó chỉ đổi "hỏng nhanh" thành "treo qua đêm"."""
    from agent.client import _PATIENCE_CEILING

    seen: list[float] = []
    state = {"n": 0}

    def fake_post(self, payload):
        seen.append(self.timeout)
        state["n"] += 1
        if state["n"] <= 2:
            return _reply(CUT_PILOT17, "length", spent=13_000)
        return _reply('{"html": "x"}', "stop", spent=10)

    monkeypatch.setattr(Client, "_post", fake_post)
    # Hạn gốc đã sát trần: nới hai lần không được vượt nó.
    a_client().decide_with_usage("sys", "user", SCHEMA,
                                 max_tokens=13_000,
                                 timeout=_PATIENCE_CEILING * 0.9)
    assert len(seen) == 3
    assert all(t <= _PATIENCE_CEILING for t in seen), seen
    assert seen[-1] == _PATIENCE_CEILING, "phải kẹp ĐÚNG ở trần, không dưới"


def test_the_two_patience_ceilings_are_the_same_number():
    """`client.py` không import được `compose_page.py` (vòng import), nên con
    số phải viết hai lần. Hai lần viết là hai chỗ để lệch nhau -- đúng cái
    `AGENTS.md` gọi là "một luật, hai người dựng". Test này là người thứ ba
    đứng giữa: đổi một bên mà quên bên kia thì nó đỏ."""
    from agent.client import _PATIENCE_CEILING
    from agent.compose_page import PATIENCE_CEILING

    assert _PATIENCE_CEILING == PATIENCE_CEILING
