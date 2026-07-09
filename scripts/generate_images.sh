#!/usr/bin/env bash
# ──────────────────────────────────────────────
# 根据 outputs/metadata/*.json 中的 prompt 批量生成图片
# 不重新生成故事，只调 Replicate API 出图 + 后期处理
# ──────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

OUTPUTS_DIR="$PROJECT_DIR/outputs"
META_DIR="$OUTPUTS_DIR/metadata"
IMAGE_DIR="$OUTPUTS_DIR/images"

# 读取 .env
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

if [ -z "${REPLICATE_API_TOKEN:-}" ]; then
    echo "❌ REPLICATE_API_TOKEN 未配置，请检查 .env"
    exit 1
fi

# 参数：模型（默认 SDXL）
MODEL="${1:-stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc}"

echo "🎨 批量生成图片 — 从 metadata 读取 prompt"
echo "   模型: $MODEL"
echo "   元数据: $META_DIR"
echo "   输出: $IMAGE_DIR"
echo "============================================"

mkdir -p "$IMAGE_DIR"

# 收集所有 .json 文件
JSON_FILES=("$META_DIR"/*.json)
TOTAL=${#JSON_FILES[@]}
COUNT=0

for meta_file in "${JSON_FILES[@]}"; do
    [ -f "$meta_file" ] || continue
    COUNT=$((COUNT + 1))

    # 提取字段
    title=$(python3 -c "import json; print(json.load(open('$meta_file'))['title'])" 2>/dev/null)
    prompt=$(python3 -c "import json; print(json.load(open('$meta_file'))['image_prompt'])" 2>/dev/null)
    negative=$(python3 -c "import json; print(json.load(open('$meta_file'))['negative_prompt'])" 2>/dev/null)

    if [ -z "$prompt" ]; then
        echo "   ⚠️  [$COUNT/$TOTAL] $meta_file 中无 image_prompt，跳过"
        continue
    fi

    safe_name=$(echo "$title" | python3 -c "import sys,re; print(re.sub(r'[^\w]', '_', sys.stdin.read().strip()))")
    timestamp=$(date +%Y%m%d_%H%M%S)

    echo ""
    echo "📄 [$COUNT/$TOTAL] $title"
    echo "   🖼️  调 Replicate 生成..."

    # 调 Replicate API
    output=$(curl -s -X POST "https://api.replicate.com/v1/models/${MODEL}/predictions" \
        -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$(python3 -c "
import json
params = {
    'input': {
        'prompt': '''$prompt''',
        'negative_prompt': '''$negative''',
        'width': 768,
        'height': 1024,
        'num_inference_steps': 30,
        'guidance_scale': 7.5,
        'num_outputs': 1,
    }
}
print(json.dumps(params))
")")

    # 解析返回，获取 prediction id 并轮询
    pred_id=$(echo "$output" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

    if [ -z "$pred_id" ]; then
        echo "   ❌ API 调用失败: $(echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail', d.get('error', 'unknown')))" 2>/dev/null)"
        continue
    fi

    # 轮询直到完成
    status="starting"
    image_url=""
    for i in $(seq 1 60); do
        sleep 3
        result=$(curl -s "https://api.replicate.com/v1/predictions/$pred_id" \
            -H "Authorization: Bearer $REPLICATE_API_TOKEN")

        status=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
        image_url=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); o=d.get('output'); print(o[0] if isinstance(o,list) and o else o if isinstance(o,str) else '')" 2>/dev/null || echo "")

        echo -n "."
        if [ "$status" = "succeeded" ] && [ -n "$image_url" ]; then
            echo ""
            echo "   ✅ 生成成功: $image_url"
            break
        fi
        if [ "$status" = "failed" ]; then
            echo ""
            echo "   ❌ 生成失败"
            break
        fi
    done

    if [ -n "$image_url" ]; then
        # 下载原始图片
        raw_path="$IMAGE_DIR/${safe_name}_${timestamp}_raw.png"
        curl -sL -o "$raw_path" "$image_url"
        echo "   💾 原始图片: $raw_path"

        # 更新 metadata 中的 image_url 和 image_path
        python3 -c "
import json
p = '$meta_file'
d = json.load(open(p))
d['image_url'] = '$image_url'
d['backend'] = 'replicate'
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
" 2>/dev/null && echo "   📝 metadata 已更新"

        # 后期处理（调用 Python post_process）
        python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from src.image_engine.post_process import process_image
from PIL import Image
img = Image.open('$raw_path')
result = process_image(img)
out_path = '$IMAGE_DIR/${safe_name}_${timestamp}.png'
result.save(out_path)
print(f'   处理后: {out_path}')
" 2>/dev/null || echo "   ⚠️  后期处理跳过（可能缺 Pillow）"
    fi
done

echo ""
echo "============================================"
echo "✅ 完成！共处理 $TOTAL 个 metadata 文件"
ls -la "$IMAGE_DIR"/*.png 2>/dev/null | awk '{print "   " $NF " (" $5 " bytes)"}'