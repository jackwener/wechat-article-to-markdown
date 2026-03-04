# wechat-article-to-markdown

微信公众号文章抓取 & Markdown 转换工具。

使用 **cheerio + axios + turndown** 将微信公众号文章转换为干净的 Markdown 文件，图片自动下载到本地。

> 🔗 **同系列 AI 工具**: [bilibili-cli](https://github.com/jackwener/bilibili-cli) — B站命令行工具，支持视频信息、字幕、搜索、互动，同样为 AI Agent 设计。

## 功能

- 📄 **文章抓取** — 输入 URL，输出结构化 Markdown
- 🖼 **图片本地化** — 微信 CDN 图片并发下载到本地，Markdown 引用相对路径
- 💻 **代码块提取** — 正确处理微信 `code-snippet` 代码块，保留语言标识
- 📅 **元数据保留** — 标题、公众号名称、发布时间、原文链接
- 🧹 **格式清理** — 去除 `&nbsp;`、多余空行、行尾空格

## 快速开始

```bash
# 安装依赖
npm install

# 抓取文章
node index.js "https://mp.weixin.qq.com/s/xxxxxxxx"
```

输出目录结构：

```
output/
└── 文章标题/
    ├── 文章标题.md
    └── images/
        ├── img_001.png
        ├── img_002.png
        └── ...
```

## 输出示例

```markdown
# 文章标题

> 公众号: xxx
> 发布时间: 2026-02-28 11:42
> 原文链接: https://mp.weixin.qq.com/s/...

---

正文内容...

![](images/img_001.png)
```

## 技术方案

| 功能 | 方案 |
|------|------|
| HTTP 请求 | axios + 浏览器 UA 伪装 |
| HTML 解析 | cheerio (jQuery-like selector) |
| HTML → Markdown | turndown |
| 图片下载 | axios arraybuffer + 并发控制 |

### 微信文章 HTML 关键结构

| 元素 | 选择器 |
|------|--------|
| 标题 | `#activity-name` |
| 公众号名 | `#js_name` |
| 发布时间 | JS 变量 `create_time` |
| 正文 | `#js_content` |
| 图片 | `img[data-src]` (懒加载) |
| 代码块 | `.code-snippet__fix` |

## 限制

- 微信反爬机制可能导致验证码拦截（频繁请求时）
- 部分代码块用图片/SVG 渲染，无法提取文本
- 仅支持公开可访问的文章 URL

## AI 助手集成

### Claude Code / Antigravity

```bash
# 克隆到项目的 skills 目录
mkdir -p .agents/skills
git clone git@github.com:jackwener/wechat-article-to-markdown.git .agents/skills/wechat-article-to-markdown

# 或者只复制 SKILL.md
curl -o .agents/skills/wechat-article-to-markdown/SKILL.md \
  https://raw.githubusercontent.com/jackwener/wechat-article-to-markdown/main/SKILL.md
```

添加后，支持 `.agents/skills/` 的 AI Agent 会自动发现并使用本工具。

### OpenClaw / ClawHub

官方支持 [OpenClaw](https://openclaw.ai) 和 [ClawHub](https://docs.openclaw.ai/tools/clawhub) 生态。通过 ClawHub 安装：

```bash
clawhub install wechat-article-to-markdown
```

安装后即可在 OpenClaw 中直接使用。SKILL.md 同时兼容 Claude Code 和 OpenClaw 两个生态。

## License

MIT
