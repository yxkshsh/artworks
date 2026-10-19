#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把素材目录里的图片 / 视频整理成一个静态作品集页面。

    python tools/build.py                       # 用默认素材目录
    python tools/build.py --src "D:\\别的目录"

视频会统一转成 H.264（原片多为 HEVC，Chrome 播不了），
需要 ffmpeg：优先用 PATH 里的，其次用 `pip install imageio-ffmpeg` 自带的。
没有 ffmpeg 时会退化成直接拷贝，页面在 Chrome 里可能播不了。

产物：
    index.html          构建时生成，不要手改
    assets/             手写样式与脚本
    media/video/        发布用视频（H.264）
    media/orig/         原始图片备份
    media/web/          网页用 webp：大图 / 缩略图 / 海报 / 封面
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path(r"D:\下载\素材")
INK = (10, 10, 11)  # 页面底色，用来压平透明通道

# ------------------------------------------------------------------
# 站点信息：改标题、署名、年份，只改这里
# ------------------------------------------------------------------

SITE = {
    "name": "yxkshsh",                 # 署名：页头、页脚、浏览器标签里用
    "title": "作品集",                  # 大标题（首屏那个巨大的字）
    "title_en": "Selected Works",      # 右上角的英文小字
    "kicker": "AI 影像与图像",          # 大标题上方那行小字
    "year": "2026",
    "url": "https://yxkshsh.github.io/artworks/",
    "repo": "https://github.com/yxkshsh/artworks",
}

SITE_URL = SITE["url"]  # 社交卡片、canonical 要用绝对地址

# ------------------------------------------------------------------
# 内容清单：标题、顺序、文案、抽帧时间都在这里改
# ------------------------------------------------------------------

FILMS = [
    {
        "slug": "night-street",
        "title": "夜街 · 猫耳",
        "en": "Night Street",
        "desc": "自拍视角走过夜里的街，走到一半，身后多了一个人。",
        "src": "152d95c1c39c9ffeb68a3d2c420634fa.mp4",
        "poster_at": 9.0,
    },
    {
        "slug": "face-check",
        "title": "FACE CHECK",
        "en": "Face Check",
        "desc": "正面特写、打勾、再换一个角度：把「验脸」做成十五秒的梗。",
        "src": "5266ff62a87a8b5a705f2eadc5c01bfe.mp4",
        "poster_at": 9.0,
        "focus": "50% 32%",
    },
    {
        "slug": "waterside",
        "title": "水畔",
        "en": "Waterside",
        "desc": "蓝发少女泡在水光与虹彩里，画面几乎是静的，只有高光在动。",
        "src": "7ea1049345fb60bf0eb34d877d950499.mp4",
        "poster_at": 2.0,
    },
    {
        "slug": "dialogue",
        "title": "对白",
        "en": "Dialogue",
        "desc": "夜车里的一场对话，浅景深，对面的人始终只露一个肩。",
        "src": "canvas-video-20260808022600.mp4",
        "poster_at": 10.0,
        "scale_w": 1600,
    },
    {
        "slug": "offcut",
        "title": "试剪 06",
        "en": "Offcut 06",
        "desc": "四秒钟的试剪，从上一段素材里留下的一个眼神。",
        "src": "video-fb8802fa-1ec8-42d5-a657-24c1fb9f0d2d-assistant.mp4",
        "poster_at": 2.2,
    },
]

STILLS = [
    {
        "slug": "portrait",
        "title": "肖像",
        "sub": "Portrait",
        "src": "kling_20260806_作品_25岁女性_五官精致_5400_0.png",
        "desc": "白底、黑大衣、自然光，一张干净的定妆照。",
    },
    {
        "slug": "empty-scene",
        "title": "空场景",
        "sub": "Empty Scene",
        "src": "kling_20260806_作品_空场景_无角色_荒寂_5464_0.png",
        "desc": "夜里的一扇门、一条空街，一个人也没有。",
        "crop_bottom": 0.07,  # 去掉右下角的工具水印
    },
    {
        "slug": "cloud-city",
        "title": "云上白城",
        "sub": "City Above Clouds",
        "src": "canvas-image-20260808020919.png",
        "desc": "云层之上的白色城邦，也在首页当了封面。",
    },
]

# 不进公开页面的素材：第三方水印或重复内容
EXCLUDED = [
    ("A3-构图锚点.png", "电视剧截图，带 L!BTV 台标"),
    ("A4-风格锚点.png", "电视剧截图，带 L!BTV 台标"),
    ("image.png", "带「知乎 @浮点AI」水印的第三方图"),
    ("da0c88183e537ccc6707cd08bd934c4a.mp4", "抖音竖版轮播，画面内嵌抖音号水印，与 FACE CHECK 重复"),
    ("5266ff62a87a8b5a705f2eadc5c01bfe.jpg", "FACE CHECK 的静帧，改由视频抽帧"),
    ("da0c88183e537ccc6707cd08bd934c4a.jpg", "竖版静帧，随竖版视频一起排除"),
    ("152d95c1c39c9ffeb68a3d2c420634fa.jpg", "夜街静帧，改由视频抽帧"),
    ("7ea1049345fb60bf0eb34d877d950499.jpg", "水畔静帧，改由视频抽帧"),
]


# ------------------------------------------------------------------
# ffmpeg
# ------------------------------------------------------------------

def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(cmd[:4])} ...\n{proc.stderr[-800:]}")


def copy_file(src: Path, dst: Path) -> None:
    """复制文件，并去掉只读属性（素材常是只读的，留着会导致下次构建删不掉旧文件）。"""
    shutil.copy2(src, dst)
    try:
        dst.chmod(0o666)
    except OSError:
        pass


# ------------------------------------------------------------------
# mp4 解析（判断编码与尺寸，不依赖 ffprobe）
# ------------------------------------------------------------------

def _boxes(f, start: int, end: int):
    f.seek(start)
    while f.tell() + 8 <= end:
        pos = f.tell()
        size, kind = struct.unpack(">I4s", f.read(8))
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            data = pos + 16
        elif size == 0:
            size = end - pos
            data = pos + 8
        else:
            data = pos + 8
        if size < 8:
            return
        yield kind.decode("latin1"), data, pos + size
        f.seek(pos + size)


def _first_sample_format(f, start: int, end: int) -> str:
    """在 moov 里递归找 stsd，返回第一条 sample entry 的编码名（hvc1 / avc1 …）。"""
    for kind, s, e in _boxes(f, start, end):
        if kind == "stsd":
            f.seek(s + 12)
            return f.read(4).decode("latin1", "ignore").strip()
        if kind in ("trak", "mdia", "minf", "stbl"):
            found = _first_sample_format(f, s, e)
            if found:
                return found
    return ""


def probe_video(path: Path) -> dict:
    info = {"width": 0, "height": 0, "seconds": 0.0, "codec": ""}
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            total = f.tell()
            dims: list[tuple[float, float]] = []
            for kind, start, end in _boxes(f, 0, total):
                if kind != "moov":
                    continue
                for k2, s2, e2 in _boxes(f, start, end):
                    if k2 == "mvhd":
                        f.seek(s2)
                        version = f.read(1)[0]
                        f.seek(s2 + 4)
                        if version == 1:
                            f.read(16)
                            ts = struct.unpack(">I", f.read(4))[0]
                            dur = struct.unpack(">Q", f.read(8))[0]
                        else:
                            f.read(8)
                            ts = struct.unpack(">I", f.read(4))[0]
                            dur = struct.unpack(">I", f.read(4))[0]
                        info["seconds"] = round(dur / ts, 2) if ts else 0.0
                    elif k2 == "trak":
                        for k3, s3, _e3 in _boxes(f, s2, e2):
                            if k3 == "tkhd":
                                f.seek(s3)
                                version = f.read(1)[0]
                                f.seek(s3 + (36 if version == 1 else 24) + 52)
                                dims.append(
                                    (
                                        struct.unpack(">I", f.read(4))[0] / 65536,
                                        struct.unpack(">I", f.read(4))[0] / 65536,
                                    )
                                )
                            elif k3 == "stsd" and not info["codec"]:
                                f.seek(s3 + 12)
                                info["codec"] = f.read(4).decode("latin1", "ignore").strip()
                if not info["codec"]:
                    info["codec"] = _first_sample_format(f, start, end)
            if dims:
                info["width"] = int(max(d[0] for d in dims))
                info["height"] = int(max(d[1] for d in dims))
    except Exception as exc:
        print(f"  ! 读取视频信息失败 {path.name}: {exc}")
    return info


# ------------------------------------------------------------------
# 图片
# ------------------------------------------------------------------

def to_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, INK)
        flat.paste(im, mask=im.getchannel("A"))
        return flat
    return im.convert("RGB")


def fit(im: Image.Image, max_edge: int) -> Image.Image:
    out = im.copy()
    out.thumbnail((max_edge, max_edge), Image.LANCZOS)
    return out


def crop_ratio(im: Image.Image, ratio: float, anchor: float = 0.35) -> Image.Image:
    w, h = im.size
    target_h = int(round(w / ratio))
    if target_h <= h:
        top = max(0, int((h - target_h) * anchor))
        return im.crop((0, top, w, top + target_h))
    target_w = int(round(h * ratio))
    left = max(0, (w - target_w) // 2)
    return im.crop((left, 0, left + target_w, h))


def save_webp(im: Image.Image, out: Path, quality: int = 82) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "WEBP", quality=quality, method=6)
    return out.stat().st_size


def clock(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


# ------------------------------------------------------------------
# 构建
# ------------------------------------------------------------------

def build(src: Path) -> None:
    if not src.is_dir():
        raise SystemExit(f"素材目录不存在：{src}")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("! 没找到 ffmpeg：视频会原样拷贝，HEVC 在 Chrome 里可能无法播放")

    dirs = {
        "video": ROOT / "media" / "video",
        "orig": ROOT / "media" / "orig",
        "web": ROOT / "media" / "web",
        "thumb": ROOT / "media" / "web" / "thumb",
        "poster": ROOT / "media" / "web" / "poster",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    keep: set[Path] = set()
    payload = 0
    print(f"素材：{src}")

    # ---- 影像 ----
    for item in FILMS:
        spath = src / item["src"]
        if not spath.exists():
            raise SystemExit(f"缺少视频：{spath}")
        dst = dirs["video"] / f"{item['slug']}.mp4"
        keep.add(dst)

        src_info = probe_video(spath)
        need_encode = bool(ffmpeg) and (
            src_info["codec"] in ("hvc1", "hev1")
            or src_info["width"] > 1600
            or spath.stat().st_size > 12 * 1024 * 1024
        )

        if need_encode:
            tmp = dst.with_name(dst.stem + ".tmp.mp4")
            vf = []
            if item.get("scale_w") and src_info["width"] > item["scale_w"]:
                vf.append(f"scale={item['scale_w']}:-2:flags=lanczos")
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(spath)]
            if vf:
                cmd += ["-vf", ",".join(vf)]
            cmd += [
                "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(tmp),
            ]
            print(f"  转码 {item['slug']} …（{src_info['codec'] or '?'} {src_info['width']}×{src_info['height']}）")
            run(cmd)
            if dst.exists():
                dst.chmod(0o666)
                dst.unlink()
            tmp.replace(dst)
        elif not dst.exists() or dst.stat().st_size != spath.stat().st_size:
            copy_file(spath, dst)

        info = probe_video(dst)
        item.update(
            width=info["width"],
            height=info["height"],
            seconds=info["seconds"],
            duration=clock(info["seconds"]),
            dims=f"{info['width']}×{info['height']}",
            portrait=info["height"] > info["width"],
            size_mb=round(dst.stat().st_size / 1e6, 1),
            codec=info["codec"],
        )
        payload += dst.stat().st_size

        # 海报：从成片里抽一帧
        if ffmpeg and info["seconds"]:
            at = min(float(item.get("poster_at", 1.0)), max(0.0, info["seconds"] - 0.2))
            frame = Path(tempfile.gettempdir()) / f"dsh-{item['slug']}.png"
            run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(dst),
                 "-frames:v", "1", str(frame)])
            im = to_rgb(Image.open(frame))
            poster = dirs["poster"] / f"{item['slug']}.webp"
            keep.add(poster)
            payload += save_webp(fit(im, 1600), poster, 78)
            item["poster_web"] = f"media/web/poster/{item['slug']}.webp"
            frame.unlink(missing_ok=True)

        print(
            f"  影像 {item['slug']:13s} {item['dims']:>10s} {item['duration']} "
            f"{item['codec']:5s} {item['size_mb']:5.1f} MB"
        )

    # ---- 图像 ----
    for item in STILLS:
        spath = src / item["src"]
        if not spath.exists():
            raise SystemExit(f"缺少图片：{spath}")
        im = to_rgb(Image.open(spath))
        if item.get("crop_bottom"):
            cut = int(im.height * float(item["crop_bottom"]))
            im = im.crop((0, 0, im.width, im.height - cut))
        item["width"], item["height"] = im.size

        orig = dirs["orig"] / f"{item['slug']}{spath.suffix.lower()}"
        keep.add(orig)
        if not orig.exists() or orig.stat().st_size != spath.stat().st_size:
            copy_file(spath, orig)

        web = dirs["web"] / f"{item['slug']}.webp"
        thumb = dirs["thumb"] / f"{item['slug']}.webp"
        keep.update({web, thumb})
        payload += save_webp(fit(im, 1800), web, 84)
        payload += save_webp(fit(im, 900), thumb, 76)

        item["web"] = f"media/web/{item['slug']}.webp"
        item["thumb"] = f"media/web/thumb/{item['slug']}.webp"
        item["orig"] = f"media/orig/{orig.name}"
        print(f"  图像 {item['slug']:13s} {item['width']}×{item['height']}")

    # ---- 封面 / 社交卡片 ----
    cover_item = next((s for s in STILLS if s["slug"] == "cloud-city"), STILLS[0])
    cover_im = to_rgb(Image.open(src / cover_item["src"]))
    for name, ratio, edge, q in (("cover.webp", 21 / 9, 2200, 82), ("og.webp", 1200 / 630, 1200, 84)):
        p = dirs["web"] / name
        keep.add(p)
        payload += save_webp(fit(crop_ratio(cover_im, ratio), edge), p, q)

    # ---- 清掉上一版留下的文件 ----
    for d in (dirs["video"], dirs["web"], dirs["poster"], dirs["thumb"], dirs["orig"]):
        for f in d.glob("*"):
            if f.is_file() and f not in keep:
                f.unlink()
                print(f"  - 删除旧文件 {f.relative_to(ROOT)}")

    # ---- 页面 ----
    (ROOT / "index.html").write_text(render_html(generated=date.today().isoformat()), encoding="utf-8")
    (ROOT / "README.md").write_text(render_readme(), encoding="utf-8")
    (ROOT / "media" / "manifest.json").write_text(
        json.dumps(
            {
                "built": date.today().isoformat(),
                "source": str(src),
                "films": FILMS,
                "stills": [{k: v for k, v in s.items() if k != "src"} for s in STILLS],
                "excluded": [{"file": f, "reason": r} for f, r in EXCLUDED],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n完成：{ROOT / 'index.html'}")
    print(f"页面资源体积约 {payload / 1e6:.1f} MB（{len(FILMS)} 段影像 / {len(STILLS)} 幅图像）")


# ------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------

def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(generated: str) -> str:
    films = []
    for i, f in enumerate(FILMS, 1):
        poster = (
            f'<img src="{f["poster_web"]}" alt="{esc(f["title"])}的画面" />'
            if f.get("poster_web")
            else ""
        )
        cls = "film reveal"
        focus = f' style="object-position:{f["focus"]}"' if f.get("focus") else ""
        if poster and focus:
            poster = poster.replace("<img ", f"<img{focus} ")
        films.append(
            f"""      <figure class="{cls}" data-title="{esc(f['title'])}">
        <button class="frame"
                data-video="media/video/{f['slug']}.mp4" data-poster="{f.get('poster_web', '')}"
                aria-label="播放《{esc(f['title'])}》">{poster}
          <span class="idx">{i:02d}</span>
          <span class="play" aria-hidden="true"></span>
          <span class="dur">{f['duration']}</span>
        </button>
        <figcaption>
          <h3>{esc(f['title'])}</h3>
          <span class="en">{esc(f['en'])}</span>
          <p>{esc(f['desc'])}</p>
          <span class="spec"><span>{f['dims']}</span><span>{f['duration']}</span><span>{f['size_mb']:.1f} MB</span><a href="media/video/{f['slug']}.mp4" download>下载原片</a></span>
        </figcaption>
      </figure>"""
        )

    stills = []
    for s in STILLS:
        stills.append(
            f"""      <figure class="still reveal">
        <button data-full="{s['web']}" aria-label="放大查看《{esc(s['title'])}》">
          <img src="{s['thumb']}" alt="{esc(s['title'])}：{esc(s['desc'])}" width="{s['width']}" height="{s['height']}" />
        </button>
        <figcaption>
          <h3>{esc(s['title'])}</h3>
          <span class="sub">{s['sub']} · {s['width']}×{s['height']}</span>
        </figcaption>
      </figure>"""
        )

    film_count = len(FILMS)
    still_count = len(STILLS)
    total_seconds = sum(f["seconds"] for f in FILMS)

    name = SITE["name"]
    title = SITE["title"]
    year = SITE["year"]
    page_title = f"{title} · {name}"
    page_desc = f"{year} 年的 AI 影像与图像：{film_count} 段短片、{still_count} 幅静帧。"
    repo_label = SITE["repo"].replace("https://", "").rstrip("/")

    note = ""
    if film_count % 2 == 1:
        note = """
      <aside class="film-note reveal">
        <span>过程</span>
        <p>这些画面没有摄制组。提示词、参考帧、一次次重生成——最后留下的只有这十几秒；
           同一批素材里的大部分，都还留在本地文件夹里没被选上。</p>
      </aside>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{page_title}</title>
<meta name="description" content="{page_desc}" />
<meta name="author" content="{name}" />
<meta name="theme-color" content="#0a0a0b" />
<meta property="og:type" content="website" />
<meta property="og:title" content="{page_title}" />
<meta property="og:description" content="{page_desc}" />
<meta property="og:image" content="{SITE_URL}media/web/og.webp" />
<meta property="og:url" content="{SITE_URL}" />
<meta property="og:site_name" content="{name} · {title}" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="canonical" href="{SITE_URL}" />
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%230a0a0b'/%3E%3Ctext x='32' y='45' font-family='Georgia,serif' font-size='36' fill='%23d9a96b' text-anchor='middle'%3Ey%3C/text%3E%3C/svg%3E" />
<link rel="stylesheet" href="assets/site.css" />
<script>document.documentElement.className += ' js';</script>
</head>
<body>

<header class="topbar shell">
  <a class="mark" href="#top"><b>{name}</b> · {title}</a>
  <p class="tag">{SITE["title_en"]} / {year}</p>
</header>

<main id="top">

  <section class="hero shell">
    <p class="kicker">{SITE["kicker"]} · {year}</p>
    <h1>{title}<span class="stop">。</span></h1>

    <div class="hero-row">
      <p class="lede">
        {film_count} 段十几秒的短片，{still_count} 幅静帧。没有摄制组，也没有渲染农场——
        只有提示词、几轮挑选，和一点耐心。<em>链接就是备份</em>，随时可以丢给别人看。
      </p>
      <ul class="stats">
        <li><b>{film_count:02d}</b><span>影像</span></li>
        <li><b>{still_count:02d}</b><span>图像</span></li>
        <li><b>{year}</b><span>年份</span></li>
        <li><b>AI</b><span>生成</span></li>
      </ul>
    </div>
  </section>

  <figure class="cover reveal">
    <img src="media/web/cover.webp" alt="云上白城：云层之上的白色城邦" />
    <figcaption><span>云上白城 / 封面静帧</span><span>1920 × 1072</span></figcaption>
  </figure>

  <section class="section shell" id="films">
    <div class="section-head">
      <h2>影像<small>Films</small></h2>
      <span class="count">{film_count:02d} / 共 {clock(total_seconds)} · 横屏</span>
    </div>
    <div class="films">
{chr(10).join(films)}{note}
    </div>
  </section>

  <section class="section shell" id="stills">
    <div class="section-head">
      <h2>图像<small>Stills</small></h2>
      <span class="count">{still_count:02d} / 点击放大</span>
    </div>
    <div class="stills{' stills--trio' if still_count == 3 else ''}">
{chr(10).join(stills)}
    </div>
  </section>

</main>

<footer class="footer shell">
  <p>
    页面上的影像与图像均由 AI 生成、经人工挑选整理；除另有标注外不含第三方素材。<br />
    转载或商用请先联系。© {year} {name}
  </p>
  <p>
    源码与原始文件：<a href="{SITE["repo"]}">{repo_label}</a><br />
    最近更新 {generated}
  </p>
</footer>

<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="图像查看">
  <figure>
    <button class="lb-btn lb-close" aria-label="关闭">×</button>
    <button class="lb-btn lb-prev" aria-label="上一张">‹</button>
    <button class="lb-btn lb-next" aria-label="下一张">›</button>
    <img alt="" />
  </figure>
  <figcaption><strong></strong><span class="lb-sub"></span></figcaption>
</div>

<script src="assets/site.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------
# README
# ------------------------------------------------------------------

def render_readme() -> str:
    return f"""# {SITE['title']} · {SITE['title_en']}

{SITE['year']} 年的 AI 影像与图像，发布在 GitHub Pages：

- 页面：{SITE['url']}
- 仓库：{SITE['repo']}

## 改标题 / 署名

站点级信息集中在 `tools/build.py` 顶部的 `SITE`：

```python
SITE = {{
    "name": "yxkshsh",            # 署名：页头、页脚、浏览器标签
    "title": "作品集",             # 首屏大标题
    "title_en": "Selected Works", # 右上角英文小字
    "kicker": "AI 影像与图像",     # 标题上方的小字
    "year": "2026",
    ...
}}
```

- `title` 同时决定首屏大标题、浏览器标签（`作品集 · yxkshsh`）和分享卡片标题；
- `name` 是署名，会出现在页头、页脚和 © 那一行；
- 单条作品的标题不在这里，而在下面 `FILMS` / `STILLS` 每一条的 `"title"` 字段。

改完重新构建再推送，一分钟左右线上生效：

```bash
python tools/build.py
git add -A
git commit -m "chore: 改标题"
git push
```

## 目录

```
index.html            构建产物（由 tools/build.py 生成，不要手改）
assets/site.css       样式，手写
assets/site.js        交互：视频播放 / 图像灯箱 / 滚动入场
media/video/*.mp4     发布用视频（已转成 H.264，浏览器都能播）
media/orig/*          原始图片，未压缩
media/web/*           网页用的 webp：大图、缩略图、海报、封面
media/manifest.json   每次构建的清单
tools/build.py        构建脚本，标题与文案都写在里面
tools/preview.py      本地预览（补了 webp 的 MIME）
```

## 加新作品

1. 把新文件放进素材目录（默认 `D:\\下载\\素材`）。
2. 编辑 `tools/build.py` 顶部的 `FILMS` / `STILLS` 列表，加一条记录。
3. 重新构建并发布：

```bash
python tools/build.py
git add -A
git commit -m "add: 新作品"
git push
```

GitHub Pages 会在推送后一分钟左右自动更新。

## 说明

- 视频统一转码为 H.264 + AAC，并用 `+faststart` 让首帧尽快出现；
  原片若是 HEVC（苹果设备、剪映常见），Chrome 默认放不了。
- 转码需要 ffmpeg：`pip install imageio-ffmpeg` 之后脚本会自动找到它。
- 页面没有任何外部依赖：不加载 CDN、字体或统计脚本，断网也能打开。
- 带第三方水印的素材没有放进公开页面，清单见 `media/manifest.json` 的 `excluded`。
- 图片与视频均为 AI 生成；转载或商用请先联系作者。
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建 AI 作品集静态页面")
    parser.add_argument("--src", default=str(DEFAULT_SRC), help="素材目录")
    args = parser.parse_args()
    build(Path(args.src))
