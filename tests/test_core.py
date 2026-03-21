import pytest
from bs4 import BeautifulSoup

from wechat_article_to_markdown import (
    convert_to_markdown,
    extract_publish_time,
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
