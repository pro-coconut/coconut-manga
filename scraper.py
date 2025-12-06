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
HEADERS = {"User-Agent": "Mozilla/5.0"}


# ==============================
# Safe GET (không bao giờ treo)
# ==============================
def safe_get(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        print("❌ Request failed:", url, "-", e)
        return None


# ==============================
# Load/save posted list
# ==============================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    return json.load(open(POSTED_FILE, "r", encoding="utf-8"))


def save_posted(lst):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, indent=2, ensure_ascii=False)


# ==============================
# Lấy danh sách link truyện
# ==============================
def get_story_links(limit):
    """
    Trả về đúng 'limit' link truyện mới → để bot không quét vô hạn
    """
    links = []

    print("=== 🔍 SCANNING STORIES ===")

    for page in range(START_PAGE, MAX_PAGES + 1):
        if len(links) >= limit:
            break

        url = LIST_URL.format(page=page)
        print(f"📄 Checking page {page}: {url}")

        res = safe_get(url)
        if not res:
            continue

        soup = BeautifulSoup(res.text, "lxml")
        items = soup.select("div.item figure a")

        for a in items:
            if len(links) >= limit:
                break

            link = a.get("href")
            if link.startswith("/"):
                link = DOMAIN + link
            links.append(link)

        time.sleep(0.2)

    print(f"🎉 FOUND {len(links)} LINKS")
    return links


# ==============================
# Lấy hình chapter
# ==============================
def scrape_chapter_images(ch_url):
    res = safe_get(ch_url)
    if not res:
        return []

    soup = BeautifulSoup(res.text, "lxml")
    imgs = []

    for img in soup.select(".page-chapter img"):
        src = img.get("data-src") or img.get("src")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            imgs.append(src)

    return imgs


# ==============================
# Scrap 1 truyện
# ==============================
def scrape_story(url):
    print("\n=== 📘 SCRAPING STORY ===")
    print(url)

    res = safe_get(url)
    if not res:
        return None

    soup = BeautifulSoup(res.text, "lxml")

    title = soup.select_one(".title-detail")
    title = title.text.strip() if title else "No Title"

    cover_node = soup.select_one(".detail-info img")
    cover = cover_node.get("src") if cover_node else ""

    des_node = soup.select_one(".detail-content p")
    description = des_node.text.strip() if des_node else ""

    chapters = []
    ch_nodes = soup.select(".list-chapter li a")

    for c in ch_nodes[::-1]:  # đảo để chapter cũ trước
        ch_name = c.text.strip()
        ch_url = c.get("href")

        if ch_url.startswith("/"):
            ch_url = DOMAIN + ch_url

        imgs = scrape_chapter_images(ch_url)

        chapters.append({
            "chapter": ch_name,
            "images": imgs
        })

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
    try:
        res = requests.post(
            f"{API_BASE}/api/stories/create",
            json=data,
            timeout=10
        )
        print("📤 API:", res.status_code, res.text)
        if res.status_code != 200:
            return False
        return res.json().get("success", False)
    except Exception as e:
        print("❌ API Error:", e)
        return False


# ==============================
# MAIN
# ==============================
def main():
    posted = load_posted()

    # chỉ tìm đúng 3 truyện cần đăng
    links = get_story_links(STORIES_PER_RUN)

    uploaded = 0

    for url in links:
        if uploaded >= STORIES_PER_RUN:
            break

        if url in posted:
            continue

        data = scrape_story(url)
        if not data:
            continue

        if upload_story(data):
            posted.append(url)
            save_posted(posted)
            uploaded += 1
            print(f"✅ Uploaded {uploaded}/{STORIES_PER_RUN}")

    print("\n🎯 DONE.")


if __name__ == "__main__":
    main()
