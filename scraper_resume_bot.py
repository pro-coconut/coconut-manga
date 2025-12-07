import os
import json
import requests
from bs4 import BeautifulSoup
from git import Repo

# ================= CONFIG =================
START_PAGE = 4
END_PAGE = 14
GITHUB_TOKEN = "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"
GITHUB_USERNAME = "pro-coconut"
REPO_NAME = "pro-coconut.github.io"
BRANCH = "main"
REPO_URL = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{REPO_NAME}.git"
STORIES_FILE = "stories.json"

BASE_LIST_URL = "https://nettruyen0209.com/danh-sach-truyen/{page}/?sort=last_update&status=0"
BASE_MANGA_URL = "https://nettruyen0209.com/manga/{slug}"

# ==========================================

def fetch_html(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[WARN] Failed fetching {url}: {e}")
        return None

def parse_story_list(page):
    url = BASE_LIST_URL.format(page=page)
    html = fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items = soup.select(".item-truyen")
    stories = []
    for item in items:
        try:
            title_tag = item.select_one(".story-name a")
            title = title_tag.text.strip()
            slug = title_tag['href'].split("/")[-1]
            author_tag = item.select_one(".author")
            author = author_tag.text.strip() if author_tag else "Không rõ"
            thumb_tag = item.select_one(".img img")
            thumbnail = thumb_tag['data-src'] if thumb_tag and thumb_tag.has_attr("data-src") else ""
            desc_tag = item.select_one(".story-intro")
            description = desc_tag.text.strip() if desc_tag else ""
            stories.append({
                "id": slug,
                "title": title,
                "author": author,
                "description": description,
                "thumbnail": thumbnail,
                "chapters": []
            })
        except Exception as e:
            print(f"[WARN] Error parsing story item: {e}")
    return stories

def parse_chapters(story):
    slug = story['id']
    chapter_index = 1
    while True:
        chapter_url = f"https://nettruyen0209.com/manga/{slug}/chapter-{chapter_index}"
        html = fetch_html(chapter_url)
        if not html or "Truyện đang cập nhật" in html:
            break
        soup = BeautifulSoup(html, "lxml")
        img_tags = soup.select(".chapter-content img")
        images = [img['data-src'] for img in img_tags if img.has_attr("data-src")]
        if not images:
            break
        story['chapters'].append({
            "name": f"Chapter {chapter_index}",
            "images": images
        })
        print(f"Scraped {story['title']} - Chapter {chapter_index}")
        chapter_index += 1

def save_stories(stories):
    with open(STORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(stories)} stories to {STORIES_FILE}")

def push_to_github():
    if not os.path.exists(".git"):
        repo = Repo.init(os.getcwd())
        origin = repo.create_remote("origin", REPO_URL)
    else:
        repo = Repo(os.getcwd())
        origin = repo.remote(name="origin")
    repo.git.add(STORIES_FILE)
    repo.index.commit("Update stories.json via scraper")
    origin.push(refspec=f"{BRANCH}:{BRANCH}")
    print("[DONE] Pushed to GitHub")

def run_scraper():
    all_stories = []
    for page in range(START_PAGE, END_PAGE + 1):
        print(f"Fetching list page: {BASE_LIST_URL.format(page=page)}")
        stories = parse_story_list(page)
        for story in stories:
            parse_chapters(story)
        all_stories.extend(stories)
    save_stories(all_stories)
    push_to_github()

if __name__ == "__main__":
    run_scraper()
