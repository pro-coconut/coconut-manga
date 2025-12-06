#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import urljoin, urlparse

# ========== CẤU HÌNH ==========
BASE_URL = "https://nettruyen0209.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
}

DELAY = 1.5                # Delay giữa requests (sửa nếu cần)
MAX_LISTING_PAGES = 20     # Số trang listing sẽ quét (tăng nếu muốn quét toàn site)
MAX_STORIES = None         # Nếu muốn giới hạn tổng số truyện (None = không giới hạn)
OUTPUT_JSON = "stories.json"

# ========== TIỆN ÍCH ==========
def safe_get(url, **kwargs):
    """Gọi requests.get có xử lý lỗi cơ bản."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=20, **kwargs)
        res.raise_for_status()
        return res
    except Exception as e:
        print(f"⚠ Lỗi GET {url}: {e}")
        return None

def normalize_link(href):
    if not href:
        return None
    return urljoin(BASE_URL, href)

def is_manga_link(href):
    if not href:
        return False
    # nettruyen0209 dùng đường dẫn như /manga/slug...
    return "/manga/" in href and href.count("/") >= 2

# ========== LẤY DANH SÁCH TRUYỆN TỪ CÁC TRANG LISTING ==========
def gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=None):
    """
    Quét nhiều trang (bắt đầu từ trang chủ) để tìm các link chứa '/manga/'.
    Trả về list link duy nhất (không duplicate).
    """
    found = []
    seen = set()
    seeds = [BASE_URL, urljoin(BASE_URL, "/truyen-tranh"), urljoin(BASE_URL, "/truyen-tranh?page=1")]
    # Một số trang có /page/2 hoặc ?page=2; chúng ta thử cả hai mẫu
    page_variants = [
        lambda n: urljoin(BASE_URL, f"/page/{n}"),
        lambda n: urljoin(BASE_URL, f"/?page={n}"),
        lambda n: urljoin(BASE_URL, f"/truyen-tranh?page={n}"),
        lambda n: urljoin(BASE_URL, f"/truyen-tranh/page/{n}")
    ]

    # Khởi đầu: quét seeds
    for seed in seeds:
        print("Quét seed:", seed)
        r = safe_get(seed)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        a_tags = soup.find_all("a", href=True)
        for a in a_tags:
            href = a.get("href")
            if is_manga_link(href):
                full = normalize_link(href)
                if full not in seen:
                    seen.add(full)
                    found.append(full)
                    print("  → Tìm:", full)
                    if max_stories and len(found) >= max_stories:
                        return found

    # Quét thêm theo mẫu page
    for n in range(1, max_pages + 1):
        for variant in page_variants:
            url = variant(n)
            print(f"Quét trang listing: {url}")
            r = safe_get(url)
            if not r:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            a_tags = soup.find_all("a", href=True)
            added = 0
            for a in a_tags:
                href = a.get("href")
                if is_manga_link(href):
                    full = normalize_link(href)
                    if full not in seen:
                        seen.add(full)
                        found.append(full)
                        added += 1
                        print("  → Tìm:", full)
                        if max_stories and len(found) >= max_stories:
                            return found
            print(f"  → Thêm {added} link từ trang {url}")
            time.sleep(DELAY)
        # ngắt sớm nếu không có link mới trong vòng 1 vòng page_variants
    print(f"Tổng link thu thập: {len(found)}")
    return found

# ========== LẤY TOÀN BỘ CHAPTER TRONG 1 TRUYỆN ==========
def parse_story_page(story_url):
    """
    Trả về dict:
    {
      id, title, author, description, thumbnail, chapters: [{name, url}, ...]
    }
    """
    r = safe_get(story_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    title_elem = soup.select_one("h1.title-detail") or soup.select_one("h1")
    title = title_elem.get_text(strip=True) if title_elem else "Không có tiêu đề"
    sid = re.sub(r'[^a-z0-9]', '', title.lower())

    # Author (cố gắng lấy)
    author = "Không rõ"
    try:
        # tìm thẻ chứa "Tác giả"
        li = soup.find(lambda tag: tag.name in ["li", "p", "div", "span"] and "Tác giả" in tag.get_text())
        if li:
            a = li.find("a")
            if a:
                author = a.get_text(strip=True)
    except Exception:
        pass

    # Description
    desc = ""
    desc_elem = soup.select_one(".detail-content, .summary, .desc, .story-intro")
    if desc_elem:
        desc = desc_elem.get_text(strip=True)

    # Thumbnail
    thumb = ""
    img_elem = soup.select_one(".col-image img, .book img, .thumb img, img[itemprop='image']")
    if img_elem:
        thumb = img_elem.get("src") or img_elem.get("data-src") or ""

    # Danh sách chapter (nhiều selector để bền)
    chap_selectors = [
        ".list-chapter li a",
        "ul.row-content-chapter li a",
        ".chapter_list a",
        ".chapters a",
        ".chapter a",
        ".chapter-list a",
        "a[href*='/manga/'][href*='chapter']"  # fallback: link chứa 'chapter'
    ]

    chap_links = []
    for sel in chap_selectors:
        elems = soup.select(sel)
        if elems:
            for a in elems:
                href = a.get("href")
                name = a.get_text(strip=True)
                if href and name:
                    full = normalize_link(href)
                    # loại ra các link không phải chapter
                    if "chapter" in full or re.search(r'chap(ter)?[-\s\d]', full, re.I):
                        chap_links.append((name, full))
            if chap_links:
                break

    # Nếu chưa tìm được chapter bằng selectors, tìm tất cả a chứa 'chapter' trong href
    if not chap_links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "chapter" in href.lower() or re.search(r'/chapter[-_/]?\d+', href, re.I):
                name = a.get_text(strip=True) or href.split("/")[-1]
                chap_links.append((name, normalize_link(href)))

    # Deduplicate và sort theo thứ tự xuất hiện (sau đó đảo để chap1->chapN)
    seen = set()
    cleaned = []
    for name, link in chap_links:
        if link not in seen:
            seen.add(link)
            cleaned.append({"name": name, "url": link})

    # Một số trang liệt kê chapter theo thứ tự mới->cũ, nên đảo để chap 1 trước
    cleaned.reverse()

    story = {
        "id": sid,
        "title": title,
        "author": author,
        "description": desc,
        "thumbnail": thumb,
        "chapters": cleaned
    }
    print(f"Parsed story: {title} - {len(cleaned)} chapters found")
    return story

# ========== LẤY ẢNH TRONG 1 CHAPTER ==========
def parse_chapter_images(chap_url):
    """
    Trả về list url ảnh (chuỗi) cho chapter.
    """
    r = safe_get(chap_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    # Nhiều selector cho ảnh
    img_selectors = [
        ".reading-detail img",   # một số theme
        ".chapter-content img",
        ".page-chapter img",
        "img.img-responsive",
        ".container-chapter-reader img",
        "img"
    ]

    imgs = []
    for sel in img_selectors:
        elems = soup.select(sel)
        if not elems:
            continue
        for img in elems:
            src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
            if src and src.startswith("http"):
                imgs.append(src)
        if imgs:
            break

    # Filter ra các ảnh có kích thước, không phải icon
    filtered = []
    for u in imgs:
        # bỏ các link favicon hoặc small icons
        if any(x in u for x in ["/logo", "favicon", "icons", "icon"]):
            continue
        filtered.append(u)
    print(f"    → {len(filtered)} images found in chapter {chap_url}")
    return filtered

# ========== CẬP NHẬT STORIES.JSON ==========
def load_stories():
    if not os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []

def save_stories(stories):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)

def merge_and_save(parsed_story):
    """
    parsed_story có dạng: id, title, author, description, thumbnail, chapters: [{name, url}, ...]
    Ta cần: lưu cấu trúc với chapters chứa {name, images: [...]}
    """
    if not parsed_story:
        return

    stories = load_stories()
    exist = next((s for s in stories if s.get("id") == parsed_story["id"]), None)

    if not exist:
        # Truyện mới: tải từng chapter images và thêm toàn bộ
        print(f"🟢 Thêm truyện mới: {parsed_story['title']}")
        story_entry = {
            "id": parsed_story["id"],
            "title": parsed_story["title"],
            "author": parsed_story.get("author", ""),
            "description": parsed_story.get("description", ""),
            "thumbnail": parsed_story.get("thumbnail", ""),
            "chapters": []
        }
        for chap in parsed_story["chapters"]:
            print(f"   Tải chapter: {chap['name']}")
            images = parse_chapter_images(chap["url"])
            story_entry["chapters"].append({
                "name": chap["name"],
                "images": images
            })
            time.sleep(DELAY)
        stories.append(story_entry)
        save_stories(stories)
    else:
        # Truyện đã tồn tại: chỉ thêm những chapter chưa có
        print(f"🔍 Truyện đã có: {parsed_story['title']}, kiểm tra chapter mới...")
        existing_names = {c["name"] for c in exist.get("chapters", [])}
        added = 0
        for chap in parsed_story["chapters"]:
            if chap["name"] not in existing_names:
                print(f"   Thêm chapter mới: {chap['name']}")
                images = parse_chapter_images(chap["url"])
                exist["chapters"].append({"name": chap["name"], "images": images})
                added += 1
                time.sleep(DELAY)
        if added:
            save_stories(stories)
        print(f"   Đã thêm {added} chapter mới")

# ========== MAIN ==========
def main():
    print("=== BOT NETTRUYEN0209 START ===")
    links = gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=MAX_STORIES)
    print(f"➡ Tổng truyện sẽ xử lý: {len(links)}")

    # Duyệt các truyện
    for idx, link in enumerate(links, start=1):
        print(f"\n[{idx}/{len(links)}] Xử lý: {link}")
        parsed = parse_story_page(link)
        if not parsed:
            print("  ! Bỏ qua do lỗi parse")
            continue
        merge_and_save(parsed)
        # delay giữa truyện để tránh bị chặn
        time.sleep(DELAY)

    print("\n=== BOT HOÀN THÀNH ===")

if __name__ == "__main__":
    main()
