from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_kb, cancel_kb
from database import db
from services.economy import check_jail

router = Router()

class Settings(StatesGroup):
    change_name = State()
    change_surname = State()

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    is_jailed, jail_msg = await check_jail(message.from_user.id)
    if is_jailed:
        await message.answer(jail_msg)
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ Сменить Имя", callback_data="settings_change_name")],
        [types.InlineKeyboardButton(text="✏️ Сменить Фамилию", callback_data="settings_change_surname")],
        [types.InlineKeyboardButton(text="🔄 Сброс прогресса (Опасно!)", callback_data="settings_reset_confirm")]
    ])

    await message.answer("⚙️ Настройки профиля:", reply_markup=kb)

@router.callback_query(F.data == "settings_change_name")
async def change_name_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое имя:", reply_markup=cancel_kb())
    await state.set_state(Settings.change_name)
    await callback.answer()

@router.message(Settings.change_name)
async def change_name_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if len(message.text) > 20:
        await message.answer("Слишком длинное имя.")
        return

    await db.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (message.text, message.from_user.id))
    await message.answer(f"✅ Имя изменено на {message.text}", reply_markup=main_menu_kb())
    await state.clear()

@router.callback_query(F.data == "settings_change_surname")
async def change_surname_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую фамилию:", reply_markup=cancel_kb())
    await state.set_state(Settings.change_surname)
    await callback.answer()

@router.message(Settings.change_surname)
async def change_surname_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if len(message.text) > 20:
        await message.answer("Слишком длинная фамилия.")
        return

    await db.execute("UPDATE users SET last_name = ? WHERE user_id = ?", (message.text, message.from_user.id))
    await message.answer(f"✅ Фамилия изменена на {message.text}", reply_markup=main_menu_kb())
    await state.clear()

@router.callback_query(F.data == "settings_reset_confirm")
async def reset_confirm(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="ДА, СБРОСИТЬ ВСЁ", callback_data="settings_reset_final")],
        [types.InlineKeyboardButton(text="НЕТ, ОТМЕНА", callback_data="settings_cancel")]
    ])
    await callback.message.edit_text("⚠️ Вы уверены? Это удалит ВЕСЬ прогресс, деньги и бизнесы безвозвратно!", reply_markup=kb)

@router.callback_query(F.data == "settings_reset_final")
async def reset_final(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM user_businesses WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM user_robots WHERE user_id = ?", (user_id,))
    await state.clear()
    await callback.message.answer("🔄 Прогресс сброшен. Введите /start для начала новой игры.", reply_markup=types.ReplyKeyboardRemove())
    await callback.answer()

@router.callback_query(F.data == "settings_cancel")
async def settings_cancel(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")
