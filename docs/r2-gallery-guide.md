# ☁️ R2 Comic Bucket 浏览指南

如何预览和查看 Cloudflare R2 中存储的连环画作品。

---

## 目录

1. [R2 存储配置](#1-r2-存储配置)
2. [方案对比一览](#2-方案对比一览)
3. [方案一：本地画廊服务器（推荐快速预览）](#3-方案一本地画廊服务器推荐快速预览)
4. [方案二：Cyberduck（macOS GUI，推荐日常管理）](#4-方案二cyberduckmacos-gui推荐日常管理)
5. [方案三：Cloudflare Dashboard（Web 管理）](#5-方案三cloudflare-dashboardweb-管理)
6. [方案四：AWS CLI（命令行操作）](#6-方案四aws-cli命令行操作)
7. [方案五：rclone serve（本地 HTTP 服务器）](#7-方案五rclone-serve本地-http-服务器)
8. [附：R2 目录结构](#8-附r2-目录结构)

---

## 1. R2 存储配置

项目 `.env` 中的 R2 相关变量：

```dotenv
# Cloudflare R2
S3_API=https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com/comic
R2_URL=https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev
R2_ACCESS_KEY_ID=<your_r2_access_key_id>
R2_SECRET_ACCESS_KEY=<your_r2_secret_access_key>
```

| 变量 | 用途 |
|------|------|
| `S3_API` | S3 兼容 API 端点（含 bucket 名） |
| `R2_URL` | 公开访问 URL（不支持目录浏览） |
| `R2_ACCESS_KEY_ID` | 访问密钥 ID（从 Cloudflare R2 面板获取）|
| `R2_SECRET_ACCESS_KEY` | 访问密钥 Secret（从 Cloudflare R2 面板获取）|

> ⚠️ **注意**：R2 公开 URL 不支持目录浏览。直接访问 `https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/` 会返回 404。只能通过完整路径访问单个文件，如：
>
> ```
> https://pub-349ba70c209a4d1eb96f5f9b7b5f946c.r2.dev/光武昆阳突阵图_20260714_123057.png
> ```

---

## 2. 方案对比一览

| 方案 | 类型 | 体验 | 安装 | 推荐场景 |
|------|------|------|------|----------|
| ① 本地画廊 | Python HTTP 服务 | ⭐⭐⭐⭐⭐ | 无需额外安装 | **快速浏览作品** |
| ② Cyberduck | macOS GUI 客户端 | ⭐⭐⭐⭐⭐ | `brew install` | **日常文件管理** |
| ③ Cloudflare Dashboard | Web UI | ⭐⭐⭐ | 无需安装 | 偶尔查看/管理 |
| ④ AWS CLI | 命令行 | ⭐⭐⭐ | `pip install` | 批量操作/脚本 |
| ⑤ rclone serve | HTTP 服务 | ⭐⭐⭐⭐ | `brew install` | 轻量 HTTP 浏览 |

---

## 3. 方案一：本地画廊服务器（推荐快速预览）

项目自带 `scripts/r2_gallery.py`，启动后通过浏览器以图墙形式展示 R2 中的连环画。

### 启动

```bash
# 确保在项目根目录
cd /path/to/LianHuaAI

# 使用项目虚拟环境启动
venv/bin/python scripts/r2_gallery.py 8080
```

参数 `8080` 为端口号，可按需修改。

### 访问

打开浏览器访问 **http://localhost:8080**

### 功能

- ✅ 图片墙网格布局，自动加载 R2 中所有图片
- ✅ 点击图片放大预览（Lightbox）
- ✅ 搜索过滤文件名
- ✅ 排序：最新优先 / 最早优先 / 按名称
- ✅ 深色主题，适配桌面和移动端
- ✅ 每张卡片显示文件名、上传时间、文件大小

### 依赖

画廊使用 `boto3` 和 `python-dotenv`，项目虚拟环境中已安装，无需额外操作。

### 注意事项

- 画廊读取的是 R2 bucket 中的文件列表，**不是本地文件**
- 图片实际托管在 R2 上，画廊仅提供浏览界面
- 停止服务按 `Ctrl+C`

---

## 4. 方案二：Cyberduck（macOS GUI，推荐日常管理）

Cyberduck 是 macOS 上流行的 S3 兼容客户端，支持图形化浏览、预览、拖拽下载。

### 安装

```bash
brew install --cask cyberduck
```

### 连接配置

1. 打开 Cyberduck
2. **File → Open Connection**（或按 `Cmd+O`）
3. 选择 **Amazon S3**
4. 填入以下参数：

| 字段 | 值 |
|------|-----|
| Server | `ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com` |
| Port | `443` |
| Access Key ID | 从 `.env` 的 `R2_ACCESS_KEY_ID` 获取 |
| Secret Access Key | 从 `.env` 的 `R2_SECRET_ACCESS_KEY` 获取 |
| Path | `comic` |

5. 勾选 **Use default (s3v4)** 签名版本
6. 点击 **Connect**

### 功能

- 📁 文件列表浏览（类似 Finder）
- 🖼️ 缩略图预览
- ⬇️ 拖拽下载到本地
- ⬆️ 上传/删除文件
- 📋 批量操作

---

## 5. 方案三：Cloudflare Dashboard（Web 管理）

无需安装任何软件，通过 Cloudflare 官方 Web 控制台管理。

### 步骤

1. 打开 https://dash.cloudflare.com
2. 登录你的 Cloudflare 账号
3. 左侧导航栏点击 **R2**
4. 选择 `comic` bucket

### 功能

- Web 界面浏览文件列表
- 搜索文件
- 上传/下载/删除
- 查看文件详情
- 设置公开访问权限

适合偶尔查看或管理，功能不如客户端丰富。

---

## 6. 方案四：AWS CLI（命令行操作）

AWS CLI 可以通过 S3 兼容接口操作 R2，适合脚本化批量处理。

### 安装

```bash
# 使用 pip 安装
venv/bin/pip install awscli

# 或通过 Homebrew
brew install awscli
```

### 配置

```bash
aws configure set aws_access_key_id <从.env的R2_ACCESS_KEY_ID获取>
aws configure set aws_secret_access_key <从.env的R2_SECRET_ACCESS_KEY获取>
```

### 常用命令

```bash
# 列出所有文件
aws s3 ls s3://comic/ \
  --endpoint-url https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com \
  --region auto

# 下载文件到本地
aws s3 cp s3://comic/光武昆阳突阵图_20260714_123057.png ./ \
  --endpoint-url https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com \
  --region auto

# 同步整个 bucket 到本地
aws s3 sync s3://comic/ ./r2-backup/ \
  --endpoint-url https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com \
  --region auto

# 上传文件
aws s3 cp ./local-image.png s3://comic/ \
  --endpoint-url https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com \
  --region auto
```

---

## 7. 方案五：rclone serve（本地 HTTP 服务器）

rclone 是一个命令行云存储管理工具，支持 R2 的 S3 兼容接口，可以启动 HTTP 服务浏览文件。

### 安装

```bash
brew install rclone
```

### 配置

```bash
rclone config
```

交互式配置流程：

1. `n` 新建配置，命名为 `lianhua`
2. 选择 `s3` 类型（Amazon S3 Compliant Storage Provider）
3. 选择 `Cloudflare R2` 作为 provider
4. 输入 Access Key ID（从 `.env` 的 `R2_ACCESS_KEY_ID` 获取）
5. 输入 Secret Access Key（从 `.env` 的 `R2_SECRET_ACCESS_KEY` 获取）
6. 输入 Region: `auto`
7. 输入 Endpoint: `https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com`
8. 其他选项保持默认
9. 完成配置

### 启动 HTTP 服务

```bash
# 启动 HTTP 浏览服务
rclone serve http --addr :8081 lianhua:comic

# 打开浏览器访问 http://localhost:8081
```

### 命令式（不创建配置）

```bash
rclone serve http --addr :8081 \
  :s3,access_key_id=<从.env的R2_ACCESS_KEY_ID获取>,\
secret_access_key=<从.env的R2_SECRET_ACCESS_KEY获取>,\
endpoint=https://ad9e2df833f783172de48d7948ed2acd.r2.cloudflarestorage.com,\
region=auto:comic
```

支持目录树浏览和文件预览。

---

## 8. 附：R2 目录结构

当前 R2 `comic` bucket 中的文件列表（截至 2026-07-14）：

| 文件 | 大小 | 上传时间 |
|------|------|----------|
| `光武昆阳突阵图_20260714_123057.png` | 2,010 KB | 2026-07-14 19:30 |
| `昆阳夜突十三骑_20260714_121655.png` | 1,350 KB | 2026-07-14 19:16 |
| `长安观耀_20260714_122156.png` | 1,117 KB | 2026-07-14 19:21 |
| `采石飞戈夺岸矶_20260714_123735.png` | 798 KB | 2026-07-14 19:37 |
| `夜访书痴_20260714_123416.png` | 550 KB | 2026-07-14 19:34 |

文件命名格式：`<作品名>_<生成日期>_<时间戳>.png`

文件上传由 `src/main.py` 的 `_upload_to_r2()` 方法自动完成，启用 `--r2` 标志即可：

```bash
venv/bin/python -m src.main --batch 5 --r2
```
