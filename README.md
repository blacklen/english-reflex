# English Reflex Trainer — Discord Bot 🤖

Practice English reflexes on Discord using real posts from Reddit. Completely free.

> Note: the bot talks to users in **Vietnamese** (it's built for Vietnamese learners of English). This README is the developer/setup documentation.

## Features
- `/train` — the bot pulls a Reddit post and asks you a question in English. You reply → the bot analyzes your answer and shows you how a native speaker would say it.
  - 💬 **Comment thật** (*Real comments*) — click to read the real native-speaker comments on the current post (only you can see them).
  - ⏭ **Bài khác** (*Next one*) — skip and get a different question.
- `/digest` — read a summary of today's trending Reddit posts, in Vietnamese.
- `/done` — end the session.

---

## Setup (~20 min)

### Step 1 — Get API keys

**A. Discord Bot Token**
1. Go to https://discord.com/developers/applications
2. Click "New Application" → give it a name
3. Open the **Bot** tab → click "Add Bot"
4. Click "Reset Token" → copy the token
5. ⚠️ Still in the Bot tab, enable **Message Content Intent** (under Privileged Gateway Intents) — the bot can't read your replies without it
6. Open **OAuth2 → URL Generator**:
   - Scopes: select `bot` and `applications.commands`
   - Bot Permissions: select `Send Messages`, `Read Messages/View Channels`
7. Copy the generated URL → open it in a browser → invite the bot to your server

**B. Guild (Server) ID**
1. Open Discord Settings → Advanced → enable **Developer Mode**
2. Right-click your server name → "Copy Server ID"

**C. Google Gemini API Key (free)**
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API key" → copy it

**D. Reddit** — nothing needed! ✅
The bot reads public posts via Reddit's public **RSS feeds**, so no app registration, no API key, and no Reddit account are required.

---

### Step 2 — Install

```bash
cd english-reflex

# Use a working Python 3.10+ (python3 --version to check)
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt

cp env.example .env
# Open .env and fill in the 3 keys (Discord token, Guild ID, Gemini key)
```

---

### Step 3 — Run

```bash
python bot.py
```

Open Discord → go to your server → type `/start`.

> Slash commands sync instantly when `GUILD_ID` is set correctly.

**Gotcha:** if the bot doesn't respond to your typed replies, check that the channel isn't **private** without the bot added — a private channel hides your messages from the bot. Either use a public channel or add the bot to the channel's permissions (View Channel, Read Message History, Send Messages).

---

## Run 24/7 (deploy to Render — free)

This repo includes `render.yaml`, `runtime.txt` (Python 3.11), and a small built-in keep-alive web server, so it deploys to Render's free tier out of the box.

1. Push this repo to GitHub.
2. On [dashboard.render.com](https://dashboard.render.com): **New + → Web Service** → connect the repo. Render reads `render.yaml` automatically.
3. In the **Environment** tab, set `DISCORD_TOKEN`, `GUILD_ID`, and `GEMINI_API_KEY` (the same values as your local `.env`).
4. Deploy and watch the logs for `Logged in as … — ready!`.
5. **Keep it awake:** Render's free tier sleeps after 15 min idle. Add a free [UptimeRobot](https://uptimerobot.com) HTTP monitor pointing at your Render URL, every ~5 minutes.
6. Stop your local `python bot.py` — Discord allows only one connection per bot token at a time.

---

## Customize

In `bot.py`, find `SUBREDDITS = [...]` and add/remove subreddits to taste.

---

## Notes
- Gemini free tier: 1,500 requests/day — plenty for personal use.
- Sessions are stored in memory → restarting the bot resets them (expected). Run `/train` again after a restart.
- Reddit's unauthenticated JSON API is IP-blocked, so the bot uses RSS feeds instead. A side effect: RSS doesn't expose post score or the "stickied" flag, so the old quality filters are gone (hot posts still carry decent engagement).
