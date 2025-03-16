import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

TOKEN = "7597499330:AAFV_qzG1EpcW6cxN-MY2ZJwcwVQWJFL9GQ"
ADMIN_ID = 1089550963
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
db_path = "shop.db"

def init_db():
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                media_type TEXT,
                media TEXT
            )
        ''')
        conn.commit()

class ProductForm(StatesGroup):
    name = State()
    description = State()
    category = State()
    media_type = State()
    media = State()

class AdminState(StatesGroup):
    main = State()
    add_product = State()
    manage_products = State()

class UserState(StatesGroup):
    selecting_category = State()
    viewing_products = State()
    viewing_product = State()

def get_main_keyboard():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("🛍️ Начать поиск"),
        KeyboardButton("❓ Помощь")
    )

def get_user_mode_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🛍️ Начать поиск"))
    keyboard.add(KeyboardButton("❓ Помощь"))
    keyboard.add(KeyboardButton("🔙 Главное меню"))
    return keyboard

def get_admin_keyboard():
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add_product"),
        InlineKeyboardButton("🗑️ Удалить товар", callback_data="admin_delete_product"),
        InlineKeyboardButton("🔄 Редактировать товар", callback_data="admin_edit_product"),
        InlineKeyboardButton("❌ Удалить категорию", callback_data="admin_delete_category"),
        InlineKeyboardButton("✏️ Изменить категорию", callback_data="admin_edit_category"),
        InlineKeyboardButton("🔙 Выйти из админки", callback_data="admin_exit")
    )

def get_categories_keyboard():
    with sqlite3.connect(db_path) as conn:
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    keyboard = InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        keyboard.insert(InlineKeyboardButton(cat[0], callback_data=f"category_{cat[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    return keyboard

def get_product_keyboard(product_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🔙 К категориям", callback_data="back_to_categories"),
        InlineKeyboardButton("🔝 Главное меню", callback_data="main_menu")
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Выберите режим:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
            KeyboardButton("Пользовательский режим"),
            KeyboardButton("Админ панель")
        ))
    else:
        await message.answer("Добро пожаловать!", reply_markup=get_main_keyboard())

@dp.message_handler(text="Пользовательский режим", user_id=ADMIN_ID)
async def user_mode(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Переключен в пользовательский режим", reply_markup=get_main_keyboard())

@dp.message_handler(text="Админ панель", user_id=ADMIN_ID)
async def admin_panel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())
    await AdminState.main.set()

@dp.callback_query_handler(text="admin_exit", state=AdminState.main)
async def exit_admin(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("Вы вышли из админ-панели", reply_markup=get_main_keyboard())

@dp.callback_query_handler(text="admin_add_product", state=AdminState.main)
async def add_product(call: types.CallbackQuery):
    await call.message.answer("Введите название товара:")
    await ProductForm.name.set()

@dp.message_handler(state=ProductForm.name)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text
    await message.answer("Введите описание товара:")
    await ProductForm.description.set()

@dp.message_handler(state=ProductForm.description)
async def process_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text
    await message.answer("Введите категорию товара:")
    await ProductForm.category.set()

@dp.message_handler(state=ProductForm.category)
async def process_category(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['category'] = message.text
    await message.answer("Отправьте медиафайл (фото/видео):")
    await ProductForm.media_type.set()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO], state=ProductForm.media_type)
async def process_media(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['media_type'] = 'photo' if message.photo else 'video'
        data['media'] = message.photo[-1].file_id if message.photo else message.video.file_id

        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                INSERT INTO products (name, description, category, media_type, media)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data['name'],
                data['description'],
                data['category'],
                data['media_type'],
                data['media']
            ))
            conn.commit()
        
    await message.answer("✅ Товар успешно добавлен!", reply_markup=get_admin_keyboard())
    await AdminState.main.set()

@dp.callback_query_handler(text="admin_delete_product", state=AdminState.main)
async def delete_product(call: types.CallbackQuery):
    with sqlite3.connect(db_path) as conn:
        products = conn.execute("SELECT id, name FROM products").fetchall()
    keyboard = InlineKeyboardMarkup(row_width=1)
    for product in products:
        keyboard.add(InlineKeyboardButton(product[1], callback_data=f"delete_{product[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    await call.message.answer("Выберите товар для удаления:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("delete_"), state=AdminState.main)
async def confirm_delete(call: types.CallbackQuery):
    product_id = call.data.split("_")[1]
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    await call.message.answer("Товар удален!", reply_markup=get_admin_keyboard())

@dp.callback_query_handler(text="admin_edit_product", state=AdminState.main)
async def edit_product(call: types.CallbackQuery):
    with sqlite3.connect(db_path) as conn:
        products = conn.execute("SELECT id, name FROM products").fetchall()
    keyboard = InlineKeyboardMarkup(row_width=1)
    for product in products:
        keyboard.add(InlineKeyboardButton(product[1], callback_data=f"edit_{product[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    await call.message.answer("Выберите товар для редактирования:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("edit_"), state=AdminState.main)
async def edit_product_handler(call: types.CallbackQuery, state: FSMContext):
    product_id = call.data.split("_")[1]
    with sqlite3.connect(db_path) as conn:
        product = conn.execute(
            "SELECT name, description FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    await state.update_data(product_id=product_id)
    await call.message.answer(f"Редактирование товара '{product[0]}'")
    await call.message.answer(f"Текущее название: {product[0]}\nВведите новое название:")
    await ProductForm.name.set()

@dp.callback_query_handler(text="admin_delete_category", state=AdminState.main)
async def delete_category(call: types.CallbackQuery):
    with sqlite3.connect(db_path) as conn:
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    if not categories:
        await call.message.answer("❌ Нет доступных категорий для удаления.")
        return
    keyboard = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        keyboard.add(InlineKeyboardButton(cat[0], callback_data=f"delete_cat_{cat[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_main"))
    await call.message.answer("Выберите категорию для удаления:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("delete_cat_"), state=AdminState.main)
async def confirm_delete_category(call: types.CallbackQuery):
    category = call.data.split("_")[2]
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM products WHERE category = ?", (category,))
        conn.commit()
    await call.message.answer(f"✅ Категория '{category}' успешно удалена!", reply_markup=get_admin_keyboard())

@dp.callback_query_handler(text="admin_edit_category", state=AdminState.main)
async def edit_category(call: types.CallbackQuery):
    await call.message.answer("Введите название категории для изменения:")
    await AdminState.manage_products.set()

@dp.message_handler(state=AdminState.manage_products)
async def process_old_category(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['old_category'] = message.text
    await message.answer(f"Введите новое название для категории '{data['old_category']}':")
    await AdminState.add_product.set()

@dp.message_handler(state=AdminState.add_product)
async def confirm_edit_category(message: types.Message, state: FSMContext):
    new_category = message.text
    async with state.proxy() as data:
        old_category = data['old_category']
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE products SET category = ? WHERE category = ?", (new_category, old_category))
        conn.commit()
    await message.answer(f"✅ Категория '{old_category}' успешно изменена на '{new_category}'!", reply_markup=get_admin_keyboard())
    await AdminState.main.set()

@dp.message_handler(text="🛍️ Начать поиск", state="*")
async def start_search(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Выберите категорию:", reply_markup=get_categories_keyboard())
    await UserState.selecting_category.set()

@dp.callback_query_handler(lambda c: c.data.startswith("category_"), state=UserState.selecting_category)
async def show_products(call: types.CallbackQuery):
    category = call.data.split("_")[1]
    with sqlite3.connect(db_path) as conn:
        products = conn.execute(
            "SELECT id, name FROM products WHERE category = ?", (category,)
        ).fetchall()

    if not products:
        await call.message.answer(f"❌ В категории '{category}' пока нет товаров")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for product in products:
        keyboard.add(InlineKeyboardButton(product[1], callback_data=f"product_{product[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))

    await call.message.answer(f"🛒 Товары в категории '{category}':", reply_markup=keyboard)
    await UserState.viewing_products.set()

@dp.callback_query_handler(lambda c: c.data.startswith("product_"), state=UserState.viewing_products)
async def show_product_details(call: types.CallbackQuery):
    product_id = call.data.split("_")[1]
    with sqlite3.connect(db_path) as conn:
        product = conn.execute(
            "SELECT name, description, category, media_type, media FROM products WHERE id = ?", (product_id,)
        ).fetchone()

    response = f"Название: {product[0]}\nОписание: {product[1]}\nКатегория: {product[2]}"

    try:
        if product[3] == "photo":
            await call.message.answer_photo(photo=product[4], caption=response, reply_markup=get_product_keyboard(product_id))
        elif product[3] == "video":
            await call.message.answer_video(video=product[4], caption=response, reply_markup=get_product_keyboard(product_id))
    except Exception:
        await call.message.answer(f"Ошибка загрузки медиа\n\n{response}", reply_markup=get_product_keyboard(product_id))

    await UserState.viewing_product.set()

@dp.callback_query_handler(text="back_to_categories", state=UserState.viewing_product)
async def back_to_categories(call: types.CallbackQuery):
    await call.message.answer("Выберите категорию:", reply_markup=get_categories_keyboard())
    await UserState.selecting_category.set()

@dp.message_handler(text="❓ Помощь", state="*")
async def help_command(message: types.Message):
    help_text = (
        "В пользовательском режиме доступно:\n"
        "1. Поиск товаров по категориям\n"
        "2. Просмотр деталей товаров\n"
        "3. Навигация с помощью кнопок 'Назад'\n"
        "4. Выход через '🔙 Главное меню'"
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())

@dp.message_handler(text="🔙 Главное меню", state="*")
async def exit_user_mode(message: types.Message, state: FSMContext):
    await state.finish()
    if message.from_user.id == ADMIN_ID:
        await message.answer("Главное меню:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
            KeyboardButton("Пользовательский режим"),
            KeyboardButton("Админ панель")
        ))
    else:
        await message.answer("Главное меню:", reply_markup=get_main_keyboard())

@dp.callback_query_handler(text="main_menu", state="*")
async def back_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    if call.from_user.id == ADMIN_ID:
        await call.message.answer("Главное меню:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
            KeyboardButton("Пользовательский режим"),
            KeyboardButton("Админ панель")
        ))
    else:
        await call.message.answer("Главное меню:", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    init_db()
    executor.start_polling(dp, skip_updates=True)