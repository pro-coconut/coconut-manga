import requests
from bs4 import BeautifulSoup
import json
import os
import time

API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
STORIES_PER_RUN = 5
START_PAGE = 3

LIST_URL = "https://nettruyen0209.com/danh-sach-truyen/{page}/?sort=last_update&status=0"
POSTED_FILE = "posted.json"


# ==============================
# Load & Save posted stories
# ==============================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []

    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==============================
# Lấy danh sách link truyện
# ==============================
def get_story_links():
    links = []
    print("=== 🔍 START SCANNING FOR STORIES ===")

    for page in range(START_PAGE, MAX_PAGES + 1):
        url = LIST_URL.format(page=page)
        print(f"📄 Checking page {page}: {url}")

        html = requests.get(url).text
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("div.item figure a")

        if not items:
            print(f"⚠ Page {page} returned 0 items. Possible end.")
            break

        for a in items:
            link = a.get("href")
            if link and link not in links:
                links.append(link)

        print(f"➕ Added {len(items)} links from page {page}")
        time.sleep(0.8)

    print(f"🎉 TOTAL LINKS: {len(links)}")
    return links


# ==============================
# Lấy thông tin truyện + chapter
# ==============================
def scrape_story(url):
    print(f"\n=== 📘 SCRAPING STORY ===")
    print(url)

    html = requests.get(url).text
    soup = BeautifulSoup(html, "lxml")

    # TITLE
    title_node = soup.select_one(".title-detail")
    title = title_node.text.strip() if title_node else "No Title"

    # COVER
    cover_node = soup.select_one(".detail-info img")
    cover = cover_node.get("src") if cover_node else ""

    # DESCRIPTION
    des = soup.select_one(".detail-content p")
    description = des.text.strip() if des else ""

    # CHAPTER LIST
    chapters = []
    chapter_nodes = soup.select(".list-chapter li a")

    for c in chapter_nodes:
        ch_name = c.text.strip()
        ch_url = c.get("href")

        # Lấy ảnh trong chapter
        chapters.append({
            "chapter": ch_name,
            "images": scrape_chapter_images(ch_url)
        })

        time.sleep(0.5)

    return {
        "name": title,
        "cover": cover,
        "description": description,
        "chapters": chapters
    }


# ==============================
# Lấy ảnh trong 1 chapter
# ==============================
def scrape_chapter_images(url):
    html = requests.get(url).text
    soup = BeautifulSoup(html, "lxml")

    imgs = []
    for img in soup.select(".page-chapter img"):
        link = img.get("data-src") or img.get("src")
        if link:
            imgs.append(link)

    return imgs


# ==============================
# Upload lên API
# ==============================
def upload_story(data):
    if not API_BASE:
        print("❌ API_BASE_URL is empty!")
        return False

    try:
        res = requests.post(f"{API_BASE}/api/stories/create", json=data)
        print(f"📤 API Response: {res.status_code} - {res.text}")
        return True
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False


# ==============================
# MAIN
# ==============================
def main():
    posted = load_posted()
    all_links = get_story_links()

    # Lọc ra các truyện chưa đăng
    new_links = [l for l in all_links if l not in posted]

    if not new_links:
        print("🎉 No new stories left.")
        return

    print(f"\n📌 Stories remaining: {len(new_links)}")
    print(f"🚀 Will upload next {STORIES_PER_RUN} stories")

    upload_count = 0

    for url in new_links:
        if upload_count >= STORIES_PER_RUN:
            break

        data = scrape_story(url)

        if upload_story(data):
            posted.append(url)
            upload_count += 1
            print(f"✅ Uploaded {upload_count}/{STORIES_PER_RUN}")
        else:
            print("❌ Skipped due to error")

        save_posted(posted)
        time.sleep(1)

    print("\n🎯 DONE for this run.")


if __name__ == "__main__":
    main()
