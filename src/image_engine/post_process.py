"""图像后期处理 — 宣纸纹理叠加、泛黄做旧、传统版式边框"""

import random
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# 宋体字路径（macOS 系统字体）
_SONGTI_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"
_SONGTI_INDEX = 1  # Songti SC Bold


class PostProcessor:
    """图像后期处理器

    对生成的图像进行：
    - 宣纸纹理叠加（模拟传统宣纸质感）
    - 泛黄做旧效果（复古泛黄纸张纹理）
    - 传统版式边框（经典连环画边框）
    - 连环画风格标题题字
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.paper_texture_enabled = self._get("post_process.paper_texture", True)
        self.aging_enabled = self._get("post_process.aging_effect", True)
        self.aging_intensity = self._get("post_process.aging_intensity", 0.35)
        self.add_border = self._get("post_process.add_border", True)
        self.add_title = self._get("post_process.add_title", True)

        paper_texture_dir = self._get("post_process.paper_texture_dir", "assets/paper_textures")
        self.paper_texture_blend = self._get("post_process.paper_texture_blend", 0.15)
        self.texture_paths: List[Path] = []
        self._load_texture_files(paper_texture_dir)

        self._title_font: Optional[ImageFont.FreeTypeFont] = None
        self._subtitle_font: Optional[ImageFont.FreeTypeFont] = None

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

    def process(self, image: Image.Image, title: Optional[str] = None) -> Image.Image:
        """对图像执行全套后期处理

        Args:
            image: PIL Image (RGB 或 RGBA)
            title: 可选，用于添加到图像上的连环画风格标题

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

        # 5. 添加连环画风格标题题字
        if self.add_title and title:
            img_aged = self._add_lianhuanhua_title(img_aged, title)

        # 6. 添加传统边框
        if self.add_border:
            img_aged = self._add_traditional_border(img_aged)

        return img_aged

    def _get_title_font(self, target_size: int) -> ImageFont.FreeTypeFont:
        """获取标题字体（Songti SC Bold），带缓存"""
        if self._title_font is None or self._title_font.size != target_size:
            self._title_font = ImageFont.truetype(_SONGTI_PATH, target_size, index=_SONGTI_INDEX)
        return self._title_font

    def _add_lianhuanhua_title(self, img: Image.Image, title: str) -> Image.Image:
        """在图像顶部添加传统连环画风格标题

        模仿传统小人书/连环画的版式标题：
        - 顶部居中，宋体加粗
        - 深墨色文字
        - 半透明古纸底色条衬托
        - 下方装饰细线分隔
        """
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # 标题区高度：根据图像高度自适应（约 5%）
        title_h = max(int(height * 0.055), 36)

        # 字体：标题区高度的 55%
        font_size = max(int(title_h * 0.55), 16)
        font = self._get_title_font(font_size)

        # 文字尺寸
        bbox = draw.textbbox((0, 0), title, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # 标题底色条位置（顶部居中）
        padding_x = int(width * 0.04)
        margin_y = max(int(height * 0.015), 6)
        rect_x0 = padding_x
        rect_y0 = margin_y
        rect_x1 = width - padding_x
        rect_y1 = margin_y + title_h

        # 绘制半透明古纸底色条（暖白泛黄，与做旧风格统一）
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [rect_x0, rect_y0, rect_x1, rect_y1],
            radius=3,
            fill=(245, 235, 215, 160),  # 古纸色，半透明
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 绘制标题文字（深墨色，带轻微做旧感）
        text_x = (width - text_w) // 2
        text_y = rect_y0 + (title_h - text_h) // 2 - 2
        text_color = (45, 40, 35)  # 深墨色，非纯黑
        draw.text((text_x, text_y), title, font=font, fill=text_color)

        # 下方装饰细线
        line_y = rect_y1 + 2
        line_color = (100, 90, 80)
        draw.line([(padding_x + 4, line_y), (width - padding_x - 4, line_y)], fill=line_color, width=1)

        return img

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
