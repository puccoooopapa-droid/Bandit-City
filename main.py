import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import db
from handlers import start, menu, profile, work, bank, business, casino, admin, shop, settings, donate, taxi, trading, invest, achievements
from services.scheduler import start_loops
from webapp.api import start_web_server

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    print("🚀 Бот запускается...")

    # Инициализация БД
    await db.connect()
    await db.create_tables()
    logging.info("Database connected and tables checked.")

    # Инициализация бота
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

    # Запуск фоновых задач (экономика, рынок)
    await start_loops(bot)

    # Запуск бота и веб-сервера параллельно
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            start_web_server()
        )
    finally:
        await bot.session.close()
        await db.close()
        logging.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
