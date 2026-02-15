from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_kb, cancel_kb
from database import db
from services.economy import update_money, update_donate, get_user
import time
from config import VIP_DURATION

router = Router()

class Donate(StatesGroup):
    exchange_amount = State()

# Цены
EXCHANGE_RATE = 10000 # 1 💎 = $10000
VIP_PRICE = 500      # 500 💎
COOLDOWN_BOOST_PRICE = 100 # 100 💎
CASINO_INSURANCE_PRICE = 200 # 200 💎
COOLDOWN_BOOST_DURATION = 3600 # 1 час

@router.message(F.text == "💎 Донат")
async def donate_menu(message: types.Message):
    user = await get_user(message.from_user.id)

    if not user:
        await message.answer("Ошибка: Пользователь не найден.")
        return

    vip_status = "❌ Нет"
    if user['vip_until'] and user['vip_until'] > time.time():
        days_left = int((user['vip_until'] - time.time()) / 86400)
        vip_status = f"✅ Активен ({days_left} дн.)"

    text = (f"💎 <b>Донат Меню</b>\n"
            f"Ваш баланс: {user['donate']} 💎\n"
            f"VIP статус: {vip_status}\n\n"
            f"👑 <b>VIP привилегии:</b>\n"
            f"• x2 Доход с работ\n"
            f"• x2 Доход с бизнесов\n"
            f"• Уникальный значок в профиле\n\n"
            f"💱 <b>Курс обмена:</b> 1 💎 = ${EXCHANGE_RATE}")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="donate_buy")],
        [types.InlineKeyboardButton(text="👑 Купить VIP (500 💎)", callback_data="donate_buy_vip")],
        [types.InlineKeyboardButton(text="⚡ Ускорить кулдауны (100 💎)", callback_data="donate_cooldown_boost")],
        [types.InlineKeyboardButton(text="🛡 Страховка казино (200 💎)", callback_data="donate_casino_insurance")],
        [types.InlineKeyboardButton(text="💱 Обменять 💎 на $", callback_data="donate_exchange")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "donate_buy")
async def donate_buy_info(callback: types.CallbackQuery):
    text = ("💳 <b>Пополнение баланса</b>\n\n"
            "Для пополнения донат-валюты свяжитесь с администратором: @A1ztv\n"
            "Укажите свой ID (Фамилия#XXXX) и желаемую сумму.\n"
            "После оплаты администратор выдаст вам 💎.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="donate_back")]]))

@router.callback_query(F.data == "donate_back")
async def donate_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await donate_menu(callback.message)

@router.callback_query(F.data == "donate_buy_vip")
async def buy_vip(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)

    if user['vip_until'] and user['vip_until'] > time.time():
        await callback.answer("У вас уже есть VIP!", show_alert=True)
        return

    if user['donate'] < VIP_PRICE:
        await callback.answer(f"Не хватает {VIP_PRICE - user['donate']} 💎", show_alert=True)
        return

    await update_donate(callback.from_user.id, -VIP_PRICE)
    new_vip_time = int(time.time() + VIP_DURATION)
    await db.execute("UPDATE users SET vip_until = ? WHERE user_id = ?", (new_vip_time, callback.from_user.id))

    await callback.message.edit_text(f"👑 <b>Поздравляем!</b>\nВы купили VIP статус на 30 дней.\nТеперь ваши доходы удвоены!", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "donate_cooldown_boost")
async def buy_cooldown_boost(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)

    if user['donate'] < COOLDOWN_BOOST_PRICE:
        await callback.answer(f"Не хватает {COOLDOWN_BOOST_PRICE - user['donate']} 💎", show_alert=True)
        return

    await db.execute("UPDATE users SET work_cooldown = 0 WHERE user_id = ?", (callback.from_user.id,))
    await update_donate(callback.from_user.id, -COOLDOWN_BOOST_PRICE)

    await callback.message.edit_text(f"⚡ Ваши кулдауны на работу сброшены! Можете сразу приступать к новой работе.")
    await callback.answer()

@router.callback_query(F.data == "donate_casino_insurance")
async def buy_casino_insurance(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)

    if user['donate'] < CASINO_INSURANCE_PRICE:
        await callback.answer(f"Не хватает {CASINO_INSURANCE_PRICE - user['donate']} 💎", show_alert=True)
        return

    insurance_duration = 3600 # 1 час
    await db.execute("UPDATE users SET casino_insurance_until = ? WHERE user_id = ?", (int(time.time() + insurance_duration), callback.from_user.id))
    await update_donate(callback.from_user.id, -CASINO_INSURANCE_PRICE)

    await callback.message.edit_text(f"🛡 Вы купили страховку казино на 1 час! В случае проигрыша, часть ставки будет возвращена.")
    await callback.answer()

@router.callback_query(F.data == "donate_exchange")
async def exchange_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите количество 💎 для обмена:", reply_markup=cancel_kb())
    await state.set_state(Donate.exchange_amount)
    await callback.answer()

@router.message(Donate.exchange_amount)
async def exchange_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    amount = int(message.text)
    if amount <= 0: return

    user = await get_user(message.from_user.id)
    if user['donate'] < amount:
        await message.answer("Недостаточно 💎 на балансе.")
        return

    money_amount = amount * EXCHANGE_RATE

    await update_donate(message.from_user.id, -amount)
    await update_money(message.from_user.id, money_amount)

    await message.answer(f"✅ Обмен успешен!\nВы обменяли {amount} 💎 на ${money_amount}", reply_markup=main_menu_kb())
    await state.clear()
