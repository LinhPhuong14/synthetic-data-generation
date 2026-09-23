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
import os
import re
import time
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from dataclasses import replace as _replace

URL_ENV = "VLM_LLM_URL"
MODEL_ENV = "VLM_LLM_MODEL"
KEY_ENV = "VLM_LLM_KEY"


class LLMError(RuntimeError):
    """The server answered, and the answer was not usable."""


# OpenAI tự nói trần THẬT của model ngay trong câu lỗi -- "max_tokens is too
# large: 28600. This model supports at most 16384 completion tokens, ...".
# Đọc con số ra, không hardcode bảng trần theo tên model (mỗi model một
# trần khác nhau, và bảng ấy cũ đi ngay khi OpenAI thêm model mới).
_MAX_TOKENS_RE = re.compile(r"supports at most (\d+) completion tokens")


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
    enable_thinking: bool = False
    # TỰ DÒ, không đặt tay. Bản trước để người gọi tự khai `vllm_extras` --
    # đúng câu hỏi của người dùng: "sao không tổng quát, cứ thêm model mới
    # là phải viết thêm một nhánh". Bây giờ không ai phải khai gì cả.
    #
    # Bắt đầu LẠC QUAN (giả định server hiểu mọi thứ vLLM hiểu: hai trường
    # `reasoning_effort`/`chat_template_kwargs`, và `strict: true` với một
    # schema có nhánh mở như `data`). Gặp đúng chữ ký lỗi của MỘT trong hai
    # giới hạn ấy thì tự hạ xuống, MỘT LẦN, rồi nhớ cho mọi lời gọi sau trên
    # cùng client -- xem `_decide`. Không đoán theo URL/tên provider (một
    # server tự lưu trữ có thể mang tên miền trông giống OpenAI, Azure OpenAI
    # thì không), chỉ đọc CÂU TRẢ LỜI THẬT của chính server đó.
    #
    # Đo thật trên `https://api.openai.com/v1` (2026-09-21): OpenAI từ chối
    # cả `chat_template_kwargs`/`reasoning_effort` ("Unrecognized request
    # arguments supplied") LẪN `strict: true` trên schema có nhánh mở
    # ("'additionalProperties' is required to be supplied and to be false").
    # Hai giới hạn ấy đi cùng nhau trên mọi backend "hosted, nghiêm ngặt" đã
    # gặp, nên một cờ hạ cả hai một lúc -- không cần hai vòng dò riêng.
    _vllm_extras: bool = field(default=True, init=False, repr=False, compare=False)
    # TRẦN TOKEN THẬT CỦA MODEL, tự dò -- không đoán trước. `agent/
    # compose_page.py::budget()` co giãn trần theo số tờ, có thể tới 60 000
    # cho tài liệu dài -- đúng với cửa sổ 262 144 của server nội bộ, nhưng
    # đo thật trên OpenAI `gpt-4o-mini`: `HTTP 400 "max_tokens is too large:
    # 28600. This model supports at most 16384 completion tokens"`. Mỗi
    # model một trần khác nhau (không chỉ khác giữa vLLM/OpenAI, mà giữa
    # CÁC MODEL OpenAI với nhau), và OpenAI nói thẳng con số thật trong câu
    # lỗi -- đọc từ đó, không hardcode bảng trần theo tên model.
    _max_output_tokens: int | None = field(default=None, init=False,
                                           repr=False, compare=False)

    @property
    def hosted(self) -> bool:
        """True once this client has LEARNED the server rejects the
        vLLM-only extras / open-schema `strict` mode (xem `_vllm_extras`).

        Đọc công khai để chỗ khác (`agent/compose_page.py::kind_constraint`)
        tận dụng lại đúng một cờ đã dò được, thay vì tự dò lại lần hai --
        `False` cho tới khi client này gặp request đầu tiên và học được."""
        return not self._vllm_extras

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
                #
                # 429 IS THE EXCEPTION, và nó là 4xx duy nhất đáng thử lại:
                # nó không phán quyết nội dung, nó phán quyết THỜI ĐIỂM. Cùng
                # một payload gửi lại sau vài giây thì qua. Đo được ngày
                # 23-09-2026 trên `gpt-4.1-mini`: 2 trên 8 tờ mất trắng vì
                # `Rate limit reached`, và cả hai chỉ cần chờ.
                #
                # Nghỉ theo `Retry-After` khi máy chủ nói ra -- đoán một con
                # số trong khi server vừa đưa con số đúng là tự chuốc thêm
                # một lần 429 nữa.
                if error.code == 429 and attempt < self.retries:
                    try:
                        wait = float(error.headers.get("Retry-After") or 0)
                    except (TypeError, ValueError):
                        wait = 0.0
                    time.sleep(max(wait, 2.0 * (attempt + 1)))
                    continue
                if error.code < 500:
                    break
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
            # `http.client.HTTPException` KHÔNG phải `OSError`.
            #
            # `IncompleteRead` -- phản hồi bị cắt giữa chừng -- là con của
            # `HTTPException`, và ba nhánh cũ không nhánh nào bắt nó. Nên một
            # câu trả lời đứt không thành "thử lại", nó thành một traceback
            # ném lên `ThreadPoolExecutor` và giết cả lượt chạy: đo được ngày
            # 23-09-2026, lô 12 tờ chết ở tờ thứ mấy đó, không `compose_
            # report.json`, không một tờ nào được giữ.
            #
            # Đúng loại lỗi đáng thử lại nhất: payload không sai, đường
            # truyền sai.
            except (urllib.error.URLError, http.client.HTTPException,
                    OSError, ValueError) as error:
                last = f"{type(error).__name__}: {error}"
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"{self.url}: {last}")

    def _max_tokens_field(self, max_tokens: int) -> dict:
        """`{"max_tokens": N}` hoặc `{}` -- N kẹp bởi trần THẬT đã dò được
        (`_max_output_tokens`), không bao giờ vượt quá, dù `budget()` phía
        gọi tính ra một số lớn hơn."""
        requested = max_tokens or self.max_tokens
        if self._max_output_tokens:
            requested = (min(requested, self._max_output_tokens) if requested
                        else self._max_output_tokens)
        return {"max_tokens": requested} if requested else {}

    def _payload(self, system: str, user: str, schema: dict,
                max_tokens: int) -> dict:
        """Thân request cho MỘT lần thử -- hình dạng phụ thuộc `self.
        _vllm_extras`, đọc lúc gọi chứ không đóng cứng, vì `_decide` có thể
        đang thử lại sau khi vừa hạ nó xuống."""
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            # `strict` CHỈ BẬT Ở BACKEND ÉP ĐƯỢC SCHEMA NÀY.
            #
            # vLLM/xgrammar biên dịch schema thành ngữ pháp và ép từng token
            # -- đó là chỗ `enum`/`pattern` có nghĩa, và là lý do lời dặn
            # không phải cầu xin model nhớ danh sách.
            #
            # Structured Outputs của OpenAI thì đòi ngược lại: MỌI object phải
            # khai đủ `properties` + `additionalProperties: false`. Cây `data`
            # ở đây là free-form theo thiết kế -- model tự đặt `data-path` nên
            # nó tự đặt luôn hình cây -- nên schema này không bao giờ hợp lệ
            # với `strict: true`. Nên hosted chạy `strict: false`: schema
            # thành lời hướng dẫn thay vì ngữ pháp, model vẫn trả JSON đúng
            # hình, và phần ÉP chuyển sang cổng (`llm_page.problems`) +
            # `repair.settle` -- hai thứ không phụ thuộc backend nào.
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "plan", "schema": schema,
                                                # ÉP KHI SCHEMA TỰ ĐÓNG, dù
                                                # server là ai -- xem `closed()`.
                                                # Schema mở trên backend hosted
                                                # thì vẫn phải `false`, nếu
                                                # không OpenAI trả 400.
                                                "strict": bool(self._vllm_extras
                                                               or closed(schema))}},
            "temperature": self.temperature,
            # Trần của LỜI GỌI này đè trần của client: một tờ sáu trang cần
            # nhiều token hơn một tờ một trang, và một con số cố định cho cả
            # hai thì hoặc cắt cụt tờ dài, hoặc thả lỏng tờ ngắn. Kẹp thêm
            # bởi `_max_output_tokens` nếu đã dò được -- xem khai trường.
            **self._max_tokens_field(max_tokens),
            # Chỉ vLLM/SGLang/llama.cpp mới nên nhận hai trường này -- xem
            # `_vllm_extras` ở khai trường phía trên.
            **({"reasoning_effort": self.reasoning_effort,
               "chat_template_kwargs": {"enable_thinking": self.enable_thinking}}
               if self._vllm_extras else {}),
        }

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
        # `caller` mang timeout riêng của LỜI GỌI này (nếu có) -- `_post`
        # phải dùng nó. Nhưng cờ `_vllm_extras` đọc/ghi trên CHÍNH `self`,
        # không phải trên `caller`: `dataclasses.replace()` dựng một instance
        # MỚI, và trường `init=False` như `_vllm_extras` bị reset về mặc định
        # trên bản sao ấy -- nếu học được cờ ở đó thì bài học mất ngay khi
        # lời gọi kết thúc. Học trên `self` thì mọi lời gọi sau, kể cả từ
        # luồng khác dùng chung `self` (`agent/compose_page.py::run()` share
        # đúng một `Client` cho cả `ThreadPoolExecutor`), đọc lại đúng cờ đã
        # học -- chỉ lần ĐẦU TIÊN trên một server mới trả giá một request hỏng.
        caller = self if not timeout else _replace(self, timeout=timeout)
        tried_downgrade = False
        tried_token_cap = False
        while True:
            try:
                answer = caller._post(self._payload(system, user, schema, max_tokens))
                break
            except LLMError as error:
                text = str(error)
                # Hai chữ ký lỗi đã đo được thật trên OpenAI (2026-09-21) --
                # xem docstring `_vllm_extras`. Khớp MỘT trong hai là đủ:
                # chúng đi cùng nhau trên mọi backend "hosted, nghiêm ngặt".
                signature = ("Unrecognized request argument" in text
                            or "additionalProperties" in text)
                capped = _MAX_TOKENS_RE.search(text)
                # KHÔNG hỏi cờ hiện tại, chỉ hỏi SERVER VỪA NÓI GÌ.
                #
                # `run()` chia đúng một `Client` cho cả `ThreadPoolExecutor`,
                # nên bốn luồng cùng gửi request đầu tiên trước khi ai kịp
                # học. Luồng A nhận 400, hạ cờ, thử lại, xong. Luồng B, C, D
                # đã gửi payload MANG trường sai từ trước và cũng nhận 400 --
                # nhưng tới lúc chúng xử lý lỗi thì cờ đã `False`, nên vế
                # `self._vllm_extras` sai và chúng ném thẳng thay vì thử lại.
                # Đo được: 3 trên 8 tờ trượt vì đúng chuyện này ở song song 4,
                # và con số ấy lớn dần theo mức song song.
                #
                # Cờ vẫn ghi (idempotent) để payload dựng lại không mang
                # trường sai nữa; chỉ điều kiện thử lại là bỏ nó đi.
                if signature and not tried_downgrade:
                    self._vllm_extras = False
                    tried_downgrade = True
                    continue
                if capped and not tried_token_cap:
                    self._max_output_tokens = int(capped.group(1))
                    tried_token_cap = True
                    continue
                raise
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


def closed(schema) -> bool:
    """Schema này có TỰ ĐÓNG không: mọi object khai đủ `properties`,
    `additionalProperties: false`, và `required` liệt kê đủ mọi khoá.

    Đây là điều kiện OpenAI Structured Outputs đòi để `strict: true` chạy.
    Hỏi chính schema thay vì hỏi một cờ về server: người viết schema biết
    mình có đóng nó hay không, còn `_vllm_extras` chỉ biết server là ai. Nhờ
    thế `agent/compose_page.py` bật được ép thật trên OpenAI mà không buộc
    `planner.py` hay `compose_layout.py` -- vốn gửi schema mở -- phải đổi
    theo.

    Vì sao phải ép: đo thật trên `gpt-4.1-mini` ngày 23-09-2026, cùng một
    schema, cùng một lời nhờ. `strict: false` -> 812 token, và câu trả lời
    mang các khoá CON của `plan` ở mức gốc, không có `data`, không có `rows`,
    không có `html`. `strict: true` -> 5 192 token, đủ bốn khoá, `html` 11 847
    ký tự vẽ ra được. Không phải model kém: schema không ép thì nó không theo.
    """
    if not isinstance(schema, dict):
        return True
    kind = schema.get("type")
    if kind == "object":
        props = schema.get("properties")
        if not isinstance(props, dict) or not props:
            return False
        if schema.get("additionalProperties") is not False:
            return False
        if set(schema.get("required") or []) != set(props):
            return False
        return all(closed(v) for v in props.values())
    if kind == "array":
        return closed(schema.get("items") or {})
    return True


def from_env(timeout: float | None = None,
             max_tokens: int = 0) -> Client | None:
    """The configured client, or None when this run has no server.

    Không có biến môi trường nào để khai server có phải vLLM hay không --
    `Client` tự dò việc đó ở lần gọi đầu tiên (xem `Client._vllm_extras`).
    Thêm một provider mới không cần sửa dòng nào ở đây."""
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


__all__ = ["KEY_ENV", "MODEL_ENV", "TIMEOUT_ENV", "URL_ENV", "closed",
          "Client", "LLMError", "from_env"]
