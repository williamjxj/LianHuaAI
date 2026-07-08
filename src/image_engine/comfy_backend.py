"""ComfyUI 本地图像生成后端 (预留)"""

from typing import Any, Dict

from src.image_engine.backend import ImageBackend, ImageResult


class ComfyUIBackend(ImageBackend):
    """ComfyUI 本地后端

    注意: 当前为预留桩代码。
    Mac M3 上运行 SDXL 速度较慢，建议优先使用 Replicate 云端 API。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        comfy_cfg = config["image"].get("comfyui", {})
        self.server_url = comfy_cfg.get("server_url", "http://127.0.0.1:8188")
        self.workflow_path = comfy_cfg.get("workflow_path", "")

    def name(self) -> str:
        return f"ComfyUI ({self.server_url})"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        return ImageResult(
            success=False,
            error="ComfyUI 后端尚未实现。请使用 Replicate 后端或配置 image.backend=dry_run。",
        )
