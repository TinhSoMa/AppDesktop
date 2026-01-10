import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

import logging

try:
    from app.ui.components.file_combobox import FileCombobox
    import app.core.v7_funtion as v7_core
except ImportError:
    from ui.components.file_combobox import FileCombobox
    import core.v7_funtion as v7_core

class V7Tab:
    """Tab V7 Tools - Xử lý nâng cao CapCut Draft (JSON)"""
    
    def __init__(self, parent, work_dir_var=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.frame = ttk.Frame(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Main Content Frame
        main_content = ttk.Frame(self.frame, padding="10")
        main_content.pack(fill=tk.BOTH, expand=True)

        # 2. Input Section
        input_frame = ttk.LabelFrame(main_content, text="Chọn Draft Content JSON", padding="10")
        input_frame.pack(fill='x', pady=5)
        
        ttk.Label(input_frame, text="File Draft:", width=12).pack(side=tk.LEFT)
        self.draft_json_var = tk.StringVar(value="draft_content.json") 
        
        self.combo_draft = FileCombobox(
            input_frame, 
            self.work_dir_var, 
            ['.json'], 
            textvariable=self.draft_json_var, 
            width=60
        )
        self.combo_draft.pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="Browse", command=self._browse_json).pack(side=tk.LEFT)

        # 3. Actions Sections
        
        # --- Group 1: Export Tools ---
        grp_export = ttk.LabelFrame(main_content, text="Công cụ Xuất", padding="10")
        grp_export.pack(fill='x', pady=5)
        
        ttk.Button(grp_export, text="Xuất CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_export, text="Xuất SRT", command=self.export_srt).pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_export, text="Xuất CN (Giới hạn)", command=self.export_cn_limit).pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_export, text="Xuất Tên Audio", command=self.export_audio_names).pack(side=tk.LEFT, padx=5)

        # --- Group 2: Excel Tools (Import/Edit) ---
        grp_excel = ttk.LabelFrame(main_content, text="Công cụ Excel (Thay thế / Chia)", padding="10")
        grp_excel.pack(fill='x', pady=5)
        
        ttk.Label(grp_excel, text="File Excel:").pack(side=tk.LEFT)
        self.excel_path_var = tk.StringVar()
        self.combo_excel = FileCombobox(grp_excel, self.work_dir_var, ['.xlsx'], textvariable=self.excel_path_var, width=40)
        self.combo_excel.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(grp_excel, text="Thay thế Text", command=self.replace_text_excel).pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_excel, text="Chia Text theo Ký tự", command=self.split_text_by_char).pack(side=tk.LEFT, padx=5)

        # --- Group 3: Apply Style & Timing ---
        grp_timing = ttk.LabelFrame(main_content, text="Style & Thời gian", padding="10")
        grp_timing.pack(fill='x', pady=5)
        
        # Apply Style
        ttk.Button(grp_timing, text="Áp dụng Style (Toàn bộ)", command=self.apply_style).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(grp_timing, orient='vertical').pack(side=tk.LEFT, fill='y', padx=10)
        
        # Split SRT
        ttk.Label(grp_timing, text="SRT File:").pack(side=tk.LEFT)
        self.srt_path_var = tk.StringVar()
        self.combo_srt = FileCombobox(grp_timing, self.work_dir_var, ['.srt'], textvariable=self.srt_path_var, width=25)
        self.combo_srt.pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_timing, text="Cắt Video theo SRT", command=self.split_video_srt).pack(side=tk.LEFT)

        # --- Group 4: Advanced Sync ---
        grp_sync = ttk.LabelFrame(main_content, text="Đồng bộ Nâng cao (Tốc độ Video)", padding="10")
        grp_sync.pack(fill='x', pady=5)
        
        ttk.Label(grp_sync, text="Index Video Bắt đầu:").pack(side=tk.LEFT)
        self.vid_idx = tk.StringVar(value="0")
        ttk.Entry(grp_sync, textvariable=self.vid_idx, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(grp_sync, text="Đồng bộ Tốc độ Video theo Audio", command=self.sync_video_audio).pack(side=tk.LEFT, padx=5)

    # ===== Helpers =====
    def _get_work_dir(self):
        return self.work_dir_var.get() if self.work_dir_var else os.getcwd()

    def _browse_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], initialdir=self._get_work_dir())
        if f: self.draft_json_var.set(f)
        
    def _check_file(self, path):
        if not path or not os.path.exists(path):
            msg = f"File không tồn tại: {path}"
            logging.warning(msg)
            return False
        return True

    def get_frame(self):
        return self.frame

    # ===== Actions =====
    
    def export_csv(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        
        logging.info(f"Bắt đầu Export CSV từ: {json_path}")
        if v7_core.v7_export_csv_from_draft_logic(json_path, self._get_work_dir()):
            msg = f"Đã xuất CSV/Excel tại: {self._get_work_dir()}"
            logging.info(msg)
        else: 
            logging.error("Lỗi khi xuất CSV. Xem chi tiết ở trên.")

    def export_srt(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        
        output_path = json_path.replace(".json", ".srt")
        logging.info(f"Bắt đầu Export SRT từ: {json_path} -> {output_path}")
        
        if v7_core.v7_export_to_srt(json_path, output_path):
             msg = f"Đã xuất SRT: {output_path}"
             logging.info(msg)
        else: 
            logging.error("Lỗi khi xuất SRT.")

    def export_cn_limit(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        
        logging.info("Bắt đầu Export CN (Limit)...")
        if v7_core.v7_export_cn_with_limit_logic(json_path, self._get_work_dir()):
            msg = "Đã xuất captions_cn_limit.txt"
            logging.info(msg)
        else: 
            logging.error("Lỗi khi xuất CN Limit.")

    def export_audio_names(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        
        logging.info("Bắt đầu Export Audio Names...")
        res = v7_core.v7_find_idSubtile_and_nameAudio_sort(json_path, self._get_work_dir())
        if res: 
            msg = f"Đã xuất danh sách audio:\n{res}"
            logging.info(msg)
        else: 
            logging.error("Lỗi khi xuất Audio Names.")

    def replace_text_excel(self):
        json_path = self.combo_draft.get_full_path()
        xlsx_path = self.combo_excel.get_full_path()
        if not self._check_file(json_path) or not self._check_file(xlsx_path): return
        
        logging.info(f"Bắt đầu Replace Text từ Excel: {xlsx_path}")
        if v7_core.v7_replace_text_from_xlsx_logic(json_path, xlsx_path):
            logging.info("Thay thế text thành công!")
        else: 
            logging.error("Lỗi khi Replace Text.")

    def split_text_by_char(self):
        json_path = self.combo_draft.get_full_path()
        xlsx_path = self.combo_excel.get_full_path()
        if not self._check_file(json_path) or not self._check_file(xlsx_path): return
        
        logging.info(f"Bắt đầu Split Text theo Character từ Excel: {xlsx_path}")
        if v7_core.v7_split_by_character_logic(json_path, xlsx_path):
            logging.info("Đã chia text thành các track theo nhân vật!")
        else: 
            logging.error("Lỗi khi Split Text.")

    def apply_style(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        
        logging.info("Bắt đầu Apply Style...")
        if v7_core.v7_apply_style_logic(json_path):
            logging.info("Apply style thành công!")
        else: 
            logging.error("Lỗi khi Apply Style.")

    def split_video_srt(self):
        json_path = self.combo_draft.get_full_path()
        srt_path = self.combo_srt.get_full_path()
        if not self._check_file(json_path) or not self._check_file(srt_path): return
        
        logging.info(f"Bắt đầu Split Video theo SRT: {srt_path}")
        if v7_core.v7_split_video_by_srt_logic(json_path, srt_path):
            logging.info("Chia video thành công!")
        else: 
            logging.error("Lỗi khi Split Video.")
             
    def sync_video_audio(self):
        json_path = self.combo_draft.get_full_path()
        if not self._check_file(json_path): return
        try: idx = int(self.vid_idx.get())
        except: 
            logging.error("Index phải là số")
            return
        
        logging.info(f"Bắt đầu Sync Video (Start Index: {idx})...")
        if v7_core.v7_sync_video_audio_logic(json_path, idx):
            logging.info("Sync Video-Audio thành công!")
        else: 
            logging.error("Lỗi khi Sync Video.")
