# AGENTS.md — 中国传统白描连环画生成器

## 项目概述

AI 驱动的单幅白描连环画自动生成系统。每次生成执行 5 重随机（题材板块→出处书目→经典场景→画师风格→解说风格），经 LLM 生成故事 + 图像 prompt → Replicate/ComfyUI 出图 → 后期宣纸纹理/做旧处理。

**核心管道**: `config.yaml` → `StoryGenerator` → `Narrator` → `PromptBuilder` → `ImageBackend` → `PostProcessor`

## 项目结构

```
src/
├── config.py              # YAML 配置 + .env 环境变量加载
├── models.py              # StoryOutput / ArtistStyle(21枚举) / 风格描述
├── main.py                # CLI 入口 + ComicPipeline 批量循环
├── story_engine/
│   ├── generator.py       # 10大板块 + 83场景 + LLM 故事生成
│   ├── narrator.py        # 旁白解说词独立生成
│   └── prompts.py         # system prompt + 5种解说风格指南
├── image_engine/
│   ├── prompt_builder.py  # 白描 SD/FLUX prompt 构建 (中英双语)
│   ├── backend.py         # ImageBackend 抽象接口
│   ├── replicate_backend.py  # Replicate API 实现
│   ├── comfy_backend.py   # ComfyUI 本地后端 (预留桩)
│   ├── style_manager.py   # 21 画师查询
│   └── post_process.py    # 宣纸纹理 + 泛黄做旧 + 双线边框
└── utils/
    └── random_utils.py    # weighted_choice
```

## 数据模型

| 模型 | 位置 | 关键字段 |
|------|------|----------|
| ArtistStyle | models.py | 21 位枚举 + ARTIST_STYLE_DESCRIPTIONS |
| StoryOutput | models.py | title/theme/theme_board/source_book/era/artist/narrator_style |
| HISTORY_BOARDS | generator.py | 9 板块 × 书目 × 示例场景 (83 个) |
| HARRATOR_STYLES | prompts.py | 5 种 (林汉达/高阳/金庸/罗贯中/施耐庵) |

## CLI 入口

```
python -m src.main --dry-run          # 故事测试 (不出图)
python -m src.main --batch 5          # 批量生成
python -m src.main --batch 3 --theme three_kingdoms -o ./out  # 指定题材
```

## 关键约定

### 权重配置 (config.yaml)
- `story.themes`: 10 大板块各 ~11.1%，总和 100%
- `story.narrator_style: random` → 每轮从 5 种中随机抽取

### 画师规则
- 单人单幅：1 幅只固定 1 位画师风格
- 21 位枚举 `ArtistStyle`，无增减

### 后期处理管线
灰度 → 增强对比 → 宣纸纤维噪点 → 泛黄映射 → 污渍 → 双线边框
- `post_process.py` 中的 `aging_intensity` 控制做旧程度

### LLM provider 切换
`config.yaml#llm.provider`: deepseek / kimi / minimax
（对应 .env 中的 API Key 和环境变量命名）

### 图像后端切换
`config.yaml#image.backend`: replicate / comfyui / dry_run

## 禁止项

- 不得使用 `as any` / `@ts-ignore` 类型逃逸（Python 项目但请注意 typing 完整性）
- 不得添加现代/玄幻/架空/穿越题材到 HISTORY_BOARDS
- 不得在 Generator 中写死画师风格或解说风格
- Prompt 中的白描风格 `NEGATIVE_PROMPT` 不得移除「color, CG, anime, 3D, oil painting」
- 后期处理 `post_process.py` 的灰度转换 `convert("L")` 不能移除（否则没有白描感）

## 依赖关键链

```
openai>=1.0          ← story_engine (DeepSeek/Kimi/MiniMax API)
replicate>=0.25      ← replicate_backend (图像生成)
Pillow>=10.0         ← post_process (宣纸/做旧)
opencv-python        ← post_process (辅助)
python-dotenv        ← config.py (.env 加载)
```

## 已知注意事项

- `replicate_backend.py` 的 `model` 字段是 SDXL 默认值；换 FLUX 需改 `image.replicate.model`
- `comfy_backend.py` 是空壳桩，仅返回 error
- `scripts/setup.sh` 创建 `.venv` 并安装依赖，有 .env 不存在时从 `.env.example` 复制
- Post-process 的 `_apply_paper_texture()` 使用 numpy 随机噪点，每次运行结果略有不同（期望行为）