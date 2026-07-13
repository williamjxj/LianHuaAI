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
    - 底部统一解说条：标题 + 旁白 + 出处
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.paper_texture_enabled = self._get("post_process.paper_texture", True)
        self.aging_enabled = self._get("post_process.aging_effect", True)
        self.aging_intensity = self._get("post_process.aging_intensity", 0.35)
        self.add_border = self._get("post_process.add_border", True)
        self.add_narration = self._get("post_process.add_narration", True)

        paper_texture_dir = self._get("post_process.paper_texture_dir", "assets/paper_textures")
        self.paper_texture_blend = self._get("post_process.paper_texture_blend", 0.15)
        self.texture_paths: List[Path] = []
        self._load_texture_files(paper_texture_dir)

        self._title_font: Optional[ImageFont.FreeTypeFont] = None
        self._body_font: Optional[ImageFont.FreeTypeFont] = None
        self._source_font: Optional[ImageFont.FreeTypeFont] = None

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

    def process(
        self,
        image: Image.Image,
        title: Optional[str] = None,
        narration: Optional[str] = None,
        source_book: Optional[str] = None,
    ) -> Image.Image:
        """对图像执行全套后期处理

        Args:
            image: PIL Image (RGB 或 RGBA)
            title: 故事标题
            narration: 旁白解说文字
            source_book: 出处书目（如《三国演义》）

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
            img_aged = self._to_warm_tone(img_paper)

        # 5. 底部统一解说条（标题 + 旁白 + 出处合并到底部）
        if self.add_narration and (title or narration):
            img_aged = self._add_bottom_info_bar(img_aged, title or "", narration or "", source_book or "")

        # 6. 添加传统边框
        if self.add_border:
            img_aged = self._add_traditional_border(img_aged)

        return img_aged

    def _get_font_sized(self, cache_attr: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
        """获取指定尺寸的宋体字体（带缓存）"""
        cached = getattr(self, cache_attr, None)
        if cached is None or cached.size != size:
            font = ImageFont.truetype(_SONGTI_PATH, size, index=index)
            setattr(self, cache_attr, font)
        return getattr(self, cache_attr)

    def _add_bottom_info_bar(self, img: Image.Image, title: str, narration: str, source_book: str) -> Image.Image:
        """在图像底部添加统一解说条：标题 + 旁白 + 出处

        布局设计（三行，字体从大到小）：
        ┌─────────────────────────────────────────┐
        │    仁寿宫惊变                              │  ← 标题（大号粗体，居中）
        │    却说隋文帝卧病仁寿宫……                       │  ← 旁白（中号，居中，自动换行）
        │    ——《隋唐演义》                           │  ← 出处（小号，右下）
        └─────────────────────────────────────────┘
        """
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # ── 底部条区域参数 ──
        padding_x = int(width * 0.04)
        bar_x0 = padding_x
        bar_x1 = width - padding_x
        inner_pad_x = int(width * 0.03)

        # 标题行（粗体）
        title_font_size = max(int(height * 0.030), 14)
        title_font = self._get_font_sized("_title_font", title_font_size, index=_SONGTI_INDEX)
        title_h = title_font_size + 4

        # 旁白行（常规体，自动换行，最多2行）
        body_font_size = max(int(height * 0.022), 11)
        body_font = self._get_font_sized("_body_font", body_font_size, index=0)
        body_line_h = body_font_size + 3

        max_body_w = (bar_x1 - bar_x0) - inner_pad_x * 2
        body_lines = self._wrap_text(narration, body_font, max_body_w, draw)
        # 最多显示2行
        if len(body_lines) > 2:
            body_lines = body_lines[:2]
            # 最后一行为省略效果
            if body_lines[1][-1] not in "。！？":
                body_lines[1] = body_lines[1][:-1] + "…"
        body_total_h = len(body_lines) * body_line_h if body_lines else 0

        # 出处行（最小号）
        source_font_size = max(int(height * 0.018), 9)
        source_font = self._get_font_sized("_source_font", source_font_size, index=0)
        source_h = source_font_size + 2 if source_book else 0

        # ── 计算 bar 总高度（紧凑）──
        inner_pad_y = int(height * 0.008)
        bar_h = (
            inner_pad_y * 2
            + title_h
            + (2 if body_total_h > 0 else 0)
            + body_total_h
            + (2 if source_h > 0 else 0)
            + source_h
        )
        bar_h = max(bar_h, int(height * 0.07))

        bottom_margin = max(int(height * 0.015), 4)
        bar_y0 = height - bar_h - bottom_margin
        bar_y1 = height - bottom_margin

        # ── 绘制半透明古纸底色条 ──
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [bar_x0, bar_y0, bar_x1, bar_y1],
            radius=4,
            fill=(245, 235, 215, 175),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 顶部装饰分隔线
        sep_color = (100, 90, 80)
        draw.line([(bar_x0 + 6, bar_y0), (bar_x1 - 6, bar_y0)], fill=sep_color, width=1)

        # ── 1. 标题（大号粗体，居中） ──
        text_color_dark = (45, 40, 35)
        title_y = bar_y0 + inner_pad_y
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((width - title_w) // 2, title_y), title, font=title_font, fill=text_color_dark)

        # ── 2. 旁白（中号，居中，自动换行） ──
        body_y = title_y + title_h + 4
        text_color_mid = (65, 58, 50)
        for line in body_lines:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            line_w = bbox[2] - bbox[0]
            draw.text(((width - line_w) // 2, body_y), line, font=body_font, fill=text_color_mid)
            body_y += body_line_h

        # ── 3. 出处（小号，右下） ──
        if source_book:
            src_y = bar_y1 - source_h - inner_pad_y
            src_text = f"——{source_book}"
            bbox = draw.textbbox((0, 0), src_text, font=source_font)
            src_w = bbox[2] - bbox[0]
            text_color_light = (100, 90, 80)
            draw.text((bar_x1 - inner_pad_x - src_w, src_y), src_text, font=source_font, fill=text_color_light)

        return img

    @staticmethod
    def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list:
        """将文本按最大宽度自动换行，返回行列表"""
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            chars = list(paragraph)
            current_line = ""
            for ch in chars:
                test_line = current_line + ch
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if (bbox[2] - bbox[0]) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = ch
            if current_line:
                lines.append(current_line)
        return lines if lines else [""]

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
