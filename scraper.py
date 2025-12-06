import os
import json
import time
import requests
from bs4 import BeautifulSoup
from git import Repo
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------
# CONFIG
# ----------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN_BOT")
if not GITHUB_TOKEN:
    raise ValueError("Missing GitHub token! Set secret MY_GITHUB_TOKEN and map to GITHUB_TOKEN_BOT in workflow.")

STORIES_FILE = "stories.json"
START_PAGE = 1
MAX_PAGES = 5
STORIES_PER_RUN = 3
MAX_CHAPTERS_PER_RUN = 50
MAX_WORKERS = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

# ----------------------------
# UTILITIES
# ----------------------------
def safe_get(url):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return r
            print(f"[WARNING] Status {r.status_code} for {url}")
        except Exception as e:
            print(f"[WARNING] Request error: {e} for {url}")
        time.sleep(1)
    return None

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") or img.get("data-src") for img in imgs if img.get("src") or img.get("data-src")]

def load_stories():
    if not os.path.exists(STORIES_FILE):
        return []
    with open(STORIES_FILE, "r", encoding="utf8") as f:
        return json.load(f)

def save_stories(data):
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ----------------------------
# SCRAPE STORY
# ----------------------------
def scrape_story(story_url, existing_chapters=None):
    full_url = story_url if story_url.startswith("http") else "https://nettruyen0209.com" + story_url

    r = safe_get(full_url)
    if not r:
        print(f"[ERROR] Cannot fetch story page: {story_url}")
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

    end_chapter = max_chapter if MAX_CHAPTERS_PER_RUN is None else min(max_chapter, start_chapter + MAX_CHAPTERS_PER_RUN -1)
    if start_chapter > end_chapter:
        print(f"[INFO] Story {title} is up-to-date. No new chapters.")
        return {"id": story_id, "title": title, "author": author, "description": description, "thumbnail": thumbnail, "chapters":[]}

    chapters = []

    def fetch_chapter(i):
        chapter_url = f"{full_url}/chapter-{i}"
        imgs = scrape_chapter(chapter_url)
        if imgs:
            print(f"[OK] Scraped {title} - Chapter {i} ({len(imgs)} images)")
            return {"name": f"Chapter {i}", "images": imgs}
        else:
            print(f"[SKIP] {title} - Chapter {i} has no images")
        return None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_chapter, i) for i in range(start_chapter, end_chapter+1)]
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                chapters.append(result)

    chapters.sort(key=lambda x:int(x["name"].replace("Chapter","").strip()))
    return {"id": story_id, "title": title, "author": author, "description": description, "thumbnail": thumbnail, "chapters": chapters}

# ----------------------------
# PUSH TO GITHUB
# ----------------------------
def push_to_github():
    if not os.path.exists(".git"):
        Repo.clone_from(f"https://{GITHUB_TOKEN}@github.com/pro-coconut/pro-coconut.github.io.git", ".")
    repo = Repo(".")
    repo.git.add(STORIES_FILE)
    repo.index.commit("Update stories.json via GitHub Actions bot")
    repo.remote().push()
    print("[INFO] stories.json pushed to GitHub Pages!")

# ----------------------------
# RUN SCRAPER
# ----------------------------
def run_scraper():
    stories = load_stories()
    story_dict = {s["id"]: s for s in stories}

    added = 0
    for page in range(START_PAGE, MAX_PAGES+1):
        page_url = f"https://nettruyen0209.com/?page={page}"
        print(f"[SCAN] Page {page_url}")
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
            if not story_data or not story_data["chapters"]:
                continue
            if story_id in story_dict:
                story_dict[story_id]["chapters"].extend(story_data["chapters"])
                # loại trùng chapter
                unique = {}
                for c in story_dict[story_id]["chapters"]:
                    unique[c["name"]] = c
                story_dict[story_id]["chapters"] = sorted(unique.values(), key=lambda x:int(x["name"].replace("Chapter","").strip()))
            else:
                story_dict[story_id] = story_data

            save_stories(list(story_dict.values()))
            added += 1
            print(f"[DONE] Story scraped: {story_data['title']} ({added}/{STORIES_PER_RUN})")
            time.sleep(2)

            if added >= STORIES_PER_RUN:
                break
        if added >= STORIES_PER_RUN:
            break

    push_to_github()
    print("[INFO] Bot run finished.")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    run_scraper()
