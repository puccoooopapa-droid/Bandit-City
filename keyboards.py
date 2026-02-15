from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Reply Keyboards ---

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Персонаж"), KeyboardButton(text="💼 Работа")],
            [KeyboardButton(text="🚕 Транспорт"), KeyboardButton(text="🏪 Магазины")],
            [KeyboardButton(text="💼 Бизнесы"), KeyboardButton(text="🏦 Банк")],
            [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="💎 Донат")],
            [KeyboardButton(text="📈 Трейдинг"), KeyboardButton(text="🏦 Инвестиции")],
            [KeyboardButton(text="🏆 Достижения"), KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )

def transport_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚕 Заказать такси")],
            [KeyboardButton(text="🚗 Поехать на своей")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

def confirm_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# --- Registration ---
def gender_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def district_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Центр"), KeyboardButton(text="Гетто")],
            [KeyboardButton(text="Элитный"), KeyboardButton(text="Промзона")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def reg_confirm_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Всё верно"), KeyboardButton(text="🔁 Начать заново")]
        ],
        resize_keyboard=True
    )

# --- Work ---
def work_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚕 Такси (Водитель)"), KeyboardButton(text="📦 Курьер")],
            [KeyboardButton(text="🧰 Подработка"), KeyboardButton(text="🏪 Грузчик")],
            [KeyboardButton(text="🧼 Клинер"), KeyboardButton(text="🏗 Стройка")],
            [KeyboardButton(text="💻 Хакер"), KeyboardButton(text="🍹 Бармен")], # Новые работы
            [KeyboardButton(text="🔪 Ограбление"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def courier_type_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍔 Еда"), KeyboardButton(text="📄 Документы")],
            [KeyboardButton(text="💻 Техника"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def courier_route_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Безопасно"), KeyboardButton(text="🟡 Быстро")],
            [KeyboardButton(text="🔴 Рискованно"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# --- Taxi Passenger ---
def taxi_passenger_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚕 Заказать такси")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def taxi_dest_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Центр"), KeyboardButton(text="Гетто")],
            [KeyboardButton(text="Элитный"), KeyboardButton(text="Промзона")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# --- Bank ---
def bank_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Взять кредит"), KeyboardButton(text="💸 Погасить кредит")],
            [KeyboardButton(text="🤝 Передать"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def transfer_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💸 Деньги"), KeyboardButton(text="🎁 Предметы")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# --- Casino ---
def casino_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎰 Слоты"), KeyboardButton(text="🃏 Блэкджек")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def blackjack_action_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Ещё"), KeyboardButton(text="🛑 Стоп")]
        ],
        resize_keyboard=True
    )

# --- Business ---
def business_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Мои бизнесы"), KeyboardButton(text="🛒 Купить бизнес")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# --- Inline Keyboards ---
def business_action_kb(biz_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"biz_upgrade:{biz_id}")],
        [InlineKeyboardButton(text="💰 Продать", callback_data=f"biz_sell:{biz_id}")]
    ])
