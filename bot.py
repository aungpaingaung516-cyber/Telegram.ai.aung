import os
import io
import logging
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # fallback AI — optional
PORT = int(os.environ.get("PORT", 10000))

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are a friendly, helpful AI assistant chatting with users on Telegram. "
    "Keep replies conversational and not too long. Be warm and a little playful, "
    "but always genuinely helpful."
)

gemini_model = genai.GenerativeModel("gemini-3.5-flash-lite", system_instruction=SYSTEM_INSTRUCTION)

logging.basicConfig(level=logging.INFO)

user_histories = {}
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


def get_history(chat_id):
    if chat_id not in user_histories:
        user_histories[chat_id] = []
    return user_histories[chat_id]


def ask_gemini(history, user_text, image=None):
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [msg["content"]]})
    parts = [user_text] if image is None else [user_text, image]
    contents.append({"role": "user", "parts": parts})
    response = gemini_model.generate_content(contents)
    return response.text


def ask_groq(history, user_text):
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
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


def get_ai_response(history, user_text, image=None):
    try:
        return ask_gemini(history, user_text, image)
    except Exception as e:
        logging.error(f"Gemini failed: {e}")
        if image is not None or not GROQ_API_KEY:
            raise
        logging.info("Falling back to Groq...")
        return ask_groq(history, user_text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_chat.id] = []
    await update.message.reply_text(
        "Hi! I'm your AI chat bot. Send me anything — text or a photo — and let's talk. "
        "Use /reset to start a fresh conversation."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_chat.id] = []
    await update.message.reply_text("Conversation cleared. Let's start fresh!")


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    history = get_history(chat_id)

    try:
        reply = get_ai_response(history, user_text)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:300]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not should_respond_in_group(update):
        return

    chat_id = update.effective_chat.id
    history = get_history(chat_id)

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(io.BytesIO(bytes(photo_bytes)))
    caption = update.message.caption or "What is in this image?"

    try:
        reply = get_ai_response(history, caption, image=image)
        history.append({"role": "user", "content": caption})
        history.append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
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
