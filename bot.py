import os
import logging
import sqlite3
import asyncio
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# === НАСТРОЙКИ ===
BOT_TOKEN = "8084175310:AAHcesuZy1oiiLpFXMIybdo9KNReBN6SlnY"
ADMIN_ID = 7221610910

# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('finservice_bot.db', check_same_thread=False)
    c = conn.cursor()
    
    # Удаляем старую таблицу если есть проблемы
    c.execute("DROP TABLE IF EXISTS stats")
    
    # Создаем новую таблицу с правильной структурой
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (date TEXT PRIMARY KEY, users INTEGER, active INTEGER, conversions INTEGER)''')
    
    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                  reg_date TEXT, last_active TEXT)''')
    
    # Проверяем есть ли сегодняшняя дата
    today = date.today().isoformat()
    c.execute("SELECT COUNT(*) FROM stats WHERE date = ?", (today,))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats (date, users, active, conversions) VALUES (?, 0, 0, 0)", (today,))
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def update_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect('finservice_bot.db', check_same_thread=False)
    c = conn.cursor()
    today = datetime.now().isoformat()
    
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_name, reg_date, last_active) 
                 VALUES (?, ?, ?, COALESCE((SELECT reg_date FROM users WHERE user_id = ?), ?), ?)''',
              (user_id, username, first_name, user_id, today, today))
    
    # Обновляем дневную статистику
    today_date = date.today().isoformat()
    c.execute("UPDATE stats SET users = users + 1 WHERE date = ? AND NOT EXISTS (SELECT 1 FROM users WHERE user_id = ? AND reg_date < ?)", 
              (today_date, user_id, today))
    c.execute("UPDATE stats SET active = active + 1 WHERE date = ?", (today_date,))
    
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('finservice_bot.db', check_same_thread=False)
    c = conn.cursor()
    
    # Общая статистика
    c.execute("SELECT SUM(users), SUM(active), SUM(conversions) FROM stats")
    total_stats = c.fetchone()
    
    # Сегодняшняя статистика
    today = date.today().isoformat()
    c.execute("SELECT users, active, conversions FROM stats WHERE date = ?", (today,))
    today_stats = c.fetchone()
    
    # Всего пользователей
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_active': total_stats[1] or 0,
        'total_conversions': total_stats[2] or 0,
        'today_users': today_stats[0] if today_stats else 0,
        'today_active': today_stats[1] if today_stats else 0,
        'today_conversions': today_stats[2] if today_stats else 0
    }

# === ТЕКСТЫ ===
START_TEXT = """🚀 <b>ХВАТИТ ИСКАТЬ РАБОТУ - ЗАРАБОТАЙ СЕЙЧАС!</b>

💰 <b>от 500₽ до 2500₽</b> за оформление банковской карты

✅ <b>Преимущества:</b>
• 💳 Карта должна быть <b>ПЕРВОЙ</b> от этого банка
• 💸 Нужна одна покупка от 500₽ (<b>деньги даём МЫ</b>)
• 🚀 Деньги <b>РЕАЛЬНЫЕ</b>, выплата в течение 24 часов
• 📈 Список карт постоянно пополняется
• ⏱ 15 минут на оформление
• 🛡️ 100% гарантия выплаты

🎯 <b>А если не получится заработать - я лично отправлю тебе 3000₽ за потраченное время!</b>

Готов начать?"""

CARDS_TEXT = """🎯 <b>ВЫБЕРИ КАРТУ И ЗАРАБОТАЙ:</b>

💳 <b>Дебетовые карты:</b>
• Т-Банк Black - <b>700₽</b>
• МТС Деньги - <b>700₽</b>  
• ВТБ МИР - <b>1000₽</b>
• Альфа-Банк - <b>700₽</b>
• Фора-Банк - <b>700₽</b>
• Газпромбанк - <b>700₽</b>

💸 <b>Кредитные карты:</b>
• Т-Банк Платинум - <b>2000₽</b>
• Совкомбанк Халва - <b>1000₽</b>
• Альфа-Банк Кредитная - <b>700₽</b>
• Уралсиб Банк - <b>2000₽</b>

💰 <b>МЫ ФИНАНСИРУЕМ</b> твою первую покупку 500₽ по ЛЮБОЙ карте!

👇 Переходи на сайт, выбирай карту:"""

INSTRUCTION_TEXT = """📋 <b>ПОШАГОВАЯ ИНСТРУКЦИЯ:</b>

1️⃣ <b>Выбираешь карту</b> на сайте (<b>ВПЕРВЫЕ</b> для этого банка)
2️⃣ <b>Оформляешь</b> по нашей ссылке на сайте
3️⃣ <b>Получаешь карту</b> (доставка бесплатная)
4️⃣ <b>Активируешь</b> и делаешь покупку от 500₽
5️⃣ <b>Присылаешь нам чек</b>/подтверждение
6️⃣ <b>Получаешь выплату</b> в течение 24 часов!

💡 <b>Важно:</b> карта бесплатная, ты платишь только за свою покупку

👩‍💼 <b>Контакты менеджера:</b> @bussstle"""

REFERRAL_TEXT = """👥 <b>ПРИГЛАСИ ДРУГА - ПОЛУЧИ БОНУС!</b>

🎁 <b>За каждого друга который оформит карту:</b>
• ➕ <b>Ты получаешь:</b> 300₽ бонус
• ➕ <b>Друг получает:</b> полную выплату за карту

🔗 <b>Твоя реферальная ссылка:</b>
<code>https://t.me/finsrvc_bot?start=ref_{user_id}</code>

📤 <b>Просто отправь другу эту ссылку!</b>"""

FAQ_TEXT = """❓ <b>ЧАСТЫЕ ВОПРОСЫ:</b>

💸 <b>Как происходит выплата?</b>
✅ Сначала получаешь 500₽ на покупку, после чека - остальную сумму

📈 <b>Будут ли новые карты?</b>
✅ Да, постоянно добавляем новые карты и банки

💳 <b>А если у меня уже есть карта этого банка?</b>
✅ Платим только за первую карту от банка

👩‍💼 <b>Как получить деньги на покупку?</b>
✅ Напиши менеджеру @bussstle когда получишь карту

🎯 <b>Какая карта самая выгодная?</b>
✅ Уралсиб Банк и Т-Банк Платинум - 1500₽ выплата после покупки

⏱ <b>Сколько ждать выплату?</b>
✅ В течение 24 часов после предоставления чека"""

MANAGER_TEXT = """👩‍💼 <b>ВАШ МЕНЕДЖЕР</b>

💁 <b>Яна</b> - поможет с любыми вопросами:
• ❌ Не получается оформить карту
• 💰 Проблемы с выплатой  
• 🤝 Хочешь обсудить условия
• 🔧 Технические неполадки
• 📊 Статус заявки

📞 <b>Напиши ей в Telegram:</b>
👉 @bussstle

⏰ <b>Время работы:</b> ежедневно 10:00-22:00 по МСК"""

# === КЛАВИАТУРЫ ===
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 ВЫБРАТЬ КАРТУ", callback_data="choose_card")],
        [InlineKeyboardButton("📋 ИНСТРУКЦИЯ", callback_data="instruction")],
        [InlineKeyboardButton("👥 ПРИГЛАСИТЬ ДРУЗЕЙ", callback_data="referral")],
        [InlineKeyboardButton("❓ ЧАСТЫЕ ВОПРОСЫ", callback_data="faq")],
        [InlineKeyboardButton("👩‍💼 МЕНЕДЖЕР", callback_data="manager")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]])

def website_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 ПЕРЕЙТИ НА САЙТ", url="https://fin-serv.ru")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]
    ])

# === ОБРАБОТЧИКИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"👤 Новый пользователь: {user.id} (@{user.username})")
    update_user(user.id, user.username, user.first_name)
    
    # Обработка реферальных ссылок
    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0][4:])
            print(f"🔗 Реферальный переход от {referrer_id} к {user.id}")
        except:
            pass
    
    await update.message.reply_text(
        START_TEXT, 
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"🔍 Команда /admin от пользователя {user_id}")
    
    if user_id != ADMIN_ID:
        print(f"❌ Доступ запрещен для {user_id}")
        await update.message.reply_text("❌ <b>Доступ запрещён</b>", parse_mode='HTML')
        return
    
    print("✅ Админ авторизован")
    stats = get_stats()
    conversion_rate = (stats['total_conversions'] / stats['total_active'] * 100) if stats['total_active'] > 0 else 0
    
    text = f"""📊 <b>АДМИН ПАНЕЛЬ</b>

👥 <b>Пользователи:</b>
• Всего: <b>{stats['total_users']}</b>
• Новых сегодня: <b>{stats['today_users']}</b>
• Активных сегодня: <b>{stats['today_active']}</b>

💰 <b>Конверсия:</b>
• Всего: <b>{stats['total_conversions']}</b>
• Сегодня: <b>{stats['today_conversions']}</b>
• Rate: <b>{conversion_rate:.1f}%</b>

⚡ <b>Команды:</b>
/stat - детальная статистика"""
    
    await update.message.reply_text(text, parse_mode='HTML')

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"📈 Команда /stat от пользователя {user_id}")
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ <b>Доступ запрещён</b>", parse_mode='HTML')
        return
    
    stats = get_stats()
    conversion_rate = (stats['total_conversions'] / stats['total_active'] * 100) if stats['total_active'] > 0 else 0
    
    text = f"""📈 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>

📅 <b>За всё время:</b>
• 👥 Пользователей: <b>{stats['total_users']}</b>
• 🔄 Активных: <b>{stats['total_active']}</b>
• 💰 Конверсий: <b>{stats['total_conversions']}</b>

📊 <b>Сегодня ({date.today().strftime('%d.%m.%Y')}):</b>
• 👥 Новых: <b>{stats['today_users']}</b>
• 🔄 Активных: <b>{stats['today_active']}</b>
• 💰 Конверсий: <b>{stats['today_conversions']}</b>

📊 <b>Метрики:</b>
• 📈 Конверсия: <b>{conversion_rate:.1f}%</b>

🕒 <b>Обновлено:</b> {datetime.now().strftime('%H:%M:%S')}"""
    
    await update.message.reply_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    print(f"🖱️ Нажата кнопка {query.data} пользователем {user.id}")
    update_user(user.id, user.username, user.first_name)
    
    if query.data == "choose_card":
        await query.edit_message_text(
            CARDS_TEXT, 
            reply_markup=website_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == "instruction":
        await query.edit_message_text(
            INSTRUCTION_TEXT, 
            reply_markup=back_button_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == "referral":
        text = REFERRAL_TEXT.format(user_id=user.id)
        await query.edit_message_text(
            text, 
            reply_markup=back_button_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == "faq":
        await query.edit_message_text(
            FAQ_TEXT, 
            reply_markup=back_button_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == "manager":
        await query.edit_message_text(
            MANAGER_TEXT, 
            reply_markup=back_button_keyboard(),
            parse_mode='HTML'
        )
    elif query.data == "back_to_main":
        await query.edit_message_text(
            START_TEXT, 
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

# === ЗАПУСК ===
def main():
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Инициализация БД
    init_db()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("stat", stat_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запуск бота
    print("=" * 50)
    print("🤖 FinService Bot ЗАПУЩЕН ЛОКАЛЬНО!")
    print(f"📍 Папка: {os.getcwd()}")
    print(f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    
    try:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            close_loop=False
        )
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        import time
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()