const { manga } = require('manga-lib');
const fs = require('fs-extra');
const simpleGit = require('simple-git');
const path = require('path');

// ==== CẤU HÌNH ====
const TOKEN = "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"; // token GitHub
const USERNAME = "pro-coconut";
const REPO = "pro-coconut.github.io";
const BRANCH = "main";

const START_PAGE = 4;
const END_PAGE = 14;

const LOCAL_DIR = process.cwd();
const STORIES_FILE = path.join(LOCAL_DIR, 'stories.json');
const REPO_URL = `https://${TOKEN}@github.com/${USERNAME}/${REPO}.git`;

// ==== LOAD STORIES HIỆN CÓ ====
let stories = [];
if (fs.existsSync(STORIES_FILE)) {
  stories = fs.readJsonSync(STORIES_FILE);
}

// ==== LẤY DANH SÁCH TRUYỆN ====
async function fetchStoryList(page) {
  const listUrl = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
  const result = await manga.list(listUrl);
  return result; // trả về mảng { title, url }
}

// ==== LẤY THÔNG TIN TRUYỆN ====
async function fetchStoryData(url) {
  const info = await manga.info(url);
  // Kiểm tra xem truyện đã có chưa
  const slug = info.slug;
  const exist = stories.find(s => s.id === slug);
  let chapters = [];
  if (exist) {
    // chỉ lấy các chapter mới
    const existChaps = exist.chapters.map(c => c.name);
    chapters = info.chapters.filter(c => !existChaps.includes(c.name));
    exist.chapters.push(...chapters);
    return null; // không thêm truyện mới
  } else {
    chapters = info.chapters;
    return {
      id: slug,
      title: info.title,
      author: info.author || "Không rõ",
      description: info.description || "",
      thumbnail: info.thumbnail || "",
      chapters: chapters
    };
  }
}

// ==== CHẠY SCRAPER ====
(async () => {
  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching page ${page}...`);
    let list = [];
    try {
      list = await fetchStoryList(page);
    } catch (e) {
      console.log("[WARN] Lỗi fetch list:", e.message);
      continue;
    }
    for (const item of list) {
      console.log(`Scraping ${item.title}`);
      try {
        const story = await fetchStoryData(item.url);
        if (story) stories.push(story);
      } catch (e) {
        console.log("[WARN] Lỗi fetch story:", e.message);
      }
    }
  }

  fs.writeJsonSync(STORIES_FILE, stories, { spaces: 2, encoding: 'utf-8' });
  console.log(`Saved ${stories.length} stories to ${STORIES_FILE}`);

  // ==== PUSH GITHUB ====
  const git = simpleGit(LOCAL_DIR);
  await git.add('./*');
  await git.commit('Update stories.json');
  await git.push(REPO_URL, BRANCH);
  console.log('Pushed to GitHub successfully!');
})();
