"""旁白生成器 — 独立优化旁白文案"""

from typing import Any, Dict, Optional

from openai import OpenAI

from src.config import get_llm_config
from src.story_engine.prompts import build_narration_prompt


class Narrator:
    """旁白解说词生成器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        llm_cfg = get_llm_config(config["llm"]["provider"])

        self.client = OpenAI(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg["base_url"],
        )
        self.model = llm_cfg["model"]
        self.temperature = config["llm"].get("temperature", 0.85)

    def generate(
        self,
        scene_description: str,
        style: Optional[str] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
        theme: str = "",
    ) -> str:
        """为场景生成旁白解说词

        Args:
            scene_description: 画面场景描述
            style: 旁白风格 (林汉达 | 高阳 | 金庸 | 罗贯中 | 施耐庵)
            min_chars: 最少字数
            max_chars: 最多字数
            theme: 故事题材

        Returns:
            旁白文案
        """
        style = style or self.config["story"].get("narrator_style", "林汉达")
        min_chars = min_chars or self.config["story"].get("narration_min_chars", 80)
        max_chars = max_chars or self.config["story"].get("narration_max_chars", 150)

        user_prompt = build_narration_prompt(style, scene_description, min_chars, max_chars, theme)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=self.temperature,
            max_tokens=1024,
        )

        return response.choices[0].message.content.strip()
