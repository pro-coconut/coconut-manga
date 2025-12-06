import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import urljoin

BASE_URL = "https://nettruyen0209.com"
DELAY = 3
NUM_TRUYEN_QUET = 10

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
    'Accept-Language': 'vi,en;q=0.9'
}

# ================================
# LẤY ẢNH 1 CHAPTER
# ================================
def scrape_chapter(chap_url):
    try:
        time.sleep(DELAY)
        res = requests.get(chap_url, headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")

        images = []
        for img in soup.select(".page-chapter img, img.lazy, img.page"):
            src = img.get("src") or img.get("data-src") or ""
            if src.startswith("http"):
                images.append(src)

        return images

    except Exception as e:
        print("⚠ Lỗi tải chapter:", e)
        return []


# ================================
# LẤY CHI TIẾT TRUYỆN + TOÀN BỘ CHAPTER
# ================================
def scrape_story_detail(url):
    try:
        print(f"\n=== Đang lấy truyện: {url}")
        res = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")

        # Lấy tiêu đề truyện
        title_elem = soup.select_one("h1.title-detail")
        if not title_elem:
            print("❌ Không tìm thấy tiêu đề!")
            return None

        title = title_elem.get_text(strip=True)
        sid = re.sub(r'[^a-z0-9]', '', title.lower())

        # Lấy toàn bộ chapter
        chap_elems = soup.select(".list-chapter li a, ul.row-content-chapter li a")

        if not chap_elems:
            print("❌ Không tìm thấy chapter nào!")
            return None

        chapters = []
        print(f"➡ Found {len(chap_elems)} chapters")

        for a in reversed(chap_elems):  # đảo để chap1 → chapN
            chap_name = a.text.strip()
            chap_url = urljoin(BASE_URL, a.get("href"))

            print(f" → Tải {chap_name} ...")
            images = scrape_chapter(chap_url)

            chapters.append({
                "name": chap_name,
                "images": images
            })

        return {
            "id": sid,
            "title": title,
            "author": "Không rõ",
            "description": "Đang cập nhật...",
            "thumbnail": "",
            "chapters": chapters
        }

    except Exception as e:
        print("Lỗi scrape chi tiết:", e)
        return None


# ================================
# UPDATE stories.json
# ================================
def update_stories(new_data):
    if not os.path.exists("stories.json"):
        with open("stories.json", "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

    with open("stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    exist = next((s for s in stories if s["id"] == new_data["id"]), None)

    if not exist:
        print(f"🟢 Thêm truyện mới: {new_data['title']}")
        stories.append(new_data)
    else:
        print(f"🔍 Truyện đã tồn tại: {new_data['title']}")
        exist_chaps = {c["name"] for c in exist["chapters"]}

        for chap in new_data["chapters"]:
            if chap["name"] not in exist_chaps:
                print(f"   → Thêm chapter mới: {chap['name']}")
                exist["chapters"].append(chap)

    with open("stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2, ensure_ascii=False)


# ================================
# MAIN SCRAPER
# ================================
def get_hot_stories():
    print("Đang quét danh sách truyện mới...")
    try:
        res = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        items = soup.select(".item .title a")[:NUM_TRUYEN_QUET]

        stories = []
        for a in items:
            title = a.get("title") or a.text.strip()
            link = urljoin(BASE_URL, a.get("href"))
            print("✔", title)
            stories.append({
                "title": title,
                "link": link
            })

        return stories

    except Exception as e:
        print("Lỗi quét trang chủ:", e)
        return []


# ================================
# CHẠY BOT
# ================================
if __name__ == "__main__":
    print("=== BOT BẮT ĐẦU ===")

    hot = get_hot_stories()
    print(f"\n➡ Tổng {len(hot)} truyện tìm thấy\n")

    for item in hot:
        data = scrape_story_detail(item["link"])
        if data:
            update_stories(data)

    print("\n=== BOT HOÀN THÀNH ===")
