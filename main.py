import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import db
from handlers import start, menu, profile, work, bank, business, casino, admin, shop, settings, donate, taxi, trading, invest, achievements
from services.scheduler import start_loops

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключение роутеров
dp.include_routers(
    start.router,
    menu.router,
    profile.router,
    work.router,
    bank.router,
    business.router,
    casino.router,
    shop.router,
    settings.router,
    donate.router,
    taxi.router,
    trading.router,
    invest.router,
    achievements.router,
    admin.router
)

async def start_bot():
    print("🚀 Бот запускается через FastAPI...")

    # Инициализация БД
    await db.connect()
    await db.create_tables()
    logging.info("Database connected and tables checked.")

    # Запуск фоновых задач (экономика, рынок)
    await start_loops(bot)

    # Запуск поллинга
    try:
        # drop_pending_updates=True пропускает старые сообщения, чтобы бот не отвечал на них при перезапуске
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()
        logging.info("Bot stopped.")
