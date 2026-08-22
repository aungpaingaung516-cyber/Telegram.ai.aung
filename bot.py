import os
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai
from flask import Flask

# 1. Flask server တည်ဆောက်ခြင်း (Render ရဲ့ Port တောင်းဆိုမှုကို ဖြေရှင်းရန်)
server = Flask(__name__)

@server.route('/')
def home():
    return "🤖 Bot is running 24/7!"

def run_flask():
    # Render ပေးမယ့် Port ကို ယူသုံးမယ် (မရှိရင် 8080 ကို သုံးမယ်)
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# 2. Telegram Bot တည်ဆောက်ခြင်း
TELEGRAM_BOT_TOKEN = "8903870807:AAHs_ovC4nvT0elYHbbNX-D7j-yc5PujCbs"
GEMINI_API_KEY = "AQ.Ab8RN6LXpFbFcoqbJRpGqSbMusj-m58_upYcAZ4COhzjdgWl_g"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = model.generate_content(user_message)
        bot_reply = response.text
    except Exception as e:
        bot_reply = "ခဏလေးနော် အကိုအောင်၊ အမှားအယွင်းရှိလို့ပါ 😅"
    await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    # Flask ကို Background ထဲမှာ သီးသန့် Run ပေးမယ့် Thread
    t = threading.Thread(target=run_flask)
    t.start()

    # Telegram Bot ကို စတင် Run မယ်
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
