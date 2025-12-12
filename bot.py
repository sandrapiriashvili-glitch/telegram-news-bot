import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

DATA_FILE = 'news.json'

def load_news():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_news(news_list):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📰 Показать новости"), KeyboardButton("➕ Добавить новость")]]
    await update.message.reply_text(
        "👋 Привет! Я бот для управления новостями.\n\nВыбери действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_list = load_news()
    if not news_list:
        await update.message.reply_text("📭 Новостей пока нет")
        return
    
    text = "📰 *Список новостей:*\n\n"
    for i, news in enumerate(news_list, 1):
        text += f"{i}. {news}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_news_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_news'] = True
    await update.message.reply_text("✍️ Напиши текст новости:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_news'):
        news_list = load_news()
        news_list.append(update.message.text)
        save_news(news_list)
        context.user_data['waiting_news'] = False
        await update.message.reply_text("✅ Новость добавлена!")
    else:
        await update.message.reply_text("Используй кнопки меню")

def main():
    token = os.getenv('BOT_TOKEN')
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📰 Показать новости$"), show_news))
    app.add_handler(MessageHandler(filters.Regex("^➕ Добавить новость$"), add_news_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    port = int(os.getenv('PORT', 8080))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=f"{os.getenv('RENDER_EXTERNAL_URL')}/{token}",
        url_path=token
    )

if __name__ == '__main__':
    main()
