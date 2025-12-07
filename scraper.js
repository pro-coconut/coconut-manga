const { Mangas, Sources } = require("manga-lib");
const fs = require("fs");

// Chọn nguồn truyện
const source = Sources.NetTruyen;

// Danh sách truyện cần lấy (slug trên NetTruyen)
const storySlugs = [
  "gap-manh-thi-manh-ta-tu-vi-vo-thuong-han",
  "tien-hoa-vo-han-bat-dau-tu-con-so-khong"
];

const STORIES_FILE = "stories.json";

// ==== Load stories.json cũ ====
let existingStories = [];
if (fs.existsSync(STORIES_FILE)) {
  try {
    existingStories = JSON.parse(fs.readFileSync(STORIES_FILE, "utf-8"));
  } catch (e) {
    console.log("Không thể đọc stories.json cũ:", e.message);
  }
}

// Helper để tìm truyện theo slug
function findStory(slug) {
  return existingStories.find(s => s.id === slug);
}

// ==== Main scraper ====
async function main() {
  for (let slug of storySlugs) {
    try {
      const manga = await Mangas.fetch({ source, slug });
      let story = findStory(slug);

      // Nếu truyện chưa có, tạo mới
      if (!story) {
        story = {
          id: slug,
          title: manga.title,
          author: manga.author || "Không rõ",
          description: manga.description || "",
          thumbnail: manga.thumbnail || "",
          chapters: []
        };
        existingStories.push(story);
      }

      // Lấy danh sách chapter mới
      const existingChapterNames = story.chapters.map(c => c.name);
      for (let chapter of manga.chapters) {
        if (!existingChapterNames.includes(chapter.title)) {
          story.chapters.push({
            name: chapter.title,
            images: chapter.pages
          });
          console.log(`Added new chapter: ${slug} - ${chapter.title}`);
        }
      }

    } catch (e) {
      console.log(`Lỗi lấy truyện ${slug}:`, e.message);
    }
  }

  // Lưu lại stories.json
  fs.writeFileSync(STORIES_FILE, JSON.stringify(existingStories, null, 2), "utf-8");
  console.log("Updated stories.json thành công!");
}

main();
