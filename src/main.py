#!/usr/bin/env python3
"""
中国传统白描连环画生成器 — 主入口

批量循环随机生成单幅中国传统白描连环画作品，配套历史故事解说文案。

使用方法:
    python -m src.main --batch 5          # 生成5幅
    python -m src.main --dry-run          # 测试运行（不调用API）
    python -m src.main --batch 3 --output ./my_outputs
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import io
import os

from PIL import Image
import requests

from src.config import PROJECT_ROOT, load_config
from src.image_engine.post_process import PostProcessor
from src.image_engine.prompt_builder import build_image_prompt, build_negative_prompt
from src.story_engine.generator import HISTORY_BOARDS, StoryGenerator
from src.story_engine.narrator import Narrator
from src.story_engine.prompts import select_narrator_style

# 确保 src 可导入
sys.path.insert(0, str(PROJECT_ROOT))


class ComicPipeline:
    """连环画生成管线"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config = load_config(config_path)
        self.config_path = config_path

        # 初始化各模块
        self.story_generator = StoryGenerator(self.config)
        self.narrator = Narrator(self.config)
        self.post_processor = PostProcessor(self.config)

        # 后端
        self.image_backend = None

        # 输出目录
        output_base = self.config.get("output_dir", str(PROJECT_ROOT / "outputs"))
        self.image_dir = Path(output_base) / "images"
        self.metadata_dir = Path(output_base) / "metadata"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _init_backend(self):
        """懒初始化图像后端"""
        if self.image_backend is not None:
            return

        backend_type = self.config["image"].get("backend", "replicate")

        if backend_type == "replicate":
            from src.image_engine.replicate_backend import ReplicateBackend

            self.image_backend = ReplicateBackend(self.config)
        elif backend_type == "comfyui":
            from src.image_engine.comfy_backend import ComfyUIBackend

            self.image_backend = ComfyUIBackend(self.config)
        elif backend_type == "dry_run":
            self.image_backend = None
        else:
            raise ValueError(f"不支持的图像后端: {backend_type}，可选: replicate, comfyui, dry_run")

    def generate_one(self, custom_theme: Optional[str] = None) -> dict:
        """生成一幅完整的连环画（故事 + 画面提示词 + 图片 + 旁白）

        Args:
            custom_theme: 可选，指定题材

        Returns:
            包含所有输出信息的 dict
        """
        print("=" * 60)
        print(f"📖 生成第 {self.story_generator.recent_topics.__len__() + 1} 幅连环画...")
        print("=" * 60)

        # Step 1: 生成故事
        print("📝 [1/4] 生成故事...")
        story = self.story_generator.generate_story(custom_theme)
        print(f"   标题：{story.title}")
        print(f"   时代：{story.era}")
        print(f"   画师：{story.artist.value}")
        print(f"   人物：{'、'.join(story.characters)}")

        # Step 2: 生成旁白（如果故事中已有且质量好则复用）
        print("📝 [2/4] 优化旁白解说...")
        narrator_style = story.narrator_style
        if story.narration and len(story.narration) >= 50:
            narration = story.narration
        else:
            narration = self.narrator.generate(
                scene_description=story.scene_description,
                style=narrator_style,
                theme=story.theme,
            )
        print(f"   旁白 (风格: {narrator_style}): {narration[:100]}...")

        # 更新旁白
        story.narration = narration

        # Step 3: 构建图像 prompt
        print("🎨 [3/4] 构建图像提示词...")
        image_prompt = build_image_prompt(story)
        negative_prompt = build_negative_prompt()

        story_cfg = self.config.get("story", {})
        narration_cfg = story.narrator_style
        narration_min = story_cfg.get("narration_min_chars", 80)
        narration_max = story_cfg.get("narration_max_chars", 150)

        # Step 4: 生成图像
        result = self._generate_image(image_prompt, negative_prompt, story)

        # 保存元数据
        metadata = {
            "title": story.title,
            "theme": story.theme,
            "theme_board": story.theme_board,
            "source_book": story.source_book,
            "era": story.era,
            "characters": story.characters,
            "artist": story.artist.value,
            "scene_description": story.scene_description,
            "narration": narration,
            "historical_note": story.historical_note,
            "image_prompt": image_prompt,
            "negative_prompt": negative_prompt,
            "narration_style": narration_cfg,
            "narration_chars": f"{narration_min}-{narration_max}",
            "generated_at": datetime.now().isoformat(),
            "image_path": result.get("image_path"),
            "image_url": result.get("image_url"),
            "backend": self.config["image"].get("backend", "unknown"),
            "llm_provider": self.config["llm"].get("provider", "unknown"),
        }

        self._save_metadata(story.title, metadata)

        print(f"\n✅ 完成！")
        print(f"   图片：{result.get('image_path', result.get('image_url', 'N/A'))}")
        print(f"   元数据：{self.metadata_dir / f'{self._safe_filename(story.title)}.json'}")

        return metadata

    def _generate_image(
        self,
        prompt: str,
        negative_prompt: str,
        story,
    ) -> dict:
        """生成图像"""
        result = {"image_path": None, "image_url": None, "error": None}

        self._init_backend()

        if self.image_backend is None:
            # Dry run 模式
            print("   🏜️ [dry-run 模式] 跳过图像生成")
            print(f"   Prompt:\n{prompt[:300]}...\n")
            return result

        print(f"   🖼️  使用 {self.image_backend.name()} 生成图像...")

        img_cfg = self.config["image"]
        backend_result = self.image_backend.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=img_cfg.get("width", 768),
            height=img_cfg.get("height", 1024),
        )

        if not backend_result.success:
            print(f"   ❌ 图像生成失败: {backend_result.error}")
            result["error"] = backend_result.error
            return result

        # 下载并保存本地
        if backend_result.image_url:
            result["image_url"] = backend_result.image_url
            local_path = self._download_and_process(backend_result.image_url, story.title)
            result["image_path"] = str(local_path) if local_path else None

        return result

    def _download_and_process(self, url: str, title: str) -> Optional[Path]:
        """下载远程图片并应用后期处理

        Args:
            url: 图片 URL
            title: 故事标题

        Returns:
            本地保存路径
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            # 保存原始图片
            img = Image.open(io.BytesIO(resp.content))
            safe_name = self._safe_filename(title)
            raw_path = self.image_dir / f"{safe_name}_raw.png"
            img.save(raw_path)

            # 后期处理
            print("   🎨 应用后期处理（宣纸纹理 + 做旧 + 边框）...")
            processed = self.post_processor.process(img)
            final_path = self.image_dir / f"{safe_name}.png"
            processed.save(final_path, quality=95)

            # 删除原始图（可选，保留可注释）
            # raw_path.unlink()

            print(f"   💾 已保存: {final_path}")
            return final_path

        except Exception as e:
            print(f"   ⚠️ 图片处理失败: {e}")
            return None

    def _save_metadata(self, title: str, metadata: dict) -> Path:
        """保存元数据 JSON"""
        safe_name = self._safe_filename(title)
        path = self.metadata_dir / f"{safe_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def _safe_filename(title: str) -> str:
        """将标题转为安全文件名"""
        safe = "".join(c for c in title if c.isalnum() or c in " _-")
        # 添加时间戳防重
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe}_{ts}"

    def run_batch(
        self,
        count: int = 1,
        custom_theme: Optional[str] = None,
        delay: int = 2,
    ) -> List[dict]:
        """批量生成多幅连环画

        Args:
            count: 生成数量
            custom_theme: 指定题材（可选）
            delay: 每次生成间隔秒数

        Returns:
            元数据列表
        """
        results = []
        for i in range(count):
            try:
                print(f"\n{'=' * 60}")
                print(f"  进度: {i + 1} / {count}")
                print(f"{'=' * 60}")

                meta = self.generate_one(custom_theme)
                results.append(meta)

                if i < count - 1 and delay > 0:
                    print(f"\n⏳ 等待 {delay} 秒后继续下一幅...")
                    time.sleep(delay)

            except KeyboardInterrupt:
                print("\n\n⚠️ 用户中断。")
                break
            except Exception as e:
                print(f"\n❌ 生成失败: {e}")
                results.append({"error": str(e)})
                continue

        print(f"\n{'=' * 60}")
        print(f"📊 批量生成完成: {len(results)}/{count}")
        success = [r for r in results if "error" not in r or not r.get("error")]
        print(f"   成功: {len(success)}, 失败: {len(results) - len(success)}")
        print(f"{'=' * 60}")

        return results

    def dry_run(self, count: int = 1):
        """测试运行 — 仅生成故事和 prompt，不调用图像 API

        Args:
            count: 测试次数
        """
        self.config.setdefault("image", {})["backend"] = "dry_run"

        for i in range(count):
            print(f"\n{'─' * 50}")
            print(f"  Dry Run #{i + 1}")
            print(f"{'─' * 50}")

            # 随机选题
            story = self.story_generator.dry_run()
            print(f"  标题: {story.title}")
            print(f"  板块: {story.theme} ({story.theme_board})")
            print(f"  出处: {story.source_book}")
            print(f"  时代: {story.era}")
            print(f"  画师: {story.artist.value}")
            print(f"  解说风格: {story.narrator_style}")
            print(f"  场景: {story.scene_description[:150]}...")
            print(f"\n  旁白: {story.narration}")
            print(f"\n  画师风格: {story.artist.value}")
            print(f"{'─' * 50}\n")


def main():
    parser = argparse.ArgumentParser(
        description="中国传统白描连环画生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m src.main --dry-run              # 测试运行\n"
            "  python -m src.main --batch 5              # 生成5幅\n"
            f"  python -m src.main --batch 3 --theme three_kingdoms  # 指定三国题材\n"
            f"  可选题材: {', '.join(HISTORY_BOARDS.keys())}\n"
            "  python -m src.main --batch 10 --delay 5   # 生成10幅，间隔5秒\n"
        ),
    )
    parser.add_argument(
        "--batch", "-b",
        type=int,
        default=1,
        help="批量生成数量 (默认: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="测试模式: 仅生成故事和 prompt，不调用图像 API",
    )
    parser.add_argument(
        "--theme", "-t",
        type=str,
        default=None,
choices=list(HISTORY_BOARDS.keys()),
        help="指定故事题材 (默认: 随机)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=int,
        default=2,
        help="每次生成间隔秒数 (默认: 2)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出目录 (默认: ./outputs)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (默认: ./config.yaml)",
    )

    args = parser.parse_args()

    # 初始化管线
    config_path = Path(args.config) if args.config else None
    pipeline = ComicPipeline(config_path)

    # 自定义输出目录
    if args.output:
        pipeline.image_dir = Path(args.output) / "images"
        pipeline.metadata_dir = Path(args.output) / "metadata"
        pipeline.image_dir.mkdir(parents=True, exist_ok=True)
        pipeline.metadata_dir.mkdir(parents=True, exist_ok=True)

    # 最后询问用户是否要运行
    if args.dry_run:
        print("🏜️  Dry Run 模式 — 不调用任何外部 API\n")
        pipeline.dry_run(count=args.batch)
        return

    print(f"🎨 中国传统白描连环画生成器")
    print(f"   图像后端: {pipeline.config['image'].get('backend', '未配置')}")
    print(f"   LLM: {pipeline.config['llm'].get('provider', '未配置')}")
    print(f"   输出目录: {pipeline.image_dir.parent}\n")

    pipeline.run_batch(
        count=args.batch,
        custom_theme=args.theme,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
