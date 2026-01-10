"""
FFmpeg Path Helper
Tự động tìm ffmpeg/ffprobe từ bundled location khi chạy .exe
hoặc từ system PATH khi chạy development
"""
import sys
import os
import subprocess
from pathlib import Path

def get_resource_path(relative_path):
    """
    Lấy đường dẫn tuyệt đối đến resource, xử lý cả runtime và development
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_ffmpeg_path():
    """
    Trả về đường dẫn đến ffmpeg.exe
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return get_resource_path(os.path.join('ffmpeg', 'ffmpeg.exe'))
    else:
        # Running as script - use system ffmpeg
        return 'ffmpeg'

def get_ffprobe_path():
    """
    Trả về đường dẫn đến ffprobe.exe
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return get_resource_path(os.path.join('ffmpeg', 'ffprobe.exe'))
    else:
        # Running as script - use system ffprobe
        return 'ffprobe'

# For easy import
FFMPEG_PATH = get_ffmpeg_path()
FFPROBE_PATH = get_ffprobe_path()

# Test if they exist
def test_ffmpeg():
    """Test if ffmpeg is accessible"""
    try:
        result = subprocess.run(
            [FFMPEG_PATH, '-version'], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        print(f"FFmpeg test failed: {e}")
        return False

if __name__ == "__main__":
    print(f"FFmpeg path: {FFMPEG_PATH}")
    print(f"FFprobe path: {FFPROBE_PATH}")
    print(f"FFmpeg exists: {os.path.exists(FFMPEG_PATH) if getattr(sys, 'frozen', False) else 'Using system PATH'}")
    print(f"FFmpeg works: {test_ffmpeg()}")
