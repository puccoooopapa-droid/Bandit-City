from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from database import db
from keyboards import main_menu_kb, gender_kb, district_kb, reg_confirm_kb, back_kb
from states import Registration
import time
import random
import logging
from config import START_MONEY, START_DONATE

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))

    if user:
        # Миграция для старых игроков без тега
        if user['tag'] is None or user['tag'] == 0:
            while True:
                new_tag = random.randint(1000, 9999)
                exists = await db.fetchone("SELECT 1 FROM users WHERE last_name = ? AND tag = ?", (user['last_name'], new_tag))
                if not exists:
                    await db.execute("UPDATE users SET tag = ? WHERE user_id = ?", (new_tag, message.from_user.id))
                    user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
                    break

        logger.info(f"User {message.from_user.id} ({user['first_name']} {user['last_name']}) started bot (logged in).")
        await message.answer(f"👋 С возвращением, {user['first_name']}!", reply_markup=main_menu_kb())
    else:
        logger.info(f"New user {message.from_user.id} started registration.")
        await message.answer("👋 Добро пожаловать в БОТ БАНДИТ 2.0!\nДавайте создадим вашего персонажа.\n\nВведите ваше Имя:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.name)

@router.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    if len(message.text) > 20:
        await message.answer("Слишком длинное имя. Попробуйте еще раз:")
        return
    await state.update_data(name=message.text)
    await message.answer("Введите вашу Фамилию:", reply_markup=back_kb())
    await state.set_state(Registration.surname)

@router.message(Registration.surname)
async def reg_surname(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите ваше Имя:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.name)
        return

    await state.update_data(surname=message.text)
    await message.answer("Введите ваш возраст (10-90):", reply_markup=back_kb())
    await state.set_state(Registration.age)

@router.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите вашу Фамилию:", reply_markup=back_kb())
        await state.set_state(Registration.surname)
        return

    if not message.text.isdigit() or not (10 <= int(message.text) <= 90):
        await message.answer("Некорректный возраст. Введите число от 10 до 90:")
        return

    await state.update_data(age=int(message.text))
    await message.answer("Выберите пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)

@router.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите ваш возраст (10-90):", reply_markup=back_kb())
        await state.set_state(Registration.age)
        return

    if message.text not in ["Мужской", "Женский"]:
        await message.answer("Выберите пол кнопкой:")
        return

    await state.update_data(gender=message.text)
    await message.answer("Выберите район:", reply_markup=district_kb())
    await state.set_state(Registration.district)

@router.message(Registration.district)
async def reg_district(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Выберите пол:", reply_markup=gender_kb())
        await state.set_state(Registration.gender)
        return

    if message.text not in ["Центр", "Гетто", "Элитный", "Промзона"]:
        await message.answer("Выберите район кнопкой:")
        return

    await state.update_data(district=message.text)
    data = await state.get_data()

    text = (f"👤 Проверьте данные:\n\n"
            f"Имя: {data['name']}\n"
            f"Фамилия: {data['surname']}\n"
            f"Возраст: {data['age']}\n"
            f"Пол: {data['gender']}\n"
            f"Район: {data['district']}")

    await message.answer(text, reply_markup=reg_confirm_kb())
    await state.set_state(Registration.confirm)

@router.message(Registration.confirm)
async def reg_confirm(message: types.Message, state: FSMContext):
    if message.text == "🔁 Начать заново":
        await message.answer("Введите ваше Имя:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.name)
        return

    if message.text == "✅ Всё верно":
        data = await state.get_data()

        while True:
            tag = random.randint(1000, 9999)
            exists = await db.fetchone("SELECT 1 FROM users WHERE last_name = ? AND tag = ?", (data['surname'], tag))
            if not exists:
                break

        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, tag, age, gender, district, money, donate, reg_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, message.from_user.username, data['name'], data['surname'], tag, data['age'], data['gender'], data['district'], START_MONEY, START_DONATE, int(time.time())))

        logger.info(f"User {message.from_user.id} registered as {data['name']} {data['surname']}#{tag}.")
        await message.answer(f"✅ Персонаж создан!\nВаш ID: {data['surname']}#{str(tag).zfill(4)}\nДобро пожаловать в игру.", reply_markup=main_menu_kb())
        await state.clear()
    else:
        await message.answer("Используйте кнопки.")
