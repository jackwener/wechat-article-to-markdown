---
name: wechat-article-to-markdown
description: Fetch WeChat Official Account (微信公众号) articles from mp.weixin.qq.com and convert to Markdown. 微信文章转 Markdown 工具，支持图片去重和 Obsidian 直接导入。
author: jackwener
version: "1.1.0"
tags:
  - wechat
  - 微信
  - 微信文章
  - 公众号
  - mp.weixin.qq.com
  - markdown
  - article
  - converter
  - cli
  - obsidian
  - 知识库
  - 图片去重
---

# WeChat Article to Markdown

Fetch a WeChat Official Account article and convert it to a clean Markdown file.

## When to use

Use this skill when you need to save WeChat articles as Markdown for:
- Personal archive
- AI summarization input
- Knowledge base ingestion (Obsidian, Logseq, etc.)

## Prerequisites

- Python 3.8+

```bash
# Install
uv tool install wechat-article-to-markdown
# Or: pipx install wechat-article-to-markdown
```

## Usage

### Basic: Fetch & Convert

```bash
wechat-article-to-markdown "<WECHAT_ARTICLE_URL>"
```

Input URL format:
- `https://mp.weixin.qq.com/s/...`

Output files:
- `<cwd>/output/<article-title>/<article-title>.md`
- `<cwd>/output/<article-title>/images/*`

### Advanced: Import into Obsidian with Image Deduplication

For knowledge base users (Obsidian, Logseq), use the companion script to:
1. Automatically deduplicate images by MD5 hash
2. Store all images in a central `wechat-images/` folder in your vault root
3. Fix image paths in Markdown to use correct relative paths

```bash
# Prerequisites: clone the dedup script alongside your vault
# git clone https://github.com/YOUR_FORK/wechat-article-to-markdown.git

# Step 1: Fetch article (saves to Desktop by default)
wechat-article-to-markdown "<URL>" -o ~/Desktop/

# Step 2: Import into Obsidian with deduplication
python3 wechat-dedup.py \
  ~/Desktop/<article-folder>/ \
  ~/Documents/Obsidian\ Vault/ \
  "AI/<article-category>/"

# Example:
python3 wechat-dedup.py \
  ~/Desktop/从_写代码_到_管AI团队_：OpenAI\ Codex\ App实战指南/ \
  ~/Documents/Obsidian\ Vault/ \
  "AI/Codex App实战指南/"
```

**`wechat-dedup.py`** (companion script, place in the same repo):

```python
#!/usr/bin/env python3
"""
wechat-dedup.py - Deduplicate WeChat article images and prepare for Obsidian import.

Usage:
    python3 wechat-dedup.py <article_dir> <vault_root> [vault_subdir]

Args:
    article_dir  : Path to the downloaded article folder (contains .md + images/)
    vault_root   : Path to your Obsidian vault root
    vault_subdir : (optional) Where to save the article inside the vault,
                   e.g. "AI/Tech/" or "Knowledge/"

Effect:
    - Images are copied to <vault_root>/wechat-images/ with MD5 hash filenames
    - Duplicate images (same content) are skipped (only stored once)
    - Markdown image paths are rewritten to relative paths from article location
      to vault root, e.g. ../../wechat-images/<hash>.ext
    - Article .md is copied to the target vault subdirectory

Notes:
    - Folder name MUST NOT start with "." (Obsidian ignores dotfolders)
    - Use "wechat-images/" not ".wechat-images/" in vault root
    - Relative path depth is auto-calculated, works from any vault subdirectory
"""
import os
import sys
import hashlib
import shutil
import re

def main():
    if len(sys.argv) < 3:
        print("Usage: wechat-dedup.py <article_dir> <vault_root> [vault_subdir]")
        sys.exit(1)

    article_dir = sys.argv[1]
    vault_root = sys.argv[2]
    vault_subdir = sys.argv[3] if len(sys.argv) > 3 else ""

    central_images = os.path.join(vault_root, "wechat-images")
    images_dir = os.path.join(article_dir, "images")
    md_file = None

    # Find .md file in article dir
    for f in os.listdir(article_dir):
        if f.endswith(".md"):
            md_file = os.path.join(article_dir, f)
            break

    if not md_file:
        print("❌ No Markdown file found")
        sys.exit(1)

    # Destination path for the .md file
    if vault_subdir:
        dest_dir = os.path.join(vault_root, vault_subdir)
        os.makedirs(dest_dir, exist_ok=True)
        dest_md = os.path.join(dest_dir, os.path.basename(md_file))
    else:
        dest_md = md_file

    shutil.copy2(md_file, dest_md)

    os.makedirs(central_images, exist_ok=True)

    # Calculate relative path: from article.md dir → vault root
    rel_prefix = os.path.relpath(vault_root, os.path.dirname(dest_md)).replace(os.sep, "/") + "/"

    replacements = {}
    for fname in os.listdir(images_dir):
        fpath = os.path.join(images_dir, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "rb") as f:
            h = hashlib.md5(f.read()).hexdigest()
        ext = fname.rsplit(".", 1)[-1]
        deduped = f"{h}.{ext}"
        dest_path = os.path.join(central_images, deduped)
        if not os.path.exists(dest_path):
            shutil.copy2(fpath, dest_path)
            print(f"  ✅ {deduped}")
        else:
            print(f"  ⏭️  already exists: {deduped}")
        # Store full relative path for the replacement
        replacements[fname] = rel_prefix + "wechat-images/" + deduped

    # Rewrite image paths in .md
    with open(dest_md, "r") as f:
        content = f.read()
    for orig, resolved in replacements.items():
        content = content.replace(f"images/{orig}", resolved)
    with open(dest_md, "w") as f:
        f.write(content)

    print(f"\n✅ Done! {len(replacements)} images deduplicated.")
    print(f"   Vault images: {central_images}")
    print(f"   Article: {dest_md}")

if __name__ == "__main__":
    main()
```

## Features

1. Anti-detection fetch with Camoufox
2. Metadata extraction (title, account name, publish time, source URL)
3. Image localization to local files
4. WeChat code-snippet extraction and fenced code block output
5. HTML to Markdown conversion via markdownify
6. Concurrent image downloading
7. **Image deduplication** via MD5 hash (same image across articles = stored once)
8. **Obsidian/Logseq ready** — auto-fixes relative image paths for any vault subdirectory

## Limitations

- Some code snippets are image/SVG rendered and cannot be extracted as source code
- Public `mp.weixin.qq.com` URL is required
- Vault must NOT use a dotfolder (`.wechat-images/`) for image storage — Obsidian ignores dotfolders
