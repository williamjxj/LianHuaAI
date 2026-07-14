# 中国传统白描连环画自动生成系统

批量循环随机生成单幅中国传统白描连环画作品，配套一段简短历史故事解说文案。

---

## 🖼️ 作品展示 (Gallery)

点击图片查看完整大图 · [🖥️ 本地画廊浏览全部作品 →](http://localhost:8080)（需先启动 `venv/bin/python scripts/r2_gallery.py 8080`）· [📖 画廊配置指南 →](./docs/r2-gallery-guide.md)

| 东汉·光武昆阳突阵 | 三国·孟德献刀刺董卓 |
|:---:|:---:|
| [![光武昆阳突阵](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/光武昆阳突阵图_20260714_123057.png)](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/光武昆阳突阵图_20260714_123057.png) | [![孟德献刀刺董卓](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/孟德献刀刺董卓_20260714_142435.png)](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/孟德献刀刺董卓_20260714_142435.png) |

| 周幽王·千金一笑失江山 | 宋代·金沙滩双龙困主 |
|:---:|:---:|
| [![千金一笑失江山](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/千金一笑失江山_20260714_141726.png)](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/千金一笑失江山_20260714_141726.png) | [![金沙滩双龙困主](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/金沙滩双龙困主_20260714_142106.png)](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/金沙滩双龙困主_20260714_142106.png) |

> 以上作品均为 AI 自动生成，经白描 Prompt 约束 + 后期做旧处理，呈现宣纸墨线效果。每幅作品包含完整的历史故事解说与结构化 Scene Plan 场景规划。
>
> 📂 所有已生成作品存储在 Cloudflare R2，可通过 [在线画廊](https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev) 或 [本地画廊服务器](./docs/r2-gallery-guide.md) 浏览。元数据（画师、解说词、Prompt 等）在 [`outputs/metadata/`](./outputs/metadata/)。

---

## 项目核心理念

```
随机种子 → 选题材 → 选出处 → 选场景 → 选画师 → 选解说风格
     → 生成故事(含ScenePlan) → 构建Prompt → 生成图像 → Vision QA质检 → 后期处理 → 输出
```

每次生成是 **7 重随机** 的排列组合：题材板块、出处书目、经典场景、画师风格、解说风格、画幅比例、画幅宽度 + 结构化场景规划(Scene Plan)指导构图，保证每幅作品的独特性和高质量。

---

## 系统架构

```
config.yaml                    # 全局配置
src/
├── main.py                    # 入口 + 批量生成管线
├── config.py                  # 配置管理（加载 yaml + .env）
├── models.py                  # 数据模型（StoryOutput / ArtistStyle / ScenePlan）
├── story_engine/
│   ├── generator.py           # 故事生成 (LLM + 9大板块 + 83个经典场景)
│   ├── narrator.py            # 旁白解说生成器
│   └── prompts.py             # 系统提示词 + 5种解说风格
├── image_engine/
│   ├── prompt_builder.py      # 白描风格 Prompt 构建 (中英双语)
│   ├── backend.py             # 抽象后端接口 + ImageResult
│   ├── runninghub_backend.py  # RunningHub (runninghub.cn) 云端后端
│   ├── zhipu_backend.py       # 智谱 AI (CogView-4/GLM-Image) 后端
│   ├── tongyi_backend.py      # 通义万相 (wan2.7) 后端
│   ├── minimax_backend.py     # MiniMax image-01 后端
│   ├── replicate_backend.py   # Replicate API 实现
│   ├── comfy_backend.py       # ComfyUI 本地后端 (预留桩)
│   ├── style_manager.py       # 21位画师风格管理
│   ├── post_process.py        # 宣纸纹理 + 泛黄做旧 + 传统边框 + 标题题字
│   └── vision_qa.py           # LLM Vision 自动质检（彩色泄漏/现代元素/人体畸变）
└── utils/
    └── random_utils.py        # 加权随机选择工具
```

## 9大历史故事板块

| 板块 | 占比 | 出处书目 | 场景数 |
|------|------|----------|--------|
| 三国演义 | ~11.12% | 《三国演义》 | 16 |
| 东周列国（先秦） | ~11.11% | 《东周列国志》 | 10 |
| 西汉历史 | ~11.11% | 《西汉演义》《史记》《汉书》 | 11 |
| 东汉演义 | ~11.11% | 《东汉演义》《后汉书》 | 7 |
| 隋唐合集 | ~11.11% | 《说唐》《隋唐演义》《薛家将》 | 8 |
| 宋代合集 | ~11.11% | 《水浒传》《杨家将演义》《说岳全传》《三侠五义》 | 11 |
| 明代开国演义 | ~11.11% | 《朱元璋演义》 | 6 |
| 通史&志怪神魔合集 | ~11.11% | 《资治通鉴》《西游记》《聊斋志异》 | 7 |
| 晚明晚清乱世演义 | ~11.11% | 《李自成演义》、太平天国故事、左宗棠西征 | 7 |
| **合计** | **100%** | **20+ 部典籍** | **83** |

**禁止题材**：现代、玄幻、架空、穿越、科幻。

## 21位古典连环画大师

每次随机抽取一位贯彻整图，不混合多人笔触：

刘继卣、刘锡永、陈光镒、汪玉山、凌涛、李铁生、徐正平、冯墨农、朱光玉、严绍唐、杨青华、徐宏达、徐正方、赵三岛、徐一鸣、屠全枫、蒋萍、徐进、王亦秋、胡若佛、张令涛

## 5种解说风格

| 风格 | 来源 | 特点 |
|------|------|------|
| **林汉达** | 通俗历史作家 | 娓娓道来，短句口语化 |
| **高阳** | 《胡雪岩》作者 | 细节丰富，雅俗共赏 |
| **金庸** | 武侠小说宗师 | 大气磅礴，张弛有度 |
| **罗贯中** | 《三国演义》作者 | 半文半白，典雅庄重 |
| **施耐庵** | 《水浒传》作者 | 市井鲜活，俚语入文 |

每次随机抽取一种，解说词 80-150 字。

## 白描画风控制

统一约束（通过 Prompt Engineering + 后期处理实现）：

- **画种**：传统白描（baimiao）墨线稿
- **纸张**：宣纸质感，泛黄做旧
- **线条**：均匀排线，墨分五色
- **版式**：每次随机选取画幅比例（4:3/7:5/3:2/16:9/2:1）+ 随机宽度（768/896/1024/1152），高度按比例缩放
- **解说条**：底部统一解说条（标题 + 旁白 + 出处，紧凑三行排版）+ 经典双线边框
严格禁止：彩色、CG、二次元、厚涂油画、现代服饰、科幻元素、扭曲人体、模糊线条

## 环境要求

- Python 3.10+
- Apple Silicon (MPS) 或 x86_64
- 需配置的 API Key（见 `.env.example`）

## 快速开始

```bash
# 1. 安装依赖
bash scripts/setup.sh

# 2. 配置 API Key
#    编辑 .env，填入 DeepSeek / Kimi / MiniMax + RunningHub API Key (或 Replicate Token)

# 3. 测试运行（不调图像 API，仅验证故事生成流程）
python -m src.main --dry-run

# 4. 批量生成
python -m src.main --batch 5                    # 随机题材生成 5 幅
python -m src.main --batch 3 --theme three_kingdoms  # 指定三国题材
python -m src.main --batch 10 --delay 3 -o ./works   # 间隔 3 秒，输出到 ./works

# 5. 从已有 metadata 重新生成图像（重新生成旁白 + 随机画幅出图）
python -m src.main --regen
```

### 全部参数

```
--batch, -b N      批量生成数量（默认 1）
--dry-run          测试模式，不调用图像 API
--regen            从已有 metadata JSON 重新生成图像（精简旁白 + 古典连环画风格 + 随机画幅）
--theme, -t KEY    指定题材，可选: three_kingdoms, pre_qin, western_han, eastern_han,
                    sui_tang, song_dynasty, ming_founding, general_history, late_ming_qing
--delay, -d SEC    每幅间隔秒数（默认 2）
--output, -o DIR   输出目录（默认 ./outputs）
--config FILE      配置文件路径（默认 ./config.yaml）
```

## 配置文件

`config.yaml` 可调整：

- `llm.provider` — 切换 LLM 后端（deepseek / kimi / minimax）
- `image.backend` — 图像后端（runninghub / replicate / zhipu / tongyi / comfyui / dry_run）
- `image.canvas_select` — 画幅选择策略（`random` 每次随机 / `4:3` 固定等）
- `image.canvas_presets` — 画幅预设列表（含 4:3 / 7:5 / 3:2 / 16:9 / 2:1）
- `image.regen_widths` — 宽度随机缩放基数 [768, 896, 1024, 1152]
- `image.runninghub.model` — RunningHub 模型（默认 `rhart-image-g-2-official`）
- `image.zhipu.model` — 智谱图像模型（默认 `auto`，由策略选择）
- `image.zhipu.model_strategy` — 智谱模型策略（默认 `classic_comic_first`）
- `image.tongyi.model` — 通义万相模型（默认 `wan2.7-image-pro`）
- `image.vision_qa.enabled` — 是否启用 Vision QA 质检（默认 true）
- `image.vision_qa.provider` — Vision QA 使用的 LLM（默认 reuse llm.provider）
- `image.post_process.paper_texture_dir` — 宣纸纹理扫描图目录（默认 `assets/paper_textures/`）
- `image.post_process.paper_texture_blend` — 纹理混合强度（默认 0.15）
- `story.themes` — 各板块权重
- `story.narrator_style` — 解说风格（random 则每轮随机抽取）
- `story.narration_min_chars` / `story.narration_max_chars` — 旁白字数限制（默认 30-80）
- `image.post_process.paper_texture` — 宣纸纹理开关（默认 true）
- `image.post_process.paper_texture_dir` — 纹理扫描图目录（默认 `assets/paper_textures/`）
- `image.post_process.paper_texture_blend` — 纹理混合强度（默认 0.15）
- `image.post_process.aging_effect` — 做旧效果开关
- `image.post_process.aging_intensity` — 做旧强度（0-1）
- `image.width` — 输出画幅宽度（默认 768，被 canvas_presets 覆盖）
- `image.height` — 输出画幅高度（默认 576，被 canvas_presets 覆盖）
- `image.post_process.add_narration` — 底部解说条开关（默认 true）
- `image.post_process.add_border` — 双线边框开关

## 输出结构

```
outputs/
├── images/                        ← 📂 本地已生成图片
│   ├── 关羽温酒斩华雄_20260708_120000.png      # 处理后成品
│   └── 关羽温酒斩华雄_20260708_120000_raw.png  # 原始下载图
├── metadata/                      ← 📂 生成元数据
│   └── 关羽温酒斩华雄_20260708_120000.json      # 生成元数据
└── works/                         ← 📂 `--regen` 模式输出目录
    ├── 关羽温酒斩华雄.png                        # 重新生成的图像
    └── 关羽温酒斩华雄.json                        # 更新后的元数据
```

元数据包含：标题、板块、出处书目、时代、人物、画师、解说词、解说风格、完整 Prompt、生成时间等。

## 图像生成后端

| 后端 | 状态 | 说明 |
|------|------|------|
| **RunningHub** (runninghub.cn) | ✅ 推荐 | 全能图片G-2 模型，中文理解强，消费级 API Key 即可使用 |
| **Zhipu AI** (open.bigmodel.cn) | ✅ 可用 | CogView-4 / GLM-Image，支持按古典连环画优先策略自动选模 |
| **Tongyi Wanxiang** (DashScope) | ✅ 可用 | 通义万相 wan2.7，中文古风理解好，适合作为国产主力对照组 |
| **MiniMax** (minimaxi.com) | ✅ 可用 | image-01 模型，支持 16:9 横屏 |
| Replicate API | ✅ 可用 | 云端 SDXL/FLUX，需 API Token（账户余额可能不足） |
| ComfyUI 本地 | ⏳ 预留 | 本地推理预留桩（尚未实现） |
| Dry Run | ✅ 可用 | 仅生成文案和 Prompt，不出图 |

### RunningHub 配置

`config.yaml` 中 `image.backend: runninghub` 时使用。基于 RunningHub **AI App API**（消费级-会员 API Key 可用），通过异步任务提交 + 轮询获取结果。

详细 API 文档：[runninghub.cn 文档中心](https://www.runninghub.cn/runninghub-api-doc-cn)

```yaml
image:
  backend: runninghub
  runninghub:
    model: rhart-image-g-2-official       # AI App ID: 2046794551444119554
    timeout: 300                            # 任务超时秒数
    poll_interval: 2                        # 轮询间隔秒数
```

环境变量 `.env`：
```
RUNNINGHUB_API_KEY=your_key_here
```

### Zhipu AI 配置

`config.yaml` 中 `image.backend: zhipu` 时使用。通过智谱开放平台的图像生成 HTTP API 调用，适合中文古风、历史题材和连环画风格。

```yaml
image:
    backend: zhipu
    zhipu:
        model: auto
        model_strategy: classic_comic_first
        classic_model: cogView-4-250304
        text_heavy_model: glm-image
        base_url: https://open.bigmodel.cn/api/paas/v4
        timeout: 120
        quality: hd
        watermark_enabled: false
```

环境变量 `.env`：
```
ZHIPU_API_KEY=your_key_here
```

### 通义万相配置

`config.yaml` 中 `image.backend: tongyi` 时使用。通过 DashScope / 百炼官方接口调用通义万相，适合批量生成古风图像。

```yaml
image:
    backend: tongyi
    tongyi:
        model: wan2.7-image-pro
        base_url: https://dashscope.aliyuncs.com/api/v1
        timeout: 120
        size: 2K
        watermark: false
        thinking_mode: true
```

环境变量 `.env`：
```
DASHSCOPE_API_KEY=your_key_here
```

## 后期处理管线

1. 转灰度 → 2. 增强对比 → 3. 宣纸纹理叠加（优先使用 `assets/paper_textures/` 中的真实扫描图，目录为空时回退随机噪点）→ 4. 泛黄做旧映射 → 5. 污渍效果 → 6. 底部解说条（标题 + 旁白 + 出处）→ 7. 输出

## Vision QA 自动质检

生成图像后自动调用 LLM Vision 进行质量检查，确保输出符合白描标准：

- **彩色泄漏检测** — 检查是否含有彩色（白描应为纯黑白）
- **现代元素检测** — 检查是否出现现代服饰、建筑或物品
- **人体畸变检测** — 检查人物手部、面部是否有明显扭曲变形

质检未通过的图像会被自动跳过（不保存），不影响 batch 中后续图像的生成。API 调用失败时自动放行，确保管线不因网络问题中断。

`config.yaml` 中 `image.vision_qa.enabled` 可关闭此功能。

## Scene Planner 结构化场景规划

LLM 生成故事时同步输出 **Scene Plan** 子对象，对画面进行完整分镜规划：

| 维度 | 说明 |
|------|------|
| **前景** (foreground) | 画面最前方的主体元素 |
| **中景** (middle_ground) | 承前启后的叙事主体 |
| **背景** (background) | 时代环境与氛围 |
| **人物站位** (character_positions) | 人物的位置与朝向关系 |
| **动作** (actions) | 关键动态瞬间 |
| **镜头** (camera) | 景别选择（特写/中景/全景/鸟瞰）|
| **构图** (composition) | 画面结构（中心/三角/对角线/留白）|
| **光影** (lighting) | 光源方向与明暗基调 |

该场景规划会被注入图像 Prompt，有效弥补通用文生图模型在构图控制上的不足。

在 `--dry-run` 模式下会打印 Scene Plan 信息，方便验证合理性。

## JSON 解析容错

LLM 返回的 JSON 可能格式异常，`StoryGenerator._parse_story_json()` 实现了 4 级回退解析：

1. 直接 `json.loads` 解析
2. 从 markdown 代码块 ` ```json ``` ` 提取
3. 用正则 `{…}` 提取第一个 JSON 对象
4. 逐行扫描查找首个 `{` 起始行

全部失败时自动重试 3 次（每次重新选择解说风格，增加 LLM 输出变化概率），极大减少了因 JSON 格式问题导致生成中断的情况。

## 项目文件结构（完整）

```
comic/
├── README.md
├── AGENTS.md
├── TODO.md
├── config.yaml
├── .env
├── .env.example
├── requirements.txt
├── scripts/
│   └── setup.sh
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── story_engine/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── narrator.py
│   │   └── prompts.py
│   ├── image_engine/
│   │   ├── __init__.py
│   │   ├── zhipu_backend.py        # 智谱 AI 图像生成后端
│   │   ├── prompt_builder.py
│   │   ├── backend.py
│   │   ├── replicate_backend.py
│   │   ├── runninghub_backend.py
│   │   ├── comfy_backend.py
│   │   ├── style_manager.py
│   │   ├── post_process.py
│   │   └── vision_qa.py
│   └── utils/
│       ├── __init__.py
│       └── random_utils.py
├── outputs/
│   ├── images/
│   ├── metadata/
│   └── works/
├── assets/
│   └── paper_textures/
└── docs/
    ├── chatgpt.md
    ├── 自动连环画循环生成方案.md
    └── baimiao_generation_blueprint.html
```

## License

MIT