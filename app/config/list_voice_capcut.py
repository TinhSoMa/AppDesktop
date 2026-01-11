
"""
Quản lý danh sách giọng đọc CapCut và các tiện ích liên quan.
"""

from typing import List, Dict, Optional

# Giọng mặc định (Cô gái hoạt ngôn)
DEFAULT_SPEAKER = "BV074_streaming"

# Danh sách giọng đọc
VOICE_LIST = {
    "categories": [
        {
            "name": "Tiếng Việt",
            "voices": [
                # --- Các giọng cũ ---
                {
                    "name": "Cô Gái Hoạt Ngôn",
                    "id": "BV074_streaming",
                    "gender": "female",
                    "desc": "Giọng nữ tự nhiên (Mặc định)"
                },
                {
                    "name": "Giọng bé",
                    "id": "BV074_streaming_dsp",
                    "gender": "female",
                    "desc": "Giọng nữ tự nhiên (DSP version)"
                },
                
                # --- Các giọng mới thêm ---
                {
                    "name": "Cute Female (Ngôn)",
                    "id": "BV074_streaming",
                    "gender": "female",
                    "desc": "Miễn phí (Tên khác của Cô Gái Hoạt Ngôn)"
                },
                {
                    "name": "Confident Male (Tin)",
                    "id": "BV075_streaming",
                    "gender": "male",
                    "desc": "Miễn phí"
                },
                {
                    "name": "Anh Dũng",
                    "id": "BV560_streaming",
                    "gender": "male",
                    "desc": "VIP (Pro)"
                },
                {
                    "name": "Chí Mai",
                    "id": "BV562_streaming",
                    "gender": "female",
                    "desc": "VIP (Pro)"
                },
                {
                    "name": "Giọng nữ phổ thông",
                    "id": "vi_female_huong",
                    "gender": "female",
                    "desc": "VIP (Pro)"
                },
                {
                    "name": "Sweet Little Girl",
                    "id": "BV421_vivn_streaming",
                    "gender": "female",
                    "desc": "VIP (Pro)"
                }
            ]
        }
    ]
}

def get_all_voices() -> List[Dict]:
    """Trả về danh sách phẳng tất cả các giọng đọc."""
    all_voices = []
    for category in VOICE_LIST["categories"]:
        for voice in category["voices"]:
            voice_copy = voice.copy()
            voice_copy["category"] = category["name"]
            all_voices.append(voice_copy)
    return all_voices

def get_voice_id_by_name(name: str) -> Optional[str]:
    """Lấy ID giọng đọc dựa trên tên hiển thị."""
    for category in VOICE_LIST["categories"]:
        for voice in category["voices"]:
            if voice["name"] == name:
                return voice["id"]
    return None

def get_voice_name_by_id(voice_id: str) -> Optional[str]:
    """Lấy tên giọng đọc dựa trên ID."""
    for category in VOICE_LIST["categories"]:
        for voice in category["voices"]:
            if voice["id"] == voice_id:
                return voice["name"]
    return None
