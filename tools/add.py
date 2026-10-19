#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式添加作品：问几个问题，写进 content.json，然后可选地构建 / 发布。

    python tools\\add.py            # 一步一步问
    python tools\\add.py --help     # 也能用参数一次跑完

它会做的事：
  1. 把文件复制进素材目录（默认 D:\\下载\\素材，已经在里面就跳过）
  2. 读视频时长 / 图片尺寸，给封面时间一个合理默认值
  3. 在 content.json 的 films / stills 里追加一条
  4. 问你要不要现在构建、要不要现在发布
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content.json"
sys.path.insert(0, str(ROOT / "tools"))

import build as B  # noqa: E402  （复用素材目录、mp4 解析）

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

NONINTERACTIVE = False  # --yes 时打开，所有问题都用默认值


# ------------------------------------------------------------------
# 小工具
# ------------------------------------------------------------------

def ask(prompt: str, default: str = "") -> str:
    if NONINTERACTIVE:
        return default
    hint = f"（回车用「{default}」）" if default else ""
    try:
        raw = input(f"{prompt}{hint}：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消，没有改动。")
        sys.exit(1)
    return raw or default


def ask_yes(prompt: str, default_yes: bool = True) -> bool:
    if NONINTERACTIVE:
        return default_yes
    hint = "[Y/n]" if default_yes else "[y/N]"
    raw = ask(f"{prompt} {hint}", "y" if default_yes else "n").lower()
    return raw.startswith("y")


def clean_path(raw: str) -> Path:
    text = raw.strip().strip('"').strip("'")
    return Path(text).expanduser()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "work"


def unique_slug(base: str, taken: set[str]) -> str:
    slug, n = base, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    return slug


def load_json() -> dict:
    if not CONTENT.exists():
        return {"films": [], "stills": [], "excluded": []}
    return json.loads(CONTENT.read_text(encoding="utf-8"))


def save_json(data: dict) -> None:
    CONTENT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def human_time(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def ensure_in_materials(path: Path) -> Path:
    """把文件放进素材目录。已在里面就原样返回。"""
    src_dir = B.DEFAULT_SRC
    src_dir.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve() == src_dir.resolve():
        return path

    dest = src_dir / path.name
    if dest.exists():
        if dest.stat().st_size == path.stat().st_size:
            print(f"  素材目录里已有同名同大小的文件，直接用它：{dest.name}")
            return dest
        if not ask_yes(f"素材目录已有同名文件 {dest.name}，覆盖吗？", False):
            print("  已取消。")
            sys.exit(1)
    shutil.copy2(path, dest)
    try:
        dest.chmod(0o666)
    except OSError:
        pass
    print(f"  已复制到素材目录：{dest}")
    return dest


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="交互式添加一件作品到作品集")
    parser.add_argument("--file", help="视频或图片路径")
    parser.add_argument("--title", help="中文标题")
    parser.add_argument("--en", help="英文小字")
    parser.add_argument("--desc", help="一句话介绍")
    parser.add_argument("--slug", help="URL 用的英文短名")
    parser.add_argument("--poster-at", type=float, help="视频封面取第几秒")
    parser.add_argument("--crop-bottom", type=float, help="图片裁掉底部比例，例如 0.07")
    parser.add_argument("--yes", action="store_true", help="其余问题全用默认值，不交互")
    parser.add_argument("--no-build", action="store_true", help="只写入清单，不构建")
    parser.add_argument("--publish", action="store_true", help="构建后直接 commit + push")
    args = parser.parse_args()

    global NONINTERACTIVE
    NONINTERACTIVE = args.yes

    data = load_json()
    films, stills = data.setdefault("films", []), data.setdefault("stills", [])
    taken_slugs = {x["slug"] for x in films + stills}
    taken_srcs = {x["src"] for x in films + stills}

    print("=" * 52)
    print("  添加作品")
    print("=" * 52)

    # 1. 文件
    raw_path = args.file or ask("把文件拖进来，或输入完整路径")
    path = clean_path(raw_path)
    while not path.is_file():
        print(f"  找不到文件：{path}")
        raw_path = ask("再试一次（直接回车退出）")
        if not raw_path:
            sys.exit(1)
        path = clean_path(raw_path)

    ext = path.suffix.lower()
    if ext in VIDEO_EXT:
        kind = "film"
    elif ext in IMAGE_EXT:
        kind = "still"
    else:
        print(f"  不认识的扩展名：{ext}")
        print("  支持的视频：mp4 / mov / m4v / webm；图片：png / jpg / webp")
        sys.exit(1)

    # 2. 读元数据
    info = ""
    duration = 0.0
    if kind == "film":
        meta = B.probe_video(path)
        duration = meta["seconds"]
        info = f"视频 · {meta['width']}×{meta['height']} · {human_time(duration)}"
        if meta["width"] == 0:
            info = "视频（读不出尺寸，构建时会再试）"
        default_poster = f"{min(3.0, max(0.3, duration * 0.3)):.1f}" if duration else "3.0"
    else:
        from PIL import Image

        with Image.open(path) as im:
            info = f"图片 · {im.width}×{im.height}"
        default_poster = None

    print(f"\n  识别为：{info}\n")

    # 3. 文案
    default_title = path.stem
    title = args.title or ask("中文标题", default_title)
    en = args.en if args.en is not None else ask("英文小字（可留空，直接回车）", "")
    desc = args.desc if args.desc is not None else ask("一句话介绍（可留空）", "")

    # 4. slug
    suggested = slugify(title if re.search(r"[a-zA-Z]", title) else path.stem)
    slug_default = unique_slug(suggested, taken_slugs)
    slug = (args.slug or ask("英文短名（决定网址和文件名）", slug_default)).strip()
    slug = slugify(slug)
    if slug in taken_slugs:
        print(f"  短名 {slug} 已被占用，换成 {unique_slug(slug, taken_slugs)}")
        slug = unique_slug(slug, taken_slugs)

    # 5. 类型专属参数
    poster_at = 0.0
    crop_bottom = 0.0
    if kind == "film":
        raw = ask("封面取第几秒", str(args.poster_at if args.poster_at else default_poster))
        try:
            poster_at = max(0.0, float(raw))
        except ValueError:
            poster_at = float(default_poster)
        print(f"  提醒：原片如果是 HEVC，构建时会自动转成 H.264（要几十秒）")
    else:
        if args.crop_bottom is not None:
            crop_bottom = max(0.0, min(0.2, args.crop_bottom))
        elif ask_yes("底部有水印要裁掉吗？", False):
            raw = ask("裁掉底部百分之几（1–10）", "5")
            try:
                crop_bottom = max(0.0, min(0.2, float(raw) / 100))
            except ValueError:
                crop_bottom = 0.05

    # 6. 落盘
    if path.name in taken_srcs:
        print(f"\n  注意：{path.name} 已经在清单里用过了。")
        if not ask_yes("还是要再加一条吗？", False):
            sys.exit(1)

    material_path = ensure_in_materials(path)

    entry: dict = {"slug": slug, "title": title}
    if kind == "film":
        entry.update({"en": en, "desc": desc, "src": material_path.name, "poster_at": poster_at})
    else:
        entry.update({"sub": en, "src": material_path.name, "desc": desc})
        if crop_bottom:
            entry["crop_bottom"] = round(crop_bottom, 3)

    (films if kind == "film" else stills).append(entry)
    save_json(data)

    print("\n  已写入 content.json：")
    print("  " + json.dumps(entry, ensure_ascii=False, indent=2).replace("\n", "\n  "))

    if args.no_build:
        print("\n  跳过构建。下次运行 python tools\\build.py 时生效。")
        return

    if not ask_yes("\n现在构建吗？", True):
        print("  好的，稍后自己跑 python tools\\build.py 即可。")
        return

    print("\n  构建中…\n")
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], cwd=ROOT)
    if result.returncode != 0:
        print("\n  构建失败，看一下上面的报错。")
        sys.exit(result.returncode)

    publish = args.publish or ask_yes("\n现在发布到网站吗？（会 commit + push）", False)
    if not publish:
        print("\n  已构建，本地预览：python tools\\preview.py 8899 → http://127.0.0.1:8899/")
        print("  想发布时：git add -A && git commit -m \"add: " + title + "\" && git push")
        return

    print("\n  发布中…")
    steps = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", f"add: {title}"],
        ["git", "push"],
    ]
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        if tail:
            print("  " + "\n  ".join(tail))
        if proc.returncode != 0:
            if cmd[1] == "commit" and "nothing to commit" in (proc.stdout + proc.stderr):
                print("  没有新改动，跳过提交。")
                continue
            print("\n  这一步失败了：" + " ".join(cmd))
            print("  常见原因：网络连不上 github.com，或本地和远端分叉。")
            print("  可以稍后手动重试：git push")
            sys.exit(1)

    print("\n  完成，一分钟左右线上更新：https://yxkshsh.github.io/artworks/")


if __name__ == "__main__":
    main()
