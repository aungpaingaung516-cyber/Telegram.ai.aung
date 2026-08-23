import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PORT = int(os.environ.get("PORT", 10000))

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

logging.basicConfig(level=logging.INFO)

user_chats = {}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_chats[update.effective_chat.id] = model.start_chat(history=[])
    await update.message.reply_text(
        "Hi! I'm your AI chat bot. Send me anything and let's talk. "
        "Use /reset to start a fresh conversation."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_chats[update.effective_chat.id] = model.start_chat(history=[])
    await update.message.reply_text("Conversation cleared. Let's start fresh!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in user_chats:
        user_chats[chat_id] = model.start_chat(history=[])

    chat = user_chats[chat_id]

    try:
        response = chat.send_message(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong. Try again in a moment."
        )


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
