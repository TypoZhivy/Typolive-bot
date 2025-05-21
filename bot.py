import os
import openai
import logging
import requests
import random
from datetime import datetime, timedelta
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
MY_USER_ID = 375047802  # ← Заменить на свой Telegram ID

def is_authorized(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == MY_USER_ID

# === OpenAI (OpenRouter) ===
openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# === Статистика ===
post_count = 0
last_post_time = None
posted_messages = {}  # Словарь для хранения ID опубликованных постов

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
        sent_message = bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
        
        post_count += 1
        last_post_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Сохраняем ID опубликованного поста для последующего удаления
        posted_messages[sent_message.message_id] = datetime.now()
        
        logger.info(f"Пост опубликован. Всего сегодня: {post_count}")
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")

# === Удаление поста по ID ===
def delete_post(post_id: int):
    if post_id in posted_messages:
        try:
            bot.delete_message(chat_id=CHANNEL_ID, message_id=post_id)
            del posted_messages[post_id]
            logger.info(f"Пост с ID {post_id} был удалён.")
        except Exception as e:
            logger.error(f"Ошибка при удалении поста с ID {post_id}: {e}")
    else:
        logger.warning(f"Пост с ID {post_id} не найден.")

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

# === Удаление поста по ID ===
async def delete_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("У тебя нет доступа.")
        logger.warning("Неавторизованный доступ к /deletepost")
        return
    
    if context.args:
        try:
            post_id = int(context.args[0])
            delete_post(post_id)
            await update.message.reply_text(f"Пост с ID {post_id} был удалён.")
        except ValueError:
            await update.message.reply_text("Введите правильный ID поста.")
    else:
        await update.message.reply_text("Укажите ID поста для удаления.")

# === Функция для удаления старых постов ===
def auto_delete_old_posts():
    now = datetime.now()
    for post_id, post_time in list(posted_messages.items()):
        if now - post_time > timedelta(days=1):  # Удаляем посты старше 24 часов
            delete_post(post_id)

# === Асинхронный планировщик ===
async def run_schedule():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# === Основной запуск ===
async def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("createpost", create_post))
    application.add_handler(CommandHandler("deletepost", delete_post_command))  # Добавляем команду /deletepost

    # Расписание постов
    schedule.every().day.at("09:00").do(post_to_channel)
    schedule.every().day.at("12:00").do(post_to_channel)
    schedule.every().day.at("15:00").do(post_to_channel)
    schedule.every().day.at("18:00").do(post_to_channel)
    schedule.every().day.at("21:00").do(post_to_channel)

    # Расписание для отправки ежедневного отчёта
    schedule.every().day.at("22:00").do(send_daily_report)

    # Расписание для удаления старых постов (посты старше 24 часов)
    schedule.every().hour.do(auto_delete_old_posts)

    # Асинхронный запуск
    await asyncio.gather(application.run_polling(), run_schedule())

if __name__ == "__main__":
    asyncio.run(main())
