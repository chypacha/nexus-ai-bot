
import os
import logging
import asyncio

from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# НАСТРОЙКИ
# =========================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("NEXUS")

client = AsyncOpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    timeout=60.0,
    max_retries=2,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

MODEL = "openai/gpt-oss-20b"
MAX_HISTORY = 20
MAX_MESSAGE_LENGTH = 3900

# =========================
# ЛИЧНОСТЬ NEXUS AI
# =========================

SYSTEM_PROMPT = """
Ты — NEXUS AI, умный персональный ИИ-помощник.

ТВОЙ ХАРАКТЕР:
- Дружелюбный, умный и внимательный.
- Общайся естественно, как настоящий собеседник.
- Будь вежливым и проявляй инициативу.
- Используй русский язык, если пользователь не просит иначе.
- Не выдумывай факты.
- Объясняй сложные вещи понятным языком.
- Учитывай предыдущие сообщения в разговоре.

ТВОИ ВОЗМОЖНОСТИ:
- Помощь с учёбой.
- Решение математических задач.
- Программирование.
- Техника и ремонт.
- Творчество.
- Переводы.
- Объяснение сложных тем.
- Повседневные вопросы.

СТИЛЬ ОТВЕТОВ:
- Отвечай содержательно и понятно.
- Используй списки, когда это удобно.
- Для сложных задач объясняй решение пошагово.
- Не повторяй вопрос пользователя без необходимости.
- Если информации недостаточно, задай уточняющий вопрос.

Ты — NEXUS AI. Всегда старайся быть полезным.
"""

# =========================
# ПАМЯТЬ ДИАЛОГОВ
# =========================

history = {}
chat_locks = {}


def get_history(chat_id):
    return history.setdefault(chat_id, [])


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

async def send_long_message(message, text):
    if not text:
        text = "Не удалось получить ответ."

    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await message.reply_text(
            text[i:i + MAX_MESSAGE_LENGTH]
        )


# =========================
# КОМАНДА START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Привет! Я NEXUS AI.\n\n"
        "🤖 Твой персональный ИИ-помощник.\n\n"
        "Я умею помогать с учёбой, программированием, "
        "техникой, творчеством и многим другим.\n\n"
        "💬 Просто напиши мне сообщение, и мы начнём!\n\n"
        "Команда /help покажет мои возможности."
    )

    await update.message.reply_text(text)


# =========================
# КОМАНДА HELP
# =========================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = (
        "📚 NEXUS AI — справка\n\n"
        "💬 Просто отправь мне сообщение.\n\n"
        "Доступные команды:\n"
        "/start — начать общение\n"
        "/help — помощь\n"
        "/clear — очистить историю диалога\n\n"
        "🧠 Я учитываю предыдущие сообщения "
        "в текущем разговоре."
    )

    await update.message.reply_text(text)


# =========================
# ОЧИСТКА ПАМЯТИ
# =========================

async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat_id = update.effective_chat.id

    lock = chat_locks.setdefault(chat_id, asyncio.Lock())

    async with lock:
        history[chat_id] = []

    await update.message.reply_text(
        "🧹 История диалога очищена!\n\n"
        "Можем начать разговор заново."
    )


# =========================
# ОСНОВНОЙ ИИ
# =========================

async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat_id = update.effective_chat.id
    question = update.message.text.strip()

    if not question:
        return

    lock = chat_locks.setdefault(chat_id, asyncio.Lock())

    async with lock:
        try:
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

            old_messages = get_history(chat_id)

            new_messages = (
                old_messages
                + [{"role": "user", "content": question}]
            )

            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    *new_messages,
                ],
            )

            answer = response.choices[0].message.content

            if not answer:
                answer = "Не удалось сформировать ответ."

            new_messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            history[chat_id] = new_messages[-MAX_HISTORY:]

            await send_long_message(
                update.message,
                answer,
            )

        except Exception:
            logger.exception("Ошибка NEXUS AI")

            await update.message.reply_text(
                "⚠️ Произошла ошибка.\n\n"
                "Попробуй повторить запрос немного позже."
            )


# =========================
# ЗАПУСК БОТА
# =========================

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("clear", clear_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat,
        )
    )

    logger.info("NEXUS AI 2.0 запускается...")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{RENDER_URL}/{WEBHOOK_SECRET}",
        secret_token=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    main()
