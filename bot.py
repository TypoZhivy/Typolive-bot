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
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не установлена")
if not OPENAI_API_KEY:
    raise ValueError("Переменная OPENAI_API_KEY не установлена")
if not CHANNEL_ID:
    raise ValueError("Переменная CHANNEL_ID не установлена")
if not UNSPLASH_ACCESS_KEY:
    raise ValueError("Переменная UNSPLASH_ACCESS_KEY не установлена")

# === Telegram-бот ===
bot = Bot(token=TELEGRAM_TOKEN)

# === Только ты можешь управлять ботом ===
MY_USER_ID = 375047802  # ← ЗАМЕНИ на свой Telegram ID!

def is_authorized(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == MY_USER_ID

# === OpenAI (OpenRouter) ===
openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# === Статистика ===
post_count = 0
last_post_time = None

# === Генерация текста поста ===
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

# === Подбор изображения по теме ===
def generate_image():
    keywords = ["tired", "anxiety", "life", "sadness", "urban"]
    query = random.choice(keywords)
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={UNSPLASH_ACCESS_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        image_url = data[0]["urls"]["regular"]
        logger.info(f"Изображение найдено по теме: {query}")
        return image_url
    except Exception as e:
        logger.error(f"Ошибка при получении изображения: {e}")
        return "https://placekitten.com/640/360"  # запасной вариант

# === Публикация в канал ===
def post_to_channel():
    global post_count, last_post_time
    logger.info("Начинаю постинг в канал")
    
    try:
        text = generate_post()
        image_url = generate_image()
        bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
        
        post_count += 1
        last_post_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Пост опубликован. Всего сегодня: {post_count}")
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")

# === Функция для отправки ежедневного отчёта ===
def send_daily_report():
    if MY_USER_ID:
        report_text = f"📋 Отчёт за сегодня:\nПостов опубликовано: {post_count}"
        if last_post_time:
            report_text += f"\nПоследний пост: {last_post_time}"
        else:
            report_text += f"\nПосты сегодня ещё не публиковались."
        
        bot.send_message(chat_id=MY_USER_ID, text=report_text)
        logger.info(f"Отправлен ежедневный отчёт пользователю {MY_USER_ID}")

# === Команды Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /start")
        return
    await update.message.reply_text("Бот работает. Используй /report или /createpost.")
    logger.info("Пользователь вызвал /start")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /report")
        return

    report_text = f"📊 Статистика:\nПостов сегодня: {post_count}"
    if last_post_time:
        report_text += f"\nПоследний пост: {last_post_time}"
    else:
        report_text += f"\nПосты сегодня ещё не публиковались."

    await update.message.reply_text(report_text)
    logger.info("Отправлен отчёт /report")

async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /createpost")
        return
    text = generate_post()
    image_url = generate_image()
    await update.message.reply_photo(photo=image_url, caption=text)
    logger.info("Пост создан вручную")

# === Асинхронный планировщик ===
async def run_schedule():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# === Основной запуск ===
async def main():
    # Создаем экземпляр приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("createpost", create_post))

    # Расписание постов
    schedule.every().day.at("09:00").do(post_to_channel)
    schedule.every().day.at("12:00").do(post_to_channel)
    schedule.every().day.at("15:00").do(post_to_channel)
    schedule.every().day.at("18:00").do(post_to_channel)
    schedule.every().day.at("21:00").do(post_to_channel)

    # Расписание для отправки ежедневного отчёта
    schedule.every().day.at("22:00").do(send_daily_report)

    # Запускаем планировщик и бота
    await asyncio.gather(
        application.run_polling(),
        run_schedule()
    )

if __name__ == "__main__":
    import sys
    if sys.version_info < (3, 7):
        print("Python version must be >= 3.7")
        sys.exit(1)
    asyncio.run(main())
