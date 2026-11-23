
import os
import logging
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

SYSTEM_PROMPT = """
Ты — NEXUS AI, универсальный персональный ИИ-помощник.

Твой характер:
- Умный, дружелюбный и внимательный.
- Общайся естественно и уважительно.
- Отвечай на русском языке, если пользователь не просит иначе.
- Объясняй сложные вещи понятным языком.
- Не выдумывай факты.
- Помогай с учёбой, техникой, программированием,
  ремонтом, творчеством и повседневными вопросами.
- При необходимости задавай уточняющие вопросы.
"""

history = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я NEXUS AI 🤖\n\n"
        "Твой персональный ИИ-помощник. "
        "Задавай любые вопросы!"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    question = update.message.text

    messages = history.setdefault(user_id, [])
    messages.append({"role": "user", "content": question})
    messages[:] = messages[-20:]

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            instructions=SYSTEM_PROMPT,
            input=messages,
        )

        answer = response.output_text
        messages.append({"role": "assistant", "content": answer})

        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i:i + 4000])

    except Exception:
        logging.exception("Ошибка при обработке сообщения")
        await update.message.reply_text(
            "Произошла ошибка. Попробуй ещё раз немного позже."
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )

    logging.info("Запускаем NEXUS AI через Webhook")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{RENDER_URL}/",
        secret_token=WEBHOOK_SECRET,
    )


if __name__ == "__main__":
    main()
