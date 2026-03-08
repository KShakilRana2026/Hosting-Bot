# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট (সম্পূর্ণ বাংলায়)
# ==========================================================

import os
import time
import shutil
import base64
import zipfile
import requests
import telebot
import firebase_admin
import tempfile
import json

from io import BytesIO
from datetime import datetime, timedelta
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ==========================================================
# 🔐 এনভায়রনমেন্ট ভেরিয়েবল লোড
# ==========================================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

# টোকেন চেক
if not BOT_TOKEN:
    print("❌ BOT_TOKEN নেই! .env ফাইল চেক করুন")
    exit(1)

# ==========================================================
# 🚀 বট চালু
# ==========================================================
bot = telebot.TeleBot(BOT_TOKEN)

# Firebase সেটআপ
try:
    if os.path.exists("firebase.json"):
        cred = credentials.Certificate("firebase.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DB_URL
        })
        print("✅ Firebase চালু হয়েছে!")
    else:
        print("❌ firebase.json ফাইল নেই!")
        exit(1)
except Exception as e:
    print(f"❌ Firebase এরর: {e}")
    exit(1)

# ==========================================================
# 🎛 মেনু তৈরি
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 হোস্ট ওয়েবসাইট", "📂 আমার সাইটসমূহ")
    markup.row("🌐 ডোমেইন যোগ করুন", "🗑 সাইট ডিলিট")
    markup.row("📊 দৈনিক লিমিট", "👑 অ্যাডমিন")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 মোট ইউজার", "🌍 মোট সাইট")
    markup.row("🚫 ইউজার ব্লক", "✅ ইউজার আনব্লক")
    markup.row("🔄 লিমিট রিসেট", "📢 ব্রডকাস্ট")
    markup.row("⬅️ মূল মেনু")
    return markup

# ==========================================================
# ✅ ভেরিফিকেশন চেক
# ==========================================================
def is_verified(user_id):
    try:
        ch = bot.get_chat_member(CHANNEL_ID, user_id)
        gp = bot.get_chat_member(GROUP_ID, user_id)
        return ch.status in ["member", "administrator", "creator"] and \
               gp.status in ["member", "administrator", "creator"]
    except:
        return False

# ==========================================================
# 📊 দৈনিক লিমিট চেক
# ==========================================================
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
    
    if data.get("date") != today:
        ref.update({"date": today, "count": 0})
        return True
    
    return data.get("count", 0) < 5

def increase_count(user_id):
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    if data:
        ref.update({"count": data.get("count", 0) + 1})

# ==========================================================
# 🚀 /start কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 চ্যানেল", url="https://t.me/your_channel"),
            InlineKeyboardButton("👥 গ্রুপ", url="https://t.me/your_group")
        )
        bot.reply_to(
            message,
            "❌ আগে আমাদের চ্যানেল ও গ্রুপে জয়েন করুন!",
            reply_markup=markup
        )
        return
    
    welcome_text = (
        f"👋 স্বাগতম {message.from_user.first_name}!\n\n"
        f"📌 এই বট দিয়ে আপনি ওয়েবসাইট হোস্ট করতে পারবেন।\n"
        f"✅ দৈনিক ৫টি সাইট হোস্ট করা যাবে।\n\n"
        f"কিভাবে ব্যবহার করবেন:\n"
        f"1️⃣ আপনার ওয়েবসাইটের ফাইল জিপ করুন\n"
        f"2️⃣ জিপ ফাইলটি এখানে আপলোড করুন\n"
        f"3️⃣ বট অটো ডিপ্লয় করবে\n"
        f"4️⃣ লাইভ লিংক পেয়ে যাবেন\n"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডেল
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    # ভেরিফিকেশন চেক
    if not is_verified(user_id):
        bot.reply_to(message, "❌ আগে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    # ফাইল চেক
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ শুধু ZIP ফাইল দিতে হবে!")
        return
    
    # লিমিট চেক
    if not check_daily_limit(user_id):
        bot.reply_to(message, "❌ আজকের লিমিট শেষ! (৫টি/দিন)")
        return
    
    # সাইজ চেক (50MB)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ ৫০MB এর বড় ফাইল দেয়া যাবে না!")
        return
    
    msg = bot.reply_to(message, "⏳ ডাউনলোড হচ্ছে...")
    
    try:
        # ফাইল ডাউনলোড
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 জিপ এক্সট্র্যাক্ট হচ্ছে...", message.chat.id, msg.message_id)
        
        # টেম্প ফোল্ডার
        with tempfile.TemporaryDirectory() as temp_dir:
            # জিপ এক্সট্র্যাক্ট
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)
            
            # index.html চেক
            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html নেই!", message.chat.id, msg.message_id)
                return
            
            # রিপো নাম
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 GitHub এ আপলোড হচ্ছে...", message.chat.id, msg.message_id)
            
            # GitHub রিপো তৈরি
            headers = {"Authorization": f"token {GITHUB_TOKEN}"}
            r = requests.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json={"name": repo_name, "private": False}
            )
            
            if r.status_code != 201:
                bot.edit_message_text("❌ GitHub রিপো তৈরি হয়নি!", message.chat.id, msg.message_id)
                return
            
            # ফাইল আপলোড
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, temp_dir)
                    
                    with open(file_path, 'rb') as f:
                        content = base64.b64encode(f.read()).decode()
                    
                    requests.put(
                        f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}",
                        headers=headers,
                        json={"message": f"Add {rel_path}", "content": content}
                    )
            
            bot.edit_message_text("🚀 Vercel এ ডিপ্লয় হচ্ছে...", message.chat.id, msg.message_id)
            
            # Vercel ডিপ্লয়
            v_headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
            
            # প্রোজেক্ট তৈরি
            requests.post(
                "https://api.vercel.com/v9/projects",
                headers=v_headers,
                json={
                    "name": repo_name,
                    "gitRepository": {
                        "type": "github",
                        "repo": f"{GITHUB_USERNAME}/{repo_name}"
                    }
                }
            )
            
            # ডিপ্লয়
            deploy = requests.post(
                "https://api.vercel.com/v13/deployments",
                headers=v_headers,
                json={
                    "name": repo_name,
                    "gitSource": {
                        "type": "github",
                        "repo": f"{GITHUB_USERNAME}/{repo_name}",
                        "ref": "main"
                    }
                }
            )
            
            if deploy.status_code not in [200, 201]:
                bot.edit_message_text("❌ Vercel ডিপ্লয় হয়নি!", message.chat.id, msg.message_id)
                return
            
            live_url = f"https://{repo_name}.vercel.app"
            
            # Firebase এ সেভ
            db.reference(f'users/{user_id}/sites/{repo_name}').set({
                "name": repo_name,
                "url": live_url,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            
            increase_count(user_id)
            
            success_text = (
                f"✅ সফলভাবে ডিপ্লয় হয়েছে!\n\n"
                f"🌐 লাইভ URL:\n{live_url}\n\n"
                f"📂 GitHub:\nhttps://github.com/{GITHUB_USERNAME}/{repo_name}\n\n"
                f"⭐ কাস্টম ডোমেইন যোগ করতে 'ডোমেইন যোগ করুন' মেনু ব্যবহার করুন"
            )
            
            bot.edit_message_text(success_text, message.chat.id, msg.message_id)
    
    except Exception as e:
        bot.edit_message_text(f"❌ সমস্যা: {str(e)[:100]}", message.chat.id, msg.message_id)

# ==========================================================
# 📂 আমার সাইটসমূহ
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইটসমূহ")
def my_sites(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    sites = db.reference(f'users/{user_id}/sites').get()
    
    if not sites:
        bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
        return
    
    text = "🌐 আপনার সাইটসমূহ:\n\n"
    for name, data in sites.items():
        text += f"📁 {name}\n🔗 {data.get('url')}\n📅 {data.get('date')}\n\n"
    
    bot.send_message(message.chat.id, text)

# ==========================================================
# 🌐 ডোমেইন যোগ করুন
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন যোগ করুন")
def add_domain(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    sites = db.reference(f'users/{user_id}/sites').get()
    
    if not sites:
        bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
        return
    
    site_list = "\n".join([f"• {name}" for name in sites.keys()])
    bot.reply_to(
        message,
        f"আপনার সাইটসমূহ:\n{site_list}\n\nযে সাইটে ডোমেইন যোগ করবেন তার নাম লিখুন:"
    )
    bot.register_next_step_handler(message, process_domain_name)

def process_domain_name(message):
    project = message.text.strip()
    user_id = message.from_user.id
    
    site = db.reference(f'users/{user_id}/sites/{project}').get()
    
    if not site:
        bot.reply_to(message, "❌ সাইটটি খুঁজে পাইনি!")
        return
    
    bot.reply_to(message, "আপনার ডোমেইন নাম লিখুন (যেমন: example.com):")
    bot.register_next_step_handler(message, lambda m: add_domain_to_vercel(m, project))

def add_domain_to_vercel(message, project):
    domain = message.text.strip()
    
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    r = requests.post(
        f"https://api.vercel.com/v9/projects/{project}/domains",
        headers=headers,
        json={"name": domain}
    )
    
    if r.status_code in [200, 201]:
        bot.reply_to(
            message,
            f"✅ ডোমেইন যোগ হয়েছে!\n\n"
            f"আপনার DNS-এ নিচের রেকর্ড যোগ করুন:\n"
            f"টাইপ: CNAME\n"
            f"নাম: @\n"
            f"ভ্যালু: cname.vercel-dns.com"
        )
    else:
        bot.reply_to(message, f"❌ সমস্যা: {r.json().get('error', {}).get('message', 'Unknown')}")

# ==========================================================
# 🗑 সাইট ডিলিট
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 সাইট ডিলিট")
def delete_site(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    sites = db.reference(f'users/{user_id}/sites').get()
    
    if not sites:
        bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_{name}"))
    
    bot.send_message(message.chat.id, "যে সাইট ডিলিট করবেন সিলেক্ট করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_callback(call):
    project = call.data.replace('del_', '')
    user_id = call.from_user.id
    
    # Vercel থেকে ডিলিট
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers)
    
    # GitHub থেকে ডিলিট
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    requests.delete(f"https://api.github.com/repos/{GITHUB_USERNAME}/{project}", headers=headers)
    
    # Firebase থেকে ডিলিট
    db.reference(f'users/{user_id}/sites/{project}').delete()
    
    bot.edit_message_text(
        f"✅ {project} ডিলিট হয়েছে!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📊 দৈনিক লিমিট
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 দৈনিক লিমিট")
def show_limit(message):
    user_id = message.from_user.id
    
    data = db.reference(f'users/{user_id}').get()
    
    if not data:
        used = 0
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") == today:
            used = data.get("count", 0)
        else:
            used = 0
    
    text = f"📊 আপনি আজ {used}/৫টি সাইট হোস্ট করেছেন।"
    bot.reply_to(message, text)

# ==========================================================
# 👑 অ্যাডমিন প্যানেল
# ==========================================================
admin_sessions = {}

def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)

@bot.message_handler(func=lambda m: m.text == "👑 অ্যাডমিন")
def admin_panel(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ আপনার অ্যাডমিন অ্যাক্সেস নেই!")
        return
    
    if user_id in admin_sessions and admin_sessions[user_id]:
        bot.send_message(message.chat.id, "👑 অ্যাডমিন প্যানেল", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 অ্যাডমিন পাসওয়ার্ড দিন:")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ লগইন সফল!", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ ভুল পাসওয়ার্ড!", reply_markup=main_menu())

# 📊 মোট ইউজার
@bot.message_handler(func=lambda m: m.text == "📊 মোট ইউজার")
def total_users(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    users = db.reference("users").get()
    count = len(users) if users else 0
    bot.reply_to(message, f"👥 মোট ইউজার: {count}")

# 🌍 মোট সাইট
@bot.message_handler(func=lambda m: m.text == "🌍 মোট সাইট")
def total_sites(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    users = db.reference("users").get()
    total = 0
    if users:
        for data in users.values():
            total += len(data.get("sites", {}))
    
    bot.reply_to(message, f"🌐 মোট সাইট: {total}")

# 🚫 ইউজার ব্লক
@bot.message_handler(func=lambda m: m.text == "🚫 ইউজার ব্লক")
def ban_user_start(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারকে ব্লক করবেন তার ID দিন:")
    bot.register_next_step_handler(message, ban_user)

def ban_user(message):
    uid = message.text.strip()
    db.reference(f'blacklist/{uid}').set(True)
    bot.reply_to(message, f"✅ ইউজার {uid} ব্লক হয়েছে!")

# ✅ ইউজার আনব্লক
@bot.message_handler(func=lambda m: m.text == "✅ ইউজার আনব্লক")
def unban_user_start(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারকে আনব্লক করবেন তার ID দিন:")
    bot.register_next_step_handler(message, unban_user)

def unban_user(message):
    uid = message.text.strip()
    db.reference(f'blacklist/{uid}').delete()
    bot.reply_to(message, f"✅ ইউজার {uid} আনব্লক হয়েছে!")

# 🔄 লিমিট রিসেট
@bot.message_handler(func=lambda m: m.text == "🔄 লিমিট রিসেট")
def reset_limit_start(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারের লিমিট রিসেট করবেন তার ID দিন:")
    bot.register_next_step_handler(message, reset_limit)

def reset_limit(message):
    uid = message.text.strip()
    db.reference(f'users/{uid}/count').set(0)
    bot.reply_to(message, f"✅ ইউজার {uid} এর লিমিট রিসেট হয়েছে!")

# 📢 ব্রডকাস্ট
@bot.message_handler(func=lambda m: m.text == "📢 ব্রডকাস্ট")
def broadcast_start(message):
    if not is_admin(message.from_user.id) or not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "সব ইউজারকে কি বার্তা পাঠাবেন?")
    bot.register_next_step_handler(message, broadcast_send)

def broadcast_send(message):
    text = message.text
    users = db.reference("users").get()
    
    if not users:
        bot.reply_to(message, "❌ কোনো ইউজার নেই!")
        return
    
    sent = 0
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 অ্যাডমিন বার্তা:\n\n{text}")
            sent += 1
        except:
            pass
    
    bot.reply_to(message, f"✅ {sent} জন ইউজারে বার্তা পাঠানো হয়েছে!")

# ⬅️ মূল মেনু
@bot.message_handler(func=lambda m: m.text == "⬅️ মূল মেনু")
def back_to_main(message):
    bot.send_message(message.chat.id, "মূল মেনুতে ফিরে এলাম!", reply_markup=main_menu())

# ==========================================================
# 🏁 বট চালু
# ==========================================================
if __name__ == "__main__":
    print("=" * 50)
    print("🔥 টেলিগ্রাম হোস্টিং বট চালু হচ্ছে...")
    print("=" * 50)
    print(f"বট ইউজারনেম: @{bot.get_me().username}")
    print("=" * 50)
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ বট বন্ধ: {e}")
