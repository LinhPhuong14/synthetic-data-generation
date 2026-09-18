"""Talking to whatever LLM server the run was pointed at, or to none.

    llm = client.from_env()          # None when no server is configured
    picks = llm.decide(prompt, schema)

Any OpenAI-compatible endpoint: vLLM (`vllm serve ... --port 8000`), SGLang,
llama.cpp's server, Ollama (`/v1`), or a hosted one. Written on `urllib`
because the driver has to run under the repository's bare interpreter, which
has PyYAML and nothing else -- adding a dependency to the one module that is
allowed to be absent would be the wrong trade.

**A missing server is a mode, not a failure.** `from_env()` returns None when
`VLM_LLM_URL` is unset, and the planner then runs its offline policy, which is
the same decision procedure with the model's judgement replaced by a coverage
objective. A run that silently degraded would be the bad outcome; a run that
records which mode it used, per image, is not -- see `planner.Decision.by`.

The schema is sent as `response_format: {type: json_schema}`, which vLLM
enforces by constrained decoding (`--structured-outputs-config.backend
xgrammar`). Enforcement matters more than prompting here: the ids the model
returns have to be ids the rules actually define, and an enum in the schema is
the only mechanism that makes that true by construction rather than by hope.
"""

from __future__ import annotations

import json
from dataclasses import replace as _replace
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

URL_ENV = "VLM_LLM_URL"
MODEL_ENV = "VLM_LLM_MODEL"
KEY_ENV = "VLM_LLM_KEY"


class LLMError(RuntimeError):
    """The server answered, and the answer was not usable."""


@dataclass
class Client:
    """One endpoint, one model, and a bounded retry."""

    url: str
    model: str
    key: str = "EMPTY"
    timeout: float = 120.0
    retries: int = 2
    temperature: float = 0.85
    # Qwen3.x and gpt-oss think by default. For picking ids off a list that is
    # spend with no return, so it is asked for explicitly and low; a server
    # that does not know the field ignores it.
    reasoning_effort: str = "low"
    # TRẦN TOKEN ĐẦU RA. Trước đây không đặt, nên vLLM dùng trần của chính nó
    # -- thường là cả cửa sổ ngữ cảnh. Một trang model viết lan man chạy tới
    # trần ấy rồi mới dừng: đo được một tờ tiêu 360 giây ở 15 tok/s, tức hơn
    # năm nghìn token, và `_post` còn thử lại ba lần nên mất 364 giây rồi vẫn
    # hỏng. Trần chặn được ca xấu nhất mà không đụng ca thường: trung vị một
    # tờ HTML là 4 685 token.
    #
    # `0` = không đặt, để vLLM tự quyết -- giữ nguyên hành vi cũ cho những chỗ
    # gọi khác (`planner`, `compose_layout`) vốn xin câu trả lời ngắn.
    max_tokens: int = 0
    # `reasoning_effort` alone did NOT stop a real Qwen3 server (vllm 0.21)
    # from thinking: a bare request with no `chat_template_kwargs` spent its
    # whole `max_tokens` on an unfinished `reasoning` field and came back with
    # `content: null` after 38s for a three-word answer -- measured against
    # the team's own vLLM host. Qwen3's own template switch, `enable_thinking:
    # false`, cut that to 0.4s on the same server, same request otherwise.
    # Sent unconditionally: a server that does not read `chat_template_kwargs`
    # (SGLang, llama.cpp, a hosted endpoint) ignores an object it does not
    # recognise the same way it already ignores `reasoning_effort`.
    enable_thinking: bool = False

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url.rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"})
        last: str = "no attempt was made"
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                # `HTTPError` is a `URLError` AND a file object: the server's own
                # explanation is sitting in its body, and the branch below used
                # to drop it on the floor, leaving "HTTP Error 500: Internal
                # Server Error" -- true, and useless. A 500 from vLLM is almost
                # always one specific sentence (a schema the grammar backend
                # cannot compile, a chat-template kwarg the model's template
                # rejects), and that sentence is the whole diagnosis.
                detail = ""
                try:
                    detail = error.read().decode("utf-8", "replace").strip()
                except Exception:       # noqa: BLE001 -- the body is a bonus
                    pass
                last = f"HTTP {error.code} {error.reason}"
                if detail:
                    last += f" -- {detail[:1200]}"
                # 4xx is a verdict on THIS payload; sending it again unchanged
                # buys nothing but 4.5s of sleep. 5xx and transport errors can
                # be the server catching its breath, so those still retry.
                if error.code < 500:
                    break
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
            except (urllib.error.URLError, OSError, ValueError) as error:
                last = f"{type(error).__name__}: {error}"
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"{self.url}: {last}")

    def decide(self, system: str, user: str, schema: dict) -> dict:
        """One JSON object matching `schema`. Raises rather than guessing."""
        return self.decide_with_usage(system, user, schema)[0]

    def decide_with_usage(self, system: str, user: str, schema: dict,
                          max_tokens: int = 0,
                          timeout: float = 0.0) -> tuple[dict, dict]:
        """`(object, usage)` -- the same call, plus what it cost.

        vLLM returns `usage` on every reply and `decide` threw it away, so a
        run could say how many SECONDS it spent and nothing about how many
        TOKENS. Seconds alone do not size a job: the same wall-clock covers a
        short page at a busy moment and a long one at a quiet one, and only
        the token count tells the two apart or predicts what 20 000 pages
        cost.

        A separate method rather than a changed return type: `planner.py`,
        `compose_layout.py` and `compose_archetype.py` all call `decide`, and
        a tuple where they expect a dict fails at the first attribute access
        rather than at the call.
        """
        answer = (self if not timeout else _replace(self, timeout=timeout))._post({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "plan", "schema": schema,
                                                "strict": True}},
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            # Trần của LỜI GỌI này đè trần của client: một tờ sáu trang cần
            # nhiều token hơn một tờ một trang, và một con số cố định cho cả
            # hai thì hoặc cắt cụt tờ dài, hoặc thả lỏng tờ ngắn.
            **({"max_tokens": max_tokens or self.max_tokens}
               if (max_tokens or self.max_tokens) else {}),
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        })
        try:
            content = answer["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError(f"no content in the reply: {answer}") from error
        usage = dict(answer.get("usage") or {})
        try:
            return json.loads(content), usage
        except json.JSONDecodeError as error:
            raise LLMError(f"reply was not JSON: {content[:300]!r}") from error

    def alive(self) -> bool:
        try:
            request = urllib.request.Request(
                self.url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {self.key}"})
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except Exception:       # noqa: BLE001 -- any failure means "not there"
            return False


# Hạn chờ đặt được từ môi trường, vì nó phụ thuộc VIỆC chứ không phụ thuộc
# server: chọn một id trong danh sách xong trong vài giây, còn viết cả một tờ
# HTML năm nghìn token thì không. Đo trên `Qwen3.8-27B-FP8` với bốn request
# song song: 53 tok/s lúc rảnh, tụt xuống 15 tok/s khi cả bốn cùng sinh -- tức
# là một trang năm nghìn token mất tới 330 giây, gấp gần ba lần hạn 120 giây.
TIMEOUT_ENV = "VLM_LLM_TIMEOUT"


def from_env(timeout: float | None = None,
             max_tokens: int = 0) -> Client | None:
    """The configured client, or None when this run has no server."""
    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return None
    if timeout is None:
        try:
            timeout = float(os.environ.get(TIMEOUT_ENV, "") or 120.0)
        except ValueError:
            timeout = 120.0
    return Client(url=url, model=os.environ.get(MODEL_ENV, "planner").strip() or "planner",
                  key=os.environ.get(KEY_ENV, "EMPTY"), timeout=timeout,
                  max_tokens=max_tokens or 0)


__all__ = ["KEY_ENV", "MODEL_ENV", "TIMEOUT_ENV", "URL_ENV", "Client",
           "LLMError", "from_env"]
