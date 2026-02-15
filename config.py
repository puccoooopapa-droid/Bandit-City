import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # Замените на свой токен или используйте .env

# Исправленная логика получения ID админов
admin_ids_str = os.getenv("ADMIN_IDS", "1750230081")
if "," in admin_ids_str:
    ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]
else:
    if admin_ids_str.strip():
        ADMIN_IDS = [int(admin_ids_str.strip())]
    else:
        ADMIN_IDS = []

ADMIN_PASSWORD = "7777" # ИЗМЕНЕНИЕ: Пароль изменен

DB_NAME = "bot_bandit.db"

# Настройки времени (в секундах)
GAME_DAY_SECONDS = 1200 # 20 минут реального времени = 1 игровой день (для кредитов)
JAIL_TIME_SHORT = 300   # 5 минут
JAIL_TIME_LONG = 3600   # 1 час
BUSINESS_TICK_INTERVAL = 60 # 1 минута

# Настройки доната
VIP_DURATION = 30 * 24 * 3600 # 30 дней в секундах

# Настройки экономики
START_MONEY = 1000
START_DONATE = 0
TRANSFER_COMMISSION = 0.03
