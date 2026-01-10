import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
import subprocess
import logging

try:
    from app.ui.components.file_combobox import FileCombobox
except ImportError:
    from ui.components.file_combobox import FileCombobox

class SRTTab:
    """Tab xử lý file subtitle SRT - Modular
    Giao diện được chia thành 3 tab nhỏ.
    Sử dụng FileCombobox để chọn file từ WorkDir.
    Output Path tự động sinh.
    """
    
    def __init__(self, parent, work_dir_var=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.frame = ttk.Frame(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # Main Layout: PanedWindow (Split Left | Right)
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- Left Pane: Conversion (SRT <-> TXT) ---
        left_pane = ttk.Frame(paned, padding="5")
        paned.add(left_pane, weight=1)
        
        self._create_extract_captions_section(left_pane)
        ttk.Separator(left_pane, orient='horizontal').pack(fill='x', pady=10)
        self._create_convert_srt_section(left_pane)

        # --- Right Pane: Text Tools & Timing ---
        right_pane = ttk.Frame(paned, padding="5")
        paned.add(right_pane, weight=1)
        
        self._create_format_txt_section(right_pane)
        ttk.Separator(right_pane, orient='horizontal').pack(fill='x', pady=10)
        self._create_split_txt_section(right_pane)
        ttk.Separator(right_pane, orient='horizontal').pack(fill='x', pady=10)
        self._create_scale_speed_section(right_pane)
    
    # ===== Section Creation with FileCombobox =====
    
    def _create_extract_captions_section(self, parent):
        section_frame = ttk.LabelFrame(parent, text="Trích xuất Caption (SRT → TXT)", padding="10")
        section_frame.pack(fill='x', pady=5)
        
        # Input
        input_frame = ttk.Frame(section_frame)
        input_frame.pack(fill='x', pady=5)
        ttk.Label(input_frame, text="File SRT:", width=12).pack(side=tk.LEFT)
        
        self.extract_srt_var = tk.StringVar()
        # Thay Entry bằng FileCombobox
        self.combo_extract_srt = FileCombobox(
            input_frame, 
            self.work_dir_var, 
            ['.srt'], 
            textvariable=self.extract_srt_var,
            width=57
        )
        self.combo_extract_srt.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(input_frame, text="Duyệt", command=lambda: self._browse_file(self.extract_srt_var, [("SRT files", "*.srt")])).pack(side=tk.LEFT)
        ttk.Button(input_frame, text="Trích xuất", command=self.extract_captions).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(section_frame, text="*Output tự động: [filename].txt -> WorkDir", font=("Arial", 9, "italic"), foreground="gray").pack()
    
    def _create_convert_srt_section(self, parent):
        section_frame = ttk.LabelFrame(parent, text="Chuyển đổi SRT (TXT + Template → SRT)", padding="10")
        section_frame.pack(fill='x', pady=5)
        
        # Input TXT
        f1 = ttk.Frame(section_frame)
        f1.pack(fill='x', pady=5)
        ttk.Label(f1, text="File TXT:", width=12).pack(side=tk.LEFT)
        
        self.convert_txt_var = tk.StringVar()
        self.combo_convert_txt = FileCombobox(f1, self.work_dir_var, ['.txt'], textvariable=self.convert_txt_var, width=57)
        self.combo_convert_txt.pack(side=tk.LEFT, padx=5)
        ttk.Button(f1, text="Duyệt", command=lambda: self._browse_file(self.convert_txt_var, [("Text files", "*.txt")])).pack(side=tk.LEFT)
        
        # Template SRT
        f2 = ttk.Frame(section_frame)
        f2.pack(fill='x', pady=5)
        ttk.Label(f2, text="Mẫu:", width=12).pack(side=tk.LEFT)
        
        self.convert_template_var = tk.StringVar()
        self.combo_convert_template = FileCombobox(f2, self.work_dir_var, ['.srt'], textvariable=self.convert_template_var, width=57)
        self.combo_convert_template.pack(side=tk.LEFT, padx=5)
        ttk.Button(f2, text="Duyệt", command=lambda: self._browse_file(self.convert_template_var, [("SRT files", "*.srt")])).pack(side=tk.LEFT)
        ttk.Button(f2, text="Chuyển đổi", command=self.convert_to_srt).pack(side=tk.LEFT, padx=5)
    
    def _create_format_txt_section(self, parent):
        section_frame = ttk.LabelFrame(parent, text="Định dạng TXT (Làm sạch)", padding="10")
        section_frame.pack(fill='x', pady=5)
        
        # Input
        f1 = ttk.Frame(section_frame)
        f1.pack(fill='x', pady=5)
        ttk.Label(f1, text="File TXT:", width=12).pack(side=tk.LEFT)
        
        self.format_input_var = tk.StringVar()
        self.combo_format_input = FileCombobox(f1, self.work_dir_var, ['.txt'], textvariable=self.format_input_var, width=57)
        self.combo_format_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(f1, text="Duyệt", command=lambda: self._browse_file(self.format_input_var, [("Text files", "*.txt")])).pack(side=tk.LEFT)
        ttk.Button(f1, text="Format TXT", command=self.format_txt).pack(side=tk.LEFT, padx=5)
        
        # Options
        opts = ttk.Frame(section_frame)
        opts.pack(fill='x', pady=5)
        # self.remove_special_chars = tk.BooleanVar(value=True) # Không dùng nữa
        ttk.Label(opts, text="Dấu phân cách: '|' (Tách dòng)", foreground="blue").pack(side=tk.LEFT, padx=10)
        
        self.remove_extra_spaces = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Xóa khoảng trắng thừa", variable=self.remove_extra_spaces).pack(side=tk.LEFT, padx=10)
    
    def _create_split_txt_section(self, parent):
        section_frame = ttk.LabelFrame(parent, text="Chia nhỏ TXT", padding="10")
        section_frame.pack(fill='x', pady=5)
        
        # Input
        f1 = ttk.Frame(section_frame)
        f1.pack(fill='x', pady=5)
        ttk.Label(f1, text="File TXT:", width=12).pack(side=tk.LEFT)
        
        self.split_input_var = tk.StringVar()
        self.combo_split_input = FileCombobox(f1, self.work_dir_var, ['.txt'], textvariable=self.split_input_var, width=57)
        self.combo_split_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(f1, text="Duyệt", command=lambda: self._browse_file(self.split_input_var, [("Text files", "*.txt")])).pack(side=tk.LEFT)
        ttk.Button(f1, text="Thực hiện Chia", command=self.split_txt).pack(side=tk.LEFT, padx=5)
        
        # Options
        opts = ttk.Frame(section_frame)
        opts.pack(fill='x', pady=5)
        
        self.split_by_lines = tk.BooleanVar(value=True)
        ttk.Radiobutton(opts, text="Số dòng/file:", variable=self.split_by_lines, value=True).pack(side=tk.LEFT)
        self.lines_per_file = tk.StringVar(value="100")
        # Combobox nhỏ cho số dòng (Editable)
        ttk.Combobox(opts, textvariable=self.lines_per_file, values=["50", "100", "200", "500"], width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(opts, text="dòng").pack(side=tk.LEFT)
        
        ttk.Label(opts, text="|").pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(opts, text="Số phần:", variable=self.split_by_lines, value=False).pack(side=tk.LEFT)
        self.number_of_parts = tk.StringVar(value="5")
        ttk.Entry(opts, textvariable=self.number_of_parts, width=6).pack(side=tk.LEFT, padx=2)        
        ttk.Label(opts, text="phần").pack(side=tk.LEFT)

    def _create_scale_speed_section(self, parent):
        section_frame = ttk.LabelFrame(parent, text="Chỉnh Tốc độ (Scale Speed)", padding="10")
        section_frame.pack(fill='x', pady=20)
        
        # Input
        f1 = ttk.Frame(section_frame)
        f1.pack(fill='x', pady=5)
        ttk.Label(f1, text="File SRT:", width=12).pack(side=tk.LEFT)
        
        self.scale_input_var = tk.StringVar()
        self.combo_scale_input = FileCombobox(f1, self.work_dir_var, ['.srt'], textvariable=self.scale_input_var, width=57)
        self.combo_scale_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(f1, text="Duyệt", command=lambda: self._browse_file(self.scale_input_var, [("SRT files", "*.srt")])).pack(side=tk.LEFT)
        ttk.Button(f1, text="Áp dụng", command=self.scale_speed).pack(side=tk.LEFT, padx=5)
        
        # Factor
        f2 = ttk.Frame(section_frame)
        f2.pack(fill='x', pady=5)
        ttk.Label(f2, text="Hệ số:", width=12).pack(side=tk.LEFT)
        self.speed_factor = tk.StringVar(value="1.0")
        ttk.Entry(f2, textvariable=self.speed_factor, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(f2, text="(>1.0: chậm, <1.0: nhanh)").pack(side=tk.LEFT, padx=5)

    # ===== Helpers =====

    def _get_work_dir(self):
        if self.work_dir_var and self.work_dir_var.get():
            return self.work_dir_var.get()
        return os.getcwd()

    def _browse_file(self, variable, filetypes):
        # Browse sẽ trả về full path.
        # Nếu đang ở chế độ FileCombobox hiển thị name-only, ta có thể cần xử lý để chỉ hiển thị tên file
        # Tuy nhiên, FileCombobox được thiết kể để chấp nhận cả full path và rel path.
        filename = filedialog.askopenfilename(
            title="Chọn file",
            initialdir=self._get_work_dir(),
            filetypes=filetypes + [("All files", "*.*")]
        )
        if filename:
            # Nếu file nằm trong work_dir, chỉ lấy tên file cho đẹp
            work_dir = self._get_work_dir()
            if os.path.dirname(filename) == work_dir.replace("/", "\\") or os.path.dirname(filename) == work_dir:
                 variable.set(os.path.basename(filename))
            else:
                 variable.set(filename)
            
    def _generate_output_path(self, input_full_path, extension, suffix=""):
        work_dir = self._get_work_dir()
        file_name = Path(input_full_path).stem
        if suffix:
            file_name = f"{file_name}_{suffix}"
        
        new_name = f"{file_name}{extension}"
        # Chuẩn hóa đường dẫn về '/' để tránh bị trộn lẫn \ và / trên Windows
        return os.path.join(work_dir, new_name).replace("\\", "/")
    
    def _open_folder(self, path):
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        if os.path.exists(folder):
            try:
                os.startfile(folder)
            except: pass

    # ===== Action Methods (Updated to use compbox.get_full_path()) =====
    
    def extract_captions(self):
        srt_path = self.combo_extract_srt.get_full_path()
        if not srt_path or not os.path.exists(srt_path): 
            logging.warning("File SRT không tồn tại!")
            return
        
        txt_path = self._generate_output_path(srt_path, ".txt")
        
        try:
            from app.core.srt_funtion import extract_srt_captions
            success, count = extract_srt_captions(srt_path, txt_path)
            if success:
                logging.info(f"Trích xuất {count} dòng thành công. Output: {txt_path}")
            else: logging.error("Lỗi khi trích xuất. Xem Log để biết chi tiết.")
        except Exception as e: logging.error(f"Lỗi Extract Caption: {e}")

    def convert_to_srt(self):
        txt_path = self.combo_convert_txt.get_full_path()
        template_path = self.combo_convert_template.get_full_path()
        
        if not txt_path or not os.path.exists(txt_path): 
            logging.warning("File TXT không hợp lệ!")
            return
        if not template_path or not os.path.exists(template_path): 
            logging.warning("File Template không hợp lệ!")
            return
        
        output_path = self._generate_output_path(txt_path, ".srt", suffix="converted")
        
        try:
            from app.core.srt_funtion import convert_txt_to_srt_using_template
            success, count = convert_txt_to_srt_using_template(txt_path, template_path, output_path)
            if success:
                logging.info(f"Convert {count} dòng thành công. Output: {output_path}")
            else: logging.error("Lỗi khi chuyển đổi SRT. Xem Log.")
        except Exception as e: logging.error(f"Lỗi Convert SRT: {e}")

    def format_txt(self):
        input_path = self.combo_format_input.get_full_path()
        if not input_path or not os.path.exists(input_path): 
            logging.warning("File TXT không hợp lệ!")
            return
        
        output_path = self._generate_output_path(input_path, ".txt", suffix="formatted")
        
        try:
            from app.core.srt_funtion import format_txt_file
            # Mặc định delimiter là '|', có thể thêm UI để user nhập sau này
            success = format_txt_file(
                input_path, output_path, 
                delimiter="|", 
                remove_extra_spaces=self.remove_extra_spaces.get()
            )
            if success:
                logging.info(f"Format TXT thành công. Output: {output_path}")
            else: logging.error("Lỗi khi Format TXT. Xem Log.")
        except Exception as e: logging.error(f"Lỗi Format TXT: {e}")

    def scale_speed(self):
        input_path = self.combo_scale_input.get_full_path()
        try: factor = float(self.speed_factor.get())
        except: 
            logging.error("Hệ số sai format!")
            return
        
        if not input_path or not os.path.exists(input_path): 
            logging.warning("File SRT không hợp lệ!")
            return
        
        output_path = self._generate_output_path(input_path, ".srt", suffix=f"x{factor}")
        
        try:
            from app.core.srt_funtion import scale_srt_speed
            success = scale_srt_speed(input_path, output_path, factor)
            if success:
                logging.info(f"Scale Speed thành công. Output: {output_path}")
            else: logging.error("Lỗi khi Scale Speed. Xem Log.")
        except Exception as e: logging.error(f"Lỗi Scale Speed: {e}")

    def split_txt(self):
        input_path = self.combo_split_input.get_full_path()
        if not input_path or not os.path.exists(input_path): 
            logging.warning("File TXT không hợp lệ!")
            return
        
        folder_name = Path(input_path).stem + "_parts"
        output_dir = os.path.join(self._get_work_dir(), folder_name)
        
        try:
            split_lines = self.split_by_lines.get()
            val = int(self.lines_per_file.get()) if split_lines else int(self.number_of_parts.get())
            
            from app.core.srt_funtion import split_text_file
            success, count = split_text_file(input_path, output_dir, split_lines, val)
            if success:
                logging.info(f"Đã chia thành {count} file. Folder: {output_dir}")
            else: logging.error("Lỗi khi chia file. Xem Log.")
        except Exception as e: logging.error(f"Lỗi Split TXT: {e}")

    def get_frame(self):
        return self.frame
