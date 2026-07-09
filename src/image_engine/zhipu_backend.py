"""Zhipu AI 图像生成后端"""

from typing import Any, Dict, Optional

import requests

from src.config import get_zhipu_api_key
from src.image_engine.backend import ImageBackend, ImageResult


DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "auto"
DEFAULT_CLASSIC_MODEL = "cogView-4-250304"
DEFAULT_TEXT_HEAVY_MODEL = "glm-image"

CLASSIC_COMIC_KEYWORDS = (
    "白描",
    "连环画",
    "线描",
    "墨线",
    "宣纸",
    "古典",
    "历史",
    "三国",
    "东汉",
    "西汉",
    "唐代",
    "宋代",
    "明代",
    "清代",
    "古装",
    "古建筑",
    "碑刻",
    "卷轴",
)

MULTI_PANEL_KEYWORDS = (
    "多格",
    "分镜",
    "图文混排",
    "海报",
    "标题",
    "字幕",
    "对话框",
    "文字",
    "书法",
    "题字",
    "招牌",
    "版式",
    "说明图",
    "信息图",
)


class ZhipuBackend(ImageBackend):
    """智谱 AI 图像生成后端。

    通过智谱开放平台的 HTTP 图像生成接口调用，适合中文古风、历史题材和连环画风格。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        zhipu_cfg = config["image"].get("zhipu", {})

        self.api_key = get_zhipu_api_key()
        self.base_url = zhipu_cfg.get("base_url", DEFAULT_BASE_URL).rstrip("/")
        self.model = zhipu_cfg.get("model", DEFAULT_MODEL)
        self.model_strategy = zhipu_cfg.get("model_strategy", "classic_comic_first")
        self.classic_model = zhipu_cfg.get("classic_model", DEFAULT_CLASSIC_MODEL)
        self.text_heavy_model = zhipu_cfg.get("text_heavy_model", DEFAULT_TEXT_HEAVY_MODEL)
        self.timeout = zhipu_cfg.get("timeout", 120)
        self.quality = zhipu_cfg.get("quality", "hd")
        self.watermark_enabled = zhipu_cfg.get("watermark_enabled", False)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def name(self) -> str:
        if self.model and self.model != "auto":
            return f"Zhipu AI ({self.model})"
        return f"Zhipu AI (auto:{self.model_strategy})"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        try:
            selected_model = self._select_model(prompt, negative_prompt)
            image_url = self._generate_image(
                selected_model,
                prompt,
                negative_prompt,
                width,
                height,
            )
            return ImageResult(
                success=True,
                image_url=image_url,
                metadata={
                    "model": selected_model,
                    "strategy": self.model_strategy,
                    "size": f"{width}x{height}",
                    "backend": "zhipu",
                },
            )
        except Exception as exc:
            return ImageResult(success=False, error=str(exc))

    def _select_model(self, prompt: str, negative_prompt: str) -> str:
        requested_model = (self.model or "auto").strip().lower()
        if requested_model and requested_model != "auto":
            return self.model

        normalized_text = f"{prompt} {negative_prompt}".lower()

        if self.model_strategy == "text_heavy_first":
            if self._matches_any(normalized_text, MULTI_PANEL_KEYWORDS):
                return self.text_heavy_model
            if self._matches_any(normalized_text, CLASSIC_COMIC_KEYWORDS):
                return self.classic_model
            return self.text_heavy_model

        if self.model_strategy == "classic_comic_first":
            if self._matches_any(normalized_text, MULTI_PANEL_KEYWORDS):
                return self.text_heavy_model
            return self.classic_model

        if self.model_strategy == "balanced":
            classic_score = self._score_keywords(normalized_text, CLASSIC_COMIC_KEYWORDS)
            text_score = self._score_keywords(normalized_text, MULTI_PANEL_KEYWORDS)
            return self.classic_model if classic_score >= text_score else self.text_heavy_model

        return self.classic_model

    def _generate_image(
        self,
        model: str,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
    ) -> str:
        payload = self._build_payload(model, prompt, negative_prompt, width, height)
        response = self.session.post(
            f"{self.base_url}/images/generations",
            json=payload,
            timeout=self.timeout,
        )

        if not response.ok:
            raise RuntimeError(self._format_error(response))

        data = response.json()
        image_url = self._extract_image_url(data)
        if not image_url:
            raise RuntimeError(f"智谱图像接口未返回图片地址: {data}")

        return image_url

    def _build_payload(
        self,
        model: str,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
    ) -> Dict[str, Any]:
        final_prompt = prompt.strip()
        if negative_prompt.strip():
            final_prompt = (
                f"{final_prompt}\n\n"
                f"严格避免：{negative_prompt.strip()}"
            )

        size = self._normalize_size(model, width, height)

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": final_prompt,
            "size": size,
        }

        if model.lower().startswith("glm-image"):
            payload["quality"] = self.quality
            payload["watermark_enabled"] = self.watermark_enabled

        return payload

    @staticmethod
    def _matches_any(text: str, keywords) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _score_keywords(text: str, keywords) -> int:
        return sum(1 for keyword in keywords if keyword in text)

    @staticmethod
    def _normalize_size(model: str, width: int, height: int) -> str:
        if not model.lower().startswith("glm-image"):
            return f"{width}x{height}"

        aspect_ratio_map = {
            (1024, 1024): "1280x1280",
            (768, 1024): "864x1152",
            (1024, 768): "1152x864",
            (1024, 576): "1440x720",
            (576, 1024): "720x1440",
            (1344, 768): "1344x768",
            (768, 1344): "768x1344",
        }
        if (width, height) in aspect_ratio_map:
            return aspect_ratio_map[(width, height)]
        if width >= height:
            return "1440x720"
        return "720x1440"

    @staticmethod
    def _extract_image_url(data: Dict[str, Any]) -> Optional[str]:
        images = data.get("data")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                return first.get("url") or first.get("file_url")
        return None

    @staticmethod
    def _format_error(response: requests.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        return f"智谱图像接口请求失败: HTTP {response.status_code}, {payload}"