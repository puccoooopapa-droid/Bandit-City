from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from database import db
from keyboards import main_menu_kb, gender_kb, district_kb, reg_confirm_kb
from states import Registration
import time

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))

    if user:
        await message.answer(f"С возвращением, {user['first_name']}!", reply_markup=main_menu_kb())
    else:
        await message.answer("👋 Добро пожаловать в <b>Bandit City</b>!\n\nДавай создадим твоего персонажа.\nКак тебя зовут? (Имя)", parse_mode="HTML")
        await state.set_state(Registration.name)

@router.message(Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    if len(message.text) > 20:
        await message.answer("Имя слишком длинное. Попробуй еще раз.")
        return
    await state.update_data(name=message.text)
    await message.answer("Теперь введи свою фамилию:")
    await state.set_state(Registration.surname)

@router.message(Registration.surname)
async def process_surname(message: types.Message, state: FSMContext):
    if len(message.text) > 20:
        await message.answer("Фамилия слишком длинная.")
        return
    await state.update_data(surname=message.text)
    await message.answer("Сколько тебе лет? (18-90)")
    await state.set_state(Registration.age)

@router.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    age = int(message.text)
    if not (18 <= age <= 90):
        await message.answer("Возраст должен быть от 18 до 90.")
        return
    await state.update_data(age=age)
    await message.answer("Твой пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)

@router.message(Registration.gender)
async def process_gender(message: types.Message, state: FSMContext):
    if message.text not in ["Мужской", "Женский"]:
        await message.answer("Выберите пол кнопкой.")
        return
    await state.update_data(gender=message.text)
    await message.answer("В каком районе начнешь путь?", reply_markup=district_kb())
    await state.set_state(Registration.district)

@router.message(Registration.district)
async def process_district(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Твой пол:", reply_markup=gender_kb())
        await state.set_state(Registration.gender)
        return

    if message.text not in ["Центр", "Гетто", "Элитный", "Промзона"]:
        await message.answer("Выберите район кнопкой.")
        return

    await state.update_data(district=message.text)
    data = await state.get_data()

    # Генерация уникального тега
    while True:
        tag = int(str(time.time_ns())[-4:]) # Простой рандом
        exists = await db.fetchone("SELECT 1 FROM users WHERE last_name = ? AND tag = ?", (data['surname'], tag))
        if not exists: break

    # Сохранение в БД
    await db.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, tag, age, gender, district, money, reg_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, message.from_user.username, data['name'], data['surname'], tag, data['age'], data['gender'], data['district'], 1000, int(time.time())))

    await state.clear()

    # --- ИЗМЕНЕНИЕ: Предложение подписаться ---
    text = (f"✅ Персонаж создан!\n"
            f"👤 <b>{data['name']} {data['surname']} #{tag}</b>\n\n"
            f"🔥 Чтобы быть в курсе новостей и обновлений, подпишись на наш канал!")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Подписаться", url="https://t.me/BanditCity_K")],
        [types.InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_sub")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# Обработчик кнопки "Пропустить"
@router.callback_query(F.data == "skip_sub")
async def skip_subscription(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Добро пожаловать в город! 🌆", reply_markup=main_menu_kb())
