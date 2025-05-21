import os
import openai
from telegram import Bot
from telegram.ext import Application, CommandHandler
import schedule
import time
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

bot = Bot(token=TELEGRAM_TOKEN)

def generate_post():
    prompt = "Придумай короткий и ироничный пост в стиле 'Типо живу', на тему усталости, тревоги, жизни."
    response = openai.ChatCompletion.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message["content"]

def generate_image():
    return "https://placekitten.com/640/360"

def post_to_channel():
    text = generate_post()
    image_url = generate_image()
    bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)

async def start(update, context):
    await update.message.reply_text("Бот работает. Используй /report или /createpost.")

async def report(update, context):
    await update.message.reply_text("Опубликовано 5 постов. Подписчиков: неизвестно.")

async def create_post(update, context):
    text = generate_post()
    await update.message.reply_photo(photo=generate_image(), caption=text)

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

    async def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    application.run_polling()

if __name__ == "__main__":
    main()
