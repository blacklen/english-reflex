# English Reflex Trainer — Discord Bot 🤖

Luyện phản xạ tiếng Anh trên Discord, dùng bài thật từ Reddit.
Hoàn toàn miễn phí.

## Tính năng
- `/train`  — bot kéo bài Reddit, hỏi bạn một câu bằng tiếng Anh. Bạn reply → bot phân tích và chỉ "bản xứ nói vầy nè"
  - 💬 **Comment thật** — bấm nút này để đọc comment thật của người bản xứ về bài hiện tại (chỉ mình bạn thấy)
  - ⏭ **Bài khác** — bỏ qua, lấy câu hỏi khác
- `/digest` — đọc digest Reddit hôm nay tóm tắt bằng tiếng Việt
- `/done`   — kết thúc session

---

## Setup (~20 phút)

### Bước 1 — Lấy API keys

**A. Discord Bot Token**
1. Vào https://discord.com/developers/applications
2. Click "New Application" → đặt tên
3. Vào tab **Bot** → click "Add Bot"
4. Click "Reset Token" → copy token
5. ⚠️ Cũng trong tab Bot, bật **Message Content Intent** (phần Privileged Gateway Intents)
6. Vào tab **OAuth2 → URL Generator**:
   - Scopes: chọn `bot` và `applications.commands`
   - Bot Permissions: chọn `Send Messages`, `Read Messages/View Channels`
7. Copy URL ở dưới → mở trình duyệt → mời bot vào server của bạn

**B. Guild (Server) ID**
1. Mở Discord Settings → Advanced → bật **Developer Mode**
2. Right-click tên server → "Copy Server ID"

**C. Google Gemini API Key (free)**
1. Vào https://aistudio.google.com/app/apikey
2. Click "Create API key" → copy

**D. Reddit** — không cần gì cả! ✅
Bot đọc bài public qua Reddit JSON API, không cần đăng ký app hay tài khoản Reddit.

---

### Bước 2 — Cài đặt

```bash
cd reddit-reflex-bot

python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt

cp env.example .env
# Mở .env và điền 3 keys vào (Discord token, Guild ID, Gemini key)
```

---

### Bước 3 — Chạy

```bash
python bot.py
```

Mở Discord → vào server → gõ `/start`.

> Slash commands sync ngay lập tức nếu GUILD_ID được điền đúng.

---

## Tuỳ chỉnh

Trong `bot.py`, tìm `SUBREDDITS = [...]` và thêm/bỏ subreddit theo sở thích.

---

## Notes
- Gemini free tier: 1,500 req/ngày — thoải mái cho cá nhân
- Session lưu trong bộ nhớ → restart bot thì reset (bình thường)
- Muốn chạy 24/7 → deploy lên Render (free tier)
