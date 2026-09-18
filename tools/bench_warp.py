#!/usr/bin/env python3
"""Đo giá của warp hình học, và của các cách làm nó rẻ đi.

    python tools/bench_warp.py --page data/forms16/html/html_002.jpg --out data/bench_warp

Warp hình học là đường đắt nhất của kho này: một trang `page_curl` đo được
~98 giây, so với ~2 giây cho mọi trang khác. Với một lượt 200 ảnh mà 20% bốc
trúng warp, riêng nó chiếm 95% thời gian vẽ. File này đo ba thứ, tách bạch:

1. **Từng pha** — dựng mesh + render trong Blender (subprocess), đọc EXR, nghịch
   đảo UV thành backward map (scipy Delaunay), phóng lại kích thước. Không đoán
   pha nào đắt: đo.
2. **Từng cấu hình render** — engine, số mẫu, độ phân giải canvas. Đọc qua biến
   môi trường `VLM_BLENDER_*` mà `vendor/config.py` nhận, nên không cấu hình nào
   ở đây phải sửa file vendor.
3. **Số lần retry camera** — `render.py` dựng lại mesh và lùi camera tới 6 lần
   khi `NoValidCameraAngleError`. Mỗi lần là một render đầy đủ nữa. Một scenario
   hay trượt thì chi phí thật gấp đôi, gấp ba con số trên giấy.

Chất lượng được đo bằng hai con số so với cấu hình gốc, trên cùng seed và cùng
trang: độ sắc nét (phương sai Laplacian, tụt = ảnh mờ đi) và nhiễu hạt (độ lệch
chuẩn của hiệu ảnh sau khi căn cùng cỡ). Không thay được mắt người — ảnh được
ghi ra để nhìn — nhưng nó bắt được cái mà một bảng thời gian không bắt được.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Bốn cấu hình, và cấu hình `base` phải chạy trước để hai cái sau có gì mà so.
CONFIGS = {
    "base": {},
    "eevee": {"VLM_BLENDER_ENGINE": "BLENDER_EEVEE_NEXT", "VLM_BLENDER_SAMPLES": "32"},
    "cycles_light": {"VLM_BLENDER_SAMPLES": "16", "VLM_BLENDER_RES_PCT": "70"},
    "cycles_16": {"VLM_BLENDER_SAMPLES": "16"},
}


def sharpness(image) -> float:
    import cv2

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def one(scenario: str, page, seed: int, params: dict | None):
    """Một lượt warp, có đo pha. Trả (ảnh, số liệu)."""
    import random

    import numpy as np

    from degradation.blender import render as blender_render
    from degradation.blender import uv_inverse

    calls = {"renders": 0, "blender_seconds": 0.0, "backward_seconds": 0.0}
    real_run = blender_render._run_sample_renderer
    real_backward = blender_render.uv_to_backward_map

    def timed_run(*args, **kwargs):
        started = time.time()
        try:
            return real_run(*args, **kwargs)
        finally:
            calls["renders"] += 1
            calls["blender_seconds"] += time.time() - started

    def timed_backward(*args, **kwargs):
        started = time.time()
        try:
            return real_backward(*args, **kwargs)
        finally:
            calls["backward_seconds"] += time.time() - started

    blender_render._run_sample_renderer = timed_run
    blender_render.uv_to_backward_map = timed_backward
    try:
        # Bốn góc trang, để backward map thật sự bị gọi — một lượt không có quad
        # nào bỏ qua hẳn pha đắt thứ hai và làm phép đo nói dối.
        h, w = page.shape[:2]
        quads = np.array([[[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]], dtype=np.float32)
        started = time.time()
        out, moved = blender_render.apply_warp(
            scenario, page, quads, params, random.Random(seed))
        total = time.time() - started
    finally:
        blender_render._run_sample_renderer = real_run
        blender_render.uv_to_backward_map = real_backward
        del uv_inverse

    return out, {
        "seconds": round(total, 2),
        "blender_seconds": round(calls["blender_seconds"], 2),
        "backward_seconds": round(calls["backward_seconds"], 2),
        "other_seconds": round(total - calls["blender_seconds"] - calls["backward_seconds"], 2),
        "renders": calls["renders"],
        "size": [int(out.shape[1]), int(out.shape[0])],
        "sharpness": round(sharpness(out), 1),
        "moved_quad": [[round(float(x), 1), round(float(y), 1)] for x, y in moved[0]],
    }


def main() -> int:
    import cv2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "bench_warp")
    parser.add_argument("--scenarios", default="page_curl,folded,crumple")
    parser.add_argument("--configs", default=",".join(CONFIGS))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--repeat", type=int, default=1,
                        help="số lần lặp mỗi (cấu hình, scenario) — retry camera "
                             "làm thời gian dao động mạnh, nên >1 khi cần số tin được")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    page = cv2.imread(str(args.page))
    if page is None:
        print(f"không đọc được {args.page}")
        return 1
    from rulebase.spec import load_rules

    # `--scenarios` nhận ID CỦA GIÁ TRỊ augmentation (`page_curl`, `folded`,
    # `lifted_corner`…) chứ không phải tên mesh (`fold_crease`, `corner_bulge`)
    # — vì đó là cái người dùng thấy trong kế hoạch và trong báo cáo phân phối.
    # Cả hai đều tra được, và cả hai đọc từ rulebase chứ không chép tay.
    params, warp_of = {}, {}
    for option in load_rules(REPO_ROOT / "rulebase" / "rules").get("augmentation", ()):
        warp = (option.params or {}).get("warp") or {}
        if warp.get("name"):
            name = str(warp["name"])
            params[name] = warp.get("params") or {}
            warp_of[option.id] = name
            warp_of.setdefault(name, name)

    rows = []
    for config in args.configs.split(","):
        overrides = CONFIGS.get(config)
        if overrides is None:
            print(f"bỏ qua cấu hình lạ {config!r}")
            continue
        for key in ("VLM_BLENDER_ENGINE", "VLM_BLENDER_SAMPLES", "VLM_BLENDER_RES_X",
                    "VLM_BLENDER_RES_Y", "VLM_BLENDER_RES_PCT", "VLM_BLENDER_DENOISE"):
            os.environ.pop(key, None)
        os.environ.update(overrides)
        for scenario in args.scenarios.split(","):
            mesh = warp_of.get(scenario)
            if mesh is None:
                print(f"bỏ qua {scenario!r}: không giá trị augmentation nào "
                      f"gọi warp ấy; có {', '.join(sorted(warp_of))}")
                continue
            for run in range(args.repeat):
                seed = args.seed + run
                try:
                    image, row = one(mesh, page, seed, params.get(mesh))
                except Exception as error:                    # noqa: BLE001
                    row = {"error": f"{type(error).__name__}: {error}"}
                    image = None
                row.update({"config": config, "scenario": scenario, "seed": seed})
                rows.append(row)
                if image is not None:
                    cv2.imwrite(str(args.out / f"{config}__{scenario}__{seed}.jpg"), image)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                (args.out / "bench.jsonl").write_text(
                    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")

    print("\n== TÓM TẮT ==")
    for config in args.configs.split(","):
        mine = [r for r in rows if r.get("config") == config and "seconds" in r]
        if not mine:
            continue
        print(f"{config:14s} {statistics.mean(r['seconds'] for r in mine):6.1f}s/trang  "
              f"blender {statistics.mean(r['blender_seconds'] for r in mine):6.1f}s  "
              f"backward {statistics.mean(r['backward_seconds'] for r in mine):5.1f}s  "
              f"render/trang {statistics.mean(r['renders'] for r in mine):.2f}  "
              f"sắc nét {statistics.mean(r['sharpness'] for r in mine):8.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
