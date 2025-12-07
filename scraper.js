const { Manga } = require("manga-lib");
const axios = require("axios");
const cheerio = require("cheerio");
const fs = require("fs");
const path = require("path");
const os = require("os");

const STORIES_FILE = path.join(__dirname, "stories.json");
const CONCURRENCY = 5; // số page chạy song song

async function fetchTotalPages() {
  try {
    const res = await axios.get(`https://nettruyen0209.com/danh-sach-truyen/1/?sort=last_update&status=0`);
    const $ = cheerio.load(res.data);
    const lastPage = $(".pagination a.page-link").last().prev().text();
    return parseInt(lastPage) || 1;
  } catch (err) {
    console.log(`[WARN] Failed to fetch total pages: ${err.message}`);
    return 1;
  }
}

async function fetchStoryList(page) {
  try {
    const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
    const res = await axios.get(url);
    const $ = cheerio.load(res.data);
    return $(".col-truyen-list .list-truyen-item a")
      .map((i, el) => $(el).attr("href"))
      .get()
      .filter(Boolean);
  } catch (err) {
    console.log(`[WARN] Failed list page ${page}: ${err.message}`);
    return [];
  }
}

async function fetchStoryData(url) {
  try {
    const story = new Manga(url);
    await story.init();

    const chapters = [];
    for (let i = 1; i <= story.chapters.length; i++) {
      try {
        const chap = await story.getChapter(i);
        chapters.push({ name: `Chapter ${i}`, images: chap.pages });
      } catch {
        continue;
      }
    }

    const slug = url.split("/").pop();
    return {
      id: slug,
      title: story.title || "Không rõ",
      author: story.author || "Không rõ",
      description: story.description || "",
      thumbnail: story.thumbnail || "",
      chapters
    };
  } catch (err) {
    console.log(`[WARN] Failed story ${url}: ${err.message}`);
    return null;
  }
}

// Xử lý đa luồng
async function asyncPool(poolLimit, array, iteratorFn) {
  const ret = [];
  const executing = [];
  for (const item of array) {
    const p = Promise.resolve().then(() => iteratorFn(item));
    ret.push(p);
    if (poolLimit <= array.length) {
      const e = p.then(() => executing.splice(executing.indexOf(e), 1));
      executing.push(e);
      if (executing.length >= poolLimit) {
        await Promise.race(executing);
      }
    }
  }
  return Promise.all(ret);
}

async function runScraper() {
  let stories = [];
  if (fs.existsSync(STORIES_FILE)) {
    stories = JSON.parse(fs.readFileSync(STORIES_FILE, "utf-8"));
  }

  const totalPages = await fetchTotalPages();
  console.log(`Total pages: ${totalPages}`);

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  await asyncPool(CONCURRENCY, pages, async (page) => {
    console.log(`Fetching list page: ${page}`);
    const urls = await fetchStoryList(page);
    for (const url of urls) {
      console.log(`Processing story: ${url}`);
      const storyData = await fetchStoryData(url);
      if (!storyData) continue;

      const index = stories.findIndex(s => s.id === storyData.id);
      if (index >= 0) {
        const existingChaps = stories[index].chapters.map(c => c.name);
        const newChaps = storyData.chapters.filter(c => !existingChaps.includes(c.name));
        if (newChaps.length > 0) {
          stories[index].chapters.push(...newChaps);
        }
      } else {
        stories.push(storyData);
      }
    }
  });

  fs.writeFileSync(STORIES_FILE, JSON.stringify(stories, null, 2), "utf-8");
  console.log(`Saved ${stories.length} stories to stories.json`);
}

runScraper();
