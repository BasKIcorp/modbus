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

    # Проверяем, существует ли запись
    cursor.execute("""SELECT COUNT(*) FROM static_params WHERE param_name = ?""", (param_name, ))
    exists = cursor.fetchone()[0] > 0

    if exists:
        # Обновляем существующую запись
        cursor.execute("""UPDATE static_params SET value = ? WHERE param_name = ?""", (value, param_name))
    else:
        lab = 14
        if param_name == "T" or param_name == "P":
            lab = 13
        # Создаем новую запись
        cursor.execute("""INSERT INTO static_params (param_name, type, value, equipment_id) VALUES (?, 1, ?, ?)""", (param_name, value, lab))

    conn.commit()
    conn.close()


# Хранение информации о данных для считывания
params_to_read = {"trm202": ["lab13", ["T", d["lab13"]["trm202"]["first_register"]]],
                  "pressure_sensor": ["lab13", ["P", d["lab13"]["pressure_sensor"]["first_register"]]],
                  "trm200": ["lab14", ["T1", d["lab14"]["trm200"]["first_register"]],
                             ["T2", d["lab14"]["trm200"]["second_register"]]],
                  "sensor": ["lab14", ["DP", d["lab14"]["sensor"]["first_register"]]]}


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
    answer = []
    # Количество попыток и задержка между ними
    max_retries = d["max_retries"]
    retry_delay = d["delay_seconds"]  # в секундах

    for attempt in range(max_retries):
        try:
            client = AsyncModbusTcpClient(host, port=port)
            await client.connect()
            for i in range(len(devices)):
                for j in range(len(start_addresses[i])):  # получаем номер регистра
                    start_address = start_addresses[i][j]
                    device = devices[i]
                    slave_id = slave_ids[i]
                    if device == "sensor" or device == "trm200":
                        count = 1
                    else:
                        count = 2
                    try:
                        if device == "sensor":
                            data = await client.read_input_registers(address=start_address, count=count, slave=slave_id)
                        else:
                            data = await client.read_holding_registers(address=start_address, count=count,
                                                                       slave=slave_id)
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
                                f"регистр {start_address}, прочитано значение {value}")
                            temp_data = (param_name, value)  # собираем полученные данные в один кортеж
                            answer.append(temp_data)
                            if param_name == "P":
                                if value > 2000:  # проверяем давление, если больше 2000 - выключаем насос
                                    print("насос выключить!")
                                    data = await client.write_registers(address=8, values=[1],
                                                                        slave=16)  # запись данных
                                    data = await client.write_registers(address=10, values=[0],
                                                                        slave=16)  # запись данных
                                    await asyncio.sleep(1)
                                    data = await client.write_registers(address=10, values=[1000],
                                                                        slave=16)
                                    data = await client.write_registers(address=9,
                                                                        values=[0],
                                                                        slave=16)
                                    if not data.isError():
                                        print("насос экстренно вырублен")
                                    else:
                                        print("ошибка выключения насоса")
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
        except ConnectionException:
            log_error(502, f"Ошибка подключения Modbus. Попытка {attempt + 1} из {max_retries}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        except Exception as e:
            log_error(502, f"Ошибка Modbus: {str(e)}")
            break
    log_error(500, "Не удалось получить данные после всех попыток")
    return None


# Функция запуска по таймеру
async def scheduled_task():
    try:
        data = await _read_params()
        if data is not None:
            print(data)
            for answer in data:
                save_to_db(answer[0], answer[1])
    except asyncio.CancelledError:
        log_error(500, "Ошибка чтения данных. Проверьте подключение")
    except Exception as e:
        log_error(500, f"Ошибка: {str(e)}")


# Функция удаления логов по прошествии n дней
def delete_logs():
    log_file = "poll_params.log"
    log_dir = os.path.dirname(log_file)
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
