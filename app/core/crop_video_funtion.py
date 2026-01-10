import subprocess
import os
import json
import re
import shutil

def parse_ffmpeg_progress(line):
    """
    Parse FFmpeg progress from stderr output.
    Returns time in seconds if found, else None.
    Example: "time=00:00:12.34" returns 12.34
    """
    match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return None


def get_duration(filename):
    """
    Get the duration of a video file in seconds using ffprobe.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename
        ]
        # Use shell=True for Windows to avoid path issues sometimes, or keep it safe with list. 
        # Usually subprocess.run with list is safer/better.
        # But if user provided raw commands, I 'll stick to the logic.
        
        # On windows, sometimes creationflags are needed to hide window
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0.0

def find_silence_time(filename, start_search, duration_to_scan=120):
    """
    Find the start timestamp of the first silence detected in the specified range.
    Returns the timestamp (float) or None if no silence is found.
    scans around the cut point (e.g. +/- 60s).
    The user guide says: "tìm điểm im lặng (silence) gần mốc thời gian đó (± 1 phút)".
    So if we want to cut at T, we scan T-60 to T+60.
    start_search should be T-60 (but >= 0).
    duration_to_scan should be 120 (or less if near end).
    """
    
    # ffmpeg -ss [start] -t [scan_duration] -i [input] -vn -sn -af silencedetect=noise=-30dB:d=0.5 -f null -
    cmd = [
        "ffmpeg",
        "-ss", str(max(0, start_search)),
        "-t", str(duration_to_scan),
        "-i", filename,
        "-vn", "-sn",
        "-af", "silencedetect=noise=-30dB:d=0.5",
        "-f", "null",
        "-"
    ]
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, startupinfo=startupinfo)
        # Output is in stderr
        output = result.stderr
        
        # Look for silence_start: ...
        # [silencedetect @ 0000...] silence_start: 12.345
        
        matches = re.findall(r'silence_start: (\d+(\.\d+)?)', output)
        if matches:
            # Return the first silence start found relative to the file.
            # However, ffmpeg with -ss resets timestamp? 
            # If using -ss before -i, timestamps in output *usually* reset to 0 or are relative to the seek point depending on version.
            # Wait, standard behavior of -ss before -i is "fast seek". The output timestamps of filter might be relative to 0 (the new start).
            # Let's verify standard ffmpeg behavior or just assume relative and add start_search.
            # Actually, `silencedetect` usually outputs timestamps relative to the input stream as processed.
            # If we seek to 100s, the first frame is treated as 0s in the filter chain usually?
            # Let's assume relative to the cut for safety, so we add start_search. 
            # But wait, ffprobe/ffmpeg timestamp behavior can be tricky. 
            
            # Use 'silence_start' directly if it looks absolute. 
            # If I run `ffmpeg -ss 10 -i file ...`, the output usually starts at 0.
            # So if silence is found at 5s in the clip, it's 15s in original.
            
            first_silence = float(matches[0][0])
            return start_search + first_silence
            
        return None
    except Exception as e:
        print(f"Error finding silence: {e}")
        return None

def smart_split_video(input_file, segment_duration_minutes, output_dir, progress_callback=None, progress_percent_callback=None, stop_event=None):
    """
    Split video intelligently at silence points.
    
    Args:
        input_file: Path to input video
        segment_duration_minutes: Duration of each segment in minutes
        output_dir: Output directory for split files
        progress_callback: Callback for status messages (msg)
        progress_percent_callback: Callback for progress percentage (0-100)
        stop_event: threading.Event to signal stop request
    """
    if not os.path.exists(output_file := input_file):
        if progress_callback: progress_callback("Error: Input file not found.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    total_duration = get_duration(input_file)
    if total_duration == 0:
        if progress_callback: progress_callback("Error: Could not determine video duration.")
        return

    segment_duration = segment_duration_minutes * 60
    current_start = 0.0
    part_number = 1
    
    filename_base = os.path.splitext(os.path.basename(input_file))[0]

    while current_start < total_duration:
        # Check for stop signal
        if stop_event and stop_event.is_set():
            if progress_callback:
                progress_callback("Process stopped by user.")
            return
        
        # Update progress percentage
        if progress_percent_callback:
            percent = min(100, int((current_start / total_duration) * 100))
            progress_percent_callback(percent)
        
        target_end = current_start + segment_duration
        
        # If this is the last segment (or close to it)
        if target_end >= total_duration:
            actual_end = total_duration
        else:
            # Search for silence around target_end (+/- 60s)
            search_start = max(current_start, target_end - 60)
            search_duration = 120 # +/- 60s
            
            # Don't search past total duration
            if search_start + search_duration > total_duration:
                search_duration = total_duration - search_start
            
            if progress_callback:
                progress_callback(f"Analyzing silence for Part {part_number} around {target_end/60:.2f}m...")

            silence_point = find_silence_time(input_file, search_start, search_duration)
            
            if silence_point:
                actual_end = silence_point
                if progress_callback:
                    progress_callback(f"Found silence at {actual_end:.2f}s (Target: {target_end:.2f}s)")
            else:
                actual_end = target_end
                if progress_callback:
                    progress_callback(f"No silence found. Splitting exactly at {actual_end:.2f}s")
        
        # Do the cut
        output_filename = f"{filename_base}_part{part_number:03d}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        if progress_callback:
            progress_callback(f"Exporting Part {part_number}: {output_filename}...")
            
        # Correct logic for "Stream Copy" safe split:
        cmd_cut = [
            "ffmpeg",
            "-ss", str(current_start),
            "-t", str(actual_end - current_start),
            "-i", input_file,
            "-c", "copy",
            "-y",
            output_path
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(cmd_cut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        
        current_start = actual_end
        part_number += 1
        
    # Final progress update
    if progress_percent_callback:
        progress_percent_callback(100)
        
    if progress_callback:
        progress_callback("Split complete!")

def convert_videos_to_wav(file_list, progress_callback=None, progress_percent_callback=None, stop_event=None):
    """
    Convert a list of video files to WAV audio with real-time progress tracking.
    
    Args:
        file_list: List of video file paths
        progress_callback: Callback for status messages (msg)
        progress_percent_callback: Callback for progress percentage (0-100)
        stop_event: threading.Event to signal stop request
    """
    total_files = len(file_list)
    
    for file_index, input_file in enumerate(file_list):
        # Check for stop signal
        if stop_event and stop_event.is_set():
            if progress_callback:
                progress_callback("Process stopped by user.")
            return
        
        if not os.path.exists(input_file):
            continue
            
        file_name = os.path.basename(input_file)
        if progress_callback:
            progress_callback(f"Converting ({file_index+1}/{total_files}): {file_name}")
            
        # Output WAV name
        output_file = os.path.splitext(input_file)[0] + ".wav"
        
        # Get video duration for progress calculation
        video_duration = get_duration(input_file)
        if video_duration == 0:
            video_duration = None  # Unknown duration
        
        # ffmpeg -i [input_video] -vn -acodec pcm_s16le -ar 44100 -ac 2 -y [output_wav]
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # PCM 16-bit little-endian (lossless)
            "-ar", "44100",  # Sample rate 44.1kHz
            "-ac", "2",  # 2 channels (stereo)
            "-y",
            output_file
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Use Popen to capture real-time progress
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            universal_newlines=True,
            bufsize=1
        )
        
        # Read stderr for progress
        while True:
            # Check for stop signal
            if stop_event and stop_event.is_set():
                process.terminate()
                if progress_callback:
                    progress_callback("Process stopped by user.")
                return
            
            line = process.stderr.readline()
            if not line:
                break
                
            # Parse progress
            if video_duration:
                current_time = parse_ffmpeg_progress(line)
                if current_time is not None and progress_percent_callback:
                    # Calculate file progress (0-100% of this file)
                    file_progress = min(100, int((current_time / video_duration) * 100))
                    
                    # Calculate overall progress
                    # Each file contributes (100 / total_files) percent
                    overall_progress = int((file_index * 100 + file_progress) / total_files)
                    progress_percent_callback(overall_progress)
        
        # Wait for process to complete
        process.wait()
        
        # Update progress to account for completed file
        if progress_percent_callback:
            overall_progress = int(((file_index + 1) * 100) / total_files)
            progress_percent_callback(overall_progress)
        
    # Final progress update
    if progress_percent_callback:
        progress_percent_callback(100)
        
    if progress_callback:
        progress_callback("All conversions complete!")

