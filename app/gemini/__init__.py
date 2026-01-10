"""
Gemini module - Contains API configuration and prompt templates
"""
from .prompt_template import get_prompt_template, DEFAULT_PROMPT_TEMPLATE
from .api_config import get_merged_config, save_state_from_config, get_appdata_dir
from .api_keys import EMBEDDED_API_KEYS, get_all_api_keys, get_total_keys
