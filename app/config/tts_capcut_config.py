class TTSCapCutConfig:
    # Cấu hình từ HAR analysis
    WS_URL = "wss://sami-normal-sg.capcutapi.com/internal/api/v1/ws"
    APPKEY = "ddjeqjLGMn"

    # Token này lấy từ HAR file (có thể cần cập nhật mới nếu hết hạn)
    # Lưu ý: Token này thường xuyên thay đổi và cần cập nhật mới khi có lỗi xác thực
    TOKEN = "BRJio1Hh2zRV6EH97c+JtDmI1cvMPTR7XaCVW1Zd3AocPgTcu0hRM4fPJiCBxfFqHRcxKu9VOJKaPP0a323zKwN+IfuVkdABzMRdMYVNdk86SG5Dn2xhXYuZIkOEdr+uvpgc/BTRUnuvs9CqA1zSQ1JhEugP/zfcLCkG7X5Mc2WXjSiGO8copxDFP5Q8KUG/SfDbX/DFqMdetjcRNGln53DYCyxRGK22sx3oBHfV6HNvGvapAj3Nw0Ejo2NfwEBb9XWAbYFctOSbmw+2yqPIdyHun90We5M5d+EGRpKhziY2kNIDgjuGute0LY3UyckqZeUZpe7BpmxUSq2+zSWWCIkk5IHISgvgVGOwTcvq8g0DTvWQffzmIXRSHbuFWKhvOWT3PvnBNnaYzWd10wI/DoaWEVBUdSHgErtrxCuDI+0rcvqShjdk5U6RfjY0zV7zXBvMPjwpAfVWvuZ30dSHT15zV73Jfcl3bBERimuM+RLESEE1HbvtrmXcSK1ICWu/JAxGKQ+7OM9V3ZyD/OchybRwZJYhNqzXR0GrW3+tIAgJ1HK4hV+QX5u7vt206RDPeDITzS6O2yqPvXT3Ni6VfFfNTOqkueu+8UjYFgP0rjshOcD36ECXPqkUlY8QVPa8dC+UECD1RClYMv4PgyeCjdsoMEUBt/8nzITcEejKfy27rOrxj4xrQjYNxTGxhb5Ztnkz77P5MNezNmYuMFiTOpFOEqa85w56ueNa2FUHLSIfcQC9500fCzY+PnuE9PlU3vkl4IZDLV+0J7RCVUFmk7iVeva0Is2zX4w6Oi7BijRn7gc7BokKlUjvIrSDWe65xvvSc4xq+y6Vkb9wNhD8sJOCKd1qoIIhoTasBy8zb47mt8Q4QzUc0UiYHW19LEzQKurbdCS1BknRYSkT/xJLx9Fc/GXqGObf4VMsLqsATIYGAY+sn0Ki8ahBkG4QlwT4/6aUFWX4Rm6SdhppBMg6cMq+l3yQ0+r6h7TbN1S6dARTtTfZUUakBze57"

    # Headers giả lập giống CapCut PC
    HEADERS = {
        "User-Agent": "Cronet/TTNetVersion:e159bc05 2022-08-16 QuicVersion:68cae75d 2021-08-12",
        "X-SS-DP": "359289"
    }

    # Cấu hình Audio mặc định (tham khảo từ file HAR)
    AUDIO_CONFIG = {
        "bit_rate": 64000,          # Bitrate mặc định: 64kbps
        "sample_rate": 24000,       # Tần số mẫu: 24kHz
        "speech_rate": 0,           # Tốc độ đọc: 0 (Bình thường). >0: Nhanh, <0: Chậm
        "enable_split": False,      # Không chia nhỏ file audio
        "enable_timestamp": False,  # Không lấy timestamp
        "format": "wav"             # Định dạng đầu ra mặc định
    }
