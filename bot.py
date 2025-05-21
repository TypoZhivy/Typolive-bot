import os
import openai
import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import schedule
import asyncio

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# === Переменные окружения ===
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не установлена")
if not OPENAI_API_KEY:
    raise ValueError("Переменная OPENAI_API_KEY не установлена")
if not CHANNEL_ID:
    raise ValueError("Переменная CHANNEL_ID не установлена")

# === Подключение к OpenRouter (OpenAI-совместимый API) ===
openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# === Telegram-бот ===
bot = Bot(token=TELEGRAM_TOKEN)

# === Авторизация: только ты можешь управлять ботом ===
MY_USER_ID = 375047802  # ← ВСТАВЬ сюда свой Telegram ID (число)

def is_authorized(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == MY_USER_ID

# === Генерация поста и картинки ===
def generate_post():
    prompt = "Придумай короткий и ироничный пост в стиле 'Типо живу', на тему усталости, тревоги, жизни."
    logger.info("Генерирую текст поста через OpenRouter")
    response = openai.ChatCompletion.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message["content"]
    logger.info("Текст поста сгенерирован")
    return content

def generate_image():
    # Пока заглушка — котик
    return "https://placekitten.com/640/360"

def post_to_channel():
    logger.info("Начинаю постинг в канал")
    text = generate_post()
    image_url = generate_image()
    bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
    logger.info("Пост опубликован в канал")

# === Команды Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /start")
        return
    await update.message.reply_text("Бот работает. Используй /report или /createpost.")
    logger.info("Авторизованный пользователь вызвал /start")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /report")
        return
    await update.message.reply_text("Опубликовано 5 постов. Подписчиков: неизвестно.")
    logger.info("Вызвана команда /report")

async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /createpost")
        return
    logger.info("Авторизованный пользователь запросил /createpost")
    text = generate_post()
    await update.message.reply_photo(photo=generate_image(), caption=text)
    logger.info("Пост создан вручную по запросу")

# === Асинхронное расписание ===
async def run_schedule():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# === Основная функция ===
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("createpost", create_post))

    schedule.every().day.at("09:00").do(post_to_channel)
    schedule.every().day.at("12:00").do(post_to_channel)
    schedule.every().day.at("15:00").do(post_to_channel)
    schedule.every().day.at("18:00").do(post_to_channel)
    schedule.every().day.at("21:00").do(post_to_channel)

    async def run():
        asyncio.create_task(run_schedule())
        await application.run_polling()

    asyncio.run(run())

if __name__ == "__main__":
    main()
