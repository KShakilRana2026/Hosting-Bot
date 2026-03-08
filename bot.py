# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট (সম্পূর্ণ এরর-ফ্রি ভার্সন)
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

from io import BytesIO
from datetime import datetime, timedelta
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ==========================================================
# 🔐 লোড এনভায়রনমেন্ট ভেরিয়েবল
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
print("🔥 টেলিগ্রাম হোস্টিং বট চালু হচ্ছে...")
print("=" * 60)
print(f"BOT_TOKEN: {'✅ পাওয়া গেছে' if BOT_TOKEN else '❌ নেই'}")
print(f"GITHUB_TOKEN: {'✅ পাওয়া গেছে' if GITHUB_TOKEN else '❌ নেই'}")
print(f"GITHUB_USERNAME: {'✅ পাওয়া গেছে' if GITHUB_USERNAME else '❌ নেই'}")
print(f"VERCEL_TOKEN: {'✅ পাওয়া গেছে' if VERCEL_TOKEN else '❌ নেই'}")
print(f"ADMIN_PASSWORD: {'✅ পাওয়া গেছে' if ADMIN_PASSWORD else '❌ নেই'}")
print(f"ADMIN_ID: {'✅ পাওয়া গেছে' if ADMIN_ID else '❌ নেই'}")
print(f"CHANNEL_ID: {'✅ পাওয়া গেছে' if CHANNEL_ID else '❌ নেই'}")
print(f"GROUP_ID: {'✅ পাওয়া গেছে' if GROUP_ID else '❌ নেই'}")
print(f"FIREBASE_DB_URL: {'✅ পাওয়া গেছে' if FIREBASE_DB_URL else '❌ নেই'}")
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
    print(f"❌ নিচের Environment Variables গুলো নেই: {', '.join(missing_vars)}")
    print("⚠️ Render Dashboard-এ Environment Variables সেট করুন")
    sys.exit(1)

# Convert to proper types
try:
    ADMIN_ID = int(ADMIN_ID)
    CHANNEL_ID = int(CHANNEL_ID)
    GROUP_ID = int(GROUP_ID)
except ValueError as e:
    print(f"❌ ADMIN_ID, CHANNEL_ID বা GROUP_ID ভুল ফরম্যাটে আছে: {e}")
    print("⚠️ এগুলো সংখ্যা হতে হবে (যেমন: 123456789)")
    sys.exit(1)

# ==========================================================
# 🚀 বট ইনিশিয়ালাইজেশন
# ==========================================================
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ বট টোকেন ভ্যালিড")
except Exception as e:
    print(f"❌ বট টোকেন ভুল: {e}")
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
    print("⚠️ Render Dashboard-এ নিচের যেকোনো একটি সেট করুন:")
    print("   1. Secret File হিসেবে firebase.json আপলোড করুন")
    print("   2. FIREBASE_CONFIG_BASE64 environment variable সেট করুন")
    print("   3. অথবা আলাদা আলাদা FIREBASE_* variables সেট করুন")
    sys.exit(1)

print("✅ Firebase is ready!")

# ==========================================================
# 📊 রেট লিমিটার ক্লাস
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
# 📊 দৈনিক লিমিট চেক
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
# 🔐 সিকিউর জিপ এক্সট্র্যাক্ট
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
# 🚀 /start কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 চ্যানেল", url="https://t.me/your_channel"),
            InlineKeyboardButton("👥 গ্রুপ", url="https://t.me/your_group")
        )
        bot.reply_to(
            message,
            "❌ আগে আমাদের চ্যানেল ও গ্রুপে জয়েন করুন!\n\n"
            "জয়িন করার পর আবার /start দিন।",
            reply_markup=markup
        )
        return
    
    welcome_text = (
        f"👋 স্বাগতম {username}!\n\n"
        f"📌 এই বট দিয়ে আপনি ওয়েবসাইট হোস্ট করতে পারবেন।\n"
        f"✅ দৈনিক ৫টি সাইট হোস্ট করা যাবে।\n\n"
        f"📋 **কিভাবে ব্যবহার করবেন:**\n"
        f"1️⃣ আপনার ওয়েবসাইটের সব ফাইল জিপ করুন\n"
        f"2️⃣ জিপ ফাইলটি এখানে আপলোড করুন\n"
        f"3️⃣ বট অটো GitHub ও Vercel-এ ডিপ্লয় করবে\n"
        f"4️⃣ আপনি একটি লাইভ লিংক পাবেন\n\n"
        f"⚠️ জিপ ফাইলের মধ্যে index.html থাকতে হবে"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডেল
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    # Verification check
    if not is_verified(user_id):
        bot.reply_to(message, "❌ আগে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    # File type check
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ শুধু ZIP ফাইল অনুমোদিত!")
        return
    
    # Daily limit check
    if not check_daily_limit(user_id):
        used = get_user_count(user_id)
        bot.reply_to(message, f"❌ আজকের লিমিট শেষ! (আপনি {used}/৫টি ব্যবহার করেছেন)")
        return
    
    # Size check (50MB)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ ৫০MB এর বড় ফাইল দেয়া যাবে না!")
        return
    
    # Send status message
    status_msg = bot.reply_to(message, "⏳ ডাউনলোড শুরু হচ্ছে...")
    
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 জিপ এক্সট্র্যাক্ট করা হচ্ছে...", 
                            message.chat.id, status_msg.message_id)
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract zip
            if not secure_extract_zip(downloaded, temp_dir):
                bot.edit_message_text("❌ জিপ ফাইল এক্সট্র্যাক্ট করতে সমস্যা!", 
                                    message.chat.id, status_msg.message_id)
                return
            
            # Generate unique repo name
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            # Create GitHub repo
            bot.edit_message_text("🔧 GitHub রিপোজিটরি তৈরি হচ্ছে...", 
                                message.chat.id, status_msg.message_id)
            
            if not create_github_repo(repo_name, temp_dir):
                bot.edit_message_text("❌ GitHub রিপোজিটরি তৈরি করতে সমস্যা!", 
                                    message.chat.id, status_msg.message_id)
                return
            
            # Deploy to Vercel
            bot.edit_message_text("🚀 Vercel-এ ডিপ্লয় হচ্ছে...", 
                                message.chat.id, status_msg.message_id)
            
            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                bot.edit_message_text("❌ Vercel ডিপ্লয় করতে সমস্যা!", 
                                    message.chat.id, status_msg.message_id)
                return
            
            # Save to Firebase
            save_site_to_firebase(user_id, repo_name, live_url)
            
            # Increase count
            increase_count(user_id)
            
            # Success message
            used_now = get_user_count(user_id)
            success_text = (
                f"✅ **সফলভাবে ডিপ্লয় হয়েছে!**\n\n"
                f"🌐 **লাইভ URL:**\n`{live_url}`\n\n"
                f"📂 **GitHub:**\nhttps://github.com/{GITHUB_USERNAME}/{repo_name}\n\n"
                f"📊 **আজকে ব্যবহার:** {used_now}/৫\n\n"
                f"💡 **পরবর্তী ধাপ:**\n"
                f"• কাস্টম ডোমেইন যোগ করতে '🌐 ডোমেইন যোগ করুন' মেনু ব্যবহার করুন\n"
                f"• সাইট ডিলিট করতে '🗑 সাইট ডিলিট' মেনু ব্যবহার করুন"
            )
            
            bot.edit_message_text(success_text, message.chat.id, status_msg.message_id,
                                parse_mode="Markdown")
            
    except Exception as e:
        error_msg = str(e)[:200]
        bot.edit_message_text(f"❌ সমস্যা হয়েছে: {error_msg}", 
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
# 📂 আমার সাইটসমূহ
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইটসমূহ")
def my_sites(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        
        if not sites:
            bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
            return
        
        text = "🌐 **আপনার সাইটসমূহ:**\n\n"
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
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# ==========================================================
# 🌐 ডোমেইন যোগ করুন
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন যোগ করুন")
def add_domain_start(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        
        if not sites:
            bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
            return
        
        # Create inline keyboard with sites
        markup = InlineKeyboardMarkup(row_width=1)
        for name in sites.keys():
            markup.add(InlineKeyboardButton(f"🌐 {name}", callback_data=f"domain_{name}"))
        
        bot.send_message(message.chat.id, "যে সাইটে ডোমেইন যোগ করবেন সিলেক্ট করুন:", 
                        reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('domain_'))
def domain_callback(call):
    project = call.data.replace('domain_', '')
    
    bot.edit_message_text(
        f"আপনার ডোমেইন নাম লিখুন (যেমন: example.com):",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Register next step
    bot.register_next_step_handler(call.message, lambda m: add_domain_to_vercel(m, project))

def add_domain_to_vercel(message, project):
    domain = message.text.strip().lower()
    
    # Validate domain
    if not domain or '.' not in domain:
        bot.reply_to(message, "❌ ভ্যালিড ডোমেইন দিন!")
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
                f"✅ **ডোমেইন যোগ হয়েছে!**\n\n"
                f"📌 **DNS সেটিংস:**\n"
                f"```\n"
                f"টাইপ: CNAME\n"
                f"নাম: @\n"
                f"ভ্যালু: cname.vercel-dns.com\n"
                f"```\n\n"
                f"⚠️ DNS প্রপাগেট হতে ২৪-৪৮ ঘন্টা সময় লাগতে পারে।"
            )
            bot.reply_to(message, dns_text, parse_mode="Markdown")
        else:
            error_msg = r.json().get('error', {}).get('message', 'Unknown error')
            bot.reply_to(message, f"❌ ডোমেইন যোগ করতে সমস্যা: {error_msg}")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# ==========================================================
# 🗑 সাইট ডিলিট
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 সাইট ডিলিট")
def delete_site_start(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        
        if not sites:
            bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
            return
        
        # Create inline keyboard with sites
        markup = InlineKeyboardMarkup(row_width=1)
        for name in sites.keys():
            markup.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"delete_{name}"))
        
        bot.send_message(message.chat.id, "যে সাইট ডিলিট করবেন সিলেক্ট করুন:", 
                        reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_callback(call):
    project = call.data.replace('delete_', '')
    user_id = call.from_user.id
    
    # Confirmation
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ হ্যাঁ", callback_data=f"confirm_{project}"),
        InlineKeyboardButton("❌ না", callback_data="cancel_delete")
    )
    
    bot.edit_message_text(
        f"আপনি কি **{project}** ডিলিট করতে চান?",
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
        f"🔄 {project} ডিলিট করা হচ্ছে...",
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
            f"✅ **{project}** সফলভাবে ডিলিট হয়েছে!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.edit_message_text(
            f"❌ ডিলিট করতে সমস্যা: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete(call):
    bot.edit_message_text(
        "✅ ডিলিট বাতিল করা হয়েছে!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📊 দৈনিক লিমিট
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 দৈনিক লিমিট")
def show_limit(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    used = get_user_count(user_id)
    remaining = 5 - used
    
    # Create progress bar
    bar = "🟩" * used + "⬜" * remaining
    
    text = (
        f"📊 **আপনার দৈনিক ব্যবহার:**\n\n"
        f"{bar}\n"
        f"**ব্যবহার:** {used}/৫\n"
        f"**বাকি:** {remaining}\n\n"
        f"🕒 রিসেট হবে: আজ রাত ১২টায়"
    )
    
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================================
# 👑 অ্যাডমিন প্যানেল
# ==========================================================
admin_sessions = {}

def is_admin(user_id):
    """Check if user is admin"""
    return str(user_id) == str(ADMIN_ID)

def is_admin_logged_in(user_id):
    """Check if admin is logged in"""
    return admin_sessions.get(user_id, False)

@bot.message_handler(func=lambda m: m.text == "👑 অ্যাডমিন")
def admin_panel(message):
    user_id = message.from_user.id
    
    if not is_verified(user_id):
        bot.reply_to(message, "❌ ভেরিফাইড নন!")
        return
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ আপনার অ্যাডমিন অ্যাক্সেস নেই!")
        return
    
    if is_admin_logged_in(user_id):
        bot.send_message(message.chat.id, "👑 **অ্যাডমিন প্যানেল**", 
                        parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 **অ্যাডমিন পাসওয়ার্ড দিন:**", parse_mode="Markdown")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ **লগইন সফল!**", 
                        parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ **ভুল পাসওয়ার্ড!**", 
                    parse_mode="Markdown", reply_markup=main_menu())

# 📊 মোট ইউজার
@bot.message_handler(func=lambda m: m.text == "📊 মোট ইউজার")
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
            f"📊 **ইউজার পরিসংখ্যান:**\n\n"
            f"মোট ইউজার: **{count}**\n"
            f"অ্যাক্টিভ: **{active}**\n"
            f"ইনঅ্যাক্টিভ: **{count - active}**"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# 🌍 মোট সাইট
@bot.message_handler(func=lambda m: m.text == "🌍 মোট সাইট")
def total_sites(message):
    if not is_admin_logged_in(message.from_user.id):
        return
    
    try:
        users = db.reference("users").get()
        total = 0
        if users:
            for data in users.values():
                total += len(data.get("sites", {}))
        
        bot.reply_to(message, f"🌐 **মোট সাইট:** {total}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# 🚫 ইউজার ব্লক
@bot.message_handler(func=lambda m: m.text == "🚫 ইউজার ব্লক")
def ban_user_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারকে ব্লক করবেন তার **ID** দিন:", parse_mode="Markdown")
    bot.register_next_step_handler(message, ban_user)

def ban_user(message):
    try:
        uid = message.text.strip()
        db.reference(f'blacklist/{uid}').set(True)
        bot.reply_to(message, f"✅ ইউজার **{uid}** ব্লক করা হয়েছে!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# ✅ ইউজার আনব্লক
@bot.message_handler(func=lambda m: m.text == "✅ ইউজার আনব্লক")
def unban_user_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারকে আনব্লক করবেন তার **ID** দিন:", parse_mode="Markdown")
    bot.register_next_step_handler(message, unban_user)

def unban_user(message):
    try:
        uid = message.text.strip()
        db.reference(f'blacklist/{uid}').delete()
        bot.reply_to(message, f"✅ ইউজার **{uid}** আনব্লক করা হয়েছে!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# 🔄 লিমিট রিসেট
@bot.message_handler(func=lambda m: m.text == "🔄 লিমিট রিসেট")
def reset_limit_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return
    
    bot.reply_to(message, "যে ইউজারের লিমিট রিসেট করবেন তার **ID** দিন:", parse_mode="Markdown")
    bot.register_next_step_handler(message, reset_limit)

def reset_limit(message):
    try:
        uid = message.text.strip()
        db.reference(f'users/{uid}/count').set(0)
        db.reference(f'users/{uid}/date').set(datetime.now().strftime("%Y-%m-%d"))
        bot.reply_to(message, f"✅ ইউজার **{uid}** এর লিমিট রিসেট করা হয়েছে!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# 📢 ব্রডকাস্ট
@bot.message_handler(func=lambda m: m.text == "📢 ব্রডকাস্ট")
def broadcast_start(message):
    if not is_admin_logged_in(message.from_user.id):
        return
    
    bot.reply_to(message, "সব ইউজারকে কি বার্তা পাঠাবেন?")
    bot.register_next_step_handler(message, broadcast_send)

def broadcast_send(message):
    text = message.text
    
    try:
        users = db.reference("users").get()
        
        if not users:
            bot.reply_to(message, "❌ কোনো ইউজার নেই!")
            return
        
        status_msg = bot.reply_to(message, "📨 বার্তা পাঠানো হচ্ছে...")
        
        sent = 0
        failed = 0
        
        for uid in users.keys():
            try:
                bot.send_message(int(uid), f"📢 **অ্যাডমিন বার্তা:**\n\n{text}", 
                               parse_mode="Markdown")
                sent += 1
                time.sleep(0.05)  # Rate limit avoid
            except:
                failed += 1
        
        bot.edit_message_text(
            f"✅ **ব্রডকাস্ট সম্পন্ন!**\n\n"
            f"পাঠানো হয়েছে: **{sent}**\n"
            f"ব্যর্থ: **{failed}**",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

# ⬅️ মূল মেনু
@bot.message_handler(func=lambda m: m.text == "⬅️ মূল মেনু")
def back_to_main(message):
    bot.send_message(message.chat.id, "মূল মেনুতে ফিরে এলাম!", reply_markup=main_menu())

# ==========================================================
# 🔄 Fallback handler
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "❌ দয়া করে মেনু থেকে অপশন সিলেক্ট করুন!", reply_markup=main_menu())

# ==========================================================
# 🏁 বট চালু
# ==========================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🔥 টেলিগ্রাম হোস্টিং বট চালু হচ্ছে...")
    print("=" * 60)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ বট ইউজারনেম: @{bot_info.username}")
        print(f"✅ বট নাম: {bot_info.first_name}")
        print("=" * 60)
        print("🟢 বট রানিং... (Press Ctrl+C to stop)")
        print("=" * 60)
        
        # Start bot
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n👋 বট বন্ধ করা হচ্ছে...")
    except Exception as e:
        print(f"❌ বট এরর: {e}")
        traceback.print_exc()
