import os
import re
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

import sys

# ============================================================================
# SIÊU PATCH: CHẶN TASKBAR ICON VÀ CỬA SỔ CMD
# ============================================================================
if os.name == 'nt':
    # 1. Thiết lập cấu hình khởi tạo tiến trình ẩn
    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _startupinfo.wShowWindow = subprocess.SW_HIDE
    
    _creationflags = 0x08000000  # CREATE_NO_WINDOW

    # 2. Patch subprocess.Popen gốc
    _original_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        kwargs['startupinfo'] = _startupinfo
        kwargs['creationflags'] = _creationflags
        return _original_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen

    # 3. Ép asyncio dùng ProactorEventLoop (tránh nháy cửa sổ khi dùng edge-tts)
    if sys.version_info >= (3, 7):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ============================================================================

# Cố gắng import edge_tts, nếu chưa có thì log warning
try:
    import edge_tts
except ImportError:
    edge_tts = None
    logging.warning("Thư viện 'edge-tts' chưa được cài đặt. Hãy chạy: pip install edge-tts")

# Import FFmpeg helper for bundled executable support
try:
    from app.core.ffmpeg_helper import FFMPEG_PATH, FFPROBE_PATH
except ImportError:
    try:
        from core.ffmpeg_helper import FFMPEG_PATH, FFPROBE_PATH
    except ImportError:
        # Fallback to system PATH
        FFMPEG_PATH = 'ffmpeg'
        FFPROBE_PATH = 'ffprobe'

class SRTEntry:
    def __init__(self, index, start_ms, end_ms, text):
        self.index = index
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text
        self.duration_ms = end_ms - start_ms

    def __repr__(self):
        return f"SRTEntry(#{self.index}, {self.start_ms}-{self.end_ms}ms, '{self.text}')"

def parse_srt_file(srt_path: str) -> List[SRTEntry]:
    """Đọc file SRT và trả về danh sách SRTEntry"""
    if not os.path.exists(srt_path):
        return []

    entries = []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # Tách các block bằng 2 dòng trống (chuẩn SRT)
    blocks = re.split(r'\n\s*\n', content)
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            try:
                index = int(lines[0])
                # Parse timestamp: 00:00:01,500 --> 00:00:03,000
                times = lines[1].split('-->')
                start_ms = _srt_time_to_ms(times[0].strip())
                end_ms = _srt_time_to_ms(times[1].strip())
                # Text có thể nhiều dòng, nối lại
                text = " ".join(lines[2:])
                entries.append(SRTEntry(index, start_ms, end_ms, text))
            except Exception as e:
                logging.warning(f"Lỗi parse block SRT: {lines[0]} - {e}")
                continue
                
    return entries

def _srt_time_to_ms(time_str: str) -> int:
    """Chuyển 00:00:01,500 thành milliseconds"""
    # Fix format if comma is dot
    time_str = time_str.replace('.', ',')
    hours, minutes, seconds = time_str.split(':')
    seconds, millis = seconds.split(',')
    
    return (int(hours) * 3600000 + 
            int(minutes) * 60000 + 
            int(seconds) * 1000 + 
            int(millis))

def get_safe_filename(index: int, text: str) -> str:
    """Tạo tên file an toàn từ index và text"""
    # Xử lý text để loại bỏ ký tự đặc biệt
    safe_text = re.sub(r'[^\w\s-]', '', text)[:30].replace(' ', '_')
    return f"{index:03d}_{safe_text}.wav"

def validate_generated_files(entries: List[SRTEntry], output_dir: str) -> List[SRTEntry]:
    """Kiểm tra các file đã tạo, trả về danh sách các entry bị lỗi (thiếu hoặc 0 byte)"""
    failed = []
    for entry in entries:
        filename = get_safe_filename(entry.index, entry.text)
        path = os.path.join(output_dir, filename)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            failed.append(entry)
    return failed

async def generate_single_audio(text, voice, rate, volume, pitch, output_path):
    if not edge_tts:
        return False
    try:
        # Determine strict output format
        is_wav = output_path.lower().endswith(".wav")
        
        # Temp path for raw edge-tts output (MP3)
        temp_mp3 = output_path + ".temp.mp3" if is_wav else output_path
        
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
        await communicate.save(temp_mp3)
        
        if is_wav:
            # Convert MP3 to WAV using FFmpeg
            
            # Helper for Windows to hide window in asyncio subprocess
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = 0x08000000 # CREATE_NO_WINDOW
            
            # Async subprocess to avoid blocking
            proc = await asyncio.create_subprocess_exec(
                'ffmpeg', '-y', '-i', temp_mp3, '-f', 'wav', output_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            await proc.wait()
            
            # Clean temp
            if os.path.exists(temp_mp3):
                try:
                    os.remove(temp_mp3)
                except: pass
                
            if proc.returncode != 0:
                logging.error(f"Failed to convert to wav: {output_path}")
                return False

        # Validate file size > 0
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logging.error(f"❌ Error: Generated file is 0KB (Empty): {output_path}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False

        return True
    except Exception as e:
        logging.error(f"Lỗi generate audio '{text[:20]}...': {e}")
        return False

async def generate_batch_audio_logic(
    entries: List[SRTEntry], 
    output_dir: str, 
    voice="vi-VN-HoaiMyNeural", 
    rate="+0%", 
    volume="+0%", 
    pitch="+0Hz",
    max_concurrent=5,
    stop_event=None,
    progress_callback=None
) -> List[Tuple[str, int]]:
    """
    Tạo audio cho toàn bộ danh sách entries.
    Trả về list: [(file_path, start_time_ms), ...]
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    total_items = len(entries)
    completed_count = [0]

    async def generate_one(entry):
        async with semaphore:
            if stop_event and stop_event.is_set():
                return None
            # Tạo tên file an toàn
            filename = get_safe_filename(entry.index, entry.text)
            path = os.path.join(output_dir, filename)
            
            # Nếu file đã tồn tại và size > 0 thì bỏ qua (resume)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                logging.info(f"Skipped (Existed): {filename}")
                
                # Update progress
                completed_count[0] += 1
                if progress_callback:
                    progress_callback(completed_count[0], total_items, f"Skipped: {filename}")
                
                return (path, entry.start_ms)

            if stop_event and stop_event.is_set():
                return None
            success = await generate_single_audio(entry.text, voice, rate, volume, pitch, path)
            
            # Update progress
            completed_count[0] += 1
            if progress_callback:
                if success:
                    progress_callback(completed_count[0], total_items, f"Generated: {filename}")
                else:
                    progress_callback(completed_count[0], total_items, f"Failed: {filename}")

            if success:
                logging.info(f"Generated: {filename}")
                return (path, entry.start_ms)
            else:
                return None

    tasks = [generate_one(entry) for entry in entries]
    results = await asyncio.gather(*tasks)
    
    # Filter None và sort theo thời gian
    valid_results = [r for r in results if r]
    valid_results.sort(key=lambda x: x[1])
    
    return valid_results

def merge_audio_files_ffmpeg(file_list: List[Tuple[str, int]], output_path: str, stop_event=None):
    """
    Ghép audio sử dụng FFmpeg adelay và amix.
    Xử lý batching để tránh lỗi "Argument list too long" hoặc giới hạn input của ffmpeg.
    """
    if not file_list:
        return False
    
    # Chia nhỏ thành các batch (ví dụ 32 file một lần) để tránh quá tải filter complex
    BATCH_SIZE = 32
    temp_files = []
    
    try:
        # Nếu chỉ có 1 file, copy luôn
        if len(file_list) == 1:
            cmd = [FFMPEG_PATH, '-y', '-i', file_list[0][0], '-c', 'copy', output_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

        # Process từng batch
        for i in range(0, len(file_list), BATCH_SIZE):
            if stop_event and stop_event.is_set():
                logging.warning("Merge stopped by user.")
                return False
            batch = file_list[i : i + BATCH_SIZE]
            logging.info(f"Merging batch {i//BATCH_SIZE + 1} with {len(batch)} files...")
            
            root, ext = os.path.splitext(output_path)
            temp_output = f"{root}_temp_batch_{i}{ext}"
            _merge_small_batch(batch, temp_output)
            temp_files.append(temp_output)
        
        # Merge các file temp lại với nhau
        if len(temp_files) == 1:
             if os.path.exists(output_path): os.remove(output_path)
             os.rename(temp_files[0], output_path)
             return True
             
        # Mix các temp files
        logging.info("Mixing batch results...")
        cmd_final = ['ffmpeg', '-y']
        for tf in temp_files:
            if stop_event and stop_event.is_set():
                logging.warning("Merge stopped by user.")
                return False
            cmd_final.extend(['-i', tf])
            
        # amix tất cả temp files
        mix_inputs = "".join([f"[{i}:a]" for i in range(len(temp_files))])
        filter_complex = f"{mix_inputs}amix=inputs={len(temp_files)}:duration=longest:dropout_transition=0:normalize=0[out]"
        
        cmd_final.extend(['-filter_complex', filter_complex, '-map', '[out]'])
        
        if output_path.lower().endswith(".wav"):
             cmd_final.extend(['-c:a', 'pcm_s16le'])
        else:
             cmd_final.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
             
        cmd_final.append(output_path)
        
        subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Clean temp
        for tf in temp_files:
            if os.path.exists(tf): os.remove(tf)
            
        return True

    except Exception as e:
        logging.error(f"Lỗi merge ffmpeg: {e}")
        return False

def _merge_small_batch(batch_list, output_file):
    """
    Hàm helper để merge 1 nhóm nhỏ audio file dùng adelay + amix
    """
    cmd = [FFMPEG_PATH, '-y']
    filter_parts = []
    
    # Input files
    for idx, (path, start_ms) in enumerate(batch_list):
        cmd.extend(['-i', path])
        # Delay: adelay=1000|1000 (cho cả channel trái phải nếu stereo, hoặc just 1000 if mono logic handles it automatically usually but explicit pipes safer)
        # Lưu ý: adelay nhận duration in milliseconds
        filter_parts.append(f"[{idx}:a]adelay={start_ms}|{start_ms}[a{idx}]")
    
    # Amix
    mix_inputs = "".join([f"[a{i}]" for i in range(len(batch_list))])
    # normalize=0 để tránh volume bị giảm khi mix nhiều file
    filter_complex = ";".join(filter_parts) + \
                     f";{mix_inputs}amix=inputs={len(batch_list)}:duration=longest:dropout_transition=0:normalize=0[out]"
    
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[out]'
    ])
    
    if output_file.lower().endswith(".wav"):
         cmd.extend(['-c:a', 'pcm_s16le'])
    else:
         cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
         
    cmd.append(output_file)
    
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@dataclass
class AudioSegment:
    """Thông tin một đoạn audio"""
    index: int
    audio_path: str
    srt_start_ms: int
    srt_end_ms: int
    srt_duration_ms: int
    actual_duration_ms: int
    overflow_ms: int
    overflow_percent: float
    
    @property
    def has_overflow(self) -> bool:
        """Audio có dài hơn thời gian cho phép không"""
        return self.actual_duration_ms > self.srt_duration_ms
    
    @property
    def overflow_ratio(self) -> float:
        """Tỷ lệ vượt quá (1.0 = không vượt, 1.5 = vượt 50%)"""
        return self.actual_duration_ms / self.srt_duration_ms if self.srt_duration_ms > 0 else 1.0


@dataclass
class MergeAnalysis:
    """Phân tích kết quả trước khi ghép"""
    total_segments: int
    overflow_segments: int
    max_overflow_ratio: float
    max_overflow_segment: Optional[AudioSegment]
    top_overflow_segments: List[AudioSegment] # NEW: List top segments
    recommended_time_scale: float
    original_duration_ms: int
    adjusted_duration_ms: int
    segments: List[AudioSegment]
    
    def __str__(self) -> str:
        """Hiển thị thông tin phân tích"""
        lines = [
            "=" * 70,
            "📊 PHÂN TÍCH TỐC ĐỘ (ĐỀ XUẤT)",
            "=" * 70,
            f"Tổng số đoạn audio: {self.total_segments}",
            f"Số đoạn vượt thời gian: {self.overflow_segments} ({self.overflow_segments/self.total_segments*100:.1f}%)",
            "",
        ]
        
        if self.top_overflow_segments:
            lines.append("⚠️  CÁC ĐOẠN VƯỢT THỜI GIAN DÀI NHẤT (Top 5):")
            for i, seg in enumerate(self.top_overflow_segments, 1):
                safe_name = os.path.basename(seg.audio_path)
                lines.extend([
                    f" {i}. {safe_name} (Index #{seg.index + 1})",
                    f"    - Thời gian SRT: {seg.srt_duration_ms}ms | Thực tế: {seg.actual_duration_ms}ms",
                    f"    - Vượt: {seg.overflow_ms}ms | Tỷ lệ: {seg.overflow_ratio:.2f}x",
                ])
            lines.append("")
        
        lines.extend([
            "📏 ĐỀ XUẤT ĐIỀU CHỈNH:",
            f"   - Hệ số tốc độ (Speed Factor): {self.recommended_time_scale:.2f}x",
            f"   - Thời gian gốc: {self.original_duration_ms/1000:.2f}s",
            f"   - Thời gian sau điều chỉnh: {self.adjusted_duration_ms/1000:.2f}s",
            f"   - Tăng thêm: {(self.adjusted_duration_ms - self.original_duration_ms)/1000:.2f}s",
            "=" * 70,
        ])
        
        return "\n".join(lines)


class IntelligentAudioMerger:
    """Công cụ ghép audio thông minh"""
    
    def __init__(self, min_scale: float = 1.1, max_scale: float = 1.4):
        """
        Args:
            min_scale: Hệ số mở rộng tối thiểu (1.1 = +10%)
            max_scale: Hệ số mở rộng tối đa (1.4 = +40%)
        """
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.batch_size = 32
        
    def get_audio_duration(self, audio_path: str) -> int:
        """Lấy thời lượng thực tế của file audio (milliseconds)"""
        try:
            cmd = [
                FFPROBE_PATH, '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration_seconds = float(result.stdout.strip())
            return int(duration_seconds * 1000)
        except Exception as e:
            logging.error(f"Không thể lấy thời lượng audio {audio_path}: {e}")
            return 0
    
    def analyze_audio_files(self, audio_dir: str, srt_path: str) -> MergeAnalysis:
        """
        Phân tích các file audio so với timeline SRT
        """
        # Parse SRT
        srt_segments = parse_srt_file(srt_path)
        
        # Phân tích từng đoạn
        audio_segments = []
        max_overflow_ratio = 1.0
        max_overflow_segment = None
        overflow_count = 0
        
        for entry in srt_segments:
            # Logic quét file
            prefix_pattern = f"{entry.index:03d}_"
            simple_pattern = f"{entry.index}.wav"
            
            audio_path = os.path.join(audio_dir, f"{entry.index:03d}_unknown.wav")
            
            if os.path.exists(audio_dir):
                for f in os.listdir(audio_dir):
                     if f.startswith(prefix_pattern) and (f.endswith(".mp3") or f.endswith(".wav")):
                         audio_path = os.path.join(audio_dir, f)
                         break
                     elif f == simple_pattern:
                         audio_path = os.path.join(audio_dir, f)
                         break
            
            actual_duration = 0
            if os.path.exists(audio_path):
                actual_duration = self.get_audio_duration(audio_path)

            srt_duration = entry.duration_ms
            overflow = actual_duration - srt_duration
            overflow_percent = (overflow / srt_duration * 100) if srt_duration > 0 else 0
            
            segment = AudioSegment(
                index=entry.index - 1, 
                audio_path=audio_path,
                srt_start_ms=entry.start_ms,
                srt_end_ms=entry.end_ms,
                srt_duration_ms=srt_duration,
                actual_duration_ms=actual_duration,
                overflow_ms=overflow,
                overflow_percent=overflow_percent
            )
            
            audio_segments.append(segment)
            
            if segment.has_overflow:
                overflow_count += 1
                if segment.overflow_ratio > max_overflow_ratio:
                    max_overflow_ratio = segment.overflow_ratio
                    max_overflow_segment = segment
        
        # Get Top 5 Overflow Segments
        # Sort by overflow ratio descending
        sorted_by_ratio = sorted(
            [s for s in audio_segments if s.has_overflow], 
            key=lambda x: x.overflow_ratio, 
            reverse=True
        )
        top_overflow = sorted_by_ratio[:5]

        # Tính hệ số mở rộng đề xuất
        if max_overflow_ratio > 1.0:
            recommended_scale = min(
                max(max_overflow_ratio * 1.05, self.min_scale),  # +5% buffer
                self.max_scale
            )
        else:
            recommended_scale = 1.0
        
        original_duration = srt_segments[-1].end_ms if srt_segments else 0
        adjusted_duration = int(original_duration * recommended_scale)
        
        return MergeAnalysis(
            total_segments=len(audio_segments),
            overflow_segments=overflow_count,
            max_overflow_ratio=max_overflow_ratio,
            max_overflow_segment=max_overflow_segment,
            top_overflow_segments=top_overflow,
            recommended_time_scale=recommended_scale,
            original_duration_ms=original_duration,
            adjusted_duration_ms=adjusted_duration,
            segments=audio_segments
        )
    
    def calculate_adjusted_timeline(
        self, 
        analysis: MergeAnalysis, 
        time_scale: Optional[float] = None
    ) -> List[Tuple[str, int]]:
        """
        Tính toán timeline mới với thời gian đã điều chỉnh
        
        Args:
            analysis: Kết quả phân tích
            time_scale: Hệ số mở rộng (None = dùng recommended)
        
        Returns:
            List[(audio_path, adjusted_start_ms)]
        """
        if time_scale is None:
            time_scale = analysis.recommended_time_scale
        
        adjusted_timeline = []
        
        for segment in analysis.segments:
            # Điều chỉnh thời gian bắt đầu
            adjusted_start = int(segment.srt_start_ms * time_scale)
            if os.path.exists(segment.audio_path):
                 adjusted_timeline.append((segment.audio_path, adjusted_start))
        
        return adjusted_timeline
    
    def merge_with_adjusted_timeline(
        self,
        adjusted_timeline: List[Tuple[str, int]],
        output_path: str,
        stop_event=None
    ) -> bool:
        """
        Ghép audio với timeline đã điều chỉnh
        
        Args:
            adjusted_timeline: [(audio_path, start_ms)]
            output_path: Đường dẫn file output
            stop_event: Event để dừng quá trình
        
        Returns:
            bool: True nếu thành công
        """
        if not adjusted_timeline:
            logging.error("No audio files to merge")
            return False
        
        temp_files = []
        
        try:
            # Nếu chỉ có 1 file
            if len(adjusted_timeline) == 1:
                cmd = [FFMPEG_PATH, '-y', '-i', adjusted_timeline[0][0], '-c', 'copy', output_path]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            
            # Chia thành batch
            for i in range(0, len(adjusted_timeline), self.batch_size):
                if stop_event and stop_event.is_set():
                    logging.warning("Merge stopped by user")
                    return False
                
                batch = adjusted_timeline[i:i + self.batch_size]
                logging.info(f"Merging batch {i//self.batch_size + 1}/{(len(adjusted_timeline)-1)//self.batch_size + 1}...")
                
                root, ext = os.path.splitext(output_path)
                temp_output = f"{root}_temp_batch_{i}{ext}"
                self._merge_small_batch(batch, temp_output)
                temp_files.append(temp_output)
            
            # Merge các batch lại
            if len(temp_files) == 1:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_files[0], output_path)
                return True
            
            # Mix các temp files
            logging.info("Mixing batch results...")
            cmd_final = ['ffmpeg', '-y']
            
            for tf in temp_files:
                if stop_event and stop_event.is_set():
                    return False
                cmd_final.extend(['-i', tf])
            
            # amix
            mix_inputs = "".join([f"[{i}:a]" for i in range(len(temp_files))])
            filter_complex = f"{mix_inputs}amix=inputs={len(temp_files)}:duration=longest:dropout_transition=0:normalize=0[out]"
            
            cmd_final.extend(['-filter_complex', filter_complex, '-map', '[out]'])
            
            if output_path.lower().endswith(".wav"):
                 cmd_final.extend(['-c:a', 'pcm_s16le'])
            else:
                 cmd_final.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
                 
            cmd_final.append(output_path)
            
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Xóa temp files
            for tf in temp_files:
                if os.path.exists(tf):
                    os.remove(tf)
            
            return True
            
        except Exception as e:
            logging.error(f"Error merging audio: {e}")
            # Cleanup
            for tf in temp_files:
                if os.path.exists(tf):
                    os.remove(tf)
            return False
    
    def _merge_small_batch(self, batch_list: List[Tuple[str, int]], output_file: str):
        """Merge một batch nhỏ audio files"""
        cmd = [FFMPEG_PATH, '-y']
        filter_parts = []
        
        # Input files và adelay

        for idx, (path, start_ms) in enumerate(batch_list):
            cmd.extend(['-i', path])
            filter_parts.append(f"[{idx}:a]adelay={start_ms}|{start_ms}[a{idx}]")
        
        # Amix
        mix_inputs = "".join([f"[a{i}]" for i in range(len(batch_list))])
        filter_complex = ";".join(filter_parts) + \
                        f";{mix_inputs}amix=inputs={len(batch_list)}:duration=longest:dropout_transition=0:normalize=0[out]"
        
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[out]'
        ])
        
        if output_file.lower().endswith(".wav"):
             cmd.extend(['-c:a', 'pcm_s16le'])
        else:
             cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
             
        cmd.append(output_file)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def smart_merge(
        self,
        audio_dir: str,
        srt_path: str,
        output_path: str,
        auto_adjust: bool = True,
        custom_scale: Optional[float] = None,
        stop_event=None
    ) -> Tuple[bool, Optional[MergeAnalysis]]:
        """
        Ghép audio thông minh với phân tích và điều chỉnh tự động
        
        Args:
            audio_dir: Thư mục chứa audio files
            srt_path: File SRT
            output_path: File output
            auto_adjust: Tự động điều chỉnh timeline nếu có overflow
            custom_scale: Hệ số mở rộng tùy chỉnh (None = dùng recommended)
            stop_event: Event để dừng
        
        Returns:
            (success, analysis)
        """
        # Bước 1: Phân tích
        logging.info("🔍 Analyzing audio files...")
        analysis = self.analyze_audio_files(audio_dir, srt_path)
        
        logging.info(str(analysis))
        
        # Bước 2: Quyết định có điều chỉnh không
        if analysis.overflow_segments > 0 and auto_adjust:
            logging.info(f"⚙️  Adjusting timeline with scale factor: {analysis.recommended_time_scale:.2f}x")
            adjusted_timeline = self.calculate_adjusted_timeline(analysis, custom_scale)
        else:
            logging.info("✅ No adjustment needed, using original timeline")
            adjusted_timeline = self.calculate_adjusted_timeline(analysis, 1.0)
        
        # Bước 3: Ghép
        logging.info("🎵 Merging audio files...")
        success = self.merge_with_adjusted_timeline(adjusted_timeline, output_path, stop_event)
        
        if success:
            logging.info(f"✅ Successfully merged to: {output_path}")
        else:
            logging.error("❌ Failed to merge audio files")
        
        return success, analysis


# ============================================================================
# UTILITY FUNCTIONS - Dễ dàng tích hợp vào code hiện tại
# ============================================================================

def analyze_before_merge(audio_dir: str, srt_path: str, 
                         min_scale: float = 1.1, max_scale: float = 1.4) -> MergeAnalysis:
    """
    Wrapper function: Phân tích trước khi ghép
    """
    merger = IntelligentAudioMerger(min_scale, max_scale)
    return merger.analyze_audio_files(audio_dir, srt_path)


def merge_audio_intelligent(audio_dir: str, srt_path: str, output_path: str,
                            auto_adjust: bool = True, 
                            custom_scale: Optional[float] = None,
                            stop_event=None) -> bool:
    """
    Wrapper function: Ghép audio thông minh
    """
    merger = IntelligentAudioMerger()
    success, _ = merger.smart_merge(audio_dir, srt_path, output_path, 
                                    auto_adjust, custom_scale, stop_event)
    return success

def trim_silence_from_audio_simple(input_path: str, output_path: str = None) -> bool:
    """
    Cắt bỏ khoảng im lặng - version đơn giản hơn (nhanh hơn)
    Chỉ cắt đầu và cuối, không quá aggressive
    """
    if output_path is None:
        if input_path.endswith(".wav"):
             temp_path = input_path.replace(".wav", "_temp.wav")
        else:
             temp_path = input_path.replace(".mp3", "_temp.mp3")
    else:
        temp_path = output_path
    
    try:
        # Get duration before
        dur_before = 0
        try:
            cmd_probe = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_path]
            res = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
            dur_before = int(float(res.stdout.strip()) * 1000)
        except: pass

        # Use validated filter from test script
        # Filter: remove start silence ONLY
        filter_str = "silenceremove=start_periods=1:start_threshold=-50dB"
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-af', filter_str
        ]
        
        # Determine codec based on extension
        if input_path.lower().endswith(".wav"):
             cmd.extend(['-c:a', 'pcm_s16le'])
        else:
             cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])

        cmd.extend([temp_path])
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if output_path is None:
            os.remove(input_path)
            os.rename(temp_path, input_path)
            final_path = input_path
        else:
            final_path = output_path
        
        # Get duration after
        dur_after = 0
        try:
            cmd_probe = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', final_path]
            res = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
            dur_after = int(float(res.stdout.strip()) * 1000)
        except: pass
        
        reduced = dur_before - dur_after
        logging.info(f"✂️ Trimmed {os.path.basename(input_path)}: {dur_before}ms -> {dur_after}ms (Reduced: {reduced}ms)")

        return True
        
    except Exception as e:
        logging.error(f"Lỗi trim silence: {e}")
        if os.path.exists(temp_path) and output_path is None:
            os.remove(temp_path)
        return False

def batch_trim_audio_directory(audio_dir: str, backup: bool = True):
    """
    Trim silence cho tất cả file trong thư mục
    
    Args:
        audio_dir: Thư mục chứa audio
        backup: True = backup file gốc trước khi trim
    """
    import glob
    import shutil
    
    audio_files = glob.glob(os.path.join(audio_dir, "*.mp3")) + glob.glob(os.path.join(audio_dir, "*.wav"))
    if not audio_files:
        logging.warning("No audio files (mp3/wav) found to trim.")
        return 0
    
    # Create backup directory outside (sibling)
    clean_audio_dir = os.path.normpath(audio_dir)
    backup_dir = f"{clean_audio_dir}_backup"
    if backup:
        os.makedirs(backup_dir, exist_ok=True)
        logging.info(f"Backing up to: {backup_dir}")
    
    total = len(audio_files)
    success_count = 0
    
    logging.info(f"Trimming {total} audio files...")
    
    for idx, audio_path in enumerate(audio_files, 1):
        filename = os.path.basename(audio_path)
        
        # Skip temp files or backup files if logic grabs them
        if "_temp" in filename or "_merged" in filename: 
            continue

        # Backup nếu cần
        if backup:
            backup_path = os.path.join(backup_dir, filename)
            shutil.copy2(audio_path, backup_path)
        
        logging.info(f"Processing ({idx}/{total}): {filename}")
        
        # Sử dụng logic mới: Phân tích silencedetect -> Cắt đoạn giữa
        success = trim_silence_advanced(audio_path)
        
        if success:
            success_count += 1
            # Log mỗi 10 file hoặc log hết nếu cần
            if idx % 5 == 0:
                logging.info(f"⏳ Progress: {idx}/{total} ({success_count} success)")
        else:
            logging.warning(f"❌ Failed to trim: {filename}")
    
    logging.info(f"✅ DONE. Trimmed {success_count}/{total} files.")
    return success_count

def get_silence_intervals(file_path: str, threshold: str = "-50dB", duration: float = 0.1) -> List[Tuple[float, float, float]]:
    """
    Phát hiện các khoảng lặng sử dụng ffmpeg silencedetect
    Trả về: List[(start, end, duration)]
    """
    cmd = [
        FFMPEG_PATH,
        '-i', file_path,
        '-af', f'silencedetect=noise={threshold}:d={duration}',
        '-f', 'null',
        '-'
    ]
    
    try:
        # ffmpeg output to stderr
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        output = result.stderr
        
        silences = []
        current_start = None
        
        for line in output.split('\n'):
            if 'silence_start' in line:
                match = re.search(r'silence_start: (\d+(\.\d+)?)', line)
                if match:
                    current_start = float(match.group(1))
            elif 'silence_end' in line:
                match_end = re.search(r'silence_end: (\d+(\.\d+)?)', line)
                match_dur = re.search(r'silence_duration: (\d+(\.\d+)?)', line)
                if match_end and current_start is not None:
                    end = float(match_end.group(1))
                    dur = float(match_dur.group(1)) if match_dur else (end - current_start)
                    silences.append((current_start, end, dur))
                    current_start = None
                    
        return silences
    except Exception as e:
        logging.error(f"Error silencedetect {file_path}: {e}")
        return []

def trim_silence_advanced(input_path: str) -> bool:
    """
    Cắt khoảng lặng dựa trên phân tích (logic strictly from test script):
    - Tìm First Silence (nếu ở đầu file) và cắt bỏ.
    - Giữ nguyên phần đuôi (không cắt silence cuối).
    """
    try:
        # Detect intervals - High sensitivity
        silences = get_silence_intervals(input_path, threshold="-50dB", duration=0.1)
        
        if not silences:
            # logging.info(f"Skipped {os.path.basename(input_path)}: No silence detected.")
            return False
            
        # 1. Check First Silence Segment
        start_cut = 0.0
        if silences:
            first = silences[0] # (start, end, duration)
            # Nếu silence bắt đầu ở 0 (cho phép sai số < 0.2s)
            if first[0] < 0.2:
                start_cut = first[1]
        
        if start_cut == 0.0:
            return False 

        # 3. Extract Audio
        root, ext = os.path.splitext(input_path)
        temp_path = f"{root}_temp_trim{ext}"
        
        cmd = [
            FFMPEG_PATH, '-y',
            '-ss', str(start_cut),
            '-i', input_path,
        ]
        
        if ext.lower() == ".wav":
             cmd.extend(['-c:a', 'pcm_s16le'])
        else:
             cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
             
        cmd.append(temp_path)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Replace original
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            if os.path.exists(input_path):
                os.remove(input_path)
            os.rename(temp_path, input_path)
            
            logging.info(f"✅ Trimmed Start: {os.path.basename(input_path)} (Removed first {start_cut:.2f}s)")
            return True
        else:
            logging.error("Trim failed (output empty/missing).")
            return False
        
    except Exception as e:
        logging.error(f"Error trimming {os.path.basename(input_path)}: {e}")
        return False

def sort_srt_captions_by_duration(srt_path: str, output_report_path: str) -> bool:
    """
    Phân tích file SRT và tạo danh sách các caption sắp xếp theo thời gian (ngắn -> dài).
    Kết quả lưu vào file txt.
    """
    logging.info(f"Analyzing SRT Duration: {os.path.basename(srt_path)}")
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse blocks
        blocks = re.split(r'\n\s*\n', content.strip())
        parsed_data = [] # List of dict: {index, start, end, duration, text}

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 2: continue
            
            # Find timestamp line
            timestamp_idx = -1
            for idx, line in enumerate(lines):
                if "-->" in line:
                    timestamp_idx = idx
                    break
            
            if timestamp_idx != -1:
                # Get Index
                try:
                    seq_index = lines[timestamp_idx-1].strip() if timestamp_idx > 0 else "0"
                except: seq_index = "?"

                # Get Timing
                time_line = lines[timestamp_idx]
                match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
                if match:
                    t_start = match.group(1)
                    t_end = match.group(2)
                    
                    # Calculate duration
                    def t_to_ms(t_str):
                        h, m, s, ms = map(int, re.split('[:,]', t_str))
                        return (h*3600 + m*60 + s) * 1000 + ms
                        
                    dur_ms = t_to_ms(t_end) - t_to_ms(t_start)
                    
                    # Get Text
                    text_content = " ".join(lines[timestamp_idx+1:])
                    
                    parsed_data.append({
                        "index": seq_index,
                        "start": t_start,
                        "end": t_end,
                        "duration_ms": dur_ms,
                        "text": text_content
                    })

        # Sort by duration ascending
        parsed_data.sort(key=lambda x: x["duration_ms"])
        
        # Write Report
        with open(output_report_path, "w", encoding="utf-8") as f:
            f.write(f"REPORT: SRT DURATION ANALYSIS (Sorted Shortest -> Longest)\n")
            f.write(f"Source: {os.path.basename(srt_path)}\n")
            f.write(f"Total Lines: {len(parsed_data)}\n")
            f.write("="*80 + "\n")
            f.write(f"{'Index':<10} | {'Duration':<15} | {'Timing':<30} | {'Content'}\n")
            f.write("="*80 + "\n")
            
            for item in parsed_data:
                dur_sec = item["duration_ms"] / 1000.0
                timing = f"{item['start']} --> {item['end']}"
                content_preview = (item['text'][:40] + '...') if len(item['text']) > 40 else item['text']
                f.write(f"{item['index']:<10} | {dur_sec:6.2f}s        | {timing:<30} | {content_preview}\n")

        logging.info(f"Report generated: {output_report_path}")
        return True, len(parsed_data)

    except Exception as e:
        logging.error(f"Error analyzing SRT: {e}")
        return False, 0
