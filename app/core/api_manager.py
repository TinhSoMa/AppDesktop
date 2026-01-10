"""
API Key Manager - Quản lý thông minh API keys cho Gemini
Thuật toán "Quét Ngang" (Horizontal Sweep):
- Quét qua tất cả accounts trước khi chuyển sang project tiếp theo
- Mỗi account được nghỉ 13-14 giây giữa các request
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import threading

class APIKeyManager:
    """
    Quản lý API keys với thuật toán "Quét Ngang":
    - Request 1: Acc1-Proj1
    - Request 2: Acc2-Proj1
    - ...
    - Request 14: Acc14-Proj1
    - Request 15: Acc1-Proj2 (Acc1 đã nghỉ 13s!)
    """
    
    STATUS_AVAILABLE = "available"
    STATUS_RATE_LIMITED = "rate_limited"
    STATUS_EXHAUSTED = "exhausted"
    STATUS_ERROR = "error"
    
    def __init__(self, config_path: str = None):
        """
        Khởi tạo API Manager.
        Sử dụng embedded keys từ api_keys.py + state từ AppData.
        """
        self._lock = threading.Lock()
        self.config = self._load_config()
        self._auto_recover_all()
        self._check_daily_reset()
    
    def _load_config(self) -> dict:
        """
        Load config từ embedded keys + AppData state.
        Keys: app/gemini/api_keys.py (hardcoded)
        State: AppData/AppDesktop/api_state.json
        """
        try:
            from app.gemini.api_config import get_merged_config
            return get_merged_config()
        except ImportError:
            pass
        
        try:
            from gemini.api_config import get_merged_config
            return get_merged_config()
        except ImportError:
            pass
        
        logging.error("Không thể load api_config module!")
        return self._create_default_config()
    
    def _create_default_config(self) -> dict:
        """Tạo config mặc định"""
        return {
            "settings": {
                "global_cooldown_seconds": 65,
                "default_rpm_limit": 15,
                "max_rpd_limit": 1500,
                "rotation_strategy": "horizontal_sweep",
                "delay_between_requests_ms": 1000
            },
            "rotation_state": {
                "current_project_index": 0,
                "current_account_index": 0,
                "total_requests_sent": 0,
                "rotation_round": 1,
                "last_daily_reset": None
            },
            "accounts": []
        }
    
    def _save_config(self):
        """
        Lưu state vào AppData (chỉ lưu status, stats, không lưu keys).
        Keys được giữ cố định trong api_keys.py
        """
        try:
            from app.gemini.api_config import save_state_from_config
            save_state_from_config(self.config)
        except ImportError:
            try:
                from gemini.api_config import save_state_from_config
                save_state_from_config(self.config)
            except ImportError:
                logging.error("Không thể save state - api_config module not found")
    
    def _get_rotation_state(self) -> dict:
        """Lấy rotation state, tạo mới nếu chưa có"""
        if "rotation_state" not in self.config:
            self.config["rotation_state"] = {
                "current_project_index": 0,
                "current_account_index": 0,
                "total_requests_sent": 0,
                "rotation_round": 1,
                "last_daily_reset": None
            }
        return self.config["rotation_state"]
    
    def _auto_recover_all(self):
        """Auto-recover tất cả projects bị rate_limited đã hết cooldown"""
        current_time = datetime.now()
        recovered_count = 0
        
        for account in self.config.get("accounts", []):
            for project in account.get("projects", []):
                if project.get("status") == self.STATUS_RATE_LIMITED:
                    limit = project.get("limit_tracking", {})
                    reset_at = limit.get("rate_limit_reset_at")
                    
                    if reset_at:
                        try:
                            reset_time = datetime.fromisoformat(reset_at)
                            if current_time >= reset_time:
                                project["status"] = self.STATUS_AVAILABLE
                                limit["rate_limit_reset_at"] = None
                                limit["minute_request_count"] = 0
                                recovered_count += 1
                        except:
                            pass
        
        if recovered_count > 0:
            logging.info(f"Auto-recovered {recovered_count} projects từ rate_limited")
            self._save_config()
    
    def _check_daily_reset(self):
        """Kiểm tra và reset stats hàng ngày (0h sáng)"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        rotation_state = self._get_rotation_state()
        last_reset = rotation_state.get("last_daily_reset")
        
        if last_reset != current_date:
            logging.info(f"Đang reset daily stats (last: {last_reset}, current: {current_date})")
            
            for account in self.config.get("accounts", []):
                for project in account.get("projects", []):
                    stats = project.get("stats", {})
                    stats["total_requests_today"] = 0
                    stats["success_count"] = 0
                    stats["error_count"] = 0
                    
                    # Recover exhausted projects
                    if project.get("status") == self.STATUS_EXHAUSTED:
                        project["status"] = self.STATUS_AVAILABLE
                        limit = project.get("limit_tracking", {})
                        limit["daily_limit_reset_at"] = None
            
            rotation_state["last_daily_reset"] = current_date
            self._save_config()
    
    def _is_project_available(self, project: dict) -> bool:
        """Kiểm tra project có available không (bao gồm auto-recover)"""
        status = project.get("status", self.STATUS_AVAILABLE)
        
        # Check rate limit recovery
        if status == self.STATUS_RATE_LIMITED:
            limit = project.get("limit_tracking", {})
            reset_at = limit.get("rate_limit_reset_at")
            if reset_at:
                try:
                    reset_time = datetime.fromisoformat(reset_at)
                    if datetime.now() >= reset_time:
                        project["status"] = self.STATUS_AVAILABLE
                        limit["rate_limit_reset_at"] = None
                        limit["minute_request_count"] = 0
                        return True
                except:
                    pass
            return False
        
        # Check exhausted recovery (daily reset handles this)
        if status == self.STATUS_EXHAUSTED:
            return False
        
        # Check disabled (user manually disabled)
        if status == "disabled":
            return False
        
        if status == self.STATUS_ERROR:
            return False
        
        # Check if api_key is empty
        if not project.get("api_key"):
            return False
        
        return status == self.STATUS_AVAILABLE
    
    def get_next_api_key(self) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Lấy API key tiếp theo theo thuật toán "Quét Ngang".
        
        Logic:
        1. Lấy key tại (current_account_index, current_project_index)
        2. Tăng current_account_index
        3. Nếu đã hết accounts → reset account_index, tăng project_index
        4. Nếu đã hết projects → reset project_index (quay lại vòng mới)
        
        Returns:
            (api_key, key_info) hoặc (None, None) nếu không có key available
        """
        with self._lock:
            self._auto_recover_all()
            
            accounts = self.config.get("accounts", [])
            if not accounts:
                return None, None
            
            num_accounts = len(accounts)
            num_projects = 5  # Fixed 5 projects per account
            
            # Lấy state hiện tại
            state = self._get_rotation_state()
            current_acc_idx = state.get("current_account_index", 0)
            current_proj_idx = state.get("current_project_index", 0)
            
            # Thử tìm key available, quét qua tất cả accounts/projects
            total_attempts = num_accounts * num_projects
            attempts = 0
            
            while attempts < total_attempts:
                # Wrap around indices
                acc_idx = current_acc_idx % num_accounts
                proj_idx = current_proj_idx % num_projects
                
                account = accounts[acc_idx]
                projects = account.get("projects", [])
                
                # Kiểm tra account active và có project
                if account.get("account_status") == "active" and proj_idx < len(projects):
                    project = projects[proj_idx]
                    
                    if self._is_project_available(project):
                        # ✅ TÌM THẤY KEY AVAILABLE
                        api_key = project["api_key"]
                        
                        key_info = {
                            "account_id": account["account_id"],
                            "account_email": account.get("email", ""),
                            "project_name": project["project_name"],
                            "api_key": api_key,
                            "name": f"{account['account_id']}/{project['project_name']}",
                            "account_index": acc_idx,
                            "project_index": proj_idx
                        }
                        
                        # Cập nhật state CHO LẦN REQUEST TIẾP THEO
                        next_acc_idx = acc_idx + 1
                        next_proj_idx = proj_idx
                        
                        # Nếu đã hết accounts → chuyển sang project tiếp theo
                        if next_acc_idx >= num_accounts:
                            next_acc_idx = 0
                            next_proj_idx = (proj_idx + 1) % num_projects
                            state["rotation_round"] = state.get("rotation_round", 1) + 1
                        
                        state["current_account_index"] = next_acc_idx
                        state["current_project_index"] = next_proj_idx
                        state["total_requests_sent"] = state.get("total_requests_sent", 0) + 1
                        
                        self._save_config()
                        
                        return api_key, key_info
                
                # Thử account tiếp theo
                current_acc_idx += 1
                if current_acc_idx >= num_accounts:
                    current_acc_idx = 0
                    current_proj_idx += 1
                
                attempts += 1
            
            # Không tìm thấy key available nào
            return None, None
    
    def get_all_available_keys(self) -> List[Dict]:
        """Lấy tất cả API keys đang available"""
        self._auto_recover_all()
        available = []
        
        for account in self.config.get("accounts", []):
            if account.get("account_status") != "active":
                continue
            
            for project in account.get("projects", []):
                if self._is_project_available(project):
                    available.append({
                        "account_id": account["account_id"],
                        "account_email": account.get("email", ""),
                        "project_name": project["project_name"],
                        "api_key": project["api_key"],
                        "name": f"{account['account_id']}/{project['project_name']}"
                    })
        return available

    def reset_all_status_except_disabled(self):
        """
        Reset trạng thái của tất cả keys từ rate_limited/exhausted -> available.
        Không reset keys bị 'disabled' manual hoặc 'error'.
        Dùng khi chuyển model (vì limit tính theo model tier trên key).
        """
        logging.info("Resetting all key statuses for model switching...")
        with self._lock:
            for account in self.config.get("accounts", []):
                for project in account.get("projects", []):
                    status = project.get("status")
                    if status in [self.STATUS_RATE_LIMITED, self.STATUS_EXHAUSTED]:
                        project["status"] = self.STATUS_AVAILABLE
                        # Reset tracking
                        limit = project.get("limit_tracking", {})
                        limit["rate_limit_reset_at"] = None
                        limit["daily_limit_reset_at"] = None
                        limit["minute_request_count"] = 0
            
            self._save_config()
    
    def record_success(self, api_key: str):
        """Ghi nhận request thành công"""
        with self._lock:
            project = self._find_project_by_key(api_key)
            if project:
                stats = project.setdefault("stats", {})
                stats["total_requests_today"] = stats.get("total_requests_today", 0) + 1
                stats["success_count"] = stats.get("success_count", 0) + 1
                stats["last_success_timestamp"] = datetime.now().isoformat()
                
                limit = project.setdefault("limit_tracking", {})
                limit["last_used_timestamp"] = datetime.now().isoformat()
                limit["minute_request_count"] = limit.get("minute_request_count", 0) + 1
                
                self._save_config()
    
    def record_rate_limit_error(self, api_key: str):
        """Ghi nhận lỗi rate limit (429) - RPM"""
        with self._lock:
            project = self._find_project_by_key(api_key)
            if project:
                cooldown = self.config.get("settings", {}).get("global_cooldown_seconds", 65)
                reset_time = datetime.now() + timedelta(seconds=cooldown)
                
                project["status"] = self.STATUS_RATE_LIMITED
                
                stats = project.setdefault("stats", {})
                stats["error_count"] = stats.get("error_count", 0) + 1
                stats["last_error_message"] = f"429 Rate Limited at {datetime.now().isoformat()}"
                
                limit = project.setdefault("limit_tracking", {})
                limit["rate_limit_reset_at"] = reset_time.isoformat()
                limit["minute_request_count"] = 0
                
                logging.warning(f"API key bị rate limit, sẽ reset lúc {reset_time}")
                self._save_config()
    
    def record_quota_exhausted(self, api_key: str):
        """Ghi nhận lỗi hết quota ngày (RPD)"""
        with self._lock:
            project = self._find_project_by_key(api_key)
            if project:
                tomorrow = (datetime.now() + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                
                project["status"] = self.STATUS_EXHAUSTED
                
                stats = project.setdefault("stats", {})
                stats["error_count"] = stats.get("error_count", 0) + 1
                stats["last_error_message"] = f"Daily quota exhausted at {datetime.now().isoformat()}"
                
                limit = project.setdefault("limit_tracking", {})
                limit["daily_limit_reset_at"] = tomorrow.isoformat() + "Z"
                
                logging.warning(f"API key hết quota ngày, sẽ reset lúc {tomorrow}")
                self._save_config()
    
    def record_error(self, api_key: str, error_message: str):
        """Ghi nhận lỗi khác (không phải rate limit)"""
        with self._lock:
            project = self._find_project_by_key(api_key)
            if project:
                stats = project.setdefault("stats", {})
                stats["error_count"] = stats.get("error_count", 0) + 1
                stats["last_error_message"] = error_message
                
                # Nếu lỗi nghiêm trọng (key invalid), đánh dấu error
                if "invalid" in error_message.lower() or "api key" in error_message.lower():
                    project["status"] = self.STATUS_ERROR
                
                self._save_config()
    
    def _find_project_by_key(self, api_key: str) -> Optional[dict]:
        """Tìm project theo API key"""
        for account in self.config.get("accounts", []):
            for project in account.get("projects", []):
                if project.get("api_key") == api_key:
                    return project
        return None
    
    def get_stats(self) -> dict:
        """Lấy thống kê tổng quan"""
        total_accounts = len(self.config.get("accounts", []))
        total_projects = 0
        available = 0
        rate_limited = 0
        exhausted = 0
        error = 0
        total_requests = 0
        empty_keys = 0
        
        for account in self.config.get("accounts", []):
            for project in account.get("projects", []):
                total_projects += 1
                
                if not project.get("api_key"):
                    empty_keys += 1
                    continue
                
                status = project.get("status", "unknown")
                
                if self._is_project_available(project):
                    available += 1
                elif status == self.STATUS_RATE_LIMITED:
                    rate_limited += 1
                elif status == self.STATUS_EXHAUSTED:
                    exhausted += 1
                else:
                    error += 1
                
                total_requests += project.get("stats", {}).get("total_requests_today", 0)
        
        state = self._get_rotation_state()
        
        return {
            "total_accounts": total_accounts,
            "total_projects": total_projects,
            "available": available,
            "rate_limited": rate_limited,
            "exhausted": exhausted,
            "error": error,
            "empty_keys": empty_keys,
            "total_requests_today": total_requests,
            "current_account_index": state.get("current_account_index", 0),
            "current_project_index": state.get("current_project_index", 0),
            "rotation_round": state.get("rotation_round", 1)
        }
    
    def get_delay_ms(self) -> int:
        """Lấy delay giữa các request (milliseconds)"""
        return self.config.get("settings", {}).get("delay_between_requests_ms", 1000)
    
    def reload(self):
        """Reload config từ file"""
        with self._lock:
            self.config = self._load_config()
            self._auto_recover_all()
            self._check_daily_reset()
    
    def reset_rotation_state(self):
        """Reset rotation state về đầu"""
        with self._lock:
            state = self._get_rotation_state()
            state["current_account_index"] = 0
            state["current_project_index"] = 0
            state["rotation_round"] = 1
            self._save_config()
            logging.info("Đã reset rotation state")


# Singleton instance
_manager_instance = None
_manager_lock = threading.Lock()

def get_api_manager() -> APIKeyManager:
    """Lấy instance của APIKeyManager (singleton, thread-safe)"""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is None:
            _manager_instance = APIKeyManager()
        return _manager_instance
