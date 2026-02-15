import aiosqlite
from config import DB_NAME
import random
import json

class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_name)
        self.conn.row_factory = aiosqlite.Row

    async def close(self):
        await self.conn.close()

    async def execute(self, query, params=()):
        async with self.conn.execute(query, params) as cursor:
            await self.conn.commit()
            return cursor.lastrowid

    async def fetchone(self, query, params=()):
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query, params=()):
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def create_tables(self):
        # --- Пользователи ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                tag INTEGER,
                bio TEXT,
                rating REAL DEFAULT 0,
                age INTEGER,
                gender TEXT,
                district TEXT,
                money INTEGER DEFAULT 0,
                donate INTEGER DEFAULT 0,
                reputation INTEGER DEFAULT 0,
                credit_amount INTEGER DEFAULT 0,
                credit_term_days INTEGER DEFAULT 0,
                credit_start_time INTEGER DEFAULT 0,
                jail_until INTEGER DEFAULT 0,
                vip_until INTEGER DEFAULT 0,
                work_cooldown INTEGER DEFAULT 0,
                work_in_progress INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                max_energy INTEGER DEFAULT 100,
                garage_slots INTEGER DEFAULT 1,
                inventory_slots INTEGER DEFAULT 10,
                casino_insurance_until INTEGER DEFAULT 0,
                reg_date INTEGER
            )
        """)

        # --- Бизнесы ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS user_businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                business_type TEXT,
                level INTEGER DEFAULT 1,
                stock INTEGER DEFAULT 100,
                max_stock INTEGER DEFAULT 100,
                has_manager INTEGER DEFAULT 0,
                cash_box INTEGER DEFAULT 0,
                treasury INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # --- Инвентарь ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS owned_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                item_key TEXT,
                item_name TEXT,
                price INTEGER,
                created_at INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # --- Логи транзакций ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                description TEXT,
                timestamp INTEGER
            )
        """)

        # --- Заказы такси ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS taxi_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER,
                driver_id INTEGER,
                destination TEXT,
                price INTEGER,
                status TEXT,
                created_at INTEGER
            )
        """)

        # --- ТРЕЙДИНГ: Активы ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS crypto_assets (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                current_price REAL,
                history TEXT, -- JSON string
                volatility TEXT -- high, medium, low
            )
        """)

        # --- ТРЕЙДИНГ: Портфель ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolio (
                user_id INTEGER,
                symbol TEXT,
                amount REAL,
                average_buy_price REAL,
                PRIMARY KEY (user_id, symbol)
            )
        """)

        # --- ТРЕЙДИНГ: История сделок ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS trades_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                symbol TEXT,
                type TEXT, -- BUY or SELL
                amount REAL,
                price REAL,
                timestamp INTEGER
            )
        """)

        # --- ИНВЕСТИЦИИ ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                npc_name TEXT,
                invested_amount INTEGER,
                potential_profit_percent REAL,
                risk_level TEXT,
                end_time INTEGER,
                status TEXT -- active, completed, failed
            )
        """)

        # --- ДОСТИЖЕНИЯ ---
        await self.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER,
                achievement_key TEXT,
                unlocked_at INTEGER,
                PRIMARY KEY (user_id, achievement_key)
            )
        """)

        # Инициализация активов
        assets = [
            ("BTCX", "Bitcoin X", 50000.0, "high"),
            ("ZEN", "ZenCoin", 150.0, "medium"),
            ("OIL", "Oil Future", 80.0, "events"),
            ("TECH", "Tech Index", 2500.0, "low"),
            ("DARK", "DarkCoin", 10.0, "extreme"),
            ("DOG", "DogCoin", 0.5, "high"), # Новая
            ("SYM", "Symbiosis", 1200.0, "medium") # Новая
        ]
        for symbol, name, price, vol in assets:
            exists = await self.fetchone("SELECT 1 FROM crypto_assets WHERE symbol = ?", (symbol,))
            if not exists:
                history = json.dumps([price] * 200)
                await self.execute("INSERT INTO crypto_assets (symbol, name, current_price, history, volatility) VALUES (?, ?, ?, ?, ?)",
                                   (symbol, name, price, history, vol))

db = Database(DB_NAME)
