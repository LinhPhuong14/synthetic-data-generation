# 250 câu hỏi để kiểm nhãn KIE, và bản thiết kế chữa chỗ hỏng

> **Đọc theo thứ tự này:** [Cập nhật `pilot10`](#cập-nhật-17-09-1513--datapilot10-đổi-bàn-cờ)
> (bàn cờ đã đổi) → [Phần IV](#phần-iv--chữa-từng-ca-23-ca-hỏng-của-50-câu-đầu)
> (chữa từng ca) → [Phần V](#phần-v--100-câu-nâng-cao-đợt-2-uad-câu-151250) (100 câu mới).
> Phần I–III là bản đo đợt đầu trên `data/test1`, giữ nguyên làm mốc so sánh.

> Đo trên `data/test1` (24 tài liệu, 11 bảng, 773 ô bảng, 2 156 thực thể), ngày
> 17-09-2026. Ký hiệu: **✅** nhãn trả lời được · **⚠️** trả lời được nhưng phải
> đoán/parse, hoặc nghĩa sai · **❌** nhãn không có thông tin để trả lời.
>
> Tổng: **58 ✅ · 46 ⚠️ · 46 ❌** trên 150 câu.

| phần | câu | ✅ | ⚠️ | ❌ |
| --- | ---: | ---: | ---: | ---: |
| 50 câu cơ bản (A–J) | 1–50 | 27 | 13 | 10 |
| 100 câu nâng cao (K–T) | 51–150 | 31 | 33 | 36 |

---

# Phần I · Bản thiết kế: chữa 5 chỗ hỏng

Năm chỗ dưới đây giải thích **92/150** câu không đạt. Xếp theo số câu chữa được.

## Chữa 1 — Nhãn âm: ba trạng thái thay vì hai (~27 câu)

Hôm nay nhãn chỉ biết nói "có gì". 192/773 ô bảng (24,8%) vắng mặt, và không gì
phân biệt **ô trống trên giấy** với **ô bị rớt khỏi nhãn**. Model không có cách
nào học câu trả lời "không có".

Mỗi chỗ đáng lẽ có giá trị mang một trong ba trạng thái:

```json
{"value": "Thiếu 5 túi", "state": "printed", "bbox": [...]}
{"value": null, "state": "blank",  "bbox": [ô <td> trống, engine đã có rect]}
{"value": null, "state": "absent", "bbox": null}
```

- `blank` — **ô có trên giấy, không có mực**. Hộp là rect của `<td>`, đọc từ
  cùng chỗ DOM đã cho mọi hộp khác. Không đo lại gì.
- `absent` — **tờ này không có trường ấy**. Chỉ sinh cho **từ vựng đóng**: tập
  `kind` engine phát ra, cộng `declared.plan.field_plan` của các phôi cùng loại
  chứng từ. Nhãn âm mở (mọi thứ không có trên đời) là vô hạn và vô dụng.

`declared/` đã có sẵn nguồn: `field_plan` liệt kê trường model **định** in.
Trừ đi thứ thực sự in ra thì được hai tập khác nhau về chất:

| trong `field_plan` | có thực thể | nghĩa |
| --- | --- | --- |
| có | có | `printed` |
| có | không | **lỗi sinh** — khai mà không in, phải báo |
| không | — | `absent` hợp lệ cho loại chứng từ này |

Chữa: 26–30, 27, 29, 81–90, 82, 86, 87, 88.

## Chữa 2 — Giá trị chuẩn hoá và dòng kiểm tra (~23 câu)

Schema khai `"type": "number"` nhưng value là `"2.500.000"`. Mọi câu số học
thành câu parse chuỗi, và không có gì để chấm đúng/sai.

```json
{"value": "2.500.000", "value_norm": 2500000, "unit": "VND",
 "format": "vi_thousand_dot"}
{"value": "15/06/2024", "value_norm": "2024-06-15", "format": "dd/mm/yyyy"}
{"value": "10%", "value_norm": 0.10, "format": "percent"}
```

Chuỗi in giữ nguyên — OCR phải học đúng cái in ra. `value_norm` là bản để chấm.

Và dòng tổng khai **quan hệ**, không chỉ giá trị:

```json
{"kind": "grand_total",
 "checks": [{"op": "sum", "column": "so_tien", "over_rows": [1, 11],
             "declared": 352000000, "computed": 352000000, "ok": true}]}
```

Có nó thì model học **kiểm tra** chứ không chỉ đọc, và câu "tổng có khớp không"
mới có đáp án. Bộ sinh biết trước cả hai vế — nó vừa in ra chúng.

Chữa: 16, 18–24, 51–53, 55, 56, 58–70, 80.

## Chữa 3 — Danh tính cột lấy từ giấy, không từ rulebase (~6 câu, và mọi câu bảng)

`BY_KIND` đang gánh hai vai và chỉ đúng một. Tách:

```json
{"key": "so_luong__theo_so",          // slug của column_path, nối bằng __
 "path": ["Số lượng", "Theo sổ"],      // nghĩa, lấy từ giấy
 "role": "menu.qty",                   // vai, do engine khai — GIỮ
 "index": 5,
 "description": "Cột 'Theo sổ' trong nhóm 'Số lượng'."}
```

Hai cột trùng tiêu đề (7/11 tài liệu) thì thêm chỉ số: `so_tien__c4`.
`COLUMNS[...].describe` thôi làm nguồn câu tả — nó đang tả `amount` là "lượng
nhân đơn giá" trong khi giấy in "Thực tế".

Chữa: bẫy của 11–15, 74, 91, 97.

## Chữa 4 — Khối chữ ký là object, list có thứ tự đọc (~6 câu)

Hôm nay `signer_name` là list phẳng xếp **phải→trái** (`x=749, 455, 104`), và
chức danh nằm ở list khác. Câu "người ký thứ hai" vô nghĩa.

```json
"signatures": [
  {"index": 1, "title": "NGƯỜI ĐỀ NGHỊ", "role_note": "Chuyên viên kinh doanh",
   "name": "Nguyễn Thị Hồng Nhung", "signed": true,
   "title_bbox": [...], "name_bbox": [...], "block_bbox": [...]}]
```

Thứ tự là **thứ tự đọc** (trên→dưới, rồi trái→phải), khai rõ trong
`order_basis`. `declared.plan.signers` đã có thứ tự đúng để đối chiếu.
Cặp `sign.title ↔ sign.name` đã vào HEAD (`80f69a6e`) nhưng chưa có bộ nào chạy
với nó — `data/test1` sinh lúc 10:33, commit lúc 13:08.

Chữa: 8, 44, 101, 111, 112.

## Chữa 5 — Bảng trải trang: thiếu DỮ LIỆU, không thiếu nhãn (~5 câu)

0/11 bảng tràn sang trang sau, dù 8/24 tài liệu có 2 trang. Nhánh này chưa từng
được học. Ép sinh bảng đủ dài, rồi nhãn khai thêm:

```json
{"table_id": "t1", "page": 2, "continues_from_page": 1,
 "row_index_global": 14, "row_index_in_page": 2}
```

`synthgen/paginate.py` đã cắt bằng phép đo và biết chỗ cắt — chỉ là chưa khai ra.

Chữa: 49, 50, 121, 126, 128.

## Phụ — hai chỗ nhỏ

- **Thứ tự đọc toàn trang** (`reading_order` trên entity): mở ra mọi câu
  "bên phải cái gì", "ngay dưới dòng nào" mà không phải suy từ toạ độ. Chữa
  40, 57, 102, 103, 106, 108.
- **`declared.plan` vào nhãn**: `purpose`, `issuer`, `signers` là ngữ cảnh model
  đã viết ra rồi vứt đi. Chữa 138, 139, 141, 143.

---

# Phần II · 50 câu cơ bản (A–J)

## A · Trích trường có nhãn in — 5 ✅
1. ✅ Số biên bản là gì?
2. ✅ Ngày kiểm kê?
3. ✅ Lý do kiểm kê ghi gì?
4. ✅ Giá trị bên cạnh nhãn "Khu vực"?
5. ✅ Nhãn của giá trị "15/06/2024" là gì? (hỏi ngược)

## B · Trường không có nhãn in — 3 ✅ · 1 ⚠️ · 1 ❌
6. ✅ Tiêu đề tài liệu?
7. ✅ Cơ quan ban hành?
8. ❌ Căn cứ pháp lý **thứ hai** là gì? — list không có thứ tự đọc
9. ✅ Chữ chìm trên trang ghi gì?
10. ⚠️ Có mấy điều khoản? — đếm được, không có nhãn đối chiếu

## C · Tra cứu theo hàng — 5 ✅
11. ✅ Tên hàng có số lượng 144?
12. ✅ Số lượng của "Xi măng PCB40"?
13. ✅ Mã hàng ở dòng 3?
14. ✅ Dòng nào ghi "Thiếu 5 túi"?
15. ✅ Đơn giá của hàng mã TH-001?

> Đo: 11 bảng đẻ ra **2 872 câu dạng này có đáp án duy nhất** (~261 câu/bảng),
> cộng 121 câu nhiều đáp án — dùng cho "liệt kê mọi dòng có…".
> Bẫy: hỏi bằng tên cột trong `kie_schemas` thì `qty` mang 4 nghĩa.

## D · Số học — 1 ✅ · 4 ⚠️
16. ⚠️ Tổng số tiền? — chỉ 3/11 bảng có dòng `grand_total`
17. ✅ Bảng có bao nhiêu dòng?
18. ⚠️ Tổng số lượng tất cả các hàng?
19. ⚠️ Dòng nào thành tiền lớn nhất?
20. ⚠️ Chênh lệch Theo sổ vs Thực tế dòng 2?

## E · So sánh & lọc — 1 ✅ · 4 ⚠️
21. ⚠️ Những dòng nào số lượng > 100?
22. ⚠️ Hàng nào đắt nhất?
23. ⚠️ Thực tế có khớp theo sổ không?
24. ⚠️ Ba hàng đắt nhất, xếp giảm dần?
25. ✅ Dòng nào ghi chú khác "Đủ số"?

## F · Phủ định & tồn tại — 0 ✅
26. ❌ Tài liệu có mã số thuế không?
27. ❌ Ô Ghi chú dòng 5 có trống không?
28. ❌ Có hàng nào tên "Sắt hộp" không?
29. ❌ Trường nào trên tờ này để trống?
30. ❌ Có chữ ký giám đốc không?

## G · Cấu trúc bảng — 3 ✅ · 2 ⚠️
31. ✅ Bảng có mấy cột?
32. ✅ Kể tên các cột?
33. ✅ Cột "Theo sổ" thuộc nhóm nào?
34. ⚠️ Dòng TỔNG CỘNG ở đâu? — 3/11
35. ⚠️ Bảng có dòng nhóm nào? — "Số lượng" bị đếm hai lần

## H · Định vị — 4 ✅ · 1 ⚠️
36. ✅ Số biên bản nằm ở đâu?
37. ✅ Khoanh vùng bảng
38. ✅ Con dấu ở đâu?
39. ✅ Đọc chữ trong vùng [x1,y1,x2,y2]
40. ⚠️ Trường nào ngay bên phải "Số:"?

## I · Chữ ký — 2 ✅ · 1 ⚠️ · 2 ❌
41. ✅ Ai ký tên?
42. ❌ Ai ký với chức danh "Kế toán trưởng"?
43. ⚠️ Chức danh người ký bên phải?
44. ❌ Người ký **thứ hai** là ai?
45. ✅ Nơi và ngày ký?

## J · Tài liệu & đa trang — 3 ✅ · 2 ❌
46. ✅ Đây là loại chứng từ gì?
47. ✅ Mấy trang?
48. ✅ Trường X ở trang mấy?
49. ❌ Bảng tiếp sang trang sau ở dòng nào? — 0/11
50. ❌ Tổng trang cuối khớp các dòng trang trước?

---

# Phần III · 100 câu nâng cao (K–T)

## K · Đa bước — 2 ✅ · 8 ⚠️
51. ⚠️ Đơn giá của hàng có số lượng lớn nhất?
52. ⚠️ Ghi chú của dòng chênh lệch sổ/thực tế lớn nhất?
53. ⚠️ Tổng tiền các dòng có ghi chú chứa "Thiếu"?
54. ✅ Người ký duyệt của tờ có số hiệu X?
55. ⚠️ Hàng nào vừa thiếu số lượng vừa có trị giá > 10 triệu?
56. ⚠️ Cột nào có tổng lớn nhất?
57. ✅ Mã hàng của dòng ngay dưới "Sơn nước"?
58. ⚠️ Bao nhiêu dòng nằm giữa dòng nhóm và dòng tổng?
59. ⚠️ Đơn vị tính của hàng đắt nhất?
60. ⚠️ Ngày kiểm kê có sau ngày lập biên bản không?

## L · Số học & nhất quán — 0 ✅ · 1 ⚠️ · 9 ❌
61. ❌ Thành tiền dòng 3 có bằng số lượng × đơn giá?
62. ❌ Tổng cộng có bằng tổng các dòng?
63. ❌ Số tiền bằng chữ có khớp bằng số?
64. ❌ Thuế GTGT có bằng 10% doanh số?
65. ❌ Tổng các cột con có bằng cột tổng?
66. ❌ Số dòng thực có khớp "gồm 11 khoản" ghi trong văn bản?
67. ❌ Chênh lệch = Thực tế − Theo sổ, đúng không?
68. ❌ Có dòng nào bị tính sai không?
69. ❌ Tổng chân bảng khớp dòng "TỔNG CỘNG" trong văn bản?
70. ⚠️ Trị giá cả bảng, làm tròn đến triệu?

## M · Chuẩn hoá & định dạng — 1 ✅ · 4 ⚠️ · 5 ❌
71. ❌ Ngày kiểm kê ở dạng ISO?
72. ❌ Số tiền dạng số nguyên, không dấu chấm?
73. ❌ Đơn vị tiền tệ là gì?
74. ⚠️ "Theo sổ" tính bằng đơn vị nào? — cột "Đơn vị" không gắn với cột số nào
75. ❌ Tỷ lệ 10% dưới dạng thập phân?
76. ⚠️ Mã hàng có theo mẫu `XX-000` không?
77. ❌ Số hiệu văn bản gồm mấy phần?
78. ✅ Tên người viết hoa hay viết thường?
79. ⚠️ Số thẻ BHYT có đủ số ký tự không?
80. ⚠️ Giá trị nào trong bảng không phải số dù cột là số?

## N · Phủ định nâng cao & từ chối trả lời — 0 ✅ · 10 ❌
81. ❌ Tờ này có mã số thuế không? Nếu có thì bao nhiêu?
82. ❌ Ô "Ghi chú" dòng 7 trống — đúng hay sai?
83. ❌ Có cột "Thuế suất" trong bảng không?
84. ❌ Câu hỏi này không trả lời được từ tờ giấy — đúng không?
85. ❌ Tên khách hàng là gì? (tờ không có trường ấy)
86. ❌ Dòng 12 có tồn tại không?
87. ❌ Có chỗ ký nào bỏ trống không?
88. ❌ Trường nào trong mẫu chuẩn mà tờ này thiếu?
89. ❌ Con dấu có đè lên chữ ký không?
90. ❌ Có phụ lục đính kèm không?

## O · Cấu trúc bảng khó — 5 ✅ · 4 ⚠️ · 1 ❌
91. ✅ "Theo sổ" và "Thực tế" cùng thuộc nhóm nào?
92. ✅ Bảng có tiêu đề mấy tầng? — đo được 0/1/2 tầng
93. ⚠️ Ô nào bị gộp (colspan)? — markup có, nhãn không xuất
94. ✅ Dòng nào là nhóm, dòng nào là dữ liệu?
95. ✅ Cột nào là cột số thứ tự?
96. ⚠️ Bảng thứ hai trên trang nói về gì?
97. ❌ Có bao nhiêu bảng trên trang? — export gộp hết vào một `line_items`
98. ⚠️ Ô nào không thuộc cột nào? — 16 ô có `column_path` rỗng
99. ⚠️ Dòng tổng nằm trong `thead` hay `tfoot`?
100. ✅ Cột "Ghi chú" rộng bao nhiêu pixel?

## P · Grounding & không gian — 3 ✅ · 6 ⚠️ · 1 ❌
101. ⚠️ Vẽ hộp quanh toàn bộ khối chữ ký
102. ⚠️ Trường nào nằm cùng dòng với "Số:"?
103. ⚠️ Nội dung ở góc trên bên phải là gì?
104. ✅ Bảng chiếm bao nhiêu % chiều cao trang?
105. ⚠️ Chữ nào nằm trong vùng con dấu?
106. ❌ Thứ tự đọc của trang là gì?
107. ✅ Hộp của "Xi măng PCB40" ở toạ độ nào (lưới 0–1000)?
108. ⚠️ Hai trường nào gần nhau nhất?
109. ⚠️ Tiêu đề căn giữa hay căn trái?
110. ✅ Vùng nào là `Page-Header`?

## Q · Chữ ký, dấu, hình — 6 ✅ · 1 ⚠️ · 3 ❌
111. ⚠️ Ai ký ở vị trí bên trái?
112. ❌ Chức danh của người ký tên "Trần Văn Hải"?
113. ✅ Có mấy con dấu? — 5 vùng `Stamp` trên cả bộ
114. ❌ Dấu của đơn vị nào?
115. ❌ Có chữ viết tay hay chỉ tên đánh máy? — `ink` 100% `print`, không có mẫu
116. ✅ Hình/logo nằm ở đâu?
117. ✅ Chú thích của hình là gì?
118. ✅ Công thức trong tài liệu là gì?
119. ✅ Mục lục có mấy mục?
120. ✅ Trang của mục "Phụ lục 1" trong mục lục?

## R · Đa trang & liên tài liệu — 3 ✅ · 3 ⚠️ · 4 ❌
121. ❌ Bảng tiếp tục ở trang 2 từ dòng nào?
122. ⚠️ Tiêu đề có lặp lại ở trang 2 không?
123. ✅ Chân trang ghi số trang mấy?
124. ✅ Trường X xuất hiện ở mấy trang?
125. ❌ Hai tờ này có cùng số hiệu không?
126. ❌ Tổng ở trang 2 có gồm cả dòng trang 1?
127. ✅ Trang nào có bảng?
128. ⚠️ Nội dung trang 2 nối tiếp đoạn nào ở trang 1?
129. ❌ Tài liệu này thuộc bộ hồ sơ nào?
130. ⚠️ Số trang in trên giấy có khớp số trang thật?

## S · Đọc hiểu văn bản — 5 ✅ · 5 ⚠️
131. ✅ Điều 3 quy định gì?
132. ✅ Có bao nhiêu điều khoản?
133. ✅ Căn cứ pháp lý nào được viện dẫn?
134. ⚠️ Điều khoản nào nói về thời hạn?
135. ⚠️ Ai chịu trách nhiệm theo điều 2?
136. ✅ Lý do lập biên bản?
137. ⚠️ Hiệu lực từ ngày nào?
138. ⚠️ Tóm tắt tờ giấy trong một câu? — `declared.plan.purpose` có sẵn, bị vứt
139. ⚠️ Tài liệu này ai gửi cho ai?
140. ✅ Ghi chú chân trang nói gì?

## T · Meta-schema & tự đánh giá — 6 ✅ · 1 ⚠️ · 3 ❌
141. ✅ Tờ này thuộc loại chứng từ gì?
142. ✅ Liệt kê mọi trường trích được, kèm hộp
143. ❌ Trường nào bạn không chắc? — không có nhãn độ tin cậy
144. ✅ Trường nào lấy từ nhãn in, trường nào suy ra? — `source`, `description_source`
145. ✅ Xuất toàn bộ theo JSON Schema đính kèm
146. ⚠️ Có trường nào trùng tên không? — hậu tố `_2`
147. ✅ Độ phủ nhãn của trang này? — `kie.coverage`
148. ✅ Chữ nào trên trang không thuộc trường nào? — 38% ngoài KIE
149. ❌ Nếu chỗ này bị mờ, còn đọc được không?
150. ❌ Câu hỏi nào về tờ này là không trả lời được?

---

## Điều đáng chú ý nhất

Hai khối hỏng nặng nhất — **L (số học, 9/10 ❌)** và **N (phủ định, 10/10 ❌)**
— chiếm 19 trên 36 câu hỏng của phần nâng cao, và **cả hai chữa bằng đúng hai
thay đổi nhãn**: ba trạng thái (Chữa 1) và `value_norm` + `checks` (Chữa 2).

Cấu trúc quan hệ thì không thiếu chỗ nào: 2 872 câu tra cứu theo hàng đã mine
được mà chưa sửa một dòng code.

---

# Cập nhật 17-09 15:13 — `data/pilot10` đổi bàn cờ

Bộ `pilot10` (15 tài liệu) chạy với một đường nhãn chưa có lúc đo `test1`:
**`source: "declared"`** — model tự khai `data-path` trên từng thẻ, KIE lấy
nguyên, không suy gì.

| | `test1` (10:33) | `pilot10` (15:13) |
| --- | ---: | ---: |
| độ phủ thực thể | 0,623 | **0,913** |
| nguồn cặp | label 235 · table 727 · implied 237 | declared 401 · table 449 · implied 362 · label 98 · **family 8** · pair 4 |

Đường `declared` mang lại đúng thứ buổi bàn này đang tìm — **ghép theo nghĩa,
không theo suy luận**:

```
items[0].print_qty        = "5.000"
items[0].distribution_qty = "4.800"
items[0].ad_revenue       = "925.000.000"
```

Chỉ số hàng nằm trong đường dẫn, tên cột là nghĩa do chính model đặt. Đo trên
`copyright_reconciliation_statement`: 56/56 ô bảng có `data-path`, và **56/56
ô ấy cũng có cặp `table` kèm tiêu đề in trên giấy** ("Doanh thu quảng cáo
(đồng)"). Hai cách gọi tên cùng tồn tại — máy và giấy.

**Nhưng nó đẻ ra hai lỗi mới, cả hai đều đo được:**

1. **Một chỗ mực thành hai trường.** 57/77 thực thể mang từ 2 cặp trở lên
   (`items_0_ad_revenue` và `doanh_thu_quang_cao_dong_r1`, cùng giá trị, cùng
   hộp). Đúng cái `pipeline/kie.py` đã cấm ở đường khác.
2. **`kie.schema` bị phẳng hoá bởi bảng.** Trung bình 37,2 thuộc tính một
   trang, **cao nhất 113** — `items_0_stt … items_6_note`. Đây chính là "hai
   trăm thuộc tính ô bảng" mà docstring của `pipeline/kie.py` nói không được
   đưa vào schema.

**Chữa (Chữa 3, viết lại):** hợp nhất hai cách gọi tên thành **một** trường,
và bảng thành mảng chứ không phẳng:

```json
"items": {"type": "array", "items": {"type": "object", "properties": {
  "print_qty": {"type": "number",
                "path": "items[].print_qty",
                "printed_header": ["Số in (bản)"],
                "role": "menu.qty"}}}}
```

`path` là danh tính máy · `printed_header` là nghĩa trên giấy · `role` là vai
engine khai. Ba thứ khác nhau, ba ô khác nhau, một trường.

---

# Phần IV · Chữa từng ca: 23 ca hỏng của 50 câu đầu

| # | câu | vì sao hỏng | chữa bằng | sau `pilot10` |
| ---: | --- | --- | --- | --- |
| 8 ❌ | "Căn cứ pháp lý **thứ hai**?" | list không có thứ tự đọc | F4 `order_basis` | **đã chữa một phần** — model khai được chỉ số mảng (`items[0]`), áp cho `legal_basis[]` là xong |
| 10 ⚠️ | "Có mấy điều khoản?" | đếm được, không có nhãn đối chiếu | F2 `checks` | chưa |
| 16 ⚠️ | "Tổng số tiền?" | 3/11 bảng có `grand_total` | F2 `row.kind` + `checks` | chưa |
| 18 ⚠️ | "Tổng số lượng các hàng?" | phải tự cộng chuỗi | F2 `value_norm` | chưa |
| 19 ⚠️ | "Dòng nào thành tiền lớn nhất?" | `"2.500.000"` là chuỗi | F2 `value_norm` | chưa |
| 20 ⚠️ | "Chênh lệch sổ/thực tế dòng 2?" | như trên | F2 `value_norm` | chưa |
| 21 ⚠️ | "Dòng nào số lượng > 100?" | như trên | F2 `value_norm` | chưa |
| 22 ⚠️ | "Hàng nào đắt nhất?" | như trên | F2 `value_norm` | chưa |
| 23 ⚠️ | "Thực tế khớp theo sổ không?" | không có quan hệ giữa hai cột | F2 `checks` | chưa |
| 24 ⚠️ | "Ba hàng đắt nhất?" | như 19 | F2 `value_norm` | chưa |
| 26 ❌ | "Có mã số thuế không?" | không có nhãn âm | **F1 `state: absent`** | chưa |
| 27 ❌ | "Ô Ghi chú dòng 5 trống?" | 24,8% ô vắng, không phân biệt trống/rớt | **F1 `state: blank` + hộp `<td>`** | chưa |
| 28 ❌ | "Có hàng tên 'Sắt hộp' không?" | không có nhãn dương cho câu "không" | F1 | chưa |
| 29 ❌ | "Trường nào để trống?" | như trên | F1 | chưa |
| 30 ❌ | "Có chữ ký giám đốc không?" | như trên | F1 + F4 | chưa |
| 34 ⚠️ | "Dòng TỔNG CỘNG ở đâu?" | ô trải cột nhận tên cột đầu | F3 + `row.kind` | **đã chữa** — `80f69a6e`; cần đo lại trên `pilot10` |
| 35 ⚠️ | "Bảng có dòng nhóm nào?" | tiêu đề tầng 1 bị đếm thành `group` | F3 `tier` vs `row.kind` | chưa |
| 40 ⚠️ | "Trường nào bên phải 'Số:'?" | không có nhãn quan hệ không gian | F6 `reading_order` | chưa |
| 42 ❌ | "Ai ký chức danh 'Kế toán trưởng'?" | `sign.title ↔ sign.name` chưa ghép | F4 | **đã chữa** — `family` xuất hiện 8 cặp ở `pilot10` |
| 43 ⚠️ | "Chức danh người ký bên phải?" | ghép có rồi, thiếu vị trí | F4 + F6 | một phần |
| 44 ❌ | "Người ký **thứ hai**?" | list xếp phải→trái | F4 `order_basis` | chưa |
| 49 ❌ | "Bảng tiếp trang sau từ dòng nào?" | **0/11 bảng trải trang** | F5 — thiếu **dữ liệu**, không thiếu nhãn | chưa |
| 50 ❌ | "Tổng trang cuối gồm dòng trang trước?" | như trên | F5 + F2 | chưa |

**Đọc bảng này theo cột cuối:** 3/23 ca đã tự chữa trong hai ngày, và **12/23
ca còn lại chỉ cần hai thay đổi** — F1 (ba trạng thái) và F2 (`value_norm` +
`checks`). Không ca nào đòi viết lại phép ghép.

---

# Phần V · 100 câu nâng cao đợt 2 (U–AD), câu 151–250

> Mười trục chưa động tới ở K–T. Đo trên `pilot10` khi có dữ liệu, trên `test1`
> khi `pilot10` chưa xuất bản tương ứng.

## U · Truy vấn nhiều điều kiện — 4 ✅ · 5 ⚠️ · 1 ❌
151. ⚠️ Hàng nào vừa có số in > 3.000 vừa có tỷ lệ chia < 12%?
152. ⚠️ Liệt kê mọi dòng có ghi chú rỗng **và** số lượng bằng 0
153. ✅ Dòng nào có mã bắt đầu bằng "TH"?
154. ⚠️ Hai dòng có trị giá gần nhau nhất?
155. ✅ Dòng đầu tiên có ghi chú khác rỗng?
156. ⚠️ Cột nào có nhiều ô rỗng nhất?
157. ✅ Những dòng nào KHÔNG thuộc nhóm nào?
158. ⚠️ Xếp hạng các dòng theo tỷ lệ chia, giảm dần
159. ✅ Dòng cuối cùng trước dòng tổng là dòng nào?
160. ❌ Có dòng nào trùng hoàn toàn với dòng khác không?

## V · Tiền tệ, đơn vị & tỉ lệ — 1 ✅ · 3 ⚠️ · 6 ❌
161. ❌ Đơn vị tiền của cột "Thành tiền" là gì?
162. ❌ Bảng ghi "Đơn vị tính: triệu đồng" — số 925 nghĩa là bao nhiêu?
163. ❌ Cột "Số lượng" đo bằng đơn vị nào? (gắn cột `unit` với cột số)
164. ⚠️ Tỷ lệ 15% áp lên cơ sở nào?
165. ❌ Đổi toàn bộ cột tiền sang đơn vị nghìn đồng
166. ✅ Ký hiệu tiền tệ nào xuất hiện trên tờ?
167. ❌ Giá trị nào là số âm?
168. ⚠️ Số nào ghi theo chuẩn Việt (dấu chấm) và số nào theo chuẩn Anh?
169. ⚠️ "0" trong ô này là số không hay là ô bỏ trống ghi 0?
170. ❌ Tổng tiền quy đổi ra USD theo tỷ giá in trên tờ?

## W · Thời gian & kỳ hạn — 2 ✅ · 3 ⚠️ · 5 ❌
171. ❌ Kỳ báo cáo kéo dài bao nhiêu ngày?
172. ⚠️ Ngày ký có nằm trong kỳ báo cáo không?
173. ✅ Có mấy mốc thời gian trên tờ?
174. ❌ Mốc thời gian nào sớm nhất?
175. ⚠️ "Quý II/2024" là từ ngày nào đến ngày nào?
176. ❌ Hiệu lực còn bao lâu tính từ ngày ký?
177. ✅ Ngày nào viết dạng chữ, ngày nào dạng số?
178. ❌ Hạn nộp có trước ngày lập không?
179. ⚠️ Thời hạn "30 ngày kể từ ngày ký" rơi vào ngày nào?
180. ❌ Có mốc thời gian nào mâu thuẫn nhau không?

## X · Đối chiếu `declared` ↔ chữ in — 6 ✅ · 3 ⚠️ · 1 ❌ ← **trục mới**
181. ✅ Trường `items[0].print_qty` ứng với cột in tên gì?
182. ✅ Cột "Doanh thu quảng cáo (đồng)" mang đường dẫn máy nào?
183. ✅ Có trường nào model khai mà không in ra giấy không?
184. ⚠️ Có chữ nào in ra mà model không khai đường dẫn?
185. ✅ Đường dẫn máy và tiêu đề in có mâu thuẫn nghĩa ở cột nào?
186. ✅ Trường nào có hai tên (declared + table) trỏ cùng một hộp?
187. ⚠️ Nếu hai tên đá nhau, tên nào đúng?
188. ✅ Cây dữ liệu `data` của tờ này có mấy nhánh?
189. ⚠️ `items[]` có bao nhiêu phần tử, khớp số dòng bảng không?
190. ❌ Model khai `items[7]` nhưng bảng chỉ có 7 dòng — sai ở đâu?

## Y · Mực: in, viết tay, chữ ký — 1 ✅ · 2 ⚠️ · 7 ❌
191. ⚠️ Giá trị này in máy hay viết tay?
192. ❌ Ô nào được điền tay sau khi in?
193. ❌ Chữ ký là nét bút hay tên đánh máy?
194. ✅ Trường nào mang `ink: print`?
195. ❌ Có ô nào để người dùng điền mà chưa điền?
196. ❌ Nét chữ của hai người ký có khác nhau không?
197. ❌ Con dấu đỏ hay đen?
198. ⚠️ Mực chữ ký có đè lên dòng kẻ không?
199. ❌ Chữ viết tay này đọc được không?
200. ❌ Tờ này là bản điền tay hay bản đánh máy toàn phần?

> `ink` có trong `word_annotations` nhưng `pilot10` **100% `print`** — trục
> viết tay không có một mẫu nào. Đây là thiếu **dữ liệu**, như F5.

## Z · Xuống cấp & độ đọc được — 0 ✅ · 2 ⚠️ · 8 ❌
201. ❌ Ảnh này đã qua những phép làm cũ nào?
202. ❌ Vùng nào bị mờ đến mức không đọc được?
203. ❌ Con dấu có che mất chữ nào không?
204. ⚠️ Chữ nào nằm ngoài mép giấy?
205. ❌ Trang có bị nghiêng bao nhiêu độ?
206. ❌ Hộp nào bị warp làm méo (không còn chữ nhật)?
207. ⚠️ Độ tương phản của vùng này đủ để OCR không?
208. ❌ Nếu bỏ lớp làm cũ, chữ này là gì?
209. ❌ Vết bẩn nào là nhiễu, vết nào là con dấu thật?
210. ❌ Ảnh bị nén JPEG mức nào?

> `manifest.jsonl` của `synthgen` không ghi chuỗi làm cũ. `pipeline/synthesis.json`
> có, nhưng chỉ đường A. Chữa: đưa `augmentation`, `toner`, `drum`, `warp` vào
> manifest của mọi lượt.

## AA · Suy luận nghiệp vụ — 3 ✅ · 4 ⚠️ · 3 ❌
211. ⚠️ Tờ này đã đủ chữ ký để có hiệu lực chưa?
212. ❌ Bên nào có nghĩa vụ thanh toán?
213. ✅ Ai là bên lập, ai là bên nhận?
214. ⚠️ Số tiền này do ai chi trả?
215. ✅ Tờ này thuộc quy trình nào (đề nghị / nghiệm thu / quyết toán)?
216. ⚠️ Có cần đóng dấu giáp lai không?
217. ❌ Theo mẫu chuẩn của loại này, tờ đang thiếu mục nào?
218. ✅ Chức danh cao nhất ký trên tờ là gì?
219. ⚠️ Khoản nào bất thường so với các khoản còn lại?
220. ❌ Tờ này có dấu hiệu sửa chữa không?

## AB · Đầu ra có ràng buộc — 5 ✅ · 4 ⚠️ · 1 ❌
221. ✅ Xuất JSON đúng theo schema đính kèm, không thêm khoá
222. ✅ Mỗi trường kèm hộp lưới 0–1000
223. ⚠️ Trường không đọc được thì trả `null`, không đoán
224. ✅ Chỉ trả về các trường thuộc nhóm "chữ ký"
225. ⚠️ Trả lời kèm độ tin cậy từng trường
226. ✅ Trả về bảng dưới dạng CSV
227. ⚠️ Trả lời bằng tiếng Anh nhưng giữ nguyên giá trị tiếng Việt
228. ✅ Trích đúng 5 trường quan trọng nhất, tự chọn
229. ⚠️ Nếu có hai đáp án, trả cả hai kèm hộp
230. ❌ Nêu lý do bạn chọn hộp này chứ không phải hộp kia

## AC · Bẫy & tiền đề sai — 0 ✅ · 2 ⚠️ · 8 ❌
231. ❌ "Số hoá đơn" của biên bản này là gì? (tờ không phải hoá đơn)
232. ❌ Cột "Thuế suất" có giá trị bao nhiêu? (không có cột ấy)
233. ❌ Dòng 20 ghi gì? (bảng có 11 dòng)
234. ⚠️ Tổng cộng là 352 triệu — đúng không? (gài số sai)
235. ❌ Ai ký ở ô thứ tư? (chỉ có ba ô)
236. ❌ Trang 3 nói gì? (tờ 2 trang)
237. ⚠️ "Theo sổ" và "Sổ sách" là cùng một cột phải không?
238. ❌ Giá trị ở ô giao giữa "Ghi chú" và dòng nhóm là gì?
239. ❌ Mã số thuế ghi ở góc dưới bên trái — đọc giúp
240. ❌ Con dấu ghi tên đơn vị nào? (tờ không có dấu)

## AD · So sánh nhiều tài liệu — 3 ✅ · 4 ⚠️ · 3 ❌
241. ✅ Hai tờ này có cùng loại chứng từ không?
242. ✅ Tờ nào có nhiều dòng bảng hơn?
243. ⚠️ Hai tờ có cùng đơn vị phát hành không?
244. ❌ Có hai tờ nào trùng số hiệu không?
245. ⚠️ Cùng phôi, hai tờ khác nhau ở những trường nào?
246. ✅ Trong bộ này, loại chứng từ nào nhiều nhất?
247. ⚠️ Trường nào xuất hiện ở mọi tờ cùng loại?
248. ❌ Tờ nào lệch khỏi mẫu chuẩn của loại nó?
249. ⚠️ Giá trị trường X có phân bố thế nào trên cả bộ?
250. ❌ Hai tờ này có phải cùng một bộ hồ sơ không?

---

## Tổng kết 250 câu

| phần | câu | ✅ | ⚠️ | ❌ |
| --- | ---: | ---: | ---: | ---: |
| A–J cơ bản | 1–50 | 27 | 13 | 10 |
| K–T nâng cao đợt 1 | 51–150 | 31 | 33 | 36 |
| U–AD nâng cao đợt 2 | 151–250 | 25 | 32 | 43 |
| **cộng** | **250** | **83** | **78** | **89** |

### Ba trục mới lộ ra ở đợt 2

1. **Đơn vị đo không gắn với số** (V, W — 11 ❌). Cột "Đơn vị" và cột "Số lượng"
   là hai cột rời; không nhãn nào nói cột nào đo cột nào. Thêm `measures:` trỏ
   từ cột đơn vị sang cột số là xong — thông tin đã nằm trong `data-path`.
2. **Lượt làm cũ không được ghi lại** (Z — 8 ❌). `synthgen` biết nó vừa bôi gì
   lên trang rồi vứt đi. Đây là thứ rẻ nhất trong cả tài liệu: chép một dict
   vào `manifest.jsonl`.
3. **Trục mực chưa có mẫu** (Y — 7 ❌). `ink` 100% `print` trên `pilot10`. Giống
   F5: thiếu dữ liệu, không thiếu nhãn.

### Điều không đổi sau 250 câu

`declared` đã chữa đúng cái nó hứa — ghép theo nghĩa, phủ 0,913. Nhưng **89 câu
❌ còn lại không có câu nào hỏng vì ghép sai**. Chúng hỏng vì nhãn **chỉ biết
nói "có gì", không biết nói "không có gì", "bằng bao nhiêu", "đo bằng gì", và
"đã bị bôi gì lên"**.
