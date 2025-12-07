const fs = require("fs-extra");
const path = require("path");
const axios = require("axios");
const { Manga } = require("manga-lib");
const { execSync } = require("child_process");

// ==== CẤU HÌNH ====
const START_PAGE = 4;
const END_PAGE = 14;

const LOCAL_DIR = process.cwd();
const STORIES_FILE = path.join(LOCAL_DIR, "stories.json");
const BRANCH = "main";
const REPO_URL = `https://${process.env.GITHUB_TOKEN}@github.com/${process.env.REPO_NAME}.git`;

// ==== HÀM LẤY DANH SÁCH TRUYỆN ====
async function fetchStoryList(page) {
  const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
  const res = await axios.get(url);
  const html = res.data;
  const manga = new Manga(html);
  return manga.list.map((m) => m.link);
}

// ==== HÀM LẤY THÔNG TIN TRUYỆN ====
async function fetchStoryData(storyUrl) {
  const manga = new Manga(storyUrl);
  await manga.load();
  return {
    id: manga.slug,
    title: manga.title,
    author: manga.author || "Không rõ",
    description: manga.description || "",
    thumbnail: manga.cover,
    chapters: manga.chapters.map((c) => ({
      name: c.title,
      images: c.images
    }))
  };
}

// ==== HÀM LƯU JSON ====
async function saveStories(data) {
  await fs.writeJson(STORIES_FILE, data, { spaces: 2 });
  console.log(`Saved ${data.length} stories to ${STORIES_FILE}`);
}

// ==== HÀM PUSH GITHUB ====
function pushToGitHub() {
  try {
    execSync(`git config user.name "github-actions"`);
    execSync(`git config user.email "actions@github.com"`);
    execSync(`git add .`);
    execSync(`git commit -m "Update stories.json" || echo "No changes"`);
    execSync(`git push ${REPO_URL} ${BRANCH}:${BRANCH}`);
    console.log("Pushed to GitHub successfully!");
  } catch (err) {
    console.error("Git push failed:", err.message);
  }
}

// ==== CHẠY SCRAPER ====
(async () => {
  const allStories = [];
  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching list page: ${page}`);
    try {
      const links = await fetchStoryList(page);
      for (const link of links) {
        console.log(`Scraping ${link}`);
        try {
          const data = await fetchStoryData(link);
          allStories.push(data);
        } catch (e) {
          console.warn(`[WARN] Failed ${link}: ${e.message}`);
        }
      }
    } catch (e) {
      console.warn(`[WARN] Page ${page} failed: ${e.message}`);
    }
  }
  await saveStories(allStories);
  pushToGitHub();
})();
