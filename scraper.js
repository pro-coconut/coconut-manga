const { Manga } = require('manga-lib');
const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

// ==== CẤU HÌNH ====
const TOKEN = "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"; // token GitHub
const USERNAME = "pro-coconut";
const REPO_NAME = "pro-coconut.github.io";
const BRANCH = "main";
const REPO_URL = `https://${TOKEN}@github.com/${USERNAME}/${REPO_NAME}.git`;

const START_PAGE = 4;
const END_PAGE = 14;
const STORIES_FILE = path.join(__dirname, 'stories.json');

// ==== HÀM SCRAPER TRUYỆN ====
async function scrapeStory(storyUrl) {
    try {
        const story = new Manga(storyUrl);
        await story.fetch();
        return {
            id: story.slug,
            title: story.title,
            author: story.author || "Không rõ",
            description: story.description || "",
            thumbnail: story.cover || "",
            chapters: story.chapters.map(ch => ({
                name: ch.title,
                images: ch.pages
            }))
        };
    } catch (e) {
        console.warn(`[WARN] Failed ${storyUrl}: ${e}`);
        return null;
    }
}

// ==== LẤY DANH SÁCH TRUYỆN TỪ NETTRUYEN ====
async function fetchStoryList(page) {
    const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
    const story = new Manga(url);
    await story.fetchList();
    return story.urls; // trả về array URL truyện
}

// ==== CHẠY SCRAPER ====
async function runScraper() {
    let stories = [];
    if (fs.existsSync(STORIES_FILE)) {
        stories = JSON.parse(fs.readFileSync(STORIES_FILE, 'utf-8'));
    }

    for (let page = START_PAGE; page <= END_PAGE; page++) {
        console.log(`Fetching list page: ${page}`);
        let urls;
        try {
            urls = await fetchStoryList(page);
        } catch (e) {
            console.warn(`[WARN] Failed page ${page}: ${e}`);
            continue;
        }

        for (const url of urls) {
            const slug = url.split('/').pop();
            let exist = stories.find(s => s.id === slug);
            if (exist) {
                console.log(`Skipping existing story: ${slug}`);
                continue;
            }
            console.log(`Scraping story: ${url}`);
            const data = await scrapeStory(url);
            if (data) stories.push(data);
        }
    }

    fs.writeFileSync(STORIES_FILE, JSON.stringify(stories, null, 2), 'utf-8');
    console.log(`Saved ${stories.length} stories to ${STORIES_FILE}`);
}

// ==== PUSH LÊN GITHUB ====
function pushToGitHub() {
    try {
        execSync('git config --global user.name "github-actions[bot]"');
        execSync('git config --global user.email "github-actions[bot]@users.noreply.github.com"');
        execSync('git add stories.json');
        execSync('git commit -m "Update stories.json" || echo "No changes to commit"');
        execSync(`git push ${REPO_URL} ${BRANCH}`);
        console.log("Pushed to GitHub successfully!");
    } catch (e) {
        console.error("Failed to push to GitHub:", e.message);
    }
}

// ==== MAIN ====
(async () => {
    await runScraper();
    pushToGitHub();
})();
