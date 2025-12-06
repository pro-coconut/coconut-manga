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
    # lấy src hoặc data-src
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

    # Lấy title
    title_tag = soup.select_one("h1.title-detail")
    if not title_tag:
        print("ERROR: cannot find title")
        return None
    title = title_tag.text.strip()

    # Lấy chapter links
    chapter_links = [a.get("href") for a in soup.select("div.list-chapter a") if a.get("href")]
    if not chapter_links:
        print("ERROR: no chapters found for", title)
        return None

    chapter_links = chapter_links[::-1]  # old → new

    chapters = []
    for i, ch in enumerate(chapter_links):
        chapter_url = ch if ch.startswith("http") else "https://nettruyen0209.com" + ch
        images = scrape_chapter(chapter_url)
        if len(images) == 0:
            print(f"WARNING: chapter {i+1} has no images, skip")
            continue
        chapters.append({
            "chapter": i + 1,
            "images": images
        })
        time.sleep(1)

    if len(chapters) == 0:
        print("ERROR: no chapters with images found for", title)
        return None

    return title, chapters

# ----------------------------
# Upload batch
# ----------------------------

def upload_batch(title, batch):
    payload = {
        "title": title,
        "chapters": batch
    }
    try:
        r = requests.post(
            f"{API_BASE_URL}/api/stories/create",
            json=payload,
            timeout=20
        )
        print("API:", r.status_code, r.text)
        return r.status_code == 200
    except Exception as e:
        print("UPLOAD ERR:", e)
        return False

# ----------------------------
# MAIN
# ----------------------------

def main():
    stories = load_stories()
    posted_urls = {s["url"] for s in stories if "url" in s}

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
            if story_url in posted_urls:
                continue

            print("\n== SCRAPE:", story_url, "==")
            result = scrape_story(story_url)
            if not result:
                print("FAILED story, skip.")
                continue

            title, chapters = result
            if len(chapters) == 0:
                print("No chapters scraped, skip.")
                continue

            # Upload by batch
            for i in range(0, len(chapters), BATCH_SIZE):
                batch = chapters[i:i+BATCH_SIZE]
                ok = upload_batch(title, batch)
                if not ok:
                    print("Batch fail → stop this story")
                    break

            # Save to stories.json
            stories.append({
                "url": story_url,
                "title": title,
                "chapters": len(chapters)
            })
            save_stories(stories)

            added += 1
            if added >= STORIES_PER_RUN:
                print("\nDONE:", added, "stories this run.")
                return

            time.sleep(2)

    print("\nEND — no more stories.")

if __name__ == "__main__":
    main()
