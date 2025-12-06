#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full scraper for nettruyen0209.com
- Quét nhiều trang listing -> tìm từng truyện (link chứa /manga/)
- Với mỗi truyện: lấy info + toàn bộ chapter (chap1->chapN)
- Lấy ảnh cho mỗi chapter
- Gọi API của bạn để: check -> create -> add-chapter
Config via ENV:
  API_BASE_URL (required) e.g. https://manga-api-gr26.onrender.com
  API_KEY (optional)
  MAX_LISTING_PAGES (default 5)
  MAX_STORIES (optional, for testing)
  DELAY (default 1.5)
"""
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import sys
from random import uniform

# ------- Config from env -------
BASE_SITE = "https://nettruyen0209.com"
API_BASE = os.environ.get("API_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("API_KEY")  # optional
MAX_LISTING_PAGES = int(os.environ.get("MAX_LISTING_PAGES", "5"))
MAX_STORIES = os.environ.get("MAX_STORIES")  # optional (string)
DELAY = float(os.environ.get("DELAY", "1.5"))

if not API_BASE:
    print("ERROR: Set API_BASE_URL environment variable (Render URL).")
    sys.exit(1)

# ------- Session for scraping (no API auth headers here) -------
SCRAPE_SESSION = requests.Session()
SCRAPE_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
})

# ------- Session for API (may include Authorization) -------
API_SESSION = requests.Session()
API_SESSION.headers.update({"Content-Type": "application/json"})
if API_KEY:
    API_SESSION.headers.update({"Authorization": f"Bearer {API_KEY}"})

# ------- Helpers -------
def safe_get(session, url, max_retries=3, timeout=20):
    """GET with retries, returns response.text or None"""
    attempt = 0
    while attempt < max_retries:
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            attempt += 1
            print(f"[GET ERR] {url} (attempt {attempt}) -> {e}")
            time.sleep(1 + attempt * 0.5)
    return None

def api_post(path, payload):
    url = API_BASE + path
    try:
        r = API_SESSION.post(url, json=payload, timeout=30)
        r.raise_for_status()
        try:
            return r.json()
        except:
            return {"raw": r.text}
    except Exception as e:
        print(f"[API POST ERR] {url} -> {e}")
        return None

def api_get(path):
    url = API_BASE + path
    try:
        r = API_SESSION.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API GET ERR] {url} -> {e}")
        return None

def normalize_link(href, base=BASE_SITE):
    if not href:
        return None
    return urljoin(base, href)

# ------- 1) Gather manga links from listing pages -------
def gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=None):
    found = []
    seen = set()
    print("🔍 START SCRAPING NETTRUYEN...")

    seeds = [BASE_SITE, urljoin(BASE_SITE, "/truyen-tranh"), urljoin(BASE_SITE, "/danh-sach")]
    # initial seeds
    for seed in seeds:
        r = safe_get(SCRAPE_SESSION, seed)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/manga/" in href:
                full = normalize_link(href)
                if full not in seen:
                    seen.add(full)
                    found.append(full)
                    print("  Found (seed):", full)
                    if max_stories and len(found) >= int(max_stories):
                        return found

    # iterate pages
    for p in range(1, max_pages + 1):
        variants = [
            f"{BASE_SITE}/truyen-tranh?page={p}",
            f"{BASE_SITE}/tim-truyen?page={p}",
            f"{BASE_SITE}/truyen-tranh/page/{p}"
        ]
        for url in variants:
            print(f"📄 PAGE {p} -> {url}")
            r = safe_get(SCRAPE_SESSION, url)
            if not r:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            added = 0
            # try common item selectors first
            selectors = [".story-item a", ".item .image a", ".manga-item a", ".list-truyen a", ".name a"]
            anchors = []
            for sel in selectors:
                anchors = soup.select(sel)
                if anchors:
                    break
            if not anchors:
                anchors = soup.find_all("a", href=True)
            for a in anchors:
                href = a.get("href")
                if not href:
                    continue
                if "/manga/" in href:
                    full = normalize_link(href)
                    if full not in seen:
                        seen.add(full)
                        found.append(full)
                        added += 1
                        print("   →", full)
                        if max_stories and len(found) >= int(max_stories):
                            return found
            print(f"  Added {added} links from {url}")
            time.sleep(DELAY + uniform(0, 0.6))
    print("Total links found:", len(found))
    return found

# ------- 2) Parse story page: info + list of chapter links -------
def parse_story_page(story_url):
    r = safe_get(SCRAPE_SESSION, story_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Title robust selectors
    title_elem = soup.select_one("h1.title-detail") or soup.select_one("h1") or soup.select_one(".title")
    title = title_elem.get_text(strip=True) if title_elem else "No title"

    # thumbnail
    thumb = ""
    img = soup.select_one(".col-image img, .book img, img[itemprop='image'], .thumbnail img, .detail-thumbnail img")
    if img:
        thumb = img.get("src") or img.get("data-src") or ""

    # description
    desc = ""
    desc_elem = soup.select_one(".detail-content, .summary, .desc, #tab-summary, .story-info-right .desc")
    if desc_elem:
        desc = desc_elem.get_text(strip=True)

    # get chapter anchors
    chap_selectors = [
        ".list-chapter li a",
        "ul.row-content-chapter li a",
        ".chapter-list a",
        ".chapters a",
        ".chapter a",
        ".chapter_list a"
    ]
    chap_links = []
    for sel in chap_selectors:
        elems = soup.select(sel)
        if elems:
            for a in elems:
                href = a.get("href")
                name = a.get_text(strip=True)
                if href and name:
                    chap_links.append({"name": name, "url": normalize_link(href)})
            if chap_links:
                break

    # fallback: scan anchors containing 'chapter'
    if not chap_links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "chapter" in href.lower() or re.search(r'/chapter[-_/]?\d+', href, re.I):
                name = a.get_text(strip=True) or href.split("/")[-1]
                chap_links.append({"name": name, "url": normalize_link(href)})

    # dedupe preserve order then reverse (so chap1 -> chapN)
    seen = set()
    cleaned = []
    for c in chap_links:
        if c["url"] not in seen:
            seen.add(c["url"])
            cleaned.append(c)
    cleaned.reverse()

    print(f"Parsed story: {title} - {len(cleaned)} chapters")
    return {
        "title": title,
        "thumbnail": thumb,
        "description": desc,
        "chapters": cleaned
    }

# ------- 3) Parse chapter images -------
def parse_chapter_images(chap_url):
    r = safe_get(SCRAPE_SESSION, chap_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    selectors = [
        ".reading-detail img",
        ".chapter-content img",
        ".page-chapter img",
        ".container-chapter-reader img",
        ".chapter-img img",
        "img"
    ]
    imgs = []
    for sel in selectors:
        elems = soup.select(sel)
        if elems:
            for img in elems:
                src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
                if src and src.startswith("http"):
                    imgs.append(src)
            if imgs:
                break
    # filter out icons
    imgs = [u for u in imgs if not any(x in u for x in ["/logo", "favicon", "icons", "icon"])]
    print(f"    Images found: {len(imgs)}")
    return imgs

# ------- 4) API helpers -------
def check_story_api(name):
    payload = {"name": name}
    res = api_post("/api/stories/check", payload)
    return res

def create_story_api(name, cover, description):
    payload = {"name": name, "cover": cover, "description": description}
    return api_post("/api/stories/create", payload)

def add_chapter_api(story_id, chapter_name, images):
    payload = {"storyId": story_id, "chapter": chapter_name, "images": images}
    return api_post("/api/stories/add-chapter", payload)

# ------- 5) Process one story -------
def process_story(link):
    print("\n=== Processing story:", link)
    parsed = parse_story_page(link)
    if not parsed:
        print("  ! Parse failed, skip.")
        return

    # Check API
    chk = check_story_api(parsed["title"])
    if chk is None:
        print("  ! API check failed, skip story.")
        return

    if not chk.get("exists"):
        print("  → Story not exists on API, creating...")
        res = create_story_api(parsed["title"], parsed["thumbnail"], parsed["description"])
        if not res:
            print("  ! Create story API failed.")
            return
        story_id = res.get("storyId") or res.get("id")
        existing_ch_names = set()
        print("  → Created story id:", story_id)
    else:
        story_id = chk.get("storyId")
        existing_ch_names = set(chk.get("chapters", []) or [])
        print("  → Story exists id:", story_id, "existing chapters:", len(existing_ch_names))

    added = 0
    for chap in parsed["chapters"]:
        chap_name = chap["name"]
        if chap_name in existing_ch_names:
            print("   - Chapter already exists:", chap_name)
            continue
        print("   - New chapter:", chap_name, "-> fetch images")
        images = parse_chapter_images(chap["url"])
        if not images:
            print("     ! No images found, skipping chapter")
            continue
        res = add_chapter_api(story_id, chap_name, images)
        if res is None:
            print("     ! API add chapter failed")
            continue
        print("     ✓ Added chapter:", chap_name)
        added += 1
        time.sleep(DELAY + uniform(0, 0.5))
    print(f"  => Done. Chapters added: {added}")

# ------- MAIN -------
def main():
    links = gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=MAX_STORIES)
    print("Total stories to process:", len(links))
    for idx, link in enumerate(links, start=1):
        print(f"\n[{idx}/{len(links)}] {link}")
        try:
            process_story(link)
        except Exception as e:
            print("  ERROR processing:", e)
        time.sleep(DELAY + uniform(0, 0.6))
    print("=== Scraper Bot FINISHED ===")

if __name__ == "__main__":
    main()
