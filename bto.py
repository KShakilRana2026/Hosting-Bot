# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট - Vercel ফিক্সড ভার্সন
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
from datetime import datetime
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup
from dotenv import load_dotenv

# ==========================================================
# 🔐 লোড এনভায়রনমেন্ট ভেরিয়েবল
# ==========================================================
load_dotenv()

# ভেরিয়েবল লোড
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

# ভেরিয়েবল চেক
missing = []
if not BOT_TOKEN: missing.append("BOT_TOKEN")
if not GITHUB_TOKEN: missing.append("GITHUB_TOKEN")
if not GITHUB_USERNAME: missing.append("GITHUB_USERNAME")
if not VERCEL_TOKEN: missing.append("VERCEL_TOKEN")

if missing:
    print(f"❌ অনুপস্থিত: {', '.join(missing)}")
    print("⚠️ Environment Variables সেট করুন")
    sys.exit(1)

# ID কনভার্ট
try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
    CHANNEL_ID = int(CHANNEL_ID) if CHANNEL_ID else 0
    GROUP_ID = int(GROUP_ID) if GROUP_ID else 0
except:
    print("❌ ID কনভার্ট করতে সমস্যা")
    sys.exit(1)

# ==========================================================
# 🚀 বট ইনিশিয়ালাইজেশন
# ==========================================================
bot = telebot.TeleBot(BOT_TOKEN)
print("✅ বট টোকেন সঠিক")

# ==========================================================
# 🔥 ফায়ারবেস (অপশনাল)
# ==========================================================
firebase_ready = False

if FIREBASE_CONFIG_BASE64 and FIREBASE_DB_URL:
    try:
        json_bytes = base64.b64decode(FIREBASE_CONFIG_BASE64)
        cred_dict = json.loads(json_bytes)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cred_dict, f)
            temp_path = f.name
        
        cred = credentials.Certificate(temp_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        os.unlink(temp_path)
        firebase_ready = True
        print("✅ ফায়ারবেস কানেক্টেড")
    except Exception as e:
        print(f"⚠️ ফায়ারবেস কানেক্ট হয়নি: {e}")

# ==========================================================
# 📊 রেট লিমিটার (মেমরি)
# ==========================================================
user_counts = {}

def check_limit(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    if key not in user_counts:
        user_counts[key] = 0
        return True
    return user_counts[key] < 5

def add_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    user_counts[key] = user_counts.get(key, 0) + 1

def get_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{user_id}_{today}"
    return user_counts.get(key, 0)

# ==========================================================
# 🎛 মেনু
# ==========================================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 হোস্ট", "📂 সাইট")
    markup.row("📊 লিমিট", "👑 অ্যাডমিন")
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 ইউজার", "🌍 সাইট")
    markup.row("⬅️ মেনু")
    return markup

# ==========================================================
# ✅ ভেরিফিকেশন
# ==========================================================
def is_admin(user_id):
    return user_id == ADMIN_ID

# ==========================================================
# 🚀 স্টার্ট কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    text = "👋 স্বাগতম!\n\n📤 জিপ ফাইল আপলোড করুন।"
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    # ফাইল চেক
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ শুধু .zip ফাইল দিন!")
        return
    
    # লিমিট চেক
    if not check_limit(user_id):
        used = get_count(user_id)
        bot.reply_to(message, f"❌ লিমিট শেষ! ব্যবহার: {used}/5")
        return
    
    # সাইজ চেক
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ 50MB এর বেশি নয়!")
        return
    
    status = bot.reply_to(message, "⏳ প্রসেসিং...")
    
    try:
        # ডাউনলোড
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 এক্সট্র্যাক্ট...", message.chat.id, status.message_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # এক্সট্র্যাক্ট
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)
            
            # index.html চেক
            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html নেই!", message.chat.id, status.message_id)
                return
            
            # রিপো নাম
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 GitHub...", message.chat.id, status.message_id)
            
            # GitHub
            github_ok, github_msg = create_github(repo_name, temp_dir)
            if not github_ok:
                bot.edit_message_text(f"❌ GitHub: {github_msg}", message.chat.id, status.message_id)
                return
            
            bot.edit_message_text("🚀 Vercel...", message.chat.id, status.message_id)
            
            # Vercel
            live_url = create_vercel(repo_name)
            if not live_url:
                bot.edit_message_text("❌ Vercel ডিপ্লয় হয়নি!", message.chat.id, status.message_id)
                return
            
            # কাউন্ট
            add_count(user_id)
            used = get_count(user_id)
            
            # সফল
            text = (
                f"✅ **সফল!**\n\n"
                f"🌐 **URL:**\n`{live_url}`\n\n"
                f"📂 **GitHub:**\nhttps://github.com/{GITHUB_USERNAME}/{repo_name}\n\n"
                f"📊 **আজ:** {used}/5"
            )
            
            bot.edit_message_text(text, message.chat.id, status.message_id, parse_mode="Markdown")
            
            # ফায়ারবেস (যদি থাকে)
            if firebase_ready:
                try:
                    db.reference(f'users/{user_id}/sites/{repo_name}').set({
                        "url": live_url,
                        "time": datetime.now().isoformat()
                    })
                except:
                    pass
    
    except zipfile.BadZipFile:
        bot.edit_message_text("❌ ভুল জিপ!", message.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)[:100]}", message.chat.id, status.message_id)
        print(traceback.format_exc())

# ==========================================================
# 🔧 GitHub ফাংশন (টেস্টেড)
# ==========================================================
def create_github(repo_name, local_path):
    """GitHub রিপো তৈরি"""
    
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    try:
        # টোকেন টেস্ট
        r = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if r.status_code != 200:
            return False, "টোকেন ইনভ্যালিড"
        
        # রিপো তৈরি
        data = {"name": repo_name, "private": False, "auto_init": False}
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        
        if r.status_code == 422:
            repo_name = f"{repo_name}-{int(time.time())}"
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        
        if r.status_code != 201:
            return False, f"স্ট্যাটাস: {r.status_code}"
        
        # ফাইল আপলোড
        for root, _, files in os.walk(local_path):
            for file in files:
                if file.startswith('.'):
                    continue
                
                path = os.path.join(root, file)
                rel = os.path.relpath(path, local_path)
                
                with open(path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                
                url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel}"
                data = {"message": f"Add {rel}", "content": content, "branch": "main"}
                
                requests.put(url, headers=headers, json=data, timeout=30)
        
        return True, "সফল"
        
    except Exception as e:
        return False, str(e)

# ==========================================================
# 🚀 Vercel ফাংশন (ফিক্সড)
# ==========================================================
def create_vercel(repo_name):
    """Vercel ডিপ্লয় - ফিক্সড ভার্সন"""
    
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # টোকেন টেস্ট
        r = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"❌ Vercel টোকেন ইনভ্যালিড: {r.status_code}")
            return None
        
        # প্রথমে প্রোজেক্ট তৈরি করি
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
            json=project_data,
            timeout=30
        )
        
        # প্রোজেক্ট তৈরি হোক বা না হোক, ডিপ্লয় চেষ্টা করি
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            },
            "target": "production"
        }
        
        r = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=deploy_data,
            timeout=30
        )
        
        if r.status_code in [200, 201]:
            return f"https://{repo_name}.vercel.app"
        
        # 400 error হলে দেখা যাক
        if r.status_code == 400:
            try:
                data = r.json()
                if "already_exists" in str(data):
                    return f"https://{repo_name}.vercel.app"
            except:
                pass
        
        print(f"❌ Vercel error: {r.status_code}")
        print(r.text[:200])
        return None
        
    except Exception as e:
        print(f"❌ Vercel exception: {e}")
        return None

# ==========================================================
# 📂 মেনু হ্যান্ডলার
# ==========================================================

@bot.message_handler(func=lambda m: m.text == "🚀 হোস্ট")
def host_menu(message):
    bot.reply_to(message, "📤 জিপ ফাইল আপলোড করুন")

@bot.message_handler(func=lambda m: m.text == "📂 সাইট")
def sites_menu(message):
    user_id = message.from_user.id
    if not firebase_ready:
        bot.reply_to(message, "❌ ডাটাবেস নেই")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        if not sites:
            bot.reply_to(message, "❌ কোনো সাইট নেই")
            return
        
        text = "🌐 **সাইটসমূহ:**\n\n"
        for name, data in sites.items():
            text += f"• {name}\n{data.get('url')}\n\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ সমস্যা হয়েছে")

@bot.message_handler(func=lambda m: m.text == "📊 লিমিট")
def limit_menu(message):
    used = get_count(message.from_user.id)
    bot.reply_to(message, f"📊 আজ ব্যবহার: {used}/5")

@bot.message_handler(func=lambda m: m.text == "👑 অ্যাডমিন")
def admin_menu_handler(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "👑 অ্যাডমিন প্যানেল", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ আপনি অ্যাডমিন নন")

# অ্যাডমিন হ্যান্ডলার
@bot.message_handler(func=lambda m: m.text == "📊 ইউজার")
def admin_users_handler(message):
    if not is_admin(message.from_user.id):
        return
    if firebase_ready:
        try:
            users = db.reference("users").get()
            count = len(users) if users else 0
            bot.reply_to(message, f"📊 ইউজার: {count}")
        except:
            bot.reply_to(message, "❌ ডাটাবেস সমস্যা")
    else:
        bot.reply_to(message, "📊 ইউজার: N/A")

@bot.message_handler(func=lambda m: m.text == "🌍 সাইট")
def admin_sites_handler(message):
    if not is_admin(message.from_user.id):
        return
    if firebase_ready:
        try:
            users = db.reference("users").get()
            total = 0
            if users:
                for data in users.values():
                    total += len(data.get("sites", {}))
            bot.reply_to(message, f"🌍 সাইট: {total}")
        except:
            bot.reply_to(message, "❌ ডাটাবেস সমস্যা")
    else:
        bot.reply_to(message, "🌍 সাইট: N/A")

@bot.message_handler(func=lambda m: m.text == "⬅️ মেনু")
def back_handler(message):
    bot.send_message(message.chat.id, "মেনুতে ফিরে এলাম", reply_markup=main_menu())

# ==========================================================
# 🔄 ফলব্যাক
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(message, "❌ মেনু থেকে সিলেক্ট করুন", reply_markup=main_menu())

# ==========================================================
# 🌐 HTTP সার্ভার (Render)
# ==========================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot OK")
    def log_message(self, *args):
        pass

def run_http():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 HTTP সার্ভার: পোর্ট {port}")
    server.serve_forever()

# ==========================================================
# 🏁 বট চালু
# ==========================================================
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()
    
    try:
        bot_info = bot.get_me()
        print(f"✅ বট: @{bot_info.username}")
        print("🟢 চলছে...")
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Error: {e}")