import requests
from bs4 import BeautifulSoup
import time
import os

API = os.getenv("API_BASE_URL")
MAX_PAGES = int(os.getenv("MAX_LISTING_PAGES", 3))
DELAY = float(os.getenv("DELAY", 1.5))

headers = {
    "User-Agent": "Mozilla/5.0"
}

def fetch(url):
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def get_story_links(page):
    url = f"https://nettruyen0209.com/tim-truyen?page={page}"
    soup = fetch(url)
    links = []

    for item in soup.select(".item .image a"):
        links.append(item["href"])

    return links

def scrape_story_info(url):
    soup = fetch(url)

    name = soup.select_one(".title-detail").text.strip()
    cover = soup.select_one(".detail-thumbnail img")["src"]
    description = soup.select_one("#story-detail .detail-content").text.strip()

    # chapter list
    chapters = []
    for ch in soup.select(".list-chapter li a"):
        chapters.append({
            "chapter": ch.text.strip(),
            "url": ch["href"]
        })

    return name, cover, description, list(reversed(chapters))

def scrape_chapter_images(url):
    soup = fetch(url)
    imgs = [img["src"] for img in soup.select(".reading-detail img")]
    return imgs

def api_post(path, data):
    r = requests.post(f"{API}{path}", json=data)
    return r.json()

def run():
    print("🔍 START SCRAPING NETTRUYEN...")

    for page in range(1, MAX_PAGES + 1):
        print(f"\n📄 PAGE {page}")
        links = get_story_links(page)

        for link in links:
            print(f"➡ QUÉT TRUYỆN: {link}")
            name, cover, desc, chapters = scrape_story_info(link)

            # check story
            check = api_post("/api/stories/check", {"name": name})

            if not check["exists"]:
                # create new story
                created = api_post("/api/stories/create", {
                    "name": name,
                    "cover": cover,
                    "description": desc
                })
                storyId = created["storyId"]
            else:
                storyId = check["storyId"]

            existing_chapters = check["chapters"] if check["exists"] else []

            # add chapters
            for ch in chapters:
                if ch["chapter"] in existing_chapters:
                    print(f"   ⏩ Bỏ qua (đã có): {ch['chapter']}")
                    continue

                print(f"   ➕ Thêm chapter: {ch['chapter']}")

                imgs = scrape_chapter_images(ch["url"])

                api_post("/api/stories/add-chapter", {
                    "storyId": storyId,
                    "chapter": ch["chapter"],
                    "images": imgs
                })

                time.sleep(DELAY)

        time.sleep(DELAY)

    print("\n✅ HOÀN THÀNH SCRAPE!")
    

if __name__ == "__main__":
    run()
