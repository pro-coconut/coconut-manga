import requests
from bs4 import BeautifulSoup
import json
import os
import subprocess

# ==== CẤU HÌNH ====
TOKEN = "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"  # Token GitHub
USERNAME = "pro-coconut"
REPO_NAME = "pro-coconut.github.io"
BRANCH = "main"

START_PAGE = 4
END_PAGE = 14

LOCAL_DIR = os.getcwd()  # root repo
STORIES_FILE = os.path.join(LOCAL_DIR, "stories.json")

REPO_URL = f"https://{TOKEN}@github.com/{USERNAME}/{REPO_NAME}.git"

# ==== HÀM LẤY DANH SÁCH TRUYỆN ====
def fetch_story_list(page):
    url = f"https://nettruyen0209.com/danh-sach-truyen/{page}/?sort=last_update&status=0"
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select(".col-truyen-list .list-truyen-item a")
    return [link['href'] for link in links if link.get('href')]

# ==== HÀM LẤY THÔNG TIN TRUYỆN ====
def fetch_story_data(story_url):
    resp = requests.get(story_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    title_tag = soup.select_one("h1.title-detail")
    title = title_tag.text.strip() if title_tag else "Không rõ"
    author_tag = soup.select_one(".author span")
    author = author_tag.text.strip() if author_tag else "Không rõ"
    description_tag = soup.select_one(".summary_content")
    description = description_tag.text.strip() if description_tag else ""
    slug = story_url.rstrip("/").split("/")[-1]
    thumbnail_tag = soup.select_one(".info-image img")
    thumbnail = thumbnail_tag['src'] if thumbnail_tag else ""
    chapters = fetch_chapters(story_url, slug)
    return {
        "id": slug,
        "title": title,
        "author": author,
        "description": description,
        "thumbnail": thumbnail,
        "chapters": chapters
    }

# ==== HÀM LẤY CHAPTER VÀ URL ẢNH ====
def fetch_chapters(story_url, slug):
    chapters = []
    for i in range(1, 101):  # giả sử max 100 chapter
        chap_url = f"{story_url}/chapter-{i}"
        resp = requests.get(chap_url)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        imgs = soup.select(".reading-detail img")
        if not imgs:
            continue
        img_urls = [img.get('data-src') or img.get('src') for img in imgs]
        chapters.append({
            "name": f"Chapter {i}",
            "images": img_urls
        })
    return chapters

# ==== HÀM LƯU JSON ====
def save_stories(data):
    with open(STORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data)} stories to {STORIES_FILE}")

# ==== HÀM PUSH GITHUB ====
def push_to_github():
    # git add, commit
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Update stories.json"], check=True)
    # git push với token nhúng
    subprocess.run(["git", "push", REPO_URL, f"{BRANCH}:{BRANCH}"], check=True)
    print("Pushed to GitHub successfully!")

# ==== CHẠY SCRAPER ====
def run_scraper():
    all_stories = []
    for page in range(START_PAGE, END_PAGE + 1):
        print(f"Fetching list page: {page}")
        try:
            story_links = fetch_story_list(page)
        except Exception as e:
            print(f"[WARN] Failed to fetch list page {page}: {e}")
            continue
        for link in story_links:
            print(f"Scraping {link}")
            try:
                story_data = fetch_story_data(link)
                all_stories.append(story_data)
            except Exception as e:
                print(f"[WARN] Failed {link}: {e}")
    save_stories(all_stories)
    push_to_github()

if __name__ == "__main__":
    run_scraper()
