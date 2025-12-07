import os
import json
import time
import requests
from bs4 import BeautifulSoup
from git import Repo
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

# ----------------------------
# CẤU HÌNH
# ----------------------------
REPO_PATH = "."  # root repo
STORIES_FILE = "stories.json"
TOKEN = "nhập_token_của_bạn_vào_đây"  # hoặc lấy từ secret/GITHUB_TOKEN trong workflow
BRANCH = "main"

BASE_URL = "https://nettruyen0209.com"
LIST_PAGE_START = 4
LIST_PAGE_END = 5  # sửa theo nhu cầu
STORIES_PER_RUN = 3
MAX_THREADS = 5

# Danh sách truyện ưu tiên
PRIORITY_SLUGS = [
    "bach-luyen-thanh-than",
    "vo-luyen-dinh-phong",
    "dai-quan-gia-la-ma-hoang"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

# ----------------------------
# Load / Save stories
# ----------------------------
def load_stories():
    if not os.path.exists(STORIES_FILE):
        return {}
    try:
        with open(STORIES_FILE, "r", encoding="utf8") as f:
            data = json.load(f)
            result = {}
            if isinstance(data, list):
                for s in data:
                    slug = s.get("id") or s.get("slug")
                    if slug:
                        result[slug] = s
            return result
    except:
        return {}

def save_stories(data):
    if isinstance(data, dict):
        data = list(data.values())
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ----------------------------
# Request helper
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

# ----------------------------
# Scrape chapter images
# ----------------------------
def scrape_chapter_images(chapter_url):
    r = safe_get(chapter_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter img")
    return [img.get("src") for img in imgs if img.get("src")]

# ----------------------------
# Scrape story info
# ----------------------------
def scrape_story(slug, existing_story=None):
    story_url = f"{BASE_URL}/manga/{slug}"
    r = safe_get(story_url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    title_tag = soup.select_one("h1.title-detail")
    author_tag = soup.select_one("li.author a")
    desc_tag = soup.select_one("div.detail-content p")
    thumb_tag = soup.select_one("div.picture img")

    title = title_tag.text.strip() if title_tag else slug
    author = author_tag.text.strip() if author_tag else "Không rõ"
    description = desc_tag.text.strip() if desc_tag else ""
    thumbnail = thumb_tag.get("src") if thumb_tag else ""

    # Get chapter links
    chapter_links = soup.select("ul.list-chapter a")
    chapter_links = chapter_links[::-1]  # old → new

    # Tạo danh sách chapters từ 1 → N
    chapters = existing_story.get("chapters", []) if existing_story else []

    start_chapter = len(chapters) + 1

    for i in range(start_chapter, len(chapter_links)+1):
        chapter_url = f"{BASE_URL}/manga/{slug}/chapter-{i}"
        images = scrape_chapter_images(chapter_url)
        if images:
            chapters.append({
                "name": f"Chapter {i}",
                "images": images
            })
            print(f"[OK] Scraped {title} - Chapter {i}")
        else:
            print(f"[WARN] Chapter {i} failed or no images, skip.")

    story_data = {
        "id": slug,
        "title": title,
        "author": author,
        "description": description,
        "thumbnail": thumbnail,
        "chapters": chapters
    }
    return story_data

# ----------------------------
# Push to GitHub
# ----------------------------
def push_to_github():
    repo = Repo(REPO_PATH)
    repo.git.add(STORIES_FILE)
    repo.index.commit(f"Update stories.json")
    origin = repo.remote(name="origin")
    # Push with token
    url_with_token = f"https://{TOKEN}@github.com/{repo.remotes.origin.url.split('github.com/')[1]}"
    origin.set_url(url_with_token)
    origin.push(refspec=f"{BRANCH}:{BRANCH}")
    print("[DONE] Pushed to GitHub")

# ----------------------------
# Main scraper runner
# ----------------------------
def run_scraper():
    stories_dict = load_stories()
    scraped = 0

    # Danh sách các slug ưu tiên trước
    slugs = PRIORITY_SLUGS.copy()

    # Sau đó lấy các slug khác từ danh sách trang
    for page_num in range(LIST_PAGE_START, LIST_PAGE_END+1):
        page_url = f"{BASE_URL}/danh-sach-truyen/{page_num}/?sort=last_update&status=0"
        r = safe_get(page_url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("div.col-truyen-main > div.row > div.col-truyen > a")
        for a in items:
            href = a.get("href")
            if href:
                slug = href.strip("/").split("/")[-1]
                if slug not in slugs:
                    slugs.append(slug)

    # Multi-thread scrape
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = []
        for slug in slugs:
            existing = stories_dict.get(slug)
            futures.append(executor.submit(scrape_story, slug, existing))
        for future in futures:
            story_data = future.result()
            if story_data:
                stories_dict[story_data["id"]] = story_data
                scraped += 1
                print(f"[DONE] Story scraped: {story_data['title']} ({scraped}/{STORIES_PER_RUN})")
                if scraped >= STORIES_PER_RUN:
                    break

    save_stories(stories_dict)
    push_to_github()

if __name__ == "__main__":
    run_scraper()
