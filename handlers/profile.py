from aiogram import Router, F, types
from database import db
from services.economy import check_jail
from services.events import current_event # Импортируем текущее событие
import time
import random

router = Router()

@router.message(F.text == "👤 Персонаж")
async def show_profile(message: types.Message):
    user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    if not user:
        await message.answer("Ошибка: Персонаж не найден. Введите /start")
        return

    # Миграция для старых игроков без тега (если вдруг пропустили)
    if user['tag'] is None or user['tag'] == 0:
        while True:
            new_tag = random.randint(1000, 9999)
            exists = await db.fetchone("SELECT 1 FROM users WHERE last_name = ? AND tag = ?", (user['last_name'], new_tag))
            if not exists:
                await db.execute("UPDATE users SET tag = ? WHERE user_id = ?", (new_tag, message.from_user.id))
                user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,)) # Обновляем данные пользователя
                break

    businesses = await db.fetchall("SELECT * FROM user_businesses WHERE user_id = ?", (message.from_user.id,))
    biz_count = len(businesses)

    is_jailed, jail_msg = await check_jail(message.from_user.id)
    status = jail_msg if is_jailed else "Свободен"

    credit_info = ""
    if user['credit_amount'] > 0:
        credit_info = f"\n💳 Кредит: ${user['credit_amount']} (Срок: {user['credit_term_days']} дн.)"

    vip_badge = ""
    if user['vip_until'] and user['vip_until'] > time.time():
        vip_badge = " 👑 VIP"

    # Формируем ID игрока
    player_id_str = f"{user['last_name']}#{str(user['tag']).zfill(4)}"
    if user['username']:
        player_id_str += f" (@{user['username']})"

    # Био
    bio_text = f"📝 Био: {user['bio']}\n" if user['bio'] else ""

    # Информация о текущем событии
    event_info = ""
    if current_event["name"] != "Спокойствие":
        event_info = f"✨ Событие: {current_event['name']} ({current_event['description']})\n"

    text = (
        f"👤 <b>Профиль: {user['first_name']} {user['last_name']}</b>{vip_badge}\n"
        f"🆔 ID: <code>{player_id_str}</code>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🎂 Возраст: {user['age']}\n"
        f"🚻 Пол: {user['gender']}\n"
        f"🏙 Район: {user['district']}\n"
        f"{bio_text}"
        f"⚡ Энергия: {user['energy']}/{user['max_energy']}\n"
        f"🚗 Гараж: {user['garage_slots']} слотов\n"
        f"🎒 Инвентарь: {user['inventory_slots']} слотов\n"
        f"⭐ Рейтинг: {user['rating']:.1f}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 Деньги: ${user['money']}\n"
        f"💎 Донат: {user['donate']}\n"
        f"🌟 Репутация: {user['reputation']}\n"
        f"💼 Бизнесов: {biz_count}\n"
        f"👮 Статус: {status}\n"
        f"{event_info}" # Добавляем информацию о событии
        f"{credit_info}"
    )

    await message.answer(text, parse_mode="HTML")
