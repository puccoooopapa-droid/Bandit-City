from aiogram import Router, types
from aiogram.filters import Command
from database import db
from config import ADMIN_PASSWORD, ADMIN_IDS
from services.economy import update_money, update_donate, get_user
from handlers.shop import SHOP_ITEMS
from handlers.business import BUSINESS_TYPES
from services.scheduler import business_tick
from services.events import trigger_random_event, ALL_EVENTS, current_event
from services.market import start_trend # ИЗМЕНЕНИЕ: Импорт start_trend
import time
import json
import random

router = Router()

# Вспомогательная функция для поиска пользователя по разным идентификаторам
async def find_user_by_identifier(identifier):
    user = None
    if identifier.isdigit():
        user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (int(identifier),))
    elif identifier.startswith("@"):
        username = identifier[1:]
        user = await db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
    elif "#" in identifier:
        try:
            surname, tag = identifier.split("#")
            user = await db.fetchone("SELECT * FROM users WHERE last_name = ? AND tag = ?", (surname, int(tag)))
        except ValueError:
            pass
    return user

@router.message(Command("admin"))
async def admin_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /admin <password> <command> ...")
        return

    password = args[1]
    if password != ADMIN_PASSWORD:
        if message.from_user.id not in ADMIN_IDS:
             await message.answer("Неверный пароль.")
             return

    if len(args) < 3:
        await message.answer("Команды:\nadd_money <id> <amount>\nset_money <id> <amount>\nadd_donate <id> <amount>\njail <id> <seconds>\nreset_user <id>\n/debug_catalog\n/force_tick\n/check_biz <id>\n/reset_market\n/trigger_event [id]\n/pump_dump <symbol> <percent> [seconds]")
        return

    cmd = args[2]

    try:
        if cmd == "force_tick":
            await message.answer("⏳ Запускаю принудительный тик экономики...")
            await business_tick()
            await message.answer("✅ Тик выполнен. Проверьте консоль.")
            return

        if cmd == "reset_market":
            assets = [
                ("BTCX", 50000.0),
                ("ZEN", 150.0),
                ("OIL", 80.0),
                ("TECH", 2500.0),
                ("DARK", 10.0)
            ]
            for symbol, price in assets:
                history = json.dumps([price] * 30)
                await db.execute("UPDATE crypto_assets SET current_price = ?, history = ? WHERE symbol = ?", (price, history, symbol))

            await message.answer("✅ Рынок криптовалют сброшен к начальным значениям.")
            return

        if cmd == "trigger_event":
            event_id = int(args[3]) if len(args) > 3 else None

            if event_id is not None and 0 <= event_id < len(ALL_EVENTS):
                event_data = ALL_EVENTS[event_id]
            else:
                event_data = random.choice(ALL_EVENTS)

            current_event["name"] = event_data["name"]
            current_event["description"] = event_data["description"]
            current_event["effects"] = event_data["effects"]
            current_event["ends_at"] = int(time.time()) + event_data["duration"]

            await message.answer(f"🔥 <b>Событие запущено!</b>\n\n{event_data['name']}\n{event_data['description']}\n\nДлительность: {event_data['duration']//60} мин.", parse_mode="HTML")
            return

        if cmd == "pump_dump":
            if len(args) < 5:
                await message.answer("Использование: /admin <pass> pump_dump <symbol> <percent> [seconds]")
                return

            symbol = args[3].upper()
            percent = float(args[4])
            duration = int(args[5]) if len(args) > 5 else 60 # По умолчанию 60 секунд

            success, target_price = await start_trend(symbol, percent, duration)

            if success:
                arrow = "📈" if percent > 0 else "📉"
                await message.answer(f"{arrow} <b>{symbol}</b>: Запущен тренд на {percent}% за {duration} сек.\nЦель: ${target_price:.2f}", parse_mode="HTML")
            else:
                await message.answer(f"Актив {symbol} не найден.")
            return

        if cmd == "check_biz":
            user_identifier = args[3]
            target_user = await find_user_by_identifier(user_identifier)
            if not target_user:
                await message.answer(f"Пользователь '{user_identifier}' не найден.")
                return

            businesses = await db.fetchall("SELECT * FROM user_businesses WHERE user_id = ?", (target_user['user_id'],))
            if not businesses:
                await message.answer(f"У пользователя {target_user['first_name']} нет бизнесов.")
                return

            response = f"Бизнесы пользователя {target_user['first_name']}:\n\n"
            for biz in businesses:
                response += f"ID: {biz['id']}\n"
                response += f"Тип: {biz['business_type']}\n"
                response += f"Уровень: {biz['level']}\n"
                response += f"Склад: {biz['stock']}/{biz['max_stock']}\n"
                response += f"Касса: ${biz['cash_box']}\n"
                response += f"Менеджер: {'Да' if biz['has_manager'] else 'Нет'}\n"
                response += "-------------------\n"
            await message.answer(response)
            return

        # Команды, требующие идентификатор пользователя
        if cmd in ["add_money", "set_money", "add_donate", "jail", "reset_user"]:
            if len(args) < 4:
                await message.answer(f"Недостаточно аргументов для {cmd}.")
                return

            user_identifier = args[3]
            target_user = await find_user_by_identifier(user_identifier)

            if not target_user:
                await message.answer(f"Пользователь '{user_identifier}' не найден.")
                return

            target_user_id = target_user['user_id']
            target_user_name = f"{target_user['first_name']} {target_user['last_name']}#{str(target_user['tag']).zfill(4)}"

            if cmd == "add_money":
                amount = int(args[4])
                await update_money(target_user_id, amount)
                await message.answer(f"Выдано ${amount} пользователю {target_user_name}")

            elif cmd == "set_money":
                amount = int(args[4])
                await db.execute("UPDATE users SET money = ? WHERE user_id = ?", (amount, target_user_id))
                await message.answer(f"Установлен баланс ${amount} пользователю {target_user_name}")

            elif cmd == "add_donate":
                amount = int(args[4])
                await update_donate(target_user_id, amount)
                await message.answer(f"Выдано {amount} доната пользователю {target_user_name}")

            elif cmd == "jail":
                seconds = int(args[4])
                await db.execute("UPDATE users SET jail_until = ? WHERE user_id = ?", (int(time.time() + seconds), target_user_id))
                await message.answer(f"Пользователь {target_user_name} посажен на {seconds} сек.")

            elif cmd == "reset_user":
                await db.execute("DELETE FROM users WHERE user_id = ?", (target_user_id,))
                await db.execute("DELETE FROM user_businesses WHERE user_id = ?", (target_user_id,))
                await db.execute("DELETE FROM owned_items WHERE user_id = ?", (target_user_id,))
                await db.execute("DELETE FROM transactions WHERE user_id = ?", (target_user_id,))
                await db.execute("DELETE FROM taxi_orders WHERE passenger_id = ? OR driver_id = ?", (target_user_id, target_user_id))
                await message.answer(f"Пользователь {target_user_name} сброшен.")

        elif cmd == "debug_catalog":
            debug_text = "--- DEBUG CATALOG ---\n\n"
            debug_text += "SHOP ITEMS:\n"
            for cat_key, cat_data in SHOP_ITEMS.items():
                debug_text += f"  Category: {cat_key}\n"
                for item in cat_data['items']:
                    debug_text += f"    - {item['id']}\n"

            debug_text += "\nBUSINESSES:\n"
            for biz_key in BUSINESS_TYPES.keys():
                debug_text += f"  - {biz_key}\n"

            print(debug_text)
            await message.answer("Вывел каталоги в консоль.")

        else:
            await message.answer("Неизвестная команда.")

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
