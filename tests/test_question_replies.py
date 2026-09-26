"""Câu trả lời của khối biểu mẫu đi THEO TỪNG CÂU HỎI, không từ rổ chung.

Đo trên `data/26-09-hand-check` (seed 771, 12 tài liệu): 6/13 ô viết tay
`survey.answer` là câu lạc đề -- "Mức lương đề nghị: xin bắt đầu từ đầu tháng
sau", "Ca làm việc: ☒ Ca đêm / Vui lòng cho biết thời gian và nơi thực hiện:
mong được đào tạo thêm nghiệp vụ". Nguồn của cả sáu là một: câu nào không tra
ra loại từ nhãn thì bốc rổ `answers` chung của cả chủ đề.

Không cần trình duyệt, chỉ cần `synthgen/content.py` nạp được.
"""

from __future__ import annotations

import random

from synthgen import content as C


def _items():
    for theme, data in C.QUESTION_THEMES.items():
        for item in data['items']:
            yield theme, item


def test_every_question_has_a_source_for_its_answer():
    """Mô-đun kêu lúc nạp; test này chỉ ghim để lỗi hiện tên câu hỏi."""
    assert C._check_replies(C.QUESTION_THEMES) == []


def test_free_blank_without_replies_is_refused():
    themes = {'x': {'items': ({'shape': 'blank', 'prompt': 'Mức lương đề nghị'},)}}
    assert C._check_replies(themes)


def test_inline_reply_must_match_blank_count():
    item = {'shape': 'inline_blank', 'prompt': 'Tôi ở bộ phận …, vị trí …',
            'replies': ('Kế toán',)}
    problems = C._check_replies({'x': {'items': (item,)}})
    assert any('1 ô' in p for p in problems)


def test_unknown_placeholder_is_refused():
    item = {'shape': 'blank', 'prompt': 'Lý do', 'replies': ('{nguoi}',)}
    assert any('chỗ giữ lạ' in p for p in C._check_replies({'x': {'items': (item,)}}))


def test_answers_come_from_the_question_itself():
    """Mọi câu trả lời `blank` có khai đáp án phải là một trong số đáp án ấy."""
    for theme, item in _items():
        replies = item.get('replies')
        if item['shape'] != 'blank' or not replies or any('{' in r for r in replies):
            continue
        for seed in range(20):
            got = C._filled(item, random.Random(seed), [])['answer']
            assert got in replies, (theme, item['prompt'], got)


def test_yesno_follow_only_with_replies_and_on_the_right_tick():
    for theme, item in _items():
        if item['shape'] != 'yesno':
            continue
        for seed in range(30):
            got = C._filled(item, random.Random(seed), [])
            if not item.get('replies'):
                assert not got['sub'] and not got['answer'], (theme, item['prompt'])
            elif got['answer']:
                assert got['ticked'] == C._follow_trigger(got['sub']), (theme, got)


def test_other_option_is_written_only_when_ticked():
    """"Nếu chọn "Khác", vui lòng ghi rõ" mà ô Khác không tích thì dòng ấy trống."""
    for theme, item in _items():
        if item['shape'] != 'options' or item.get('follow'):
            continue
        for seed in range(30):
            got = C._filled(item, random.Random(seed), [])
            if got['answer']:
                assert C.OTHER_OPTION in got['picked'], (theme, got)
            if not item.get('replies'):
                assert not got['sub'], (theme, item['prompt'])


def test_inline_slots_keep_their_line_together():
    """Vốn điều lệ và phần bằng chữ đến từ CÙNG một phương án."""
    item = next(i for _, i in _items() if i['prompt'].startswith('Vốn điều lệ là'))
    lines = [C._slots(r) for r in item['replies']]
    for seed in range(20):
        got = C._filled(item, random.Random(seed), [])['answers']
        assert any(got[:2] == line[:2] for line in lines), got


def test_birthdate_label_gives_an_adult():
    item = next(i for _, i in _items() if i['prompt'].startswith('Tôi tên là'))
    for seed in range(20):
        born = C._filled(item, random.Random(seed), [])['answers'][1]
        assert 1955 <= int(born[-4:]) <= 2005, born
