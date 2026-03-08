import os
import telebot
import firebase_admin
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup
from datetime import datetime

# =============================
# 🔐 CONFIG (EDIT ONLY HERE)
# =============================

BOT_TOKEN = "8551402834:AAEj34D1ImTVuSGGb4SKdsSiWPMz4S_yeN4"
CHANNEL_ID = -1003736706053
GROUP_ID = -1003771909344
FIREBASE_DB_URL = "https://bd-host-43562-default-rtdb.firebaseio.com"

# =============================

bot = telebot.TeleBot(BOT_TOKEN)

# Firebase Init
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DB_URL
})

# =============================
# 🎛 MAIN MENU
# =============================

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Host Website", "📂 My Sites")
    markup.row("🌐 Add Domain", "🗑 Remove Site")
    markup.row("📊 Daily Limit")
    return markup

# =============================
# 🔎 VERIFY SYSTEM
# =============================

def is_verified(user_id):
    try:
        channel = bot.get_chat_member(CHANNEL_ID, user_id)
        group = bot.get_chat_member(GROUP_ID, user_id)

        if channel.status in ["member", "administrator", "creator"] and \
           group.status in ["member", "administrator", "creator"]:
            return True
    except:
        return False
    return False

# =============================
# 📊 DAILY LIMIT SYSTEM
# =============================

def check_daily_limit(user_id):
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    today = datetime.now().strftime("%Y-%m-%d")

    if not data:
        ref.set({
            "date": today,
            "count": 0,
            "sites": {}
        })
        return True

    if data["date"] != today:
        ref.update({
            "date": today,
            "count": 0
        })
        return True

    if data["count"] >= 5:
        return False

    return True

def increase_count(user_id):
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    ref.update({
        "count": data["count"] + 1
    })

# =============================
# 🚀 COMMAND HANDLERS
# =============================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(
            message,
            "❌ আগে আমাদের Group & Channel join করুন।"
        )
        return

    bot.send_message(
        message.chat.id,
        "👑 Welcome to Hosting Bot\n\nSelect an option:",
        reply_markup=main_menu()
    )

# =============================
# 🚀 HOST WEBSITE BUTTON
# =============================

@bot.message_handler(func=lambda m: m.text == "🚀 Host Website")
def host_website(message):
    user_id = message.from_user.id

    if not check_daily_limit(user_id):
        bot.reply_to(message, "❌ Daily limit reached (5 sites per day).")
        return

    bot.reply_to(message, "📦 Send your ZIP file to host.")

# =============================
# 📊 DAILY LIMIT BUTTON
# =============================

@bot.message_handler(func=lambda m: m.text == "📊 Daily Limit")
def show_limit(message):
    ref = db.reference(f'users/{message.from_user.id}')
    data = ref.get()

    if not data:
        bot.reply_to(message, "Used: 0 / 5")
    else:
        bot.reply_to(message, f"Used: {data['count']} / 5")

# =============================
# 📂 MY SITES (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "📂 My Sites")
def my_sites(message):
    bot.reply_to(message, "🔄 Coming in Part 2...")

# =============================
# 🌐 ADD DOMAIN (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "🌐 Add Domain")
def add_domain(message):
    bot.reply_to(message, "🔄 Domain system coming in Part 3...")

# =============================
# 🗑 REMOVE SITE (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Site")
def remove_site(message):
    bot.reply_to(message, "🔄 Remove system coming in Part 4...")

# =============================
# 🔄 START BOT
# =============================

print("Bot Running...")
bot.infinity_polling()
