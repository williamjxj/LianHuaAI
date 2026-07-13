"""RunningHub (runninghub.cn) 图像生成后端

基于 RunningHub AI App API（消费级 API Key 可用）：
  1. POST /task/openapi/ai-app/run  提交任务
  2. POST /task/openapi/status       查询状态
  3. POST /task/openapi/outputs      获取结果

默认 AI App: 全能图片G-2.0-文生图-低价渠道版
需要 RUNNINGHUB_API_KEY 环境变量。
"""

import time
from typing import Any, Dict, List

import requests

from src.config import get_runninghub_api_key
from src.image_engine.backend import ImageBackend, ImageResult

BASE_URL = "https://www.runninghub.cn"
# 全能图片G-2.0-文生图-低价渠道版 (消费级 Key 可用)
DEFAULT_AI_APP_ID = "2046794551444119554"

# 宽高比映射（覆盖所有 canvas_presets，仅用 API 支持的标准比例）
_ASPECT_RATIOS = {
    (768, 576): "4:3",
    (768, 1024): "3:4",
    (806, 576): "4:3",      # 7:5 接近 4:3，用 _fit_canvas 精确裁切
    (864, 576): "3:2",
    (1024, 768): "4:3",
    (1024, 1024): "1:1",
    (1024, 576): "16:9",
    (1152, 576): "2:1",
    (512, 1024): "1:2",
    (1024, 512): "2:1",
    (1152, 768): "3:2",
    (768, 1152): "2:3",
    (576, 1024): "9:16",
}

# 预置 AI App 映射
_AI_APPS = {
    "rhart-image-g-2-official": "2046794551444119554",
}


class RunningHubBackend(ImageBackend):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        rh_cfg = config["image"]["runninghub"]

        self.api_key = get_runninghub_api_key()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Host": "www.runninghub.cn",
        }

        model_name = rh_cfg.get("model", "rhart-image-g-2-official")
        webapp_id = _AI_APPS.get(model_name, model_name)
        self.model_name = model_name
        self.webapp_id = webapp_id

        self.timeout = rh_cfg.get("timeout", 120)
        self.poll_interval = rh_cfg.get("poll_interval", 2)

    def name(self) -> str:
        return f"RunningHub ({self.model_name})"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        **kwargs,
    ) -> ImageResult:
        try:
            task_id = self._submit_task(prompt, width, height)
            if not task_id:
                return ImageResult(success=False, error="提交任务失败: 未获取到 taskId")

            print(f"   ⏳ 任务已提交 (taskId: {task_id})，正在等待生成...")
            image_url = self._poll_result(task_id)

            if not image_url:
                return ImageResult(success=False, error="任务执行超时或失败")

            return ImageResult(
                success=True,
                image_url=image_url,
                metadata={
                    "model": self.model_name,
                    "webapp_id": self.webapp_id,
                    "task_id": task_id,
                    "backend": "runninghub",
                },
            )

        except Exception as e:
            return ImageResult(success=False, error=str(e))

    def _submit_task(self, prompt: str, width: int, height: int) -> str:
        aspect = width / height
        # 找最接近的预定义比例
        best_ratio = "3:4"  # default fallback
        best_diff = float("inf")
        for (rw, rh), ratio_str in _ASPECT_RATIOS.items():
            r = rw / rh
            diff = abs(r - aspect)
            if diff < best_diff:
                best_diff = diff
                best_ratio = ratio_str
        aspect_ratio = best_ratio
        payload = {
            "webappId": self.webapp_id,
            "apiKey": self.api_key,
            "nodeInfoList": [
                {
                    "nodeId": "18",
                    "fieldName": "aspectRatio",
                    "fieldValue": aspect_ratio,
                },
                {
                    "nodeId": "18",
                    "fieldName": "resolution",
                    "fieldValue": "2k",
                },
                {
                    "nodeId": "18",
                    "fieldName": "prompt",
                    "fieldValue": prompt,
                },
            ],
        }
        resp = requests.post(
            f"{BASE_URL}/task/openapi/ai-app/run",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code")
        if code != 0:
            raise RuntimeError(
                f"RunningHub API 返回错误: code={code} msg={data.get('msg', 'unknown')}"
            )
        return data.get("data", {}).get("taskId", "")

    def _poll_result(self, task_id: str) -> str:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            status = self._get_status(task_id)
            if status == "SUCCESS":
                outputs = self._get_outputs(task_id)
                if outputs:
                    return outputs[0]
                return ""
            if status == "FAILED":
                raise RuntimeError(f"任务 {task_id} 失败")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"任务 {task_id} 超时 ({self.timeout}秒)")

    def _get_status(self, task_id: str) -> str:
        resp = requests.post(
            f"{BASE_URL}/task/openapi/status",
            headers=self.headers,
            json={"taskId": task_id, "apiKey": self.api_key},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", resp.text)

    def _get_outputs(self, task_id: str) -> List[str]:
        resp = requests.post(
            f"{BASE_URL}/task/openapi/outputs",
            headers=self.headers,
            json={"taskId": task_id, "apiKey": self.api_key},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        records = result.get("data", [])
        if isinstance(records, list):
            urls = []
            for item in records:
                url = item.get("fileUrl", item.get("file_url", ""))
                if url:
                    urls.append(url)
            return urls
        if isinstance(records, dict) and records.get("failedReason"):
            reason = records["failedReason"]
            raise RuntimeError(
                reason.get("exception_message", "未知错误")
            )
        return []