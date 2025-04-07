import json
import os
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from flask import Blueprint
from locks import device_locks
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException

poll_params = Blueprint('poll_params', __name__)

# Подгружаем настройки из файла
with open('config.json') as f:
    d = json.load(f)


# Создание логгера
def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


poll_logger = create_logger("poll_params_logger", "poll_params.log")


# В случае ошибки записываем в логгер
def log_error(code, message):
    poll_logger.error(f'Ошибка {code}: {message}')


# Создание базы данных
DB_FILE = 'params.db'
UNITS_DB_FILE = 'units.db'


# Создание таблицы базы данных
def init_params_db():
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


# Создание таблицы units.db
def init_units_db():
    conn = sqlite3.connect(UNITS_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS units (
            unit_id INTEGER PRIMARY KEY,
            availability BOOLEAN NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO units (unit_id, availability) VALUES (13, 0)")
    cursor.execute("INSERT OR IGNORE INTO units (unit_id, availability) VALUES (14, 0)")
    conn.commit()
    conn.close()


# Обновление статуса доступности в units.db
def update_unit_availability(unit_id, availability):
    conn = sqlite3.connect(UNITS_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE units SET availability = ? WHERE unit_id = ?", (availability, unit_id))
    conn.commit()
    conn.close()


init_params_db()
init_units_db()


# Функция сохранения данных
def save_to_db(param_name, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""SELECT COUNT(*) FROM static_params WHERE param_name = ?""", (param_name,))
    exists = cursor.fetchone()[0] > 0
    if exists:
        cursor.execute("""UPDATE static_params SET value = ? WHERE param_name = ?""", (value, param_name))
    else:
        lab = 14
        if param_name == "T" or param_name == "P":
            lab = 13
        cursor.execute("""INSERT INTO static_params (param_name, type, value, equipment_id) VALUES (?, 1, ?, ?)""",
                       (param_name, value, lab))
    conn.commit()
    conn.close()


# Хранение информации о данных для считывания
params_to_read = {
    "trm202": ["lab13", ["T", d["lab13"]["trm202"]["first_register"]]],
    "pressure_sensor": ["lab13", ["P", d["lab13"]["pressure_sensor"]["first_register"]]],
    "trm200": ["lab14", ["T1", d["lab14"]["trm200"]["first_register"]],
               ["T2", d["lab14"]["trm200"]["second_register"]]],
    "sensor": ["lab14", ["DP", d["lab14"]["sensor"]["first_register"]]]
}

# Глобальное состояние доступности устройств
device_status = {
    "trm202": False,
    "pressure_sensor": False,
    "trm200": False,
    "sensor": False
}


async def _read_params():
    devices = list(params_to_read.keys())
    host = d["server_host"]
    port = d["server_port"]
    answer = []

    # Временное состояние для текущего опроса
    current_device_status = {device: False for device in devices}

    for device in devices:
        lab_num = params_to_read.get(device)[0]
        slave_id = d[lab_num][device]["slave_id"]
        start_addresses = [params_to_read.get(device)[i][1] for i in range(1, len(params_to_read.get(device)))]

        client = None
        device_success = False
        async with device_locks[device]:
            try:
                client = AsyncModbusTcpClient(host, port=port)
                # Устанавливаем таймаут подключения, например, 0.3 секунды
                await asyncio.wait_for(client.connect(), timeout=0.3)

                for j, start_address in enumerate(start_addresses):
                    try:
                        count = 1
                        if device == "trm200" or device == "pressure_sensor":
                            count = 2 if j == 0 else 1

                        print(f"Запрос на {device} отправлен, адрес: {start_address}, count: {count}")
                        # Устанавливаем таймаут для чтения данных, например, 0.2 секунды
                        if device == "sensor":
                            data = await asyncio.wait_for(
                                client.read_input_registers(address=start_address, count=count, slave=slave_id),
                                timeout=0.2
                            )
                        else:
                            data = await asyncio.wait_for(
                                client.read_holding_registers(address=start_address, count=count, slave=slave_id),
                                timeout=0.2
                            )

                        if not data.isError():
                            if device == "trm202" or device == "trm200":
                                value = data.registers[0] / 10
                            elif device == "sensor":
                                value = data.registers[0]
                            else:
                                value = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                                value = round(value, 1)

                            param_name = params_to_read.get(device)[j + 1][0]
                            poll_logger.info(
                                f"Получение параметров, прибор {device}, параметр {param_name}, "
                                f"регистр {start_address}, прочитано значение {value}"
                            )

                            temp_data = (param_name, value)
                            answer.append(temp_data)
                            device_success = True

                            # Проверка давления
                            if param_name == "P" and value > 2000:
                                print("насос выключить!")
                                await client.write_registers(address=8, values=[1], slave=16)
                                await client.write_registers(address=10, values=[0], slave=16)
                                await asyncio.sleep(1)
                                await client.write_registers(address=10, values=[1000], slave=16)
                                await client.write_registers(address=9, values=[0], slave=16)
                                print("насос экстренно вырублен")

                    except asyncio.TimeoutError:
                        param_name = params_to_read.get(device)[j + 1][0]
                        poll_logger.error(
                            f"Таймаут чтения: прибор {device}, параметр {param_name}, регистр {start_address}"
                        )
                        continue
                    except Exception as e:
                        param_name = params_to_read.get(device)[j + 1][0]
                        poll_logger.error(
                            f"Ошибка чтения: прибор {device}, параметр {param_name}, "
                            f"регистр {start_address}: {str(e)}"
                        )
                        continue

                if device_success:
                    current_device_status[device] = True

            except asyncio.TimeoutError:
                log_error(502, f"Таймаут подключения к {device}")
                current_device_status[device] = False
            except ConnectionException:
                log_error(502, f"Ошибка подключения к {device}")
                current_device_status[device] = False
            except Exception as e:
                log_error(502, f"Ошибка Modbus для {device}: {str(e)}")
                current_device_status[device] = False
            finally:
                if client and client.connected:
                    client.close()

            if not device_success:
                print(f"Ошибка получения данных с устройства {device}")
                log_error(500, f"Не удалось получить данные с устройства {device}")

    # Обновляем глобальный статус
    for device in devices:
        if current_device_status[device]:
            device_status[device] = True
        elif not any(device in [x[0] for x in answer] for x in answer):
            device_status[device] = False

    # Определяем доступность для lab13 и lab14
    lab13_devices = [dev for dev in devices if params_to_read[dev][0] == "lab13"]
    lab14_devices = [dev for dev in devices if params_to_read[dev][0] == "lab14"]

    lab13_availability = any(device_status[dev] for dev in lab13_devices)
    lab14_availability = any(device_status[dev] for dev in lab14_devices)

    update_unit_availability(13, lab13_availability)
    update_unit_availability(14, lab14_availability)

    print(f"Текущий статус устройств: {device_status}")
    print(f"Доступность lab13: {lab13_availability}, lab14: {lab14_availability}")

    # await asyncio.sleep(0.2)
    return answer if answer else None


async def scheduled_task():
    try:
        data = await _read_params()
        if data:
            print(data)
            for answer in data:
                save_to_db(answer[0], answer[1])
        else:
            print("Нет данных для сохранения")
    except Exception as e:
        log_error(500, f"Ошибка в scheduled_task: {str(e)}")


# Функция удаления логов
def delete_logs():
    log_file = "poll_params.log"
    log_dir = os.path.dirname(log_file)
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)