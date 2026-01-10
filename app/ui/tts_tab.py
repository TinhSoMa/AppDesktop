import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import asyncio
import os
import logging
import json
from app.ui.components.file_combobox import FileCombobox
import app.core.tts_funtion as tts_core

# Danh sách giọng đọc phổ biến
VOICES = [
    "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "ja-JP-NanamiNeural",
    "ko-KR-SunHiNeural"
]

class TTSTab:
    def __init__(self, parent, work_dir_var=None, tts_config=None):
        self.parent = parent
        self.work_dir_var = work_dir_var
        self.tts_config = tts_config or {}  # Config from parent
        self.frame = ttk.Frame(parent)
        
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        # Load config defaults - use parent config or fallback
        defaults = {
            "voice": self.tts_config.get("voice", "vi-VN-HoaiMyNeural"),
            "rate": self.tts_config.get("rate", "+0%"),
            "volume": self.tts_config.get("volume", "+0%"),
            "pitch": self.tts_config.get("pitch", "+0Hz")
        }
        logging.info(f"TTS Tab loaded with config: {defaults}")

        # 1. Main Content
        main_content = ttk.Frame(self.frame, padding="10")
        main_content.pack(fill=tk.BOTH, expand=True)
        
        # --- Group Input ---
        grp_input = ttk.LabelFrame(main_content, text="Nguồn dữ liệu", padding="10")
        grp_input.pack(fill='x', pady=5)
        
        ttk.Label(grp_input, text="File SRT:").grid(row=0, column=0, sticky='w')
        self.srt_path_var = tk.StringVar()
        self.combo_srt = FileCombobox(grp_input, self.work_dir_var, ['.srt'], textvariable=self.srt_path_var, width=50)
        self.combo_srt.grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Duyệt...", command=self._browse_srt).grid(row=0, column=2, padx=5)
        
        ttk.Label(grp_input, text="Thư mục Audio:").grid(row=1, column=0, sticky='w', pady=5)
        self.audio_dir_var = tk.StringVar()
        ttk.Entry(grp_input, textvariable=self.audio_dir_var, width=50).grid(row=1, column=1, padx=5, sticky='ew')
        ttk.Button(grp_input, text="Chọn...", command=self._browse_audio_dir).grid(row=1, column=2, padx=5)
        
        # --- Group Config ---
        grp_config = ttk.LabelFrame(main_content, text="Cấu hình", padding="10")
        grp_config.pack(fill='x', pady=5)
        
        # Voice
        ttk.Label(grp_config, text="Giọng đọc:").grid(row=0, column=0, sticky='w', pady=2)
        self.voice_var = tk.StringVar(value=defaults["voice"])
        cb_voice = ttk.Combobox(grp_config, textvariable=self.voice_var, values=VOICES, width=30)
        cb_voice.grid(row=0, column=1, padx=5, sticky='w')
        
        # Rate
        ttk.Label(grp_config, text="Tốc độ:").grid(row=1, column=0, sticky='w', pady=2)
        self.rate_var = tk.StringVar(value=defaults["rate"])
        ttk.Entry(grp_config, textvariable=self.rate_var, width=10).grid(row=1, column=1, padx=5, sticky='w')
        ttk.Label(grp_config, text="(VD: +10%, -10%)").grid(row=1, column=2, sticky='w')

        # Volume
        ttk.Label(grp_config, text="Âm lượng:").grid(row=2, column=0, sticky='w', pady=2)
        self.vol_var = tk.StringVar(value=defaults["volume"])
        ttk.Entry(grp_config, textvariable=self.vol_var, width=10).grid(row=2, column=1, padx=5, sticky='w')
        
        # Pitch
        ttk.Label(grp_config, text="Cao độ:").grid(row=3, column=0, sticky='w', pady=2)
        self.pitch_var = tk.StringVar(value=defaults["pitch"])
        ttk.Entry(grp_config, textvariable=self.pitch_var, width=10).grid(row=3, column=1, padx=5, sticky='w')
        
        # Concurrency
        ttk.Label(grp_config, text="Số luồng:").grid(row=4, column=0, sticky='w', pady=2)
        self.concurrent_var = tk.StringVar(value="5")
        ttk.Spinbox(grp_config, from_=1, to=20, textvariable=self.concurrent_var, width=5).grid(row=4, column=1, padx=5, sticky='w')

        # Save & Load Config Buttons
        btn_frame = ttk.Frame(grp_config)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky='w')
        
        ttk.Button(btn_frame, text="Lưu mặc định", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Tải mặc định", command=self.load_default_config).pack(side=tk.LEFT, padx=5)

        # --- Group Actions ---
        grp_action = ttk.LabelFrame(main_content, text="Thao tác", padding="10")
        grp_action.pack(fill='x', pady=5)
        
        self.btn_gen = ttk.Button(grp_action, text="Tạo Audio (Riêng lẻ)", command=self.run_generation)
        self.btn_gen.pack(side=tk.LEFT, padx=5)
        
        self.btn_merge = ttk.Button(grp_action, text="Ghép thành 1 file", command=self.run_merge)
        self.btn_merge.pack(side=tk.LEFT, padx=5)
        
        self.btn_suggest = ttk.Button(grp_action, text="Đề xuất tốc độ", command=self.run_suggest_speed)
        self.btn_suggest.pack(side=tk.LEFT, padx=5)

        self.btn_sort_srt = ttk.Button(grp_action, text="Sắp xếp SRT", command=self.run_sort_srt)
        self.btn_sort_srt.pack(side=tk.LEFT, padx=5)

        self.btn_trim = ttk.Button(grp_action, text="Cắt khoảng lặng", command=self.run_trim_silence)
        self.btn_trim.pack(side=tk.LEFT, padx=5)
        
        self.btn_all = ttk.Button(grp_action, text="Chạy tất cả (Tạo + Ghép)", command=self.run_all)
        self.btn_all.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(grp_action, text="Dừng lại", command=self.stop_processing, state='disabled')
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        # Status
        self.lbl_status = ttk.Label(grp_action, text="Sẵn sàng", foreground="blue")
        self.lbl_status.pack(side=tk.LEFT, padx=20)

    def get_frame(self):
        return self.frame

    def _get_work_dir(self):
        return self.work_dir_var.get() if self.work_dir_var else os.getcwd()

    def _browse_srt(self):
        f = filedialog.askopenfilename(
            title="Chọn file SRT",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")], 
            initialdir=self._get_work_dir()
        )
        if f:
             self.srt_path_var.set(f)

    def _browse_audio_dir(self):
        d = filedialog.askdirectory(initialdir=self._get_work_dir(), title="Chọn thư mục chứa Audio")
        if d:
            self.audio_dir_var.set(d)

    def _check_input(self):
        srt_path = self.combo_srt.get_full_path()
        if not srt_path or not os.path.exists(srt_path):
            logging.warning("Vui lòng chọn file SRT hợp lệ!")
            return None
        return srt_path

    def save_config(self):
        """Lưu TTS config vào user config"""
        try:
            # Get proper config path (same logic as main.py)
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
            
            # Update TTS config
            data["tts_config"] = {
                "voice": self.voice_var.get(),
                "rate": self.rate_var.get(),
                "volume": self.vol_var.get(),
                "pitch": self.pitch_var.get()
            }
            
            # Save
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            logging.info(f"Đã lưu cấu hình TTS vào: {config_path}")
        except Exception as e:
            logging.error(f"Không thể lưu cấu hình: {e}")

    def load_default_config(self):
        """Load lại config từ parent's tts_config"""
        try:
            # Use stored config from parent
            self.voice_var.set(self.tts_config.get("voice", "vi-VN-HoaiMyNeural"))
            self.rate_var.set(self.tts_config.get("rate", "+0%"))
            self.vol_var.set(self.tts_config.get("volume", "+0%"))
            self.pitch_var.set(self.tts_config.get("pitch", "+0Hz"))
            logging.info("Đã tải lại cấu hình mặc định!")
        except Exception as e:
            logging.error(f"Không thể tải cấu hình: {e}")
        
    def set_running(self, running: bool):
        self.is_running = running
        if running:
            self.stop_event.clear()
            
        state = 'disabled' if running else 'normal'
        stop_state = 'normal' if running else 'disabled'
        
        self.btn_gen.config(state=state)
        self.btn_merge.config(state=state)
        self.btn_suggest.config(state=state)
        self.btn_sort_srt.config(state=state)
        self.btn_trim.config(state=state)
        self.btn_all.config(state=state)
        self.btn_stop.config(state=stop_state)
        
        if running:
            self.lbl_status.config(text="Đang chạy...", foreground="red")
        else:
            self.lbl_status.config(text="Hoàn tất / Chờ", foreground="green")

    def stop_processing(self):
        if self.is_running:
            logging.warning("Đang yêu cầu dừng tác vụ...")
            self.stop_event.set()

    def run_generation(self):
        self._run_thread(self._task_generate, False)

    def run_merge(self):
        if self.is_running: return
        srt_path = self._check_input()
        if not srt_path: return
        
        audio_dir = self.audio_dir_var.get()
        self.set_running(True)
        threading.Thread(target=self._task_merge, args=(srt_path, audio_dir), daemon=True).start()

    def run_all(self):
        self._run_thread(self._task_generate, True)

    def _run_thread(self, target, merge_after):
        if self.is_running: return
        srt_path = self._check_input()
        if not srt_path: return
        
        self.set_running(True)
        threading.Thread(target=target, args=(srt_path, merge_after), daemon=True).start()

    def _task_generate(self, srt_path, do_merge_after):
        """Task chạy trong thread riêng để generate audio"""
        try:
            logging.info(f"Start generating audio for: {srt_path}")
            
            # 1. Parse SRT
            entries = tts_core.parse_srt_file(srt_path)
            if not entries:
                logging.error("Không đọc được nội dung file SRT.")
                logging.error("File SRT rỗng hoặc không hợp lệ.")
                return

            logging.info(f"Found {len(entries)} lines in SRT.")
            
            # 2. Config output dir
            # Output sẽ nằm trong folder cùng tên với file srt: /path/to/Video/filename_TTS/
            base_name = os.path.splitext(os.path.basename(srt_path))[0]
            work_dir = os.path.dirname(srt_path)
            output_dir = os.path.join(work_dir, f"{base_name}_TTS")
            
            # 3. Async Generate
            # Create new loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Define progress callback
            def on_progress(current, total, message):
                 short_msg = message
                 if len(short_msg) > 40: short_msg = short_msg[:40] + "..."
                 self.parent.after(0, lambda: self.lbl_status.config(text=f"Gen {current}/{total}: {short_msg}", foreground="blue"))

            concurrent = int(self.concurrent_var.get())
            generated_files = loop.run_until_complete(
                tts_core.generate_batch_audio_logic(
                    entries, output_dir,
                    voice=self.voice_var.get(),
                    rate=self.rate_var.get(),
                    volume=self.vol_var.get(),
                    pitch=self.pitch_var.get(),
                    max_concurrent=concurrent,
                    stop_event=self.stop_event,
                    progress_callback=on_progress
                )
            )
            
            # --- Auto Retry Logic ---
            # Tự động kiểm tra và tạo lại các file bị lỗi (0 byte hoặc thiếu)
            for attempt in range(3): # Thử lại tối đa 3 lần
                if self.stop_event.is_set(): break
                
                failed_entries = tts_core.validate_generated_files(entries, output_dir)
                if not failed_entries:
                    break # All good
                
                logging.warning(f"⚠️ Phát hiện {len(failed_entries)} file lỗi. Đang thử lại (Lần {attempt+1}/3)...")
                self.parent.after(0, lambda: self.lbl_status.config(text=f"Retry {attempt+1}: Fix {len(failed_entries)} files", foreground="orange"))
                
                # Retry generation for failed entries only
                retry_results = loop.run_until_complete(
                    tts_core.generate_batch_audio_logic(
                        failed_entries, output_dir,
                        voice=self.voice_var.get(),
                        rate=self.rate_var.get(),
                        volume=self.vol_var.get(),
                        pitch=self.pitch_var.get(),
                        max_concurrent=concurrent,
                        stop_event=self.stop_event,
                        progress_callback=on_progress
                    )
                )
                
                if retry_results:
                    generated_files.extend(retry_results)
            
            loop.close()
            
            logging.info(f"Generated {len(generated_files)} audio files in {output_dir}")
            
            if do_merge_after and generated_files:
                if not self.stop_event.is_set():
                    self._task_merge_logic(generated_files, srt_path)
            elif generated_files and not self.stop_event.is_set():
                 logging.info(f"Đã tạo {len(generated_files)} file audio lẻ. Hoàn tất.")


        except Exception as e:
            logging.error(f"Error in generation task: {e}")
            logging.error(str(e))
        finally:
            if not do_merge_after: # Nếu còn merge thì chưa stop
                self.parent.after(0, lambda: self.set_running(False))

    def _task_merge(self, srt_path, user_audio_dir=None):
        """Task chạy thread riêng để merge (khi bấm nút Merge Only)"""
        try:
            # Determine Audio Dir
            if user_audio_dir and os.path.exists(user_audio_dir):
                output_dir = user_audio_dir
            else:
                base_name = os.path.splitext(os.path.basename(srt_path))[0]
                work_dir = os.path.dirname(srt_path)
                output_dir = os.path.join(work_dir, f"{base_name}_TTS")
            
            logging.info(f"Using audio dir for merge: {output_dir}")
            
            if not os.path.exists(output_dir):
                logging.error(f"Folder audio không tồn tại: {output_dir}")
                return

            # Re-parse để lấy timing
            entries = tts_core.parse_srt_file(srt_path)
            files_to_merge = []
            missing_entries = []
            
            for entry in entries:
                # Re-construct filename logic
                filename = tts_core.get_safe_filename(entry.index, entry.text)
                path = os.path.join(output_dir, filename)
                
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    files_to_merge.append((path, entry.start_ms))
                else:
                    missing_entries.append(entry)
            
            # Nếu có file thiếu, tự động generate lại
            if missing_entries:
                logging.warning(f"Phát hiện {len(missing_entries)} file audio thiếu hoặc lỗi. Đang tạo lại...")
                
                if self.stop_event.is_set():
                    return

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                concurrent = int(self.concurrent_var.get())
                # Chỉ generate các entry bị thiếu
                regenerated_files = loop.run_until_complete(
                    tts_core.generate_batch_audio_logic(
                        missing_entries, output_dir,
                        voice=self.voice_var.get(),
                        rate=self.rate_var.get(),
                        volume=self.vol_var.get(),
                        pitch=self.pitch_var.get(),
                        max_concurrent=concurrent,
                        stop_event=self.stop_event
                    )
                )
                loop.close()
                
                if self.stop_event.is_set():
                    logging.warning("Dừng merge (do user stop khi đang fix file).")
                    return

                # Thêm các file vừa tạo vào danh sách merge
                if regenerated_files:
                    files_to_merge.extend(regenerated_files)
                    # Sort lại theo thời gian để đảm bảo thứ tự
                    files_to_merge.sort(key=lambda x: x[1])
                    logging.info(f"Đã tạo lại thành công {len(regenerated_files)} file.")
                else:
                    logging.error("Không thể tạo lại các file bị thiếu. Merge có thể bị khuyết.")

            if not files_to_merge:
                logging.error("Không có file audio nào để merge.")
                return

            self._task_merge_logic(files_to_merge, srt_path)
            
        except Exception as e:
            logging.error(f"Error in merge task: {e}")
        finally:
            self.parent.after(0, lambda: self.set_running(False))

    def _task_merge_logic(self, file_list, srt_path):
        """Logic merge chung"""
        output_wav = srt_path.replace(".srt", "_merged.wav")
        logging.info(f"Merging {len(file_list)} files into {output_wav}...")
        
        success = tts_core.merge_audio_files_ffmpeg(file_list, output_wav, stop_event=self.stop_event)
        
        if success:
             logging.info(f"Merge success: {output_wav}")
             logging.info(f"Tạo file thành công: {output_wav}")
        else:
             logging.error("Merge failed.")
             logging.error("Lỗi khi ghép file audio.")
             
        self.parent.after(0, lambda: self.set_running(False))

    def run_suggest_speed(self):
        if self.is_running: return
        srt_path = self._check_input()
        if not srt_path: return
        
        # Determine audio dir
        audio_dir = self.audio_dir_var.get()
        
        # If not set, try default
        if not audio_dir:
            base_name = os.path.splitext(os.path.basename(srt_path))[0]
            work_dir = os.path.dirname(srt_path)
            default_dir = os.path.join(work_dir, f"{base_name}_TTS")
            if os.path.exists(default_dir):
                audio_dir = default_dir
            else:
                 # Ask user
                audio_dir = filedialog.askdirectory(
                    title="Chọn thư mục chứa file Audio để phân tích",
                    initialdir=work_dir
                )
        
        if not audio_dir:
            return

        self.set_running(True)
        threading.Thread(target=self._task_suggest_speed, args=(srt_path, audio_dir), daemon=True).start()

    def _task_suggest_speed(self, srt_path, audio_dir):
        """Task chạy thread riêng để phân tích và đề xuất tốc độ"""
        try:
            if not os.path.exists(audio_dir):
                logging.error(f"Folder audio không tồn tại: {audio_dir}")
                return

            logging.info(f"Start Analyzing Speed for: {srt_path}")
            logging.info(f"Audio Dir: {audio_dir}")
            
            # Call Core Analysis Only
            analysis = tts_core.analyze_before_merge(audio_dir, srt_path)
            
            # Log result
            logging.info(str(analysis))
            
            # Show summary popup
            self.parent.after(0, lambda: self._show_analysis_result(analysis))

        except Exception as e:
            logging.error(f"Error in analysis task: {e}")
            logging.exception(e)
        finally:
            self.parent.after(0, lambda: self.set_running(False))

    def _show_analysis_result(self, analysis):
        """Hiển thị kết quả phân tích"""
        # Create a simple message message
        msg = f"Đề xuất hệ số tốc độ (Speed Factor): {analysis.recommended_time_scale:.2f}x\n"
        msg += f"Tổng số file: {analysis.total_segments}\n"
        msg += f"Số file quá dài: {analysis.overflow_segments}\n\n"
        
        if analysis.top_overflow_segments:
            msg += "Top file dài nhất:\n"
            for i, seg in enumerate(analysis.top_overflow_segments[:3], 1):
                msg += f" {i}. Index #{seg.index + 1}: Vượt {seg.overflow_ms}ms ({seg.overflow_ratio:.2f}x)\n"
        
        messagebox.showinfo("Kết quả Đề xuất Tốc độ", msg)

    def run_sort_srt(self):
        srt_path = self._check_input()
        if not srt_path: return
        
        # Output report path
        work_dir = os.path.dirname(srt_path)
        base_name = os.path.splitext(os.path.basename(srt_path))[0]
        report_path = os.path.join(work_dir, f"{base_name}_duration_report.txt").replace("\\", "/")
        
        try:
            # We assume tts_core is imported, and we added the function there
            success, count = tts_core.sort_srt_captions_by_duration(srt_path, report_path)
            
            if success:
                logging.info(f"Đã tạo báo cáo phân tích thành công: {report_path}")
                if messagebox.askyesno("Thành công", f"Đã tạo báo cáo ({count} dòng).\nFile: {os.path.basename(report_path)}\nBạn có muốn mở file báo cáo ngay không?"):
                    try:
                        os.startfile(report_path)
                    except: pass
            else:
                 messagebox.showerror("Lỗi", "Không thể phân tích file SRT.")
                 
        except Exception as e:
            logging.error(f"Error sorting SRT: {e}")
            logging.exception(e)

    def run_trim_silence(self):
        if self.is_running: return
        
        # Audio dir logic
        audio_dir = self.audio_dir_var.get()
        if not audio_dir:
            # Try from SRT input if available
            srt_path = self.combo_srt.get_full_path()
            if srt_path and os.path.exists(srt_path):
                base_name = os.path.splitext(os.path.basename(srt_path))[0]
                work_dir = os.path.dirname(srt_path)
                default_dir = os.path.join(work_dir, f"{base_name}_TTS")
                if os.path.exists(default_dir):
                    audio_dir = default_dir
        
        if not audio_dir or not os.path.exists(audio_dir):
            audio_dir = filedialog.askdirectory(title="Chọn thư mục Audio để cắt khoảng lặng")
            if audio_dir:
                self.audio_dir_var.set(audio_dir)
        
        if not audio_dir: return

        self.set_running(True)
        threading.Thread(target=self._task_trim_silence, args=(audio_dir,), daemon=True).start()

    def _task_trim_silence(self, audio_dir):
        """Task cắt silence riêng biệt"""
        try:
            logging.info(f"Start trimming silence in: {audio_dir}")
            count = tts_core.batch_trim_audio_directory(audio_dir, backup=True)
            logging.info(f"Hoàn tất cắt khoảng lặng cho {count} file.")
            if count > 0:
                 messagebox.showinfo("Thông báo", f"Đã cắt khoảng lặng thành công {count} file.\nFile gốc được lưu trong thư mục _backup.")
            else:
                 logging.warning("Không tìm thấy file audio nào để xử lý.")

        except Exception as e:
            logging.error(f"Trim Error: {e}")
        finally:
            self.parent.after(0, lambda: self.set_running(False))
