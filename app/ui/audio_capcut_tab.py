import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import logging
import json
import subprocess
from app.ui.components.file_combobox import FileCombobox
import app.core.v7_funtion as v7_core
import app.core.tts_funtion as tts_core

class AudioCapcutTab:
    """Tab Audio - Merger & Sync (CapCut)"""
    
    def __init__(self, parent, work_dir_var=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.frame = ttk.Frame(parent)
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()
        
    def setup_ui(self):
        main_content = ttk.Frame(self.frame, padding="10")
        main_content.pack(fill=tk.BOTH, expand=True)

        # --- 1. Khu vực nhập liệu (Input) ---
        grp_input = ttk.LabelFrame(main_content, text="Dữ liệu đầu vào", padding="10")
        grp_input.pack(fill='x', pady=5)
        
        # SRT File
        ttk.Label(grp_input, text="File SRT:").grid(row=0, column=0, sticky='w')
        self.srt_path_var = tk.StringVar()
        self.combo_srt = FileCombobox(grp_input, self.work_dir_var, ['.srt'], textvariable=self.srt_path_var, width=50)
        self.combo_srt.grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Duyệt...", command=self._browse_srt).grid(row=0, column=2, padx=5)

        # Audio Folder -> Chọn thư mục chứa file audio lẻ (vd: output từ Tab TTS)
        ttk.Label(grp_input, text="Thư mục Audio:").grid(row=1, column=0, sticky='w')
        self.audio_dir_var = tk.StringVar()
        self.entry_audio_dir = ttk.Entry(grp_input, textvariable=self.audio_dir_var, width=53)
        self.entry_audio_dir.grid(row=1, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Chọn Thư mục", command=self._browse_audio_dir).grid(row=1, column=2, padx=5)

        # Audio List File (Optional)
        ttk.Label(grp_input, text="Danh sách Audio:").grid(row=2, column=0, sticky='w')
        self.audio_list_var = tk.StringVar(value="audio_names_sorted.txt")
        self.combo_list = FileCombobox(grp_input, self.work_dir_var, ['.txt'], textvariable=self.audio_list_var, width=50)
        self.combo_list.grid(row=2, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Duyệt...", command=self._browse_list).grid(row=2, column=2, padx=5)

        # Draft Content JSON (Cho chức năng Sort)
        ttk.Label(grp_input, text="File Draft JSON:").grid(row=3, column=0, sticky='w')
        self.json_path_var = tk.StringVar(value="draft_content.json")
        self.combo_json = FileCombobox(grp_input, self.work_dir_var, ['.json'], textvariable=self.json_path_var, width=50)
        self.combo_json.grid(row=3, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Duyệt...", command=self._browse_json).grid(row=3, column=2, padx=5)

        # --- 2. Cấu hình (Settings) ---
        grp_config = ttk.LabelFrame(main_content, text="Cấu hình", padding="10")
        grp_config.pack(fill='x', pady=5)
        
        # Output Filename
        ttk.Label(grp_config, text="Tên file Output:").grid(row=0, column=0, sticky='w')
        self.out_name_var = tk.StringVar(value="output_merged.mp3")
        ttk.Entry(grp_config, textvariable=self.out_name_var, width=30).grid(row=0, column=1, padx=5, sticky='w')
        
        # Format (Hiển thị thôi, core dùng ffmpeg)
        ttk.Label(grp_config, text="Lưu ý: File output sẽ được lưu cùng cấp với thư mục Audio (Parent Folder)").grid(row=1, column=0, columnspan=3, sticky='w', pady=2)

        # --- 3. Actions ---
        grp_action = ttk.LabelFrame(main_content, text="Thao tác", padding="10")
        grp_action.pack(fill='x', pady=5)
        
        self.btn_analyze = ttk.Button(grp_action, text="Kiểm tra số lượng", command=self.analyze_files)
        self.btn_analyze.pack(side=tk.LEFT, padx=5)
        
        self.btn_merge = ttk.Button(grp_action, text="Ghép Audio (theo SRT)", command=self.run_merge)
        self.btn_merge.pack(side=tk.LEFT, padx=5)
        
        self.btn_sort = ttk.Button(grp_action, text="Trích xuất tên Audio (JSON)", command=self.run_sort_names)
        self.btn_sort.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(grp_action, text="Dừng lại", command=self.stop_processing, state='disabled')
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Status
        self.lbl_status = ttk.Label(grp_action, text="Sẵn sàng", foreground="blue")
        self.lbl_status.pack(side=tk.LEFT, padx=20)
        
    def get_frame(self):
        return self.frame

    def _get_work_dir(self):
        return self.work_dir_var.get() if self.work_dir_var else os.getcwd()

    # --- Browse Handlers ---
    def _browse_srt(self):
        f = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")], initialdir=self._get_work_dir())
        if f: self.srt_path_var.set(f)

    def _browse_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], initialdir=self._get_work_dir())
        if f: self.json_path_var.set(f)

    def _browse_audio_dir(self):
        d = filedialog.askdirectory(initialdir=self._get_work_dir(), title="Chọn thư mục chứa Audio lẻ")
        if d: self.audio_dir_var.set(d)

    def _browse_list(self):
        f = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")], initialdir=self._get_work_dir())
        if f: self.audio_list_var.set(f)

    # --- UI Status ---
    def set_running(self, running: bool):
        self.is_running = running
        if running:
            self.stop_event.clear()
            self.lbl_status.config(text="Đang xử lý...", foreground="red")
        else:
            self.lbl_status.config(text="Hoàn tất / Chờ", foreground="green")
            
        state = 'disabled' if running else 'normal'
        stop_state = 'normal' if running else 'disabled'
        
        self.btn_analyze.config(state=state)
        self.btn_merge.config(state=state)
        self.btn_sort.config(state=state)
        self.btn_stop.config(state=stop_state)

    def stop_processing(self):
        if self.is_running:
            logging.warning("User requested STOP...")
            self.stop_event.set()

    # --- Logic ---

    def analyze_files(self):
        """Kiểm tra số lượng câu trong SRT vs số file Audio"""
        srt_path = self.combo_srt.get_full_path()
        audio_dir = self.audio_dir_var.get()
        
        if not srt_path or not os.path.exists(srt_path):
            logging.warning("SRT file không hợp lệ!")
            return
        if not audio_dir or not os.path.exists(audio_dir):
            logging.warning("Audio Folder không hợp lệ!")
            return
            
        try:
            # 1. Parse SRT
            entries = tts_core.parse_srt_file(srt_path)
            srt_count = len(entries)
            
            # 2. Scan audio files (mp3/wav)
            files = [f for f in os.listdir(audio_dir) if f.lower().endswith(('.mp3', '.wav'))]
            audio_count = len(files)
            
            logging.info(f"--- Analysis ---")
            logging.info(f"SRT Entries: {srt_count}")
            logging.info(f"Audio Files: {audio_count}")
            
            if srt_count == audio_count:
                logging.info("Số lượng khớp nhau!")
                logging.info(f"Kết quả: Đủ file ({audio_count} files). Khớp với số lượng phụ đề SRT.")
            else:
                logging.warning(f"Số lượng LỆCH! (SRT: {srt_count} vs Audio: {audio_count})")
                
        except Exception as e:
            logging.error(f"Analysis error: {e}")

    def run_merge(self):
        if self.is_running: return
        self.set_running(True)
        threading.Thread(target=self._task_merge, daemon=True).start()

    def _task_merge(self):
        try:
            srt_path = self.combo_srt.get_full_path()
            audio_dir = self.audio_dir_var.get()
            out_name = self.out_name_var.get()
            
            if not srt_path or not os.path.exists(srt_path):
                logging.error("Chưa chọn file SRT")
                return
            if not audio_dir or not os.path.exists(audio_dir):
                logging.error("Chưa chọn Audio Folder")
                return
            
            # Output saved up one level
            parent_dir = os.path.dirname(audio_dir)
            if parent_dir and os.path.exists(parent_dir):
                 output_path = os.path.join(parent_dir, out_name)
            else:
                 output_path = os.path.join(audio_dir, out_name)
            output_path = os.path.normpath(output_path)
            
            logging.info(f"Bắt đầu ghép Audio...\nSRT: {srt_path}\nFolder: {audio_dir}\nOutput: {output_path}")
            
            # 1. Parse SRT để lấy timing
            entries = tts_core.parse_srt_file(srt_path)
            if not entries:
                logging.error("SRT rỗng.")
                return

            # 2. Match SRT entries với Audio files
            # Logic mới: Nếu có file Audio List, dùng danh sách đó để match theo thứ tự
            # Nếu không, dùng logic cũ (match theo index ở đầu tên file)
            audio_list_path = self.combo_list.get_full_path()
            use_list_file = False
            audio_lines = []
            
            if audio_list_path and os.path.exists(audio_list_path):
                 try:
                     with open(audio_list_path, 'r', encoding='utf-8') as f:
                         audio_lines = [l.strip() for l in f.readlines() if l.strip()]
                     if audio_lines:
                         use_list_file = True
                         logging.info(f"Sử dụng danh sách file audio từ: {audio_list_path} ({len(audio_lines)} dòng)")
                 except Exception as e:
                     logging.warning(f"Không đọc được file list: {e}")

            files_to_merge = []
            missing = []

            if use_list_file:
                 # Match theo thứ tự: Entry #1 <-> Line #1
                 # SRT entries đã được sort theo index chưa? Helper trả về list sorted? -> Có, thường là vậy.
                 # Nhưng để chắc ăn, sort entries theo index
                 entries.sort(key=lambda x: x.index)
                 
                 for i, entry in enumerate(entries):
                     if i < len(audio_lines):
                         fname = audio_lines[i]
                         # Nếu trong list chỉ là tên file, cần join với audio_dir
                         # Nếu là đường dẫn tuyệt đối thì thôi
                         if os.path.isabs(fname):
                             path = fname
                         else:
                             path = os.path.join(audio_dir, fname)
                         
                         # Check exist (Try extensions if not found)
                         final_path = None
                         if os.path.exists(path):
                             final_path = path
                         else:
                             # Try adding extensions
                             for ext in ['.wav', '.mp3', '.m4a', '.aac']:
                                 p = path + ext
                                 if os.path.exists(p):
                                     final_path = p
                                     break
                         
                         if final_path:
                             files_to_merge.append((final_path, entry.start_ms))
                         else:
                             logging.warning(f"Audio file not found (tried extensions): {path}")
                             missing.append(entry.index)
                     else:
                         missing.append(entry.index)
            else:
                # Logic cũ
                scanned_files = os.listdir(audio_dir)
                files_map = {} # Mapping Index -> Filename
                
                # Scan folder để build map index -> path
                for fname in scanned_files:
                    if not fname.lower().endswith(('.mp3', '.wav')): continue
                    # Regex tìm số ở đầu: "001_abc" -> 1
                    m = tts_core.re.match(r'^(\d+)_', fname)
                    if m:
                        idx = int(m.group(1))
                        files_map[idx] = os.path.join(audio_dir, fname)
                
                for entry in entries:
                    if entry.index in files_map:
                        path = files_map[entry.index]
                        files_to_merge.append((path, entry.start_ms))
                    else:
                        missing.append(entry.index)
            
            if missing:
                logging.warning(f"Thiếu audio cho các dòng sub: {missing}")
                if len(missing) > len(entries) * 0.5:
                    logging.error("Thiếu quá nhiều file (>50%). Hủy ghép.")
                    return
            
            if missing:
                logging.warning(f"⚠️ Thiếu audio cho các dòng sub: {missing}")
                if len(missing) > len(entries) * 0.5:
                    logging.error("Thiếu quá nhiều file (>50%). Hủy ghép.")
                    return
            
            if not files_to_merge:
                logging.error("Không tìm thấy cặp audio nào khớp.")
                return

            # 3. Call ffmpeg merge logic (tận dụng hàm có sẵn bên tts_core)
            # Hàm này đã hỗ trợ stop_event
            success = tts_core.merge_audio_files_ffmpeg(files_to_merge, output_path, stop_event=self.stop_event)
            
            if success:
                logging.info(f"Ghép thành công: {output_path}")
            else:
                logging.error("Ghép thất bại.")
                
        except Exception as e:
            logging.error(f"Merge error: {e}")
        finally:
            self.parent.after(0, lambda: self.set_running(False))

    def run_sort_names(self):
        """Sắp xếp tên file audio dựa trên JSON draft"""
        if self.is_running: return
        self.set_running(True)
        threading.Thread(target=self._task_sort, daemon=True).start()

    def _task_sort(self):
        try:
            json_path = self.combo_json.get_full_path()
            if not json_path or not os.path.exists(json_path):
                logging.error("Chưa chọn file JSON Draft.")
                return
            
            # Hàm v7_find_idSubtile_and_nameAudio_sort trả về path file text hoặc False
            # Mặc định nó xuất ra work_dir
            logging.info("Đang trích xuất và sắp xếp tên audio...")
            res = v7_core.v7_find_idSubtile_and_nameAudio_sort(json_path, self._get_work_dir())
            
            if res:
                logging.info(f"Đã xuất danh sách audio sorted: {res}")
            else:
                logging.error("Lỗi khi sort audio names.")
                
        except Exception as e:
            logging.error(f"Sort error: {e}")
        finally:
            self.parent.after(0, lambda: self.set_running(False))
