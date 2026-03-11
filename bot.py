# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট – উন্নত সংস্করণ v2 (কাস্টম নাম + ভেরিফাই বাটন)
# ==========================================================
# পরিবর্তনসমূহ:
# ১. Vercel ডাইরেক্ট ফাইল আপলোড (গিট ইন্টিগ্রেশন ছাড়াই কাজ করবে)
# ২. vercel.json স্বয়ংক্রিয়ভাবে GitHub রিপোতে যোগ
# ৩. জিপে সাবফোল্ডার থাকলেও index.html খুঁজে বের করবে
# ৪. ডোমেইন ম্যানেজমেন্ট উন্নত (যোগ/দেখা/সরানো/স্ট্যাটাস)
# ৫. Deployment URL API response থেকে নেয়া (অনুমান নয়)
# ৬. ভালো এরর হ্যান্ডলিং ও ইউজার ফিডব্যাক
# ৭. চ্যানেল/গ্রুপ ভেরিফিকেশনের জন্য আলাদা লিংক সমর্থন
# ৮. GitHub ডাটাবেজ রিপোজিটরি এখন প্রাইভেট (নিরাপত্তা)
# ৯. Vercel ফাইল আপলোড ব্যর্থ হলে তালিকায় যোগ না করা
# ১০. ডোমেইন স্ট্যাটাস একবারেই API কল করে দেখা (দ্রুত)
# ১১. 🆕 কাস্টম প্রকল্প নাম: জিপ ফাইলের নাম অনুযায়ী Vercel সাবডোমেইন
# ১২. 🆕 ভেরিফাই বাটন: জয়েন করার পর আর /start নয়, বাটন চাপলেই ভেরিফিকেশন
# ==========================================================

import os
import sys
import time
import shutil
import base64
import zipfile
import requests
import telebot
import tempfile
import json
import hashlib
import traceback
import threading
import re  # নতুন: স্যানিটাইজের জন্য
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ==========================================================
# 🔐 লোড এনভায়রনমেন্ট ভেরিয়েবল
# ==========================================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("GROUP_ID")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
GROUP_LINK = os.getenv("GROUP_LINK")

if not CHANNEL_LINK:
    CHANNEL_LINK = "https://t.me/your_channel"
if not GROUP_LINK:
    GROUP_LINK = "https://t.me/your_group"

print("=" * 70)
print("🔥 টেলিগ্রাম হোস্টিং বট v2 (কাস্টম নাম + ভেরিফাই বাটন)")
print("=" * 70)

required_vars = {
    "BOT_TOKEN": BOT_TOKEN,
    "GITHUB_TOKEN": GITHUB_TOKEN,
    "GITHUB_USERNAME": GITHUB_USERNAME,
    "VERCEL_TOKEN": VERCEL_TOKEN,
    "ADMIN_PASSWORD": ADMIN_PASSWORD,
    "ADMIN_ID": ADMIN_ID,
    "CHANNEL_ID": CHANNEL_ID,
    "GROUP_ID": GROUP_ID,
}

missing_vars = []
for var_name, var_value in required_vars.items():
    if not var_value:
        missing_vars.append(var_name)
    else:
        print(f"✅ {var_name}: পাওয়া গেছে")

if missing_vars:
    print(f"❌ অনুপস্থিত ভেরিয়েবল: {', '.join(missing_vars)}")
    print("⚠️ Render Dashboard-এ সব Environment Variables সেট করুন")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError:
    print("❌ ADMIN_ID, CHANNEL_ID বা GROUP_ID সঠিক সংখ্যা নয়")
    sys.exit(1)

try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ বট টোকেন সঠিক")
except Exception as e:
    print(f"❌ বট টোকেন ভুল: {e}")
    sys.exit(1)

# ==========================================================
# 🔧 গিটহাব ডাটাবেজ ক্লাস (ফায়ারবেস ছাড়া) – প্রাইভেট রিপো
# ==========================================================
class GitHubDB:
    def __init__(self, token, username, repo_name="telegram-bot-db"):
        self.token = token
        self.username = username
        self.repo_name = repo_name
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{username}/{repo_name}/contents"
        self._ensure_repo_exists()

    def _ensure_repo_exists(self):
        url = f"https://api.github.com/repos/{self.username}/{self.repo_name}"
        r = requests.get(url, headers=self.headers, timeout=10)
        if r.status_code == 404:
            create_url = "https://api.github.com/user/repos"
            data = {
                "name": self.repo_name,
                "private": True,
                "description": "Telegram Bot Database",
                "auto_init": True
            }
            r = requests.post(create_url, headers=self.headers, json=data, timeout=30)
            if r.status_code == 201:
                print(f"✅ ডাটাবেজ রিপোজিটরি তৈরি হয়েছে (প্রাইভেট): {self.repo_name}")
            else:
                print(f"❌ ডাটাবেজ রিপোজিটরি তৈরি ব্যর্থ: {r.status_code}")

    def _get_file_sha(self, path):
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers, timeout=10)
        return r.json().get('sha') if r.status_code == 200 else None

    def _read_file(self, path):
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content)
        return None

    def _write_file(self, path, content, message="Update database"):
        url = f"{self.base_url}/{path}"
        json_str = json.dumps(content, indent=2)
        content_b64 = base64.b64encode(json_str.encode()).decode()
        sha = self._get_file_sha(path)
        data = {
            "message": message,
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        r = requests.put(url, headers=self.headers, json=data, timeout=30)
        return r.status_code in [200, 201]

    # ইউজার ম্যানেজমেন্ট
    def get_user(self, user_id):
        return self._read_file(f"users/{user_id}.json")

    def save_user(self, user_id, user_data):
        return self._write_file(f"users/{user_id}.json", user_data, f"Update user {user_id}")

    def get_all_users(self):
        url = f"{self.base_url}/users"
        r = requests.get(url, headers=self.headers, timeout=10)
        users = {}
        if r.status_code == 200:
            for file in r.json():
                if file['name'].endswith('.json'):
                    uid = file['name'].replace('.json', '')
                    users[uid] = self._read_file(f"users/{file['name']}")
        return users

    # সাইট ম্যানেজমেন্ট
    def add_site(self, user_id, site_name, site_data):
        user = self.get_user(user_id) or {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "sites": {},
            "daily_count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "last_active": datetime.now().isoformat()
        }
        user["sites"][site_name] = {
            "url": site_data.get("url"),
            "github": site_data.get("github"),
            "created_at": datetime.now().isoformat(),
            "domains": []
        }
        user["last_active"] = datetime.now().isoformat()
        return self.save_user(user_id, user)

    def get_user_sites(self, user_id):
        user = self.get_user(user_id)
        return user.get("sites", {}) if user else {}

    def delete_site(self, user_id, site_name):
        user = self.get_user(user_id)
        if user and site_name in user.get("sites", {}):
            del user["sites"][site_name]
            user["last_active"] = datetime.now().isoformat()
            return self.save_user(user_id, user)
        return False

    def add_domain_to_site(self, user_id, site_name, domain):
        user = self.get_user(user_id)
        if user and site_name in user.get("sites", {}):
            if "domains" not in user["sites"][site_name]:
                user["sites"][site_name]["domains"] = []
            if domain not in user["sites"][site_name]["domains"]:
                user["sites"][site_name]["domains"].append(domain)
            user["last_active"] = datetime.now().isoformat()
            return self.save_user(user_id, user)
        return False

    def remove_domain_from_site(self, user_id, site_name, domain):
        user = self.get_user(user_id)
        if user and site_name in user.get("sites", {}):
            domains = user["sites"][site_name].get("domains", [])
            if domain in domains:
                domains.remove(domain)
                user["last_active"] = datetime.now().isoformat()
                return self.save_user(user_id, user)
        return False

    # দৈনিক কাউন্টার
    def increment_daily_count(self, user_id):
        user = self.get_user(user_id) or {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "sites": {},
            "daily_count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "last_active": datetime.now().isoformat()
        }
        today = datetime.now().strftime("%Y-%m-%d")
        if user.get("last_reset") != today:
            user["daily_count"] = 1
            user["last_reset"] = today
        else:
            user["daily_count"] = user.get("daily_count", 0) + 1
        user["last_active"] = datetime.now().isoformat()
        self.save_user(user_id, user)
        return user["daily_count"]

    def get_daily_count(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return 0
        today = datetime.now().strftime("%Y-%m-%d")
        if user.get("last_reset") == today:
            return user.get("daily_count", 0)
        return 0

    def reset_daily_count(self, user_id):
        user = self.get_user(user_id)
        if user:
            user["daily_count"] = 0
            user["last_reset"] = datetime.now().strftime("%Y-%m-%d")
            return self.save_user(user_id, user)
        return False

    # অ্যাডমিন ম্যানেজমেন্ট
    def get_admins(self):
        return self._read_file("admins.json") or {}

    def add_admin(self, user_id, added_by):
        admins = self.get_admins()
        admins[str(user_id)] = {
            "added_by": added_by,
            "added_at": datetime.now().isoformat()
        }
        return self._write_file("admins.json", admins, f"Add admin {user_id}")

    def remove_admin(self, user_id):
        admins = self.get_admins()
        if str(user_id) in admins:
            del admins[str(user_id)]
            return self._write_file("admins.json", admins, f"Remove admin {user_id}")
        return False

    def is_admin(self, user_id, super_admin_id):
        if str(user_id) == str(super_admin_id):
            return True
        admins = self.get_admins()
        return str(user_id) in admins

    # ব্ল্যাকলিস্ট
    def get_blacklist(self):
        return self._read_file("blacklist.json") or {}

    def ban_user(self, user_id, banned_by):
        blacklist = self.get_blacklist()
        blacklist[str(user_id)] = {
            "banned_by": banned_by,
            "banned_at": datetime.now().isoformat()
        }
        return self._write_file("blacklist.json", blacklist, f"Ban user {user_id}")

    def unban_user(self, user_id):
        blacklist = self.get_blacklist()
        if str(user_id) in blacklist:
            del blacklist[str(user_id)]
            return self._write_file("blacklist.json", blacklist, f"Unban user {user_id}")
        return False

    def is_banned(self, user_id):
        blacklist = self.get_blacklist()
        return str(user_id) in blacklist

    # পরিসংখ্যান
    def get_stats(self):
        users = self.get_all_users()
        total_users = len(users)
        total_sites = 0
        active_today = 0
        today = datetime.now().strftime("%Y-%m-%d")
        for data in users.values():
            total_sites += len(data.get("sites", {}))
            if data.get("last_active", "").startswith(today):
                active_today += 1
        return {
            "total_users": total_users,
            "total_sites": total_sites,
            "active_today": active_today
        }

db = GitHubDB(GITHUB_TOKEN, GITHUB_USERNAME, repo_name="telegram-bot-db")
print("✅ GitHub ডাটাবেজ সংযুক্ত (প্রাইভেট)")

# ==========================================================
# 📊 ক্যাশ মেমরি (দৈনিক কাউন্ট)
# ==========================================================
daily_cache = {}

def check_daily_limit(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{user_id}_{today}"
    if cache_key in daily_cache:
        return daily_cache[cache_key] < 5
    count = db.get_daily_count(user_id)
    daily_cache[cache_key] = count
    return count < 5

def increment_daily_count(user_id):
    count = db.increment_daily_count(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_cache[f"{user_id}_{today}"] = count
    return count

def get_daily_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{user_id}_{today}"
    if cache_key in daily_cache:
        return daily_cache[cache_key]
    count = db.get_daily_count(user_id)
    daily_cache[cache_key] = count
    return count

# ==========================================================
# 🌐 ডোমেইন সেশন (কনটেক্সট সংরক্ষণ)
# ==========================================================
domain_sessions = {}

# ==========================================================
# 🎛 মেনু তৈরি
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 ওয়েবসাইট হোস্ট করো", "📂 আমার সাইট")
    markup.row("🌐 ডোমেইন ম্যানেজ করো", "🗑 সাইট ডিলিট করো")
    markup.row("📊 লিমিট দেখো", "👑 অ্যাডমিন প্যানেল")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 মোট ইউজার", "🌍 মোট সাইট")
    markup.row("🚫 ইউজার ব্লক করো", "✅ ইউজার আনব্লক করো")
    markup.row("🔄 লিমিট রিসেট করো", "📢 ব্রডকাস্ট করো")
    markup.row("➕ অ্যাডমিন যোগ করো", "➖ অ্যাডমিন রিমুভ করো")
    markup.row("📋 অ্যাডমিন তালিকা", "🚪 লগআউট")
    markup.row("⬅️ মূল মেনু")
    return markup

# ==========================================================
# ✅ চ্যানেল/গ্রুপ ভেরিফিকেশন ফাংশন
# ==========================================================
def is_verified(user_id):
    if db.is_banned(user_id):
        return False
    try:
        ch_member = bot.get_chat_member(CHANNEL_ID, user_id)
        if ch_member.status not in ["member", "administrator", "creator"]:
            return False
        gp_member = bot.get_chat_member(GROUP_ID, user_id)
        if gp_member.status not in ["member", "administrator", "creator"]:
            return False
        return True
    except Exception as e:
        print(f"⚠️ ভেরিফিকেশন এরর (user {user_id}): {e}")
        return False

# ==========================================================
# 🚀 /start কমান্ড (ভেরিফাই বাটন সহ)
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.first_name

    if not is_verified(user_id):
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করো", url=CHANNEL_LINK),
            InlineKeyboardButton("👥 গ্রুপে জয়েন করো", url=GROUP_LINK),
            InlineKeyboardButton("✅ ভেরিফাই করো", callback_data="verify_me")  # নতুন বাটন
        )
        bot.reply_to(
            message,
            "❌ **ভেরিফিকেশন প্রয়োজন**\n\nআমাদের চ্যানেল ও গ্রুপে জয়েন করার পর '✅ ভেরিফাই করো' বাটনে ক্লিক করুন।",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"👋 **স্বাগতম {username}!**\n\n"
        f"📌 এই বটের মাধ্যমে আপনি বিনামূল্যে আপনার ওয়েবসাইট Vercel-এ হোস্ট করতে পারবেন।\n"
        f"✅ **দৈনিক লিমিট:** ৫টি সাইট\n\n"
        f"📋 **ব্যবহারের নিয়ম:**\n"
        f"১️⃣ আপনার ওয়েবসাইটের ফাইলগুলো জিপ করো (অবশ্যই index.html থাকতে হবে)\n"
        f"২️⃣ জিপ ফাইলটি এখানে আপলোড করো\n"
        f"৩️⃣ বট স্বয়ংক্রিয়ভাবে GitHub ও Vercel-এ ডিপ্লয় করবে\n"
        f"৪️⃣ তুমি সাথে সাথে লাইভ লিংক পাবে\n\n"
        f"⚠️ **সর্বোচ্চ ফাইল সাইজ:** ৫০MB\n"
        f"🎯 **কাস্টম নাম:** জিপ ফাইলের নাম অনুযায়ী Vercel সাবডোমেইন সেট হবে (যেমন macose.zip → macose-xxx.vercel.app)"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# ✅ ভেরিফাই বাটন কলব্যাক হ্যান্ডলার
# ==========================================================
@bot.callback_query_handler(func=lambda call: call.data == "verify_me")
def verify_callback(call):
    user_id = call.from_user.id
    if is_verified(user_id):
        # ভেরিফাই成功后，编辑原消息显示欢迎和主菜单
        welcome_text = (
            f"👋 **স্বাগতম {call.from_user.first_name}!**\n\n"
            f"📌 এই বটের মাধ্যমে আপনি বিনামূল্যে আপনার ওয়েবসাইট Vercel-এ হোস্ট করতে পারবেন।\n"
            f"✅ **দৈনিক লিমিট:** ৫টি সাইট\n\n"
            f"📋 **ব্যবহারের নিয়ম:**\n"
            f"১️⃣ আপনার ওয়েবসাইটের ফাইলগুলো জিপ করো (অবশ্যই index.html থাকতে হবে)\n"
            f"২️⃣ জিপ ফাইলটি এখানে আপলোড করো\n"
            f"৩️⃣ বট স্বয়ংক্রিয়ভাবে GitHub ও Vercel-এ ডিপ্লয় করবে\n"
            f"৪️⃣ তুমি সাথে সাথে লাইভ লিংক পাবে\n\n"
            f"⚠️ **সর্বোচ্চ ফাইল সাইজ:** ৫০MB\n"
            f"🎯 **কাস্টম নাম:** জিপ ফাইলের নাম অনুযায়ী Vercel সাবডোমেইন সেট হবে (যেমন macose.zip → macose-xxx.vercel.app)"
        )
        bot.edit_message_text(
            welcome_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.send_message(call.message.chat.id, "✅ ভেরিফিকেশন সফল! নিচের মেনু ব্যবহার করুন:", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনও চ্যানেল/গ্রুপ জয়েন করেননি!", show_alert=True)

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার (কাস্টম নাম সমর্থন)
# ==========================================================
def find_index_root(base_dir):
    if os.path.exists(os.path.join(base_dir, 'index.html')):
        return base_dir
    for entry in os.listdir(base_dir):
        subdir = os.path.join(base_dir, entry)
        if os.path.isdir(subdir) and not entry.startswith('.') and entry != '__MACOSX':
            if os.path.exists(os.path.join(subdir, 'index.html')):
                return subdir
    return None

def sanitize_project_name(name):
    """জিপ ফাইলের নাম থেকে প্রকল্পের নাম তৈরি (ছোট হাতের, হাইফেন, সংখ্যা)"""
    # এক্সটেনশন বাদ
    base = os.path.splitext(name)[0]
    # ছোট হাতের করুন, স্পেসকে হাইফেনে রূপান্তর
    base = base.lower().replace(' ', '-')
    # শুধু a-z, 0-9, হাইফেন রাখুন
    base = re.sub(r'[^a-z0-9-]', '', base)
    # খালি হয়ে গেলে ফallback
    if not base:
        base = "site"
    # খুব দীর্ঘ হলে ছোট করুন (গিটহাব রিপো নাম সর্বোচ্চ ১০০)
    if len(base) > 80:
        base = base[:80]
    return base

@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও! /start দিয়ে ভেরিফিকেশন করো।")
        return

    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ শুধু .zip ফাইল অনুমোদিত!")
        return

    if not check_daily_limit(user_id):
        used = get_daily_count(user_id)
        bot.reply_to(message, f"❌ আজকের লিমিট শেষ! ব্যবহার করেছো: {used}/৫")
        return

    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ ফাইল সাইজ ৫০MB-এর বেশি হতে পারবে না!")
        return

    status_msg = bot.reply_to(message, "⏳ প্রসেসিং শুরু হচ্ছে...")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        bot.edit_message_text("📦 জিপ ফাইল এক্সট্র্যাক্ট করা হচ্ছে...", message.chat.id, status_msg.message_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)

            root_dir = find_index_root(temp_dir)
            if root_dir is None:
                bot.edit_message_text(
                    "❌ **index.html ফাইল পাওয়া যায়নি!**\n\n"
                    "📌 নিশ্চিত করো যে তোমার জিপ ফাইলে `index.html` আছে।\n"
                    "💡 ফোল্ডারের ভেতরে থাকলেও কাজ করবে (১ লেভেল পর্যন্ত)।",
                    message.chat.id, status_msg.message_id,
                    parse_mode="Markdown"
                )
                return

            # ===== কাস্টম নাম তৈরি (জিপ ফাইলের নাম থেকে) =====
            desired_name = sanitize_project_name(message.document.file_name)
            repo_name = f"{desired_name}-{int(time.time())}"  # ইউনিক করতে টাইমস্ট্যাম্প যোগ
            # তবে create_github_repo ফাংশন আগে থেকেই ৪২২ এ টাইমস্ট্যাম্প যোগ করে, তাই আমরা desired_name-ই পাঠাব
            repo_name = desired_name  # আমরা base name পাঠাব, create_github_repo নিজেই কনফ্লিক্ট হ্যান্ডেল করবে

            # ======= ধাপ ১: GitHub রিপোজিটরি =======
            bot.edit_message_text("🔧 GitHub রিপোজিটরি তৈরি হচ্ছে...", message.chat.id, status_msg.message_id)

            github_ok, github_url = create_github_repo(repo_name, root_dir)
            if not github_ok:
                bot.edit_message_text(
                    "❌ **GitHub রিপোজিটরি তৈরি ব্যর্থ!**\n\n"
                    "🔑 তোমার GitHub Token চেক করো।",
                    message.chat.id, status_msg.message_id,
                    parse_mode="Markdown"
                )
                return

            # ======= ধাপ ২: Vercel ডিপ্লয় =======
            bot.edit_message_text(
                "🚀 Vercel-এ ডিপ্লয় হচ্ছে...\n\n"
                "⏳ ফাইল আপলোড ও বিল্ড চলছে, কিছুক্ষণ অপেক্ষা করো...",
                message.chat.id, status_msg.message_id
            )

            live_url = deploy_to_vercel(repo_name, root_dir)
            if not live_url:
                delete_github_repo(repo_name)
                bot.edit_message_text(
                    "❌ **Vercel ডিপ্লয় ব্যর্থ!**\n\n"
                    "🔑 সম্ভাব্য কারণ:\n"
                    "• Vercel টোকেন ভুল বা মেয়াদ উত্তীর্ণ\n"
                    "• ফাইলে সমস্যা আছে\n\n"
                    "📌 ঠিক করার উপায়:\n"
                    "১. https://vercel.com/account/tokens এ যাও\n"
                    "২. নতুন টোকেন বানাও (full access)\n"
                    "৩. Render Dashboard-এ VERCEL_TOKEN আপডেট করো\n"
                    "৪. আবার চেষ্টা করো",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode="Markdown"
                )
                return

            used_now = increment_daily_count(user_id)
            db.add_site(user_id, repo_name, {"url": live_url, "github": github_url})

            success_text = (
                f"✅ **ডিপ্লয় সফল হয়েছে!** 🎉\n\n"
                f"🌐 **লাইভ ইউআরএল:**\n{live_url}\n\n"
                f"📂 **GitHub রিপোজিটরি:**\n{github_url}\n\n"
                f"📊 **আজকে ব্যবহার:** {used_now}/৫\n\n"
                f"💡 **পরবর্তী ধাপ:**\n"
                f"• '🌐 ডোমেইন ম্যানেজ করো' দিয়ে কাস্টম ডোমেইন যোগ করতে পারো\n"
                f"• '📂 আমার সাইট' দিয়ে সব সাইট দেখতে পারো\n"
                f"• '🗑 সাইট ডিলিট করো' দিয়ে সাইট মুছে ফেলতে পারো"
            )

            bot.edit_message_text(
                success_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    except zipfile.BadZipFile:
        bot.edit_message_text("❌ জিপ ফাইল নষ্ট বা ভুল ফরম্যাট!", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ অপ্রত্যাশিত ত্রুটি: {str(e)[:150]}", message.chat.id, status_msg.message_id)
        print(traceback.format_exc())

# ==========================================================
# 🔧 গিটহাব রিপোজিটরি তৈরি ফাংশন (vercel.json সহ)
# ==========================================================
def create_github_repo(repo_name, local_path):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        test = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print("❌ GitHub টোকেন ইনভ্যালিড")
            return False, None

        data = {"name": repo_name, "private": False}
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code == 422:
            repo_name = f"{repo_name}-{int(time.time())}"
            data["name"] = repo_name
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code != 201:
            print(f"❌ GitHub রিপো তৈরি ব্যর্থ: {r.status_code}")
            return False, None

        time.sleep(1)

        vercel_config = {
            "version": 2,
            "cleanUrls": True,
            "trailingSlash": False
        }
        vercel_content = base64.b64encode(
            json.dumps(vercel_config, indent=2).encode()
        ).decode()
        vercel_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/vercel.json"
        vercel_data = {
            "message": "Add vercel.json for static site config",
            "content": vercel_content,
            "branch": "main"
        }
        requests.put(vercel_url, headers=headers, json=vercel_data, timeout=30)

        for root, dirs, files in os.walk(local_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
            for file in files:
                if file.startswith('.') or file == '.DS_Store':
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path).replace("\\", "/")
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}"
                fdata = {"message": f"Add {rel_path}", "content": content, "branch": "main"}
                resp = requests.put(url, headers=headers, json=fdata, timeout=30)
                if resp.status_code not in [200, 201]:
                    print(f"⚠️ {rel_path} আপলোড ব্যর্থ: {resp.status_code}")

        return True, f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
    except Exception as e:
        print(f"GitHub create error: {e}")
        traceback.print_exc()
        return False, None

def delete_github_repo(repo_name):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
        r = requests.delete(url, headers=headers, timeout=30)
        return r.status_code == 204
    except:
        return False

# ==========================================================
# 🚀 Vercel ডিপ্লয় ফাংশন (ডাইরেক্ট ফাইল আপলোড - গিট ছাড়া)
# ==========================================================
def deploy_to_vercel(repo_name, local_path):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        test = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print(f"❌ Vercel টোকেন ইনভ্যালিড: {test.status_code}")
            return None

        files_list = []
        for root, dirs, filenames in os.walk(local_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
            for fn in filenames:
                if fn.startswith('.') or fn == '.DS_Store':
                    continue
                filepath = os.path.join(root, fn)
                rel_path = os.path.relpath(filepath, local_path).replace("\\", "/")

                with open(filepath, 'rb') as f:
                    content = f.read()

                sha1 = hashlib.sha1(content).hexdigest()

                upload_headers = {
                    "Authorization": f"Bearer {VERCEL_TOKEN}",
                    "Content-Type": "application/octet-stream",
                    "x-vercel-digest": sha1,
                    "Content-Length": str(len(content))
                }
                upload_resp = requests.post(
                    "https://api.vercel.com/v2/files",
                    headers=upload_headers,
                    data=content,
                    timeout=60
                )
                if upload_resp.status_code in [200, 201]:
                    files_list.append({
                        "file": rel_path,
                        "sha": sha1,
                        "size": len(content)
                    })
                else:
                    print(f"⚠️ ফাইল আপলোড ব্যর্থ: {rel_path} → {upload_resp.status_code}")

        if not files_list:
            print("❌ কোনো ফাইল পাওয়া যায়নি")
            return None

        has_vercel_json = any(f["file"] == "vercel.json" for f in files_list)
        if not has_vercel_json:
            vc_content = json.dumps({"version": 2}, indent=2).encode()
            vc_sha = hashlib.sha1(vc_content).hexdigest()
            upload_resp = requests.post(
                "https://api.vercel.com/v2/files",
                headers={
                    "Authorization": f"Bearer {VERCEL_TOKEN}",
                    "Content-Type": "application/octet-stream",
                    "x-vercel-digest": vc_sha,
                    "Content-Length": str(len(vc_content))
                },
                data=vc_content,
                timeout=30
            )
            if upload_resp.status_code in [200, 201]:
                files_list.append({
                    "file": "vercel.json",
                    "sha": vc_sha,
                    "size": len(vc_content)
                })

        deploy_payload = {
            "name": repo_name,
            "files": files_list,
            "target": "production",
            "projectSettings": {
                "framework": None
            }
        }

        r = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=deploy_payload,
            timeout=60
        )

        if r.status_code not in [200, 201]:
            print(f"❌ Vercel ডিপ্লয় ব্যর্থ: {r.status_code} - {r.text[:300]}")
            return None

        deploy_data = r.json()
        deploy_id = deploy_data.get("id")
        deploy_url = deploy_data.get("url", "")

        print(f"🚀 Vercel ডিপ্লয়মেন্ট তৈরি হয়েছে: {deploy_id}")
        print(f"   URL: {deploy_url}")
        print(f"   State: {deploy_data.get('readyState', 'unknown')}")

        if deploy_id:
            for attempt in range(36):
                time.sleep(5)
                check = requests.get(
                    f"https://api.vercel.com/v13/deployments/{deploy_id}",
                    headers=headers,
                    timeout=10
                )
                if check.status_code == 200:
                    state = check.json().get("readyState", "")
                    if state == "READY":
                        actual_url = check.json().get("url", deploy_url)
                        print(f"✅ ডিপ্লয়মেন্ট READY: https://{actual_url}")
                        return f"https://{actual_url}"
                    elif state in ["ERROR", "CANCELED"]:
                        error_msg = check.json().get("errorMessage", "Unknown error")
                        print(f"❌ ডিপ্লয়মেন্ট ব্যর্থ: {state} - {error_msg}")
                        return None
                    else:
                        if attempt % 6 == 0:
                            print(f"   ⏳ অপেক্ষা... ({state})")

        if deploy_url:
            return f"https://{deploy_url}"

        return None

    except Exception as e:
        print(f"❌ Vercel error: {e}")
        traceback.print_exc()
        return None

# ==========================================================
# 📂 আমার সাইট মেনু (ডোমেইন তথ্য সহ)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইট")
def my_sites_menu(message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "📂 তোমার এখনো কোনো সাইট নেই!\n\n💡 একটা .zip ফাইল পাঠাও ওয়েবসাইট হোস্ট করতে।")
        return
    text = "🌐 **তোমার সাইটসমূহ:**\n\n"
    for name, data in sites.items():
        text += f"📁 **{name}**\n"
        text += f"🔗 {data.get('url', 'N/A')}\n"
        if data.get('github'):
            text += f"📂 {data.get('github')}\n"
        domains = data.get('domains', [])
        if domains:
            text += f"🌐 ডোমেইন: {', '.join(domains)}\n"
        text += f"📅 তৈরি: {data.get('created_at', '')[:10]}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

# ==========================================================
# 🌐 ডোমেইন ম্যানেজমেন্ট (উন্নত - যোগ/দেখা/সরানো/স্ট্যাটাস)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন ম্যানেজ করো")
def domain_manage_menu(message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ তোমার কোনো সাইট নেই!\n\n💡 আগে একটা ওয়েবসাইট হোস্ট করো।")
        return

    sites_list = list(sites.keys())
    domain_sessions[user_id] = {"sites_list": sites_list}

    markup = InlineKeyboardMarkup(row_width=1)
    for i, name in enumerate(sites_list):
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"dom_site_{i}"))
    markup.add(InlineKeyboardButton("❌ বাতিল", callback_data="dom_cancel"))

    bot.send_message(
        message.chat.id,
        "📂 **ডোমেইন ম্যানেজমেন্ট**\n\nযে সাইটের ডোমেইন ম্যানেজ করতে চাও সেটি নির্বাচন করো:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('dom_'))
def domain_callback_router(call):
    data = call.data
    user_id = call.from_user.id

    if data == "dom_cancel":
        bot.edit_message_text("✅ বাতিল করা হয়েছে।", call.message.chat.id, call.message.message_id)
        domain_sessions.pop(user_id, None)
        return

    session = domain_sessions.get(user_id)
    if not session:
        bot.answer_callback_query(call.id, "⚠️ সেশন শেষ! আবার '🌐 ডোমেইন ম্যানেজ করো' চাপো।")
        return

    if data.startswith("dom_site_"):
        try:
            idx = int(data.replace("dom_site_", ""))
            if idx >= len(session.get("sites_list", [])):
                return
            site_name = session["sites_list"][idx]
            session["site"] = site_name
        except (ValueError, IndexError):
            return

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("➕ ডোমেইন যোগ করো", callback_data="dom_opt_add"),
            InlineKeyboardButton("📋 ডোমেইন দেখো ও স্ট্যাটাস চেক", callback_data="dom_opt_view"),
            InlineKeyboardButton("🗑 ডোমেইন সরাও", callback_data="dom_opt_rem"),
            InlineKeyboardButton("⬅️ ফিরে যাও", callback_data="dom_cancel")
        )
        bot.edit_message_text(
            f"🌐 **{site_name}** সাইটের ডোমেইন ম্যানেজমেন্ট:\n\nকী করতে চাও?",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    if data == "dom_opt_add":
        project = session.get("site")
        if not project:
            return
        bot.edit_message_text(
            f"➕ **{project}** সাইটে ডোমেইন যোগ করো\n\n"
            "তোমার ডোমেইন নাম লিখো:\n"
            "📌 উদাহরণ: `example.com` অথবা `www.example.com`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, lambda m: process_add_domain(m, project))
        return

    if data == "dom_opt_view":
        project = session.get("site")
        if not project:
            return
        view_domain_status(call, project)
        return

    if data == "dom_opt_rem":
        project = session.get("site")
        if not project:
            return
        show_removable_domains(call, project)
        return

    if data.startswith("dom_rmsel_"):
        try:
            idx = int(data.replace("dom_rmsel_", ""))
            domains_list = session.get("domains_list", [])
            if idx >= len(domains_list):
                return
            domain = domains_list[idx]
            project = session.get("site")
            if not project:
                return
            execute_domain_removal(call, project, domain)
        except (ValueError, IndexError):
            return
        return

def process_add_domain(message, project):
    domain = message.text.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    if not domain or '.' not in domain or ' ' in domain or len(domain) < 3:
        bot.reply_to(message, "❌ সঠিক ডোমেইন নাম দাও!\n\n📌 উদাহরণ: `example.com` বা `www.example.com`", parse_mode="Markdown")
        return

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        r = requests.post(
            f"https://api.vercel.com/v9/projects/{project}/domains",
            headers=headers,
            json={"name": domain},
            timeout=30
        )

        if r.status_code in [200, 201]:
            db.add_domain_to_site(message.from_user.id, project, domain)

            parts = domain.split('.')
            is_apex = len(parts) == 2

            if is_apex:
                dns_text = (
                    f"✅ **ডোমেইন `{domain}` সফলভাবে যোগ হয়েছে!** 🎉\n\n"
                    f"📌 **DNS কনফিগারেশন (তোমার ডোমেইন প্রোভাইডারে সেট করো):**\n\n"
                    f"**অপশন ১ (A Record — Apex Domain-এর জন্য সেরা):**\n"
                    f"  📍 Type: `A`\n"
                    f"  📍 Name: `@`\n"
                    f"  📍 Value: `76.76.21.21`\n\n"
                    f"**অপশন ২ (CNAME — যদি A Record না চলে):**\n"
                    f"  📍 Type: `CNAME`\n"
                    f"  📍 Name: `@`\n"
                    f"  📍 Value: `cname.vercel-dns.com`\n\n"
                    f"⏱ DNS পরিবর্তন কার্যকর হতে ১-৪৮ ঘন্টা লাগতে পারে।\n"
                    f"✅ 'ডোমেইন দেখো' দিয়ে স্ট্যাটাস চেক করতে পারবে।"
                )
            else:
                subdomain_name = parts[0]
                dns_text = (
                    f"✅ **ডোমেইন `{domain}` সফলভাবে যোগ হয়েছে!** 🎉\n\n"
                    f"📌 **DNS কনফিগারেশন:**\n\n"
                    f"  📍 Type: `CNAME`\n"
                    f"  📍 Name: `{subdomain_name}`\n"
                    f"  📍 Value: `cname.vercel-dns.com`\n\n"
                    f"⏱ DNS পরিবর্তন কার্যকর হতে ১-৪৮ ঘন্টা লাগতে পারে।\n"
                    f"✅ 'ডোমেইন দেখো' দিয়ে স্ট্যাটাস চেক করতে পারবে।"
                )

            bot.reply_to(message, dns_text, parse_mode="Markdown")

        elif r.status_code == 409:
            bot.reply_to(
                message,
                f"⚠️ ডোমেইন `{domain}` আগে থেকেই এই প্রোজেক্টে যোগ করা আছে!",
                parse_mode="Markdown"
            )
        elif r.status_code == 400:
            error_detail = ""
            try:
                error_detail = r.json().get("error", {}).get("message", "")
            except:
                pass
            if "already used" in error_detail.lower():
                bot.reply_to(
                    message,
                    f"❌ ডোমেইন `{domain}` অন্য একটি Vercel প্রোজেক্টে ব্যবহৃত হচ্ছে!\n\n"
                    f"📌 আগে সেখান থেকে সরাও, তারপর এখানে যোগ করো।",
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(
                    message,
                    f"❌ ডোমেইন যোগ ব্যর্থ!\n\n`{error_detail or r.text[:150]}`",
                    parse_mode="Markdown"
                )
        else:
            error_msg = ""
            try:
                error_msg = r.json().get("error", {}).get("message", r.text[:150])
            except:
                error_msg = r.text[:150]
            bot.reply_to(
                message,
                f"❌ ডোমেইন যোগ ব্যর্থ! (কোড: {r.status_code})\n\n`{error_msg}`",
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.reply_to(message, f"❌ ত্রুটি: {str(e)[:100]}")

def view_domain_status(call, project):
    user_id = call.from_user.id
    sites = db.get_user_sites(user_id)
    site = sites.get(project, {})
    domains = site.get("domains", [])

    if not domains:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("➕ ডোমেইন যোগ করো", callback_data="dom_opt_add"),
            InlineKeyboardButton("⬅️ ফিরে যাও", callback_data="dom_cancel")
        )
        bot.edit_message_text(
            f"📋 **{project}** সাইটে কোনো কাস্টম ডোমেইন নেই।\n\n"
            f"🔗 ডিফল্ট URL: {site.get('url', 'N/A')}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    text = f"📋 **{project}** সাইটের ডোমেইনসমূহ:\n\n"

    try:
        r = requests.get(
            f"https://api.vercel.com/v9/projects/{project}/domains",
            headers=headers,
            timeout=10
        )
        if r.status_code == 200:
            domains_data = r.json().get("domains", [])
            domain_dict = {d["name"]: d for d in domains_data}
        else:
            domain_dict = {}
    except Exception as e:
        domain_dict = {}
        print(f"ডোমেইন API কল ব্যর্থ: {e}")

    for domain in domains:
        if domain in domain_dict:
            d = domain_dict[domain]
            verified = d.get("verified", False)
            misconfigured = d.get("misconfigured", True)
            if verified and not misconfigured:
                status = "✅ সক্রিয় (কাজ করছে)"
            elif verified and misconfigured:
                status = "⚠️ DNS ভুল কনফিগ"
            elif not verified:
                status = "⏳ যাচাইকরণ বাকি"
            else:
                status = "❓ অজানা অবস্থা"
        else:
            status = "❓ Vercel-এ নেই (সম্ভবত ডাটাবেজে আছে)"

        text += f"🌐 `{domain}`\n   → {status}\n\n"

    text += f"🔗 **ডিফল্ট URL:** {site.get('url', 'N/A')}"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ ফিরে যাও", callback_data="dom_cancel"))

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup,
        disable_web_page_preview=True
    )

def show_removable_domains(call, project):
    user_id = call.from_user.id
    session = domain_sessions.get(user_id, {})
    sites = db.get_user_sites(user_id)
    site = sites.get(project, {})
    domains = site.get("domains", [])

    if not domains:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ ফিরে যাও", callback_data="dom_cancel"))
        bot.edit_message_text(
            f"📋 **{project}** সাইটে কোনো কাস্টম ডোমেইন নেই।",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    session["domains_list"] = domains

    markup = InlineKeyboardMarkup(row_width=1)
    for i, domain in enumerate(domains):
        markup.add(InlineKeyboardButton(f"🗑 {domain}", callback_data=f"dom_rmsel_{i}"))
    markup.add(InlineKeyboardButton("⬅️ ফিরে যাও", callback_data="dom_cancel"))

    bot.edit_message_text(
        f"🗑 **{project}** সাইট থেকে কোন ডোমেইন সরাতে চাও?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

def execute_domain_removal(call, project, domain):
    user_id = call.from_user.id
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}

    try:
        r = requests.delete(
            f"https://api.vercel.com/v9/projects/{project}/domains/{domain}",
            headers=headers,
            timeout=30
        )

        if r.status_code in [200, 204]:
            db.remove_domain_from_site(user_id, project, domain)
            bot.edit_message_text(
                f"✅ ডোমেইন `{domain}` সফলভাবে সরানো হয়েছে!\n\n"
                f"📌 তোমার DNS রেকর্ডও মুছে ফেলতে পারো।",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
        elif r.status_code == 404:
            db.remove_domain_from_site(user_id, project, domain)
            bot.edit_message_text(
                f"⚠️ ডোমেইন `{domain}` Vercel-এ পাওয়া যায়নি।\nডাটাবেজ থেকে সরিয়ে দেওয়া হয়েছে।",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
        else:
            error_msg = ""
            try:
                error_msg = r.json().get("error", {}).get("message", r.text[:100])
            except:
                error_msg = r.text[:100]
            bot.edit_message_text(
                f"❌ ডোমেইন সরানো ব্যর্থ!\n\n`{error_msg}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.edit_message_text(
            f"❌ ত্রুটি: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id
        )

# ==========================================================
# 🗑 সাইট ডিলিট করো মেনু
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 সাইট ডিলিট করো")
def delete_site_menu(message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ তোমার কোনো সাইট নেই!")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_{name}"))
    markup.add(InlineKeyboardButton("❌ বাতিল", callback_data="del_cancel"))
    bot.send_message(message.chat.id, "যে সাইট ডিলিট করতে চাও সেটি নির্বাচন করো:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_callback(call):
    if call.data == "del_cancel":
        bot.edit_message_text("✅ বাতিল করা হয়েছে", call.message.chat.id, call.message.message_id)
        return
    project = call.data.replace('del_', '')
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ হ্যাঁ", callback_data=f"conf_{project}"),
        InlineKeyboardButton("❌ না", callback_data="del_cancel")
    )
    bot.edit_message_text(
        f"**{project}** কি সত্যিই ডিলিট করতে চাও?\n\n⚠️ GitHub রিপো ও Vercel প্রোজেক্ট মুছে যাবে!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('conf_'))
def confirm_delete(call):
    project = call.data.replace('conf_', '')
    user_id = call.from_user.id

    bot.edit_message_text(
        f"⏳ **{project}** ডিলিট করা হচ্ছে...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers, timeout=30)
    delete_github_repo(project)
    db.delete_site(user_id, project)

    bot.edit_message_text(
        f"✅ **{project}** সফলভাবে ডিলিট করা হয়েছে!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

# ==========================================================
# 📊 লিমিট দেখো মেনু
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 লিমিট দেখো")
def daily_limit_menu(message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও!")
        return
    used = get_daily_count(user_id)
    remaining = 5 - used
    bar = "🟩" * used + "⬜" * remaining
    text = f"📊 **আজকের ব্যবহার:**\n\n{bar}\n**ব্যবহার করেছো:** {used}/৫\n**বাকি:** {remaining}"
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 অ্যাডমিন প্যানেল
# ==========================================================
admin_sessions = {}

@bot.message_handler(func=lambda m: m.text == "👑 অ্যাডমিন প্যানেল")
def admin_panel_handler(message):
    user_id = message.from_user.id
    if not db.is_admin(user_id, ADMIN_ID):
        bot.reply_to(message, "❌ তোমার অ্যাডমিন অ্যাক্সেস নেই!")
        return
    if admin_sessions.get(user_id):
        bot.send_message(message.chat.id, "👑 **অ্যাডমিন প্যানেল**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **অ্যাডমিন পাসওয়ার্ড দাও:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ **লগইন সফল!**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **ভুল পাসওয়ার্ড!**", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📊 মোট ইউজার")
def admin_total_users(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"📊 **মোট ইউজার:** {stats['total_users']}\n👤 **আজকে সক্রিয়:** {stats['active_today']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌍 মোট সাইট")
def admin_total_sites(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"🌍 **মোট সাইট:** {stats['total_sites']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚫 ইউজার ব্লক করো")
def admin_ban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "যে ইউজারকে ব্লক করতে চাও তার **আইডি** দাও:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_ban)

def process_ban(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    db.ban_user(target, message.from_user.id)
    bot.reply_to(message, f"✅ ইউজার {target} ব্লক করা হয়েছে!")

@bot.message_handler(func=lambda m: m.text == "✅ ইউজার আনব্লক করো")
def admin_unban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "যে ইউজারকে আনব্লক করতে চাও তার **আইডি** দাও:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_unban)

def process_unban(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    db.unban_user(target)
    bot.reply_to(message, f"✅ ইউজার {target} আনব্লক করা হয়েছে!")

@bot.message_handler(func=lambda m: m.text == "🔄 লিমিট রিসেট করো")
def admin_reset_limit(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "যে ইউজারের লিমিট রিসেট করতে চাও তার **আইডি** দাও:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_reset)

def process_reset(message):
    try:
        target = int(message.text.strip())
    except ValueError:
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    if db.reset_daily_count(target):
        today = datetime.now().strftime("%Y-%m-%d")
        daily_cache.pop(f"{target}_{today}", None)
        bot.reply_to(message, f"✅ ইউজার {target} এর লিমিট রিসেট করা হয়েছে!")
    else:
        bot.reply_to(message, f"❌ ইউজার {target} খুঁজে পাওয়া যায়নি!")

@bot.message_handler(func=lambda m: m.text == "📢 ব্রডকাস্ট করো")
def admin_broadcast(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "সব ইউজারকে কী বার্তা পাঠাতে চাও?")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    text = message.text
    users = db.get_all_users()
    sent = 0
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 **অ্যাডমিন বার্তা:**\n\n{text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.reply_to(message, f"✅ {sent} জন ইউজারে বার্তা পাঠানো হয়েছে!")

@bot.message_handler(func=lambda m: m.text == "➕ অ্যাডমিন যোগ করো")
def admin_add_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "নতুন অ্যাডমিনের **আইডি** দাও:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    if db.add_admin(target, message.from_user.id):
        bot.reply_to(message, f"✅ ইউজার {target} অ্যাডমিন হয়েছে!")
    else:
        bot.reply_to(message, "❌ অ্যাডমিন যোগ ব্যর্থ!")

@bot.message_handler(func=lambda m: m.text == "➖ অ্যাডমিন রিমুভ করো")
def admin_remove_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "যে অ্যাডমিনকে রিমুভ করতে চাও তার **আইডি** দাও:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    if db.remove_admin(target):
        bot.reply_to(message, f"✅ ইউজার {target} এর অ্যাডমিন ক্ষমতা কেড়ে নেওয়া হয়েছে!")
    else:
        bot.reply_to(message, "❌ অ্যাডমিন রিমুভ ব্যর্থ!")

@bot.message_handler(func=lambda m: m.text == "📋 অ্যাডমিন তালিকা")
def admin_list(message):
    if not admin_sessions.get(message.from_user.id):
        return
    admins = db.get_admins()
    text = f"👑 **মূল অ্যাডমিন:** {ADMIN_ID}\n\n"
    if admins:
        text += "📋 **অন্যান্য অ্যাডমিন:**\n"
        for aid in admins:
            text += f"• {aid}\n"
    else:
        text += "📋 অন্য কোনো অ্যাডমিন নেই।"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚪 লগআউট")
def admin_logout(message):
    if message.from_user.id in admin_sessions:
        del admin_sessions[message.from_user.id]
    bot.send_message(message.chat.id, "✅ **লগআউট!**", parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ মূল মেনু")
def back_to_main(message):
    bot.send_message(message.chat.id, "⬅️ **মূল মেনু**", parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 🔄 ফলব্যাক হ্যান্ডলার (সবশেষে)
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(message, "❌ দয়া করে মেনুর বাটন ব্যবহার করো!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP সার্ভার (Render-এর জন্য)
# ==========================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass

def run_http_server():
    port = int(os.getenv("PORT", 10000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"🌐 HTTP সার্ভার চলছে পোর্ট {port}-এ")
    httpd.serve_forever()

# ==========================================================
# 🏁 বট চালু করা
# ==========================================================
if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    bot.remove_webhook()
    time.sleep(1)

    try:
        bot_info = bot.get_me()
        print(f"✅ বট ইউজারনেম: @{bot_info.username}")
        print("=" * 70)
        print("🟢 বট চলছে... (Ctrl+C দিয়ে বন্ধ করতে পারো)")
        print("=" * 70)
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n👋 বট বন্ধ করা হলো")
    except Exception as e:
        print(f"❌ মারাত্মক ত্রুটি: {e}")
        traceback.print_exc()