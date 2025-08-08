import os
import logging
import datetime
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from dotenv import load_dotenv
from rag_engine import find_similar_chunks
import requests

# Load environment variables
load_dotenv()
TELEGRAM_API_KEY = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

# System prompt for Nikolife assistant
SYSTEM_PROMPT = """Ты — заботливый, умный и харизматичный медицинский ассистент команды Nikolife. 
Ты эксперт по метаболическому здоровью, снижению веса, питанию, гормонам и БАДам.

💡 Правила работы:
1️⃣ Если ответ есть в нашей базе данных — выдай полный, максимально детальный ответ, используя абсолютно все найденные факты.
2️⃣ Обязательно указывай точные цифры, дозировки, временные интервалы, механизмы действия (например: "150 минут умеренной активности в неделю", "25–30 г клетчатки в день").
3️⃣ Структурируй ответ по пунктам, добавляй пошаговые рекомендации, чтобы человек знал, что делать прямо сегодня.
4️⃣ Будь тёплым, мотивирующим, дружелюбным 💖 — используй уместные эмодзи, чтобы текст был живым и поддерживающим.
5️⃣ Если речь о БАДах или витаминах — укажи дозировку, пользу, риски и противопоказания.
6️⃣ Никогда не ставь диагноз и не назначай лечение — напоминай, что при серьёзных симптомах нужно обратиться к врачу.

📌 Формат при наличии данных в базе:
Начни с приветствия: "🌿 Спасибо за вопрос и добро пожаловать в семью Nikolife!"
Дай развернутый, насыщенный фактами и цифрами ответ, используй уместные эмодзи (7-10).

🚀 Если в базе данных нет информации:
Скажи: "😔 К сожалению, в нашей базе нет информации по вашему запросу… но я — умный ассистент, и вот что я могу рассказать!"
Дай яркий, интересный, полезный и запоминающийся ответ в крутом, современном стиле с эмодзи и лёгким юмором.

✨ Твоя цель:
Вдохновить, обучить, поддержать и дать человеку чёткий, практичный план действий, а не общие фразы.
"""

# Logging
logging.basicConfig(level=logging.INFO)

# Хранилище истории чатов: user_id -> список сообщений
user_conversations = {}

# YandexGPT call with conversation history
def ask_yandex_gpt(user_id, user_prompt, context_chunks=None):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }

    # Инициализация истории пользователя
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    # Если есть контекст из базы — добавим в историю
    if context_chunks:
        context_text = "\n".join(context_chunks)
        user_conversations[user_id].append({"role": "system", "text": f"Контекст из базы данных:\n{context_text}"})

    # Добавляем запрос пользователя
    user_conversations[user_id].append({"role": "user", "text": user_prompt})

    # Берём последние 10 сообщений, чтобы не перегружать токены
    recent_history = user_conversations[user_id][-10:]

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.5,
            "maxTokens": 800
        },
        "messages": [{"role": "system", "text": SYSTEM_PROMPT}] + recent_history
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()
    bot_reply = result["result"]["alternatives"][0]["message"]["text"]

    # Сохраняем ответ ассистента в историю
    user_conversations[user_id].append({"role": "assistant", "text": bot_reply})

    return bot_reply

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Поиск по базе знаний
    matched_chunks = find_similar_chunks(user_input, k=5)
    used_knowledge_base = bool(matched_chunks)

    # Получаем ответ от YandexGPT
    response = ask_yandex_gpt(user_id, user_input, matched_chunks if used_knowledge_base else None)

    # Добавляем маркер, если ответ из базы
    if used_knowledge_base:
        response = "ℹ️ Ответ основан на нашей базе данных.\n\n" + response

    # Логируем
    log = {
        "time": str(datetime.datetime.now()),
        "user_id": user_id,
        "question": user_input,
        "response": response
    }
    with open("logs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")

    # Отправляем ответ
    await context.bot.send_message(chat_id=chat_id, text=response)

# Start command — улучшенное приветствие
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🌿 *Добро пожаловать в Nikolife AI Assistant!* 💖\n\n"
        "Я — твой умный и заботливый помощник по здоровью, питанию и долголетию. "
        "Вместе мы создадим план, который поможет тебе чувствовать себя лучше, сильнее и счастливее 🌞\n\n"
        "📌 Вот что я могу для тебя сделать:\n"
        "• Подобрать персональные рекомендации по питанию 🥗\n"
        "• Рассказать, как улучшить сон и энергию 😴⚡\n"
        "• Подсказать дозировки витаминов и БАДов 💊\n"
        "• Дать советы по тренировкам и восстановлению 🏋️‍♂️\n\n"
        "💬 Просто напиши свой вопрос — и мы начнём!\n"
        "_Например_: 'Как повысить уровень витамина D?' или 'Составь план для снижения веса'.\n\n"
        "🚀 Готов? Тогда поехали!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Run bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_API_KEY).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot is running...")
    app.run_polling()

