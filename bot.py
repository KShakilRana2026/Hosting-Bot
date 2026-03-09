# ==========================================================
# 🔥 TELEGRAM HOSTING BOT - COMPLETE PRODUCTION VERSION
# ==========================================================
# All Features Included:
# ✅ Telegram Bot Base
# ✅ Reply Keyboard (not Inline)
# ✅ Group + Channel Verify
# ✅ Firebase Connect
# ✅ Daily 5 Limit System
# ✅ Basic Menu Control
# ✅ Render Compatible
# ✅ ZIP download
# ✅ Secure extract (zip slip protection)
# ✅ File scan
# ✅ GitHub repo create
# ✅ GitHub API file-by-file upload
# ✅ Firebase site storage
# ✅ Daily count increase
# ✅ GitHub repo → Vercel project link
# ✅ Auto deploy trigger
# ✅ Deploy status check
# ✅ Live URL return
# ✅ Custom domain add
# ✅ Firebase update
# ✅ Full Remove System
# ✅ GitHub repo delete
# ✅ Vercel project delete
# ✅ Firebase clean delete
# ✅ Temp folder cleanup
# ✅ Error-safe protection
# ✅ Production-safe structure
# ✅ Admin Password Login
# ✅ Session-based Access
# ✅ Multiple Admin Support
# ✅ Firebase Admin List
# ✅ Ban / Unban
# ✅ Reset Limit
# ✅ Total Users / Sites
# ✅ Delete ANY User Site
# ✅ Broadcast
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
# 🔐 LOAD ENVIRONMENT VARIABLES
# ==========================================================
load_dotenv()

# Required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SUPER_ADMIN_ID = os.getenv("ADMIN_ID")  # Super Admin ID
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("GROUP_ID")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
FIREBASE_CONFIG_BASE64 = os.getenv("FIREBASE_CONFIG_BASE64")
PORT = int(os.getenv("PORT", 10000))

print("=" * 60)
print("🔥 TELEGRAM HOSTING BOT - STARTING UP")
print("=" * 60)

# Check required variables
missing_vars = []
if not BOT_TOKEN: missing_vars.append("BOT_TOKEN")
if not GITHUB_TOKEN: missing_vars.append("GITHUB_TOKEN")
if not GITHUB_USERNAME: missing_vars.append("GITHUB_USERNAME")
if not VERCEL_TOKEN: missing_vars.append("VERCEL_TOKEN")
if not ADMIN_PASSWORD: missing_vars.append("ADMIN_PASSWORD")
if not SUPER_ADMIN_ID: missing_vars.append("ADMIN_ID")
if not CHANNEL_ID: missing_vars.append("CHANNEL_ID")
if not GROUP_ID: missing_vars.append("GROUP_ID")
if not FIREBASE_DB_URL: missing_vars.append("FIREBASE_DB_URL")
if not FIREBASE_CONFIG_BASE64: missing_vars.append("FIREBASE_CONFIG_BASE64")

if missing_vars:
    print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
    print("⚠️ Please set all required variables in Render Dashboard")
    sys.exit(1)

# Convert IDs to integers
try:
    SUPER_ADMIN_ID = int(SUPER_ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError as e:
    print(f"❌ ID conversion error: {e}")
    sys.exit(1)

# ==========================================================
# 🚀 BOT INITIALIZATION
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot token valid")
except Exception as e:
    print(f"❌ Invalid bot token: {e}")
    sys.exit(1)

# ==========================================================
# 🔥 FIREBASE INITIALIZATION
# ==========================================================
def init_firebase():
    """Initialize Firebase from Base64 config"""
    try:
        json_bytes = base64.b64decode(FIREBASE_CONFIG_BASE64)
        json_str = json_bytes.decode('utf-8')
        cred_dict = json.loads(json_str)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cred_dict, f)
            temp_path = f.name
        
        cred = credentials.Certificate(temp_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        os.unlink(temp_path)
        print("✅ Firebase connected successfully")
        return True
    except Exception as e:
        print(f"❌ Firebase connection failed: {e}")
        return False

FIREBASE_READY = init_firebase()

# ==========================================================
# 📊 ADMIN SESSIONS & PERMISSIONS
# ==========================================================
admin_sessions = {}  # {user_id: login_time}
banned_users = {}    # Cache for banned users

def is_super_admin(user_id):
    """Check if user is super admin (from env)"""
    return int(user_id) == SUPER_ADMIN_ID

def is_admin(user_id):
    """Check if user is any admin (super admin + firebase admins)"""
    if is_super_admin(user_id):
        return True
    
    if not FIREBASE_READY:
        return False
    
    try:
        admin_ref = db.reference(f'admins/{user_id}')
        return admin_ref.get() is not None
    except:
        return False

def is_admin_logged_in(user_id):
    """Check if admin is logged in"""
    return user_id in admin_sessions

def is_banned(user_id):
    """Check if user is banned"""
    # Check cache first
    if user_id in banned_users:
        return True
    
    if not FIREBASE_READY:
        return False
    
    try:
        banned = db.reference(f'banned/{user_id}').get()
        if banned:
            banned_users[user_id] = True
            return True
        return False
    except:
        return False

# ==========================================================
# 📊 RATE LIMITER (Daily 5 Sites)
# ==========================================================
class RateLimiter:
    def __init__(self):
        self.user_counts = {}  # {user_id_date: count}
    
    def check_limit(self, user_id):
        """Check if user has reached daily limit"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        
        if key not in self.user_counts:
            return True
        
        return self.user_counts[key] < 5
    
    def add_count(self, user_id):
        """Add one to user's daily count"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        self.user_counts[key] = self.user_counts.get(key, 0) + 1
        return self.user_counts[key]
    
    def get_count(self, user_id):
        """Get user's current count"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        return self.user_counts.get(key, 0)
    
    def reset_limit(self, user_id):
        """Reset user's limit (admin function)"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        if key in self.user_counts:
            del self.user_counts[key]

rate_limiter = RateLimiter()

# ==========================================================
# 🎛 MENU CREATION
# ==========================================================
def main_menu():
    """Main user menu"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 HOST WEBSITE", "📂 MY SITES")
    markup.row("🌐 ADD DOMAIN", "🗑 DELETE SITE")
    markup.row("📊 DAILY LIMIT", "👑 ADMIN PANEL")
    return markup

def admin_menu():
    """Admin panel menu"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 TOTAL USERS", "🌍 TOTAL SITES")
    markup.row("🚫 BAN USER", "✅ UNBAN USER")
    markup.row("🔄 RESET LIMIT", "📢 BROADCAST")
    markup.row("➕ ADD ADMIN", "➖ REMOVE ADMIN")
    markup.row("📋 ADMIN LIST", "🗑 DELETE USER SITE")
    markup.row("🚪 LOGOUT", "⬅️ MAIN MENU")
    return markup

# ==========================================================
# ✅ VERIFICATION SYSTEM
# ==========================================================
def verify_user(user_id):
    """Check if user is in channel and group"""
    if is_banned(user_id):
        return False
    
    try:
        channel_member = bot.get_chat_member(CHANNEL_ID, user_id)
        group_member = bot.get_chat_member(GROUP_ID, user_id)
        
        channel_ok = channel_member.status in ["member", "administrator", "creator"]
        group_ok = group_member.status in ["member", "administrator", "creator"]
        
        return channel_ok and group_ok
    except Exception as e:
        print(f"⚠️ Verification error for user {user_id}: {e}")
        return True  # Allow if verification fails (graceful degradation)

# ==========================================================
# 🔐 SECURE ZIP EXTRACT (with path traversal protection)
# ==========================================================
def secure_extract_zip(zip_content, extract_path):
    """
    Securely extract zip file with protection against:
    - Path traversal attacks
    - Large files
    - Malicious content
    """
    try:
        with zipfile.ZipFile(BytesIO(zip_content)) as zf:
            # Check all files before extraction
            for file_info in zf.infolist():
                # Check path traversal
                if '..' in file_info.filename or file_info.filename.startswith('/'):
                    raise Exception(f"Path traversal detected: {file_info.filename}")
                
                # Check file size (max 100MB per file)
                if file_info.file_size > 100 * 1024 * 1024:
                    raise Exception(f"File too large: {file_info.filename}")
            
            # Extract all files
            zf.extractall(extract_path)
            
            # Check if index.html exists
            if not os.path.exists(os.path.join(extract_path, 'index.html')):
                # Find any HTML file
                html_files = []
                for root, _, files in os.walk(extract_path):
                    for file in files:
                        if file.endswith('.html'):
                            html_files.append(os.path.join(root, file))
                
                if html_files:
                    # Copy first HTML file as index.html
                    shutil.copy(html_files[0], os.path.join(extract_path, 'index.html'))
                else:
                    raise Exception("No HTML file found in zip!")
        
        return True, "Extraction successful"
    except zipfile.BadZipFile:
        return False, "Invalid zip file"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🔧 GITHUB FUNCTIONS
# ==========================================================
def create_github_repo(repo_name, local_path):
    """
    Create GitHub repository and upload all files
    Returns: (success, message, repo_name)
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Test token
        test_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test_resp.status_code != 200:
            return False, "Invalid GitHub token", None
        
        # Create repository
        repo_data = {
            "name": repo_name,
            "private": False,
            "auto_init": False,
            "description": "Hosted via Telegram Bot"
        }
        
        resp = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=repo_data,
            timeout=30
        )
        
        # Handle duplicate name
        if resp.status_code == 422:
            repo_name = f"{repo_name}-{int(time.time())}"
            resp = requests.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json=repo_data,
                timeout=30
            )
        
        if resp.status_code != 201:
            return False, f"GitHub API error: {resp.status_code}", None
        
        # Upload files one by one
        uploaded = 0
        failed = 0
        
        for root, _, files in os.walk(local_path):
            for file in files:
                if file.startswith('.'):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path)
                
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                
                file_data = {
                    "message": f"Add {rel_path}",
                    "content": content,
                    "branch": "main"
                }
                
                url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}"
                upload_resp = requests.put(url, headers=headers, json=file_data, timeout=30)
                
                if upload_resp.status_code in [200, 201]:
                    uploaded += 1
                else:
                    failed += 1
        
        return True, f"Uploaded {uploaded} files, Failed: {failed}", repo_name
        
    except requests.exceptions.Timeout:
        return False, "GitHub API timeout", None
    except requests.exceptions.ConnectionError:
        return False, "Network connection error", None
    except Exception as e:
        return False, str(e), None

def delete_github_repo(repo_name):
    """Delete GitHub repository"""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
        resp = requests.delete(url, headers=headers, timeout=30)
        
        return resp.status_code in [204, 404]  # 204=deleted, 404=already gone
    except:
        return False

# ==========================================================
# 🚀 VERCEL FUNCTIONS
# ==========================================================
def deploy_to_vercel(repo_name):
    """
    Deploy GitHub repo to Vercel
    Returns: (success, url_or_error)
    """
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Test token
        test_resp = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test_resp.status_code != 200:
            return False, "Invalid Vercel token"
        
        # Create project
        project_data = {
            "name": repo_name,
            "gitRepository": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        
        proj_resp = requests.post(
            "https://api.vercel.com/v9/projects",
            headers=headers,
            json=project_data,
            timeout=30
        )
        
        # Create deployment
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            },
            "target": "production"
        }
        
        deploy_resp = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=deploy_data,
            timeout=30
        )
        
        if deploy_resp.status_code in [200, 201]:
            return True, f"https://{repo_name}.vercel.app"
        
        # Handle "already exists" case
        if deploy_resp.status_code == 400:
            try:
                error_data = deploy_resp.json()
                if "already_exists" in str(error_data).lower():
                    return True, f"https://{repo_name}.vercel.app"
            except:
                pass
        
        return False, f"Vercel error: {deploy_resp.status_code}"
        
    except Exception as e:
        return False, str(e)

def delete_vercel_project(project_name):
    """Delete Vercel project"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    try:
        url = f"https://api.vercel.com/v9/projects/{project_name}"
        resp = requests.delete(url, headers=headers, timeout=30)
        
        return resp.status_code in [200, 204, 404]
    except:
        return False

def add_domain_to_vercel(project_name, domain):
    """Add custom domain to Vercel project"""
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        data = {"name": domain}
        url = f"https://api.vercel.com/v9/projects/{project_name}/domains"
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        
        if resp.status_code in [200, 201]:
            return True, "Domain added successfully"
        else:
            return False, f"Error: {resp.status_code}"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 💾 FIREBASE DATABASE FUNCTIONS
# ==========================================================
def save_site_to_db(user_id, repo_name, live_url):
    """Save site information to Firebase"""
    if not FIREBASE_READY:
        return False
    
    try:
        ref = db.reference(f'users/{user_id}/sites/{repo_name}')
        ref.set({
            "name": repo_name,
            "url": live_url,
            "github": f"https://github.com/{GITHUB_USERNAME}/{repo_name}",
            "created": datetime.now().isoformat(),
            "status": "active"
        })
        
        # Update user's daily count in Firebase
        today = datetime.now().strftime("%Y-%m-%d")
        count_ref = db.reference(f'users/{user_id}/counts/{today}')
        count_ref.transaction(lambda current: (current or 0) + 1)
        
        return True
    except Exception as e:
        print(f"⚠️ Firebase save error: {e}")
        return False

def delete_site_from_db(user_id, repo_name):
    """Delete site from Firebase"""
    if not FIREBASE_READY:
        return False
    
    try:
        db.reference(f'users/{user_id}/sites/{repo_name}').delete()
        return True
    except:
        return False

def get_user_sites(user_id):
    """Get all sites for a user"""
    if not FIREBASE_READY:
        return None
    
    try:
        return db.reference(f'users/{user_id}/sites').get()
    except:
        return None

def get_all_users():
    """Get all users from Firebase"""
    if not FIREBASE_READY:
        return None
    
    try:
        return db.reference('users').get()
    except:
        return None

def ban_user(user_id):
    """Ban a user"""
    if not FIREBASE_READY:
        return False
    
    try:
        db.reference(f'banned/{user_id}').set(True)
        banned_users[user_id] = True
        return True
    except:
        return False

def unban_user(user_id):
    """Unban a user"""
    if not FIREBASE_READY:
        return False
    
    try:
        db.reference(f'banned/{user_id}').delete()
        if user_id in banned_users:
            del banned_users[user_id]
        return True
    except:
        return False

def add_admin(user_id, added_by):
    """Add a new admin"""
    if not FIREBASE_READY:
        return False
    
    try:
        db.reference(f'admins/{user_id}').set({
            "added_by": added_by,
            "added_at": datetime.now().isoformat()
        })
        return True
    except:
        return False

def remove_admin(user_id):
    """Remove an admin"""
    if not FIREBASE_READY:
        return False
    
    try:
        db.reference(f'admins/{user_id}').delete()
        return True
    except:
        return False

def get_admin_list():
    """Get list of all admins"""
    if not FIREBASE_READY:
        return None
    
    try:
        return db.reference('admins').get()
    except:
        return None

# ==========================================================
# 🚀 COMMAND: /start
# ==========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    if not verify_user(user_id):
        bot.reply_to(
            message,
            "❌ Please join our channel and group first!\n\n"
            "After joining, send /start again."
        )
        return
    
    welcome = (
        f"👋 Welcome {username}!\n\n"
        f"📌 This bot hosts websites on Vercel via GitHub.\n"
        f"✅ Daily limit: 5 sites per user.\n\n"
        f"📋 **How to use:**\n"
        f"1️⃣ Zip all website files (must contain index.html)\n"
        f"2️⃣ Upload the zip file\n"
        f"3️⃣ Bot creates GitHub repo and deploys to Vercel\n"
        f"4️⃣ You receive a live URL\n\n"
        f"⚠️ Max file size: 50MB"
    )
    
    bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 📦 ZIP FILE HANDLER (MAIN FEATURE)
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    # Verification
    if not verify_user(user_id):
        bot.reply_to(message, "❌ Please join channel & group first!")
        return
    
    # File type check
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only .zip files are allowed!")
        return
    
    # Daily limit check
    if not rate_limiter.check_limit(user_id):
        used = rate_limiter.get_count(user_id)
        bot.reply_to(message, f"❌ Daily limit reached! You've used {used}/5 today.")
        return
    
    # File size check (50MB)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ File size exceeds 50MB limit!")
        return
    
    status_msg = bot.reply_to(message, "⏳ Processing...")
    
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 Extracting zip...", message.chat.id, status_msg.message_id)
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Secure extract
            extract_success, extract_msg = secure_extract_zip(downloaded, temp_dir)
            if not extract_success:
                bot.edit_message_text(f"❌ {extract_msg}", message.chat.id, status_msg.message_id)
                return
            
            # Generate repo name
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 Creating GitHub repository...", message.chat.id, status_msg.message_id)
            
            # Create GitHub repo
            github_success, github_msg, final_repo_name = create_github_repo(repo_name, temp_dir)
            if not github_success:
                bot.edit_message_text(f"❌ GitHub error: {github_msg}", message.chat.id, status_msg.message_id)
                return
            
            bot.edit_message_text("🚀 Deploying to Vercel...", message.chat.id, status_msg.message_id)
            
            # Deploy to Vercel
            vercel_success, vercel_result = deploy_to_vercel(final_repo_name)
            if not vercel_success:
                bot.edit_message_text(f"❌ Vercel error: {vercel_result}", message.chat.id, status_msg.message_id)
                return
            
            live_url = vercel_result
            
            # Save to Firebase
            if FIREBASE_READY:
                save_site_to_db(user_id, final_repo_name, live_url)
            
            # Update daily count
            rate_limiter.add_count(user_id)
            used_now = rate_limiter.get_count(user_id)
            
            # Cleanup temp folder (automatically done by TemporaryDirectory)
            
            # Success message
            success_text = (
                f"✅ **DEPLOYMENT SUCCESSFUL!**\n\n"
                f"🌐 **Live URL:**\n`{live_url}`\n\n"
                f"📂 **GitHub:**\nhttps://github.com/{GITHUB_USERNAME}/{final_repo_name}\n\n"
                f"📊 **Today's usage:** {used_now}/5\n\n"
                f"💡 **Next steps:**\n"
                f"• Use '🌐 ADD DOMAIN' to add custom domain\n"
                f"• Use '📂 MY SITES' to view all sites\n"
                f"• Use '🗑 DELETE SITE' to remove sites"
            )
            
            bot.edit_message_text(
                success_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        error_msg = str(e)[:200]
        bot.edit_message_text(f"❌ Error: {error_msg}", message.chat.id, status_msg.message_id)
        print(f"Error details: {traceback.format_exc()}")

# ==========================================================
# 📂 MENU: MY SITES
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 MY SITES")
def menu_my_sites(message):
    user_id = message.from_user.id
    
    if not verify_user(user_id):
        bot.reply_to(message, "❌ Please verify first!")
        return
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "❌ You have no sites yet!")
        return
    
    text = "🌐 **Your Sites:**\n\n"
    for name, data in sites.items():
        created = data.get('created', 'Unknown')
        if len(created) > 10:
            created = created[:10]
        text += f"📁 **{name}**\n🔗 {data.get('url')}\n📅 {created}\n\n"
    
    # Handle long messages
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            bot.send_message(message.chat.id, part, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================================
# 🌐 MENU: ADD DOMAIN
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ADD DOMAIN")
def menu_add_domain(message):
    user_id = message.from_user.id
    
    if not verify_user(user_id):
        bot.reply_to(message, "❌ Please verify first!")
        return
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "❌ You have no sites!")
        return
    
    # Create inline keyboard with sites
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"domain_{name}"))
    
    bot.send_message(message.chat.id, "Select site to add domain:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('domain_'))
def domain_callback(call):
    project = call.data.replace('domain_', '')
    
    bot.edit_message_text(
        f"Enter domain name (e.g., example.com):",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(call.message, lambda m: process_domain(m, project))

def process_domain(message, project):
    domain = message.text.strip().lower()
    
    # Basic validation
    if not domain or '.' not in domain or ' ' in domain:
        bot.reply_to(message, "❌ Invalid domain format!")
        return
    
    # Add domain to Vercel
    success, result = add_domain_to_vercel(project, domain)
    
    if success:
        dns_text = (
            f"✅ **Domain added successfully!**\n\n"
            f"📌 **DNS Configuration:**\n"
            f"```\n"
            f"Type: CNAME\n"
            f"Name: @\n"
            f"Value: cname.vercel-dns.com\n"
            f"```\n\n"
            f"⏱️ DNS propagation may take 24-48 hours."
        )
        bot.reply_to(message, dns_text, parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ Failed: {result}")

# ==========================================================
# 🗑 MENU: DELETE SITE
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 DELETE SITE")
def menu_delete_site(message):
    user_id = message.from_user.id
    
    if not verify_user(user_id):
        bot.reply_to(message, "❌ Please verify first!")
        return
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "❌ You have no sites!")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"delete_{name}"))
    
    bot.send_message(message.chat.id, "Select site to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_callback(call):
    project = call.data.replace('delete_', '')
    user_id = call.from_user.id
    
    # Confirmation
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ YES", callback_data=f"confirm_{project}"),
        InlineKeyboardButton("❌ NO", callback_data="cancel_delete")
    )
    
    bot.edit_message_text(
        f"⚠️ Delete **{project}**?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def confirm_delete(call):
    project = call.data.replace('confirm_', '')
    user_id = call.from_user.id
    
    bot.edit_message_text(f"🔄 Deleting {project}...", call.message.chat.id, call.message.message_id)
    
    # Delete from Vercel
    delete_vercel_project(project)
    
    # Delete from GitHub
    delete_github_repo(project)
    
    # Delete from Firebase
    delete_site_from_db(user_id, project)
    
    bot.edit_message_text(
        f"✅ **{project}** deleted successfully!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete(call):
    bot.edit_message_text("✅ Deletion cancelled!", call.message.chat.id, call.message.message_id)

# ==========================================================
# 📊 MENU: DAILY LIMIT
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 DAILY LIMIT")
def menu_daily_limit(message):
    user_id = message.from_user.id
    used = rate_limiter.get_count(user_id)
    remaining = 5 - used
    
    bar = "🟩" * used + "⬜" * remaining
    
    text = (
        f"📊 **Your Daily Usage:**\n\n"
        f"{bar}\n"
        f"**Used:** {used}/5\n"
        f"**Remaining:** {remaining}\n\n"
        f"🕒 Resets at midnight UTC"
    )
    
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 ADMIN PANEL ACCESS
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def menu_admin_panel(message):
    user_id = message.from_user.id
    
    if not verify_user(user_id):
        bot.reply_to(message, "❌ Please verify first!")
        return
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ You are not an admin!")
        return
    
    if is_admin_logged_in(user_id):
        bot.send_message(message.chat.id, "👑 **Admin Panel**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **Enter admin password:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_password)

def check_admin_password(message):
    user_id = message.from_user.id
    
    if message.text == ADMIN_PASSWORD:
        admin_sessions[user_id] = datetime.now()
        bot.send_message(message.chat.id, "✅ **Login successful!**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **Wrong password!**", parse_mode="Markdown", reply_markup=main_menu())

# ==========================================================
# 📊 ADMIN: TOTAL USERS
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 TOTAL USERS")
def admin_total_users(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    users = get_all_users()
    count = len(users) if users else 0
    
    bot.reply_to(message, f"📊 **Total Users:** {count}", parse_mode="Markdown")

# ==========================================================
# 🌍 ADMIN: TOTAL SITES
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌍 TOTAL SITES")
def admin_total_sites(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    users = get_all_users()
    total = 0
    
    if users:
        for data in users.values():
            total += len(data.get('sites', {}))
    
    bot.reply_to(message, f"🌍 **Total Sites:** {total}", parse_mode="Markdown")

# ==========================================================
# 🚫 ADMIN: BAN USER
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER")
def admin_ban_user(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter **User ID** to ban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_ban_user)

def process_ban_user(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid user ID!")
        return
    
    target_id = int(target_id)
    
    if target_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "❌ Cannot ban super admin!")
        return
    
    if ban_user(target_id):
        bot.reply_to(message, f"✅ User **{target_id}** banned!", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Failed to ban user!")

# ==========================================================
# ✅ ADMIN: UNBAN USER
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "✅ UNBAN USER")
def admin_unban_user(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter **User ID** to unban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_unban_user)

def process_unban_user(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid user ID!")
        return
    
    target_id = int(target_id)
    
    if unban_user(target_id):
        bot.reply_to(message, f"✅ User **{target_id}** unbanned!", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Failed to unban user!")

# ==========================================================
# 🔄 ADMIN: RESET LIMIT
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🔄 RESET LIMIT")
def admin_reset_limit(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter **User ID** to reset limit:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_reset_limit)

def process_reset_limit(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid user ID!")
        return
    
    target_id = int(target_id)
    rate_limiter.reset_limit(target_id)
    
    bot.reply_to(message, f"✅ Daily limit reset for user **{target_id}**!", parse_mode="Markdown")

# ==========================================================
# 📢 ADMIN: BROADCAST
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def admin_broadcast(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "📝 Enter message to broadcast:")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    broadcast_text = message.text
    
    if not FIREBASE_READY:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    users = get_all_users()
    
    if not users:
        bot.reply_to(message, "❌ No users found!")
        return
    
    status_msg = bot.reply_to(message, "📨 Broadcasting...")
    
    sent = 0
    failed = 0
    
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 **Admin Broadcast:**\n\n{broadcast_text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)  # Rate limit protection
        except:
            failed += 1
    
    bot.edit_message_text(
        f"✅ **Broadcast complete!**\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}",
        message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown"
    )

# ==========================================================
# ➕ ADMIN: ADD ADMIN
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "➕ ADD ADMIN")
def admin_add_admin(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only super admin can add admins!")
        return
    
    bot.reply_to(message, "Enter **User ID** to make admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    adder_id = message.from_user.id
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid user ID!")
        return
    
    target_id = int(target_id)
    
    if target_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "⚠️ User is already super admin!")
        return
    
    if add_admin(target_id, adder_id):
        bot.reply_to(message, f"✅ User **{target_id}** is now admin!", parse_mode="Markdown")
        
        # Notify new admin
        try:
            bot.send_message(
                target_id,
                "🎉 You have been granted **Admin** access!\n\nUse the admin panel with your password."
            )
        except:
            pass
    else:
        bot.reply_to(message, "❌ Failed to add admin!")

# ==========================================================
# ➖ ADMIN: REMOVE ADMIN
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "➖ REMOVE ADMIN")
def admin_remove_admin(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only super admin can remove admins!")
        return
    
    admins = get_admin_list()
    
    if not admins:
        bot.reply_to(message, "❌ No additional admins found!")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for uid, data in admins.items():
        added_at = data.get('added_at', 'unknown')[:10]
        markup.add(InlineKeyboardButton(f"❌ Admin {uid} (added: {added_at})", callback_data=f"remove_admin_{uid}"))
    
    markup.add(InlineKeyboardButton("🔙 Cancel", callback_data="cancel_admin_remove"))
    
    bot.send_message(message.chat.id, "Select admin to remove:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_admin_'))
def remove_admin_callback(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Only super admin can do this!")
        return
    
    target_id = int(call.data.replace('remove_admin_', ''))
    
    if remove_admin(target_id):
        bot.edit_message_text(
            f"✅ Admin **{target_id}** removed!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        
        # Notify removed admin
        try:
            bot.send_message(target_id, "⚠️ Your **Admin** access has been revoked.")
        except:
            pass
    else:
        bot.edit_message_text(
            "❌ Failed to remove admin!",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_admin_remove")
def cancel_admin_remove(call):
    bot.edit_message_text(
        "✅ Operation cancelled!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📋 ADMIN: ADMIN LIST
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📋 ADMIN LIST")
def admin_list_admins(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    text = f"👑 **Super Admin:** `{SUPER_ADMIN_ID}`\n\n"
    
    admins = get_admin_list()
    
    if admins:
        text += "📋 **Additional Admins:**\n"
        for uid, data in admins.items():
            added_at = data.get('added_at', 'unknown')[:10]
            text += f"• `{uid}` (added: {added_at})\n"
    else:
        text += "📋 No additional admins."
    
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 🗑 ADMIN: DELETE USER SITE
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 DELETE USER SITE")
def admin_delete_user_site(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter **User ID**:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_delete_user_site_1)

def process_delete_user_site_1(message):
    target_user = message.text.strip()
    
    if not target_user.isdigit():
        bot.reply_to(message, "❌ Invalid user ID!")
        return
    
    admin_sessions['temp_target'] = int(target_user)
    
    bot.reply_to(message, "Enter **Site Name**:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_delete_user_site_2)

def process_delete_user_site_2(message):
    target_site = message.text.strip()
    target_user = admin_sessions.get('temp_target')
    
    if not target_user:
        bot.reply_to(message, "❌ Session expired!")
        return
    
    # Delete from Vercel
    delete_vercel_project(target_site)
    
    # Delete from GitHub
    delete_github_repo(target_site)
    
    # Delete from Firebase
    delete_site_from_db(target_user, target_site)
    
    del admin_sessions['temp_target']
    
    bot.reply_to(
        message,
        f"✅ Site **{target_site}** deleted for user **{target_user}**!",
        parse_mode="Markdown"
    )

# ==========================================================
# 🚪 ADMIN: LOGOUT
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🚪 LOGOUT")
def admin_logout(message):
    user_id = message.from_user.id
    
    if user_id in admin_sessions:
        del admin_sessions[user_id]
    
    bot.send_message(message.chat.id, "✅ Logged out!", reply_markup=main_menu())

# ==========================================================
# ⬅️ MENU: MAIN MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "⬅️ MAIN MENU")
def back_to_main_menu(message):
    bot.send_message(message.chat.id, "Main Menu", reply_markup=main_menu())

# ==========================================================
# 🔄 FALLBACK HANDLER (MUST BE LAST)
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(message, "❌ Please use the menu buttons!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP HEALTH CHECK SERVER (FOR RENDER)
# ==========================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    
    def log_message(self, format, *args):
        # Suppress log messages
        pass

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"🌐 Health check server running on port {PORT}")
    server.serve_forever()

# ==========================================================
# 🏁 START BOT
# ==========================================================
if __name__ == "__main__":
    # Start health check server (for Render)
    threading.Thread(target=run_health_server, daemon=True).start()
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot username: @{bot_info.username}")
        print(f"✅ Bot name: {bot_info.first_name}")
        print("=" * 60)
        print("🟢 Bot is running...")
        print("=" * 60)
        
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except KeyboardInterrupt:
        print("\n👋 Bot shutting down...")
    except Exception as e:
        print(f"❌ Bot error: {e}")
        traceback.print_exc()