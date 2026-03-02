---
name: wechat-article-to-markdown
description: 抓取微信公众号文章并转换为 Markdown 格式，使用 Camoufox 反检测浏览器避免验证拦截
---

# WeChat Article to Markdown

将微信公众号文章抓取并转换为干净的 Markdown 文件。

## 使用场景

当需要将微信公众号文章保存为 Markdown 格式时使用此 skill。适用于：
- 归档微信文章为本地 Markdown
- 提取文章内容用于后续处理（如 AI 摘要、知识库导入）
- 批量保存公众号内容

## 前置条件

- Python 3.10+ 已安装
- 依赖已安装 (`pip install -r requirements.txt`)
- Camoufox 浏览器已下载 (`python -m camoufox fetch`)

## 使用方法

```bash
cd /Users/jakevin/kabi-reader/wechat-article-to-markdown
python main.py "<微信文章URL>"
```

**输入**: 微信公众号文章 URL (形如 `https://mp.weixin.qq.com/s/...`)

**输出**: `output/<文章标题>/` 目录下：
- `<文章标题>.md` — Markdown 文件，包含标题、作者、发布时间、原文链接和正文
- `images/` — 文章配图（自动从微信 CDN 下载到本地）

## 功能特性

1. **反检测抓取** — 使用 Camoufox (修改版 Firefox) 通过微信环境检测，避免 "环境异常" 验证
2. **元数据提取** — 标题、公众号名称、发布时间、原文链接
3. **图片本地化** — 微信 CDN 图片自动下载到本地 `images/` 目录，Markdown 引用本地路径
4. **代码块处理** — 正确提取微信 `code-snippet` 代码块，识别语言标识，过滤 CSS counter 垃圾
5. **HTML → Markdown** — 使用 markdownify 转换，保留标题层级、列表、引用块、粗体等格式
6. **并发下载** — 图片并发下载（默认 5 并发），加速处理

## 限制

- 部分文章的代码块使用图片/SVG 渲染而非文本，这些无法提取为代码
- 需要文章的公开 URL（`mp.weixin.qq.com` 域名）
