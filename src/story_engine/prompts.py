"""故事生成的系统提示词"""

import random

# ─── 5种解说风格 ─────────────────────────────
NARRATOR_STYLES = {
    "lin_handa": (
        "林汉达风格：语言通俗易懂，娓娓道来如讲故事，"
        "注重情节的连贯性和人物的心理活动，语气亲切自然，"
        "如同一位博学的长者在给孩子讲历史故事。"
        "句子短小精悍，善用口语化表达，避免文言和过于书面化的词语。"
    ),
    "gao_yang": (
        "高阳风格（胡雪岩作者）：叙事从容不迫，细节丰富生动，"
        "善于通过具体的人物言行展现历史情境，"
        "语言雅俗共赏，既有文人的雅致，又有市井的鲜活。"
        "常以具体器物、服饰、礼仪细节烘托时代氛围。"
    ),
    "jin_yong": (
        "金庸风格：叙事大气磅礴，人物刻画栩栩如生，"
        "语言既有古典文学韵味又有现代小说的可读性。"
        "善于渲染气氛、塑造英雄气概，叙事节奏张弛有度，"
        "常以短句营造紧张感，以铺垫烘托高潮。"
    ),
    "luo_guanzhong": (
        "罗贯中风格（三国演义作者）：半文半白，典雅庄重，"
        "叙事宏阔大气，善于铺陈战争场面和英雄气概。"
        "语言极具表现力，人物对话生动传神。"
        "常有「话说」「却说」「且看」等章回小说开头语。"
    ),
    "shi_naian": (
        "施耐庵风格（水浒传作者）：语言通俗活泼，贴近市井民生，"
        "人物语言极具个性，善于通过动作和对话塑造人物。"
        "叙事节奏明快，细节描写生动传神，常以俚语俗语入文。"
    ),
}

NARRATOR_STYLE_KEYS = list(NARRATOR_STYLES.keys())


def select_narrator_style() -> str:
    """随机抽取一种解说风格"""
    return random.choice(NARRATOR_STYLE_KEYS)


def get_narrator_style_guide(style: str) -> str:
    """获取风格描述"""
    return NARRATOR_STYLES.get(style, NARRATOR_STYLES["lin_handa"])


# ─── 故事生成系统提示 ─────────────────────────
STORY_SYSTEM_PROMPT = """你是一位精通中国古典历史与文学的连环画故事编剧。你的任务是为中国传统白描连环画生成故事内容。

## 核心要求

1. **历史真实性**：所有故事必须基于正史或经典演义，人物服饰、兵器、建筑、礼仪需严格符合对应朝代规制。

2. **题材范围**：以下十大板块随机抽取：
   - 三国演义 | 东周列国（先秦）| 西汉历史 | 东汉演义 | 隋唐合集
   - 宋代合集（水浒传、杨家将、说岳全传、三侠五义）
   - 明代开国演义 | 通史&志怪神魔合集（资治通鉴、西游记、聊斋志异）
   - 晚明晚清乱世演义（李自成、太平天国、左宗棠）
   
   **严禁**现代、玄幻、架空、穿越题材，也不得编造不在上述板块中的故事。

3. **叙事风格**：故事选材应具有画面感和戏剧冲突——适合用单幅画面表现的经典场景。

4. **解说词风格**：解说词要贴合指定的叙事风格（林汉达/高阳/金庸/罗贯中/施耐庵），不能平淡叙述。

5. **输出格式**：严格按照以下JSON格式返回，不得包含额外文字。

## 输出JSON格式
```json
{
  "title": "故事标题（四到八字，传统章回风格）",
  "theme": "题材分类",
  "era": "历史时期",
  "scene_description": "画面场景的详细描述（200-300字），包含人物位置、姿态、表情、服饰颜色纹样、兵器、背景建筑/山水等，供画师参考",
  "narration": "旁白解说词（80-150字），严格按照指定的解说风格",
  "historical_note": "此场景的历史出处（一两句话）",
  "characters": ["人物1", "人物2"]
}
```

## 重要约束
- scene_description 要具体到人物的动态、神情、服饰细节，这是画师作画的依据
- narration 要贴合指定的解说风格，控制在80-150字
- 确保历史细节准确——比如三国时期没有马镫、唐代铠甲形制与明代不同等"""


def build_story_prompt(
    theme: str,
    source_book: str,
    era_hint: str,
    example_title: str,
    example_scene: str,
    narrator_style: str,
) -> str:
    """构建故事生成 prompt"""
    style_guide = get_narrator_style_guide(narrator_style)

    return f"""请为中国传统白描连环画生成一个故事。

题材板块：{theme}
出处书目：{source_book}
历史时期：{era_hint}
可参考场景：{example_title}（{example_scene}，不限于此，只是举例）

解说风格要求：{style_guide}

要求：
1. 从指定的题材板块和书目中，选择一个具体的历史场景或演义故事片段
2. 场景要有画面张力——人物互动、戏剧冲突、典型瞬间
3. 旁白解说词要严格按照指定的解说风格撰写
4. 所有细节必须符合历史背景
5. scene_description 要详细，包含人物服饰颜色、姿态、神情、兵器等

请严格按照JSON格式输出。"""


def build_narration_prompt(
    style: str,
    scene: str,
    min_chars: int,
    max_chars: int,
    theme: str = "",
) -> str:
    """构建旁白生成 prompt"""
    style_guide = get_narrator_style_guide(style)

    return f"""请根据以下画面场景，写一段旁白解说词。

画面场景：{scene}
故事题材：{theme if theme else '中国传统历史故事'}

风格要求：{style_guide}

字数要求：{min_chars}-{max_chars}字

请直接输出旁白文案，不要包含其他内容。"""