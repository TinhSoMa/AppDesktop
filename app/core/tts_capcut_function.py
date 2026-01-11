"""
Module TTS CapCut - Chuyển văn bản thành giọng nói sử dụng dịch vụ CapCut.

Cung cấp các hàm đơn giản để tạo file audio từ văn bản:
- tts_single(): Tạo 1 file audio từ 1 đoạn text
- tts_batch(): Tạo nhiều file audio từ danh sách text
- tts_batch_sync(): Phiên bản đồng bộ của tts_batch()
"""

import asyncio
import json
import os
from typing import List, Optional, Callable, Dict
from dataclasses import dataclass

try:
    import websockets
except ImportError:
    raise ImportError("Thư viện 'websockets' chưa được cài đặt. Vui lòng chạy: pip install websockets")

# Import config
from app.config.tts_capcut_config import TTSCapCutConfig
from app.config.list_voice_capcut import DEFAULT_SPEAKER, get_voice_id_by_name


# ============ Data Classes ============

@dataclass
class TTSResult:
    """Kết quả TTS cho một đoạn text."""
    index: int
    text: str
    output_path: str
    duration: float
    success: bool
    error_message: str = ""


# ============ Async Functions ============

async def tts_batch(
    texts: List[str],
    output_dir: str,
    speaker: str = None,
    audio_format: str = "wav",
    speech_rate: int = 0,
    filename_pattern: str = "{index:03d}.{ext}",
    verbose: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[TTSResult]:
    """
    Tạo nhiều file audio từ danh sách văn bản (async version).
    Sử dụng 1 WebSocket request duy nhất cho tất cả texts.
    
    Args:
        texts: Danh sách các văn bản cần chuyển thành giọng nói.
        output_dir: Thư mục chứa các file audio đầu ra.
        speaker: Mã giọng đọc hoặc tên giọng đọc. Mặc định: DEFAULT_SPEAKER.
        audio_format: Định dạng âm thanh ("ogg_opus", "wav", "mp3", "pcm").
        speech_rate: Tốc độ đọc (0: bình thường, >0: nhanh, <0: chậm).
        filename_pattern: Pattern đặt tên file, hỗ trợ {index} và {ext}.
        verbose: In thông tin chi tiết.
        progress_callback: Callback function(completed, total, filename).
    
    Returns:
        Danh sách TTSResult chứa kết quả cho từng text.
    
    Example:
        results = await tts_batch(
            texts=["Xin chào", "Tạm biệt"],
            output_dir="audio_output"
        )
    """
    if not texts:
        return []
    
    # Xử lý speaker - có thể là ID hoặc tên
    if speaker is None:
        speaker_id = DEFAULT_SPEAKER
    else:
        # Thử tìm ID theo tên, nếu không có thì dùng trực tiếp
        speaker_id = get_voice_id_by_name(speaker) or speaker
    
    # Xác định extension
    ext_map = {"ogg_opus": "ogg", "wav": "wav", "mp3": "mp3", "pcm": "pcm"}
    ext = ext_map.get(audio_format, "ogg")
    
    # Tạo thư mục output
    os.makedirs(output_dir, exist_ok=True)
    
    # Tạo mapping từ index -> output path
    total = len(texts)
    output_paths = {}
    for i in range(total):
        filename = filename_pattern.format(index=i+1, ext=ext)
        output_paths[i] = os.path.join(output_dir, filename)
    
    # Lưu trữ audio data và duration cho từng index
    audio_buffers: Dict[int, bytearray] = {i: bytearray() for i in range(total)}
    durations: Dict[int, float] = {i: 0.0 for i in range(total)}
    current_index = None
    
    if verbose:
        print(f"[TTS] Bắt đầu tạo {total} file audio...")
    
    # Payload cấu hình
    audio_config = TTSCapCutConfig.AUDIO_CONFIG.copy()
    audio_config.update({
        "format": audio_format,
        "speech_rate": speech_rate,
    })

    inner_payload = {
        "audio_config": audio_config,
        "speaker": speaker_id,
        "texts": texts
    }
    
    start_task_msg = {
        "appkey": TTSCapCutConfig.APPKEY,
        "event": "StartTask",
        "namespace": "TTS",
        "token": TTSCapCutConfig.TOKEN,
        "payload": json.dumps(inner_payload),
        "version": "sdk_v1"
    }

    try:
        async with websockets.connect(
            TTSCapCutConfig.WS_URL, 
            extra_headers=TTSCapCutConfig.HEADERS
        ) as websocket:
            if verbose:
                print(f"[TTS] Đã kết nối server")
            
            # Gửi StartTask
            await websocket.send(json.dumps(start_task_msg))
            if verbose:
                print(f"[TTS] Đã gửi yêu cầu với {total} texts")
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    
                    if isinstance(message, str):
                        try:
                            data = json.loads(message)
                            event = data.get("event")
                            
                            if event == "TaskStarted":
                                if verbose:
                                    print(f"[TTS] Task đã bắt đầu")
                                
                                # Gửi FinishTask ngay sau TaskStarted
                                finish_task_msg = {
                                    "appkey": TTSCapCutConfig.APPKEY,
                                    "event": "FinishTask",
                                    "namespace": "TTS",
                                    "token": TTSCapCutConfig.TOKEN,
                                    "version": "sdk_v1"
                                }
                                await websocket.send(json.dumps(finish_task_msg))
                            
                            elif event == "TTSResponse":
                                payload = json.loads(data.get("payload", "{}"))
                                idx = payload.get("index")
                                duration = payload.get("duration", 0)
                                
                                if idx is not None:
                                    current_index = idx
                                    durations[idx] = duration
                                    if verbose:
                                        text_preview = texts[idx][:30] if idx < len(texts) else ""
                                        print(f"[TTS] Đang xử lý [{idx+1}/{total}]: {text_preview}...")
                            
                            elif event == "TaskFinished":
                                if verbose:
                                    print(f"[TTS] Task hoàn thành")
                                break
                            
                            elif event == "TaskFailed":
                                if verbose:
                                    print(f"[TTS] Task thất bại: {data}")
                                break
                                
                        except json.JSONDecodeError:
                            pass
                    
                    elif isinstance(message, bytes):
                        # Nhận binary audio data
                        if current_index is not None and current_index < total:
                            audio_buffers[current_index].extend(message)
                
                except asyncio.TimeoutError:
                    if verbose:
                        print(f"[TTS] Timeout chờ dữ liệu")
                    break
                except websockets.exceptions.ConnectionClosed:
                    if verbose:
                        print(f"[TTS] Kết nối đóng")
                    break
        
        # Ghi các file audio và tạo kết quả
        results = []
        
        for i, text in enumerate(texts):
            output_path = output_paths[i]
            audio_data = bytes(audio_buffers[i])
            
            if audio_data:
                with open(output_path, "wb") as f:
                    f.write(audio_data)
                result = TTSResult(
                    index=i,
                    text=text,
                    output_path=output_path,
                    duration=durations[i],
                    success=True
                )
                if verbose:
                    print(f"[TTS] ✓ Đã lưu: {os.path.basename(output_path)}")
            else:
                result = TTSResult(
                    index=i,
                    text=text,
                    output_path=output_path,
                    duration=0,
                    success=False,
                    error_message="Không nhận được dữ liệu audio"
                )
                if verbose:
                    print(f"[TTS] ✗ Lỗi index {i}: {text[:30]}...")
            
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total, output_path)
        
        if verbose:
            success_count = sum(1 for r in results if r.success)
            print(f"[TTS] Hoàn thành: {success_count}/{total} files")
        
        return results
        
    except Exception as e:
        if verbose:
            print(f"[TTS] Lỗi: {e}")
        return [
            TTSResult(
                index=i,
                text=text,
                output_path=output_paths.get(i, ""),
                duration=0,
                success=False,
                error_message=str(e)
            )
            for i, text in enumerate(texts)
        ]


async def tts_single(
    text: str,
    output_path: str,
    speaker: str = None,
    audio_format: str = "wav",
    speech_rate: int = 0,
    verbose: bool = False
) -> TTSResult:
    """
    Tạo 1 file audio từ 1 đoạn văn bản (async version).
    
    Args:
        text: Văn bản cần chuyển thành giọng nói.
        output_path: Đường dẫn file audio đầu ra.
        speaker: Mã giọng đọc hoặc tên giọng đọc.
        audio_format: Định dạng âm thanh.
        verbose: In thông tin chi tiết.
    
    Returns:
        TTSResult chứa kết quả.
    
    Example:
        result = await tts_single(
            text="Xin chào",
            output_path="output/hello.wav"
        )
    """
    output_dir = os.path.dirname(output_path) or "."
    filename = os.path.basename(output_path)
    
    # Tách extension từ filename
    name_parts = filename.rsplit(".", 1)
    if len(name_parts) == 2:
        base_name, ext = name_parts
    else:
        base_name = filename
        ext = audio_format
    
    results = await tts_batch(
        texts=[text],
        output_dir=output_dir,
        speaker=speaker,
        audio_format=audio_format,
        speech_rate=speech_rate,
        filename_pattern=f"{base_name}.{{ext}}",
        verbose=verbose
    )
    
    if results:
        return results[0]
    else:
        return TTSResult(
            index=0,
            text=text,
            output_path=output_path,
            duration=0,
            success=False,
            error_message="Không có kết quả"
        )


# ============ Sync Wrapper Functions ============

def tts_batch_sync(
    texts: List[str],
    output_dir: str,
    speaker: str = None,
    audio_format: str = "wav",
    speech_rate: int = 0,
    filename_pattern: str = "{index:03d}.{ext}",
    verbose: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[TTSResult]:
    """
    Tạo nhiều file audio từ danh sách văn bản (sync version).
    Wrapper đồng bộ cho tts_batch().
    
    Args:
        texts: Danh sách các văn bản cần chuyển thành giọng nói.
        output_dir: Thư mục chứa các file audio đầu ra.
        speaker: Mã giọng đọc hoặc tên giọng đọc. Mặc định: DEFAULT_SPEAKER.
        audio_format: Định dạng âm thanh.
        speech_rate: Tốc độ đọc.
        filename_pattern: Pattern đặt tên file.
        verbose: In thông tin chi tiết.
        progress_callback: Callback function(completed, total, filename).
    
    Returns:
        Danh sách TTSResult chứa kết quả cho từng text.
    
    Example:
        results = tts_batch_sync(
            texts=["Xin chào", "Tạm biệt"],
            output_dir="audio_output"
        )
    """
    return asyncio.run(tts_batch(
        texts=texts,
        output_dir=output_dir,
        speaker=speaker,
        audio_format=audio_format,
        speech_rate=speech_rate,
        filename_pattern=filename_pattern,
        verbose=verbose,
        progress_callback=progress_callback
    ))


def tts_single_sync(
    text: str,
    output_path: str,
    speaker: str = None,
    audio_format: str = "wav",
    speech_rate: int = 0,
    verbose: bool = False
) -> TTSResult:
    """
    Tạo 1 file audio từ 1 đoạn văn bản (sync version).
    Wrapper đồng bộ cho tts_single().
    
    Args:
        text: Văn bản cần chuyển thành giọng nói.
        output_path: Đường dẫn file audio đầu ra.
        speaker: Mã giọng đọc hoặc tên giọng đọc.
        audio_format: Định dạng âm thanh.
        verbose: In thông tin chi tiết.
    
    Returns:
        TTSResult chứa kết quả.
    
    Example:
        result = tts_single_sync(
            text="Xin chào",
            output_path="output/hello.wav"
        )
    """
    return asyncio.run(tts_single(
        text=text,
        output_path=output_path,
        speaker=speaker,
        audio_format=audio_format,
        speech_rate=speech_rate,
        verbose=verbose
    ))
