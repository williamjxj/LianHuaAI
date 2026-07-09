#!/usr/bin/env python3
"""
连环画素材批量爬取脚本
======================

读取 scripts/scrape.json，搜索白描连环画内页素材，输出到 assets/paper_textures/，
用作 RunningHub 白描图像生成器的风格参考图。

支持三种搜索后端:
  duckduckgo  — DuckDuckGo Images（默认，全球可用，无需 API Key）
  bing        — Bing Image Search（全球可用，通过页面解析）
  baidu       — 百度图片（仅在中国大陆网络环境下可用）

过滤管线:
  搜索 → 关键词粗筛（丢弃AI图/海报/油画）→ 封面过滤（丢弃封面/封底）
       → 下载 → 图像分析（宽高比封面检测 + 顶部文字栏检测 + 灰度检测）
       → 保存到 assets/paper_textures/{画家名}/

用法:
    python scripts/scrape.py                          # 全部画家，每关键词 5 张
    python scripts/scrape.py --limit 10               # 每关键词最多 10 张
    python scripts/scrape.py --artist 刘继卣           # 只爬指定画家
    python scripts/scrape.py --source bing            # 使用 Bing 搜索
    python scripts/scrape.py --source baidu           # 使用百度搜索
    python scripts/scrape.py --output ./my_images     # 指定输出目录
    python scripts/scrape.py --dry-run                # 只搜索不下载
"""

import argparse
import html
import json
import os
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

import numpy as np
import requests
from PIL import Image
from tqdm import tqdm

# ─── 路径常量 ──────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = SCRIPT_DIR / "scrape.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "paper_textures"

# ─── 默认参数 ──────────────────────────────────────

DEFAULT_LIMIT = 5
DEFAULT_MIN_WIDTH = 200
DEFAULT_MIN_HEIGHT = 200
DEFAULT_MAX_COLOR_RATIO = 0.15       # 彩色像素占比超过此值则丢弃
DEFAULT_MIN_FILE_SIZE_KB = 5         # 小于此值的文件视为无效
DEFAULT_REQUEST_INTERVAL = (1.0, 2.5)
DEFAULT_KEYWORD_INTERVAL = (1.5, 3.0)
DEFAULT_SEARCH_TIMEOUT = 20

# ─── User-Agent 池 ────────────────────────────────

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

BLOCK_KEYWORDS = [
    "现代插画", "AI绘图", "ai绘画", "ai生成", "彩色重绘", "海报", "油画",
    "短视频截图", "书法单字", "人物照片", "cos", "cosplay",
    "color", "colored", "painting", "poster", "oil",
    "anime", "CG", "3D", "卡通", "动漫", "二次元",
    "表情包", "头像", "壁纸", "手机壁纸",
]

PREFER_KEYWORDS = [
    "线稿", "白描", "原稿", "连环画", "小人书", "黑白", "线描",
    "内页", "扫描", "工笔", "手稿", "墨线", "插页", "画稿",
]

# ─── 封面/内页过滤 ────────────────────────────────
# 这些图用作 RunningHub 白描生成器的风格参考，需要干净的单幅内页
# 封面通常有标题大字、装饰边框、出版社信息，不适合做风格参考

BLOCK_COVER_KEYWORDS = [
    "封面", "cover", "封底", "扉页", "书皮", "书盒", "函套",
    "版权页", "目录页", "连环画封面", "书籍封面",
]

PREFER_INTERIOR_KEYWORDS = [
    "内页", "正文", "插页", "单幅", "全幅", "画稿", "原稿扫描",
    "内页扫描", "正文页", "单页", "画幅",
]


# ────────────────────────────────────────────────────
#  HTTP 工具
# ────────────────────────────────────────────────────

def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def build_headers(referer: str = "") -> dict:
    h = {
        "User-Agent": get_random_ua(),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if referer:
        h["Referer"] = referer
    return h


def safe_request(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_SEARCH_TIMEOUT,
    max_retries: int = 2,
    stream: bool = False,
) -> Optional[requests.Response]:
    """带重试的 HTTP GET"""
    if headers is None:
        headers = build_headers()
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                url, params=params, headers=headers,
                timeout=timeout, stream=stream,
            )
            resp.raise_for_status()
            return resp
        except requests.ConnectTimeout:
            if attempt < max_retries:
                time.sleep(2 + attempt)
                continue
            raise
        except requests.ReadTimeout:
            if attempt < max_retries:
                time.sleep(2 + attempt)
                continue
            raise
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep(1 + attempt)
                continue
            raise
    return None


# ────────────────────────────────────────────────────
#  DuckDuckGo 搜索（默认）
# ────────────────────────────────────────────────────

def search_duckduckgo_images(
    query: str,
    limit: int = 5,
    timeout: int = DEFAULT_SEARCH_TIMEOUT,
) -> list[dict]:
    """
    DuckDuckGo Images API（无 Key，全球可用）。
    使用 duckduckgo_search 库；若未安装则回退到直接 HTTP 请求。
    """
    # 优先使用 ddgs / duckduckgo_search 库
    DDGS = None
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            pass

    if DDGS is not None:
        results: list[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.images(
                    keywords=query,
                    max_results=limit * 3,
                    region="cn-zh",
                ):
                    results.append({
                        "url": r.get("image", ""),
                        "title": r.get("title", ""),
                        "width": r.get("width", 0) or 0,
                        "height": r.get("height", 0) or 0,
                    })
            if results:
                return results
        except Exception:
            pass

    # 回退：直接 HTTP 请求 DuckDuckGo 图片搜索 HTML
    return _search_duckduckgo_direct(query, limit, timeout)


def _search_duckduckgo_direct(
    query: str, limit: int, timeout: int
) -> list[dict]:
    """直接解析 DuckDuckGo 图片搜索页面（回退方案）"""
    results: list[dict] = []
    url = "https://duckduckgo.com/"
    params = {
        "q": query,
        "iax": "images",
        "ia": "images",
    }
    try:
        resp = safe_request(url, params=params, timeout=timeout)
        if resp is None:
            return results
    except requests.RequestException:
        return results

    # 从 vqd token 获取
    vqd_match = re.search(r'vqd=["\']([^"\']+)["\']', resp.text)
    if not vqd_match:
        return results
    vqd = vqd_match.group(1)

    # 请求图片 API
    api_url = "https://duckduckgo.com/i.js"
    api_params = {
        "l": "cn-zh",
        "o": "json",
        "q": query,
        "vqd": vqd,
        "f": ",,,,,",
        "p": "1",
    }
    try:
        api_resp = safe_request(api_url, params=api_params, timeout=timeout)
        if api_resp is None:
            return results
        data = api_resp.json()
        for r in data.get("results", [])[: limit * 3]:
            img_url = r.get("image", "") or r.get("thumbnail", "")
            if img_url:
                results.append({
                    "url": img_url,
                    "title": r.get("title", ""),
                    "width": int(r.get("width", 0) or 0),
                    "height": int(r.get("height", 0) or 0),
                })
    except Exception:
        pass

    return results


# ────────────────────────────────────────────────────
#  Bing 搜索
# ────────────────────────────────────────────────────

def search_bing_images(
    query: str,
    limit: int = 5,
    timeout: int = DEFAULT_SEARCH_TIMEOUT,
) -> list[dict]:
    """
    Bing Image Search（全球可用，页面解析）。
    从 https://www.bing.com/images/search 解析图片 URL。
    """
    results: list[dict] = []
    headers = build_headers(referer="https://www.bing.com/")

    collected = 0
    first = 0

    while collected < limit * 3:
        params = {
            "q": query,
            "first": str(first),
            "FORM": "HDRSC2",
        }
        try:
            resp = safe_request(
                "https://www.bing.com/images/search",
                params=params, headers=headers, timeout=timeout,
            )
            if resp is None:
                break
        except requests.RequestException:
            break

        # Bing 图片数据在 <a class="iusc"> 的 m 属性中（JSON 内嵌）
        # 匹配模式: m='{...}' 或 m="{...}"
        matches = re.findall(r"m='({[^']*?})'", resp.text)
        matches += re.findall(r'm="({[^"]*?})"', resp.text)

        if not matches and first == 0:
            # 部分页面用另一种格式: <img class="mimg" src="...">
            alt_matches = re.findall(
                r'<img[^>]+class="mimg"[^>]+src="([^"]+)"',
                resp.text,
            )
            for src in alt_matches:
                if collected >= limit * 3:
                    break
                if src.startswith("http"):
                    results.append({
                        "url": src,
                        "title": query,
                        "width": 0,
                        "height": 0,
                    })
                    collected += 1
            if alt_matches:
                break

        page_had_results = False
        for m_str in matches:
            if collected >= limit * 3:
                break
            try:
                # HTML 实体解码
                m_str = html.unescape(m_str)
                data = json.loads(m_str)
                img_url = data.get("murl", "") or data.get("turl", "")
                if img_url and img_url.startswith("http"):
                    results.append({
                        "url": img_url,
                        "title": data.get("desc", "") or data.get("t", query),
                        "width": int(data.get("w", 0) or 0),
                        "height": int(data.get("h", 0) or 0),
                    })
                    collected += 1
                    page_had_results = True
            except (json.JSONDecodeError, KeyError):
                continue

        if not page_had_results:
            break

        first += len(matches)
        if first >= 150:  # Bing 通常最多 150 条
            break
        time.sleep(random.uniform(*DEFAULT_REQUEST_INTERVAL))

    return results


# ────────────────────────────────────────────────────
#  百度图片搜索（仅中国大陆可用）
# ────────────────────────────────────────────────────

def search_baidu_images(
    query: str,
    limit: int = 5,
    timeout: int = DEFAULT_SEARCH_TIMEOUT,
) -> list[dict]:
    """
    百度图片 acjson 接口搜索。
    注意：image.baidu.com 在中国大陆以外地区可能无法访问。
    """
    results: list[dict] = []
    pn = 0
    max_pages = max((limit * 2) // 30 + 2, 3)

    session = requests.Session()
    session.headers.update(build_headers(referer="https://image.baidu.com/"))

    # 先访问首页获取 cookie
    try:
        session.get("https://image.baidu.com/", timeout=10)
    except requests.ConnectTimeout:
        print("  ⚠ 无法连接 image.baidu.com（可能不在中国大陆网络环境）")
        print("    请换用 --source duckduckgo 或 --source bing")
        return []
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
                "https://image.baidu.com/search/acjson",
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            text = resp.text
            if text.startswith("try{") or "(" in text[:20]:
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    text = match.group()
            data = json.loads(text)
        except json.JSONDecodeError:
            pn += 30
            continue
        except requests.ConnectTimeout:
            print(f"  ⚠ 百度连接超时，建议换用 --source duckduckgo")
            break
        except requests.RequestException as e:
            print(f"  ⚠ 搜索失败 [{query}]: {e}")
            break

        entries = data.get("data", [])
        if not entries:
            break

        for entry in entries:
            url = (
                entry.get("objURL", "")
                or entry.get("thumbURL", "")
                or entry.get("middleURL", "")
            )
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
            break
        time.sleep(random.uniform(*DEFAULT_REQUEST_INTERVAL))

    return results


# ────────────────────────────────────────────────────
#  桩接口
# ────────────────────────────────────────────────────

def search_lib_sinocomic(query: str, limit: int = 5) -> list[dict]:
    """[桩] 中国连环画数字图书馆"""
    return []


def search_lhhart(query: str, limit: int = 5) -> list[dict]:
    """[桩] 连艺网"""
    return []


# ────────────────────────────────────────────────────
#  搜索调度
# ────────────────────────────────────────────────────

SEARCH_BACKENDS = {
    "duckduckgo": search_duckduckgo_images,
    "bing":       search_bing_images,
    "baidu":      search_baidu_images,
    "sinocomic":  search_lib_sinocomic,
    "lhhart":     search_lhhart,
}


# ────────────────────────────────────────────────────
#  关键词过滤（粗筛）
# ────────────────────────────────────────────────────

def filter_by_keyword(item: dict) -> tuple[bool, str]:
    """URL + 标题关键词粗筛（含封面过滤）。返回 (保留?, 原因)"""
    url = item.get("url", "")
    title = item.get("title", "")
    combined = f"{url} {title}".lower()
    for kw in BLOCK_KEYWORDS:
        if kw.lower() in combined:
            return False, f"匹配丢弃词: {kw}"
    for kw in BLOCK_COVER_KEYWORDS:
        if kw.lower() in combined:
            return False, f"匹配封面词: {kw}"
    return True, ""


def has_prefer_keyword(item: dict) -> bool:
    """是否包含优先关键词（含内页优先）"""
    url = item.get("url", "")
    title = item.get("title", "")
    combined = f"{url} {title}".lower()
    return any(kw.lower() in combined for kw in (PREFER_KEYWORDS + PREFER_INTERIOR_KEYWORDS))


def sort_by_preference(results: list[dict]) -> list[dict]:
    """优先关键词排前面"""
    preferred = [r for r in results if has_prefer_keyword(r)]
    others = [r for r in results if not has_prefer_keyword(r)]
    return preferred + others


# ────────────────────────────────────────────────────
#  图像分析过滤（细筛）
# ────────────────────────────────────────────────────

def is_likely_cover(img: Image.Image) -> tuple[bool, str]:
    """
    图像层面的封面检测（不做 OCR，用视觉特征）：
    1. 宽高比：封面通常接近正方形 (0.75–1.3)，内页更扁长 (~0.6–0.75)
    2. 顶部文字栏：封面顶部通常有标题/出版社文字条（高对比度横带）
    返回 (是否疑似封面, 原因)
    """
    w, h = img.size
    aspect = w / h if h > 0 else 0

    # 正方形倾向检测
    if 0.80 <= aspect <= 1.30:
        return True, f"疑似封面（宽高比 {aspect:.2f}，接近正方形）"

    # 顶部文字栏检测：分析顶部 12% 区域 vs 中间区域
    if img.mode in ("RGBA", "P", "LA"):
        img_rgb = img.convert("RGB")
    elif img.mode == "L":
        img_rgb = img.convert("RGB")
    else:
        img_rgb = img

    arr = np.array(img_rgb)
    top_band_h = max(int(h * 0.12), 10)
    mid_start = int(h * 0.25)
    mid_end = int(h * 0.55)

    top_band = arr[:top_band_h, :, :]
    mid_band = arr[mid_start:mid_end, :, :]

    if top_band.size > 0 and mid_band.size > 0:
        # 比较顶部和中间区域的亮度标准差
        top_std = float(np.std(top_band))
        mid_std = float(np.std(mid_band))
        # 封面顶部文字栏：顶部标准差显著高于中部（有文字 vs 画面）
        if mid_std > 0 and top_std / mid_std > 1.8:
            return True, f"疑似封面（顶部文字栏，top_std/mid_std={top_std/mid_std:.1f}）"

    return False, ""


def filter_by_image(
    image_bytes: bytes,
    min_width: int = DEFAULT_MIN_WIDTH,
    min_height: int = DEFAULT_MIN_HEIGHT,
    max_color_ratio: float = DEFAULT_MAX_COLOR_RATIO,
    min_file_size_kb: float = DEFAULT_MIN_FILE_SIZE_KB,
) -> tuple[bool, str]:
    """
    下载后图像分析:
    1. 文件大小 ≥ min_file_size_kb KB
    2. 分辨率 ≥ min_width × min_height
    3. 彩色像素占比 ≤ max_color_ratio
    """
    size_kb = len(image_bytes) / 1024
    if size_kb < min_file_size_kb:
        return False, f"文件过小 ({size_kb:.1f}KB)"

    try:
        img = Image.open(BytesIO(image_bytes))
    except Exception as e:
        return False, f"无法解析图片: {e}"

    w, h = img.size
    if w < min_width or h < min_height:
        return False, f"分辨率过低 ({w}x{h})"

    # 封面检测
    cover, cover_reason = is_likely_cover(img)
    if cover:
        return False, cover_reason

    # 灰度检测
    try:
        if img.mode == "L":
            return True, ""
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        arr = np.array(img)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            arr_rgb = arr[:, :, :3]
            std_per_pixel = np.std(arr_rgb, axis=2)
            color_ratio = float(np.sum(std_per_pixel > 25)) / (
                arr_rgb.shape[0] * arr_rgb.shape[1]
            )
            if color_ratio > max_color_ratio:
                return False, f"彩色像素占比过高 ({color_ratio:.1%} > {max_color_ratio:.0%})"
    except Exception:
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
            resp = requests.get(
                url,
                headers=build_headers(),
                timeout=timeout,
                stream=True,
            )
            resp.raise_for_status()

            ct = resp.headers.get("Content-Type", "").lower()
            if ct and "text/html" in ct:
                if attempt < max_retries:
                    time.sleep(1 + attempt)
                    continue
                return None

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > 20 * 1024 * 1024:
                return None

            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                chunks.append(chunk)
                total += len(chunk)
                if total > 20 * 1024 * 1024:
                    return None
            return b"".join(chunks)

        except requests.RequestException:
            if attempt < max_retries:
                time.sleep(1 + attempt)
                continue
            return None
    return None


# ────────────────────────────────────────────────────
#  工具函数
# ────────────────────────────────────────────────────

def load_artist_data(json_path: Path) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def guess_extension(url: str) -> str:
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    for ext in (".png", ".webp", ".gif", ".bmp", ".jpeg"):
        if path_lower.endswith(ext):
            return ext
    return ".jpg"


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', '_', name).strip('_')


# ────────────────────────────────────────────────────
#  单画家管线
# ────────────────────────────────────────────────────

def scrape_artist(
    artist_data: dict,
    output_dir: Path,
    limit: int,
    min_width: int = DEFAULT_MIN_WIDTH,
    min_height: int = DEFAULT_MIN_HEIGHT,
    max_color_ratio: float = DEFAULT_MAX_COLOR_RATIO,
    dry_run: bool = False,
    source: str = "duckduckgo",
) -> dict:
    """为单个画家爬取所有关键词的素材，返回统计 dict。"""
    artist_name = artist_data["artist_name"]
    keywords = artist_data.get("search_keywords_general", [])
    image_names = artist_data.get("image_names", [])
    artist_dir = output_dir / artist_name

    stats = {
        "downloaded": 0, "skipped_keyword_filter": 0,
        "skipped_image_filter": 0, "failed": 0, "already_exist": 0,
    }

    if not keywords:
        tqdm.write(f"  ⚠ {artist_name}: 无搜索关键词，跳过")
        return stats

    search_fn = SEARCH_BACKENDS.get(source)
    if search_fn is None:
        tqdm.write(f"  ✗ 未知搜索来源: {source}")
        return stats

    tqdm.write(f"\n{'─'*50}")
    tqdm.write(f"画家: {artist_name}  ({len(keywords)} 个关键词)")
    tqdm.write(f"输出: {artist_dir}")

    for idx, keyword in enumerate(keywords):
        # 文件名前缀
        if idx < len(image_names):
            base_name = sanitize_filename(image_names[idx])
        else:
            safe_kw = re.sub(r'\s+', '_', keyword)[:30]
            base_name = sanitize_filename(f"{artist_name}_{safe_kw}_auto_{idx:02d}")

        tqdm.write(f"\n  [{idx+1}/{len(keywords)}] 搜索: \"{keyword}\"")

        # ── 搜索 ──
        try:
            results = search_fn(keyword, limit=limit)
        except Exception as e:
            tqdm.write(f"    ✗ 搜索异常: {e}")
            continue

        # ── 关键词粗筛 ──
        filtered: list[dict] = []
        for item in results:
            keep, _reason = filter_by_keyword(item)
            if keep:
                filtered.append(item)
            else:
                stats["skipped_keyword_filter"] += 1
        filtered = sort_by_preference(filtered)
        tqdm.write(f"    搜索: {len(results)} 结果 → 关键词过滤后: {len(filtered)}")

        # ── 下载 ──
        download_count = 0
        for item in filtered:
            if download_count >= limit:
                break

            url = item["url"]
            ext = guess_extension(url)
            save_name = (
                f"{base_name}_{download_count + 1:02d}{ext}"
                if limit > 1 else f"{base_name}{ext}"
            )
            save_path = artist_dir / save_name

            if save_path.exists():
                tqdm.write(f"    ⏭ 已存在: {save_name}")
                download_count += 1
                stats["already_exist"] += 1
                continue

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
                min_width=min_width, min_height=min_height,
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

            time.sleep(random.uniform(*DEFAULT_REQUEST_INTERVAL))

        if not dry_run and idx < len(keywords) - 1:
            time.sleep(random.uniform(*DEFAULT_KEYWORD_INTERVAL))

    tqdm.write(
        f"  ── {artist_name} 完成: "
        f"下载 {stats['downloaded']}, 已存在 {stats['already_exist']}, "
        f"关键词过滤 {stats['skipped_keyword_filter']}, "
        f"图像过滤 {stats['skipped_image_filter']}, 失败 {stats['failed']}"
    )
    return stats


# ────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="连环画素材批量爬取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/scrape.py                        # 全部画家，输出到 assets/paper_textures/
  python scripts/scrape.py --source bing          # 使用 Bing 搜索
  python scripts/scrape.py --source baidu         # 使用百度搜索（需中国大陆网络）
  python scripts/scrape.py --artist 刘继卣         # 只爬指定画家
  python scripts/scrape.py --artist 刘继卣 -l 10   # 每关键词 10 张
  python scripts/scrape.py --dry-run              # 只搜索不下载
        """,
    )
    parser.add_argument(
        "--input", "-i", type=Path, default=DEFAULT_INPUT,
        help=f"JSON 数据文件路径（默认: {DEFAULT_INPUT}）",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=DEFAULT_OUTPUT,
        help=f"输出目录（默认: {DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=DEFAULT_LIMIT,
        help=f"每个关键词最多下载张数（默认: {DEFAULT_LIMIT}）",
    )
    parser.add_argument(
        "--artist", "-a", type=str, default=None,
        help="只爬取指定画家（模糊匹配）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只搜索不下载",
    )
    parser.add_argument(
        "--source", type=str, default="duckduckgo",
        choices=["duckduckgo", "bing", "baidu", "sinocomic", "lhhart"],
        help="搜索后端（默认: duckduckgo）",
    )
    parser.add_argument(
        "--min-width", type=int, default=DEFAULT_MIN_WIDTH,
        help=f"最低宽度 px（默认: {DEFAULT_MIN_WIDTH}）",
    )
    parser.add_argument(
        "--min-height", type=int, default=DEFAULT_MIN_HEIGHT,
        help=f"最低高度 px（默认: {DEFAULT_MIN_HEIGHT}）",
    )
    parser.add_argument(
        "--max-color", type=float, default=DEFAULT_MAX_COLOR_RATIO,
        help=f"最大彩色像素占比（默认: {DEFAULT_MAX_COLOR_RATIO}）",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"✗ 输入文件不存在: {args.input}")
        sys.exit(1)

    data = load_artist_data(args.input)
    print(f"加载 {len(data)} 位画家的搜索配置")

    if args.artist:
        data = [d for d in data if args.artist in d.get("artist_name", "")]
        if not data:
            print(f"✗ 未找到匹配 '{args.artist}' 的画家")
            sys.exit(1)
        print(f"筛选到 {len(data)} 位匹配画家")

    print(f"输出目录:     {args.output.resolve()}")
    print(f"搜索后端:     {args.source}")
    print(f"每关键词上限: {args.limit} 张")
    print(f"灰度阈值:     彩色像素 ≤ {args.max_color:.0%}")
    print(f"最低分辨率:    {args.min_width}×{args.min_height}")
    print(f"模式:         {'dry-run (仅搜索)' if args.dry_run else '正常下载'}")

    if args.source in ("sinocomic", "lhhart"):
        print(f"⚠ {args.source} 为桩接口，当前返回空结果")
    if args.source == "baidu":
        print("⚠ 百度图片仅在中国大陆网络环境下可用，超时请换用 duckduckgo/bing")

    total = {"downloaded": 0, "skipped_keyword_filter": 0,
             "skipped_image_filter": 0, "failed": 0, "already_exist": 0}

    iterator = tqdm(data, desc="画家进度", unit="位") if len(data) > 1 else data
    for artist_data in iterator:
        stats = scrape_artist(
            artist_data, output_dir=args.output, limit=args.limit,
            min_width=args.min_width, min_height=args.min_height,
            max_color_ratio=args.max_color,
            dry_run=args.dry_run, source=args.source,
        )
        for k in total:
            total[k] += stats.get(k, 0)

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
