import json
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Blueprint
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException,\
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

poll_temps = Blueprint('poll_temps', __name__)

with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)


def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


lab13_logger = create_logger("poll_temps_logger", "modbusRESTAPI/poll_temps.log")


def log_error(code, message):
    lab13_logger.error(f'Ошибка {code}: {message}')


DB_FILE = 'modbusRESTAPI/temperature_data.db'


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temperatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT NOT NULL,
            start_address INT NOT NULL,
            temperature REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


async def _read_temperatures():
    devices = ["trm200", "trm202"]
    function = "get_temp"
    slave_ids = [d["lab13_2"]["trm200"]["slave_id"], d["lab13_1"]["trm202"]["slave_id"]]
    host = "10.2.147.7"
    port = 502
    start_address = 4105
    count = 2
    answer = []

    client = AsyncModbusTcpClient(host, port=port)
    await client.connect()
    for i in range(len(devices)):
        device = devices[i]
        slave_id = slave_ids[i]
        try:
            data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)
            if not data.isError():
                value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                lab13_logger.info(
                    f"Получение температур, прибор {device}, регистр {start_address - 4104}, функция {function}, "
                    f"прочитано значение {value_float32}")
                temp_data = (device, start_address, value_float32)
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

    device = devices[0]
    slave_id = slave_ids[0]
    start_address = 4107
    try:
        data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)
        if not data.isError():
            value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
            lab13_logger.info(
                f"Получение температур, прибор {device}, регистр {start_address - 4104}, функция {function}, "
                f"прочитано значение {value_float32}")
            temp_data = (device, start_address, value_float32)
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


def save_to_db(device, start_address, temperature):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO temperatures (device, start_address, temperature) VALUES (?, ?, ?)", (device, start_address, temperature))
    conn.commit()
    conn.close()


async def scheduled_task():
    try:
        data = await _read_temperatures()
        if data is not None:
            print(data)
            for answer in data:
                save_to_db(answer[0], answer[1], answer[2])
    except Exception as e:
        log_error(500, f"Unexpected error: {str(e)}")


scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(scheduled_task()), 'interval', minutes=d["poll_time_minutes"], seconds=d["poll_time_seconds"])
scheduler.start()
