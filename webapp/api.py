from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import hmac
import hashlib
import logging
import os
from urllib.parse import parse_qsl
from config import BOT_TOKEN
from database import db
from services.economy import update_money, get_user
from services.market import buy_asset, sell_asset, sell_all_assets

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class TradeRequest(BaseModel):
    action: str
    symbol: str
    amount: float

# --- Auth ---
def validate_init_data(init_data: str, bot_token: str):
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

async def get_current_user(request: Request):
    # --- ТЕСТОВЫЙ РЕЖИМ (ЗАГЛУШКА) ---
    # return {"id": 1750230081, "first_name": "Admin", "username": "admin"}
    # ---------------------------------

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise HTTPException(status_code=401, detail="No auth header")

    is_valid, user_data = validate_init_data(auth_header, BOT_TOKEN)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid initData")

    return user_data

# --- Routes ---

@app.get("/")
async def index():
    return FileResponse('webapp/public/index.html')

@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_id = user['id']
    db_user = await get_user(user_id)

    if not db_user:
        # Фолбэк для новых юзеров
        return {
            "id": user_id,
            "name": user.get('first_name', 'Guest'),
            "username": user.get('username', ''),
            "tag": 0,
            "balance": 0,
            "donate": 0,
            "net_worth": 0,
            "portfolio": []
        }

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

    return {
        "id": db_user['user_id'],
        "name": f"{db_user['first_name']} {db_user['last_name']}",
        "username": db_user['username'],
        "tag": db_user['tag'],
        "balance": db_user['money'],
        "donate": db_user['donate'],
        "net_worth": db_user['money'] + total_assets_value,
        "portfolio": clean_portfolio
    }

@app.get("/api/market")
async def get_market(user: dict = Depends(get_current_user)):
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
    return result

@app.get("/api/trades")
async def get_trades(user: dict = Depends(get_current_user)):
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
    return result

@app.get("/api/top")
async def get_top_traders(user: dict = Depends(get_current_user)):
    top_users = await db.fetchall("SELECT first_name, last_name, money FROM users ORDER BY money DESC LIMIT 5")
    result = []
    for u in top_users:
        result.append({
            "name": f"{u['first_name']} {u['last_name']}",
            "money": u['money']
        })
    return result

@app.post("/api/trade")
async def trade(req: TradeRequest, user: dict = Depends(get_current_user)):
    user_id = user['id']

    if req.amount <= 0:
        return JSONResponse({"error": "Сумма должна быть больше 0"}, status_code=400)

    print(f"[WEBAPP] User {user_id} trade: {req.action.upper()} {req.amount} {req.symbol}")

    if req.action == 'buy':
        user_money_row = await db.fetchone("SELECT money FROM users WHERE user_id = ?", (user_id,))
        if not user_money_row: return JSONResponse({"error": "User not found"}, status_code=404)

        if user_money_row['money'] < req.amount:
            return JSONResponse({"error": f"Недостаточно средств! Баланс: ${user_money_row['money']}"}, status_code=400)

        success, msg = await buy_asset(user_id, req.symbol, req.amount)
        if success:
            await update_money(user_id, -int(req.amount))
            return {"status": "ok", "message": msg}
        else:
            return JSONResponse({"error": msg}, status_code=400)

    elif req.action == 'sell':
        success, val = await sell_asset(user_id, req.symbol, req.amount)
        if success:
            await update_money(user_id, int(val))
            msg = f"Продано за ${val:.2f}"
            return {"status": "ok", "message": msg}
        else:
            return JSONResponse({"error": val}, status_code=400)

    return JSONResponse({"error": "Invalid action"}, status_code=400)

@app.post("/api/sell_all")
async def trade_sell_all(user: dict = Depends(get_current_user)):
    user_id = user['id']
    success, total = await sell_all_assets(user_id)

    if success:
        await update_money(user_id, int(total))
        return {"status": "ok", "message": f"Продано всё за ${total:.2f}"}
    else:
        return JSONResponse({"error": total}, status_code=400)

# --- Запуск (для локального теста через python main.py) ---
async def start_web_server():
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
