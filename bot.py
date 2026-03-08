# ==========================================================
# 🔥 ADVANCED TELEGRAM HOSTING BOT (FULLY FIXED & SECURE)
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
import hashlib
import hmac

from io import BytesIO
from datetime import datetime, timedelta
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from pathlib import Path

# ==========================================================
# 🔐 লোড এনভায়রনমেন্ট ভেরিয়েবল
# ==========================================================
load_dotenv()

# Required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

# Validate required variables
if not all([BOT_TOKEN, GITHUB_TOKEN, GITHUB_USERNAME, VERCEL_TOKEN, 
            ADMIN_PASSWORD, FIREBASE_DB_URL]):
    raise ValueError("Missing required environment variables!")

# ==========================================================
# 🚀 বট ইনিশিয়ালাইজেশন
# ==========================================================
bot = telebot.TeleBot(BOT_TOKEN)

# Firebase Init with error handling
try:
    # Check if firebase.json exists
    if os.path.exists("firebase.json"):
        cred = credentials.Certificate("firebase.json")
    else:
        # Try to get from environment variable
        firebase_cred_json = os.getenv("FIREBASE_CRED_JSON")
        if firebase_cred_json:
            import json
            cred_dict = json.loads(firebase_cred_json)
            cred = credentials.Certificate(cred_dict)
        else:
            raise FileNotFoundError("firebase.json not found!")
    
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DB_URL
    })
    print("✅ Firebase initialized successfully!")
except Exception as e:
    print(f"❌ Firebase init error: {e}")
    exit(1)

# ==========================================================
# 📊 রেট লিমিটিং ও ক্যাশ ব্যবস্থাপনা
# ==========================================================
class RateLimiter:
    def __init__(self):
        self.user_requests = {}
    
    def check_limit(self, user_id, limit_type='daily'):
        """চেক ইউজার রিকোয়েস্ট লিমিট"""
        now = datetime.now()
        user_key = f"{user_id}_{limit_type}"
        
        if user_key not in self.user_requests:
            self.user_requests[user_key] = []
        
        # পুরনো এন্ট্রি মুছে ফেলো
        self.user_requests[user_key] = [
            req_time for req_time in self.user_requests[user_key]
            if now - req_time < timedelta(hours=24 if limit_type == 'daily' else 1)
        ]
        
        limit = 5 if limit_type == 'daily' else 10  # 5 daily, 10 hourly
        return len(self.user_requests[user_key]) < limit
    
    def add_request(self, user_id, limit_type='daily'):
        """রিকোয়েস্ট যোগ করো"""
        user_key = f"{user_id}_{limit_type}"
        if user_key not in self.user_requests:
            self.user_requests[user_key] = []
        self.user_requests[user_key].append(datetime.now())

rate_limiter = RateLimiter()

# ==========================================================
# 🎛 মেনু সিস্টেম
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("🚀 হোস্ট ওয়েবসাইট", "📂 আমার সাইটসমূহ")
    markup.row("🌐 ডোমেইন যোগ করুন", "🗑 সাইট ডিলিট")
    markup.row("📊 দৈনিক লিমিট", "👑 অ্যাডমিন প্যানেল")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row("📊 মোট ইউজার", "🌍 মোট সাইট")
    markup.row("🚫 ইউজার ব্লক", "✅ ইউজার আনব্লক")
    markup.row("🔄 লিমিট রিসেট", "🗑 ইউজারের সাইট ডিলিট")
    markup.row("📢 ব্রডকাস্ট", "👥 অ্যাডমিন যোগ/রিমুভ")
    markup.row("📊 সিস্টেম স্ট্যাটাস", "⬅️ মূল মেনু")
    return markup

# ==========================================================
# 🔎 ভেরিফিকেশন সিস্টেম
# ==========================================================
def is_verified(user_id):
    """চেক করো ইউজার চ্যানেল ও গ্রুপে আছে কিনা"""
    try:
        # ব্ল্যাকলিস্ট চেক
        blacklist_ref = db.reference(f'blacklist/{user_id}')
        if blacklist_ref.get():
            return False
        
        ch = bot.get_chat_member(CHANNEL_ID, user_id)
        gp = bot.get_chat_member(GROUP_ID, user_id)
        return ch.status in ["member", "administrator", "creator"] and \
               gp.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Verification error: {e}")
        return False

# ==========================================================
# 📊 ডেইলি লিমিট চেক
# ==========================================================
def check_limit(user_id):
    """দৈনিক ব্যবহারের লিমিট চেক"""
    if not rate_limiter.check_limit(user_id, 'daily'):
        return False
    
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

def increase_count(user_id):
    """ব্যবহারের কাউন্ট বাড়াও"""
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    if data:
        ref.update({"count": data.get("count", 0) + 1})
    rate_limiter.add_request(user_id, 'daily')

# ==========================================================
# 🔐 সিকিউর জিপ এক্সট্রাক্ট
# ==========================================================
def secure_extract_zip(zip_content, extract_path):
    """সিকিউরলি জিপ ফাইল এক্সট্র্যাক্ট করো"""
    try:
        with zipfile.ZipFile(BytesIO(zip_content)) as zf:
            # ফাইল লিস্ট চেক করো
            bad_files = []
            for file_info in zf.infolist():
                # পাথ ট্রাভার্সাল চেক
                if '..' in file_info.filename or file_info.filename.startswith('/'):
                    bad_files.append(file_info.filename)
                    continue
                
                # ফাইল সাইজ চেক (100MB limit)
                if file_info.file_size > 100 * 1024 * 1024:
                    bad_files.append(file_info.filename)
                    continue
            
            if bad_files:
                raise Exception(f"Invalid files found: {bad_files}")
            
            # এক্সট্র্যাক্ট করো
            zf.extractall(extract_path)
            
            # index.html চেক করো
            if not os.path.exists(os.path.join(extract_path, 'index.html')):
                # খোঁজো কোনো HTML ফাইল
                html_files = list(Path(extract_path).rglob('*.html'))
                if html_files:
                    # প্রথম HTML ফাইলকে কপি করো index.html হিসেবে
                    shutil.copy(html_files[0], os.path.join(extract_path, 'index.html'))
                else:
                    raise Exception("No HTML file found!")
        
        return True
    except Exception as e:
        print(f"Extraction error: {e}")
        return False

# ==========================================================
# 🚀 স্টার্ট কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    
    if not is_verified(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 চ্যানেল", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}"),
            InlineKeyboardButton("👥 গ্রুপ", url=f"https://t.me/c/{str(GROUP_ID)[4:]}")
        )
        bot.reply_to(
            msg, 
            "❌ প্রথমে আমাদের চ্যানেল ও গ্রুপে জয়েন করুন!",
            reply_markup=markup
        )
        return
    
    welcome_text = (
        f"👋 স্বাগতম {msg.from_user.first_name}!\n\n"
        "🎯 এই বটের মাধ্যমে আপনি সহজেই আপনার ওয়েবসাইট হোস্ট করতে পারবেন।\n\n"
        "📌 কীভাবে ব্যবহার করবেন:\n"
        "1️⃣ আপনার ওয়েবসাইটের ফাইল জিপ করুন\n"
        "2️⃣ জিপ ফাইলটি বটে আপলোড করুন\n"
        "3️⃣ বট অটোমেটিকভাবে GitHub ও Vercel এ ডিপ্লয় করবে\n"
        "4️⃣ আপনি একটি লাইভ লিংক পাবেন\n\n"
        "⚠️ দৈনিক ৫টি সাইট হোস্ট করা যাবে!"
    )
    
    bot.send_message(msg.chat.id, welcome_text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(msg):
    user_id = msg.from_user.id
    
    # ভেরিফিকেশন চেক
    if not is_verified(user_id):
        bot.reply_to(msg, "❌ প্রথমে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    # ফাইল টাইপ চেক
    if not msg.document.file_name.endswith('.zip'):
        bot.reply_to(msg, "❌ শুধুমাত্র ZIP ফাইল অনুমোদিত!")
        return
    
    # লিমিট চেক
    if not check_limit(user_id):
        bot.reply_to(msg, "❌ আপনার দৈনিক লিমিট শেষ! (৫টি/দিন)")
        return
    
    # সাইজ চেক (50MB)
    if msg.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(msg, "❌ ফাইল সাইজ ৫০MB এর কম হতে হবে!")
        return
    
    status_msg = bot.reply_to(msg, "⏳ ডাউনলোড শুরু হচ্ছে...")
    
    try:
        # ডাউনলোড করো
        file_info = bot.get_file(msg.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 জিপ ফাইল এক্সট্র্যাক্ট করা হচ্ছে...", 
                            msg.chat.id, status_msg.message_id)
        
        # টেম্প ফোল্ডার তৈরি করো
        with tempfile.TemporaryDirectory() as temp_dir:
            # সিকিউর এক্সট্র্যাক্ট
            if not secure_extract_zip(downloaded, temp_dir):
                bot.edit_message_text("❌ জিপ ফাইল এক্সট্র্যাক্ট করতে সমস্যা!", 
                                    msg.chat.id, status_msg.message_id)
                return
            
            # ইউনিক রিপো নাম জেনারেট করো
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            # গিটহাব রিপোজিটরি তৈরি করো
            bot.edit_message_text("🔧 GitHub রিপোজিটরি তৈরি হচ্ছে...", 
                                msg.chat.id, status_msg.message_id)
            
            if not create_github_repo(repo_name, temp_dir):
                bot.edit_message_text("❌ GitHub রিপোজিটরি তৈরি করতে সমস্যা!", 
                                    msg.chat.id, status_msg.message_id)
                return
            
            # ভার্সেল ডিপ্লয়
            bot.edit_message_text("🚀 Vercel এ ডিপ্লয় হচ্ছে...", 
                                msg.chat.id, status_msg.message_id)
            
            live_url = deploy_to_vercel(repo_name)
            if not live_url:
                bot.edit_message_text("❌ Vercel ডিপ্লয় করতে সমস্যা!", 
                                    msg.chat.id, status_msg.message_id)
                return
            
            # ফায়ারবেসে সেভ করো
            save_to_firebase(user_id, repo_name, live_url)
            
            # কাউন্ট বাড়াও
            increase_count(user_id)
            
            # সাফল্যের বার্তা
            success_text = (
                f"✅ সফলভাবে ডিপ্লয় হয়েছে!\n\n"
                f"🌐 লাইভ URL:\n{live_url}\n\n"
                f"📂 প্রোজেক্ট নাম: {repo_name}\n"
                f"📊 ব্যবহৃত: {get_user_count(user_id)}/৫\n\n"
                f"💡 টিপস:\n"
                f"• কাস্টম ডোমেইন যোগ করুন: 'ডোমেইন যোগ করুন' মেনু থেকে\n"
                f"• GitHub: https://github.com/{GITHUB_USERNAME}/{repo_name}"
            )
            
            bot.edit_message_text(success_text, msg.chat.id, status_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ সমস্যা হয়েছে: {str(e)[:100]}", 
                            msg.chat.id, status_msg.message_id)
        print(f"Error: {e}")

def create_github_repo(repo_name, local_path):
    """গিটহাব রিপোজিটরি তৈরি করো"""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # রিপোজিটরি তৈরি
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
        return False
    
    # ফাইল আপলোড
    for root, dirs, files in os.walk(local_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, local_path)
            
            with open(file_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
            
            # ফাইল আপলোড
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
                return False
    
    return True

def deploy_to_vercel(repo_name):
    """ভার্সেলে ডিপ্লয় করো"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    # প্রোজেক্ট তৈরি
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
        return None
    
    # ডিপ্লয়মেন্ট
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
        return None
    
    # ডিপ্লয়মেন্ট স্ট্যাটাস চেক
    deploy_id = r.json().get("id")
    max_attempts = 30
    attempts = 0
    
    while attempts < max_attempts:
        time.sleep(5)
        r = requests.get(
            f"https://api.vercel.com/v13/deployments/{deploy_id}",
            headers=headers
        )
        
        status = r.json().get("readyState")
        if status == "READY":
            return f"https://{repo_name}.vercel.app"
        elif status in ["ERROR", "CANCELED"]:
            return None
        
        attempts += 1
    
    return None

def save_to_firebase(user_id, repo_name, live_url):
    """ফায়ারবেসে ডেটা সেভ করো"""
    ref = db.reference(f'users/{user_id}/sites/{repo_name}')
    ref.set({
        "repo": repo_name,
        "live_url": live_url,
        "github_url": f"https://github.com/{GITHUB_USERNAME}/{repo_name}",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active"
    })

def get_user_count(user_id):
    """ইউজারের কাউন্ট দেখাও"""
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    return data.get("count", 0) if data else 0

# ==========================================================
# 📂 আমার সাইটসমূহ
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 আমার সাইটসমূহ")
def my_sites(msg):
    if not is_verified(msg.from_user.id):
        bot.reply_to(msg, "❌ প্রথমে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    ref = db.reference(f'users/{msg.from_user.id}/sites')
    sites = ref.get()
    
    if not sites:
        bot.reply_to(msg, "❌ আপনার কোনো সাইট নেই!")
        return
    
    text = "🌐 আপনার সাইটসমূহ:\n\n"
    for name, data in sites.items():
        text += f"📁 {name}\n"
        text += f"🔗 {data.get('live_url')}\n"
        text += f"📅 {data.get('created')}\n\n"
    
    # পেজিনেশন
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            bot.send_message(msg.chat.id, part)
    else:
        bot.send_message(msg.chat.id, text)

# ==========================================================
# 🌐 ডোমেইন যোগ করুন
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ডোমেইন যোগ করুন")
def add_domain_start(msg):
    if not is_verified(msg.from_user.id):
        bot.reply_to(msg, "❌ প্রথমে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    bot.reply_to(msg, "🔍 আপনার প্রোজেক্টের নাম লিখুন:")
    bot.register_next_step_handler(msg, process_domain_project)

def process_domain_project(msg):
    project = msg.text.strip()
    bot.reply_to(msg, "🌐 আপনার ডোমেইন নাম লিখুন (যেমন: example.com):")
    bot.register_next_step_handler(msg, lambda m: add_domain_to_vercel(m, project))

def add_domain_to_vercel(msg, project):
    domain = msg.text.strip().lower()
    
    # ডোমেইন ভ্যালিডেশন
    if not domain or '.' not in domain:
        bot.reply_to(msg, "❌ ভ্যালিড ডোমেইন দিন!")
        return
    
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    # ডোমেইন যোগ
    r = requests.post(
        f"https://api.vercel.com/v9/projects/{project}/domains",
        headers=headers,
        json={"name": domain}
    )
    
    if r.status_code in [200, 201]:
        # DNS রেকর্ড দেখাও
        dns_text = (
            f"✅ ডোমেইন যোগ হয়েছে!\n\n"
            f"📌 আপনার DNS সেটিংসে এই রেকর্ড যোগ করুন:\n\n"
            f"টাইপ: CNAME\n"
            f"নাম: @ অথবা www\n"
            f"ভ্যালু: cname.vercel-dns.com\n\n"
            f"⚠️ DNS প্রপাগেট হতে ২৪-৪৮ ঘন্টা সময় লাগতে পারে।"
        )
        bot.reply_to(msg, dns_text)
    else:
        bot.reply_to(msg, f"❌ ডোমেইন যোগ করতে সমস্যা! {r.json().get('error', {}).get('message', '')}")

# ==========================================================
# 🗑 সাইট ডিলিট
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 সাইট ডিলিট")
def delete_site_start(msg):
    if not is_verified(msg.from_user.id):
        bot.reply_to(msg, "❌ প্রথমে চ্যানেল ও গ্রুপে জয়েন করুন!")
        return
    
    # ইউজারের সাইট লিস্ট দেখাও
    ref = db.reference(f'users/{msg.from_user.id}/sites')
    sites = ref.get()
    
    if not sites:
        bot.reply_to(msg, "❌ আপনার কোনো সাইট নেই!")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for site_name in sites.keys():
        markup.add(InlineKeyboardButton(
            f"🗑 {site_name}", 
            callback_data=f"delete_{site_name}"
        ))
    
    bot.send_message(msg.chat.id, "কোন সাইট ডিলিট করতে চান?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_site_callback(call):
    site_name = call.data.replace('delete_', '')
    user_id = call.from_user.id
    
    # ডিলিট কনফার্মেশন
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ হ্যাঁ", callback_data=f"confirm_{site_name}"),
        InlineKeyboardButton("❌ না", callback_data="cancel_delete")
    )
    
    bot.edit_message_text(
        f"আপনি কি {site_name} ডিলিট করতে চান?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=mark
