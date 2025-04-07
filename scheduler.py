import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from lab13.lab13 import delete_logs as delete_logs_lab13
from lab14.lab14 import delete_logs as delete_logs_lab14
from poll_params import scheduled_task, delete_logs as delete_logs_poll

# Подгружаем настройки из файла
with open('config.json') as f:
    d = json.load(f)


# Функция для настройки планировщика
def configure_scheduler(scheduler):
    scheduler.add_job(delete_logs_lab13, 'interval', days=d["delete_logs_days"])
    scheduler.add_job(delete_logs_lab14, 'interval', days=d["delete_logs_days"])
    scheduler.add_job(scheduled_task, 'interval', minutes=d["poll_time_minutes"], seconds=d["poll_time_seconds"])
    scheduler.add_job(delete_logs_poll, 'interval', days=d["delete_logs_days"])
