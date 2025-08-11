import os
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

TOKEN = os.getenv("TELEGRAM_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@YourChannelName")  # الآن يدعم متغير البيئة

# قاعدة بيانات SQLite
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

GENRES = {
    "رومانسي": 10749,
    "أكشن": 28,
    "فنتازيا": 14,
    "كوميدي": 35,
    "رعب": 27,
    "دراما": 18
}

COMPANIES = {
    "نتفلكس": 213,
    "HBO": 49,
    "Apple TV": 2552,
    "Warner Bros": 174
}

def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

def get_movies_by_genre(genre_id, page=1):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "with_genres": genre_id,
        "language": "ar",
        "sort_by": "popularity.desc",
        "page": page
    }
    res = requests.get(url, params=params).json()
    return res.get("results", [])[:10]

def get_movies_by_company(company_id, page=1):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "with_companies": company_id,
        "language": "ar",
        "sort_by": "popularity.desc",
        "page": page
    }
    res = requests.get(url, params=params).json()
    return res.get("results", [])[:10]

def get_movies_sorted_by_rating(desc=True, page=1):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "ar",
        "sort_by": "vote_average.desc" if desc else "vote_average.asc",
        "vote_count.gte": 1000,
        "page": page
    }
    res = requests.get(url, params=params).json()
    return res.get("results", [])[:10]

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "ar"
    }
    res = requests.get(url, params=params).json()
    return res

def format_movie_detail(movie):
    title_en = movie.get("original_title", "No Title")
    overview_ar = movie.get("overview", "لا يوجد وصف")
    release_date = movie.get("release_date", "غير معروف")
    rating = movie.get("vote_average", "N/A")
    poster_path = movie.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

    text = f"*{title_en}* ({release_date[:4]})\n⭐ التقييم: {rating}\n\n{overview_ar}"
    return text, poster_url

async def send_movies_list(update, context, movies, category, id_or_type, page):
    query = update.callback_query
    if not movies:
        await query.edit_message_text("لا توجد نتائج.")
        return

    context.user_data["current_movies"] = movies
    context.user_data["category"] = category
    context.user_data["id_or_type"] = id_or_type
    context.user_data["page"] = page

    first_movie_id = movies[0]["id"]
    first_movie = get_movie_details(first_movie_id)
    text, poster_url = format_movie_detail(first_movie)

    buttons = []
    for i, movie in enumerate(movies):
        prefix = "👉 " if i == 0 else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{movie.get('original_title','No Title')}", callback_data=f"select_movie_{i}"))

    nav_buttons = [
        InlineKeyboardButton("غيرهم", callback_data=f"{category}_{id_or_type}_{page + 1}"),
        InlineKeyboardButton("تغيير القائمة", callback_data="start_menu")
    ]

    keyboard = InlineKeyboardMarkup(build_menu(buttons, 2) + [nav_buttons])

    if poster_url:
        await query.edit_message_media(
            media=InputMediaPhoto(media=poster_url, caption=text, parse_mode="Markdown"),
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_genres(update, context):
    query = update.callback_query
    buttons = [InlineKeyboardButton(name, callback_data=f"genre_{gid}_1") for name, gid in GENRES.items()]
    keyboard = InlineKeyboardMarkup(build_menu(buttons, 2))
    await query.edit_message_text("اختر التصنيف:", reply_markup=keyboard)

async def show_companies(update, context):
    query = update.callback_query
    buttons = [InlineKeyboardButton(name, callback_data=f"company_{cid}_1") for name, cid in COMPANIES.items()]
    keyboard = InlineKeyboardMarkup(build_menu(buttons, 2))
    await query.edit_message_text("اختر شركة الإنتاج:", reply_markup=keyboard)

async def show_ratings(update, context):
    query = update.callback_query
    buttons = [
        InlineKeyboardButton("أعلى 10 أفلام تقييمًا", callback_data="rating_high_1"),
        InlineKeyboardButton("أقل 10 أفلام تقييمًا", callback_data="rating_low_1")
    ]
    keyboard = InlineKeyboardMarkup(build_menu(buttons, 1))
    await query.edit_message_text("اختر:", reply_markup=keyboard)

async def send_sports_link(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("موقع الرياضة: https://ahnjs.is-best.net/?i=1")

def is_admin(user_id):
    return user_id in ADMINS

async def check_subscription(user_id, bot):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

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

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribed = await check_subscription(user.id, context.bot)
    if not subscribed:
        await update.message.reply_text(f"يرجى الاشتراك في القناة أولاً: {CHANNEL_USERNAME}")
        return
    await register_user(user)
    buttons = [
        [InlineKeyboardButton("التصنيفات", callback_data="show_genres")],
        [InlineKeyboardButton("المنصات", callback_data="show_companies")],
        [InlineKeyboardButton("رياضة", callback_data="show_sports")],
        [InlineKeyboardButton("مشاهدة فيلم حسب البحث", callback_data="search_movie")],
    ]
    await update.message.reply_text("اختر من القائمة:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if context.user_data.get("waiting_for_search"):
        query_text = update.message.text.strip()
        search_keyword = query_text.replace(" ", "+")
        search_url = f"https://moviebox.ph/web/searchResult?keyword={search_keyword}"

        context.user_data["waiting_for_search"] = False

        await update.message.reply_text(f"نتائج البحث هنا:\n{search_url}\n\nيمكنك فتح الرابط ومتابعة البحث.")
    else:
        await update.message.reply_text("شكراً لتفاعلك! استخدم /start للبدء.")

async def stats(update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذه الأوامر للأدمن فقط.")
        return
    cutoff = datetime.utcnow() - timedelta(days=7)
    cutoff_iso = cutoff.isoformat()
    cursor.execute("SELECT user_id, username, last_active FROM users WHERE last_active > ?", (cutoff_iso,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("لا يوجد مستخدمين نشطين خلال الأسبوع الماضي.")
        return
    msg = "المستخدمين النشطين خلال 7 أيام:\n"
    for row in rows:
        uid, username, last_active = row
        msg += f"- {username or 'لا يوجد اسم'} (ID: {uid}) آخر نشاط: {last_active}\n"
    await update.message.reply_text(msg)

async def select_movie(update, context):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("_")[-1])

    movies = context.user_data.get("current_movies", [])
    if not movies or index >= len(movies):
        await query.edit_message_text("حدث خطأ، حاول مرة أخرى.")
        return

    movie_id = movies[index]["id"]
    movie = get_movie_details(movie_id)
    text, poster_url = format_movie_detail(movie)

    buttons = []
    for i, movie_i in enumerate(movies):
        prefix = "👉 " if i == index else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{movie_i.get('original_title','No Title')}", callback_data=f"select_movie_{i}"))

    nav_buttons = [
        InlineKeyboardButton("غيرهم", callback_data=f"{context.user_data['category']}_{context.user_data['id_or_type']}_{context.user_data['page']}"),
        InlineKeyboardButton("تغيير القائمة", callback_data="start_menu")
    ]

    keyboard = InlineKeyboardMarkup(build_menu(buttons, 2) + [nav_buttons])

    if poster_url:
        await query.edit_message_media(
            media=InputMediaPhoto(media=poster_url, caption=text, parse_mode="Markdown"),
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def button_handler(update, context):
    query = update.callback_query
    data = query.data
    await query.answer()

    # تسجيل نشاط المستخدم في كل تفاعل
    user = update.effective_user
    await register_user(user)

    if data == "start_menu":
        await start(update, context)
    elif data == "show_genres":
        await show_genres(update, context)
    elif data == "show_companies":
        await show_companies(update, context)
    elif data == "show_sports":
        await send_sports_link(update, context)
    elif data.startswith("genre_"):
        parts = data.split("_")
        genre_id = parts[1]
        page = int(parts[2])
        movies = get_movies_by_genre(genre_id, page)
        await send_movies_list(update, context, movies, "genre", genre_id, page)
    elif data.startswith("company_"):
        parts = data.split("_")
        company_id = parts[1]
        page = int(parts[2])
        movies = get_movies_by_company(company_id, page)
        await send_movies_list(update, context, movies, "company", company_id, page)
    elif data.startswith("rating_"):
        parts = data.split("_")
        desc = True if parts[1] == "high" else False
        page = int(parts[2])
        movies = get_movies_sorted_by_rating(desc, page)
        await send_movies_list(update, context, movies, "rating", parts[1], page)
    elif data.startswith("select_movie_"):
        await select_movie(update, context)
    elif data == "search_movie":
        await query.edit_message_text("أرسل كلمة البحث:")
        context.user_data["waiting_for_search"] = True
    else:
        await query.edit_message_text("اختيار غير معروف.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stats", stats))  # أمر الإحصائيات للأدمن
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("بوت التليجرام شغال!")
    app_bot.run_polling()
