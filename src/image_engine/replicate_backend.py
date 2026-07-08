"""Replicate API 图像生成后端"""

from typing import Any, Dict

import replicate

from src.config import get_replicate_token
from src.image_engine.backend import ImageBackend, ImageResult


class ReplicateBackend(ImageBackend):
    """Replicate 云端图像生成

    默认使用 SDXL 模型，可通过 config.yaml 切换为 FLUX 或其他模型。
    需要 REPLICATE_API_TOKEN 环境变量。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        replicate_cfg = config["image"]["replicate"]

        token = get_replicate_token()
        self.client = replicate.Client(api_token=token)

        self.model = replicate_cfg.get(
            "model",
            "stability-ai/stable-diffusion:db21e45d3f7023abc2a46c38b5f1e6c9c5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5",
        )
        self.num_steps = replicate_cfg.get("num_inference_steps", 30)
        self.guidance_scale = replicate_cfg.get("guidance_scale", 7.5)
        self.lora_url = replicate_cfg.get("lora_url", "")
        self.lora_scale = replicate_cfg.get("lora_scale", 0.8)

        # 是否为 FLUX 系列模型（接口不同）
        self._is_flux = "flux" in self.model.lower()

    def name(self) -> str:
        return f"Replicate ({self.model})"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        """调用 Replicate 生成图像"""
        try:
            if self._is_flux:
                return self._generate_flux(prompt, width, height, **kwargs)
            else:
                return self._generate_sdxl(prompt, negative_prompt, width, height, **kwargs)
        except Exception as e:
            return ImageResult(success=False, error=str(e))

    def _generate_sdxl(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        **kwargs,
    ) -> ImageResult:
        """SDXL 模型"""
        input_params = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": self.num_steps,
            "guidance_scale": self.guidance_scale,
            "num_outputs": 1,
        }

        # 可选 LoRA
        if self.lora_url:
            input_params["lora_urls"] = [self.lora_url]
            input_params["lora_scales"] = [self.lora_scale]

        output = self.client.run(self.model, input=input_params)

        image_url = output[0] if isinstance(output, list) else str(output)
        return ImageResult(
            success=True,
            image_url=image_url,
            metadata={"model": self.model, "prompt": prompt[:200]},
        )

    def _generate_flux(
        self,
        prompt: str,
        width: int,
        height: int,
        **kwargs,
    ) -> ImageResult:
        """FLUX 模型（接口略有不同）"""
        input_params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_inference_steps": self.num_steps,
            "guidance_scale": self.guidance_scale,
            "num_outputs": 1,
        }

        output = self.client.run(self.model, input=input_params)

        image_url = output[0] if isinstance(output, list) else str(output)
        return ImageResult(
            success=True,
            image_url=image_url,
            metadata={"model": self.model, "prompt": prompt[:200]},
        )
