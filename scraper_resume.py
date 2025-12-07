import os
import json
import requests
from bs4 import BeautifulSoup
from git import Repo
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- CONFIG ----------------
TOKEN = "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"
USERNAME = "pro-coconut"
REPO_NAME = "pro-coconut.github.io"
BRANCH = "main"
REPO_PATH = "."  # root repo
STORIES_FILE = "stories.json"
START_PAGE = 4
END_PAGE = 14
MAX_THREADS = 5  # số thread cùng lúc

LIST_URL = "https://nettruyen0209.com/danh-sach-truyen/{}/?sort=last_update&status=0"

# ---------------- FUNCTIONS ----------------
def load_stories():
    if os.path.exists(STORIES_FILE):
        with open(STORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {s['id']: s for s in data if 'id' in s}
    return {}

def fetch_story_list(existing_stories):
    stories = []
    for page in range(START_PAGE, END_PAGE + 1):
        url = LIST_URL.format(page)
        print(f"Fetching list page: {url}")
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("div.story-item"):
            title_tag = item.select_one("h3.story-name a")
            if not title_tag: 
                continue
            title = title_tag.text.strip()
            link = title_tag['href']
            slug = link.rstrip("/").split("/")[-1]
            if slug in existing_stories:
                story_data = existing_stories[slug]
            else:
                author_tag = item.select_one("p.author")
                author = author_tag.text.replace("Tác giả:", "").strip() if author_tag else "Không rõ"
                thumbnail_tag = item.select_one("img")
                thumbnail = thumbnail_tag['data-src'] if thumbnail_tag else ""
                story_data = {
                    "id": slug,
                    "title": title,
                    "author": author,
                    "description": "",
                    "thumbnail": thumbnail,
                    "chapters": [],
                    "url": link
                }
            stories.append(story_data)
    return stories

def fetch_chapters(story):
    base_url = story['url']
    print(f"Scraping story: {story['title']}")
    try:
        resp = requests.get(base_url)
        soup = BeautifulSoup(resp.text, "lxml")
        chapter_links = soup.select("ul.list-chapter a")
        existing_chap_names = {c['name'] for c in story.get('chapters', [])}
        for a in reversed(chapter_links):  # từ chapter 1 trở đi
            chap_name = a.text.strip()
            if chap_name in existing_chap_names:
                continue  # đã có chapter
            chap_url = a['href']
            images = fetch_chapter_images(chap_url)
            if images:
                story.setdefault('chapters', []).append({
                    "name": chap_name,
                    "images": images
                })
    except Exception as e:
        print(f"[ERROR] Failed to fetch chapters for {story['title']}: {e}")

def fetch_chapter_images(chap_url):
    try:
        resp = requests.get(chap_url)
        soup = BeautifulSoup(resp.text, "lxml")
        imgs = soup.select("div.page-chapter img")
        return [img['src'] for img in imgs if img.get('src')]
    except:
        return []

def save_stories(stories):
    with open(STORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(stories)} stories to {STORIES_FILE}")

def push_to_github():
    repo = Repo(REPO_PATH)
    origin = repo.remote(name="origin")
    token_url = f"https://{TOKEN}@github.com/{USERNAME}/{REPO_NAME}.git"
    origin.set_url(token_url)
    repo.git.add(STORIES_FILE)
    repo.index.commit("Update stories.json via scraper bot with resume")
    origin.push(refspec=f"{BRANCH}:{BRANCH}")
    print("Pushed to GitHub successfully!")

# ---------------- MAIN ----------------
def run_scraper():
    existing_stories = load_stories()
    stories = fetch_story_list(existing_stories)
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(fetch_chapters, story) for story in stories]
        for future in as_completed(futures):
            pass
    save_stories(stories)
    push_to_github()

if __name__ == "__main__":
    run_scraper()
