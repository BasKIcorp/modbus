import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from flask import Blueprint
from flask_restful import Api, Resource, reqparse, marshal, fields, abort
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

lab_num = "lab14"

lab_14 = Blueprint('lab14', __name__)
api = Api(lab_14)

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


lab14_logger = create_logger("lab14_logger", "lab14.log")


# В случае ошибки записываем в логгер и отправляем код ошибки
def log_error(code, message):
    lab14_logger.error(f'Ошибка {code}: {message}')
    abort(code, message=message)


class Lab14API(Resource):
    def get(self, device, function):
        if device in ["trm200", "trm210"]:  # устройства лабы "Закон Шарля"
            try:
                data = asyncio.run(self._read_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _read_device_data(self, device, function):
        slave_id = d[lab_num][device]["slave_id"]
        host = d["server_host"]
        port = d["server_port"]
        start_address = None
        count = 2
        if (device == "trm200" and function == "get_temp_1") or \
                (device == "trm210" and function == "get_pressure"):    # первый регистр, проверяем наличие функций
            start_address = 4105
        elif device == "trm200" and function == "get_temp_2":   # второй регистр, проверяем наличие функций
            start_address = 4107
        else:
            log_error(404, message="Нет функции {}".format(function))

        # Количество попыток и задержка между ними
        max_retries = d["max_retries"]
        retry_delay = d["delay_seconds"]  # в секундах

        for attempt in range(max_retries):
            try:
                client = AsyncModbusTcpClient(host, port=port)
                await client.connect()
                try:
                    data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)  # считывание данных
                    if not data.isError():
                        value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)    # переводим в читаемый вид
                        lab14_logger.info(f"Лаб14, прибор {device}, функция {function}, прочитано значение {value_float32}")
                        result = [{'Прибор': device, 'Функция': function, 'Значение': value_float32}]
                        reg_fields = {'Прибор': fields.String, 'Функция': fields.String, 'Значение': fields.Float}
                        return {'Полученные значения': [marshal(reg, reg_fields) for reg in result]}    # отправляем на сервис ответ
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
            except ConnectionException:
                log_error(502, f"Ошибка подключения Modbus. Попытка {attempt + 1} из {max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
            except Exception as e:
                log_error(502, f"Ошибка Modbus: {str(e)}")
                break
        log_error(500, "Не удалось получить данные после всех попыток")

    def post(self, device, function):
        if device == "trm210":  # запись только для устройства trm210
            try:
                data = asyncio.run(self._write_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _write_device_data(self, device, function):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("value", type=int, location="args")    # получение значения для записи
        query = parser.parse_args()
        if device == "trm210":
            slave_id = d[lab_num][device]["slave_id"]
            value = query["value"]
            host = d["server_host"]
            port = d["server_port"]
            start_address = None
            if device == "trm210" and function == "set_voltage":    # проверяем наличие функции
                start_address = d[lab_num][device]["write_register"]
                value = value // 100    # преобразовываем в формат, нужный для устройства
            else:
                log_error(404, message="Нет функции {}".format(function))

            client = AsyncModbusTcpClient(host, port=port)
            await client.connect()
            try:
                data = await client.write_registers(address=start_address, values=[value], slave=slave_id)  # запись данных
                if not data.isError():
                    lab14_logger.info(f"Лаб14, прибор {device}, функция {function}, значение {value} записано")
                    return {'Значение записано': True}
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


api.add_resource(Lab14API, '/lab14/<string:device>/<string:function>')


# Функция удаления логов по прошествии n дней
def delete_logs():
    log_file = "lab14.log"
    log_dir = os.path.dirname(log_file)
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)