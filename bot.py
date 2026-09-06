import os
import io
import json
import logging
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # fallback AI — optional
UPSTASH_URL = os.environ.get("UPSTASH_URL")    # persistent storage — optional
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

# ----------------- ပြင်ဆင်ပြီးသား Link များနှင့် Username -----------------
ADMIN_USERNAME = "Aungphyopaing7"
MUSIC_CHANNEL_LINK = "https://t.me/A_MUSIC_CHANNEL_LINK"
# -------------------------------------------------------------------------

genai.configure(api_key=GEMINI_API_KEY)

# AI Mode အလိုက် စကားပြောမည့် System Instructions များ
SYSTEM_INSTRUCTIONS = {
    "friendly": (
        "You are a warm, friendly, engaging, and helpful AI assistant chatting on Telegram. "
        "Keep replies conversational, warm, and a little playful."
    ),
    "pro": (
        "You are a professional, polite, structured, and clear AI assistant chatting on Telegram. "
        "Provide accurate, well-formatted, and concise answers."
    )
}

logging.basicConfig(level=logging.INFO)

_memory_histories = {}
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
        return []


def save_history(chat_id, history):
    history = history[-MAX_HISTORY_MESSAGES:]
    if not UPSTASH_URL:
        _memory_histories[chat_id] = history
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


def ask_gemini(history, user_text, image=None, sys_instruction=None):
    instruction = sys_instruction or SYSTEM_INSTRUCTIONS["friendly"]
    model = genai.GenerativeModel("gemini-3.5-flash-lite", system_instruction=instruction)
    
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [msg["content"]]})
    parts = [user_text] if image is None else [user_text, image]
    contents.append({"role": "user", "parts": parts})
    response = model.generate_content(contents)
    return response.text


def ask_groq(history, user_text, sys_instruction=None):
    instruction = sys_instruction or SYSTEM_INSTRUCTIONS["friendly"]
    messages = [{"role": "system", "content": instruction}]
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


def get_ai_response(history, user_text, image=None, mode="friendly"):
    sys_instruction = SYSTEM_INSTRUCTIONS.get(mode, SYSTEM_INSTRUCTIONS["friendly"])
    try:
        return ask_gemini(history, user_text, image, sys_instruction)
    except Exception as e:
        logging.error(f"Gemini failed: {e}")
        if image is not None or not GROQ_API_KEY:
            raise
        logging.info("Falling back to Groq...")
        return ask_groq(history, user_text, sys_instruction)


# --- Menu Keyboards ---
def get_main_keyboard():
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
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_history(update.effective_chat.id, [])
    welcome_text = (
        "Hi! I'm your AI chat bot. Send me anything — text or a photo — and let's talk.\n"
        "လိုရာ Menu ခလုတ်များကိုလည်း အောက်တွင် ရွေးချယ်နိုင်ပါတယ် -"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_history(update.effective_chat.id, [])
    await update.message.reply_text("Conversation cleared. Let's start fresh!")


# --- Button Click Actions ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id

    if data == "reset_chat":
        save_history(chat_id, [])
        await query.edit_message_text(
            "🔄 စကားပြော History များကို ရှင်းလင်းလိုက်ပါပြီ။ အကြောင်းအရာ အသစ် စပြောနိုင်ပါပြီ!",
            reply_markup=get_main_keyboard()
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
        await query.edit_message_text("AI စကားပြောမည့် Tone ကို ရွေးပါ -", reply_markup=InlineKeyboardMarkup(mode_keyboard))

    elif data == "main_menu":
        await query.edit_message_text("လိုရာ Menu ကို ရွေးချယ်ပါ -", reply_markup=get_main_keyboard())

    elif data.startswith("prompt_"):
        prompt_type = data.replace("prompt_", "")
        msg = f"💡 Prompt ရွေးချယ်လိုက်ပါပြီ (`{prompt_type}`)။ သိလိုသည်များကို စတင်မေးမြန်းနိုင်ပါပြီ!"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif data.startswith("mode_"):
        selected_mode = data.replace("mode_", "")
        context.user_data["mode"] = selected_mode  # AI Mode ကို သိမ်းဆည်းခြင်း
        mode_title = "😊 Friendly Mode" if selected_mode == "friendly" else "💼 Professional Mode"
        msg = f"⚙️ AI Mode ကို *{mode_title}* သို့ ပြောင်းလဲလိုက်ပါပြီ!"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())


def should_respond_in_group(update: Update) -> bool:
    message = update.effective_message
    if message.chat.type == "private":
        return True
    if message.reply_to_message and message.reply_to_message.from_user.username == BOT_USERNAME:
        return True
    if message.text and BOT_USERNAME and f"@{BOT_USERNAME}" in message.text:
        return True
    if message.caption and BOT_USERNAME and f"@{BOT_USERNAME}" in message.caption:
        return True
    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    message = update.effective_message
    chat_id = message.chat_id
    user_text = message.text
    history = get_history(chat_id)
    current_mode = context.user_data.get("mode", "friendly")

    try:
        reply = get_ai_response(history, user_text, mode=current_mode)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        save_history(chat_id, history)
        await message.reply_text(reply)
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text(f"⚠️ Error: {str(e)[:300]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    message = update.effective_message
    chat_id = message.chat_id
    history = get_history(chat_id)
    current_mode = context.user_data.get("mode", "friendly")

    photo_file = await message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(io.BytesIO(bytes(photo_bytes)))
    caption = message.caption or "What is in this image?"

    try:
        reply = get_ai_response(history, caption, image=image, mode=current_mode)
        history.append({"role": "user", "content": caption})
        history.append({"role": "assistant", "content": reply})
        save_history(chat_id, history)
        await message.reply_text(reply)
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

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
er))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
