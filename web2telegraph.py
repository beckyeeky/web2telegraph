#!/usr/bin/env python3
"""
网页正文抓取 -> Telegraph 发布工具

用法:
  python web2telegraph.py https://example.com/article
  python web2telegraph.py                         # 交互式输入
  python web2telegraph.py --setup                 # 配置 Telegraph 账号
"""

import argparse
import json
import os
import re
import sys
import warnings

# 消除 requests 与 urllib3 版本不匹配的警告（不影响功能）
warnings.filterwarnings("ignore", message=".*urllib3.*")

import requests
from readability import Document
from html_telegraph_poster import TelegraphPoster
from html_telegraph_poster.utils import DocumentPreprocessor

# ── 配置 ────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "telegraph_config.json")
DEFAULT_AUTHOR = "Web2Telegraph"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ── 配置管理 ────────────────────────────────────────
def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ── 设置 Telegraph 账号 ─────────────────────────────
def setup():
    """交互式配置 Telegraph 账号，获取 access_token"""
    config = load_config()
    print("📝 Telegraph 账号配置")
    print("-" * 40)
    print("提示: 按回车使用默认值（括号内为默认值）\n")

    author = input(f"作者名 [{config.get('author', DEFAULT_AUTHOR)}]: ").strip()
    if not author:
        author = config.get("author", DEFAULT_AUTHOR)

    short_name = input(
        f"短名称(仅字母数字) [{config.get('short_name', author[:32])}]: "
    ).strip()
    if not short_name:
        short_name = config.get("short_name", author[:32])

    author_url = input(f"作者主页链接 [{config.get('author_url', '')}]: ").strip()
    if not author_url:
        author_url = config.get("author_url", "")

    print("\n⏳ 正在创建/获取 Telegraph Token...")
    t = TelegraphPoster(use_api=True)
    result = t.create_api_token(author, short_name, author_url or None)

    config["access_token"] = result["access_token"]
    config["author"] = author
    config["short_name"] = short_name
    config["author_url"] = author_url
    save_config(config)

    print("\n✅ 配置完成!")
    print(f"   Token:  {result['access_token'][:16]}...")
    print(f"   作者:   {author}")
    print(f"   配置已保存到: {CONFIG_FILE}")

# ── 正文提取 ────────────────────────────────────────
def extract_content(url: str) -> tuple:
    """
    抓取网页正文，三级回退策略
    返回: (title, content_html)
    """
    print(f"🌐 正在抓取: {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    html = resp.text
    print(f"   页面大小: {len(html)} 字符")

    # ── 策略1: readability-lxml ──
    try:
        doc = Document(html)
        title = doc.title() or _extract_title_fallback(html)
        content_html = str(doc.summary())
        text_len = len(re.sub(r"<[^>]+>", "", content_html).strip())
        if text_len > 100:
            print(f"✅ readability 提取: ~{text_len} 纯文本字符")
            return title, content_html
    except Exception as e:
        print(f"⚠️  readability 失败: {e}")

    # ── 策略2: trafilatura ──
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            output_format="html",
            url=url,
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True,
        )
        if extracted and len(re.sub(r"<[^>]+>", "", extracted).strip()) > 100:
            title = _extract_title_fallback(html) or url
            print(f"✅ trafilatura 提取: ~{len(extracted)} 字符")
            return title, extracted
    except Exception as e:
        print(f"⚠️  trafilatura 失败: {e}")

    # ── 策略3: readability 强制回退 ──
    try:
        doc = Document(html)
        title = doc.title() or _extract_title_fallback(html)
        content_html = str(doc.summary())
        print("⚠️  使用回退提取（内容可能不完整）")
        return title, content_html
    except Exception:
        raise RuntimeError("所有提取策略均失败，请检查 URL 是否可访问")


def _extract_title_fallback(html: str) -> str:
    """从 HTML 中提取标题的备用方法"""
    m = re.search(r"<title.*?>(.*?)</title>", html, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    return ""

# ── Telegraph 发布 ──────────────────────────────────
def post_to_telegraph(
    title, content_html, author, access_token, upload_images=True
):
    """
    发布到 Telegraph
    返回: 页面 URL (成功) 或 None (失败)
    """
    print("📤 正在发布到 Telegraph...")

    # 上传图片到 Telegraph 图床
    if upload_images:
        try:
            dp = DocumentPreprocessor(content_html)
            dp.upload_all_images()
            content_html = dp.get_processed_html()
            print("   🖼️  图片已上传到 Telegraph 图床")
        except Exception as e:
            print(f"   ⚠️  图片处理跳过: {e}")

    t = TelegraphPoster(access_token=access_token)

    try:
        result = t.post(title=title, author=author, text=content_html)
        url = result["url"]
        print(f"\n🎉 发布成功!")
        print(f"📄 标题: {title}")
        print(f"🔗 链接: {url}")
        return url
    except Exception as e:
        print(f"❌ 发布失败: {e}")
        return None

# ── 交互菜单 ────────────────────────────────────────
def interactive_menu():
    """交互式菜单：无需记命令，跟着提示走"""
    config = load_config()

    while True:
        print("\n" + "=" * 50)
        print("   📰 Web → Telegraph 网页转存工具")
        print("=" * 50)

        status = "✅ 已配置" if config.get("access_token") else "❌ 未配置"
        author = config.get("author", "-")
        print(f"   Token: {status}  |  作者: {author}")
        print("-" * 50)
        print("   1. 抓取网页并发布到 Telegraph")
        print("   2. 配置/重新配置 Telegraph 账号")
        print("   3. 查看已有配置")
        print("   0. 退出")
        print("-" * 50)

        choice = input("👉 请选择 [1]: ").strip() or "1"

        if choice == "1":
            # 检查是否已配置
            if not config.get("access_token"):
                print("\n⚠️  尚未配置账号，先来配置一下：")
                setup()
                config = load_config()
                continue

            _do_capture(config)

        elif choice == "2":
            setup()
            config = load_config()

        elif choice == "3":
            _show_config(config)

        elif choice == "0":
            print("👋 再见!")
            break
        else:
            print("❌ 无效选项，请重试")


def _do_capture(config):
    """交互式抓取流程"""
    print("\n" + "-" * 40)
    print("📥 抓取网页")

    # 支持粘贴多个 URL，分批处理
    url_input = input("🔗 网页 URL: ").strip()
    if not url_input:
        return

    urls = [u.strip() for u in url_input.split() if u.strip()]
    if not urls:
        return

    for i, url in enumerate(urls):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if len(urls) > 1:
            print(f"\n── [{i+1}/{len(urls)}] ──")

        # 1. 抓取
        try:
            title, content_html = extract_content(url)
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
            continue

        # 让用户确认/修改标题
        print(f"\n📄 原标题: {title}")
        custom_title = input("   自定义标题 (回车保持原标题): ").strip()
        if custom_title:
            title = custom_title

        # 作者
        default_author = config.get("author", DEFAULT_AUTHOR)
        author_input = input(f"   作者名 [{default_author}]: ").strip()
        author = author_input if author_input else default_author

        # 图片
        upload_img = True
        img_choice = input("   上传图片到 Telegraph? [Y/n]: ").strip().lower()
        if img_choice in ("n", "no"):
            upload_img = False

        # 2. 发布
        result_url = post_to_telegraph(
            title=title,
            content_html=content_html,
            author=author,
            access_token=config["access_token"],
            upload_images=upload_img,
        )

        if result_url and len(urls) > 1 and i < len(urls) - 1:
            input("\n按回车继续下一个...")


def _show_config(config):
    """显示当前配置"""
    print("\n📋 当前配置:")
    print("-" * 40)
    if not config:
        print("  (空 - 尚未配置)")
    else:
        for k, v in config.items():
            if k == "access_token":
                v = v[:20] + "..." if len(v) > 20 else v
            print(f"  {k}: {v}")


# ── CLI 快速模式 (保留向后兼容) ─────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="网页正文抓取 -> Telegraph 发布工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python web2telegraph.py                              # 交互菜单 (推荐)
  python web2telegraph.py https://example.com/article  # 快速抓取
  python web2telegraph.py --setup                      # 配置账号
  python web2telegraph.py URL -t "标题" -a "作者"       # 带参数
        """,
    )
    parser.add_argument("url", nargs="?", help="要抓取的网页 URL")
    parser.add_argument("--setup", action="store_true", help="配置 Telegraph 账号")
    parser.add_argument("--title", "-t", help="自定义标题")
    parser.add_argument("--author", "-a", help="自定义作者名")
    parser.add_argument("--no-images", action="store_true", help="不上传图片")

    args = parser.parse_args()

    # 配置模式
    if args.setup:
        setup()
        return

    # 无参数 -> 进入交互菜单
    if not args.url:
        interactive_menu()
        return

    # CLI 快速模式
    config = load_config()
    if not config.get("access_token"):
        print("⚠️  尚未配置 Telegraph Token")
        print("   即将进入交互菜单...")
        interactive_menu()
        return

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        title, content_html = extract_content(url)
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        sys.exit(1)

    if args.title:
        title = args.title
    author = args.author or config.get("author", DEFAULT_AUTHOR)

    result_url = post_to_telegraph(
        title=title,
        content_html=content_html,
        author=author,
        access_token=config["access_token"],
        upload_images=not args.no_images,
    )

    if not result_url:
        sys.exit(1)


if __name__ == "__main__":
    main()
