"""Khối "Nơi nhận" là danh sách nơi gửi, không phải một ô ký.

Trước đây 140/439 phôi khai "NƠI NHẬN" trong `sign_sets`, nên nó ra một ô ký
có "(Ký, ghi rõ họ tên)" và một tên người viết tay -- đo trên
`data/26-09-hand-check`: `cv_dao_tao_boi_duong_00010` và
`ph_an_toan_lao_dong_00008`. Không cần trình duyệt.
"""

from __future__ import annotations

import random
import re

import yaml

from synthgen import archetypes as A
from synthgen import content as C
from synthgen import design as D
from synthgen import markup as M


def test_no_archetype_signs_under_recipients():
    for arch in D.ARCHETYPES:
        for signs in arch.sign_sets:
            assert all(c.strip().rstrip(':').upper() != 'NƠI NHẬN' for c in signs), arch.id


def test_the_gate_refuses_recipients_as_a_signer():
    spec = yaml.safe_load(open(A.ARCHETYPE_DIR / 'ban_giai_trinh.yaml', encoding='utf-8'))
    spec['sign_sets'] = [['NƠI NHẬN', 'GIÁM ĐỐC']]
    assert any('NƠI NHẬN' in p for p in A.problems(spec))
    spec['sign_sets'] = [['GIÁM ĐỐC']]
    spec['recipients'] = 1.5
    assert any('recipients' in p for p in A.problems(spec))


def test_recipients_lines_follow_the_decree_shape():
    design = next(d for d in (D.draw(random.Random(s), s) for s in range(400))
                  if d.recipients)
    lines = C.recipients_of(design)
    assert lines[-1].startswith('- Lưu: VT, ') and lines[-1].endswith('.')
    assert all(line.startswith('- ') and line.endswith(';') for line in lines[:-1])


def test_recipients_cell_carries_no_signature():
    seen = 0
    for seed in range(400):
        design = D.draw(random.Random(seed), seed)
        doc = C.build(design, random.Random(seed ^ 0x5A), 4)
        html = M.markup(doc, [(0, len(doc.rows))])
        cells = re.findall(r'<div class="scell rcpt".*?</div>', html, re.S)
        drawn = design.recipients and doc.signatures and design.has('signatures')
        assert bool(cells) == bool(drawn), seed
        for cell in cells:
            seen += 1
            assert 'sign.' not in cell
            assert 'data-kind="recipients.label"' in cell
    assert seen, 'không tờ nào trong 400 seed có khối nơi nhận'
