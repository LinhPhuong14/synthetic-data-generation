"""Mô tả KIE: một câu một giọng, và cùng một giọng ở mọi chỗ trong một file.

Không có gì ở đây vẽ ảnh hay gọi model -- `phrasing` là một bảng chữ, và
`kie_schema.build` nhận một dict bản ghi -- nên nó chạy trong cái CI không cần
phụ thuộc nào, cùng chỗ với `test_kie.py` và `test_record.py`.

Cái khiến file này tồn tại: bảng cách nói được thêm, `derive.py` áp nó cho
`kie.pairs`, và không gì bảo rằng `kie.schema` vẫn đọc câu gốc từ
`design.COLUMNS`. Nên `line_items.qty` y hệt nhau trên 20 099 trang trong khi
`kie.pairs` của cùng file đã có bốn cách nói, và chỉ người dùng mở hai file ra
so mới thấy. Mỗi test dưới đây là một nửa của chuyện ấy.
"""

from __future__ import annotations

from agent import augment_descriptions as A
from synthgen import kie_schema
from synthgen.phrasing import POOL, describe, pool

CANON = "Quantity of the item on this line."


def a_record(job_id, description, column="qty"):
    """Bản ghi nhỏ nhất `kie_schema.build` cần: một cặp một ô bảng."""
    return {
        "job_id": job_id,
        "entity_annotations": [],
        "kie": {"pairs": [{
            "source": "table", "column": column, "row": 1,
            "field": f"{column}_r1", "value_text": "12",
            "description": description, "page_number": 1,
        }]},
    }


# ------------------------------------------------------------------ phrasing


def test_the_same_seed_and_field_always_choose_the_same_wording():
    once = describe(CANON, "job-abc", "qty")
    again = describe(CANON, "job-abc", "qty")
    assert once == again
    assert once in pool()[CANON]


def test_choosing_again_on_an_already_rephrased_sentence_lands_on_the_same_one():
    """`derive.py` chạy được nhiều lần, và lần hai nó đọc cái lần một ghi ra.

    Không có bảng ngược thì một cách nói đã chọn không tra được về câu gốc,
    `describe` trả nguyên nó, và mọi cặp KIE bị ĐÓNG BĂNG ở lựa chọn cũ -- một
    lần mở rộng bảng chữ về sau không với tới chúng nữa."""
    once = describe(CANON, "job-abc", "qty")
    assert describe(once, "job-abc", "qty") == once


def test_the_committed_phrasings_file_widens_the_hand_written_core():
    """`rulebase/kie_phrasings.json` là chỗ bảng chữ lớn lên.

    `synthgen/phrasing.py` giữ phần viết tay; file kia là phần model viết, qua
    gác cổng của `agent/augment_descriptions.py`. Gộp chứ không thay, nên mất
    file thì vẫn còn bốn cách nói mỗi câu."""
    merged = pool()
    assert set(POOL) <= set(merged)
    assert len(merged[CANON]) > len(POOL[CANON])
    for canon, variants in POOL.items():
        assert set(variants) <= set(merged[canon])


def test_two_documents_do_not_get_the_same_wording_for_every_field():
    # Không đòi hai tài liệu BẤT KỲ phải khác nhau -- bốn cách nói thì hai tờ
    # trùng nhau là chuyện thường. Đòi rằng trên nhiều tài liệu thì cả bốn cách
    # nói đều được dùng, tức là hàm chọn thật sự tản ra.
    said = {describe(CANON, f"job-{n}", "qty") for n in range(400)}
    assert said == set(pool()[CANON])


def test_a_sentence_nobody_declared_comes_back_unchanged():
    lost = "A description no table in this repository has ever printed."
    assert describe(lost, "job-abc", "qty") == lost


# ---------------------------------------------------------------- kie_schema


def test_a_table_column_is_described_the_way_its_pairs_describe_it():
    # Đây là lỗi đã xảy ra: `build` đọc `COLUMNS["qty"]["describe"]` nên mô tả
    # cột quay về câu gốc dù cặp đã đổi giọng.
    voice = "Số lượng của mặt hàng ở dòng này."
    assert voice != CANON and voice in POOL[CANON]
    schema, _value = kie_schema.build(a_record("job-abc", voice))
    column = schema["properties"]["line_items"]["items"]["properties"]["qty"]
    assert column["description"] == voice


def test_two_documents_describe_their_line_items_array_differently():
    first = kie_schema.build(a_record("job-1", CANON))[0]
    rows = {kie_schema.build(a_record(f"job-{n}", CANON))[0]
            ["properties"]["line_items"]["description"] for n in range(40)}
    assert len(rows) > 1
    assert first["properties"]["line_items"]["description"] in rows


def test_a_column_with_no_description_falls_back_to_the_declared_one():
    # Mất đa dạng thì được, mất mô tả thì không.
    schema, _value = kie_schema.build(a_record("job-abc", ""))
    column = schema["properties"]["line_items"]["items"]["properties"]["qty"]
    assert column["description"].strip()


# ------------------------------------------------- cái gác cổng của augment


def test_the_gate_accepts_every_wording_a_person_wrote():
    """Luật nào loại một câu người đã viết là luật sai, không phải câu sai.

    Cùng bất biến `agent/corpus_rules.py` dựng cho corpus, áp cho bảng này:
    ngưỡng đo từ `POOL` thì phải nhận lại đúng `POOL`."""
    box = A.envelopes()
    for canon, variants in POOL.items():
        for variant in variants:
            lang = "vi" if A.vietnamese(variant) else "en"
            why = box[lang].fits(variant, canon)
            assert not why, f"{lang}: {variant!r} bị loại vì {why}"


def test_the_gate_throws_out_the_four_things_the_model_actually_does():
    box = A.envelopes()
    reply = "\n".join([
        "Dưới đây là các cách nói khác:",          # câu dẫn
        "Number of units recorded against this line.",   # tốt
        "- Quantity of the item on this line",     # trùng câu gốc, thiếu dấu chấm
        "Số lượng mặt hàng của dòng này.",          # sai thứ tiếng cho lượt `en`
        "Qty.",                                    # quá ngắn
    ])
    kept, thrown = A.sift(reply, CANON, "en", list(POOL[CANON]), box["en"])
    assert kept == ["Number of units recorded against this line."]
    assert [why for _line, why in thrown] == [
        "câu dẫn, không phải mô tả",
        "trùng câu đã có",
        "lượt tiếng Anh mà câu có dấu tiếng Việt",
        "1 từ, ngoài 2-21 đo được",
    ]


def test_every_canonical_sentence_in_the_repository_is_offered_to_the_model():
    """Bước sinh đọc câu gốc từ DỮ LIỆU, nên một loại chứng từ mới là xong.

    `POOL` là nửa synthgen; `rulebase/kie_field_glossary.json` là nửa pipeline
    chính. Một danh sách viết cứng trong `augment_descriptions.py` sẽ lặng lẽ
    bỏ sót nửa sau."""
    every = A.canonicals()
    assert set(POOL) <= set(every)
    assert any(source.startswith("slug:") for source in every.values())
    assert any(source.startswith("kind:") for source in every.values())
