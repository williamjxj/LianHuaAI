"""Vision QA 质检 — 用 LLM Vision 检查生成图像质量"""

import base64
import io
from dataclasses import dataclass, field
from typing import List

from openai import OpenAI
from PIL import Image

from src.config import get_llm_config


@dataclass
class QAResult:
    """质检结果"""

    passed: bool = True
    reasons: List[str] = field(default_factory=list)


# 质检提示词
_SYSTEM_PROMPT = """你是一位中国传统白描连环画质量审核员。请检查这幅图像并输出JSON。

检查维度：
1. 是否包含彩色（正确白描应为黑白，无彩色泄漏）
2. 是否包含现代元素（现代服饰、建筑、物品、车辆等）
3. 人物手部、面部是否有明显扭曲变形或残缺

输出严格JSON格式（不要包含额外文字）：
{"passed": true/false, "reasons": ["原因1", "原因2"]}

注意：黑白或泛黄老照片风格不算彩色。只有明显彩色区域才算彩色泄漏。"""


class VisionQA:
    """视觉质检器 — 用 LLM Vision 能力检查图像"""

    def __init__(self, config: dict):
        provider = config.get("image", {}).get("vision_qa", {}).get("provider")
        if not provider:
            provider = config.get("llm", {}).get("provider", "deepseek")

        llm_cfg = get_llm_config(provider)
        self.client = OpenAI(api_key=llm_cfg["api_key"], base_url=llm_cfg["base_url"])
        self.model = llm_cfg["model"]
        self.enabled = config.get("image", {}).get("vision_qa", {}).get("enabled", True)

    def check(self, image: Image.Image) -> QAResult:
        """检查图像质量

        Args:
            image: PIL Image (RGB 或 RGBA)

        Returns:
            QAResult — passed=False 时附带失败原因
        """
        if not self.enabled:
            return QAResult(passed=True)

        try:
            base64_img = self._encode_image(image)
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_img}"
                                },
                            },
                            {"type": "text", "text": "请检查这幅连环画图像的质量。"},
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=256,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse_result(raw)

        except Exception as e:
            return QAResult(passed=True, reasons=[f"Vision QA API error: {e}"])

    def _encode_image(self, image: Image.Image) -> str:
        """PIL Image → base64 PNG"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _parse_result(self, raw: str) -> QAResult:
        """解析 LLM 返回的 JSON 结果"""
        import json
        import re

        # 尝试提取 JSON
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return QAResult(
                    passed=data.get("passed", True),
                    reasons=data.get("reasons", []),
                )
            except json.JSONDecodeError:
                pass

        # 回退：根据文本判断
        if "false" in raw.lower() or "not pass" in raw.lower():
            return QAResult(passed=False, reasons=[f"Unparseable rejection: {raw[:200]}"])
        return QAResult(passed=True)