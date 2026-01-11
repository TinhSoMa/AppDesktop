"""
Gemini API Module - Gọi API Gemini để dịch text
"""
import os
import json
import requests
import time
import logging

# URL base của Gemini API
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def load_api_keys():
    """
    Đọc danh sách API keys từ APIKeyManager (multi-account support)
    Trả về list các keys đang available với smart rotation
    """
    try:
        from app.core.api_manager import get_api_manager
    except ImportError:
        try:
            from api_manager import get_api_manager
        except ImportError:
            # Fallback to old method
            return _load_api_keys_legacy()
    
    try:
        manager = get_api_manager()
        available_keys = manager.get_all_available_keys()
        
        if not available_keys:
            logging.warning("Không có API key nào available")
            return []
        
        logging.info(f"Đã load {len(available_keys)} API key(s) available")
        return available_keys
        
    except Exception as e:
        logging.error(f"Lỗi load API keys từ manager: {e}")
        return _load_api_keys_legacy()


def _load_api_keys_legacy():
    """Fallback: Đọc API keys theo format cũ"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        api_path = os.path.join(app_dir, "gemini", "api.json")
        
        if not os.path.exists(api_path):
            logging.error(f"File api.json không tồn tại: {api_path}")
            return []
        
        with open(api_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        keys = []
        # Try new format (accounts)
        if "accounts" in data:
            for account in data.get("accounts", []):
                if account.get("account_status") != "active":
                    continue
                for project in account.get("projects", []):
                    if project.get("status") == "available":
                        keys.append({
                            "name": f"{account['account_id']}/{project['project_name']}",
                            "key": project["api_key"],
                            "api_key": project["api_key"]
                        })
        # Old format (keys array)
        elif "keys" in data:
            for item in data["keys"]:
                if isinstance(item, dict) and "key" in item:
                    if item.get("status", "available") == "available":
                        keys.append({
                            "name": item.get("name", f"Key {len(keys)+1}"),
                            "key": item["key"],
                            "api_key": item["key"]
                        })
                elif isinstance(item, str):
                    keys.append({"name": f"Key {len(keys)+1}", "key": item, "api_key": item})
        
        logging.info(f"Đã load {len(keys)} API key(s) (legacy)")
        return keys
    except Exception as e:
        logging.error(f"Lỗi đọc api.json: {e}")
        return []


def load_prompt_template():
    """
    Đọc prompt template từ module Python (ưu tiên) hoặc file JSON (fallback).
    Module Python được bundle vào EXE khi build.
    """
    # Ưu tiên: Load từ module Python
    try:
        from app.gemini.prompt_template import get_prompt_template
        return get_prompt_template()
    except ImportError:
        pass
    
    try:
        from gemini.prompt_template import get_prompt_template
        return get_prompt_template()
    except ImportError:
        pass
    
    # Fallback: Load từ file JSON
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        prompt_path = os.path.join(app_dir, "gemini", "translation-prompt.json")
        
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                logging.info("Loaded prompt from JSON file (fallback)")
                return json.load(f)
    except Exception as e:
        logging.error(f"Lỗi đọc prompt JSON: {e}")
    
    logging.error("Không thể load prompt template!")
    return None


def build_prompt_for_file(file_path, prompt_template):
    """
    Tạo prompt hoàn chỉnh từ template và nội dung file text
    
    Args:
        file_path: Đường dẫn đến file text cần dịch
        prompt_template: Template prompt từ translation-prompt.json
    
    Returns:
        JSON string prompt hoàn chỉnh giống promt_saukhigui.json
    """
    try:
        # Đọc nội dung file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            return None, "File trống"
        
        # Tạo bản sao của template
        prompt = json.loads(json.dumps(prompt_template))
        
        # Thay thế các placeholder
        file_name = os.path.basename(file_path)
        count = len(lines)
        
        # Cập nhật task name
        prompt["task"] = f"subtitle_translation_{file_name}"
        
        # Cập nhật source_text
        prompt["source_text"]["total_lines"] = str(count)
        prompt["source_text"]["content"] = lines
        
        # Cập nhật các quy tắc với số lượng thực tế
        if "instructions" in prompt and "critical_rules" in prompt["instructions"]:
            for i, rule in enumerate(prompt["instructions"]["critical_rules"]):
                prompt["instructions"]["critical_rules"][i] = rule.replace("{{COUNT}}", str(count))
        
        if "instructions" in prompt and "formatting" in prompt["instructions"]:
            if "example" in prompt["instructions"]["formatting"]:
                prompt["instructions"]["formatting"]["example"] = prompt["instructions"]["formatting"]["example"].replace("{{COUNT}}", str(count))
        
        if "instructions" in prompt and "output_requirements" in prompt["instructions"]:
            if "format" in prompt["instructions"]["output_requirements"]:
                prompt["instructions"]["output_requirements"]["format"] = prompt["instructions"]["output_requirements"]["format"].replace("{{COUNT}}", str(count))
            if "verification" in prompt["instructions"]["output_requirements"]:
                prompt["instructions"]["output_requirements"]["verification"] = prompt["instructions"]["output_requirements"]["verification"].replace("{{COUNT}}", str(count))
        
        if "response_format" in prompt:
            prompt["response_format"] = prompt["response_format"].replace("{{COUNT}}", str(count))
        
        return prompt, None
        
    except Exception as e:
        return None, str(e)


def call_gemini_api(prompt_json, api_key, model="gemini-2.5-flash"):
    """
    Gọi Gemini API với prompt JSON
    
    Args:
        prompt_json: Dict/JSON prompt để gửi
        api_key: API key
        model: Tên model Gemini
    
    Returns:
        (success, result_text hoặc error_message)
    """
    try:
        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
        
        # Convert prompt thành text
        prompt_text = json.dumps(prompt_json, ensure_ascii=False, indent=2)
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        
        headers = {"Content-Type": "application/json"}
        
        logging.info(f"Gọi Gemini API với model: {model}")
        logging.debug(f"Prompt length: {len(prompt_text)} chars")
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 429:
            return False, "RATE_LIMIT"
        
        if response.status_code == 404:
            return False, f"Model {model} không tồn tại"
        
        # Log lỗi chi tiết trước khi raise
        if response.status_code != 200:
            try:
                error_detail = response.json()
                error_msg = error_detail.get("error", {}).get("message", "Unknown error")
                logging.error(f"API Error {response.status_code}: {error_msg}")
                return False, f"API Error: {error_msg}"
            except:
                logging.error(f"API Error {response.status_code}: {response.text[:500]}")
                return False, f"HTTP {response.status_code}"
        
        result = response.json()
        
        # Trích xuất text từ response
        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                text = candidate["content"]["parts"][0].get("text", "")
                return True, text.strip()
        
        return False, "Response không có nội dung"
        
    except requests.exceptions.Timeout:
        return False, "Timeout khi gọi API"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP Error: {e}"
    except Exception as e:
        return False, str(e)


def translate_file(file_path, output_path, api_keys, model, prompt_template, progress_callback=None):
    """
    Dịch một file text sử dụng Gemini API
    
    Args:
        file_path: Đường dẫn file input
        output_path: Đường dẫn file output
        api_keys: List các API keys (có thể truyền rỗng, sẽ tự lấy từ api_manager)
        model: Tên model
        prompt_template: Template prompt
        progress_callback: Callback function để báo tiến độ
    
    Returns:
        (success, message)
    """
    # Build prompt
    prompt, error = build_prompt_for_file(file_path, prompt_template)
    if not prompt:
        return False, f"Lỗi tạo prompt: {error}"
    
    # === LẤY API MANAGER ===
    try:
        from app.core.api_manager import get_api_manager
        manager = get_api_manager()
    except ImportError:
        try:
            from api_manager import get_api_manager
            manager = get_api_manager()
        except ImportError:
            manager = None
    
    # === KIỂM TRA NẾU CÓ API_KEYS ĐƯỢC TRUYỀN VÀO ===
    # Nếu có api_keys hợp lệ, dùng trực tiếp thay vì lấy từ api_manager
    already_tried_keys = set()  # Theo dõi keys đã thử để không thử lại ở fallback
    
    if api_keys and len(api_keys) > 0:
        # Dùng api_keys được truyền vào
        last_error = None
        rate_limited_count = 0
        
        for key_idx, api_key_info in enumerate(api_keys):
            if isinstance(api_key_info, dict):
                api_key = api_key_info.get("api_key") or api_key_info.get("key")
                account_name = api_key_info.get("name", f"Key {key_idx+1}")
            else:
                api_key = api_key_info
                account_name = f"Key {key_idx+1}"
            
            if not api_key:
                continue
            
            already_tried_keys.add(api_key)  # Đánh dấu key này đã thử
            
            # Không log "Thử API key" vì đã log ở auto_funtion.py rồi
            logging.info(f"Gọi Gemini API với model: {model}")
            
            success, result = call_gemini_api(prompt, api_key, model)
            
            if success:
                try:
                    clean_result = result.strip()
                    if clean_result.startswith("|"):
                        clean_result = clean_result[1:]
                    if clean_result.endswith("|"):
                        clean_result = clean_result[:-1]
                    
                    translated_lines = [line.strip() for line in clean_result.split("|") if line.strip()]
                    
                    with open(output_path, "w", encoding="utf-8") as f:
                        for line in translated_lines:
                            f.write(line + "\n")
                    
                    # Ghi nhận thành công
                    if manager:
                        manager.record_success(api_key)
                    
                    logging.info(f"[Gemini] ✓ Thành công với {account_name}")
                    return True, f"Đã dịch {len(translated_lines)} dòng"
                    
                except Exception as e:
                    last_error = f"Lỗi parse kết quả: {e}"
                    logging.error(f"[Gemini] Lỗi parse: {e}")
                    continue
            
            elif result == "RATE_LIMIT":
                logging.warning(f"[Gemini] ⚠ Rate limit với {account_name}, thử key tiếp theo...")
                if manager:
                    manager.record_rate_limit_error(api_key)
                last_error = "RATE_LIMIT_ALL_KEYS"
                rate_limited_count += 1
                time.sleep(0.3)
                continue
            else:
                logging.error(f"[Gemini] ✗ Lỗi với {account_name}: {result}")
                if manager:
                    manager.record_error(api_key, result)
                last_error = result
                continue
        
        # Nếu hết api_keys truyền vào mà vẫn thất bại
        # KHÔNG trả về ngay, tiếp tục thử với các key khác từ api_manager
        if rate_limited_count > 0:
            logging.info(f"[Gemini] Key được chỉ định bị rate limit, thử các key khác...")
            # Tiếp tục xuống phần fallback bên dưới để thử api_manager
        elif last_error:
            return False, f"Thất bại với key được chỉ định: {last_error}"
    
    # === TIẾP TỤC THỬ VỚI API_MANAGER ===
    if not manager:
        return False, "Không có API key và không có api_manager"
    
    stats = manager.get_stats()
    total_keys = stats.get("total_projects", 0)
    
    if total_keys == 0:
        return False, "Không có API key nào trong hệ thống"
    
    last_error = None
    rate_limited_count = 0
    tried_keys = already_tried_keys.copy()  # Bắt đầu với các key đã thử ở phần trên
    
    max_attempts = total_keys
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        
        api_key, key_info = manager.get_next_api_key()
        
        if not api_key:
            logging.warning(f"[Gemini] Không còn key available sau {attempt} lần thử")
            break
        
        # Bỏ qua key đã thử
        if api_key in tried_keys:
            # Kiểm tra xem đã hết key chưa
            if len(tried_keys) >= total_keys:
                logging.info(f"[Gemini] Đã thử hết tất cả keys ({len(tried_keys)} keys)")
                break
            continue
        
        tried_keys.add(api_key)
        account_name = key_info.get("name", f"Key #{attempt}") if key_info else f"Key #{attempt}"
        
        logging.info(f"Thử API key #{len(tried_keys)} ({account_name})")
        
        success, result = call_gemini_api(prompt, api_key, model)
        
        if success:
            # Parse kết quả (format: |Câu1|Câu2|...|CâuN|)
            try:
                clean_result = result.strip()
                if clean_result.startswith("|"):
                    clean_result = clean_result[1:]
                if clean_result.endswith("|"):
                    clean_result = clean_result[:-1]
                
                translated_lines = [line.strip() for line in clean_result.split("|") if line.strip()]
                
                # Ghi ra file
                with open(output_path, "w", encoding="utf-8") as f:
                    for line in translated_lines:
                        f.write(line + "\n")
                
                # Ghi nhận thành công (rotation state đã được update trong get_next_api_key)
                manager.record_success(api_key)
                
                logging.info(f"[Gemini] ✓ Thành công với {account_name}")
                return True, f"Đã dịch {len(translated_lines)} dòng"
                
            except Exception as e:
                last_error = f"Lỗi parse kết quả: {e}"
                logging.error(f"[Gemini] Lỗi parse: {e}")
                continue
        
        elif result == "RATE_LIMIT":
            logging.warning(f"[Gemini] ⚠ Rate limit với {account_name}, thử key tiếp theo...")
            manager.record_rate_limit_error(api_key)
            last_error = "RATE_LIMIT_ALL_KEYS"
            rate_limited_count += 1
            time.sleep(0.3)  # Short delay before trying next key
            continue
        else:
            # Ghi nhận lỗi khác
            logging.error(f"[Gemini] ✗ Lỗi với {account_name}: {result}")
            manager.record_error(api_key, result)
            last_error = result
            continue
    
    # Kiểm tra kết quả
    if rate_limited_count > 0 and rate_limited_count >= len(tried_keys):
        logging.warning(f"[Gemini] Tất cả {rate_limited_count} keys đã thử đều bị rate limit")
        return False, "RATE_LIMIT_ALL_KEYS"
    
    return False, f"Thất bại sau {attempt} lần thử: {last_error}"


def _translate_file_legacy(prompt, output_path, api_keys, model):
    """Fallback: Dịch file với danh sách api_keys truyền vào (không dùng api_manager)"""
    if not api_keys:
        return False, "Không có API key nào"
    
    for key_idx, api_key_info in enumerate(api_keys):
        if isinstance(api_key_info, dict):
            api_key = api_key_info.get("api_key") or api_key_info.get("key")
        else:
            api_key = api_key_info
        
        if not api_key:
            continue
        
        success, result = call_gemini_api(prompt, api_key, model)
        if success:
            try:
                clean_result = result.strip().strip("|")
                lines = [l.strip() for l in clean_result.split("|") if l.strip()]
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                return True, f"Đã dịch {len(lines)} dòng"
            except Exception as e:
                continue
    
    return False, "Tất cả API key đều thất bại"


def _record_api_success(api_key: str):
    """Ghi nhận thành công vào APIKeyManager"""
    try:
        from app.core.api_manager import get_api_manager
        get_api_manager().record_success(api_key)
    except:
        pass

def _record_api_rate_limit(api_key: str):
    """Ghi nhận rate limit vào APIKeyManager"""
    try:
        from app.core.api_manager import get_api_manager
        get_api_manager().record_rate_limit_error(api_key)
    except:
        pass

def _record_api_error(api_key: str, error_msg: str):
    """Ghi nhận lỗi vào APIKeyManager"""
    try:
        from app.core.api_manager import get_api_manager
        if "exhausted" in error_msg.lower() or "quota" in error_msg.lower():
            get_api_manager().record_quota_exhausted(api_key)
        else:
            get_api_manager().record_error(api_key, error_msg)
    except:
        pass
