import tkinter as tk
from tkinter import ttk, scrolledtext
import logging

class LogTab:
    """Tab hiển thị Log (Nhật ký hoạt động)"""
    
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # Khu vực chứa log
        log_frame = ttk.LabelFrame(self.frame, text="Hoạt động hệ thống", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ScrolledText widget
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            state='disabled', 
            height=8, # Giảm chiều cao log mặc định
            font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Tag configs cho màu sắc (Info, Warning, Error)
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        
        # Nút Clear Log
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="Xóa Log", command=self.clear_log).pack(side=tk.RIGHT)

    def append_log(self, msg, level='INFO'):
        """Thêm log vào widget"""
        self.log_text.configure(state='normal')
        
        # Insert text với tag màu tương ứng
        self.log_text.insert(tk.END, msg + "\n", level)
        
        # Auto scroll to bottom
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def clear_log(self):
        """Xóa toàn bộ log"""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        
    def get_frame(self):
        return self.frame
