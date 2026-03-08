# ==========================================================
# 🔥 Telegram Hosting Bot (For Render Web Service)
# ==========================================================

import os
import sys
import time
import shutil
import base64
import zipfile
import requests
import telebot
import firebase_admin
import tempfile
import json
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from io import BytesIO
from datetime import datetime, timedelta
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ==========================================================
# 🔐 Load Environment Variables
# ==========================================================
load_dotenv()

# Required environment variables with error checking
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("GROUP_ID")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

# Print environment variables status (without showing actual values)
print("=" * 60)
print("🔥 Telegram Hosting Bot is starting...")
print("=" * 60)
print(f"BOT_TOKEN: {'✅ Found' if BOT_TOKEN else '❌ Missing'}")
print(f"GITHUB_TOKEN: {'✅ Found' if GITHUB_TOKEN else '❌ Missing'}")
print(f"GITHUB_USERNAME: {'✅ Found' if GITHUB_USERNAME else '❌ Missing'}")
print(f"VERCEL_TOKEN: {'✅ Found' if VERCEL_TOKEN else '❌ Missing'}")
print(f"ADMIN_PASSWORD: {'✅ Found' if ADMIN_PASSWORD else '❌ Missing'}")
print(f"ADMIN_ID: {'✅ Found' if ADMIN_ID else '❌ Missing'}")
print(f"CHANNEL_ID: {'✅ Found' if CHANNEL_ID else '❌ Missing'}")
print(f"GROUP_ID: {'✅ Found' if GROUP_ID else '❌ Missing'}")
print(f"FIREBASE_DB_URL: {'✅ Found' if FIREBASE_DB_URL else '❌ Missing'}")
print("=" * 60)

# Check required variables
missing_vars = []
if not BOT_TOKEN: missing_vars.append("BOT_TOKEN")
if not GITHUB_TOKEN: missing_vars.append("GITHUB_TOKEN")
if not GITHUB_USERNAME: missing_vars.append("GITHUB_USERNAME")
if not VERCEL_TOKEN: missing_vars.append("VERCEL_TOKEN")
if not ADMIN_PASSWORD: missing_vars.append("ADMIN_PASSWORD")
if not ADMIN_ID: missing_vars.append("ADMIN_ID")
if not CHANNEL_ID: missing_vars.append("CHANNEL_ID")
if not GROUP_ID: missing_vars.append("GROUP_ID")
if not FIREBASE_DB_URL: missing_vars.append("FIREBASE_DB_URL")

if missing_vars:
    print(f"❌ The following Environment Variables are missing: {', '.join(missing_vars)}")
    print("⚠️ Please set Environment Variables in the Render Dashboard")
    sys.exit(1)

# Convert to proper types
try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError as e:
    print(f"❌ ADMIN_ID, CHANNEL_ID or GROUP_ID has invalid format: {e}")
    print("⚠️ These must be numbers (e.g.: 123456789)")
    sys.exit(1)

# ==========================================================
# 🚀 Bot Initialization
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot token is valid")
except Exception as e:
    print(f"❌ Invalid bot token: {e}")
    sys.exit(1)

# ==========================================================
# 🔥 Firebase initialization with multiple methods
# ==========================================================

def init_firebase():
    """Try multiple methods to initialize Firebase"""

    print("🔄 Firebase initialization started...")

    # Method 1: Direct file (for local development)
    if os.path.exists("firebase.json"):
        try:
            cred = credentials.Certificate("firebase.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })
            print("✅ Firebase initialized from firebase.json file")
            return True
        except Exception as e:
            print(f"❌ Firebase init from file failed: {e}")

    # Method 2: Secret file in Render (/etc/secrets)
    if os.path.exists("/etc/secrets/firebase.json"):
        try:
            cred = credentials.Certificate("/etc/secrets/firebase.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })
            print("✅ Firebase initialized from Render secret file")
            return True
        except Exception as e:
            print(f"❌ Firebase init from secret file failed: {e}")

    # Method 3: Base64 from environment variable
    firebase_base64 = os.getenv("FIREBASE_CONFIG_BASE64")
    if firebase_base64:
        try:
            print("🔄 Found FIREBASE_CONFIG_BASE64, decoding...")

            # Decode base64 to JSON string
            json_bytes = base64.b64decode(firebase_base64)
            json_str = json_bytes.decode('utf-8')
            cred_dict = json.loads(json_str)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(cred_dict, f)
                temp_path = f.name
                print(f"🔄 Created temp file: {temp_path}")

            # Initialize Firebase with temp file
            cred = credentials.Certificate(temp_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })

            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

            print("✅ Firebase initialized from base64 environment variable!")
            return True
        except Exception as e:
            print(f"❌ Firebase init from base64 failed: {e}")
            print(f"Error details: {str(e)}")

    # Method 4: Individual environment variables (fallback)
    if os.getenv("FIREBASE_PROJECT_ID") and os.getenv("FIREBASE_PRIVATE_KEY"):
        try:
            print("🔄 Trying individual environment variables...")

            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
                "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL", "")
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(cred_dict, f)
                temp_path = f.name

            cred = credentials.Certificate(temp_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })

            try:
                os.unlink(temp_path)
            except:
                pass

            print("✅ Firebase initialized from individual env vars")
            return True
        except Exception as e:
            print(f"❌ Firebase init from env vars failed: {e}")

    print("❌ Could not initialize Firebase with any method!")
    return False

# Initialize Firebase
if not init_firebase():
    print("❌ Firebase initialization failed! Exiting...")
    print("⚠️ Please set one of the following in the Render Dashboard:")
    print("   1. Upload firebase.json as a Secret File")
    print("   2. Set the FIREBASE_CONFIG_BASE64 environment variable")
    print("   3. Or set individual FIREBASE_* variables")
    sys.exit(1)

print("✅ Firebase is ready!")

# ==========================================================
# 📊 Rate Limiter Class
# ==========================================================
class RateLimiter:
    def __init__(self):
        self.user_requests = {}

    def check_limit(self, user_id, limit_type='daily'):
        """Check user request limit"""
        now = datetime.now()
        user_key = f"{user_id}_{limit_type}"

        if user_key not in self.user_requests:
            self.user_requests[user_key] = []

        # Remove old entries
        self.user_requests[user_key] = [
            req_time for req_time in self.user_requests[user_key]
            if now - req_time < timedelta(hours=24 if limit_type == 'daily' else 1)
        ]

        limit = 5 if limit_type == 'daily' else 10
        return len(self.user_requests[user_key]) < limit

    def add_request(self, user_id, limit_type='daily'):
        """Add a request"""
        user_key = f"{user_id}_{limit_type}"
        if user_key not in self.user_requests:
            self.user_requests[user_key] = []
        self.user_requests[user_key].append(datetime.now())

rate_limiter = RateLimiter()

# ==========================================================
# 🎛 Menu Creation
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 Host Website", "📂 My Sites")
    markup.row("🌐 Add Domain", "🗑 Delete Site")
    markup.row("📊 Daily Limit", "👑 Admin")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 Total Users", "🌍 Total Sites")
    markup.row("🚫 Block User", "✅ Unblock User")
    markup.row("🔄 Reset Limit", "📢 Broadcast")
    markup.row("➕ Add Admin", "➖ Remove Admin")
    markup.row("📋 Admin List", "🚪 Logout")
    markup.row("⬅️ Main Menu")
    return markup

# ==========================================================
# ✅ Verification Check
# ==========================================================
def is_verified(user_id):
    """Check if user is in channel and group"""
    try:
        # Check blacklist
        blacklist_ref = db.reference(f'blacklist/{user_id}')
        if blacklist_ref.get():
            return False

        # Check channel membership
        ch = bot.get_chat_member(CHANNEL_ID, user_id)
        gp = bot.get_chat_member(GROUP_ID, user_id)
        return ch.status in ["member", "administrator", "creator"] and \
               gp.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Verification error for user {user_id}: {e}")
        return False

# ==========================================================
# 📊 Daily Limit Check
# ==========================================================
def check_daily_limit(user_id):
    """Check daily usage limit"""
    if not rate_limiter.check_limit(user_id, 'daily'):
        return False

    try:
        ref = db.reference(f'users/{user_id}')
        data = ref.get()
        today = datetime.now().strftime("%Y-%m-%d")

        if not data:
            ref.set({
                "date": today,
                "count": 0,
                "sites": {},
                "joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return True

        if data.get("date") != today:
            ref.update({"date": today, "count": 0})
            return True

        return data.get("count", 0) < 5
    except Exception as e:
        print(f"Check limit error: {e}")
        return False

def increase_count(user_id):
    """Increase user count"""
    try:
        ref = db.reference(f'users/{user_id}')
        data = ref.get()
        if data:
            ref.update({"count": data.get("count", 0) + 1})
        rate_limiter.add_request(user_id, 'daily')
    except Exception as e:
        print(f"Increase count error: {e}")

def get_user_count(user_id):
    """Get user's today's count"""
    try:
        ref = db.reference(f'users/{user_id}')
        data = ref.get()
        if not data:
            return 0

        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") == today:
            return data.get("count", 0)
        return 0
    except:
        return 0

# ==========================================================
# 🔐 Secure Zip Extract
# ==========================================================
def secure_extract_zip(zip_content, extract_path):
    """Safely extract zip file"""
    try:
        with zipfile.ZipFile(BytesIO(zip_content)) as zf:
            # Check for malicious files
            for file_info in zf.infolist():
                # Check path traversal
                if '..' in file_info.filename or file_info.filename.startswith('/'):
                    raise Exception(f"Invalid file path: {file_info.filename}")

                # Check file size (100MB limit)
                if file_info.file_size > 100 * 1024 * 1024:
                    raise Exception(f"File too large: {file_info.filename}")

            # Extract all
            zf.extractall(extract_path)

            # Check if index.html exists
            if not os.path.exists(os.path.join(extract_path, 'index.html')):
                # Try to find any HTML file
                html_files = []
                for root, dirs, files in os.walk(extract_path):
                    for file in files:
                        if file.endswith('.html'):
                            html_files.append(os.path.join(root, file))

                if html_files:
                    # Copy first HTML file as index.html
                    shutil.copy(html_files[0], os.path.join(extract_path, 'index.html'))
                else:
                    raise Exception("No HTML file found in zip!")

        return True
    except Exception as e:
        print(f"Extraction error: {e}")
        return False

# ==========================================================
# 🚀 /start Command
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.first_name

    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel"),
            InlineKeyboardButton("👥 Group", url="https://t.me/your_group")
        )
        bot.reply_to(
            message,
            "❌ Please join our channel and group first!\n\n"
            "After joining, send /start again.",
            reply_markup=markup
        )
        return

    welcome_text = (
        f"👋 Welcome {username}!\n\n"
        f"📌 You can host websites using this bot.\n"
        f"✅ You can host up to 5 sites per day.\n\n"
        f"📋 **How to use:**\n"
        f"1️⃣ Zip all your website files\n"
        f"2️⃣ Upload the zip file here\n"
        f"3️⃣ The bot will auto-deploy to GitHub & Vercel\n"
        f"4️⃣ You will receive a live link\n\n"
        f"⚠️ The zip file must contain an index.html"
    )

    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# ==========================================================
# 📦 Zip File Handler
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id

    # Verification check
    if not is_verified(user_id):
        bot.reply_to(message, "❌ Please join the channel and group first!")
        return

    # File type check
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only ZIP files are allowed!")
        return

    # Daily limit check
    if not check_daily_limit(user_id):
        used = get_user_count(user_id)
        bot.reply_to(message, f"❌ Today's limit reached! (You've used {used}/5)")
        return

    # Size check (50MB)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ Files larger than 50MB are not allowed!")
        return

    # Send status message
    status_msg = bot.reply_to(message, "⏳ Starting download...")

    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        bot.edit_message_text("📦 Extracting zip file...",
                            message.chat.id, status_msg.message_id)

        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract zip
            if not secure_extract_zip(downloaded, temp_dir):
                bot.edit_message_text("❌ Failed to extract zip file!",
                                    message.chat.id, status_msg.message_id)
                return

            # Generate unique repo name
            repo_name = f"site-{user_id}-{int(time.time())}"

            # Create GitHub repo
            bot.edit_message_text("🔧 Creating GitHub repository...",
                                message.chat.id, status_msg.message_id)

            if not create_github_repo(repo_name, temp_dir):
                bot.edit_message_text("❌ Failed to create GitHub repository!",
                                    message.chat.id, status_msg.message_id)
                return

            # Deploy to Vercel
            bot.edit_message_text("🚀 Deploying to Vercel...",
                                message.chat.id, status_msg.message_id)

            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                bot.edit_message_text("❌ Failed to deploy to Vercel!",
                                    message.chat.id, status_msg.message_id)
                return

            # Save to Firebase
            save_site_to_firebase(user_id, repo_name, live_url)

            # Increase count
            increase_count(user_id)

            # Success message
            used_now = get_user_count(user_id)
            success_text = (
                f"✅ **Successfully deployed!**\n\n"
                f"🌐 **Live URL:**\n`{live_url}`\n\n"
                f"📂 **GitHub:**\nhttps://github.com/{GITHUB_USERNAME}/{repo_name}\n\n"
                f"📊 **Used today:** {used_now}/5\n\n"
                f"💡 **Next steps:**\n"
                f"• Use '🌐 Add Domain' menu to add a custom domain\n"
                f"• Use '🗑 Delete Site' menu to delete a site"
            )

            bot.edit_message_text(success_text, message.chat.id, status_msg.message_id,
                                parse_mode="Markdown")

    except Exception as e:
        error_msg = str(e)[:200]
        bot.edit_message_text(f"❌ An error occurred: {error_msg}",
                            message.chat.id, status_msg.message_id)
        print(f"Error in handle_zip: {traceback.format_exc()}")

def create_github_repo(repo_name, local_path):
    """Create GitHub repository and upload files"""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Create repository
        r = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={
                "name": repo_name,
                "private": False,
                "auto_init": False,
                "description": f"Website hosted via Telegram Bot"
            }
        )

        if r.status_code != 201:
            print(f"GitHub repo creation failed: {r.status_code} - {r.text}")
            return False

        # Upload files
        for root, dirs, files in os.walk(local_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path)

                # Skip hidden files
                if file.startswith('.'):
                    continue

                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()

                # Upload file
                r = requests.put(
                    f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}",
                    headers=headers,
                    json={
                        "message": f"Add {rel_path}",
                        "content": content,
                        "branch": "main"
                    }
                )

                if r.status_code not in [200, 201]:
                    print(f"Failed to upload {rel_path}: {r.status_code}")
                    return False

        return True
    except Exception as e:
        print(f"GitHub error: {e}")
        return False

def deploy_to_vercel(repo_name):
    """Deploy to Vercel"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}

    try:
        # Create project
        project_data = {
            "name": repo_name,
            "gitRepository": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }

        r = requests.post(
            "https://api.vercel.com/v9/projects",
            headers=headers,
            json=project_data
        )

        if r.status_code not in [200, 201]:
            print(f"Vercel project creation failed: {r.status_code}")
            return None

        # Create deployment
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }

        r = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=deploy_data
        )

        if r.status_code not in [200, 201]:
            print(f"Vercel deployment failed: {r.status_code}")
            return None

        # Check deployment status
        deploy_id = r.json().get("id")
        max_attempts = 30
        attempts = 0

        while attempts < max_attempts:
            time.sleep(5)
            r = requests.get(
                f"https://api.vercel.com/v13/deployments/{deploy_id}",
                headers=headers
            )

            if r.status_code == 200:
                data = r.json()
                status = data.get("readyState")
                if status == "READY":
                    return f"https://{repo_name}.vercel.app"
                elif status in ["ERROR", "CANCELED"]:
                    print(f"Deployment failed with status: {status}")
                    return None

            attempts += 1

        return f"https://{repo_name}.vercel.app"
    except Exception as e:
        print(f"Vercel error: {e}")
        return None

def save_site_to_firebase(user_id, repo_name, live_url):
    """Save site info to Firebase"""
    try:
        ref = db.reference(f'users/{user_id}/sites/{repo_name}')
        ref.set({
            "name": repo_name,
            "url": live_url,
            "github": f"https://github.com/{GITHUB_USERNAME}/{repo_name}",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active"
        })
    except Exception as e:
        print(f"Firebase save error: {e}")

# ==========================================================
# 📂 My Sites
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 My Sites")
def my_sites(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ Not verified!")
        return

    try:
        sites = db.reference(f'users/{user_id}/sites').get()

        if not sites:
            bot.reply_to(message, "❌ You don't have any sites!")
            return

        text = "🌐 **Your Sites:**\n\n"
        for name, data in sites.items():
            text += f"📁 **{name}**\n"
            text += f"🔗 {data.get('url')}\n"
            text += f"📅 {data.get('created')}\n\n"

        # Pagination if too long
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# 🌐 Add Domain
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 Add Domain")
def add_domain_start(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ Not verified!")
        return

    try:
        sites = db.reference(f'users/{user_id}/sites').get()

        if not sites:
            bot.reply_to(message, "❌ You don't have any sites!")
            return

        # Create inline keyboard with sites
        markup = InlineKeyboardMarkup(row_width=1)
        for name in sites.keys():
            markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"domain_{name}"))

        bot.send_message(message.chat.id, "Select the site to add a domain to:",
                        reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('domain_'))
def domain_callback(call):
    project = call.data.replace('domain_', '')

    bot.edit_message_text(
        f"Enter your domain name (e.g.: example.com):",
        call.message.chat.id,
        call.message.message_id
    )

    # Register next step
    bot.register_next_step_handler(call.message, lambda m: add_domain_to_vercel(m, project))

def add_domain_to_vercel(message, project):
    domain = message.text.strip().lower()

    # Validate domain
    if not domain or '.' not in domain:
        bot.reply_to(message, "❌ Please enter a valid domain!")
        return

    try:
        headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}

        # Add domain to Vercel
        r = requests.post(
            f"https://api.vercel.com/v9/projects/{project}/domains",
            headers=headers,
            json={"name": domain}
        )

        if r.status_code in [200, 201]:
            dns_text = (
                f"✅ **Domain added successfully!**\n\n"
                f"📌 **DNS Settings:**\n"
                f"```\n"
                f"Type: CNAME\n"
                f"Name: @\n"
                f"Value: cname.vercel-dns.com\n"
                f"```\n\n"
                f"⚠️ DNS propagation may take 24-48 hours."
            )
            bot.reply_to(message, dns_text, parse_mode="Markdown")
        else:
            error_msg = r.json().get('error', {}).get('message', 'Unknown error')
            bot.reply_to(message, f"❌ Failed to add domain: {error_msg}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# 🗑 Delete Site
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 Delete Site")
def delete_site_start(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ Not verified!")
        return

    try:
        sites = db.reference(f'users/{user_id}/sites').get()

        if not sites:
            bot.reply_to(message, "❌ You don't have any sites!")
            return

        # Create inline keyboard with sites
        markup = InlineKeyboardMarkup(row_width=1)
        for name in sites.keys():
            markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"delete_{name}"))

        bot.send_message(message.chat.id, "Select the site to delete:",
                        reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_callback(call):
    project = call.data.replace('delete_', '')
    user_id = call.from_user.id

    # Confirmation
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{project}"),
        InlineKeyboardButton("❌ No", callback_data="cancel_delete")
    )

    bot.edit_message_text(
        f"Do you want to delete **{project}**?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def confirm_delete(call):
    project = call.data.replace('confirm_', '')
    user_id = call.from_user.id

    bot.edit_message_text(
        f"🔄 Deleting {project}...",
        call.message.chat.id,
        call.message.message_id
    )

    try:
        # Delete from Vercel
        headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
        requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers)

        # Delete from GitHub
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        requests.delete(f"https://api.github.com/repos/{GITHUB_USERNAME}/{project}", headers=headers)

        # Delete from Firebase
        db.reference(f'users/{user_id}/sites/{project}').delete()

        bot.edit_message_text(
            f"✅ **{project}** has been deleted successfully!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Failed to delete: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete(call):
    bot.edit_message_text(
        "✅ Deletion cancelled!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📊 Daily Limit
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 Daily Limit")
def show_limit(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ Not verified!")
        return

    used = get_user_count(user_id)
    remaining = 5 - used

    # Create progress bar
    bar = "🟩" * used + "⬜" * remaining

    text = (
        f"📊 **Your Daily Usage:**\n\n"
        f"{bar}\n"
        f"**Used:** {used}/5\n"
        f"**Remaining:** {remaining}\n\n"
        f"🕒 Resets at: Midnight tonight"
    )

    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 Admin Panel (Multi-Admin Support)
# ==========================================================
admin_sessions = {}

def is_super_admin(user_id):
    """Check if user is the super admin (from env variable)"""
    return int(user_id) == ADMIN_ID

def is_admin(user_id):
    """Check if user is any admin (super admin or added admin)"""
    # Check super admin first
    if is_super_admin(user_id):
        return True
    # Check Firebase admin list
    try:
        admin_ref = db.reference(f'admins/{user_id}')
        admin_data = admin_ref.get()
        return admin_data is not None
    except Exception as e:
        print(f"Admin check error: {e}")
        return False

def is_admin_logged_in(user_id):
    """Check if admin is logged in"""
    return admin_sessions.get(user_id, False)

@bot.message_handler(func=lambda m: m.text == "👑 Admin")
def admin_panel(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "❌ Not verified!")
        return

    if not is_admin(user_id):
        bot.reply_to(message, "❌ You don't have admin access!")
        return

    if is_admin_logged_in(user_id):
        bot.send_message(message.chat.id, "👑 **Admin Panel**",
                        parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **Enter admin password:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ **Login successful!**",
                        parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **Wrong password!**",
                    parse_mode="Markdown", reply_markup=main_menu())

# 📊 Total Users
@bot.message_handler(func=lambda m: m.text == "📊 Total Users")
def total_users(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    try:
        users = db.reference("users").get()
        count = len(users) if users else 0

        # Count active users
        active = 0
        if users:
            for uid in users.keys():
                try:
                    bot.get_chat_member(CHANNEL_ID, int(uid))
                    active += 1
                except:
                    pass

        text = (
            f"📊 **User Statistics:**\n\n"
            f"Total Users: **{count}**\n"
            f"Active: **{active}**\n"
            f"Inactive: **{count - active}**"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# 🌍 Total Sites
@bot.message_handler(func=lambda m: m.text == "🌍 Total Sites")
def total_sites(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    try:
        users = db.reference("users").get()
        total = 0
        if users:
            for data in users.values():
                total += len(data.get("sites", {}))

        bot.reply_to(message, f"🌐 **Total Sites:** {total}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# 🚫 Block User
@bot.message_handler(func=lambda m: m.text == "🚫 Block User")
def ban_user_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    bot.reply_to(message, "Enter the **User ID** to block:", parse_mode="Markdown")
    bot.register_next_step_handler(message, ban_user)

def ban_user(message):
    try:
        uid = message.text.strip()
        # Validate numeric ID
        if not uid.isdigit():
            bot.reply_to(message, "❌ Invalid User ID! Please enter a numeric ID.")
            return
        db.reference(f'blacklist/{uid}').set(True)
        bot.reply_to(message, f"✅ User **{uid}** has been blocked!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ✅ Unblock User
@bot.message_handler(func=lambda m: m.text == "✅ Unblock User")
def unban_user_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    bot.reply_to(message, "Enter the **User ID** to unblock:", parse_mode="Markdown")
    bot.register_next_step_handler(message, unban_user)

def unban_user(message):
    try:
        uid = message.text.strip()
        # Validate numeric ID
        if not uid.isdigit():
            bot.reply_to(message, "❌ Invalid User ID! Please enter a numeric ID.")
            return
        db.reference(f'blacklist/{uid}').delete()
        bot.reply_to(message, f"✅ User **{uid}** has been unblocked!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# 🔄 Reset Limit
@bot.message_handler(func=lambda m: m.text == "🔄 Reset Limit")
def reset_limit_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    bot.reply_to(message, "Enter the **User ID** to reset limit:", parse_mode="Markdown")
    bot.register_next_step_handler(message, reset_limit)

def reset_limit(message):
    try:
        uid = message.text.strip()
        # Validate numeric ID
        if not uid.isdigit():
            bot.reply_to(message, "❌ Invalid User ID! Please enter a numeric ID.")
            return

        # Check if user exists
        user_data = db.reference(f'users/{uid}').get()
        if not user_data:
            bot.reply_to(message, f"❌ User **{uid}** not found in database!", parse_mode="Markdown")
            return

        db.reference(f'users/{uid}/count').set(0)
        db.reference(f'users/{uid}/date').set(datetime.now().strftime("%Y-%m-%d"))
        bot.reply_to(message, f"✅ Limit for user **{uid}** has been reset!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# 📢 Broadcast
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def broadcast_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return

    bot.reply_to(message, "What message do you want to send to all users?\n\n(Send /cancel to cancel)")
    bot.register_next_step_handler(message, broadcast_send)

def broadcast_send(message):
    # Check if message has text
    if not message.text:
        bot.reply_to(message, "❌ Please send a text message only!")
        return

    # Allow cancellation
    if message.text.strip() == "/cancel":
        bot.reply_to(message, "✅ Broadcast cancelled!", reply_markup=admin_menu())
        return

    text = message.text

    try:
        users = db.reference("users").get()

        if not users:
            bot.reply_to(message, "❌ No users found!")
            return

        status_msg = bot.reply_to(message, "📨 Sending messages...")

        sent = 0
        failed = 0

        for uid in users.keys():
            try:
                bot.send_message(int(uid), f"📢 **Admin Message:**\n\n{text}",
                               parse_mode="Markdown")
                sent += 1
                time.sleep(0.05)  # Rate limit avoid
            except:
                failed += 1

        bot.edit_message_text(
            f"✅ **Broadcast complete!**\n\n"
            f"Sent: **{sent}**\n"
            f"Failed: **{failed}**",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# ➕ Add Admin (Super Admin Only)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "➕ Add Admin")
def add_admin_start(message):
    user_id = message.from_user.id

    if not is_admin_logged_in(user_id):
        return

    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only the Super Admin can add new admins!")
        return

    bot.reply_to(message, "Enter the **User ID** of the new admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, add_admin_process)

def add_admin_process(message):
    try:
        uid = message.text.strip()

        # Validate numeric ID
        if not uid.isdigit():
            bot.reply_to(message, "❌ Invalid User ID! Please enter a numeric ID.")
            return

        # Check if already super admin
        if int(uid) == ADMIN_ID:
            bot.reply_to(message, "⚠️ This user is already the Super Admin!")
            return

        # Check if already an admin
        existing = db.reference(f'admins/{uid}').get()
        if existing:
            bot.reply_to(message, f"⚠️ User **{uid}** is already an admin!", parse_mode="Markdown")
            return

        # Add to Firebase admins list
        db.reference(f'admins/{uid}').set({
            "added_by": message.from_user.id,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": int(uid)
        })

        bot.reply_to(message, f"✅ User **{uid}** has been added as admin!", parse_mode="Markdown")

        # Try to notify the new admin
        try:
            bot.send_message(int(uid), "🎉 You have been granted **Admin** access!\n\nUse the 👑 Admin button to access the admin panel.", parse_mode="Markdown")
        except:
            pass  # User may not have started the bot

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# ➖ Remove Admin (Super Admin Only)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "➖ Remove Admin")
def remove_admin_start(message):
    user_id = message.from_user.id

    if not is_admin_logged_in(user_id):
        return

    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only the Super Admin can remove admins!")
        return

    try:
        admins = db.reference('admins').get()

        if not admins:
            bot.reply_to(message, "❌ No additional admins found!")
            return

        # Create inline keyboard with admin list
        markup = InlineKeyboardMarkup(row_width=1)
        for uid, data in admins.items():
            added_at = data.get('added_at', 'Unknown')
            markup.add(InlineKeyboardButton(
                f"🗑 Admin {uid} (added: {added_at})",
                callback_data=f"rmadmin_{uid}"
            ))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_rmadmin"))

        bot.send_message(message.chat.id, "Select the admin to remove:", reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rmadmin_'))
def remove_admin_callback(call):
    # Only super admin can do this
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Only Super Admin can do this!")
        return

    uid = call.data.replace('rmadmin_', '')

    try:
        # Remove from Firebase
        db.reference(f'admins/{uid}').delete()

        # Remove admin session if active
        if int(uid) in admin_sessions:
            del admin_sessions[int(uid)]

        bot.edit_message_text(
            f"✅ Admin **{uid}** has been removed!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )

        # Try to notify the removed admin
        try:
            bot.send_message(int(uid), "⚠️ Your **Admin** access has been revoked.", parse_mode="Markdown")
        except:
            pass

    except Exception as e:
        bot.edit_message_text(
            f"❌ Error removing admin: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_rmadmin")
def cancel_remove_admin(call):
    bot.edit_message_text(
        "✅ Admin removal cancelled!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📋 Admin List
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📋 Admin List")
def admin_list(message):
    user_id = message.from_user.id

    if not is_admin_logged_in(user_id):
        return

    try:
        text = "👑 **Admin List:**\n\n"
        text += f"⭐ **Super Admin:** `{ADMIN_ID}`\n\n"

        admins = db.reference('admins').get()
        if admins:
            text += "📋 **Other Admins:**\n"
            for uid, data in admins.items():
                added_at = data.get('added_at', 'Unknown')
                text += f"• `{uid}` (added: {added_at})\n"
        else:
            text += "📋 No additional admins added yet."

        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# 🚪 Admin Logout
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🚪 Logout")
def admin_logout(message):
    user_id = message.from_user.id

    if user_id in admin_sessions:
        del admin_sessions[user_id]

    bot.send_message(message.chat.id, "✅ Logged out from admin panel!",
                    reply_markup=main_menu())

# ⬅️ Main Menu
@bot.message_handler(func=lambda m: m.text == "⬅️ Main Menu")
def back_to_main(message):
    bot.send_message(message.chat.id, "Back to the main menu!", reply_markup=main_menu())

# ==========================================================
# 🔄 Fallback handler
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "❌ Please select an option from the menu!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP Server (Port listener for Render)
# ==========================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h1>Telegram Bot is Running!</h1>")

    def log_message(self, format, *args):
        # Suppress log messages
        pass

def run_http_server():
    port = int(os.getenv("PORT", 10000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"🌐 HTTP Server running on port {port}")
    httpd.serve_forever()

# ==========================================================
# 🏁 Start Bot
# ==========================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🔥 Telegram Hosting Bot is starting...")
    print("=" * 60)

    # Start HTTP server in a separate thread (for Render port binding)
    threading.Thread(target=run_http_server, daemon=True).start()
    print("✅ HTTP Server thread started")

    try:
        bot_info = bot.get_me()
        print(f"✅ Bot username: @{bot_info.username}")
        print(f"✅ Bot name: {bot_info.first_name}")
        print("=" * 60)
        print("🟢 Bot is running... (Press Ctrl+C to stop)")
        print("=" * 60)

        # Start bot
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n👋 Shutting down the bot...")
    except Exception as e:
        print(f"❌ Bot error: {e}")
        traceback.print_exc()
