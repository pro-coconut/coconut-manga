import os
import json
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from git import Repo, GitCommandError

# ----------------------------
# CẤU HÌNH GITHUB
# ----------------------------
GITHUB_TOKEN = "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"  # <-- nhập token ở đây
GITHUB_REPO = "https://github.com/pro-coconut/pro-coconut.github.io.git"
BRANCH = "main"

# ----------------------------
# CẤU HÌNH SCRAPER
# ----------------------------
BASE_URL = "https://nettruyen0209.com"
LIST_URL_TEMPLATE = BASE_URL + "/danh-sach-truyen/{page}/?sort=last_update&status=0"
STORIES_FILE = "stories.json"
MAX_PAGES = 4
MAX_THREADS = 5
STORIES_PER_RUN = 3

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

# ----------------------------
# Load / Save stories.json
# ----------------------------
def load_stories():
    if not os.path.exists(STORIES_FILE):
        return {}
    with open(STORIES_FILE, "r", encoding="utf8") as f:
        data = json.load(f)
        return {s['slug']: s for s in data} if isinstance(data, list) else {}

def save_stories(stories_dict):
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(list(stories_dict.values()), f, ensure_ascii=False, indent=2)

# ----------------------------
# Fetch utils
# ----------------------------
def safe_get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            return r
    except:
        pass
    return None

# ----------------------------
# Scrape chapter images
# ----------------------------
def scrape_chapter(slug, chapter_number):
    url = f"{BASE_URL}/manga/{slug}/chapter-{chapter_number}"
    r = safe_get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    imgs = [img.get("src") for img in soup.select("div.page-chapter img") if img.get("src")]
    if not imgs:
        return None
    print(f"Scraped {slug} - Chapter {chapter_number} ({len(imgs)} images)")
    return {"name": f"Chapter {chapter_number}", "images": imgs}

def scrape_story_chapters(slug, last_chapter=0):
    chapters = []
    chapter_number = last_chapter + 1
    futures = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        while True:
            futures.append(executor.submit(scrape_chapter, slug, chapter_number))
            chapter_number += 1
            if len(futures) >= MAX_THREADS:
                done = [f.result() for f in futures]
                futures.clear()
                any_new = False
                for res in done:
                    if res:
                        chapters.append(res)
                        any_new = True
                if not any_new:
                    return chapters
    # xử lý các future còn lại
    for f in futures:
        res = f.result()
        if res:
            chapters.append(res)
    return chapters

# ----------------------------
# Scrape story info
# ----------------------------
def scrape_story_info(story_url):
    r = safe_get(story_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    title_tag = soup.select_one("h1.title-detail")
    title = title_tag.text.strip() if title_tag else "Unknown"
    author_tag = soup.select_one("a.author")
    author = author_tag.text.strip() if author_tag else "Không rõ"
    desc_tag = soup.select_one("div.detail-content")
    description = desc_tag.text.strip() if desc_tag else ""
    thumb_tag = soup.select_one("div.detail-info img")
    thumbnail = thumb_tag.get("src") if thumb_tag else ""
    slug = story_url.rstrip("/").split("/")[-1]
    return {"slug": slug, "title": title, "author": author,
            "description": description, "thumbnail": thumbnail}

# ----------------------------
# Push stories.json lên GitHub
# ----------------------------
def push_to_github():
    print("[INFO] Pushing stories.json to GitHub...")
    repo_url_with_token = GITHUB_REPO.replace("https://", f"https://{GITHUB_TOKEN}@")
    repo_path = ".temp_repo"
    if not os.path.exists(repo_path):
        Repo.clone_from(repo_url_with_token, repo_path, branch=BRANCH)
    repo = Repo(repo_path)
    repo.git.add(STORIES_FILE)
    repo.index.commit(f"Update stories.json ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    try:
        origin = repo.remote()
        origin.push()
        print("[DONE] Pushed to GitHub successfully.")
    except GitCommandError as e:
        print("[ERROR] Git push failed:", e)

# ----------------------------
# Main scraper
# ----------------------------
def run_scraper():
    stories_dict = load_stories()
    added = 0

    for page in range(4, 4 + MAX_PAGES):
        list_url = LIST_URL_TEMPLATE.format(page=page)
        print("\nSCAN PAGE:", list_url)
        r = safe_get(list_url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("h3.title a")
        for a in items:
            story_url = a.get("href")
            if not story_url or not story_url.startswith(BASE_URL):
                continue
            slug = story_url.rstrip("/").split("/")[-1]
            if slug in stories_dict:
                story_data = stories_dict[slug]
                last_chapter = len(story_data.get("chapters", []))
            else:
                info = scrape_story_info(story_url)
                if not info:
                    print(f"[WARN] Cannot fetch info for {story_url}")
                    continue
                story_data = info
                story_data["chapters"] = []
                last_chapter = 0

            new_chapters = scrape_story_chapters(slug, last_chapter)
            if new_chapters:
                story_data["chapters"].extend(new_chapters)
                stories_dict[slug] = story_data
                save_stories(stories_dict)
                print(f"[DONE] Story scraped: {story_data['title']} ({len(story_data['chapters'])} chapters)")
                added += 1
                if added >= STORIES_PER_RUN:
                    print("\nReached STORIES_PER_RUN limit.")
                    push_to_github()
                    return

    push_to_github()
    print("\nScraper run complete.")

if __name__ == "__main__":
    run_scraper()
