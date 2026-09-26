"""How close two DRAWN pages landed -- the half `document_distance.py` refuses.

    from agent.geometry_distance import jaccard, hamming, collides

`agent/document_distance.py` measures how far apart two `DocumentPlan`s are
and says so in its own docstring: "never geometry ... never a box, never a
pixel". That is the right boundary for what it answers -- document diversity
and dressing diversity are orthogonal by construction. This module is the
other side of the same boundary, and it exists because the measurement below
showed the structural side alone is blind to a real duplicate.

## The measurement that made this module necessary

94 LLM-written documents, `data/pilot16` + `data/pilot17`, 4 371 unordered
pairs, grid 8x12 (`agent/fingerprint.py::GRID_COLS`):

| pair | plan distance | geometry Jaccard |
| --- | --- | --- |
| `handover_record_0010` / `invoice_detailed_0023` | **1.000** | 0.895 |
| `form_roster_0007` / `invoice_detailed_0023` | **1.000** | 0.891 |
| `form_roster_0007` / `handover_record_0010` | **1.000** | 0.858 |

`distance()` in `document_distance.py` reads 1.000 -- "differs at every tier
including family" -- on the three most visually identical pairs in the whole
corpus. It is not wrong; it is answering a different question. Three families
that each drew `density=dense` + `table` and got realized into the same
three-sheet `Page-Header / Title / Table x3 / Text` stack ARE structurally
different documents. They are also, to a model reading the pixels, the same
sheet of paper three times.

## Two numbers, one of them decides

- **`jaccard(a, b)`** over the labelled cell sets -- the decision. 0.0 no
  shared cell, 1.0 the same regions in the same cells on the same sheets.
- **`hamming(a, b)`** over the tờ-đầu ink bitmap -- reported, never a gate.

Why Hamming does not gate, measured on the same 4 371 pairs:

    pairs with Jaccard >= 0.60 ....  38, and ALL 38 have Hamming <= 0.240
                                     (median 0.078) -- a `Hamming <= 0.25`
                                     condition would have vetoed 0 of them
    pairs with Jaccard <  0.60 .... 4 333, of which 1 329 (30,7%) ALSO have
                                     Hamming <= 0.25

So Hamming-as-a-second-condition is a gate that has never once fired, and
Hamming-alone would call nearly a third of ordinary pairs duplicates. A
condition that cannot change a decision must not be written as if it could
(AGENTS.md mục 5: chỗ đỡ, không phải cổng gác). It is kept because it is a
genuinely independent view -- it reads no labels at all -- so when the two
numbers ever DO disagree on real data, the report shows it and somebody gets
to look. `nearest()` returns both for exactly that reason.

## Why a recent WINDOW and not the whole batch

Comparing against every page ever made is O(n) per page and, worse, wrong at
scale: at 20 000 pages some pair of them is going to be close no matter what
the sampler does, and rejecting on that is rejecting the birthday paradox.
What a corpus can actually be faulted for is pages that repeat each other
NEARBY. Measured on the 94-document corpus in corpus order:

    window  12, J >= 0.60 ....  8/94 ( 8,5%) pages would be rejected
    window  24, J >= 0.60 .... 14/94 (14,9%)
    window all, J >= 0.60 .... 17/94 (18,1%)

The window is a knob on how much regeneration the batch is willing to buy,
and 24 is the default because it is one full round of the 30-family
round-robin minus a few -- roughly "do not repeat a layout inside one lap".
"""

from __future__ import annotations

from agent.fingerprint import (
    GRID_COLS,
    GRID_ROWS,
    GeometryFingerprint,
    geometry_fingerprint,
)

# Jaccard từ mức này trở lên là TRÙNG. Chọn 0,60 từ bảng đo trong docstring
# (cửa sổ 24): 0,70 chỉ bắt 4/94 tờ (4,3%) -- bỏ sót cả cặp J=0,66 mà mắt đọc
# là một tờ; 0,50 bắt 24/94 (25,5%), tức một phần tư lô phải sinh lại và mỗi
# lần sinh lại là một lời gọi model chừng 110-430 giây. 0,60 bắt 14/94 (14,9%).
JACCARD_CEILING = 0.60

# Bao nhiêu tờ gần đây được so. Xem "Why a recent WINDOW" trên.
WINDOW = 24


def jaccard(a: GeometryFingerprint, b: GeometryFingerprint) -> float:
    """Phần giao trên phần hợp của hai tập ô có nhãn. 1.0 = trùng khít.

    Hai dấu vân RỖNG (không vùng nào đo được) trả 0.0, không phải 1.0. Hai
    tờ không đo được không phải hai tờ giống nhau -- chúng là hai tờ chưa
    biết, và gọi chúng là trùng sẽ loại tờ thứ hai vì một phép đo hỏng."""
    if not a.cells or not b.cells:
        return 0.0
    union = len(a.cells | b.cells)
    return len(a.cells & b.cells) / union if union else 0.0


def hamming(a: GeometryFingerprint, b: GeometryFingerprint,
           bits: int = GRID_COLS * GRID_ROWS) -> float:
    """Tỉ lệ ô lưới tờ đầu mà một bên có mực còn bên kia không. 0.0 = trùng."""
    return bin(a.grid ^ b.grid).count("1") / bits if bits else 0.0


def nearest(target: GeometryFingerprint,
           seen: list) -> tuple[int, float, float] | None:
    """Tờ gần nhất trong `seen` theo Jaccard: `(chỉ số, jaccard, hamming)`.

    `seen` là danh sách `(khoá, GeometryFingerprint)` -- khoá là thứ caller
    dùng để gọi tên tờ ấy (chỉ số trang, stem...), hàm này không đọc nó.
    `None` khi `seen` rỗng hoặc `target` không có ô nào đo được.

    Trả CẢ HAI con số, không chỉ con số quyết định: xem docstring module --
    Hamming ở đây để lần đầu tiên hai phép đo bất đồng thì báo cáo nói ra."""
    if not seen or not target.cells:
        return None
    best = None
    for key, other in seen:
        score = jaccard(target, other)
        if best is None or score > best[1]:
            best = (key, score, hamming(target, other))
    return best


def collides(target: GeometryFingerprint, seen: list,
            ceiling: float = JACCARD_CEILING) -> tuple[int, float, float] | None:
    """Tờ gần nhất NẾU nó vượt ngưỡng, `None` nếu không. Không ném."""
    best = nearest(target, seen)
    return best if best is not None and best[1] >= ceiling else None


def corpus_geometry(fingerprints: list, window: int = WINDOW,
                   ceiling: float = JACCARD_CEILING) -> dict:
    """Tóm tắt cả lô: phân bố khoảng cách tới láng giềng gần nhất.

    Song song `document_distance.corpus_diversity`, và cố ý KHÁC nó ở một
    chỗ: không tính trung bình mọi cặp. Trung bình mọi cặp trên một lô 20 000
    tờ là một con số bị chi phối bởi những cặp chẳng liên quan gì đến nhau,
    và nó nhúc nhích quá chậm để đọc ra xu hướng. Thứ đọc được là **láng
    giềng gần nhất trong cửa sổ** của từng tờ: trung vị nói cả lô đang lặp
    đến đâu, phân vị 90 nói cái đuôi xấu nhất, và `over_ceiling` đếm thẳng
    số tờ đáng lẽ đã bị loại.

    Thứ tự danh sách LÀ thứ tự sinh -- cửa sổ trượt theo nó."""
    order = list(fingerprints)
    js: list[float] = []
    hs: list[float] = []
    over = 0
    seen: list = []
    for i, fp in enumerate(order):
        best = nearest(fp, seen[-window:]) if seen else None
        if best is not None:
            js.append(round(best[1], 4))
            hs.append(round(best[2], 4))
            if best[1] >= ceiling:
                over += 1
        seen.append((i, fp))

    def spread(values: list[float]) -> dict:
        if not values:
            return {"n": 0, "median": None, "p90": None, "max": None}
        ordered = sorted(values)
        return {"n": len(ordered),
                "median": ordered[len(ordered) // 2],
                "p90": ordered[min(int(0.9 * len(ordered)), len(ordered) - 1)],
                "max": ordered[-1]}

    # Histogram cố định 10 khoang: một khoang thay đổi theo dữ liệu thì hai
    # lượt chạy không so được với nhau, và so hai lượt chính là việc của nó.
    bins = {f"{i / 10:.1f}-{(i + 1) / 10:.1f}": 0 for i in range(10)}
    for value in js:
        index = min(9, max(0, int(value * 10)))
        bins[f"{index / 10:.1f}-{(index + 1) / 10:.1f}"] += 1
    return {
        "documents": len(order),
        "window": window, "ceiling": ceiling,
        "grid": f"{GRID_COLS}x{GRID_ROWS}",
        "nearest_jaccard": spread(js),
        "nearest_hamming": spread(hs),
        "jaccard_histogram": bins,
        "over_ceiling": over,
        "over_ceiling_share": round(over / len(order), 4) if order else 0.0,
        "distinct_cell_sets": len({fp.cells for fp in order}),
    }


__all__ = ["JACCARD_CEILING", "WINDOW", "collides", "corpus_geometry",
          "geometry_fingerprint", "hamming", "jaccard", "nearest"]
