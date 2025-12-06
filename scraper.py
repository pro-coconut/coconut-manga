import os
import json
import time
import requests
from bs4 import BeautifulSoup
from git import Repo

# ----------------------------
# CONFIG
# ----------------------------
# Lấy token từ secret workflow
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN_BOT")
if not GITHUB_TOKEN:
    raise ValueError("Missing GitHub token! Set secret MY_GITHUB_TOKEN and map to GITHUB_TOKEN_BOT in workflow.")

REPO_URL = "https://github.com/pro-coconut/pro-coconut.github.io.git"
LOCAL_REPO = "pro-coconut-site"
STORIES_FILE = "stories.json"

START_PAGE = 1
MAX_PAGES = 5
STORIES_PER_RUN = 3
MAX_CHAPTERS_PER_RUN = 50

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

# ----------------------------
# UTILITIES
# ----------------------------
def safe_get(url):
    for _ in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                return r
            time.sleep(2)
        except:
            time.sleep(2)
    return None

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") or img.get("data-src") for img in imgs if img.get("src") or img.get("data-src")]

def load_stories():
    path = os.path.join(LOCAL_REPO, STORIES_FILE)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)

def save_stories(data):
    path = os.path.join(LOCAL_REPO, STORIES_FILE)
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ----------------------------
# SCRAPE STORY
# ----------------------------
def scrape_story(story_url, existing_chapters=None):
    full_url = story_url if story_url.startswith("http") else "https://nettruyen0209.com" + story_url

    r = safe_get(full_url)
    if not r:
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

    chapter_links = soup.select("div.list-chapter a")
    max_chapter = 0
    for a in chapter_links:
        text = a.text.lower().strip()
        if text.startswith("chapter"):
            try:
                n = int(text.replace("chapter","").strip())
                if n > max_chapter:
                    max_chapter = n
            except:
                continue

    start_chapter = 1
    if existing_chapters:
        scraped_nums = [int(c["name"].replace("Chapter","").strip()) for c in existing_chapters if c["name"].lower().startswith("chapter")]
        start_chapter = max(scraped_nums+[0]) + 1

    end_chapter = max_chapter if MAX_CHAPTERS_PER_RUN is None else min(max_chapter, MAX_CHAPTERS_PER_RUN)
    if start_chapter > end_chapter:
        return {"id": story_id, "title": title, "author": author, "description": description, "thumbnail": thumbnail, "chapters":[]}

    chapters = []
    for i in range(start_chapter, end_chapter+1):
        chapter_url = f"{full_url}/chapter-{i}"
        imgs = scrape_chapter(chapter_url)
        if imgs:
            chapters.append({"name": f"Chapter {i}", "images": imgs})
        time.sleep(0.5)

    return {"id": story_id, "title": title, "author": author, "description": description, "thumbnail": thumbnail, "chapters": chapters}

# ----------------------------
# PUSH TO GITHUB
# ----------------------------
def push_to_github():
    if not os.path.exists(LOCAL_REPO):
        Repo.clone_from(f"https://{GITHUB_TOKEN}@github.com/pro-coconut/pro-coconut.github.io.git", LOCAL_REPO)
    repo = Repo(LOCAL_REPO)
    repo.git.add(STORIES_FILE)
    repo.index.commit("Update stories.json via GitHub Actions bot")
    repo.remote().push()
    print("stories.json pushed to GitHub Pages!")

# ----------------------------
# RUN SCRAPER
# ----------------------------
def run_scraper():
    stories = load_stories()
    story_dict = {s["id"]: s for s in stories}

    added = 0
    for page in range(START_PAGE, MAX_PAGES+1):
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
                href = "https://nettruyen0209.com"+href
            story_id = href.rstrip("/").split("/")[-1]
            existing_chapters = story_dict[story_id]["chapters"] if story_id in story_dict else None
            story_data = scrape_story(href, existing_chapters)
            if not story_data:
                continue
            if story_id in story_dict:
                story_dict[story_id]["chapters"].extend(story_data["chapters"])
                story_dict[story_id]["chapters"].sort(key=lambda x:int(x["name"].replace("Chapter","").strip()))
            else:
                story_dict[story_id] = story_data
            save_stories(list(story_dict.values()))
            added += 1
            if added >= STORIES_PER_RUN:
                break
        if added >= STORIES_PER_RUN:
            break
    push_to_github()
    print("Bot run finished.")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    run_scraper()
