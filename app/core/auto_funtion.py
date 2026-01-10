import os
import json
import re
import math
import logging
import subprocess
import sys

# ============================================================================
# PATCH: CHẶN CỬA SỔ CMD KHI CHẠY FFMPEG VÀ EDGE-TTS (WINDOWS)
# ============================================================================
if os.name == 'nt':
    import asyncio
    
    # 1. Thiết lập cấu hình khởi tạo tiến trình ẩn
    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _startupinfo.wShowWindow = subprocess.SW_HIDE
    
    _creationflags = 0x08000000  # CREATE_NO_WINDOW

    # 2. Patch subprocess.Popen gốc
    _original_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        if 'startupinfo' not in kwargs:
            kwargs['startupinfo'] = _startupinfo
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = _creationflags
        return _original_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen

    # 3. Ép asyncio dùng ProactorEventLoop (tránh nháy cửa sổ khi dùng edge-tts)
    if sys.version_info >= (3, 7):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ============================================================================

# Import hàm export_to_srt từ utils (đã có sẵn logic đọc draft_content.json)
try:
    from app.core.utils import export_to_srt, milliseconds_to_srt_time
except ImportError:
    from utils import export_to_srt, milliseconds_to_srt_time


# ========== STEP 1: Extract SRT from Draft Content JSON ==========
def extract_srt_from_draft(draft_json_path, output_dir):
    """
    Đọc file draft_content.json và xuất ra file auto_subtitle.srt
    trong thư mục 'auto' (sẽ được tạo nếu chưa có).
    
    Sử dụng logic từ utils.export_to_srt() - đã được test và hoạt động đúng.
    
    Args:
        draft_json_path: Đường dẫn đến file draft_content.json
        output_dir: Thư mục gốc làm việc (work_dir)
        
    Returns:
        (success: bool, output_path: str hoặc error_message: str)
    """
    logging.info(f"[Step 1] Bắt đầu Extract SRT từ: {os.path.basename(draft_json_path)}")
    
    if not os.path.exists(draft_json_path):
        error_msg = f"File không tồn tại: {draft_json_path}"
        logging.error(error_msg)
        return False, error_msg
    
    try:
        # Tạo thư mục 'auto' để lưu output
        auto_dir = os.path.join(output_dir, "auto")
        os.makedirs(auto_dir, exist_ok=True)
        
        # Output path
        output_path = os.path.join(auto_dir, "auto_subtitle.srt")
        
        # Sử dụng hàm export_to_srt từ utils.py
        success = export_to_srt(draft_json_path, output_path)
        
        if success:
            logging.info(f"[Step 1] Extract thành công -> {output_path}")
            return True, output_path
        else:
            return False, "Không thể xuất SRT từ draft"
        
    except Exception as e:
        error_msg = f"Lỗi không xác định: {e}"
        logging.error(error_msg)
        return False, error_msg


# ========== STEP 2: Extract Text from SRT & Split into Parts ==========
def run_step2_split(srt_path, output_dir, split_by_lines=True, value=100):
    """
    Bước 2: Trích xuất text từ SRT (Step 1) và chia thành nhiều file TXT.
    
    Args:
        srt_path: Đường dẫn đến file SRT từ Step 1 (auto/auto_subtitle.srt)
        output_dir: Thư mục gốc làm việc (work_dir)
        split_by_lines: True = chia theo số dòng/file, False = chia theo số phần
        value: Số dòng mỗi file (nếu split_by_lines=True) hoặc số phần (nếu False)
        
    Returns:
        (success: bool, result: str hoặc error_message)
    """
    logging.info(f"[Step 2] Bắt đầu Split từ: {os.path.basename(srt_path)}")
    
    if not os.path.exists(srt_path):
        error_msg = f"File SRT không tồn tại: {srt_path}"
        logging.error(error_msg)
        return False, error_msg
    
    try:
        # Thư mục output: auto/text/
        text_dir = os.path.join(output_dir, "auto", "text")
        os.makedirs(text_dir, exist_ok=True)
        
        # Bước 2.1: Trích xuất text từ SRT
        texts = extract_text_lines_from_srt(srt_path)
        
        if not texts:
            return False, "Không tìm thấy text trong file SRT"
        
        logging.info(f"[Step 2] Trích xuất được {len(texts)} dòng text từ SRT")
        
        # Bước 2.2: Chia thành nhiều file
        total_lines = len(texts)
        
        if split_by_lines:
            lines_per_file = int(value)
            num_files = math.ceil(total_lines / lines_per_file)
        else:
            num_parts = int(value)
            lines_per_file = math.ceil(total_lines / num_parts)
            num_files = num_parts

        created_files = []
        for i in range(num_files):
            start_idx = i * lines_per_file
            end_idx = start_idx + lines_per_file
            if start_idx >= total_lines: 
                break
            
            chunk = texts[start_idx:end_idx]

            file_start = start_idx + 1
            file_end = min(end_idx, total_lines)
            filename = f"part_{i+1}_lines_{file_start}-{file_end}.txt"
            file_path = os.path.join(text_dir, filename)

            with open(file_path, "w", encoding="utf-8") as out:
                for line in chunk:
                    out.write(line + "\n")
            
            created_files.append(filename)
            logging.info(f"  - Đã tạo: {filename}")

        logging.info(f"[Step 2] Chia file hoàn tất: Tổng {len(created_files)} file trong {text_dir}")
        return True, f"Đã tạo {len(created_files)} file trong auto/text/"

    except Exception as e:
        error_msg = f"Lỗi Step 2: {e}"
        logging.error(error_msg)
        return False, error_msg


def extract_text_lines_from_srt(srt_path):
    """Trích xuất danh sách dòng text từ file SRT (bỏ timing)"""
    texts = []
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r'\n\s*\n', content.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            # Tìm dòng có timestamp
            for idx, line in enumerate(lines):
                if "-->" in line:
                    # Text nằm sau dòng timestamp
                    text_lines = lines[idx+1:]
                    if text_lines:
                        # Gộp các dòng text (nếu subtitle có nhiều dòng)
                        text = " ".join(text_lines).strip()
                        if text:
                            texts.append(text)
                    break
    except Exception as e:
        logging.error(f"Lỗi đọc SRT: {e}")
    
    return texts


# ========== STEP 3: Call Gemini API for Translation ==========
def run_step3_translate(work_dir, model, max_workers=3, progress_callback=None):
    """
    Bước 3: Dịch tất cả các file part bằng Gemini API (đa luồng)
    (Có hỗ trợ tự động đổi model nếu hết Quota)
    """
    import threading
    import queue
    import time
    
    logging.info(f"[Step 3] Bắt đầu dịch. Model khởi điểm: {model}")

    # Import dependencies
    try:
        from app.core import gemini
        from app.core.api_manager import get_api_manager
    except ImportError:
        import gemini
        from api_manager import get_api_manager
    
    # 1. Setup paths
    text_dir = os.path.join(work_dir, "auto", "text")
    if not os.path.exists(text_dir):
        return False, "Thư mục auto/text không tồn tại. Hãy chạy Step 2 trước."
    
    part_files = sorted([f for f in os.listdir(text_dir) if f.startswith("part_") and f.endswith(".txt")])
    if not part_files:
        return False, "Không tìm thấy file nào để dịch trong auto/text/"
    
    # 2. Setup Resources
    api_manager = get_api_manager()
    api_manager.reload()
    
    prompt_template = gemini.load_prompt_template()
    if not prompt_template:
        return False, "Không thể đọc file prompt template."
        
    translated_dir = os.path.join(work_dir, "auto", "translated")
    os.makedirs(translated_dir, exist_ok=True)

    # 3. Model Hierarchy & Fallback Setup
    MODEL_PRIORITY = [
        "gemini-3-pro-preview", 
        "gemini-2.5-pro",
        "gemini-3-flash-preview", 
        "gemini-2.5-flash", 
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite"
    ]
    
    current_model = model
    files_to_process = list(part_files)
    completed_files = set()
    errors_encountered = []
    
    if current_model not in MODEL_PRIORITY:
        MODEL_PRIORITY = [current_model] + [m for m in MODEL_PRIORITY if m != current_model]

    # --- MAIN LOOP: Retry with fallback models ---
    while True:
        logging.info(f">>> [Step 3 Session] Chạy {len(files_to_process)} files với model: {current_model}")
        
        q = queue.Queue()
        for f in files_to_process:
            q.put(f)
            
        lock = threading.Lock()
        no_key_event = threading.Event()
        batch_completed_files = []
        batch_failed_files = []
        
        def worker():
            while not q.empty() and not no_key_event.is_set():
                try:
                    filename = q.get(timeout=1)
                except queue.Empty:
                    break
                
                if no_key_event.is_set():
                    q.task_done()
                    return

                with lock:
                    api_key, key_info = api_manager.get_next_api_key()
                
                if not api_key:
                    no_key_event.set()
                    q.task_done()
                    return

                # Process
                input_path = os.path.join(text_dir, filename)
                output_filename = filename.replace(".txt", "_translated.txt")
                output_path = os.path.join(translated_dir, output_filename)
                account_name = key_info.get("name", "Unknown") if key_info else "Unknown"
                
                logging.info(f"   [{current_model}] Dịch {filename} bằng {account_name}")
                
                success, msg = gemini.translate_file(
                    file_path=input_path,
                    output_path=output_path,
                    api_keys=[{"key": api_key, "name": account_name}],
                    model=current_model,
                    prompt_template=prompt_template
                )
                
                if success:
                    with lock:
                        batch_completed_files.append(filename)
                        logging.info(f"   ✓ Xong {filename}")
                else:
                    with lock:
                        batch_failed_files.append(filename)
                        errors_encountered.append(f"{filename}: {msg}")
                        logging.error(f"   ✗ Lỗi {filename}: {msg}")
                
                delay = api_manager.get_delay_ms()
                if delay > 0:
                    time.sleep(delay / 1000.0)
                
                q.task_done()

        threads = []
        workers = min(max_workers, len(files_to_process))
        for _ in range(workers):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()

        for f in batch_completed_files:
            completed_files.add(f)
        
        files_to_process = [f for f in part_files if f not in completed_files]
        
        if not files_to_process:
            logging.info(">>> Đã dịch xong tất cả các file.")
            break
            
        if no_key_event.is_set():
            logging.warning(f"!!! HẾT KEY CHO MODEL {current_model} !!!")
            try:
                curr_idx = MODEL_PRIORITY.index(current_model)
                if curr_idx + 1 < len(MODEL_PRIORITY):
                    next_model = MODEL_PRIORITY[curr_idx + 1]
                    logging.info(f"🔃 TỰ ĐỘNG CHUYỂN MODEL: {current_model} ➔ {next_model}")
                    current_model = next_model
                    api_manager.reset_all_status_except_disabled()
                    continue 
                else:
                    logging.error("Đã hết danh sách model dự phòng!")
                    break
            except ValueError:
                logging.error(f"Model {current_model} không nằm trong danh sách fallback.")
                break
        else:
            if batch_failed_files:
                logging.warning(f"Có {len(batch_failed_files)} file bị lỗi nội dung.")
                break
            else:
                break

    success_count = len(completed_files)
    
    if success_count > 0:
        try:
            merged_path = os.path.join(work_dir, "auto", "translated_full.txt")
            translated_files = []
            for part in part_files:
                if part in completed_files:
                    t_name = part.replace(".txt", "_translated.txt")
                    if os.path.exists(os.path.join(translated_dir, t_name)):
                        translated_files.append(t_name)
            
            all_lines = []
            for tf in translated_files:
                tf_path = os.path.join(translated_dir, tf)
                with open(tf_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    all_lines.extend(lines)
            
            with open(merged_path, "w", encoding="utf-8") as f:
                for line in all_lines:
                    f.write(line + "\n")
            
            srt_template = os.path.join(work_dir, "auto", "auto_subtitle.srt")
            output_srt = os.path.join(work_dir, "auto", "translated_subtitle.srt")
            if os.path.exists(srt_template):
                srt_success, srt_count = convert_txt_to_srt_using_template(merged_path, srt_template, output_srt)
        except Exception as e:
            logging.error(f"Merge error: {e}")

    if not files_to_process:
        return True, f"Hoàn thành 100% ({success_count} files)"
    elif success_count > 0:
        return True, f"Hoàn thành một phần {success_count}/{len(part_files)}. Lỗi: {len(files_to_process)} file."
    else:
        return False, f"Thất bại hoàn toàn. {errors_encountered[:1]}"


def convert_txt_to_srt_using_template(txt_path, srt_template_path, output_srt_path):
    """
    Thay thế text trong SRT template bằng text đã dịch.
    Giữ nguyên timing, chỉ thay đổi nội dung.
    """
    logging.info(f"Convert TXT -> SRT: {os.path.basename(txt_path)}")
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            txt_lines = [l.strip() for l in f if l.strip()]

        with open(srt_template_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        # Parse SRT blocks
        pattern = r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:(?!\n\d+\n\d{2}:\d{2}:\d{2},\d{3}).)*)"
        blocks = re.findall(pattern, srt_content, re.DOTALL)
        
        if not blocks:
            # Fallback parsing
            logging.warning("Regex không bắt được cấu trúc chuẩn, thử fallback parsing...")
            raw_blocks = re.split(r'\n\s*\n', srt_content.strip())
            parsed_blocks = []
            for b in raw_blocks:
                lines = b.strip().split('\n')
                if len(lines) >= 2:
                    for idx, line in enumerate(lines):
                        if "-->" in line:
                            seq = lines[0] if idx > 0 else str(len(parsed_blocks) + 1)
                            parsed_blocks.append((seq, line))
                            break
            blocks = parsed_blocks

        count = min(len(txt_lines), len(blocks))
        new_content = ""

        for i in range(count):
            seq_num = blocks[i][0] if blocks[i][0] else str(i+1)
            timing = blocks[i][1]
            text = txt_lines[i]
            new_content += f"{seq_num}\n{timing}\n{text}\n\n"

        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logging.info(f"Convert thành công: {count} lines -> {output_srt_path}")
        return True, count

    except Exception as e:
        logging.error(f"Lỗi convert_txt_to_srt: {e}")
        return False, 0


# ========== STEP 4: Generate TTS Audio ==========
def run_step4_tts(work_dir, voice, rate, volume, speed_factor=1.0, progress_callback=None):
    """
    Bước 4: Tạo audio từ SRT đã dịch
    
    Args:
        work_dir: Thư mục làm việc gốc
        voice: Tên giọng đọc (vi-VN-NamMinhNeural, ...)
        rate: Tốc độ đọc (+30%, -20%, ...)
        volume: Âm lượng (+30%, ...)
        speed_factor: Hệ số scale thời gian SRT (1.0 = không đổi, 1.2 = chậm lại 20%)
        progress_callback: Callback cập nhật UI
        
    Returns:
        (success: bool, result_message: str)
    """
    import asyncio
    
    logging.info(f"[Step 4] Bắt đầu TTS với voice: {voice}, rate: {rate}")
    
    # Import TTS functions
    try:
        from app.core.tts_funtion import (
            parse_srt_file, 
            generate_batch_audio_logic
        )
    except ImportError:
        from tts_funtion import (
            parse_srt_file,
            generate_batch_audio_logic
        )
    
    # Đường dẫn input/output
    srt_input = os.path.join(work_dir, "auto", "translated_subtitle.srt")
    audio_dir = os.path.join(work_dir, "auto", "audio")
    
    # Tên file output có thêm tốc độ nếu != 1.0
    if speed_factor != 1.0:
        output_audio = os.path.join(work_dir, "auto", f"merged_audio_{speed_factor}x.wav")
    else:
        output_audio = os.path.join(work_dir, "auto", "merged_audio.wav")
    
    if not os.path.exists(srt_input):
        return False, "File translated_subtitle.srt không tồn tại. Hãy chạy Step 3 trước."
    
    # Parse SRT
    entries = parse_srt_file(srt_input)
    if not entries:
        return False, "Không tìm thấy subtitle trong file SRT"
    
    logging.info(f"[Step 4] Tìm thấy {len(entries)} subtitle entries")
    
    # Tạo thư mục audio
    os.makedirs(audio_dir, exist_ok=True)
    
    # ===== Bước 4.1: Tạo audio từng câu =====
    async def run_tts():
        return await generate_batch_audio_logic(
            entries=entries,
            output_dir=audio_dir,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch="+0Hz",
            max_concurrent=5,
            stop_event=None,
            progress_callback=None
        )
    
    try:
        # Chạy async TTS
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_files = loop.run_until_complete(run_tts())
        loop.close()
        
        logging.info(f"[Step 4] Đã tạo {len(audio_files)} audio files")
        
        if not audio_files:
            return False, "Không tạo được audio nào"
            
    except Exception as e:
        logging.error(f"[Step 4] Lỗi tạo audio: {e}")
        return False, f"Lỗi TTS: {e}"
    
    # ===== Kiểm tra và tạo lại các file bị lỗi (size = 0) =====
    try:
        from app.core.tts_funtion import validate_generated_files, get_safe_filename
    except ImportError:
        from tts_funtion import validate_generated_files, get_safe_filename
    
    failed_entries = validate_generated_files(entries, audio_dir)
    
    if failed_entries:
        logging.warning(f"[Step 4] Phát hiện {len(failed_entries)} file bị lỗi, đang tạo lại...")
        
        # Retry tạo lại các file bị lỗi (tối đa 2 lần)
        for retry in range(2):
            if not failed_entries:
                break
                
            logging.info(f"[Step 4] Retry lần {retry + 1}: tạo lại {len(failed_entries)} file...")
            
            async def retry_tts():
                return await generate_batch_audio_logic(
                    entries=failed_entries,
                    output_dir=audio_dir,
                    voice=voice,
                    rate=rate,
                    volume=volume,
                    pitch="+0Hz",
                    max_concurrent=3,
                    stop_event=None,
                    progress_callback=None
                )
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                retry_files = loop.run_until_complete(retry_tts())
                loop.close()
                
                # Kiểm tra lại
                failed_entries = validate_generated_files(failed_entries, audio_dir)
                
                if not failed_entries:
                    logging.info(f"[Step 4] Đã tạo lại thành công tất cả file lỗi!")
                    # Thêm các file mới vào danh sách
                    audio_files.extend(retry_files)
                    
            except Exception as e:
                logging.error(f"[Step 4] Lỗi retry TTS: {e}")
        
        if failed_entries:
            logging.warning(f"[Step 4] Vẫn còn {len(failed_entries)} file không tạo được")
    
    # ===== Bước 4.2: Cắt khoảng lặng đầu file audio =====
    logging.info(f"[Step 4] Đang cắt khoảng lặng đầu các file audio...")
    trim_count = 0
    for audio_path, _ in audio_files:
        if os.path.exists(audio_path):
            if trim_silence_from_audio(audio_path):
                trim_count += 1
    logging.info(f"[Step 4] Đã trim {trim_count}/{len(audio_files)} file audio")
    
    # ===== Bước 4.3: Scale SRT nếu cần =====
    if speed_factor != 1.0:
        scaled_srt = os.path.join(work_dir, "auto", f"translated_subtitle_{speed_factor}x.srt")
        scale_success = scale_srt_timing(srt_input, scaled_srt, speed_factor)
        if scale_success:
            srt_for_merge = scaled_srt
            logging.info(f"[Step 4] Đã scale SRT với factor {speed_factor}x")
        else:
            srt_for_merge = srt_input
    else:
        srt_for_merge = srt_input
    
    # ===== Bước 4.3: Ghép audio (không phân tích tốc độ) =====
    try:
        from app.core.tts_funtion import merge_audio_files_ffmpeg, parse_srt_file as parse_srt
    except ImportError:
        from tts_funtion import merge_audio_files_ffmpeg, parse_srt_file as parse_srt
    
    # Lấy danh sách audio files với timing từ SRT
    srt_entries = parse_srt(srt_for_merge)
    file_list = []
    
    for entry in srt_entries:
        # Tìm file audio tương ứng
        prefix = f"{entry.index:03d}_"
        for f in os.listdir(audio_dir):
            if f.startswith(prefix) and f.endswith(".wav"):
                audio_path = os.path.join(audio_dir, f)
                file_list.append((audio_path, entry.start_ms))
                break
    
    if not file_list:
        return False, "Không tìm thấy file audio để ghép"
    
    logging.info(f"[Step 4] Ghép {len(file_list)} audio files...")
    
    # Xóa file output cũ nếu tồn tại (tránh lỗi file đang bị khóa)
    if os.path.exists(output_audio):
        try:
            os.remove(output_audio)
            logging.info(f"[Step 4] Đã xóa file cũ: {os.path.basename(output_audio)}")
        except PermissionError:
            # File đang bị khóa, thử tên file khác
            import time
            timestamp = int(time.time())
            output_audio = output_audio.replace(".wav", f"_{timestamp}.wav")
            logging.warning(f"[Step 4] File bị khóa, sử dụng tên mới: {os.path.basename(output_audio)}")
    
    try:
        success = merge_audio_files_ffmpeg(file_list, output_audio)
        
        if success:
            logging.info(f"[Step 4] Đã ghép audio -> {output_audio}")
            return True, f"Đã tạo audio: {os.path.basename(output_audio)}"
        else:
            return False, "Lỗi ghép audio"
            
    except Exception as e:
        logging.error(f"[Step 4] Lỗi merge audio: {e}")
        return False, f"Lỗi merge: {e}"


def scale_srt_timing(input_path, output_path, factor):
    """Scale timing của SRT theo hệ số factor (1.2 = chậm lại 20%)"""
    logging.info(f"Scale SRT timing (x{factor}): {os.path.basename(input_path)}")
    
    def parse_time(time_str):
        h, m, s, ms = map(int, re.split('[:,]', time_str))
        return (h*3600 + m*60 + s) * 1000000 + ms * 1000

    def format_time(micros):
        total_ms = int(micros / 1000)
        ms = total_ms % 1000
        s = (total_ms // 1000) % 60
        m = (total_ms // 60000) % 60
        h = (total_ms // 3600000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'

        def replace_func(match):
            start_str, end_str = match.groups()
            new_start = parse_time(start_str) * factor
            new_end = parse_time(end_str) * factor
            return f"{format_time(new_start)} --> {format_time(new_end)}"

        new_content = re.sub(pattern, replace_func, content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logging.info(f"Scale thành công -> {output_path}")
        return True
    except Exception as e:
        logging.error(f"Lỗi scale_srt_timing: {e}")
        return False


def trim_silence_from_audio(input_path, output_path=None):
    """
    Cắt bỏ khoảng im lặng đầu file audio bằng FFmpeg.
    
    Args:
        input_path: Đường dẫn file audio
        output_path: Đường dẫn output (None = ghi đè file gốc)
    
    Returns:
        bool: True nếu thành công
    """
    if output_path is None:
        if input_path.endswith(".wav"):
            temp_path = input_path.replace(".wav", "_temp.wav")
        else:
            temp_path = input_path.replace(".mp3", "_temp.mp3")
    else:
        temp_path = output_path
    
    try:
        # FFmpeg filter: cắt khoảng lặng đầu file
        filter_str = "silenceremove=start_periods=1:start_threshold=-50dB"
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-af', filter_str
        ]
        
        # Codec theo extension
        if input_path.lower().endswith(".wav"):
            cmd.extend(['-c:a', 'pcm_s16le'])
        else:
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])

        cmd.append(temp_path)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Nếu không có output_path, ghi đè file gốc
        if output_path is None:
            os.remove(input_path)
            os.rename(temp_path, input_path)
        
        return True
        
    except Exception as e:
        logging.error(f"Lỗi trim silence: {e}")
        if os.path.exists(temp_path) and output_path is None:
            try:
                os.remove(temp_path)
            except:
                pass
        return False


# ========== UTILITY: Extract Text Only from SRT (for translation) ==========
def extract_text_from_srt(srt_path, output_txt_path):
    """Trích xuất text từ file SRT (không có timing)"""
    logging.info(f"Extract text from SRT: {os.path.basename(srt_path)}")
    
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r'\n\s*\n', content.strip())
        texts = []

        for block in blocks:
            lines = block.strip().split("\n")
            # Tìm dòng có timestamp
            for idx, line in enumerate(lines):
                if "-->" in line:
                    # Text nằm sau dòng timestamp
                    text_lines = lines[idx+1:]
                    if text_lines:
                        texts.append(" ".join(text_lines))
                    break

        with open(output_txt_path, "w", encoding="utf-8") as f:
            for t in texts:
                f.write(t + "\n")

        logging.info(f"Extracted {len(texts)} lines -> {output_txt_path}")
        return True, len(texts)

    except Exception as e:
        logging.error(f"Lỗi extract_text_from_srt: {e}")
        return False, str(e)
