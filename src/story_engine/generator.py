"""故事生成器 — 基于 LLM API 生成历史故事"""

import json
import random
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.config import get_llm_config
from src.models import ArtistStyle, ScenePlan, StoryOutput
from src.story_engine.prompts import (
    STORY_SYSTEM_PROMPT,
    NARRATOR_STYLE_KEYS,
    build_story_prompt,
    select_narrator_style,
)
from src.utils.random_utils import pick_random


# ──────────────────────────────────────────
# 10大历史故事板块定义
# 每板块: 占比10% | 含出处书目 | 经典故事场景
# ──────────────────────────────────────────
HISTORY_BOARDS = {
    "three_kingdoms": {
        "name": "三国演义",
        "books": ["《三国演义》"],
        "eras": ["东汉末年", "三国"],
        "examples": [
            ("桃园三结义", "刘备、关羽、张飞在桃园结拜为兄弟"),
            ("温酒斩华雄", "关羽请战华雄，曹操斟热酒壮行"),
            ("三英战吕布", "刘关张三英在虎牢关合力战吕布"),
            ("煮酒论英雄", "曹操与刘备青梅煮酒论天下英雄"),
            ("千里走单骑", "关羽保二位嫂嫂千里寻兄"),
            ("官渡之战", "曹操以少胜多击败袁绍"),
            ("三顾茅庐", "刘备三次拜访请诸葛亮出山"),
            ("长坂坡", "赵云在长坂坡七进七出救阿斗"),
            ("赤壁之战", "孙刘联军火攻大破曹操"),
            ("空城计", "诸葛亮在空城上抚琴退敌"),
            ("定军山", "老将黄忠在定军山斩杀夏侯渊"),
            ("七擒孟获", "诸葛亮七次擒放孟获收服人心"),
            ("失街亭", "马谡兵败街亭"),
            ("五丈原", "诸葛亮在五丈原病逝"),
            ("空城计", "诸葛亮坐空城抚琴退司马懿大军"),
            ("单刀赴会", "关羽独自带刀赴鲁肃之约"),
        ],
    },
    "pre_qin": {
        "name": "东周列国（先秦）",
        "books": ["《东周列国志》"],
        "eras": ["西周", "春秋", "战国"],
        "examples": [
            ("烽火戏诸侯", "周幽王烽火戏诸侯失天下"),
            ("管仲拜相", "管仲被齐桓公拜为相国"),
            ("晏子使楚", "晏子出使楚國不辱使命"),
            ("卧薪尝胆", "勾践卧薪尝胆复国雪耻"),
            ("孙武练兵", "孙武为吴王训练女兵斩宠妃"),
            ("围魏救赵", "孙膑围困魏国都城救赵"),
            ("完璧归赵", "蔺相如完璧归赵不辱使命"),
            ("荆轲刺秦", "荆轲易水悲歌别燕丹刺秦王"),
            ("赵氏孤儿", "程婴舍子救赵氏遗孤"),
            ("田单复齐", "田单火牛阵大破燕军"),
        ],
    },
    "western_han": {
        "name": "西汉历史",
        "books": ["《西汉演义》", "《史记》", "《汉书》"],
        "eras": ["秦末", "楚汉", "西汉"],
        "examples": [
            ("鸿门宴", "项羽在鸿门宴请刘邦欲除之"),
            ("韩信拜将", "萧何月下追韩信，刘邦拜为大将"),
            ("四面楚歌", "项羽被围垓下四面楚歌"),
            ("霸王别姬", "项羽与虞姬诀别"),
            ("苏武牧羊", "苏武持汉节牧羊北海十九年"),
            ("昭君出塞", "王昭君出塞和亲"),
            ("李广射虎", "飞将军李广射石没镞"),
            ("卫青出征", "卫青率军出击匈奴"),
            ("霍去病封狼居胥", "霍去病大破匈奴封狼居胥"),
            ("张骞通西域", "张骞出使西域开拓丝绸之路"),
            ("司马迁著史记", "司马迁忍辱负重撰写《史记》"),
        ],
    },
    "eastern_han": {
        "name": "东汉演义",
        "books": ["《东汉演义》", "《后汉书》"],
        "eras": ["新朝", "东汉"],
        "examples": [
            ("王莽篡汉", "王莽篡位建立新朝"),
            ("光武中兴", "刘秀在昆阳大战中以少胜多"),
            ("班超投笔从戎", "班超投笔从戎出使西域"),
            ("马援伏波", "马援将军出征交趾立铜柱"),
            ("黄巾起义", "张角黄巾起义天下大乱"),
            ("董卓入京", "董卓率兵入洛阳乱朝纲"),
            ("党锢之祸", "宦官专权士大夫遭禁锢"),
        ],
    },
    "sui_tang": {
        "name": "隋唐合集",
        "books": ["《说唐》", "《隋唐演义》", "《薛家将》"],
        "eras": ["隋", "隋唐", "唐"],
        "examples": [
            ("隋炀帝下扬州", "隋炀帝开凿大运河三下扬州"),
            ("瓦岗寨起义", "程咬金秦琼等英雄聚义瓦岗山"),
            ("玄武门之变", "李世民发动玄武门之变登基"),
            ("薛仁贵征东", "薛仁贵三箭定天山平定辽东"),
            ("安史之乱", "安禄山范阳起兵叛乱"),
            ("郭子仪单骑退敌", "郭子仪单骑入回纥军退兵"),
            ("魏徵谏太宗", "魏徵直言进谏唐太宗"),
            ("文成公主入藏", "文成公主远嫁吐蕃"),
        ],
    },
    "song_dynasty": {
        "name": "宋代合集",
        "books": ["《水浒传》", "《杨家将演义》", "《说岳全传》", "《三侠五义》"],
        "eras": ["北宋", "南宋", "宋"],
        "examples": [
            ("陈桥兵变", "赵匡胤陈桥驿黄袍加身"),
            ("杯酒释兵权", "宋太祖杯酒解众将兵权"),
            ("杨家将血战金沙滩", "杨家将金沙滩大战辽兵"),
            ("穆桂英挂帅", "穆桂英挂帅出征大破天门阵"),
            ("岳飞大战金兀术", "岳飞率岳家军在郾城大败金兀术"),
            ("风波亭", "岳飞被秦桧以莫须有罪名害死"),
            ("武松打虎", "武松在景阳冈赤手空拳打死猛虎"),
            ("林教头风雪山神庙", "林冲被逼上梁山"),
            ("智取生辰纲", "晁盖吴用智取梁中书生辰纲"),
            ("鲁提辖拳打镇关西", "鲁达三拳打死镇关西"),
            ("包公铡判官", "包拯铁面无私铡判官"),
        ],
    },
    "ming_founding": {
        "name": "明代开国演义",
        "books": ["《朱元璋演义》"],
        "eras": ["元末", "明初"],
        "examples": [
            ("朱元璋起义", "朱元璋投奔郭子兴起义军"),
            ("决战鄱阳湖", "朱元璋与陈友谅在鄱阳湖决战"),
            ("徐达北伐", "徐达率军北伐攻克大都"),
            ("刘伯温求雨", "刘伯温为朱元璋出谋划策"),
            ("火烧庆功楼", "朱元璋火烧庆功楼"),
            ("常遇春夺城", "常遇春勇猛攻破元大都"),
        ],
    },
    "general_history": {
        "name": "通史&志怪神魔合集",
        "books": ["《资治通鉴》", "《西游记》", "《聊斋志异》"],
        "eras": ["战国", "秦汉", "魏晋", "南北朝", "隋", "唐", "五代", "唐", "清"],
        "examples": [
            ("大闹天宫", "孙悟空大闹天宫"),
            ("三打白骨精", "孙悟空三打白骨精"),
            ("大圣取经", "唐三藏西天取经"),
            ("画皮", "《聊斋》画皮故事"),
            ("聂小倩", "《聊斋》聂小倩与宁采臣故事"),
            ("赤壁之战正史", "《资治通鉴》记载赤壁之战"),
            ("淝水之战", "《资治通鉴》淝水之战谢玄破苻坚"),
        ],
    },
    "late_ming_qing": {
        "name": "晚明晚清乱世演义",
        "books": ["《李自成演义》", "太平天国故事", "左宗棠西征"],
        "eras": ["明末", "清"],
        "examples": [
            ("李自成进京", "李自成大军攻入北京"),
            ("吴三桂引清军入关", "吴三桂山海关引清军入关"),
            ("史可法守扬州", "史可法孤守扬州十日"),
            ("洪承畴降清", "洪承畴被俘后降清"),
            ("太平军起义", "洪秀全金田起义"),
            ("左宗棠收复新疆", "左宗棠抬棺出征收复新疆"),
            ("曾国藩组建湘军", "曾国藩组建湘军对抗太平军"),
        ],
    },
}


class StoryGenerator:
    """故事生成器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        llm_cfg = get_llm_config(config["llm"]["provider"])

        self.client = OpenAI(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg["base_url"],
        )
        self.model = llm_cfg["model"]
        self.temperature = config["llm"].get("temperature", 0.85)
        self.max_tokens = config["llm"].get("max_tokens", 2048)

        self.recent_topics: List[str] = []
        self.avoid_recent = config["story"].get("avoid_recent_topics", 5)

    def select_theme_board(self) -> tuple[str, dict]:
        """按配置权重随机选择10大板块之一"""
        theme_weights = self.config["story"]["themes"]
        # 归一化为总和100
        boards = list(theme_weights.keys())
        weights = [theme_weights[b] for b in boards]
        selected = random.choices(boards, weights=weights, k=1)[0]
        return selected, HISTORY_BOARDS[selected]

    def select_artist(self) -> ArtistStyle:
        """随机选择一位画师风格"""
        return random.choice(ArtistStyle.list_all())

    def select_source_and_example(self, board: dict) -> tuple[str, str, str]:
        """从板块中随机选取出处书目和具体故事场景"""
        book = random.choice(board["books"])
        example_title, example_desc = random.choice(board["examples"])
        return book, example_title, example_desc

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content.strip()

    def _parse_story_json(self, raw: str) -> Dict[str, Any]:
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 {…} 结构（可能前面有文字说明）
        brace_match = re.search(r"\{[\s\S]*\}", raw)
        if brace_match:
            candidate = brace_match.group()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 尝试逐行查找 "{" 之后的内容（兼容 LLM 先发文字再发 JSON 的情况）
        lines = raw.strip().split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("{"):
                candidate = "\n".join(lines[i:])
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
                break

        raise ValueError(f"Cannot parse LLM JSON response:\n{raw[:500]}")

    def generate_story(self, custom_theme: Optional[str] = None) -> StoryOutput:
        """生成一个完整的历史故事（失败时自动重试 3 次）"""
        if custom_theme and custom_theme in HISTORY_BOARDS:
            board_key = custom_theme
            board_info = HISTORY_BOARDS[board_key]
        else:
            board_key, board_info = self.select_theme_board()

        book, ex_title, ex_scene = self.select_source_and_example(board_info)

        era_hint = random.choice(board_info["eras"])

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                # 每次重试重新选旁白风格和画师，增加变化
                narrator_style = select_narrator_style()

                user_prompt = build_story_prompt(
                    theme=board_info["name"],
                    source_book=book,
                    era_hint=era_hint,
                    example_title=ex_title,
                    example_scene=ex_scene,
                    narrator_style=narrator_style,
                )

                raw = self._call_llm(STORY_SYSTEM_PROMPT, user_prompt)
                data = self._parse_story_json(raw)

                # Parse scene_plan if present
                scene_plan_data = data.get("scene_plan")
                scene_plan = ScenePlan(**scene_plan_data) if isinstance(scene_plan_data, dict) else None

                artist = self.select_artist()

                topic_key = data.get("title", "")
                self.recent_topics.append(topic_key)

                # 成功则跳出重试循环
                break

            except (ValueError, json.JSONDecodeError, KeyError, TypeError) as e:
                last_error = e
                if attempt < max_retries:
                    print(f"   ⚠️ JSON 解析失败 (尝试 {attempt}/{max_retries})，重新生成...")
                else:
                    raise ValueError(
                        f"LLM 返回无效 JSON (重试 {max_retries} 次均失败):\n{last_error}"
                    )

        # ─── 以下代码原在循环外，现在按需提取 ───
        if len(self.recent_topics) > self.avoid_recent:
            self.recent_topics.pop(0)

        return StoryOutput(
            title=data.get("title", "无题"),
            theme=data.get("theme", board_info["name"]),
            theme_board=board_key,
            source_book=book,
            era=data.get("era", era_hint),
            scene_description=data.get("scene_description", ""),
            narration=data.get("narration", ""),
            historical_note=data.get("historical_note", ""),
            characters=data.get("characters", []),
            artist=artist,
            scene_plan=scene_plan,
            narrator_style=narrator_style,
        )

    def dry_run(self) -> StoryOutput:
        """无需 API 调用的测试运行"""
        artist = self.select_artist()
        narrator_style = select_narrator_style()
        return StoryOutput(
            title="测试：关羽温酒斩华雄",
            theme="三国演义",
            theme_board="three_kingdoms",
            source_book="《三国演义》",
            era="东汉末年",
            scene_description=(
                "帐前空地上，关羽横刀立马，青龙偃月刀寒光逼人，"
                "地上倒着华雄的首级。曹操端坐帐中，案上温酒尚有余温。"
                "众诸侯或惊或喜，表情各异。"
            ),
            narration=(
                "话说关羽讨令出战华雄，袁术嫌他职位低微，曹操却斟了一杯热酒给他壮行。"
                "关羽说:「斩了华雄回来再喝!」提刀出帐，飞身上马。"
                "众诸侯只听帐外鼓声震天，不多时，关羽提着华雄首级掷于帐前——"
                "那杯酒，还温着呢。"
            ),
            historical_note=(
                "出自《三国演义》第五回，温酒斩华雄是演义经典桥段。"
            ),
            characters=["关羽", "曹操", "袁术", "华雄"],
            artist=artist,
            scene_plan=ScenePlan(
                foreground="关羽横刀立马，青龙偃月刀寒光逼人",
                middle_ground="帐前空地上，倒着华雄的首级",
                background="中军大帐，众诸侯列坐",
                character_positions="关羽居中立马，曹操端坐帐中主位，众诸侯分列两侧",
                actions="关羽提刀立马，曹操举杯",
                camera="中景平视",
                composition="中心构图，关羽位于画面中央",
                lighting="帐外自然昼光",
            ),
            narrator_style=narrator_style,
        )