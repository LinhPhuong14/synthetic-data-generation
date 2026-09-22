"""Thước đo cho nhãn kho này sinh ra: PCC cho KIE, GriTS cho bảng.

Kho này là bộ SINH, không phải bộ huấn luyện — nên module này không chấm một
mô hình nào. Nó cho phép so **một đầu ra bất kỳ** với nhãn của một trang, bằng
đúng thước mà hai benchmark tham chiếu dùng, để câu "dữ liệu này dạy được"
thôi là một lời khai.

## Vì sao PCC chứ không phải IoU

DocILE (arXiv 2302.05658) chấm KIE bằng **Pseudo-Character-Center**: chỗ ngồi
của một trường được quyết bởi việc hộp của nó quây trúng **tâm ký tự của
những từ nào** trên trang, và một dự đoán đúng khi nó quây ra **đúng tập ấy**.
IoU thì phạt oan đúng chỗ kho này hay rơi vào: hộp ở đây đọc từ DOM Chromium
nên nó ôm cả phần đệm của thẻ, rộng hơn nét mực. Hai hộp cùng trỏ vào một
chuỗi chữ có thể chỉ đạt IoU 0,25 mà vẫn là cùng một câu trả lời.

## Vì sao GriTS bên cạnh TEDS

GriTS (arXiv 2203.12555) so hai bảng dưới dạng **ma trận**, không dưới dạng
cây HTML. Tác giả chỉ ra TEDS nhạy khác nhau với việc thiếu một CỘT so với
thiếu một DÒNG, vì cây HTML dựng theo dòng — một bất đối xứng không có trong
bản thân cái bảng. Ba biến thể, cùng một công thức, khác nhau ở hàm so ô:

    GriTS_f(A, B) = 2 · Σ f(Ã_ij, B̃_ij) / (|A| + |B|)

- `top` — hình học lưới: IoU của (rowspan, colspan)
- `con` — nội dung: LCS chuẩn hoá trên chữ của ô
- `loc` — chỗ đứng thật: IoU của hộp pixel

## Chỗ này KHÁC bài báo, nói trước

2D-MSS là bài toán NP-khó; bài báo dùng một heuristic thời gian đa thức. Ở đây
dùng phép **xấp xỉ tách trục**: gióng cột trước bằng quy hoạch động, rồi gióng
dòng dưới phép gióng cột ấy. Nó không đi tìm cực đại toàn cục, nên điểm trả về
là **cận dưới** của GriTS thật. Với bảng sinh từ markup — cùng số cột, chỉ
lệch ở nội dung — hai con số trùng nhau; với bảng lệch cấu trúc nặng thì điểm
ở đây thấp hơn. Đừng đem so thẳng với bảng xếp hạng của bài báo.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Sequence

# ------------------------------------------------------------------ PCC


def pseudo_character_centers(bbox: Sequence[float],
                             text: str) -> list[tuple[float, float]]:
    """Tâm giả của từng ký tự trong một từ đã có hộp.

    Chia bề ngang hộp thành `len(text)` lát bằng nhau rồi lấy tâm mỗi lát.
    Không đo lại gì từ ảnh — đó là cả điểm của phép này: nó chạy được ở nơi
    chỉ có nhãn, và nó đủ để nói "hộp này có trùm chữ ấy không".

    Khoảng trắng KHÔNG sinh tâm: một dấu cách không có mực, nên một hộp cắt
    ngang khoảng trắng giữa hai từ không vì thế mà bị tính là trùm.
    """
    x1, y1, x2, y2 = (float(v) for v in bbox)
    body = [i for i, ch in enumerate(text) if not ch.isspace()]
    if not body or x2 <= x1:
        return []
    width = (x2 - x1) / len(text)
    middle = (y1 + y2) / 2.0
    return [(x1 + width * (i + 0.5), middle) for i in body]


def _inside(point: tuple[float, float], bbox: Sequence[float]) -> bool:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return x1 <= point[0] <= x2 and y1 <= point[1] <= y2


def page_points(words: Sequence[dict]) -> list[tuple[int, int, float, float]]:
    """Tâm ký tự của CẢ TRANG, tính một lần: `(từ, ký tự, x, y)`.

    Tách ra khỏi `selected` vì chi phí nằm ở đây, không ở phép quây. Một trang
    có ~450 từ ~8 ký tự là ~3.600 điểm; `score_lir` xét mọi cặp (dòng thật,
    dòng dự đoán) nên với 136 dòng hàng nó gọi `score_kile` 18.496 lần. Tính
    lại 3.600 điểm mỗi lần là 67 triệu phép — đo được: quá 120 giây cho MỘT
    tờ. Tính trước rồi lọc thì mỗi lần chỉ còn một vòng quét.
    """
    out: list[tuple[int, int, float, float]] = []
    for index, word in enumerate(words):
        box = word.get("bbox")
        if not box:
            continue
        for at, (x, y) in enumerate(pseudo_character_centers(box,
                                                             word.get("text", ""))):
            out.append((index, at, x, y))
    return out


def selected(bbox: Sequence[float],
             words: Sequence[dict] | None = None,
             points: Sequence[tuple[int, int, float, float]] | None = None,
             ) -> frozenset[tuple[int, int]]:
    """Những tâm ký tự của trang mà hộp này quây được.

    Khoá là `(chỉ số từ, chỉ số ký tự)`, nên hai từ trùng chữ ở hai chỗ khác
    nhau không lẫn vào nhau. Đưa `points` của `page_points` vào khi gọi nhiều
    lần trên cùng một trang.
    """
    if points is None:
        points = page_points(words or [])
    x1, y1, x2, y2 = (float(v) for v in bbox)
    return frozenset((i, at) for i, at, x, y in points
                     if x1 <= x <= x2 and y1 <= y <= y2)


def pcc_hit(predicted: Sequence[float], target: Sequence[float],
            words: Sequence[dict]) -> bool:
    """Hộp `predicted` có trỏ đúng chỗ `target` trỏ không, theo luật DocILE.

    Luật là **hai hộp quây ra CÙNG MỘT tập tâm ký tự** của những từ trên
    trang — không phải "hộp dự đoán chứa đủ chữ và không chứa gì khác". Khác
    nhau ở chỗ quan trọng: nhãn của kho này có hộp LỒNG NHAU hợp lệ (một cặp
    `declared` trùm cả run, một cặp `table` trỏ vào một ô bên trong nó), và
    luật "không chứa gì khác" bắt chính nhãn thật trượt. Đo được trên
    `bang_luong_00000`: **145 trên 306** trường có hộp chứa tâm ký tự của
    trường khác, nên chấm nhãn với chính nó chỉ ra F1 **0,53** — một thước đo
    mà bản thân sự thật không đạt điểm tuyệt đối thì không đo được gì.

    Cách so tập thì đúng theo định nghĩa: `score(gold, gold)` luôn bằng 1.

    `words` là `record.word_annotations` của trang — từ và hộp của chúng.
    Không có từ nào thì không có gì để quây, và hàm trả về False thay vì lặng
    lẽ coi hai hộp rỗng là khớp nhau.
    """
    mine = selected(predicted, words)
    if not mine:
        return False
    return mine == selected(target, words)


def _f1(hit: int, n_pred: int, n_gold: int) -> dict[str, float]:
    precision = hit / n_pred if n_pred else 0.0
    recall = hit / n_gold if n_gold else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "matched": hit,
            "predicted": n_pred, "gold": n_gold}


def _matched(predicted: Sequence[dict], pred_sel: Sequence[frozenset],
             gold: Sequence[dict], gold_sel: Sequence[frozenset]) -> int:
    """Số trường thật được ghép. Mỗi trường thật nhiều nhất một lần — không thì
    mười dự đoán chồng lên một trường đúng sẽ ra recall hoàn hảo."""
    taken: set[int] = set()
    hit = 0
    for at, pred in enumerate(predicted):
        if not pred_sel[at]:
            continue
        for index, one in enumerate(gold):
            if index in taken or one.get("field") != pred.get("field"):
                continue
            if pred_sel[at] == gold_sel[index]:
                taken.add(index)
                hit += 1
                break
    return hit


def score_kile(predicted: Sequence[dict], gold: Sequence[dict],
               words: Sequence[dict]) -> dict[str, float]:
    """KILE của DocILE: đúng khi CÙNG loại trường và CÙNG chỗ.

    `predicted` và `gold` là list `{"field": str, "bbox": [x1,y1,x2,y2]}` —
    đúng hình dạng `kie.pairs` mang, chỉ đổi tên `value_*`. `words` là
    `record.word_annotations` của trang: chỗ ngồi được quyết bằng việc hai hộp
    quây ra cùng những từ nào, nên phải có danh sách từ để mà quây.
    """
    points = page_points(words)
    return _f1(_matched(predicted, [selected(p["bbox"], points=points) for p in predicted],
                        gold, [selected(g["bbox"], points=points) for g in gold]),
               len(predicted), len(gold))


def score_lir(predicted: Sequence[dict], gold: Sequence[dict],
              words: Sequence[dict]) -> dict[str, float]:
    """LIR của DocILE: gom trường thành DÒNG HÀNG rồi mới chấm.

    Bài báo tìm phép ghép cực đại giữa dòng hàng dự đoán và dòng hàng thật,
    tối đa hoá recall toàn cục. Ở đây dùng phép tham lam: xét dòng thật theo
    thứ tự số trường giảm dần, mỗi dòng lấy dòng dự đoán khớp được nhiều
    trường nhất còn trống. Với bảng mà mỗi dòng là một dòng hàng rõ ràng, hai
    phép cho cùng kết quả; phép tham lam chỉ thua khi hai dòng thật tranh nhau
    một dòng dự đoán, và khi ấy nó cho **cận dưới**.

    Trường không thuộc dòng hàng nào (`line_item_id` rỗng — nhãn trải cả dòng,
    chẳng hạn) bị bỏ qua ở cả hai vế: LIR không hỏi về chúng.
    """
    def grouped(rows: Sequence[dict]) -> dict[Any, list[dict]]:
        out: dict[Any, list[dict]] = {}
        for row in rows:
            key = row.get("line_item_id")
            if key:
                out.setdefault(key, []).append(row)
        return out

    gold_items = grouped(gold)
    pred_items = grouped(predicted)
    # Tính tâm ký tự MỘT LẦN cho cả trang, rồi tập quây MỘT LẦN cho mỗi trường.
    # Vòng tham lam dưới đây xét mọi cặp (dòng thật, dòng dự đoán) nên chi phí
    # là số cặp, không được nhân thêm chi phí tính lại cả trang.
    points = page_points(words)
    sel = {id(row): selected(row["bbox"], points=points)
           for row in list(gold) + list(predicted)}
    free = set(pred_items)
    hit = 0
    for _, want in sorted(gold_items.items(), key=lambda kv: -len(kv[1])):
        want_sel = [sel[id(r)] for r in want]
        best_key, best_hit = None, 0
        for key in free:
            rows = pred_items[key]
            got = _matched(rows, [sel[id(r)] for r in rows], want, want_sel)
            if got > best_hit:
                best_key, best_hit = key, got
        if best_key is not None:
            free.discard(best_key)
            hit += best_hit
    n_pred = sum(len(v) for v in pred_items.values())
    n_gold = sum(len(v) for v in gold_items.values())
    return _f1(hit, n_pred, n_gold)


# ---------------------------------------------------------------- GriTS


def _lcs(a: str, b: str) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for ch in a:
        current = [0]
        for j, other in enumerate(b):
            current.append(previous[j] + 1 if ch == other
                           else max(previous[j + 1], current[j]))
        previous = current
    return previous[-1]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", " ".join(str(text or "").split()))


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = (float(v) for v in a)
    bx1, by1, bx2, by2 = (float(v) for v in b)
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    overlap = ix * iy
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - overlap
    return overlap / union if union > 0 else 0.0


def cell_similarity(left: dict | None, right: dict | None, kind: str) -> float:
    """Ba hàm so ô của GriTS.

    HAI BÊN CÙNG TRỐNG LÀ ĐỒNG Ý, không phải bất đồng. Bảng thật có hàng răng
    cưa — một hàng bốn ô nằm trong bảng sáu cột — nên ma trận có lỗ, và lỗ ấy
    là một sự thật về cái bảng chứ không phải chỗ thiếu dữ liệu. Tính
    `f(None, None) = 0` thì mẫu số vẫn đếm ô ấy mà tử số thì không, nên một
    bảng so với CHÍNH NÓ không ra 1,0. Đo được trên 555 bảng thật: trung bình
    **0,727**, thấp nhất 0,257 — một thước đo mà sự thật không đạt điểm tuyệt
    đối thì không đo được gì.

    Một bên có ô, bên kia trống thì vẫn là 0: đó mới là bất đồng thật.
    """
    if left is None and right is None:
        return 1.0
    if not left or not right:
        return 0.0
    if kind == "top":
        # Hình học LƯỚI: coi (colspan, rowspan) là một hình chữ nhật đặt ở gốc
        # rồi lấy IoU. Hai ô cùng trải 2x1 là giống nhau hoàn toàn, dù chúng
        # ngồi ở đâu — chỗ ngồi đã do phép gióng lo.
        return _iou([0, 0, left.get("colspan", 1), left.get("rowspan", 1)],
                    [0, 0, right.get("colspan", 1), right.get("rowspan", 1)])
    if kind == "con":
        a, b = _norm(left.get("text", "")), _norm(right.get("text", ""))
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return 2.0 * _lcs(a, b) / (len(a) + len(b))
    if kind == "loc":
        if not left.get("bbox") or not right.get("bbox"):
            return 0.0
        return _iou(left["bbox"], right["bbox"])
    raise ValueError(f"kind phải là 'top'/'con'/'loc', không phải {kind!r}")


def _align(n: int, m: int, score) -> list[tuple[int, int]]:
    """Gióng hai dãy giữ nguyên thứ tự, tối đa tổng điểm. Cho phép bỏ qua."""
    table = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            table[i][j] = max(table[i - 1][j], table[i][j - 1],
                              table[i - 1][j - 1] + score(i - 1, j - 1))
    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        if table[i][j] == table[i - 1][j]:
            i -= 1
        elif table[i][j] == table[i][j - 1]:
            j -= 1
        else:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
    return pairs[::-1]


def as_matrix(table: dict) -> list[list[dict | None]]:
    """Bảng của `kie_full.table_structures` thành ma trận ô.

    Một ô trải `colspan` cột thì nó NGỒI Ở CẢ NGẦN ẤY Ô của ma trận — đó là
    định nghĩa "dạng ma trận" của GriTS, và cũng là lý do phép đo này không
    cần canonicalize: ô gộp đã được trải ra, nên hai cách viết cùng một bảng
    cho cùng một ma trận.

    ## `row` là chỉ số THẬT, không phải chỉ số trong mảnh

    `_Spans` lấy `row` từ `data-row` khi thẻ có — và engine đánh số ấy theo cả
    bảng dài, không theo mảnh. Đo được trên `bang_cham_cong_00007` mảnh `t2`:
    54 hàng, nhưng `row` chạy 0..92. Bản trước dựng lưới 54 dòng rồi bỏ mọi ô
    có `row > 53`, nên ma trận rỗng gần hết và GriTS tự chấm chính nó ra
    **0,33** thay vì 1,0 — hỏng im lặng, và bộ test dùng bảng đồ chơi đánh số
    liền từ 0 nên không thấy.

    Nên nén chỉ số: các giá trị `row` có mặt, xếp tăng dần, thành 0..n-1. Giữ
    `row` gốc trong ô (nó là thông tin thật, dùng để nối mảnh) và chỉ nén ở
    đây, nơi cần một lưới đặc.
    """
    rows = sorted({c["row"] for c in table["cells"]})
    cols = sorted({c["col"] for c in table["cells"]})
    if not rows or not cols:
        return []
    row_at = {value: index for index, value in enumerate(rows)}
    col_at = {value: index for index, value in enumerate(cols)}
    width = max(len(cols), max(col_at[c["col"]] + c.get("colspan", 1)
                               for c in table["cells"]))
    grid: list[list[dict | None]] = [[None] * width for _ in rows]
    for cell in table["cells"]:
        top, left = row_at[cell["row"]], col_at[cell["col"]]
        for r in range(top, min(top + cell.get("rowspan", 1), len(rows))):
            for c in range(left, min(left + cell.get("colspan", 1), width)):
                grid[r][c] = cell
    return grid


def grits(gold: dict, predicted: dict, kind: str = "con") -> float:
    """`GriTS_f(A, B) = 2·Σ f / (|A| + |B|)`, xấp xỉ tách trục.

    `|A|`, `|B|` là SỐ Ô CỦA MA TRẬN (dòng × cột), không phải số thẻ `<td>`:
    một ô trải bốn cột đóng góp bốn ô, và một bảng đoán thiếu nó mất cả bốn.
    """
    a, b = as_matrix(gold), as_matrix(predicted)
    if not a or not b or not a[0] or not b[0]:
        return 0.0

    # ĐỆM THEO CẶP Ô. Bảng quy hoạch động hỏi cùng một cặp ô rất nhiều lần:
    # với bảng 93 dòng x 4 cột, `row_score` gọi `cell_similarity` khoảng 35
    # nghìn lần, mỗi lần một phép LCS trên chữ của ô. Đo được: 555 bảng chạy
    # quá 120 giây. Số cặp ô KHÁC NHAU thì nhỏ hơn nhiều, nên nhớ lại là đủ.
    #
    # Khoá theo `id`: ô là dict không băm được. Đệm chỉ bỏ công VIỆC LẶP,
    # không gộp hai ô khác nhau làm một.
    memo: dict[tuple[int, int], float] = {}

    def sim(left, right) -> float:
        key = (id(left), id(right))
        got = memo.get(key)
        if got is None:
            got = cell_similarity(left, right, kind)
            memo[key] = got
        return got

    # Cột trước: so hai cột bằng tổng điểm ô dưới phép gióng dòng đồng nhất.
    def column_score(i: int, j: int) -> float:
        return sum(sim(a[r][i], b[r][j]) for r in range(min(len(a), len(b))))

    columns = _align(len(a[0]), len(b[0]), column_score)

    # Rồi dòng, dưới đúng phép gióng cột vừa tìm được.
    def row_score(i: int, j: int) -> float:
        return sum(sim(a[i][ci], b[j][cj]) for ci, cj in columns)

    rows = _align(len(a), len(b), row_score)

    total = sum(sim(a[ri][ci], b[rj][cj])
                for ri, rj in rows for ci, cj in columns)
    size = len(a) * len(a[0]) + len(b) * len(b[0])
    return round(2.0 * total / size, 4) if size else 0.0


__all__ = ["as_matrix", "cell_similarity", "grits", "pcc_hit", "selected",
           "page_points", "pseudo_character_centers", "score_kile", "score_lir"]
