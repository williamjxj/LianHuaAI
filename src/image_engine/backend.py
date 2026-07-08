"""图像生成后端抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ImageResult:
    """图像生成结果"""

    success: bool
    image_url: Optional[str] = None    # 远程图片 URL
    image_path: Optional[str] = None   # 本地文件路径
    error: Optional[str] = None        # 错误信息
    metadata: Optional[Dict[str, Any]] = None  # 生成元数据


class ImageBackend(ABC):
    """图像生成后端抽象基类"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        """生成图像

        Args:
            prompt: 正向 prompt
            negative_prompt: 反向 prompt
            width: 图片宽度
            height: 图片高度

        Returns:
            ImageResult
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        ...
