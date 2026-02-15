from aiogram import Router, F, types
from aiogram.types import WebAppInfo
from database import db
from services.economy import get_user

router = Router()

# URL вашего WebApp (нужно заменить на реальный HTTPS URL после деплоя)
# Для локальной разработки используйте ngrok URL
WEBAPP_URL = "https://bandit-city.onrender.com"

@router.message(F.text == "📈 Трейдинг")
async def trading_menu(message: types.Message):
    # ИЗМЕНЕНИЕ: Убрана проверка достижения, доступ открыт всем
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Открыть биржу", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("📈 Доступ к бирже открыт! Нажмите кнопку ниже, чтобы начать торговлю.", reply_markup=kb)

