#!/usr/bin/env python3
# wechat-dedup.py - 微信公众号图片去重脚本
# 用法: python3 wechat-dedup.py <下载的文章目录> <Vault根目录> [文章在Vault中的保存路径]
#
# 示例:
#   python3 wechat-dedup.py ~/Desktop/某文章/ ~/Documents/Obsidian\ Vault AI/某文章/
#
# 效果:
#   - 图片按 MD5 hash 集中存到 Vault/wechat-images/
#   - 同内容图片只存一份
#   - Markdown 中路径自动更新为 wechat-images/<hash>.<ext>

import os
import sys
import hashlib
import shutil
import re

def main():
    if len(sys.argv) < 3:
        print("用法: wechat-dedup.py <文章下载目录> <Vault根目录> [文章在Vault中的子目录]")
        sys.exit(1)

    article_dir = sys.argv[1]
    vault_root = sys.argv[2]
    vault_subdir = sys.argv[3] if len(sys.argv) > 3 else ""

    central_images = os.path.join(vault_root, "wechat-images")
    images_dir = os.path.join(article_dir, "images")
    md_file = None

    # 找到 md 文件
    for f in os.listdir(article_dir):
        if f.endswith(".md"):
            md_file = os.path.join(article_dir, f)
            break

    if not md_file:
        print("❌ 未找到 Markdown 文件")
        sys.exit(1)

    # 目标 md 路径
    if vault_subdir:
        dest_dir = os.path.join(vault_root, vault_subdir)
        os.makedirs(dest_dir, exist_ok=True)
        dest_md = os.path.join(dest_dir, os.path.basename(md_file))
    else:
        dest_md = md_file

    # 计算相对路径：文章位置 → Vault根目录
    rel_from_md_to_vault = os.path.relpath(vault_root, os.path.dirname(dest_md))
    # 将路径分隔符标准化（Windows兼容）
    rel_prefix = rel_from_md_to_vault.replace(os.sep, "/") + "/"

    # 复制原始 md
    shutil.copy2(md_file, dest_md)

    os.makedirs(central_images, exist_ok=True)
    print(f"📦 公共图片库: {central_images}")

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
            print(f"  ✅ 新增: {deduped}")
        else:
            print(f"  ⏭️  已存在: {deduped}")

        replacements[fname] = deduped

    # 更新 md 路径
    with open(dest_md, "r") as f:
        content = f.read()

    for orig, deduped in replacements.items():
        content = content.replace(f"images/{orig}", rel_prefix + "wechat-images/" + replacements[orig])

    with open(dest_md, "w") as f:
        f.write(content)

    print(f"\n✅ 完成！")
    print(f"   文章: {dest_md}")
    print(f"   图片: {len(replacements)} 张（已去重）")

if __name__ == "__main__":
    main()
