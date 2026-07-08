# 中国传统白描连环画自动生成系统

批量循环随机生成单幅中国传统白描连环画作品，配套一段简短历史故事解说文案。

## 项目核心理念

```
随机种子 → 选题材 → 选出处 → 选场景 → 选画师 → 选解说风格
     → 生成故事 → 构建Prompt → 生成图像 → 后期处理 → 输出
```

每次生成是 **5 重随机** 的排列组合：题材板块、出处书目、经典场景、画师风格、解说风格，保证每幅作品的独特性。

---

## 系统架构

```
config.yaml                    # 全局配置
src/
├── main.py                    # 入口 + 批量生成管线
├── config.py                  # 配置管理（加载 yaml + .env）
├── models.py                  # 数据模型
├── story_engine/
│   ├── generator.py           # 故事生成 (LLM + 10大板块 + 83个经典场景)
│   ├── narrator.py            # 旁白解说生成器
│   └── prompts.py             # 系统提示词 + 5种解说风格
├── image_engine/
│   ├── prompt_builder.py      # 白描风格 Prompt 构建 (中英双语)
│   ├── backend.py             # 抽象后端接口
│   ├── replicate_backend.py   # Replicate API 实现
│   ├── comfy_backend.py       # ComfyUI 本地后端 (预留)
│   ├── style_manager.py       # 21位画师风格管理
│   └── post_process.py        # 宣纸纹理 + 泛黄做旧 + 传统边框
└── utils/
    └── random_utils.py        # 加权随机选择工具
```

## 10大历史故事板块

| 板块 | 占比 | 出处书目 | 场景数 |
|------|------|----------|--------|
| 三国演义 | ~11% | 《三国演义》 | 16 |
| 东周列国（先秦） | ~11% | 《东周列国志》 | 10 |
| 西汉历史 | ~11% | 《西汉演义》《史记》《汉书》 | 11 |
| 东汉演义 | ~11% | 《东汉演义》《后汉书》 | 7 |
| 隋唐合集 | ~11% | 《说唐》《隋唐演义》《薛家将》 | 8 |
| 宋代合集 | ~11% | 《水浒传》《杨家将演义》《说岳全传》《三侠五义》 | 11 |
| 明代开国演义 | ~11% | 《朱元璋演义》 | 6 |
| 通史&志怪神魔合集 | ~11% | 《资治通鉴》《西游记》《聊斋志异》 | 7 |
| 晚明晚清乱世演义 | ~12% | 《李自成演义》、太平天国故事、左宗棠西征 | 7 |
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
- **构图**：竖幅传统连环画开本
- **线条**：均匀排线，墨分五色
- **版式**：经典连环画双线边框

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
#    编辑 .env，填入 DeepSeek / Kimi / MiniMax + Replicate Token

# 3. 测试运行（不调图像 API，仅验证故事生成流程）
python -m src.main --dry-run

# 4. 批量生成
python -m src.main --batch 5                    # 随机题材生成 5 幅
python -m src.main --batch 3 --theme three_kingdoms  # 指定三国题材
python -m src.main --batch 10 --delay 3 -o ./works   # 间隔 3 秒，输出到 ./works
```

### 全部参数

```
--batch, -b N      批量生成数量（默认 1）
--dry-run          测试模式，不调用图像 API
--theme, -t KEY    指定题材，可选: three_kingdoms, pre_qin, western_han, eastern_han,
                    sui_tang, song_dynasty, ming_founding, general_history, late_ming_qing
--delay, -d SEC    每幅间隔秒数（默认 2）
--output, -o DIR   输出目录（默认 ./outputs）
--config FILE      配置文件路径（默认 ./config.yaml）
```

## 配置文件

`config.yaml` 可调整：

- `llm.provider` — 切换 LLM 后端（deepseek / kimi / minimax）
- `image.backend` — 图像后端（replicate / comfyui / dry_run）
- `story.themes` — 各板块权重
- `story.narrator_style` — 解说风格（random 则每轮随机抽取）
- `image.post_process` — 宣纸纹理、做旧强度、边框开关

## 输出结构

```
outputs/
├── images/
│   ├── 关羽温酒斩华雄_20260708_120000.png      # 处理后成品
│   └── 关羽温酒斩华雄_20260708_120000_raw.png  # 原始下载图
└── metadata/
    └── 关羽温酒斩华雄_20260708_120000.json      # 生成元数据
```

元数据包含：标题、板块、出处书目、时代、人物、画师、解说词、解说风格、完整 Prompt、生成时间等。

## 图像生成后端

| 后端 | 状态 | 说明 |
|------|------|------|
| Replicate API | ✅ 可用 | 云端 SDXL/FLUX，需 API Token |
| ComfyUI 本地 | ⏳ 预留 | M3 本地推理，速度较慢 |
| Dry Run | ✅ 可用 | 仅生成文案和 Prompt，不出图 |

## 后期处理管线

1. 转灰度 →  2. 增强对比 →  3. 宣纸纤维纹理叠加 →  4. 泛黄做旧映射 →  5. 传统双线边框 →  6. 输出

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
│   │   ├── prompt_builder.py
│   │   ├── backend.py
│   │   ├── replicate_backend.py
│   │   ├── comfy_backend.py
│   │   ├── style_manager.py
│   │   └── post_process.py
│   └── utils/
│       ├── __init__.py
│       └── random_utils.py
├── outputs/
│   ├── images/
│   └── metadata/
├── assets/
│   └── paper_textures/
└── docs/
    ├── chatgpt.md
    ├── 自动连环画循环生成方案.md
    └── baimiao_generation_blueprint.html
```

## License

MIT