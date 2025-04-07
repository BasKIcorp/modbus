import json
import asyncio
import threading
from flask import Flask
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from lab13.lab13 import lab_13
from lab14.lab14 import lab_14
from poll_params import poll_params
from scheduler import configure_scheduler

app = Flask(__name__)
app.register_blueprint(lab_13)
app.register_blueprint(lab_14)
app.register_blueprint(poll_params)

# Подгружаем настройки из файла
with open('config.json') as f:
    d = json.load(f)

# Создаем асинхронный планировщик
scheduler = AsyncIOScheduler()

# Настраиваем задачи планировщика
configure_scheduler(scheduler)


# Асинхронная функция для запуска планировщика
async def run_scheduler():
    scheduler.start()
    print(f"Планировщик запущен с интервалом {d['poll_time_minutes']} минут и {d['poll_time_seconds']} секунд")
    try:
        # Держим цикл событий активным
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


# Функция для запуска асинхронного цикла в отдельном потоке
def start_scheduler_in_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_scheduler())


# Запускаем планировщик в фоновом потоке при старте приложения
def start_app():
    # Создаем новый цикл событий для планировщика
    scheduler_loop = asyncio.new_event_loop()
    scheduler_thread = threading.Thread(target=start_scheduler_in_thread, args=(scheduler_loop,), daemon=True)
    scheduler_thread.start()

    # Запускаем Flask
    app.run(debug=False, port=d["port"])


if __name__ == "__main__":
    start_app()
