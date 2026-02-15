from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import taxi_passenger_kb, taxi_dest_kb, main_menu_kb, confirm_kb, transport_menu_kb
from database import db
from services.economy import update_money, get_user, check_jail
from services.events import current_event
from handlers.shop import SHOP_ITEMS
from states import TaxiOrder, PersonalTravel
import time
import asyncio
import random
import logging

router = Router()
logger = logging.getLogger(__name__)

# --- Меню Транспорта ---
@router.message(F.text == "🚕 Транспорт")
async def transport_menu(message: types.Message):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return
    await message.answer("Выберите способ передвижения:", reply_markup=transport_menu_kb())

# --- 1. Поездка на СВОЕЙ машине ---
@router.message(F.text == "🚗 Поехать на своей")
async def personal_travel_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    my_cars = await db.fetchall("SELECT * FROM owned_items WHERE user_id = ? AND category = 'car'", (message.from_user.id,))

    if not my_cars:
        await message.answer("❌ У вас нет машины! Купите её в магазине (Промзона).")
        return

    best_car = None
    min_time = 9999

    for car_db in my_cars:
        car_config = next((item for item in SHOP_ITEMS['car']['items'] if item['id'] == car_db['item_key']), None)
        if car_config and car_config.get('travel_time', 999) < min_time:
            min_time = car_config['travel_time']
            best_car = car_config

    if best_car:
        await state.update_data(car_name=best_car['name'], travel_time=min_time)
        await message.answer(f"🚗 Ваша машина: <b>{best_car['name']}</b>\nКуда поедем? (Время: {min_time} сек)", parse_mode="HTML", reply_markup=taxi_dest_kb())
        await state.set_state(PersonalTravel.destination)
    else:
        await message.answer("Ошибка данных о машине.")

@router.message(PersonalTravel.destination)
async def personal_travel_dest(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Меню транспорта", reply_markup=transport_menu_kb())
        await state.clear()
        return

    if message.text not in ["Центр", "Гетто", "Элитный", "Промзона"]:
        await message.answer("Выберите район кнопкой.")
        return

    user = await get_user(message.from_user.id)
    if user['district'] == message.text:
        await message.answer("Вы уже находитесь в этом районе.")
        return

    data = await state.get_data()
    await state.update_data(dest=message.text)

    await message.answer(f"Поехать в {message.text} на {data['car_name']}?\nЭто займет {data['travel_time']} сек.", reply_markup=confirm_kb())
    await state.set_state(PersonalTravel.confirm)

@router.message(PersonalTravel.confirm)
async def personal_travel_confirm(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        dest = data['dest']
        travel_time = data['travel_time']

        await message.answer(f"🚗 Вы поехали в {dest}...", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()

        await asyncio.sleep(travel_time)

        await db.execute("UPDATE users SET district = ? WHERE user_id = ?", (dest, message.from_user.id))
        logger.info(f"User {message.from_user.id} traveled to {dest} in their car.")
        await message.answer(f"🏁 Вы прибыли в {dest}!", reply_markup=main_menu_kb())

    else:
        await message.answer("Отмена.", reply_markup=transport_menu_kb())
        await state.clear()


# --- 2. Заказ ТАКСИ ---
@router.message(F.text == "🚕 Заказать такси")
async def taxi_order_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    active_order = await db.fetchone("SELECT * FROM taxi_orders WHERE passenger_id = ? AND status IN ('WAITING', 'ASSIGNED')", (message.from_user.id,))
    if active_order:
        await message.answer("❌ У вас уже есть активный заказ!")
        return

    await message.answer("Куда поедем на такси?", reply_markup=taxi_dest_kb())
    await state.set_state(TaxiOrder.destination)

@router.message(TaxiOrder.destination)
async def taxi_dest_chosen(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Меню транспорта", reply_markup=transport_menu_kb())
        await state.clear()
        return

    if message.text not in ["Центр", "Гетто", "Элитный", "Промзона"]:
        await message.answer("Выберите район кнопкой.")
        return

    price = 100
    if message.text == "Элитный": price = 300

    await state.update_data(dest=message.text, price=price)
    await message.answer(f"Поездка в {message.text}. Цена: ${price}.\nЗаказываем?", reply_markup=confirm_kb())
    await state.set_state(TaxiOrder.confirm)

@router.message(TaxiOrder.confirm)
async def taxi_confirm(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        user = await get_user(message.from_user.id)

        if user['money'] < data['price']:
            await message.answer("Недостаточно денег!")
            await state.clear()
            return

        order_id = await db.execute("""
            INSERT INTO taxi_orders (passenger_id, destination, price, status, created_at)
            VALUES (?, ?, ?, 'WAITING', ?)
        """, (message.from_user.id, data['dest'], data['price'], int(time.time())))

        logger.info(f"User {message.from_user.id} created taxi order #{order_id} to {data['dest']} for ${data['price']}.")
        await message.answer("🚕 Заказ создан! Ищем водителя (60 сек)...", reply_markup=types.ReplyKeyboardRemove())

        asyncio.create_task(wait_for_driver(message, order_id, data['price'], data['dest']))
        await state.clear()

    else:
        await message.answer("Отмена.", reply_markup=transport_menu_kb())
        await state.clear()

async def wait_for_driver(message, order_id, price, dest):
    for _ in range(12):
        await asyncio.sleep(5)
        order = await db.fetchone("SELECT * FROM taxi_orders WHERE id = ?", (order_id,))

        if order['status'] == 'ASSIGNED':
            driver = await get_user(order['driver_id'])
            logger.info(f"Taxi order #{order_id} assigned to driver {driver['user_id']}.")
            await message.answer(f"✅ Вас забрал водитель {driver['first_name']} {driver['last_name']}!\nЕдем в {dest}...")

            await asyncio.sleep(50)

            # --- РИСК В ТАКСИ ---
            outcome = random.choices(["success", "tip", "escape", "scam"], weights=[70, 15, 10, 5], k=1)[0]

            if outcome == "success":
                await update_money(message.from_user.id, -price)
                await update_money(order['driver_id'], price)
                await message.answer("🏁 Приехали! Вы оплатили поездку.")
                logger.info(f"Taxi order #{order_id} completed successfully. Driver earned ${price}.")
            elif outcome == "tip":
                tip = int(price * 0.2)
                await update_money(message.from_user.id, -(price + tip))
                await update_money(order['driver_id'], price + tip)
                await message.answer(f"🏁 Приехали! Вы остались довольны и оставили ${tip} чаевых.")
                logger.info(f"Taxi order #{order_id} completed with a tip. Driver earned ${price + tip}.")
            elif outcome == "escape":
                await update_money(order['driver_id'], -int(price * 0.5)) # Штраф водителю
                await message.answer("🏃‍♂️ Вы сбежали, не заплатив! Водитель в ярости.")
                logger.warning(f"Taxi order #{order_id}: passenger escaped. Driver fined ${int(price * 0.5)}.")
            elif outcome == "scam":
                await update_money(message.from_user.id, -price) # Пассажир платит
                # Водитель не получает деньги
                await message.answer("😠 Водитель оказался мошенником и увез вас не туда! Деньги списаны, но вы остались в том же районе.")
                logger.warning(f"Taxi order #{order_id}: driver was a scammer. Passenger paid, driver got nothing.")
                dest = (await get_user(message.from_user.id))['district'] # Остаемся в том же районе

            await db.execute("UPDATE taxi_orders SET status = 'COMPLETED' WHERE id = ?", (order_id,))

            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ 5", callback_data=f"rate_taxi_{order['driver_id']}_5")],
                [types.InlineKeyboardButton(text="⭐ 1", callback_data=f"rate_taxi_{order['driver_id']}_1")]
            ])
            await message.answer("Оцените водителя:", reply_markup=kb)

            await db.execute("UPDATE users SET district = ? WHERE user_id = ?", (dest, message.from_user.id))
            return

    await db.execute("UPDATE taxi_orders SET status = 'COMPLETED', driver_id = 0 WHERE id = ?", (order_id,))
    await update_money(message.from_user.id, -price)
    await db.execute("UPDATE users SET district = ? WHERE user_id = ?", (dest, message.from_user.id))
    logger.info(f"Taxi order #{order_id} completed by NPC.")
    await message.answer(f"🚕 Водители заняты. Вас отвезло NPC-такси.\nСписано ${price}. Вы прибыли в {dest}.", reply_markup=main_menu_kb())

# --- Водитель: Взять заказ ---
@router.callback_query(F.data.startswith("take_order_"))
async def take_order_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])

    order = await db.fetchone("SELECT * FROM taxi_orders WHERE id = ?", (order_id,))
    if not order or order['status'] != 'WAITING':
        await callback.answer("Заказ уже не актуален", show_alert=True)
        await callback.message.delete()
        return

    if order['passenger_id'] == callback.from_user.id:
        await callback.answer("Нельзя везти самого себя!", show_alert=True)
        return

    await db.execute("UPDATE taxi_orders SET status = 'ASSIGNED', driver_id = ? WHERE id = ?", (callback.from_user.id, order_id))

    logger.info(f"User {callback.from_user.id} took taxi order #{order_id}.")
    await callback.message.edit_text(f"✅ Вы взяли заказ! Везите пассажира в {order['destination']}.")
    await callback.answer()

# --- Рейтинг ---
@router.callback_query(F.data.startswith("rate_taxi_"))
async def rate_driver(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    driver_id = int(parts[2])
    stars = int(parts[3])

    driver = await get_user(driver_id)
    new_rating = (driver['rating'] * 10 + stars) / 11 if driver['rating'] > 0 else stars

    await db.execute("UPDATE users SET rating = ? WHERE user_id = ?", (new_rating, driver_id))
    logger.info(f"User {callback.from_user.id} rated driver {driver_id} with {stars} stars.")
    await callback.message.edit_text("Спасибо за оценку!")
