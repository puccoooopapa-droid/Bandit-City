from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup # ИЗМЕНЕНИЕ: Добавлен импорт StatesGroup
from keyboards import bank_menu_kb, confirm_kb, main_menu_kb, cancel_kb, transfer_menu_kb
from states import Bank, Transfer
from services.economy import check_jail, update_money, get_user, add_transaction
from config import GAME_DAY_SECONDS, TRANSFER_COMMISSION
from database import db
import time

router = Router()

# --- Передача предметов (States) ---
class ItemTransfer(StatesGroup):
    choose_item = State()
    recipient = State()
    confirm = State()

@router.message(F.text == "🏦 Банк")
async def bank_menu(message: types.Message):
    await message.answer("🏦 Добро пожаловать в Банк!", reply_markup=bank_menu_kb())

# --- Кредиты (без изменений) ---
@router.message(F.text == "💰 Взять кредит")
async def credit_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    user = await get_user(message.from_user.id)
    if user['credit_amount'] > 0:
        await message.answer(f"❌ У вас уже есть активный кредит: ${user['credit_amount']}")
        return

    await message.answer("Введите сумму кредита (1000 - 200000):", reply_markup=cancel_kb())
    await state.set_state(Bank.credit_amount)

@router.message(Bank.credit_amount)
async def credit_amount_handler(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=bank_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    amount = int(message.text)
    if not (1000 <= amount <= 200000):
        await message.answer("Сумма должна быть от 1000 до 200000.")
        return

    await state.update_data(amount=amount)
    await message.answer("Введите срок кредита в игровых днях (30 - 50):")
    await state.set_state(Bank.credit_term)

@router.message(Bank.credit_term)
async def credit_term_handler(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=bank_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    days = int(message.text)
    if not (30 <= days <= 50):
        await message.answer("Срок должен быть от 30 до 50 дней.")
        return

    data = await state.get_data()
    amount = data['amount']
    total_repay = int(amount * 1.2) # 20%

    await state.update_data(days=days, total_repay=total_repay)

    await message.answer(
        f"📝 Условия кредита:\n"
        f"Сумма: ${amount}\n"
        f"Срок: {days} дней\n"
        f"К возврату: ${total_repay} (+20%)\n\n"
        f"Подтверждаете?",
        reply_markup=confirm_kb()
    )
    await state.set_state(Bank.credit_confirm)

@router.message(Bank.credit_confirm)
async def credit_confirm_handler(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        await db.execute("""
            UPDATE users SET money = money + ?, credit_amount = ?, credit_term_days = ?, credit_start_time = ?
            WHERE user_id = ?
        """, (data['amount'], data['total_repay'], data['days'], int(time.time()), message.from_user.id))

        await add_transaction(message.from_user.id, data['amount'], "Кредит: Получение")
        await message.answer(f"✅ Кредит на ${data['amount']} выдан!", reply_markup=bank_menu_kb())
    else:
        await message.answer("❌ Кредит отменен.", reply_markup=bank_menu_kb())

    await state.clear()

@router.message(F.text == "💸 Погасить кредит")
async def repay_credit_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user['credit_amount'] <= 0:
        await message.answer("У вас нет активных кредитов.")
        return

    await message.answer(f"Ваш долг: ${user['credit_amount']}\nВведите сумму погашения:", reply_markup=cancel_kb())
    await state.set_state(Bank.repay_amount)

@router.message(Bank.repay_amount)
async def repay_amount_handler(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=bank_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    amount = int(message.text)
    user = await get_user(message.from_user.id)

    if amount > user['money']:
        await message.answer("Недостаточно средств.")
        return

    if amount > user['credit_amount']:
        amount = user['credit_amount']

    new_credit = user['credit_amount'] - amount

    if new_credit == 0:
        await db.execute("UPDATE users SET money = money - ?, credit_amount = 0, credit_term_days = 0, credit_start_time = 0, reputation = reputation + 10 WHERE user_id = ?", (amount, message.from_user.id))
        await message.answer(f"✅ Кредит полностью погашен! Репутация +10.", reply_markup=bank_menu_kb())
    else:
        await db.execute("UPDATE users SET money = money - ?, credit_amount = ? WHERE user_id = ?", (amount, new_credit, message.from_user.id))
        await message.answer(f"✅ Внесено ${amount}. Остаток долга: ${new_credit}", reply_markup=bank_menu_kb())

    await add_transaction(message.from_user.id, -amount, "Кредит: Погашение")
    await state.clear()

# --- Переводы ---
@router.message(F.text == "🤝 Передать")
async def transfer_menu(message: types.Message):
    await message.answer("Что хотите передать?", reply_markup=transfer_menu_kb())

@router.message(F.text == "💸 Деньги")
async def transfer_money_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return
    await message.answer("Введите получателя в формате:\n<b>Фамилия#1234</b>\nИли @username", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(Transfer.recipient)

@router.message(Transfer.recipient)
async def transfer_recipient(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=bank_menu_kb())
        return

    target = message.text.strip()
    recipient = None

    if "@" in target:
        username = target.replace("@", "")
        recipient = await db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
    elif "#" in target:
        try:
            surname, tag = target.split("#")
            recipient = await db.fetchone("SELECT * FROM users WHERE last_name = ? AND tag = ?", (surname, int(tag)))
        except:
            pass

    if not recipient:
        await message.answer("❌ Игрок не найден. Проверьте формат (Фамилия#1234).")
        return

    if recipient['user_id'] == message.from_user.id:
        await message.answer("Нельзя переводить самому себе.")
        return

    await state.update_data(recipient_id=recipient['user_id'], recipient_name=f"{recipient['first_name']} {recipient['last_name']}")

    # Проверяем, что мы передаем (деньги или предмет)
    # Т.к. мы пришли из "💸 Деньги", то запрашиваем сумму
    # Но если бы мы пришли из "🎁 Предметы", логика была бы другой.
    # Упростим: этот хендлер только для денег, для предметов сделаем отдельный флоу или проверку стейта.

    await message.answer(f"Получатель: {recipient['first_name']} {recipient['last_name']}\nВведите сумму:", reply_markup=cancel_kb())
    await state.set_state(Transfer.amount)

@router.message(Transfer.amount)
async def transfer_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=bank_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    amount = int(message.text)
    if amount <= 0:
        await message.answer("Сумма должна быть больше 0.")
        return

    user = await get_user(message.from_user.id)
    total_amount = int(amount * (1 + TRANSFER_COMMISSION))

    if user['money'] < total_amount:
        await message.answer(f"Недостаточно средств. С учетом комиссии {int(TRANSFER_COMMISSION*100)}% нужно ${total_amount}")
        return

    data = await state.get_data()
    await state.update_data(amount=amount, total_amount=total_amount)

    await message.answer(f"Перевод ${amount} игроку {data['recipient_name']}.\nСпишется: ${total_amount} (комиссия).\nПодтвердить?", reply_markup=confirm_kb())
    await state.set_state(Transfer.confirm)

@router.message(Transfer.confirm)
async def transfer_confirm(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        await update_money(message.from_user.id, -data['total_amount'])
        await update_money(data['recipient_id'], data['amount'])

        await add_transaction(message.from_user.id, -data['total_amount'], f"Перевод игроку {data['recipient_id']}")
        await add_transaction(data['recipient_id'], data['amount'], f"Перевод от игрока {message.from_user.id}")

        await message.answer("✅ Перевод выполнен!", reply_markup=bank_menu_kb())
    else:
        await message.answer("❌ Перевод отменен.", reply_markup=bank_menu_kb())
    await state.clear()

@router.message(F.text == "🎁 Предметы")
async def transfer_item_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    items = await db.fetchall("SELECT * FROM owned_items WHERE user_id = ?", (message.from_user.id,))
    if not items:
        await message.answer("У вас нет предметов для передачи.")
        return

    kb = []
    for item in items:
        kb.append([types.InlineKeyboardButton(text=f"{item['item_name']}", callback_data=f"gift_item_{item['id']}")])
    kb.append([types.InlineKeyboardButton(text="❌ Отмена", callback_data="gift_cancel")])

    await message.answer("Выберите предмет для подарка:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(ItemTransfer.choose_item)

@router.callback_query(F.data.startswith("gift_item_"))
async def gift_item_chosen(callback: types.CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[2])
    item = await db.fetchone("SELECT * FROM owned_items WHERE id = ?", (item_id,))

    if not item:
        await callback.answer("Предмет не найден")
        return

    await state.update_data(item_id=item_id, item_name=item['item_name'])
    await callback.message.edit_text(f"Выбрано: {item['item_name']}.\nВведите получателя (Фамилия#1234 или @username):")
    await state.set_state(ItemTransfer.recipient)

@router.message(ItemTransfer.recipient)
async def gift_recipient(message: types.Message, state: FSMContext):
    target = message.text.strip()
    recipient = None

    if "@" in target:
        username = target.replace("@", "")
        recipient = await db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
    elif "#" in target:
        try:
            surname, tag = target.split("#")
            recipient = await db.fetchone("SELECT * FROM users WHERE last_name = ? AND tag = ?", (surname, int(tag)))
        except:
            pass

    if not recipient:
        await message.answer("❌ Игрок не найден.")
        return

    if recipient['user_id'] == message.from_user.id:
        await message.answer("Нельзя дарить самому себе.")
        return

    data = await state.get_data()
    await state.update_data(recipient_id=recipient['user_id'], recipient_name=f"{recipient['first_name']} {recipient['last_name']}")

    await message.answer(f"Подарить {data['item_name']} игроку {recipient['first_name']} {recipient['last_name']}?", reply_markup=confirm_kb())
    await state.set_state(ItemTransfer.confirm)

@router.message(ItemTransfer.confirm)
async def gift_confirm(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить":
        data = await state.get_data()

        # Передача владения
        await db.execute("UPDATE owned_items SET user_id = ? WHERE id = ?", (data['recipient_id'], data['item_id']))

        await message.answer(f"✅ Вы подарили {data['item_name']} игроку {data['recipient_name']}!", reply_markup=bank_menu_kb())
    else:
        await message.answer("❌ Отмена.", reply_markup=bank_menu_kb())
    await state.clear()
