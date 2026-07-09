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
        "刘继卣（北派宗师）：工写兼备，融合西画人体解剖与传统白描；劈笔丝毛独创技法，线条刚劲顿挫、轻重变化极强；人物造型写实精准，骨骼肌肉写实，武将雄浑、孩童灵动；衣纹大笔挥洒流畅，善用皴擦表现体积；画面构图大开大合，气势磅礴，神态心理刻画入微；兼顾动物、人物、重彩条屏，代表作《武松打虎》《大闹天宫》《鸡毛信》，是新中国连环画奠基人。"
    ),
    ArtistStyle.LIU_XIYONG: (
        "刘锡永（三国造型奠基人）：北派徐燕荪一脉，线条苍辣沉厚，简繁对比分明，次要人物简笔概括；人物比例严谨、古装考据标准；构图饱满宏大，擅长大规模古战场、群像叙事，分层清晰；山水背景厚重写实，上美《三国》五虎造型设计者，代表作《长坂坡》《赤壁大战》《瓦岗寨》。"
    ),
    ArtistStyle.CHEN_GUANGYI: (
        "陈光镒：线条粗犷奔放、顿挫有力，短粗硬线强化力量感；人物动态极度夸张，肢体幅度大；明暗对比强烈，黑白张力拉满，火光、厮杀、冲锋等激烈战斗场面为一绝；擅长乱世武将、混战群像，代表作《千里走单骑》《董卓进京》。"
    ),
    ArtistStyle.WANG_YUSHAN: (
        "汪玉山：工整流畅长线白描，线条均匀顺滑无剧烈顿挫；构图四平八稳、传统庙堂式布局；人物造型端正圆润，多侧面构图，面部略丰腴；亭台楼阁、古代室内布景考据精细，传统界画功底扎实，擅长文官朝堂、民间市井故事，《三国》多文官分册出自其手。"
    ),
    ArtistStyle.LING_TAO: (
        "凌涛（沈曼云高徒）：线条清秀顿挫、棱角柔和，笔墨淡雅清润；人物气质温润儒雅，仕女线条纤细修长；山水留白多，意境悠远空灵；群像疏密排布舒缓，少激烈冲突，擅长文人、隐逸、闺阁题材，画面整体柔和和谐。"
    ),
    ArtistStyle.LI_TIESHENG: (
        "李铁生：线条刚健挺直，硬直线条表现铠甲、兵器；武将形象英武方正，衣纹转折棱角分明；擅长武将对阵、边塞征伐宏大场面；短板是普通百姓面部造型相似度偏高，辨识度弱于武将，《东周列国》《三国》武将册主力画师。"
    ),
    ArtistStyle.XU_ZHENGPING: (
        "徐正平：造型极致严谨规范，线条挺拔干净、无多余杂笔；人物动态自然克制，神态精准内敛；构图电影化叙事，主次层次清晰，擅长智者、谋士、文臣刻画，诸葛亮形象标杆；上美三国核心造型画师，线条工整兼具气韵。"
    ),
    ArtistStyle.FENG_MONONG: (
        "冯墨农：墨法层次丰富，浓淡干湿变化明显，善用淡墨渲染阴影；线条粗细随形体自由切换，衣纹层层叠加区分布料质感；擅长多人互动复杂场景，人物前后遮挡、空间层次极强，擅长家族、市井群像。"
    ),
    ArtistStyle.ZHU_GUANGYU: (
        "朱光玉：工致秀丽铁线描，线条均匀纤细流畅；人物造型古典典雅，仕女身段柔美；构图疏密均衡，留白克制，无大开大合冲突；传统文人画韵味浓厚，画面清秀雅致，才子佳人、宫廷仕女题材见长。"
    ),
    ArtistStyle.YAN_SHAOTANG: (
        "严绍唐：笔墨厚重朴实，线条粗拙稳健、少华丽转折；人物造型敦厚质朴，面部圆润，动态平实少夸张；场景布局规整对称，古意浓郁，传统老派连环画风格，适合民间演义、乡土历史故事。"
    ),
    ArtistStyle.YANG_QINGHUA: (
        "杨青华：长线飘逸流畅，线条自带韵律曲线；人物姿态优雅舒展，衣袂飘带动感柔和；构图灵动新颖，打破传统对称布局，画面诗意柔和，擅长仙侠、仕女、浪漫古典故事，装饰感强。"
    ),
    ArtistStyle.XU_HONGDA: (
        "徐宏达（海派四小名旦）：用笔挥洒豪放，线条粗细变化自由；人物生动活泼，神态富有烟火气；墨色干湿并用，画面气韵流动，兼顾武将与市井小人物，动态松弛自然，不刻板。"
    ),
    ArtistStyle.XU_ZHENGFANG: (
        "徐正方：极致工整细密白描，线条细碎入微，每处衣纹、配饰完整刻画；人物面部细节拉满，五官刻画深入；场景器物排布井然有序，界画精准，偏静态叙事，适合宫廷、礼仪、精细古风场景。"
    ),
    ArtistStyle.ZHAO_SANDAO: (
        "赵三岛：金石味苍劲老辣线条，顿挫厚重如刻碑；笔墨沉暗浓郁，黑白对比沉稳；人物造型古朴厚重，面部轮廓方正硬朗；画面沉着大气，无轻飘笔触，擅长乱世枭雄、古代战争、侠义硬汉题材。"
    ),
    ArtistStyle.XU_YIMING: (
        "徐一鸣：自然流畅中长线，线条柔和不生硬；构图饱满充盈，画面信息量大；叙事性极强，单幅容纳多人物、完整情节；人物动态生活化，冲突自然不刻意，通俗演义连环画主力。"
    ),
    ArtistStyle.TU_QUANFENG: (
        "屠全枫：笔墨清润淡雅，细线柔和圆润，无尖锐棱角；人物温婉秀气，男女形象柔美统一；画面低对比、留白柔和，整体柔美和谐，闺阁、神话温柔题材为主。"
    ),
    ArtistStyle.JIANG_PING: (
        "蒋萍：工整秀丽兰叶描，线条流畅雅致；人物身姿优雅舒展，五官清秀；构图精巧留白，疏密错落有致，画面清丽干净，宫廷仕女、才子故事擅长。"
    ),
    ArtistStyle.XU_JIN: (
        "徐进：笔墨扎实稳健，线条均匀有力、工整不飘；人物造型标准准确，五官规整；画面主次分割清晰，前景实、背景虚，克制内敛，文臣、中等规模战场都适配。"
    ),
    ArtistStyle.WANG_YIQIU: (
        "王亦秋：飘逸灵动游丝描，线条轻盈洒脱；人物神态鲜活，擅长夸张趣味表情；构图新颖多变，融入民间装饰纹样，兼具传统与现代装饰趣味，代表作《杨门女将》《兰亭传奇》。"
    ),
    ArtistStyle.HU_RUOFU: (
        "胡若佛（张令涛黄金搭档）：极致精细游丝白描，衣纹行云流水、发丝配饰分毫毕现；仕女婀娜柔美，眉眼精致，古典美人刻画国内顶尖；线条极细但力道充足，重细节质感，几乎专擅才子佳人、宫廷仕女题材。"
    ),
    ArtistStyle.ZHANG_LINGTAO: (
        "张令涛：奔放粗重长线，线条豪迈粗犷，转折力度极强；人物动态戏剧化，肢体幅度大，冲突冲击力强；常与胡若佛合作，张令涛铺大构图、人物动态，胡若佛细化衣纹面部，擅长战争、家国史诗题材。"
    ),
}

ARTIST_NAME_MAP = {style.value: style for style in ArtistStyle}