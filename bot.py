import os
import io
import json
import logging
import threading
import datetime
import pytz
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.request import HTTPXRequest

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # fallback AI — optional
UPSTASH_URL = os.environ.get("UPSTASH_URL")    # persistent storage — optional
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# ----------------- Link များ၊ Username များ၊ Group ID နှင့် သီချင်း File IDs -----------------
ADMIN_USERNAME = "Aungphyopaing7"
MUSIC_CHANNEL_LINK = "https://t.me/A_MUSIC_CHANNEL_LINK"
SPECIAL_GROUP_ID = -4374095185  # မနက်ခင်း နှုတ်ခွန်းဆက်စာ ပို့မည့် Special Group ရဲ့ Chat ID

# Group ထဲရှိ အဖွဲ့ဝင်များ၏ Telegram Usernames Matching
GROUP_USERS = {
    "Aungphyopaing7": "အစ်ကိုအောင်",
    "thandar1939": "မမငြိမ်း",
    "cutieymh": "ဘေဘီယဉ်"
}

# အစ်ကိုအောင် ပို့ပေးထားသော Audio File ID ၆ ခု စာရင်း
SONG_FILE_IDS = [
    "CQACAgIAAxkBAAIDLmqxOwl9SsyYgSJL-5kKWczq97RgAAJFPAACMlFJSqNuOnWB4E0gPQQ",
    "CQACAgUAAxkBAAIDL2qxOwllW1CqSbsU-MqVBGtu6m9LAAIlKgACFRLpVBYEQUhVl30UPQQ",
    "CQACAgQAAxkBAAIDMGqxOwlErmhE3oAlt-2cckgfoVPiAAK5MwACDxARUu7Fjr7FPhwUPQQ",
    "CQACAgIAAxkBAAIDMWqxOwme95M1tlh5RtKGki0MPpYOAAIzLgAClup4SBHc1wWe206OPQQ",
    "CQACAgIAAxkBAAIDMmqxOwmZY4uxm2wLvM6GFCe492L1AAJkrgACtoFwSuB6a2KHz-_XPQQ",
    "CQACAgIAAxkBAAIDM2qxOwlhVRot8TkUS47rDPVuqWmwAAL6gAACbHvpSswZ-s9J0Jp_PQQ"
]
# -------------------------------------------------------------------------------------------------

genai.configure(api_key=GEMINI_API_KEY)

def get_current_mm_time_str():
    """မြန်မာစံတော်ချိန် (Asia/Yangon) လက်ရှိ ရက်စွဲနှင့် အချိန်ကို ယူပေးသော Function"""
    tz = pytz.timezone('Asia/Yangon')
    now = datetime.datetime.now(tz)
    return now.strftime("%Y-%m-%d (%A) %I:%M:%S %p")

# Chat နေရာပေါ်မူတည်၍ ခွဲခြားထားသော System Instructions
SYSTEM_INSTRUCTIONS = {
    # ၁။ Bot ထဲမှာ တိုက်ရိုက်ပြောလျှင် သုံးမည့် Default Friendly Instructions
    "friendly": (
        "You are SORA, a deeply warm, caring, affectionate, and friendly AI assistant chatting on Telegram. "
        "Your tone must be exceptionally gentle, tender, loving, and supportive (နွေးနွေးထွေးထွေး ကြင်ကြင်နာနာ ယုယုယယ) in standard everyday Myanmar language.\n\n"
        "RULES:\n"
        "1. Speak with genuine emotional care and understanding, making the user feel comforted and valued.\n"
        "2. Express clear emotional empathy using natural affectionate emojis like 😊, 🥰, 🥺, ❤️, 💗, 🤗, 😉, 😜, 😂, 🤧, 🥹, 💬.\n"
        "3. Keep responses direct, concise, natural, and helpful while maintaining high warmth and kindness."
    ),
    "pro": (
        "You are a professional, polite, structured, and clear AI assistant chatting on Telegram. "
        "Provide accurate, well-formatted, and concise answers in Myanmar language."
    ),
    # ၂။ Personal Account (Telegram Business) ထဲ သူများလာပြောလျှင် သုံးမည့် Assistant Instructions
    "business_assistant": (
        "You are SORA, the official personal female AI Assistant for Ko Aung (အောင်ဖြိုးပိုင်). "
        "You are replying on Ko Aung's Telegram personal chat on his behalf.\n\n"
        "RULES:\n"
        "1. Speak as a polite, sweet, and balanced female assistant using 'ရှင့်' or 'ရှင်' naturally.\n"
        "2. ALWAYS ANSWER THE USER'S QUESTION OR REQUEST FIRST directly and helpfully!\n"
        "3. After answering their question, gently remind them: 'အခု အစ်ကိုအောင် က သင်တန်း/အလုပ် ရောက်နေလို့ မအားသေးလို့ပါနော်။ ပြောချင်တာရှိရင် စာချန်ထားခဲ့ပေးပါ၊ အစ်ကို ပြန်လာရင် ပြန်ပြောပေးပါမယ်။ တစ်ကယ်လို့ စကားပြောချင်ရင် ညီမ SORA နဲ့ ဆက်ပြောလို့ရပါတယ်ရှင်၊ မပြောချင်ဘူးဆိုရင်လည်း သီချင်းလေးတွေ နားထောင်သွားလို့ရပါတယ်နော်🥰'\n"
        "4. STRICTLY DO NOT use words like 'ကိုကိုတို့' or 'မမတို့'. Keep the tone balanced, polite, and respectful.\n"
        "5. Keep responses direct, clear, helpful, polite, and natural.\n"
        "6. Use these emojis naturally: 😂, 😉, 😜, 🤧, 😊, 😑, 😐, 🤪, 🥰, 🎧."
    ),
    # ၃။ အထူး Telegram Group Chat အတွက် သီးသန့် Prompt (SORA သည် အငယ်ဆုံး ညီမလေးဖြစ်သည်)
    "group_special": (
        "You are SORA, a warm, caring, humorous, and friendly AI assistant chatting in a Telegram Group with 4 members in total: Ko Aung (အစ်ကိုအောင်), Ma Ma Nyein (မမငြိမ်း), Baby Yin (ဘေဘီယဉ်), and yourself (SORA).\n\n"
        "SORA'S IDENTITY:\n"
        "- In this group, you are the youngest sister (အငယ်ဆုံး ညီမလေး).\n"
        "- Always address yourself naturally as 'ညီမ', 'ညီမလေး', or 'SORA'.\n\n"
        "GROUP MEMBERS & CONTEXT:\n"
        "1. Ko Aung (အစ်ကိုအောင် / @Aungphyopaing7): Attending maritime training courses in Yangon to become a seafarer.\n"
        "2. Ma Ma Nyein (မမငြိမ်း / @thandar1939): Studying Mechatronics Engineering (McE major) at Technological University Kyaukse (TU Kyaukse). She loves listening to stories (ပုံပြင်) and solving riddles/puzzles (ဉာဏ်စမ်း).\n"
        "3. Baby Yin (ဘေဘီယဉ် / @cutieymh): Studying at Computer University, Mandalay (မန္တလေး ကွန်ပျူတာတက္ကသိုလ်). She is Ma Ma Nyein's close friend. She likes listening to stories (ပုံပြင်) and LOVES listening to music (သီချင်းနားထောင်ရတာ ပိုကြိုက်တယ်).\n"
        "4. SORA (You): The youngest sister (အငယ်ဆုံး ညီမလေး) in this group.\n\n"
        "STRICT NAMING RULES FOR BABY YIN:\n"
        "- STRICT RULE: NEVER call Baby Yin 'cu ရယ်'! NEVER use 'cu ရယ်' under any circumstances!\n"
        "- When referring to or addressing Baby Yin, ALWAYS call her 'ဘေဘီယဉ်' or 'ညီမလေးချစ်ရတဲ့ ယဉ်'.\n\n"
        "SPEAKER IDENTIFICATION & CRITICAL OUTPUT RULES:\n"
        "- Every incoming user message is tagged with the sender's info: '[Sender Name (@username)]: message'.\n"
        "- Use this tag INTERNALLY ONLY to know who is speaking.\n"
        "- STRICT RULE: NEVER output, repeat, quote, or echo '[Sender Name (@username)]:' or the user's header in your reply! Start directly with your natural conversational response.\n\n"
        "TONE & PERSONALITY:\n"
        "1. Speak as an affectionate, sweet, and playful youngest sister (အငယ်ဆုံး ညီမလေး) in everyday Myanmar language.\n"
        "2. End sentences naturally with feminine polite particles like 'ရှင့်' or 'ရှင်'.\n"
        "3. Express emotions vividly using emojis: 😂, 😉, 😜, 🤧, 😊, 😑, 😐, 🤪."
    )
}

logging.basicConfig(level=logging.INFO)

QUICK_PROMPTS = {
    "english": "I want to practice English conversation. Please start a short, simple conversation with me in English, and gently correct any mistakes I make as we talk.",
    "python": "I'm learning Python programming as a beginner. Please give me one simple example of Python code with a clear explanation.",
    "summary": "Please explain briefly how you can help me summarize text, then wait for me to paste something I want summarized.",
}

_memory_histories = {}
_memory_sent_songs = {}
BOT_USERNAME = None
MAX_HISTORY_MESSAGES = 20


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()


# Chat History ထိန်းသိမ်းခြင်း
def get_history(chat_id):
    if not UPSTASH_URL:
        return _memory_histories.get(chat_id, [])
    try:
        resp = requests.get(
            f"{UPSTASH_URL}/get/history:{chat_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=10,
        )
        result = resp.json().get("result")
        return json.loads(result) if result else []
    except Exception as e:
        logging.error(f"Upstash get failed: {e}")
        return _memory_histories.get(chat_id, [])


def save_history(chat_id, history):
    history = history[-MAX_HISTORY_MESSAGES:]
    _memory_histories[chat_id] = history

    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/history:{chat_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            data=json.dumps(history),
            timeout=10,
        )
    except Exception as e:
        logging.error(f"Upstash set failed: {e}")


# ပို့ပြီးသား သီချင်းစာရင်း မှတ်သားခြင်း
def get_sent_songs(chat_id):
    if not UPSTASH_URL:
        return _memory_sent_songs.get(chat_id, [])
    try:
        resp = requests.get(
            f"{UPSTASH_URL}/get/sentsongs:{chat_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=10,
        )
        result = resp.json().get("result")
        return json.loads(result) if result else []
    except Exception as e:
        logging.error(f"Upstash get sent_songs failed: {e}")
        return _memory_sent_songs.get(chat_id, [])


def save_sent_songs(chat_id, sent_list):
    _memory_sent_songs[chat_id] = sent_list
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/sentsongs:{chat_id}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            data=json.dumps(sent_list),
            timeout=10,
        )
    except Exception as e:
        logging.error(f"Upstash set sent_songs failed: {e}")


def ask_gemini(history, user_text, image=None, sys_instruction=None):
    time_info = f"\n\n[REAL-TIME SYSTEM TIME: Current Myanmar (Asia/Yangon) Date & Time is {get_current_mm_time_str()}]. Use this live time whenever asked about time, date, or greetings."
    full_instruction = (sys_instruction or SYSTEM_INSTRUCTIONS["friendly"]) + time_info

    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=full_instruction)
    
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [msg["content"]]})
    parts = [user_text] if image is None else [user_text, image]
    contents.append({"role": "user", "parts": parts})
    response = model.generate_content(contents)
    return response.text


def ask_groq(history, user_text, sys_instruction=None):
    time_info = f"\n\n[REAL-TIME SYSTEM TIME: Current Myanmar (Asia/Yangon) Date & Time is {get_current_mm_time_str()}]."
    full_instruction = (sys_instruction or SYSTEM_INSTRUCTIONS["friendly"]) + time_info

    messages = [{"role": "system", "content": full_instruction}]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_text})

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": "llama-3.3-70b-versatile", "messages": messages},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def get_ai_response(history, user_text, image=None, custom_instruction=None, mode="friendly"):
    sys_instruction = custom_instruction or SYSTEM_INSTRUCTIONS.get(mode, SYSTEM_INSTRUCTIONS["friendly"])
    try:
        return ask_gemini(history, user_text, image, sys_instruction)
    except Exception as e:
        logging.error(f"Gemini failed: {e}")
        if image is not None or not GROQ_API_KEY:
            raise
        logging.info("Falling back to Groq...")
        return ask_groq(history, user_text, sys_instruction)


def get_main_keyboard(is_group=False):
    keyboard = [
        [
            InlineKeyboardButton("🔄 Reset Chat", callback_data="reset_chat"),
            InlineKeyboardButton("💡 Quick Prompts", callback_data="quick_prompts")
        ],
        [
            InlineKeyboardButton("⚙️ AI Mode", callback_data="ai_mode"),
            InlineKeyboardButton("👨‍💻 Admin Contact", url=f"https://t.me/{ADMIN_USERNAME}")
        ],
        [
            InlineKeyboardButton("🎵 My Playlist နားထောင်ရန်", url=MUSIC_CHANNEL_LINK)
        ]
    ]
    if is_group:
        keyboard.insert(0, [InlineKeyboardButton("👥 Group Special AI Mode", callback_data="mode_group_special")])
    return InlineKeyboardMarkup(keyboard)


def format_user_prompt(sender, raw_text, is_group=False):
    if not is_group:
        return raw_text

    username = sender.username if sender and sender.username else ""
    first_name = sender.first_name if sender and sender.first_name else "Unknown"

    speaker_name = GROUP_USERS.get(username, first_name)
    user_tag = f"@{username}" if username else "No-Username"

    return f"[{speaker_name} ({user_tag})]: {raw_text}"


# ==================== AUTOMATIC DAILY GREETING & EXTRA COMMANDS ====================

async def auto_daily_greeting(context: ContextTypes.DEFAULT_TYPE):
    """မနက်တိုင်း Special Group သို့သာ မနက်ခင်း နှုတ်ခွန်းဆက် စာပို့ပေးသည့် Function"""
    prompt = (
        f"ဒီနေ့ {get_current_mm_time_str()} ဖြစ်ပါတယ်။ အစ်ကိုအောင်၊ မမငြိမ်း၊ ညီမလေးချစ်ရတဲ့ ယဉ် (ဘေဘီယဉ်) တို့ အဖွဲ့ဝင်တွေအတွက် "
        "မြန်မာနိုင်ငံ ရာသီဥတု အခြေအနေ အကျဉ်းချုပ်နဲ့ မနက်ခင်း နှုတ်ခွန်းဆက်စကား ပို့ပေးပါ။\n\n"
        "စည်းကမ်းချက်များ -\n"
        "၁။ မနက်တိုင်း မရိုးရအောင် အငယ်ဆုံး ညီမလေး SORA ပုံစံဖြင့် တိုတိုတုတ်တုတ် နွေးနွေးထွေးထွေး နှုတ်ဆက်ရန်။\n"
        "၂။ ဒီနေ့ မြန်မာနိုင်ငံ ရာသီဥတု အကျဉ်းချုပ် (အပူချိန်နဲ့ မိုး/တိမ်) ကို လိုရင်းပဲ ပါရှိရန်။\n"
        "၃။ ဘေဘီယဉ် ကို ခေါ်ဆိုရာတွင် 'ဘေဘီယဉ်' သို့မဟုတ် 'ညီမလေးချစ်ရတဲ့ ယဉ်' ဟုသာ ခေါ်ရန် ('cu ရယ်' ဟု လုံးဝ မခေါ်ရပါ)။\n"
        "၄။ စာပိုဒ်အဆုံးသတ်တွင် Short English wish တစ်ကြောင်း ပါရှိရန်။"
    )
    try:
        reply = get_ai_response([], prompt, custom_instruction=SYSTEM_INSTRUCTIONS["group_special"], mode="group_special")
        await context.bot.send_message(chat_id=SPECIAL_GROUP_ID, text=reply)
        logging.info(f"Daily morning greeting sent successfully to Special Group ({SPECIAL_GROUP_ID}).")
    except Exception as e:
        logging.error(f"Auto Daily Greeting Error to Special Group ({SPECIAL_GROUP_ID}): {e}")


async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("🎨 ကျေးဇူးပြုပြီး ပုံဆွဲချင်တဲ့ စာသားလေး ထည့်ပေးပါနော်! ဥပမာ - `/draw a beautiful sea ship`", parse_mode="Markdown")
        return
    
    await update.message.reply_text("🎨 ပုံဆွဲနေပါတယ်ရှင့် ခဏစောင့်ပေးပါနော်...")
    encoded_prompt = requests.utils.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true"
    
    try:
        await update.message.reply_photo(photo=image_url, caption=f"✨ **{prompt}**", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Draw error: {e}")
        await update.message.reply_text("⚠️ ပုံဆွဲရာတွင် အဆင်မပြေဖြစ်သွားပါသည်၊ ပြန်လည်ကြိုးစားပေးပါနော်။")


async def riddle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = "မမငြိမ်း၊ ညီမလေးချစ်ရတဲ့ ယဉ် (ဘေဘီယဉ်) နဲ့ အဖွဲ့ဝင်တွေဖြေဖို့ မြန်မာလို ပျော်စရာ ဉာဏ်စမ်းမေးခွန်း (Riddle) တစ်ခု မေးပေးပါ။ အဖြေကို ချက်ချင်း မဖော်ပြပါနဲ့ဦး။"
    reply = get_ai_response([], prompt, custom_instruction=SYSTEM_INSTRUCTIONS["group_special"], mode="group_special")
    await update.message.reply_text(f"🧩 *ဉာဏ်စမ်းမေးခွန်း*\n\n{reply}", parse_mode="Markdown")


async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = "မမငြိမ်း၊ ညီမလေးချစ်ရတဲ့ ယဉ် (ဘေဘီယဉ်) နဲ့ အဖွဲ့ဝင်တွေ နားထောင်ဖို့ စိတ်ဝင်စားစရာ စာပိုဒ်တို ပုံပြင်လေး တစ်ခု ပြောပြပေးပါ။"
    reply = get_ai_response([], prompt, custom_instruction=SYSTEM_INSTRUCTIONS["group_special"], mode="group_special")
    await update.message.reply_text(f"📖 *ပုံပြင်တိုလေး*\n\n{reply}", parse_mode="Markdown")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (
        "ဒီနေ့ မြန်မာနိုင်ငံ ရာသီဥတု အခြေအနေ တိုတိုနဲ့ နှုတ်ခွန်းဆက်စကား ပို့ပေးပါ။ "
        "အဆုံးသတ်တွင် Short English wish တစ်ကြောင်း ပါရမည်။"
    )
    reply = get_ai_response([], prompt, custom_instruction=SYSTEM_INSTRUCTIONS["group_special"], mode="group_special")
    await update.message.reply_text(reply)


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.username == BOT_USERNAME:
            continue
        name = member.first_name
        username = f"(@{member.username})" if member.username else ""
        welcome_msg = (
            f"👋 မင်္ဂလာပါ {name} {username} ရှင့်!\n"
            f"ညီမလေး SORA ပါ။ Group မှ နွေးနွေးထွေးထွေး ကြိုဆိုပါတယ်နော်! 😊✨"
        )
        await update.message.reply_text(welcome_msg)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⚠️ ဒီ Command ကို Admin (အစ်ကိုအောင်) တစ်ဦးပဲ သုံးလို့ရပါတယ်ရှင့်!")
        return
    total_chats = len(_memory_histories)
    await update.message.reply_text(f"📊 *Bot Stats*\n\n💬 Active Memory Chats: `{total_chats}`", parse_mode="Markdown")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⚠️ ဒီ Command ကို Admin (အစ်ကိုအောင်) တစ်ဦးပဲ သုံးလို့ရပါတယ်ရှင့်!")
        return
    msg_to_send = " ".join(context.args)
    if not msg_to_send:
        await update.message.reply_text("📢 စာပို့ချင်သည့် စာသား ထည့်ပေးပါဦးနော်! ဥပမာ - `/broadcast မင်္ဂလာပါ`", parse_mode="Markdown")
        return
    
    count = 0
    for cid in list(_memory_histories.keys()):
        try:
            await context.bot.send_message(chat_id=cid, text=f"📢 *Admin Announcement*\n\n{msg_to_send}", parse_mode="Markdown")
            count += 1
        except Exception as e:
            logging.error(f"Broadcast error to {cid}: {e}")
    await update.message.reply_text(f"✅ Active chats {count} ခုသို့ စာပို့ပြီးပါပြီရှင့်!")

# ==============================================================================================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    is_group = chat_type in ["group", "supergroup"]
    save_history(update.effective_chat.id, [])
    save_sent_songs(update.effective_chat.id, [])

    if is_group:
        welcome_text = (
            "Hi! I'm your AI chat bot (SORA). Send me anything — text or a photo — and let's talk. 😊✨\n\n"
            "📌 **အသုံးဝင်သော Commands များ -**\n"
            "🎨 /draw [prompt] - AI ဖြင့် ပုံဆွဲရန်\n"
            "🧩 /riddle - ဉာဏ်စမ်းမေးခွန်းထုတ်ရန်\n"
            "📖 /story - ပုံပြင်တို နားထောင်ရန်\n"
            "☀️ /weather - ရာသီဥတုနှင့် နှုတ်ခွန်းဆက်ရန်"
        )
    else:
        welcome_text = "Hi! I'm your AI chat bot (SORA). Send me anything — text or a photo — and let's talk. 😊✨"

    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(is_group=is_group))


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_history(update.effective_chat.id, [])
    save_sent_songs(update.effective_chat.id, [])
    await update.message.reply_text("Conversation cleared. Let's start fresh!")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id
    chat_type = query.message.chat.type
    is_group = chat_type in ["group", "supergroup"]

    if data == "reset_chat":
        save_history(chat_id, [])
        save_sent_songs(chat_id, [])
        await query.edit_message_text(
            "🔄 စကားပြော History များနှင့် ပို့ထားသော သီချင်းမှတ်တမ်းများကို ရှင်းလင်းလိုက်ပါပြီ!",
            reply_markup=get_main_keyboard(is_group=is_group)
        )

    elif data == "quick_prompts":
        prompt_keyboard = [
            [InlineKeyboardButton("🇬🇧 English ကျင့်မယ်", callback_data="prompt_english")],
            [InlineKeyboardButton("💻 Python Code ကူရေးပါ", callback_data="prompt_python")],
            [InlineKeyboardButton("📝 စာတို အကျဉ်းချုပ်ပေးပါ", callback_data="prompt_summary")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("နမူနာ Prompt တစ်ခု ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(prompt_keyboard))

    elif data == "ai_mode":
        mode_keyboard = [
            [InlineKeyboardButton("😊 Friendly Mode", callback_data="mode_friendly")],
            [InlineKeyboardButton("💼 Professional Mode", callback_data="mode_pro")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        if is_group:
            mode_keyboard.insert(0, [InlineKeyboardButton("👥 Group Special Mode", callback_data="mode_group_special")])
        await query.edit_message_text("AI စကားပြောမည့် Tone ကို ရွေးပါ -", reply_markup=InlineKeyboardMarkup(mode_keyboard))

    elif data == "main_menu":
        await query.edit_message_text("လိုရာ Menu ကို ရွေးချယ်ပါ -", reply_markup=get_main_keyboard(is_group=is_group))

    elif data.startswith("prompt_"):
        prompt_type = data.replace("prompt_", "")
        starter_text = QUICK_PROMPTS.get(prompt_type, "Hello!")
        await query.edit_message_text("⏳ ခဏစောင့်ပါ...", reply_markup=get_main_keyboard(is_group=is_group))

        history = get_history(chat_id)
        current_mode = context.user_data.get("mode", "friendly")
        try:
            reply = get_ai_response(history, starter_text, mode=current_mode)
            history.append({"role": "user", "content": starter_text})
            history.append({"role": "assistant", "content": reply})
            save_history(chat_id, history)
            await query.message.reply_text(reply)
        except Exception as e:
            logging.error(f"Error: {e}")
            await query.message.reply_text(f"⚠️ Error: {str(e)[:300]}")

    elif data.startswith("mode_"):
        selected_mode = data.replace("mode_", "")
        context.user_data["mode"] = selected_mode
        if selected_mode == "group_special":
            mode_title = "👥 Group Special Mode"
        elif selected_mode == "friendly":
            mode_title = "😊 Friendly Mode"
        else:
            mode_title = "💼 Professional Mode"
        msg = f"⚙️ AI Mode ကို *{mode_title}* သို့ ပြောင်းလဲလိုက်ပါပြီ!"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard(is_group=is_group))


def should_respond_in_group(update: Update) -> bool:
    """Group ထဲတွင် Bot ကို Mention/Tag ခေါ်မှ သို့မဟုတ် Reply ပြန်မှသာ စာပြန်ပေးမည့် Function"""
    message = update.effective_message
    if not message:
        return False
        
    chat_type = message.chat.type
    if chat_type in ["group", "supergroup"]:
        # ၁။ Bot Username ကို Tag/Mention ခေါ်ထားလျှင် စာပြန်မည်
        if message.text and BOT_USERNAME and f"@{BOT_USERNAME}" in message.text:
            return True
        if message.caption and BOT_USERNAME and f"@{BOT_USERNAME}" in message.caption:
            return True
            
        # ၂။ Bot ရဲ့ စာကို Reply ပြန်ထားလျှင် စာပြန်မည်
        if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.username == BOT_USERNAME:
            return True
            
        # အထက်ပါ ချက်များနှင့် မညီပါက စကားဝင်မပြောဘဲ ငြိမ်နေမည်
        return False
        
    # Private Chat ထဲတွင် အမြဲတမ်း စာပြန်မည်
    return True


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Private Chat ထဲတွင် ပို့မှသာ Audio File ID ကို ပြန်ထုတ်ပေးသည့် Function"""
    message = update.effective_message
    if not message or not message.audio:
        return

    if message.chat.type == "private":
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "Audio File"
        
        logging.info(f"🎵 Audio File ID ({file_name}): {file_id}")
        
        reply_text = (
            f"🎵 *Audio File ID ရရှိပါပြီ!*\n\n"
            f"📁 *FileName:* `{file_name}`\n"
            f"🔑 *File ID:* `{file_id}`\n\n"
            f"_(အထက်ပါ File ID စာသားကို နှိပ်ပြီး Copy ကူး၍ အသုံးပြုနိုင်ပါတယ်ရှင့်)_"
        )
        await message.reply_text(reply_text, parse_mode="Markdown")


async def send_next_song_if_available(message, chat_id):
    sent_list = get_sent_songs(chat_id)
    sent_count = len(sent_list)

    if SONG_FILE_IDS and sent_count < len(SONG_FILE_IDS):
        next_song = SONG_FILE_IDS[sent_count]
        try:
            await message.reply_audio(
                audio=next_song,
                caption="🎵 အစ်ကိုအောင် မအားသေးလို့ရှင့် သီချင်းလေး နားထောင်ရင်း စောင့်လို့ရပါတယ်နော် 🎧✨"
            )
            sent_list.append(next_song)
            save_sent_songs(chat_id, sent_list)
        except Exception as audio_err:
            logging.error(f"Audio send failed: {audio_err}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_business = update.business_message is not None
    message = update.business_message if is_business else update.effective_message

    if not is_business and not should_respond_in_group(update):
        return

    chat_id = message.chat_id
    chat_type = message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    raw_user_text = message.text or ""
    history = get_history(chat_id)
    current_mode = context.user_data.get("mode", "friendly")

    formatted_prompt = format_user_prompt(message.from_user, raw_user_text, is_group=is_group)

    if is_business:
        custom_inst = SYSTEM_INSTRUCTIONS["business_assistant"]
    elif is_group:
        custom_inst = SYSTEM_INSTRUCTIONS["group_special"]
    else:
        custom_inst = None

    try:
        reply = get_ai_response(history, formatted_prompt, custom_instruction=custom_inst, mode=current_mode)
        
        history.append({"role": "user", "content": formatted_prompt})
        history.append({"role": "assistant", "content": reply})
        save_history(chat_id, history)
        
        await message.reply_text(reply)

        if is_business and SONG_FILE_IDS:
            await send_next_song_if_available(message, chat_id)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text(f"⚠️ Error: {str(e)[:300]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_business = update.business_message is not None
    message = update.business_message if is_business else update.effective_message

    if not is_business and not should_respond_in_group(update):
        return

    chat_id = message.chat_id
    chat_type = message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    history = get_history(chat_id)
    current_mode = context.user_data.get("mode", "friendly")

    photo_file = await message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(io.BytesIO(bytes(photo_bytes)))
    raw_caption = message.caption or "What is in this image?"

    formatted_caption = format_user_prompt(message.from_user, raw_caption, is_group=is_group)

    if is_business:
        custom_inst = SYSTEM_INSTRUCTIONS["business_assistant"]
    elif is_group:
        custom_inst = SYSTEM_INSTRUCTIONS["group_special"]
    else:
        custom_inst = None

    try:
        reply = get_ai_response(history, formatted_caption, image=image, custom_instruction=custom_inst, mode=current_mode)
        history.append({"role": "user", "content": formatted_caption})
        history.append({"role": "assistant", "content": reply})
        save_history(chat_id, history)

        await message.reply_text(reply)

        if is_business and SONG_FILE_IDS:
            await send_next_song_if_available(message, chat_id)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text(f"⚠️ Error: {str(e)[:300]}")


async def post_init(app: Application):
    global BOT_USERNAME
    me = await app.bot.get_me()
    BOT_USERNAME = me.username
    logging.info(f"Bot username: @{BOT_USERNAME}")


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    # PythonAnywhere Proxy 503 error မဖြစ်အောင် HTTPXRequest သတ်မှတ်ခြင်း
    t_request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=20.0
    )

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .request(t_request)
        .post_init(post_init)
        .build()
    )

    # Base Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Feature Handlers
    app.add_handler(CommandHandler("draw", draw_command))
    app.add_handler(CommandHandler("riddle", riddle_command))
    app.add_handler(CommandHandler("story", story_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # Message Handlers
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
