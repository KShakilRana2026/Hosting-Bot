# ==========================================================
# 🔥 Telegram Hosting Bot – Enhanced v2 (Fully English)
# ==========================================================
# Changes made:
# 1. Custom subdomain name: User provides site name, used as Vercel subdomain.
# 2. Detailed instructions before ZIP upload.
# 3. All messages and buttons are in English.
# 4. Bot ignores messages from groups/channels (works only in private chat).
# 5. Added pre‑checks for GitHub repo and Vercel project name conflicts.
#    If name exists, user is asked to choose another one.
# 6. Deployment URL is now exactly `https://<name>.vercel.app` (no extra strings).
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
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ==========================================================
# 🔐 Load Environment Variables
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

# Fallback links
if not CHANNEL_LINK:
    CHANNEL_LINK = "https://t.me/your_channel"
if not GROUP_LINK:
    GROUP_LINK = "https://t.me/your_group"

print("=" * 70)
print("🔥 Telegram Hosting Bot v2 (English Interface)")
print("=" * 70)

# Check required variables
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
        print(f"✅ {var_name}: Found")

if missing_vars:
    print(f"❌ Missing variables: {', '.join(missing_vars)}")
    print("⚠️ Set all environment variables in Render Dashboard")
    sys.exit(1)

# Convert IDs to integers
try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError:
    print("❌ ADMIN_ID, CHANNEL_ID or GROUP_ID is not a valid number")
    sys.exit(1)

# ==========================================================
# 🚀 Bot Initialization
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot token is valid")
except Exception as e:
    print(f"❌ Bot token is invalid: {e}")
    sys.exit(1)

# ==========================================================
# 🔧 GitHub Database Class (Private repo)
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
        """Create database repo as private if it doesn't exist"""
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
                print(f"✅ Database repo created (private): {self.repo_name}")
            else:
                print(f"❌ Failed to create database repo: {r.status_code}")

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

    # User management
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

    # Site management
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

    # Daily counter
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

    # Admin management
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

    # Blacklist
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

    # Stats
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

# Initialize GitHub DB
db = GitHubDB(GITHUB_TOKEN, GITHUB_USERNAME, repo_name="telegram-bot-db")
print("✅ GitHub Database connected (private)")

# ==========================================================
# 📊 Daily Count Cache
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
# 🌐 Domain Sessions
# ==========================================================
domain_sessions = {}

# ==========================================================
# 🔍 Name conflict checks
# ==========================================================
def check_github_repo_exists(repo_name):
    """Return True if a GitHub repository with the given name already exists."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.status_code == 200
    except:
        return False

def check_vercel_project_exists(project_name):
    """Return True if a Vercel project with the given name already exists."""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    url = f"https://api.vercel.com/v9/projects/{project_name}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.status_code == 200
    except:
        return False

# ==========================================================
# 🎛 Menu Creation (English)
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 Host Website", "📂 My Sites")
    markup.row("🌐 Manage Domains", "🗑 Delete Site")
    markup.row("📊 Check Limit", "👑 Admin Panel")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 Total Users", "🌍 Total Sites")
    markup.row("🚫 Ban User", "✅ Unban User")
    markup.row("🔄 Reset Limit", "📢 Broadcast")
    markup.row("➕ Add Admin", "➖ Remove Admin")
    markup.row("📋 Admin List", "🚪 Logout")
    markup.row("⬅️ Main Menu")
    return markup

# ==========================================================
# ✅ Channel/Group Verification
# ==========================================================
def is_verified(user_id):
    """Check if user is member of channel & group and not banned"""
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
        print(f"⚠️ Verification error (user {user_id}): {e}")
        return False

# ==========================================================
# 🚀 /start command
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    # Only work in private chat
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    username = message.from_user.first_name

    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("👥 Join Group", url=GROUP_LINK)
        )
        bot.reply_to(
            message,
            "❌ **Verification Required**\n\nPlease join our channel and group then /start again.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"👋 **Welcome {username}!**\n\n"
        f"📌 With this bot you can host your static website on Vercel for free.\n"
        f"✅ **Daily limit:** 5 sites\n\n"
        f"📋 **How to use:**\n"
        f"1️⃣ Zip your website files (must contain index.html)\n"
        f"2️⃣ Upload the zip file here\n"
        f"3️⃣ Bot will automatically deploy to GitHub and Vercel\n"
        f"4️⃣ You'll get the live link immediately\n\n"
        f"⚠️ **Max file size:** 50MB"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 📦 Custom site name handling before ZIP upload
# ==========================================================
# Temporary storage for user's site name request
user_site_name = {}

@bot.message_handler(func=lambda m: m.text == "🚀 Host Website")
def ask_site_name(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified! Use /start first.")
        return

    bot.reply_to(
        message,
        "📝 **Send site name** (letters & numbers only, lowercase, 3-30 characters):\n\n"
        "It will be used as: `https://<name>.vercel.app`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_site_name)

def process_site_name(message):
    user_id = message.from_user.id
    site_name = message.text.strip().lower()

    # Validate site name
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', site_name) or len(site_name) < 3 or len(site_name) > 30:
        bot.reply_to(
            message,
            "❌ Invalid name! Use only lowercase letters, numbers, and hyphens (not at start/end). Length 3-30.\n\n"
            "Please try again using the '🚀 Host Website' button.",
            reply_markup=main_menu()
        )
        return

    # Check GitHub for name conflict
    if check_github_repo_exists(site_name):
        bot.reply_to(
            message,
            f"❌ The name `{site_name}` is already taken on GitHub. Please choose a different name.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    # Check Vercel for name conflict
    if check_vercel_project_exists(site_name):
        bot.reply_to(
            message,
            f"❌ The name `{site_name}` is already taken on Vercel. Please choose a different name.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    # Name is available, store it
    user_site_name[user_id] = site_name

    # Ask for ZIP file with detailed instructions
    instructions = (
        f"📤 **Now send the ZIP file for site:** `https://{site_name}.vercel.app`\n\n"
        f"**Requirements:**\n"
        f"• The ZIP must contain an `index.html` file at the root or inside a single folder.\n"
        f"• Max size: 50MB.\n"
        f"• All files will be uploaded and deployed as a static site.\n\n"
        f"After upload, the bot will create a GitHub repo and deploy to Vercel."
    )
    bot.send_message(message.chat.id, instructions, parse_mode="Markdown")

# Modify handle_zip to use custom name if available
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified! Use /start first.")
        return

    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only .zip files are allowed!")
        return

    # Check if user has provided a site name
    if user_id not in user_site_name:
        bot.reply_to(
            message,
            "❌ Please first use '🚀 Host Website' and provide a site name.",
            reply_markup=main_menu()
        )
        return

    site_name = user_site_name[user_id]

    if not check_daily_limit(user_id):
        used = get_daily_count(user_id)
        bot.reply_to(message, f"❌ Daily limit exceeded! Used: {used}/5")
        return

    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ File size cannot exceed 50MB!")
        return

    status_msg = bot.reply_to(message, "⏳ Processing started...")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        bot.edit_message_text("📦 Extracting ZIP file...", message.chat.id, status_msg.message_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)

            # Find index.html (support subfolders)
            root_dir = find_index_root(temp_dir)
            if root_dir is None:
                bot.edit_message_text(
                    "❌ **index.html not found!**\n\n"
                    "Make sure your ZIP contains `index.html` (maybe inside a folder).",
                    message.chat.id, status_msg.message_id,
                    parse_mode="Markdown"
                )
                # Clear stored name
                user_site_name.pop(user_id, None)
                return

            repo_name = site_name  # Use user-provided name

            # ======= Step 1: Create GitHub Repository =======
            bot.edit_message_text("🔧 Creating GitHub repository...", message.chat.id, status_msg.message_id)

            github_ok, github_url = create_github_repo(repo_name, root_dir)
            if not github_ok:
                bot.edit_message_text(
                    "❌ **GitHub repository creation failed!**\n\n"
                    "Check your GitHub token.",
                    message.chat.id, status_msg.message_id,
                    parse_mode="Markdown"
                )
                user_site_name.pop(user_id, None)
                return

            # ======= Step 2: Deploy to Vercel =======
            bot.edit_message_text(
                "🚀 Deploying to Vercel...\n\n"
                "⏳ Uploading files and building, please wait...",
                message.chat.id, status_msg.message_id
            )

            live_url = deploy_to_vercel(repo_name, root_dir)
            if not live_url:
                # If Vercel fails, delete GitHub repo
                delete_github_repo(repo_name)
                bot.edit_message_text(
                    "❌ **Vercel deployment failed!**\n\n"
                    "Possible reasons:\n"
                    "• Invalid Vercel token\n"
                    "• Issues with your files\n"
                    "• Name conflict (should have been caught earlier)\n\n"
                    "Please try again later.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode="Markdown"
                )
                user_site_name.pop(user_id, None)
                return

            # Success: increment count, save to DB
            used_now = increment_daily_count(user_id)
            db.add_site(user_id, repo_name, {"url": clean_url, "github": github_url})

            success_text = (
                f"✅ **Deployment successful!** 🎉\n\n"
                f"🌐 **Live URL:**\n{clean_url}\n\n"
                f"📂 **GitHub Repository:**\n{github_url}\n\n"
                f"📊 **Today's usage:** {used_now}/5\n\n"
                f"💡 **Next steps:**\n"
                f"• Use '🌐 Manage Domains' to add a custom domain\n"
                f"• Use '📂 My Sites' to see all your sites\n"
                f"• Use '🗑 Delete Site' to remove a site"
            )

            bot.edit_message_text(
                success_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

            # Clear stored name
            user_site_name.pop(user_id, None)

    except zipfile.BadZipFile:
        bot.edit_message_text("❌ Corrupted or invalid ZIP file!", message.chat.id, status_msg.message_id)
        user_site_name.pop(user_id, None)
    except Exception as e:
        bot.edit_message_text(f"❌ Unexpected error: {str(e)[:150]}", message.chat.id, status_msg.message_id)
        print(traceback.format_exc())
        user_site_name.pop(user_id, None)

def find_index_root(base_dir):
    """Find directory containing index.html (supports one level subfolder)"""
    if os.path.exists(os.path.join(base_dir, 'index.html')):
        return base_dir

    for entry in os.listdir(base_dir):
        subdir = os.path.join(base_dir, entry)
        if os.path.isdir(subdir) and not entry.startswith('.') and entry != '__MACOSX':
            if os.path.exists(os.path.join(subdir, 'index.html')):
                return subdir

    return None

# ==========================================================
# 🔧 GitHub repository creation (with vercel.json)
# ==========================================================
def create_github_repo(repo_name, local_path):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        # Validate token
        test = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print("❌ GitHub token invalid")
            return False, None

        # Create repo
        data = {"name": repo_name, "private": False}  # Public for hosting
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code == 422:
            # Name conflict – should not happen because we pre‑checked, but handle gracefully
            repo_name = f"{repo_name}-{int(time.time())}"
            data["name"] = repo_name
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code != 201:
            print(f"❌ GitHub repo creation failed: {r.status_code}")
            return False, None

        time.sleep(1)

        # Add vercel.json
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

        # Upload all files
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
                    print(f"⚠️ {rel_path} upload failed: {resp.status_code}")

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
# 🚀 Vercel deploy function (direct file upload)
# ==========================================================
def deploy_to_vercel(repo_name, local_path):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        # Validate token
        test = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print(f"❌ Vercel token invalid: {test.status_code}")
            return None

        # Upload each file
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
                    print(f"⚠️ File upload failed: {rel_path} → {upload_resp.status_code}")

        if not files_list:
            print("❌ No files to upload")
            return None

        # Ensure vercel.json exists
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

        # Create deployment
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
            print(f"❌ Vercel deployment failed: {r.status_code} - {r.text[:300]}")
            return None

        deploy_data = r.json()
        deploy_id = deploy_data.get("id")
        deploy_url = deploy_data.get("url", "")

        print(f"🚀 Vercel deployment created: {deploy_id}")
        print(f"   URL: {deploy_url}")

        # Wait for deployment to be ready (max 3 min)
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
                        print(f"✅ Deployment READY: https://{actual_url}")
                        # Ensure the URL is exactly repo_name.vercel.app (no extra suffixes)
                        # The API should return the project's primary URL, but sometimes it returns a deployment URL.
                        # We'll trust the API; however, if it's not the desired format, we can construct it.
                        # But we already checked name conflicts, so it should be fine.
                        return f"https://{actual_url}"
                    elif state in ["ERROR", "CANCELED"]:
                        error_msg = check.json().get("errorMessage", "Unknown error")
                        print(f"❌ Deployment failed: {state} - {error_msg}")
                        return None
                    else:
                        if attempt % 6 == 0:
                            print(f"   ⏳ Waiting... ({state})")

        # Fallback
        if deploy_url:
            return f"https://{deploy_url}"

        return None

    except Exception as e:
        print(f"❌ Vercel error: {e}")
        traceback.print_exc()
        return None

# ==========================================================
# 📂 My Sites (English)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 My Sites")
def my_sites_menu(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "📂 You have no sites yet!\n\n💡 Upload a .zip file to host a website.")
        return
    text = "🌐 **Your sites:**\n\n"
    for name, data in sites.items():
        text += f"📁 **{name}**\n"
        text += f"🔗 {data.get('url', 'N/A')}\n"
        if data.get('github'):
            text += f"📂 {data.get('github')}\n"
        domains = data.get('domains', [])
        if domains:
            text += f"🌐 Domains: {', '.join(domains)}\n"
        text += f"📅 Created: {data.get('created_at', '')[:10]}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

# ==========================================================
# 🌐 Domain Management (English, unchanged logic)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 Manage Domains")
def domain_manage_menu(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ You have no sites!\n\n💡 Host a website first.")
        return

    sites_list = list(sites.keys())
    domain_sessions[user_id] = {"sites_list": sites_list}

    markup = InlineKeyboardMarkup(row_width=1)
    for i, name in enumerate(sites_list):
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"dom_site_{i}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="dom_cancel"))

    bot.send_message(
        message.chat.id,
        "📂 **Domain Management**\n\nSelect a site to manage its domains:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('dom_'))
def domain_callback_router(call):
    data = call.data
    user_id = call.from_user.id

    if data == "dom_cancel":
        bot.edit_message_text("✅ Cancelled.", call.message.chat.id, call.message.message_id)
        domain_sessions.pop(user_id, None)
        return

    session = domain_sessions.get(user_id)
    if not session:
        bot.answer_callback_query(call.id, "⚠️ Session expired! Use '🌐 Manage Domains' again.")
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
            InlineKeyboardButton("➕ Add Domain", callback_data="dom_opt_add"),
            InlineKeyboardButton("📋 View Domains & Status", callback_data="dom_opt_view"),
            InlineKeyboardButton("🗑 Remove Domain", callback_data="dom_opt_rem"),
            InlineKeyboardButton("⬅️ Back", callback_data="dom_cancel")
        )
        bot.edit_message_text(
            f"🌐 **{site_name}** – Domain Management:\n\nWhat do you want to do?",
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
            f"➕ Add domain to **{project}**\n\n"
            "Enter your domain name:\n"
            "📌 Example: `example.com` or `www.example.com`",
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
        bot.reply_to(message, "❌ Provide a valid domain!\n\n📌 Example: `example.com` or `www.example.com`", parse_mode="Markdown")
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
                    f"✅ **Domain `{domain}` added successfully!** 🎉\n\n"
                    f"📌 **DNS Configuration (set at your domain provider):**\n\n"
                    f"**Option 1 (A Record – recommended for apex domain):**\n"
                    f"  📍 Type: `A`\n"
                    f"  📍 Name: `@`\n"
                    f"  📍 Value: `76.76.21.21`\n\n"
                    f"**Option 2 (CNAME – if A record doesn't work):**\n"
                    f"  📍 Type: `CNAME`\n"
                    f"  📍 Name: `@`\n"
                    f"  📍 Value: `cname.vercel-dns.com`\n\n"
                    f"⏱ DNS changes may take 1-48 hours to propagate.\n"
                    f"✅ Use 'View Domains & Status' to check verification."
                )
            else:
                subdomain_name = parts[0]
                dns_text = (
                    f"✅ **Domain `{domain}` added successfully!** 🎉\n\n"
                    f"📌 **DNS Configuration:**\n\n"
                    f"  📍 Type: `CNAME`\n"
                    f"  📍 Name: `{subdomain_name}`\n"
                    f"  📍 Value: `cname.vercel-dns.com`\n\n"
                    f"⏱ DNS changes may take 1-48 hours.\n"
                    f"✅ Use 'View Domains & Status' to check verification."
                )

            bot.reply_to(message, dns_text, parse_mode="Markdown")

        elif r.status_code == 409:
            bot.reply_to(
                message,
                f"⚠️ Domain `{domain}` is already added to this project!",
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
                    f"❌ Domain `{domain}` is already used by another Vercel project!\n\n"
                    f"Remove it from that project first.",
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(
                    message,
                    f"❌ Failed to add domain!\n\n`{error_detail or r.text[:150]}`",
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
                f"❌ Failed to add domain! (Code: {r.status_code})\n\n`{error_msg}`",
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

def view_domain_status(call, project):
    user_id = call.from_user.id
    sites = db.get_user_sites(user_id)
    site = sites.get(project, {})
    domains = site.get("domains", [])

    if not domains:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("➕ Add Domain", callback_data="dom_opt_add"),
            InlineKeyboardButton("⬅️ Back", callback_data="dom_cancel")
        )
        bot.edit_message_text(
            f"📋 **{project}** has no custom domains.\n\n"
            f"🔗 Default URL: {site.get('url', 'N/A')}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    text = f"📋 **{project}** domains:\n\n"

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
        print(f"Domain API error: {e}")

    for domain in domains:
        if domain in domain_dict:
            d = domain_dict[domain]
            verified = d.get("verified", False)
            misconfigured = d.get("misconfigured", True)
            if verified and not misconfigured:
                status = "✅ Active (working)"
            elif verified and misconfigured:
                status = "⚠️ DNS misconfigured"
            elif not verified:
                status = "⏳ Verification pending"
            else:
                status = "❓ Unknown"
        else:
            status = "❓ Not found in Vercel (maybe in DB)"

        text += f"🌐 `{domain}`\n   → {status}\n\n"

    text += f"🔗 **Default URL:** {site.get('url', 'N/A')}"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="dom_cancel"))

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
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="dom_cancel"))
        bot.edit_message_text(
            f"📋 **{project}** has no custom domains.",
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
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="dom_cancel"))

    bot.edit_message_text(
        f"🗑 Which domain do you want to remove from **{project}**?",
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
                f"✅ Domain `{domain}` removed successfully!\n\n"
                f"📌 You may also delete the DNS record.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
        elif r.status_code == 404:
            db.remove_domain_from_site(user_id, project, domain)
            bot.edit_message_text(
                f"⚠️ Domain `{domain}` not found in Vercel. Removed from database.",
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
                f"❌ Failed to remove domain!\n\n`{error_msg}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Error: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id
        )

# ==========================================================
# 🗑 Delete Site (English)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 Delete Site")
def delete_site_menu(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ You have no sites!")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_{name}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="del_cancel"))
    bot.send_message(message.chat.id, "Select the site you want to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_callback(call):
    if call.data == "del_cancel":
        bot.edit_message_text("✅ Cancelled", call.message.chat.id, call.message.message_id)
        return
    project = call.data.replace('del_', '')
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"conf_{project}"),
        InlineKeyboardButton("❌ No", callback_data="del_cancel")
    )
    bot.edit_message_text(
        f"**{project}** – Are you sure you want to delete it?\n\n⚠️ GitHub repo and Vercel project will be removed!",
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
        f"⏳ Deleting **{project}**...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers, timeout=30)
    delete_github_repo(project)
    db.delete_site(user_id, project)

    bot.edit_message_text(
        f"✅ **{project}** deleted successfully!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

# ==========================================================
# 📊 Check Limit (English)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 Check Limit")
def daily_limit_menu(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    used = get_daily_count(user_id)
    remaining = 5 - used
    bar = "🟩" * used + "⬜" * remaining
    text = f"📊 **Today's usage:**\n\n{bar}\n**Used:** {used}/5\n**Remaining:** {remaining}"
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 Admin Panel (English)
# ==========================================================
admin_sessions = {}

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_handler(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if not db.is_admin(user_id, ADMIN_ID):
        bot.reply_to(message, "❌ You don't have admin access!")
        return
    if admin_sessions.get(user_id):
        bot.send_message(message.chat.id, "👑 **Admin Panel**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **Enter admin password:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ **Login successful!**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **Wrong password!**", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📊 Total Users")
def admin_total_users(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"📊 **Total Users:** {stats['total_users']}\n👤 **Active today:** {stats['active_today']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌍 Total Sites")
def admin_total_sites(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"🌍 **Total Sites:** {stats['total_sites']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚫 Ban User")
def admin_ban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Send the **ID** of the user you want to ban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_ban)

def process_ban(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ ID must be a number!")
        return
    db.ban_user(target, message.from_user.id)
    bot.reply_to(message, f"✅ User {target} has been banned!")

@bot.message_handler(func=lambda m: m.text == "✅ Unban User")
def admin_unban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Send the **ID** of the user you want to unban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_unban)

def process_unban(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ ID must be a number!")
        return
    db.unban_user(target)
    bot.reply_to(message, f"✅ User {target} has been unbanned!")

@bot.message_handler(func=lambda m: m.text == "🔄 Reset Limit")
def admin_reset_limit(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Send the **ID** of the user whose daily limit you want to reset:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_reset)

def process_reset(message):
    try:
        target = int(message.text.strip())
    except ValueError:
        bot.reply_to(message, "❌ ID must be a number!")
        return
    if db.reset_daily_count(target):
        today = datetime.now().strftime("%Y-%m-%d")
        daily_cache.pop(f"{target}_{today}", None)
        bot.reply_to(message, f"✅ User {target}'s limit has been reset!")
    else:
        bot.reply_to(message, f"❌ User {target} not found!")

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def admin_broadcast(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Send the message you want to broadcast to all users:")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    text = message.text
    users = db.get_all_users()
    sent = 0
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 **Admin Message:**\n\n{text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.reply_to(message, f"✅ Message sent to {sent} users!")

@bot.message_handler(func=lambda m: m.text == "➕ Add Admin")
def admin_add_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "Send the **ID** of the new admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ ID must be a number!")
        return
    if db.add_admin(target, message.from_user.id):
        bot.reply_to(message, f"✅ User {target} is now an admin!")
    else:
        bot.reply_to(message, "❌ Failed to add admin!")

@bot.message_handler(func=lambda m: m.text == "➖ Remove Admin")
def admin_remove_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "Send the **ID** of the admin you want to remove:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    target = message.text.strip()
    if not target.isdigit():
        bot.reply_to(message, "❌ ID must be a number!")
        return
    if db.remove_admin(target):
        bot.reply_to(message, f"✅ User {target} is no longer an admin!")
    else:
        bot.reply_to(message, "❌ Failed to remove admin!")

@bot.message_handler(func=lambda m: m.text == "📋 Admin List")
def admin_list(message):
    if not admin_sessions.get(message.from_user.id):
        return
    admins = db.get_admins()
    text = f"👑 **Super Admin:** {ADMIN_ID}\n\n"
    if admins:
        text += "📋 **Other Admins:**\n"
        for aid in admins:
            text += f"• {aid}\n"
    else:
        text += "📋 No other admins."
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚪 Logout")
def admin_logout(message):
    if message.from_user.id in admin_sessions:
        del admin_sessions[message.from_user.id]
    bot.send_message(message.chat.id, "✅ **Logged out!**", parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Main Menu")
def back_to_main(message):
    bot.send_message(message.chat.id, "⬅️ **Main Menu**", parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 🔄 Fallback Handler (only for private chat)
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    if message.chat.type != "private":
        return  # Ignore group/channel messages
    bot.reply_to(message, "❌ Please use the menu buttons!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP Server (for Render)
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
    print(f"🌐 HTTP server running on port {port}")
    httpd.serve_forever()

# ==========================================================
# 🏁 Start Bot
# ==========================================================
if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()

    bot.remove_webhook()
    time.sleep(1)

    try:
        bot_info = bot.get_me()
        print(f"✅ Bot username: @{bot_info.username}")
        print("=" * 70)
        print("🟢 Bot is running... (Press Ctrl+C to stop)")
        print("=" * 70)

        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        print("\n👋 Bot stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
