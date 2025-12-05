document.addEventListener('DOMContentLoaded', () => {
  const list = document.getElementById('story-list');

  fetch('stories.json')
    .then(r => r.json())
    .then(stories => {
      list.innerHTML = ''; // xóa loading

      stories.forEach(story => {
        const div = document.createElement('div');
        div.className = 'story-card';
        div.onclick = () => location.href = `reader.html?id=${story.id}`;

        div.innerHTML = `
          <img src="${story.thumbnail}" alt="${story.title}" loading="lazy">
          <h3>${story.title}</h3>
          <p>${story.author || 'Đang cập nhật'}</p>
        `;
        list.appendChild(div);
      });
    })
    .catch(err => {
      list.innerHTML = `<div class="loading">Lỗi tải dữ liệu: ${err.message}</div>`;
    });
});
