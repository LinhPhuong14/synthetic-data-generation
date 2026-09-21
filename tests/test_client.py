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
