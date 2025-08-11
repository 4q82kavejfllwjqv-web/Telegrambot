import os
import random
import requests
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from openai import OpenAI

# مفاتيح API وتوكن بوت
TOKEN = os.getenv("TELEGRAM_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@YourChannelName")

client = OpenAI(api_key=OPENAI_API_KEY)

# إعداد قاعدة بيانات للمستخدمين (إذا تريد)
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_seen TEXT,
    last_active TEXT
)""")
conn.commit()

ADMINS = [722400128]  # معرف الأدمنين

app = Flask("")

@app.route("/")
def home():
    return "بوت شغّال!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# دالة تسجيل المستخدمين
async def register_user(user):
    now = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_seen, last_active) VALUES (?, ?, ?, ?)",
        (user.id, user.username or "", now, now)
    )
    cursor.execute(
        "UPDATE users SET last_active = ? WHERE user_id = ?",
        (now, user.id)
    )
    conn.commit()

# دوال TMDb للبحث عن أفلام
def search_movies_tmdb(query, page=1):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "ar",
        "page": page,
        "include_adult": False
    }
    res = requests.get(url, params=params).json()
    return res.get("results", [])[:5]

def format_movie_detail(movie):
    title = movie.get("original_title", "لا يوجد عنوان")
    overview = movie.get("overview", "لا يوجد وصف")
    release_date = movie.get("release_date", "غير معروف")
    rating = movie.get("vote_average", "N/A")
    poster_path = movie.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

    text = f"*{title}* ({release_date[:4]})\n⭐ التقييم: {rating}\n\n{overview}"
    return text, poster_url

# قائمة إيموجي للتفاعل العشوائي
EMOJIS = ["😀", "🤣", "😊", "👍", "🙌", "😎", "🔥", "✨"]

# دالة تحدد إذا النص وصف فيلم أو لا باستخدام GPT
async def is_movie_description(text):
    prompt = (
        "هل النص التالي هو وصف لفيلم أو مسلسل؟ أجب بنعم أو لا فقط.\n\n"
        f"النص: \"{text}\"\n"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content.strip().lower()
        return "نعم" in answer or "yes" in answer
    except Exception:
        return False

# الردود التفاعلية البسيطة (عراقي بسيط + سمايلات أحيانًا)
async def chat_response(text):
    prompt = (
        "أنت صديق عراقي ودود، تتفاعل مع كلام الناس بشكل عفوي وحميمي، "
        "تحب تضيف سمايلات أحيانًا، ولا ترد بشكل رسمي. "
        "إليك رسالة المستخدم:\n"
        f"{text}\n"
        "كيف ترد عليه؟"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip()
        # أضف إيموجي عشوائي 20% من الوقت
        if random.random() < 0.2:
            reply += " " + random.choice(EMOJIS)
        return reply
    except Exception as e:
        return "آسف، صار خطأ."

# معالجة رسائل المستخدم
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)

    text = update.message.text.strip()

    # نتحقق إذا الرسالة وصف فيلم
    if await is_movie_description(text):
        # إذا نعم، نبحث في TMDb
        movies = search_movies_tmdb(text)
        if not movies:
            await update.message.reply_text("ما لقيت فلم يناسب وصفك 😔")
            return
        # نعرض أول 3 أفلام
        msg = "لقيت لك أفلام تناسب الوصف:\n\n"
        for movie in movies[:3]:
            title = movie.get("original_title", "لا يوجد عنوان")
            date = movie.get("release_date", "غير معروف")[:4]
            msg += f"🎬 *{title}* ({date})\n"
        msg += "\nاكتب وصف ثاني لو تريد."
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        # إذا مو وصف فلم، نرد بشكل تفاعلي
        reply = await chat_response(text)
        await update.message.reply_text(reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    await update.message.reply_text("هلا! أرسل لي وصف فلم أو أي كلام، وأنا أساعدك.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("بوت التليجرام شغال!")
    app_bot.run_polling()
