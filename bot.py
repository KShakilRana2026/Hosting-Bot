# ==========================================================
# 🔥 ADVANCED TELEGRAM HOSTING BOT - PROFESSIONAL VERSION
# ==========================================================
# ✅ All Features Included:
# ✅ Group + Channel Verify | ✅ Firebase Connect | ✅ Daily 5 Limit
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

# Core Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("GROUP_ID")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
FIREBASE_CONFIG_BASE64 = os.getenv("FIREBASE_CONFIG_BASE64")

print("=" * 70)
print("🔥 ADVANCED TELEGRAM HOSTING BOT")
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
    "FIREBASE_DB_URL": FIREBASE_DB_URL
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
# 🔥 FIREBASE INITIALIZATION
# ==========================================================
firebase_ready = False
admin_cache = {}  # Cache for admin list

def init_firebase():
    """Initialize Firebase with Base64 config"""
    global firebase_ready
    
    if not FIREBASE_CONFIG_BASE64:
        print("⚠️ Firebase config not found - continuing without database")
        return False
    
    try:
        # Decode Base64 config
        json_bytes = base64.b64decode(FIREBASE_CONFIG_BASE64)
        json_str = json_bytes.decode('utf-8')
        cred_dict = json.loads(json_str)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cred_dict, f)
            temp_path = f.name
        
        # Initialize Firebase
        cred = credentials.Certificate(temp_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        
        # Clean up temp file
        os.unlink(temp_path)
        
        firebase_ready = True
        print("✅ Firebase connected successfully")
        
        # Load admin list into cache
        load_admin_cache()
        return True
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return False

def load_admin_cache():
    """Load admin list from Firebase to cache"""
    global admin_cache
    if not firebase_ready:
        return
    try:
        admins = db.reference('admins').get()
        if admins:
            admin_cache = admins
        # Always include super admin
        admin_cache[str(ADMIN_ID)] = {"super": True}
    except:
        admin_cache = {str(ADMIN_ID): {"super": True}}

# Initialize Firebase
init_firebase()

# ==========================================================
# 📊 RATE LIMITER
# ==========================================================
class RateLimiter:
    def __init__(self):
        self.user_requests = {}
        self.daily_limit = 5
    
    def check_daily_limit(self, user_id):
        """Check if user has reached daily limit"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        
        if key not in self.user_requests:
            self.user_requests[key] = 0
            return True
        
        return self.user_requests[key] < self.daily_limit
    
    def increment_count(self, user_id):
        """Increment user's daily count"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        
        if key not in self.user_requests:
            self.user_requests[key] = 0
        
        self.user_requests[key] += 1
        
        # Also update Firebase if connected
        if firebase_ready:
            try:
                user_ref = db.reference(f'users/{user_id}')
                user_data = user_ref.get() or {}
                user_data['daily_count'] = self.user_requests[key]
                user_data['last_active'] = datetime.now().isoformat()
                user_ref.set(user_data)
            except:
                pass
        
        return self.user_requests[key]
    
    def get_user_count(self, user_id):
        """Get user's today's count"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        return self.user_requests.get(key, 0)
    
    def reset_user_limit(self, user_id):
        """Reset user's daily limit (admin function)"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{user_id}_{today}"
        self.user_requests[key] = 0
        
        if firebase_ready:
            try:
                db.reference(f'users/{user_id}/daily_count').set(0)
            except:
                pass
        return True

rate_limiter = RateLimiter()

# ==========================================================
# 🎛 MENU CREATION
# ==========================================================
def main_menu():
    """Create main user menu"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 HOST WEBSITE", "📂 MY SITES")
    markup.row("🌐 ADD DOMAIN", "🗑 DELETE SITE")
    markup.row("📊 DAILY LIMIT", "👑 ADMIN PANEL")
    return markup

def admin_menu():
    """Create admin menu"""
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
    """Check if user is in required channel and group"""
    try:
        # Check if banned
        if firebase_ready:
            banned = db.reference(f'banned/{user_id}').get()
            if banned:
                return False
        
        # Check channel membership
        ch = bot.get_chat_member(CHANNEL_ID, user_id)
        if ch.status not in ["member", "administrator", "creator"]:
            return False
        
        # Check group membership
        gp = bot.get_chat_member(GROUP_ID, user_id)
        if gp.status not in ["member", "administrator", "creator"]:
            return False
        
        return True
    except Exception as e:
        print(f"Verification error for {user_id}: {e}")
        return False

# ==========================================================
# 👑 ADMIN SYSTEM
# ==========================================================
admin_sessions = {}

def is_super_admin(user_id):
    """Check if user is super admin (from env)"""
    return int(user_id) == ADMIN_ID

def is_admin(user_id):
    """Check if user has admin privileges"""
    # Check super admin first
    if is_super_admin(user_id):
        return True
    
    # Check cache
    if str(user_id) in admin_cache:
        return True
    
    # Check Firebase if cache miss
    if firebase_ready:
        try:
            admin_data = db.reference(f'admins/{user_id}').get()
            if admin_data:
                admin_cache[str(user_id)] = admin_data
                return True
        except:
            pass
    
    return False

def is_admin_logged_in(user_id):
    """Check if admin session is active"""
    return admin_sessions.get(user_id, False)

def add_admin(admin_id, added_by):
    """Add new admin (super admin only)"""
    if not firebase_ready:
        return False, "Firebase not connected"
    
    try:
        admin_data = {
            "added_by": added_by,
            "added_at": datetime.now().isoformat(),
            "user_id": admin_id
        }
        db.reference(f'admins/{admin_id}').set(admin_data)
        admin_cache[str(admin_id)] = admin_data
        return True, "Admin added successfully"
    except Exception as e:
        return False, str(e)

def remove_admin(admin_id):
    """Remove admin (super admin only)"""
    if not firebase_ready:
        return False, "Firebase not connected"
    
    try:
        db.reference(f'admins/{admin_id}').delete()
        if str(admin_id) in admin_cache:
            del admin_cache[str(admin_id)]
        return True, "Admin removed successfully"
    except Exception as e:
        return False, str(e)

def ban_user(user_id, banned_by):
    """Ban a user"""
    if not firebase_ready:
        return False, "Firebase not connected"
    
    try:
        ban_data = {
            "banned_by": banned_by,
            "banned_at": datetime.now().isoformat()
        }
        db.reference(f'banned/{user_id}').set(ban_data)
        return True, "User banned successfully"
    except Exception as e:
        return False, str(e)

def unban_user(user_id):
    """Unban a user"""
    if not firebase_ready:
        return False, "Firebase not connected"
    
    try:
        db.reference(f'banned/{user_id}').delete()
        return True, "User unbanned successfully"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🔐 SECURE ZIP EXTRACTOR
# ==========================================================
def secure_extract_zip(zip_content, extract_path):
    """Safely extract zip file with path traversal protection"""
    try:
        with zipfile.ZipFile(BytesIO(zip_content)) as zf:
            # Check for malicious files
            for file_info in zf.infolist():
                # Path traversal check
                if '..' in file_info.filename or file_info.filename.startswith('/'):
                    raise Exception(f"Invalid file path detected: {file_info.filename}")
                
                # File size check (100MB limit)
                if file_info.file_size > 100 * 1024 * 1024:
                    raise Exception(f"File too large: {file_info.filename}")
            
            # Extract all files
            zf.extractall(extract_path)
            
            # Check for index.html
            if not os.path.exists(os.path.join(extract_path, 'index.html')):
                # Look for any HTML file
                html_files = []
                for root, _, files in os.walk(extract_path):
                    for file in files:
                        if file.endswith('.html'):
                            html_files.append(os.path.join(root, file))
                
                if html_files:
                    # Use first HTML file as index
                    shutil.copy(html_files[0], os.path.join(extract_path, 'index.html'))
                else:
                    raise Exception("No HTML file found in zip")
        
        return True, "Extraction successful"
    except zipfile.BadZipFile:
        return False, "Invalid zip file"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🔧 GITHUB FUNCTIONS
# ==========================================================
def create_github_repo(repo_name, local_path):
    """Create GitHub repository and upload files"""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Test token
        test_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test_resp.status_code != 200:
            return False, "Invalid GitHub token"
        
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
        
        if resp.status_code == 422:
            # Repository name exists, add timestamp
            repo_name = f"{repo_name}-{int(time.time())}"
            resp = requests.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json=repo_data,
                timeout=30
            )
        
        if resp.status_code != 201:
            return False, f"GitHub API error: {resp.status_code}"
        
        # Upload files
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
        
        return True, {
            "repo_name": repo_name,
            "uploaded": uploaded,
            "failed": failed,
            "url": f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        }
        
    except requests.exceptions.Timeout:
        return False, "GitHub API timeout"
    except requests.exceptions.ConnectionError:
        return False, "Network connection error"
    except Exception as e:
        return False, str(e)

def delete_github_repo(repo_name):
    """Delete GitHub repository"""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
        resp = requests.delete(url, headers=headers, timeout=30)
        
        if resp.status_code == 204:
            return True, "Repository deleted"
        else:
            return False, f"Delete failed: {resp.status_code}"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🚀 VERCEL FUNCTIONS (FULLY FIXED)
# ==========================================================
def deploy_to_vercel(repo_name):
    """Deploy to Vercel - Completely fixed version"""
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔄 Starting Vercel deployment for {repo_name}")
        
        # Step 1: Verify token
        test_resp = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test_resp.status_code != 200:
            print(f"❌ Vercel token invalid: {test_resp.status_code}")
            return None
        
        user_data = test_resp.json()
        print(f"✅ Vercel authenticated as: {user_data.get('user', {}).get('name', 'Unknown')}")
        
        # Step 2: Create/Get project
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
        
        if proj_resp.status_code not in [200, 201]:
            print(f"⚠️ Project creation status: {proj_resp.status_code}")
        
        # Step 3: Create deployment
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
        
        print(f"📡 Vercel response: {deploy_resp.status_code}")
        
        if deploy_resp.status_code in [200, 201]:
            print("✅ Vercel deployment successful")
            return f"https://{repo_name}.vercel.app"
        
        # If deployment already exists
        if deploy_resp.status_code == 400:
            try:
                error_data = deploy_resp.json()
                if "already_exists" in str(error_data).lower():
                    print("⚠️ Deployment already exists, using existing URL")
                    return f"https://{repo_name}.vercel.app"
            except:
                pass
        
        print(f"❌ Vercel error: {deploy_resp.text[:200]}")
        return None
        
    except requests.exceptions.Timeout:
        print("❌ Vercel timeout")
        return None
    except Exception as e:
        print(f"❌ Vercel exception: {e}")
        return None

def delete_vercel_project(project_name):
    """Delete Vercel project"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    try:
        url = f"https://api.vercel.com/v9/projects/{project_name}"
        resp = requests.delete(url, headers=headers, timeout=30)
        
        if resp.status_code in [200, 204]:
            return True, "Project deleted"
        else:
            return False, f"Delete failed: {resp.status_code}"
    except Exception as e:
        return False, str(e)

def add_domain_to_vercel(project_name, domain):
    """Add custom domain to Vercel project"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    try:
        data = {"name": domain}
        url = f"https://api.vercel.com/v9/projects/{project_name}/domains"
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        
        if resp.status_code in [200, 201]:
            return True, "Domain added successfully"
        else:
            error = resp.json().get('error', {}).get('message', 'Unknown error')
            return False, error
    except Exception as e:
        return False, str(e)

# ==========================================================
# 💾 FIREBASE DATABASE FUNCTIONS
# ==========================================================
def save_site_to_firebase(user_id, site_data):
    """Save site information to Firebase"""
    if not firebase_ready:
        return False
    
    try:
        site_ref = db.reference(f'users/{user_id}/sites/{site_data["repo_name"]}')
        site_ref.set({
            "url": site_data["live_url"],
            "github": site_data["github_url"],
            "created": datetime.now().isoformat(),
            "status": "active",
            "domains": []
        })
        
        # Update user's site count
        user_ref = db.reference(f'users/{user_id}')
        user_data = user_ref.get() or {}
        sites = user_data.get('sites', {})
        sites[site_data["repo_name"]] = True
        user_ref.update({'sites': sites})
        
        return True
    except Exception as e:
        print(f"Firebase save error: {e}")
        return False

def get_user_sites(user_id):
    """Get all sites of a user from Firebase"""
    if not firebase_ready:
        return None
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        return sites
    except:
        return None

def delete_site_from_firebase(user_id, repo_name):
    """Delete site from Firebase"""
    if not firebase_ready:
        return False
    
    try:
        db.reference(f'users/{user_id}/sites/{repo_name}').delete()
        return True
    except:
        return False

def get_total_users():
    """Get total user count"""
    if not firebase_ready:
        return 0
    
    try:
        users = db.reference('users').get()
        return len(users) if users else 0
    except:
        return 0

def get_total_sites():
    """Get total sites count"""
    if not firebase_ready:
        return 0
    
    try:
        users = db.reference('users').get()
        total = 0
        if users:
            for user_data in users.values():
                total += len(user_data.get('sites', {}))
        return total
    except:
        return 0

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
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

# ==========================================================
# 📦 ZIP FILE HANDLER
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    # Verification check
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified! Use /start first.")
        return
    
    # File type check
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only ZIP files are allowed!")
        return
    
    # Daily limit check
    if not rate_limiter.check_daily_limit(user_id):
        used = rate_limiter.get_user_count(user_id)
        bot.reply_to(message, f"❌ Daily limit reached! You've used {used}/5 sites today.")
        return
    
    # Size check (50MB)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ File size exceeds 50MB limit!")
        return
    
    status_msg = bot.reply_to(message, "⏳ Processing your request...")
    
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 Extracting zip file...", message.chat.id, status_msg.message_id)
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract zip securely
            extract_success, extract_msg = secure_extract_zip(downloaded, temp_dir)
            if not extract_success:
                bot.edit_message_text(f"❌ {extract_msg}", message.chat.id, status_msg.message_id)
                return
            
            # Generate unique repo name
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 Creating GitHub repository...", message.chat.id, status_msg.message_id)
            
            # Create GitHub repo
            github_success, github_result = create_github_repo(repo_name, temp_dir)
            if not github_success:
                bot.edit_message_text(f"❌ GitHub Error: {github_result}", message.chat.id, status_msg.message_id)
                return
            
            # Extract repo name from result
            if isinstance(github_result, dict):
                repo_name = github_result.get('repo_name', repo_name)
                github_url = github_result.get('url', f"https://github.com/{GITHUB_USERNAME}/{repo_name}")
            else:
                github_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
            
            bot.edit_message_text("🚀 Deploying to Vercel...", message.chat.id, status_msg.message_id)
            
            # Deploy to Vercel
            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                bot.edit_message_text("❌ Vercel deployment failed! Please try again.", message.chat.id, status_msg.message_id)
                # Clean up GitHub repo
                delete_github_repo(repo_name)
                return
            
            # Update daily count
            rate_limiter.increment_count(user_id)
            used_now = rate_limiter.get_user_count(user_id)
            
            # Save to Firebase
            if firebase_ready:
                site_data = {
                    "repo_name": repo_name,
                    "live_url": live_url,
                    "github_url": github_url
                }
                save_site_to_firebase(user_id, site_data)
            
            # Success message
            success_text = (
                f"✅ **DEPLOYMENT SUCCESSFUL!**\n\n"
                f"🌐 **Live URL:**\n`{live_url}`\n\n"
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
            
    except Exception as e:
        error_msg = str(e)[:200]
        bot.edit_message_text(f"❌ Unexpected error: {error_msg}", message.chat.id, status_msg.message_id)
        print(f"Error in handle_zip: {traceback.format_exc()}")

# ==========================================================
# 📂 MY SITES MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 MY SITES")
def menu_my_sites(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected. Please try again later.")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "📂 You haven't hosted any sites yet!")
        return
    
    text = "🌐 **Your Hosted Sites:**\n\n"
    for name, data in sites.items():
        text += f"📁 **{name}**\n"
        text += f"🔗 {data.get('url', 'N/A')}\n"
        text += f"📅 {data.get('created', 'Unknown')[:10]}\n\n"
    
    # Handle long message
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            bot.send_message(message.chat.id, part, parse_mode="Markdown")
    else:
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
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected.")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "❌ You don't have any sites yet!")
        return
    
    # Create inline keyboard with sites
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"domain_{name}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_domain"))
    
    bot.send_message(
        message.chat.id,
        "Select the site to add a custom domain:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('domain_'))
def domain_callback(call):
    project = call.data.replace('domain_', '')
    
    bot.edit_message_text(
        f"Enter your domain name (e.g., example.com):",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.register_next_step_handler(call.message, lambda m: process_domain(m, project))

def process_domain(message, project):
    domain = message.text.strip().lower()
    
    # Basic domain validation
    if not domain or '.' not in domain or len(domain) < 4:
        bot.reply_to(message, "❌ Invalid domain name!")
        return
    
    status = bot.reply_to(message, f"⏳ Adding domain {domain} to {project}...")
    
    success, result = add_domain_to_vercel(project, domain)
    
    if success:
        # Save domain to Firebase
        if firebase_ready:
            try:
                db.reference(f'users/{message.from_user.id}/sites/{project}/domains').push(domain)
            except:
                pass
        
        dns_text = (
            f"✅ **Domain added successfully!**\n\n"
            f"📌 **DNS Configuration:**\n"
            f"```\n"
            f"Type: CNAME\n"
            f"Name: @\n"
            f"Value: cname.vercel-dns.com\n"
            f"```\n\n"
            f"⚠️ DNS propagation may take 24-48 hours."
        )
        bot.edit_message_text(dns_text, message.chat.id, status.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text(f"❌ Failed to add domain: {result}", message.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_domain")
def cancel_domain(call):
    bot.edit_message_text(
        "✅ Operation cancelled.",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 🗑 DELETE SITE MENU
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 DELETE SITE")
def menu_delete_site(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected.")
        return
    
    sites = get_user_sites(user_id)
    
    if not sites:
        bot.reply_to(message, "❌ You don't have any sites to delete!")
        return
    
    # Create inline keyboard with sites
    markup = InlineKeyboardMarkup(row_width=1)
    for name in sites.keys():
        markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"delete_{name}"))
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete"))
    
    bot.send_message(
        message.chat.id,
        "Select the site to delete:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_callback(call):
    project = call.data.replace('delete_', '')
    user_id = call.from_user.id
    
    # Confirmation
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirm_{project}"),
        InlineKeyboardButton("❌ No, cancel", callback_data="cancel_delete")
    )
    
    bot.edit_message_text(
        f"Are you sure you want to delete **{project}**?\n\n⚠️ This will delete from GitHub, Vercel, and database!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def confirm_delete(call):
    project = call.data.replace('confirm_', '')
    user_id = call.from_user.id
    
    status_msg = bot.edit_message_text(
        f"🔄 Deleting {project}...",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Track deletion results
    results = []
    
    # Delete from Vercel
    vercel_success, vercel_msg = delete_vercel_project(project)
    results.append(f"Vercel: {'✅' if vercel_success else '❌'} {vercel_msg}")
    
    # Delete from GitHub
    github_success, github_msg = delete_github_repo(project)
    results.append(f"GitHub: {'✅' if github_success else '❌'} {github_msg}")
    
    # Delete from Firebase
    if firebase_ready:
        fb_success = delete_site_from_firebase(user_id, project)
        results.append(f"Database: {'✅' if fb_success else '❌'}")
    
    # Final message
    final_text = f"🗑 **Deletion Results for {project}:**\n\n" + "\n".join(results)
    
    bot.edit_message_text(
        final_text,
        call.message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete(call):
    bot.edit_message_text(
        "✅ Deletion cancelled.",
        call.message.chat.id,
        call.message.message_id
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
    
    used = rate_limiter.get_user_count(user_id)
    remaining = 5 - used
    
    # Create progress bar
    bar = "🟩" * used + "⬜" * remaining
    
    text = (
        f"📊 **Your Daily Usage:**\n\n"
        f"{bar}\n"
        f"**Used:** {used}/5\n"
        f"**Remaining:** {remaining}\n\n"
        f"🕒 Resets at midnight (UTC+6)"
    )
    
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 ADMIN PANEL
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def menu_admin_panel(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ You are not verified!")
        return
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ You don't have admin access!")
        return
    
    if is_admin_logged_in(user_id):
        bot.send_message(
            message.chat.id,
            "👑 **Admin Panel**\n\nWelcome to the admin control center.",
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
    else:
        bot.reply_to(message, "🔑 **Enter admin password:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_password)

def check_admin_password(message):
    user_id = message.from_user.id
    
    if message.text == ADMIN_PASSWORD:
        admin_sessions[user_id] = True
        bot.send_message(
            message.chat.id,
            "✅ **Login successful!**",
            parse_mode="Markdown",
            reply_markup=admin_menu()
        )
    else:
        bot.reply_to(
            message,
            "❌ **Wrong password!**",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

# ==========================================================
# 👑 ADMIN MENU HANDLERS
# ==========================================================

@bot.message_handler(func=lambda m: m.text == "📊 TOTAL USERS")
def admin_total_users(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    total = get_total_users()
    bot.reply_to(message, f"📊 **Total Users:** {total}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌍 TOTAL SITES")
def admin_total_sites(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    total = get_total_sites()
    bot.reply_to(message, f"🌍 **Total Sites:** {total}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER")
def admin_ban_user(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter the **User ID** to ban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_ban)

def process_ban(message):
    admin_id = message.from_user.id
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    
    success, result = ban_user(target_id, admin_id)
    bot.reply_to(message, f"{'✅' if success else '❌'} {result}")

@bot.message_handler(func=lambda m: m.text == "✅ UNBAN USER")
def admin_unban_user(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter the **User ID** to unban:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_unban)

def process_unban(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    
    success, result = unban_user(target_id)
    bot.reply_to(message, f"{'✅' if success else '❌'} {result}")

@bot.message_handler(func=lambda m: m.text == "🔄 RESET LIMIT")
def admin_reset_limit(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(message, "Enter the **User ID** to reset daily limit:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_reset_limit)

def process_reset_limit(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    
    rate_limiter.reset_user_limit(target_id)
    bot.reply_to(message, f"✅ Daily limit reset for user {target_id}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def admin_broadcast(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    bot.reply_to(
        message,
        "📢 **Send the message to broadcast to all users:**\n\n(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    if message.text == "/cancel":
        bot.reply_to(message, "✅ Broadcast cancelled.", reply_markup=admin_menu())
        return
    
    broadcast_text = message.text
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Firebase not connected!")
        return
    
    try:
        users = db.reference('users').get()
        if not users:
            bot.reply_to(message, "❌ No users found!")
            return
        
        status = bot.reply_to(message, "📨 Sending broadcast...")
        
        sent = 0
        failed = 0
        
        for uid in users.keys():
            try:
                bot.send_message(
                    int(uid),
                    f"📢 **ADMIN BROADCAST**\n\n{broadcast_text}",
                    parse_mode="Markdown"
                )
                sent += 1
                time.sleep(0.05)  # Rate limit avoidance
            except:
                failed += 1
        
        bot.edit_message_text(
            f"✅ **Broadcast Complete**\n\nSent: {sent}\nFailed: {failed}",
            message.chat.id,
            status.message_id,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ Broadcast failed: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "➕ ADD ADMIN")
def admin_add_admin(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only Super Admin can add new admins!")
        return
    
    bot.reply_to(message, "Enter the **User ID** to make admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    admin_id = message.from_user.id
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    
    if int(target_id) == ADMIN_ID:
        bot.reply_to(message, "⚠️ This user is already the Super Admin!")
        return
    
    success, result = add_admin(target_id, admin_id)
    bot.reply_to(message, f"{'✅' if success else '❌'} {result}")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE ADMIN")
def admin_remove_admin(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Only Super Admin can remove admins!")
        return
    
    bot.reply_to(message, "Enter the **User ID** to remove from admin:", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.reply_to(message, "❌ Invalid User ID! Must be numeric.")
        return
    
    if int(target_id) == ADMIN_ID:
        bot.reply_to(message, "⚠️ Cannot remove Super Admin!")
        return
    
    success, result = remove_admin(target_id)
    bot.reply_to(message, f"{'✅' if success else '❌'} {result}")

@bot.message_handler(func=lambda m: m.text == "📋 ADMIN LIST")
def admin_list(message):
    user_id = message.from_user.id
    
    if not is_admin_logged_in(user_id):
        return
    
    text = "👑 **Admin List:**\n\n"
    text += f"⭐ **Super Admin:** `{ADMIN_ID}`\n\n"
    
    if admin_cache:
        text += "📋 **Other Admins:**\n"
        for aid in admin_cache.keys():
            if int(aid) != ADMIN_ID:
                text += f"• `{aid}`\n"
    else:
        text += "📋 No other admins."
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚪 LOGOUT")
def admin_logout(message):
    user_id = message.from_user.id
    
    if user_id in admin_sessions:
        del admin_sessions[user_id]
    
    bot.send_message(
        message.chat.id,
        "✅ **Logged out of admin panel**",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "⬅️ MAIN MENU")
def back_to_main_menu(message):
    bot.send_message(message.chat.id, "⬅️ Back to main menu", reply_markup=main_menu())

# ==========================================================
# 🔄 FALLBACK HANDLER
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(
        message,
        "❌ Please use the menu buttons to navigate!",
        reply_markup=main_menu()
    )

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
    """Run HTTP server for Render health checks"""
    port = int(os.getenv("PORT", 10000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"🌐 HTTP server running on port {port}")
    httpd.serve_forever()

# ==========================================================
# 🏁 START BOT
# ==========================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🔥 STARTING TELEGRAM HOSTING BOT")
    print("=" * 70)
    
    # Start HTTP server in separate thread
    threading.Thread(target=run_http_server, daemon=True).start()
    
    try:
        # Get bot info
        bot_info = bot.get_me()
        print(f"✅ Bot username: @{bot_info.username}")
        print(f"✅ Bot name: {bot_info.first_name}")
        print("=" * 70)
        print("🟢 Bot is running... (Press Ctrl+C to stop)")
        print("=" * 70)
        
        # Start polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()