import os
from dotenv import load_dotenv
load_dotenv()

import openai
import logging
import requests
import random
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import schedule
import asyncio

# === Логирование ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# === Переменные окружения ===
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY or not CHANNEL_ID or not UNSPLASH_ACCESS_KEY:
    raise ValueError("Одна или несколько переменных окружения не установлены")

bot = Bot(token=TELEGRAM_TOKEN)
MY_USER_ID = 375047802  # ← замени на свой Telegram ID

def is_authorized(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == MY_USER_ID

# OpenAI
openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# Статистика
post_count = 0
last_post_time = None

def generate_post():
    prompt = "Придумай короткий и ироничный пост в стиле 'Типо живу', на тему усталости, тревоги, жизни."
    logger.info("Генерирую текст поста через OpenRouter")
    response = openai.ChatCompletion.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message["content"]
    return content

def generate_image():
    keywords = ["tired", "anxiety", "life", "sadness", "urban"]
    query = random.choice(keywords)
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return data["urls"]["regular"]
    except Exception as e:
        logger.error(f"Ошибка при получении изображения: {e}")
        return "https://placekitten.com/640/360"

def post_to_channel():
    global post_count, last_post_time
    try:
        text = generate_post()
        image_url = generate_image()
        bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
        post_count += 1
        last_post_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Ошибка при публикации: {e}")

def send_daily_report():
    report = f"📋 Отчёт за сегодня:\nПостов: {post_count}"
    if last_post_time:
        report += f"\nПоследний пост: {last_post_time}"
    else:
        report += "\nПосты не публиковались."
    bot.send_message(chat_id=MY_USER_ID, text=report)

# Команды Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update):
        await update.message.reply_text("Бот работает.")
    else:
        await update.message.reply_text("Нет доступа.")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update):
        await update.message.reply_text(f"📊 Постов: {post_count}\nПоследний: {last_post_time}")
    else:
        await update.message.reply_text("Нет доступа.")

async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update):
        text = generate_post()
        image_url = generate_image()
        await update.message.reply_photo(photo=image_url, caption=text)
    else:
        await update.message.reply_text("Нет доступа.")

# Планировщик
async def run_schedule():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# Запуск
if __name__ == "__main__":
    from telegram.ext import ApplicationBuilder

    async def run():
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("report", report))
        application.add_handler(CommandHandler("createpost", create_post))

        # Расписание
        schedule.every().day.at("09:00").do(post_to_channel)
        schedule.every().day.at("12:00").do(post_to_channel)
        schedule.every().day.at("15:00").do(post_to_channel)
        schedule.every().day.at("18:00").do(post_to_channel)
        schedule.every().day.at("21:00").do(post_to_channel)
        schedule.every().day.at("22:00").do(send_daily_report)

        asyncio.create_task(run_schedule())
        await application.run_polling()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        asyncio.ensure_future(run())
    else:
        asyncio.run(run())
