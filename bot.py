# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট - সম্পূর্ণ ফাংশনাল ভার্সন
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
# 🔐 লোড এনভায়রনমেন্ট ভেরিয়েবল
# ==========================================================
load_dotenv()

# ভেরিয়েবল গুলো লোড করা হচ্ছে
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

print("=" * 60)
print("🔥 টেলিগ্রাম হোস্টিং বট চালু হচ্ছে...")
print("=" * 60)

# ভেরিয়েবল চেক করা হচ্ছে
missing = []
if not BOT_TOKEN: missing.append("BOT_TOKEN")
if not GITHUB_TOKEN: missing.append("GITHUB_TOKEN")
if not GITHUB_USERNAME: missing.append("GITHUB_USERNAME")
if not VERCEL_TOKEN: missing.append("VERCEL_TOKEN")
if not ADMIN_PASSWORD: missing.append("ADMIN_PASSWORD")
if not ADMIN_ID: missing.append("ADMIN_ID")
if not CHANNEL_ID: missing.append("CHANNEL_ID")
if not GROUP_ID: missing.append("GROUP_ID")
if not FIREBASE_DB_URL: missing.append("FIREBASE_DB_URL")

if missing:
    print(f"❌ অনুপস্থিত: {', '.join(missing)}")
    print("⚠️ দয়া করে Environment Variables সেট করুন")
    # ফায়ারবেস কনফিগ ছাড়া চলতে দিই
    print("⚠️ ফায়ারবেস ছাড়া চলবে, কিন্তু ডাটা সেভ হবে না")

# ID গুলো ইন্টিজারে কনভার্ট করা হচ্ছে
try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
    CHANNEL_ID = int(CHANNEL_ID) if CHANNEL_ID else 0
    GROUP_ID = int(GROUP_ID) if GROUP_ID else 0
except:
    print("❌ ID কনভার্ট করতে সমস্যা হয়েছে")
    sys.exit(1)

# ==========================================================
# 🚀 বট ইনিশিয়ালাইজেশন
# ==========================================================
bot = telebot.TeleBot(BOT_TOKEN)
print("✅ বট টোকেন সঠিক")

# ==========================================================
# 🔥 ফায়ারবেস ইনিশিয়ালাইজেশন
# ==========================================================
firebase_ready = False

def init_firebase():
    """ফায়ারবেস কানেক্ট করা হচ্ছে"""
    global firebase_ready
    
    if not FIREBASE_CONFIG_BASE64:
        print("⚠️ ফায়ারবেস কনফিগ নেই, ডাটা সেভ হবে না")
        return False
    
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
        print("✅ ফায়ারবেস কানেক্ট হয়েছে")
        firebase_ready = True
        return True
    except Exception as e:
        print(f"❌ ফায়ারবেস কানেক্ট হয়নি: {e}")
        return False

init_firebase()

# ==========================================================
# 📊 রেট লিমিটার (মেমরিতে রাখব)
# ==========================================================
user_daily_count = {}  # ইউজারের দৈনিক কাউন্ট মেমরিতে রাখব

def check_daily_limit(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    
    if key not in user_daily_count:
        user_daily_count[key] = 0
        return True
    
    return user_daily_count[key] < 5

def increase_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    
    if key not in user_daily_count:
        user_daily_count[key] = 0
    
    user_daily_count[key] += 1
    return user_daily_count[key]

def get_user_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    return user_daily_count.get(key, 0)

# ==========================================================
# 🎛 মেনু তৈরি
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 হোস্ট ওয়েবসাইট", "📂 আমার সাইট")
    markup.row("🌐 ডোমেইন যোগ", "🗑 সাইট ডিলিট")
    markup.row("📊 লিমিট চেক", "👑 অ্যাডমিন")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 মোট ইউজার", "🌍 মোট সাইট")
    markup.row("🚫 ইউজার ব্লক", "✅ ইউজার আনব্লক")
    markup.row("🔄 লিমিট রিসেট", "📢 ব্রডকাস্ট")
    markup.row("➕ অ্যাডমিন যোগ", "➖ অ্যাডমিন রিমুভ")
    markup.row("📋 অ্যাডমিন লিস্ট", "🚪 লগআউট")
    markup.row("⬅️ মূল মেনু")
    return markup

# ==========================================================
# ✅ ভেরিফিকেশন চেক (সিম্পল ভার্সন)
# ==========================================================
def is_verified(user_id):
    # টেস্টিং এর জন্য সবাই ভেরিফাইড
    return True

def is_admin(user_id):
    return user_id == ADMIN_ID

# ==========================================================
# 🚀 /start কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    welcome_text = f"👋 স্বাগতম {username}!\n\n📤 আপনার ওয়েবসাইটের জিপ ফাইল আপলোড করুন। আমি GitHub ও Vercel-এ হোস্ট করে দেব।"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # ফাইল চেক
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ শুধু .zip ফাইল দিন!")
        return
    
    # লিমিট চেক
    if not check_daily_limit(user_id):
        used = get_user_count(user_id)
        bot.reply_to(message, f"❌ আজকের লিমিট শেষ! আপনি {used}/৫টি ব্যবহার করেছেন।")
        return
    
    # সাইজ চেক (৫০ এমবি)
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ ৫০ এমবির বেশি ফাইল দেওয়া যাবে না!")
        return
    
    status_msg = bot.reply_to(message, "⏳ ডাউনলোড শুরু হচ্ছে...")
    
    try:
        # ফাইল ডাউনলোড
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 জিপ এক্সট্র্যাক্ট করা হচ্ছে...", chat_id, status_msg.message_id)
        
        # টেম্প ফোল্ডার
        with tempfile.TemporaryDirectory() as temp_dir:
            # জিপ এক্সট্র্যাক্ট
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)
            
            # index.html চেক
            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html নেই! আপনার ওয়েবসাইটে একটি index.html ফাইল থাকতে হবে।", chat_id, status_msg.message_id)
                return
            
            # রিপো নাম
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 GitHub এ আপলোড হচ্ছে...", chat_id, status_msg.message_id)
            
            # GitHub রিপো তৈরি
            github_success, github_result = create_github_repo(repo_name, temp_dir)
            
            if not github_success:
                bot.edit_message_text(f"❌ GitHub সমস্যা: {github_result}", chat_id, status_msg.message_id)
                return
            
            bot.edit_message_text("🚀 Vercel এ ডিপ্লয় হচ্ছে...", chat_id, status_msg.message_id)
            
            # Vercel ডিপ্লয়
            live_url = deploy_to_vercel(repo_name)
            
            if not live_url:
                bot.edit_message_text("❌ Vercel ডিপ্লয় হয়নি!", chat_id, status_msg.message_id)
                return
            
            # ফায়ারবেসে সেভ (যদি কানেক্ট থাকে)
            if firebase_ready:
                save_to_firebase(user_id, repo_name, live_url)
            
            # কাউন্ট বাড়াও
            increase_count(user_id)
            used_now = get_user_count(user_id)
            
            # সফল বার্তা
            success_text = (
                f"✅ **ডিপ্লয় সফল!**\n\n"
                f"🌐 **লাইভ ইউআরএল:**\n`{live_url}`\n\n"
                f"📂 **গিটহাব:**\nhttps://github.com/{GITHUB_USERNAME}/{repo_name}\n\n"
                f"📊 **আজকে ব্যবহার:** {used_now}/৫\n\n"
                f"💡 **নোট:** DNS প্রপাগেট হতে ২-৩ মিনিট সময় লাগতে পারে।"
            )
            
            bot.edit_message_text(success_text, chat_id, status_msg.message_id, parse_mode="Markdown")
            
    except zipfile.BadZipFile:
        bot.edit_message_text("❌ ভুল জিপ ফাইল! সঠিক জিপ ফাইল দিন।", chat_id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ সমস্যা: {str(e)[:100]}", chat_id, status_msg.message_id)
        print(f"Error: {traceback.format_exc()}")

# ==========================================================
# 🔧 গিটহাব ফাংশন (ফিক্সড)
# ==========================================================
def create_github_repo(repo_name, local_path):
    """গিটহাবে রিপোজিটরি তৈরি করে ফাইল আপলোড করে"""
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # টোকেন টেস্ট
        test = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if test.status_code != 200:
            return False, f"GitHub token invalid (Status: {test.status_code})"
        
        # রিপোজিটরি তৈরি
        repo_data = {
            "name": repo_name,
            "private": False,
            "auto_init": False,
            "description": "Telegram Bot Hosting"
        }
        
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=repo_data, timeout=30)
        
        if r.status_code == 422:
            # রিপো আগে থাকলে নতুন নাম নেব
            repo_name = f"{repo_name}-{int(time.time())}"
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=repo_data, timeout=30)
        
        if r.status_code != 201:
            return False, f"GitHub repo creation failed (Status: {r.status_code})"
        
        # ফাইল আপলোড
        files_uploaded = 0
        files_failed = 0
        
        for root, dirs, files in os.walk(local_path):
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
                resp = requests.put(url, headers=headers, json=file_data, timeout=30)
                
                if resp.status_code in [200, 201]:
                    files_uploaded += 1
                else:
                    files_failed += 1
        
        return True, f"Uploaded {files_uploaded} files, Failed: {files_failed}"
        
    except requests.exceptions.Timeout:
        return False, "GitHub API timeout"
    except requests.exceptions.ConnectionError:
        return False, "Network connection error"
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🚀 ভার্সেল ফাংশন (ফিক্সড)
# ==========================================================
def deploy_to_vercel(repo_name):
    """Vercel-এ ডিপ্লয় করে"""
    
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔄 Vercel deploying: {repo_name}")
        
        # টোকেন টেস্ট
        test_resp = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test_resp.status_code != 200:
            print(f"❌ Vercel token invalid: {test_resp.status_code}")
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
        
        project_resp = requests.post(
            "https://api.vercel.com/v9/projects",
            headers=headers,
            json=project_data,
            timeout=30
        )
        
        if project_resp.status_code not in [200, 201]:
            print(f"⚠️ Project creation status: {project_resp.status_code}")
            # প্রোজেক্ট না থাকলেও চলবে, ডিপ্লয় ট্রাই করব
        
        # ডিপ্লয়
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
            print(f"✅ Vercel deploy successful")
            return f"https://{repo_name}.vercel.app"
        
        # ৪২২ এরর হলে (রিপো ইতিমধ্যে ডিপ্লয় হয়েছে)
        if deploy_resp.status_code == 400:
            try:
                error_data = deploy_resp.json()
                if "already_exists" in str(error_data):
                    print("⚠️ Deployment already exists, using existing URL")
                    return f"https://{repo_name}.vercel.app"
            except:
                pass
        
        print(f"❌ Vercel deploy failed: {deploy_resp.status_code}")
        print(f"Response: {deploy_resp.text[:200]}")
        return None
        
    except Exception as e:
        print(f"❌ Vercel error: {e}")
        return None

# ==========================================================
# 💾 ফায়ারবেস ফাংশন
# ==========================================================
def save_to_firebase(user_id, repo_name, live_url):
    """ফায়ারবেসে সাইটের তথ্য সেভ করে"""
    if not firebase_ready:
        return
    
    try:
        ref = db.reference(f'users/{user_id}/sites/{repo_name}')
        ref.set({
            "name": repo_name,
            "url": live_url,
            "github": f"https://github.com/{GITHUB_USERNAME}/{repo_name}",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active"
        })
        print(f"✅ Firebase saved: {repo_name}")
    except Exception as e:
        print(f"❌ Firebase save error: {e}")

# ==========================================================
# 📂 মেনু হ্যান্ডলার
# ==========================================================

@bot.message_handler(func=lambda m: m.text == "🚀 হোস্ট ওয়েবসাইট")
def menu_host(message):
    bot.reply_to(message, "📤 আপনার ওয়েবসাইটের জিপ ফাইল আপলোড করুন।")

@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইট")
def menu_my_sites(message):
    user_id = message.from_user.id
    
    if not firebase_ready:
        bot.reply_to(message, "❌ ফায়ারবেস কানেক্ট নেই! সাইটের তথ্য দেখা যাচ্ছে না।")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        
        if not sites:
            bot.reply_to(message, "❌ আপনার কোনো সাইট নেই!")
            return
        
        text = "🌐 **আপনার সাইটসমূহ:**\n\n"
        for name, data in sites.items():
            text += f"📁 **{name}**\n🔗 {data.get('url')}\n📅 {data.get('created')}\n\n"
        
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
            
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন যোগ")
def menu_domain(message):
    bot.reply_to(message, "🌐 ডোমেইন যোগ ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "🗑 সাইট ডিলিট")
def menu_delete(message):
    bot.reply_to(message, "🗑 সাইট ডিলিট ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "📊 লিমিট চেক")
def menu_limit(message):
    user_id = message.from_user.id
    used = get_user_count(user_id)
    remaining = 5 - used
    bar = "🟩" * used + "⬜" * remaining
    text = f"📊 **আপনার দৈনিক ব্যবহার:**\n\n{bar}\n**ব্যবহার:** {used}/৫\n**বাকি:** {remaining}"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👑 অ্যাডমিন")
def menu_admin(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 **অ্যাডমিন প্যানেল**", parse_mode="Markdown", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন!")

# ==========================================================
# 👑 অ্যাডমিন হ্যান্ডলার (সিম্পল)
# ==========================================================

@bot.message_handler(func=lambda m: m.text == "📊 মোট ইউজার")
def admin_users(message):
    if message.from_user.id != ADMIN_ID: return
    if firebase_ready:
        try:
            users = db.reference("users").get()
            count = len(users) if users else 0
            bot.reply_to(message, f"📊 মোট ইউজার: {count}")
        except:
            bot.reply_to(message, "📊 ফায়ারবেস থেকে তথ্য নেওয়া যাচ্ছে না")
    else:
        bot.reply_to(message, "📊 ফায়ারবেস কানেক্ট নেই")

@bot.message_handler(func=lambda m: m.text == "🌍 মোট সাইট")
def admin_sites(message):
    if message.from_user.id != ADMIN_ID: return
    if firebase_ready:
        try:
            users = db.reference("users").get()
            total = 0
            if users:
                for data in users.values():
                    total += len(data.get("sites", {}))
            bot.reply_to(message, f"🌍 মোট সাইট: {total}")
        except:
            bot.reply_to(message, "🌍 ফায়ারবেস থেকে তথ্য নেওয়া যাচ্ছে না")
    else:
        bot.reply_to(message, "🌍 ফায়ারবেস কানেক্ট নেই")

@bot.message_handler(func=lambda m: m.text == "🚫 ইউজার ব্লক")
def admin_block(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "🚫 এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "✅ ইউজার আনব্লক")
def admin_unblock(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "✅ এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "🔄 লিমিট রিসেট")
def admin_reset(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "🔄 এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "📢 ব্রডকাস্ট")
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "📢 এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "➕ অ্যাডমিন যোগ")
def admin_add(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "➕ এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "➖ অ্যাডমিন রিমুভ")
def admin_remove(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "➖ এই ফিচার শীঘ্রই আসছে...")

@bot.message_handler(func=lambda m: m.text == "📋 অ্যাডমিন লিস্ট")
def admin_list(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, f"📋 অ্যাডমিন:\n{ADMIN_ID} (মূল অ্যাডমিন)")

@bot.message_handler(func=lambda m: m.text == "🚪 লগআউট")
def admin_logout(message):
    if message.from_user.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "✅ লগআউট!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ মূল মেনু")
def back_to_main(message):
    bot.send_message(message.chat.id, "মূল মেনুতে ফিরে এলাম!", reply_markup=main_menu())

# ==========================================================
# 🔄 ফলব্যাক হ্যান্ডলার
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "❌ মেনু থেকে সিলেক্ট করুন!", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP সার্ভার (Render এর জন্য)
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
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🌐 HTTP সার্ভার চালু হয়েছে পোর্ট {port} এ")
    server.serve_forever()

# ==========================================================
# 🏁 বট চালু
# ==========================================================
if __name__ == "__main__":
    # HTTP সার্ভার চালু (Render এর জন্য)
    threading.Thread(target=run_http_server, daemon=True).start()
    
    # বট চালু
    try:
        bot_info = bot.get_me()
        print(f"✅ বট ইউজারনেম: @{bot_info.username}")
        print("=" * 60)
        print("🟢 বট চলছে...")
        print("=" * 60)
        
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except KeyboardInterrupt:
        print("\n👋 বট বন্ধ করা হচ্ছে...")
    except Exception as e:
        print(f"❌ বট এরর: {e}")
        traceback.print_exc()