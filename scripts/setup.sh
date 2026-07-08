#!/usr/bin/env bash
# ──────────────────────────────────────────────
# 中国传统白描连环画生成器 — 环境初始化脚本
# ──────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🎨 中国传统白描连环画生成器 — 环境初始化"
echo "============================================"
echo ""

# 1. 检测 Python
echo "🔍 [1/4] 检测 Python 环境..."
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "   ✓ $PYTHON_VERSION"

# 2. 创建虚拟环境
echo "🔍 [2/4] 设置 Python 虚拟环境..."
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "   ✓ 虚拟环境已创建: $VENV_DIR"
else
    echo "   ✓ 虚拟环境已存在: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 3. 安装依赖
echo "🔍 [3/4] 安装 Python 依赖..."
pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_DIR/requirements.txt"
echo "   ✓ 依赖安装完成"

# 4. 配置检查
echo "🔍 [4/4] 配置检查..."
CONFIG_FILE="$PROJECT_DIR/config.yaml"
ENV_FILE="$PROJECT_DIR/.env"
ENV_EXAMPLE="$PROJECT_DIR/.env.example"

if [ -f "$CONFIG_FILE" ]; then
    echo "   ✓ config.yaml 存在"
else
    echo "   ⚠️  config.yaml 不存在，请检查"
fi

if [ -f "$ENV_FILE" ]; then
    echo "   ✓ .env 存在"

    # 检查必要变量
    source "$ENV_FILE"

    if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
        echo "   ✓ DEEPSEEK_API_KEY 已配置"
    else
        echo "   ⚠️  DEEPSEEK_API_KEY 未配置"
    fi

    if [ -n "${REPLICATE_API_TOKEN:-}" ]; then
        echo "   ✓ REPLICATE_API_TOKEN 已配置"
    else
        echo "   ⚠️  REPLICATE_API_TOKEN 未配置 (图像生成需要)"
        echo "     请前往 https://replicate.com 注册获取 Token"
    fi
else
    echo "   ⚠️  .env 文件不存在"
    echo "     正在从 .env.example 创建..."
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "   📄 已创建 $ENV_FILE，请编辑填入你的 API Key"
    fi
fi

# 创建输出目录
mkdir -p "$PROJECT_DIR/outputs"/{images,metadata}

echo ""
echo "============================================"
echo "✅ 环境初始化完成！"
echo ""
echo "使用方法:"
echo "  cd $PROJECT_DIR"
echo "  source .venv/bin/activate"
echo "  python -m src.main --dry-run      # 测试运行"
echo "  python -m src.main --batch 5      # 生成5幅"
echo "============================================"
