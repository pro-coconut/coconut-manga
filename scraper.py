#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Random-1-story scraper for nettruyen0209.com
Behavior:
 - Gather manga links from listing pages (tim-truyen?sort=created&page=1..N)
 - Pick ONE random manga from collected links
 - Parse the story page -> get info and full chapter list (chap1 -> chapN)
 - For each chapter not present on API: fetch images and POST to API
Config via ENV:
  API_BASE_URL (required)      - e.g. https://manga-api-gr26.onrender.com
  API_KEY (optional)           - if your API supports Bearer token
  MAX_LISTING_PAGES (optional) - how many listing pages to scan (default 5)
  DELAY (optional)             - base delay seconds between requests (default 1.5)
  MAX_RETRY (optional)         - retries for GET (default 3)
"""
import os, sys, time, random, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
BASE_SITE = "https://nettruyen0209.com"
API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("API_KEY") or None
MAX_LISTING_PAGES = int(os.getenv("MAX_LISTING_PAGES", "5"))
DELAY = float(os.getenv("DELAY", "1.5"))
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))

if not API_BASE:
    print("ERROR: set API_BASE_URL environment variable (Render API URL).")
    sys.exit(1)

# ---------------- SESSIONS ----------------
SCRAPE_SESSION = requests.Session()
SCRAPE_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
})

API_SESSION = requests.Session()
API_SESSION.headers.update({"Content-Type": "application/json"})
if API_KEY:
    API_SESSION.headers.update({"Authorization": f"Bearer {API_KEY}"})

# ---------------- HELPERS ----------------
def safe_get(session, url, max_retries=MAX_RETRY, timeout=18):
    attempt = 0
    while attempt < max_retries:
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            attempt += 1
            print(f"[GET ERR] {url} (attempt {attempt}) -> {e}")
            time.sleep(0.8 + attempt * 0.5)
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

def normalize(href):
    if not href:
        return None
    return urljoin(BASE_SITE, href)

# ---------------- GATHER LINKS ----------------
def gather_manga_links(max_pages=MAX_LISTING_PAGES, limit=None):
    links = []
    seen = set()
    print("Gathering manga links from listing pages...")
    # listing pattern: /tim-truyen?sort=created&page=N
    for p in range(1, max_pages + 1):
        url = f"{BASE_SITE}/tim-truyen?sort=created&page={p}"
        print("  Scanning:", url)
        r = safe_get(SCRAPE_SESSION, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        # try robust selectors for items
        selectors = [".item .image a", ".story-item a", ".manga-item a", ".list-truyen a"]
        anchors = []
        for sel in selectors:
            anchors = soup.select(sel)
            if anchors:
                break
        if not anchors:
            anchors = soup.find_all("a", href=True)

        added = 0
        for a in anchors:
            href = a.get("href")
            if not href:
                continue
            if "/manga/" in href:
                full = normalize(href)
                if full not in seen:
                    seen.add(full)
                    links.append(full)
                    added += 1
                    # safety: limit
                    if limit and len(links) >= int(limit):
                        print(f"  Collected {len(links)} links (limit reached)")
                        return links
        print(f"  Added {added} links from page {p}")
        time.sleep(DELAY + random.uniform(0, 0.6))
    print("Total links gathered:", len(links))
    return links

# ---------------- PARSE STORY PAGE ----------------
def parse_story_page(url):
    r = safe_get(SCRAPE_SESSION, url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # title
    title_elem = soup.select_one("h1.title-detail") or soup.select_one("h1") or soup.select_one(".title")
    title = title_elem.get_text(strip=True) if title_elem else "No title"

    # thumbnail
    img = soup.select_one(".col-image img, .detail-thumbnail img, img[itemprop='image'], .thumb img")
    thumb = img.get("src") or img.get("data-src") if img else ""

    # description
    desc_elem = soup.select_one(".detail-content, .summary, #tab-summary, .story-info-right .desc")
    desc = desc_elem.get_text(strip=True) if desc_elem else ""

    # chapter list selectors (robust)
    chap_selectors = [
        ".list-chapter li a",
        "ul.row-content-chapter li a",
        ".chapter-list a",
        ".chapters a",
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
                    chap_links.append({"name": name, "url": normalize(href)})
            if chap_links:
                break

    # fallback: scan anchors with 'chapter' pattern
    if not chap_links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "chapter" in href.lower() or re.search(r'/chapter[-_/]?\d+', href, re.I):
                name = a.get_text(strip=True) or href.split("/")[-1]
                chap_links.append({"name": name, "url": normalize(href)})

    # dedupe preserve order then reverse so chap1->chapN
    seen_urls = set()
    cleaned = []
    for c in chap_links:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            cleaned.append(c)
    cleaned.reverse()

    print(f"Parsed story: {title} - {len(cleaned)} chapters")
    return {"title": title, "thumbnail": thumb, "description": desc, "chapters": cleaned}

# ---------------- PARSE CHAPTER IMAGES ----------------
def parse_chapter_images(chap_url):
    r = safe_get(SCRAPE_SESSION, chap_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    img_selectors = [
        ".reading-detail img",
        ".chapter-content img",
        ".page-chapter img",
        ".container-chapter-reader img",
        "img"
    ]
    imgs = []
    for sel in img_selectors:
        elems = soup.select(sel)
        if elems:
            for img in elems:
                src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
                if src and src.startswith("http"):
                    imgs.append(src)
            if imgs:
                break
    imgs = [u for u in imgs if not any(x in u for x in ["/logo", "favicon", "icons", "icon"])]
    print(f"    Images found: {len(imgs)}")
    return imgs

# ---------------- API INTERACTIONS ----------------
def check_story_api(name):
    payload = {"name": name}
    return api_post("/api/stories/check", payload)

def create_story_api(name, cover, description):
    payload = {"name": name, "cover": cover, "description": description}
    return api_post("/api/stories/create", payload)

def add_chapter_api(story_id, chapter_name, images):
    payload = {"storyId": story_id, "chapter": chapter_name, "images": images}
    return api_post("/api/stories/add-chapter", payload)

# ---------------- PROCESS SINGLE STORY ----------------
def process_story(link):
    print("\n=== Processing:", link)
    parsed = parse_story_page(link)
    if not parsed:
        print("  ! parse failed -> skip")
        return

    # check story on API
    chk = check_story_api(parsed["title"])
    if chk is None:
        print("  ! API check failed -> skip")
        return

    if not chk.get("exists"):
        print("  -> not exist on API -> creating...")
        res = create_story_api(parsed["title"], parsed["thumbnail"], parsed["description"])
        if not res:
            print("  ! create failed -> skip")
            return
        story_id = res.get("storyId") or res.get("id")
        existing = set()
        print("  -> created id:", story_id)
    else:
        story_id = chk.get("storyId")
        existing = set(chk.get("chapters", []) or [])
        print(f"  -> exists id: {story_id} (have {len(existing)} chapters)")

    added = 0
    for chap in parsed["chapters"]:
        name = chap["name"]
        if name in existing:
            print("   - skip existing:", name)
            continue
        print("   - add chapter:", name)
        imgs = parse_chapter_images(chap["url"])
        if not imgs:
            print("     ! no images -> skip chap")
            continue
        res = add_chapter_api(story_id, name, imgs)
        if res is None:
            print("     ! API add failed")
            continue
        print("     ✓ added:", name)
        added += 1
        time.sleep(DELAY + random.uniform(0, 0.6))
    print(f"  => done, chapters added: {added}")

# ---------------- MAIN (random 1 story) ----------------
def main():
    print("=== BOT START (random 1 story mode) ===")
    links = gather_manga_links(MAX_LISTING_PAGES)
    if not links:
        print("No links found -> exit")
        return
    choice = random.choice(links)
    print("Selected:", choice)
    process_story(choice)
    print("=== BOT FINISHED ===")

if __name__ == "__main__":
    main()
