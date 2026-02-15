import random
import time
import logging

logger = logging.getLogger(__name__)

# Глобальное состояние текущего события
current_event = {
    "name": "Спокойствие",
    "description": "В городе все спокойно.",
    "effects": {},
    "ends_at": 0
}

# Список возможных событий
ALL_EVENTS = [
    {
        "name": "📈 Экономический бум",
        "description": "Инвесторы вкладывают деньги в город! Доход от всех бизнесов и работ временно увеличен на 30%.",
        "effects": {"income_multiplier": 1.3},
        "duration": 10 * 60 # 10 минут
    },
    {
        "name": "🚔 Полицейский рейд",
        "description": "Полиция проводит облавы! Доход от всех работ и бизнесов временно снижен на 20% из-за проверок.",
        "effects": {"income_multiplier": 0.8},
        "duration": 15 * 60 # 15 минут
    },
    {
        "name": "🎉 Городской праздник",
        "description": "В городе праздник! Все в хорошем настроении, шанс получить чаевые в такси увеличен.",
        "effects": {"taxi_tip_chance_multiplier": 2.0},
        "duration": 20 * 60 # 20 минут
    }
]

async def trigger_random_event(bot):
    global current_event

    # Проверяем, не закончилось ли текущее событие
    if time.time() > current_event.get("ends_at", 0):
        if current_event["name"] != "Спокойствие":
            logger.info(f"[EVENT] Событие '{current_event['name']}' закончилось.")
            current_event = {
                "name": "Спокойствие",
                "description": "В городе все спокойно.",
                "effects": {},
                "ends_at": 0
            }
            # Можно отправить сообщение всем пользователям, но это сложно и может привести к спаму.
            # Лучше, чтобы они видели эффект при работе.

    # Шанс запустить новое событие, если сейчас спокойно
    if current_event["name"] == "Спокойствие":
        if random.randint(1, 3) == 1: # 33% шанс на событие каждые 10 минут
            event_data = random.choice(ALL_EVENTS)
            current_event = {
                "name": event_data["name"],
                "description": event_data["description"],
                "effects": event_data["effects"],
                "ends_at": int(time.time()) + event_data["duration"]
            }
            logger.info(f"[EVENT] Началось новое событие: {current_event['name']} на {event_data['duration']/60} минут.")
            # Здесь можно было бы сделать рассылку, но пока ограничимся логом
            # await broadcast(bot, f"📢 <b>Внимание!</b>\n{current_event['description']}")

# async def broadcast(bot, text):
#     # Функция для рассылки (требует получения всех user_id из БД)
#     # Пока не используется, чтобы не усложнять
#     pass
