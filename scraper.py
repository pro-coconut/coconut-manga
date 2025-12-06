import os
import json
import time
import requests
from bs4 import BeautifulSoup

API_BASE_URL = os.getenv("API_BASE_URL")
START_PAGE = int(os.getenv("START_PAGE", 1))
MAX_PAGES = int(os.getenv("MAX_PAGES", 5))
STORIES_PER_RUN = int(os.getenv("STORIES_PER_RUN", 3))
BATCH_SIZE = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

STORIES_FILE = "stories.json"

# ----------------------------
# Load / Save stories.json
# ----------------------------

def load_stories():
    if not os.path.exists(STORIES_FILE):
        return []
    try:
        with open(STORIES_FILE, "r", encoding="utf8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print("ERROR loading stories.json:", e)
        return []

def save_stories(data):
    try:
        with open(STORIES_FILE, "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("ERROR saving stories.json:", e)

# ----------------------------
# Safe request
# ----------------------------

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

# ----------------------------
# Scrape chapter images
# ----------------------------

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") or img.get("data-src") for img in imgs if img.get("src") or img.get("data-src")]

# ----------------------------
# Scrape story
# ----------------------------

def scrape_story(story_url):
    full_url = story_url if story_url.startswith("http") else "https://nettruyen0209.com" + story_url

    r = safe_get(full_url)
    if not r:
        print("ERROR: cannot GET story page:", full_url)
        return None

    soup = BeautifulSoup(r.text, "lxml")

    # Title
    title_tag = soup.select_one("h1.title-detail")
    title = title_tag.text.strip() if title_tag else "Không rõ"

    # Author
    author_tag = soup.select_one("p.author a")
    author = author_tag.text.strip() if author_tag else "Không rõ"

    # Description
    desc_tag = soup.select_one("div.detail-content p")
    description = desc_tag.text.strip() if desc_tag else ""

    # Thumbnail
    thumb_tag = soup.select_one("div.detail-info img")
    thumbnail = thumb_tag.get("src") if thumb_tag else ""

    # ID từ slug URL
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

    print(f"Found {max_chapter} chapters for {title}")

    # Tạo chapters list
    chapters = []
    for i in range(1, max_chapter + 1):
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

    if len(chapters) == 0:
        print("ERROR: no chapters with images found for", title)
        return None

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
# MAIN
# ----------------------------

def main():
    stories = load_stories()
    posted_ids = {s["id"] for s in stories if "id" in s}

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
            if story_id in posted_ids:
                continue

            print("\n== SCRAPE:", story_url, "==")
            story_data = scrape_story(story_url)
            if not story_data:
                print("FAILED story, skip.")
                continue

            stories.append(story_data)
            save_stories(stories)
            added += 1

            if added >= STORIES_PER_RUN:
                print("\nDONE:", added, "stories this run.")
                return

            time.sleep(2)

    print("\nEND — no more stories.")

if __name__ == "__main__":
    main()
