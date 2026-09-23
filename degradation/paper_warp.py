"""Warp a page with the SAME photograph of paper that is then laid over it.

The cheap half of `degradation/blender/`. That module renders a real 3D sheet
in Blender and costs seconds to a minute a page, which is why every rule-base
option naming it ships `enabled: false`. This one buys most of the look for
milliseconds: no mesh, no camera, no light -- the fold shape is READ OUT of a
photograph of a crumpled sheet (`augmentations/data/image/`, SynthDoG's) by
treating its brightness as a height field, and the page is remapped by that
field's gradient.

What makes it read as one sheet rather than as a warp with a picture on top is
that both halves use the SAME aligned crop: the photo is cover-cropped to the
page once, that one crop is differentiated for the displacement AND blended on
top by `texture.blend_sheet`, so a fold line shades exactly the pixels it bent.
Picking the photo twice -- once here, once in a `paper_overlay` chain entry --
would put the visible crease and the measurable crease in two different places.

**The bound is on stretch, not on shift.** Scaling `gradient(field)` so its peak
magnitude hits a pixel budget says how far a pixel moves, and nothing about how
fast that movement changes between neighbours -- which is what decides whether a
glyph is carried along rigidly or smeared. Since the Jacobian of
`scale * gradient(field)` is `scale * Hessian(field)`, bounding
`scale * max(curvature)` to `max_stretch` bounds local area/length change to that
fraction everywhere, however sharp any one fold is. At `max_stretch: 0.28`,
measured over the six layouts in `data/paper_warp_test/`, `det(J)` stays in
0.746..1.295 -- comfortably positive, so the map never folds onto itself and no
glyph tears, while pixels still travel up to ~33px on a 1020x2289 page.

`sigma_ratio` scales the pre-blur with the page because curvature is a SECOND
derivative: it falls off with the square of the smoothing radius, so a
fixed-radius blur that silences pixel noise is nowhere near enough to also tame
real fold curvature, and the bound above would crush the field to near zero.

Boxes are remapped, not assumed. `cv2.remap` reads a BACKWARD map, so the label
at source `(x, y)` ends up where the map points back at it -- found by fixed-point
iteration in `_invert`, which converges because the displacement's own gradient
is bounded by `max_stretch < 1`.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .texture import OVERLAY_DIR, _as_bgr, _cover, _pick_texture, _restore, blend_sheet

# One engine, named the way `degradation.blender.meshes` names its scenarios --
# `rulebase/rules/augmentation.yaml`'s `warp.name` is drawn from both namespaces
# and dispatched by `degradation.warp`. WHICH photograph is a `params` choice,
# not a name, because the photographs are data: drop a file into OVERLAY_DIR and
# it is drawn from without touching this file or the rules.
NAME = "paper_photo"

DEFAULTS: dict[str, Any] = {
    "photo": "auto",        # a file stem in OVERLAY_DIR, or "auto" to draw one
    "max_stretch": 0.28,    # cap on local area/length change, |det(J) - 1|
    "sigma_ratio": 0.09,    # pre-blur radius, as a fraction of the page's long side
    "alpha": 0.38,          # overlay multiply -- fibre and fold shadow darken
    "lighten": 0.35,        # overlay screen -- real paper scatters light back
}
_ITERATIONS = 8             # fixed-point steps for the box inverse; see `_invert`


def names() -> list[str]:
    return [NAME]


# Sigma mà `_wide_blur` nhắm tới SAU khi thu nhỏ. Mười hai: dưới mức này thì
# nhân Gauss đã đủ nhỏ để phép thu nhỏ không mua được gì, trên mức này thì
# ảnh thu nhỏ vẫn giữ đủ cấu trúc cho bộ lọc làm việc.
_WIDE_TARGET = 12.0


def _draw(rng: random.Random, spec: Any) -> float:
    """A fixed number is used as-is; a `(low, high)` pair is drawn from.

    Same convention as `degradation.blender.meshes`, so one `warp.params` block
    reads the same whichever engine it names.
    """
    if isinstance(spec, (tuple, list)):
        low, high = spec
        return rng.uniform(float(low), float(high))
    return float(spec)


def _wide_blur(field: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur at a very large sigma, done on a shrunken copy.

    A blur whose sigma is a tenth of the page is a low-pass filter with a
    cut-off far below anything a shrunken copy would lose, so shrinking by
    `k`, blurring at `sigma/k` and scaling back gives back the same field.

    How close, measured on the three sheets in `textures/paper/` at the sigma
    this function actually sees (148 on 1646x1164): mean error 0.12-0.19% of
    the field's own amplitude, worst pixel 1-2%. On white noise the relative
    error is an order of magnitude worse -- a wide blur of noise has almost no
    amplitude left to be relative to -- but the input here is a photographed
    sheet of paper, which is smooth by construction.

    Why bother: this one call was the most expensive OpenCV operation in the
    whole degradation stage. Measured over a ten-page run, `sigma=148` on a
    1646x1164 sheet cost 0.28 s a call and 8% of the entire run -- more than
    every other `GaussianBlur` in `degradation/` put together. Separable
    Gaussian is O(sigma) per pixel, so the cost grows with the blur; shrinking
    first turns that into O(sigma/k) on 1/k^2 of the pixels.

    `k` is chosen so the shrunken sigma stays near `_WIDE_TARGET`: big enough
    that the filter is still doing real smoothing at the small size, small
    enough that the shrink never removes structure the blur would have kept.
    Sigma under the target is left alone -- there is nothing to win there and
    a needless resize costs more than it saves."""
    if sigma <= _WIDE_TARGET:
        return cv2.GaussianBlur(field, (0, 0), sigmaX=sigma)
    height, width = field.shape[:2]
    k = max(int(sigma / _WIDE_TARGET), 2)
    small = cv2.resize(field, (max(width // k, 8), max(height // k, 8)),
                       interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigmaX=sigma / k)
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)


def displacement(sheet_gray: np.ndarray, max_stretch: float, sigma_ratio: float
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Aligned paper grayscale -> the `(dx, dy)` backward map, curvature-bounded."""
    height, width = sheet_gray.shape[:2]
    sigma = max(width, height) * float(sigma_ratio)
    smoothed = _wide_blur(sheet_gray.astype(np.float32), sigma)
    low, high = float(smoothed.min()), float(smoothed.max())
    field = (smoothed - low) / max(high - low, 1e-6)

    gy, gx = np.gradient(field)
    gyy, _ = np.gradient(gy)
    gxy, gxx = np.gradient(gx)
    # Sum-of-abs bound on the Hessian's largest eigenvalue (Gershgorin) --
    # conservative (it may leave a little of the safe budget unused) but it
    # never under-estimates the real risk, which is the direction that matters
    # when the cost of being wrong is a torn glyph in a labelled record.
    curvature = np.abs(gxx) + np.abs(gyy) + 2 * np.abs(gxy)
    scale = float(max_stretch) / (float(curvature.max()) or 1e-9)
    return (gx * scale).astype(np.float32), (gy * scale).astype(np.float32)


def _invert(dx: np.ndarray, dy: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Where source points end up, given the BACKWARD map `cv2.remap` consumes.

    `remap` fills output `(u, v)` from input `(u + dx, v + dy)`, so the source
    point `(x, y)` is wherever `u + dx(u, v) = x`. Solved by iteration from
    `(u, v) = (x, y)`: the step is a contraction with factor `max|grad d|`, which
    `displacement` has already bounded by `max_stretch`, so a handful of passes
    lands well inside a tenth of a pixel. Points off the page keep working --
    `BORDER_REPLICATE` extends the field rather than reading zeros, which would
    yank an off-page corner back towards the origin.
    """
    if not len(points):
        return points.reshape(-1, 2).astype(np.float32)

    target = points.reshape(-1, 2).astype(np.float32)
    guess = target.copy()
    for _ in range(_ITERATIONS):
        map_x = guess[:, 0].reshape(-1, 1)
        map_y = guess[:, 1].reshape(-1, 1)
        sampled_x = cv2.remap(dx, map_x, map_y, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE).reshape(-1)
        sampled_y = cv2.remap(dy, map_x, map_y, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE).reshape(-1)
        guess = np.stack([target[:, 0] - sampled_x, target[:, 1] - sampled_y], axis=1)
    return guess.astype(np.float32)


def apply_warp(
    name: str,
    image: np.ndarray,
    quads: np.ndarray,
    params: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    overlays_dir: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Warp `image` and `quads` by one photograph, then lay that photograph over it.

    With no photographs present this is a no-op on both, for the same reason
    `texture.paper_overlay` is: the effect is meaningless without a real sheet,
    and a synthetic stand-in would make a missing directory invisible.
    """
    if name != NAME:
        raise KeyError(f"unknown paper warp {name!r}; have {NAME}")

    rng = rng or random.Random(0)
    options = {**DEFAULTS, **(params or {})}
    directory = Path(overlays_dir) if overlays_dir else OVERLAY_DIR
    photo = options["photo"]
    texture = _pick_texture(directory, None if photo in (None, "auto") else str(photo), rng)
    if texture is None:
        return image, quads

    out, was_gray = _as_bgr(image)
    height, width = out.shape[:2]
    sheet = _cover(texture, (width, height))

    dx, dy = displacement(
        cv2.cvtColor(sheet, cv2.COLOR_BGR2GRAY),
        _draw(rng, options["max_stretch"]),
        float(options["sigma_ratio"]),
    )
    xx, yy = np.meshgrid(np.arange(width, dtype=np.float32),
                         np.arange(height, dtype=np.float32))
    warped = cv2.remap(out, xx + dx, yy + dy, interpolation=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_REPLICATE)

    blended = blend_sheet(warped, sheet,
                          _draw(rng, options["alpha"]), _draw(rng, options["lighten"]))
    moved = _invert(dx, dy, np.asarray(quads, dtype=np.float32))
    return _restore(blended, was_gray), moved.reshape(np.shape(quads))


def warp_regions(
    name: str, image: np.ndarray, params: dict[str, Any] | None, rng: random.Random,
    *region_lists: list[dict[str, Any]],
) -> tuple[Any, ...]:
    """Warp `image` and every quad in `region_lists` through ONE displacement field.

    Same contract as `degradation.blender.warp_regions`, and the same reason for
    it: `boxes`, `words` and `cells` describe one page, so one field has to move
    all three -- and one draw has to pick the photograph, or each list would be
    warped by a different sheet.
    """
    counts = [len(regions) for regions in region_lists]
    flat = [box["quad"] for regions in region_lists for box in regions]
    quads = (np.asarray(flat, dtype=np.float32).reshape(-1, 4, 2)
             if flat else np.zeros((0, 4, 2), dtype=np.float32))

    new_image, new_quads = apply_warp(name, image, quads, params, rng)

    out: list[list[dict[str, Any]]] = []
    offset = 0
    for regions, count in zip(region_lists, counts):
        updated = []
        for box, quad in zip(regions, new_quads[offset:offset + count].tolist()):
            updated.append({**box, "quad": [[round(x, 1), round(y, 1)] for x, y in quad]})
        out.append(updated)
        offset += count
    return (new_image, *out)


__all__ = ["DEFAULTS", "NAME", "apply_warp", "displacement", "names", "warp_regions"]
