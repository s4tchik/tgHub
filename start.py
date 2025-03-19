import logging
from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes
)
import requests
from datetime import datetime
import re

# Настройки
BOT_TOKEN = "1"
GOOGLE_SCRIPT_URL = "1"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
(MAIN_MENU, QUIZ_ATMOSPHERE, QUIZ_COMPANY,
 QUIZ_CREATION, CLASS_PICK, DATE_PICK,
 CUSTOM_DATE, PHONE, FAQ) = range(9)

# Текстовые константы
TEXTS = {
    'welcome': "Добро пожаловать в GlassBaker! 🎨\nВыберите действие:",
    'classes': "Наши мастер-классы:",
    'class_details': "**{name}**\n\n{description}\n\nДаты: {dates}",
    'date_prompt': "Выберите дату:",
    'custom_date_prompt': "Введите дату в формате ДД.ММ.ГГГГ:",
    'phone_prompt': "Введите ваш телефон в формате +79123456789:",
    'invalid_phone': "Неверный формат! Используйте +79123456789:",
    'invalid_date': "Неверный формат даты! Попробуйте снова:",
    'booking_success': (
        "✅ Запись подтверждена!\n"
        "Класс: {class_name}\n"
        "Дата: {date}\n"
        "Телефон: {phone}"
    ),
    'faq': (
        "❓ Часто задаваемые вопросы:\n\n"
        "1. Как записаться?\n- Используйте кнопку 'Запись'\n"
        "2. Можно с детьми?\n- Да, есть семейные мастер-классы"
    ),
    'operator_request': "Оператор получил ваш запрос. Ожидайте ответа!"
}

# Основное меню
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["🎨 О мастер-классах", "🎯 Быстрый квиз"],
    ["📅 Запись", "❓ FAQ"],
    ["💬 Оператор"]
], resize_keyboard=True)

# Данные мастер-классов
CLASSES = {
    "lampwork": {
        "name": "Lampwork (бусины в огне)",
        "description": "Изготовление стеклянных бусин на открытом огне. Подходит для новичков.",
        "dates": ["20.03.2025", "25.03.2025"]
    },
    "tiffany": {
        "name": "Витраж «Тиффани»",
        "description": "Создание витражей в технике Тиффани.",
        "dates": ["22.03.2025", "27.03.2025"]
    },
    "fusing": {
        "name": "Фьюзинг",
        "description": "Создание изделий из стекла методом спекания.",
        "dates": ["21.03.2025", "26.03.2025"]
    },
    "family": {
        "name": "Семейные форматы",
        "description": "Мастер-классы для всей семьи.",
        "dates": ["23.03.2025", "28.03.2025"]
    }
}


def create_classes_keyboard():
    return [
        [InlineKeyboardButton(cls['name'], callback_data=f"class_{id}")]
        for id, cls in CLASSES.items()
    ] + [[InlineKeyboardButton("Назад", callback_data="back_main")]]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(TEXTS['welcome'], reply_markup=MAIN_KEYBOARD)
    elif update.callback_query:
        await update.callback_query.message.reply_text(TEXTS['welcome'], reply_markup=MAIN_KEYBOARD)
    return MAIN_MENU


async def show_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = create_classes_keyboard()
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(
                TEXTS['classes'],
                reply_markup=markup
            )
        except Exception as e:
            if "not modified" in str(e):
                await query.answer()
                return CLASS_PICK
    else:
        await update.message.reply_text(
            TEXTS['classes'],
            reply_markup=markup
        )

    return CLASS_PICK


async def class_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_main":
        try:
            await query.edit_message_text(
                TEXTS['welcome'],
                reply_markup=MAIN_KEYBOARD
            )
        except Exception as e:
            if "not modified" in str(e):
                await query.answer()
        return MAIN_MENU

    # Проверяем, что callback_data соответствует формату "class_<id>"
    if not query.data.startswith("class_"):
        await query.answer("Ошибка: неверный формат данных")
        return CLASS_PICK

    class_id = query.data.split("_")[1]

    # Проверяем, что class_id существует в CLASSES
    if class_id not in CLASSES:
        await query.answer("Ошибка: мастер-класс не найден")
        return CLASS_PICK

    cls = CLASSES[class_id]
    context.user_data['class'] = class_id

    new_text = TEXTS['class_details'].format(
        name=cls['name'],
        description=cls['description'],
        dates=', '.join(cls['dates'])
    )

    keyboard = [
        [InlineKeyboardButton("Записаться", callback_data=f"book_{class_id}")],
        [InlineKeyboardButton("Назад", callback_data="back_classes")]
    ]

    try:
        await query.edit_message_text(
            new_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        if "not modified" in str(e):
            await query.answer()

    return CLASS_PICK


async def book_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    class_id = query.data.split("_")[1]
    cls = CLASSES[class_id]
    context.user_data['class'] = class_id

    keyboard = [
        [KeyboardButton(date) for date in cls['dates']],
        [KeyboardButton("Своя дата")]
    ]

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=TEXTS['date_prompt'],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DATE_PICK


async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if user_input == "Своя дата":
        await update.message.reply_text(
            TEXTS['custom_date_prompt'],
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад")]], resize_keyboard=True)
        )
        return CUSTOM_DATE

    context.user_data['date'] = user_input
    await update.message.reply_text(
        TEXTS['phone_prompt'],
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад")]], resize_keyboard=True)
    )
    return PHONE


async def handle_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if user_input == "Назад":
        return await show_classes(update, context)

    try:
        datetime.strptime(user_input, "%d.%m.%Y")
        context.user_data['date'] = user_input
        await update.message.reply_text(
            TEXTS['phone_prompt'],
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад")]], resize_keyboard=True)
        )
        return PHONE
    except ValueError:
        await update.message.reply_text(TEXTS['invalid_date'])
        return CUSTOM_DATE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if user_input == "Назад":
        return await show_classes(update, context)

    if not re.fullmatch(r'^\+7\d{10}$', user_input):
        await update.message.reply_text(TEXTS['invalid_phone'])
        return PHONE

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = requests.post(
            GOOGLE_SCRIPT_URL,
            data={
                'timestamp': timestamp,
                'name': update.message.from_user.first_name,
                'phone': user_input,
                'class': CLASSES[context.user_data['class']]['name'],
                'date': context.user_data['date']
            }
        )

        if response.status_code != 200:
            raise Exception(f"HTTP Error: {response.status_code}")

        if "success" not in response.text.lower():
            raise Exception("Google Script Error: " + response.text)

    except Exception as e:
        logger.error(f"Ошибка записи: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка записи. Попробуйте позже.")
        return MAIN_MENU

    await update.message.reply_text(
        TEXTS['booking_success'].format(
            class_name=CLASSES[context.user_data['class']]['name'],
            date=context.user_data['date'],
            phone=user_input
        ),
        reply_markup=MAIN_KEYBOARD
    )
    return MAIN_MENU


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([
        ["Спокойная", "Весёлая"],
        ["Яркая", "Быстрая"],
        ["Назад"]
    ], resize_keyboard=True)
    await update.message.reply_text("Какая атмосфера вам ближе?", reply_markup=keyboard)
    return QUIZ_ATMOSPHERE


async def quiz_atmosphere(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Назад":
        await start(update, context)
        return MAIN_MENU

    context.user_data['atmosphere'] = update.message.text
    keyboard = ReplyKeyboardMarkup([
        ["Один", "С другом"],
        ["Семья", "Группа"],
        ["Назад"]
    ], resize_keyboard=True)
    await update.message.reply_text("С кем вы придёте?", reply_markup=keyboard)
    return QUIZ_COMPANY


async def quiz_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Назад":
        return await start_quiz(update, context)

    context.user_data['company'] = update.message.text
    keyboard = ReplyKeyboardMarkup([
        ["Украшение", "Витраж"],
        ["Просто попробовать"],
        ["Назад"]
    ], resize_keyboard=True)
    await update.message.reply_text("Что хотите создать?", reply_markup=keyboard)
    return QUIZ_CREATION


async def quiz_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Назад":
        return await quiz_atmosphere(update, context)

    recommended = "tiffany" if "Витраж" in update.message.text else "lampwork"
    context.user_data['class'] = recommended
    cls = CLASSES[recommended]

    keyboard = [
        [KeyboardButton(date) for date in cls['dates']],
        [KeyboardButton("Своя дата"), KeyboardButton("Назад")]
    ]
    await update.message.reply_text(
        f"Рекомендуем: {cls['name']}\nВыберите дату:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DATE_PICK


async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXTS['faq'],
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад")]], resize_keyboard=True)
    )
    return FAQ


async def operator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS['operator_request'], reply_markup=MAIN_KEYBOARD)
    return MAIN_MENU


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex(r'^(🎨 О мастер-классах|📅 Запись)$'), show_classes),
                MessageHandler(filters.Regex('^🎯 Быстрый квиз$'), start_quiz),
                MessageHandler(filters.Regex('^❓ FAQ$'), faq_handler),
                MessageHandler(filters.Regex('^💬 Оператор$'), operator_handler),
            ],
            CLASS_PICK: [
                CallbackQueryHandler(class_details, pattern=r'^class_'),
                CallbackQueryHandler(book_class, pattern=r'^book_'),
                CallbackQueryHandler(start, pattern=r'^back_main'),
                CallbackQueryHandler(show_classes, pattern=r'^back_classes'),
            ],
            DATE_PICK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date),
            ],
            CUSTOM_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_date),
                MessageHandler(filters.Regex('^Назад$'), show_classes)
            ],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone),
                MessageHandler(filters.Regex('^Назад$'), show_classes)
            ],
            QUIZ_ATMOSPHERE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_atmosphere),
                MessageHandler(filters.Regex('^Назад$'), start)
            ],
            QUIZ_COMPANY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_company),
                MessageHandler(filters.Regex('^Назад$'), start_quiz)
            ],
            QUIZ_CREATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_creation),
                MessageHandler(filters.Regex('^Назад$'), quiz_atmosphere)
            ],
            FAQ: [
                MessageHandler(filters.Regex('^Назад$'), start)
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
