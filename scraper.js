import { Manga } from "manga-lib";
import fs from "fs-extra";
import path from "path";

// ==== CẤU HÌNH ====
const START_PAGE = 4;
const END_PAGE = 14;
const STORIES_FILE = path.join(process.cwd(), "stories.json");

// Repo push config (sử dụng GITHUB_TOKEN của Actions)
const REPO_URL = `https://x-access-token:${process.env.GITHUB_TOKEN}@github.com/pro-coconut/pro-coconut.github.io.git`;
const BRANCH = "main";

// ==== LOAD STORIES CŨ ====
let stories = [];
if (fs.existsSync(STORIES_FILE)) {
  stories = fs.readJsonSync(STORIES_FILE);
}

// ==== HÀM CẬP NHẬT TRUYỆN ====
async function fetchStory(url) {
  const manga = new Manga(url);
  const info = await manga.getInfo();

  // Lấy slug/id từ url
  const slug = url.split("/").filter(Boolean).pop();

  // Kiểm tra truyện đã có chưa
  let existing = stories.find(s => s.id === slug);

  // Nếu có rồi, chỉ lấy chapter mới
  let chapters = [];
  if (existing) {
    const lastChapter = existing.chapters.length;
    const newChaps = await manga.getChapters(lastChapter + 1, lastChapter + 50); // lấy 50 chap kế tiếp
    chapters = existing.chapters.concat(newChaps.map(c => ({
      name: c.title,
      images: c.images
    })));
    existing.chapters = chapters;
    return existing;
  } else {
    const allChaps = await manga.getChapters(1, 1000); // giả sử max 1000 chap
    chapters = allChaps.map(c => ({
      name: c.title,
      images: c.images
    }));
    return {
      id: slug,
      title: info.title,
      author: info.author || "Không rõ",
      description: info.description || "",
      thumbnail: info.image || "",
      chapters
    };
  }
}

// ==== HÀM CHẠY SCRAPER ====
async function runScraper() {
  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching list page: ${page}`);
    const listUrl = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
    const mangaList = await Manga.getList(listUrl);

    for (const mangaUrl of mangaList) {
      console.log(`Scraping ${mangaUrl}`);
      try {
        const story = await fetchStory(mangaUrl);

        // Nếu chưa có, push vào array
        if (!stories.find(s => s.id === story.id)) {
          stories.push(story);
        }
      } catch (err) {
        console.warn(`Failed ${mangaUrl}:`, err.message);
      }
    }
  }

  // Lưu stories.json
  fs.writeJsonSync(STORIES_FILE, stories, { spaces: 2, encoding: "utf-8" });
  console.log(`Saved ${stories.length} stories to ${STORIES_FILE}`);

  // Push lên repo
  console.log("Pushing to GitHub...");
  await import("child_process").then(cp => {
    cp.execSync(`git config --global user.email "action@github.com"`);
    cp.execSync(`git config --global user.name "GitHub Action"`);
    cp.execSync(`git add ${STORIES_FILE}`);
    cp.execSync(`git commit -m "Update stories.json" || echo "No changes"`);
    cp.execSync(`git push ${REPO_URL} ${BRANCH}`);
  });
}

runScraper();
