"""
API Configuration - Quản lý state của API keys
- API Keys: Hardcoded trong api_keys.py (bundle vào EXE)
- State (status, stats): Lưu trong AppData/AppDesktop/api_state.json
"""

import os
import sys
import json
import logging
from datetime import datetime

# AppData path
APP_NAME = "AppDesktop"


def get_appdata_dir() -> str:
    """Lấy thư mục AppData cho ứng dụng"""
    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        app_dir = os.path.join(appdata, APP_NAME)
    else:
        app_dir = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
    
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_state_file_path() -> str:
    """Lấy đường dẫn file state"""
    return os.path.join(get_appdata_dir(), "api_state.json")


# Default settings
DEFAULT_SETTINGS = {
    "global_cooldown_seconds": 65,
    "default_rpm_limit": 15,
    "max_rpd_limit": 1500,
    "rotation_strategy": "horizontal_sweep",
    "retry_exhausted_after_hours": 24,
    "delay_between_requests_ms": 1000
}

DEFAULT_ROTATION_STATE = {
    "current_project_index": 0,
    "current_account_index": 0,
    "total_requests_sent": 0,
    "rotation_round": 1,
    "last_daily_reset": None
}


def create_default_project_state() -> dict:
    """Tạo state mặc định cho 1 project"""
    return {
        "status": "available",
        "stats": {
            "total_requests_today": 0,
            "success_count": 0,
            "error_count": 0,
            "last_success_timestamp": None,
            "last_error_message": None
        },
        "limit_tracking": {
            "last_used_timestamp": None,
            "minute_request_count": 0,
            "rate_limit_reset_at": None,
            "daily_limit_reset_at": None
        }
    }


def create_default_account_state(account_id: str, num_projects: int = 5) -> dict:
    """Tạo state mặc định cho 1 account"""
    return {
        "account_id": account_id,
        "account_status": "active",
        "projects": [
            {
                "project_index": i,
                **create_default_project_state()
            }
            for i in range(num_projects)
        ]
    }


def load_embedded_keys() -> list:
    """Load API keys đã được hardcode trong api_keys.py"""
    try:
        from app.gemini.api_keys import EMBEDDED_API_KEYS
        return EMBEDDED_API_KEYS
    except ImportError:
        pass
    
    try:
        from gemini.api_keys import EMBEDDED_API_KEYS
        return EMBEDDED_API_KEYS
    except ImportError:
        pass
    
    logging.error("Không thể load EMBEDDED_API_KEYS!")
    return []


def load_api_state() -> dict:
    """
    Load state từ file AppData.
    Nếu file không tồn tại, tạo mới từ embedded keys.
    """
    state_path = get_state_file_path()
    
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Lỗi đọc api_state.json: {e}")
    
    # Tạo state mới từ embedded keys
    return create_fresh_state()


def create_fresh_state() -> dict:
    """Tạo state mới từ embedded keys"""
    embedded_keys = load_embedded_keys()
    
    accounts_state = []
    for i, acc in enumerate(embedded_keys):
        num_projects = len(acc.get("projects", []))
        accounts_state.append(create_default_account_state(f"acc_{i+1:02d}", num_projects))
    
    return {
        "settings": DEFAULT_SETTINGS.copy(),
        "rotation_state": DEFAULT_ROTATION_STATE.copy(),
        "accounts": accounts_state
    }


def save_api_state(state: dict) -> bool:
    """Lưu state vào file AppData"""
    state_path = get_state_file_path()
    
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Lỗi lưu api_state.json: {e}")
        return False


def get_merged_config() -> dict:
    """
    Merge embedded keys với state để tạo config hoàn chỉnh.
    Đây là config được api_manager sử dụng.
    """
    embedded_keys = load_embedded_keys()
    state = load_api_state()
    
    # Merge
    merged_accounts = []
    
    for i, embedded_acc in enumerate(embedded_keys):
        acc_id = f"acc_{i+1:02d}"
        
        # Tìm state tương ứng
        acc_state = None
        for s in state.get("accounts", []):
            if s.get("account_id") == acc_id:
                acc_state = s
                break
        
        if acc_state is None:
            acc_state = create_default_account_state(acc_id, len(embedded_acc.get("projects", [])))
        
        # Merge account
        merged_acc = {
            "account_id": acc_id,
            "email": embedded_acc.get("email", ""),
            "account_status": acc_state.get("account_status", "active"),
            "projects": []
        }
        
        # Merge projects
        for j, embedded_proj in enumerate(embedded_acc.get("projects", [])):
            proj_state = None
            for ps in acc_state.get("projects", []):
                if ps.get("project_index") == j:
                    proj_state = ps
                    break
            
            if proj_state is None:
                proj_state = create_default_project_state()
                proj_state["project_index"] = j
            
            merged_proj = {
                "project_name": embedded_proj.get("project_name", f"Project-{j+1}"),
                "api_key": embedded_proj.get("api_key", ""),
                "status": proj_state.get("status", "available"),
                "stats": proj_state.get("stats", {}),
                "limit_tracking": proj_state.get("limit_tracking", {})
            }
            
            merged_acc["projects"].append(merged_proj)
        
        merged_accounts.append(merged_acc)
    
    return {
        "settings": state.get("settings", DEFAULT_SETTINGS.copy()),
        "rotation_state": state.get("rotation_state", DEFAULT_ROTATION_STATE.copy()),
        "accounts": merged_accounts
    }


def save_state_from_config(config: dict) -> bool:
    """
    Lưu state từ config (chỉ lưu phần state, không lưu keys).
    """
    state = {
        "settings": config.get("settings", {}),
        "rotation_state": config.get("rotation_state", {}),
        "accounts": []
    }
    
    for acc in config.get("accounts", []):
        acc_state = {
            "account_id": acc.get("account_id"),
            "account_status": acc.get("account_status", "active"),
            "projects": []
        }
        
        for j, proj in enumerate(acc.get("projects", [])):
            proj_state = {
                "project_index": j,
                "status": proj.get("status", "available"),
                "stats": proj.get("stats", {}),
                "limit_tracking": proj.get("limit_tracking", {})
            }
            acc_state["projects"].append(proj_state)
        
        state["accounts"].append(acc_state)
    
    return save_api_state(state)
