import os
import json
import time
import requests
from bs4 import BeautifulSoup
import threading

# ----------------------------
# CONFIG
# ----------------------------
API_BASE_URL = os.getenv("API_BASE_URL")
START_PAGE = int(os.getenv("START_PAGE", 1))
MAX_PAGES = int(os.getenv("MAX_PAGES", 5))
STORIES_PER_RUN = int(os.getenv("STORIES_PER_RUN", 3))
BATCH_SIZE = 5
MAX_CHAPTERS_PER_STORY = None  # None = scrape tất cả chapter
RUN_INTERVAL_MINUTES = 30      # Auto run mỗi 30 phút

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

STORIES_FILE = "stories.json"

# ----------------------------
# UTILITIES
# ----------------------------
def load_stories():
    if not os.path.exists(STORIES_FILE):
        return []
    try:
        with open(STORIES_FILE, "r", encoding="utf8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print("ERROR loading stories.json:", e)
        return []

def save_stories(data):
    try:
        with open(STORIES_FILE, "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("ERROR saving stories.json:", e)

def safe_get(url):
    for _ in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                return r
            print("WARNING: status code", r.status_code, "for", url)
            time.sleep(2)
        except Exception as e:
            print("WARNING: request error:", e)
            time.sleep(2)
    return None

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") or img.get("data-src") for img in imgs if img.get("src") or img.get("data-src")]

# ----------------------------
# SCRAPER
# ----------------------------
def scrape_story(story_url, existing_chapters=None):
    full_url = story_url if story_url.startswith("http") else "https://nettruyen0209.com" + story_url

    r = safe_get(full_url)
    if not r:
        print("ERROR: cannot GET story page:", full_url)
        return None

    soup = BeautifulSoup(r.text, "lxml")

    title_tag = soup.select_one("h1.title-detail")
    title = title_tag.text.strip() if title_tag else "Không rõ"

    author_tag = soup.select_one("p.author a")
    author = author_tag.text.strip() if author_tag else "Không rõ"

    desc_tag = soup.select_one("div.detail-content p")
    description = desc_tag.text.strip() if desc_tag else ""

    thumb_tag = soup.select_one("div.detail-info img")
    thumbnail = thumb_tag.get("src") if thumb_tag else ""

    story_id = story_url.rstrip("/").split("/")[-1]

    # Lấy max chapter
    chapter_links = soup.select("div.list-chapter a")
    max_chapter = 0
    for a in chapter_links:
        text = a.text.strip().lower()
        if text.startswith("chapter"):
            try:
                num = int(text.replace("chapter", "").strip())
                if num > max_chapter:
                    max_chapter = num
            except:
                continue

    if max_chapter == 0:
        print("ERROR: cannot determine max chapter for", title)
        return None

    # Tính chapter cần scrape
    start_chapter = 1
    if existing_chapters:
        scraped_nums = []
        for c in existing_chapters:
            if c.lower().startswith("chapter"):
                try:
                    n = int(c.lower().replace("chapter", "").strip())
                    scraped_nums.append(n)
                except:
                    continue
        start_chapter = max(scraped_nums + [0]) + 1

    end_chapter = max_chapter if MAX_CHAPTERS_PER_STORY is None else min(max_chapter, MAX_CHAPTERS_PER_STORY)
    if start_chapter > end_chapter:
        print("All chapters already scraped for", title)
        return {
            "id": story_id,
            "title": title,
            "author": author,
            "description": description,
            "thumbnail": thumbnail,
            "chapters": []
        }

    chapters = []
    for i in range(start_chapter, end_chapter + 1):
        chapter_url = f"{full_url}/chapter-{i}"
        images = scrape_chapter(chapter_url)
        if len(images) == 0:
            print(f"WARNING: chapter {i} has no images, skip")
            continue
        chapters.append({
            "name": f"Chapter {i}",
            "images": images
        })
        time.sleep(1)

    story_data = {
        "id": story_id,
        "title": title,
        "author": author,
        "description": description,
        "thumbnail": thumbnail,
        "chapters": chapters
    }

    return story_data

# ----------------------------
# MAIN SCRAPER RUN
# ----------------------------
def run_scraper():
    stories = load_stories()
    story_dict = {s["id"]: s for s in stories if "id" in s}

    added = 0

    for page in range(START_PAGE, MAX_PAGES + 1):
        page_url = f"https://nettruyen0209.com/?page={page}"
        print("\nSCAN PAGE:", page_url)

        r = safe_get(page_url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("div.item > a")

        story_links = []
        for a in items:
            href = a.get("href")
            if href:
                if not href.startswith("http"):
                    href = "https://nettruyen0209.com" + href
                story_links.append(href)

        for story_url in story_links:
            story_id = story_url.rstrip("/").split("/")[-1]
            existing_chapters = None
            if story_id in story_dict:
                existing_chapters = [c["name"] for c in story_dict[story_id].get("chapters", [])]

            print("\n== SCRAPE:", story_url, "==")
            story_data = scrape_story(story_url, existing_chapters=existing_chapters)
            if not story_data:
                print("FAILED story, skip.")
                continue

            # Nếu truyện đã có, append chapter mới
            if story_id in story_dict:
                story_dict[story_id]["chapters"].extend(story_data["chapters"])
                # Sắp xếp chapter theo số
                story_dict[story_id]["chapters"].sort(key=lambda x: int(x["name"].replace("Chapter", "").strip()))
            else:
                story_dict[story_id] = story_data

            save_stories(list(story_dict.values()))
            added += 1

            if added >= STORIES_PER_RUN:
                print("\nDONE:", added, "stories this run.")
                return

            time.sleep(2)

    print("\nEND — no more stories.")

# ----------------------------
# AUTO RUN THREAD
# ----------------------------
def auto_run():
    while True:
        print("\n===== BOT RUN START =====")
        try:
            run_scraper()
        except Exception as e:
            print("ERROR in scraper run:", e)
        print(f"Bot sleeping for {RUN_INTERVAL_MINUTES} minutes...\n")
        time.sleep(RUN_INTERVAL_MINUTES * 60)

# ----------------------------
# START BOT
# ----------------------------
if __name__ == "__main__":
    print("Starting auto scraper bot...")
    # Chạy bot trong thread để có thể mở rộng nếu muốn GUI hoặc web interface sau này
    t = threading.Thread(target=auto_run, daemon=True)
    t.start()

    # Giữ main thread sống
    while True:
        time.sleep(60)
