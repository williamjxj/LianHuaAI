# AGENTS.md — 中国传统白描连环画生成器

## 项目概述

AI 驱动的单幅白描连环画自动生成系统。每次生成执行 5 重随机（题材板块→出处书目→经典场景→画师风格→解说风格）+ 2 重画幅随机（比例 + 宽度），经 LLM 生成故事 + 图像 prompt → RunningHub 出图 → 后期宣纸纹理/做旧处理。

**核心管道**: `config.yaml` → `StoryGenerator`(含ScenePlan) → `Narrator` → `PromptBuilder` → `ImageBackend` → `VisionQA` → `PostProcessor`

## 项目结构

```
src/
├── config.py              # YAML 配置 + .env 环境变量加载
├── models.py              # StoryOutput / ArtistStyle(21枚举) / ScenePlan / 风格描述
├── main.py                # CLI 入口 + ComicPipeline 批量循环
├── story_engine/
│   ├── generator.py       # 9 大板块 + 83 场景 + LLM 故事生成
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
python -m src.main --regen                   # 从已有 metadata 批量重新生成图像
```

## 关键约定

### 权重配置 (config.yaml)
- `story.themes`: 9 大板块各 ~11.1%，总和 100%
- `story.narrator_style: random` → 每轮从 5 种中随机抽取
- `image.canvas_select: random` → 每次从 canvas_presets 中随机选一种画幅
- `image.canvas_presets`: 5 种画幅（4:3/7:5/3:2/16:9/2:1），每次随机
- `image.regen_widths`: [768, 896, 1024, 1152] — 随机缩放宽度，高度按比例计算
- `image.post_process.add_narration`: 底部解说条开关（默认 true，控制标题+旁白+出处合并显示）

### 画师规则
- 单人单幅：1 幅只固定 1 位画师风格
- 21 位枚举 `ArtistStyle`，无增减

### 后期处理管线
灰度 → 增强对比 → 宣纸纹理（真实扫描图/噪点回退）→ 泛黄映射 → 污渍 → 底部解说条（标题+旁白+出处）→ 双线边框
- `post_process.py` 中的 `aging_intensity` 控制做旧程度
- `paper_texture_dir` 配置宣纸纹理目录，放入 `.jpg/.png` 扫描图后自动随机选取叠加
- 目录为空时回退到随机噪点纹理
- `_add_bottom_info_bar()`: 统一底部解说条，3 行布局：标题（加粗大字号）、旁白（自动换行，最多2行，超长省略）、出处（右对齐小字，带 —— 前缀）。使用 `<Title> —— <Narration> —— <Source>` 三段式显示在仿古底色透明条中。旁白字体约 2.2% 高度（紧凑）

### 画幅随机化
每次生成从以下预设中随机选取一种画幅比例，再随机从 `regen_widths: [768, 896, 1024, 1152]` 中选宽度，高度按比例缩放，保证每次输出绝对尺寸不同：
- 4:3 (768×576) — 经典传统
- 7:5 (806×576) — 传统连环画常见比例
- 3:2 (864×576) — 经典照片比例
- 16:9 (1024×576) — 宽屏（原默认）
- 2:1 (1152×576) — 超宽幅
- 随机化示例：4:3 选中 width=1024 → 1024×768；16:9 选中 width=896 → 896×504
- 强制适配：`_fit_canvas()` 通过 center-crop + resize 将后端返回的任意尺寸图像强制统一到目标画幅

### JSON 解析容错
`StoryGenerator._parse_story_json()` 在 LLM 返回格式异常时有 4 级回退解析：
1. 直接 `json.loads`
2. 从 markdown 代码块 ````json```` 提取
3. 用正则 `{…}` 提取第一个 JSON 对象
4. 逐行扫描查找首个 `{` 起始行
全部失败时自动重试 3 次（每次重新选择解说风格，增加 Parser 原始输出变化概率）

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
- **comfyui**: 本地推理预留桩（仅返回 error）
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
- `runninghub_backend.py` 的宽高比改用数学最近匹配：从预定义映射表中找最接近当前 w/h 的比例，兼容随机缩放宽度后的各种尺寸
- `minimax_backend.py` 的 `generate()` 会对超长 prompt（>1400 字符）自动截断并打印日志
- `comfy_backend.py` 是空壳桩，仅返回 error
- `scripts/setup.sh` 创建 `venv` 并安装依赖，有 .env 不存在时从 `.env.example` 复制
- Post-process 的 `_apply_paper_texture()` 使用 numpy 随机噪点，每次运行结果略有不同（期望行为）
- `comfy_backend.py` 是空壳桩，所有方法均返回 `ImageResult(success=False, error="ComfyUI 本地后端尚未实现")`
- `vision_qa.py` 复用 `config.py` 的 `get_llm_config()` 获取 provider 配置；API 调用失败时自动放行（返回 passed），不阻塞管线
- `StoryOutput.scene_plan` 为可选字段（Optional[ScenePlan]），LLM 未输出时 `PromptBuilder` 使用通用 prompt 降级
- 若在 `--dry-run` 模式下 Scene Plan 未打印，请检查 LLM 输出是否包含有效的 `scene_plan` JSON 子对象
- `--regen` 模式：遍历 `outputs/metadata/` 下所有 JSON，重新生成精简旁白(30-80字)、注入"中国古典连环画风格，三国演义连环画风格"到 prompt，随机选画幅出图，保存到 `outputs/works/`。同时输出更新后的 metadata JSON 到 `outputs/works/`
- JSON 解析容错：`_parse_story_json()` 有 4 级回退解析 + 3 次自动重试（每次重选解说风格），有效降低 LLM 返回格式异常导致的失败率
- 画幅宽度随机化：`_select_canvas()` 先随机选比例预设，再从 `regen_widths: [768, 896, 1024, 1152]` 中随机选宽度，按比例计算高度，保证每次输出绝对尺寸不同