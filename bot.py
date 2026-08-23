import os
import io
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PORT = int(os.environ.get("PORT", 10000))

genai.configure(api_key=GEMINI_API_KEY)

# ===== Bot ရဲ့ character — ဒီစာသားကို ပြောင်းရင် bot ရဲ့ ပြောပုံစံ ပြောင်းပါလိမ့်မယ် =====
SYSTEM_INSTRUCTION = (
    "You are a friendly, helpful AI assistant chatting with users on Telegram. "
    "Keep replies conversational and not too long. Be warm and a little playful, "
    "but always genuinely helpful."
)

model = genai.GenerativeModel("gemini-3.6-flash", system_instruction=SYSTEM_INSTRUCTION)

logging.basicConfig(level=logging.INFO)

user_chats = {}
BOT_USERNAME = None


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()


def get_chat(chat_id):
    if chat_id not in user_chats:
        user_chats[chat_id] = model.start_chat(history=[])
    return user_chats[chat_id]


def should_respond_in_group(update: Update) -> bool:
    message = update.message
    if message.chat.type == "private":
        return True
    if message.reply_to_message and message.reply_to_message.from_user.username == BOT_USERNAME:
        return True
    if message.text and BOT_USERNAME and f"@{BOT_USERNAME}" in message.text:
        return True
    if message.caption and BOT_USERNAME and f"@{BOT_USERNAME}" in message.caption:
        return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_chats[update.effective_chat.id] = model.start_chat(history=[])
    await update.message.reply_text(
        "Hi! I'm your AI chat bot. Send me anything — text or a photo — and let's talk. "
        "Use /reset to start a fresh conversation."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_chats[update.effective_chat.id] = model.start_chat(history=[])
    await update.message.reply_text("Conversation cleared. Let's start fresh!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    chat = get_chat(chat_id)

    try:
        response = chat.send_message(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:300]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    chat_id = update.effective_chat.id
    chat = get_chat(chat_id)

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(io.BytesIO(bytes(photo_bytes)))

    caption = update.message.caption or "What is in this image?"

    try:
        response = chat.send_message([caption, image])
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:300]}")


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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
