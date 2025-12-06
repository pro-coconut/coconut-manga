import requests
from bs4 import BeautifulSoup
import json
import os
import time

API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
STORIES_PER_RUN = 3
START_PAGE = 3

DOMAIN = "https://nettruyen0209.com"
LIST_URL = DOMAIN + "/danh-sach-truyen/{page}/?sort=last_update&status=0"

POSTED_FILE = "posted.json"


# ==============================
# Load/save posted list
# ==============================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(lst):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, indent=2, ensure_ascii=False)


# ==============================
# Lấy danh sách link truyện
# ==============================
def get_story_links():
    links = []

    print("=== 🔍 SCANNING FOR STORIES ===")

    for page in range(START_PAGE, MAX_PAGES + 1):
        url = LIST_URL.format(page=page)
        print(f"📄 Checking page {page}: {url}")

        try:
            html = requests.get(url, timeout=10).text
        except:
            print("❌ Failed to load page")
            continue

        soup = BeautifulSoup(html, "lxml")
        items = soup.select("div.item figure a")

        if not items:
            print("⚠ No more items → stop scan")
            break

        for a in items:
            link = a.get("href")
            if link.startswith("/"):
                link = DOMAIN + link
            links.append(link)

        print(f"➕ Added {len(items)} links from page {page}")
        time.sleep(0.5)

    print(f"🎉 TOTAL LINKS FOUND: {len(links)}")
    return links


# ==============================
# Lấy hình ảnh chapter
# ==============================
def scrape_chapter_images(url):
    try:
        html = requests.get(url, timeout=10).text
    except:
        print("❌ Cannot load chapter:", url)
        return []

    soup = BeautifulSoup(html, "lxml")

    imgs = []
    for img in soup.select(".page-chapter img"):
        src = img.get("data-src") or img.get("src")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            imgs.append(src)

    return imgs


# ==============================
# Scrap full truyện + chapter
# ==============================
def scrape_story(url):
    print("\n=== 📘 SCRAPING STORY ===")
    print(url)

    try:
        html = requests.get(url, timeout=10).text
    except:
        print("❌ Cannot load story URL")
        return None

    soup = BeautifulSoup(html, "lxml")

    title = soup.select_one(".title-detail")
    title = title.text.strip() if title else "No Title"

    cover_node = soup.select_one(".detail-info img")
    cover = cover_node.get("src") if cover_node else ""

    des_node = soup.select_one(".detail-content p")
    description = des_node.text.strip() if des_node else ""

    chapters = []
    ch_nodes = soup.select(".list-chapter li a")

    for c in ch_nodes:
        ch_name = c.text.strip()
        ch_url = c.get("href")
        if not ch_url:
            continue
        if ch_url.startswith("/"):
            ch_url = DOMAIN + ch_url

        chapter_imgs = scrape_chapter_images(ch_url)

        chapters.append({
            "chapter": ch_name,
            "images": chapter_imgs
        })

        time.sleep(0.3)

    return {
        "name": title,
        "cover": cover,
        "description": description,
        "chapters": chapters
    }


# ==============================
# Upload API
# ==============================
def upload_story(data):
    if not API_BASE:
        print("❌ API_BASE_URL missing!")
        return False

    try:
        res = requests.post(f"{API_BASE}/api/stories/create", json=data)
        print(f"📤 API Response: {res.status_code} - {res.text}")

        if res.status_code != 200:
            return False

        j = res.json()
        return j.get("success") is True

    except Exception as e:
        print("❌ API upload error:", e)
        return False


# ==============================
# MAIN
# ==============================
def main():
    posted = load_posted()
    all_links = get_story_links()

    new_links = [l for l in all_links if l not in posted]

    if not new_links:
        print("🎉 No new stories left.")
        return

    print(f"\n📌 Stories remaining: {len(new_links)}")
    print(f"🚀 Will upload next {STORIES_PER_RUN} stories")

    uploaded = 0

    for url in new_links:
        if uploaded >= STORIES_PER_RUN:
            break

        data = scrape_story(url)
        if not data:
            continue

        if upload_story(data):
            posted.append(url)
            uploaded += 1
            save_posted(posted)
            print(f"✅ Uploaded {uploaded}/{STORIES_PER_RUN}")

        time.sleep(1)

    print("\n🎯 DONE.")


if __name__ == "__main__":
    main()
