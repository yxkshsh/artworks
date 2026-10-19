# 作品集 · Selected Works

2026 年的 AI 影像与图像，发布在 GitHub Pages：

- 页面：https://yxkshsh.github.io/artworks/
- 仓库：https://github.com/yxkshsh/artworks

## 改标题 / 署名

站点级信息集中在 `tools/build.py` 顶部的 `SITE`：

```python
SITE = {
    "name": "yxkshsh",            # 署名：页头、页脚、浏览器标签
    "title": "作品集",             # 首屏大标题
    "title_en": "Selected Works", # 右上角英文小字
    "kicker": "AI 影像与图像",     # 标题上方的小字
    "year": "2026",
    ...
}
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
content.json          作品清单：标题、顺序、文案都在这里
assets/site.css       样式，手写
assets/site.js        交互：视频播放 / 图像灯箱 / 滚动入场
assets/boot.js        版本自检：页面是旧的就自动刷新一次
version.json          构建号，boot.js 用它判断新旧
media/video/*.mp4     发布用视频（已转成 H.264，浏览器都能播）
media/orig/*          原始图片，未压缩
media/web/*           网页用的 webp：大图、缩略图、海报、封面
media/manifest.json   每次构建的清单
tools/build.py        构建脚本
tools/add.py          交互式添加作品
tools/preview.py      本地预览（补了 webp 的 MIME）
```

## 推上去之后网页没变？

GitHub Pages 会给 HTML 和 CSS 加 `Cache-Control: max-age=600`，也就是最多 10 分钟缓存。
所以刚推完立刻刷新，经常看到的还是旧页面——这不是没部署成功。

这个站做了两层处理：

1. `site.css` / `site.js` / `boot.js` 的地址后面挂了内容哈希（`?v=1b646057`），
   文件一改地址就变，浏览器只能重新下载；
2. `boot.js` 加载时会用 `no-store` 去问 `version.json`，发现服务器上的构建号比
   本页新，就自动刷新一次（每个构建只试一次，不会循环）。

还是看到旧版时：按 `Ctrl + F5`（Mac 是 `Cmd + Shift + R`）强制刷新，
或者在网址后面随便加个参数，例如 `https://yxkshsh.github.io/artworks/?v=2`。

## 加新作品

**方式一：交互式脚本（推荐）**

```powershell
cd D:\project_study\artworks
python tools\add.py
```

按提示把文件拖进窗口，回答标题、英文小字、介绍；它会自动把文件复制进素材目录、
读出时长或尺寸、写进 `content.json`，最后问你要不要构建、要不要顺手发布。

也可以直接双击仓库根目录的 `添加作品.cmd`，效果一样。

**方式二：手动编辑 content.json**

1. 把文件放进素材目录（默认 `D:\下载\素材`）。
2. 在 `content.json` 的 `films` / `stills` 里加一条，字段可以参考已有条目：
   视频用 `slug / title / en / desc / src / poster_at`，
   图片用 `slug / title / sub / src / desc`（可选 `crop_bottom`）。
3. 构建并发布：

```bash
python tools/build.py
git add -A
git commit -m "add: 新作品"
git push
```

`slug` 决定网址和文件名，不能重复；顺序就是页面上的顺序，编号会自动重排。

GitHub Pages 会在推送后一分钟左右自动更新。

## 说明

- 视频统一转码为 H.264 + AAC，并用 `+faststart` 让首帧尽快出现；
  原片若是 HEVC（苹果设备、剪映常见），Chrome 默认放不了。
- 转码需要 ffmpeg：`pip install imageio-ffmpeg` 之后脚本会自动找到它。
- 页面没有任何外部依赖：不加载 CDN、字体或统计脚本，断网也能打开。
- 带第三方水印的素材没有放进公开页面，清单见 `media/manifest.json` 的 `excluded`。
- 图片与视频均为 AI 生成；转载或商用请先联系作者。
