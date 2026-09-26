"""Pha 2: điền giá trị thật vào phôi. KHÔNG một lời gọi model nào.

    from synthgen.fill import Filler
    filler = Filler(template)
    page = filler.draw(random.Random(3))      # một tờ khác, cùng phôi

Một phôi đã qua cổng ở pha 1 (`agent/compose_template.py`) sinh ra hàng trăm
tới hàng nghìn tờ ở đây, với giá bằng không lời gọi model. Đó là cả lý do
đường sinh này tồn tại -- xem `docs/duong-sinh-phoi.md` cho bảng chi phí ba
đường.

## Hai tầng chống trùng, và vì sao chúng đo hai thứ khác nhau

| tầng | câu hỏi | trí nhớ | ai quyết |
| --- | --- | --- | --- |
| **trong một phôi** | tổ hợp giá trị này đã điền vào ĐÚNG phôi này chưa | `Filler` | trước khi vẽ, miễn phí |
| **cả lô** | tờ vừa vẽ có ĐÁP xuống chỗ một tờ gần đây không | `DiversityWarden` | sau khi vẽ, đọc pixel |

Tầng một dùng `agent/coverage.py::CoverageMemory` nguyên văn, trên một
`agent/fingerprint.py::Fingerprint` ba tầng dựng từ GIÁ TRỊ thay vì từ
`DocumentPlan` -- cùng lớp, cùng phép xếp hạng từ điển (coarse quyết trước,
mid phá hoà, fine phá hoà tiếp), khác mỗi nguồn của ba tuple. Nó bắt được
"hai tờ này khác mỗi cái tên khách hàng"; nó KHÔNG bắt được "hai phôi khác
nhau vẽ ra hai tờ trông y hệt", vì nó chưa từng nhìn thấy pixel nào.

Tầng hai bắt đúng chỗ ấy, và nó phải nằm sau phép vẽ vì đó là chỗ duy nhất
đọc được chỗ mực rơi xuống. Ba cặp tờ giống nhau nhất trong `data/pilot16` +
`data/pilot17` được `agent/document_distance.py` chấm 1.000 -- khác nhau tối
đa -- vì chúng thuộc ba family khác nhau; bảng số ở
`agent/geometry_distance.py`. Một dấu vân đọc cấu hình không bao giờ thấy
được điều một dấu vân đọc hình học thấy ngay.

Cái giá của hai tầng ở đây RẺ hơn hẳn đường model-viết-từng-trang: ở đó, một
tờ bị loại vì trùng hình học đốt thêm một lời gọi 110-430 giây; ở đây nó đốt
thêm một lần bốc giá trị (chừng một phần nghìn giây) cộng một lần dàn trang
(một tới ba giây). Nên `attempts` ở đây để rộng tay được, và mặc định 4 thay
vì 2 của `agent/diversity.py::MAX_ATTEMPTS`.

## Hộp đo TRÊN TRANG ĐÃ ĐIỀN, không bao giờ trên phôi

`synthgen/template.py::Template` không mang một toạ độ nào, có chủ ý: giá trị
thật dài ngắn khác chỗ trống (`{{issuer.name}}` là 17 ký tự, "CÔNG TY TNHH KỸ
THUẬT VÀ TỰ ĐỘNG HOÁ TÂN PHÁT" là 45), nên mọi hộp đo trên phôi đều sai cho
trang đã điền. Ở đây trang đã điền đi qua đúng `synthgen/draw_llm.py::
draw_one` mà mọi trang khác của kho đi qua, và Chromium đo lại từ đầu
(AGENTS.md luật 1). `tests/test_fill_measure.py` khoá lại điều ấy bằng cách
điền hai bộ giá trị dài ngắn khác nhau vào CÙNG một phôi rồi đòi hộp phải
khác nhau.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.coverage import CoverageMemory  # noqa: E402
from agent.fingerprint import Fingerprint  # noqa: E402
from synthgen import template as T  # noqa: E402
from synthgen import values as V  # noqa: E402

# Bao nhiêu tổ hợp giá trị rút ra rồi giữ lại cái ít gặp nhất. Cùng con số
# `agent/diversity.py::CANDIDATES` dùng cho plan, và cùng lý lẽ: một lần bốc
# giá trị là vài trăm micro giây còn một lần dàn trang là một tới ba giây --
# không có lý do tiết kiệm ở đầu rẻ.
CANDIDATES = 8

# Rút lại mấy lần khi tổ hợp vừa rút TRÙNG KHÍT một tổ hợp đã điền vào chính
# phôi này. Tám là đủ rộng: với 8-40 chỗ trống, mỗi chỗ rút từ một kho hàng
# trăm mục, tám lần rút hụt liên tiếp nghĩa là phôi ấy thật sự chỉ có vài tổ
# hợp (một phôi hai chỗ trống, cả hai là `document.currency` chẳng hạn).
EXACT_RETRIES = 8

# Mức dòng bảng. `coarse` đọc NHÓM chứ không đọc con số: 7 dòng và 8 dòng là
# cùng một hình dáng tờ giấy, còn 7 dòng và 40 dòng thì không.
ROW_BANDS = (0, 1, 4, 9, 16, 30, 60)


def _band(n: int) -> int:
    top = 0
    for edge in ROW_BANDS:
        if n >= edge:
            top = edge
    return top


@dataclass
class Filling:
    """Một lần điền: tờ khai sự thật, HTML đã điền, và dấu vân của nó."""

    html: str
    tree: dict
    values: dict                 # bảng phẳng ĐÃ BUNG chỉ số
    counts: dict                 # {"line_items": 9, "signers": 2}
    printed: dict                # chỉ những chỗ trống phôi THẬT SỰ in ra
    fingerprint: Fingerprint
    missing: list = field(default_factory=list)

    @property
    def rows(self) -> list:
        """Dòng bảng ở dạng SỐ NGUYÊN, cho phép kiểm số học."""
        return list(self.tree.get("_rows") or [])


def value_fingerprint(template_id: str, printed: dict, counts: dict) -> Fingerprint:
    """Ba tầng cho MỘT tổ hợp giá trị -- cùng lớp `Fingerprint` của plan.

    * `coarse` -- phôi nào, bao nhiêu dòng (theo NHÓM), bao nhiêu người ký.
      "Tờ này đại khái cùng dáng với tờ kia."
    * `mid` -- KHÔNG mang `template_id`, cố ý, y như `mid` của
      `agent/fingerprint.py` cố ý không mang `family`: nó so được GIỮA các
      phôi, và trả lời "bao nhiêu tờ trong cả lô ra đúng cái dáng này", đúng
      câu mà một phép phá hoà coverage muốn hỏi.
    * `fine` -- phôi cộng TOÀN BỘ cặp (đường dẫn, giá trị) đã in. Hai lần điền
      chỉ `fine`-trùng khi chúng là cùng một tờ giấy, chữ trên chữ.

    Chỉ đọc `printed` -- chỗ trống phôi THẬT SỰ in -- chứ không đọc cả tờ
    khai: `facts()` sinh đủ 60 khoá cho mọi lần điền, nên một dấu vân đọc cả
    tờ khai sẽ coi hai tờ khác nhau ở đúng cái trường mà phôi không in là hai
    tờ khác nhau. Chúng không khác nhau -- trên giấy chúng giống hệt."""
    rows = int(counts.get("line_items", 0) or 0)
    signers = int(counts.get("signers", 0) or 0)
    printed_len = sum(len(str(v)) for v in printed.values())
    coarse = (template_id, _band(rows), signers)
    mid = (_band(rows), signers, printed_len // 200, len(printed))
    fine = (template_id,) + tuple(sorted(printed.items()))
    return Fingerprint(coarse=coarse, mid=mid, fine=fine)


class Filler:
    """Trí nhớ giá trị của MỘT phôi. Không an toàn nhiều luồng -- mỗi luồng
    một `Filler`, hoặc một khoá ở người gọi.

    Khác `agent/diversity.py::DiversityWarden` ở chỗ đó có chủ ý: warden giữ
    trí nhớ CẢ LÔ nên phải khoá, còn phôi thì chia được theo luồng (một luồng
    một phôi) và một khoá cho mỗi phôi là một khoá không ai tranh."""

    def __init__(self, template: T.Template, *,
                 candidates: int = CANDIDATES,
                 exact_retries: int = EXACT_RETRIES,
                 rows: tuple[int, int] = (3, 24),
                 signers: tuple[int, int] = (1, 4),
                 clauses: tuple[int, int] = (2, 7)) -> None:
        self.template = template
        self.candidates = candidates
        self.exact_retries = exact_retries
        self._rows = rows
        self._signers = signers
        self._clauses = clauses
        self._memory = CoverageMemory()
        # Tổ hợp ĐÃ DÙNG, chặn CỨNG. `CoverageMemory` chỉ hạ ưu tiên, không
        # cấm -- và yêu cầu ở đây là "đừng điền cùng một tổ hợp hai lần vào
        # cùng một phôi", một câu cấm chứ không phải một câu nghiêng.
        self._used: set = set()
        self._exact_collisions = 0
        self._drawn = 0
        self._slots = T.paths(template.html)
        self._repeats = template.repeat_names

    # --------------------------------------------------------------- rút giá trị

    def _counts(self, rng: random.Random) -> dict:
        """Số dòng cho mỗi nhóm lặp mà phôi này THẬT SỰ có.

        Phôi không có khối `data-repeat="line_items"` thì không xin dòng hàng
        nào, và rút một con số cho nó là làm lệch dấu vân bằng một chiều
        không tồn tại trên giấy."""
        out: dict = {}
        for name in self._repeats:
            lo, hi = {"line_items": self._rows, "signers": self._signers,
                      "clauses": self._clauses}.get(name, (1, 6))
            out[name] = rng.randint(lo, hi)
        return out

    def _one(self, rng: random.Random) -> Filling:
        counts = self._counts(rng)
        overrides = {}
        if self.template.doc_title:
            overrides["document.title"] = self.template.doc_title
        tree = V.facts(rng,
                       rows=counts.get("line_items", 0),
                       signers=counts.get("signers", 0),
                       clauses=counts.get("clauses", 0),
                       overrides=overrides)
        flat = V.flatten(tree)
        html, missing = T.fill_html(self.template.html, flat, counts)
        printed = {k: v for k, v in flat.items() if _wanted(k, self._slots)}
        fp = value_fingerprint(self.template.template_id, printed, counts)
        return Filling(html=html, tree=tree, values=flat, counts=counts,
                       printed=printed, fingerprint=fp, missing=missing)

    def draw(self, rng: random.Random) -> Filling:
        """Một lần điền đã né tổ hợp cũ. Ghi nhận rồi trả về.

        Hai vòng, hai việc khác nhau:

        1. `exact_retries` lần để tránh TRÙNG KHÍT (`fine` đã dùng). Đây là
           một câu cấm.
        2. `candidates` tổ hợp độc lập, giữ cái `CoverageMemory` chấm ít gặp
           nhất. Đây là một câu nghiêng -- nó không cấm gì, chỉ đẩy phân bố ra
           khỏi vùng đã bão hoà, đúng lời `agent/coverage.py` viết ra
           ("controlled distribution, not maximum uniqueness").

        Rút hụt cả `exact_retries` lần thì VẪN TRẢ tổ hợp cuối và cộng
        `exact_collisions`: bỏ hẳn một tờ vì một phôi cạn tổ hợp là để cái
        phôi nghèo nhất quyết số trang của cả lô. Báo cáo đọc được con số ấy
        và người đọc biết phôi nào nên nghỉ."""
        best: Filling | None = None
        best_priority = None
        for _ in range(max(1, self.candidates)):
            got = self._one(rng)
            self._drawn += 1
            for _retry in range(max(0, self.exact_retries)):
                if got.fingerprint.fine not in self._used:
                    break
                got = self._one(rng)
                self._drawn += 1
            else:
                if got.fingerprint.fine in self._used:
                    self._exact_collisions += 1
            priority = self._memory.priority(got.fingerprint)
            if best_priority is None or priority < best_priority:
                best, best_priority = got, priority
        assert best is not None
        self._memory.observe(best.fingerprint)
        self._used.add(best.fingerprint.fine)
        return best

    # ------------------------------------------------------------------ báo cáo

    def metrics(self) -> dict:
        return {"template_id": self.template.template_id,
                "slots": len(self._slots),
                "repeats": list(self._repeats),
                "fillings_kept": len(self._used),
                "combinations_drawn": self._drawn,
                "exact_collisions": self._exact_collisions,
                "coverage_observed": self._memory.total_observed()}


def _wanted(key: str, slots) -> bool:
    """Khoá phẳng này có phải chỗ trống phôi xin không.

    So sau khi gom chỉ số: phôi viết `line_items[].name`, bảng phẳng mang
    `line_items[3].name`. Không gom thì mọi ô bảng rơi ra ngoài dấu vân và
    hai tờ khác nhau hoàn toàn ở bảng vẫn `fine`-trùng."""
    import re  # noqa: PLC0415

    return re.sub(r"\[\d+\]", "[]", key) in slots


def prepare(html: str, seed: int) -> tuple[str, dict, int, int]:
    """Chữa + điền mực thật cho một trang ĐÃ ĐIỀN GIÁ TRỊ.

    `(html, việc đã chữa, số dấu, số chữ ký)`.

    Thứ tự giống hệt `agent/compose_page.py::one()` và phải giống hệt: cổng
    đo trên HTML CUỐI CÙNG, không đo trên bản nháp.

    `repair()` chạy SAU khi điền chứ không phải trên phôi, vì `repair.grid()`
    đánh `data-row`/`data-col` cho từng ô bảng -- đánh trên phôi thì mọi dòng
    nhân bản ra mang cùng một số hàng, và `synthgen/kie_full.py` đọc chỗ ngồi
    từ hai thuộc tính ấy nên cả bảng thành một dòng lặp lại N lần. `rows_out`
    thì KHÔNG chạy: dòng bảng ở đây do khối `data-repeat` bung ra, không do
    một mảng `rows` model khai rời khỏi HTML, nên không có hai nguồn nào để
    hoà."""
    from synthgen.adorn import hands, seals  # noqa: PLC0415
    from synthgen.repair import repair  # noqa: PLC0415

    html, mended = repair(html)
    html, stamped = seals(html, seed=seed)
    html, signed = hands(html, seed=seed)
    if stamped:
        mended["dấu thật đã điền"] = stamped
    return html, mended, stamped, signed


__all__ = ["CANDIDATES", "EXACT_RETRIES", "Filler", "Filling", "prepare",
           "value_fingerprint"]
