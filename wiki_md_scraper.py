#!/usr/bin/env python3
"""Dark Souls 3 wiki scraper — fextralife.com → markdown files.

Crawls the four main sections and their sub-pages:
  - Character Information
  - Equipment & Magic
  - World Information
  - Guides & Walkthroughs

Usage:
  python3 wiki_md_scraper.py              # full crawl
  python3 wiki_md_scraper.py --dry-run    # print URLs without saving
"""

import argparse
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import html2text
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://darksouls3.wiki.fextralife.com"
OUT_DIR = Path("data/wiki")
DELAY = 1.5  # seconds between requests
MAX_DEPTH = 2

SEED_PATHS = [
    "/Character+Information",
    "/Equipment+%26+Magic",
    "/World+Information",
    "/Guides+%26+Walkthroughs",
]

SKIP_PATTERNS = [
    r"[?&]action=",
    r"[?&]search=",
    r"/Forum",
    r"/Special[+:]",
    r"twitter\.com",
    r"facebook\.com",
    r"instagram\.com",
    r"youtube\.com",
    r"discord\.com",
    r"reddit\.com",
    r"/login",
    r"/register",
    r"/account",
    r"/profile",
    r"/user/",
    r"wp-admin",
    r"wp-login",
    r"\.xlsx$",
    r"\.pdf$",
    r"\.zip$",
    r"/file/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REMOVE_SELECTORS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    ".wiki-nav",
    "#wiki-navi",
    "#wiki-navigation",
    ".comments-area",
    "#comments",
    ".social-buttons",
    ".share-buttons",
    "#wiki-footer",
    "[class*='advertisement']",
    "[class*='ad-']",
    "[id*='ad-']",
    ".breadcrumb",
    ".breadcrumbs",
    "#breadcrumb",
    ".patreon",
    ".newsletter",
    "#sidebar",
    ".sidebar",
    "#sidebar-wrapper",
    "#related-wiki-entries",
    "#discussions-section",
]


def should_skip(url: str) -> bool:
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def is_wiki_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "darksouls3.wiki.fextralife.com"


def url_to_path(url: str) -> Path:
    parsed = urlparse(url)
    slug = unquote(parsed.path).strip("/")
    slug = re.sub(r'[<>:"/\\|?*&+]', "_", slug)
    slug = slug.strip("_") or "index"
    return OUT_DIR / f"{slug}.md"


def fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        time.sleep(DELAY)
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        print(f"    FETCH ERROR: {exc}", file=sys.stderr)
        return None


def get_title(soup: BeautifulSoup) -> str:
    for tag in ("h1", "title"):
        el = soup.find(tag)
        if el:
            return el.get_text().split("|")[0].strip()
    return ""


def extract_content_html(soup: BeautifulSoup) -> str | None:
    content = (
        soup.find("div", id="wiki-content-block")
        or soup.find("div", class_="wiki-content-block")
        or soup.find("main")
        or soup.find("article")
    )
    if not content:
        return None

    for sel in REMOVE_SELECTORS:
        for el in content.select(sel):
            el.decompose()

    return str(content)


def to_markdown(html: str, title: str = "") -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    converter.unicode_snob = True
    converter.skip_internal_links = False
    converter.protect_links = False
    converter.wrap_links = False

    md = converter.handle(html)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = md.strip()

    if title:
        return f"# {title}\n\n{md}\n"
    return md + "\n"


def links_from_markdown(md_path: Path, page_url: str) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    links = []
    for href in re.findall(r'\]\((/[^)#\s"]+)', text):
        absolute = urljoin(BASE_URL, href).split("#")[0]
        if is_wiki_url(absolute) and not should_skip(absolute):
            links.append(absolute)
    return links


def extract_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    content = (
        soup.find("div", id="wiki-content-block")
        or soup.find("div", class_="wiki-content-block")
        or soup.find("body")
    )
    if not content:
        return []

    links = []
    for a in content.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        absolute = urljoin(page_url, href).split("#")[0]
        if is_wiki_url(absolute) and not should_skip(absolute):
            links.append(absolute)
    return links


def scrape(dry_run: bool = False) -> None:
    if not dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()

    for path in SEED_PATHS:
        url = BASE_URL + path
        visited.add(url)
        queue.append((url, 0))

    saved = skipped = errors = 0

    while queue:
        url, depth = queue.popleft()
        out_path = url_to_path(url)

        if not dry_run and out_path.exists():
            print(f"[skip] {url}")
            skipped += 1
            if depth < MAX_DEPTH:
                for link in links_from_markdown(out_path, url):
                    if link not in visited:
                        visited.add(link)
                        queue.append((link, depth + 1))
            continue

        print(f"[d{depth}] {url}")

        if dry_run:
            if depth < MAX_DEPTH:
                soup = fetch(url)
                if soup:
                    for link in extract_links(soup, url):
                        if link not in visited:
                            visited.add(link)
                            queue.append((link, depth + 1))
            continue

        soup = fetch(url)
        if not soup:
            errors += 1
            continue

        title = get_title(soup)
        html = extract_content_html(soup)
        if not html:
            print(f"    WARN: no content block found", file=sys.stderr)
            errors += 1
        else:
            md = to_markdown(html, title)
            out_path.write_text(md, encoding="utf-8")
            print(f"    → {out_path} ({len(md):,} chars)")
            saved += 1

        if depth < MAX_DEPTH:
            for link in extract_links(soup, url):
                if link not in visited:
                    visited.add(link)
                    queue.append((link, depth + 1))

    print(f"\nDone. saved={saved} skipped={skipped} errors={errors}")


def main() -> None:
    global DELAY, MAX_DEPTH

    parser = argparse.ArgumentParser(description="Dark Souls 3 wiki → markdown scraper")
    parser.add_argument("--dry-run", action="store_true", help="Print URLs without saving")
    parser.add_argument("--delay", type=float, default=DELAY, help=f"Seconds between requests (default {DELAY})")
    parser.add_argument("--depth", type=int, default=MAX_DEPTH, help=f"Max crawl depth (default {MAX_DEPTH})")
    args = parser.parse_args()

    DELAY = args.delay
    MAX_DEPTH = args.depth

    print(f"Output dir : {OUT_DIR.resolve()}")
    print(f"Delay      : {DELAY}s")
    print(f"Max depth  : {MAX_DEPTH}")
    print(f"Dry run    : {args.dry_run}\n")

    scrape(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
