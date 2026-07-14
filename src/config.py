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


def get_minimax_api_key() -> str:
    token = os.getenv("MINIMAX_API_KEY")
    if not token:
        raise ValueError(
            "MINIMAX_API_KEY 未设置。\n"
            "请前往 https://platform.minimaxi.com 注册获取 API Key，\n"
            "然后添加到 .env 文件: MINIMAX_API_KEY=your_key_here"
        )
    return token


def get_r2_config() -> dict:
    """获取 Cloudflare R2 S3 兼容配置

    .env 格式:
        S3_API=https://<accountid>.r2.cloudflarestorage.com/<bucket>
        R2_URL=https://pub-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.r2.dev
        R2_ACCESS_KEY_ID=<your_key_id>
        R2_SECRET_ACCESS_KEY=<your_secret_key>

    Returns:
        dict 包含 endpoint, bucket, public_url, access_key_id, secret_access_key
    """
    from urllib.parse import urlparse

    s3_api = os.getenv("S3_API")
    r2_url = os.getenv("R2_URL")
    access_key_id = os.getenv("R2_ACCESS_KEY_ID")
    secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")

    missing = []
    if not s3_api:
        missing.append("S3_API")
    if not r2_url:
        missing.append("R2_URL")
    if not access_key_id:
        missing.append("R2_ACCESS_KEY_ID")
    if not secret_access_key:
        missing.append("R2_SECRET_ACCESS_KEY")

    if missing:
        raise ValueError(
            "R2 配置不完整，请在 .env 中补充:\n"
            + "\n".join(f"  {k}=<value>" for k in missing)
            + "\n\n格式说明:\n"
            "  S3_API: https://<accountid>.r2.cloudflarestorage.com/<bucket>\n"
            "  R2_URL: https://pub-<xxxx>.r2.dev\n"
            "  R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY: 在 R2 面板创建 API 令牌获得"
        )

    parsed = urlparse(s3_api)
    endpoint = f"{parsed.scheme}://{parsed.netloc}"
    bucket = parsed.path.strip("/")

    return {
        "endpoint": endpoint,
        "bucket": bucket,
        "public_url": r2_url.rstrip("/"),
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
    }


# 模块加载时自动加载环境变量
load_env()
