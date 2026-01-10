"""
Translation Prompt Template - Embedded in Python for EXE bundling
Thay thế file translation-prompt.json
"""

# Default prompt template as Python dict
DEFAULT_PROMPT_TEMPLATE = {
    "task": "subtitle_translation_{{FILE_NAME}}",
    "source_text": {
        "language": "việt",
        "total_lines": "{{COUNT}}",
        "content": "{{CONTENT_ARRAY}}"
    },
    "instructions": {
        "primary_goal": "Dịch chính xác 100% số lượng câu subtitle từ tiếng Trung sang tiếng Việt",
        "critical_rules": [
            "QUY TẮC TUYỆT ĐỐI #1: Input có {{COUNT}} câu → Output PHẢI CÓ CHÍNH XÁC {{COUNT}} câu. Đếm lại trước khi trả về!",
            "QUY TẮC TUYỆT ĐỐI #2: 1 câu input = 1 câu output. KHÔNG tách, KHÔNG gộp câu",
            "QUY TẮC TUYỆT ĐỐI #3: Chỉ trả về bản dịch thuần túy, không có bất kỳ nội dung nào khác",
            "Format output: |Câu1|Câu2|Câu3|...|Câu{{COUNT}}| (tất cả trên một dòng, không xuống dòng)",
            "Không thêm câu hỏi, gợi ý, nhận xét, lời giới thiệu hay kết thúc"
        ],
        "translation_guidelines": {
            "style": "Dịch thuần Việt, mạch lạc, tự nhiên như lời thoại",
            "terminology": "Danh từ riêng để Hán Việt",
            "pronouns": "Chú ý cách xưng hô phù hợp ngữ cảnh",
            "word_limit": "Số từ tiếng Việt không vượt quá số từ tiếng Trung + 3 từ mỗi câu",
            "tone": "Có thể điều chỉnh cho hài hước, sinh động nếu phù hợp, nhưng giữ nguyên ý nghĩa",
            "modern_language": {
                "allowed": True,
                "description": "Có thể sử dụng từ ngữ GenZ/mạng phổ biến khi phù hợp ngữ cảnh",
                "examples": [
                    "vãi, xịn, ngon, đỉnh, ơ mây zing, ghê, chất, flex, chill, mood, slay",
                    "bá đạo, troll, drama, fake, real, vibe, crush, ship, toxic",
                    "đỉnh cao, xịn sò, bá cháy, quá trời, căng đét, lố bịch"
                ],
                "usage_guidelines": [
                    "Chỉ dùng khi phù hợp với cảm xúc/tình huống của câu",
                    "Không lạm dụng, giữ sự tự nhiên",
                    "Ưu tiên dùng cho các tình huống cảm thán, ngạc nhiên, khen ngợi, châm chọc",
                    "Tránh dùng trong ngữ cảnh nghiêm túc hoặc trang trọng"
                ]
            }
        },
        "consistency_requirements": [
            "Thống nhất tên nhân vật xuyên suốt",
            "Thống nhất các danh từ được sử dụng lại",
            "Phân tích rõ ràng các nhân vật trong nội dung",
            "Thống nhất phong cách từ ngữ GenZ nếu có sử dụng"
        ],
        "formatting": {
            "separator": "|",
            "structure": "Bắt đầu bằng |, kết thúc bằng |, mỗi câu ngăn cách bằng |",
            "single_line": "Tất cả trên một dòng liên tục, không xuống dòng",
            "example": "|Câu dịch 1|Câu dịch 2|Câu dịch 3|...|Câu dịch {{COUNT}}|",
            "prohibited": [
                "Không xuống dòng (line break)",
                "Không chèn ghi chú hoặc đánh giá",
                "Không thêm ký tự đặc biệt không cần thiết"
            ]
        },
        "output_requirements": {
            "format": "Một dòng duy nhất: |Câu1|Câu2|...|Câu{{COUNT}}|",
            "verification": "Trước khi trả về, đếm số câu để đảm bảo = {{COUNT}}",
            "pure_translation_only": "Chỉ bản dịch, không có nội dung khác"
        }
    },
    "execution_mode": "silent",
    "response_format": "|Câu1|Câu2|Câu3|...|Câu{{COUNT}}|"
}


def get_prompt_template() -> dict:
    """
    Lấy prompt template.
    Returns prompt đã được nhúng trong code Python.
    """
    return DEFAULT_PROMPT_TEMPLATE.copy()


def get_prompt_as_json_string() -> str:
    """
    Lấy prompt template dưới dạng JSON string.
    """
    import json
    return json.dumps(DEFAULT_PROMPT_TEMPLATE, ensure_ascii=False, indent=4)
