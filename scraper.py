import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import quote, urljoin

# Cấu hình
BASE_URL = "https://nettruyen0209.com"
DELAY = 5  # Delay an toàn
NUM_TRUYEN_QUET = 10  # Quét 10 truyện để test nhanh

def get_all_stories():
    """Quét trang chủ lấy danh sách truyện – dùng urljoin để sửa URL thiếu scheme"""
    url = BASE_URL + "/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        stories = []
        items = soup.select('.story-item a[href*="/manga/"], .manga-item a, .item a, h3 a, li a')[:NUM_TRUYEN_QUET]
        for item in items:
            try:
                title = item.get('title') or item.text.strip()
                if not title or len(title) < 5:
                    continue
                href = item.get('href', '')
                link = urljoin(BASE_URL, href)  # ← SỬA LỖI URL THIẾU SCHEME
                stories.append({'title': title, 'link': link})
                print(f"Tìm thấy: {title}")
            except Exception as e:
                print(f"Lỗi item: {e}")
                continue
        return stories if stories else []
    except Exception as e:
        print(f"Lỗi quét trang chủ: {e}")
        return []

def scrape_story_detail(url):
    """Scrape chi tiết 1 truyện + chapter mới nhất – tăng timeout, urljoin an toàn"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    try:
        res = requests.get(url, headers=headers, timeout=30)  # Tăng timeout
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        # Title
        title_elem = soup.find("h1", class_="title-detail") or soup.find("h1")
        title = title_elem.text.strip() if title_elem else "Không có tên"
        story_id = re.sub(r'[^a-z0-9]', '', title.lower())

        # Author
        author_elem = soup.find("li", string=re.compile("Tác giả")) or soup.find("span", class_="author")
        author = author_elem.find_next("a").text.strip() if author_elem else "Không rõ"

        # Description
        desc_elem = soup.find("div", class_="detail-content") or soup.find("p", class_="desc")
        desc = desc_elem.get_text(strip=True)[:500] + "..." if desc_elem else "Chưa có tóm tắt"

        # Cover
        cover_elem = soup.find("div", class_="col-image") or soup.find("img", class_="cover")
        cover = cover_elem.get("src") if cover_elem and cover_elem.get("src") else ""

        # Latest chapter
        latest_chap = soup.find("a", class_="chapter-row") or soup.find("a", class_="chapter")
        if not latest_chap:
            print("Không tìm thấy chapter")
            return None
        chap_name = latest_chap.text.strip()
        chap_href = latest_chap.get("href", "")
        chap_url = urljoin(BASE_URL, chap_href)  # ← SỬA LỖI URL THIẾU SCHEME CHO CHAPTER

        time.sleep(DELAY)
        ch_res = requests.get(chap_url, headers=headers, timeout=30)
        ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
        images = []
        for img in ch_soup.find_all("img", class_="page-break") or ch_soup.find_all("img", class_="page"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if src and src.startswith("http"):
                images.append(src)

        return {
            "id": story_id,
            "title": title,
            "author": author,
            "description": desc,
            "thumbnail": cover,
            "new_chapter": {"name": chap_name, "images": images}
        }
    except Exception as e:
        print(f"Lỗi scrape chi tiết {url}: {e}")
        return None

def update_stories(new_data):
    """Kiểm tra mới/cũ, thêm truyện/chapter mới"""
    if not os.path.exists("stories.json"):
        with open("stories.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    with open("stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    exist = next((s for s in stories if s["id"] == new_data["id"]), None)
    if not exist:
        stories.append({
            "id": new_data["id"],
            "title": new_data["title"],
            "author": new_data["author"],
            "description": new_data["description"],
            "thumbnail": new_data["thumbnail"],
            "chapters": [new_data["new_chapter"]]
        })
        print(f"THÊM TRUYỆN MỚI: {new_data['title']}")
    else:
        if not any(ch["name"] == new_data["new_chapter"]["name"] for ch in exist["chapters"]):
            exist["chapters"].append(new_data["new_chapter"])
            print(f"THÊM CHAPTER MỚI: {new_data['new_chapter']['name']} - {new_data['title']}")
        else:
            print(f"Chapter đã có: {new_data['title']}")

    with open("stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)

# MAIN
if __name__ == "__main__":
    print("Bot bắt đầu quét nettruyen0209.com...")
    hot_list = get_all_stories()
    print(f"Tìm thấy {len(hot_list)} truyện từ trang chủ")

    for item in hot_list:
        data = scrape_story_detail(item["link"])
        if data:
            update_stories(data)
        time.sleep(DELAY)

    print("Bot hoàn thành – cập nhật stories.json!")
