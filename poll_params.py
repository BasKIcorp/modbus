import json
import os
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Blueprint
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

poll_params = Blueprint('poll_params', __name__)

# Подгружаем настройки из файла
with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)


# Создание логгера
def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


poll_logger = create_logger("poll_params_logger", "modbusRESTAPI/poll_params.log")


# В случае ошибки записываем в логгер
def log_error(code, message):
    poll_logger.error(f'Ошибка {code}: {message}')


# Создание базы данных
DB_FILE = 'modbusRESTAPI/params.db'


# Создание таблицы базы данных
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS static_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            param_name TEXT NOT NULL,
            type INT NOT NULL,
            value REAL NOT NULL,
            equipment_id INT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


# Функция сохранения данных
def save_to_db(param_name, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO static_params (param_name, type, value, equipment_id) VALUES (?, 1, ?, 1)",
                   (param_name, value))
    conn.commit()
    conn.close()


# Хранение информации о данных для считывания
params_to_read = {"trm202": ["lab13", ["DP", d["lab13"]["trm202"]["first_register"]],
                             ["T", d["lab13"]["trm202"]["second_register"]]],
                  "trm200": ["lab14", ["T1", d["lab14"]["trm200"]["first_register"]],
                             ["T2", d["lab14"]["trm200"]["second_register"]]],
                  "trm210": ["lab14", ["DPy", d["lab14"]["trm210"]["first_register"]],
                             ["Tn", d["lab14"]["trm210"]["second_register"]]]}


async def _read_params():
    devices = list(params_to_read.keys())  # список устройств, с которых получаем данные
    slave_ids = []
    host = d["server_host"]
    port = d["server_port"]
    start_addresses = []
    for device in devices:
        lab_num = params_to_read.get(device)[0]
        slave_ids.append(d[lab_num][device]["slave_id"])
        start_address = []
        for i in range(1, len(params_to_read.get(device))):
            start_address.append(params_to_read.get(device)[i][1])  # получаем адреса регистров, записанные в словаре
        start_addresses.append(start_address)
    count = 2
    answer = []
    client = AsyncModbusTcpClient(host, port=port)
    await client.connect()
    print(start_addresses)
    for i in range(len(devices)):
        for j in range(len(start_addresses[i])):  # получаем номер регистра
            start_address = start_addresses[i][j]
            device = devices[i]
            slave_id = slave_ids[i]
            try:
                data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)
                if not data.isError():
                    value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                    param_name = params_to_read.get(device)[j + 1][0]
                    poll_logger.info(
                        f"Получение параметров, прибор {device}, параметр {param_name}"
                        f"регистр {start_address}, прочитано значение {value_float32}")
                    temp_data = (param_name, value_float32)  # собираем полученные данные в один кортеж
                    answer.append(temp_data)
                else:
                    log_error(502, "Ошибка: {}".format(data))
            except ConnectionException:
                log_error(502, "Нет соединения с устройством")
            except ModbusIOException:
                log_error(502, "Нет ответа от устройства")
            except ParameterException:
                log_error(502, "Неверные параметры соединения")
            except NoSuchSlaveException:
                log_error(502, "Нет устройства с id {}".format(slave_id))
            except NotImplementedException:
                log_error(502, "Нет данной функции")
            except InvalidMessageReceivedException:
                log_error(502, "Неверная контрольная сумма в ответе")
            except MessageRegisterException:
                log_error(502, "Неверный адрес регистра")
    client.close()
    return answer


# Функция запуска по таймеру
async def scheduled_task():
    try:
        data = await _read_params()
        if data is not None:
            print(data)
            for answer in data:
                save_to_db(answer[0], answer[1])
    except Exception as e:
        log_error(500, f"Unexpected error: {str(e)}")


# Функция удаления логов по просшествии n дней
def delete_logs(log_file):
    log_dir = os.path.dirname(log_file)
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)


# Планировщик с двумя задачами: считывание данных и удаление логов
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(scheduled_task()), 'interval', minutes=d["poll_time_minutes"],
                  seconds=d["poll_time_seconds"])
scheduler.add_job(delete_logs, 'interval', days=d["delete_logs_days"], args=["modbusRESTAPI/poll_params.log"])
scheduler.start()
