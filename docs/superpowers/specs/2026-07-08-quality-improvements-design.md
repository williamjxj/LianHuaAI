# 白描连环画生成器 — 质量提升设计 Spec

## 概述

提升白描连环画生成系统的输出质量，聚焦四个维度：
1. **Vision QA 质检**（P0）—— 自动检测出图质量，拦截低质量图像
2. **Scene Planner 结构化**（P1）—— 生成场景前先做结构化的分层规划
3. **历史约束注入**（P2）—— 在 story generator prompt 中加入时代约束
4. **宣纸纹理用真实底图**（P3）—— 用 assets/ 下的扫描宣纸纹理替代纯随机噪点

---

## 1. Vision QA 质检

### 目标
在批量生成管线中，对 RunningHub 下载的原始图像进行自动视觉质检。质检不合格时跳过该图（不保存），在日志中记录失败原因。

### 检测维度（3 项）
| 维度 | 检测方法 | 判定标准 |
|------|----------|----------|
| 彩色泄漏 | 调用 DeepSeek Vision（LLM）看图，判断是否含彩色/非黑白元素 | 出现彩色 → fail |
| 现代元素 | LLM 判断图中是否有现代服饰、建筑、物品 | 检测到 → fail |
| 人体畸变 | LLM 判断人物手部、面部是否有明显扭曲/残缺 | 明显畸变 → fail |

### 实现方式
- 新增 `src/image_engine/vision_qa.py`，`VisionQA` 类
  - 复用 `config.yaml` 中 `llm.provider` 的 DeepSeek 配置（`get_llm_config()`）
  - 用 OpenAI 兼容 API（`/v1/chat/completions`），传入 base64 图片
  - 返回结构化结果：`{"pass": bool, "reasons": [str]}`
- 在 `main.py` 的 `ComicPipeline._generate_single()` 中，图像下载后、后期处理前插入质检步骤：
  - pass → 继续后期处理
  - fail → 记录日志，跳过该图（不中断 batch）

### 配置
```yaml
image:
  vision_qa:
    enabled: true           # 是否启用
    provider: deepseek      # 复用 llm.provider
    retry_limit: 0           # 不合格不重试，仅跳过
```

### 新增文件
- `src/image_engine/vision_qa.py`

### 修改文件
- `src/image_engine/backend.py` — 无改动（Vision QA 不改变 ImageResult 签名）
- `src/main.py` — `_run_single()` 中插入 Vision QA 调用
- `config.yaml` — 添加 `image.vision_qa` 配置节

---

## 2. Scene Planner 结构化场景规划

### 目标
在 LLM 生成故事时，要求先输出结构化的画面规划（分镜信息），再基于此生成视觉 Prompt。让 prompt 带有明确的空间/构图指导。

### 实现方式
- `StoryOutput` 新增 `scene_plan` 字段，类型为 `ScenePlan` dataclass：

```python
@dataclass
class ScenePlan:
    foreground: str        # 前景描述
    middle_ground: str     # 中景描述
    background: str        # 背景描述
    character_positions: str  # 人物站位
    actions: str           # 动作
    camera: str            # 镜头角度（如 平视/俯视/特写）
    composition: str       # 构图（如 标准连环画竖幅中心构图）
    lighting: str          # 光影（如 自然光/战场烽烟光）
```

- `generator.py` 的 system prompt 和 user prompt 中加入结构化的画面规划指令，要求 LLM 先输出 JSON 格式的 `scene_plan`，再输出故事文本
- `PromptBuilder` 读取 `story.scene_plan` 字段拼入最终的 image prompt

### 修改文件
- `src/models.py` — 新增 `ScenePlan` dataclass，`StoryOutput` 增加 `scene_plan` 字段
- `src/story_engine/generator.py` — system prompt 中加入结构化规划指令
- `src/story_engine/prompts.py` — 可选的 scene plan prompt 常量
- `src/image_engine/prompt_builder.py` — 从 scene_plan 提取构图/空间描述注入 prompt

---

## 3. 历史约束注入（Prompt 内约束）

### 目标
在 Story Generator 的 system prompt 中增加一段精确的时代约束指令，防止跨朝代混搭。

### 实现方式
- 在 `src/story_engine/prompts.py` 的 `STORY_SYSTEM_PROMPT` 末尾追加一段"时代约束"指令：
  - 人物服饰必须匹配所选朝代
  - 建筑、兵器、礼仪均需符合时代背景
  - 如选定"东汉末年/三国"，禁止使用宋明清服饰、建筑元素
- 在 `src/story_engine/generator.py` 的 `build_story_prompt()` 中，将 `era` 信息传递给 LLM，让 LLM 知道自己正在处理哪个时代

### 修改文件
- `src/story_engine/prompts.py` — 新增 `ERA_CONSTRAINT_PROMPT` 或追加到 `STORY_SYSTEM_PROMPT`
- `src/story_engine/generator.py` — user prompt 中注入时代信息

---

## 4. 宣纸纹理用真实底图

### 目标
用真实的宣纸扫描图替代当前纯随机高斯噪点，使宣纸质感更逼真。

### 实现方式
- `PostProcessor.__init__()` 增加 `paper_texture_dir` 参数（默认 `assets/paper_textures/`）
- 启动时扫描该目录，加载所有 `.jpg`/`.png` 图片作为纹理候选
- `_apply_paper_texture()` 改为：随机选一张纹理底图 → resize 匹配目标图像尺寸 → 叠加混合（alpha blend, 强度 0.1-0.15）
- 若目录为空或不存在，回退到当前的高斯噪点模式

### config.yaml 新增字段
```yaml
image:
  post_process:
    paper_texture_dir: assets/paper_textures/   # 宣纸纹理目录
    paper_texture_blend: 0.15                   # 纹理混合强度
```

### 修改文件
- `src/image_engine/post_process.py` — 修改 `_apply_paper_texture()`
- `config.yaml` — 新增 `paper_texture_dir` / `paper_texture_blend` 配置

---

## 文件变更清单

| 文件 | 改动类型 | 对应模块 |
|------|----------|----------|
| `src/image_engine/vision_qa.py` | **新增** | Vision QA |
| `src/main.py` | 修改 | Vision QA 插入管线 |
| `src/models.py` | 修改 | ScenePlan dataclass + StoryOutput 扩展 |
| `src/story_engine/generator.py` | 修改 | Scene planner prompt + 历史约束 |
| `src/story_engine/prompts.py` | 修改 | 新增 scene plan / 历史约束 prompt |
| `src/image_engine/prompt_builder.py` | 修改 | 读取 scene_plan 注入 prompt |
| `src/image_engine/post_process.py` | 修改 | 真实宣纸纹理加载 + 混合 |
| `config.yaml` | 修改 | vision_qa / paper_texture_dir 等配置 |
| `assets/paper_textures/` | **填充** | 用户放置宣纸扫描图 |

---

## 验证

1. `python -c "from src.image_engine.vision_qa import VisionQA; print('ok')"` — 模块导入
2. `python -c "from src.models import ScenePlan; print('ok')"` — 新 model 导入
3. `python -m src.main --dry-run` — 故事生成含 scene_plan + 历史约束，story output 打印 scene_plan
4. `python -c "
from src.image_engine.post_process import PostProcessor
from PIL import Image
pp = PostProcessor({'post_process':{'paper_texture':True}})
img = Image.new('L', (200,200))
pp.process(img).save('/tmp/texture_test.png')
"` — 宣纸纹理加载逻辑正常
5. `python -m src.main --batch 2` — 完整管线，含 Vision QA 过滤