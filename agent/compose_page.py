#!/usr/bin/env python3
"""Xin model soạn MỘT TỜ GIẤY: nội dung và HTML vẽ ra nó.

    python -m agent.compose_page --want 30 -o data/pilot-llm
    python -m agent.compose_page --want 30 -o data/pilot-llm --concurrency 4

Đây là bước sinh của phép thử "LLM tự vẽ bố cục". Nó KHÔNG vẽ ảnh: nó viết ra
những cặp `<stem>.html` + `<stem>.json` đã qua cổng, để `synthgen` vẽ chúng
bằng đúng Chromium và đúng phép đo đang dùng cho mọi trang khác.

## Vì sao tách làm hai bước

Hộp vẫn đến từ engine đã dàn chữ -- luật ấy không đổi khi model viết HTML. Thứ
đổi là ai hứa trang ấy ĐO ĐƯỢC, và câu trả lời là `synthgen/llm_page.py`: một
cổng chín luật, đo được cả hai chiều (60/60 trang engine viết qua, chín cách
trang hỏng đều bị bắt).

Nên model chạy ở đây, ra file, cổng gác, rồi mới tới lượt vẽ. Trang nào trượt
thì in lý do và bỏ -- không sửa hộ, vì một cái cổng biết vá là một cái cổng cho
qua thứ nó vừa vá.

## Bốn con số phép thử này phải trả lời

1. **Số học sai bao nhiêu.** Model tự viết `qty`, `unit_price`, `amount`; ở đây
   đếm số dòng mà `qty x unit_price != amount`. Đây là con số quyết định model
   có được cầm những con số hay không -- `synthgen/check.py` kiểm đúng phép ấy
   trên mọi tờ giấy của kho.
2. **Giây mỗi trang.** Đo được: một request 3 000 token mất 44 giây trên
   `Qwen3.8-27B-FP8`. Nhân 20 000 là 244 giờ đơn luồng, nên `--concurrency`
   có mặt từ đầu.
3. **Bao nhiêu trang qua cổng.**
4. **Đa dạng so với engine.** Đo ở bước sau, bằng `agent/distance.py` và phân
   bố nhãn bố cục.

## Cái này không tự sửa

Nội dung có thật hay không. Một hoá đơn của "Công ty TNHH Mặt Trời Mọc" là hợp
lệ và có thể chẳng tồn tại; cổng máy bắt cái đo được, người đọc diff bắt phần
còn lại. Cùng giới hạn `agent/corpus_rules.py` đã viết ra cho corpus.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import json
import os
import random
import re
import queue
import pathlib
import sys
import threading
import time
import unicodedata
from pathlib import Path

if __package__ in (None, ""):                   # `python compose_page.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.client import LLMError, from_env
from agent.promptbook import prompt
from agent import document_plan as DP
from agent import grammar as G
from agent import rate_match
from pipeline import failures
from synthgen import design as D
from synthgen.llm_page import (REGIONS, _rooted, declared_paths, kinds,
                               printed_kinds, problems)
from synthgen.adorn import hands, seals
from synthgen.repair import repair

PROMPT = "page"
GUIDELINE_DIR = Path(__file__).resolve().parent / "guideline"


def base_rules() -> str:
    """The base-rules layer that used to sit unused in `agent/guideline/`.

    `agent/guideline.py::write()` composes `SYSTEM_PROMPT.md` from
    `agent/policy.yaml` for a DIFFERENT track (the one that picks rulebase
    attribute IDs, `agent/planner.py`) and nobody ever sent it here -- this
    call went straight to `prompt("page")` and nothing else. The role,
    diversity/balancing philosophy, and known-failure-pattern sections of
    that file apply just as much to a model that writes the whole page
    itself, so it belongs in this track's system turn too.

    Read fresh on every call, same as `prompt()` above: a hand edit or a
    `tools/critic_review.py --guideline` regeneration takes effect on the
    next request, no restart. Missing file is not fatal -- an empty string
    just leaves `system_prompt()` to fall back to `page.md` alone."""
    path = GUIDELINE_DIR / "SYSTEM_PROMPT.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def system_prompt() -> str:
    """What actually goes in the system turn.

    Two files answer two different questions, so both go in, base rules
    first: `SYSTEM_PROMPT.md` says WHY the corpus should end up varied and
    realistic (role, diversity, balancing, failure patterns); `page.md` says
    HOW to draw one sheet (data tree, data-kind/data-path, tables, KIE,
    hard negatives, HTML mechanics). Concatenating roughly doubles the
    system-prompt token cost of every call -- worth watching against
    `budget()`/`patience()` if per-page latency regresses once this runs at
    scale."""
    base = base_rules()
    page = prompt(PROMPT)
    return f"{base}\n\n---\n\n{page}" if base else page


def schema() -> dict:
    """Hình dạng câu trả lời. vLLM ép theo nó bằng constrained decoding.

    ## `plan` KHÔNG còn là nơi model quyết cấu trúc -- đó là việc của engine

    Bản trước-trước đưa model một phôi đã khai sẵn: trường nào, ai ký, ghi
    chú gì. Model chỉ còn việc bày chúng ra. Kết quả là ba mươi tờ đi ra từ
    cùng một khuôn -- đúng thứ kiến trúc "N phôi" mà người dùng đã bác.

    Bản kế (trước Phase 5) để model tự quyết HOÀN TOÀN, và `plan` bắt nó
    nói quyết định ấy ra trước khi viết HTML. Đúng hướng ở chỗ model không
    còn điền vào khuôn cố định -- nhưng sai ở chỗ "quyết định" đó không ai
    kiểm, nên không khác gì model tự tạo ra plan RỒI TỰ CHẤM cho chính nó.

    Phase 5 (`docs/ke-hoach-refactor-engine.md`, điểm 3 review): cấu trúc
    -- có bảng hay không, mấy chữ ký, family nào -- giờ do
    `agent/grammar.py` + `agent/document_plan.py` RÚT TRƯỚC, đưa vào brief
    qua `describe_plan()`. `plan` trong JSON trả về đây vẫn giữ (protocol
    ổn định, `reasoning` vẫn hữu ích để gỡ lỗi), nhưng đổi vai trò thành
    **tóm tắt việc model đã làm**, không phải nguồn quyết cấu trúc --
    `agent/compose_page.py::plan_conformance_problems()` so HTML với
    `DocumentPlan` của ENGINE, không so với `plan` model tự khai ở đây.

    `field_plan` vẫn buộc model ÁNH XẠ trường nó viết sang `data-kind` có
    thật trong từ vựng đóng -- đây là chỗ nó hỏng nhiều nhất khi còn được
    hỏi (sáu tờ trượt vì `patient.name`, `project.code`, `admission.date`:
    tên model tự đặt cho trường mà nó chưa bao giờ phải đối chiếu với danh
    sách), và việc đó không đổi dù cấu trúc trang không còn do model quyết.
    """
    return {
        "type": "object",
        "properties": {
            "plan": {
                "type": "object",
                "properties": {
                    "doc_kind": {"type": "string"},
                    # TÊN FILE, do model tự đặt, bằng tiếng Anh ASCII.
                    #
                    # Trước đây tên thư mục chuyển ngữ từ `doc_kind` tiếng
                    # Việt, và mỗi bước chuyển ngữ là một chỗ hỏng: `đ` bị
                    # xoá ("hoạt động" -> `hoat_ong`), dấu gạch chéo cắt
                    # đường dẫn làm đôi, và khi lời dặn bằng tiếng Anh thì
                    # model trả về lẫn lộn -- khi thì câu tiếng Việt, khi thì
                    # một slug nó tự bịa, khi thì bảy mươi ký tự có ngoặc.
                    #
                    # `pattern` khiến bộ giải mã có ràng buộc KHÔNG THỂ sinh
                    # ra thứ khác. Tên file thôi là thứ phải đoán.
                    "doc_slug": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]{2,47}$",
                        # TIẾNG ANH. `pattern` ép được hình dạng nhưng không ép
                        # được ngôn ngữ, và pilot9 cho thấy chênh lệch: model
                        # chuyển ngữ tiếng Việt không dấu rồi nuốt chữ --
                        # `phiexacnhansohuyentranduy`,
                        # `biau_phan_loai_quan_ly_chung_cu`,
                        # `ho_so_hanh_hang`. Tên file thành thứ không đọc
                        # được, và hai tài liệu khác nhau dễ đụng tên.
                        #
                        # Tiếng Anh thì không có bước chuyển ngữ nào để hỏng.
                        # Nội dung TỜ GIẤY vẫn tiếng Việt -- `doc_kind` giữ
                        # tên tiếng Việt, cái này chỉ là tên thư mục.
                        "description": "ENGLISH snake_case document type, "
                                       "e.g. vat_declaration, tuition_notice, "
                                       "warehouse_issue_note. Never Vietnamese.",
                    },
                    "doc_title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "issuer": {"type": "string"},
                    "signers": {"type": "array", "items": {"type": "string"}},
                    "field_plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                # ENUM, không phải `string`. Đây là khác biệt
                                # lớn nhất giữa xin và ép.
                                #
                                # Lời dặn "đừng tự đặt tên mới" là một lời
                                # xin, và pilot5 cho thấy nó không đủ: model
                                # viết `seal.round` vì prompt bảo thế, viết
                                # `patient.name` vì nó hợp lý. Cả hai đều đi
                                # qua `{"type": "string"}` không vướng gì, rồi
                                # chết ở cổng sau khi đã đốt 300 giây.
                                #
                                # `enum` thì bộ giải mã có ràng buộc của vLLM
                                # KHÔNG THỂ sinh ra một tên ngoài danh sách --
                                # ngữ pháp không cho. Không còn là chuyện model
                                # có nhớ danh sách hay không.
                                "kind": {"type": "string",
                                         "enum": sorted(kinds())},
                            },
                            "required": ["label", "kind"],
                        },
                    },
                    "table_columns": {"type": "array",
                                      "items": {"type": "string"}},
                    # MỘT MỤC CHO MỖI TỜ ĐƯỢC XIN.
                    #
                    # Đo trên pilot13: model viết 1 951 token cho mỗi tờ được
                    # xin -- đúng MỘT NỬA mức 3 900 lời dặn yêu cầu -- và
                    # 14/16 tài liệu ra ít tờ hơn xin. Càng xin nhiều càng
                    # hụt: xin hai tờ thì gần đủ, xin tám tờ thì được ba.
                    #
                    # Lời dặn đã nói "nhân lượng chữ theo số tờ" và model
                    # không nghe. Thứ từng ép được nó nghe là RÀNG BUỘC CẤU
                    # TRÚC, không phải câu chữ: `field_plan` bắt nó mở danh
                    # sách kind ra đối chiếu, `enum` chặn nó bịa tên.
                    #
                    # `sheet_plan` bắt nó nghĩ RIÊNG cho từng tờ trước khi
                    # viết. Một mảng đúng tám mục cho tám tờ là tám lần nó
                    # phải trả lời "tờ này in cái gì" -- khó bỏ trống hơn
                    # nhiều so với một câu dặn chung.
                    "sheet_plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet": {"type": "integer"},
                                "sections": {"type": "array",
                                             "items": {"type": "string"}},
                                "rows_here": {"type": "integer"},
                            },
                            "required": ["sheet", "sections"],
                        },
                    },
                    "layout_idea": {"type": "string"},
                    # TƯ DUY, viết ra thành lời.
                    #
                    # `layout_idea` nói model ĐỊNH làm gì. `reasoning` nói VÌ
                    # SAO -- và đó mới là thứ đọc được khi một tờ hỏng. Một tờ
                    # trượt cổng hiện chỉ để lại HTML và câu báo lỗi: ta thấy
                    # nó sai ở đâu, không thấy nó nghĩ gì mà ra sai.
                    #
                    # Ba câu hỏi, vì ba chỗ hay hỏng nhất đo được: chọn loại
                    # chứng từ (model bịa ra loại không có thật), ánh xạ kind
                    # (bịa tên kind), và bày trang (dồn mọi thứ vào `Text`).
                    "reasoning": {
                        "type": "object",
                        "properties": {
                            "why_this_document": {"type": "string"},
                            "why_this_layout": {"type": "string"},
                            "hardest_choice": {"type": "string"},
                        },
                        "required": ["why_this_document", "why_this_layout",
                                     "hardest_choice"],
                    },
                },
                "required": ["doc_kind", "doc_slug", "doc_title", "purpose",
                             "issuer", "signers", "field_plan", "layout_idea",
                             "reasoning", "sheet_plan"],
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "unit": {"type": "string"},
                        "qty": {"type": "integer"},
                        "unit_price": {"type": "integer"},
                        "amount": {"type": "integer"},
                    },
                    "required": ["name", "qty", "unit_price", "amount"],
                },
            },
            # CÂY DỮ LIỆU, viết TRƯỚC HTML.
            #
            # Đây là chỗ đảo kiến trúc. Bản trước: model viết HTML, rồi pipeline
            # SUY ra cặp nhãn-giá trị từ toạ độ -- và mọi lỗi KIE đo được hôm
            # nay nằm đúng ở phép suy ấy (`stt_r9` nhận "TỔNG CỘNG" vì ô trải
            # bốn cột bắt đầu ở cột STT; "Số: 12/BB-HĐSP" nhận ngày tháng ở góc
            # phải vì nó là run kế tiếp trong cây DOM). Đo được: 30% run mang
            # vai key không có tín hiệu cấu trúc nào tách chúng khỏi một dòng
            # đã trọn nghĩa -- tức phép suy KHÔNG THỂ đúng hết.
            #
            # Bộ `pair_prompt100` của người dùng làm ngược lại: `data/*.json`
            # là cây dữ liệu viết trước, HTML là khuôn mang điểm ràng buộc
            # `value-path-value="merchant.tax_id"` -- 96 điểm trên một tờ biên
            # lai. KIE không phải suy gì cả: đường dẫn nằm sẵn trên thẻ.
            #
            # Ta lấy đúng ý ấy, bớt một bước: model viết CẢ giá trị lẫn đường
            # dẫn vào cùng một span (`data-path="merchant.tax_id"`), nên không
            # cần bước bơm dữ liệu vào khuôn. Trang vẽ ra ngay, và KIE đọc
            # thẳng `data-path`.
            #
            # Không ép hình dạng cây: mỗi loại chứng từ có cây riêng, và ép nó
            # là quay lại lối phôi cố định. Chỉ ép rằng nó PHẢI CÓ.
            "data": {"type": "object"},
            "html": {"type": "string"},
        },
        "required": ["plan", "data", "rows", "html"],
    }


# MƯỜI HAI LĨNH VỰC, không phải chín mươi bảy phôi. Đây là chỗ duy nhất còn
# viết cứng, và nó viết cứng ở mức "giấy tờ Việt Nam có những ngành nào" chứ
# không ở mức "tờ giấy này có những trường nào" -- model tự nghĩ ra loại chứng
# từ trong ngành, tự quyết trường, người ký, ghi chú, cột.
#
# Vì sao vẫn cần lĩnh vực: bỏ trắng thì model viết hoá đơn ba mươi lần. Một
# lĩnh vực là cái đẩy nó ra khỏi chỗ quen, không phải cái khuôn nó phải điền.
DOMAINS = (
    ("y tế", "bệnh viện, phòng khám, trạm y tế, bảo hiểm y tế"),
    ("giáo dục", "trường học, trung tâm đào tạo, phòng giáo dục"),
    ("hành chính nhà nước", "uỷ ban, sở ngành, công an, toà án"),
    ("thuế và kế toán", "cơ quan thuế, phòng kế toán doanh nghiệp"),
    ("ngân hàng và tài chính", "ngân hàng, quỹ tín dụng, công ty chứng khoán"),
    ("bảo hiểm", "doanh nghiệp bảo hiểm nhân thọ và phi nhân thọ"),
    ("xây dựng", "ban quản lý dự án, nhà thầu, tư vấn giám sát"),
    ("vận tải và kho bãi", "hãng vận tải, kho hàng, cảng, chuyển phát"),
    ("thương mại và bán lẻ", "siêu thị, cửa hàng, nhà phân phối"),
    ("nhân sự và lao động", "phòng nhân sự, trung tâm giới thiệu việc làm"),
    ("nhà đất", "sàn bất động sản, ban quản lý toà nhà, văn phòng đăng ký đất đai"),
    ("báo chí và xuất bản", "toà soạn báo, tạp chí, nhà xuất bản"),
)

# BA BẢN NGÔN NGỮ CHO CÙNG MỘT LUẬT.
#
# Server chạy Qwen, và Qwen được tinh chỉnh theo lệnh mạnh nhất ở tiếng Anh và
# tiếng Trung. Prompt tiếng Việt có thể đang bắt nó làm việc ở chỗ nó yếu nhất
# -- nhưng "có thể" không phải là kết luận, nên ba bản cùng tồn tại và `--lang`
# chọn bản nào. Nội dung tờ giấy thì LUÔN là tiếng Việt: ngôn ngữ của lời dặn
# và ngôn ngữ của sản phẩm là hai chuyện khác nhau, và cả ba bản đều nói rõ
# điều ấy ngay đầu file.
#
# Token nạp: ĐO ĐƯỢC cho `zh` là 3 633 mỗi lời gọi (pilot7, server tự báo
# trong `usage.prompt_tokens`, tức tokenizer thật của Qwen). `vi` và `en` chưa
# có lượt nào kịp ghi báo cáo nên chưa đo -- và ước lượng cũ của tôi ở đây
# (zh ~2 485) lệch 32% so với số thật, nên đừng dùng ước lượng ký-tự-chia-N
# thay cho `usage`: tokenizer của Qwen không chia đều theo ký tự, nhất là với
# tiếng Việt có dấu.
PROMPT_OF = {"en": "page"}

# Tên lĩnh vực dịch sang hai thứ tiếng kia. Để nguyên tiếng Việt trong một
# prompt tiếng Anh thì model phải chuyển ngữ trước khi nghĩ -- thêm một bước
# không ai cần, và đúng cái bước mà bản tiếng Anh sinh ra để bỏ đi.
DOMAINS_EN = (
    ("healthcare", "hospitals, clinics, health stations, health insurance"),
    ("education", "schools, training centres, education departments"),
    ("public administration", "people's committees, departments, police, courts"),
    ("tax and accounting", "tax offices, corporate accounting departments"),
    ("banking and finance", "banks, credit funds, securities firms"),
    ("insurance", "life and non-life insurers"),
    ("construction", "project management boards, contractors, supervision consultants"),
    ("transport and warehousing", "carriers, warehouses, ports, courier firms"),
    ("trade and retail", "supermarkets, shops, distributors"),
    ("human resources and labour", "HR departments, employment service centres"),
    ("property", "real-estate agencies, building management, land registries"),
    ("press and publishing", "newspaper and magazine offices, publishers"),
)
DOMAINS_ZH = (
    ("医疗", "医院、诊所、卫生站、医疗保险"),
    ("教育", "学校、培训中心、教育局"),
    ("国家行政", "人民委员会、各厅局、公安、法院"),
    ("税务与会计", "税务机关、企业会计部门"),
    ("银行与金融", "银行、信用基金、证券公司"),
    ("保险", "寿险与非寿险公司"),
    ("建筑", "项目管理委员会、承包商、监理顾问"),
    ("运输与仓储", "运输公司、仓库、港口、快递"),
    ("贸易与零售", "超市、商店、经销商"),
    ("人事与劳动", "人事部门、就业服务中心"),
    ("房地产", "房产交易中心、楼宇管理处、土地登记处"),
    ("新闻与出版", "报社、杂志社、出版社"),
)
DOMAINS_OF = {"en": DOMAINS_EN}

# Cầu nối giữa hai từ vựng độc lập: mười hai lĩnh vực ở trên, và tên phôi trong
# `rulebase/synthgen/`. Không có trường nào trong phôi nói nó thuộc lĩnh vực
# nào -- `profile` quá thô (44 trên 97 phôi là `admin`), nên khớp bằng gốc từ
# trong CHÍNH cái `id`.
#
# Vì sao cần: `inspiration()` quay theo `index`, `ask_for` quay lĩnh vực cũng
# theo `index`, nhưng hai chu kỳ khác nhau -- nên một tờ "thuế và kế toán"
# nhận ba phôi y tế (`don_thuoc`, `giay_chuyen_tuyen`, `the_bhyt`). Model phải
# tự bắc cầu, và nó bắc sai: pilot9 có tờ thuế in ra khối chẩn đoán.
#
# Gốc từ chứ không phải tên đầy đủ, nên phôi mới thêm vào tự rơi đúng nhóm mà
# không ai phải sửa bảng này.
DOMAIN_STEMS = {
    0: ("benh", "vien_phi", "kham", "thuoc", "bhyt", "y_te", "suc_khoe", "dieu_tri"),
    1: ("hoc", "sinh_vien", "dao_tao", "diem", "truong", "tot_nghiep", "giao_duc"),
    2: ("cong_van", "quyet_dinh", "to_trinh", "giay_moi", "don_", "xac_nhan",
        "bien_ban", "uy_quyen", "cong_chung", "ho_khau", "khai_sinh"),
    3: ("thue", "gtgt", "tncn", "tndn", "hoa_don", "quyet_toan", "so_sach",
        "ke_toan", "phieu_thu", "phieu_chi", "bang_can_doi"),
    4: ("ngan_hang", "tin_dung", "tai_khoan", "sao_ke", "vay", "chuyen_tien",
        "the_atm", "chung_khoan", "lai_suat"),
    5: ("bao_hiem", "bhxh", "boi_thuong", "quyen_loi", "giam_dinh", "hop_dong_bh"),
    6: ("xay_dung", "nghiem_thu", "thi_cong", "cong_trinh", "khoi_luong",
        "du_toan", "giam_sat", "vat_tu"),
    7: ("van_don", "van_chuyen", "kho", "xuat_kho", "nhap_kho", "giao_nhan",
        "logistics", "cang", "container"),
    8: ("ban_le", "sieu_thi", "don_hang", "bao_gia", "menu", "hang_hoa",
        "khuyen_mai", "bakery", "shop"),
    9: ("luong", "nhan_su", "lao_dong", "cham_cong", "tuyen_dung", "nghi_viec",
        "danh_gia_nhan_su", "bang_luong"),
    10: ("nha", "dat", "can_ho", "chung_cu", "thue_nha", "bat_dong_san",
         "ban_giao_can_ho", "toa_nha"),
    11: ("bao", "tap_chi", "xuat_ban", "ban_thao", "in_an", "phat_hanh",
         "ban_quyen", "toa_soan"),
}

# TÊN THẬT tiếng Việt cho 30 family của `agent/grammar.py` (Phase 3-4,
# `docs/ke-hoach-refactor-engine.md`). Model không còn cần đoán tên chứng từ
# từ một lĩnh vực rồi tự bịa `doc_slug` -- family ĐÃ LÀ một slug snake_case
# hợp lệ (`one()` gán thẳng `doc_slug = plan.family`, không hỏi model), và
# gợi ý ở đây chỉ để model biết gọi gì bằng tiếng Việt (`doc_kind`) và viết
# nội dung gì cho đúng loại giấy tờ. Một câu ngắn, không phải định nghĩa đầy
# đủ -- phần "loại giấy tờ này thật sự trông ra sao" là việc của
# `agent/grammar.py`, không phải việc lặp lại ở đây.
FAMILY_HINT = {
    "authorisation_letter": "giấy uỷ quyền",
    "cash_receipt_voucher": "phiếu thu/chi tiền mặt",
    "dispatch_letter": "công văn hoặc thông báo hành chính",
    "export_invoice": "hoá đơn xuất khẩu",
    "form_activity": "biên bản hoạt động có xác nhận chữ ký",
    "form_checklist": "phiếu kiểm tra dạng checklist",
    "form_dense": "phiếu đăng ký hoặc hồ sơ khai chi tiết",
    "form_roster": "bảng chấm công hoặc phân công theo lịch",
    "form_sectioned": "biểu mẫu nhiều mục có bảng dữ liệu",
    "form_symmetric": "biểu mẫu hai cột đối xứng",
    "handover_record": "biên bản bàn giao",
    "hospital_bill": "bảng kê chi phí khám chữa bệnh",
    "hotel_stay": "hoá đơn lưu trú khách sạn",
    "insurance_application_form": "giấy yêu cầu bảo hiểm",
    "insurance_auto_certificate": "giấy chứng nhận bảo hiểm ô tô",
    "insurance_cargo_policy": "đơn bảo hiểm hàng hoá",
    "insurance_fire_certificate": "giấy chứng nhận bảo hiểm cháy nổ",
    "insurance_health_certificate": "giấy chứng nhận bảo hiểm sức khoẻ",
    "insurance_health_id_card": "thẻ bảo hiểm y tế",
    "insurance_life_schedule": "bảng quyền lợi bảo hiểm nhân thọ",
    "insurance_moto_certificate": "giấy chứng nhận bảo hiểm xe máy",
    "insurance_property_contract": "hợp đồng bảo hiểm tài sản",
    "insurance_travel_certificate": "giấy chứng nhận bảo hiểm du lịch",
    "invoice_detailed": "hoá đơn bán hàng chi tiết",
    "leave_application": "đơn xin nghỉ phép",
    "meeting_minutes": "biên bản họp",
    "retail_vat_invoice": "hoá đơn bán lẻ có thuế GTGT",
    "tax_invoice_en": "hoá đơn thuế song ngữ Anh-Việt",
    "utility_power": "hoá đơn tiền điện",
    "utility_water": "hoá đơn tiền nước",
}


# FAMILY -> khoá của `DOMAIN_STEMS`, để `inspiration()` lọc phôi tham khảo
# đúng lĩnh vực của family đã chọn -- không phải theo `index % 12` như bản
# cũ. Hai chu kỳ khác độ dài (30 family, 12 domain) drift ra khỏi nhau nếu
# cứ lấy chung một `index`, đúng lớp lỗi mà chính comment ở `DOMAIN_STEMS`
# phía trên đã kể lại (pilot9: tờ thuế in khối chẩn đoán y tế). Ánh xạ
# tường minh ở đây tránh lặp lại đúng lỗi ấy dưới hình dạng khác.
FAMILY_DOMAIN = {
    "hospital_bill": 0, "insurance_health_certificate": 0,
    "insurance_health_id_card": 0,
    "form_dense": 1, "form_checklist": 1,
    "authorisation_letter": 2, "dispatch_letter": 2, "form_activity": 2,
    "form_sectioned": 2, "form_symmetric": 2, "handover_record": 2,
    "leave_application": 2, "meeting_minutes": 2,
    "cash_receipt_voucher": 3, "retail_vat_invoice": 3, "tax_invoice_en": 3,
    "invoice_detailed": 3, "export_invoice": 3,
    "insurance_application_form": 5, "insurance_auto_certificate": 5,
    "insurance_cargo_policy": 5, "insurance_fire_certificate": 5,
    "insurance_life_schedule": 5, "insurance_moto_certificate": 5,
    "insurance_property_contract": 5, "insurance_travel_certificate": 5,
    "form_roster": 9,
    "utility_power": 8, "utility_water": 8, "hotel_stay": 8,
}


def describe_plan(plan: DP.DocumentPlan) -> str:
    """`DocumentPlan` -> đoạn brief mô tả CẤU TRÚC engine đã quyết -- đây
    là chỗ mục 5.1 (Phase 5) thật sự đổi: model không còn được mời "tự
    nghĩ" cấu trúc, chỉ hiện thực hoá cái đã có.

    Không nêu GIÁ TRỊ nội dung (tên công ty, số tiền...) -- chỉ nêu HÌNH
    DẠNG (có bảng hay không, mấy chữ ký, bố cục nào). Nội dung vẫn của
    model, đúng "không khoá literal" (điểm 1 review, tránh G1)."""
    a = plan.assignment
    lines = [f"- family: `{plan.family}` (đã chọn sẵn -- KHÔNG đổi sang loại "
            "chứng từ khác)"]
    if "density" in a:
        lines.append(f"- density: {a['density']}")
    if "header" in a:
        lines.append(f"- header/letterhead layout: {a['header']}")
    if "party_block" in a:
        lines.append(f"- customer/party block layout: {a['party_block']}")
    if "table" in a:
        lines.append(f"- table: CÓ, kiểu {a['table']} (không phải \"none\")")
    else:
        lines.append("- table: KHÔNG -- đừng vẽ bảng nào trên trang này")
    if "signature_count" in a:
        n = a["signature_count"]
        lines.append(f"- signatures: đúng {n} người ký"
                     + (" (không chữ ký nào)" if n == 0 else ""))
    if "signature_layout" in a:
        lines.append(f"- signature layout: {a['signature_layout']}")
    if plan.hard_negative_profile:
        decoys = "; ".join(f"{k} (chiến lược {v})"
                           for k, v in plan.hard_negative_profile.items())
        lines.append(f"- hard negatives bắt buộc cho: {decoys}")
    return "\n".join(lines)


# CHUYỂN VÀO `agent/rate_match.py` (Phase 4 task 4.4, docs/ke-hoach-refactor-
# engine.md) -- cùng lý do `sheets` dưới `one()` cũng chuyển: sampler cần
# gọi được hai hàm này mà không phải biết chúng từng sống ở callsite nào.
# Alias giữ TÊN CŨ để không phải sửa mọi chỗ gọi trong file này, và để
# không phá bất kỳ ai từng `from agent.compose_page import wants_table`.
wants_table = rate_match.wants_table


SAY = {
    "en": {
        "after_table": "Read them for how real Vietnamese paper words things "
                       "(labels, signature block wording, section order) -- "
                       "not for whether to have a table. This document's own "
                       "table decision is already fixed above; use these only "
                       "for wording and tone.",
        "shapes": "Three real Vietnamese documents, reduced to their SHAPE "
                  "(not their content):",
        "blocks": "blocks", "signs": "signed by", "nosign": "nobody signs",
        "after": "Read them for how real Vietnamese paper words things -- not "
                 "for structure. This document's own structure is already "
                 "fixed above.",
        "step1": "## Step one: REALIZE the document the engine already planned",
        "field": "Reference field (for wording/tone only -- not a menu to "
                 "pick a new document type from)", "invent":
            "The structure below is DECIDED, not a suggestion -- table "
            "presence, signature count, layout topology are the engine's "
            "call, not yours. Your job: invent a document `doc_title` and "
            "content that plausibly NEEDS exactly this structure, then "
            "realize it. Answer for yourself: given this structure, what is "
            "this sheet for, which body issues it, what does it print -- "
            "not whether to have a table or how many people sign, which are "
            "already fixed.",
        "planfirst": "Put your answers in the `plan` block. **Write `plan` "
                     "first, `html` second** -- and the HTML must match both "
                     "the `plan` you just wrote AND the structure fixed "
                     "above. `plan` here is your OWN summary of how you "
                     "realized the fixed structure, not a second, competing "
                     "source of truth -- the structure above is authoritative "
                     "and the validator checks the HTML against IT, not "
                     "against your `plan`.\n\nWrite `doc_kind` in VIETNAMESE "
                     "(the sheet's real name, matching the document family "
                     "above). `doc_slug` is filled in for you from the "
                     "family -- do not worry about it.",
        "done": "Already made this run", "nothing": "nothing yet",
        "other": "Invent a plausible DIFFERENT reason/content for the same "
                 "fixed structure -- not a different document type.",
        "step2": "## Step two: map each field to a `data-kind`",
        "map": "Every field you just invented must correspond to ONE "
               "`data-kind` from the list below. Write the `label` -> `kind` "
               "pairs into `field_plan`. If none fits, take the nearest in "
               "meaning -- **do not invent a new name**; an unlisted name gets "
               "the whole page rejected.",
        "regions": "Permitted `data-region`",
        "step3": "## Step three: write the sheet",
        "one_sheet": "This document is **one sheet**.",
        "n_sheets": "This document runs to about **{n} A4 sheets**: write "
                    "ONE `<div class=\"sheet\">` holding enough content for "
                    "that many -- the machine cuts it to A4 height. Do not "
                    "open a new `.sheet`, and do not number the pages "
                    "yourself.",
        "table": "This one HAS an item table, {lo}-{hi} rows.",
        "notable": "This one has **no item table at all**. Lay it out some "
                   "other way: two-column field blocks, prose, numbered "
                   "clauses, tick boxes, a captioned figure frame, a footer "
                   "note.",
        "return": "Return JSON matching the schema: `plan`, `rows` {rows}, and "
                  "`html`.",
        "rows_y": "(one entry per table row, for the arithmetic check)",
        "rows_n": "(an EMPTY list)",
    },
}


def inspiration(index: int, family: str, lang: str = "en", how_many: int = 3,
                table: bool = False) -> str:
    """Vài phôi THẬT của kho, đưa cho model ĐỌC HIỂU chứ không phải ĐIỀN.

    Người dùng hỏi thẳng: "có cách nào đưa các phôi trước đó vào để llm đọc
    hiểu không". Có, và nó giải đúng cái bệnh nhiều bảng.

    Đo trên 97 phôi trong `rulebase/synthgen/`: chỉ **18%** bắt buộc có bảng
    hàng. Còn nhánh LLM đang ép 60%. Chênh lệch ấy không phải do model thích
    bảng -- mà do nó chưa bao giờ được thấy giấy tờ Việt Nam bày bằng cách
    nào khác. Một tờ phiếu chi thật là `fields + totals + signatures`, không
    có lấy một dòng bảng.

    Nên đưa **hình dạng** chứ không đưa nội dung: danh sách khối, một bộ chữ
    ký, khoảng số dòng. Model thấy `phieu_chi` bày ra sao rồi tự nghĩ ra tờ
    khác của riêng nó. Đây không phải quay lại lối "N phôi" người dùng đã bác
    -- phôi ở đây là VÍ DỤ ĐỂ HIỂU, không phải khuôn để điền, và mỗi lượt gọi
    thấy một bộ ví dụ khác nhau.

    Tên phôi và tên chức danh giữ nguyên tiếng Việt ở cả ba bản: chúng là DỮ
    LIỆU về giấy tờ Việt Nam, không phải lời dặn. Dịch "THỦ QUỸ" sang
    "treasurer" là bỏ đi đúng thứ model cần thấy.

    Rẻ: ba phôi rút gọn tốn chừng 120 token nạp, đổi lấy việc model thôi vẽ
    bảng ở chỗ giấy thật không có bảng."""
    pool = D.ARCHETYPES
    if not pool:
        return ""
    say = SAY["en"]
    # Lọc theo lĩnh vực TRƯỚC khi quay vòng. Không đủ ba phôi khớp thì bù bằng
    # cả kho -- thà một ví dụ lệch còn hơn không có ví dụ nào. Tra qua
    # `FAMILY_DOMAIN`, không qua `index % len(DOMAINS)` -- xem lý do ở chỗ
    # khai `FAMILY_DOMAIN`.
    stems = DOMAIN_STEMS.get(FAMILY_DOMAIN.get(family, -1), ())
    near = [a for a in pool if any(s in a.id for s in stems)]
    if len(near) >= how_many:
        pool = near
    # Quay vòng theo `index` bằng bước nguyên tố cùng nhau với độ dài: mỗi
    # lượt thấy một bộ khác, và sau nhiều lượt thì cả kho đều được thấy.
    step = max(1, len(pool) // max(1, how_many))
    picked = [pool[(index * 7 + i * step) % len(pool)] for i in range(how_many)]
    lines = []
    for a in picked:
        blocks = ", ".join(a.always or ())
        signs = " / ".join((a.sign_sets or [()])[0][:3]) or say["nosign"]
        lines.append(f"* `{a.id}` -- {say['blocks']}: {blocks}; "
                     f"{say['signs']}: {signs}")
    # Câu đóng phải khớp với việc tờ này CÓ bảng hay không. Bản trước luôn nói
    # "phần lớn giấy tờ không có bảng hàng nào" rồi bước ba nói ngay "Tờ này CÓ
    # bảng hàng, 7-18 dòng" -- hai câu chỏi nhau trong cùng một lời nhờ.
    close = say["after_table"] if table else say["after"]
    return f"{say['shapes']}\n\n" + "\n".join(lines) + f"\n\n{close}\n\n"


def ask_for(index: int, made: list[str], plan: DP.DocumentPlan, sheets: int,
           lang: str = "en") -> str:
    """Lời nhờ cho MỘT tờ.

    Phase 5 (task 5.1, `docs/ke-hoach-refactor-engine.md`): trước đây
    không có phôi nào ở đây, model tự nghĩ toàn bộ cấu trúc. Giờ `plan`
    (rút từ `agent/grammar.py` qua `agent/document_plan.py`) CỐ ĐỊNH cấu
    trúc -- có bảng hay không, mấy chữ ký, bố cục nào -- và model chỉ còn
    tự do ở nội dung: `doc_title` cụ thể, lý do tài liệu này tồn tại, chữ
    trên trang. Đây đúng ranh giới "LLM là Realizer" (mục 1 tư duy gốc),
    không phải nới lỏng ngược lại G1.

    `made` là những loại chứng từ lượt này đã làm. Đưa vào để đẩy sang chỗ
    khác, không phải để cấm: cùng lối `agent/planner.py` dùng `pressure` để
    phủ đuôi phân phối thay vì bốc độc lập và bỏ trống những góc hiếm."""
    say = SAY["en"]
    hint = FAMILY_HINT.get(plan.family, plan.family)
    every = ", ".join(sorted(kinds()))
    seen = (", ".join(made[-14:]) if made else say["nothing"])
    table = "table" in plan.assignment
    # Số dòng bảng theo SỐ TỜ, không theo chỉ số lượt. Bản trước cho tới 30
    # dòng trên một tờ giấy duy nhất: bảng nuốt hết trang (đúng cái đã sửa ở
    # `1e6b114`), và thân bảng là 21% số ký tự model phải viết ra, tức 21%
    # thời gian. Tài liệu bốn tờ thì cần nhiều dòng để có cớ sang trang; tài
    # liệu một tờ thì không.
    low, high = 4 + index % 4, 10 + sheets * 4
    shape = (say["table"].format(lo=low, hi=high) if table else say["notable"])
    many = (say["one_sheet"] if sheets == 1 else say["n_sheets"].format(n=sheets))
    return (
        f"{say['step1']}\n\n"
        f"{say['field']}: **{hint}** (`{plan.family}`).\n\n"
        "### Structure -- decided by the engine, not by you\n\n"
        f"{describe_plan(plan)}\n\n"
        f"{inspiration(index, plan.family, lang, table=table)}"
        f"{say['invent']}\n\n"
        f"{say['planfirst']}\n\n"
        f"{say['done']}: {seen}. {say['other']}\n\n"
        f"{say['step2']}\n\n"
        f"{say['map']}\n\n"
        f"{every}\n\n"
        f"{say['regions']}: {', '.join(REGIONS)}\n\n"
        f"{say['step3']}\n\n"
        f"{many}\n\n{shape}\n\n"
        + say["return"].format(rows=say["rows_y"] if table else say["rows_n"])
        + "\n"
    )


def arithmetic(rows: list[dict]) -> tuple[int, int]:
    """`(số dòng sai, tổng số dòng)` -- `qty x unit_price` có bằng `amount` không."""
    bad = 0
    for row in rows:
        try:
            if int(row["qty"]) * int(row["unit_price"]) != int(row["amount"]):
                bad += 1
        except (KeyError, TypeError, ValueError):
            bad += 1
    return bad, len(rows)


_PATH_STEP = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)|\[(\d+)\]")


def resolve_path(data: dict, path: str) -> tuple[bool, object]:
    """Đi theo một `data-path` (`issuer.tax_code`, `line_items[0].name`) vào
    cây `data`. `(True, giá trị)` nếu đi hết đường; `(False, None)` nếu gãy
    ở đâu đó -- đường dẫn có đoạn không khớp khoá/chỉ số nào trong cây."""
    node: object = data
    for match in _PATH_STEP.finditer(path):
        name, index = match.group(1), match.group(2)
        if name is not None:
            if not isinstance(node, dict) or name not in node:
                return False, None
            node = node[name]
        else:
            if not isinstance(node, list) or int(index) >= len(node):
                return False, None
            node = node[int(index)]
    return True, node


def data_path_mismatches(data: dict, html: str) -> list[str]:
    """Mỗi `data-path` HTML in ra, đối chiếu với chính cây `data` model đã
    viết TRƯỚC đó -- cây ấy vào `schema()` từ bản sửa architecture cũ (suy
    KIE từ toạ độ), giờ được ghi ra `declared/*.json` rồi không ai đọc lại
    (xem `docs/ke-hoach-refactor-engine.md`, task 1.4). Đây là cách dùng nó:
    không phải nguồn KIE thứ hai -- `data-path` trong HTML đã là nguồn --
    mà một phép đối chiếu NỘI TẠI, bắt đúng lúc model tự mâu thuẫn với chính
    mình giữa hai phần của cùng một câu trả lời.

    KHÔNG gate -- cùng lý do `synthgen/llm_page.py::problems()` chưa ép
    `data-path` phải có mặt: chưa đo được tỉ lệ khớp trên `page.md` mới, và
    ép theo một con số chưa đo là đổi tỉ lệ chấp nhận mà không ai biết trước
    bao nhiêu. Đây là hàm ĐO, để `thinking()`/Phase 2 dùng, không phải hàm
    LOẠI."""
    found: list[str] = []
    for path, printed in declared_paths(html):
        ok, value = resolve_path(data, path)
        if not ok:
            found.append(f'`data-path="{path}"` không tra được trong cây `data` '
                         "model tự viết")
            continue
        wanted = " ".join(str(value).split())
        if wanted and wanted != printed:
            found.append(f'`data-path="{path}"`: `data` ghi {wanted!r}, HTML in '
                         f"ra {printed!r}")
    return found


def _slug(text: str) -> str:
    """Tên thư mục an toàn từ loại chứng từ model tự đặt."""
    plain = str(text).lower()
    # `đ` KHÔNG phân rã được. `unicodedata.normalize("NFD", ...)` tách dấu ra
    # khỏi `ộ` thành `o` + dấu, nhưng `đ` là một CHỮ CÁI riêng trong bảng chữ
    # cái tiếng Việt, không phải `d` có dấu -- NFD để nguyên, rồi bộ lọc
    # `[^a-z0-9]` xoá sạch. Kết quả đo trên pilot6: "hoạt động" -> `hoat_ong`,
    # "đăng ký" -> `ang_ky`. Đổi trước khi phân rã.
    plain = plain.replace("đ", "d").replace("Đ", "d")
    plain = unicodedata.normalize("NFD", plain)
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")[:40] or "llm"


def sheet_plan_problems(plan: dict, sheets: int) -> list[str]:
    """Kế hoạch từng tờ có đủ số tờ được xin không.

    Cổng này không chấm nội dung -- nó chỉ đếm. Model khai bốn mục cho tám tờ
    nghĩa là nó chưa nghĩ về bốn tờ còn lại, và bốn tờ ấy sẽ không có chữ.

    Vì sao đếm chứ không đo chữ: lượng chữ đo được SAU khi dàn trang, còn cổng
    chạy TRƯỚC. Thứ cổng nhìn thấy là lời khai, nên nó gác lời khai."""
    plan_rows = plan.get("sheet_plan")
    if not isinstance(plan_rows, list) or not plan_rows:
        return [f"`sheet_plan` trống; tài liệu này xin {sheets} tờ"]
    if len(plan_rows) < sheets:
        return [f"`sheet_plan` chỉ khai {len(plan_rows)} tờ, tài liệu xin "
                f"{sheets} tờ -- {sheets - len(plan_rows)} tờ chưa ai nghĩ tới"]
    empty = [r.get("sheet") for r in plan_rows
             if not (r.get("sections") or [])]
    if empty:
        return [f"tờ {empty} khai trong `sheet_plan` mà không mục nào"]
    return []


def plan_problems(plan: dict, html: str) -> list[str]:
    """Kế hoạch model tự viết có khớp với trang nó vẽ không.

    Cổng này KHÔNG có ở bản trước, vì bản trước model không tự quyết gì. Giờ
    nó quyết, nên phải kiểm rằng nó làm đúng thứ mình vừa nói -- một kế hoạch
    không ai đối chiếu là một kế hoạch để trang trí.

    Chỉ kiểm hai điều, và cả hai đo được trên chính HTML:

    * `field_plan` ánh xạ sang `data-kind` THẬT. Đây là chỗ lượt trước hỏng
      nhiều nhất -- `patient.name`, `project.code` là tên model tự đặt.
    * `kind` nào đã hứa trong kế hoạch thì phải có mặt trên trang. Hứa mà
      không in là kế hoạch nói một đằng trang làm một nẻo.

    KHÔNG kiểm `purpose`, `issuer`, `layout_idea`: chúng là suy nghĩ, và một
    cái cổng chấm điểm suy nghĩ là một cái cổng đoán."""
    known = kinds()
    found: list[str] = []
    # NHÁY ĐƠN CŨNG LÀ HTML. Bản trước so chuỗi `f'data-kind="{kind}"'`, nên
    # một trang model viết `data-kind='store.name'` trượt SẠCH mọi kind nó đã
    # hứa -- đo trên pilot8: ba tờ báo 0/29, 0/37, 0/38, trong khi phép đo thật
    # (`querySelectorAll('span[data-kind]')`) đếm được 216 hộp từ trên chính
    # một trong ba tờ ấy. Trình duyệt đọc được, cổng gác thì không.
    #
    # Bảy mươi mốt lời than "kế hoạch hứa `…` mà trang không in nó ra" ở lượt
    # pilot8 gần như toàn bộ từ đây, và chúng loại những trang viết đúng.
    printed = printed_kinds(html)
    planned = {k for k in (str(f.get("kind") or "")
                           for f in (plan.get("field_plan") or [])) if k}
    for kind in sorted(planned):
        if kind not in known and not _rooted(kind, known):
            found.append(f"`field_plan` đặt tên `{kind}` không có trong từ vựng")

    # HỨA-MÀ-KHÔNG-IN: đo theo TỈ LỆ, không bắt từng cái một.
    #
    # Luật cũ loại trang ngay khi MỘT kind đã hứa vắng mặt. Đo trên pilot8 sau
    # khi sửa lỗi dấu nháy: mười bảy trên hai mươi hai tờ in đúng 100% kế
    # hoạch, hai tờ thiếu đúng một kind (96% và 97%), một tờ thiếu năm (80%),
    # một tờ thiếu quá nửa (47%). Cái đuôi 96-97% là người ta soạn giấy tờ:
    # lên danh sách rồi bỏ bớt một mục lúc bày trang. Loại nó là loại một tờ
    # viết đúng.
    #
    # Phần từ vựng -- việc THẬT của `field_plan` -- đã do `enum` trong schema
    # lo, và lo chặt hơn mọi lời dặn: bộ giải mã không sinh nổi tên ngoài danh
    # sách. Thứ còn lại cho luật này là bắt trang BỎ HẲN kế hoạch, và một
    # ngưỡng tỉ lệ bắt đúng thứ ấy.
    if planned:
        missing = sorted(k for k in planned if k not in printed)
        # Tha tối đa một phần mười kế hoạch, và ít nhất một kind -- NHƯNG
        # không bao giờ tha cả kế hoạch. Cái sàn "ít nhất một" mà đứng một
        # mình thì với kế hoạch chỉ có một kind, nó tha đúng 100% số bị bỏ:
        # trang vứt sạch kế hoạch vẫn đi qua.
        # MỘT PHẦN NĂM, không phải một phần mười. Đo trên pilot9 sau khi
        # `repair.vocabulary` ánh xạ kind lạ: 23 trên 24 tờ bỏ tối đa 20% kế
        # hoạch, một tờ bỏ 60%. Khe giữa 20% và 60% là khe thật, không phải
        # chỗ tôi chọn cho tiện -- ngưỡng 10% loại 6 tờ nằm trong cụm 8-12%,
        # tức loại đúng cái đuôi "soạn danh sách rồi bỏ bớt một mục", còn
        # ngưỡng 20% vẫn bắt tờ duy nhất thật sự vứt kế hoạch.
        allowed = min(max(1, len(planned) // 5), len(planned) - 1)
        if len(missing) > allowed:
            found.append(
                f"trang bỏ {len(missing)}/{len(planned)} kind đã hứa trong kế "
                f"hoạch (cho phép {allowed}): {', '.join(missing[:6])}")
    if not plan.get("signers") and "sign." in html:
        found.append("trang có chữ ký mà `plan.signers` để trống")
    return found


_HTML_TABLE = re.compile(r"<table\b", re.IGNORECASE)


def plan_conformance_problems(plan: DP.DocumentPlan, html: str) -> list[str]:
    """So HTML THẬT với `DocumentPlan` của ENGINE -- không qua `plan` model
    tự khai lại trong câu trả lời (điểm 3 review, Phase 5 task 5.2):
    `DocumentPlan` là nguồn sự thật, `plan_problems()` ở trên vẫn hữu ích
    (bắt model khai `field_plan` sai từ vựng, hoặc bỏ sót phần đã hứa
    trong CHÍNH câu trả lời của nó) nhưng không được dùng để nói "cấu trúc
    trang đúng" -- việc đó là của hàm này.

    Chỉ kiểm hai điều đo được chắc chắn từ HTML mà không cần đoán: có bảng
    hay không (thẻ `<table>` thật), có chữ ký hay không (`data-kind` bắt
    đầu bằng `sign.`) -- cả hai đều là nhị phân trong `DocumentPlan`
    (`"table" in assignment`, `signature_count == 0` hay `> 0`), nên so
    được thẳng, không cần suy luận số lượng chính xác."""
    found: list[str] = []
    has_table = bool(_HTML_TABLE.search(html))
    wants_table_plan = "table" in plan.assignment
    if wants_table_plan and not has_table:
        found.append(f"engine plan ({plan.family}) yêu cầu có bảng "
                     "(`table` trong DocumentPlan) nhưng HTML không có thẻ "
                     "`<table>` nào")
    elif not wants_table_plan and has_table:
        found.append(f"engine plan ({plan.family}) không có nhánh `table` "
                     "(gia đình này không dùng bảng) nhưng HTML có `<table>`")

    sig_count = plan.assignment.get("signature_count")
    has_signature = "sign." in html
    if sig_count == 0 and has_signature:
        found.append(f"engine plan ({plan.family}) yêu cầu 0 chữ ký nhưng "
                     "HTML có `data-kind` bắt đầu bằng `sign.`")
    elif isinstance(sig_count, int) and sig_count > 0 and not has_signature:
        found.append(f"engine plan ({plan.family}) yêu cầu {sig_count} chữ "
                     "ký nhưng HTML không có `data-kind` nào bắt đầu bằng "
                     "`sign.`")
    return found


def budget(sheets: int) -> int:
    """Trần token đầu ra cho một tài liệu `sheets` tờ.

    Trần CỐ ĐỊNH 9 000 không khớp với chính lời dặn của mình: prompt cho mỗi tờ
    8 000 ký tự, và đo được 2,05 ký tự mỗi token, nên một tờ tốn chừng 3 900
    token. Ba tờ đã cần 11 700 -- vượt trần. Đo trên pilot8: hai lời gọi duy
    nhất trả về "reply was not JSON" là đúng hai tài liệu 4 tờ và 6 tờ, cụt
    giữa chừng vì chạm trần sau 168 giây.

    2 600 token cho `plan` và `rows`, cộng 4 200 mỗi tờ. Trần trên 30 000 để
    một lời gọi lạc lối vẫn hỏng nhanh thay vì ăn hết cửa sổ ngữ cảnh."""
    # Trần trên 40 000, không 30 000. Tám tờ cần chừng 31 200 token ở mức
    # 8 000 ký tự mỗi tờ, nên trần cũ cắt cụt đúng cỡ dài nhất. Cửa sổ ngữ
    # cảnh của máy chủ là 262 144 nên còn rộng chán; trần ở đây chỉ để một
    # lời gọi lạc lối hỏng nhanh thay vì ăn hết cửa sổ.
    return min(40_000, 2_600 + max(1, sheets) * 4_200)


def patience(sheets: int, floor: float) -> float:
    """Hạn chờ cho một tài liệu `sheets` tờ, tính từ trần token.

    Trần co giãn thì hạn chờ phải co giãn theo, nếu không ta chỉ đổi kiểu hỏng:
    tờ sáu trang thôi cụt JSON mà chuyển sang hết hạn chờ. 23 400 token ở 24
    tok/s -- tốc độ đo được lúc máy chủ bận -- là 975 giây, vượt hạn 600.

    Lấy 15 tok/s làm đáy: chậm hơn mọi lượt đã đo (pilot7 24, pilot8 52), nên
    hạn rộng mà vẫn hữu hạn. Không bao giờ ngắn hơn `floor` người dùng đặt."""
    return max(floor, budget(sheets) / 15.0)


def thinking(got: dict, brief: str) -> str:
    """Một trang đọc được, ghép mọi thứ cần để mổ một tờ hỏng.

    Vì sao cần: một tờ trượt cổng hiện để lại HTML trong `rejected/`, một câu
    báo lỗi trong `declared/`, và một tấm ảnh trong `rejected_boxes/` -- ba chỗ
    khác nhau, và không chỗ nào nói model NGHĨ GÌ. Người sửa lời dặn phải tự
    ghép lại, và ghép sai thì sửa nhầm.

    Gộp bốn thứ vào một tệp: lời nhờ nó nhận, kế hoạch nó viết, lý lẽ nó nêu,
    và phán quyết của cổng. Đọc từ trên xuống là thấy chỗ suy nghĩ rẽ sai.

    Viết cho MỌI tờ, không riêng tờ hỏng: một tờ ĐẠT cũng đáng đọc, vì so nó
    với tờ hỏng cạnh bên là cách nhanh nhất thấy khác biệt."""
    plan = got.get("plan") or {}
    why = plan.get("reasoning") or {}
    ok = got.get("ok")
    lines = [
        f"# {got.get('loai_tai_lieu') or got['archetype']}",
        "",
        f"* **Kết quả**: {'ĐẠT' if ok else 'TRƯỢT CỔNG'}",
        f"* **Thư mục**: `{got['archetype']}`  ·  chỉ số {got['index']}",
        f"* **Thời gian**: {got.get('seconds')}s  ·  "
        f"{got.get('tokens_out')} token ra / {got.get('tokens_in')} vào",
        f"* **Xin**: {got.get('sheets_asked')} tờ  ·  "
        f"bảng: {'có' if got.get('table_asked') else 'không'}",
        "",
        "## Model nghĩ gì",
        "",
        f"**Vì sao chọn loại chứng từ này** — {why.get('why_this_document') or '(không nói)'}",
        "",
        f"**Vì sao bày trang như vậy** — {why.get('why_this_layout') or '(không nói)'}",
        "",
        f"**Chỗ khó nhất** — {why.get('hardest_choice') or '(không nói)'}",
        "",
        "## Model định làm gì",
        "",
        f"* mục đích: {plan.get('purpose') or '—'}",
        f"* cơ quan phát hành: {plan.get('issuer') or '—'}",
        f"* người ký: {', '.join(plan.get('signers') or []) or '—'}",
        f"* ý bố cục: {plan.get('layout_idea') or '—'}",
        "",
    ]
    fields = plan.get("field_plan") or []
    if fields:
        lines += [f"### {len(fields)} trường đã ánh xạ", "",
                  "| nhãn trên giấy | `data-kind` |", "|---|---|"]
        lines += [f"| {f.get('label','')} | `{f.get('kind','')}` |" for f in fields]
        lines += [""]
    mended = {k: v for k, v in (got.get("mended") or {}).items() if v}
    if mended:
        lines += ["## Bản vá máy đã chữa trước khi ra cổng", ""]
        lines += [f"* {k}: {v}" for k, v in mended.items()]
        lines += [""]
    if not ok:
        lines += ["## Vì sao cổng loại", ""]
        lines += [f"* {w}" for w in (got.get("why") or [])]
        lines += [""]
    lines += ["## Lời nhờ nó nhận", "", "```", brief.strip(), "```", ""]
    return "\n".join(lines)


def one(client, index: int, made: list[str], seed: int,
        lang: str = "en") -> dict:
    """Một tờ: hỏi, đo, gác cổng. Không ném -- lỗi là một kết quả."""
    started = time.time()
    # Số tờ vẫn quay vòng qua `agent/rate_match.py` (Phase 4 task 4.4) --
    # khái niệm "mấy trang" không nằm trong grammar (Phase 3), độc lập với
    # family đã rút.
    sheets = rate_match.sheet_count(index)
    # PHASE 5 (task 5.1): family + cấu trúc rút từ `agent/grammar.py` qua
    # `agent/document_plan.py`, KHÔNG để model tự nghĩ nữa. `seed + index`
    # giống hệt cách `seals()`/`hands()` bên dưới seed -- an toàn khi chạy
    # song song (`ThreadPoolExecutor` trong `run()`), mỗi `index` một RNG
    # riêng, không có state dùng chung.
    rng = random.Random(seed + index)
    family = sorted(G.FAMILIES)[index % len(G.FAMILIES)]
    plan = DP.sample(G.FAMILIES[family], rng)
    brief = ask_for(index, made, plan, sheets, lang)
    try:
        answer, usage = client.decide_with_usage(
            system_prompt(),
            brief, schema(),
            max_tokens=budget(sheets), timeout=patience(sheets, client.timeout))
    except LLMError as error:
        spent = round(time.time() - started, 1)
        text = str(error)
        # Phân biệt HẾT HẠN CHỜ với lỗi khác: log tổng hợp phải đếm riêng hai
        # thứ ấy, vì cách chữa khác hẳn nhau -- một bên nới hạn hoặc giảm số
        # request song song, một bên sửa prompt hoặc schema.
        timed_out = "timed out" in text.lower() or "timeout" in text.lower()
        return {"index": index, "archetype": "llm", "ok": False,
                "seconds": spent, "timed_out": timed_out,
                "tokens_in": 0, "tokens_out": 0,
                "why": [f"model không trả lời: {text[:120]}"]}
    spent = round(time.time() - started, 1)
    out_tokens = int(usage.get("completion_tokens") or 0)
    in_tokens = int(usage.get("prompt_tokens") or 0)

    html = str(answer.get("html") or "")
    # `declared` là model TỰ TÓM TẮT nó đã làm gì -- KHÔNG phải nguồn sự
    # thật (điểm 3 review, Phase 5 task 5.2). Đặt tên khác `plan` (biến ở
    # trên, `DocumentPlan` của engine) có chủ đích: hai biến trùng tên từng
    # là cách dễ nhất để lỡ tay validate nhầm bằng bản model tự khai thay vì
    # bản engine đã quyết.
    declared = dict(answer.get("plan") or {})
    # CÂY DỮ LIỆU. Bản trước khai nó trong schema rồi vứt đi -- đo được 0/12 tờ
    # có `data` trong `declared/`, không phải vì model không viết mà vì không
    # ai đọc ra khỏi câu trả lời.
    tree = answer.get("data")
    tree = tree if isinstance(tree, dict) else {}
    rows = list(answer.get("rows") or [])
    wrong, total = arithmetic(rows)
    # CHỮA TRƯỚC KHI GÁC. Đo trên pilot6: sáu tờ bị loại, năm tờ trượt vì hai
    # lỗi mà máy chữa được không cần đoán -- `<td>` thiếu `data-cell`, và
    # `<br>` nằm trong span có nhãn. Tỉ lệ đạt 3/9 lên 8/9.
    #
    # Đây không phải nới lỏng cổng gác: cổng vẫn y nguyên, chạy sau, và vẫn
    # loại mọi thứ nó vẫn loại. Chỉ là thôi bắt model làm một việc mười dòng
    # mã làm đúng mọi lần -- đúng ranh giới `synthgen/markup.py` vẫn giữ.
    html, mended = repair(html)
    # MỰC THẬT vào chỗ model đặt sẵn. Phải chạy TRƯỚC cổng gác: cổng đo trên
    # HTML cuối cùng, không đo trên bản nháp.
    html, stamped = seals(html, seed=seed + index)
    # Nét chữ ký sau con dấu, cùng một lẽ: model đặt CHỖ, engine điền MỰC.
    html, signed = hands(html, seed=seed + index)
    mended["dấu thật đã điền"] = stamped
    # `plan_conformance_problems` so HTML với `plan` (ENGINE, authoritative).
    # `plan_problems`/`sheet_plan_problems` vẫn so với `declared` (model tự
    # khai) -- vẫn hữu ích để bắt model tự mâu thuẫn với chính lời nó vừa
    # nói, nhưng không còn là nơi quyết "cấu trúc trang có đúng không".
    found = (problems(html) + plan_problems(declared, html)
             + sheet_plan_problems(declared, sheets)
             + plan_conformance_problems(plan, html))
    # `doc_slug` giờ LÀ `plan.family` -- engine đã quyết, không hỏi model
    # nữa (điểm 3 review). `declared.get("doc_slug")` không còn dùng để
    # đặt tên thư mục, chỉ còn trong `declared` để đọc lại lúc gỡ lỗi.
    kind = plan.family
    return {
        "index": index, "archetype": kind, "ok": not found,
        "seconds": spent, "why": found,
        "html": html, "rows": rows, "plan": declared,
        "engine_plan": dict(plan.assignment),
        "hard_negative_profile": dict(plan.hard_negative_profile),
        "data": tree,
        "loai_tai_lieu": str(declared.get("doc_kind") or kind),
        "doc_title": str(declared.get("doc_title") or ""),
        "sheets_asked": sheets, "table_asked": "table" in plan.assignment,
        "chars": len(html), "rows_wrong": wrong, "rows_total": total,
        "tokens_in": in_tokens, "tokens_out": out_tokens,
        "tokens_per_second": round(out_tokens / spent, 1) if spent else 0.0,
        "mended": {k: v for k, v in mended.items() if v},
        "brief": brief,
        "stamped": stamped, "signed": signed,
    }



def _mend_tally(made: list[dict]) -> dict[str, int]:
    """Bản vá máy đã chữa những gì, tổng cộng bao nhiêu chỗ."""
    tally: dict[str, int] = {}
    for m in made:
        for k, v in (m.get("mended") or {}).items():
            tally[k] = tally.get(k, 0) + v
    return tally


def _why_tally(made: list[dict]) -> dict[str, int]:
    """Lý do trượt, gộp theo DẠNG chứ không theo câu chữ.

    "10 ô bảng thiếu `data-cell`" và "14 ô bảng thiếu `data-cell`" là MỘT lỗi.
    Đếm chúng riêng ra thì bảng xếp hạng nói về số ô, không nói về số lỗi -- và
    thứ cần sửa là cái lỗi."""
    tally: dict[str, int] = {}
    for m in made:
        for why in (m.get("why") or []):
            key = re.sub(r"\d+", "N", str(why)).split(";")[0][:70]
            tally[key] = tally.get(key, 0) + 1
    return dict(sorted(tally.items(), key=lambda kv: -kv[1]))


def _write_performance(out: Path, report: dict, made: list[dict]) -> None:
    """`performance.md` -- một trang đọc được bằng mắt, và `calls.jsonl`.

    `compose_report.json` đã có đủ số, nhưng nó là JSON: mở ra để trả lời "lượt
    này chạy thế nào" thì phải tự cộng trong đầu. File này trả lời sẵn, và nó
    tồn tại vì người dùng hỏi đúng câu ấy -- vào/ra, token vào/ra, thời gian,
    số lần hết hạn chờ, số ca hỏng.

    `calls.jsonl` là một dòng một lời gọi: dùng khi cần so hai lượt với nhau
    hoặc dựng biểu đồ, thứ mà một file markdown không làm được."""
    pages = sorted(made, key=lambda m: m["index"])
    with (out / "calls.jsonl").open("w", encoding="utf-8") as fh:
        for m in pages:
            fh.write(json.dumps(
                {k: v for k, v in m.items() if k not in ("html", "rows", "plan")},
                ensure_ascii=False) + "\n")

    secs = sorted(m.get("seconds", 0) for m in pages)
    outs = sorted(m.get("tokens_out", 0) for m in pages if m.get("tokens_out"))
    mid = lambda v: v[len(v) // 2] if v else 0                    # noqa: E731
    kept = [m for m in pages if m["ok"]]
    lines = [
        f"# Hiệu năng lượt sinh -- {report['when']}",
        "",
        f"* **Model** `{report['model']}` tại `{report['url']}`",
        f"* **Lời dặn** bằng `{report.get('lang')}`"
        f" (`agent/guideline/SYSTEM_PROMPT.md` +"
        f" `agent/prompts/{PROMPT_OF.get(report.get('lang'), 'page')}.md`)",
        f"* **Song song** {report['concurrency']} request",
        "",
        "## Kết quả",
        "",
        "| | |",
        "|---|---|",
        f"| Xin | {report['asked']} tờ |",
        f"| Qua cổng | **{report['kept']}** "
        f"({100 * report['kept'] / max(report['asked'], 1):.0f}%) |",
        f"| Trượt cổng | {len(pages) - len(kept) - report['timed_out']} |",
        f"| Hết hạn chờ / không trả lời | {report['timed_out']} |",
        f"| Chưa chạy tới | {report['asked'] - len(pages)} |",
        "",
        "## Thời gian",
        "",
        "| | |",
        "|---|---|",
        f"| Tổng | {report['seconds']}s |",
        f"| Mỗi tờ (gộp cả song song) | {report['seconds_per_page']}s |",
        f"| Một lời gọi, trung vị | {mid(secs)}s |",
        f"| Một lời gọi, nhanh nhất / chậm nhất | "
        f"{secs[0] if secs else 0}s / {secs[-1] if secs else 0}s |",
        "",
        "## Token",
        "",
        "| | |",
        "|---|---|",
        f"| Vào, tổng | {report['tokens_in']} |",
        f"| Ra, tổng | {report['tokens_out']} |",
        f"| Ra, mỗi tờ trung vị | {mid(outs)} |",
        f"| Ra, nhỏ nhất / lớn nhất | "
        f"{outs[0] if outs else 0} / {outs[-1] if outs else 0} |",
        f"| Tốc độ gộp | {report['tokens_per_second']} tk/s |",
        f"| Ký tự HTML, trung vị | {report['median_chars']} |",
        "",
    ]
    if report["tokens_per_second"]:
        hours = (report["tokens_out_per_page"] * 20000
                 / report["tokens_per_second"] / 3600)
        lines += [f"Suy ra: **20 000 tờ ≈ {hours:.1f} giờ** ở tốc độ và mức "
                  f"song song này.", ""]
    if report["mended"]:
        lines += ["## Bản vá máy đã chữa", "",
                  "Những lỗi này KHÔNG tính là trượt -- `synthgen/repair.py` "
                  "sửa xong trước khi ra cổng.", "", "| Việc | Số chỗ |",
                  "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in report["mended"].items()]
        lines += [""]
    if report["why_tally"]:
        lines += ["## Vì sao trượt", "", "| Lý do | Số tờ |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in report["why_tally"].items()]
        lines += [""]
    kinds_made = [m.get("loai_tai_lieu") or m["archetype"] for m in pages]
    lines += ["## Loại chứng từ model tự nghĩ ra", "",
              f"{len(set(kinds_made))} loại khác nhau trên {len(pages)} tờ.", ""]
    lines += [f"* {'✓' if m['ok'] else '✗'} `{m['archetype']}` -- "
              f"{m.get('loai_tai_lieu') or ''}" for m in pages]
    (out / "performance.md").write_text("\n".join(lines) + "\n",
                                        encoding="utf-8")



class Artist(threading.Thread):
    """Thợ vẽ: một luồng, một trình duyệt, vẽ ngay khi HTML vừa ghi ra đĩa.

    Bản trước vẽ ở CUỐI lượt, sau khi hai mươi tư tờ đã xong. Hai cái giá:
    tấm ảnh đầu tiên phải đợi cả lượt (pilot7 mất mười chín phút), và một lượt
    gãy giữa chừng không để lại tấm nào -- đúng cái đã xảy ra ở pilot5.

    Vẽ xen kẽ còn KHÔNG tốn thêm thời gian: lượt sinh dành gần hết thời gian
    ngồi đợi server trả lời, nên vẽ (khoảng một giây một tờ) lấp vào chỗ trống
    ấy. Xong tờ cuối là xong cả ảnh.

    MỘT luồng, không phải bốn: `playwright` bản đồng bộ gắn với luồng tạo ra
    nó, nên nhiều luồng cùng vẽ là hỏng. Một luồng là đủ -- vẽ nhanh hơn sinh
    hai trăm lần."""

    def __init__(self, out: Path) -> None:
        super().__init__(daemon=True)
        self.out = out
        self.queue: queue.Queue = queue.Queue()
        self.rows: list[dict] = []
        self.started_ok = False
        self.why = ""

    def put(self, path: Path, passed: bool) -> None:
        self.queue.put((path, passed))

    def close(self) -> None:
        """Báo hết việc rồi đợi vẽ nốt."""
        self.queue.put(None)
        self.join()

    def run(self) -> None:                                  # noqa: D102
        from synthgen import draw_llm                       # noqa: PLC0415

        try:
            drawer_cm = draw_llm.Drawer(self.out)
        except Exception as error:                          # noqa: BLE001
            self.why = f"{type(error).__name__}: {error}"
            self._drain()
            return
        try:
            with drawer_cm as drawer:
                self.started_ok = True
                while True:
                    job = self.queue.get()
                    if job is None:
                        break
                    path, passed = job
                    try:
                        line, _ok = drawer.draw(path, passed)
                    except Exception as error:              # noqa: BLE001
                        line = f"  ✗ {path.stem}: {type(error).__name__}: {error}"
                    print(f"[vẽ]{line}", flush=True)
                self.rows = drawer.rows
        except Exception as error:                          # noqa: BLE001
            # Vẽ hỏng KHÔNG được làm hỏng lượt sinh: HTML và báo cáo đã nằm
            # trên đĩa rồi, và chúng là thứ đắt. Nói ra rồi đi tiếp.
            self.why = f"{type(error).__name__}: {error}"
            self._drain()

    def _drain(self) -> None:
        """Nuốt nốt hàng đợi để `close()` không treo khi thợ vẽ đã chết."""
        while True:
            if self.queue.get() is None:
                return


def _draw(out: Path) -> None:
    """Vẽ ảnh hộp bố cục và KIE cho lượt vừa sinh.

    Chạy bằng SUBPROCESS chứ không `import`: trình thông dịch có `playwright`
    thường không phải trình thông dịch đang chạy hàm này."""
    exe = drawing_python()
    if exe is None:
        print("[trang] không môi trường nào có `playwright`, nên không vẽ "
              "được ảnh. Cài vào một môi trường rồi chạy:\n"
              f"  <python có playwright> -m synthgen.draw_llm {out}")
        return
    print(f"\n[trang] vẽ ảnh kiểm tra (hộp bố cục + KIE) bằng {exe}...")
    done = subprocess.run([exe, "-m", "synthgen.draw_llm", str(out)],
                          cwd=str(Path(__file__).resolve().parents[1]),
                          check=False)
    if done.returncode:
        # Vẽ hỏng KHÔNG được làm hỏng lượt sinh: HTML và báo cáo đã nằm trên
        # đĩa rồi, và chúng là thứ đắt. Nói ra rồi đi tiếp.
        print(f"[trang] vẽ hỏng (mã {done.returncode}); HTML vẫn còn -- "
              f"chạy lại bằng:\n  {exe} -m synthgen.draw_llm {out}")


def run(want: int, out: Path, *, concurrency: int, seed: int,
        lang: str = "en", no_draw: bool = False) -> int:
    # Sáu trăm giây cho MỘT tờ. Viết một trang HTML là việc dài nhất kho này
    # nhờ model làm: đo được 5 400 token ở 15 tok/s khi bốn request chạy cùng
    # lúc, tức 360 giây -- vượt hạn mặc định 120 giây, và `_post` thử lại ba
    # lần nên một tờ nghẹn mất 364 giây rồi vẫn hỏng.
    # Trần 9 000 token đầu ra. Trung vị một tờ là 4 685 token HTML cộng `plan`
    # và `rows`, nên 9 000 là rộng rãi cho cả tờ sáu trang -- nó chỉ chặn ca
    # model lan man, thứ vốn tiêu 360 giây rồi vẫn hỏng.
    client = from_env(timeout=float(os.environ.get("VLM_LLM_TIMEOUT", 600)),
                      max_tokens=int(os.environ.get("VLM_LLM_MAX_TOKENS", 9000)))
    if client is None:
        print("chưa đặt VLM_LLM_URL. Ví dụ:\n"
              "  export VLM_LLM_URL=http://10.148.20.19:8008/v1\n"
              "  export VLM_LLM_MODEL=Qwen/Qwen3.8-27B-FP8\n"
              "  export NO_PROXY='10.148.20.19,localhost,127.0.0.1'")
        return 1
    if not client.alive():
        print(f"{client.url} không trả lời.\n"
              "Nếu máy có proxy thì mọi kết nối tới IP nội bộ bị chặn -- "
              "`env | grep -i proxy`, rồi đặt NO_PROXY.")
        return 1

    print(f"[trang] {want} tờ, {concurrency} request song song, "
          f"model {client.model}")
    print(f"[trang] engine chọn family + cấu trúc ({len(G.FAMILIES)} family, "
          "agent/grammar.py); model hiện thực hoá nội dung (Phase 5)")
    out.mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(exist_ok=True)
    (out / "rejected").mkdir(exist_ok=True)
    (out / "thinking").mkdir(exist_ok=True)
    (out / "declared").mkdir(exist_ok=True)

    started = time.time()
    made: list[dict] = []
    # Những loại đã làm, để lời nhờ tiếp theo đẩy model sang chỗ khác. Dùng
    # chung giữa các luồng nên có khoá -- danh sách này đọc ở mỗi lần hỏi.
    kinds_made: list[str] = []
    lock = threading.Lock()

    def work(index: int) -> dict:
        with lock:
            seen = list(kinds_made)
        got = one(client, index, seen, seed, lang)
        with lock:
            if got.get("loai_tai_lieu"):
                kinds_made.append(got["loai_tai_lieu"])
        return got

    artist: Artist | None = None
    if not no_draw:
        for name in ("html", "rejected", "declared", "thinking"):
            (out / name).mkdir(parents=True, exist_ok=True)
        artist = Artist(out)
        artist.start()

    with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(work, i): i for i in range(want)}
        for future in cf.as_completed(futures):
            got = future.result()
            made.append(got)
            mark = "✓" if got["ok"] else "✗"
            note = "" if got["ok"] else f"  {got['why'][0][:70]}"
            arith = (f"  số học {got['rows_wrong']}/{got['rows_total']} sai"
                     if got.get("rows_total") else "")
            cost = (f"  {got['tokens_out']}tk {got['tokens_per_second']}tk/s"
                    if got.get("tokens_out") else "")
            print(f"  {mark} {len(made):3d}/{want}  {got['archetype']:22s} "
                  f"{got['seconds']:5.1f}s{cost}{arith}{note}", flush=True)
            # GIỮ CẢ TRANG TRƯỢT. Bản đầu chỉ lưu trang qua cổng, nên 21
            # trang hỏng biến mất cùng lý do của chúng -- không soi được model
            # sai ở đâu, không sửa được lời dặn, và không chạy lại cổng trên
            # chúng sau khi cổng đổi. Một phép thử vứt đi mọi ca hỏng là một
            # phép thử chỉ nhìn thấy cái nó đã đúng.
            #
            # `html/` là trang qua cổng, `rejected/` là trang trượt: tách thư
            # mục chứ không tách bằng tên, để `synthgen/draw_llm.py` vẽ cả hai
            # mà `synthgen/run.py` chỉ lấy thư mục đầu.
            stem = f"llm_{got['archetype']}_{got['index']:04d}"
            # `.get`, không `[...]`. Một tờ mà model KHÔNG trả lời (hết hạn
            # chờ) không có khoá `html` nào, và bản trước lấy `got["html"]`
            # thẳng tay -- nên một request hết hạn ở tờ thứ mười lăm giết cả
            # lượt chạy, và mười bốn tờ đã xong đi theo. Một lượt sinh phải
            # sống sót qua một lần server nghẹn.
            folder = "html" if got["ok"] else "rejected"
            if got.get("html"):
                (out / folder / f"{stem}.html").write_text(got["html"],
                                                          encoding="utf-8")
            # NHẬT KÝ TƯ DUY, một tệp một tờ. Viết cho cả tờ đạt lẫn tờ
            # trượt: so hai cái cạnh nhau là cách nhanh nhất thấy khác biệt.
            if got.get("brief"):
                (out / "thinking" / f"{stem}.md").write_text(
                    thinking(got, got["brief"]), encoding="utf-8")
            (out / "declared" / f"{stem}.json").write_text(
                json.dumps({"loai_tai_lieu": got.get("loai_tai_lieu", ""),
                            # KẾ HOẠCH model tự viết, giữ nguyên. Đây là chỗ
                            # đọc được nó NGHĨ gì trước khi vẽ -- và khi một
                            # trang trượt, so kế hoạch với HTML nói ngay nó
                            # hiểu sai ở bước nào.
                            "plan": got.get("plan") or {},
                            # Cây dữ liệu model viết TRƯỚC khi bày trang. Giữ
                            # nguyên: nó là sự thật của tờ giấy, và `data-path`
                            # trong HTML trỏ về đây.
                            "data": got.get("data") or {},
                            "doc_title": got.get("doc_title", ""),
                            # `archetype` là SLUG do ta chọn, không phải tên
                            # model tự đặt: `loai_tai_lieu` nó trả về là chữ
                            # tự do tiếng Việt ("Tờ khai báo y tế / Phiếu khai
                            # báo dịch tễ"), và dùng nó làm tên thư mục thì
                            # dấu gạch chéo cắt đường dẫn làm đôi.
                            "archetype": got["archetype"],
                            # SỐ TỜ ĐÃ XIN. Từ khi máy cắt theo bề dài A4,
                            # model không quyết số tờ nữa -- nó quyết LƯỢNG
                            # CHỮ. Ghi con số đã xin để bước vẽ nói được "xin 4
                            # -> cắt ra 2": cách duy nhất thấy model viết thiếu.
                            "sheets_asked": got.get("sheets_asked", 1),
                            # SỐ TỜ ĐÃ XIN. Từ khi máy cắt theo bề dài A4,
                            # model không quyết số tờ nữa -- nó quyết LƯỢNG
                            # CHỮ. Ghi con số đã xin ở đây để bước vẽ nói được
                            # "xin 4 tờ, cắt ra 2": đó là cách duy nhất thấy
                            # model viết thiếu, vì trang nào cũng qua cổng dù
                            # ngắn hay dài.
                            "sheets_asked": got.get("sheets_asked", 1),
                            "rows": got.get("rows") or [],
                            "ok": got["ok"], "why": got["why"]},
                           ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
            # VẼ NGAY. `declared/` phải ghi TRƯỚC: `Drawer.draw` đọc nó để lấy
            # `archetype` làm tên thư mục và `why` để in kèm.
            if artist is not None and got.get("html"):
                artist.put(out / folder / f"{stem}.html", got["ok"])

    spent = time.time() - started
    kept = [m for m in made if m["ok"]]
    wrong = sum(m.get("rows_wrong", 0) for m in made)
    total = sum(m.get("rows_total", 0) for m in made)
    report = {
        "asked": want, "kept": len(kept),
        "seconds": round(spent, 1),
        "seconds_per_page": round(spent / max(want, 1), 1),
        # TOKEN, không chỉ giây. Giây một mình không ước lượng được một lượt
        # hai mươi nghìn trang: cùng một khoảng thời gian che cả một trang ngắn
        # lúc server rảnh lẫn một trang dài lúc server bận. Token thì không.
        "tokens_out": sum(m.get("tokens_out", 0) for m in made),
        "tokens_in": sum(m.get("tokens_in", 0) for m in made),
        "tokens_out_per_page": round(
            sum(m.get("tokens_out", 0) for m in made) / max(len(made), 1)),
        "tokens_per_second": round(
            sum(m.get("tokens_out", 0) for m in made) / max(spent, 1e-6), 1),
        "concurrency": concurrency,
        "model": client.model, "url": client.url,
        "rows_wrong": wrong, "rows_total": total,
        "arithmetic_error_rate": round(wrong / total, 4) if total else None,
        "median_chars": sorted(m.get("chars", 0) for m in made)[len(made) // 2]
        if made else 0,
        "when": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages": [{k: v for k, v in m.items() if k not in ("html", "rows")}
                  for m in sorted(made, key=lambda m: m["index"])],
    }
    report["lang"] = lang
    report["timed_out"] = sum(1 for m in made if m.get("timed_out"))
    report["mended"] = _mend_tally(made)
    report["why_tally"] = _why_tally(made)
    # MÃ, không chỉ CÂU. `why_tally` gộp theo câu (đã bỏ số) -- đọc được bằng
    # mắt nhưng không `groupby` được giữa các lượt chạy nếu câu đổi chữ.
    # `pipeline.failures.classify` gán mỗi câu một trong 12 mã cố định
    # (`docs/ke-hoach-refactor-engine.md` Phase 2), nên script so sánh
    # nhiều lượt chạy đọc `failure_codes`, người đọc bằng mắt vẫn đọc
    # `why_tally`.
    report["failure_codes"] = failures.tally(
        [why for m in made for why in (m.get("why") or [])])
    (out / "compose_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _write_performance(out, report, made)

    print(f"\n[trang] {len(kept)}/{want} qua cổng  ({100*len(kept)/max(want,1):.0f}%)")
    if report["tokens_out"]:
        print(f"[trang] token: {report['tokens_out']} ra / "
              f"{report['tokens_in']} vào, "
              f"{report['tokens_out_per_page']} tk mỗi tờ, "
              f"{report['tokens_per_second']} tk/s gộp")
        rate = report["tokens_per_second"]
        if rate:
            hours = report["tokens_out_per_page"] * 20000 / rate / 3600
            print(f"[trang] suy ra: 20 000 tờ ≈ {hours:.1f} giờ "
                  f"ở tốc độ và mức song song này")
    print(f"[trang] {spent:.0f}s, {report['seconds_per_page']}s mỗi tờ, "
          f"{concurrency} song song")
    if total:
        print(f"[trang] SỐ HỌC: {wrong}/{total} dòng sai "
              f"({100*wrong/total:.1f}%) -- `qty x đơn giá != thành tiền`")
    why: dict[str, int] = {}
    for m in made:
        for line in m["why"]:
            key = re.sub(r"`[^`]*`", "`…`", line)[:64]
            why[key] = why.get(key, 0) + 1
    if why:
        print("[trang] lý do bị loại:")
        for line, n in sorted(why.items(), key=lambda kv: -kv[1]):
            print(f"    {n:3d}  {line}")
    print(f"[trang] -> {out}")
    # VẼ LUÔN. Người dùng phải xem được chất lượng ngay sau lượt chạy, không
    # phải nhớ chạy thêm một lệnh nữa -- và cái cần xem là ẢNH: hộp bố cục
    # chồng lên trang, và KIE chồng lên trang. Một `compose_report.json` nói
    # trang qua cổng; chỉ con mắt nói trang có DÙNG ĐƯỢC không.
    #
    # `draw_llm` vẽ cả `html/` lẫn `rejected/`, nên tờ trượt cũng có ảnh --
    # đó là cách đọc ra model hiểu sai chỗ nào.
    if artist is not None:
        artist.close()
        if artist.why:
            # `playwright` giờ nằm cùng môi trường với bộ sinh (xem
            # `requirements.txt`). Nếu vẫn thiếu thì nói thẳng cách cài, chứ
            # đừng đi tìm một trình thông dịch khác -- hai môi trường cho một
            # đường chạy đúng là chỗ pilot7 mất sạch ảnh.
            print(f"[trang] vẽ hỏng ({artist.why}); HTML vẫn còn.\n"
                  f"  thiếu playwright thì: .venv/bin/pip install -r "
                  f"requirements.txt\n"
                  f"  rồi vẽ lại: .venv/bin/python -m synthgen.draw_llm {out}")
        elif artist.rows:
            from synthgen import draw_llm                    # noqa: PLC0415

            print(f"[trang] {len(artist.rows)} tờ đã vẽ; gộp json và KIE...")
            draw_llm.finish(out, artist.rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--want", type=int, default=30, help="số tờ")
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4,
                        help="số request gửi song song")
    parser.add_argument("--seed", type=int, default=0,
                        help="chọn phôi nào -- để phép thử lặp lại được")
    # Mặc định `en`: người dùng chốt "sửa prompt thành default tiếng anh".
    # Server chạy Qwen, tinh chỉnh theo lệnh mạnh nhất ở tiếng Anh và Trung;
    # `--lang vi` vẫn còn để so, và chỉ phép đo mới nói được bản nào hơn.
    parser.add_argument("--no-draw", action="store_true",
                        help="chỉ sinh HTML, không vẽ ảnh hộp bố cục và KIE")
    args = parser.parse_args()
    return run(args.want, args.out.resolve(),
               concurrency=args.concurrency, seed=args.seed,                no_draw=args.no_draw)


if __name__ == "__main__":
    raise SystemExit(main())
