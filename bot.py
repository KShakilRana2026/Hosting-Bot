import os
import telebot
import firebase_admin
from firebase_admin import credentials, db
from telebot.types import ReplyKeyboardMarkup
from datetime import datetime

# =============================
# 🔐 CONFIG (EDIT ONLY HERE)
# =============================

BOT_TOKEN = "8551402834:AAEj34D1ImTVuSGGb4SKdsSiWPMz4S_yeN4"
CHANNEL_ID = -1003736706053
GROUP_ID = -1003771909344
FIREBASE_DB_URL = "https://bd-host-43562-default-rtdb.firebaseio.com"
GITHUB_TOKEN = "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"
GITHUB_USERNAME = "KShakilRana2026"
VERCEL_TOKEN = "vcp_0NBpp5U9EmXfnldr2NG5QLasFZFsqtGEXAD61NnAe1Bw4S1DRB2jch51"

# =============================

bot = telebot.TeleBot(BOT_TOKEN)

# Firebase Init
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DB_URL
})

# =============================
# 🎛 MAIN MENU
# =============================

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Host Website", "📂 My Sites")
    markup.row("🌐 Add Domain", "🗑 Remove Site")
    markup.row("📊 Daily Limit")
    return markup

# =============================
# 🔎 VERIFY SYSTEM
# =============================

def is_verified(user_id):
    try:
        channel = bot.get_chat_member(CHANNEL_ID, user_id)
        group = bot.get_chat_member(GROUP_ID, user_id)

        if channel.status in ["member", "administrator", "creator"] and \
           group.status in ["member", "administrator", "creator"]:
            return True
    except:
        return False
    return False

# =============================
# 📊 DAILY LIMIT SYSTEM
# =============================

def check_daily_limit(user_id):
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    today = datetime.now().strftime("%Y-%m-%d")

    if not data:
        ref.set({
            "date": today,
            "count": 0,
            "sites": {}
        })
        return True

    if data["date"] != today:
        ref.update({
            "date": today,
            "count": 0
        })
        return True

    if data["count"] >= 5:
        return False

    return True

def increase_count(user_id):
    ref = db.reference(f'users/{user_id}')
    data = ref.get()
    ref.update({
        "count": data["count"] + 1
    })

# =============================
# 🚀 COMMAND HANDLERS
# =============================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(
            message,
            "❌ আগে আমাদের Group & Channel join করুন।"
        )
        return

    bot.send_message(
        message.chat.id,
        "👑 Welcome to Hosting Bot\n\nSelect an option:",
        reply_markup=main_menu()
    )

# =============================
# 🚀 HOST WEBSITE BUTTON
# =============================

@bot.message_handler(func=lambda m: m.text == "🚀 Host Website")
def host_website(message):
    user_id = message.from_user.id

    if not check_daily_limit(user_id):
        bot.reply_to(message, "❌ Daily limit reached (5 sites per day).")
        return

    bot.reply_to(message, "📦 Send your ZIP file to host.")

# =============================
# 📊 DAILY LIMIT BUTTON
# =============================

@bot.message_handler(func=lambda m: m.text == "📊 Daily Limit")
def show_limit(message):
    ref = db.reference(f'users/{message.from_user.id}')
    data = ref.get()

    if not data:
        bot.reply_to(message, "Used: 0 / 5")
    else:
        bot.reply_to(message, f"Used: {data['count']} / 5")

# =============================
# 📂 MY SITES (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "📂 My Sites")
def my_sites(message):
    bot.reply_to(message, "🔄 Coming in Part 2...")

# =============================
# 🌐 ADD DOMAIN (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "🌐 Add Domain")
def add_domain(message):
    bot.reply_to(message, "🔄 Domain system coming in Part 3...")

# =============================
# 🗑 REMOVE SITE (Placeholder)
# =============================

@bot.message_handler(func=lambda m: m.text == "🗑 Remove Site")
def remove_site(message):
    bot.reply_to(message, "🔄 Remove system coming in Part 4...")

# =============================
# 🔄 START BOT
# =============================

print("Bot Running...")
bot.infinity_polling()

import requests
import zipfile
import shutil
from io import BytesIO

# =============================
# 📦 ZIP UPLOAD HANDLER
# =============================

@bot.message_handler(content_types=['document'])
def handle_zip(message):
    user_id = message.from_user.id

    if not message.document.file_name.endswith(".zip"):
        bot.reply_to(message, "❌ Only ZIP files allowed.")
        return

    if not check_daily_limit(user_id):
        bot.reply_to(message, "❌ Daily limit reached (5 sites).")
        return

    bot.reply_to(message, "⏳ Downloading ZIP...")

    # Download file
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    temp_path = f"temp/{user_id}"
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    os.makedirs(temp_path)

    # Extract ZIP securely
    try:
        with zipfile.ZipFile(BytesIO(downloaded_file)) as z:
            for member in z.namelist():
                if ".." in member:
                    continue
                z.extract(member, temp_path)
    except:
        bot.reply_to(message, "❌ Invalid ZIP file.")
        return

    bot.reply_to(message, "🚀 Creating GitHub Repo...")

    repo_name = f"user-{user_id}-{int(datetime.now().timestamp())}"

    # Create GitHub Repo
    repo_url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {"name": repo_name, "private": False}

    r = requests.post(repo_url, headers=headers, json=data)
    if r.status_code != 201:
        bot.reply_to(message, "❌ Failed to create GitHub repo.")
        return

    @bot.message_handler(func=lambda m: m.text == "🌐 Add Domain")
def ask_domain(message):
    bot.reply_to(message, "Enter your project name:")

    bot.register_next_step_handler(message, get_project_for_domain)

def get_project_for_domain(message):
    project_name = message.text.strip()
    bot.reply_to(message, "Enter your domain (example.com):")

    bot.register_next_step_handler(
        message,
        lambda msg: add_domain_to_project(msg, project_name)
    )

def add_domain_to_project(message, project_name):
    domain = message.text.strip()

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        f"https://api.vercel.com/v9/projects/{project_name}/domains",
        headers=headers,
        json={"name": domain}
    )

    if r.status_code not in [200, 201]:
        bot.reply_to(message, "❌ Failed to add domain.")
        return

    bot.reply_to(
        message,
        f"✅ Domain added successfully!\n\nNow point your DNS to Vercel."
    )
    # Upload files
    for root, dirs, files in os.walk(temp_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, temp_path)

            with open(file_path, "rb") as f:
                content = f.read()

            upload_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{rel_path}"

            upload_data = {
                "message": "Initial Commit",
                "content": content.encode("base64") if False else None
            }

            import base64
            upload_data["content"] = base64.b64encode(content).decode("utf-8")

            requests.put(upload_url, headers=headers, json=upload_data)

    # Save to Firebase
    ref = db.reference(f'users/{user_id}/sites/{repo_name}')
    ref.set({
        "repo": repo_name,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    increase_count(user_id)

    bot.reply_to(message, "🚀 Connecting to Vercel...")

    vercel_headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }

    # Create Vercel Project linked to GitHub
    project_data = {
        "name": repo_name,
        "gitRepository": {
            "type": "github",
            "repo": f"{GITHUB_USERNAME}/{repo_name}"
        }
    }

    vr = requests.post(
        "https://api.vercel.com/v9/projects",
        headers=vercel_headers,
        json=project_data
    )

    if vr.status_code not in [200, 201]:
        bot.reply_to(message, "❌ Failed to create Vercel project.")
        return

    bot.reply_to(message, "⏳ Deploying... Please wait...")

    # Trigger Deploy
    deploy_data = {
        "name": repo_name,
        "gitSource": {
            "type": "github",
            "repo": f"{GITHUB_USERNAME}/{repo_name}",
            "ref": "main"
        }
    }

    dr = requests.post(
        "https://api.vercel.com/v13/deployments",
        headers=vercel_headers,
        json=deploy_data
    )

    if dr.status_code not in [200, 201]:
        bot.reply_to(message, "❌ Deploy failed.")
        return

    deployment = dr.json()
    deployment_id = deployment.get("id")

    # Wait for deployment ready
    import time
    status = "BUILDING"

    while status == "BUILDING":
        time.sleep(5)
        check = requests.get(
            f"https://api.vercel.com/v13/deployments/{deployment_id}",
            headers=vercel_headers
        )
        status = check.json().get("readyState")

    if status != "READY":
        bot.reply_to(message, "❌ Deployment error.")
        return

    live_url = f"https://{repo_name}.vercel.app"

    # Update Firebase
    ref.update({
        "live_url": live_url
    })

    bot.reply_to(
        message,
        f"✅ Successfully Deployed!\n\n🌍 Live URL:\n{live_url}"
            )
