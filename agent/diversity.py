"""Batch-wide diversity memory, shared across every generation thread.

    from agent.diversity import DiversityWarden

`agent/coverage.py` (Phase 4, task 4.3) and `agent/fingerprint.py` (4.2)
have both existed and worked since Phase 4, with tests. Neither was ever
called by `agent/compose_page.py`: `one()` drew its plan with a bare
`DP.sample(G.FAMILIES[family], rng)` on a per-index RNG, so every page was
an INDEPENDENT draw and nothing in the run remembered what the previous
pages had already used. This module is the missing caller, and the reason
it is a class rather than three loose calls in `run()` is the word
*shared*: `run()` generates on a `ThreadPoolExecutor`, so the memory that
makes a draw coverage-aware is touched by `concurrency` threads at once.

## What it holds, and why they are two memories not one

| memory | keyed on | answers |
| --- | --- | --- |
| `CoverageMemory` (reused verbatim) | `Fingerprint` of the plan | which corners of the grammar are saturated |
| geometry window | `GeometryFingerprint` of the drawn page | did this page LAND where a recent one landed |

The second exists because the first is structurally blind to it: the three
most visually identical pairs of pages in `data/pilot16` + `data/pilot17`
score `document_distance.distance` = **1.000**, maximally different, because
they come from three different families. See `agent/geometry_distance.py`
for that table.

## The order the two gates run in, and why it is that order

1. **Draw** -- `sample_with_coverage` picks the least-seen of `candidates`
   independent draws. Free: no model call has happened yet.
2. **Redraw** while the drawn plan's `fine` tier is already in the recent
   window, up to `plan_retries` times. Also free.
3. Model writes the page. **~110-430 seconds.**
4. **Render and compare geometry.** A collision here costs a whole new
   model call, so it is the last gate, not the first.

Steps 1-2 are the ones meant to do the work; step 4 is the backstop that
measures whether they did. Both are counted separately in `metrics()` for
exactly that reason -- a run where step 4 fires often is a run where the
grammar cannot express the diversity the corpus needs, and that is a
finding about `agent/grammar.py`, not about the model.

## `sample_with_coverage` observes what it draws, including redraws

`coverage.py::sample_with_coverage` calls `memory.observe()` on the plan it
returns -- documented behaviour, not a bug, and this module deliberately
does not work around it. A plan drawn at step 2 and then thrown away stays
observed, so the redraw right after it is already steered away from what it
just rejected. The cost is that `CoverageMemory.total_observed()` counts
draws, not pages; `metrics()["plans_drawn"]` reports that number next to
`pages` so nobody reads one as the other.
"""

from __future__ import annotations

import random
import threading
from collections import Counter

from agent.coverage import CoverageMemory, sample_with_coverage
from agent.document_plan import DocumentPlan, sample
from agent.fingerprint import (GRID_ROWS, Fingerprint, GeometryFingerprint,
                              fingerprint)
from agent.document_distance import corpus_diversity
from agent.geometry_distance import (JACCARD_CEILING, WINDOW, corpus_geometry,
                                    nearest)
from agent.grammar import Grammar

# Bao nhiêu plan độc lập được rút ra rồi giữ lại cái ít gặp nhất. 8 là mặc
# định của `sample_with_coverage`; giữ nguyên vì rút một plan là vài chục
# micro giây, còn một lời gọi model là 110-430 giây -- không có lý do tiết
# kiệm ở đầu rẻ.
CANDIDATES = 8

# Rút lại mấy lần khi plan vừa rút đã trùng `fine` với một tờ gần đây. Ba là
# đủ: với 30 family x chừng 100-200 tổ hợp `fine` mỗi family, ba lần rút hụt
# liên tiếp nghĩa là family ấy thật sự cạn tổ hợp, và lúc ấy rút thêm cũng
# không ra cái mới -- cứ gửi đi, rồi `metrics()` báo `plan_collisions`.
PLAN_RETRIES = 3

# Tối đa mấy lần gọi model cho MỘT tờ (lần đầu + sinh lại). 2 nghĩa là một tờ
# trùng hình học được sinh lại đúng một lần. Đo trên `data/pilot16`+`pilot17`:
# 14,9% số tờ trùng ở cửa sổ 24, nên 2 lượt đẩy chi phí kỳ vọng lên chừng
# 1,15x -- 3 lượt chỉ cứu thêm phần đuôi rất nhỏ với giá một lời gọi nữa.
MAX_ATTEMPTS = 2


class Collision:
    """Một lần đụng: tờ nào, gần đến đâu, và câu nhắc gửi lại cho model."""

    __slots__ = ("against", "jaccard", "hamming", "hint")

    def __init__(self, against, jaccard: float, hamming: float, hint: str):
        self.against = against
        self.jaccard = jaccard
        self.hamming = hamming
        self.hint = hint

    def as_dict(self) -> dict:
        return {"against": self.against, "jaccard": round(self.jaccard, 4),
                "hamming": round(self.hamming, 4)}


# Sáu dải ngang của tờ giấy, để câu nhắc nói được "khối này ngồi ở khoảng
# nào" bằng tiếng người thay vì bằng chỉ số hàng lưới. `GRID_ROWS` là 12 nên
# mỗi dải đúng hai hàng.
_BANDS = ("the very top", "the upper third", "just above the middle",
         "just below the middle", "the lower third", "the very bottom")


def _band(row: int, rows: int) -> str:
    return _BANDS[min(len(_BANDS) - 1, max(0, row * len(_BANDS) // max(rows, 1)))]


def diversify_hint(target: GeometryFingerprint, other: GeometryFingerprint,
                  rows: int) -> str:
    """Câu nhắc dựng TỪ chỗ hai tờ chồng nhau, không phải một câu viết sẵn.

    Một câu chung chung ("make it more varied") không nói được model phải
    đổi cái gì, và model sẽ đổi chữ chứ không đổi bố cục. Nên nêu đích danh:
    nhãn lớp nào, ngồi ở dải ngang nào, trên tờ thứ mấy -- ba thứ đọc thẳng
    ra từ những ô mà hai dấu vân CÙNG chiếm.

    Nêu nhiều nhất ba khối: một câu nhắc dài hơn brief thì model đọc nó như
    một bản mô tả tờ giấy phải viết, đúng cái bẫy mục `table` của `SAY` đã
    ghi lại (khai 64 dòng rồi viết một dòng)."""
    shared = target.cells & other.cells
    if not shared:
        return ""
    weight: Counter = Counter()
    for page, label, _col, row in shared:
        weight[(page, label, _band(row, rows))] += 1
    worst = weight.most_common(3)
    spots = "; ".join(
        f"`{label}` across {band} of sheet {page}" for (page, label, band), _ in worst)
    return (
        "### Do not repeat the last layout\n\n"
        "The page you wrote a moment ago for this run landed its blocks in "
        f"the same places as an earlier one: {spots}. Same structure is fine "
        "-- the engine fixed it -- but the same block SHAPES in the same "
        "places is not. Change where the weight of the page sits: a different "
        "number of columns in the field blocks, a block that runs full width "
        "where the last one ran half, a signature strip on one side instead "
        "of centred, a header that is two lines instead of four. Do not solve "
        "this by writing less or by dropping a block the structure asks for."
    )


class DiversityWarden:
    """Trí nhớ đa dạng của CẢ LÔ. Mọi phương thức an toàn với nhiều luồng.

    Một `threading.Lock` duy nhất bọc cả ba trạng thái (coverage memory, cửa
    sổ hình học, sổ đếm) chứ không một khoá cho mỗi thứ: chúng được đọc và
    ghi cùng nhau trong một quyết định, và hai khoá lồng nhau là một cách
    khoá chết. Phần đắt nhất bên trong khoá là `sample_with_coverage`
    (chừng vài chục micro giây cho 8 ứng viên), nên tranh khoá không phải
    vấn đề ở mức song song 3-8 request mà kho này chạy.

    `enabled=False` giữ NGUYÊN mọi phép đo và tắt duy nhất quyền loại tờ --
    đó là nhánh đối chứng của phép thử A/B: hai lượt chạy phải đo bằng cùng
    một thước, khác nhau ở chỗ có hành động theo số đo hay không."""

    def __init__(self, *, enabled: bool = True, steer: bool = True,
                window: int = WINDOW, ceiling: float = JACCARD_CEILING,
                candidates: int = CANDIDATES, plan_retries: int = PLAN_RETRIES,
                rows: int = GRID_ROWS) -> None:
        self.enabled = enabled
        self.steer = steer
        self.window = window
        self.ceiling = ceiling
        self.candidates = candidates
        self.plan_retries = plan_retries
        self._rows = rows
        self._lock = threading.Lock()
        self._coverage = CoverageMemory()
        self._plan_fps: list[Fingerprint] = []
        self._geometry: list[tuple[object, GeometryFingerprint]] = []
        self._plans_drawn = 0
        self._plan_collisions = 0
        self._rejected: list[dict] = []
        self._kept_colliding: list[dict] = []
        self._unavailable = 0

    # ------------------------------------------------------------ rút plan

    def draw(self, grammar: Grammar,
            rng: random.Random) -> tuple[DocumentPlan, Fingerprint]:
        """Một plan đã né vùng bão hoà, cộng dấu vân của chính nó.

        Trả cả dấu vân vì `sample_with_coverage` đã tính nó rồi -- gọi
        `fingerprint()` lần nữa ở caller là dựng lại một thứ vừa có."""
        with self._lock:
            if not self.steer:
                # ĐƯỜNG CŨ, nguyên văn: một lần bốc độc lập, không trí nhớ.
                # Đây là nhánh đối chứng của phép thử A/B -- `--no-diversity`
                # phải là "engine như trước khi nối dây", không phải "engine
                # mới nhưng tắt một nửa", nếu không con số so được là con số
                # của một thứ ba chưa từng chạy.
                plan = sample(grammar, rng)
                self._plans_drawn += 1
                return plan, fingerprint(plan)
            recent = {fp.fine for fp in self._plan_fps[-self.window:]}
            plan = fp = None
            for attempt in range(self.plan_retries + 1):
                plan, fp = sample_with_coverage(grammar, self._coverage, rng,
                                               candidates=self.candidates)
                self._plans_drawn += 1
                if fp.fine not in recent:
                    break
                # Lần rút cuối vẫn trùng thì vẫn GỬI ĐI, chỉ ghi sổ. Bỏ hẳn
                # một tờ vì không rút được cấu hình mới là để family cạn tổ
                # hợp quyết định số trang của cả lô.
                if attempt == self.plan_retries:
                    self._plan_collisions += 1
            assert plan is not None and fp is not None
            return plan, fp

    # -------------------------------------------------------- gác hình học

    def _collision(self, geo: GeometryFingerprint | None) -> Collision | None:
        """Bên trong khoá. Tờ gần nhất trong cửa sổ nếu nó vượt ngưỡng."""
        if geo is None or not geo.cells:
            return None
        window = self._geometry[-self.window:]
        best = nearest(geo, window)
        if best is None or best[1] < self.ceiling:
            return None
        key, score, ham = best
        # Quét lại danh sách thay vì `dict(window)[key]`: khoá do caller đặt,
        # và một caller đặt hai tờ cùng khoá (hay một khoá không băm được)
        # thì `dict()` nuốt mất một tờ hoặc ném -- cả hai đều là hỏng ở chỗ
        # chỉ dùng để viết một câu nhắc.
        other = next((fp for k, fp in window if k == key), None)
        hint = diversify_hint(geo, other, self._rows) if other is not None else ""
        return Collision(key, score, ham, hint)

    def _accept(self, plan_fp, geo, key, collision) -> None:
        """Bên trong khoá. Ghi một tờ đã nhận vào cả hai trí nhớ."""
        if plan_fp is not None:
            self._plan_fps.append(plan_fp)
        if geo is not None and geo.cells:
            self._geometry.append((key, geo))
        else:
            self._unavailable += 1
        if collision is not None:
            row = collision.as_dict()
            row["page"] = key
            self._kept_colliding.append(row)

    def _reject(self, key, collision: Collision, attempt: int) -> None:
        """Bên trong khoá. Ghi một tờ bị loại -- nó KHÔNG vào cửa sổ."""
        row = collision.as_dict()
        row.update({"page": key, "attempt": attempt})
        self._rejected.append(row)

    def judge(self, plan_fp: Fingerprint | None,
             geo: GeometryFingerprint | None, key: object = None,
             attempt: int = 1,
             force: bool = False) -> tuple[Collision | None, bool]:
        """XEM và GHI trong CÙNG một lần khoá. `(đụng ai, có nhận không)`.

        ## Vì sao phải là một thao tác, không phải `inspect()` rồi `accept()`

        `run()` chạy `concurrency` luồng. Hai tờ xong gần như cùng lúc mà
        hỏi rồi mới ghi thì cả hai cùng nhìn một cửa sổ CHƯA có tờ kia, cả
        hai cùng thấy sạch, và cả hai cùng được nhận -- đúng cặp trùng mà
        cổng này sinh ra để chặn, lọt qua vì hai câu lệnh không liền nhau.
        Ở mức song song 8 thì tối đa 8 tờ lọt cùng một lúc.

        `force=True` là lượt gọi cuối của tờ ấy: vẫn đo, vẫn ghi lại là
        trùng, nhưng NHẬN. Bỏ hẳn một tờ ở đây là để phép đo đa dạng quyết
        số trang của cả lô."""
        with self._lock:
            collision = self._collision(geo)
            if collision is not None and self.enabled and not force:
                self._reject(key, collision, attempt)
                return collision, False
            self._accept(plan_fp, geo, key,
                        collision if (collision is not None and self.enabled)
                        else None)
            return collision, True

    def inspect(self, geo: GeometryFingerprint) -> Collision | None:
        """Tờ gần nhất trong cửa sổ NẾU nó vượt ngưỡng. Không đổi trạng thái.

        Chỉ để ĐỌC (test, script đo lại). Đường chạy thật dùng `judge()` --
        xem docstring của nó về cuộc đua giữa hỏi và ghi."""
        with self._lock:
            return self._collision(geo)

    def accept(self, plan_fp: Fingerprint | None,
              geo: GeometryFingerprint | None, key: object = None,
              collision: Collision | None = None) -> None:
        """Ghi một tờ ĐÃ NHẬN vào cả hai trí nhớ.

        `geo=None` (không vẽ được, hết hạn chờ, `--no-draw`) vẫn ghi phần
        plan và đếm riêng ở `geometry_unavailable`: một phép đo thiếu phải
        đọc được trong báo cáo, không được lẫn vào "không có tờ nào trùng"."""
        with self._lock:
            self._accept(plan_fp, geo, key, collision)

    def reject(self, key: object, collision: Collision, attempt: int) -> None:
        """Ghi một tờ BỊ LOẠI vì trùng -- nó không vào cửa sổ."""
        with self._lock:
            self._reject(key, collision, attempt)

    # ------------------------------------------------------------- báo cáo

    def metrics(self, pages: int = 0) -> dict:
        """Số liệu đa dạng cho `compose_report.json`.

        `pages` là số tờ đã qua cổng chữ, truyền vào từ `run()`: tỉ lệ loại
        vì trùng phải tính trên số tờ THẬT SỰ được đo, không trên `want`
        (một tờ trượt cổng chưa bao giờ tới phép đo hình học)."""
        with self._lock:
            geo = [fp for _, fp in self._geometry]
            plans = list(self._plan_fps)
            rejected = list(self._rejected)
            kept_colliding = list(self._kept_colliding)
            drawn = self._plans_drawn
            plan_collisions = self._plan_collisions
            unavailable = self._unavailable
        # Mẫu số là số lượt ĐÃ TỚI CỔNG HÌNH HỌC -- tờ đo được cộng tờ bị
        # loại -- chứ không phải `pages`. Hai lý do: một tờ không dàn ra được
        # chưa bao giờ tới cổng nên không phải một lượt cổng ấy "cho qua", và
        # `_reconcile_sheet_count` ở `compose_page.py` còn lật vài tờ từ đạt
        # sang trượt SAU khi cổng này đã chạy, nên `pages` truyền vào có thể
        # nhỏ hơn số tờ cổng thật sự đã xem.
        attempts = len(geo) + len(rejected)
        return {
            "enabled": self.enabled,
            "coverage_steer": self.steer,
            "window": self.window,
            "jaccard_ceiling": self.ceiling,
            "candidates": self.candidates,
            "plan_retries": self.plan_retries,
            "pages_kept": pages,
            "pages_measured": len(geo),
            "plans_drawn": drawn,
            "plan_collisions": plan_collisions,
            "rejected_for_collision": len(rejected),
            # Mẫu số là số LƯỢT sinh đã đi tới phép đo (tờ nhận + tờ bị
            # loại), không phải số tờ nhận: "13% số lượt bị loại" và "15% số
            # tờ nhận từng bị loại một lần" là hai câu khác nhau, và câu đầu
            # mới là cái giá phải trả.
            "rejected_share": round(len(rejected) / attempts, 4) if attempts else 0.0,
            "kept_despite_collision": len(kept_colliding),
            "geometry_unavailable": unavailable,
            "plan_fingerprints": corpus_diversity(plans),
            "geometry": corpus_geometry(geo, self.window, self.ceiling),
            "collisions": rejected + [dict(r, kept=True) for r in kept_colliding],
        }


__all__ = ["CANDIDATES", "MAX_ATTEMPTS", "PLAN_RETRIES", "Collision",
          "DiversityWarden", "diversify_hint"]
