"""`synthgen/repair.py`: chữa HTML model viết trước khi ra cổng gác
(`synthgen/llm_page.py::problems`).

Đo trên `data/pilot16` (60 tờ, cổng cũ qua 12/60 -- 20%): 9 tờ trượt vì "thẻ
lồng" đều là một nhãn ngắn bọc `<strong>`/`<b>` đứng TRƯỚC phần chữ còn lại
của run, hoặc một sub-label song ngữ bọc `<span>` sau `<br>` -- hình `unnest()`
bản cũ (chỉ khớp `<span>`, và `repair()` bản cũ chạy `breaks()` TRƯỚC
`unnest()`) không với tới. 15 tờ khác trượt vì cùng một `data-path` in ra hai
giá trị khác nhau -- viết hoa khác, rút gọn khác, hoặc một nhãn bị bọc vào
chữ của MỘT trong hai lần in (mục 18 `page.md`).

File này khoá lại phép chữa cho cả hai bằng chính chuỗi HTML model đã viết
(trích nguyên văn từ `data/pilot16/rejected/*.html`), không phải ví dụ tự
bịa -- và xác nhận cổng vẫn từ chối bản CHƯA chữa, để không lặng lẽ nới cổng
trong lúc thêm phép chữa.
"""

from __future__ import annotations

from synthgen.llm_page import problems
from synthgen.repair import repair, unnest

# --------------------------------------------------- thẻ lồng (data/pilot16)


def test_a_label_wrapped_in_strong_before_the_rest_of_the_run_is_refused_raw():
    """Trước khi chữa, cổng phải từ chối -- y như pilot16 đã từ chối thật
    (idx 8, `form_sectioned`). Nếu test này đỏ thì cổng đã bị nới lỏng, không
    phải phép chữa đã tốt lên."""
    raw = ('<div class="sheet"><span data-kind="note"><strong>Bên giao '
           'thầu:</strong> Công ty CP Thiết bị Y khoa Minh Đức, đại diện '
           'bởi ông Lê Hoàng Phúc, Tổng Giám đốc, cùng đội ngũ kỹ thuật '
           'viên phụ trách lắp đặt và kiểm tra thiết bị.</span></div>')
    assert any("thẻ lồng" in line for line in problems(raw))


def test_repair_fixes_the_label_wrapped_in_strong_case():
    """Sau `repair()`: không còn "thẻ lồng", và chữ giữ nguyên -- đọc được cả
    nhãn lẫn phần còn lại của câu, chỉ mất mỗi nét đậm."""
    raw = ('<div class="sheet"><span data-kind="note"><strong>Bên giao '
           'thầu:</strong> Công ty CP Thiết bị Y khoa Minh Đức, đại diện '
           'bởi ông Lê Hoàng Phúc, Tổng Giám đốc, cùng đội ngũ kỹ thuật '
           'viên phụ trách lắp đặt và kiểm tra thiết bị.</span></div>')
    fixed, mended = repair(raw)
    found = problems(fixed)
    assert not any("thẻ lồng" in line for line in found), found
    assert "Bên giao thầu:" in fixed
    assert "Công ty CP Thiết bị Y khoa Minh Đức" in fixed
    assert mended.get("span trần bóc khỏi run") == 1


def test_repair_fixes_the_bilingual_colhdr_split_across_a_br():
    """idx 27, `tax_invoice_en`: `<br>` cộng `<span class="en">` lồng trong
    `colhdr`. Bản cũ chạy `breaks()` TRƯỚC `unnest()` nên bỏ qua (còn thẻ
    khác ngoài `<br>` khi `breaks()` nhìn vào); đổi chỗ thì `unnest()` bóc
    `<span class="en">` trước, để `breaks()` tách nốt `<br>` thành hai run
    liền kề, mỗi run một dòng."""
    raw = ('<div class="sheet"><table><tr>'
           '<th data-row="0" data-col="1" data-cell>'
           '<span data-kind="colhdr" data-path="col.name">Tên hàng hóa, '
           'dịch vụ<br><span class="en">Description of Goods/Services'
           '</span></span></th>'
           '</tr></table></div>')
    assert any("thẻ lồng" in line for line in problems(raw))
    fixed, mended = repair(raw)
    found = problems(fixed)
    assert not any("thẻ lồng" in line for line in found), found
    assert "Tên hàng hóa, dịch vụ" in fixed
    assert "Description of Goods/Services" in fixed


def test_a_note_with_no_nested_tag_is_left_alone():
    """Chiều nhận: một run KHÔNG có thẻ lồng thì `unnest()` không được đụng
    vào (đếm phải ra 0), và cổng vẫn qua sạch cả trước lẫn sau `repair()`."""
    clean = ('<div class="sheet"><span data-kind="note">Bên giao thầu: '
             'Công ty CP Thiết bị Y khoa Minh Đức</span></div>')
    assert unnest(clean) == (clean, 0)
    assert not any("thẻ lồng" in line for line in problems(clean))
    fixed, _mended = repair(clean)
    assert "Bên giao thầu: Công ty CP Thiết bị Y khoa Minh Đức" in fixed
    assert not any("thẻ lồng" in line for line in problems(fixed))


# ---------------------------------------- data-path đụng nhau (data/pilot16)


def test_two_different_values_under_one_path_is_refused_raw():
    """idx 0, `authorisation_letter`: viết hoa khác nhau cho cùng một tên
    công ty, dưới cùng một `data-path`. Phải bị từ chối trước khi chữa."""
    raw = ('<div class="sheet">'
           '<span data-kind="store.name" data-path="issuer.name">CÔNG TY '
           'CỔ PHẦN XÂY DỰNG MIỀN TRUNG</span>'
           '<span data-kind="store.name" data-path="issuer.name">Công ty '
           'Cổ phần Xây dựng Miền Trung</span>'
           '</div>')
    assert any("giá trị khác nhau" in line for line in problems(raw))


def test_repair_drops_the_clashing_path_but_keeps_both_runs():
    """`unclash()` bỏ `data-path` khỏi CẢ HAI run đụng nhau, giữ `data-kind`
    -- trang không còn tự mâu thuẫn, và không đoán bên nào "đúng" hơn bên
    nào (mất một lời khai `data-path`, không mất một run nào, không mất
    chữ)."""
    raw = ('<div class="sheet">'
           '<span data-kind="store.name" data-path="issuer.name">CÔNG TY '
           'CỔ PHẦN XÂY DỰNG MIỀN TRUNG</span>'
           '<span data-kind="store.name" data-path="issuer.name">Công ty '
           'Cổ phần Xây dựng Miền Trung</span>'
           '</div>')
    fixed, mended = repair(raw)
    found = problems(fixed)
    assert not any("giá trị khác nhau" in line for line in found), found
    assert mended.get("data-path đụng nhau đã bỏ") == 2
    assert "CÔNG TY CỔ PHẦN XÂY DỰNG MIỀN TRUNG" in fixed
    assert "Công ty Cổ phần Xây dựng Miền Trung" in fixed
    assert 'data-path="issuer.name"' not in fixed


def test_a_label_baked_into_only_one_occurrence_is_refused_then_repaired():
    """idx 36, `form_dense`: một trong hai lần in tự chèn `MST: ` ngay vào
    chữ của giá trị, lần kia in giá trị trần -- đúng lỗi mục 18 `page.md`
    cảnh báo (nhãn phải có run riêng, không được gộp vào chữ của giá trị)."""
    raw = ('<div class="sheet">'
           '<span data-kind="store.tax_code" data-path="issuer.tax_code">'
           'MST: 0313884521</span>'
           '<span data-kind="store.tax_code" data-path="issuer.tax_code">'
           '0313884521</span>'
           '</div>')
    assert any("giá trị khác nhau" in line for line in problems(raw))
    fixed, mended = repair(raw)
    assert not any("giá trị khác nhau" in line for line in problems(fixed))
    assert mended.get("data-path đụng nhau đã bỏ") == 2


def test_the_same_value_repeated_verbatim_is_never_touched():
    """Chiều nhận: đúng giá trị thật của idx 0, nhưng in ĐÚNG như mục 48
    `page.md` dặn -- cùng chữ cả hai lần. `unclash()` không được đụng vào
    một cặp không hề đụng nhau, và `data-path` phải còn nguyên trên cả hai
    run."""
    good = ('<div class="sheet">'
           '<span data-kind="store.name" data-path="issuer.name">CÔNG TY '
           'CỔ PHẦN XÂY DỰNG MIỀN TRUNG</span>'
           '<span data-kind="store.name" data-path="issuer.name">CÔNG TY '
           'CỔ PHẦN XÂY DỰNG MIỀN TRUNG</span>'
           '</div>')
    fixed, mended = repair(good)
    assert mended.get("data-path đụng nhau đã bỏ", 0) == 0
    assert fixed.count('data-path="issuer.name"') == 2
    assert not any("giá trị khác nhau" in line for line in problems(fixed))
