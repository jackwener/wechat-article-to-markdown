from __future__ import annotations

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "camoufox[geoip]",
#     "markdownify",
#     "beautifulsoup4",
#     "httpx",
# ]
# ///

"""
WeChat Article to Markdown — 微信公众号文章抓取 & Markdown 转换工具

使用 Camoufox (反检测浏览器) + BeautifulSoup + markdownify 将微信公众号文章
转换为干净的 Markdown 文件，图片自动下载到本地。
"""

import argparse
import asyncio
import html as html_mod
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
import markdownify
from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

# Default output directory (current working directory / output)
DEFAULT_OUTPUT_DIR = Path.cwd() / "output"
IMAGE_CONCURRENCY = 5


# ============================================================
# Helpers
# ============================================================


def normalize_wechat_url(raw: str) -> str:
    """Normalize a pasted WeChat article URL.

    Handles common issues:
    - Terminal/zsh auto-escaped backslashes (``\\&``, ``\\?``)
    - HTML entities (``&amp;``)
    - Missing or http scheme on mp.weixin.qq.com
    - Stray quote wrappers from copy-paste
    """
    s = str(raw or "").strip()
    if not s:
        return s

    # Strip wrapping quotes / angle brackets
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()

    # Remove backslash escapes before URL-significant characters
    s = re.sub(r"\\+([:/&?=#%])", r"\1", s)

    # Decode HTML entities
    s = html_mod.unescape(s)

    # Allow bare hostnames
    if s.startswith("mp.weixin.qq.com/") or s.startswith("//mp.weixin.qq.com/"):
        s = "https://" + s.lstrip("/")

    # Force https for mp.weixin.qq.com
    parsed = urlparse(s)
    if parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() == "mp.weixin.qq.com":
        s = urlunparse(("https", "mp.weixin.qq.com", parsed.path, parsed.params, parsed.query, parsed.fragment))

    return s


def extract_publish_time(html: str) -> str:
    """从 HTML script 标签中提取发布时间"""
    # JsDecode 格式
    m = re.search(r"create_time\s*:\s*JsDecode\('([^']+)'\)", html)
    if m:
        val = m.group(1)
        try:
            ts = int(val)
            if ts > 0:
                return format_timestamp(ts)
        except ValueError:
            return val

    # 纯数字格式
    m = re.search(r"create_time\s*:\s*'(\d+)'", html)
    if m:
        return format_timestamp(int(m.group(1)))

    # 兼容双引号与 = 赋值风格
    m = re.search(r'create_time\s*[:=]\s*["\']?(\d+)["\']?', html)
    if m:
        return format_timestamp(int(m.group(1)))

    return ""


def format_timestamp(ts: int) -> str:
    """Unix timestamp (秒) -> 'YYYY-MM-DD HH:mm:ss' (Asia/Shanghai, UTC+8)"""
    from datetime import datetime, timezone, timedelta

    tz = timezone(timedelta(hours=8))
    dt = datetime.fromtimestamp(ts, tz=tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# Image Downloading
# ============================================================


async def download_image(
    client: httpx.AsyncClient,
    img_url: str,
    img_dir: Path,
    index: int,
    semaphore: asyncio.Semaphore,
) -> tuple[str, str | None]:
    """下载单张图片到本地，返回 (remote_url, local_relative_path | None)"""
    async with semaphore:
        try:
            url = img_url if not img_url.startswith("//") else f"https:{img_url}"

            # 推断扩展名
            ext_match = re.search(r"wx_fmt=(\w+)", url) or re.search(
                r"\.(\w{3,4})(?:\?|$)", url
            )
            ext = ext_match.group(1) if ext_match else "png"

            filename = f"img_{index:03d}.{ext}"
            filepath = img_dir / filename

            resp = await client.get(
                url,
                headers={"Referer": "https://mp.weixin.qq.com/"},
                timeout=15.0,
            )
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            return img_url, f"images/{filename}"
        except Exception as e:
            print(f"  ⚠ 图片下载失败: {e}")
            return img_url, None


async def download_all_images(
    img_urls: list[str], img_dir: Path
) -> dict[str, str]:
    """并发下载所有图片，返回 {remote_url: local_path} 映射"""
    if not img_urls:
        return {}

    print(f"🖼  下载 {len(img_urls)} 张图片 (并发 {IMAGE_CONCURRENCY})...")
    semaphore = asyncio.Semaphore(IMAGE_CONCURRENCY)

    async with httpx.AsyncClient() as client:
        tasks = [
            download_image(client, url, img_dir, i + 1, semaphore)
            for i, url in enumerate(img_urls)
        ]
        results = await asyncio.gather(*tasks)

    url_map = {}
    for remote_url, local_path in results:
        if local_path:
            url_map[remote_url] = local_path

    downloaded = sum(1 for v in url_map.values() if v)
    print(f"  ✅ {downloaded}/{len(img_urls)}")
    return url_map


# ============================================================
# Content Processing
# ============================================================


def extract_metadata(soup: BeautifulSoup, html: str) -> dict:
    """提取文章元数据: 标题、作者、发布时间"""
    title_el = soup.select_one("#activity-name")
    author_el = soup.select_one("#js_name")
    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "author": author_el.get_text(strip=True) if author_el else "",
        "publish_time": extract_publish_time(html),
    }


def process_content(soup: BeautifulSoup) -> tuple[str, list[dict], list[str]]:
    """
    预处理正文 DOM：修复图片、处理代码块、移除噪声元素。
    返回 (content_html, code_blocks, img_urls)
    """
    content_el = soup.select_one("#js_content")
    if not content_el:
        return "", [], []

    # 1) 图片: data-src -> src (微信懒加载)
    for img in content_el.find_all("img"):
        data_src = img.get("data-src")
        if data_src:
            img["src"] = data_src

    # 2) 代码块: 提取 code-snippet__fix 内容，替换为占位符
    code_blocks = []
    for el in content_el.select(".code-snippet__fix"):
        # 移除行号
        for line_idx in el.select(".code-snippet__line-index"):
            line_idx.decompose()

        pre = el.select_one("pre[data-lang]")
        lang = pre.get("data-lang", "") if pre else ""

        lines = []
        for code_tag in el.find_all("code"):
            text = code_tag.get_text()
            # 跳过 CSS counter 泄漏的垃圾行
            if re.match(r"^[ce]?ounter\(line", text):
                continue
            lines.append(text)

        if not lines:
            lines.append(el.get_text())

        placeholder = f"CODEBLOCK-PLACEHOLDER-{len(code_blocks)}"
        code_blocks.append({"lang": lang, "code": "\n".join(lines)})
        el.replace_with(soup.new_tag("p", string=placeholder))

    # 3) 移除噪声元素
    for sel in ("script", "style", ".qr_code_pc", ".reward_area"):
        for tag in content_el.select(sel):
            tag.decompose()

    # 4) 收集图片 URL（去重）
    img_urls = []
    seen = set()
    for img in content_el.find_all("img", src=True):
        src = img["src"]
        if src not in seen:
            seen.add(src)
            img_urls.append(src)

    return str(content_el), code_blocks, img_urls


def convert_to_markdown(content_html: str, code_blocks: list[dict]) -> str:
    """HTML -> Markdown，还原代码块，清理格式"""
    md = markdownify.markdownify(
        content_html,
        heading_style="ATX",
        bullets="-",
        convert=["p", "h1", "h2", "h3", "h4", "h5", "h6",
                 "strong", "em", "a", "img", "ul", "ol", "li",
                 "blockquote", "br", "hr", "table", "thead",
                 "tbody", "tr", "th", "td", "pre", "code"],
    )

    # 还原代码块占位符
    for i, block in enumerate(code_blocks):
        placeholder = f"CODEBLOCK-PLACEHOLDER-{i}"
        fenced = f"\n```{block['lang']}\n{block['code']}\n```\n"
        md = md.replace(placeholder, fenced)

    # 清理 &nbsp; 残留
    md = md.replace("\u00a0", " ")
    # 清理多余空行
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    # 清理行尾多余空格
    md = re.sub(r"[ \t]+$", "", md, flags=re.MULTILINE)

    return md


def replace_image_urls(md: str, url_map: dict[str, str]) -> str:
    """替换 Markdown 中的远程图片链接为本地路径"""
    # Use exact URL matching to avoid regex edge cases such as ')' in URL.
    for remote_url, local_path in url_map.items():
        pattern = re.compile(r"!\[([^\]]*)\]\(" + re.escape(remote_url) + r"\)")
        md = pattern.sub(lambda m: f"![{m.group(1)}]({local_path})", md)
    return md


def build_markdown(meta: dict, body_md: str) -> str:
    """拼接最终 Markdown 文件内容"""
    lines = [f"# {meta['title']}", ""]
    if meta.get("author"):
        lines.append(f"> 公众号: {meta['author']}")
    if meta.get("publish_time"):
        lines.append(f"> 发布时间: {meta['publish_time']}")
    if meta.get("source_url"):
        lines.append(f"> 原文链接: {meta['source_url']}")
    if meta.get("author") or meta.get("publish_time") or meta.get("source_url"):
        lines.append("")
    lines.extend(["---", ""])
    return "\n".join(lines) + body_md


# ============================================================
# Main
# ============================================================


async def fetch_article(url: str, output_dir: Path | None = None) -> None:
    """
    抓取微信公众号文章并转换为 Markdown。

    Args:
        url: 微信文章 URL
        output_dir: 输出目录，默认为 DEFAULT_OUTPUT_DIR
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    print(f"🔄 正在抓取: {url}")

    # 使用 Camoufox 反检测浏览器获取完整 HTML
    print("🦊 启动 Camoufox 浏览器...")
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        # 等待正文加载
        try:
            await page.wait_for_selector("#js_content", timeout=10000)
        except Exception:
            pass  # 超时也继续尝试解析
        # 额外等待确保 JS 执行完毕
        await asyncio.sleep(2)
        html = await page.content()

    # 解析
    soup = BeautifulSoup(html, "html.parser")

    # 提取元数据
    meta = extract_metadata(soup, html)
    if not meta["title"]:
        print("❌ 未能提取到文章标题，可能触发了验证码")
        output_dir.mkdir(parents=True, exist_ok=True)
        debug_path = output_dir / "debug.html"
        debug_path.write_text(html, encoding="utf-8")
        print(f"已保存原始 HTML 到 {debug_path}")
        sys.exit(1)

    meta["source_url"] = url
    print(f"📄 标题: {meta['title']}")
    print(f"👤 作者: {meta['author']}")
    print(f"📅 时间: {meta['publish_time']}")

    # 处理正文
    content_html, code_blocks, img_urls = process_content(soup)
    if not content_html:
        print("❌ 未能提取到正文内容")
        sys.exit(1)

    # 转 Markdown
    md = convert_to_markdown(content_html, code_blocks)

    # 下载图片
    safe_title = re.sub(r'[/\\?%*:|"<>]', "_", meta["title"])[:80]
    article_dir = output_dir / safe_title
    img_dir = article_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    url_map = await download_all_images(img_urls, img_dir)
    md = replace_image_urls(md, url_map)

    # 写入文件
    result = build_markdown(meta, md)
    md_path = article_dir / f"{safe_title}.md"
    md_path.write_text(result, encoding="utf-8")

    print(f"✅ 已保存: {md_path}")
    print(f"📊 Markdown 约 {len(md)} 字符")


def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章抓取 & Markdown 转换工具"
    )
    parser.add_argument("url", help="微信公众号文章 URL")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录 (默认: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args()
    raw_url = args.url
    url = normalize_wechat_url(raw_url)
    if url != raw_url:
        print("ℹ️  已自动清理 URL 中的转义字符 / HTML 实体。")

    if not url.startswith("https://mp.weixin.qq.com/"):
        print("❌ 请输入有效的微信文章 URL (mp.weixin.qq.com)")
        print("提示：请用引号包住完整 URL；若粘贴后出现反斜杠转义，脚本会自动清理。")
        sys.exit(1)

    try:
        asyncio.run(fetch_article(url, output_dir=args.output))
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
