from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards import casino_menu_kb, blackjack_action_kb, main_menu_kb, cancel_kb
from states import Casino
from services.economy import check_jail, update_money, get_user
import asyncio
import random
import time

router = Router()

@router.message(F.text == "🎰 Казино")
async def casino_menu(message: types.Message):
    await message.answer("Добро пожаловать в Казино!", reply_markup=casino_menu_kb())

@router.message(F.text == "🎰 Слоты")
async def slots_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return
    await message.answer("Введите сумму ставки:", reply_markup=cancel_kb())
    await state.set_state(Casino.slots_bet)

@router.message(Casino.slots_bet)
async def slots_play(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=casino_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    bet = int(message.text)
    user = await get_user(message.from_user.id)
    if user['money'] < bet:
        await message.answer("Недостаточно денег.")
        return

    await update_money(message.from_user.id, -bet)

    msg = await message.answer("🎰 Крутим барабан... 🍒🍋🍇")
    await asyncio.sleep(0.5)
    await msg.edit_text("🎰 Крутим барабан... 🍋🍇🍒")
    await asyncio.sleep(0.5)
    await msg.edit_text("🎰 Крутим барабан... 🍇🍒🍋")
    await asyncio.sleep(0.5)

    slots = ["🍒", "🍋", "🍇", "7️⃣", "💎"]
    res = [random.choice(slots) for _ in range(3)]

    result_text = " | ".join(res)

    win_coeff = 0
    if res[0] == res[1] == res[2]:
        win_coeff = 5
        if res[0] == "7️⃣": win_coeff = 10
        if res[0] == "💎": win_coeff = 20
    elif res[0] == res[1] or res[1] == res[2] or res[0] == res[2]:
        win_coeff = 1.5 # Две одинаковые

    if win_coeff > 0:
        win_amount = int(bet * win_coeff)
        await update_money(message.from_user.id, win_amount)
        await msg.edit_text(f"🎰 Результат: {result_text}\n🎉 Вы выиграли ${win_amount}!")
    else:
        # Логика страховки казино
        if user['casino_insurance_until'] and user['casino_insurance_until'] > time.time():
            refund_amount = int(bet * 0.5)
            await update_money(message.from_user.id, refund_amount)
            await msg.edit_text(f"🎰 Результат: {result_text}\n😔 Вы проиграли, но 🛡 страховка вернула ${refund_amount}!")
        else:
            await msg.edit_text(f"🎰 Результат: {result_text}\n😔 Вы проиграли.")

    await state.clear()
    await message.answer("Сыграем еще?", reply_markup=casino_menu_kb())

# Blackjack (упрощенный)
@router.message(F.text == "🃏 Блэкджек")
async def bj_start(message: types.Message, state: FSMContext):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return
    await message.answer("Введите ставку:", reply_markup=cancel_kb())
    await state.set_state(Casino.blackjack_bet)

@router.message(Casino.blackjack_bet)
async def bj_bet(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=casino_menu_kb())
        return

    if not message.text.isdigit(): return
    bet = int(message.text)
    user = await get_user(message.from_user.id)
    if user['money'] < bet:
        await message.answer("Недостаточно денег.")
        return

    await update_money(message.from_user.id, -bet)

    player_score = random.randint(2, 11) + random.randint(2, 11)
    dealer_score = random.randint(2, 11)

    await state.update_data(bet=bet, player_score=player_score, dealer_score=dealer_score)
    await message.answer(f"🃏 Ваши карты: {player_score}\n👤 Дилер: {dealer_score} + ?", reply_markup=blackjack_action_kb())
    await state.set_state(Casino.blackjack_game)

@router.message(Casino.blackjack_game)
async def bj_game(message: types.Message, state: FSMContext):
    data = await state.get_data()
    player_score = data['player_score']
    dealer_score = data['dealer_score']
    bet = data['bet']

    if message.text == "➕ Ещё":
        card = random.randint(2, 11)
        player_score += card

        if player_score > 21:
            await message.answer(f"🃏 Вы взяли {card}. Итого: {player_score}\n💥 Перебор! Вы проиграли.", reply_markup=casino_menu_kb())
            await state.clear()
        else:
            await state.update_data(player_score=player_score)
            await message.answer(f"🃏 Вы взяли {card}. Итого: {player_score}\n👤 Дилер: {dealer_score} + ?", reply_markup=blackjack_action_kb())

    elif message.text == "🛑 Стоп":
        # Ход дилера
        while dealer_score < 17:
            dealer_score += random.randint(2, 11)

        text = f"🃏 Вы: {player_score}\n👤 Дилер: {dealer_score}\n\n"

        if dealer_score > 21 or player_score > dealer_score:
            win = bet * 2
            await update_money(message.from_user.id, win)
            text += f"🎉 Победа! Выигрыш: ${win}"
        elif player_score == dealer_score:
            await update_money(message.from_user.id, bet)
            text += "🤝 Ничья. Ставка возвращена."
        else:
            # Страховка в блэкджеке
            user = await get_user(message.from_user.id)
            if user['casino_insurance_until'] and user['casino_insurance_until'] > time.time():
                refund_amount = int(bet * 0.5)
                await update_money(message.from_user.id, refund_amount)
                text += f"😔 Вы проиграли, но 🛡 страховка вернула ${refund_amount}!"
            else:
                text += "😔 Вы проиграли."

        await message.answer(text, reply_markup=casino_menu_kb())
        await state.clear()
