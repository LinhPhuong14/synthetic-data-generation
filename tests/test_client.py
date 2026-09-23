"""`agent/client.py::Client` -- tự dò khả năng server, không đặt tay.

Nothing below opens a socket -- `Client._post` bị monkeypatch để trả lỗi/
phản hồi giả thay vì gửi đi thật, nên file này chạy trong CI không phụ thuộc.

## Vì sao tự dò, không phải một cờ người dùng đặt tay

Bản đầu có một cờ `vllm_extras`/biến môi trường người dùng phải tự khai đúng
cho từng server. Người dùng hỏi thẳng: "sao không tổng quát, cứ thêm model
mới là phải viết thêm một nhánh". Đúng -- nên bản này bỏ hẳn cờ đó: `Client`
gửi thử đầy đủ tính năng trước, đọc CÂU TRẢ LỜI THẬT của server, và chỉ hạ
xuống khi chính server nói nó không hiểu.

Hai chữ ký lỗi khoá lại ở đây đo được thật trên `https://api.openai.com/v1`
(2026-09-21, model `gpt-4o-mini`):

1. `"Unrecognized request arguments supplied: chat_template_kwargs,
   reasoning_effort"` -- hai trường mở rộng riêng của vLLM.
2. `"'additionalProperties' is required to be supplied and to be false"` --
   OpenAI Structured Outputs không chấp nhận trường `data` không khai
   `properties` (cố tình để mở, xem `agent/compose_page.py::schema()`)."""

from __future__ import annotations

import pytest

from agent.client import Client, LLMError, from_env

SCHEMA = {"type": "object", "properties": {"msg": {"type": "string"},
                                           "data": {"type": "object"}}}
OK_RESPONSE = {"choices": [{"message": {"content": "{}"}}], "usage": {}}


def a_client(**kw) -> Client:
    return Client(url="http://x", model="m", **kw)


# --------------------------------------------------------- _payload() shape


def test_payload_defaults_to_full_vllm_shape():
    payload = a_client()._payload("sys", "user", SCHEMA, 0)
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert "chat_template_kwargs" in payload
    assert "reasoning_effort" in payload


def test_payload_after_downgrade_drops_the_vllm_only_fields():
    client = a_client()
    client._vllm_extras = False        # giả lập đã tự dò xong
    payload = client._payload("sys", "user", SCHEMA, 0)
    assert payload["response_format"]["json_schema"]["strict"] is False
    assert "chat_template_kwargs" not in payload
    assert "reasoning_effort" not in payload


# --------------------------------------------------- tự dò trong decide_with_usage


def _fail_once_then_succeed(monkeypatch, message: str):
    """`_post` thất bại đúng MỘT LẦN với `message`, sau đó trả lời hợp lệ.
    Trả về danh sách payload mỗi lần `_post` NHẬN ĐƯỢC, để kiểm nó đổi hình
    dạng đúng cách giữa hai lần gọi."""
    seen: list[dict] = []
    state = {"failed": False}

    def fake_post(self, payload):
        seen.append(payload)
        if not state["failed"]:
            state["failed"] = True
            raise LLMError(f"http://x: HTTP 400 Bad Request -- {message}")
        return OK_RESPONSE

    monkeypatch.setattr(Client, "_post", fake_post)
    return seen


def test_unrecognized_argument_error_downgrades_and_retries_once(monkeypatch):
    seen = _fail_once_then_succeed(
        monkeypatch, '{"error": {"message": '
        '"Unrecognized request arguments supplied: chat_template_kwargs"}}')
    client = a_client()
    client.decide_with_usage("sys", "user", SCHEMA)
    assert len(seen) == 2
    assert "chat_template_kwargs" in seen[0]
    assert "chat_template_kwargs" not in seen[1]
    assert client._vllm_extras is False


def test_additional_properties_error_downgrades_and_retries_once(monkeypatch):
    seen = _fail_once_then_succeed(
        monkeypatch, "'additionalProperties' is required to be supplied "
        "and to be false")
    client = a_client()
    client.decide_with_usage("sys", "user", SCHEMA)
    assert len(seen) == 2
    assert seen[0]["response_format"]["json_schema"]["strict"] is True
    assert seen[1]["response_format"]["json_schema"]["strict"] is False


def test_max_tokens_too_large_error_caps_and_retries_once(monkeypatch):
    """Đo thật trên `gpt-4o-mini` (2026-09-21): xin 28600, server nói thẳng
    trần thật 16384 ngay trong câu lỗi."""
    seen = _fail_once_then_succeed(
        monkeypatch, "max_tokens is too large: 28600. This model supports "
        "at most 16384 completion tokens, whereas you provided 28600.")
    client = a_client()
    client.decide_with_usage("sys", "user", SCHEMA, max_tokens=28600)
    assert len(seen) == 2
    assert seen[0]["max_tokens"] == 28600
    assert seen[1]["max_tokens"] == 16384
    assert client._max_output_tokens == 16384


def test_the_learned_token_cap_is_never_exceeded_on_later_calls(monkeypatch):
    client = a_client()
    client._max_output_tokens = 16384
    payload = client._payload("sys", "user", SCHEMA, max_tokens=50000)
    assert payload["max_tokens"] == 16384


def test_the_learned_token_cap_still_applies_with_no_explicit_request(monkeypatch):
    client = a_client(max_tokens=0)
    client._max_output_tokens = 16384
    payload = client._payload("sys", "user", SCHEMA, max_tokens=0)
    assert payload["max_tokens"] == 16384


def test_the_learned_flag_survives_across_separate_calls(monkeypatch):
    """Lần gọi THỨ HAI trên cùng client không phải trả giá dò lại -- đúng
    điểm mấu chốt: học một lần, dùng cho cả lô."""
    _fail_once_then_succeed(
        monkeypatch, 'Unrecognized request arguments supplied: x')
    client = a_client()
    client.decide_with_usage("sys", "user", SCHEMA)
    assert client._vllm_extras is False

    seen_second: list[dict] = []
    monkeypatch.setattr(Client, "_post",
                        lambda self, payload: (seen_second.append(payload),
                                               OK_RESPONSE)[1])
    client.decide_with_usage("sys", "user", SCHEMA)
    assert len(seen_second) == 1                    # không thử lại lần nào
    assert "chat_template_kwargs" not in seen_second[0]


def test_an_unrelated_error_is_never_treated_as_a_capability_signature(monkeypatch):
    """Lỗi khác (hết hạn chờ, khoá sai...) không được đoán nhầm là 'server
    không hiểu trường lạ' -- ném thẳng, không tự hạ, không thử lại."""
    def fake_post(self, payload):
        raise LLMError("http://x: HTTP 401 Unauthorized -- bad key")

    monkeypatch.setattr(Client, "_post", fake_post)
    client = a_client()
    with pytest.raises(LLMError, match="bad key"):
        client.decide_with_usage("sys", "user", SCHEMA)
    assert client._vllm_extras is True                       # chưa đụng tới


def test_downgrade_is_attempted_at_most_once_per_call(monkeypatch):
    """Server vẫn hỏng SAU KHI đã hạ (một lỗi thật khác, không phải giới
    hạn năng lực) thì ném ra, không lặp vô hạn."""
    calls = {"n": 0}

    def fake_post(self, payload):
        calls["n"] += 1
        raise LLMError("http://x: HTTP 400 Bad Request -- "
                       "Unrecognized request arguments supplied: x")

    monkeypatch.setattr(Client, "_post", fake_post)
    client = a_client()
    with pytest.raises(LLMError):
        client.decide_with_usage("sys", "user", SCHEMA)
    assert calls["n"] == 2                    # lần gốc + đúng một lần hạ cấp


# ------------------------------------------------------------------ from_env


def test_from_env_needs_no_provider_specific_configuration(monkeypatch):
    """Không còn biến môi trường nào để khai 'server này có phải vLLM
    không' -- đúng câu hỏi gốc: thêm provider mới không cần sửa gì ở đây."""
    monkeypatch.delenv("VLM_LLM_URL", raising=False)
    monkeypatch.setenv("VLM_LLM_URL", "https://api.openai.com/v1")
    client = from_env()
    assert client is not None
    assert client._vllm_extras is True         # vẫn lạc quan cho tới lần gọi đầu


def test_from_env_returns_none_without_a_url(monkeypatch):
    monkeypatch.delenv("VLM_LLM_URL", raising=False)
    assert from_env() is None


# ==========================================================================
# ÉP SCHEMA, TRANH CHẤP LUỒNG, VÀ 429
#
# Ba lỗi thêm vào ngày 23-09-2026, cả ba im lặng theo cùng một kiểu: request
# hỏng, tờ giấy mất, báo cáo chỉ ghi "model không trả lời". Không lỗi nào
# hiện ra trong ảnh, nên không lỗi nào tự lộ -- chúng chỉ lộ khi tỉ lệ qua
# cổng tụt mà không ai giải thích được.
# ==========================================================================

from agent.client import closed                                # noqa: E402

SHUT_SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}},
               "required": ["a"], "additionalProperties": False}
REFUSAL = ("HTTP 400 Bad Request -- Unrecognized request arguments supplied: "
           "chat_template_kwargs, reasoning_effort")


def test_a_closed_schema_is_recognised_and_an_open_one_is_not():
    assert closed(SHUT_SCHEMA)
    assert not closed(SCHEMA), "`data: {type: object}` không properties là MỞ"
    assert not closed({"type": "object"})
    assert not closed({"type": "object", "properties": {"a": {"type": "string"}},
                       "required": [], "additionalProperties": False}), \
        "`required` thiếu khoá cũng là mở -- đúng luật OpenAI strict"
    assert closed({"type": "array", "items": SHUT_SCHEMA})


def test_a_closed_schema_asks_for_enforcement_even_on_a_hosted_backend():
    """Đây là cả lý do `closed()` tồn tại.

    Đo thật trên `gpt-4.1-mini` (23-09-2026), cùng schema cùng lời nhờ:
    `strict: false` -> 812 token, trả về các khoá CON của `plan` ở mức gốc,
    KHÔNG có `data`, `rows`, `html`. `strict: true` -> 5 192 token, đủ bốn
    khoá, `html` 11 847 ký tự vẽ được. Không ép thì model không theo, và
    "model kém" là chẩn đoán sai."""
    client = a_client()
    client._vllm_extras = False                    # như đã học: backend hosted
    shut = client._payload("s", "u", SHUT_SCHEMA, 0)
    assert shut["response_format"]["json_schema"]["strict"] is True
    # Schema MỞ trên backend hosted vẫn phải tắt, nếu không OpenAI trả 400 --
    # `planner.py`/`compose_layout.py` vẫn gửi schema mở, và chúng không được
    # hỏng vì một thay đổi của `compose_page.py`.
    assert client._payload("s", "u", SCHEMA, 0)[
        "response_format"]["json_schema"]["strict"] is False


def test_a_thread_that_lost_the_downgrade_race_still_retries(monkeypatch):
    """`run()` chia MỘT `Client` cho cả `ThreadPoolExecutor`.

    Luồng A nhận 400, hạ cờ, thử lại, xong. Luồng B đã gửi payload mang
    trường sai TỪ TRƯỚC và cũng nhận 400 -- nhưng tới lúc B xử lý lỗi thì cờ
    đã `False`. Điều kiện cũ hỏi `self._vllm_extras` nên B không thử lại mà
    ném thẳng: đo được 3 trên 8 tờ mất trắng ở song song 4, và tỉ lệ ấy lớn
    dần theo mức song song."""
    client = a_client()
    client._vllm_extras = False                    # luồng A đã học xong
    calls = []

    def once(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise LLMError(REFUSAL)                # lỗi của request B đã gửi
        return OK_RESPONSE

    monkeypatch.setattr(client, "_post", once)
    client.decide_with_usage("s", "u", SHUT_SCHEMA)
    assert len(calls) == 2, "luồng thua cuộc đua phải thử lại, không ném thẳng"


def _raiser(code: str, headers=None, body=b"{}"):
    import urllib.error

    class Boom(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", int(code), "nope", headers or {}, None)

        def read(self):
            return body

    return Boom


def test_a_rate_limit_waits_and_tries_again(monkeypatch):
    """429 là 4xx DUY NHẤT đáng thử lại: nó không phán quyết NỘI DUNG, nó
    phán quyết THỜI ĐIỂM. Cùng payload gửi lại sau vài giây thì qua. Đo
    được: 2 trên 8 tờ mất trắng vì `Rate limit reached`, cả hai chỉ cần chờ.

    Nghỉ theo `Retry-After` khi máy chủ nói ra -- đoán một con số trong khi
    server vừa đưa con số đúng là tự chuốc thêm một lần 429 nữa."""
    import json as _json

    client = a_client(retries=2)
    slept: list[float] = []
    monkeypatch.setattr("agent.client.time.sleep", slept.append)
    Boom = _raiser("429", {"Retry-After": "7"}, b'{"error": "rate"}')
    hits = {"n": 0}

    class Ok:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _json.dumps(OK_RESPONSE).encode()

    def urlopen(request, timeout=None):
        hits["n"] += 1
        if hits["n"] == 1:
            raise Boom()
        return Ok()

    monkeypatch.setattr("agent.client.urllib.request.urlopen", urlopen)
    client._post({"model": "m"})
    assert hits["n"] == 2, "429 phải được thử lại"
    assert slept and slept[0] >= 7.0, f"phải nghỉ theo Retry-After, nghỉ {slept}"


def test_a_four_hundred_is_still_not_retried(monkeypatch):
    """Ngược lại, và đây là lý do 429 phải là ngoại lệ HẸP: 400 là phán quyết
    về chính payload, gửi lại y nguyên chỉ tốn thêm thời gian."""
    client = a_client(retries=2)
    monkeypatch.setattr("agent.client.time.sleep", lambda *_: None)
    Boom = _raiser("400", {}, b'{"error": "bad"}')
    hits = {"n": 0}

    def urlopen(request, timeout=None):
        hits["n"] += 1
        raise Boom()

    monkeypatch.setattr("agent.client.urllib.request.urlopen", urlopen)
    with pytest.raises(LLMError):
        client._post({"model": "m"})
    assert hits["n"] == 1, f"400 gửi lại {hits['n']} lần"


def test_a_truncated_reply_is_retried_not_raised(monkeypatch):
    """`http.client.IncompleteRead` KHÔNG phải `OSError`.

    Ba nhánh `except` cũ không nhánh nào bắt nó, nên một phản hồi đứt giữa
    chừng không thành "thử lại" mà thành một traceback ném lên
    `ThreadPoolExecutor` -- và cả lượt chạy chết: đo được 23-09-2026, lô 12
    tờ không để lại `compose_report.json` nào, không giữ được tờ nào.

    Đúng loại lỗi đáng thử lại nhất: payload không sai, đường truyền sai."""
    import http.client
    import json as _json

    client = a_client(retries=2)
    monkeypatch.setattr("agent.client.time.sleep", lambda *_: None)
    hits = {"n": 0}

    class Ok:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _json.dumps(OK_RESPONSE).encode()

    def urlopen(request, timeout=None):
        hits["n"] += 1
        if hits["n"] == 1:
            raise http.client.IncompleteRead(b"mot nua")
        return Ok()

    monkeypatch.setattr("agent.client.urllib.request.urlopen", urlopen)
    client._post({"model": "m"})
    assert hits["n"] == 2, "phản hồi đứt phải được thử lại"


def test_a_truncated_reply_is_retried_not_fatal(monkeypatch):
    """`http.client.IncompleteRead` kế thừa thẳng `Exception` -- KHÔNG phải
    `OSError`, KHÔNG phải `ValueError`, KHÔNG phải `URLError`.

    Nên trước bản sửa nó trượt qua mọi nhánh `except` của `_post`, thoát ra
    ngoài, giết worker và cả lượt chạy. Đo được: một lô 12 tờ chết ở tờ thứ
    tư với `IncompleteRead(31654 bytes read)`.

    Câu trả lời càng dài càng dễ đứt, và đúng những tờ dài mới là tờ cần --
    nên đây không phải ca hiếm, nó là ca thường gặp nhất ở chỗ đắt nhất.

    Đứt đường truyền là lỗi ĐƯỜNG TRUYỀN, không phải phán quyết về payload:
    thử lại, cùng nhánh với `URLError`."""
    import http.client
    import json as _json

    client = a_client(retries=2)
    monkeypatch.setattr("agent.client.time.sleep", lambda *_: None)
    hits = {"n": 0}

    class Ok:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _json.dumps(OK_RESPONSE).encode()

    class Torn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): raise http.client.IncompleteRead(b"half a reply")

    def urlopen(request, timeout=None):
        hits["n"] += 1
        return Torn() if hits["n"] == 1 else Ok()

    monkeypatch.setattr("agent.client.urllib.request.urlopen", urlopen)
    got = client._post({"model": "m"})
    assert got == OK_RESPONSE
    assert hits["n"] == 2, "đứt giữa chừng phải được thử lại"


def test_a_transport_error_that_never_clears_raises_cleanly(monkeypatch):
    """Thử lại có hạn: đứt mãi thì ném `LLMError` để `one()` ghi vào `why`
    của TỜ ấy, chứ không để một ngoại lệ lạ giết cả `ThreadPoolExecutor`."""
    import http.client

    client = a_client(retries=1)
    monkeypatch.setattr("agent.client.time.sleep", lambda *_: None)

    class Torn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): raise http.client.IncompleteRead(b"")

    monkeypatch.setattr("agent.client.urllib.request.urlopen",
                        lambda *a, **k: Torn())
    with pytest.raises(LLMError) as caught:
        client._post({"model": "m"})
    assert "IncompleteRead" in str(caught.value)
