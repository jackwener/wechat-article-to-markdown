import re

import pytest
from bs4 import BeautifulSoup

from wechat_article_to_markdown import (
    code_placeholder,
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
    html = f"<p>before</p><p>{code_placeholder(0)}</p><p>after</p>"
    md = convert_to_markdown(html, [{"lang": "python", "code": "print(1)"}])

    assert "```python" in md
    assert "print(1)" in md
    assert "CODEBLOCK-PLACEHOLDER" not in md


def test_convert_to_markdown_restores_more_than_ten_blocks() -> None:
    # 占位符 -1 曾是 -10..-19 的前缀，升序 str.replace() 会在替换第 1 块时
    # 吃掉后者的前缀，只留下末位数字。11 块以上才能暴露这个问题。
    blocks = [{"lang": "python", "code": f"print({i})"} for i in range(23)]
    html = "".join(f"<p>{code_placeholder(i)}</p>" for i in range(len(blocks)))

    md = convert_to_markdown(html, blocks)

    assert "CODEBLOCK-PLACEHOLDER" not in md
    for i in range(len(blocks)):
        assert f"print({i})" in md
    # 每块恰好还原一次，没有被别的块覆盖
    assert md.count("```python") == len(blocks)
    # 没有替换后残留的裸数字行
    assert not re.search(r"^\d+$", md, re.MULTILINE)


def test_process_content_drops_empty_darkmode_pre() -> None:
    # 微信注入的 <pre class="js_darkmode__N"> 不含文本、也不在
    # code-snippet__fix 内，若不清理会被转成空的围栏代码块。
    html = """
    <div id="js_content">
      <div class="code-snippet__fix">
        <pre data-lang="python"></pre>
        <code>print('hello')</code>
      </div>
      <section><pre class="js_darkmode__7"></pre></section>
      <p>tail</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    content_html, code_blocks, _ = process_content(soup)
    md = convert_to_markdown(content_html, code_blocks)

    assert "js_darkmode" not in content_html
    # 只有真实代码块的那一对围栏
    assert md.count("```") == 2
    assert "print('hello')" in md
