import os
import json
import time
import requests
from bs4 import BeautifulSoup
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------
# CONFIG
# ----------------------------
STORIES_FILE = "stories.json"
PRIORITY_FILE = "priority_stories.txt"
CHAPTER_DELAY = 1
CHAPTER_RETRY = 3
MAX_WORKERS = 5  # số truyện scrape đồng thời
MAX_STORIES_PER_RUN = 5
GITHUB_USER = "pro-coconut"
GITHUB_REPO = "pro-coconut.github.io"
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Missing GitHub token! Set MY_GITHUB_TOKEN in workflow secrets.")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

# ----------------------------
# UTILITIES
# ----------------------------
def safe_get(url, retries=CHAPTER_RETRY):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return r
        except Exception as e:
            print(f"[WARN] Error fetching {url}: {e}")
        time.sleep(1)
    return None

def load_stories():
    if not os.path.exists(STORIES_FILE):
        return []
    with open(STORIES_FILE, "r", encoding="utf8") as f:
        return json.load(f)

def save_stories(data):
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_priority_stories():
    if not os.path.exists(PRIORITY_FILE):
        return []
    with open(PRIORITY_FILE, "r", encoding="utf8") as f:
        return [line.strip() for line in f if line.strip()]

# ----------------------------
# SCRAPE FUNCTIONS
# ----------------------------
def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") or img.get("data-src") for img in imgs if img.get("src") or img.get("data-src")]

def scrape_story(story_url, last_chapter_scraped=0):
    r = safe_get(story_url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    title = soup.select_one("h1.title-detail").text.strip() if soup.select_one("h1.title-detail") else "Không rõ"
    author = soup.select_one("p.author a").text.strip() if soup.select_one("p.author a") else "Không rõ"
    description = soup.select_one("div.detail-content p").text.strip() if soup.select_one("div.detail-content p") else ""
    thumbnail = soup.select_one("div.detail-info img").get("src") if soup.select_one("div.detail-info img") else ""

    # Lấy tất cả chapter
    chapter_links = []
    for a in soup.select("div.list-chapter a"):
        href = a.get("href")
        if href and href.startswith("/"):
            href = "https://nettruyen0209.com" + href
        chapter_links.append(href)

    chapter_links = chapter_links[::-1]  # chapter 1 → N
    chapters = []

    for i, ch_url in enumerate(chapter_links, start=1):
        if i <= last_chapter_scraped:
            continue
        print(f"Scraping {title} - Chapter {i}")
        imgs = scrape_chapter(ch_url)
        if not imgs:
            print(f"[WARN] Chapter {i} failed or no images, skip.")
            continue
        chapters.append({"name": f"Chapter {i}", "images": imgs})
        time.sleep(CHAPTER_DELAY)

    return {
        "id": story_url.rstrip("/").split("/")[-1],
        "title": title,
        "author": author,
        "description": description,
        "thumbnail": thumbnail,
        "chapters": chapters,
        "last_chapter_scraped": last_chapter_scraped + len(chapters)
    }

# ----------------------------
# PUSH TO GITHUB
# ----------------------------
def push_to_github():
    url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
    subprocess.run(["git", "config", "user.name", "bot"], check=True)
    subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
    subprocess.run(["git", "add", STORIES_FILE], check=True)
    subprocess.run(["git", "commit", "-m", "Update stories.json via bot"], check=False)
    subprocess.run(["git", "push", url, "HEAD:main"], check=True)
    print("[INFO] stories.json pushed successfully!")

# ----------------------------
# MAIN RUNNER
# ----------------------------
def run_scraper():
    stories = load_stories()
    story_dict = {s["id"]: s for s in stories}
    added_stories = 0

    priority_urls = load_priority_stories()
    all_urls = priority_urls.copy()

    # Quét các trang khác nếu cần
    for page in range(1, 6):
        page_url = f"https://nettruyen0209.com/?page={page}"
        r = safe_get(page_url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("div.item > a")
        for a in items:
            href = a.get("href")
            if not href:
                continue
            if not href.startswith("http"):
                href = "https://nettruyen0209.com" + href
            if href not in all_urls:
                all_urls.append(href)

    # ThreadPool scrape
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {}
        for href in all_urls:
            story_id = href.rstrip("/").split("/")[-1]
            last_scraped = story_dict[story_id]["last_chapter_scraped"] if story_id in story_dict else 0
            future = executor.submit(scrape_story, href, last_scraped)
            future_to_url[future] = href

        for future in as_completed(future_to_url):
            story_data = future.result()
            if not story_data or not story_data["chapters"]:
                continue

            story_id = story_data["id"]
            if story_id in story_dict:
                story_dict[story_id]["chapters"].extend(story_data["chapters"])
                story_dict[story_id]["last_chapter_scraped"] = story_data["last_chapter_scraped"]
            else:
                story_dict[story_id] = story_data

            added_stories += 1
            print(f"[DONE] Story scraped: {story_data['title']} ({added_stories})")
            save_stories(list(story_dict.values()))
            if added_stories >= MAX_STORIES_PER_RUN:
                push_to_github()
                return

    push_to_github()
    print("[INFO] Multi-thread bot run finished.")

if __name__ == "__main__":
    run_scraper()
