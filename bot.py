import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai
from flask import Flask

server = Flask(__name__)
@server.route('/')
def home():
    return "Bot is running!"

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
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
