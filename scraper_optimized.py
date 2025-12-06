import os
import json
import time
import requests
from bs4 import BeautifulSoup
from git import Repo

# ----------------------------
# CONFIG
# ----------------------------
STORIES_FILE = "stories.json"
MAX_STORIES_PER_RUN = 3       # số truyện scrape mỗi run
MAX_CHAPTERS_PER_STORY = 10   # số chapter mới scrape mỗi truyện

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

# ----------------------------
# TOKEN CỨNG + REPO
# ----------------------------
# Thay token và repo URL của bạn
GITHUB_TOKEN = "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"
GITHUB_USER = "pro-coconut"
REPO_NAME = "pro-coconut.github.io"
REPO_URL = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{REPO_NAME}.git"

# ----------------------------
# UTILITIES
# ----------------------------
def safe_get(url):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return r
        except:
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

def scrape_story(story_url, existing_chapters=None):
    r = safe_get(story_url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    title = soup.select_one("h1.title-detail").text.strip() if soup.select_one("h1.title-detail") else "Không rõ"
    author = soup.select_one("p.author a").text.strip() if soup.select_one("p.author a") else "Không rõ"
    description = soup.select_one("div.detail-content p").text.strip() if soup.select_one("div.detail-content p") else ""
    thumbnail = soup.select_one("div.detail-info img").get("src") if soup.select_one("div.detail-info img") else ""

    chapter_links = []
    for a in soup.select("div.list-chapter a"):
        href = a.get("href")
        if href and href.startswith("/"):
            href = "https://nettruyen0209.com" + href
        chapter_links.append(href)

    chapter_links = chapter_links[::-1]  # chapter 1 → N
    chapters = existing_chapters[:] if existing_chapters else []

    scraped_nums = [int(c["name"].replace("Chapter","").strip()) for c in chapters if c["name"].lower().startswith("chapter")]
    new_chapters = 0

    for i, ch_url in enumerate(chapter_links, start=1):
        if i in scraped_nums:
            continue
        if new_chapters >= MAX_CHAPTERS_PER_STORY:
            break
        print(f"Scraping {title} - Chapter {i}")
        imgs = scrape_chapter(ch_url)
        if imgs:
            chapters.append({"name": f"Chapter {i}", "images": imgs})
            new_chapters += 1
        time.sleep(1)

    chapters.sort(key=lambda x:int(x["name"].replace("Chapter","").strip()))
    return {
        "id": story_url.rstrip("/").split("/")[-1],
        "title": title,
        "author": author,
        "description": description,
        "thumbnail": thumbnail,
        "chapters": chapters
    }

# ----------------------------
# PUSH TO GITHUB USING TOKEN CỨNG
# ----------------------------
def push_to_github():
    repo = Repo(".")
    origin = repo.remote(name="origin")
    origin.set_url(REPO_URL)

    repo.git.add(STORIES_FILE)
    repo.index.commit("Update stories.json via bot")
    origin.push()
    print("[INFO] stories.json pushed successfully!")

# ----------------------------
# RUN SCRAPER
# ----------------------------
def run_scraper():
    stories = load_stories()
    story_dict = {s["id"]: s for s in stories}
    added_stories = 0

    for page in range(1, 6):  # scan 5 page đầu
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
            story_id = href.rstrip("/").split("/")[-1]
            existing_chapters = story_dict[story_id]["chapters"] if story_id in story_dict else None
            story_data = scrape_story(href, existing_chapters)
            if not story_data or not story_data["chapters"]:
                continue
            story_dict[story_id] = story_data
            added_stories += 1
            print(f"[DONE] Story scraped: {story_data['title']} ({added_stories}/{MAX_STORIES_PER_RUN})")
            if added_stories >= MAX_STORIES_PER_RUN:
                break
        if added_stories >= MAX_STORIES_PER_RUN:
            break

    save_stories(list(story_dict.values()))
    push_to_github()
    print("[INFO] Bot run finished.")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    run_scraper()
