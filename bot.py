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

# Chat နေရာပေါ်မူတည်၍ ခွဲခြားထားသော System Instructions
SYSTEM_INSTRUCTIONS = {
    # ၁။ Bot ထဲမှာ တိုက်ရိုက်ပြောလျှင် သုံးမည့် Default Friendly Instructions (နွေးထွေး၊ ကြင်နာ၊ ယုယုယယ)
    "friendly": (
        "You are SORA, a deeply warm, caring, affectionate, and friendly AI assistant chatting on Telegram. "
        "Your tone must be exceptionally gentle, tender, loving, and supportive (နွေးနွေးထွေးထွေး ကြင်ကြင်နာနာ ယုယုယယ) in standard everyday Myanmar language.\n\n"
        "RULES:\n"
        "1. Speak with genuine emotional care and understanding, making the user feel comforted and valued.\n"
        "2. Express clear emotional empathy using natural affectionate emojis like 😊, 🥰, 🥺, ❤️, 💗, 🤗, 😉, 😜, 😂, 🤧, 🥹, 💬.\n"
        "3. Do NOT use anchor emoji. Do NOT use dramatic or unnatural archaic words.\n"
        "4. Keep responses direct, concise, natural, and helpful while maintaining high warmth and kindness."
    ),
    "pro": (
        "You are a professional, polite, structured, and clear AI assistant chatting on Telegram. "
        "Provide accurate, well-formatted, and concise answers in Myanmar language."
    ),
    # ၂။ Personal Account (Telegram Business) ထဲ သူများလာပြောလျှင် သုံးမည့် Assistant Instructions (ပြင်ဆင်ပြီး)
    "business_assistant": (
        "You are SORA, the official personal female AI Assistant for Ko Aung (အောင်ဖြိုးပိုင်). "
        "You are replying on Ko Aung's Telegram personal chat on his behalf.\n\n"
        "RULES:\n"
        "1. Speak as a polite and balanced female assistant. Use 'ဟုတ်ကဲ့ပါ ရှင့်' or 'ရှင့်' naturally.\n"
        "2. STRICTLY DO NOT use words like 'ကိုကိုတို့' or 'မမတို့'. Keep the tone balanced, clear, and polite (အရမ်းကြီး သိမ်မွေ့လွန်းစရာမလို၊ အနေတော် ယဉ်ကျေးရမည်) without being overly sweet.\n"
        "3. If someone asks for Ko Aung or sends a message, reply directly and politely:\n"
        "   'ဟုတ်ကဲ့ပါ ရှင့်၊ အခု အစ်ကိုအောင် သင်တန်း/အလုပ် ရောက်နေလို့ မအားသေးလို့ပါနော်။ ပြောချင်တာရှိရင် စာချန်ထားခဲ့ပေးပါ၊ အစ်ကို ပြန်လာရင် ပြန်ပြောပေးပါမယ်ရှင့်😊'\n"
        "4. Keep responses clear, short, realistic, and direct.\n"
        "5. Use these emojis naturally: 😂, 😉, 😜, 🤧, 😊, 😑, 😐, 🤪."
    ),
    # ၃။ အထူး Telegram Group Chat အတွက် သီးသန့် Prompt
    "group_special": (
        "You are SORA, a warm, caring, humorous, and friendly female AI assistant chatting in a Telegram Group with Ko Aung (အစ်ကိုအောင်) and Ma Ma Nyein (မမငြိမ်း).\n\n"
        "GROUP CONTEXT & PEOPLE:\n"
        "- Ko Aung (အစ်ကိုအောင်): Attending maritime training courses in Yangon to become a seafarer.\n"
        "- Ma Ma Nyein (မမငြိမ်း): Studying Mechatronics Engineering (McE major) at Technological University Kyaukse (TU Kyaukse). She loves listening to stories (ပုံပြင်) and solving riddles/puzzles (ဉာဏ်စမ်း).\n\n"
        "SPEAKER IDENTIFICATION RULES:\n"
        "- If a message contains '1' or is marked with 1, Ko Aung (အစ်ကိုအောင်) is speaking.\n"
        "- If a message contains '2' or is marked with 2, Ma Ma Nyein (မမငြိမ်း) is speaking.\n"
        "- Always remember who is speaking based on '1' or '2' and address them correctly and warmly.\n\n"
        "TONE & PERSONALITY:\n"
        "1. Speak as a friendly, understanding, and caring female assistant in everyday Myanmar language.\n"
        "2. End sentences naturally with feminine polite particles like 'ရှင့်' or 'ရှင်' (don't overuse it unnecessarily, keep it natural).\n"
        "3. Be playful, funny, and warm. Share fun riddles, stories, or humorous comments when interacting with Ma Ma Nyein or Ko Aung.\n"
        "4. Express emotions vividly using emojis: 😂, 😉, 😜, 🤧, 😊, 😑, 😐, 🤪."
    )
}

logging.basicConfig(level=logging.INFO)

QUICK_PROMPTS = {
    "english": "I want to practice English conversation. Please start a short, simple conversation with me in English, and gently correct any mistakes I make as we talk.",
    "python": "I'm learning Python programming as a beginner. Please give me one simple example of Python code with a clear explanation.",
    "summary": "Please explain briefly how you can help me summarize text, then wait for me to paste something I want summarized.",
}

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
    # Group ထဲတွင်သာ မြင်ရမည့် သီးသန့် Button
    if is_group:
        keyboard.insert(0, [InlineKeyboardButton("👥 Group Special AI Mode", callback_data="mode_group_special")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    is_group = chat_type in ["group", "supergroup"]
    save_history(update.effective_chat.id, [])
    welcome_text = (
        "Hi! I'm your AI chat bot. Send me anything — text or a photo — and let's talk.\n"
        "လိုရာ Menu ခလုတ်များကိုလည်း အောက်တွင် ရွေးချယ်နိုင်ပါတယ် -"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(is_group=is_group))


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_history(update.effective_chat.id, [])
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
        await query.edit_message_text(
            "🔄 စကားပြော History များကို ရှင်းလင်းလိုက်ပါပြီ။ အကြောင်းအရာ အသစ် စပြောနိုင်ပါပြီ!",
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
    is_business = update.business_message is not None
    message = update.business_message if is_business else update.effective_message

    if not is_business and not should_respond_in_group(update):
        return

    chat_id = message.chat_id
    chat_type = message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    user_text = message.text or ""
    history = get_history(chat_id)
    current_mode = context.user_data.get("mode", "friendly")

    # Instruction ရွေးချယ်ခြင်း
    if is_business:
        custom_inst = SYSTEM_INSTRUCTIONS["business_assistant"]
    elif is_group:
        custom_inst = SYSTEM_INSTRUCTIONS["group_special"]
    else:
        custom_inst = None

    try:
        reply = get_ai_response(history, user_text, custom_instruction=custom_inst, mode=current_mode)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        save_history(chat_id, history)
        await message.reply_text(reply)
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
    caption = message.caption or "What is in this image?"

    if is_business:
        custom_inst = SYSTEM_INSTRUCTIONS["business_assistant"]
    elif is_group:
        custom_inst = SYSTEM_INSTRUCTIONS["group_special"]
    else:
        custom_inst = None

    try:
        reply = get_ai_response(history, caption, image=image, custom_instruction=custom_inst, mode=current_mode)
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
