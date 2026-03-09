# ==========================================================
# 🔥 টেলিগ্রাম হোস্টিং বট - Markdown ফিক্সড ভার্সন
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
if not ADMIN_PASSWORD: missing.append("ADMIN_PASSWORD")
if not ADMIN_ID: missing.append("ADMIN_ID")

if missing:
    print(f"❌ অনুপস্থিত: {', '.join(missing)}")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
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
# 🔥 ফায়ারবেস ইনিশিয়ালাইজেশন
# ==========================================================
firebase_ready = False

def init_firebase():
    global firebase_ready
    
    if not FIREBASE_CONFIG_BASE64 or not FIREBASE_DB_URL:
        print("⚠️ ফায়ারবেস কনফিগ নেই")
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
        
        firebase_ready = True
        print("✅ ফায়ারবেস কানেক্টেড")
        return True
        
    except Exception as e:
        print(f"❌ ফায়ারবেস এরর: {e}")
        return False

init_firebase()

# ==========================================================
# 📊 রেট লিমিটার
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
# ✅ ভেরিফিকেশন
# ==========================================================
def is_verified(user_id):
    try:
        if CHANNEL_ID and GROUP_ID:
            ch = bot.get_chat_member(CHANNEL_ID, user_id)
            gp = bot.get_chat_member(GROUP_ID, user_id)
            return ch.status in ["member", "administrator", "creator"] and \
                   gp.status in ["member", "administrator", "creator"]
        return True
    except:
        return True

def is_admin(user_id):
    return user_id == ADMIN_ID

# ==========================================================
# 🚀 স্টার্ট কমান্ড
# ==========================================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    text = (
        "👋 Welcome!\n\n"
        "📤 Upload your website ZIP file.\n"
        "✅ Daily limit: 5 sites\n"
        "📦 Max size: 50MB"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

# ==========================================================
# 📦 জিপ ফাইল হ্যান্ডলার - Vercel ফিক্সড
# ==========================================================
@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id
    
    if not message.document.file_name.endswith('.zip'):
        bot.reply_to(message, "❌ Only ZIP files allowed!")
        return
    
    if not check_limit(user_id):
        used = get_count(user_id)
        bot.reply_to(message, f"❌ Daily limit reached! Used: {used}/5")
        return
    
    if message.document.file_size > 50 * 1024 * 1024:
        bot.reply_to(message, "❌ File too large! Max 50MB")
        return
    
    status = bot.reply_to(message, "⏳ Processing...")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("📦 Extracting...", message.chat.id, status.message_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(BytesIO(downloaded)) as zf:
                zf.extractall(temp_dir)
            
            if not os.path.exists(os.path.join(temp_dir, 'index.html')):
                bot.edit_message_text("❌ index.html not found!", message.chat.id, status.message_id)
                return
            
            repo_name = f"site-{user_id}-{int(time.time())}"
            
            bot.edit_message_text("🔧 Creating GitHub repo...", message.chat.id, status.message_id)
            
            github_ok, github_url = create_github(repo_name, temp_dir)
            if not github_ok:
                bot.edit_message_text("❌ GitHub error!", message.chat.id, status.message_id)
                return
            
            bot.edit_message_text("🚀 Deploying to Vercel...", message.chat.id, status.message_id)
            
            # Vercel ডিপ্লয় - ফিক্সড ভার্সন
            live_url = deploy_to_vercel(repo_name)
            
            if live_url:
                add_count(user_id)
                used = get_count(user_id)
                
                if firebase_ready:
                    try:
                        db.reference(f'users/{user_id}/sites/{repo_name}').set({
                            "url": live_url,
                            "github": github_url,
                            "date": datetime.now().isoformat()
                        })
                    except:
                        pass
                
                # Markdown ছাড়া প্লেইন টেক্সট ব্যবহার করা হয়েছে parse_mode এড়ানোর জন্য
                success = (
                    f"✅ Deployment Successful!\n\n"
                    f"🌐 Live URL:\n{live_url}\n\n"
                    f"📂 GitHub:\n{github_url}\n\n"
                    f"📊 Used today: {used}/5"
                )
                
                bot.edit_message_text(success, message.chat.id, status.message_id)
            else:
                bot.edit_message_text("❌ Vercel deployment failed! Check Vercel token and try again.", message.chat.id, status.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)[:100]}", message.chat.id, status.message_id)
        print(traceback.format_exc())

def create_github(repo_name, local_path):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    try:
        # Create repo
        data = {"name": repo_name, "private": False}
        r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        
        if r.status_code != 201:
            repo_name = f"{repo_name}-{int(time.time())}"
            r = requests.post("https://api.github.com/user/repos", headers=headers, json=data, timeout=30)
        
        if r.status_code != 201:
            return False, None
        
        # Upload files
        for root, _, files in os.walk(local_path):
            for file in files:
                path = os.path.join(root, file)
                rel = os.path.relpath(path, local_path)
                
                with open(path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode()
                
                url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel}"
                data = {"message": f"Add {rel}", "content": content, "branch": "main"}
                requests.put(url, headers=headers, json=data, timeout=30)
        
        return True, f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
        
    except:
        return False, None

def deploy_to_vercel(repo_name):
    """Vercel-এ ডিপ্লয় করে - ফিক্সড ভার্সন"""
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    try:
        print(f"🔄 Vercel deploying: {repo_name}")
        
        # Token test
        test = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)
        if test.status_code != 200:
            print(f"❌ Vercel token invalid: {test.status_code}")
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
        
        proj_resp = requests.post(
            "https://api.vercel.com/v9/projects",
            headers=headers,
            json=project_data,
            timeout=30
        )
        
        if proj_resp.status_code not in [200, 201]:
            print(f"⚠️ Project creation status: {proj_resp.status_code}")
        
        # Create deployment
        deploy_data = {
            "name": repo_name,
            "gitSource": {
                "type": "github",
                "repo": f"{GITHUB_USERNAME}/{repo_name}",
                "ref": "main"
            }
        }
        
        deploy_resp = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=deploy_data,
            timeout=30
        )
        
        print(f"📡 Vercel response: {deploy_resp.status_code}")
        
        if deploy_resp.status_code in [200, 201]:
            print("✅ Vercel deployment created")
            return f"https://{repo_name}.vercel.app"
        
        # If deployment already exists
        if deploy_resp.status_code == 400:
            try:
                error_data = deploy_resp.json()
                if "already_exists" in str(error_data).lower():
                    print("⚠️ Deployment already exists")
                    return f"https://{repo_name}.vercel.app"
            except:
                pass
        
        print(f"❌ Vercel error: {deploy_resp.status_code}")
        return None
        
    except Exception as e:
        print(f"❌ Vercel exception: {e}")
        return None

# ==========================================================
# 📂 MY SITES
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📂 MY SITES")
def my_sites_handler(message):
    user_id = message.from_user.id
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    try:
        sites = db.reference(f'users/{user_id}/sites').get()
        
        if not sites:
            bot.reply_to(message, "📂 You haven't hosted any sites yet!")
            return
        
        text = "🌐 Your Sites:\n\n"
        for name, data in sites.items():
            text += f"📁 {name}\n🔗 {data.get('url', 'N/A')}\n📅 {data.get('date', '')[:10]}\n\n"
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================================
# 🌐 ADD DOMAIN
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🌐 ADD DOMAIN")
def add_domain_handler(message):
    user_id = message.from_user.id
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    sites = db.reference(f'users/{user_id}/sites').get()
    
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
        bot.reply_to(
            message,
            f"✅ Domain added!\n\nDNS: CNAME -> cname.vercel-dns.com"
        )
    else:
        bot.reply_to(message, f"❌ Failed: {r.text[:100]}")

# ==========================================================
# 🗑 DELETE SITE
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🗑 DELETE SITE")
def delete_site_handler(message):
    user_id = message.from_user.id
    
    if not firebase_ready:
        bot.reply_to(message, "❌ Database not connected!")
        return
    
    sites = db.reference(f'users/{user_id}/sites').get()
    
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
        f"Delete {project}?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('conf_'))
def confirm_delete(call):
    project = call.data.replace('conf_', '')
    user_id = call.from_user.id
    
    # Delete from Vercel
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    requests.delete(f"https://api.vercel.com/v9/projects/{project}", headers=headers)
    
    # Delete from GitHub
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    requests.delete(f"https://api.github.com/repos/{GITHUB_USERNAME}/{project}", headers=headers)
    
    # Delete from Firebase
    if firebase_ready:
        db.reference(f'users/{user_id}/sites/{project}').delete()
    
    bot.edit_message_text(
        f"✅ {project} deleted!",
        call.message.chat.id,
        call.message.message_id
    )

# ==========================================================
# 📊 DAILY LIMIT
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📊 DAILY LIMIT")
def daily_limit_handler(message):
    used = get_count(message.from_user.id)
    remaining = 5 - used
    bar = "🟩" * used + "⬜" * remaining
    
    text = f"📊 Daily Usage:\n\n{bar}\nUsed: {used}/5\nRemaining: {remaining}"
    bot.reply_to(message, text)

# ==========================================================
# 👑 ADMIN PANEL
# ==========================================================
admin_sessions = {}

@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL")
def admin_panel_handler(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Access denied!")
        return
    
    if admin_sessions.get(user_id):
        bot.send_message(message.chat.id, "👑 Admin Panel", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "🔑 Enter password:")
        bot.register_next_step_handler(message, check_admin_pass)

def check_admin_pass(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        bot.send_message(message.chat.id, "✅ Login successful!", reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ Wrong password!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📊 TOTAL USERS")
def total_users_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    if firebase_ready:
        users = db.reference('users').get()
        count = len(users) if users else 0
        bot.reply_to(message, f"📊 Total Users: {count}")
    else:
        bot.reply_to(message, "📊 Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "🌍 TOTAL SITES")
def total_sites_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    if firebase_ready:
        users = db.reference('users').get()
        total = 0
        if users:
            for data in users.values():
                total += len(data.get('sites', {}))
        bot.reply_to(message, f"🌍 Total Sites: {total}")
    else:
        bot.reply_to(message, "🌍 Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "🚫 BAN USER")
def ban_user_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "Enter User ID to ban:")
    bot.register_next_step_handler(message, process_ban)

def process_ban(message):
    if firebase_ready:
        db.reference(f'banned/{message.text}').set(True)
        bot.reply_to(message, f"✅ User {message.text} banned!")
    else:
        bot.reply_to(message, "❌ Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "✅ UNBAN USER")
def unban_user_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "Enter User ID to unban:")
    bot.register_next_step_handler(message, process_unban)

def process_unban(message):
    if firebase_ready:
        db.reference(f'banned/{message.text}').delete()
        bot.reply_to(message, f"✅ User {message.text} unbanned!")
    else:
        bot.reply_to(message, "❌ Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "🔄 RESET LIMIT")
def reset_limit_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "Enter User ID to reset limit:")
    bot.register_next_step_handler(message, process_reset)

def process_reset(message):
    global user_counts
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{message.text}_{today}"
    if key in user_counts:
        user_counts[key] = 0
    bot.reply_to(message, f"✅ Limit reset for user {message.text}")

@bot.message_handler(func=lambda m: m.text == "📢 BROADCAST")
def broadcast_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    bot.reply_to(message, "Enter message to broadcast:")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    if not firebase_ready:
        bot.reply_to(message, "❌ Firebase not connected")
        return
    
    users = db.reference('users').get()
    if not users:
        bot.reply_to(message, "❌ No users found")
        return
    
    sent = 0
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 Broadcast:\n\n{message.text}")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    
    bot.reply_to(message, f"✅ Broadcast sent to {sent} users")

@bot.message_handler(func=lambda m: m.text == "➕ ADD ADMIN")
def add_admin_handler(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    
    bot.reply_to(message, "Enter User ID to make admin:")
    bot.register_next_step_handler(message, process_add_admin)

def process_add_admin(message):
    if firebase_ready:
        db.reference(f'admins/{message.text}').set({"added_by": message.from_user.id, "date": datetime.now().isoformat()})
        bot.reply_to(message, f"✅ User {message.text} is now admin!")
    else:
        bot.reply_to(message, "❌ Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "➖ REMOVE ADMIN")
def remove_admin_handler(message):
    if not admin_sessions.get(message.from_user.id) or message.from_user.id != ADMIN_ID:
        return
    
    bot.reply_to(message, "Enter User ID to remove admin:")
    bot.register_next_step_handler(message, process_remove_admin)

def process_remove_admin(message):
    if firebase_ready:
        db.reference(f'admins/{message.text}').delete()
        bot.reply_to(message, f"✅ Admin removed from user {message.text}")
    else:
        bot.reply_to(message, "❌ Firebase not connected")

@bot.message_handler(func=lambda m: m.text == "📋 ADMIN LIST")
def admin_list_handler(message):
    if not admin_sessions.get(message.from_user.id):
        return
    
    text = f"👑 Admin List:\n\n⭐ Super Admin: {ADMIN_ID}\n\n"
    
    if firebase_ready:
        admins = db.reference('admins').get()
        if admins:
            text += "📋 Other Admins:\n"
            for aid in admins.keys():
                text += f"• {aid}\n"
    
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: m.text == "🚪 LOGOUT")
def logout_handler(message):
    if message.from_user.id in admin_sessions:
        del admin_sessions[message.from_user.id]
    bot.send_message(message.chat.id, "✅ Logged out!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ MAIN MENU")
def main_menu_handler(message):
    bot.send_message(message.chat.id, "⬅️ Main Menu", reply_markup=main_menu())

# ==========================================================
# 🔄 FALLBACK HANDLER (সবশেষে রাখতে হবে)
# ==========================================================
@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    bot.reply_to(message, "❌ Please use the menu buttons!", reply_markup=main_menu())

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
    print(f"🌐 HTTP Server on port {port}")
    server.serve_forever()

# ==========================================================
# 🏁 বট চালু
# ==========================================================
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot: @{bot_info.username}")
        print("🟢 Running...")
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Error: {e}")