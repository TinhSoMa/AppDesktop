import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import logging
from app.ui.components.file_combobox import FileCombobox
from app.core import auto_funtion
try:
    from app.ui.tts_tab import VOICES
except ImportError:
    # Fallback if import fails
    VOICES = [
        "vi-VN-HoaiMyNeural",
        "vi-VN-NamMinhNeural",
        "en-US-AriaNeural",
        "en-US-GuyNeural",
        "zh-CN-XiaoxiaoNeural",
    ]

# Danh sách Model Gemini (2025)
GEMINI_MODELS = [
    # 1. Nhóm chủ lực (Khuyên dùng)
    "gemini-3-flash-preview",  # Thông minh, dịch sâu (15 RPM)
    "gemini-2.5-flash",        # Ổn định, nhanh (15 RPM)
    
    # 2. Nhóm chất lượng cao (Đoạn khó)
    "gemini-3-pro-preview",    # Thông minh nhất, người thật (2-5 RPM)
    "gemini-2.5-pro",          # Xử lý ngữ cảnh dài (2-5 RPM)
    
    # 3. Nhóm dự phòng
    "gemini-2.0-flash",        # Dự phòng nhanh
    "gemini-2.5-flash-lite",   # Tiết kiệm
]

DEFAULT_PROMPT = """{
    "task": "subtitle_translation_{{FILE_NAME}}",
    "source_text": {
        "language": "Chinese",
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
                "allowed": true,
                "description": "Có thể sử dụng từ ngữ GenZ/mạng phổ biến khi phù hợp ngữ cảnh",
                "examples": [
                    "vãi, xịn, ngon, đỉnh, ơ mây zing, ghê, chất, flex, chill, mood, slay",
                    "bá đạo, troll, drama, fake, real, vibe, crush, ship, toxic",
                    "đỉnh cao, xịn sò, bá cháy, quá trời, căng đét, lố bịch"
                ],
                "usage_guidelines": [
                    "Chỉ dùng khi phù hợp với cảm xúc/tình huống của câu",
                    "Không lạm dụng, giữ sự tự nhiên",
                    "Tránh dùng từ lóng quá khó hiểu hoặc phản cảm"
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
}"""

class AutoTab:
    """Tab Auto - Tự động hóa quy trình (Non-functional UI)"""
    
    def __init__(self, parent, work_dir_var=None, auto_config=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.auto_config = auto_config or {}
        self.frame = ttk.Frame(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # Load config defaults
        defaults = {
            "draft_file": self.auto_config.get("draft_file", "draft_content.json"),
            "split_by_lines": self.auto_config.get("split_by_lines", True),
            "lines_per_file": self.auto_config.get("lines_per_file", "100"),
            "number_of_parts": self.auto_config.get("number_of_parts", "5"),
            # TTS Config
            "voice": self.auto_config.get("voice", "vi-VN-NamMinhNeural"),
            "rate": self.auto_config.get("rate", "+30%"),
            "volume": self.auto_config.get("volume", "+30%"),
            # Gemini Config
            "gemini_model": self.auto_config.get("gemini_model", "gemini-3-pro-preview"),
        }
        logging.info(f"Auto Tab loaded with config: {defaults}")

        # Main Layout: Split into Left and Right Panels
        self.paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Container for Left Panel
        self.left_container = ttk.Frame(self.paned)
        self.paned.add(self.left_container, weight=3)

        # Container for Right Panel
        self.right_container = ttk.Frame(self.paned)
        self.paned.add(self.right_container, weight=2)

        # Build UI content
        self.setup_left_panel(self.left_container, defaults)
        self.setup_right_panel(self.right_container)

    def setup_left_panel(self, parent, defaults):
        """Panel bên trái: Cấu hình chung + TTS"""
        
        # Scrollable wrapper could be added here if needed, keeping it simple for now
        main_content = ttk.Frame(parent, padding="5")
        main_content.pack(fill=tk.BOTH, expand=True)

        # --- Section 1: Chọn File Draft ---
        input_frame = ttk.LabelFrame(main_content, text="1. Chọn Draft Content JSON", padding="8")
        input_frame.pack(fill='x', pady=4)
        
        ttk.Label(input_frame, text="File Draft:", width=12).pack(side=tk.LEFT)
        self.draft_json_var = tk.StringVar(value=defaults["draft_file"]) 
        
        self.combo_draft = FileCombobox(
            input_frame, 
            self.work_dir_var, 
            ['.json'], 
            textvariable=self.draft_json_var, 
            width=40
        )
        self.combo_draft.pack(side=tk.LEFT, padx=5, fill='x', expand=True)
        ttk.Button(input_frame, text="Browse", command=self._browse_json).pack(side=tk.LEFT)

        # --- Section 2: Cấu hình Chia Text ---
        split_frame = ttk.LabelFrame(main_content, text="2. Cấu hình chia nhỏ Text", padding="8")
        split_frame.pack(fill='x', pady=4)
        
        self.split_by_lines = tk.BooleanVar(value=defaults["split_by_lines"])
        
        # Option A: Chia theo số dòng
        ttk.Radiobutton(split_frame, text="Số dòng/file:", variable=self.split_by_lines, value=True).pack(side=tk.LEFT)
        self.lines_per_file = tk.StringVar(value=defaults["lines_per_file"])
        ttk.Combobox(split_frame, textvariable=self.lines_per_file, values=["50", "100", "200", "500"], width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(split_frame, text="dòng").pack(side=tk.LEFT)
        
        ttk.Label(split_frame, text="|").pack(side=tk.LEFT, padx=15)
        
        # Option B: Chia theo số phần
        ttk.Radiobutton(split_frame, text="Số phần:", variable=self.split_by_lines, value=False).pack(side=tk.LEFT)
        self.number_of_parts = tk.StringVar(value=defaults["number_of_parts"])
        ttk.Entry(split_frame, textvariable=self.number_of_parts, width=6).pack(side=tk.LEFT, padx=2)        
        ttk.Label(split_frame, text="phần").pack(side=tk.LEFT)

        # --- Section 3: Cấu hình Model Use (Moved from old Section 3) ---
        gemini_frame = ttk.LabelFrame(main_content, text="3. Cấu hình Gemini Model", padding="8")
        gemini_frame.pack(fill='x', pady=4)
        
        ttk.Label(gemini_frame, text="Model:").pack(side=tk.LEFT)
        self.gemini_model_var = tk.StringVar(value=defaults["gemini_model"])
        ttk.Combobox(gemini_frame, textvariable=self.gemini_model_var, values=GEMINI_MODELS, width=25).pack(side=tk.LEFT, padx=5)
        
        # Thuật toán Quét Ngang không cần đa luồng
        self.threads_var = tk.StringVar(value="1")

        # --- Section 4: Cấu hình TTS ---
        tts_frame = ttk.LabelFrame(main_content, text="4. Cấu hình Giọng đọc (TTS)", padding="8")
        tts_frame.pack(fill='x', pady=4)
        
        # Rows using grid for alignment
        f_tts = ttk.Frame(tts_frame)
        f_tts.pack(fill='x')
        
        ttk.Label(f_tts, text="Giọng đọc:").grid(row=0, column=0, sticky='w', pady=2)
        self.voice_var = tk.StringVar(value=defaults["voice"])
        ttk.Combobox(f_tts, textvariable=self.voice_var, values=VOICES, width=30).grid(row=0, column=1, padx=5, sticky='w')
        
        ttk.Label(f_tts, text="Tốc độ:").grid(row=0, column=2, sticky='w', padx=(10, 2))
        self.rate_var = tk.StringVar(value=defaults["rate"])
        ttk.Entry(f_tts, textvariable=self.rate_var, width=8).grid(row=0, column=3, sticky='w')
        
        ttk.Label(f_tts, text="Âm lượng:").grid(row=0, column=4, sticky='w', padx=(10, 2))
        self.vol_var = tk.StringVar(value=defaults["volume"])
        ttk.Entry(f_tts, textvariable=self.vol_var, width=8).grid(row=0, column=5, sticky='w')
        
        ttk.Label(f_tts, text="Tốc độ SRT:").grid(row=0, column=6, sticky='w', padx=(10, 2))
        self.speed_factor_var = tk.StringVar(value="1.0")
        speed_spinbox = ttk.Spinbox(f_tts, from_=1.0, to=2.0, increment=0.1, textvariable=self.speed_factor_var, width=5)
        speed_spinbox.grid(row=0, column=7, sticky='w')

        # Button Config
        btn_frame = ttk.Frame(main_content, padding="8")
        btn_frame.pack(fill='x', pady=4)
        
        ttk.Button(btn_frame, text="Lưu cấu hình", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Tải mặc định", command=self.load_default_config).pack(side=tk.LEFT, padx=5)
        
        # --- Section 5: Điều khiển Chạy ---
        run_frame = ttk.LabelFrame(main_content, text="5. Tùy chọn Chạy & Tiến độ", padding="8")
        run_frame.pack(fill='x', pady=4)
        
        # Variables for Checkboxes
        self.step_vars = {}
        
        # Checkboxes for Steps (Horizontal Layout)
        step_frame = ttk.Frame(run_frame)
        step_frame.pack(fill='x', pady=5)
        
        steps = [
            (1, "1. Input"),
            (2, "2. Split"),
            (3, "3. Dịch"),
            (4, "4. TTS")
        ]
        
        for val, text in steps:
            var = tk.BooleanVar(value=True) # Default checked
            self.step_vars[val] = var
            ttk.Checkbutton(step_frame, text=text, variable=var).pack(side=tk.LEFT, padx=10)

        # Progress/Status Label (Placed below radios)
        self.lbl_progress = ttk.Label(run_frame, text="Trạng thái: Sẵn sàng", foreground="blue", font=("Segoe UI", 9, "italic"))
        self.lbl_progress.pack(anchor='w', padx=5, pady=5)

        # Buttons Frame (Start & Stop)
        btn_run_frame = ttk.Frame(run_frame)
        btn_run_frame.pack(fill='x', pady=5)
        
        self.btn_run = ttk.Button(btn_run_frame, text="▶ BẮT ĐẦU", command=self._on_run_click)
        self.btn_run.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        
        self.btn_stop = ttk.Button(btn_run_frame, text="⏹ DỪNG LẠI", state='disabled')
        self.btn_stop.pack(side=tk.LEFT, fill='x', expand=True)

    def _on_run_click(self):
        selected = [k for k, v in self.step_vars.items() if v.get()]
        selected.sort()
        
        if not selected:
            self.lbl_progress.config(text="Hãy chọn ít nhất 1 bước để chạy!", foreground="red")
            return
            
        # Validate if multiple steps selected
        if len(selected) > 1:
            # Rule: Must start from step 1 and be consecutive
            # Valid: [1], [1,2], [1,2,3], [1,2,3,4]
            # Invalid: [2,3], [1,3], [2,3,4], etc.
            
            if selected[0] != 1:
                self.lbl_progress.config(text="Lỗi: Khi chọn nhiều bước, phải bắt đầu từ Bước 1!", foreground="red")
                return
            
            # Check consecutive
            is_consecutive = all(selected[i+1] - selected[i] == 1 for i in range(len(selected) - 1))
            
            if not is_consecutive:
                self.lbl_progress.config(text="Lỗi: Các bước phải liên tiếp (1→2→3→4)!", foreground="red")
                return

        self.lbl_progress.config(text=f"Đang xử lý các bước: {selected}...", foreground="orange")
        self.frame.update_idletasks()  # Refresh UI
        
        # Disable buttons during execution
        self.btn_run.config(state='disabled')
        self.btn_stop.config(state='normal')
        
        # Execute in background thread to keep UI responsive
        import threading
        thread = threading.Thread(target=self._execute_steps_thread, args=(selected,), daemon=True)
        thread.start()

    def _execute_steps_thread(self, steps):
        """Thực thi các bước trong background thread"""
        work_dir = self._get_work_dir()
        
        for step in steps:
            # Safe UI update using after()
            self.frame.after(0, lambda s=step: self.lbl_progress.config(text=f"Đang chạy Bước {s}...", foreground="orange"))
            
            if step == 1:
                success, result = self._run_step1(work_dir)
            elif step == 2:
                success, result = self._run_step2(work_dir)
            elif step == 3:
                success, result = self._run_step3(work_dir)
            elif step == 4:
                success, result = self._run_step4(work_dir)
            else:
                continue
                
            if not success:
                self.frame.after(0, lambda r=result, s=step: self._on_step_error(s, r))
                return
        
        # Success - update UI safely
        self.frame.after(0, lambda: self._on_steps_complete(steps))

    def _on_step_error(self, step, result):
        """Callback khi step bị lỗi (chạy trên UI thread)"""
        self.lbl_progress.config(text=f"Lỗi ở Bước {step}: {result}", foreground="red")
        self.btn_run.config(state='normal')
        self.btn_stop.config(state='disabled')

    def _on_steps_complete(self, steps):
        """Callback khi hoàn thành tất cả steps (chạy trên UI thread)"""
        self.lbl_progress.config(text=f"Hoàn thành các bước: {steps}!", foreground="green")
        self.btn_run.config(state='normal')
        self.btn_stop.config(state='disabled')

    def _run_step1(self, work_dir):
        """Step 1: Đọc draft_content.json và xuất auto_subtitle.srt"""
        draft_file = self.draft_json_var.get()
        
        # Xác định đường dẫn đầy đủ
        if os.path.isabs(draft_file):
            draft_path = draft_file
        else:
            draft_path = os.path.join(work_dir, draft_file)
        
        success, result = auto_funtion.extract_srt_from_draft(draft_path, work_dir)
        return success, result
    
    def _run_step2(self, work_dir):
        """Step 2: Trích xuất text từ SRT và chia thành nhiều file"""
        # Đường dẫn SRT từ Step 1
        srt_path = os.path.join(work_dir, "auto", "auto_subtitle.srt")
        
        # Lấy cấu hình từ UI
        split_by_lines = self.split_by_lines.get()
        
        if split_by_lines:
            value = int(self.lines_per_file.get())
        else:
            value = int(self.number_of_parts.get())
        
        success, result = auto_funtion.run_step2_split(srt_path, work_dir, split_by_lines, value)
        return success, result
    
    def _run_step3(self, work_dir):
        """Step 3: Dịch bằng Gemini API"""
        model = self.gemini_model_var.get()
        max_workers = int(self.threads_var.get())
        
        # Progress callback để cập nhật UI
        def progress_callback(current, total, message):
            self.lbl_progress.config(text=f"[Step 3] {message} ({current}/{total})")
            self.frame.update_idletasks()
        
        success, result = auto_funtion.run_step3_translate(work_dir, model, max_workers, progress_callback)
        return success, result
    
    def _run_step4(self, work_dir):
        """Step 4: Tạo giọng đọc TTS"""
        voice = self.voice_var.get()
        rate = self.rate_var.get()
        volume = self.vol_var.get()
        
        # Lấy speed factor từ UI
        try:
            speed_factor = float(self.speed_factor_var.get())
        except ValueError:
            speed_factor = 1.0
        
        success, result = auto_funtion.run_step4_tts(work_dir, voice, rate, volume, speed_factor)
        return success, result


    def setup_right_panel(self, parent):
        """Panel bên phải: Quản lý API Key & Prompt"""
        # Sử dụng Notebook để chia tab
        self.right_notebook = ttk.Notebook(parent)
        self.right_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: API Keys
        self.tab_keys = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.tab_keys, text="Quản lý Keys")
        self.setup_keys_tab(self.tab_keys)
        
        # Tab 2: Prompt
        self.tab_prompt = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.tab_prompt, text="Cấu hình Prompt")
        self.setup_prompt_tab(self.tab_prompt)

    def setup_keys_tab(self, parent):
        """Content cho tab API Keys"""
        grp = ttk.LabelFrame(parent, text="Danh sách API Keys", padding="10")
        grp.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Stats frame
        stats_frame = ttk.Frame(grp)
        stats_frame.pack(fill='x', pady=(0, 5))
        
        self.lbl_key_stats = ttk.Label(stats_frame, text="📊 Loading stats...")
        self.lbl_key_stats.pack(side=tk.LEFT)
        
        ttk.Button(stats_frame, text="🔄 Refresh", command=self.refresh_api_stats, width=10).pack(side=tk.RIGHT)

        # Listbox info
        ttk.Label(grp, text="Danh sách Key hiện có:").pack(anchor='w')
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(grp)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        self.lst_keys = tk.Listbox(list_frame, height=18, yscrollcommand=scrollbar.set)
        self.lst_keys.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.lst_keys.yview)

        # Control buttons (API keys are hardcoded, no add/delete)
        btn_box = ttk.Frame(grp)
        btn_box.pack(fill='x', pady=5)
        
        ttk.Button(btn_box, text="🔄 Bật/Tắt", command=self.toggle_api_status).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_box, text="Refresh", command=self.refresh_api_stats).pack(side=tk.RIGHT, padx=2)

        # Initial Load
        self.load_api_keys()

    def setup_prompt_tab(self, parent):
        """Content cho tab Prompt Editor"""
        # Toolbar
        toolbar = ttk.Frame(parent, padding="5")
        toolbar.pack(fill='x')
        
        ttk.Button(toolbar, text="Lưu Prompt", command=self.save_prompt).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Tải lại", command=self.load_prompt).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Khôi phục mặc định", command=self.restore_default_prompt).pack(side=tk.LEFT, padx=5)
        
        # Text Editor
        editor_frame = ttk.Frame(parent, padding="5")
        editor_frame.pack(fill=tk.BOTH, expand=True)
        
        v_scroll = ttk.Scrollbar(editor_frame)
        v_scroll.pack(side=tk.RIGHT, fill='y')
        
        # Text widget with syntax highlighting potential (plain for now)
        self.txt_prompt = tk.Text(editor_frame, wrap=tk.NONE, undo=True, yscrollcommand=v_scroll.set)
        self.txt_prompt.pack(fill=tk.BOTH, expand=True)
        v_scroll.config(command=self.txt_prompt.yview)
        
        # Initial Load
        self.load_prompt()

    def restore_default_prompt(self):
        """Khôi phục nội dung prompt về mặc định"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn khôi phục prompt về mặc định ban đầu?"):
            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert("1.0", DEFAULT_PROMPT)

    # ===== API Management Helpers =====
    def _get_api_key_path(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir) # app/
            return os.path.join(app_dir, "gemini", "api.json")
        except Exception:
            return "api.json"
    
    def refresh_api_stats(self):
        """Refresh và hiển thị stats từ APIKeyManager"""
        try:
            from app.core.api_manager import get_api_manager
            manager = get_api_manager()
            manager.reload()
            stats = manager.get_stats()
            
            # Hiển thị stats + rotation state
            self.lbl_key_stats.config(
                text=f"✅ {stats['available']} | ⏳ {stats['rate_limited']} | 🚫 {stats['exhausted']} | 📈 Requests: {stats['total_requests_today']} | 🔄 Pos: Acc{stats['current_account_index']+1}-Proj{stats['current_project_index']+1} (Round #{stats['rotation_round']})"
            )
        except Exception as e:
            self.lbl_key_stats.config(text=f"❌ Lỗi load stats: {e}")
        
        # Reload danh sách keys
        self.load_api_keys()

    def load_api_keys(self):
        """Load và hiển thị API keys từ embedded keys + state"""
        self.lst_keys.delete(0, tk.END)
        
        try:
            # Load từ api_manager (embedded keys + AppData state)
            from app.core.api_manager import get_api_manager
            manager = get_api_manager()
            manager.reload()
            config = manager.config
            
            if not config.get("accounts"):
                self.lst_keys.insert(tk.END, "(Không có API keys - Kiểm tra api_keys.py)")
                return
            
            for account in config.get("accounts", []):
                acc_id = account.get("account_id", "?")
                acc_status = account.get("account_status", "active")
                email = account.get("email", "")
                
                # Truncate email for display
                if len(email) > 25:
                    email_display = email[:22] + "..."
                else:
                    email_display = email
                
                # Header cho mỗi account
                if acc_status == "inactive":
                    self.lst_keys.insert(tk.END, f"━━━ 🚫 {acc_id} ({email_display}) [TẮT] ━━━")
                else:
                    self.lst_keys.insert(tk.END, f"━━━ {acc_id} ({email_display}) ━━━")
                
                for project in account.get("projects", []):
                    proj_name = project.get("project_name", "")
                    api_key = project.get("api_key", "")
                    status = project.get("status", "available")
                    
                    # Status emoji
                    status_icons = {
                        "disabled": "⛔",
                        "available": "✅",
                        "rate_limited": "⏳",
                        "exhausted": "🚫",
                        "error": "❌"
                    }
                    status_icon = status_icons.get(status, "❓")
                    
                    # Mask key
                    if len(api_key) > 10:
                        display_key = f"{api_key[:6]}...{api_key[-4:]}"
                    elif api_key:
                        display_key = api_key
                    else:
                        display_key = "(chưa nhập)"
                    
                    self.lst_keys.insert(tk.END, f"  {status_icon} {proj_name}: {display_key}")
            
            # Update stats
            stats = manager.get_stats()
            self.lbl_key_stats.config(
                text=f"✅ {stats['available']} | ⏳ {stats['rate_limited']} | 🚫 {stats['exhausted']} | 📈 Total: {stats['total_projects']} keys"
            )
            
        except Exception as e:
            self.lst_keys.insert(tk.END, f"Lỗi load API keys: {str(e)}")
            logging.error(f"Error loading keys: {e}")

    def refresh_api_stats(self):
        """Reload API manager và refresh hiển thị"""
        try:
            from app.core.api_manager import get_api_manager
            manager = get_api_manager()
            manager.reload()
            self.load_api_keys()
        except Exception as e:
            logging.error(f"Refresh error: {e}")
    def toggle_api_status(self):
        """Bật/Tắt API key hoặc Account đã chọn"""
        selection = self.lst_keys.curselection()
        if not selection:
            messagebox.showwarning("Chọn item", "Vui lòng chọn account hoặc API key cần bật/tắt!")
            return
        
        idx = selection[0]
        item_text = self.lst_keys.get(idx)
        
        if item_text.startswith("("):  # Instructional text
            return
        
        try:
            from app.core.api_manager import get_api_manager
            manager = get_api_manager()
            config = manager.config
            
            # Xác định đây là Account header hay Project
            if item_text.startswith("━━━"):
                # Đây là Account header - toggle account_status
                acc_count = 0
                for i, text in enumerate(self.lst_keys.get(0, tk.END)):
                    if text.startswith("━━━"):
                        if i == idx:
                            break
                        acc_count += 1
                
                if acc_count < len(config.get("accounts", [])):
                    account = config["accounts"][acc_count]
                    current_status = account.get("account_status", "active")
                    new_status = "inactive" if current_status == "active" else "active"
                    account["account_status"] = new_status
                    
                    # Save via api_manager
                    manager._save_config()
                    
                    self.load_api_keys()
                    logging.info(f"User toggled account {account['account_id']}: {current_status} → {new_status}")
                    messagebox.showinfo("Thành công", f"Account {account['account_id']} đã được {'TẮT' if new_status == 'inactive' else 'BẬT'}!")
            else:
                # Đây là Project - toggle project status
                acc_idx = -1
                proj_idx = 0
                
                for i, text in enumerate(self.lst_keys.get(0, tk.END)):
                    if text.startswith("━━━"):
                        acc_idx += 1
                        proj_idx = 0
                    elif i == idx:
                        break
                    elif acc_idx >= 0:
                        proj_idx += 1
                
                if acc_idx >= 0 and acc_idx < len(config.get("accounts", [])):
                    account = config["accounts"][acc_idx]
                    projects = account.get("projects", [])
                    
                    if proj_idx < len(projects):
                        project = projects[proj_idx]
                        current_status = project.get("status", "available")
                        
                        # Danh sách status tạm thời
                        TEMPORARY_STATUSES = ["rate_limited", "exhausted", "error"]
                        
                        if current_status in TEMPORARY_STATUSES:
                            response = messagebox.askyesno(
                                "Xác nhận",
                                f"Project đang ở trạng thái '{current_status}' (tự động).\n"
                                f"Bạn có muốn reset về 'disabled' không?"
                            )
                            if not response:
                                return
                            new_status = "disabled"
                        elif current_status == "disabled":
                            new_status = "available"
                            # Clear recovery fields
                            limit = project.get("limit_tracking", {})
                            limit["rate_limit_reset_at"] = None
                            limit["daily_limit_reset_at"] = None
                            limit["minute_request_count"] = 0
                        else:  # available
                            new_status = "disabled"
                        
                        project["status"] = new_status
                        
                        # Save via api_manager
                        manager._save_config()
                        
                        self.load_api_keys()
                        proj_name = project.get("project_name", "")
                        acc_id = account.get("account_id", "")
                        logging.info(f"User toggled project {acc_id}/{proj_name}: {current_status} → {new_status}")
                        messagebox.showinfo("Thành công", f"{proj_name} đã được {'TẮT' if new_status == 'disabled' else 'BẬT'}!")
                        
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể thay đổi trạng thái: {e}")
            logging.error(f"Toggle API status error: {e}")

    # ===== Prompt Management Helpers =====
    def _get_prompt_path(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir)
            return os.path.join(app_dir, "gemini", "translation-prompt.json")
        except Exception:
            return "translation-prompt.json"
            
    def load_prompt(self):
        path = self._get_prompt_path()
        self.txt_prompt.delete("1.0", tk.END)
        
        if not os.path.exists(path):
            self.txt_prompt.insert("1.0", f"Không tìm thấy file prompt tại: {path}")
            return
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                self.txt_prompt.insert("1.0", content)
        except Exception as e:
            self.txt_prompt.insert("1.0", f"Lỗi đọc file: {e}")
            
    def save_prompt(self):
        path = self._get_prompt_path()
        content = self.txt_prompt.get("1.0", tk.END).strip()
        
        # Validate JSON
        try:
            json_content = json.loads(content)
        except json.JSONDecodeError as e:
            messagebox.showerror("Lỗi Format", f"Nội dung không phải là JSON hợp lệ:\n{e}")
            return
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content) # Write raw text to preserve formatting preference if any, or json.dump(json_content)
            messagebox.showinfo("Thành công", "Đã lưu nội dung Prompt!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    # ===== UI Helpers =====
    def _get_work_dir(self):
        return self.work_dir_var.get() if self.work_dir_var else os.getcwd()

    def _browse_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], initialdir=self._get_work_dir())
        if f: self.draft_json_var.set(os.path.basename(f) if os.path.dirname(f) == self._get_work_dir().replace("/", "\\") else f)

    def _open_prompt_file(self):
        """Mở file translation-prompt.json"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir)
            prompt_path = os.path.join(app_dir, "gemini", "translation-prompt.json")
            
            if os.path.exists(prompt_path):
                os.startfile(prompt_path)
            else:
                logging.error(f"Prompt file not found at: {prompt_path}")
                messagebox.showerror("Lỗi", "Không tìm thấy file translation-prompt.json")
        except Exception as e:
            logging.error(f"Cannot open prompt file: {e}")
            messagebox.showerror("Lỗi", f"Không thể mở file: {e}")

    def save_config(self):
        """Lưu Auto config vào user config"""
        try:
            # Get proper config path
            import sys
            if getattr(sys, 'frozen', False):
                appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
                config_dir = os.path.join(appdata, 'Tool')
            else:
                config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
            
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'config.json')
            
            # Load existing config
            data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            
            # Update Auto config
            data["auto_config"] = {
                "draft_file": self.draft_json_var.get(),
                "split_by_lines": self.split_by_lines.get(),
                "lines_per_file": self.lines_per_file.get(),
                "number_of_parts": self.number_of_parts.get(),
                "voice": self.voice_var.get(),
                "rate": self.rate_var.get(),
                "volume": self.vol_var.get(),
                "gemini_model": self.gemini_model_var.get()
            }
            
            # Save
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            logging.info(f"Đã lưu cấu hình Auto vào: {config_path}")
            messagebox.showinfo("Thông báo", "Đã lưu cấu hình!")
        except Exception as e:
            logging.error(f"Không thể lưu cấu hình: {e}")
            messagebox.showerror("Lỗi", f"Lỗi lưu cấu hình: {e}")

    def load_default_config(self):
        """Load lại config từ parent's auto_config"""
        try:
            self.draft_json_var.set(self.auto_config.get("draft_file", "draft_content.json"))
            self.split_by_lines.set(self.auto_config.get("split_by_lines", True))
            self.lines_per_file.set(self.auto_config.get("lines_per_file", "100"))
            self.number_of_parts.set(self.auto_config.get("number_of_parts", "5"))
            self.voice_var.set(self.auto_config.get("voice", "vi-VN-NamMinhNeural"))
            self.rate_var.set(self.auto_config.get("rate", "+30%"))
            self.vol_var.set(self.auto_config.get("volume", "+30%"))
            self.gemini_model_var.set(self.auto_config.get("gemini_model", "gemini-2.5-flash"))
            
            logging.info("Đã tải lại cấu hình mặc định!")
        except Exception as e:
            logging.error(f"Không thể tải cấu hình: {e}")

    def get_frame(self):
        return self.frame
