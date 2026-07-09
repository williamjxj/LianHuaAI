"""通义万相图像生成后端"""

from typing import Any, Dict, Optional

import requests

from src.config import get_tongyi_api_key
from src.image_engine.backend import ImageBackend, ImageResult


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_MODEL = "wan2.7-image-pro"
ENDPOINT_PATH = "/services/aigc/multimodal-generation/generation"


class TongyiBackend(ImageBackend):
    """通义万相图像生成后端。

    采用 DashScope 官方 HTTP 接口，适合中文古风、历史故事与连环画类题材。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        tongyi_cfg = config["image"].get("tongyi", {})

        self.api_key = get_tongyi_api_key()
        self.base_url = tongyi_cfg.get("base_url", DEFAULT_BASE_URL).rstrip("/")
        self.model = tongyi_cfg.get("model", DEFAULT_MODEL)
        self.timeout = tongyi_cfg.get("timeout", 120)
        self.size = tongyi_cfg.get("size", "2K")
        self.watermark = tongyi_cfg.get("watermark", False)
        self.thinking_mode = tongyi_cfg.get("thinking_mode", True)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def name(self) -> str:
        return f"Tongyi Wanxiang ({self.model})"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        try:
            image_url = self._generate_image(prompt, negative_prompt)
            return ImageResult(
                success=True,
                image_url=image_url,
                metadata={
                    "model": self.model,
                    "size": self.size,
                    "backend": "tongyi",
                },
            )
        except Exception as exc:
            return ImageResult(success=False, error=str(exc))

    def _generate_image(self, prompt: str, negative_prompt: str) -> str:
        payload = self._build_payload(prompt, negative_prompt)
        response = self.session.post(
            f"{self.base_url}{ENDPOINT_PATH}",
            json=payload,
            timeout=self.timeout,
        )

        if not response.ok:
            raise RuntimeError(self._format_error(response))

        data = response.json()
        image_url = self._extract_image_url(data)
        if not image_url:
            raise RuntimeError(f"通义万相接口未返回图片地址: {data}")

        return image_url

    def _build_payload(self, prompt: str, negative_prompt: str) -> Dict[str, Any]:
        final_prompt = prompt.strip()
        if negative_prompt.strip():
            final_prompt = (
                f"{final_prompt}\n\n"
                f"严格避免：{negative_prompt.strip()}"
            )

        return {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": final_prompt}],
                    }
                ]
            },
            "parameters": {
                "size": self.size,
                "n": 1,
                "watermark": self.watermark,
                "thinking_mode": self.thinking_mode,
            },
        }

    @staticmethod
    def _extract_image_url(data: Dict[str, Any]) -> Optional[str]:
        output = data.get("output", {})
        choices = output.get("choices", [])
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list) and content:
                    first_content = content[0]
                    if isinstance(first_content, dict):
                        return first_content.get("image") or first_content.get("url")

        data_block = data.get("data")
        if isinstance(data_block, list) and data_block:
            first = data_block[0]
            if isinstance(first, dict):
                return first.get("image") or first.get("url")

        return None

    @staticmethod
    def _format_error(response: requests.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        return f"通义万相接口请求失败: HTTP {response.status_code}, {payload}"