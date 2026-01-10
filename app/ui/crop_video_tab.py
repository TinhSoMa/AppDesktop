import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import logging
from app.core.crop_video_funtion import smart_split_video, convert_videos_to_wav
from app.ui.components.file_combobox import FileCombobox

class CropVideoTab:
    def __init__(self, parent, work_dir_var=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.frame = ttk.Frame(parent)
        
        self.wav_video_list = []
        
        # Stop events for process control
        self.split_stop_event = threading.Event()
        self.wav_stop_event = threading.Event()
        
        # Processing states
        self.is_split_running = False
        self.is_wav_running = False
        
        self.setup_ui()
        
        # Configure progress bar style (green color)
        style = ttk.Style()
        style.theme_use('clam')  # Use clam theme for better color support
        style.configure("green.Horizontal.TProgressbar", 
                       troughcolor='#E0E0E0',
                       background='#4CAF50',  # Green color
                       bordercolor='#388E3C',
                       lightcolor='#66BB6A',
                       darkcolor='#2E7D32')


    def setup_ui(self):
        # Master Layout: PanedWindow (Split Left | MP3 Right)
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ================== LEFT PANE: SPLIT VIDEO ==================
        left_pane = ttk.Frame(paned, padding="5")
        paned.add(left_pane, weight=1)

        # --- Group: Split Configuration ---
        grp_split = ttk.LabelFrame(left_pane, text="Cắt Video Thông Minh", padding="10")
        grp_split.pack(fill=tk.BOTH, expand=True, pady=0)

        # 1. Input File
        ttk.Label(grp_split, text="Video đầu vào:").pack(anchor='w', pady=(0, 2))
        f_input = ttk.Frame(grp_split)
        f_input.pack(fill='x', pady=(0, 10))
        
        self.split_input_var = tk.StringVar()
        self.cb_split_input = FileCombobox(f_input, self.work_dir_var, ['.mp4', '.mkv', '.mov', '.avi'], textvariable=self.split_input_var)
        self.cb_split_input.pack(side=tk.LEFT, fill='x', expand=True)
        
        ttk.Button(f_input, text="Browse", width=8, command=self.browse_split_input).pack(side=tk.LEFT, padx=(5, 0))

        # 2. Duration Settings
        ttk.Separator(grp_split, orient='horizontal').pack(fill='x', pady=5)
        ttk.Label(grp_split, text="Thời lượng mỗi phần (phút):").pack(anchor='w', pady=(5, 2))
        
        f_dur = ttk.Frame(grp_split)
        f_dur.pack(fill='x', pady=(0, 10))
        
        self.split_duration_var = tk.StringVar(value="60")
        entry_duration = ttk.Entry(f_dur, textvariable=self.split_duration_var, width=10, font=("Arial", 9))
        entry_duration.pack(side=tk.LEFT)
        
        # Presets
        f_presets = ttk.Frame(grp_split)
        f_presets.pack(fill='x', pady=0)
        
        ttk.Label(f_presets, text="Quick Set:").pack(side=tk.LEFT, padx=(0, 5))
        
        presets = [("1.5m", 1.5), ("2m", 2), ("2.5m", 2.5), 
                   ("5m", 5), ("10m", 10), ("60m", 60)]
        
        for label, val in presets:
            ttk.Button(f_presets, text=label, width=5, 
                      command=lambda v=val: self.split_duration_var.set(str(v))
                     ).pack(side=tk.LEFT, padx=2)

        # 3. Action Area (Bottom)
        ttk.Separator(grp_split, orient='horizontal').pack(fill='x', pady=15)
        
        self.split_status_var = tk.StringVar(value="Ready")
        ttk.Label(grp_split, textvariable=self.split_status_var, foreground="gray").pack(anchor='center', pady=5)
        
        # Progress Bar
        self.split_progress = ttk.Progressbar(grp_split, orient='horizontal', mode='determinate', 
                                              maximum=100, style="green.Horizontal.TProgressbar")
        self.split_progress.pack(fill='x', pady=5)
        
        # Buttons Frame
        btn_frame_split = ttk.Frame(grp_split)
        btn_frame_split.pack(fill='x', pady=10)
        
        # Start button
        self.btn_start_split = ttk.Button(btn_frame_split, text="Start Split Video", 
                                     command=self.start_split_process)
        self.btn_start_split.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5), ipady=5)
        
        # Stop button
        self.btn_stop_split = ttk.Button(btn_frame_split, text="Stop", 
                                    command=self.stop_split_process, state='disabled')
        self.btn_stop_split.pack(side=tk.LEFT, ipady=5)



        # ================== RIGHT PANE: VIDEO TO WAV ==================
        right_pane = ttk.Frame(paned, padding="5")
        paned.add(right_pane, weight=1)

        # --- Group: WAV Batch ---
        grp_wav = ttk.LabelFrame(right_pane, text="Chuyển đổi WAV Hàng Loạt", padding="10")
        grp_wav.pack(fill=tk.BOTH, expand=True, pady=0)

        # Toolbar
        f_toolbar = ttk.Frame(grp_wav)
        f_toolbar.pack(fill='x', pady=(0, 5))
        
        ttk.Button(f_toolbar, text="Add Video", command=self.add_wav_videos).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(f_toolbar, text="Clear List", command=self.clear_wav_list).pack(side=tk.LEFT)
        
        # Listbox
        f_list = ttk.Frame(grp_wav)
        f_list.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(f_list)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox_wav = tk.Listbox(f_list, selectmode=tk.EXTENDED, 
                                      activestyle='none', borderwidth=1, relief="solid",
                                      yscrollcommand=scrollbar.set, font=("Consolas", 9))
        self.listbox_wav.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox_wav.yview)

        # Action Area
        ttk.Separator(grp_wav, orient='horizontal').pack(fill='x', pady=15)
        
        self.wav_status_var = tk.StringVar(value="Ready")
        ttk.Label(grp_wav, textvariable=self.wav_status_var, foreground="gray").pack(anchor='center', pady=5)

        # Progress Bar
        self.wav_progress = ttk.Progressbar(grp_wav, orient='horizontal', mode='determinate', 
                                            maximum=100, style="green.Horizontal.TProgressbar")
        self.wav_progress.pack(fill='x', pady=5)
        
        # Buttons Frame
        btn_frame_wav = ttk.Frame(grp_wav)
        btn_frame_wav.pack(fill='x', pady=10)
        
        # Convert button
        self.btn_convert_wav = ttk.Button(btn_frame_wav, text="Convert to WAV", 
                                     command=self.start_wav_process)
        self.btn_convert_wav.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5), ipady=5)
        
        # Stop button
        self.btn_stop_wav = ttk.Button(btn_frame_wav, text="Stop", 
                                  command=self.stop_wav_process, state='disabled')
        self.btn_stop_wav.pack(side=tk.LEFT, ipady=5)



    def browse_split_input(self):
        # Use FileCombobox logic if possible? No, standard browse is fine, then update var
        filename = filedialog.askopenfilename(title="Chọn video để cắt", filetypes=[("Video Files", "*.mp4 *.mkv *.mov *.avi"), ("All Files", "*.*")])
        if filename:
            self.split_input_var.set(filename)

    def start_split_process(self):
        input_file = self.split_input_var.get()
        if not input_file or not os.path.exists(input_file):
            logging.error("Vui lòng chọn file video hợp lệ!")
            return
        
        if self.is_split_running:
            logging.warning("Quá trình cắt video đang chạy!")
            return
            
        try:
            duration_mins = float(self.split_duration_var.get())
        except ValueError:
            logging.error("Thời lượng phải là số!")
            return
            
        output_dir = os.path.join(os.path.dirname(input_file), "split_parts")
        
        def run():
            self.is_split_running = True
            self.split_stop_event.clear()  # Reset stop event
            
            # Update UI state
            self.btn_start_split.config(state='disabled')
            self.btn_stop_split.config(state='normal')
            self.split_progress['value'] = 0
            
            self.split_status_var.set("Đang xử lý... Vui lòng đợi.")
            logging.info(f"Bắt đầu cắt video: {os.path.basename(input_file)}")
            logging.info(f"Thời lượng mỗi phần: {duration_mins} phút")
            logging.info(f"Output: {output_dir}")
            
            try:
                smart_split_video(
                    input_file, 
                    duration_mins, 
                    output_dir, 
                    progress_callback=self.update_split_status,
                    progress_percent_callback=self.update_split_progress,
                    stop_event=self.split_stop_event
                )
                
                if not self.split_stop_event.is_set():
                    self.update_split_status("Hoàn tất!")
                    logging.info(f"Đã cắt video xong! Lưu tại: {output_dir}")
                else:
                    logging.warning("Quá trình cắt video đã bị dừng.")
                    
            except Exception as e:
                self.update_split_status(f"Lỗi: {str(e)}")
                logging.error(f"Lỗi khi cắt video: {str(e)}")
            finally:
                # Reset UI state
                self.is_split_running = False
                self.btn_start_split.config(state='normal')
                self.btn_stop_split.config(state='disabled')
            
        threading.Thread(target=run, daemon=True).start()
    
    def stop_split_process(self):
        """Dừng quá trình cắt video"""
        if self.is_split_running:
            logging.info("Đang dừng quá trình cắt video...")
            self.split_stop_event.set()
            self.split_status_var.set("Đang dừng...")

    def update_split_status(self, msg):
        """Thread-safe update for split status"""
        def _update():
            self.split_status_var.set(msg)
            # Log detailed progress to log tab
            if "Analyzing" in msg or "Found" in msg or "Exporting" in msg:
                logging.info(f"[Split Video] {msg}")
        
        # Schedule update in main thread
        self.frame.after(0, _update)
    
    def update_split_progress(self, percent):
        """Thread-safe update for split progress bar"""
        def _update():
            self.split_progress['value'] = percent
        
        # Schedule update in main thread
        self.frame.after(0, _update)



    def add_wav_videos(self):
        files = filedialog.askopenfilenames(title="Chọn video chuyển sang WAV", filetypes=[("Video Files", "*.mp4 *.mkv *.mov *.avi"), ("All Files", "*.*")])
        for f in files:
            if f not in self.wav_video_list:
                self.wav_video_list.append(f)
                self.listbox_wav.insert(tk.END, os.path.basename(f))

    def clear_wav_list(self):
        self.wav_video_list.clear()
        self.listbox_wav.delete(0, tk.END)

    def start_wav_process(self):
        if not self.wav_video_list:
            logging.warning("Danh sách trống!")
            return
        
        if self.is_wav_running:
            logging.warning("Quá trình chuyển đổi đang chạy!")
            return
            
        def run():
            self.is_wav_running = True
            self.wav_stop_event.clear()  # Reset stop event
            
            # Update UI state
            self.btn_convert_wav.config(state='disabled')
            self.btn_stop_wav.config(state='normal')
            self.wav_progress['value'] = 0
            
            self.wav_status_var.set("Đang chuyển đổi...")
            logging.info(f"Bắt đầu chuyển đổi {len(self.wav_video_list)} video sang WAV")
            
            try:
                convert_videos_to_wav(
                    self.wav_video_list, 
                    progress_callback=self.update_wav_status,
                    progress_percent_callback=self.update_wav_progress,
                    stop_event=self.wav_stop_event
                )
                
                if not self.wav_stop_event.is_set():
                    self.update_wav_status("Hoàn tất tất cả!")
                    logging.info("Đã chuyển đổi xong tất cả video sang WAV.")
                else:
                    logging.warning("Quá trình chuyển đổi đã bị dừng.")
                    
            except Exception as e:
                self.update_wav_status(f"Lỗi: {str(e)}")
                logging.error(f"Lỗi khi chuyển đổi WAV: {str(e)}")
            finally:
                # Reset UI state
                self.is_wav_running = False
                self.btn_convert_wav.config(state='normal')
                self.btn_stop_wav.config(state='disabled')
            
        threading.Thread(target=run, daemon=True).start()
    
    def stop_wav_process(self):
        """Dừng quá trình chuyển đổi WAV"""
        if self.is_wav_running:
            logging.info("Đang dừng quá trình chuyển đổi WAV...")
            self.wav_stop_event.set()
            self.wav_status_var.set("Đang dừng...")

    def update_wav_status(self, msg):
        """Thread-safe update for WAV status"""
        def _update():
            self.wav_status_var.set(msg)
            # Log detailed progress to log tab
            if "Converting" in msg:
                logging.info(f"[WAV Convert] {msg}")
        
        # Schedule update in main thread
        self.frame.after(0, _update)
    
    def update_wav_progress(self, percent):
        """Thread-safe update for WAV progress bar"""
        def _update():
            self.wav_progress['value'] = percent
        
        # Schedule update in main thread
        self.frame.after(0, _update)


