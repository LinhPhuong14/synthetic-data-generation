"""Prompt đã commit, đọc theo tên tệp.

## Vì sao có tệp này

Hàm `prompt()` trước đây sống trong `agent/ollama.py`, cạnh client HTTP nói
chuyện với một Ollama chạy local. Hai thứ ấy không liên quan gì nhau: đọc một
tệp `.md` trong `agent/prompts/` không cần biết ai sẽ nhận chuỗi ấy. Nhưng vì
chúng ở chung một tệp, `agent/compose_page.py` -- thứ gọi vLLM qua
`agent/client.py`, không đụng Ollama một dòng nào -- vẫn phải `from
agent.ollama import prompt`, và Ollama trông như một phụ thuộc của nhánh LLM
trong khi nó không phải.

Khi bỏ Ollama (ngày 18-09-2026, chuyển hẳn sang `VLM_LLM_*`), `prompt()` là
thứ duy nhất trong tệp ấy còn ai dùng. Nên nó ra ở riêng, chứ không chuyển
sang `client.py`: `client.py` là ĐƯỜNG TRUYỀN, tệp này là NỘI DUNG, và gộp
chúng lại là dựng lại đúng cái nhập nhằng vừa gỡ ra.
"""

from __future__ import annotations

from pathlib import Path

from agent.client import LLMError

AGENT_ROOT = Path(__file__).resolve().parent
PROMPT_DIR = AGENT_ROOT / "prompts"


def prompt(name: str) -> str:
    """A committed prompt, by file stem.

    Prompts are files rather than string literals for the same reason the rules
    are YAML: the person who should be editing the Vietnamese in them is not
    necessarily the person who edits Python, and a prompt that changed inside a
    commit touching six other things is a prompt nobody reviewed.
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in PROMPT_DIR.glob("*.md"))) or "none"
        raise LLMError(f"no prompt {name!r} in {PROMPT_DIR}; have {have}")
    return path.read_text(encoding="utf-8")


__all__ = ["AGENT_ROOT", "PROMPT_DIR", "prompt"]
