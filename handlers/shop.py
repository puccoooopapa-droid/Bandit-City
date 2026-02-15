from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_kb, confirm_kb
from services.economy import update_money, get_user, check_jail
from database import db
import time
import logging

router = Router()
logger = logging.getLogger(__name__)

# --- Конфигурация товаров (Единый источник правды) ---
SHOP_ITEMS = {
    "food": {
        "name": "🥖 Продукты",
        "district": "Центр",
        "items": [
            {"id": "bread", "name": "Хлеб", "price": 50, "energy_restore": 5},
            {"id": "milk", "name": "Молоко", "price": 80, "energy_restore": 8},
            {"id": "burger", "name": "Бургер", "price": 150, "energy_restore": 15},
            {"id": "pizza", "name": "Пицца", "price": 500, "energy_restore": 40},
            {"id": "cola", "name": "Кола", "price": 100, "energy_restore": 10},
            {"id": "beer", "name": "Пиво", "price": 200, "energy_restore": 10},
            {"id": "whiskey", "name": "Виски", "price": 2000, "energy_restore": 0},
            {"id": "caviar", "name": "Икра", "price": 5000, "energy_restore": 70},
        ]
    },
    "house": {
        "name": "🏠 Недвижимость",
        "district": "Элитный",
        "items": [
            {"id": "box", "name": "Коробка", "price": 0, "garage_slots": 0, "home_district": "Гетто"},
            {"id": "room", "name": "Комната", "price": 50000, "garage_slots": 1, "home_district": "Центр"},
            {"id": "flat_small", "name": "Квартира (студия)", "price": 150000, "garage_slots": 2, "home_district": "Центр"},
            {"id": "flat_big", "name": "Квартира (3-шка)", "price": 500000, "garage_slots": 3, "home_district": "Элитный"},
            {"id": "house_village", "name": "Дом в деревне", "price": 1000000, "garage_slots": 4, "home_district": "Промзона"},
            {"id": "cottage", "name": "Коттедж", "price": 5000000, "garage_slots": 5, "home_district": "Элитный"},
            {"id": "mansion", "name": "Особняк", "price": 20000000, "garage_slots": 7, "home_district": "Элитный"},
            {"id": "skyscraper", "name": "Небоскреб", "price": 100000000, "garage_slots": 10, "home_district": "Центр"},
        ]
    },
    "car": {
        "name": "🚗 Машины",
        "district": "Промзона",
        "items": [
            {"id": "bike", "name": "Велосипед", "price": 5000, "travel_time": 120},
            {"id": "scooter", "name": "Скутер", "price": 15000, "travel_time": 90},
            {"id": "lada", "name": "Лада", "price": 50000, "travel_time": 60},
            {"id": "kia", "name": "Kia Rio", "price": 150000, "travel_time": 45},
            {"id": "bmw", "name": "BMW M5", "price": 800000, "travel_time": 30},
            {"id": "lambo", "name": "Lamborghini", "price": 3000000, "travel_time": 20},
            {"id": "bugatti", "name": "Bugatti", "price": 10000000, "travel_time": 10},
            {"id": "jet", "name": "Частный джет", "price": 50000000, "travel_time": 5},
        ]
    },
    "furniture": {
        "name": "🛋 Мебель",
        "district": "Гетто",
        "items": [
            {"id": "chair", "name": "Стул", "price": 1000, "bonus": {"reputation": 1}},
            {"id": "table", "name": "Стол", "price": 3000, "bonus": {"reputation": 2}},
            {"id": "sofa", "name": "Диван", "price": 10000, "bonus": {"max_energy": 5}},
            {"id": "tv", "name": "Телевизор", "price": 20000, "bonus": {"reputation": 5}},
            {"id": "pc", "name": "Игровой ПК", "price": 50000, "bonus": {"max_energy": 10}},
            {"id": "bed", "name": "Кровать King Size", "price": 80000, "bonus": {"energy_restore_speed": 0.1}},
            {"id": "jacuzzi", "name": "Джакузи", "price": 150000, "bonus": {"max_energy": 20}},
            {"id": "gold_toilet", "name": "Золотой унитаз", "price": 1000000, "bonus": {"reputation": 20}},
        ]
    }
}

# --- Меню категорий ---
@router.message(F.text == "🏪 Магазины")
async def shop_menu(message: types.Message):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    kb = []
    row = []
    for cat_key, cat_data in SHOP_ITEMS.items():
        row.append(types.InlineKeyboardButton(text=f"{cat_data['name']} ({cat_data['district']})", callback_data=f"shop_cat:{cat_key}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([types.InlineKeyboardButton(text="🎒 Мои вещи", callback_data="shop_my_items")])

    await message.answer("🏪 Добро пожаловать в торговый центр! Выберите отдел:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

# --- Просмотр категории ---
@router.callback_query(F.data.startswith("shop_cat:"))
async def show_category(callback: types.CallbackQuery):
    cat_key = callback.data.split(":")[1]
    category = SHOP_ITEMS.get(cat_key)

    if not category:
        logger.error(f"Категория не найдена: {cat_key}")
        await callback.answer("Категория не найдена")
        return

    user = await get_user(callback.from_user.id)
    if user['district'] != category['district']:
        await callback.answer(f"⛔ Этот магазин находится в районе {category['district']}.\nВы сейчас в {user['district']}.\nВозьмите такси!", show_alert=True)
        return

    kb = []
    for item in category["items"]:
        btn_text = f"{item['name']} - ${item['price']}"
        kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"shop_preview:{cat_key}:{item['id']}")])

    kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="shop_main")])

    await callback.message.edit_text(f"🏪 Отдел: <b>{category['name']}</b>", parse_mode="HTML", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "shop_main")
async def back_to_shop_main(callback: types.CallbackQuery):
    await callback.message.delete()
    await shop_menu(callback.message)

# --- Превью товара ---
@router.callback_query(F.data.startswith("shop_preview:"))
async def buy_preview(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        logger.error(f"Неверный формат callback: {callback.data}")
        await callback.answer("Ошибка данных")
        return

    cat_key, item_id = parts[1], parts[2]

    category = SHOP_ITEMS.get(cat_key)
    if not category:
        logger.error(f"Категория не найдена: {cat_key}")
        await callback.answer("Категория не найдена")
        return

    item = next((i for i in category["items"] if i["id"] == item_id), None)

    if not item:
        available_ids = [i['id'] for i in category['items']]
        logger.error(f"Товар не найден! Received ID: '{item_id}', Category: '{cat_key}', Available: {available_ids}")
        await callback.answer("Товар не найден (см. консоль)")
        return

    text = (f"🛍 <b>{item['name']}</b>\n"
            f"📂 Категория: {category['name']}\n"
            f"💰 Цена: ${item['price']}\n")

    if cat_key == "food": text += f"⚡ Восстанавливает энергию: {item.get('energy_restore', 0)}\n"
    elif cat_key == "house": text += f"🚗 Слотов в гараже: {item.get('garage_slots', 0)}\n"
    elif cat_key == "car": text += f"⏱ Время в пути: {item.get('travel_time', 0)} сек.\n"
    elif cat_key == "furniture" and item.get('bonus'): text += f"🎁 Бонус: {', '.join([f'{k}: {v}' for k, v in item['bonus'].items()])}\n"

    text += "\nХотите купить?"

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Купить", callback_data=f"shop_buy:{cat_key}:{item_id}")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"shop_cat:{cat_key}")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# --- Подтверждение покупки ---
@router.callback_query(F.data.startswith("shop_buy:"))
async def buy_confirm(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка данных")
        return

    cat_key, item_id = parts[1], parts[2]

    category = SHOP_ITEMS.get(cat_key)
    if not category:
        await callback.answer("Ошибка категории")
        return

    item = next((i for i in category["items"] if i["id"] == item_id), None)

    if not item:
        await callback.answer("Ошибка товара")
        return

    user = await get_user(callback.from_user.id)

    if user['money'] < item['price']:
        await callback.answer(f"Недостаточно денег! Нужно ${item['price']}", show_alert=True)
        return

    logger.info(f"User {callback.from_user.id} is buying item '{item_id}' from category '{cat_key}' for ${item['price']}.")

    # --- Специальная логика для разных категорий ---
    if cat_key == "food":
        restore_amount = item.get('energy_restore', 0)
        new_energy = min(user['energy'] + restore_amount, user['max_energy'])
        await db.execute("UPDATE users SET energy = ? WHERE user_id = ?", (new_energy, callback.from_user.id))
        await update_money(callback.from_user.id, -item['price'])
        await callback.message.edit_text(f"✅ Вы купили <b>{item['name']}</b>! Энергия восстановлена на {restore_amount}.", parse_mode="HTML")

    elif cat_key == "house":
        # Проверяем, есть ли уже дом
        current_house = await db.fetchone("SELECT * FROM owned_items WHERE user_id = ? AND category = 'house'", (callback.from_user.id,))
        if current_house:
            await callback.answer("У вас уже есть жилье. Сначала продайте его.", show_alert=True)
            return

        # Обновляем слоты гаража и домашний район
        await db.execute("UPDATE users SET garage_slots = ?, district = ? WHERE user_id = ?",
                         (item.get('garage_slots', 0), item.get('home_district', user['district']), callback.from_user.id))
        await update_money(callback.from_user.id, -item['price'])
        await db.execute("INSERT INTO owned_items (user_id, category, item_key, item_name, price, created_at) VALUES (?, ?, ?, ?, ?, ?)", (callback.from_user.id, cat_key, item_id, item['name'], item['price'], int(time.time())))
        await callback.message.edit_text(f"✅ Вы купили <b>{item['name']}</b>! Ваш дом теперь в районе: {item.get('home_district', 'Неизвестно')}.", parse_mode="HTML")

    elif cat_key == "car":
        user_cars_count = await db.fetchone("SELECT COUNT(*) as count FROM owned_items WHERE user_id = ? AND category = 'car'", (callback.from_user.id,))
        if user_cars_count['count'] >= user['garage_slots']:
            await callback.answer(f"❌ В вашем гараже нет места! (Свободно: {user['garage_slots'] - user_cars_count['count']})", show_alert=True)
            return

        await update_money(callback.from_user.id, -item['price'])
        await db.execute("INSERT INTO owned_items (user_id, category, item_key, item_name, price, created_at) VALUES (?, ?, ?, ?, ?, ?)", (callback.from_user.id, cat_key, item_id, item['name'], item['price'], int(time.time())))
        await callback.message.edit_text(f"✅ Вы купили <b>{item['name']}</b>!", parse_mode="HTML")

    elif cat_key == "furniture":
        if item.get('bonus'):
            update_query_parts = []
            update_params = []
            if 'max_energy' in item['bonus']:
                update_query_parts.append("max_energy = max_energy + ?")
                update_params.append(item['bonus']['max_energy'])
            if 'reputation' in item['bonus']:
                update_query_parts.append("reputation = reputation + ?")
                update_params.append(item['bonus']['reputation'])

            if update_query_parts:
                update_query = "UPDATE users SET " + ", ".join(update_query_parts) + " WHERE user_id = ?"
                update_params.append(callback.from_user.id)
                await db.execute(update_query, tuple(update_params))

        await update_money(callback.from_user.id, -item['price'])
        await db.execute("INSERT INTO owned_items (user_id, category, item_key, item_name, price, created_at) VALUES (?, ?, ?, ?, ?, ?)", (callback.from_user.id, cat_key, item_id, item['name'], item['price'], int(time.time())))
        await callback.message.edit_text(f"✅ Вы купили <b>{item['name']}</b>! Бонусы применены.", parse_mode="HTML")

    await callback.answer()

# --- Инвентарь и Продажа (без изменений) ---
@router.callback_query(F.data == "shop_my_items")
async def my_items(callback: types.CallbackQuery):
    items = await db.fetchall("SELECT * FROM owned_items WHERE user_id = ?", (callback.from_user.id,))

    if not items:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="shop_main")]])
        await callback.message.edit_text("🎒 Ваш инвентарь пуст.", reply_markup=kb)
        return

    kb = []
    for item in items:
        btn_text = f"{item['item_name']} (Продать за ${int(item['price']*0.7)})"
        kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"shop_sell:{item['id']}")])

    kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="shop_main")])

    await callback.message.edit_text("🎒 Ваши вещи (нажмите, чтобы продать):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("shop_sell:"))
async def sell_item(callback: types.CallbackQuery):
    db_id = int(callback.data.split(":")[1])
    item_db = await db.fetchone("SELECT * FROM owned_items WHERE id = ?", (db_id,))

    if not item_db:
        await callback.answer("Предмет не найден")
        return

    category = SHOP_ITEMS.get(item_db['category'])
    item_config = next((i for i in category["items"] if i["id"] == item_db['item_key']), None)

    if not item_config:
        logger.error(f"Конфиг предмета {item_db['item_key']} не найден при продаже.")
        await callback.answer("Ошибка конфига предмета")
        return

    if item_db['category'] == "house":
        # Сбрасываем гараж и район на дефолт (или на предыдущий, если хранили)
        await db.execute("UPDATE users SET garage_slots = 1, district = 'Центр' WHERE user_id = ?", (callback.from_user.id,))
    elif item_db['category'] == "furniture" and item_config.get('bonus'):
        update_query_parts = []
        update_params = []
        if 'max_energy' in item_config['bonus']:
            update_query_parts.append("max_energy = max_energy - ?")
            update_params.append(item_config['bonus']['max_energy'])
        if 'reputation' in item_config['bonus']:
            update_query_parts.append("reputation = reputation - ?")
            update_params.append(item_config['bonus']['reputation'])

        if update_query_parts:
            update_query = "UPDATE users SET " + ", ".join(update_query_parts) + " WHERE user_id = ?"
            update_params.append(callback.from_user.id)
            await db.execute(update_query, tuple(update_params))

    sell_price = int(item_db['price'] * 0.7)

    await update_money(callback.from_user.id, sell_price)
    await db.execute("DELETE FROM owned_items WHERE id = ?", (db_id,))

    logger.info(f"User {callback.from_user.id} sold item '{item_db['item_name']}' for ${sell_price}.")
    await callback.answer(f"Продано за ${sell_price}", show_alert=True)
    await my_items(callback)
