#!/usr/bin/env bash
# ──────────────────────────────────────────────
# 清除所有生成内容，重置为初始状态
# ──────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🧹 清除所有生成内容..."
echo "============================================"

# 1. 清除 outputs 目录（图片 + 元数据）
OUTPUTS_DIR="$PROJECT_DIR/outputs"
if [ -d "$OUTPUTS_DIR" ]; then
    rm -rf "$OUTPUTS_DIR"/images/*.png "$OUTPUTS_DIR"/images/*.jpg "$OUTPUTS_DIR"/metadata/*.json 2>/dev/null
    echo "   ✓ 清除 outputs/images/ 和 outputs/metadata/ 中的文件"
    # 保留目录结构
    mkdir -p "$OUTPUTS_DIR"/{images,metadata}
else
    echo "   - outputs/ 不存在，跳过"
fi

# 2. 重置 image.backend 为 dry_run
CONFIG_FILE="$PROJECT_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    if grep -q "^image:" "$CONFIG_FILE"; then
        # macOS sed: 将 backend: replicate 改回 backend: dry_run
        sed -i '' 's/^  backend: replicate/  backend: dry_run/' "$CONFIG_FILE" 2>/dev/null || true
        echo "   ✓ config.yaml image.backend 重置为 dry_run"
    else
        echo "   - config.yaml 中未找到 image 配置，跳过"
    fi
else
    echo "   - config.yaml 不存在，跳过"
fi

# 3. 清除 __pycache__（可选，保持干净）
find "$PROJECT_DIR/src" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "   ✓ 清除 __pycache__ 缓存目录"

echo ""
echo "============================================"
echo "✅ 重置完成！"
echo ""
echo "现在可以开始新的一轮生成："
echo "  1. 编辑 config.yaml 设置 image.backend"
echo "     （dry_run / replicate / comfyui / runninghub / zhipu / tongyi）"
echo "  2. python -m src.main --batch 1"
echo "============================================"