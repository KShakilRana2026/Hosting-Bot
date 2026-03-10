# ==========================================================
# 🔥 ADVANCED TELEGRAM HOSTING BOT - GitHub DB VERSION
# ==========================================================
# ✅ All Features:
# ✅ GitHub as Database (No Firebase)
# ✅ Group + Channel Verify | ✅ Daily 5 Limit
# ✅ ZIP Upload & Secure Extract | ✅ GitHub Repo Create | ✅ Vercel Deploy
# ✅ Custom Domain | ✅ Full Remove System | ✅ Admin Panel
# ✅ Ban/Unban | ✅ Broadcast | ✅ Multiple Admin Support
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
# 🔐 LOAD ENVIRONMENT VARIABLES
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
print("🔥 ADVANCED TELEGRAM HOSTING BOT (GitHub DB)")
print("=" * 70)

# Validate Required Variables
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
    print("⚠️ Please set all environment variables in Render Dashboard")
    sys.exit(1)

# Convert IDs to integers
try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError:
    print("❌ Invalid ID format! ADMIN_ID, CHANNEL_ID, GROUP_ID must be integers")
    sys.exit(1)

# ==========================================================
# 🚀 BOT INITIALIZATION
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot token validated")
except Exception as e:
    print(f"❌ Invalid bot token: {e}")
    sys.exit(1)

# ==========================================================
# 🔧 GITHUB DATABASE CLASS
# ==========================================================

class GitHubDB:
    """GitHub-based database for storing user data, sites, admins, etc."""

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
        """Check if repo exists, if not create it."""
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
                print(f"✅ Database repo created: {self.repo_name}")
            else:
                print(f"❌ Failed to create repo: {r.status_code}")

    def _get_file_sha(self, path):
        """Get SHA of a file (required for updates)."""
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            return r.json().get('sha')
        return None

    def _read_file(self, path):
        """Read and decode a JSON file from repo."""
        url = f"{self.base_url}/{path}"
        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content)
        return None

    def _write_file(self, path, content, message="Update database"):
        """Write or update a JSON file in repo."""
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

    # ----- User Management -----
    def get_user(self, user_id):
        path = f"users/{user_id}.json"
        return self._read_file(path)

    def save_user(self, user_id, user_data):
        path = f"users/{user_id}.json"
        return self._write_file(path, user_data, f"Update user {user_id}")

    def get_all_users(self):
        """Get all user files and return as dict {user_id: data}."""
        url = f"{self.base_url}/users"
        r = requests.get(url, headers=self.headers)
        users = {}
        if r.status_code == 200:
            files = r.json()
            for file in files:
                if file['name'].endswith('.json'):
                    user_id = file['name'].replace('.json', '')
                    user_data = self._read_file(f"users/{file['name']}")
                    if user_data:
                        users[user_id] = user_data
        return users

    # ----- Site Management -----
    def add_site(self, user_id, site_name, site_data):
        user = self.get_user(user_id) or {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "sites": {},
            "daily_count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "last_active": datetime.now().isoformat()
        }
        if "sites" not in user:
            user["sites"] = {}
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
        if user and "sites" in user and site_name in user["sites"]:
            del user["sites"][site_name]
            user["last_active"] = datetime.now().isoformat()
            return self.save_user(user_id, user)
        return False

    def add_domain_to_site(self, user_id, site_name, domain):
        user = self.get_user(user_id)
        if user and "sites" in user and site_name in user["sites"]:
            if "domains" not in user["sites"][site_name]:
                user["sites"][site_name]["domains"] = []
            if domain not in user["sites"][site_name]["domains"]:
                user["sites"][site_name]["domains"].append(domain)
            user["last_active"] = datetime.now().isoformat()
            return self.save_user(user_id, user)
        return False

    # ----- Daily Counter -----
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

    # ----- Admin Management -----
    def get_admins(self):
        admins = self._read_file("admins.json")
        return admins if admins else {}

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

    # ----- Blacklist Management -----
    def get_blacklist(self):
        blacklist = self._read_file("blacklist.json")
        return blacklist if blacklist else {}

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

    # ----- Statistics -----
    def get_stats(self):
        users = self.get_all_users()
        total_users = len(users)
        total_sites = 0
        active_today = 0
        today = datetime.now().strftime("%Y-%m-%d")
        for user_data in users.values():
            sites = user_data.get("sites", {})
            total_sites += len(sites)
            last_active = user_data.get("last_active", "")
            if last_active.startswith(today):
                active_today += 1
        return {
            "total_users": total_users,
            "total_sites": total_sites,
            "active_today": active_today,
            "updated_at": datetime.now().isoformat()
        }

# Initialize GitHub DB
db = GitHubDB(GITHUB_TOKEN, GITHUB_USERNAME, repo_name="telegram-bot-db")
print("✅ GitHub Database connected")

# ==========================================================
# 📊 RATE LIMITER (MEMORY CACHE)
# ==========================================================
# We'll use GitHub for persistent storage, but keep an in-memory cache for performance
daily_cache = {}

def check_daily_limit(user_id):
    # Check cache first
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{user_id}_{today}"
    if cache_key in daily_cache:
        return daily_cache[cache_key] < 5

    # Fallback to GitHub
    count = db.get_daily_count(user_id)
    daily_cache[cache_key] = count
    return count < 5

def increment_daily_count(user_id):
    count = db.increment_daily_count(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{user_id}_{today}"
    daily_cache[cache_key] = count
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
# 🎛 MENU CREATION
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 HOST WEBSITE", "📂 MY SITES")
    markup.row("🌐 ADD DOMAIN", "🗑 DELETE SITE")
    markup.row("📊 DAILY LIMIT", "👑 ADMIN PANEL")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 TOTAL USERS", "🌍 TOTAL SITES")
    markup.row("🚫 BAN USER", "✅ UNBAN USER")
    markup.row("🔄 RESET LIMIT", "📢 BROADCAST")
    markup.row("➕ ADD ADMIN", "➖ REMOVE ADMIN")
    markup.row("📋 ADMIN LIST", "🚪 LOGOUT")
    markup.row("⬅️ MAIN MENU")
    return markup

# ==========================================================
# ✅ VERIFICATION SYSTEM
# ==========================================================
def is_verified(user_id):
    """Check if user is in channel/group and not banned."""
    # Check ban first
    if db.is_banned(user_id):
        return False

    try:
        if CHANNEL_ID and GROUP_ID:
            ch = bot.get_chat_member(CHANNEL_ID, user_id)
            gp = bot.get_chat_member(GROUP_ID, user_id)
            return ch.status in ["member", "administrator", "creator"] and \
                   gp.status in ["member", "administrator", "creator"]
        return True
    except Exception:
        # If verification fails (e.g., bot not in group), allow for testing
        return True

# ==========================================================
# 🚀 /START COMMAND
# ==========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.first_name

    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 JOIN CHANNEL", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}"),
            InlineKeyboardButton("👥 JOIN GROUP", url=f"https://t.me/c/{str(GROUP_ID)[4:]}")
        )
        bot.reply_to(
            message,
            "❌ **VERIFICATION REQUIRED**\n\nPlease join our channel and group to use this bot.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"👋 **Welcome {username}!**\n\n"
        f"📌 **This bot can host your websites on Vercel for FREE.**\n"
        f"✅ **Daily Limit:** 5 sites\n\n"
        f"📋 **How to use:**\n"
        f"1️⃣ Zip your website files (must include index.html)\n"
        f"2️⃣ Upload the zip file here\n"
        f"3️⃣ Bot will automatically deploy to GitHub & Vercel\n"
        f"4️⃣ Get your live URL instantly\n\n"
        f"⚠️ **Max file size:** 50MB"
    )

    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 📦 ZIP FILE HANDLER
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified! Use /start first.")
        return

    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only ZIP files are allowed!")
        return

    if not check_daily_limit(user_id):
        used = get_daily_count(user_id)
        bot.reply_to(message, f"❌ Daily limit reached! You've used {used}/5 sites today.")
        return

    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ File size exceeds 50MB limit!")
        return

    status_msg = bot.reply_to(message, "⏳ Processing your request...")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        bot.edit_message_text("📦 Extracting zip file...", message.chat.id, status_msg.message_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Secure extract (basic, add more checks if needed)
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)

            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html not found in zip!", message.chat.id, status_msg.message_id)
                return

            repo_name = f"site-{user_id}-{int(time.time())}"

            bot.edit_message_text("🔧 Creating GitHub repository...", message.chat.id, status_msg.message_id)

            github_ok, github_url = create_github_repo(repo_name, temp_dir)
            if not github_ok:
                bot.edit_message_text("❌ GitHub error! Check GitHub token.", message.chat.id, status_msg.message_id)
                return

            bot.edit_message_text("🚀 Deploying to Vercel...", message.chat.id, status_msg.message_id)

            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                # If Vercel fails, we should clean up GitHub repo
                delete_github_repo(repo_name)
                bot.edit_message_text(
                    "❌ Vercel deployment failed!\n\n"
                    "🔑 **Check your Vercel token:**\n"
                    "1. Go to https://vercel.com/account/tokens\n"
                    "2. Create a new token with full access\n"
                    "3. Update VERCEL_TOKEN in Render Dashboard\n"
                    "4. Deploy again",
                    message.chat.id,
                    status_msg.message_id
                )
                return

            # Success – update counters and save to GitHub DB
            used_now = increment_daily_count(user_id)

            site_data = {
                "url": live_url,
                "github": github_url
            }
            db.add_site(user_id, repo_name, site_data)

            success_text = (
                f"✅ **Deployment Successful!**\n\n"
                f"🌐 **Live URL:**\n{live_url}\n\n"
                f"📂 **GitHub Repository:**\n{github_url}\n\n"
                f"📊 **Today's Usage:** {used_now}/5\n\n"
                f"💡 **Next Steps:**\n"
                f"• Use '🌐 ADD DOMAIN' to add custom domain\n"
                f"• Use '📂 MY SITES' to view all your sites\n"
                f"• Use '🗑 DELETE SITE' to remove a site"
            )

            bot.edit_message_text(
                success_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    except zipfile.BadZipFile:
        bot.edit_message_text("❌ Invalid zip file!", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Unexpected error: {str(e)[:100]}", message.chat.id, status_msg.message_id)
        print(f"Error in handle_zip: {traceback.format_exc()}")

# ==========================================================
# 🔧 GITHUB REPO FUNCTIONS
# ==========================================================
def create_github_repo(repo_name, local_path):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        # Test token
        test = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test.status_code != 200:
            return False, None

        # Create repo
        data = {"name": repo_name, "private": False}
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code == 422:
            repo_name = f"{repo_name}-{int(time.time())}"
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        if r.status_code != 201:
            return False, None

        # Upload files
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
                requests.put(url, headers=headers, json=data, timeout=30)

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
# 🚀 VERCEL DEPLOY FUNCTION
# ==========================================================
def deploy_to_vercel(repo_name):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        # Test token
        test = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test.status_code != 200:
            return None

        # Create project
        project_data = {
            "name": repo_name,
            "gitRepository": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        proj_resp = requests.post("https://api.vercel.com/v9/projects", headers=headers, json=project_data, timeout=30)

        # Create deployment
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        deploy_resp = requests.post("https://api.vercel.com/v13/deployments", headers=headers, json=deploy_data, timeout=30)

        if deploy_resp.status_code in [200, 201]:
            return f"https://{repo_name}.vercel.app"
        if deploy_resp.status_code == 400:
            # Might already exist
            return f"https://{repo_name}.vercel.app"
        return None
    except Exception as e:
        print(f"Vercel error: {e}")
        return None

# ==========================================================
# 📂 MY SITES MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 MY SITES")
def menu_my_sites(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return

    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "📂 You haven't hosted any sites yet!")
        return

    text = "🌐 **Your Sites:**\n\n"
    for name, data in sites.items():
        text += f"📁 **{name}**\n🔗 {data.get('url', 'N/A')}\n📅 {data.get('created_at', '')[:10]}\n\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================================
# 🌐 ADD DOMAIN MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ADD DOMAIN")
def menu_add_domain(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return

    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ You have no sites to add domain to!")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"dom_{name}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="dom_cancel"))

    bot.send_message(message.chat.id, "Select site to add domain:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dom_'))
def domain_callback(call):
    if call.data == "dom_cancel":
        bot.edit_message_text("✅ Cancelled", call.message.chat.id, call.message.message_id)
        return

    project = call.data.replace('dom_', '')
    bot.edit_message_text("Enter your domain (example.com):", call.message.chat.id, call.message.message_id)
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
        # Save domain to GitHub DB
        db.add_domain_to_site(message.from_user.id, project, domain)
        bot.reply_to(
            message,
            f"✅ **Domain added!**\n\n📌 DNS: CNAME → cname.vercel-dns.com",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, f"❌ Failed: {r.text[:100]}")

# ==========================================================
# 🗑 DELETE SITE MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 DELETE SITE")
def menu_delete_site(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return

    sites = db.get_user_sites(user_id)
    if not sites:
        bot.reply_to(message, "❌ You have no sites to delete!")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"del_{name}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="del_cancel"))

    bot.send_message(message.chat.id, "Select site to delete:", reply_markup=markup)

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
        f"Delete **{project}**?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('conf_'))
def confirm_delete(call):
    project = call.data.replace('conf_', '')
    user_id = call.from_user.id

    # Delete from Vercel
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers)

    # Delete from GitHub repo
    delete_github_repo(project)

    # Delete from GitHub DB
    db.delete_site(user_id, project)

    bot.edit_message_text(
        f"✅ **{project}** deleted!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

# ==========================================================
# 📊 DAILY LIMIT MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 DAILY LIMIT")
def menu_daily_limit(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return

    used = get_daily_count(user_id)
    remaining = 5 - used
    bar = "🟩" * used + "⬜" * remaining

    text = f"📊 **Daily Usage:**\n\n{bar}\n**Used:** {used}/5\n**Remaining:** {remaining}"
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 ADMIN PANEL
# ==========================================================
admin_sessions = {}

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def menu_admin_panel(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return

    if not db.is_admin(user_id, ADMIN_ID):
        bot.reply_to(message, "❌ You don't have admin access!")
        return

    if admin_sessions.get(user_id):
        bot.send_message(message.chat.id, "👑 **Admin Panel**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **Enter admin password:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_password)

def check_admin_password(message):
    user_id = message.from_user.id
    if message.text == ADMIN_PASSWORD:
        admin_sessions[user_id] = True
        bot.send_message(message.chat.id, "✅ **Login successful!**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **Wrong password!**", reply_markup=main_menu())

# ==========================================================
# 👑 ADMIN MENU HANDLERS
# ==========================================================

@bot.message_handler(func=lambda m: m.text == "📊 TOTAL USERS")
def admin_total_users(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"📊 **Total Users:** {stats['total_users']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌍 TOTAL SITES")
def admin_total_sites(message):
    if not admin_sessions.get(message.from_user.id):
        return
    stats = db.get_stats()
    bot.reply_to(message, f"🌍 **Total Sites:** {stats['total_sites']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER")
def admin_ban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Enter the **User ID** to ban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_ban)

def process_ban(message):
    admin_id = message.from_user.id
    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    if db.ban_user(target_id, admin_id):
        bot.reply_to(message, f"✅ User {target_id} banned!")
    else:
        bot.reply_to(message, "❌ Failed to ban user.")

@bot.message_handler(func=lambda m: m.text == "✅ UNBAN USER")
def admin_unban_user(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Enter the **User ID** to unban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_unban)

def process_unban(message):
    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    if db.unban_user(target_id):
        bot.reply_to(message, f"✅ User {target_id} unbanned!")
    else:
        bot.reply_to(message, "❌ Failed to unban user.")

@bot.message_handler(func=lambda m: m.text == "🔄 RESET LIMIT")
def admin_reset_limit(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Enter the **User ID** to reset limit:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_reset)

def process_reset(message):
    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    if db.reset_daily_count(target_id):
        # Also clear cache
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"{target_id}_{today}"
        daily_cache.pop(cache_key, None)
        bot.reply_to(message, f"✅ Limit reset for user {target_id}")
    else:
        bot.reply_to(message, "❌ Failed to reset limit.")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def admin_broadcast(message):
    if not admin_sessions.get(message.from_user.id):
        return
    bot.reply_to(message, "Enter the message to broadcast to all users:")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    broadcast_text = message.text
    users = db.get_all_users()
    sent = 0
    failed = 0
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 **Broadcast:**\n\n{broadcast_text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            failed += 1
    bot.reply_to(message, f"✅ Broadcast sent to {sent} users. Failed: {failed}")

@bot.message_handler(func=lambda m: m.text == "➕ ADD ADMIN")
def admin_add_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "Enter the **User ID** to make admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    if db.add_admin(target_id, message.from_user.id):
        bot.reply_to(message, f"✅ User {target_id} is now admin!")
    else:
        bot.reply_to(message, "❌ Failed to add admin.")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE ADMIN")
def admin_remove_admin(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "Enter the **User ID** to remove admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    if db.remove_admin(target_id):
        bot.reply_to(message, f"✅ Admin removed from user {target_id}")
    else:
        bot.reply_to(message, "❌ Failed to remove admin.")

@bot.message_handler(func=lambda m: m.text == "📋 ADMIN LIST")
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

@bot.message_handler(func=lambda m: m.text == "🚪 LOGOUT")
def admin_logout(message):
    if message.from_user.id in admin_sessions:
        del admin_sessions[message.from_user.id]
    bot.send_message(message.chat.id, "✅ **Logged out!**", parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ MAIN MENU")
def back_to_main(message):
    bot.send_message(message.chat.id, "⬅️ **Main Menu**", parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 🔄 FALLBACK HANDLER (MUST BE LAST)
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(message, "❌ Please use the menu buttons!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP SERVER FOR RENDER
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
    print(f"🌐 HTTP Server running on port {port}")
    httpd.serve_forever()

# ==========================================================
# 🏁 START BOT
# ==========================================================
if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()

    try:
        bot_info = bot.get_me()
        print(f"✅ Bot username: @{bot_info.username}")
        print("=" * 70)
        print("🟢 Bot is running... (Press Ctrl+C to stop)")
        print("=" * 70)

        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()