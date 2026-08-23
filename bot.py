import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Keys come from Render's Environment Variables (set in the Render dashboard,
# NOT written here — this keeps them out of your public GitHub repo)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PORT = int(os.environ.get("PORT", 10000))
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"]  # auto-set by Render, e.g. https://your-app.onrender.com

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

logging.basicConfig(level=logging.INFO)

# Store conversation history per user (in memory - resets if bot restarts)
user_chats = {}


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
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running via webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{RENDER_URL}/{TELEGRAM_TOKEN}",
    )


if __name__ == "__main__":
    main()    # Flask ကို Background ထဲမှာ သီးသန့် Run ပေးမယ့် Thread
    t = threading.Thread(target=run_flask)
    t.start()

    # Telegram Bot ကို စတင် Run မယ်
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
