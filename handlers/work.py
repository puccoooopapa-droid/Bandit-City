from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from keyboards import work_menu_kb, courier_type_kb, courier_route_kb, main_menu_kb, cancel_kb
from states import Work
from services.economy import check_jail, update_money, add_transaction, get_user
from services.events import current_event
from database import db
import random
import asyncio
import time
import logging

router = Router()
logger = logging.getLogger(__name__)

# Словарь для хранения времени последнего действия (кулдаун)
user_cooldowns = {}
user_locks = {}

# --- Вспомогательные функции ---
async def check_work_status(user_id, message: types.Message):
    if user_locks.get(user_id):
        logger.info(f"User {user_id} tried to start work while already working.")
        await message.answer("⏳ Вы уже выполняете работу!")
        return True

    last_work_time = user_cooldowns.get(user_id, 0)
    if time.time() - last_work_time < 5:
        remaining = int(5 - (time.time() - last_work_time))
        logger.info(f"User {user_id} tried to start work during cooldown. Remaining: {remaining}s.")
        await message.answer(f"⏳ Отдохните еще {remaining} сек.")
        return True
    return False

async def start_work_session(user_id):
    user_locks[user_id] = True
    logger.info(f"User {user_id} started a work session.")

async def end_work_session(user_id):
    user_locks[user_id] = False
    user_cooldowns[user_id] = time.time()
    logger.info(f"User {user_id} ended a work session.")

# --- Главное меню Работ ---
@router.message(F.text == "💼 Работа")
async def work_menu(message: types.Message):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return
    logger.info(f"User {message.from_user.id} entered work menu.")
    await message.answer("Выберите работу:", reply_markup=work_menu_kb())

# --- Ограбление ---
class Robbery(Work):
    target = State()

@router.message(F.text == "🔪 Ограбление")
async def robbery_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    await message.answer("Кого будем грабить? Введите ID цели (Фамилия#XXXX или @username):", reply_markup=cancel_kb())
    await state.set_state(Robbery.target)

@router.message(Robbery.target)
async def robbery_target(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=work_menu_kb())
        return

    target_identifier = message.text.strip()
    target_user = None

    if "@" in target_identifier:
        username = target_identifier.replace("@", "")
        target_user = await db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
    elif "#" in target_identifier:
        try:
            surname, tag = target_identifier.split("#")
            target_user = await db.fetchone("SELECT * FROM users WHERE last_name = ? AND tag = ?", (surname, int(tag)))
        except ValueError:
            pass

    if not target_user:
        await message.answer("❌ Жертва не найдена. Проверьте ID.")
        return

    if target_user['user_id'] == message.from_user.id:
        await message.answer("Нельзя грабить самого себя.")
        return

    await start_work_session(message.from_user.id)
    await state.clear()

    await message.answer("Выдвигаемся на дело...", reply_markup=types.ReplyKeyboardRemove())
    await asyncio.sleep(3)

    # Шанс успеха - очень маленький
    if random.randint(1, 100) <= 10: # 10% шанс на успех
        amount = random.randint(20000, 35000)

        if target_user['money'] < amount:
            amount = target_user['money']

        await update_money(message.from_user.id, amount)
        await update_money(target_user['user_id'], -amount)

        logger.info(f"User {message.from_user.id} successfully robbed {target_user['user_id']} for ${amount}.")
        await message.answer(f"✅ Успех! Вы ограбили жертву на ${amount}!", reply_markup=work_menu_kb())
    else:
        # Провал - тюрьма
        jail_time = 10 * 60 # 10 минут
        await db.execute("UPDATE users SET jail_until = ? WHERE user_id = ?", (int(time.time() + jail_time), message.from_user.id))

        logger.warning(f"User {message.from_user.id} failed to rob {target_user['user_id']} and was jailed for {jail_time}s.")
        await message.answer(f"🚨 Провал! Вас поймала полиция. Вы в тюрьме на {jail_time // 60} минут.", reply_markup=work_menu_kb())

    await end_work_session(message.from_user.id)

# --- Такси (Водитель) ---
@router.message(F.text == "🚕 Такси (Водитель)")
async def work_taxi_driver(message: types.Message):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    orders = await db.fetchall("SELECT * FROM taxi_orders WHERE status = 'WAITING' ORDER BY created_at ASC LIMIT 5")

    if not orders:
        logger.info(f"User {user_id} checked for taxi orders, none available.")
        await message.answer("Пока нет заказов такси. Попробуйте позже.")
        return

    kb = []
    for order in orders:
        passenger = await get_user(order['passenger_id'])
        btn_text = f"🚕 {passenger['first_name']} {passenger['last_name']} в {order['destination']} (${order['price']})"
        kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"take_order_{order['id']}")])

    logger.info(f"User {user_id} viewing available taxi orders.")
    await message.answer("Доступные заказы такси:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

# --- Курьер ---
@router.message(F.text == "📦 Курьер")
async def work_courier_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    logger.info(f"User {user_id} started courier job.")
    await message.answer("Выберите тип доставки:", reply_markup=courier_type_kb())
    await state.set_state(Work.delivery_type)

@router.message(Work.delivery_type)
async def work_courier_type(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Выберите работу:", reply_markup=work_menu_kb())
        await state.clear()
        return

    delivery_type = message.text
    if delivery_type not in ["🍔 Еда", "📄 Документы", "💻 Техника"]:
        await message.answer("Выберите тип доставки кнопкой.")
        return

    await state.update_data(delivery_type=delivery_type)
    await message.answer("Выберите маршрут:", reply_markup=courier_route_kb())
    await state.set_state(Work.delivery_route)

@router.message(Work.delivery_route)
async def work_courier_route(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    if message.text == "⬅️ Назад":
        await message.answer("Выберите тип доставки:", reply_markup=courier_type_kb())
        await state.set_state(Work.delivery_type)
        return

    route = message.text
    reward = 0
    risk = 0
    time_wait = 0
    energy_cost = 0

    data = await state.get_data()
    delivery_type = data['delivery_type']

    if "Безопасно" in route:
        reward = random.randint(30, 80)
        risk = 5
        time_wait = 3
        energy_cost = 5
    elif "Быстро" in route:
        reward = random.randint(70, 150)
        risk = 20
        time_wait = 5
        energy_cost = 10
    elif "Рискованно" in route:
        reward = random.randint(150, 400)
        risk = 50
        time_wait = 7
        energy_cost = 15
    else:
        await message.answer("Выберите маршрут кнопкой.")
        return

    user = await get_user(user_id)
    if user['energy'] < energy_cost:
        logger.warning(f"User {user_id} tried courier job with insufficient energy ({user['energy']}/{energy_cost}).")
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost}) для этой работы! Поешьте.")
        await state.clear()
        return

    await start_work_session(user_id)
    await state.clear()

    await message.answer(f"📦 Вы взяли заказ ({delivery_type}). Доставляем...", reply_markup=types.ReplyKeyboardRemove())
    await asyncio.sleep(time_wait)

    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))
    user = await get_user(user_id)

    is_vip = user['vip_until'] > time.time()
    energy_multiplier = 1.0
    if user['energy'] >= 80: energy_multiplier = 1.2
    elif user['energy'] <= 39: energy_multiplier = 0.7

    reputation_multiplier = 1.0
    if user['reputation'] > 100: reputation_multiplier = 1.1
    elif user['reputation'] < 0: reputation_multiplier = 0.9

    income_multiplier = current_event["effects"].get("income_multiplier", 1.0)

    if random.randint(1, 100) <= risk:
        fine = int(reward * 0.8)
        await update_money(user_id, -fine)
        logger.info(f"User {user_id} failed courier job ({delivery_type}, {route}). Fine: ${fine}.")
        await message.answer(f"💥 Неудача! Вы повредили {delivery_type}. Штраф: ${fine}", reply_markup=work_menu_kb())
    else:
        reward = int(reward * energy_multiplier * reputation_multiplier * income_multiplier)
        if is_vip: reward *= 2
        await update_money(user_id, reward)
        await add_transaction(user_id, reward, f"Работа: Курьер ({delivery_type})")
        logger.info(f"User {user_id} completed courier job ({delivery_type}, {route}). Earned: ${reward}.")
        await message.answer(f"✅ Заказ выполнен! Вы заработали ${reward} (Энергия: {user['energy']})", reply_markup=work_menu_kb())

    await end_work_session(user_id)

# --- 🧰 Подработка (Электрик: Соедини провода) ---
@router.message(F.text == "🧰 Подработка")
async def work_odd_job(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 10
    if user['energy'] < energy_cost:
        logger.warning(f"User {user_id} tried odd job with insufficient energy ({user['energy']}/{energy_cost}).")
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost}) для этой работы! Поешьте.")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))
    user = await get_user(user_id)

    await start_work_session(user_id)

    colors = ["🔴", "🔵", "🟢", "🟡"]
    sequence = random.sample(colors, 3)

    await state.update_data(sequence=sequence, current_step=0, energy_cost=energy_cost)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=c, callback_data=f"wire_{c}") for c in colors]
    ])

    logger.info(f"User {user_id} started odd job (wires). Sequence: {sequence}.")
    await message.answer(f"⚡ <b>Электрик:</b> Соедините провода в порядке:\n\n{' ➡️ '.join(sequence)}", parse_mode="HTML", reply_markup=kb)
    await state.set_state(Work.odd_job_wires)

@router.callback_query(F.data.startswith("wire_"), Work.odd_job_wires)
async def odd_job_click(callback: types.CallbackQuery, state: FSMContext):
    color = callback.data.split("_")[1]
    data = await state.get_data()
    sequence = data['sequence']
    step = data['current_step']
    energy_cost = data['energy_cost']

    if color == sequence[step]:
        step += 1
        if step == len(sequence):
            reward = random.randint(60, 180)
            user = await get_user(callback.from_user.id)
            is_vip = user['vip_until'] > time.time()
            energy_multiplier = 1.0
            if user['energy'] >= 80: energy_multiplier = 1.2
            elif user['energy'] <= 39: energy_multiplier = 0.7
            reputation_multiplier = 1.0
            if user['reputation'] > 100: reputation_multiplier = 1.1
            elif user['reputation'] < 0: reputation_multiplier = 0.9
            income_multiplier = current_event["effects"].get("income_multiplier", 1.0)
            reward = int(reward * energy_multiplier * reputation_multiplier * income_multiplier)
            if is_vip: reward *= 2

            await update_money(callback.from_user.id, reward)
            logger.info(f"User {callback.from_user.id} completed odd job (wires). Earned: ${reward}.")
            await callback.message.edit_text(f"✅ Проводка починена! Вы заработали ${reward} (Энергия: {user['energy']})")
            await end_work_session(callback.from_user.id)
            await state.clear()
        else:
            await state.update_data(current_step=step)
            progress = "✅ " * step
            await callback.message.edit_text(f"⚡ <b>Электрик:</b> Соедините провода:\n{' ➡️ '.join(sequence)}\n\nПрогресс: {progress}", parse_mode="HTML", reply_markup=callback.message.reply_markup)
    else:
        logger.info(f"User {callback.from_user.id} failed odd job (wires). Wrong color: {color}.")
        await callback.message.edit_text("💥 Замыкание! Вы перепутали провода.")
        await end_work_session(callback.from_user.id)
        await state.clear()

    await callback.answer()

# --- 🏪 Грузчик (Сортировка: Конвейер) ---
@router.message(F.text == "🏪 Грузчик")
async def work_loader(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 8
    if user['energy'] < energy_cost:
        logger.warning(f"User {user_id} tried loader job with insufficient energy ({user['energy']}/{energy_cost}).")
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost}) для этой работы! Поешьте.")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))
    user = await get_user(user_id)

    await start_work_session(user_id)

    items = [
        {"name": "📺 Телевизор", "type": "fragile"},
        {"name": "🧱 Кирпичи", "type": "heavy"},
        {"name": "🏺 Ваза", "type": "fragile"},
        {"name": "🏋️ Гиря", "type": "heavy"},
        {"name": "🥚 Яйца", "type": "fragile"},
        {"name": "🪵 Бревна", "type": "heavy"},
    ]
    item = random.choice(items)

    await state.update_data(correct_type=item['type'], energy_cost=energy_cost)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📦 Хрупкое", callback_data="load_fragile"),
            types.InlineKeyboardButton(text="💪 Тяжелое", callback_data="load_heavy")
        ]
    ])

    logger.info(f"User {user_id} started loader job (sorting). Item: {item['name']} ({item['type']}).")
    await message.answer(f"🏪 <b>Конвейер:</b> Появился предмет:\n\n{item['name']}\n\nКуда его положить?", parse_mode="HTML", reply_markup=kb)
    await state.set_state(Work.loader_sorting)

@router.callback_query(F.data.startswith("load_"), Work.loader_sorting)
async def loader_click(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data.split("_")[1]
    data = await state.get_data()
    energy_cost = data['energy_cost']

    if choice == data['correct_type']:
        reward = random.randint(50, 140)
        user = await get_user(callback.from_user.id)
        is_vip = user['vip_until'] > time.time()
        energy_multiplier = 1.0
        if user['energy'] >= 80: energy_multiplier = 1.2
        elif user['energy'] <= 39: energy_multiplier = 0.7
        reputation_multiplier = 1.0
        if user['reputation'] > 100: reputation_multiplier = 1.1
        elif user['reputation'] < 0: reputation_multiplier = 0.9
        income_multiplier = current_event["effects"].get("income_multiplier", 1.0)
        reward = int(reward * energy_multiplier * reputation_multiplier * income_multiplier)
        if is_vip: reward *= 2

        await update_money(callback.from_user.id, reward)
        logger.info(f"User {callback.from_user.id} completed loader job (sorting). Earned: ${reward}.")
        await callback.message.edit_text(f"✅ Верно! Груз отправлен. Вы заработали ${reward} (Энергия: {user['energy']})")
    else:
        await update_money(callback.from_user.id, -20)
        logger.info(f"User {callback.from_user.id} failed loader job (sorting). Wrong choice: {choice}. Fine: $20.")
        await callback.message.edit_text("❌ Ошибка! Вы разбили груз или надорвали спину. Штраф $20.")

    await end_work_session(callback.from_user.id)
    await state.clear()
    await callback.answer()

@router.message(F.text == "🧼 Клинер")
async def work_cleaner(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 7
    if user['energy'] < energy_cost:
        logger.warning(f"User {user_id} tried cleaner job with insufficient energy ({user['energy']}/{energy_cost}).")
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost}) для этой работы! Поешьте.")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))
    user = await get_user(user_id)

    await start_work_session(user_id)

    clicks_needed = 3
    await state.update_data(clicks_needed=clicks_needed, energy_cost=energy_cost)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🧽 ТЕРЕТЬ!", callback_data="clean_scrub")]
    ])

    logger.info(f"User {user_id} started cleaner job (scrub). Clicks needed: {clicks_needed}.")
    await message.answer("🧼 <b>Уборка:</b> Грязное пятно! (Грязь: 100%)\nЖми кнопку, чтобы оттереть!", parse_mode="HTML", reply_markup=kb)
    await state.set_state(Work.cleaner_scrub)

@router.callback_query(F.data == "clean_scrub", Work.cleaner_scrub)
async def cleaner_click(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    clicks = data['clicks_needed'] - 1
    energy_cost = data['energy_cost']

    if clicks <= 0:
        reward = random.randint(40, 110)
        user = await get_user(callback.from_user.id)
        is_vip = user['vip_until'] > time.time()
        energy_multiplier = 1.0
        if user['energy'] >= 80: energy_multiplier = 1.2
        elif user['energy'] <= 39: energy_multiplier = 0.7
        reputation_multiplier = 1.0
        if user['reputation'] > 100: reputation_multiplier = 1.1
        elif user['reputation'] < 0: reputation_multiplier = 0.9
        income_multiplier = current_event["effects"].get("income_multiplier", 1.0)
        reward = int(reward * energy_multiplier * reputation_multiplier * income_multiplier)
        if is_vip: reward *= 2

        await update_money(callback.from_user.id, reward)
        logger.info(f"User {callback.from_user.id} completed cleaner job (scrub). Earned: ${reward}.")
        await callback.message.edit_text(f"✨ Чисто! Вы заработали ${reward} (Энергия: {user['energy']})")
        await end_work_session(callback.from_user.id)
        await state.clear()
    else:
        await state.update_data(clicks_needed=clicks)
        dirt = int((clicks / 3) * 100)
        await callback.message.edit_text(f"🧼 <b>Уборка:</b> Грязное пятно! (Грязь: {dirt}%)\nЖми кнопку, чтобы оттереть!", parse_mode="HTML", reply_markup=callback.message.reply_markup)

    await callback.answer()

@router.message(F.text == "🏗 Стройка")
async def work_construction(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 12
    if user['energy'] < energy_cost:
        logger.warning(f"User {user_id} tried construction job with insufficient energy ({user['energy']}/{energy_cost}).")
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost}) для этой работы! Поешьте.")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))
    user = await get_user(user_id)

    await start_work_session(user_id)

    cement_needed = random.randint(1, 3)
    water_needed = random.randint(1, 3)

    await state.update_data(
        cement_needed=cement_needed,
        water_needed=water_needed,
        cement_added=0,
        water_added=0,
        energy_cost=energy_cost
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ Цемент", callback_data="build_add_cement"),
         types.InlineKeyboardButton(text="➕ Вода", callback_data="build_add_water")],
        [types.InlineKeyboardButton(text="✅ Готово", callback_data="build_finish")]
    ])

    logger.info(f"User {user_id} started construction job (mix). Recipe: {cement_needed} cement, {water_needed} water.")
    await message.answer(f"🏗 <b>Бетономешалка:</b>\nНужно: {cement_needed} цемента и {water_needed} воды.\n\nВ баке: 0 цемента, 0 воды.", parse_mode="HTML", reply_markup=kb)
    await state.set_state(Work.construction_mix)

@router.callback_query(F.data.startswith("build_"), Work.construction_mix)
async def construction_click(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    energy_cost = data['energy_cost']

    if action == "add":
        ingredient = callback.data.split("_")[2]
        if ingredient == "cement":
            data['cement_added'] += 1
        else:
            data['water_added'] += 1

        await state.update_data(cement_added=data['cement_added'], water_added=data['water_added'])

        await callback.message.edit_text(
            f"🏗 <b>Бетономешалка:</b>\nНужно: {data['cement_needed']} цемента и {data['water_needed']} воды.\n\n"
            f"В баке: {data['cement_added']} цемента, {data['water_added']} воды.",
            parse_mode="HTML",
            reply_markup=callback.message.reply_markup
        )

    elif action == "finish":
        if data['cement_added'] == data['cement_needed'] and data['water_added'] == data['water_needed']:
            reward = random.randint(90, 280)
            user = await get_user(callback.from_user.id)
            is_vip = user['vip_until'] > time.time()
            energy_multiplier = 1.0
            if user['energy'] >= 80: energy_multiplier = 1.2
            elif user['energy'] <= 39: energy_multiplier = 0.7
            reputation_multiplier = 1.0
            if user['reputation'] > 100: reputation_multiplier = 1.1
            elif user['reputation'] < 0: reputation_multiplier = 0.9
            income_multiplier = current_event["effects"].get("income_multiplier", 1.0)
            reward = int(reward * energy_multiplier * reputation_multiplier * income_multiplier)
            if is_vip: reward *= 2

            await update_money(callback.from_user.id, reward)
            logger.info(f"User {callback.from_user.id} completed construction job (mix). Earned: ${reward}.")
            await callback.message.edit_text(f"✅ Идеальный бетон! Вы заработали ${reward} (Энергия: {user['energy']})")
        else:
            await update_money(callback.from_user.id, -50)
            logger.info(f"User {callback.from_user.id} failed construction job (mix). Wrong proportions. Fine: $50.")
            await callback.message.edit_text("❌ Плохая смесь! Пропорции нарушены. Штраф $50.")

        await end_work_session(callback.from_user.id)
        await state.clear()

    await callback.answer()

# --- 💻 Хакер (Взлом: Угадай код) ---
@router.message(F.text == "💻 Хакер")
async def work_hacker(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 15
    if user['energy'] < energy_cost:
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost})!")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))

    await start_work_session(user_id)

    code = str(random.randint(100, 999))
    # ИЗМЕНЕНИЕ: 15 попыток
    await state.update_data(code=code, attempts=15, energy_cost=energy_cost)

    await message.answer(f"💻 <b>Взлом системы:</b>\nКод состоит из 3 цифр (100-999).\nУ вас 15 попыток.\n\nВведите код:", parse_mode="HTML")
    await state.set_state(Work.hacker_guess)

@router.message(Work.hacker_guess)
async def hacker_guess_handler(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return

    data = await state.get_data()
    code = data['code']
    attempts = data['attempts'] - 1

    if message.text == code:
        reward = random.randint(1000, 2500)
        user = await get_user(message.from_user.id)
        is_vip = user['vip_until'] > time.time()
        if is_vip: reward *= 2

        await update_money(message.from_user.id, reward)
        await message.answer(f"✅ Система взломана! Код: {code}. Вы заработали ${reward}")
        await end_work_session(message.from_user.id)
        await state.clear()
    else:
        if attempts > 0:
            hint = "Больше" if int(code) > int(message.text) else "Меньше"
            await state.update_data(attempts=attempts)
            await message.answer(f"❌ Неверно! Подсказка: {hint}.\nОсталось попыток: {attempts}")
        else:
            await message.answer(f"🚫 Взлом провален! Код был: {code}.")
            await end_work_session(message.from_user.id)
            await state.clear()

# --- 🍹 Бармен (Смешай коктейль) ---
@router.message(F.text == "🍹 Бармен")
async def work_bartender(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await check_work_status(user_id, message): return

    user = await get_user(user_id)
    energy_cost = 10
    if user['energy'] < energy_cost:
        await message.answer(f"❌ Недостаточно энергии ({user['energy']}/{energy_cost})!")
        return
    await db.execute("UPDATE users SET energy = energy - ? WHERE user_id = ?", (energy_cost, user_id))

    await start_work_session(user_id)

    ingredients = ["Vodka", "Cola", "Juice", "Ice"]
    recipe = random.sample(ingredients, 3)

    await state.update_data(recipe=recipe, current_step=0)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=i, callback_data=f"bar_{i}") for i in ingredients]
    ])

    await message.answer(f"🍹 <b>Заказ:</b> {', '.join(recipe)}\n\nДобавьте ингредиенты по порядку:", parse_mode="HTML", reply_markup=kb)
    await state.set_state(Work.bartender_mix)

@router.callback_query(F.data.startswith("bar_"), Work.bartender_mix)
async def bartender_click(callback: types.CallbackQuery, state: FSMContext):
    ing = callback.data.split("_")[1]
    data = await state.get_data()
    recipe = data['recipe']
    step = data['current_step']

    if ing == recipe[step]:
        step += 1
        if step == len(recipe):
            reward = random.randint(100, 250)
            user = await get_user(callback.from_user.id)
            if user['vip_until'] > time.time(): reward *= 2

            await update_money(callback.from_user.id, reward)
            await callback.message.edit_text(f"✅ Коктейль готов! Вы заработали ${reward}")
            await end_work_session(callback.from_user.id)
            await state.clear()
        else:
            await state.update_data(current_step=step)
            await callback.message.edit_text(f"🍹 <b>Заказ:</b> {', '.join(recipe)}\n\nДобавлено: {', '.join(recipe[:step])}", parse_mode="HTML", reply_markup=callback.message.reply_markup)
    else:
        await callback.message.edit_text("🤢 Вы испортили коктейль! Клиент ушел.")
        await end_work_session(callback.from_user.id)
        await state.clear()

    await callback.answer()
