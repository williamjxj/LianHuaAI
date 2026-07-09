"""数据模型"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


@dataclass
class ScenePlan:
    """分镜级场景规划 — 8个维度描述画面"""

    foreground: str = ""
    middle_ground: str = ""
    background: str = ""
    character_positions: str = ""
    actions: str = ""
    camera: str = ""
    composition: str = ""
    lighting: str = ""


class ArtistStyle(str, Enum):
    """21位古典连环画大师风格"""

    LIU_JIYOU = "刘继卣"
    LIU_XIYONG = "刘锡永"
    CHEN_GUANGYI = "陈光镒"
    WANG_YUSHAN = "汪玉山"
    LING_TAO = "凌涛"
    LI_TIESHENG = "李铁生"
    XU_ZHENGPING = "徐正平"
    FENG_MONONG = "冯墨农"
    ZHU_GUANGYU = "朱光玉"
    YAN_SHAOTANG = "严绍唐"
    YANG_QINGHUA = "杨青华"
    XU_HONGDA = "徐宏达"
    XU_ZHENGFANG = "徐正方"
    ZHAO_SANDAO = "赵三岛"
    XU_YIMING = "徐一鸣"
    TU_QUANFENG = "屠全枫"
    JIANG_PING = "蒋萍"
    XU_JIN = "徐进"
    WANG_YIQIU = "王亦秋"
    HU_RUOFU = "胡若佛"
    ZHANG_LINGTAO = "张令涛"

    @classmethod
    def list_all(cls) -> List["ArtistStyle"]:
        return list(cls)


@dataclass
class StoryOutput:
    """单次生成的故事输出"""

    title: str
    theme: str
    theme_board: str               # 板块key (如 three_kingdoms)
    source_book: str               # 出处书目
    era: str
    scene_description: str
    narration: str
    historical_note: str
    characters: List[str]
    artist: ArtistStyle
    scene_plan: Optional[ScenePlan] = None
    narrator_style: str = "auto"   # 本次使用的旁白风格


@dataclass
class GenerationResult:
    """一次完整的生成结果"""

    story: StoryOutput
    image_prompt: str
    negative_prompt: str
    image_path: Optional[str] = None
    metadata_path: Optional[str] = None
    error: Optional[str] = None


# 每个画师的风格特征描述
ARTIST_STYLE_DESCRIPTIONS = {
    ArtistStyle.LIU_JIYOU: (
        "刘继卣风格：工写结合，线条刚劲有力，人物造型精准生动，"
        "衣纹用笔潇洒流畅，画面气势雄浑，神态刻画入微"
    ),
    ArtistStyle.LIU_XIYONG: (
        "刘锡永风格：线条细腻流畅，构图饱满，人物比例匀称，"
        "场景层次丰富，擅长战争场面和群像布局"
    ),
    ArtistStyle.CHEN_GUANGYI: (
        "陈光镒风格：用笔豪放洒脱，线条粗犷有力，人物动态夸张生动，"
        "画面充满张力，尤其擅长表现激烈战斗场景"
    ),
    ArtistStyle.WANG_YUSHAN: (
        "汪玉山风格：构图严谨，线条工整细腻，人物造型端正，"
        "场景布置考究，传统笔墨功底深厚"
    ),
    ArtistStyle.LING_TAO: (
        "凌涛风格：笔墨清秀雅致，线条流畅自然，人物神态温润，"
        "山水背景意境悠远，画面整体和谐统一"
    ),
    ArtistStyle.LI_TIESHENG: (
        "李铁生风格：线条刚健有力，人物形象英武，衣纹转折分明，"
        "擅长表现英雄人物和宏大场面"
    ),
    ArtistStyle.XU_ZHENGPING: (
        "徐正平风格：造型严谨准确，线条流畅挺拔，人物动态自然，"
        "场景构图富有叙事性，连环画功力深厚"
    ),
    ArtistStyle.FENG_MONONG: (
        "冯墨农风格：用墨浓淡有致，线条粗细变化丰富，"
        "人物衣纹层次分明，擅长表现复杂场景和人物互动"
    ),
    ArtistStyle.ZHU_GUANGYU: (
        "朱光玉风格：线条工致秀丽，人物造型典雅，"
        "构图疏密有致，画面清秀雅致，传统韵味浓厚"
    ),
    ArtistStyle.YAN_SHAOTANG: (
        "严绍唐风格：笔墨厚重稳健，线条朴实有力，"
        "人物造型敦厚，场景布局规整，古典气息浓郁"
    ),
    ArtistStyle.YANG_QINGHUA: (
        "杨青华风格：线条流畅优美，人物动态优雅，"
        "构图新颖别致，画面富有诗意和韵律感"
    ),
    ArtistStyle.XU_HONGDA: (
        "徐宏达风格：用笔豪放自如，线条挥洒有力，"
        "人物造型生动活泼，画面气韵生动"
    ),
    ArtistStyle.XU_ZHENGFANG: (
        "徐正方风格：构图工整严谨，线条细致入微，"
        "人物刻画深入，场景布置井然有序"
    ),
    ArtistStyle.ZHAO_SANDAO: (
        "赵三岛风格：线条苍劲老辣，笔墨厚重，"
        "人物造型古朴，画面沉着大气，有金石韵味"
    ),
    ArtistStyle.XU_YIMING: (
        "徐一鸣风格：线条流畅自然，人物造型生动，"
        "构图饱满丰富，故事叙述性强"
    ),
    ArtistStyle.TU_QUANFENG: (
        "屠全枫风格：笔墨清润，线条柔和细腻，"
        "人物温婉雅致，画面柔美和谐"
    ),
    ArtistStyle.JIANG_PING: (
        "蒋萍风格：线条工整秀丽，人物姿态优雅，"
        "构图精巧别致，画面雅致清丽"
    ),
    ArtistStyle.XU_JIN: (
        "徐进风格：用笔稳健扎实，线条工整有力，"
        "人物造型准确，布局主次分明"
    ),
    ArtistStyle.WANG_YIQIU: (
        "王亦秋风格：线条流畅飘逸，人物神态生动，"
        "构图新颖，画面具有现代感和装饰趣味"
    ),
    ArtistStyle.HU_RUOFU: (
        "胡若佛风格：线条精细至极，衣纹如行云流水，"
        "人物婀娜多姿，画面精美绝伦，仕女画尤为出众"
    ),
    ArtistStyle.ZHANG_LINGTAO: (
        "张令涛风格：用笔奔放有力，线条粗犷豪迈，"
        "人物动态强烈，画面富有戏剧性和冲击力"
    ),
}

ARTIST_NAME_MAP = {style.value: style for style in ArtistStyle}