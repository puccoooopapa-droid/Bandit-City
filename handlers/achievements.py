from aiogram import Router, F, types
from services.achievements import check_all_achievements, ACHIEVEMENTS
from database import db

router = Router()

@router.message(F.text == "🏆 Достижения")
async def achievements_menu(message: types.Message):
    # Сначала проверяем новые достижения
    new_unlocked = await check_all_achievements(message.from_user.id)
    if new_unlocked:
        text = "🎉 <b>Новые достижения!</b>\n\n"
        for ach in new_unlocked:
            text += f"✅ {ach['name']} (+${ach['reward_money']}, +{ach['reward_rep']} реп.)\n"
        await message.answer(text, parse_mode="HTML")

    # Показываем список
    user_achs = await db.fetchall("SELECT achievement_key FROM user_achievements WHERE user_id = ?", (message.from_user.id,))
    unlocked_keys = {row['achievement_key'] for row in user_achs}

    text = "🏆 <b>Ваши достижения:</b>\n\n"

    for key, data in ACHIEVEMENTS.items():
        status = "✅" if key in unlocked_keys else "🔒"
        text += f"{status} <b>{data['name']}</b>\n"
        text += f"   {data['desc']}\n"
        if key not in unlocked_keys:
            text += f"   Награда: ${data['reward_money']} | {data['reward_rep']} реп.\n"
        text += "\n"

    await message.answer(text, parse_mode="HTML")
