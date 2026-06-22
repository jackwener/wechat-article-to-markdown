# wechat-article-to-markdown

Fetch WeChat Official Account articles and convert them to clean Markdown.

[English](#features) | [中文](#功能特性)

## Features

- Anti-detection fetching with Camoufox
- Extract article metadata (title, account name, publish time, source URL)
- Convert WeChat article HTML to Markdown
- Download article images to local `images/` and rewrite links
- Handle WeChat `code-snippet` blocks with language fences

## Installation

```bash
# Recommended: uv tool (fast, isolated)
uv tool install wechat-article-to-markdown

# Or: pipx
pipx install wechat-article-to-markdown
```

Or from source:

```bash
git clone git@github.com:jackwener/wechat-article-to-markdown.git
cd wechat-article-to-markdown
uv sync
```

## Usage

```bash
# Installed CLI
wechat-article-to-markdown "https://mp.weixin.qq.com/s/xxxxxxxx"

# Increase navigation timeout for slow WeChat article loads
wechat-article-to-markdown "https://mp.weixin.qq.com/s/xxxxxxxx" --timeout 120

# Run in repo with uv
uv run wechat-article-to-markdown "https://mp.weixin.qq.com/s/xxxxxxxx"

# Backward-compatible local entry
uv run main.py "https://mp.weixin.qq.com/s/xxxxxxxx"
```

Output structure:

```text
output/
└── <article-title>/
    ├── <article-title>.md
    └── images/
        ├── img_001.png
        ├── img_002.png
        └── ...
```


## Testing

```bash
# Unit tests (default CI path)
uv run --with pytest pytest -q -m "not e2e"

# Live E2E against real WeChat articles
WECHAT_E2E_URLS="https://mp.weixin.qq.com/s/Y7dyRC7CJ09miHWU6LBzBA,https://mp.weixin.qq.com/s/xxxxxxxx" \
  uv run --with pytest pytest -q -m e2e -s
```

`e2e` tests require network and browser runtime, so they run via manual GitHub Actions workflow `.github/workflows/e2e.yml`.

## Use as AI Agent Skill

This project ships with [`SKILL.md`](./SKILL.md), so AI agents can discover and use this tool workflow.

### [Skills CLI](https://github.com/vercel-labs/skills) (Recommended)

```bash
npx skills add jackwener/wechat-article-to-markdown
```

| Flag | Description |
| --- | --- |
| `-g` | Install globally (user-level, shared across projects) |
| `-a claude-code` | Target a specific agent |
| `-y` | Non-interactive mode |

### Manual Install

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/wechat-article-to-markdown.git \
  .agents/skills/wechat-article-to-markdown
```

```bash
# Claude Code user-level skills directory (global)
mkdir -p ~/.claude/skills/wechat-article-to-markdown
curl -o ~/.claude/skills/wechat-article-to-markdown/SKILL.md \
  https://raw.githubusercontent.com/jackwener/wechat-article-to-markdown/main/SKILL.md
```

After adding the file, restart Claude Code to reload skills.

### ~~OpenClaw / ClawHub~~ (Deprecated)

> ⚠️ ClawHub install method is deprecated and no longer supported. Use [Skills CLI](#skills-cli-recommended) or Manual Install above.

## PyPI Publishing (GitHub Actions)

Repository: `jackwener/wechat-article-to-markdown`
Workflow: `.github/workflows/release.yml`
Environment: `pypi`

`release.yml` triggers on `v*` tags, runs unit tests + live e2e tests, then publishes to PyPI with trusted publishing (`id-token: write`).

For release e2e targets, set repository variable `RELEASE_E2E_URLS` (comma-separated article URLs).  
If not set, workflow falls back to `https://mp.weixin.qq.com/s/Y7dyRC7CJ09miHWU6LBzBA`.

---

## 功能特性

- 使用 Camoufox 进行反检测抓取
- 提取标题、公众号名称、发布时间、原文链接
- 将微信公众号文章 HTML 转换为 Markdown
- 下载图片到本地 `images/` 并自动替换链接
- 处理微信 `code-snippet` 代码块并保留语言标识

## 安装

```bash
# 推荐：uv tool
uv tool install wechat-article-to-markdown

# 或者：pipx
pipx install wechat-article-to-markdown
```

## 使用示例

```bash
wechat-article-to-markdown "https://mp.weixin.qq.com/s/xxxxxxxx"

# 如遇页面加载较慢，可调大导航超时时间（单位秒）
wechat-article-to-markdown "https://mp.weixin.qq.com/s/xxxxxxxx" --timeout 120
```

## 作为 AI Agent Skill 使用

项目自带 [`SKILL.md`](./SKILL.md)，可供支持 `.agents/skills/` 约定的 Agent 自动发现。

### [Skills CLI](https://github.com/vercel-labs/skills)（推荐）

```bash
npx skills add jackwener/wechat-article-to-markdown
```

| 参数 | 说明 |
| --- | --- |
| `-g` | 全局安装（用户级别，跨项目共享） |
| `-a claude-code` | 指定目标 Agent |
| `-y` | 非交互模式 |

### 手动安装

```bash
mkdir -p ~/.claude/skills/wechat-article-to-markdown
curl -o ~/.claude/skills/wechat-article-to-markdown/SKILL.md \
  https://raw.githubusercontent.com/jackwener/wechat-article-to-markdown/main/SKILL.md
```

### ~~OpenClaw / ClawHub~~（已过时）

> ⚠️ ClawHub 安装方式已过时，不再支持。请使用上方的 Skills CLI 或手动安装。

## License

MIT
