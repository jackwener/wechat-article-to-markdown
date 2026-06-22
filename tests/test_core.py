import asyncio

import pytest
from bs4 import BeautifulSoup

import wechat_article_to_markdown as watm
from wechat_article_to_markdown import (
    convert_to_markdown,
    extract_publish_time,
    fetch_article,
    format_timestamp,
    normalize_wechat_url,
    process_content,
    replace_image_urls,
)


# ------------------------------------------------------------------
# normalize_wechat_url
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Clean URL – no change
        (
            "https://mp.weixin.qq.com/s?__biz=ABC&mid=123&idx=1&sn=xyz",
            "https://mp.weixin.qq.com/s?__biz=ABC&mid=123&idx=1&sn=xyz",
        ),
        # Backslash-escaped separators (zsh url-quote-magic)
        (
            r"https://mp.weixin.qq.com/s\?__biz=ABC\&mid=123",
            "https://mp.weixin.qq.com/s?__biz=ABC&mid=123",
        ),
        # HTML entity &amp;
        (
            "https://mp.weixin.qq.com/s?__biz=ABC&amp;mid=123",
            "https://mp.weixin.qq.com/s?__biz=ABC&mid=123",
        ),
        # Wrapped in double quotes
        (
            '"https://mp.weixin.qq.com/s?a=1"',
            "https://mp.weixin.qq.com/s?a=1",
        ),
        # Wrapped in angle brackets
        (
            "<https://mp.weixin.qq.com/s?a=1>",
            "https://mp.weixin.qq.com/s?a=1",
        ),
        # http → https
        (
            "http://mp.weixin.qq.com/s?a=1",
            "https://mp.weixin.qq.com/s?a=1",
        ),
        # Bare hostname (no scheme)
        (
            "mp.weixin.qq.com/s?a=1",
            "https://mp.weixin.qq.com/s?a=1",
        ),
        # // prefix
        (
            "//mp.weixin.qq.com/s?a=1",
            "https://mp.weixin.qq.com/s?a=1",
        ),
        # Empty / None
        ("", ""),
        ("  ", ""),
    ],
)
def test_normalize_wechat_url(raw: str, expected: str) -> None:
    assert normalize_wechat_url(raw) == expected


def test_extract_publish_time_supports_multiple_patterns() -> None:
    ts = 1700000000
    expected = format_timestamp(ts)

    assert extract_publish_time(f"create_time:'{ts}'") == expected
    assert extract_publish_time(f'create_time:"{ts}"') == expected
    assert extract_publish_time(f"create_time = {ts}") == expected
    assert extract_publish_time(f"create_time:JsDecode('{ts}')") == expected


def test_replace_image_urls_handles_parentheses() -> None:
    md = (
        "![](https://example.com/a_(1).png)\n"
        "![alt](https://example.com/b.png?x=1&y=2)"
    )
    url_map = {
        "https://example.com/a_(1).png": "images/a.png",
        "https://example.com/b.png?x=1&y=2": "images/b.png",
    }

    out = replace_image_urls(md, url_map)
    assert "![](images/a.png)" in out
    assert "![alt](images/b.png)" in out


def test_process_content_extracts_code_and_images() -> None:
    html = """
    <div id="js_content">
      <img data-src="https://example.com/1.png" />
      <img src="https://example.com/1.png" />
      <div class="code-snippet__fix">
        <pre data-lang="python"></pre>
        <code>print('hello')</code>
      </div>
      <script>bad()</script>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    content_html, code_blocks, img_urls = process_content(soup)

    assert "script" not in content_html
    assert img_urls == ["https://example.com/1.png"]
    assert code_blocks == [{"lang": "python", "code": "print('hello')"}]


def test_convert_to_markdown_restores_code_block() -> None:
    html = "<p>before</p><p>CODEBLOCK-PLACEHOLDER-0</p><p>after</p>"
    md = convert_to_markdown(html, [{"lang": "python", "code": "print(1)"}])

    assert "```python" in md
    assert "print(1)" in md
    assert "CODEBLOCK-PLACEHOLDER-0" not in md


def test_fetch_article_passes_navigation_timeout(monkeypatch, tmp_path) -> None:
    captured = {}

    class FakePage:
        async def goto(self, url, wait_until, timeout):
            captured["url"] = url
            captured["wait_until"] = wait_until
            captured["timeout"] = timeout

        async def wait_for_selector(self, selector, timeout):
            captured["selector"] = selector
            captured["selector_timeout"] = timeout

        async def content(self):
            return """
            <html>
              <h1 id="activity-name">Test Article</h1>
              <a id="js_name">Test Account</a>
              <div id="js_content"><p>Hello</p></div>
            </html>
            """

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

    class FakeCamoufox:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return FakeBrowser()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_download_all_images(img_urls, img_dir):
        return {}

    monkeypatch.setattr(watm, "AsyncCamoufox", FakeCamoufox)
    monkeypatch.setattr(watm, "download_all_images", fake_download_all_images)

    asyncio.run(
        fetch_article(
            "https://mp.weixin.qq.com/s/test",
            output_dir=tmp_path,
            timeout_ms=120000,
        )
    )

    assert captured == {
        "url": "https://mp.weixin.qq.com/s/test",
        "wait_until": "domcontentloaded",
        "timeout": 120000,
        "selector": "#js_content",
        "selector_timeout": 10000,
    }
