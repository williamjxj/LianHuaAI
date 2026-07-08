可以，下面直接给出结果。

---

# 基于 Loop Engineering 的中国传统白描连环画自动生成系统技术方案

## 1. 项目目标

构建一个基于 AI 的自动化内容生产系统，实现批量循环生成中国传统白描连环画作品及配套故事解说。

系统具备以下能力：

* 自动搜索并生成历史故事
* 自动规划画面场景
* 自动生成高质量白描连环画
* 自动生成配套故事解说
* 自动质量检测
* 自动循环生成

系统采用 **Loop Engineering + Multi-Agent + ComfyUI** 架构，而不是传统单 Prompt 方案。

---

# 2. 总体架构

```
Scheduler
      │
      ▼
Story Generator
      │
      ▼
Historical Verifier
      │
      ▼
Scene Planner
      │
      ▼
Artist Selector
      │
      ▼
Prompt Builder
      │
      ▼
Image Generator
      │
      ▼
Vision QA
      │
 ┌────┴─────┐
 │          │
Retry      Pass
 │          │
 ▼          ▼
Narration Generator
      │
      ▼
Output
```

整个流程采用闭环（Loop）设计，每一步都可反馈修正，保证输出质量。

---

# 3. 历史故事搜索与生成

## 3.1 故事来源

优先级如下：

| 优先级   | 来源    |
| ----- | ----- |
| ★★★★★ | 三国演义  |
| ★★★★☆ | 三国志   |
| ★★★★☆ | 资治通鉴  |
| ★★★★☆ | 史记    |
| ★★★☆☆ | 左传    |
| ★★★☆☆ | 战国策   |
| ★★★☆☆ | 东周列国志 |
| ★★☆☆☆ | 汉书    |
| ★★☆☆☆ | 后汉书   |
| ★★☆☆☆ | 二十四史  |

要求：

* 正统历史
* 古典演义
* 不涉及玄幻
* 不涉及现代
* 不涉及架空

---

## 3.2 故事生成流程

```
历史知识库

↓

随机选择人物

↓

随机选择事件

↓

验证历史真实性

↓

生成故事摘要

↓

提取关键画面

↓

输出 Scene JSON
```

每张图片仅对应一个故事高潮场景。

例如：

* 桃园结义
* 三顾茅庐
* 长坂坡
* 空城计
* 草船借箭
* 单刀赴会

避免一张图片包含多个事件。

---

## 3.3 Story Agent

输入：

```
随机种子

历史知识库

已生成记录
```

输出：

```
{
故事标题
朝代
人物
地点
主要冲突
关键画面
}
```

Story Agent 负责避免重复故事。

---

# 4. 历史知识审核

History Agent 负责验证：

* 朝代
* 官职
* 建筑
* 武器
* 服饰
* 发饰
* 礼仪
* 地理

输出：

```
{
dynasty

architecture

weapon

armor

costume

hairstyle

background
}
```

确保生成内容符合历史背景。

---

# 5. 场景规划

Scene Planner 不直接写 Prompt。

而是先规划画面。

输出：

```
Foreground

Middle Ground

Background

人物站位

动作

表情

镜头

光影

构图
```

例如：

```
前景：

诸葛亮抚琴

中景：

司马懿军队停军

背景：

西城城门

天空：

乌云

构图：

传统连环画竖版
```

---

# 6. 图像模型选型

## 推荐方案

| 模型           | 推荐指数  | 作用       |
| ------------ | ----- | -------- |
| FLUX Dev     | ★★★★★ | 首次生成     |
| FLUX Kontext | ★★★★★ | 多轮编辑     |
| FLUX.2 Dev   | ★★★★★ | 高质量生成    |
| SDXL         | ★★★★☆ | LoRA生态丰富 |
| Qwen Image   | ★★★★☆ | 中文理解优秀   |
| HiDream      | ★★★★☆ | 国风表现较好   |

### 推荐组合

```
GPT-5.5

↓

FLUX Dev

↓

FLUX Kontext

↓

Upscale

↓

Vision QA
```

原因：

FLUX 系列具有较强的 Prompt 遵循能力，而 FLUX Kontext 支持基于已有图片进行多轮编辑，并保持角色、构图和风格一致性，非常适合循环优化工作流。([ComfyUI][1])

---

# 7. 白描风格实现

建议采用：

```
基础模型

+

LoRA

+

Style Prompt

+

Paper Texture
```

统一约束：

* 黑白
* 宣纸
* 白描
* 墨线
* 排线
* 做旧
* 泛黄纸张

禁止：

* 彩色
* CG
* Anime
* 3D
* 摄影
* 厚涂

---

# 8. 画师风格

建立画师数据库：

```
Artist Database
```

例如：

```
刘继卣

刘锡永

陈光镒

凌涛

徐正平

严绍唐

王亦秋

胡若佛

……
```

每位画师保存：

```
风格特征

排线

人物比例

构图

墨色

线条

典型关键词
```

生成时随机抽取一位画师，全程保持统一，不混合多人风格。

---

# 9. 文字模型选型

## 推荐

| 模型             | 用途             |
| -------------- | -------------- |
| GPT-5.5        | 故事规划           |
| GPT-5.5        | Prompt Builder |
| GPT-5.5        | Narration      |
| GPT-5.5 Vision | 图片审核           |

文字生成要求：

* 80~150 字
* 林汉达风格
* 或高阳风格
* 轻松叙事
* 贴合画面

---

# 10. 技术栈

| 模块         | 技术                        |
| ---------- | ------------------------- |
| Backend    | Python                    |
| API        | FastAPI                   |
| Workflow   | LangGraph 或自研 Loop Engine |
| Scheduler  | APScheduler               |
| Image      | ComfyUI                   |
| Database   | PostgreSQL                |
| Storage    | Cloudflare R2             |
| Frontend   | Next.js                   |
| Deployment | Docker                    |

ComfyUI 采用节点式（DAG）工作流，非常适合将图像生成拆分为模型加载、Prompt 编码、采样、放大、细节修复等模块，便于后续扩展和自动化。([AI Wiki][2])

---

# 11. 工作流

```
Scheduler

↓

Story Agent

↓

History Agent

↓

Scene Planner

↓

Artist Selector

↓

Prompt Builder

↓

ComfyUI

↓

FLUX

↓

FLUX Kontext

↓

Upscale

↓

Vision QA

↓

Narration

↓

Save

↓

Next Loop
```

---

# 12. 自动质量控制

Vision Agent 检查：

```
是否彩色

人物数量

人物比例

是否白描

是否宣纸

是否历史正确

是否现代服饰

是否现代建筑

是否CG

是否Anime

是否手部错误

是否武器错误
```

如果评分低于阈值：

```
重新编辑

↓

再次检测

↓

直到通过
```

---

# 13. 推荐技术路线

| 模块         | 推荐方案               |
| ---------- | ------------------ |
| Story      | GPT-5.5            |
| Knowledge  | 本地历史知识库 + RAG      |
| Prompt     | GPT-5.5            |
| Image      | FLUX Dev / FLUX.2  |
| Image Edit | FLUX Kontext       |
| Style      | LoRA               |
| Workflow   | ComfyUI            |
| QA         | GPT-5.5 Vision     |
| Loop       | Python + LangGraph |
| Deploy     | Docker             |

---

# 14. 总结

本方案采用 **Loop Engineering + Multi-Agent + ComfyUI** 构建自动化连环画生成系统。整体流程以历史知识库为基础，通过 Story Agent、History Agent、Scene Planner、Prompt Builder 等多个 Agent 协同完成故事规划，再结合 FLUX 系列模型完成图像生成与多轮编辑，最后由 Vision QA 自动审核并形成闭环反馈，实现稳定、高质量、可持续循环生成中国传统白描连环画作品。FLUX Kontext 的多轮一致性编辑能力和 ComfyUI 的模块化工作流，使该方案特别适合需要长期自动生产、风格一致和可迭代优化的场景。([arXiv][3])