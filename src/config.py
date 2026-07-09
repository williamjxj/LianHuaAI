"""配置管理 — 加载 config.yaml + .env 环境变量"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    path = config_path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(env_path: Optional[Path] = None) -> None:
    """加载 .env 环境变量文件"""
    path = env_path or ENV_PATH
    if path.exists():
        load_dotenv(path)


def get_llm_config(provider: str) -> Dict[str, str]:
    """获取指定 LLM 提供商的 API 配置

    Args:
        provider: deepseek | kimi | minimax

    Returns:
        dict 包含 api_key, base_url, model
    """
    provider = provider.lower()
    configs = {
        "deepseek": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        },
        "kimi": {
            "api_key": os.getenv("KIMI_API_KEY"),
            "base_url": os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
            "model": os.getenv("KIMI_MODEL", "kimi-k2.5"),
        },
        "minimax": {
            "api_key": os.getenv("MINIMAX_API_KEY"),
            "base_url": os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
            "model": os.getenv("MINIMAX_MODEL", "MiniMax-M2.5"),
        },
    }
    cfg = configs.get(provider)
    if not cfg:
        raise ValueError(f"不支持的 LLM 提供商: {provider}，可选: deepseek, kimi, minimax")
    if not cfg["api_key"]:
        raise ValueError(f"{provider} API Key 未设置，请检查 .env 文件")
    return cfg


def get_replicate_token() -> str:
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        raise ValueError(
            "REPLICATE_API_TOKEN 未设置。\n"
            "请前往 https://replicate.com 注册获取 Token，\n"
            "然后添加到 .env 文件: REPLICATE_API_TOKEN=r8_..."
        )
    return token


def get_runninghub_api_key() -> str:
    token = os.getenv("RUNNINGHUB_API_KEY")
    if not token:
        raise ValueError(
            "RUNNINGHUB_API_KEY 未设置。\n"
            "请前往 https://www.runninghub.cn 注册获取 API Key，\n"
            "然后添加到 .env 文件: RUNNINGHUB_API_KEY=your_key_here"
        )
    return token


def get_zhipu_api_key() -> str:
    token = (
        os.getenv("ZHIPU_API_KEY")
        or os.getenv("BIGMODEL_API_KEY")
        or os.getenv("GLM_API_KEY")
    )
    if not token:
        raise ValueError(
            "ZHIPU_API_KEY 未设置。\n"
            "请前往 https://open.bigmodel.cn 注册获取 API Key，\n"
            "然后添加到 .env 文件: ZHIPU_API_KEY=your_key_here"
        )
    return token


def get_tongyi_api_key() -> str:
    token = (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("TONGYI_API_KEY")
        or os.getenv("WANX_API_KEY")
    )
    if not token:
        raise ValueError(
            "DASHSCOPE_API_KEY 未设置。\n"
            "请前往阿里云百炼 / DashScope 注册获取 API Key，\n"
            "然后添加到 .env 文件: DASHSCOPE_API_KEY=your_key_here"
        )
    return token


# 模块加载时自动加载环境变量
load_env()
