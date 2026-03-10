# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট – চ্যানেল/গ্রুপ ভেরিফিকেশন সহ
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
import traceback
import threading
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

print("=" * 70)
print("🔥 টেলিগ্রাম হোস্টিং বট (চ্যানেল/গ্রুপ ভেরিফিকেশন সহ)")
print("=" * 70)

# বাধ্যতামূলক ভেরিয়েবল চেক
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

# ID গুলো ইন্টিজারে রূপান্তর
try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError:
    print("❌ ADMIN_ID, CHANNEL_ID বা GROUP_ID সঠিক সংখ্যা নয়")
    sys.exit(1)

# ==========================================================
# 🚀 বট ইনিশিয়ালাইজেশন
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ বট টোকেন সঠিক")
except Exception as e:
    print(f"❌ বট টোকেন ভুল: {e}")
    sys.exit(1)

# ==========================================================
# 🔧 গিটহাব ডাটাবেজ ক্লাস (ফায়ারবেস ছাড়া)
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
        """ডাটাবেজ রিপোজিটরি না থাকলে তৈরি করে"""
        url = f"https://api.github.com/repos/{self.username}/{self.repo_name}"
        r = requests.get(url, headers=self.headers)
        if r.status_code == 404:
            create_url = "https://api.github.com/user/repos"
            data = {
                "name": self.repo_name,
                "private": False,
                "description": "Telegram Bot Database",
                "auto_init": True
            }
            r = requests.post(create_url, headers=self.headers, json=data)
            if r.status_code == 201:
                print(f"✅ ডাটাবেজ রিপোজিটরি তৈরি হয়েছে: {self.repo_name}")
            else:
                print(f"❌ ডাটাবেজ রিপোজিটরি তৈরি ব্যর্থ: {r.status_code}")

    def _get_file_sha(self, path):
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers)
        return r.json().get('sha') if r.status_code == 200 else None

    def _read_file(self, path):
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers)
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
        r = requests.put(url, headers=self.headers, json=data)
        return r.status_code in [200, 201]

    # ইউজার ম্যানেজমেন্ট
    def get_user(self, user_id):
        return self._read_file(f"users/{user_id}.json")

    def save_user(self, user_id, user_data):
        return self._write_file(f"users/{user_id}.json", user_data, f"Update user {user_id}")

    def get_all_users(self):
        url = f"{self.base_url}/users"
        r = requests.get(url, headers=self.headers)
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

# গিটহাব ডাটাবেজ চালু
db = GitHubDB(GITHUB_TOKEN, GITHUB_USERNAME, repo_name="telegram-bot-db")
print("✅ GitHub ডাটাবেজ সংযুক্ত")

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
# 🎛 মেনু তৈরি
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 ওয়েবসাইট হোস্ট করো", "📂 আমার সাইট")
    markup.row("🌐 ডোমেইন যোগ করো", "🗑 সাইট ডিলিট করো")
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
# ✅ চ্যানেল/গ্রুপ ভেরিফিকেশন ফাংশন (সম্পূর্ণ ঠিক করা)
# ==========================================================
def is_verified(user_id):
    """
    চেক করে ইউজার চ্যানেল ও গ্রুপের সদস্য কিনা এবং ব্ল্যাকলিস্টেড কিনা
    """
    # প্রথমে ব্ল্যাকলিস্ট চেক
    if db.is_banned(user_id):
        return False

    try:
        # চ্যানেল মেম্বারশিপ চেক
        ch_member = bot.get_chat_member(CHANNEL_ID, user_id)
        if ch_member.status not in ["member", "administrator", "creator"]:
            return False

        # গ্রুপ মেম্বারশিপ চেক
        gp_member = bot.get_chat_member(GROUP_ID, user_id)
        if gp_member.status not in ["member", "administrator", "creator"]:
            return False

        return True
    except Exception as e:
        # বট যদি গ্রুপ/চ্যানেলে না থাকে বা অন্য কোনো এরর
        print(f"⚠️ ভেরিফিকেশন এরর (user {user_id}): {e}")
        # ডেভেলপমেন্টে ভেরিফিকেশন বাইপাস করতে চাইলে True রিটার্ন করুন
        # প্রোডাকশনে False রিটার্ন করা উচিত
        return False

# ==========================================================
# 🚀 /start কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.first_name

    if not is_verified(user_id):
        # ভেরিফিকেশন না থাকলে জয়েন লিংক পাঠানো
        markup = InlineKeyboardMarkup()
        try:
            channel_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
            group_link = f"https://t.me/c/{str(GROUP_ID)[4:]}"
        except:
            channel_link = "https://t.me/your_channel"
            group_link = "https://t.me/your_group"
        markup.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করো", url=channel_link),
            InlineKeyboardButton("👥 গ্রুপে জয়েন করো", url=group_link)
        )
        bot.reply_to(
            message,
            "❌ **ভেরিফিকেশন প্রয়োজন**\n\nআমাদের চ্যানেল ও গ্রুপে জয়েন করার পর আবার /start দিন।",
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
        f"⚠️ **সর্বোচ্চ ফাইল সাইজ:** ৫০MB"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার
# ==========================================================
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

    status_msg = bot.reply_to(message, "⏳ প্রসেসিং শুরু...")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        bot.edit_message_text("📦 জিপ ফাইল এক্সট্র্যাক্ট করা হচ্ছে...", message.chat.id, status_msg.message_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)

            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html ফাইল পাওয়া যায়নি!", message.chat.id, status_msg.message_id)
                return

            repo_name = f"site-{user_id}-{int(time.time())}"

            bot.edit_message_text("🔧 GitHub রিপোজিটরি তৈরি হচ্ছে...", message.chat.id, status_msg.message_id)

            github_ok, github_url = create_github_repo(repo_name, temp_dir)
            if not github_ok:
                bot.edit_message_text("❌ GitHub রিপোজিটরি তৈরি ব্যর্থ! টোকেন চেক করো।", message.chat.id, status_msg.message_id)
                return

            bot.edit_message_text("🚀 Vercel-এ ডিপ্লয় হচ্ছে...", message.chat.id, status_msg.message_id)

            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                # Vercel ব্যর্থ হলে GitHub রিপো ডিলিট করা ভালো
                delete_github_repo(repo_name)
                bot.edit_message_text(
                    "❌ Vercel ডিপ্লয় ব্যর্থ!\n\n"
                    "🔑 তোমার Vercel টোকেন চেক করো:\n"
                    "১. https://vercel.com/account/tokens এ যাও\n"
                    "২. নতুন টোকেন বানাও (full access)\n"
                    "৩. Render Dashboard-এ VERCEL_TOKEN আপডেট করো\n"
                    "৪. আবার চেষ্টা করো",
                    message.chat.id,
                    status_msg.message_id
                )
                return

            # সফল হলে কাউন্ট বাড়াও ও ডাটাবেজে সেভ করো
            used_now = increment_daily_count(user_id)
            db.add_site(user_id, repo_name, {"url": live_url, "github": github_url})

            success_text = (
                f"✅ **ডিপ্লয় সফল!**\n\n"
                f"🌐 **লাইভ ইউআরএল:**\n{live_url}\n\n"
                f"📂 **GitHub রিপোজিটরি:**\n{github_url}\n\n"
                f"📊 **আজকে ব্যবহার:** {used_now}/৫\n\n"
                f"💡 **পরবর্তী ধাপ:**\n"
                f"• '🌐 ডোমেইন যোগ করো' দিয়ে কাস্টম ডোমেইন যোগ করতে পারো\n"
                f"• '📂 আমার সাইট' দিয়ে সব সাইট দেখতে পারো\n"
                f"• '🗑 সাইট ডিলিট করো' দিয়ে সাইট মুছে ফেলতে পারো"
            )

            bot.edit_message_text(
                success_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    except zipfile.BadZipFile:
        bot.edit_message_text("❌ জিপ ফাইল নষ্ট!", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ অপ্রত্যাশিত ত্রুটি: {str(e)[:100]}", message.chat.id, status_msg.message_id)
        print(traceback.format_exc())

# ==========================================================
# 🔧 গিটহাব রিপোজিটরি তৈরি ফাংশন (API রেসপন্স চেক সহ)
# ==========================================================
def create_github_repo(repo_name, local_path):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        # টোকেন যাচাই
        test = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print("❌ GitHub টোকেন ইনভ্যালিড")
            return False, None

        # রিপো তৈরি
        data = {"name": repo_name, "private": False}
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code == 422:
            # নাম আগে থাকলে নতুন নাম দিয়ে আবার চেষ্টা
            repo_name = f"{repo_name}-{int(time.time())}"
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code != 201:
            print(f"❌ GitHub রিপো তৈরি ব্যর্থ: {r.status_code}")
            return False, None

        # ফাইল আপলোড
        for root, _, files in os.walk(local_path):
            for file in files:
                if file.startswith('.'):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path)
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}"
                data = {"message": f"Add {rel_path}", "content": content, "branch": "main"}
                resp = requests.put(url, headers=headers, json=data, timeout=30)
                if resp.status_code not in [200, 201]:
                    print(f"⚠️ {rel_path} আপলোড ব্যর্থ: {resp.status_code}")

        return True, f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
    except Exception as e:
        print(f"GitHub create error: {e}")
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
# 🚀 Vercel ডিপ্লয় ফাংশন (API রেসপন্স চেক সহ)
# ==========================================================
def deploy_to_vercel(repo_name):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        # টোকেন যাচাই
        test = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print("❌ Vercel টোকেন ইনভ্যালিড")
            return None

        # প্রোজেক্ট তৈরি
        project_data = {
            "name": repo_name,
            "gitRepository": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        requests.post("https://api.vercel.com/v9/projects", headers=headers, json=project_data, timeout=30)

        # ডিপ্লয় তৈরি
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        r = requests.post("https://api.vercel.com/v13/deployments", headers=headers, json=deploy_data, timeout=30)

        if r.status_code in [200, 201]:
            return f"https://{repo_name}.vercel.app"
        if r.status_code == 400:
            # অনেক সময় আগে থেকে থাকলে
            return f"https://{repo_name}.vercel.app"
        return None
    except Exception as e:
        print(f"Vercel error: {e}")
        return None

# ==========================================================
# 📂 আমার সাইট মেনু
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইট")
def my_sites_menu(message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ তুমি ভেরিফাইড নও!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "📂 তোমার এখনো কোনো সাইট নেই!")
        return
    text = "🌐 **তোমার সাইটসমূহ:**\n\n"
    for name, data in sites.items():
        text += f"📁 **{name}**\n🔗 {data.get('url', 'N/A')}\n📅 {data.get('created_at', '')[:10]}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================================
# 🌐 ডোমেইন যোগ করো মেনু
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন যোগ করো")
def add_domain_menu(message):
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
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"dom_{name}"))
    markup.add(InlineKeyboardButton("❌ বাতিল", callback_data="dom_cancel"))
    bot.send_message(message.chat.id, "যে সাইটে ডোমেইন যোগ করতে চাও সেটি নির্বাচন করো:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dom_'))
def domain_callback(call):
    if call.data == "dom_cancel":
        bot.edit_message_text("✅ বাতিল করা হয়েছে", call.message.chat.id, call.message.message_id)
        return
    project = call.data.replace('dom_', '')
    bot.edit_message_text("তোমার ডোমেইন নাম লিখো (যেমন: example.com):", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, lambda m: process_domain(m, project))

def process_domain(message, project):
    domain = message.text.strip()
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    r = requests.post(
        f"https://api.vercel.com/v9/projects/{project}/domains",
        headers=headers,
        json={"name": domain}
    )
    if r.status_code in [200, 201]:
        db.add_domain_to_site(message.from_user.id, project, domain)
        bot.reply_to(
            message,
            f"✅ **ডোমেইন যোগ হয়েছে!**\n\n📌 DNS সেটিংস:\nCNAME → cname.vercel-dns.com",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, f"❌ ডোমেইন যোগ ব্যর্থ: {r.text[:100]}")

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
    # Vercel থেকে ডিলিট
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers)
    # GitHub থেকে ডিলিট
    delete_github_repo(project)
    # ডাটাবেজ থেকে ডিলিট
    db.delete_site(user_id, project)
    bot.edit_message_text(
        f"✅ **{project}** ডিলিট করা হয়েছে!",
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

# অ্যাডমিন মেনু হ্যান্ডলার (শুধু সংক্ষিপ্ত, পূর্ণাঙ্গ আগের মত)
@bot.message_handler(func=lambda m: m.text == "📊 মোট ইউজার")
def admin_total_users(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"📊 **মোট ইউজার:** {stats['total_users']}", parse_mode="Markdown")

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
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ আইডি সংখ্যা হতে হবে!")
        return
    if db.reset_daily_count(target):
        # ক্যাশ থেকেও মুছে ফেলা
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
    # HTTP সার্ভার আলাদা থ্রেডে চালু
    threading.Thread(target=run_http_server, daemon=True).start()

    # 409 কনফ্লিক্ট এড়াতে আগের কোনো ওয়েবহুক সরিয়ে দেওয়া
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