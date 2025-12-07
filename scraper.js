const Manga = require('manga-lib');
const fs = require('fs-extra');
const path = require('path');
const simpleGit = require('simple-git');

const TOKEN = process.env.GITHUB_TOKEN; // để workflow tự inject
const REPO = 'https://'+TOKEN+'@github.com/pro-coconut/pro-coconut.github.io.git';
const BRANCH = 'main';
const LOCAL_FILE = path.join(__dirname, 'stories.json');

// Cấu hình trang
const START_PAGE = 4;
const END_PAGE = 14;

// Load stories.json hiện tại
let stories = [];
if (fs.existsSync(LOCAL_FILE)) {
  stories = fs.readJsonSync(LOCAL_FILE);
}

// Lấy slug từ URL
function slugFromUrl(url) {
  return url.split('/').filter(Boolean).pop();
}

// Kiểm tra xem truyện đã có chưa
function findStory(slug) {
  return stories.find(s => s.id === slug);
}

async function fetchStory(url) {
  const slug = slugFromUrl(url);
  let story = findStory(slug);
  const manga = new Manga(url);

  await manga.init(); // lấy metadata

  if (!story) {
    // Tạo mới
    story = {
      id: slug,
      title: manga.title || 'Không rõ',
      author: manga.author || 'Không rõ',
      description: manga.description || '',
      thumbnail: manga.cover || '',
      chapters: []
    };
    stories.push(story);
  }

  // Lấy chapter mới
  const existingChapters = story.chapters.map(c => c.name);
  for (let i = 0; i < manga.chapters.length; i++) {
    const chap = manga.chapters[i];
    if (!existingChapters.includes(chap.name)) {
      story.chapters.push({
        name: chap.name,
        images: chap.images
      });
      console.log(`[INFO] Added chapter ${chap.name} for ${story.title}`);
    }
  }
}

async function runScraper() {
  for (let page = START_PAGE; page <= END_PAGE; page++) {
    const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
    console.log(`Fetching page ${page}...`);
    const mangaList = await Manga.list(url); // manga-lib list page
    for (const mangaUrl of mangaList) {
      try {
        await fetchStory(mangaUrl);
      } catch (e) {
        console.log(`[WARN] Failed ${mangaUrl}: ${e}`);
      }
    }
  }

  // Lưu file
  fs.writeJsonSync(LOCAL_FILE, stories, { spaces: 2 });
  console.log(`Saved ${stories.length} stories to stories.json`);

  // Push lên GitHub
  const git = simpleGit();
  await git.add('./*');
  await git.commit('Update stories.json');
  await git.push(REPO, BRANCH);
  console.log('Pushed to GitHub successfully!');
}

runScraper();
