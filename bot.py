import os
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_message,
    )
    await update.message.reply_text(response.text)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
app.run_polling()
    
    await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot စတင်နေပါပြီ...")
    app.run_polling()
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
