from aiohttp import web
import aiohttp_cors
import json
import hmac
import hashlib
import logging
import os # Добавили импорт os
from urllib.parse import parse_qsl
from config import BOT_TOKEN
from database import db
from services.economy import update_money, get_user
from services.market import buy_asset, sell_asset, sell_all_assets

logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

# --- Auth ---
def validate_init_data(init_data, bot_token):
    try:
        parsed_data = dict(parse_qsl(init_data))
        if 'hash' not in parsed_data: return False, None
        hash_ = parsed_data.pop('hash')
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if calculated_hash == hash_:
            return True, json.loads(parsed_data['user'])
        return False, None
    except: return False, None

@web.middleware
async def auth_middleware(request, handler):
    if request.path == '/' or request.path.startswith('/static'): return await handler(request)
    if request.method == 'OPTIONS': return await handler(request)

    # --- ТЕСТОВЫЙ РЕЖИМ (ЗАГЛУШКА) ---
    # В ПРОДАКШЕНЕ ЛУЧШЕ УБРАТЬ ИЛИ ОСТАВИТЬ КАК ФОЛЛБЭК
    # request['user'] = {"id": 1750230081, "first_name": "Admin", "username": "admin"}
    # return await handler(request)

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        # Фолбэк для тестов, если нет заголовка (можно убрать на проде)
        request['user'] = {"id": 1750230081, "first_name": "Admin", "username": "admin"}
        return await handler(request)
        # return web.json_response({"error": "No auth"}, status=401)

    is_valid, user_data = validate_init_data(auth_header, BOT_TOKEN)
    if not is_valid:
        # Фолбэк для тестов
        request['user'] = {"id": 1750230081, "first_name": "Admin", "username": "admin"}
        return await handler(request)
        # return web.json_response({"error": "Invalid initData"}, status=403)

    request['user'] = user_data
    return await handler(request)

# --- API ---
async def index(request):
    return web.FileResponse('webapp/public/index.html')

async def get_me(request):
    user_id = request['user']['id']
    user = await get_user(user_id)

    # Если юзера нет (например, зашел с другого акка), создаем заглушку
    if not user:
        return web.json_response({
            "id": user_id,
            "name": "Гость",
            "username": "guest",
            "tag": 0,
            "balance": 0,
            "donate": 0,
            "net_worth": 0,
            "portfolio": []
        })

    portfolio = await db.fetchall("SELECT * FROM user_portfolio WHERE user_id = ?", (user_id,))

    market_assets = await db.fetchall("SELECT symbol, current_price FROM crypto_assets")
    prices = {a['symbol']: a['current_price'] for a in market_assets}

    clean_portfolio = []
    total_assets_value = 0

    for p in portfolio:
        price = prices.get(p['symbol'], 0)
        val = p['amount'] * price
        total_assets_value += val
        clean_portfolio.append({
            "symbol": p['symbol'],
            "amount": p['amount'],
            "price": price,
            "value": val,
            "avg_price": p['average_buy_price']
        })

    return web.json_response({
        "id": user['user_id'],
        "name": f"{user['first_name']} {user['last_name']}",
        "username": user['username'],
        "tag": user['tag'],
        "balance": user['money'],
        "donate": user['donate'],
        "net_worth": user['money'] + total_assets_value,
        "portfolio": clean_portfolio
    })

async def get_market(request):
    assets = await db.fetchall("SELECT * FROM crypto_assets")
    result = []
    for asset in assets:
        history = json.loads(asset['history'])
        change = ((asset['current_price'] - history[0]) / history[0]) * 100 if history else 0
        result.append({
            "symbol": asset['symbol'],
            "name": asset['name'],
            "price": asset['current_price'],
            "change": change,
            "history": history[-100:]
        })
    return web.json_response(result)

async def get_trades(request):
    trades = await db.fetchall("SELECT * FROM trades_history ORDER BY timestamp DESC LIMIT 10")
    result = []
    for t in trades:
        result.append({
            "username": t['username'] or f"User#{t['user_id']}",
            "type": t['type'],
            "symbol": t['symbol'],
            "amount": t['amount'],
            "price": t['price'],
            "time": t['timestamp']
        })
    return web.json_response(result)

async def get_top_traders(request):
    top_users = await db.fetchall("SELECT first_name, last_name, money FROM users ORDER BY money DESC LIMIT 5")
    result = []
    for u in top_users:
        result.append({
            "name": f"{u['first_name']} {u['last_name']}",
            "money": u['money']
        })
    return web.json_response(result)

async def trade(request):
    user_id = request['user']['id']
    try:
        data = await request.json()
        action = data.get('action')
        symbol = data.get('symbol')
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return web.json_response({"error": "Некорректная сумма"}, status=400)

    if amount <= 0:
        return web.json_response({"error": "Сумма должна быть больше 0"}, status=400)

    if action == 'buy':
        user_money_row = await db.fetchone("SELECT money FROM users WHERE user_id = ?", (user_id,))
        if not user_money_row: return web.json_response({"error": "User not found"}, status=404)

        if user_money_row['money'] < amount:
            return web.json_response({"error": f"Недостаточно средств! Баланс: ${user_money_row['money']}"}, status=400)

        success, msg = await buy_asset(user_id, symbol, amount)
        if success:
            await update_money(user_id, -int(amount))
            return web.json_response({"status": "ok", "message": msg})
        else:
            return web.json_response({"error": msg}, status=400)

    elif action == 'sell':
        success, val = await sell_asset(user_id, symbol, amount)
        if success:
            await update_money(user_id, int(val))
            msg = f"Продано за ${val:.2f}"
            return web.json_response({"status": "ok", "message": msg})
        else:
            return web.json_response({"error": val}, status=400)

    return web.json_response({"error": "Invalid action"}, status=400)

async def trade_sell_all(request):
    user_id = request['user']['id']
    success, total = await sell_all_assets(user_id)

    if success:
        await update_money(user_id, int(total))
        return web.json_response({"status": "ok", "message": f"Продано всё за ${total:.2f}"})
    else:
        return web.json_response({"error": total}, status=400)

# --- Run ---
async def start_web_server():
    app = web.Application(middlewares=[auth_middleware])
    cors = aiohttp_cors.setup(app, defaults={"*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")})

    app.router.add_get('/', index)
    app.router.add_get('/api/me', get_me)
    app.router.add_get('/api/market', get_market)
    app.router.add_get('/api/trades', get_trades)
    app.router.add_get('/api/top', get_top_traders)
    app.router.add_post('/api/trade', trade)
    app.router.add_post('/api/sell_all', trade_sell_all)

    for route in list(app.router.routes()): cors.add(route)

    runner = web.AppRunner(app)
    await runner.setup()

    # ИЗМЕНЕНИЕ: Получаем порт от Render или используем 8080 локально
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)

    await site.start()
    print(f"--- 🌐 WebApp Server started on http://0.0.0.0:{port} ---")
