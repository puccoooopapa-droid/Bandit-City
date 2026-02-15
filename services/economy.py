import time
from database import db
from config import JAIL_TIME_SHORT, JAIL_TIME_LONG, GAME_DAY_SECONDS

async def get_user(user_id):
    return await db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

async def update_money(user_id, amount):
    await db.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, user_id))

async def update_donate(user_id, amount):
    await db.execute("UPDATE users SET donate = donate + ? WHERE user_id = ?", (amount, user_id))

async def check_jail(user_id):
    user = await get_user(user_id)
    if not user:
        return False, "Пользователь не найден"

    if user['jail_until'] > time.time():
        remaining = int(user['jail_until'] - time.time())
        return True, f"🔒 Вы в тюрьме! Осталось {remaining} сек."

    if user['jail_until'] > 0 and user['jail_until'] <= time.time():
         await db.execute("UPDATE users SET jail_until = 0 WHERE user_id = ?", (user_id,))

    return False, None

async def check_credit_status(user_id):
    user = await get_user(user_id)
    if not user or user['credit_amount'] <= 0:
        return

    # Проверка просрочки
    # Логика: credit_start_time + credit_term_days * GAME_DAY_SECONDS
    deadline = user['credit_start_time'] + (user['credit_term_days'] * GAME_DAY_SECONDS)

    if time.time() > deadline:
        # Просрочен
        # Проверяем, был ли уже в тюрьме за этот кредит (можно добавить флаг в БД, но упростим)
        # Если просрочка большая - аннулируем кредит и сажаем надолго

        overdue_time = time.time() - deadline

        if overdue_time > (20 * GAME_DAY_SECONDS): # Если просрочил еще на 20 дней
             # Жесткое наказание
             await db.execute("UPDATE users SET credit_amount = 0, credit_term_days = 0, reputation = reputation - 50, jail_until = ? WHERE user_id = ?",
                              (int(time.time() + JAIL_TIME_LONG), user_id))
        else:
             # Предупредительное наказание (если еще не сидит)
             if user['jail_until'] < time.time():
                 await db.execute("UPDATE users SET jail_until = ? WHERE user_id = ?",
                                  (int(time.time() + JAIL_TIME_SHORT), user_id))

async def add_transaction(user_id, amount, description):
    await db.execute("INSERT INTO transactions (user_id, amount, description, timestamp) VALUES (?, ?, ?, ?)",
                     (user_id, amount, description, int(time.time())))
