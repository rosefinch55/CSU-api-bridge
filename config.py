"""配置模块：上游服务器、模型映射、功能开关"""

import os
from dotenv import load_dotenv

load_dotenv()

# ========== 功能开关 ==========
ENABLE_THINKING = False  # 是否允许 thinking 参数（DeepSeek 推理模式）
REQUEST_TIMEOUT = 300    # 上游请求超时（秒）

# ========== 上游服务器 ==========
UPSTREAMS = {
    "csu": {
        "url": os.getenv("CSU_URL", "https://api.chat.csu.edu.cn/v1/chat/completions"),
        "key": os.getenv("CSU_KEY", ""),
        "protocol": "openai",
    },
    "mimo": {
        "url": os.getenv("MIMO_URL", "https://token-plan-cn.xiaomimimo.com/anthropic"),
        "key": os.getenv("MIMO_KEY", ""),
        "protocol": "anthropic",
    },
}

# ========== 模型映射 ==========
# 格式: "对外模型名" → ("上游名", "上游模型名")
MODEL_MAP = {
    "csu-deepseek[1m]": ("csu", "DeepSeek-V4-Flash"),
    "csu-deepseek": ("csu", "DeepSeek-V4-Flash"),
    "csu-deepseek-thinking[1m]": ("csu", "DeepSeek-V4-Flash"),
    "csu-deepseek-thinking": ("csu", "DeepSeek-V4-Flash"),
    "csu-qwen[256k]": ("csu", "Qwen3.6-35B-A3B"),
    "csu-qwen": ("csu", "Qwen3.6-35B-A3B"),
    "csu-qwen-thinking[256k]": ("csu", "Qwen3.6-35B-A3B"),
    "csu-qwen-thinking": ("csu", "Qwen3.6-35B-A3B"),
    "mimo-v2.5-pro[1m]": ("mimo", "mimo-v2.5-pro"),
    "mimo-v2.5-pro": ("mimo", "mimo-v2.5-pro"),
    "mimo-v2.5[1m]": ("mimo", "mimo-v2.5"),
    "mimo-v2.5": ("mimo", "mimo-v2.5"),
}

DEFAULT_MODEL = "csu-deepseek"
PORT = int(os.getenv("PORT", "4000"))


def resolve_model(model_name: str) -> tuple[str | None, str | None, str | None]:
    """解析模型名 → (upstream_name, upstream_model, protocol)"""
    upstream_name, upstream_model = MODEL_MAP.get(model_name, (None, None))
    if not upstream_name:
        return None, None, None
    upstream = UPSTREAMS[upstream_name]
    return upstream_name, upstream_model, upstream["protocol"]


def get_upstream_headers(upstream_name: str) -> dict:
    """获取上游请求头"""
    upstream = UPSTREAMS[upstream_name]
    return {
        "Authorization": f"Bearer {upstream['key']}",
        "Content-Type": "application/json",
    }


def get_upstream_url(upstream_name: str) -> str:
    """获取上游 URL"""
    return UPSTREAMS[upstream_name]["url"]
