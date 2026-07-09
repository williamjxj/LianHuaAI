#!/usr/bin/env python3
"""
连环画素材批量爬取脚本 — 百度图片通用兜底
===========================================

读取 scripts/scrape.json，按画家分目录从百度图片搜索并下载白描连环画素材。

特性:
- 百度图片搜索（acjson JSON API）
- 关键词粗筛：丢弃现代插画/AI绘图/海报/油画等
- 图像分析细筛：分辨率检测 + 灰度/彩色占比检测
- 简单反爬：随机 User-Agent + 请求间隔
- 支持断点续传（跳过已存在的文件）
- 其他站点（lib.sinocomic.com / lhhart.com）预留桩接口

用法:
    python scripts/scrape.py                          # 全部画家，每关键词 5 张
    python scripts/scrape.py --limit 10               # 每关键词最多 10 张
    python scripts/scrape.py --artist 刘继卣           # 只爬指定画家
    python scripts/scrape.py --artist 刘继卣 --limit 20
    python scripts/scrape.py --output ./my_images     # 指定输出目录
    python scripts/scrape.py --dry-run                # 只搜索不下载
"""

import argparse
import json
import os
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import numpy as np
import requests
from PIL import Image
from tqdm import tqdm

# ─── 路径常量 ──────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = SCRIPT_DIR / "scrape.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "comic_reference"

# ─── 默认参数 ──────────────────────────────────────

DEFAULT_LIMIT = 5
DEFAULT_MIN_WIDTH = 200
DEFAULT_MIN_HEIGHT = 200
DEFAULT_MAX_COLOR_RATIO = 0.15       # 彩色像素占比超过此值则丢弃
DEFAULT_MIN_FILE_SIZE_KB = 5         # 小于此值的文件视为无效
DEFAULT_REQUEST_INTERVAL = (1.0, 2.5)
DEFAULT_KEYWORD_INTERVAL = (1.5, 3.0)

# ─── 百度图片 JSON API ─────────────────────────────

BAIDU_IMAGE_API = "https://image.baidu.com/search/acjson"

# ─── 随机 User-Agent 池 ────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

# ─── 过滤关键词 ────────────────────────────────────
# 匹配到 → 直接丢弃

BLOCK_KEYWORDS = [
    "现代插画", "AI绘图", "ai绘画", "ai生成", "彩色重绘", "海报", "油画",
    "短视频截图", "书法单字", "人物照片", "cos", "cosplay",
    "color", "colored", "painting", "poster", "oil",
    "anime", "CG", "3D", "卡通", "动漫", "二次元",
    "表情包", "头像", "壁纸", "手机壁纸",
]

# 匹配到 → 加权保留（排序靠前）

PREFER_KEYWORDS = [
    "线稿", "白描", "原稿", "连环画", "小人书", "黑白", "线描",
    "内页", "扫描", "工笔", "手稿", "墨线",
]

# ────────────────────────────────────────────────────
#  桩接口：其他站点搜索（待实现）
# ────────────────────────────────────────────────────

def search_lib_sinocomic(query: str, limit: int = 5) -> list[dict]:
    """
    [桩] 中国连环画数字图书馆 (lib.sinocomic.com) 搜索
    TODO: 接入馆藏搜索 API / 页面解析
    """
    return []


def search_lhhart(query: str, limit: int = 5) -> list[dict]:
    """
    [桩] 连艺网 (lhhart.com) 搜索
    TODO: 接入画家专题页面解析
    """
    return []


# ────────────────────────────────────────────────────
#  HTTP 工具
# ────────────────────────────────────────────────────

def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def build_headers(referer: str = "https://image.baidu.com/") -> dict:
    return {
        "User-Agent": get_random_ua(),
        "Referer": referer,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }


# ────────────────────────────────────────────────────
#  百度图片搜索
# ────────────────────────────────────────────────────

def search_baidu_images(
    query: str,
    limit: int = 5,
    timeout: int = 15,
) -> list[dict]:
    """
    通过百度图片 acjson 接口搜索。
    返回: [{"url": str, "title": str, "width": int, "height": int}, ...]
    """
    results: list[dict] = []
    pn = 0
    max_pages = max((limit * 2) // 30 + 2, 3)

    session = requests.Session()
    session.headers.update(build_headers())

    # 先访问一次首页获取 cookie
    try:
        session.get("https://image.baidu.com/", timeout=10, headers=build_headers())
    except Exception:
        pass

    for page in range(max_pages):
        if len(results) >= limit * 3:
            break

        params = {
            "tn": "resultjson_com",
            "ipn": "rj",
            "word": query,
            "pn": pn,
            "rn": "30",
            "ie": "utf-8",
            "oe": "utf-8",
        }

        try:
            resp = session.get(
                BAIDU_IMAGE_API,
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()

            # 百度有时返回带有特殊前缀的 JSON
            text = resp.text
            if text.startswith("try{") or "(" in text[:20]:
                # 可能是 JSONP 包裹，尝试提取
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    text = match.group()
            data = json.loads(text)
        except json.JSONDecodeError:
            # 可能被反爬，跳过这一页
            pn += 30
            continue
        except requests.RequestException as e:
            print(f"  ⚠ 搜索请求失败 [{query} p{page}]: {e}")
            break

        entries = data.get("data", [])
        if not entries:
            break

        for entry in entries:
            url = entry.get("objURL", "") or entry.get("thumbURL", "") or entry.get("middleURL", "")
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                continue
            results.append({
                "url": url,
                "title": entry.get("fromPageTitle", "") or entry.get("fromPageTitleEnc", ""),
                "width": int(entry.get("width", 0) or 0),
                "height": int(entry.get("height", 0) or 0),
            })

        pn += 30

        if len(entries) < 30:
            break  # 最后一页

        # 页间间隔
        time.sleep(random.uniform(*DEFAULT_REQUEST_INTERVAL))

    return results


# ────────────────────────────────────────────────────
#  关键词过滤（粗筛）
# ────────────────────────────────────────────────────

def filter_by_keyword(item: dict) -> tuple[bool, str]:
    """
    根据 URL 和标题中的关键词做粗筛。
    返回 (保留?, 原因)
    """
    url = item.get("url", "")
    title = item.get("title", "")
    combined = f"{url} {title}".lower()

    for kw in BLOCK_KEYWORDS:
        if kw.lower() in combined:
            return False, f"匹配丢弃词: {kw}"

    return True, ""


def has_prefer_keyword(item: dict) -> bool:
    """是否包含优先关键词"""
    url = item.get("url", "")
    title = item.get("title", "")
    combined = f"{url} {title}".lower()
    return any(kw.lower() in combined for kw in PREFER_KEYWORDS)


def sort_by_preference(results: list[dict]) -> list[dict]:
    """优先关键词的结果排前面"""
    preferred = [r for r in results if has_prefer_keyword(r)]
    others = [r for r in results if not has_prefer_keyword(r)]
    return preferred + others


# ────────────────────────────────────────────────────
#  图像分析过滤（细筛）
# ────────────────────────────────────────────────────

def filter_by_image(
    image_bytes: bytes,
    min_width: int = DEFAULT_MIN_WIDTH,
    min_height: int = DEFAULT_MIN_HEIGHT,
    max_color_ratio: float = DEFAULT_MAX_COLOR_RATIO,
    min_file_size_kb: float = DEFAULT_MIN_FILE_SIZE_KB,
) -> tuple[bool, str]:
    """
    对已下载的图片字节做分析过滤:
    1. 文件大小检查
    2. 分辨率检查
    3. 灰度/彩色像素占比检查
    返回 (保留?, 原因)
    """
    # 文件大小
    size_kb = len(image_bytes) / 1024
    if size_kb < min_file_size_kb:
        return False, f"文件过小 ({size_kb:.1f}KB)"

    # 解析图片
    try:
        img = Image.open(BytesIO(image_bytes))
    except Exception as e:
        return False, f"无法解析图片: {e}"

    # 分辨率
    w, h = img.size
    if w < min_width or h < min_height:
        return False, f"分辨率过低 ({w}x{h})"

    # 灰度检测：RGB 三通道标准差
    try:
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode == "L":
            # 已经是灰度图，直接通过
            return True, ""

        arr = np.array(img)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            # 取 RGB 三通道（忽略可能的 alpha）
            arr_rgb = arr[:, :, :3]
            std_per_pixel = np.std(arr_rgb, axis=2)
            color_mask = std_per_pixel > 25  # 阈值
            color_ratio = float(np.sum(color_mask)) / (arr_rgb.shape[0] * arr_rgb.shape[1])

            if color_ratio > max_color_ratio:
                return False, f"彩色像素占比过高 ({color_ratio:.1%} > {max_color_ratio:.0%})"
    except Exception:
        # 检测失败则保守保留
        pass

    return True, ""


# ────────────────────────────────────────────────────
#  下载
# ────────────────────────────────────────────────────

def download_image_bytes(
    url: str,
    timeout: int = 20,
    max_retries: int = 2,
) -> Optional[bytes]:
    """下载图片返回字节，失败返回 None"""
    for attempt in range(max_retries + 1):
        try:
            headers = build_headers(referer="https://image.baidu.com/")
            resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
            resp.raise_for_status()

            # 检查 Content-Type
            ct = resp.headers.get("Content-Type", "").lower()
            if ct and "text/html" in ct:
                # 可能是防盗链页面，重试
                if attempt < max_retries:
                    time.sleep(1 + attempt)
                    continue
                return None

            # 限制大小，防止下载超大文件
            content_length = resp.headers.get("Content-Length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > 20:
                    # 超过 20MB 的不下载（连环画扫描一般 < 10MB）
                    return None

            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                chunks.append(chunk)
                total += len(chunk)
                if total > 20 * 1024 * 1024:  # 20MB 硬上限
                    return None

            return b"".join(chunks)

        except requests.RequestException:
            if attempt < max_retries:
                time.sleep(1 + attempt)
                continue
            return None

    return None


# ────────────────────────────────────────────────────
#  主逻辑
# ────────────────────────────────────────────────────

def load_artist_data(json_path: Path) -> list[dict]:
    """加载 scrape.json"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def guess_extension(url: str) -> str:
    """从 URL 推测文件扩展名"""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    for ext in (".png", ".webp", ".gif", ".bmp", ".jpeg"):
        if path_lower.endswith(ext):
            return ext
    return ".jpg"


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|\s]+', '_', name).strip('_')


def scrape_artist(
    artist_data: dict,
    output_dir: Path,
    limit: int,
    min_width: int = DEFAULT_MIN_WIDTH,
    min_height: int = DEFAULT_MIN_HEIGHT,
    max_color_ratio: float = DEFAULT_MAX_COLOR_RATIO,
    dry_run: bool = False,
    source: str = "baidu",
) -> dict:
    """
    为单个画家爬取所有关键词的素材。
    返回统计 dict。
    """
    artist_name = artist_data["artist_name"]
    keywords = artist_data.get("search_keywords_general", [])
    image_names = artist_data.get("image_names", [])
    artist_dir = output_dir / artist_name

    stats = {
        "downloaded": 0,
        "skipped_keyword_filter": 0,
        "skipped_image_filter": 0,
        "failed": 0,
        "already_exist": 0,
    }

    if not keywords:
        tqdm.write(f"  ⚠ {artist_name}: 无搜索关键词，跳过")
        return stats

    tqdm.write(f"\n{'─'*50}")
    tqdm.write(f"画家: {artist_name}  ({len(keywords)} 个关键词)")
    tqdm.write(f"输出: {artist_dir}")

    for idx, keyword in enumerate(keywords):
        # 确定保存文件名前缀
        if idx < len(image_names):
            base_name = sanitize_filename(image_names[idx])
        else:
            safe_kw = re.sub(r'\s+', '_', keyword)[:30]
            base_name = sanitize_filename(f"{artist_name}_{safe_kw}_auto_{idx:02d}")

        tqdm.write(f"\n  [{idx+1}/{len(keywords)}] 搜索: \"{keyword}\"")

        # ── 搜索 ──────────────────────────────
        if source == "baidu":
            results = search_baidu_images(keyword, limit=limit)
        elif source == "sinocomic":
            results = search_lib_sinocomic(keyword, limit=limit)
        elif source == "lhhart":
            results = search_lhhart(keyword, limit=limit)
        else:
            tqdm.write(f"    ⚠ 未知来源: {source}")
            continue

        # ── 关键词粗筛 ────────────────────────
        filtered = []
        for item in results:
            keep, reason = filter_by_keyword(item)
            if keep:
                filtered.append(item)
            else:
                stats["skipped_keyword_filter"] += 1

        # 优先关键词排序
        filtered = sort_by_preference(filtered)
        tqdm.write(f"    搜索: {len(results)} 结果 → 关键词过滤后: {len(filtered)}")

        # ── 下载 ──────────────────────────────
        download_count = 0
        attempt_count = 0

        for item in filtered:
            if download_count >= limit:
                break

            url = item["url"]
            ext = guess_extension(url)
            save_name = f"{base_name}_{download_count + 1:02d}{ext}" if limit > 1 else f"{base_name}{ext}"
            save_path = artist_dir / save_name

            # 跳过已存在
            if save_path.exists():
                tqdm.write(f"    ⏭ 已存在: {save_name}")
                download_count += 1
                stats["already_exist"] += 1
                continue

            attempt_count += 1

            if dry_run:
                tqdm.write(f"    [dry-run] {url[:80]}... → {save_name}")
                download_count += 1
                stats["downloaded"] += 1
                continue

            # 下载
            tqdm.write(f"    ⬇ {url[:70]}...", end=" ")
            image_bytes = download_image_bytes(url)

            if image_bytes is None:
                tqdm.write("✗ 下载失败")
                stats["failed"] += 1
                continue

            # 图像分析
            keep_img, reason = filter_by_image(
                image_bytes,
                min_width=min_width,
                min_height=min_height,
                max_color_ratio=max_color_ratio,
            )
            if not keep_img:
                tqdm.write(f"✗ {reason}")
                stats["skipped_image_filter"] += 1
                continue

            # 保存
            artist_dir.mkdir(parents=True, exist_ok=True)
            try:
                with open(save_path, "wb") as f:
                    f.write(image_bytes)
                tqdm.write("✓")
                download_count += 1
                stats["downloaded"] += 1
            except OSError as e:
                tqdm.write(f"✗ 写入失败: {e}")
                stats["failed"] += 1

            # 下载间隔
            time.sleep(random.uniform(*DEFAULT_REQUEST_INTERVAL))

        # 关键词间间隔
        if not dry_run and idx < len(keywords) - 1:
            time.sleep(random.uniform(*DEFAULT_KEYWORD_INTERVAL))

    # 单画家小结
    tqdm.write(
        f"  ── {artist_name} 完成: "
        f"下载 {stats['downloaded']}, "
        f"已存在 {stats['already_exist']}, "
        f"关键词过滤 {stats['skipped_keyword_filter']}, "
        f"图像过滤 {stats['skipped_image_filter']}, "
        f"失败 {stats['failed']}"
    )
    return stats


# ────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="连环画素材批量爬取 — 百度图片通用兜底",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/scrape.py                        # 全部画家，每关键词 5 张
  python scripts/scrape.py --limit 10             # 每关键词最多 10 张
  python scripts/scrape.py --artist 刘继卣         # 只爬指定画家
  python scripts/scrape.py --artist 刘继卣 --limit 20
  python scripts/scrape.py --output ./my_images   # 指定输出目录
  python scripts/scrape.py --dry-run              # 只搜索不下载，查看 URL
  python scripts/scrape.py --max-color 0.10       # 更严格的灰度要求
        """,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"JSON 数据文件路径（默认: {DEFAULT_INPUT}）",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"输出目录（默认: {DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"每个关键词最多下载张数（默认: {DEFAULT_LIMIT}）",
    )
    parser.add_argument(
        "--artist", "-a",
        type=str,
        default=None,
        help="只爬取指定画家（模糊匹配，如 '刘继卣' 或 '刘'）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只搜索不下载，打印 URL 和保存路径",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="baidu",
        choices=["baidu", "sinocomic", "lhhart"],
        help="搜索来源（默认: baidu；sinocomic/lhhart 为桩接口）",
    )
    parser.add_argument(
        "--min-width",
        type=int,
        default=DEFAULT_MIN_WIDTH,
        help=f"最低宽度 px（默认: {DEFAULT_MIN_WIDTH}）",
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=DEFAULT_MIN_HEIGHT,
        help=f"最低高度 px（默认: {DEFAULT_MIN_HEIGHT}）",
    )
    parser.add_argument(
        "--max-color",
        type=float,
        default=DEFAULT_MAX_COLOR_RATIO,
        help=f"最大彩色像素占比（默认: {DEFAULT_MAX_COLOR_RATIO}，越小越严格）",
    )

    args = parser.parse_args()

    # 检查输入文件
    if not args.input.exists():
        print(f"✗ 输入文件不存在: {args.input}")
        sys.exit(1)

    # 加载数据
    data = load_artist_data(args.input)
    print(f"加载 {len(data)} 位画家的搜索配置")

    # 过滤画家
    if args.artist:
        data = [d for d in data if args.artist in d.get("artist_name", "")]
        if not data:
            print(f"✗ 未找到匹配 '{args.artist}' 的画家")
            sys.exit(1)
        print(f"筛选到 {len(data)} 位匹配画家")

    print(f"输出目录:     {args.output.resolve()}")
    print(f"每关键词上限: {args.limit} 张")
    print(f"搜索来源:     {args.source}")
    print(f"灰度阈值:     彩色像素 ≤ {args.max_color:.0%}")
    print(f"最低分辨率:    {args.min_width}×{args.min_height}")
    print(f"模式:         {'dry-run (仅搜索)' if args.dry_run else '正常下载'}")

    if args.source in ("sinocomic", "lhhart"):
        print(f"⚠ {args.source} 搜索为桩接口，当前返回空结果")

    # 汇总统计
    total = {"downloaded": 0, "skipped_keyword_filter": 0,
             "skipped_image_filter": 0, "failed": 0, "already_exist": 0}

    iterator = tqdm(data, desc="画家进度", unit="位") if len(data) > 1 else data
    for artist_data in iterator:
        stats = scrape_artist(
            artist_data,
            output_dir=args.output,
            limit=args.limit,
            min_width=args.min_width,
            min_height=args.min_height,
            max_color_ratio=args.max_color,
            dry_run=args.dry_run,
            source=args.source,
        )
        for k in total:
            total[k] += stats.get(k, 0)

    # 总结
    print(f"\n{'='*50}")
    print("全部完成！")
    print(f"  下载成功:   {total['downloaded']}")
    print(f"  已存在跳过: {total['already_exist']}")
    print(f"  关键词过滤: {total['skipped_keyword_filter']}")
    print(f"  图像过滤:   {total['skipped_image_filter']}")
    print(f"  下载失败:   {total['failed']}")
    if not args.dry_run and total["downloaded"] > 0:
        print(f"  文件位于:   {args.output.resolve()}")


if __name__ == "__main__":
    main()
