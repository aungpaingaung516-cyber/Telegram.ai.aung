import os
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai
from flask import Flask

# Web Service Port မတက်အောင် Flask Server ပါဝင်သည်
server = Flask(__name__)

@server.route('/')
def home():
    return "🤖 Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# API Keys
TELEGRAM_BOT_TOKEN = "8903870807:AAHs_ovC4nvT0elYHbbNX-D7j-yc5PujCbs"
GEMINI_API_KEY = "AQ.Ab8RN6JUV61jGI4-xRXjdg5jHR0Vvw7Kzlm_aN6V2VQe64SeKQ"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = model.generate_content(user_message)
        bot_reply = response.text
    except Exception as e:
        bot_reply = f"⚠️ Error ပေါ်နေတယ်: {str(e)}"
    
    await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    # Flask Server ကို နောက်ကွယ်တွင် Thread ဖြင့် Run ခြင်း
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Telegram Bot ကို Polling စတင်ခြင်း
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
if __name__ == '__main__':
    # Flask ကို Background ထဲမှာ သီးသန့် Run မယ့် Thread
    t = threading.Thread(target=run_flask)
    t.start()

    # Telegram Bot ကို စတင် Run မယ်
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
    # Flask ကို Background ထဲမှာ သီးသန့် Run ပေးမယ့် Thread
    t = threading.Thread(target=run_flask)
    t.start()

    # Telegram Bot ကို စတင် Run မယ်
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
