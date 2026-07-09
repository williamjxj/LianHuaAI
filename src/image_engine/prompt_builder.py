"""Prompt构建器 — 为SD/FLUX模型构造高质量白描连环画prompt"""

from src.models import ARTIST_STYLE_DESCRIPTIONS, StoryOutput

# ─── 正向 Prompt 基础框架 ──────────────────────

BASE_STYLE_PROMPT = (
    "traditional Chinese baimiao (白描) ink brush painting, "
    "classical Chinese comic book style (连环画), "
    "black ink on aged rice paper, "
    "fine ink line drawing with elegant brush strokes, "
    "uniform hatching lines, layered ink density (墨分五色), "
    "vertical format composition, "
    "vintage antique paper texture, yellowed patina, "
    "no color, no shading, pure line art, "
    "detailed traditional Chinese architecture and costumes, "
    "historical accuracy, dramatic narrative scene, "
    "expressive characters, vivid facial expressions, "
    "masterpiece, high quality, intricate details"
)

# ─── 反向 Prompt（严格禁止）───────────────────

NEGATIVE_PROMPT = (
    "color, CG, 3D, anime, manga, photorealistic, "
    "oil painting, thick paint, watercolor, "
    "modern clothing, sci-fi, fantasy, "
    "distorted anatomy, deformed hands, bad proportion, "
    "blurry lines, fuzzy, low quality, sketchy, "
    "multiple mixed art styles, signatures, watermarks, "
    "photo filter, gradient, soft shading, "
    "perspective errors, architectural anachronisms"
)

# ─── 时代辅助描述 ───────────────────────────────

ERA_CONTEXT = {
    "东汉末年": (
        "Late Eastern Han dynasty, late 2nd century AD, "
        "Han dynasty armor and official robes, "
        "traditional Han architecture with roof tiles, "
        "ancient Chinese weaponry: spears, swords, bows, shields"
    ),
    "三国": (
        "Three Kingdoms period, 3rd century AD, "
        "Three Kingdoms armor and military attire, "
        "ancient Chinese war camps and city gates, "
        "period-appropriate weapons and battle standards"
    ),
    "春秋": (
        "Spring and Autumn period, ancient Chinese Warring States, "
        "pre-Qin dynasty attire and bronze weapons, "
        "chariots and ancient city walls"
    ),
    "战国": (
        "Warring States period, ancient Chinese armor, "
        "pre-Qin dynasty bronze artifacts, "
        "warrior attire and horse-drawn chariots"
    ),
    "西汉": "Western Han dynasty, Han dynasty court attire and architecture",
    "东汉": "Eastern Han dynasty, traditional Han dynasty clothing and buildings",
    "楚汉": "Chu-Han contention period, early Han dynasty military attire",
    "隋": "Sui dynasty, traditional Sui dynasty clothing and architecture",
    "唐": (
        "Tang dynasty, Tang dynasty official robes and armor, "
        "Tang dynasty architecture with sweeping roofs, "
        "period-appropriate weapons and accessories"
    ),
    "北宋": "Northern Song dynasty, Song dynasty scholar-official attire",
    "南宋": "Southern Song dynasty, Song dynasty military and civil attire",
    "宋": "Song dynasty, traditional Song dynasty clothing and architecture",
    "隋唐": "Sui-Tang period, Tang dynasty golden age attire and architecture",
    "明": "Ming dynasty, Ming dynasty official robes and armor",
}


def build_image_prompt(
    story: StoryOutput,
) -> str:
    """构建完整的图像生成 prompt

    为 SDXL / FLUX 等模型构建高质量的 prompt，
    整合故事场景描述 + 画师风格 + 白描技法 + 历史背景。

    Args:
        story: 故事输出

    Returns:
        完整 prompt 字符串
    """
    # 画师风格描述
    artist_desc = ARTIST_STYLE_DESCRIPTIONS.get(story.artist, "")

    # 时代背景
    era_desc = ERA_CONTEXT.get(story.era, f"Ancient China, {story.era} period")

    parts = [
        # 核心场景
        story.scene_description,

        # 画师风格
        f"Art style: {artist_desc}",

        # 连环画版式
        "Layout: traditional Chinese comic (连环画) vertical format, "
        "framed composition, narrative scene from classic novel",

        # 历史背景
        f"Historical context: {story.era}, {era_desc}",

        # 白描技法
        "Technique: fine baimiao line art, even ink lines (铁线描), "
        "traditional Chinese ink brush technique, "
        "black lines on off-white aged paper, "
        "no color, no wash painting (没骨), pure line drawing",

        # 整体风格
        BASE_STYLE_PROMPT,
    ]

    return ". ".join(parts)


def build_negative_prompt() -> str:
    """构建标准反向 prompt"""
    return NEGATIVE_PROMPT
