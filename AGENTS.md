# AGENTS.md — 中国传统白描连环画生成器

## 项目概述

AI 驱动的单幅白描连环画自动生成系统。每次生成执行 5 重随机（题材板块→出处书目→经典场景→画师风格→解说风格），经 LLM 生成故事 + 图像 prompt → RunningHub 出图 → 后期宣纸纹理/做旧处理。

**核心管道**: `config.yaml` → `StoryGenerator`(含ScenePlan) → `Narrator` → `PromptBuilder` → `ImageBackend` → `VisionQA` → `PostProcessor`

## 项目结构

```
src/
├── config.py              # YAML 配置 + .env 环境变量加载
├── models.py              # StoryOutput / ArtistStyle(21枚举) / ScenePlan / 风格描述
├── main.py                # CLI 入口 + ComicPipeline 批量循环
├── story_engine/
│   ├── generator.py       # 10大板块 + 83场景 + LLM 故事生成
│   ├── narrator.py        # 旁白解说词独立生成
│   └── prompts.py         # system prompt + 5种解说风格指南
├── image_engine/
│   ├── prompt_builder.py  # 白描 prompt 构建 (中英双语, build_image_prompt / build_negative_prompt)
│   ├── backend.py         # ImageBackend 抽象接口 + ImageResult
│   ├── runninghub_backend.py # RunningHub (runninghub.cn) 云端后端
│   ├── zhipu_backend.py   # 智谱 AI (CogView-4/GLM-Image) 后端
│   ├── tongyi_backend.py  # 通义万相 (wan2.7) 后端
│   ├── minimax_backend.py # MiniMax image-01 后端
│   ├── replicate_backend.py # Replicate SDXL/FLUX 后端
│   ├── comfy_backend.py   # ComfyUI 本地后端 (预留桩，仅返回 error)
│   ├── style_manager.py   # 21 画师风格查询
│   ├── post_process.py    # 宣纸纹理 + 泛黄做旧 + 双线边框 + 标题题字
│   └── vision_qa.py       # LLM Vision 自动质检（彩色泄漏/现代元素/人体畸变）
└── utils/
    └── random_utils.py    # weighted_choice / pick_random
```

## 数据模型

| 模型 | 位置 | 关键字段 |
|------|------|----------|
| ArtistStyle | models.py | 21 位枚举 + ARTIST_STYLE_DESCRIPTIONS |
| StoryOutput | models.py | title/theme/theme_board/source_book/era/artist/narrator_style + scene_plan |
| ScenePlan | models.py | 8 维分镜：foreground/middle_ground/background/character_positions/actions/camera/composition/lighting |
| HISTORY_BOARDS | generator.py | 9 板块 × 书目 × 示例场景 (83 个) |
| NARRATOR_STYLES | prompts.py | 5 种 (林汉达/高阳/金庸/罗贯中/施耐庵) |

## CLI 入口

```
python -m src.main --dry-run                 # 故事测试 (不出图)
python -m src.main --batch 5                 # 批量生成
python -m src.main --batch 3 --theme three_kingdoms --output ./out  # 指定题材
```

## 关键约定

### 权重配置 (config.yaml)
- `story.themes`: 10 大板块各 ~11.1%，总和 100%
- `story.narrator_style: random` → 每轮从 5 种中随机抽取

### 画师规则
- 单人单幅：1 幅只固定 1 位画师风格
- 21 位枚举 `ArtistStyle`，无增减

### 后期处理管线
灰度 → 增强对比 → 宣纸纹理（真实扫描图/噪点回退）→ 泛黄映射 → 污渍 → 双线边框
- `post_process.py` 中的 `aging_intensity` 控制做旧程度
- `paper_texture_dir` 配置宣纸纹理目录，放入 `.jpg/.png` 扫描图后自动随机选取叠加
- 目录为空时回退到随机噪点纹理

### Vision QA 质检
生成图像后自动调用 LLM Vision 进行质量检查（位于 `vision_qa.py`）：
- **彩色泄漏检测**：检查是否含彩色（白描应为黑白）
- **现代元素检测**：检查是否含现代服饰/建筑/物品
- **人体畸变检测**：检查人物手部面部是否有明显扭曲
- 未通过时跳过该图（不保存），不影响 batch 继续运行
- API 调用失败时自动放行（返回 passed），不阻塞管线

### Scene Planner 结构化场景规划
LLM 生成故事时需同时输出 `scene_plan` JSON 子对象（位于 `StoryOutput.scene_plan`）：
- 8 维分镜：前景/中景/背景/人物站位/动作/镜头/构图/光影
- `PromptBuilder` 将 scene_plan 注入 image prompt，增强构图指导
- `dry_run` 模式打印 Scene Plan 信息便于验证

### LLM provider 切换
`config.yaml#llm.provider`:，变量命名如 `DEEPSEEK_API_KEY` 等）

### 图像后端切换
`config.yaml#image.backend`: runninghub / zhipu / tongyi / minimax / replicate / comfyui / dry_run
- **runninghub**（推荐）: 基于 runninghub.cn AI App API，消费级 Key 可用，中文理解强
- **zhipu**: CogView-4/GLM-Image，支持按古典连环画优先策略自动选模
- **tongyi**: 通义万相 wan2.7，阿里百炼
- **minimax**: MiniMax image-01 模型
- **replicate**: 云端 SDXL/FLUX（需 API Token）
- **comfyui**: 本地推理预留桩（仅返回 error）炼
- **comfyui**: 本地推理预留桩
- **dry_run**: 仅生成文案和 Prompt，不出图

## 禁止项

- 不得使用 `as any` / `@ts-ignore` 类型逃逸（Python 项目但请注意 typing 完整性）
- 不得添加现代/玄幻/架空/穿越题材到 HISTORY_BOARDS
- 不得在 Generator 中写死画师风格或解说风格
- Prompt 中的白描风格 `NEGATIVE_PROMPT` 不得移除「colorful, CG, anime, 3D, oil painting, photorealistic」
- `BASE_STYLE_PROMPT` 必须保留「solid black ink fills (墨块)」和「strong black-and-white contrast」— 这是区别于普通线稿的关键
- 后期处理 `post_process.py` 的灰度转换 `convert("L")` 不能移除（否则没有白描感）

## 依赖关键链
/ narrator / vision_qa (DeepSeek/Kimi/MiniMax API)
Pillow>=10.0         ← post_process (宣纸/做旧)
opencv-python        ← post_process (辅助)
python-dotenv        ← config.py (.env 加载)
requests>=2.31       ← runninghub_backend / zhipu_backend / tongyi_backend / minimax_backend
replicate>=0.25      ← replicate_backend (
requests>=2.31       ← runninghub_backend (RunningHub API)
# replicate>=0.25    ← replicate_backend (备选，切换至 replicate 后端时需要)
```

## 已知注意事项

- `replicate_backend.py` 的 `model` 字段是 SDXL 默认值；换 FLUX 需改 `image.replicate.model`
- `runninghub_backend.py` 基于 RunningHub AI App API（`POST /task/openapi/ai-app/run`），消费级-会员 Key 可用，但所有请求（含 status/outputs）均需传 `apiKey` 参数
- `runninghub_backend.py` 的输出使用 `fileUrl`（驼峰）而非 `file_url`
- `minimax_backend.py` 的 `generate()` 会对超长 prompt（>1400 字符）自动截断并打印日志
- `comfy_backend.py` 是空壳桩，仅返回 error
- `scripts/setup.sh` 创建 `venv` 并安装依赖，有 .env 不存在时从 `.env.example` 复制
- Post-process 的 `_apply_paper_texture()` 使用 numpy 随机噪点，每次运行结果略有不同（期望行为）
- `comfy_backend.py` 是空壳桩，所有方法均返回 `ImageResult(success=False, error="ComfyUI 本地后端尚未实现")`
- `vision_qa.py` 复用 `config.py` 的 `get_llm_config()` 获取 provider 配置；API 调用失败时自动放行（返回 passed），不阻塞管线
- `StoryOutput.scene_plan` 为可选字段（Optional[ScenePlan]），LLM 未输出时 `PromptBuilder` 使用通用 prompt 降级
- 若在 `--dry-run` 模式下 Scene Plan 未打印，请检查 LLM 输出是否包含有效的 `scene_plan` JSON 子对象