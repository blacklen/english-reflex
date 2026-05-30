#!/usr/bin/env python3
"""
English Reflex Trainer — Discord Bot
Uses real Reddit posts as training material for English reflex practice.

Slash commands:
  /train  — start a reflex training session
  /digest — get today's Reddit digest in Vietnamese
  /done   — end session
"""

import os
import re
import html
import random
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import discord
from discord import app_commands
from dotenv import load_dotenv
import requests
import google.generativeai as genai

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────
DISCORD_TOKEN        = os.getenv('DISCORD_TOKEN')
GUILD_ID             = int(os.getenv('GUILD_ID', 0))
GEMINI_API_KEY       = os.getenv('GEMINI_API_KEY')

SUBREDDITS = [
    'AskReddit', 'todayilearned', 'LifeProTips',
    'explainlikeimfive', 'Showerthoughts',
    'unpopularopinion', 'changemyview', 'AskMen'
]

# ── Client setup ──────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel('gemini-2.5-flash')

# Reddit's public RSS feeds — no credentials needed for reading public posts.
# (The unauthenticated JSON API is IP-blocked; the .rss feeds are not.)
# A descriptive User-Agent is required or Reddit returns HTTP 429.
# The Atom feed is machine-generated and consistent, so it's parsed with regex
# rather than xml.etree — that avoids depending on pyexpat, whose C extension
# is broken in some Python builds and would crash the bot on import/parse.
REDDIT_HEADERS = {'User-Agent': 'EnglishReflexBot/1.0 (personal learning tool)'}


def _reddit_entries(url, params=None):
    """Fetch a Reddit .rss (Atom) feed and return its raw <entry> blocks."""
    resp = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return re.findall(r'<entry>(.*?)</entry>', resp.text, re.S)


def _title(entry):
    m = re.search(r'<title[^>]*>(.*?)</title>', entry, re.S)
    return html.unescape(m.group(1)).strip() if m else ''


def _permalink(entry):
    m = re.search(r'<link[^>]*href="([^"]+)"', entry)
    return m.group(1) if m else ''


def _author(entry):
    m = re.search(r'<author>.*?<name>(.*?)</name>', entry, re.S)
    return html.unescape(m.group(1)).strip() if m else ''


def _plain_text(entry):
    """Extract an entry's <content> as stripped plain text.

    The content is HTML double-escaped inside the Atom XML, so unescape twice
    before stripping the now-real HTML tags.
    """
    m = re.search(r'<content[^>]*>(.*?)</content>', entry, re.S)
    if not m:
        return ''
    text = html.unescape(html.unescape(m.group(1)))
    text = re.sub(r'<[^>]+>', ' ', text)          # strip HTML tags
    return re.sub(r'\s+', ' ', text).strip()


def _fetch_comments(permalink, limit=5, max_len=300):
    """Return top comment bodies (len > 20, truncated) for a post's feed.

    The first entry of a comment feed is the post itself, so it's skipped.
    """
    entries = _reddit_entries(f"{permalink}.rss", params={'sort': 'top', 'limit': limit})
    comments = []
    for entry in entries[1:]:
        if _author(entry).lower() == '/u/automoderator':
            continue  # skip bot-posted moderation/flair notices
        body = _plain_text(entry)
        if len(body) > 20:
            comments.append(body[:max_len])
    return comments

# ── In-memory session storage ─────────────────────────────────────────────
sessions = {}  # { user_id: { mode, post, question, count } }

# ── Reddit helpers ────────────────────────────────────────────────────────
def fetch_post():
    subs = '+'.join(random.sample(SUBREDDITS, 3))
    try:
        entries = _reddit_entries(f"https://www.reddit.com/r/{subs}/hot.rss", params={'limit': 25})
        if not entries:
            return None
        entry = random.choice(entries)
        permalink = _permalink(entry)
        # Drop Reddit's "submitted by … [link]" footer; for link posts (no
        # self-text) this leaves an empty body, matching the old selftext behavior.
        body = re.split(r'\bsubmitted by\b', _plain_text(entry))[0].strip()
        return {
            'title': _title(entry),
            'body': body[:400],
            'url': permalink,
            'comments': _fetch_comments(permalink, limit=5)[:3],
        }
    except Exception as e:
        logger.error(f"Reddit fetch error: {e}")
        return None


def fetch_trending(limit=5):
    posts = []
    try:
        entries = _reddit_entries("https://www.reddit.com/r/popular/hot.rss", params={'limit': limit + 5})
        for entry in entries:
            permalink = _permalink(entry)
            posts.append({
                'title': _title(entry),
                'url': permalink,
                'comments': _fetch_comments(permalink, limit=3, max_len=200),
            })
            if len(posts) >= limit:
                break
    except Exception as e:
        logger.error(f"Reddit trending error: {e}")
    return posts

# ── AI helpers ────────────────────────────────────────────────────────────
def generate_question(post):
    top_comment = post['comments'][0] if post['comments'] else 'none'
    prompt = f"""You are an English Reflex Trainer.

Reddit post:
Title: {post['title']}
Body: {post['body'] or '(no body)'}
Top comment: {top_comment}

Generate ONE short, natural, conversational question in English inspired by this post.
Ask for the learner's opinion, experience, or reaction.
Sound like a friend asking casually — not formal, not academic.

Return ONLY the question. Nothing else."""
    try:
        return gemini.generate_content(prompt).text.strip()
    except Exception as e:
        logger.error(f"Gemini question error: {e}")
        return "What do you think about this?"


def generate_feedback(question, answer):
    prompt = f"""You are an English Reflex Trainer for a Vietnamese speaker.
They studied English 12 years but struggle with automatic, natural responses.

They were asked: "{question}"
Their answer: "{answer}"

Give feedback in this EXACT format:

✅ What worked: [find something good — even 1 word. Keep to 1 line.]
🗣️ Native version: [rewrite their answer how a native speaker would actually say it in casual conversation]
📌 Steal these: [list 2-3 useful chunks from the native version, one per line: "chunk" — Vietnamese explanation of when to use it]

Short, warm, honest. Show the gap to teach — not to criticize.
Plain text only, no markdown formatting."""
    try:
        return gemini.generate_content(prompt).text.strip()
    except Exception as e:
        logger.error(f"Gemini feedback error: {e}")
        return "Có lỗi khi phân tích. Thử câu tiếp theo nhé!"


def generate_digest(posts):
    items = '\n\n'.join([
        f"{i}. {p['title']}\nComments: {' | '.join(p['comments'])}"
        for i, p in enumerate(posts, 1)
    ])
    prompt = f"""Tóm tắt ngắn gọn các bài Reddit sau bằng tiếng Việt.
Mỗi bài viết 1-2 câu tự nhiên: nội dung chính + điều thú vị nhất từ bình luận.
Viết như đang kể cho bạn bè nghe.

{items}"""
    try:
        return gemini.generate_content(prompt).text.strip()
    except Exception as e:
        logger.error(f"Gemini digest error: {e}")
        return "Không tóm tắt được lúc này. Thử lại sau nhé!"


async def send_long(send, text, limit=2000):
    """Send `text` via the `send` coroutine (e.g. interaction.followup.send),
    splitting into <=limit-char chunks on line boundaries to respect Discord's
    2000-character message limit."""
    while text:
        if len(text) <= limit:
            await send(text)
            return
        cut = text.rfind('\n', 0, limit)
        if cut <= 0:                  # no newline to split on — hard cut
            cut = limit
        await send(text[:cut])
        text = text[cut:].lstrip('\n')

# ── Discord UI ────────────────────────────────────────────────────────────
class SkipView(discord.ui.View):
    """View with a Skip button for the training session."""

    def __init__(self, user_id: int, post: dict):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.post = post  # the post THIS message is about (not the live session)

    @discord.ui.button(label="⏭ Next", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Đây không phải session của bạn!", ephemeral=True
            )
            return

        session = sessions.get(self.user_id)
        if not session:
            await interaction.response.send_message(
                "Session đã kết thúc. Dùng `/train` để bắt đầu lại!"
            )
            return

        await interaction.response.defer()
        post = fetch_post() or session['post']
        question = generate_question(post)
        session.update({'post': post, 'question': question})

        await interaction.followup.send(
            f"📖 {post['title']}\n\n"
            f"💬 {question}\n\n"
            "(Trả lời bằng tiếng Anh!)",
            view=SkipView(self.user_id, post)
        )

    @discord.ui.button(label="💬 Real comments", style=discord.ButtonStyle.primary)
    async def show_comments(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Đây không phải session của bạn!", ephemeral=True
            )
            return

        comments = (self.post or {}).get('comments') or []
        if not comments:
            await interaction.response.send_message(
                "Bài này không có comment nào để đọc 😅", ephemeral=True
            )
            return

        body = (
            "🗣️ **Người bản xứ nói (comment thật từ Reddit):**\n\n"
            + "\n\n".join(f"{i}. {c}" for i, c in enumerate(comments, 1))
        )

        await interaction.response.defer(ephemeral=True)
        try:
            # A message can have only one thread, and a thread started from a
            # message shares the message's id (discord.py 2.3.2 has no
            # Message.thread), so reuse the existing one if it's there.
            guild = interaction.guild
            thread = guild.get_thread(interaction.message.id) if guild else None
            if thread is None:
                name = (self.post.get('title') or "Comment thật")[:90]
                thread = await interaction.message.create_thread(
                    name=name, auto_archive_duration=1440
                )
            await send_long(thread.send, body)
            await interaction.followup.send(
                f"Đã đăng comment vào thread 👉 {thread.mention}", ephemeral=True
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            # Missing thread permission or channel can't host threads —
            # fall back to a private (ephemeral) message so it never just fails.
            logger.warning(f"thread post failed, falling back to ephemeral: {e}")
            await send_long(
                lambda t: interaction.followup.send(t, ephemeral=True), body
            )

# ── Discord client ────────────────────────────────────────────────────────
class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # enable in Discord Dev Portal → Bot → Privileged Intents
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Slash commands synced to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally (may take up to 1hr to appear)")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} — ready!")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        session = sessions.get(message.author.id)
        if not session or session.get('mode') != 'training':
            return

        try:
            async with message.channel.typing():
                feedback = generate_feedback(session['question'], message.content)
                session['count'] += 1

                next_post = fetch_post() or session['post']
                next_question = generate_question(next_post)
                session['post'] = next_post
                session['question'] = next_question

            await message.channel.send(
                f"{feedback}\n\n"
                "─────────────────\n"
                f"📖 {next_post['title']}\n\n"
                f"💬 {next_question}",
                view=SkipView(message.author.id, next_post)
            )
        except Exception as e:
            logger.exception("on_message failed")
            await message.channel.send(f"⚠️ Lỗi: {e}")


client = MyClient()

# ── Slash commands ────────────────────────────────────────────────────────
@client.tree.command(name="start", description="Xem hướng dẫn sử dụng bot")
async def cmd_start(interaction: discord.Interaction):
    await interaction.response.send_message(
        "👋 Chào! Mình là English Reflex Trainer.\n\n"
        "Mình dùng bài thật từ Reddit để luyện phản xạ tiếng Anh.\n\n"
        "**/train** — bắt đầu luyện phản xạ\n"
        "**/digest** — đọc digest Reddit hôm nay bằng tiếng Việt\n"
        "**/done** — kết thúc session\n\n"
        "Bắt đầu với **/train** nhé! 🚀"
    )


@client.tree.command(name="train", description="Bắt đầu luyện phản xạ tiếng Anh")
async def cmd_train(interaction: discord.Interaction):
    await interaction.response.defer()

    post = fetch_post()
    if not post:
        await interaction.followup.send(
            "Không lấy được bài từ Reddit. Kiểm tra API key rồi thử lại!"
        )
        return

    question = generate_question(post)
    sessions[interaction.user.id] = {
        'mode': 'training',
        'post': post,
        'question': question,
        'count': 0,
    }

    await interaction.followup.send(
        f"📖 {post['title']}\n\n"
        f"💬 {question}\n\n"
        "(Trả lời bằng tiếng Anh — cứ nhanh, sai không sao!)",
        view=SkipView(interaction.user.id, post)
    )


@client.tree.command(name="digest", description="Đọc digest Reddit hôm nay bằng tiếng Việt")
async def cmd_digest(interaction: discord.Interaction):
    await interaction.response.defer()

    posts = fetch_trending(limit=5)
    if not posts:
        await interaction.followup.send("Không lấy được bài. Thử lại sau!")
        return

    summary = generate_digest(posts)
    links = '\n'.join([f"• {p['url']}" for p in posts])
    await send_long(
        interaction.followup.send,
        f"📰 **Reddit Digest hôm nay:**\n\n{summary}\n\n🔗 Links:\n{links}"
    )


@client.tree.command(name="done", description="Kết thúc session luyện tập")
async def cmd_done(interaction: discord.Interaction):
    session = sessions.pop(interaction.user.id, None)
    if not session:
        await interaction.response.send_message(
            "Chưa có session nào. Dùng `/train` để bắt đầu!"
        )
        return

    count = session.get('count', 0)
    await interaction.response.send_message(
        f"🎯 Session xong! Bạn đã luyện **{count} câu**.\n\n"
        "Ôn lại các chunks đã nhặt được nhé. `/train` để luyện tiếp!"
    )

# ── Keep-alive web server ──────────────────────────────────────────────────
# Render's free tier only runs *web services* and kills any deploy that opens
# no port, so this tiny health-check server keeps the deploy alive and gives
# an uptime pinger (e.g. UptimeRobot) a URL to hit so the service never sleeps.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"English Reflex bot is alive")

    def log_message(self, *args):  # silence per-request logging
        pass


def start_keepalive():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Keep-alive server listening on port {port}")


# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    missing = [k for k in ['DISCORD_TOKEN', 'GEMINI_API_KEY']
               if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}\nCheck your .env file!")

    start_keepalive()
    client.run(DISCORD_TOKEN)
