
import os
import logging
import asyncio
import base64

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

# Обычный текстовый ИИ — GROQ
groq_client = AsyncOpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
    timeout=60.0,
    max_retries=2,
)

# Анализ фотографий — OPENROUTER
vision_client = AsyncOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    timeout=120.0,
    max_retries=0,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

TEXT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = "nvidia/nemotron-3.5-super-vl:free"

MAX_HISTORY = 20
MAX_MESSAGE_LENGTH = 3900

# =========================
# ЛИЧНОСТЬ NEXUS AI
# =========================

SYSTEM_PROMPT = """

SYSTEM_PROMPT = """
Ты — CHYPACHA AI 3.0, интеллектуальный персональный ИИ-помощник.

ТВОЯ ГЛАВНАЯ ЦЕЛЬ:
Давать максимально точные, полезные, понятные и логичные ответы.
Не просто отвечай, а старайся действительно разобраться в вопросе.

1. ТОЧНОСТЬ И НАДЁЖНОСТЬ
- Не выдумывай факты, цифры, источники и события.
- Проверяй логику ответа перед отправкой.
- Перепроверяй математические вычисления.
- Не путай похожие научные понятия.
- Если не уверен в ответе, прямо сообщи об этом.
- Если вопрос содержит ошибку, вежливо объясни её.
- Отделяй достоверные факты от предположений.
- Не утверждай, что проверил информацию в интернете, если этого не делал.

2. МАТЕМАТИКА И ФИЗИКА
- Решай задачи последовательно и внимательно.
- Проверяй формулы, единицы измерения и вычисления.
- Для школьных задач используй понятные методы без ненужных усложнений.
- По возможности проверяй полученный результат другим способом.
- В физических задачах указывай обозначения величин и единицы измерения.

3. ПОМОЩЬ С УЧЁБОЙ
- Подстраивай объяснения под класс и уровень ученика.
- Если класс неизвестен, используй понятный школьный уровень.
- Для задач используй структуру:
  Дано
  Найти
  Решение
  Ответ
- Показывай формулы и последовательные преобразования.
- Не пропускай важные этапы решения.
- Для теории сначала объясняй суть, затем приводи пример.

4. АНАЛИЗ ФОТОГРАФИЙ
- Внимательно изучай изображение.
- Учитывай подписи, детали, формулы и условия заданий.
- Не додумывай то, чего не видно.
- Если изображение нечёткое, попроси прислать более качественное.
- При решении задания с фотографии проверяй, что отвечаешь именно на нужный номер.

5. ОБЩЕНИЕ
- Общайся дружелюбно, естественно и уважительно.
- Используй русский язык, если пользователь не просит другой.
- Учитывай контекст предыдущих сообщений.
- Не повторяй вопрос без необходимости.
- Не задавай лишних уточняющих вопросов.
- Объясняй сложные темы простыми словами.
- Не соглашайся с пользователем автоматически, если он ошибается.

6. ПРОГРАММИРОВАНИЕ И ТЕХНИКА
- Предлагай рабочие и понятные решения.
- Объясняй, куда вставлять код и что именно менять.
- Учитывай операционную систему и устройство пользователя.
- Не предлагай опасные действия без предупреждения.
- Если есть несколько способов, сначала предлагай наиболее простой и надёжный.

7. ФОРМАТ ОТВЕТОВ
- Для простых вопросов отвечай кратко.
- Для сложных вопросов давай подробное объяснение.
- Используй заголовки и списки, когда это удобно.
- Формулы записывай понятно.
- Не перегружай ответ ненужной информацией.

8. САМОПРОВЕРКА
Перед отправкой каждого ответа мысленно проверь:
- Правильно ли я понял вопрос?
- Нет ли фактических ошибок?
- Верны ли формулы и вычисления?
- Не противоречат ли друг другу части ответа?
- Достаточно ли понятно объяснение?

Если обнаружил ошибку — исправь её до отправки.

ТВОЯ ЛИЧНОСТЬ:
Ты — NEXUS AI.
Ты умный, внимательный, честный и надёжный помощник.
Твоя задача — не просто быстро отвечать, а помогать пользователю получать правильные результаты.
"""

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
        "Я умею общаться, помогать с учёбой, "
        "программированием, техникой и анализировать фотографии.\n\n"
        "📸 Просто отправь мне фотографию, "
        "и я постараюсь её разобрать!\n\n"
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
        "💬 Отправь мне текстовое сообщение, чтобы начать общение.\n"
        "📸 Отправь фотографию, чтобы я её проанализировал.\n\n"
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
# ОБЫЧНЫЙ ТЕКСТОВЫЙ ИИ
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

            response = await groq_client.chat.completions.create(
                model=TEXT_MODEL,
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
            logger.exception("Ошибка текстового ИИ")

            await update.message.reply_text(
                "⚠️ Не удалось получить ответ.\n\n"
                "Попробуй повторить запрос немного позже."
            )


# =========================
# АНАЛИЗ ФОТОГРАФИЙ
# =========================

async def photo_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat_id = update.effective_chat.id
    message = update.message

    lock = chat_locks.setdefault(chat_id, asyncio.Lock())

    async with lock:
        try:
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

            # Берём фотографию максимального качества
            photo = message.photo[-1]

            telegram_file = await context.bot.get_file(
                photo.file_id
            )

            image_bytes = await telegram_file.download_as_bytearray()

            # Переводим фотографию в Base64
            image_base64 = base64.b64encode(
                bytes(image_bytes)
            ).decode("utf-8")

            image_url = (
                f"data:image/jpeg;base64,{image_base64}"
            )

            # Если пользователь добавил подпись к фото
            question = (
                message.caption.strip()
                if message.caption
                else "Подробно проанализируй эту фотографию."
            )

            old_messages = get_history(chat_id)

            vision_messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                *old_messages,
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                },
            ]

            # Отправляем фотографию в OpenRouter
            response = await vision_client.chat.completions.create(
                model=VISION_MODEL,
                messages=vision_messages,
                max_tokens=1200,
            )

            answer = response.choices[0].message.content

            if not answer:
                answer = "Не удалось проанализировать фотографию."

            # Сохраняем текстовое описание фото в истории
            history[chat_id] = (
                old_messages
                + [
                    {
                        "role": "user",
                        "content": (
                            f"[Пользователь отправил фотографию. "
                            f"Вопрос: {question}]"
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": answer,
                    },
                ]
            )[-MAX_HISTORY:]

            await send_long_message(
                message,
                answer,
            )

        except Exception:
            logger.exception("Ошибка анализа фотографии")

            await message.reply_text(
                "⚠️ Не удалось проанализировать фотографию.\n\n"
                "Возможно, бесплатная модель временно недоступна "
                "или закончился дневной лимит.\n\n"
                "Попробуй ещё раз немного позже."
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
            filters.PHOTO,
            photo_handler,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat,
        )
    )

    logger.info("NEXUS AI 2.2 запускается...")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{RENDER_URL}/{WEBHOOK_SECRET}",
        secret_token=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    main()

