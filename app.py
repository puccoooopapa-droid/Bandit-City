from webapp.api import app
import asyncio
import main

@app.on_event("startup")
async def startup_event():
    # Запускаем бота в фоновой задаче при старте сервера
    asyncio.create_task(main.start_bot())
