import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 1. 动态定位到上一级目录（根目录）的 .env 文件
root_dir = Path(__file__).resolve().parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

# 2. settings.json 路径（图形化配置界面写入此文件）
SETTINGS_JSON_PATH = Path(__file__).resolve().parent / "data" / "settings.json"


def _load_settings_json() -> dict:
    """从 settings.json 动态读取配置，失败时返回空字典。"""
    try:
        if SETTINGS_JSON_PATH.exists():
            with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _cfg(*env_keys: str, json_key: str = None):
    """优先级：环境变量 > settings.json > None。
    env_keys 按顺序逐一尝试；json_key 默认取第一个 env_key。
    """
    for key in env_keys:
        val = os.getenv(key)
        if val:
            return val
    settings = _load_settings_json()
    jk = json_key or env_keys[0]
    val = settings.get(jk)
    if val:
        return val
    return None


# 3. --- 大模型配置 ---
OPENAI_API_KEY = _cfg("OPENAI_API_KEY", "LLM_API_KEY", "api_key", json_key="OPENAI_API_KEY")
OPENAI_BASE_URL = _cfg("OPENAI_BASE_URL", "LLM_BASE_URL", "base_url", json_key="OPENAI_BASE_URL")
OPENAI_MODEL = _cfg("OPENAI_MODEL", "LLM_MODEL", json_key="OPENAI_MODEL")
VISION_MODEL = _cfg("VISION_MODEL", json_key="VISION_MODEL")

LLM_API_KEY = OPENAI_API_KEY
LLM_BASE_URL = OPENAI_BASE_URL
LLM_MODEL = OPENAI_MODEL
VISION_LLM_MODEL = VISION_MODEL

# 4. --- 飞书配置 ---
FEISHU_APP_ID = _cfg("FEISHU_APP_ID", "APP_ID", json_key="FEISHU_APP_ID")
FEISHU_APP_SECRET = _cfg("FEISHU_APP_SECRET", "APP_SECRET", json_key="FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = _cfg("FEISHU_APP_TOKEN", "APP_TOKEN", json_key="FEISHU_APP_TOKEN")

# 数据表 ID 集合
FEISHU_TABLE_ID_JOBS = _cfg("FEISHU_TABLE_ID_JOBS", "TABLE_ID_JOBS", "TABLE_ID", json_key="FEISHU_TABLE_ID_JOBS")
FEISHU_TABLE_ID_CONFIG = _cfg("FEISHU_TABLE_ID_CONFIG", "TABLE_ID_CONFIG", json_key="FEISHU_TABLE_ID_CONFIG")

# 🌟 策略与配置中心表 ID
FEISHU_TABLE_ID_PROMPTS = _cfg("FEISHU_TABLE_ID_PROMPTS", json_key="FEISHU_TABLE_ID_PROMPTS")
FEISHU_TABLE_ID_RESUMES = _cfg("FEISHU_TABLE_ID_RESUMES", json_key="FEISHU_TABLE_ID_RESUMES")
FEISHU_TABLE_ID_PREFERENCES = _cfg("FEISHU_TABLE_ID_PREFERENCES", json_key="FEISHU_TABLE_ID_PREFERENCES")

# 5. --- 外部情报接口配置 ---
SERPER_API_KEY = _cfg("SERPER_API_KEY", json_key="SERPER_API_KEY")


# ==================== 🌟 动态客户端 Getter（每次调用均重读 settings.json）====================

def get_openai_client():
    """返回使用最新配置的 OpenAI 客户端（动态读取，感知 settings.json 变更）。"""
    from openai import OpenAI
    key = _cfg("OPENAI_API_KEY", "LLM_API_KEY", "api_key", json_key="OPENAI_API_KEY")
    url = _cfg("OPENAI_BASE_URL", "LLM_BASE_URL", "base_url", json_key="OPENAI_BASE_URL")
    return OpenAI(api_key=key, base_url=url)


def get_serper_api_key() -> str | None:
    """动态读取最新 Serper API Key（感知 settings.json 变更）。"""
    return _cfg("SERPER_API_KEY", json_key="SERPER_API_KEY")