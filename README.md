# 作品集 · Selected Works

2026 年的 AI 影像与图像，发布在 GitHub Pages：

- 页面：https://yxkshsh.github.io/artworks/
- 仓库：https://github.com/yxkshsh/artworks

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

1. 把新文件放进素材目录（默认 `D:\下载\素材`）。
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
