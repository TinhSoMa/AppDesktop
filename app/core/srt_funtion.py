import os
import re
import math
import logging

# 1. Extract Captions (SRT to TXT)
def extract_srt_captions(input_srt_path, output_txt_path):
    logging.info(f"Bắt đầu Extract Caption: {os.path.basename(input_srt_path)}")
    if not os.path.exists(input_srt_path):
        raise FileNotFoundError(f"File không tồn tại: {input_srt_path}")

    try:
        with open(input_srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r'\n\s*\n', content.strip())
        captions = []

        for block in blocks:
            lines = block.strip().split("\n")
            timestamp_idx = -1
            for idx, line in enumerate(lines):
                if "-->" in line:
                    timestamp_idx = idx
                    break
            
            if timestamp_idx != -1 and len(lines) > timestamp_idx + 1:
                text_content = " ".join(lines[timestamp_idx+1:])
                captions.append(text_content)
            elif len(lines) >= 3:
                 text_content = " ".join(lines[2:])
                 captions.append(text_content)

        with open(output_txt_path, "w", encoding="utf-8") as f:
            for c in captions:
                f.write(c + "\n")

        logging.info(f"Extract thành công: {len(captions)} lines -> {output_txt_path}")
        return True, len(captions)

    except Exception as e:
        logging.error(f"Lỗi extract_srt_captions: {e}")
        return False, 0

# 2. Convert SRT (TXT + SRT Template -> New SRT)
def convert_txt_to_srt_using_template(txt_path, srt_template_path, output_srt_path):
    logging.info(f"Bắt đầu Convert SRT: {os.path.basename(txt_path)}")
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            txt_lines = [l.strip() for l in f if l.strip()]

        with open(srt_template_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        pattern = r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:(?!\n\d+\n\d{2}:\d{2}:\d{2},\d{3}).)*)"
        blocks = re.findall(pattern, srt_content, re.DOTALL)
        
        if not blocks:
             logging.warning("Regex không bắt được cấu trúc chuẩn, thử fallback parsing...")
             raw_blocks = re.split(r'\n\s*\n', srt_content.strip())
             parsed_blocks = []
             for b in raw_blocks:
                 lines = b.strip().split('\n')
                 if len(lines) >= 2:
                     if "-->" in lines[1]:
                         parsed_blocks.append((lines[0], lines[1]))
                     elif "-->" in lines[0]: 
                         parsed_blocks.append(("", lines[0]))
             blocks = parsed_blocks

        count = min(len(txt_lines), len(blocks))
        new_content = ""

        for i in range(count):
            seq_num = blocks[i][0]
            if not seq_num: seq_num = str(i+1)
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

# 3. Format TXT (Split by | and Normalize)
def format_txt_file(file_path, output_path=None, delimiter="|", remove_extra_spaces=True):
    """
    Format file TXT: Tách nội dung thành các dòng dựa trên delimiter (mặc định là '|').
    """
    logging.info(f"Format File TXT (Split by '{delimiter}'): {os.path.basename(file_path)}")
    if output_path is None:
        output_path = file_path
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Logic chính: Split by delimiter -> strip -> join newline
        parts = [part.strip() for part in content.split(delimiter) if part.strip()]
        
        # Option phụ: Xóa khoảng trắng thừa trong từng dòng (nếu cần)
        if remove_extra_spaces:
            parts = [re.sub(r'\s+', ' ', p) for p in parts]
            
        formatted_content = "\n".join(parts)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted_content)

        logging.info(f"Format thành công -> {output_path}")
        return True
    except Exception as e:
        logging.error(f"Lỗi format_txt_file: {e}")
        return False

# 4. Scale Speed (Chỉnh tốc độ SRT)
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

def scale_srt_speed(input_path, output_path, factor):
    logging.info(f"Scale Speed (x{factor}): {os.path.basename(input_path)}")
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
        logging.error(f"Lỗi scale_srt_speed: {e}")
        return False

# 5. Split TXT (Chia nhỏ file văn bản)
def split_text_file(input_path, output_dir, split_by_lines=True, value=100):
    logging.info(f"Split File TXT: {os.path.basename(input_path)}")
    if not os.path.exists(input_path):
        logging.error(f"File not found: {input_path}")
        return False

    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
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
            if start_idx >= total_lines: break
            
            chunk = lines[start_idx:end_idx]
            
            # Xử lý: Loại bỏ newline ở dòng cuối cùng của chunk để không có dòng trống thừa
            if chunk and chunk[-1].endswith('\n'):
                chunk[-1] = chunk[-1].rstrip('\n')

            file_start = start_idx + 1
            file_end = min(end_idx, total_lines)
            filename = f"part_{i+1}_lines_{file_start}-{file_end}.txt"
            output_path = os.path.join(output_dir, filename)

            with open(output_path, "w", encoding="utf-8") as out:
                out.writelines(chunk)
            
            created_files.append(filename)
            logging.info(f"- Đã tạo: {filename}")

        logging.info(f"Chia file hoàn tất: Tổng {len(created_files)} file.")
        return True, len(created_files)

    except Exception as e:
        logging.error(f"Lỗi split_text_file: {e}")
        return False, 0
