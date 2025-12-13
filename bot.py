import os
import logging
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import sqlite3

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

# RSS-ленты
RSS_FEEDS = {
    'lenta': 'https://lenta.ru/rss',
    'ria': 'https://ria.ru/export/rss2/archive/index.xml',
    'tass': 'https://tass.ru/rss/v2.xml',
    'interfax': 'https://www.interfax.ru/rss.asp'
}

# База данных для хранения подписчиков
def init_db():
    conn = sqlite3.connect('subscribers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id INTEGER PRIMARY KEY,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_subscriber(chat_id):
    conn = sqlite3.connect('subscribers.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)', (chat_id,))
    conn.commit()
    conn.close()

def remove_subscriber(chat_id):
    conn = sqlite3.connect('subscribers.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subscribers WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

def get_all_subscribers():
    conn = sqlite3.connect('subscribers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM subscribers')
    subscribers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subscribers

# Функция для парсинга новостей
def fetch_news(limit=5):
    news = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'source': source.upper(),
                    'published': entry.get('published', 'N/A')
                })
        except Exception as e:
            logger.error(f"Ошибка парсинга {source}: {e}")
    return news[:limit]

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Привет! Я новостной бот.\n\n"
        "Команды:\n"
        "/news - Получить последние новости\n"
        "/subscribe - Подписаться на автообновления\n"
        "/unsubscribe - Отписаться от обновлений"
    )

async def get_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Ищу новости...")
    news = fetch_news(5)
    
    if not news:
        await update.message.reply_text("❌ Не удалось получить новости.")
        return
    
    message = "📰 *Последние новости:*\n\n"
    for item in news:
        message += f"🔹 *{item['source']}*: {item['title']}\n🔗 {item['link']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_subscriber(chat_id)
    await update.message.reply_text("✅ Вы подписались на автообновления новостей!")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    remove_subscriber(chat_id)
    await update.message.reply_text("❌ Вы отписались от автообновлений.")

# Автообновление новостей для подписчиков
async def auto_update_news(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Запуск автообновления новостей...")
    subscribers = get_all_subscribers()
    
    if not subscribers:
        logger.info("Нет подписчиков для отправки новостей")
        return
    
    news = fetch_news(3)
    
    if not news:
        logger.warning("Не удалось получить новости для автообновления")
        return
    
    message = "📰 *Автообновление новостей:*\n\n"
    for item in news:
        message += f"🔹 *{item['source']}*: {item['title']}\n🔗 {item['link']}\n\n"
    
    for chat_id in subscribers:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            logger.info(f"Новости отправлены подписчику {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки новостей подписчику {chat_id}: {e}")

# Главная функция
def main():
    logger.info("Запуск бота...")
    init_db()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("news", get_news))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    
    # Настройка автообновления новостей каждые 30 минут
    if application.job_queue:
        application.job_queue.run_repeating(auto_update_news, interval=1800, first=10)
        logger.info("Автообновление новостей настроено (каждые 30 минут)")
    else:
        logger.warning("JobQueue недоступен. Автообновление отключено.")
    
    # Запуск бота
    logger.info("Бот успешно запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
