from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_kb, cancel_kb
from database import db
from services.economy import update_money, get_user
import time
import random

router = Router()

class Invest(StatesGroup):
    amount = State()

NPC_INVESTORS = [
    {"name": "👨‍💼 Алексей (Стартап)", "min": 100000, "profit": (10, 25), "risk": "medium", "time": 1800}, # 30 мин
    {"name": "👩‍💼 Елена (Крипта)", "min": 500000, "profit": (20, 50), "risk": "high", "time": 3600}, # 1 час
    {"name": "👴 Уоррен (Фонды)", "min": 1000000, "profit": (5, 15), "risk": "low", "time": 7200}, # 2 часа
]

@router.message(F.text == "🏦 Инвестиции")
async def invest_menu(message: types.Message):
    # ИЗМЕНЕНИЕ: Убрана проверка баланса для входа

    # Проверяем активные инвестиции
    active = await db.fetchall("SELECT * FROM investments WHERE user_id = ? AND status = 'active'", (message.from_user.id,))

    text = "🏦 <b>Инвестиционный фонд</b>\n\n"

    if active:
        text += "⏳ <b>Ваши активные вклады:</b>\n"
        for inv in active:
            remaining = inv['end_time'] - time.time()
            if remaining > 0:
                text += f"🔹 {inv['npc_name']}: ${inv['invested_amount']:,} (Осталось: {int(remaining//60)} мин)\n"
            else:
                text += f"✅ {inv['npc_name']}: <b>Готово к сбору!</b>\n"
        text += "\n"

    text += "💼 <b>Доступные предложения:</b>\nВыберите, куда вложить деньги:"

    kb = []
    for i, npc in enumerate(NPC_INVESTORS):
        risk_emoji = "🟢" if npc['risk'] == "low" else "🟡" if npc['risk'] == "medium" else "🔴"
        btn_text = f"{npc['name']} | Мин: ${npc['min']:,}"
        kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"invest_info_{i}")])

    kb.append([types.InlineKeyboardButton(text="💰 Забрать прибыль", callback_data="invest_collect")])

    await message.answer(text, parse_mode="HTML", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("invest_info_"))
async def invest_info(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[2])
    npc = NPC_INVESTORS[idx]

    risk_text = "Низкий (Шанс потери 10%)" if npc['risk'] == "low" else "Средний (Шанс потери 30%)" if npc['risk'] == "medium" else "Высокий (Шанс потери 50%)"

    text = (f"📊 <b>Предложение от: {npc['name']}</b>\n\n"
            f"💰 Мин. сумма: ${npc['min']:,}\n"
            f"📈 Ожидаемая прибыль: {npc['profit'][0]}-{npc['profit'][1]}%\n"
            f"⚠️ Риск: {risk_text}\n"
            f"⏱ Срок: {int(npc['time']//60)} мин\n\n"
            f"Хотите инвестировать?")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Инвестировать", callback_data=f"invest_start_{idx}")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="invest_back")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "invest_back")
async def invest_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await invest_menu(callback.message)

@router.callback_query(F.data.startswith("invest_start_"))
async def invest_start(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[2])
    npc = NPC_INVESTORS[idx]

    await state.update_data(npc_idx=idx)
    await callback.message.answer(f"Введите сумму для инвестиции (Мин: ${npc['min']:,}):", reply_markup=cancel_kb())
    await state.set_state(Invest.amount)
    await callback.answer()

@router.message(Invest.amount)
async def invest_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if not message.text.isdigit():
        await message.answer("Введите число.")
        return

    amount = int(message.text)
    data = await state.get_data()
    npc = NPC_INVESTORS[data['npc_idx']]

    if amount < npc['min']:
        await message.answer(f"Минимальная сумма: ${npc['min']:,}")
        return

    user = await get_user(message.from_user.id)
    if user['money'] < amount:
        await message.answer("Недостаточно денег.")
        return

    await update_money(message.from_user.id, -amount)

    # Расчет результата сразу
    risk_roll = random.random()
    status = "active"
    profit_percent = 0

    # Шанс провала
    fail_chance = 0.1 if npc['risk'] == "low" else 0.3 if npc['risk'] == "medium" else 0.5

    if risk_roll < fail_chance:
        # Потеря части денег (от 10% до 50%)
        loss_percent = random.uniform(0.1, 0.5)
        profit_percent = -loss_percent
    else:
        # Прибыль
        profit_percent = random.uniform(npc['profit'][0], npc['profit'][1]) / 100

    end_time = int(time.time() + npc['time'])

    await db.execute("""
        INSERT INTO investments (user_id, npc_name, invested_amount, potential_profit_percent, risk_level, end_time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, npc['name'], amount, profit_percent, npc['risk'], end_time, status))

    await message.answer(f"✅ Вы инвестировали ${amount:,} в {npc['name']}.\nВернитесь через {int(npc['time']//60)} минут за результатом.", reply_markup=main_menu_kb())
    await state.clear()

@router.callback_query(F.data == "invest_collect")
async def invest_collect(callback: types.CallbackQuery):
    investments = await db.fetchall("SELECT * FROM investments WHERE user_id = ? AND status = 'active' AND end_time <= ?", (callback.from_user.id, int(time.time())))

    if not investments:
        await callback.answer("Нет завершенных инвестиций", show_alert=True)
        return

    total_payout = 0
    text = "📊 <b>Результаты инвестиций:</b>\n\n"

    for inv in investments:
        profit = int(inv['invested_amount'] * inv['potential_profit_percent'])
        payout = inv['invested_amount'] + profit
        total_payout += payout

        if profit > 0:
            text += f"✅ {inv['npc_name']}: Прибыль +${profit:,}\n"
        else:
            text += f"❌ {inv['npc_name']}: Убыток -${abs(profit):,}\n"

        await db.execute("UPDATE investments SET status = 'completed' WHERE id = ?", (inv['id'],))

    await update_money(callback.from_user.id, total_payout)
    text += f"\n💰 Итого получено: ${total_payout:,}"

    await callback.message.edit_text(text, parse_mode="HTML")
