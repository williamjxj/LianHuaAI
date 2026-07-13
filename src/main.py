#!/usr/bin/env python3
"""
中国传统白描连环画生成器 — 主入口

批量循环随机生成单幅中国传统白描连环画作品，配套历史故事解说文案。

使用方法:
    python -m src.main --batch 5          # 生成5幅
    python -m src.main --dry-run          # 测试运行（不调用API）
    python -m src.main --batch 3 --output ./my_outputs
    python -m src.main --regen            # 从已有 metadata 重新生成图像
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import io

from PIL import Image
import requests

from src.config import PROJECT_ROOT, load_config
from src.image_engine.post_process import PostProcessor
from src.image_engine.prompt_builder import build_image_prompt, build_negative_prompt
from src.image_engine.vision_qa import VisionQA
from src.story_engine.generator import HISTORY_BOARDS, StoryGenerator
from src.story_engine.narrator import Narrator

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
        self.vision_qa = VisionQA(self.config)

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
        elif backend_type == "runninghub":
            from src.image_engine.runninghub_backend import RunningHubBackend

            self.image_backend = RunningHubBackend(self.config)
        elif backend_type == "zhipu":
            from src.image_engine.zhipu_backend import ZhipuBackend

            self.image_backend = ZhipuBackend(self.config)
        elif backend_type == "tongyi":
            from src.image_engine.tongyi_backend import TongyiBackend

            self.image_backend = TongyiBackend(self.config)
        elif backend_type == "minimax":
            from src.image_engine.minimax_backend import MiniMaxBackend

            self.image_backend = MiniMaxBackend(self.config)
        elif backend_type == "dry_run":
            self.image_backend = None
        else:
            raise ValueError(
                f"不支持的图像后端: {backend_type}，可选: replicate, comfyui, runninghub, zhipu, tongyi, minimax, dry_run"
            )

    def _select_canvas(self) -> tuple:
        """选择随机画幅：先选比例预设，再随机缩放宽度

        Returns:
            (target_w, target_h, canvas_name)
        """
        img_cfg = self.config["image"]
        presets = img_cfg.get("canvas_presets", [{"name": "4:3", "width": 768, "height": 576}])
        canvas_select = img_cfg.get("canvas_select", "random")

        if canvas_select == "random":
            preset = random.choice(presets)
        else:
            matched = [p for p in presets if p.get("name", "").startswith(canvas_select)]
            preset = matched[0] if matched else presets[0]

        base_w, base_h = preset["width"], preset["height"]
        preset_name = preset.get("name", f"{base_w}x{base_h}")

        # 宽度随机缩放
        regen_widths = img_cfg.get("regen_widths", [base_w])
        target_w = random.choice(regen_widths)

        # 按比例计算高度
        aspect = base_w / base_h
        target_h = int(round(target_w / aspect))
        if target_h % 2 != 0:
            target_h += 1

        return target_w, target_h, preset_name

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

        # 选择随机画幅（比例 + 宽度随机化）
        target_w, target_h, aspect_ratio_name = self._select_canvas()
        print(f"   📐 画幅: {aspect_ratio_name} ({target_w}x{target_h})")

        # Step 3: 构建图像 prompt
        print("🎨 [3/4] 构建图像提示词...")
        image_prompt = build_image_prompt(story, aspect_ratio=aspect_ratio_name.split(" ")[0])
        negative_prompt = build_negative_prompt()

        story_cfg = self.config.get("story", {})
        narration_cfg = story.narrator_style
        narration_min = story_cfg.get("narration_min_chars", 80)
        narration_max = story_cfg.get("narration_max_chars", 150)

        # Step 4: 生成图像
        result = self._generate_image(image_prompt, negative_prompt, story, target_w, target_h)

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
            "canvas": f"{target_w}x{target_h}",
            "canvas_name": aspect_ratio_name,
            "generated_at": datetime.now().isoformat(),
            "image_path": result.get("image_path"),
            "image_url": result.get("image_url"),
            "backend": self.config["image"].get("backend", "unknown"),
            "llm_provider": self.config["llm"].get("provider", "unknown"),
        }

        self._save_metadata(story.title, metadata)

        print("\n✅ 完成！")
        print(f"   图片：{result.get('image_path', result.get('image_url', 'N/A'))}")
        print(f"   元数据：{self.metadata_dir / f'{self._safe_filename(story.title)}.json'}")

        return metadata

    def _generate_image(
        self,
        prompt: str,
        negative_prompt: str,
        story,
        target_w: int = 768,
        target_h: int = 576,
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
            width=target_w,
            height=target_h,
        )

        if not backend_result.success:
            print(f"   ❌ 图像生成失败: {backend_result.error}")
            result["error"] = backend_result.error
            return result

        # 下载并保存本地
        if backend_result.image_url:
            result["image_url"] = backend_result.image_url
            local_path = self._download_and_process(backend_result.image_url, story.title, story.narration, story.source_book, target_w, target_h)
            result["image_path"] = str(local_path) if local_path else None

        return result

    def _download_and_process(self, url: str, title: str, narration: str = "", source_book: str = "", target_w: int = 768, target_h: int = 576) -> Optional[Path]:
        """下载远程图片并应用后期处理（不保存中间 raw 图）

        Args:
            url: 图片 URL
            title: 故事标题
            target_w: 目标画幅宽度
            target_h: 目标画幅高度

        Returns:
            本地保存路径
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            img = Image.open(io.BytesIO(resp.content))
            safe_name = self._safe_filename(title)

            # 强制统一到目标画幅（center-crop + resize）
            if img.size != (target_w, target_h):
                img = self._fit_canvas(img, target_w, target_h)

            # Vision QA 质检
            qa_result = self.vision_qa.check(img)
            if not qa_result.passed:
                print(f"   ❌ Vision QA 未通过: {'; '.join(qa_result.reasons)}")
                return None

            # 后期处理（标题题字 + 旁白解说 + 宣纸纹理 + 做旧 + 边框）
            print("   🎨 应用后期处理（连环画标题 + 旁白解说 + 宣纸纹理 + 做旧 + 边框）...")
            processed = self.post_processor.process(img, title=title, narration=narration, source_book=source_book)
            final_path = self.image_dir / f"{safe_name}.png"
            processed.save(final_path, quality=95)

            print(f"   💾 已保存: {final_path}")
            return final_path

        except Exception as e:
            print(f"   ⚠️ 图片处理失败: {e}")
            return None

    @staticmethod
    def _fit_canvas(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """将图片强制适配到目标画幅（center-crop + resize），不拉伸变形"""
        src_w, src_h = image.size
        target_ratio = target_w / target_h
        src_ratio = src_w / src_h

        if abs(src_ratio - target_ratio) < 0.01:
            # 比例已接近，直接 resize
            return image.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 先 center-crop 到目标比例，再 resize
        if src_ratio > target_ratio:
            # 源图更宽 → crop 宽度
            new_w = int(src_h * target_ratio)
            new_h = src_h
        else:
            # 源图更高 → crop 高度
            new_w = src_w
            new_h = int(src_w / target_ratio)

        left = (src_w - new_w) // 2
        top = (src_h - new_h) // 2
        cropped = image.crop((left, top, left + new_w, top + new_h))
        return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    def _save_metadata(self, title: str, metadata: dict) -> Path:
        """保存元数据 JSON"""
        safe_name = self._safe_filename(title)
        path = self.metadata_dir / f"{safe_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def _safe_filename(title: str) -> str:
        """将标题转为安全文件名，附加时间戳（便于识别内容和防重）"""
        safe = "".join(c for c in title if c.isalnum() or c in " _-")
        safe = safe.strip() or "untitled"
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

            # 随机选画幅（比例 + 宽度随机化）
            target_w, target_h, aspect_ratio_name = self._select_canvas()

            # 随机选题
            story = self.story_generator.dry_run()
            print(f"  标题: {story.title}")
            print(f"  板块: {story.theme} ({story.theme_board})")
            print(f"  出处: {story.source_book}")
            print(f"  时代: {story.era}")
            print(f"  画师: {story.artist.value}")
            print(f"  解说风格: {story.narrator_style}")
            print(f"  画幅: {aspect_ratio_name} ({target_w}x{target_h})")
            print(f"  场景: {story.scene_description[:150]}...")
            if story.scene_plan:
                sp = story.scene_plan
                print(f"  Scene Plan: 前景={sp.foreground[:40]}... 中景={sp.middle_ground[:40]}...")
                print(f"              构图={sp.composition}  镜头={sp.camera}  光影={sp.lighting}")
            print(f"\n  旁白: {story.narration}")
            print(f"\n  画师风格: {story.artist.value}")
            print(f"{'─' * 50}\n")

    def regenerate_from_metadata(self):
        """从已有 metadata JSON 文件批量重新生成图像

        执行流程：
        1. 遍历 outputs/metadata/ 下所有 JSON
        2. 重新生成精简旁白 (30-80 字) via LLM
        3. 注入 "中国古典连环画风格，三国演义连环画风格" 到 prompt
        4. 随机选画幅，用 runninghub 重新出图
        5. 后期处理 + 紧凑底部解说条
        6. 保存到 outputs/works/ 目录
        """
        json_files = sorted(self.metadata_dir.glob("*.json"))
        if not json_files:
            print("没有找到 metadata JSON 文件。")
            return

        print(f"📂 找到 {len(json_files)} 个 metadata 文件\n")

        # 强制使用 runninghub 后端
        self.config["image"]["backend"] = "runninghub"
        self._init_backend()
        if self.image_backend is None:
            print("错误: 无法初始化 runninghub 后端")
            return

        # 创建 outputs/works/ 目录
        output_base = Path(self.config.get("output_dir", str(PROJECT_ROOT / "outputs")))
        works_dir = output_base / "works"
        works_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 输出目录: {works_dir}\n")

        success = 0
        for json_path in json_files:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                title = metadata.get("title", "untitled")
                scene_description = metadata.get("scene_description", "")
                image_prompt = metadata.get("image_prompt", "")
                negative_prompt = metadata.get("negative_prompt", "")
                source_book = metadata.get("source_book", "")
                narration_style = metadata.get("narration_style", "林汉达")
                theme = metadata.get("theme", "")

                print(f"{'─' * 50}")
                print(f"🖼️  {title}")

                if not image_prompt:
                    print("   ⚠️  metadata 中无 image_prompt，跳过")
                    continue

                # ── Step 1: 重新生成精简旁白 (30-80字) ──
                print("   📝 重新生成精简旁白...")
                narration = self.narrator.generate(
                    scene_description=scene_description,
                    style=narration_style,
                    min_chars=self.config["story"].get("narration_min_chars", 30),
                    max_chars=self.config["story"].get("narration_max_chars", 80),
                    theme=theme,
                )
                print(f"   旁白 ({narration_style}): {narration[:80]}")

                # ── Step 2: 注入古典连环画风格到 prompt ──
                style_injection = "中国古典连环画风格，三国演义连环画风格"
                modified_prompt = f"{style_injection}。\n\n{image_prompt}"
                print(f"   ✨ 已注入风格: {style_injection}")

                # ── Step 3: 随机选画幅（比例 + 宽度随机化）──
                target_w, target_h, canvas_name = self._select_canvas()
                print(f"   📐 画幅: {canvas_name} ({target_w}x{target_h})")

                # ── Step 4: 生成图像 ──
                print(f"   🖼️  使用 {self.image_backend.name()} 生成图像...")
                backend_result = self.image_backend.generate(
                    prompt=modified_prompt,
                    negative_prompt=negative_prompt,
                    width=target_w,
                    height=target_h,
                )

                if not backend_result.success:
                    print(f"   ❌ 图像生成失败: {backend_result.error}")
                    continue

                # ── Step 5: 下载 + 裁切 + 后期处理 + 保存到 works ──
                if backend_result.image_url:
                    try:
                        resp = requests.get(backend_result.image_url, timeout=60)
                        resp.raise_for_status()

                        img = Image.open(io.BytesIO(resp.content))
                        safe_name = self._safe_filename(title)

                        # 强制统一到目标画幅
                        if img.size != (target_w, target_h):
                            img = self._fit_canvas(img, target_w, target_h)

                        # Vision QA 质检
                        qa_result = self.vision_qa.check(img)
                        if not qa_result.passed:
                            print(f"   ❌ Vision QA 未通过: {'; '.join(qa_result.reasons)}")
                            continue

                        # 后期处理
                        print("   🎨 应用后期处理（宣纸纹理 + 做旧 + 解说条 + 边框）...")
                        processed = self.post_processor.process(
                            img,
                            title=title,
                            narration=narration,
                            source_book=source_book,
                        )
                        final_path = works_dir / f"{safe_name}.png"
                        processed.save(final_path, quality=95)
                        print(f"   💾 已保存: {final_path}")

                        # 更新 metadata 并保存到 works 侧
                        metadata["image_path"] = str(final_path)
                        metadata["image_url"] = backend_result.image_url
                        metadata["narration"] = narration
                        metadata["image_prompt"] = modified_prompt
                        metadata["canvas"] = f"{target_w}x{target_h}"
                        metadata["canvas_name"] = canvas_name
                        metadata["generated_at"] = datetime.now().isoformat()
                        metadata["regen_note"] = "重新生成: 精简旁白 + 古典连环画风格注入"

                        # 保存更新后的 metadata 到 works 目录
                        meta_path = works_dir / f"{safe_name}.json"
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(metadata, f, ensure_ascii=False, indent=2)

                        success += 1
                        print(f"   ✅ 成功 ({success})")

                    except Exception as e:
                        print(f"   ⚠️ 图片处理失败: {e}")
                        continue

            except Exception as e:
                print(f"   ⚠️ 处理 {json_path.name} 失败: {e}")
                continue

        print(f"\n{'=' * 50}")
        print(f"✅ 完成: {success}/{len(json_files)} 图像已生成到 {works_dir}")
        print(f"{'=' * 50}")


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
            "  python -m src.main --regen                # 从已有 metadata 重新生成图像\n"
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
    parser.add_argument(
        "--regen",
        action="store_true",
        help="从已有 metadata JSON 重新生成图像（不重新生成故事/Prompt）",
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

    if args.regen:
        print("♻️  从已有 metadata 重新生成图像\n")
        pipeline.regenerate_from_metadata()
        return

    print("🎨 中国传统白描连环画生成器")
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
