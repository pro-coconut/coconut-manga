// scraper.js
import axios from "axios";
import * as cheerio from "cheerio";
import fs from "fs";
import { execSync } from "child_process";
import path from "path";

// ==== CẤU HÌNH ====
const TOKEN = process.env.GITHUB_TOKEN; // Lấy token từ GitHub Actions Secret
const USERNAME = "pro-coconut";
const REPO_NAME = "pro-coconut.github.io";
const BRANCH = "main";

const START_PAGE = 4;
const END_PAGE = 14;

const REPO_URL = `https://${TOKEN}@github.com/${USERNAME}/${REPO_NAME}.git`;
const LOCAL_DIR = process.cwd();
const STORIES_FILE = path.join(LOCAL_DIR, "stories.json");

// ==== HÀM LẤY DANH SÁCH TRUYỆN ====
async function fetchStoryList(page) {
  try {
    const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
    const res = await axios.get(url);
    const $ = cheerio.load(res.data);
    const links = [];
    $(".col-truyen-list .list-truyen-item a").each((i, el) => {
      const href = $(el).attr("href");
      if (href) links.push(href);
    });
    return links;
  } catch (err) {
    console.warn(`[WARN] Failed page ${page}: ${err.message}`);
    return [];
  }
}

// ==== HÀM LẤY THÔNG TIN TRUYỆN ====
async function fetchStoryData(storyUrl) {
  try {
    const res = await axios.get(storyUrl);
    const $ = cheerio.load(res.data);

    const title = $("h1.title-detail").text().trim() || "Không rõ";
    const author = $(".author span").text().trim() || "Không rõ";
    const description = $(".summary_content").text().trim() || "";
    const slug = storyUrl.split("/").filter(Boolean).pop();
    const thumbnail = $(".info-image img").attr("src") || "";

    const chapters = await fetchChapters(storyUrl, slug);

    return {
      id: slug,
      title,
      author,
      description,
      thumbnail,
      chapters,
    };
  } catch (err) {
    console.warn(`[WARN] Failed story ${storyUrl}: ${err.message}`);
    return null;
  }
}

// ==== HÀM LẤY CHAPTER VÀ URL ẢNH ====
async function fetchChapters(storyUrl, slug) {
  const chapters = [];
  for (let i = 1; i <= 100; i++) {
    const chapUrl = `${storyUrl}/chapter-${i}`;
    try {
      const res = await axios.get(chapUrl);
      if (res.status !== 200) break;

      const $ = cheerio.load(res.data);
      const imgs = $(".reading-detail img");
      if (!imgs.length) continue;

      const imgUrls = [];
      imgs.each((i, el) => {
        const src = $(el).attr("data-src") || $(el).attr("src");
        if (src) imgUrls.push(src);
      });

      if (imgUrls.length > 0) {
        chapters.push({ name: `Chapter ${i}`, images: imgUrls });
      }
    } catch {
      break; // Nếu không có trang chapter nữa thì dừng
    }
  }
  return chapters;
}

// ==== HÀM LƯU JSON ====
function saveStories(data) {
  fs.writeFileSync(STORIES_FILE, JSON.stringify(data, null, 2), "utf-8");
  console.log(`Saved ${data.length} stories to ${STORIES_FILE}`);
}

// ==== HÀM PUSH GITHUB ====
function pushToGitHub() {
  try {
    execSync("git config --global user.email 'github-actions[bot]@users.noreply.github.com'");
    execSync("git config --global user.name 'github-actions[bot]'");
    execSync("git add .");
    execSync(`git commit -m "Update stories.json" || echo "No changes to commit"`);
    execSync(`git push ${REPO_URL} ${BRANCH}`);
    console.log("Pushed to GitHub successfully!");
  } catch (err) {
    console.error("Failed to push to GitHub:", err.message);
  }
}

// ==== CHẠY SCRAPER ====
async function runScraper() {
  const allStories = [];

  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching list page: ${page}`);
    const storyLinks = await fetchStoryList(page);

    for (const link of storyLinks) {
      console.log(`Scraping ${link}`);
      const storyData = await fetchStoryData(link);
      if (storyData) allStories.push(storyData);
    }
  }

  saveStories(allStories);
  pushToGitHub();
}

runScraper();
