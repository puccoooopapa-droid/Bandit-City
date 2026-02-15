import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import db
from services.scheduler import start_loops
from webapp.api import start_web_server # ИЗМЕНЕНИЕ: Импорт веб-сервера

# Импорт роутеров
from handlers import start, menu, profile, work, bank, business, casino, admin, shop, settings, donate, taxi, trading, invest, achievements

async def main():
    # Настройка логгера
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger("aiogram").setLevel(logging.WARNING)

    print("🚀 Бот запускается...")
    logging.info("Bot started.")

    # Инициализация БД
    await db.connect()
    await db.create_tables()
    logging.info("Database connected and tables checked.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Запуск фоновых задач
    await start_loops(bot)
    logging.info("Economy loops initialized.")

    # Запуск WebApp сервера
    await start_web_server() # ИЗМЕНЕНИЕ: Запуск сервера

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(profile.router)
    dp.include_router(work.router)
    dp.include_router(bank.router)
    dp.include_router(business.router)
    dp.include_router(casino.router)
    dp.include_router(admin.router)
    dp.include_router(shop.router)
    dp.include_router(settings.router)
    dp.include_router(donate.router)
    dp.include_router(taxi.router)
    dp.include_router(trading.router)
    dp.include_router(invest.router)
    dp.include_router(achievements.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close()
        logging.info("Bot stopped.")
        print("🛑 Бот остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
