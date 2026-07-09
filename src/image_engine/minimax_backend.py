"""MiniMax (platform.minimaxi.com) 图像生成后端

使用 MiniMax image-01 模型进行文生图。
需要 MINIMAX_API_KEY 环境变量。
"""

from typing import Any, Dict

import requests

from src.config import get_minimax_api_key
from src.image_engine.backend import ImageBackend, ImageResult

BASE_URL = "https://api.minimaxi.com/v1/image_generation"

# 宽高比映射
_ASPECT_RATIOS = {
    (768, 1024): "3:4",
    (1024, 768): "4:3",
    (1024, 1024): "1:1",
    (1152, 768): "3:2",
    (768, 1152): "2:3",
    (1024, 576): "16:9",
    (576, 1024): "9:16",
}


class MiniMaxBackend(ImageBackend):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        mm_cfg = config.get("image", {}).get("minimax", {})

        self.api_key = get_minimax_api_key()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        self.model = mm_cfg.get("model", "image-01")
        self.timeout = mm_cfg.get("timeout", 180)

    def name(self) -> str:
        return f"MiniMax ({self.model})"

    @staticmethod
    def _truncate_prompt(prompt: str, max_chars: int = 1400) -> str:
        if len(prompt) <= max_chars:
            return prompt
        truncated = prompt[:max_chars]
        last_period = truncated.rfind(". ")
        if last_period > max_chars * 0.7:
            truncated = truncated[: last_period + 1]
        return truncated

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        try:
            aspect_ratio = _ASPECT_RATIOS.get((width, height), "16:9")
            trimmed = self._truncate_prompt(prompt)
            if trimmed != prompt:
                print(f"   ✂️  Prompt 过长，已截断 ({len(prompt)} → {len(trimmed)} 字符)")

            payload = {
                "model": self.model,
                "prompt": trimmed,
                "n": 1,
                "aspect_ratio": aspect_ratio,
                "response_format": "url",
            }

            resp = requests.post(
                BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            base_resp = data.get("base_resp", {})
            status_code = base_resp.get("status_code")
            if status_code != 0:
                return ImageResult(
                    success=False,
                    error=f"MiniMax API 错误: code={status_code} msg={base_resp.get('status_msg', 'unknown')}",
                )

            image_urls = data.get("data", {}).get("image_urls", [])
            if not image_urls:
                return ImageResult(success=False, error="MiniMax 未返回图片 URL")

            return ImageResult(
                success=True,
                image_url=image_urls[0],
                metadata={
                    "model": self.model,
                    "backend": "minimax",
                },
            )

        except Exception as e:
            return ImageResult(success=False, error=str(e))
