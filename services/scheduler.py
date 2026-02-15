import asyncio
from database import db
from services.economy import update_money
from config import BUSINESS_TICK_INTERVAL
from handlers.business import BUSINESS_TYPES
from services.events import trigger_random_event
from services.market import update_market_prices
import logging
import time

logger = logging.getLogger(__name__)

# --- Логика Бизнеса ---
async def business_tick():
    try:
        businesses = await db.fetchall("SELECT * FROM user_businesses")
        if not businesses:
            return

        vip_cache = {}

        for biz in businesses:
            try:
                biz_key = biz['business_type']
                info = BUSINESS_TYPES.get(biz_key)

                if not info:
                    continue

                # --- 1. Проверка склада ---
                if biz['stock'] > 0:
                    user_id = biz['user_id']
                    if user_id not in vip_cache:
                        user = await db.fetchone("SELECT vip_until FROM users WHERE user_id = ?", (user_id,))
                        vip_cache[user_id] = user and user['vip_until'] > time.time()

                    is_vip = vip_cache[user_id]

                    base_income = info['income'] * biz['level']
                    income = base_income

                    if is_vip:
                        income *= 2

                    from services.events import current_event
                    event_mult = current_event["effects"].get("income_multiplier", 1.0)
                    income = int(income * event_mult)

                    # --- 2. Начисление в кассу и списание со склада ---
                    await db.execute("UPDATE user_businesses SET stock = stock - 1, cash_box = cash_box + ? WHERE id = ?", (income, biz['id']))

                    # print(f"✅ Biz #{biz['id']} ({info['name']}): +${income}")

                # --- 3. Логика менеджера (если склад пуст) ---
                else:
                    if biz['has_manager'] == 1:
                        restock_cost = int(info['stock_cost'] * 1.2)
                        user_money_row = await db.fetchone("SELECT money FROM users WHERE user_id = ?", (biz['user_id'],))

                        if user_money_row and user_money_row['money'] >= restock_cost:
                            await update_money(biz['user_id'], -restock_cost)
                            await db.execute("UPDATE user_businesses SET stock = stock + 1 WHERE id = ?", (biz['id'],))
                            # print(f"👔 Manager restocked Biz #{biz['id']}.")

            except Exception as e:
                print(f"❌ Error processing biz #{biz['id']}: {e}")

    except Exception as e:
        print(f"❌ CRITICAL BUSINESS LOOP ERROR: {e}")

# --- Логика Энергии ---
async def energy_tick():
    try:
        await db.execute("UPDATE users SET energy = MIN(energy + 1, max_energy) WHERE energy < max_energy")
    except Exception as e:
        print(f"❌ CRITICAL ENERGY LOOP ERROR: {e}")

# --- Циклы ---

async def business_loop():
    print("--- 🔄 Business Loop Started (60s) ---")
    while True:
        await asyncio.sleep(60)
        await business_tick()

async def energy_loop():
    print("--- ⚡ Energy Loop Started (5s) ---")
    while True:
        await asyncio.sleep(5)
        await energy_tick()

async def market_loop():
    print("--- 📈 Market Loop Started (1s) ---") # ИЗМЕНЕНИЕ: 1 секунда
    while True:
        await asyncio.sleep(1)
        await update_market_prices()

async def event_loop(bot):
    print("--- 🎉 Event Loop Started (10m) ---")
    while True:
        await asyncio.sleep(600)
        await trigger_random_event(bot)

# --- Запуск ---
async def start_loops(bot):
    asyncio.create_task(energy_loop())
    asyncio.create_task(business_loop())
    asyncio.create_task(market_loop())
    asyncio.create_task(event_loop(bot))
    print("--- ✅ All background loops started. ---")
