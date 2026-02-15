from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards import business_menu_kb, business_action_kb, confirm_kb, main_menu_kb
from states import Business
from services.economy import check_jail, update_money, get_user
from database import db
import time
import logging

router = Router()
logger = logging.getLogger(__name__)

# Расширенный список бизнесов (Единый источник правды)
BUSINESS_TYPES = {
    "larek": {"name": "Ларёк", "price": 5000, "income": 50, "desc": "Продает жвачки и сигареты.", "stock_item": "Товар", "stock_cost": 10, "max_stock": 100},
    "shav": {"name": "Шаурмичная", "price": 15000, "income": 150, "desc": "Лучшая шаурма на районе.", "stock_item": "Продукты", "stock_cost": 20, "max_stock": 150},
    "shop": {"name": "Магазин 24/7", "price": 50000, "income": 600, "desc": "Продукты у дома.", "stock_item": "Товары", "stock_cost": 50, "max_stock": 200},
    "bar": {"name": "Бар", "price": 120000, "income": 1500, "desc": "Напитки и закуски.", "stock_item": "Напитки", "stock_cost": 100, "max_stock": 250},
    "gas": {"name": "Заправка", "price": 300000, "income": 4000, "desc": "Бензин всегда нужен.", "stock_item": "Топливо", "stock_cost": 200, "max_stock": 300},
    "club": {"name": "Ночной клуб", "price": 800000, "income": 12000, "desc": "Тусовки до утра.", "stock_item": "Алкоголь", "stock_cost": 500, "max_stock": 350},
    "hotel": {"name": "Отель", "price": 2000000, "income": 35000, "desc": "Ночлег для туристов.", "stock_item": "Сервисы", "stock_cost": 1000, "max_stock": 400},
    "casino_biz": {"name": "Казино", "price": 5000000, "income": 90000, "desc": "Азартные игры.", "stock_item": "Фишки", "stock_cost": 5000, "max_stock": 500},
    "bank_biz": {"name": "Банк", "price": 15000000, "income": 300000, "desc": "Кредиты и вклады.", "stock_item": "Капитал", "stock_cost": 10000, "max_stock": 600},
    "oil": {"name": "Нефтевышка", "price": 50000000, "income": 1200000, "desc": "Черное золото.", "stock_item": "Нефть", "stock_cost": 50000, "max_stock": 700}
}

@router.message(F.text == "💼 Бизнесы")
async def business_menu(message: types.Message):
    await message.answer("Управление бизнесом", reply_markup=business_menu_kb())

@router.message(F.text == "📂 Мои бизнесы")
async def my_businesses(message: types.Message):
    businesses = await db.fetchall("SELECT * FROM user_businesses WHERE user_id = ?", (message.from_user.id,))
    if not businesses:
        await message.answer("У вас нет бизнесов.")
        return

    for biz in businesses:
        biz_key = biz['business_type']
        info = BUSINESS_TYPES.get(biz_key)

        if not info:
            logger.error(f"Бизнес '{biz_key}' из БД не найден в BUSINESS_TYPES. Доступные: {list(BUSINESS_TYPES.keys())}")
            await message.answer(f"🏢 Неизвестный бизнес ({biz_key}) - обратитесь к админу.")
            continue

        base_income = info['income']
        level_bonus = 1 + (biz['level'] * 0.25)
        current_income = int(base_income * level_bonus)

        treasury = biz['treasury'] if 'treasury' in biz.keys() else 0

        # Цена улучшения
        upgrade_price = int(info['price'] * 0.5 * biz['level'])

        text = (f"🏢 <b>{info['name']}</b> (Ур. {biz['level']})\n"
                f"💰 Доход: ${current_income} / мин\n"
                f"📦 Склад: {biz['stock']}/{biz['max_stock']} {info['stock_item']}\n"
                f"🏦 Казна: ${treasury}\n"
                f"⬆️ Цена улучшения: ${upgrade_price}")

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"biz_ask_upgrade:{biz['id']}")], # Изменено на ask
            [types.InlineKeyboardButton(text="📦 Закупить", callback_data=f"biz_restock:{biz['id']}"),
             types.InlineKeyboardButton(text="💰 Забрать казну", callback_data=f"biz_collect:{biz['id']}")],
            [types.InlineKeyboardButton(text="👨‍💼 Менеджер", callback_data=f"biz_manager:{biz['id']}"),
             types.InlineKeyboardButton(text="💰 Продать", callback_data=f"biz_ask_sell:{biz['id']}")], # Изменено на ask
            [types.InlineKeyboardButton(text="🔄 Обновить", callback_data=f"biz_refresh:{biz['id']}")]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

# ... (buy_business_menu, buy_biz_preview, buy_biz_back, buy_biz_confirm - без изменений)
@router.message(F.text == "🛒 Купить бизнес")
async def buy_business_menu(message: types.Message):
    text = "Выберите бизнес для покупки:"
    keyboard = []
    for key, info in BUSINESS_TYPES.items():
        btn_text = f"{info['name']} - ${info['price']}"
        keyboard.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"biz_preview:{key}")])

    kb = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("biz_preview:"))
async def buy_biz_preview(callback: types.CallbackQuery, state: FSMContext):
    biz_key = callback.data.split(":")[1]
    info = BUSINESS_TYPES.get(biz_key)

    if not info:
        logger.error(f"Бизнес не найден при превью! Received Key: '{biz_key}', Available: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка бизнеса (см. консоль)")
        return

    text = (f"🏢 <b>{info['name']}</b>\n"
            f"📝 {info['desc']}\n\n"
            f"💰 Цена: ${info['price']}\n"
            f"💵 Доход: ${info['income']} / мин\n"
            f"📦 Склад: {info.get('max_stock', 100)} {info['stock_item']}")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Купить", callback_data=f"biz_buy:{biz_key}")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="biz_buy_back")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "biz_buy_back")
async def buy_biz_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await buy_business_menu(callback.message)

@router.callback_query(F.data.startswith("biz_buy:"))
async def buy_biz_confirm(callback: types.CallbackQuery):
    biz_key = callback.data.split(":")[1]
    info = BUSINESS_TYPES.get(biz_key)

    if not info:
        logger.error(f"Бизнес не найден при покупке: {biz_key}")
        await callback.answer("Ошибка бизнеса")
        return

    user = await get_user(callback.from_user.id)
    if user['money'] < info['price']:
        await callback.answer(f"Недостаточно денег! Нужно ${info['price']}", show_alert=True)
        return

    user_businesses_count = await db.fetchone("SELECT COUNT(*) as count FROM user_businesses WHERE user_id = ?", (callback.from_user.id,))
    max_businesses = 5
    if user_businesses_count['count'] >= max_businesses:
        await callback.answer(f"❌ Вы достигли лимита бизнесов ({max_businesses}). Продайте старый, чтобы купить новый.", show_alert=True)
        return

    await update_money(callback.from_user.id, -info['price'])
    await db.execute("INSERT INTO user_businesses (user_id, business_type, stock, max_stock) VALUES (?, ?, ?, ?)",
                     (callback.from_user.id, biz_key, info.get('max_stock', 100), info.get('max_stock', 100)))

    logger.info(f"User {callback.from_user.id} bought business '{info['name']}' for ${info['price']}.")
    await callback.message.edit_text(f"✅ Вы успешно купили <b>{info['name']}</b>!", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("biz_collect:"))
async def biz_collect_cash(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz:
        await callback.answer("Бизнес не найден")
        return

    treasury = biz['treasury'] if 'treasury' in biz.keys() else 0
    cash_box = biz['cash_box'] if 'cash_box' in biz.keys() else 0
    cash_to_collect = treasury + cash_box

    if cash_to_collect <= 0:
        await callback.answer("Казна пуста!", show_alert=True)
        return

    await update_money(callback.from_user.id, cash_to_collect)
    await db.execute("UPDATE user_businesses SET treasury = 0, cash_box = 0 WHERE id = ?", (biz_id,))

    logger.info(f"User {callback.from_user.id} collected ${cash_to_collect} from business ID {biz_id}.")
    await callback.answer(f"Вы забрали ${cash_to_collect} из казны.", show_alert=True)

    await biz_refresh(callback)

# --- ПОДТВЕРЖДЕНИЕ ПРОДАЖИ ---
@router.callback_query(F.data.startswith("biz_ask_sell:"))
async def biz_ask_sell(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, продать", callback_data=f"biz_sell:{biz_id}")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"biz_refresh:{biz_id}")]
    ])
    await callback.message.edit_text("Вы уверены, что хотите продать этот бизнес? (Вернется 70% стоимости)", reply_markup=kb)

@router.callback_query(F.data.startswith("biz_sell:"))
async def sell_biz_callback(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz:
        await callback.answer("Бизнес не найден")
        return

    biz_key = biz['business_type']
    info = BUSINESS_TYPES.get(biz_key)

    if not info:
        logger.error(f"Бизнес '{biz_key}' из БД не найден в BUSINESS_TYPES при продаже. Доступные: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка: Не удалось определить цену бизнеса.")
        return

    sell_price = int(info['price'] * 0.7)
    await update_money(callback.from_user.id, sell_price)
    await db.execute("DELETE FROM user_businesses WHERE id = ?", (biz_id,))

    logger.info(f"User {callback.from_user.id} sold business '{info['name']}' for ${sell_price}.")
    await callback.message.edit_text(f"✅ Бизнес продан за ${sell_price}")

    await callback.answer()

# --- ПОДТВЕРЖДЕНИЕ УЛУЧШЕНИЯ ---
@router.callback_query(F.data.startswith("biz_ask_upgrade:"))
async def biz_ask_upgrade(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz: return

    info = BUSINESS_TYPES.get(biz['business_type'])
    upgrade_price = int(info['price'] * 0.5 * biz['level'])

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"✅ Улучшить за ${upgrade_price}", callback_data=f"biz_upgrade:{biz_id}")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"biz_refresh:{biz_id}")]
    ])
    await callback.message.edit_text(f"Улучшить <b>{info['name']}</b> до уровня {biz['level']+1}?", parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("biz_upgrade:"))
async def upgrade_biz_callback(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))

    biz_key = biz['business_type']
    info = BUSINESS_TYPES.get(biz_key)

    if not info:
        logger.error(f"Бизнес '{biz_key}' из БД не найден в BUSINESS_TYPES при улучшении. Доступные: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка данных")
        return

    upgrade_price = int(info['price'] * 0.5 * biz['level'])

    user = await get_user(callback.from_user.id)
    if user['money'] < upgrade_price:
        await callback.answer(f"Нужно ${upgrade_price}", show_alert=True)
        return

    await update_money(callback.from_user.id, -upgrade_price)
    await db.execute("UPDATE user_businesses SET level = level + 1 WHERE id = ?", (biz_id,))

    new_income = info['income'] * (biz['level'] + 1)
    logger.info(f"User {callback.from_user.id} upgraded business '{info['name']}' to level {biz['level'] + 1} for ${upgrade_price}.")
    await callback.message.edit_text(f"✅ Уровень повышен! Списано ${upgrade_price}\nНовый доход: ${new_income}")
    await callback.answer()

@router.callback_query(F.data.startswith("biz_restock:"))
async def biz_restock_start(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz:
        await callback.answer("Бизнес не найден")
        return

    info = BUSINESS_TYPES.get(biz['business_type'])
    if not info:
        logger.error(f"Бизнес '{biz['business_type']}' из БД не найден в BUSINESS_TYPES при закупке. Доступные: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка данных бизнеса")
        return

    restock_cost = info['stock_cost']
    max_fill_amount = biz['max_stock'] - biz['stock']

    if max_fill_amount <= 0:
        await callback.answer("Склад полон!", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"Закупить 1 ({restock_cost}$)", callback_data=f"biz_restock_confirm:{biz_id}:1")],
        [types.InlineKeyboardButton(text=f"Закупить 10 ({restock_cost*10}$)", callback_data=f"biz_restock_confirm:{biz_id}:10")],
        [types.InlineKeyboardButton(text=f"Закупить {max_fill_amount} ({(restock_cost*max_fill_amount)}$)", callback_data=f"biz_restock_confirm:{biz_id}:{max_fill_amount}")]
    ])
    await callback.message.edit_text(f"📦 <b>{info['name']}</b>: Склад {biz['stock']}/{biz['max_stock']}\n"
                                     f"Стоимость 1 ед. {info['stock_item']}: ${restock_cost}", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("biz_restock_confirm:"))
async def biz_restock_confirm(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    biz_id = int(parts[1])
    amount_to_restock = int(parts[2])

    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz:
        await callback.answer("Бизнес не найден")
        return

    info = BUSINESS_TYPES.get(biz['business_type'])
    if not info:
        logger.error(f"Бизнес '{biz['business_type']}' из БД не найден в BUSINESS_TYPES при подтверждении закупки. Доступные: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка данных бизнеса")
        return

    user = await get_user(callback.from_user.id)

    restock_cost_per_unit = info['stock_cost']
    total_cost = restock_cost_per_unit * amount_to_restock

    if user['money'] < total_cost:
        await callback.answer(f"Недостаточно денег! Нужно ${total_cost}", show_alert=True)
        return

    if biz['stock'] + amount_to_restock > biz['max_stock']:
        amount_to_restock = biz['max_stock'] - biz['stock']
        total_cost = restock_cost_per_unit * amount_to_restock
        if amount_to_restock <= 0:
            await callback.answer("Склад полон!", show_alert=True)
            return

    await update_money(callback.from_user.id, -total_cost)
    await db.execute("UPDATE user_businesses SET stock = stock + ? WHERE id = ?", (amount_to_restock, biz_id))

    logger.info(f"User {callback.from_user.id} restocked business '{info['name']}' by {amount_to_restock} units for ${total_cost}.")
    await callback.message.edit_text(f"✅ Склад <b>{info['name']}</b> пополнен на {amount_to_restock} {info['stock_item']} за ${total_cost}!")
    await callback.answer()

@router.callback_query(F.data.startswith("biz_manager:"))
async def biz_manager_toggle(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))
    if not biz:
        await callback.answer("Бизнес не найден")
        return

    info = BUSINESS_TYPES.get(biz['business_type'])
    if not info:
        logger.error(f"Бизнес '{biz['business_type']}' из БД не найден в BUSINESS_TYPES при менеджере. Доступные: {list(BUSINESS_TYPES.keys())}")
        await callback.answer("Ошибка данных бизнеса")
        return

    new_manager_status = 1 if biz['has_manager'] == 0 else 0

    if new_manager_status == 1:
        await db.execute("UPDATE user_businesses SET has_manager = ? WHERE id = ?", (new_manager_status, biz_id))
        logger.info(f"User {callback.from_user.id} hired manager for business '{info['name']}'.")
        await callback.message.edit_text(f"👨‍💼 Менеджер для <b>{info['name']}</b> нанят! Он будет сам пополнять склад (но дороже).")
    else:
        await db.execute("UPDATE user_businesses SET has_manager = ? WHERE id = ?", (new_manager_status, biz_id))
        logger.info(f"User {callback.from_user.id} fired manager for business '{info['name']}'.")
        await callback.message.edit_text(f"👨‍💼 Менеджер для <b>{info['name']}</b> уволен. Теперь закупка склада на вас.")

    await callback.answer()

@router.callback_query(F.data.startswith("biz_refresh:"))
async def biz_refresh(callback: types.CallbackQuery):
    biz_id = int(callback.data.split(":")[1])
    biz = await db.fetchone("SELECT * FROM user_businesses WHERE id = ?", (biz_id,))

    if not biz:
        await callback.answer("Бизнес не найден")
        return

    info = BUSINESS_TYPES.get(biz['business_type'])

    base_income = info['income']
    level_bonus = 1 + (biz['level'] * 0.25)
    current_income = int(base_income * level_bonus)

    treasury = biz['treasury'] if 'treasury' in biz.keys() else 0

    # Цена улучшения
    upgrade_price = int(info['price'] * 0.5 * biz['level'])

    text = (f"🏢 <b>{info['name']}</b> (Ур. {biz['level']})\n"
            f"💰 Доход: ${current_income} / мин\n"
            f"📦 Склад: {biz['stock']}/{biz['max_stock']} {info['stock_item']}\n"
            f"🏦 Казна: ${treasury}\n"
            f"⬆️ Цена улучшения: ${upgrade_price}")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"biz_ask_upgrade:{biz['id']}")],
        [types.InlineKeyboardButton(text="📦 Закупить", callback_data=f"biz_restock:{biz['id']}"),
         types.InlineKeyboardButton(text="💰 Забрать казну", callback_data=f"biz_collect:{biz['id']}")],
        [types.InlineKeyboardButton(text="👨‍💼 Менеджер", callback_data=f"biz_manager:{biz['id']}"),
         types.InlineKeyboardButton(text="💰 Продать", callback_data=f"biz_ask_sell:{biz['id']}")],
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data=f"biz_refresh:{biz['id']}")]
    ])

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        pass
    await callback.answer("Обновлено")
