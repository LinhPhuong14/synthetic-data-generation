#!/usr/bin/env python3
"""Đo cái server DÙNG CHUNG thật sự cho ta bao nhiêu, thay vì đoán từ tên GPU.

    python tools/llm/probe.py                    # đo đủ ba phần
    python tools/llm/probe.py --only tokens      # chỉ đếm token prompt (rẻ, 1 giây)
    python tools/llm/probe.py --max-concurrency 16

## Vì sao cần đo, không suy

`/metrics` của `10.148.20.19:8008` khai `num_gpu_blocks="856"`, `block_size="16"`
-- tức **13 696 token** KV cache cho TOÀN BỘ server. Cùng lúc ấy
`num_requests_running` là 38 và `num_preemptions_total` là 8 310. Ba con số ấy
nói rằng máy đang đập đi tính lại, nhưng chúng KHÔNG nói phần ta giành được là
bao nhiêu -- và đó mới là con số dựng nên kế hoạch 50 000 tờ.

Ba phép đo, mỗi phép trả lời một câu mà không câu nào suy ra được từ câu khác:

1. **`tokens`** -- prompt hiện tại DÀI THẬT bao nhiêu. Đếm bằng chính
   tokenizer của server (`POST /tokenize`), không phải ước "4 ký tự một
   token": văn bản tiếng Việt có dấu tốn hơn tiếng Anh khoảng rưỡi, nên ước
   sai về phía lạc quan.

2. **`cache`** -- prefix cache có SỐNG không. `enable_prefix_caching="True"`
   chỉ là cái công tắc; nó có tác dụng hay không phụ thuộc prefix có nằm lại
   trong cache tới lượt sau. Gửi CÙNG một prompt hai lần liên tiếp rồi đọc
   `usage.prompt_tokens_details.cached_tokens` của lượt hai: bằng 0 là cache
   chết ở cỡ prompt ấy. Đo ở ba cỡ để biết TRẦN -- prompt phải ngắn tới đâu
   thì cache mới giữ nổi.

3. **`throughput`** -- token/s TỔNG theo số request song song, tăng tới khi
   ngừng tăng. Điểm bão hoà ấy chia cho token mỗi tờ ra số tờ một giờ, và đó
   là toàn bộ cơ sở của lịch chạy.

## Cái này KHÔNG đo

Chất lượng. Một trang sinh ra đúng ngữ pháp mà nội dung vô nghĩa vẫn tính là
token đã trả tiền; phần ấy là việc của `synthgen/llm_page.py` và của người đọc
diff. Ở đây chỉ có đồng hồ.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent import futures as cf
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

URL_ENV, MODEL_ENV, KEY_ENV = "VLM_LLM_URL", "VLM_LLM_MODEL", "VLM_LLM_KEY"

# Ba cỡ prompt để dò trần cache. 24k là prompt THẬT hiện tại
# (`SYSTEM_PROMPT.md` + `page.md`); 6k và 2k là hai mốc "nếu cắt xuống" mà ta
# cần biết có qua được không TRƯỚC khi bỏ công cắt.
CACHE_SIZES = (2_000, 6_000, 24_000)

# Câu mồi để độn prompt cho đủ cỡ. Phải là văn xuôi thật chứ không phải "a a a"
# -- token lặp nén khác token thật, và ta đang đo cache chứ không đo entropy.
FILLER = (
    "Tờ chứng từ này được lập tại trụ sở đơn vị, có chữ ký của người lập biểu "
    "và dấu treo của phòng kế toán, dùng để đối chiếu với sổ chi tiết công nợ "
    "trong kỳ báo cáo và lưu theo quy định hiện hành về chế độ kế toán. "
)


def _endpoint(url: str, path: str) -> str:
    """`/v1` là gốc của `chat/completions`; `/tokenize` thì KHÔNG nằm dưới nó.

    vLLM để `/tokenize` ở gốc server, còn `VLM_LLM_URL` trỏ vào `/v1` vì đó là
    gốc của API tương thích OpenAI. Cắt đuôi `/v1` cho đúng một đường, chứ
    không bắt người dùng khai hai biến môi trường cho cùng một máy."""
    base = url.rstrip("/")
    if path.startswith("/v1"):
        return base + path[3:] if base.endswith("/v1") else base + path
    root = base[:-3].rstrip("/") if base.endswith("/v1") else base
    return root + path


def _post(url: str, key: str, payload: dict, timeout: float = 300.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Câu lỗi của vLLM LÀ chẩn đoán -- "prompt is longer than the maximum"
        # là câu ta đang muốn nghe, và nuốt nó đi thì phép đo mất nghĩa.
        detail = ""
        try:
            detail = error.read().decode("utf-8", "replace").strip()
        except Exception:                                    # noqa: BLE001
            pass
        raise RuntimeError(f"HTTP {error.code}: {detail[:400] or error.reason}") from None


def count_tokens(url: str, key: str, model: str, text: str) -> int:
    """Đếm bằng tokenizer của chính server. `-1` nếu server không mở endpoint."""
    try:
        answer = _post(_endpoint(url, "/tokenize"), key,
                       {"model": model, "prompt": text}, timeout=60.0)
    except Exception:                                        # noqa: BLE001
        return -1
    return int(answer.get("count", len(answer.get("tokens", []))))


def measure_prompts(url: str, key: str, model: str) -> None:
    """Phần 1 -- prompt hiện tại dài thật bao nhiêu."""
    print("\n=== 1. PROMPT HIỆN TẠI DÀI BAO NHIÊU ===")
    parts = [REPO_ROOT / "agent" / "guideline" / "SYSTEM_PROMPT.md",
             REPO_ROOT / "agent" / "prompts" / "page.md"]
    total_chars = total_tokens = 0
    for path in parts:
        if not path.exists():
            print(f"  {path.relative_to(REPO_ROOT)}: KHÔNG CÓ")
            continue
        text = path.read_text(encoding="utf-8")
        exact = count_tokens(url, key, model, text)
        total_chars += len(text)
        shown = f"{exact:,}" if exact >= 0 else f"~{len(text)//4:,} (ước)"
        if exact >= 0:
            total_tokens += exact
        print(f"  {path.relative_to(REPO_ROOT)}: {len(text):,} ký tự → {shown} token")
    if total_tokens:
        print(f"  TỔNG system turn: {total_tokens:,} token")
        print(f"  KV cache server:  13,696 token (856 block × 16)")
        print(f"  → prompt chiếm {total_tokens / 13_696 * 100:.0f}% toàn bộ KV cache")


def measure_cache(url: str, key: str, model: str) -> None:
    """Phần 2 -- prefix cache sống tới cỡ prompt nào."""
    print("\n=== 2. PREFIX CACHE SỐNG TỚI ĐÂU ===")
    print(f"  {'cỡ prompt':>12} | {'token thật':>10} | {'lần 1':>8} | "
          f"{'lần 2':>8} | {'cached lần 2':>13} | kết luận")
    print("  " + "-" * 78)
    chat = _endpoint(url, "/v1/chat/completions")
    for size in CACHE_SIZES:
        system = (FILLER * (size // 30 + 1))[: size * 4]
        exact = count_tokens(url, key, model, system)
        payload = {"model": model,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": "Trả lời đúng một từ: xong."}],
                   "max_tokens": 8, "temperature": 0.0}
        try:
            seconds, cached = [], 0
            for attempt in (1, 2):
                start = time.perf_counter()
                answer = _post(chat, key, payload)
                seconds.append(time.perf_counter() - start)
                usage = answer.get("usage", {}) or {}
                details = usage.get("prompt_tokens_details") or {}
                if attempt == 2:
                    cached = int(details.get("cached_tokens") or 0)
                    exact = exact if exact >= 0 else int(usage.get("prompt_tokens") or 0)
            verdict = ("cache SỐNG" if cached > exact * 0.5
                       else "cache CHẾT" if cached == 0 else "cache MỘT PHẦN")
            print(f"  {size:>12,} | {exact:>10,} | {seconds[0]:>7.2f}s | "
                  f"{seconds[1]:>7.2f}s | {cached:>13,} | {verdict}")
        except RuntimeError as error:
            print(f"  {size:>12,} | {exact:>10,} |  —  |  —  |  —  | TỪ CHỐI: {error}")


def measure_throughput(url: str, key: str, model: str, ceiling: int) -> None:
    """Phần 3 -- token/s tổng theo số request song song."""
    print("\n=== 3. TRẦN THÔNG LƯỢNG (chia với người khác) ===")
    chat = _endpoint(url, "/v1/chat/completions")
    system = "Bạn viết văn bản hành chính tiếng Việt."
    out_cap = 256

    def one(index: int) -> int:
        payload = {"model": model,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user",
                                 "content": f"Viết một đoạn {out_cap} token mô tả "
                                            f"chứng từ số {index}. Không giải thích."}],
                   "max_tokens": out_cap, "temperature": 0.9}
        answer = _post(chat, key, payload)
        return int((answer.get("usage") or {}).get("completion_tokens") or 0)

    level = 1
    best = (0, 0.0)
    print(f"  {'song song':>10} | {'giây':>7} | {'token ra':>9} | {'token/s tổng':>13} | mỗi luồng")
    print("  " + "-" * 66)
    while level <= ceiling:
        start = time.perf_counter()
        produced = 0
        with cf.ThreadPoolExecutor(max_workers=level) as pool:
            for got in pool.map(one, range(level)):
                produced += got
        elapsed = time.perf_counter() - start
        rate = produced / elapsed if elapsed else 0.0
        if rate > best[1]:
            best = (level, rate)
        print(f"  {level:>10} | {elapsed:>6.1f}s | {produced:>9,} | "
              f"{rate:>13.1f} | {rate / level:>6.1f} tok/s")
        level *= 2

    print(f"\n  Bão hoà quanh song song={best[0]}, ~{best[1]:.0f} token/s tổng.")
    if best[1] > 0:
        # 5 000 token ra mỗi tờ là con số ĐO ĐƯỢC ở pilot `c2`
        # (`data/c2/compose_report.json::tokens_out_per_page`).
        hours = 50_000 * 5_000 / best[1] / 3_600
        print(f"  → 50 000 tờ × 5 000 token ra = {hours:,.0f} giờ "
              f"({hours / 24:,.0f} ngày) nếu KHÔNG cắt gì.")
        print(f"  → cắt còn 1 500 token ra/tờ: {hours * 0.3:,.0f} giờ "
              f"({hours * 0.3 / 24:,.1f} ngày).")


def _preemptions(url: str) -> int:
    """`num_preemptions_total` lúc này. `-1` nếu không đọc được.

    Đọc TRƯỚC và SAU một đợt tải, rồi lấy hiệu -- con số tuyệt đối là tổng từ
    lúc server khởi động, gồm cả phần của 38 request người khác, nên nó không
    nói được gì. Cái hiệu mới nói: đợt tải VỪA RỒI làm server phải đập đi tính
    lại bao nhiêu lần."""
    try:
        root = url.rstrip("/")
        root = root[:-3].rstrip("/") if root.endswith("/v1") else root
        text = urllib.request.urlopen(root + "/metrics", timeout=30).read().decode()
    except Exception:                                        # noqa: BLE001
        return -1
    for line in text.splitlines():
        if line.startswith("vllm:num_preemptions_total{"):
            return int(float(line.rsplit("}", 1)[-1]))
    return -1


def measure_load(url: str, key: str, model: str, levels: tuple[int, ...]) -> None:
    """Phần 4 -- thông lượng ở CỠ PROMPT THẬT, cạnh cỡ prompt bé, để so.

    Phần 3 gửi system prompt hai chục token và đo được ~497 tok/s ở song song
    32. Con số ấy đẹp và VÔ DỤNG cho kế hoạch, vì workload thật gửi 22 722
    token mỗi lượt. Với 13 696 token KV cache, 32 lượt như thế đòi 727 000
    token KV -- gấp năm mươi ba lần sức chứa.

    Nên đo cả hai cỡ trên cùng một trục song song. Khoảng cách giữa hai hàng
    LÀ cái giá của prompt dài, tính bằng token/s mất đi; và `preempt` là cơ
    chế đã lấy đi chỗ ấy. Nếu hai hàng gần nhau thì prefix cache đang cứu, và
    việc cắt prompt không còn là việc gấp; nếu hàng dưới sụp thì cắt prompt là
    đòn lớn nhất còn lại, vì nó là thứ DUY NHẤT ta sửa được từ phía client."""
    print("\n=== 4. THÔNG LƯỢNG Ở CỠ PROMPT THẬT ===")
    chat = _endpoint(url, "/v1/chat/completions")
    out_cap = 256
    real = ""
    for name in ("guideline/SYSTEM_PROMPT.md", "prompts/page.md"):
        path = REPO_ROOT / "agent" / name
        if path.exists():
            real += path.read_text(encoding="utf-8")
    if not real:
        print("  không đọc được prompt thật; bỏ qua")
        return
    exact = count_tokens(url, key, model, real)
    small = "Bạn viết văn bản hành chính tiếng Việt."

    def run(system: str, level: int) -> tuple[float, int, int]:
        def one(index: int) -> int:
            answer = _post(chat, key, {
                "model": model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user",
                              "content": f"Viết một đoạn {out_cap} token mô tả "
                                         f"chứng từ số {index}. Không giải thích."}],
                "max_tokens": out_cap, "temperature": 0.9})
            return int((answer.get("usage") or {}).get("completion_tokens") or 0)

        before = _preemptions(url)
        start = time.perf_counter()
        produced = 0
        with cf.ThreadPoolExecutor(max_workers=level) as pool:
            for got in pool.map(one, range(level)):
                produced += got
        elapsed = time.perf_counter() - start
        after = _preemptions(url)
        return elapsed, produced, (after - before if before >= 0 <= after else -1)

    print(f"  prompt thật = {exact:,} token, prompt bé = ~20 token, "
          f"mỗi lượt sinh {out_cap} token")
    print(f"\n  {'song song':>10} | {'prompt bé':>12} | {'prompt thật':>12} | "
          f"{'còn lại':>8} | {'preempt':>8}")
    print("  " + "-" * 62)
    for level in levels:
        try:
            base_s, base_n, _ = run(small, level)
            real_s, real_n, preempt = run(real, level)
        except RuntimeError as error:
            print(f"  {level:>10} | TỪ CHỐI: {error}")
            continue
        base_rate = base_n / base_s if base_s else 0.0
        real_rate = real_n / real_s if real_s else 0.0
        share = f"{real_rate / base_rate * 100:.0f}%" if base_rate else "—"
        shown = f"{preempt:,}" if preempt >= 0 else "—"
        print(f"  {level:>10} | {base_rate:>8.1f} t/s | {real_rate:>8.1f} t/s | "
              f"{share:>8} | {shown:>8}")

    print("\n  Đọc bảng: cột 'còn lại' là phần thông lượng sống sót qua prompt")
    print("  22k. Dưới 50% thì cắt prompt là đòn lớn nhất còn lại.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=os.environ.get(URL_ENV, "").strip())
    parser.add_argument("--model", default=os.environ.get(MODEL_ENV, "").strip())
    parser.add_argument("--key", default=os.environ.get(KEY_ENV, "EMPTY").strip())
    parser.add_argument("--only", choices=("tokens", "cache", "throughput", "load"),
                        help="chạy một phần thay vì cả bốn")
    parser.add_argument("--max-concurrency", type=int, default=128)
    parser.add_argument("--load-levels", default="8,32,64",
                        help="các mức song song cho phần 4, ngăn bởi dấu phẩy")
    args = parser.parse_args(argv)

    if not args.url:
        print(f"thiếu {URL_ENV} (ví dụ http://10.148.20.19:8008/v1)", file=sys.stderr)
        return 2
    if not args.model:
        try:
            listing = json.loads(urllib.request.urlopen(
                _endpoint(args.url, "/v1/models"), timeout=30).read())
            args.model = listing["data"][0]["id"]
        except Exception as error:                           # noqa: BLE001
            print(f"không đọc được /v1/models: {error}", file=sys.stderr)
            return 2

    print(f"server : {args.url}")
    print(f"model  : {args.model}")

    if args.only in (None, "tokens"):
        measure_prompts(args.url, args.key, args.model)
    if args.only in (None, "cache"):
        measure_cache(args.url, args.key, args.model)
    if args.only in (None, "throughput"):
        measure_throughput(args.url, args.key, args.model, args.max_concurrency)
    if args.only in (None, "load"):
        levels = tuple(int(n) for n in args.load_levels.split(",") if n.strip())
        measure_load(args.url, args.key, args.model, levels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
