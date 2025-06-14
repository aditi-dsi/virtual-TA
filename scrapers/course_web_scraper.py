import os
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright

# === CONFIGURATION ===
BASE_URL = "https://tds.s-anand.net/#/2025-01/"
BASE_ORIGIN = "https://tds.s-anand.net"
OUTPUT_DIR = "../data/course_material"
METADATA_FILE = "../data/metadata.json"

visited = set()
metadata = []

def sanitize_filename(title):
    filename = re.sub(r'[^\w\-_.]', '_', title.strip())
    return filename[:100]  # limit length

def extract_internal_links(page):
    links = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
    return list(set(
        link for link in links
        if link.startswith(BASE_ORIGIN) and "/#/" in link
    ))

def wait_for_article_html(page):
    page.wait_for_selector("article.markdown-section#main", timeout=10000)
    return page.inner_html("article.markdown-section#main")

def crawl_web_page(page, url):
    if url in visited:
        return
    visited.add(url)

    print(f"📄 Visiting: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        html = wait_for_article_html(page)
    except Exception as e:
        print(f"Failed to load {url}: {e}")
        return

    now = datetime.now().isoformat()
    title = (page.title().split(" - ")[0].strip() or f"page_{len(visited)}")
    filename = sanitize_filename(title)
    filepath = os.path.join(OUTPUT_DIR, f"{filename}.md")

    markdown = md(html, heading_style="ATX")
    front_matter = f"""---
title: "{title}"
original_url: "{url}"
downloaded_at: "{now}"
---

"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(front_matter)
        f.write(markdown)

    metadata.append({
        "title": title,
        "filename": f"{filename}.md",
        "original_url": url,
        "downloaded_at": now
    })

    for link in extract_internal_links(page):
        if link not in visited:
            crawl_web_page(page, link)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global visited, metadata

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        crawl_web_page(page, BASE_URL)

        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nScraping complete. {len(metadata)} pages saved in '{OUTPUT_DIR}'")
        browser.close()

if __name__ == "__main__":
    main()


# RESULTS POST SCRAPING:
# Scraping complete. 693 pages saved in '../data/course_material'