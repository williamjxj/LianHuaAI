"""图像后期处理 — 宣纸纹理叠加、泛黄做旧、传统版式边框"""

import random
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance


class PostProcessor:
    """图像后期处理器

    对生成的图像进行：
    - 宣纸纹理叠加（模拟传统宣纸质感）
    - 泛黄做旧效果（复古泛黄纸张纹理）
    - 传统版式边框（经典连环画边框）
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.paper_texture_enabled = self._get("post_process.paper_texture", True)
        self.aging_enabled = self._get("post_process.aging_effect", True)
        self.aging_intensity = self._get("post_process.aging_intensity", 0.35)
        self.add_border = self._get("post_process.add_border", True)

        paper_texture_dir = self._get("post_process.paper_texture_dir", "assets/paper_textures")
        self.paper_texture_blend = self._get("post_process.paper_texture_blend", 0.15)
        self.texture_paths: List[Path] = []
        self._load_texture_files(paper_texture_dir)

    def _get(self, key: str, default):
        """从嵌套配置中取值"""
        parts = key.split(".")
        val = self.config
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return default
        return val if val is not None else default

    def process(self, image: Image.Image) -> Image.Image:
        """对图像执行全套后期处理

        Args:
            image: PIL Image (RGB 或 RGBA)

        Returns:
            处理后的 PIL Image
        """
        # 确保为 RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        # 1. 转灰度（白描为黑白线条）
        img_gray = image.convert("L")

        # 2. 增强对比度 — 让线条更清晰
        img_contrast = self._enhance_contrast(img_gray)

        # 3. 宣纸纹理（如果启用）
        if self.paper_texture_enabled:
            img_paper = self._apply_paper_texture(img_contrast)
        else:
            img_paper = img_contrast

        # 4. 泛黄做旧（如果启用）
        if self.aging_enabled:
            img_aged = self._apply_aging(img_paper)
        else:
            # 如果不做旧，直接转 RGB 的暖白底
            img_aged = self._to_warm_tone(img_paper)

        # 5. 添加传统边框
        if self.add_border:
            img_aged = self._add_traditional_border(img_aged)

        return img_aged

    def _enhance_contrast(self, img: Image.Image) -> Image.Image:
        """增强图像对比度，使墨线更清晰"""
        from PIL import ImageEnhance

        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(1.3)

    def _load_texture_files(self, dir_path: str) -> None:
        """扫描目录加载宣纸纹理文件"""
        tex_dir = Path(dir_path)
        if not tex_dir.exists():
            self.texture_paths = []
            return
        self.texture_paths = sorted(
            p for p in tex_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png")
        )

    def _load_texture(self, width: int, height: int) -> Optional[Image.Image]:
        """随机加载一张宣纸纹理并缩放到目标尺寸"""
        if not self.texture_paths:
            return None
        tex_path = random.choice(self.texture_paths)
        tex = Image.open(tex_path).convert("L")
        return tex.resize((width, height), Image.Resampling.LANCZOS)

    def _apply_paper_texture(self, img: Image.Image) -> Image.Image:
        """叠加宣纸纹理

        优先使用真实宣纸扫描图，回退到随机颗粒噪点
        """
        width, height = img.size

        # 尝试用真实纹理
        texture = self._load_texture(width, height)
        if texture is not None:
            np_img = np.array(img.convert("L"), dtype=np.float32)
            np_tex = np.array(texture, dtype=np.float32)
            blended = np_img * (1 - self.paper_texture_blend) + np_tex * self.paper_texture_blend
            return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))

        # 回退：随机噪点模拟宣纸
        np_img = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, 8, (height, width)).astype(np.float32)
        np_textured = np.clip(np_img + noise, 0, 255).astype(np.uint8)

        return Image.fromarray(np_textured)

    def _apply_aging(self, img: Image.Image) -> Image.Image:
        """应用泛黄做旧效果"""
        width, height = img.size

        # 转为 RGB
        img_rgb = img.convert("RGB")
        np_img = np.array(img_rgb, dtype=np.float32)

        # 创建泛黄映射（中心稍亮，边缘稍黄）
        y, x = np.mgrid[0:height, 0:width]
        center_y, center_x = height / 2, width / 2

        # 距离中心的归一化距离
        dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
        dist = dist / np.sqrt(center_x ** 2 + center_y ** 2)  # 0~1

        # 泛黄映射 — 边缘更黄
        sepia_strength = self.aging_intensity * (0.6 + 0.4 * dist)

        # 泛黄色调 (R, G, B)
        target_tone = np.array([220, 190, 150], dtype=np.float32)

        for c in range(3):
            np_img[:, :, c] = np_img[:, :, c] * (1 - sepia_strength) + target_tone[c] * sepia_strength

        # 添加轻微不均匀污渍
        stain_mask = np.random.random((height, width)) > 0.97
        stain_color = np.array([180, 150, 110], dtype=np.float32)
        for c in range(3):
            np_img[:, :, c] = np.where(
                stain_mask,
                np_img[:, :, c] * 0.7 + stain_color[c] * 0.3,
                np_img[:, :, c],
            )

        return Image.fromarray(np.clip(np_img, 0, 255).astype(np.uint8))

    def _to_warm_tone(self, img: Image.Image) -> Image.Image:
        """转为暖白底色（不做旧时的基础调色）"""
        img_rgb = img.convert("RGB")
        np_img = np.array(img_rgb, dtype=np.float32)

        # 轻微暖色偏移
        warm_tone = np.array([248, 240, 225], dtype=np.float32)
        blend = 0.15
        np_img = np_img * (1 - blend) + warm_tone * blend

        return Image.fromarray(np.clip(np_img, 0, 255).astype(np.uint8))

    def _add_traditional_border(self, img: Image.Image) -> Image.Image:
        """添加传统连环画版式边框

        外框 + 内框 double-line 效果，模拟老版连环画的版式
        """
        width, height = img.size
        draw = ImageDraw.Draw(img)

        border_outer = 4
        border_inner = 12
        border_color = (40, 35, 30)

        # 外框
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=border_color,
            width=border_outer,
        )

        # 内框
        draw.rectangle(
            [border_inner, border_inner, width - border_inner - 1, height - border_inner - 1],
            outline=border_color,
            width=1,
        )

        return img
