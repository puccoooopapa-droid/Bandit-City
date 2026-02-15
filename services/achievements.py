from database import db
import time
import logging

logger = logging.getLogger(__name__)

ACHIEVEMENTS = {
    "first_million": {"name": "💰 Миллионер", "desc": "Накопить 1 000 000$", "reward_money": 50000, "reward_rep": 10}, # Переименовано
    "biz_owner": {"name": "💼 Бизнесмен", "desc": "Купить первый бизнес", "reward_money": 10000, "reward_rep": 5},
    "taxi_pro": {"name": "🚖 Бомбила", "desc": "Выполнить 50 заказов в такси", "reward_money": 25000, "reward_rep": 15},
    "investor": {"name": "📈 Волк с Уолл-стрит", "desc": "Заработать на трейдинге", "reward_money": 100000, "reward_rep": 20},
    "tycoon": {"name": "🏢 Магнат", "desc": "Владеть 5 бизнесами", "reward_money": 500000, "reward_rep": 50},
    "hacker_god": {"name": "💻 Анонимус", "desc": "Успешно взломать систему 10 раз", "reward_money": 50000, "reward_rep": -10}, # Новое
    "bar_king": {"name": "🍹 Король вечеринок", "desc": "Сделать 20 идеальных коктейлей", "reward_money": 20000, "reward_rep": 10} # Новое
}

async def check_achievement(user_id, key):
    exists = await db.fetchone("SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_key = ?", (user_id, key))
    if exists: return False

    ach = ACHIEVEMENTS.get(key)
    if not ach: return False

    await db.execute("INSERT INTO user_achievements (user_id, achievement_key, unlocked_at) VALUES (?, ?, ?)",
                     (user_id, key, int(time.time())))

    await db.execute("UPDATE users SET money = money + ?, reputation = reputation + ? WHERE user_id = ?",
                     (ach['reward_money'], ach['reward_rep'], user_id))

    return ach

async def check_all_achievements(user_id):
    user = await db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not user: return []

    unlocked = []

    if user['money'] >= 1000000:
        res = await check_achievement(user_id, "first_million")
        if res: unlocked.append(res)

    biz_count = await db.fetchone("SELECT COUNT(*) as cnt FROM user_businesses WHERE user_id = ?", (user_id,))
    if biz_count['cnt'] >= 1:
        res = await check_achievement(user_id, "biz_owner")
        if res: unlocked.append(res)
    if biz_count['cnt'] >= 5:
        res = await check_achievement(user_id, "tycoon")
        if res: unlocked.append(res)

    return unlocked
