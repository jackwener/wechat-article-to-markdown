---
name: wechat-article-to-markdown
description: 抓取微信公众号文章并转换为 Markdown 格式，支持图片下载、代码块提取和元数据保留
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - wechat-to-md
    install:
      - kind: node
        package: "wechat-article-to-markdown"
        bins: [wechat-to-md]
    os: [macos, linux]
    homepage: https://github.com/jackwener/wechat-article-to-markdown
tags:
  - wechat
  - weixin
  - markdown
  - content-extraction
  - scraper
---

# WeChat Article to Markdown

将微信公众号文章抓取并转换为干净的 Markdown 文件。

## 使用场景

当需要将微信公众号文章保存为 Markdown 格式时使用此 skill。适用于：
- 归档微信文章为本地 Markdown
- 提取文章内容用于后续处理（如 AI 摘要、知识库导入）
- 批量保存公众号内容

## 安装

```bash
npm install -g wechat-article-to-markdown
```

## 使用方法

```bash
wechat-to-md "<微信文章URL>"
```

**输入**: 微信公众号文章 URL (形如 `https://mp.weixin.qq.com/s/...`)

**输出**: `output/<文章标题>/` 目录下：
- `<文章标题>.md` — Markdown 文件，包含标题、作者、发布时间、原文链接和正文
- `images/` — 文章配图（自动从微信 CDN 下载到本地）

## 功能特性

1. **元数据提取** — 标题、公众号名称、发布时间、原文链接
2. **图片本地化** — 微信 CDN 图片自动下载到本地 `images/` 目录，Markdown 引用本地路径
3. **代码块处理** — 正确提取微信 `code-snippet` 代码块，识别语言标识，过滤 CSS counter 垃圾
4. **HTML → Markdown** — 使用 turndown 转换，保留标题层级、列表、引用块、粗体等格式
5. **并发下载** — 图片并发下载（默认 5 并发），加速处理

## 常见用法

```bash
# 抓取单篇文章
wechat-to-md "https://mp.weixin.qq.com/s/xxxxxxxx"

# 配合 AI 使用：抓取后提取正文用于摘要
wechat-to-md "https://mp.weixin.qq.com/s/xxxxxxxx" && cat output/*/文章标题.md
```

## 限制

- 微信有反爬机制，频繁请求可能触发验证码（返回 "环境异常"）
- 部分文章的代码块使用图片/SVG 渲染而非文本，这些无法提取为代码
- 需要文章的公开 URL（`mp.weixin.qq.com` 域名）
