#!/usr/bin/env python3
"""R2 Comic Gallery — 本地画廊服务器，浏览 R2 bucket 中的连环画图片"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, quote

import boto3
from botocore.config import Config

# ─── 从 .env 读取配置 ─────────────────────────────
from dotenv import load_dotenv

load_dotenv()

R2_CONFIG = {
    "endpoint": os.getenv("S3_API", "").rsplit("/", 1)[0],  # https://<account>.r2.cloudflarestorage.com
    "bucket": os.getenv("S3_API", "").rsplit("/", 1)[-1] if "/" in os.getenv("S3_API", "") else "comic",
    "public_url": os.getenv("R2_URL", ""),
    "access_key_id": os.getenv("R2_ACCESS_KEY_ID", ""),
    "secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", ""),
}

if not all(R2_CONFIG.values()):
    print("❌ 请在 .env 中配置 R2 相关变量 (S3_API, R2_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)")
    sys.exit(1)

s3 = boto3.client(
    "s3",
    endpoint_url=R2_CONFIG["endpoint"],
    aws_access_key_id=R2_CONFIG["access_key_id"],
    aws_secret_access_key=R2_CONFIG["secret_access_key"],
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

# ─── HTML 画廊模板 ────────────────────────────────
GALLERY_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎨 白描连环画 · R2 Gallery</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "Noto Sans SC", system-ui, sans-serif; background: #1a1a1a; color: #eee; }
  header { background: linear-gradient(135deg, #2a1a0e, #1a1a1a); padding: 24px 32px; border-bottom: 2px solid #8b7355; }
  header h1 { font-size: 24px; letter-spacing: 2px; }
  header p { color: #999; margin-top: 4px; font-size: 14px; }
  header .stats { float: right; color: #8b7355; font-size: 14px; margin-top: 8px; }
  .toolbar { padding: 12px 32px; background: #222; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid #333; }
  .toolbar input { flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid #444; border-radius: 6px; background: #111; color: #eee; font-size: 14px; }
  .toolbar select { padding: 8px 12px; border: 1px solid #444; border-radius: 6px; background: #111; color: #eee; font-size: 14px; }
  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; padding: 24px 32px; }
  .card { background: #222; border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: transform .15s, box-shadow .15s; cursor: pointer; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.5); border-color: #8b7355; }
  .card img { width: 100%; height: 280px; object-fit: cover; display: block; background: #111; }
  .card .info { padding: 12px; }
  .card .title { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .card .sub { color: #888; font-size: 12px; margin-top: 4px; }
  .lightbox { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.92); z-index: 1000; justify-content: center; align-items: center; flex-direction: column; }
  .lightbox.active { display: flex; }
  .lightbox img { max-width: 90vw; max-height: 85vh; border-radius: 4px; }
  .lightbox .lb-title { color: #ccc; margin-top: 12px; font-size: 14px; }
  .lightbox .lb-close { position: absolute; top: 20px; right: 28px; font-size: 28px; color: #888; cursor: pointer; }
  .lightbox .lb-close:hover { color: #fff; }
  .empty { grid-column: 1/-1; text-align: center; padding: 80px; color: #666; font-size: 18px; }
  .loading { text-align: center; padding: 80px; color: #666; }
  @media (max-width: 600px) {
    .gallery { grid-template-columns: 1fr 1fr; padding: 12px; gap: 8px; }
    .card img { height: 160px; }
    header { padding: 16px; }
    header h1 { font-size: 18px; }
    .toolbar { padding: 8px 16px; }
  }
</style>
</head>
<body>
<header>
  <h1>🎨 白描连环画 · R2 Gallery</h1>
  <p>中国传统白描连环画生成器 — Cloudflare R2 存储</p>
  <span class="stats" id="stats">加载中...</span>
</header>
<div class="toolbar">
  <input type="text" id="search" placeholder="🔍 搜索文件名..." oninput="filter()">
  <select id="sort" onchange="render()">
    <option value="newest">最新优先</option>
    <option value="oldest">最早优先</option>
    <option value="name">按名称排序</option>
  </select>
</div>
<div class="gallery" id="gallery"><div class="loading">☁️ 正在从 R2 加载...</div></div>
<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <span class="lb-close" onclick="closeLightbox()">&times;</span>
  <img id="lb-img" src="" alt="">
  <div class="lb-title" id="lb-title"></div>
</div>
<script>
const PUBLIC_URL = "__PUBLIC_URL__";
let allFiles = [];
let filteredFiles = [];

async function loadFiles() {
  try {
    const res = await fetch("/api/list");
    const data = await res.json();
    if (!data.files) {
      document.getElementById("gallery").innerHTML = '<div class="empty">❌ ' + (data.error || 'R2 接口返回异常') + '</div>';
      return;
    }
    allFiles = data.files.sort((a,b) => new Date(b.lastModified) - new Date(a.lastModified));
    document.getElementById("stats").textContent = `共 ${allFiles.length} 张`;
    render();
  } catch(e) {
    document.getElementById("gallery").innerHTML = '<div class="empty">❌ 加载失败: ' + e.message + '</div>';
  }
}

function render() {
  const q = document.getElementById("search").value.toLowerCase();
  const sort = document.getElementById("sort").value;
  filteredFiles = allFiles.filter(f => f.key.toLowerCase().includes(q));
  if (sort === "newest") filteredFiles.sort((a,b) => new Date(b.lastModified) - new Date(a.lastModified));
  else if (sort === "oldest") filteredFiles.sort((a,b) => new Date(a.lastModified) - new Date(b.lastModified));
  else if (sort === "name") filteredFiles.sort((a,b) => a.key.localeCompare(b.key));

  const el = document.getElementById("gallery");
  el.innerHTML = filteredFiles.map(f => `
    <div class="card" onclick="openLightbox('${PUBLIC_URL}/${f.key}', '${f.key}')">
      <img src="${PUBLIC_URL}/${f.key}" loading="lazy" onerror="this.style.display='none'">
      <div class="info">
        <div class="title">${f.key.split('/').pop()}</div>
        <div class="sub">${new Date(f.lastModified).toLocaleString()} · ${(f.size/1024).toFixed(0)}KB</div>
      </div>
    </div>
  `).join("");
}

function filter() { render(); }

function openLightbox(url, title) {
  document.getElementById("lb-img").src = url;
  document.getElementById("lb-title").textContent = title;
  document.getElementById("lightbox").classList.add("active");
}

function closeLightbox(e) {
  if (!e || e.target === document.getElementById("lightbox")) {
    document.getElementById("lightbox").classList.remove("active");
  }
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeLightbox();
});

loadFiles();
</script>
</body>
</html>"""


class GalleryHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = GALLERY_HTML.replace("__PUBLIC_URL__", R2_CONFIG["public_url"])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif parsed.path == "/api/list":
            self._list_objects()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def _list_objects(self):
        try:
            resp = s3.list_objects_v2(Bucket=R2_CONFIG["bucket"])
            files = []
            if "Contents" in resp:
                for obj in resp["Contents"]:
                    if obj["Key"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                        files.append({
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "lastModified": obj["LastModified"].isoformat(),
                        })
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"files": files}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 静默日志


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), GalleryHandler)
    print(f"🎨 R2 Comic Gallery → http://localhost:{port}")
    print(f"   ☁️  R2 Bucket: {R2_CONFIG['bucket']}")
    print(f"   📦  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 已停止")
        server.server_close()


if __name__ == "__main__":
    main()
