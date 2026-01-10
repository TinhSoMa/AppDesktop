import tkinter as tk
from tkinter import ttk
import os
import glob
from pathlib import Path

class FileCombobox(ttk.Combobox):
    """
    Combobox tự động liệt kê các file trong work_dir dựa trên extension.
    Hiển thị dạng: ParentFolder/Filename (luôn hiển thị 1 bậc thư mục trước tên file).
    CHỈ quét file bên trong thư mục gốc (work_dir), không quét các thư mục khác cùng cấp.
    """
    def __init__(self, parent, work_dir_var, file_exts, textvariable=None, **kwargs):
        self.work_dir_var = work_dir_var
        self.file_exts = [ext.lower() for ext in file_exts]
        self.file_map = {} # Map: DisplayName -> FullPath
        
        super().__init__(
            parent, 
            textvariable=textvariable,
            postcommand=self.refresh_files,
            **kwargs
        )
        
    def refresh_files(self):
        """Quét lại file trong thư mục gốc (đệ quy chỉ bên trong thư mục gốc)"""
        if not self.work_dir_var: return

        current_dir_str = self.work_dir_var.get()
        if not current_dir_str or not os.path.exists(current_dir_str):
            self['values'] = []
            return
            
        current_dir = Path(current_dir_str).resolve()  # Chuẩn hóa đường dẫn tuyệt đối
        self.file_map = {}
        display_names = []
        
        try:
            # Quét đệ quy cho từng extension
            files = []
            for ext in self.file_exts:
                # rglob quét đệ quy tất cả subfolder
                files.extend(list(current_dir.rglob(f"*{ext}")))
            
            # LỌC: Chỉ giữ lại file nằm BÊN TRONG thư mục gốc
            filtered_files = []
            for f in files:
                try:
                    # Kiểm tra xem file có nằm trong current_dir không
                    # resolve() để chuẩn hóa đường dẫn, tránh lỗi so sánh
                    f_resolved = f.resolve()
                    
                    # Kiểm tra f_resolved có phải là con của current_dir không
                    if f_resolved.is_relative_to(current_dir):
                        filtered_files.append(f_resolved)
                except (ValueError, OSError):
                    # Bỏ qua file lỗi hoặc không thể resolve
                    continue
            
            # Sort để dễ nhìn
            filtered_files.sort()
            
            for f in filtered_files:
                if f.is_file():
                    try:
                        # Lấy đường dẫn relative so với current_dir
                        rel_path = f.relative_to(current_dir)
                        
                        # Luôn hiển thị 1 bậc thư mục trước tên file
                        if len(rel_path.parts) == 1:
                            # File nằm ngay root: hiển thị tên_thư_mục_gốc/filename
                            # Ví dụ: 1223/draft.json
                            display_name = f"{current_dir.name}/{f.name}"
                        else:
                            # File nằm trong subfolder: hiển thị parent_trực_tiếp/filename
                            # Ví dụ: subdraft/config.json
                            parent_name = f.parent.name
                            display_name = f"{parent_name}/{f.name}"
                        
                        self.file_map[display_name] = str(f)
                        display_names.append(display_name)
                    except ValueError:
                        # Nếu không thể tạo relative path, bỏ qua
                        continue
            
            self['values'] = display_names
            
        except Exception as e:
            print(f"Error scanning files: {e}")
            self['values'] = []

    def get_full_path(self):
        """Lấy đường dẫn tuyệt đối của file đang chọn"""
        val = self.get().strip()
        if not val: return None
        
        # 1. Nếu là đường dẫn tuyệt đối hợp lệ
        if os.path.isabs(val) and os.path.exists(val):
            # Cho phép file nằm ngoài kho (User browse tới)
            return val
            
        # 2. Tra cứu trong map đã scan
        if val in self.file_map:
            return self.file_map[val]
            
        # 3. Fallback: Thử ghép với work_dir (trường hợp user gõ tay)
        work_dir = Path(self.work_dir_var.get()).resolve()
        
        # TH1: User gõ "1223/draft.json" (có tên thư mục gốc)
        # Cần xử lý: nếu part đầu là tên thư mục gốc, bỏ qua nó
        parts = val.split('/')
        if len(parts) >= 2:
            if parts[0] == work_dir.name:
                # Bỏ phần tên thư mục gốc, ghép phần còn lại
                relative_part = '/'.join(parts[1:])
                try_path = work_dir / relative_part
            else:
                # Ghép trực tiếp
                try_path = work_dir / val
        else:
            try_path = work_dir / val
            
        if try_path.exists():
            # Kiểm tra lại xem có nằm trong work_dir không
            try:
                if try_path.resolve().is_relative_to(work_dir):
                    return str(try_path.resolve())
            except (ValueError, OSError):
                pass
        
        return None