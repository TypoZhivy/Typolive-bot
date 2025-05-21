import os
import openai
import logging
import requests
import random
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import schedule
import asyncio
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# === Логирование ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# === Переменные окружения ===
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
MY_USER_ID = int(os.getenv("MY_USER_ID", 0))

if not TELEGRAM_TOKEN or not CHANNEL_ID or not OPENAI_API_KEY or not UNSPLASH_ACCESS_KEY:
    raise ValueError("Не найдены необходимые переменные окружения.")

# === Telegram бот и OpenAI ===
bot = Bot(token=TELEGRAM_TOKEN)
openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

post_count = 0
last_post_time = None

# === Генерация поста ===
def generate_post():
    prompt = "Придумай короткий и ироничный пост в стиле 'Типо живу', на тему усталости, тревоги, жизни."
    response = openai.ChatCompletion.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message["content"]

# === Генерация изображения ===
def generate_image():
    keywords = ["tired", "anxiety", "life", "sadness", "urban"]
    query = random.choice(keywords)
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={UNSPLASH_ACCESS_KEY}"

    try:
        response = requests.get(url)
        data = response.json()
        return data["urls"]["regular"]
    except:
        return "https://placekitten.com/640/360"

# === Публикация ===
def post_to_channel():
    global post_count, last_post_time
    try:
        text = generate_post()
        image = generate_image()
        bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=text)
        post_count += 1
        last_post_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Пост успешно опубликован.")
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")

# === Отчет ===
def send_daily_report():
    report = f"📊 Постов сегодня: {post_count}"
    if last_post_time:
        report += f"\n⏰ Последний пост: {last_post_time}"
    bot.send_message(chat_id=MY_USER_ID, text=report)

# === Планировщик ===
async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# === Команды Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_USER_ID:
        return await update.message.reply_text("Нет доступа.")
    await update.message.reply_text("Бот запущен. Используй /report или /createpost.")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_USER_ID:
        return await update.message.reply_text("Нет доступа.")
    report = f"📊 Постов сегодня: {post_count}"
    if last_post_time:
        report += f"\n⏰ Последний пост: {last_post_time}"
    await update.message.reply_text(report)

async def createpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_USER_ID:
        return await update.message.reply_text("Нет доступа.")
    text = generate_post()
    image = generate_image()
    await update.message.reply_photo(photo=image, caption=text)

# === Главная функция ===
async def run_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("createpost", createpost))

    schedule.every().day.at("09:00").do(post_to_channel)
    schedule.every().day.at("12:00").do(post_to_channel)
    schedule.every().day.at("18:00").do(post_to_channel)
    schedule.every().day.at("22:00").do(send_daily_report)

    await asyncio.gather(
        application.run_polling(),
        scheduler()
    )

# === Запуск без asyncio.run() ===
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    loop.run_forever()
