import logging
import tkinter as tk

class WidgetLogger(logging.Handler):
    """
    Custom Logging Handler để redirect log messages vào Tkinter Text widget
    """
    def __init__(self, log_tab_instance):
        super().__init__()
        self.log_tab = log_tab_instance
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        # Sử dụng after để đảm bảo thread-safe khi update GUI từ thread khác
        self.log_tab.log_text.after(0, self.log_tab.append_log, msg, record.levelname)

def setup_logging(log_tab_instance):
    """Cấu hình logging root"""
    logger = logging.getLogger()
    
    # Xóa các handler cũ (để tránh duplicate nếu logging đã được init trước đó)
    if logger.handlers:
        logger.handlers.clear()
        
    logger.setLevel(logging.INFO)
    
    # Text Handler (GUI)
    widget_handler = WidgetLogger(log_tab_instance)
    logger.addHandler(widget_handler)
    
    # Console Handler (Terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
    logger.addHandler(console_handler)
