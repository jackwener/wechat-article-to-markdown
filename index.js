const axios = require("axios");
const cheerio = require("cheerio");
const TurndownService = require("turndown");
const fs = require("fs");
const path = require("path");

const url = process.argv[2];
if (!url) {
    console.error("Usage: node index.js <wechat-article-url>");
    process.exit(1);
}

// #8: URL 格式校验
if (!url.startsWith("https://mp.weixin.qq.com/")) {
    console.error("❌ 请输入有效的微信文章 URL (https://mp.weixin.qq.com/...)");
    process.exit(1);
}

const HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.47.2540(0x28002F31) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN",
    Accept:
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    Referer: "https://mp.weixin.qq.com/",
    Connection: "keep-alive",
};

const OUTPUT_DIR = path.join(__dirname, "output");
const IMAGE_CONCURRENCY = 5;

// ============================================================
// Helpers
// ============================================================

/**
 * 从 HTML script 标签中提取发布时间
 */
function extractPublishTime(html) {
    // 优先匹配 create_timestamp (Unix 时间戳，更可靠)
    const m0 = html.match(/create_timestamp\s*[:=]\s*['"]?(\d{10})['"]?/);
    if (m0) {
        const ts = parseInt(m0[1], 10);
        if (ts > 1000000000) {
            return formatTimestamp(ts);
        }
    }

    // 匹配 create_time: JsDecode('...')
    const m1 = html.match(/create_time\s*:\s*JsDecode\('([^']+)'\)/);
    if (m1) {
        const val = m1[1];
        // 如果已经是日期字符串格式 (包含 - 或 /)，直接返回
        if (/\d{4}[-/]\d{2}[-/]\d{2}/.test(val)) {
            return val;
        }
        // 否则尝试解析为时间戳
        const ts = parseInt(val, 10);
        if (!isNaN(ts) && ts > 1000000000) {
            return formatTimestamp(ts);
        }
    }

    // 匹配 create_time: '数字'
    const m2 = html.match(/create_time\s*:\s*['"](\d{10})['"]/);
    if (m2) {
        const ts = parseInt(m2[1], 10);
        if (ts > 1000000000) {
            return formatTimestamp(ts);
        }
    }
    return "";
}

/**
 * Unix timestamp (秒) -> "YYYY-MM-DD HH:mm:ss" (Asia/Shanghai)
 */
function formatTimestamp(ts) {
    const d = new Date(ts * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    // 使用 UTC+8 手动计算，避免 toLocaleString 格式不一致
    const offset = 8 * 60; // Asia/Shanghai = UTC+8
    const local = new Date(d.getTime() + offset * 60 * 1000);
    return `${local.getUTCFullYear()}-${pad(local.getUTCMonth() + 1)}-${pad(local.getUTCDate())} ${pad(local.getUTCHours())}:${pad(local.getUTCMinutes())}:${pad(local.getUTCSeconds())}`;
}

/**
 * 下载单张图片到本地
 */
async function downloadImage(imgUrl, imgDir, index) {
    try {
        if (imgUrl.startsWith("//")) imgUrl = "https:" + imgUrl;
        const ext =
            imgUrl.match(/wx_fmt=(\w+)/)?.[1] ||
            imgUrl.match(/\.(\w{3,4})(?:\?|$)/)?.[1] ||
            "png";
        const filename = `img_${String(index).padStart(3, "0")}.${ext}`;
        const filepath = path.join(imgDir, filename);

        const resp = await axios.get(imgUrl, {
            headers: { ...HEADERS, Referer: "https://mp.weixin.qq.com/" },
            responseType: "arraybuffer",
            timeout: 15000,
        });
        // #5: 使用异步写入避免阻塞 event loop
        await fs.promises.writeFile(filepath, resp.data);
        return filename;
    } catch (err) {
        console.warn(`  ⚠ 图片下载失败: ${err.message}`);
        return null;
    }
}

/**
 * 并发下载所有图片，返回 { [remoteUrl]: localPath } 映射
 */
async function downloadAllImages(imgUrls, imgDir) {
    const urlMap = {};
    if (imgUrls.length === 0) return urlMap;

    console.log(`🖼  下载 ${imgUrls.length} 张图片 (并发 ${IMAGE_CONCURRENCY})...`);

    // 分批并发
    for (let i = 0; i < imgUrls.length; i += IMAGE_CONCURRENCY) {
        const batch = imgUrls.slice(i, i + IMAGE_CONCURRENCY);
        const results = await Promise.all(
            batch.map((url, j) => downloadImage(url, imgDir, i + j + 1))
        );
        results.forEach((localFile, j) => {
            if (localFile) {
                urlMap[batch[j]] = `images/${localFile}`;
            }
        });
        process.stdout.write(
            `  ✅ ${Math.min(i + IMAGE_CONCURRENCY, imgUrls.length)}/${imgUrls.length}\r`
        );
    }
    console.log();
    return urlMap;
}

// ============================================================
// Content Processing
// ============================================================

/**
 * 提取文章元数据: 标题、作者、发布时间
 */
function extractMetadata($, html) {
    return {
        title: $("#activity-name").text().trim(),
        author: $("#js_name").text().trim(),
        publishTime: extractPublishTime(html),
    };
}

/**
 * 预处理正文 DOM：修复图片、处理代码块、移除噪声元素
 * 返回 { contentHtml, codeBlocks, imgUrls }
 */
function processContent($, contentEl) {
    // 1) 图片: data-src -> src (微信懒加载)
    contentEl.find("img").each((_, img) => {
        const dataSrc = $(img).attr("data-src");
        if (dataSrc) $(img).attr("src", dataSrc);
    });

    // 2) 代码块: 提取 code-snippet__fix 内容，替换为占位符
    // #6: 使用不含 Markdown 特殊字符的占位符，避免 turndown 转义问题
    const codeBlocks = [];
    contentEl.find(".code-snippet__fix").each((_, el) => {
        $(el).find(".code-snippet__line-index").remove();
        const lang = $(el).find("pre[data-lang]").attr("data-lang") || "";

        const lines = [];
        $(el)
            .find("code")
            .each((_, codeLine) => {
                const text = $(codeLine).text();
                // 跳过 CSS counter 泄漏的垃圾行
                if (/^[ce]?ounter\(line/.test(text)) return;
                lines.push(text);
            });
        if (lines.length === 0) lines.push($(el).text());

        const placeholder = `CODEBLOCK-PLACEHOLDER-${codeBlocks.length}`;
        codeBlocks.push({ lang, code: lines.join("\n") });
        $(el).replaceWith(`<p>${placeholder}</p>`);
    });

    // 3) 移除噪声元素
    contentEl.find("script, style, .qr_code_pc, .reward_area").remove();

    // #7: 在 DOM 阶段直接收集图片 URL，比从 Markdown 正则提取更可靠
    const imgUrls = [];
    const seen = new Set();
    contentEl.find("img[src]").each((_, img) => {
        const src = $(img).attr("src");
        if (src && !seen.has(src)) {
            seen.add(src);
            imgUrls.push(src);
        }
    });

    return { contentHtml: contentEl.html(), codeBlocks, imgUrls };
}

/**
 * HTML -> Markdown，还原代码块，清理格式
 */
function convertToMarkdown(contentHtml, codeBlocks) {
    const turndown = new TurndownService({
        headingStyle: "atx",
        codeBlockStyle: "fenced",
        bulletListMarker: "-",
    });
    turndown.addRule("linebreak", {
        filter: "br",
        replacement: () => "\n",
    });

    let md = turndown.turndown(contentHtml);

    // #6: 还原代码块占位符 (新占位符不含 Markdown 特殊字符，无需处理转义)
    codeBlocks.forEach((block, i) => {
        const placeholder = `CODEBLOCK-PLACEHOLDER-${i}`;
        const fenced = `\n\`\`\`${block.lang}\n${block.code}\n\`\`\`\n`;
        md = md.replace(placeholder, fenced);
    });

    // 清理 &nbsp; 残留
    md = md.replace(/\u00a0/g, " ");
    // 清理多余空行
    md = md.replace(/\n{4,}/g, "\n\n\n");
    // 清理行尾多余空格
    md = md.replace(/[ \t]+$/gm, "");

    return md;
}

/**
 * 替换 Markdown 中的远程图片链接为本地路径
 */
function replaceImageUrls(md, urlMap) {
    return md.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, imgUrl) => {
        const local = urlMap[imgUrl];
        return local ? `![${alt}](${local})` : match;
    });
}

/**
 * 拼接最终 Markdown 文件内容
 */
function buildMarkdown({ title, author, publishTime, sourceUrl }, bodyMd) {
    const header = [`# ${title}`, ""];
    if (author) header.push(`> 公众号: ${author}`);
    if (publishTime) header.push(`> 发布时间: ${publishTime}`);
    if (sourceUrl) header.push(`> 原文链接: ${sourceUrl}`);
    if (author || publishTime || sourceUrl) header.push("");
    header.push("---", "");
    return header.join("\n") + bodyMd;
}

// ============================================================
// Main
// ============================================================

async function fetchArticle(url) {
    console.log(`🔄 正在抓取: ${url}`);
    // #9: 主请求也加上 timeout
    const { data: html } = await axios.get(url, { headers: HEADERS, timeout: 30000 });
    const $ = cheerio.load(html);

    // 提取元数据
    const meta = extractMetadata($, html);
    if (!meta.title) {
        console.error("❌ 未能提取到文章标题，可能触发了验证码");
        if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });
        fs.writeFileSync(path.join(OUTPUT_DIR, "debug.html"), html);
        console.log("已保存原始 HTML 到 output/debug.html");
        // #2: 设置非零退出码
        process.exitCode = 1;
        return;
    }
    meta.sourceUrl = url;
    console.log(`📄 标题: ${meta.title}`);
    console.log(`👤 作者: ${meta.author}`);
    console.log(`📅 时间: ${meta.publishTime}`);

    // 处理正文
    // #7: imgUrls 现在从 DOM 阶段收集
    const { contentHtml, codeBlocks, imgUrls } = processContent($, $("#js_content"));
    if (!contentHtml) {
        console.error("❌ 未能提取到正文内容");
        // #2: 设置非零退出码
        process.exitCode = 1;
        return;
    }

    // 转 Markdown
    let md = convertToMarkdown(contentHtml, codeBlocks);

    // 下载图片
    const safeTitle = meta.title.replace(/[/\\?%*:|"<>]/g, "_").slice(0, 80);
    const articleDir = path.join(OUTPUT_DIR, safeTitle);
    const imgDir = path.join(articleDir, "images");
    if (!fs.existsSync(imgDir)) fs.mkdirSync(imgDir, { recursive: true });

    const urlMap = await downloadAllImages(imgUrls, imgDir);
    md = replaceImageUrls(md, urlMap);

    // 写入文件
    const result = buildMarkdown(meta, md);
    const mdPath = path.join(articleDir, `${safeTitle}.md`);
    fs.writeFileSync(mdPath, result);

    console.log(`✅ 已保存: ${mdPath}`);
    console.log(`📊 Markdown 约 ${md.length} 字符`);
}

// #1: 区分错误类型，给出可操作提示
fetchArticle(url).catch((err) => {
    if (err.response?.status === 403 || err.response?.status === 412) {
        console.error("❌ 微信反爬拦截，请稍后重试或更换 IP");
    } else if (err.code === "ECONNABORTED") {
        console.error("❌ 请求超时，请检查网络连接");
    } else {
        console.error("❌ 抓取失败:", err.message);
    }
    process.exitCode = 1;
});
