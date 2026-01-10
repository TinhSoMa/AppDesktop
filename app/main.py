import tkinter as tk
from tkinter import ttk
import sys
import os
import json
import logging

# Thêm thư mục gốc vào đường dẫn hệ thống để Python tìm thấy các module trong app
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# Helper function for bundled executable
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Development mode - use parent of current_dir (AppDesktop folder)
        base_path = root_dir
    return os.path.join(base_path, relative_path)

try:
    from app.ui.srt_tab import SRTTab
    from app.ui.log_tab import LogTab
    from app.core.logger import setup_logging
except ImportError:
    # Fallback
    from ui.srt_tab import SRTTab
    from ui.log_tab import LogTab
    from core.logger import setup_logging

# Default config - hardcoded trong code, không cần file json
DEFAULT_CONFIG = {
    "work_dir": "",
    "tts_config": {
        "voice": "vi-VN-NamMinhNeural",
        "rate": "+30%",
        "volume": "+30%",
        "pitch": "-3Hz"
    },
    "auto_config": {
        "draft_file": "draft_content.json",
        "split_by_lines": True,
        "lines_per_file": "100",
        "number_of_parts": "5",
        "voice": "vi-VN-NamMinhNeural",
        "rate": "+30%",
        "volume": "+30%",
        "gemini_key": "",
        "gemini_model": "gemini-3-pro-preview"
    }
}

# User config path logic removed. Using hardcoded DEFAULT_CONFIG only.

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("App Desktop - Công cụ Âm thanh & Phụ đề")
        self.root.geometry("1000x800")
        self.root.state('zoomed')
        
        # Set icon
        try:
            # Load icon from bundled resource (works for both dev and exe)
            icon_path = get_resource_path(os.path.join("app", "assets", "icon.png"))
            if os.path.exists(icon_path):
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
                logging.info(f"Icon loaded from: {icon_path}")
            else:
                logging.warning(f"Icon not found: {icon_path}")
        except Exception as e:
            logging.warning(f"Failed to set icon: {e}")
        
        # Load cấu hình
        self.config = self._load_config()
        last_work_dir = self.config.get("work_dir", os.getcwd())
        
        if not os.path.exists(last_work_dir):
            last_work_dir = os.getcwd()
            
        # Biến lưu thư mục gốc (Workspace) - load từ config
        self.work_dir = tk.StringVar(value=last_work_dir)
        
        # Thiết lập style cơ bản
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # === Top Bar: Root Directory Selection ===
        self._create_top_bar()
        

        # === Main Layout: PanedWindow (Chia dọc) ===
        self.paned_window = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. UPPER PANE: Notebook
        self.notebook = ttk.Notebook(self.paned_window)
        self.paned_window.add(self.notebook, weight=10)
        
        # --- Tab 1: SRT Tools ---
        self.srt_tab = SRTTab(self.notebook, work_dir_var=self.work_dir)
        self.notebook.add(self.srt_tab.frame, text="Công cụ SRT")

        # --- Tab 2: V7 Tools ---
        try:
            from app.ui.v7_tab import V7Tab
            self.v7_tab = V7Tab(self.notebook, work_dir_var=self.work_dir)
            self.notebook.add(self.v7_tab.get_frame(), text="Công cụ V7")
        except Exception as e:
            logging.error(f"Failed to load V7 Tab: {e}")

        
        # --- Tab 3: TTS Tools ---
        try:
            from app.ui.tts_tab import TTSTab
            tts_config = self.config.get("tts_config", {})
            self.tts_tab = TTSTab(self.notebook, work_dir_var=self.work_dir, tts_config=tts_config)
            self.notebook.add(self.tts_tab.get_frame(), text="Công cụ TTS")
        except Exception as e:
            logging.error(f"Failed to load TTS Tab: {e}")

        # --- Tab 4: Audio CapCut Merger ---
        try:
            from app.ui.audio_capcut_tab import AudioCapcutTab
            self.audio_tab = AudioCapcutTab(self.notebook, work_dir_var=self.work_dir)
            self.notebook.add(self.audio_tab.get_frame(), text="Ghép Audio")
        except Exception as e:
            logging.error(f"Failed to load AudioTab: {e}")

        # --- Tab 5: Caption Tools (Video Region) ---
        try:
            from app.ui.caption_tab import CaptionTab
            self.caption_tab = CaptionTab(self.notebook, work_dir_var=self.work_dir)
            self.notebook.add(self.caption_tab.get_frame(), text="Vùng & Hardsub")
        except Exception as e:
            logging.error(f"Failed to load CaptionTab: {e}")

        # --- Tab 6: Video Tools (Split & WAV) ---
        try:
            from app.ui.crop_video_tab import CropVideoTab
            self.crop_video_tab = CropVideoTab(self.notebook, work_dir_var=self.work_dir)
            self.notebook.add(self.crop_video_tab.frame, text="Video & WAV")
        except Exception as e:
            logging.error(f"Failed to load CropVideoTab: {e}")

        # --- Tab 7: Auto Tools ---
        try:
            from app.ui.auto_tab import AutoTab
            auto_config = self.config.get("auto_config", {})
            self.auto_tab = AutoTab(self.notebook, work_dir_var=self.work_dir, auto_config=auto_config)
            self.notebook.add(self.auto_tab.get_frame(), text="Auto Process")
        except Exception as e:
            logging.error(f"Failed to load AutoTab: {e}")
        
        # 2. LOWER PANE: Log Panel
        self.log_tab = LogTab(self.paned_window)
        self.paned_window.add(self.log_tab.frame, weight=1)
        
        # SETUP LOGGING
        setup_logging(self.log_tab)



    def _load_config(self):
        """Đọc config - Sử dụng DEFAULT_CONFIG hardcoded"""
        import copy
        logging.info("Using DEFAULT_CONFIG (Hardcoded)")
        return copy.deepcopy(DEFAULT_CONFIG)

    def _save_config(self):
        """Không lưu config ra file JSON"""
        pass
    
    def _create_top_bar(self):
        """Tạo thanh công cụ trên cùng để chọn thư mục gốc"""
        top_frame = ttk.Frame(self.root, padding="5")
        top_frame.pack(fill=tk.X, side=tk.TOP)
        
        ttk.Label(top_frame, text="Thư mục gốc:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Hiển thị đường dẫn
        dir_entry = ttk.Entry(top_frame, textvariable=self.work_dir, width=60)
        dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Nút chọn
        ttk.Button(
            top_frame, 
            text="Chọn thư mục", 
            command=self._select_work_dir
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', pady=0)

    def _select_work_dir(self):
        from tkinter import filedialog
        selected_dir = filedialog.askdirectory(
            title="Chọn thư mục gốc (Workspace)", 
            initialdir=self.work_dir.get()
        )
        if selected_dir:
            self.work_dir.set(selected_dir)
            self.config["work_dir"] = selected_dir
            logging.info(f"Directory changed: {selected_dir} (Not saved to disk)")


def main():
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
