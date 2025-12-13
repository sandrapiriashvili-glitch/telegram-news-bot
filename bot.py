import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import feedparser
from datetime import datetime, timedelta
import sqlite3
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram токен
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# RSS источники новостей
RSS_FEEDS = [
    'https://lenta.ru/rss',
    'https://www.vedomosti.ru/rss/news',
    'https://tass.ru/rss/v2.xml',
    'https://ria.ru/export/rss2/archive/index.xml',
]

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Парсинг новостей из RSS
def fetch_news():
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    new_count = 0
    
    for feed_url in RSS_FEEDS:
        try:
            logger.info(f"Парсинг: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:10]:  # Берём последние 10 новостей
                title = entry.get('title', 'Без заголовка')
                link = entry.get('link', '')
                published = entry.get('published', '')
                source = feed.feed.get('title', 'Неизвестный источник')
                
                try:
                    c.execute('''
                        INSERT INTO news (title, link, published, source)
                        VALUES (?, ?, ?, ?)
                    ''', (title, link, published, source))
                    new_count += 1
                except sqlite3.IntegrityError:
                    pass  # Новость уже существует
        except Exception as e:
            logger.error(f"Ошибка при парсинге {feed_url}: {e}")
    
    conn.commit()
    conn.close()
    logger.info(f"Добавлено новостей: {new_count}")
    return new_count

# Получение последних новостей
def get_latest_news(limit=5):
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute('''
        SELECT title, link, source, created_at 
        FROM news 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    news = c.fetchall()
    conn.close()
    return news

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📰 Показать новости")],
        [KeyboardButton("ℹ️ О боте"), KeyboardButton("🔄 Обновить новости")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Привет! Я бот для сбора новостей.\n\n"
        "Нажми *📰 Показать новости*, чтобы увидеть последние новости.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "📰 Показать новости":
        news = get_latest_news(5)
        if news:
            response = "📰 *Последние новости:*\n\n"
            for i, (title, link, source, created_at) in enumerate(news, 1):
                response += f"{i}. *{title}*\n"
                response += f"   🔗 [Читать]({link})\n"
                response += f"   📌 Источник: {source}\n\n"
            await update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await update.message.reply_text("❌ Новостей пока нет. Попробуй обновить!")
    
    elif text == "🔄 Обновить новости":
        await update.message.reply_text("⏳ Обновляю новости...")
        count = fetch_news()
        await update.message.reply_text(f"✅ Добавлено новых новостей: {count}")
    
    elif text == "ℹ️ О боте":
        await update.message.reply_text(
            "ℹ️ *О боте*\n\n"
            "Я собираю новости из популярных источников:\n"
            "• Лента.ру\n"
            "• Ведомости\n"
            "• ТАСС\n"
            "• РИА Новости\n\n"
            "Новости обновляются каждые 30 минут автоматически.",
            parse_mode='Markdown'
        )
    
    else:
        await update.message.reply_text("❓ Используй кнопки меню для взаимодействия с ботом.")

# Фоновое обновление новостей
async def auto_update_news(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Автоматическое обновление новостей...")
    fetch_news()

# Основная функция
def main():
    # Инициализация БД
    init_db()
    
    # Первая загрузка новостей
    logger.info("Загрузка начальных новостей...")
    fetch_news()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Настройка автообновления новостей каждые 30 минут
   if application.job_queue:
    application.job_queue.run_repeating(auto_update_news, interval=1800, first=10)
else:
    logger.warning("JobQueue не настроен. Автообновление отключено.")
    job_queue.run_repeating(auto_update_news, interval=1800, first=1800)  # 1800 сек = 30 мин
    
    # Запуск бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
