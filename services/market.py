import random
import json
import asyncio
from database import db
import logging
import time

logger = logging.getLogger(__name__)

PLAYER_IMPACT_FACTOR = 0.00001

# Глобальный словарь для хранения активных трендов
# { "BTCX": { "target": 100000, "step": 100, "active": True } }
active_trends = {}

async def update_market_prices():
    assets = await db.fetchall("SELECT * FROM crypto_assets")

    for asset in assets:
        symbol = asset['symbol']
        current_price = asset['current_price']
        volatility = asset['volatility']

        try:
            history = json.loads(asset['history'])
        except:
            history = []

        # --- ЛОГИКА ТРЕНДА (PUMP/DUMP) ---
        trend = active_trends.get(symbol)

        if trend and trend['active']:
            # Двигаемся к цели
            diff = trend['target'] - current_price

            # Если почти пришли (разница меньше шага), завершаем тренд
            if abs(diff) < abs(trend['step']):
                new_price = trend['target']
                trend['active'] = False # Стоп
            else:
                new_price = current_price + trend['step']

                # Добавляем немного шума, чтобы линия не была идеально прямой
                noise = random.uniform(-0.002, 0.002) * current_price
                new_price += noise
        else:
            # --- ОБЫЧНАЯ ВОЛАТИЛЬНОСТЬ ---
            change_percent = 0

            if volatility == "high":
                change_percent = random.uniform(-0.005, 0.005)
            elif volatility == "medium":
                change_percent = random.uniform(-0.002, 0.002)
            elif volatility == "low":
                change_percent = random.uniform(-0.0005, 0.0005)
            elif volatility == "extreme":
                change_percent = random.uniform(-0.015, 0.015)
            elif volatility == "events":
                change_percent = random.uniform(-0.003, 0.003)

            if random.random() < 0.01:
                if random.random() < 0.5:
                    change_percent += random.uniform(0.02, 0.05)
                else:
                    change_percent -= random.uniform(0.02, 0.05)

            new_price = current_price * (1 + change_percent)

        if new_price < 0.01: new_price = 0.01

        history.append(new_price)
        if len(history) > 200:
            history.pop(0)

        await db.execute("UPDATE crypto_assets SET current_price = ?, history = ? WHERE symbol = ?",
                         (new_price, json.dumps(history), symbol))

async def get_market_data():
    return await db.fetchall("SELECT * FROM crypto_assets")

# Функция для запуска плавного тренда
async def start_trend(symbol, percent, duration_seconds=60):
    asset = await db.fetchone("SELECT current_price FROM crypto_assets WHERE symbol = ?", (symbol,))
    if not asset: return False

    current_price = asset['current_price']
    target_price = current_price * (1 + percent / 100)

    # Вычисляем шаг изменения за один тик (5 сек)
    ticks = duration_seconds / 5
    if ticks < 1: ticks = 1

    total_diff = target_price - current_price
    step = total_diff / ticks

    active_trends[symbol] = {
        "target": target_price,
        "step": step,
        "active": True
    }
    return True, target_price

async def impact_price(symbol, amount_usd, is_buy):
    asset = await db.fetchone("SELECT * FROM crypto_assets WHERE symbol = ?", (symbol,))
    if not asset: return

    current_price = asset['current_price']
    history = json.loads(asset['history'])

    impact = (amount_usd * PLAYER_IMPACT_FACTOR) / (current_price ** 0.5)
    impact = min(impact, 0.05)

    if is_buy:
        new_price = current_price * (1 + impact)
    else:
        new_price = current_price * (1 - impact)

    if new_price < 0.01: new_price = 0.01

    history.append(new_price)
    if len(history) > 200: history.pop(0)

    await db.execute("UPDATE crypto_assets SET current_price = ?, history = ? WHERE symbol = ?",
                     (new_price, json.dumps(history), symbol))

async def buy_asset(user_id, symbol, amount_usd):
    asset = await db.fetchone("SELECT * FROM crypto_assets WHERE symbol = ?", (symbol,))
    if not asset: return False, "Актив не найден"

    price = asset['current_price']
    quantity = amount_usd / price

    portfolio = await db.fetchone("SELECT * FROM user_portfolio WHERE user_id = ? AND symbol = ?", (user_id, symbol))

    if portfolio:
        new_amount = portfolio['amount'] + quantity
        total_cost = (portfolio['amount'] * portfolio['average_buy_price']) + amount_usd
        new_avg_price = total_cost / new_amount
        await db.execute("UPDATE user_portfolio SET amount = ?, average_buy_price = ? WHERE user_id = ? AND symbol = ?",
                         (new_amount, new_avg_price, user_id, symbol))
    else:
        await db.execute("INSERT INTO user_portfolio (user_id, symbol, amount, average_buy_price) VALUES (?, ?, ?, ?)",
                         (user_id, symbol, quantity, price))

    await impact_price(symbol, amount_usd, is_buy=True)

    user = await db.fetchone("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = user['username'] if user else f"User#{user_id}"

    await db.execute("INSERT INTO trades_history (user_id, username, symbol, type, amount, price, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (user_id, username, symbol, 'BUY', quantity, price, int(time.time())))

    return True, f"Куплено {quantity:.4f} {symbol}"

async def sell_asset(user_id, symbol, quantity):
    asset = await db.fetchone("SELECT * FROM crypto_assets WHERE symbol = ?", (symbol,))
    portfolio = await db.fetchone("SELECT * FROM user_portfolio WHERE user_id = ? AND symbol = ?", (user_id, symbol))

    if not portfolio or portfolio['amount'] < quantity:
        return False, "Недостаточно активов"

    price = asset['current_price']
    total_usd = quantity * price

    new_amount = portfolio['amount'] - quantity
    if new_amount < 0.000001:
        await db.execute("DELETE FROM user_portfolio WHERE user_id = ? AND symbol = ?", (user_id, symbol))
    else:
        await db.execute("UPDATE user_portfolio SET amount = ? WHERE user_id = ? AND symbol = ?", (new_amount, user_id, symbol))

    await impact_price(symbol, total_usd, is_buy=False)

    user = await db.fetchone("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username = user['username'] if user else f"User#{user_id}"

    await db.execute("INSERT INTO trades_history (user_id, username, symbol, type, amount, price, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (user_id, username, symbol, 'SELL', quantity, price, int(time.time())))

    return True, total_usd

async def sell_all_assets(user_id):
    portfolio = await db.fetchall("SELECT * FROM user_portfolio WHERE user_id = ?", (user_id,))
    if not portfolio:
        return False, "Портфель пуст"

    total_usd = 0
    market_assets = await db.fetchall("SELECT symbol, current_price FROM crypto_assets")
    prices = {a['symbol']: a['current_price'] for a in market_assets}

    for item in portfolio:
        price = prices.get(item['symbol'], 0)
        if price > 0:
            amount_usd = item['amount'] * price
            total_usd += amount_usd
            await impact_price(item['symbol'], amount_usd, is_buy=False)

    await db.execute("DELETE FROM user_portfolio WHERE user_id = ?", (user_id,))

    return True, total_usd
