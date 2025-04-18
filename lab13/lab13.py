import json
import logging
import os
from locks import device_locks
from time import sleep
from logging.handlers import RotatingFileHandler
import asyncio
from flask import Blueprint
from flask_restful import Api, Resource, marshal, fields, abort, reqparse
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

lab_num = "lab13"

lab_13 = Blueprint('lab13', __name__)
api = Api(lab_13)

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


lab13_logger = create_logger("lab13_logger", "lab13.log")


def log_error(code, message):
    lab13_logger.error(f'Ошибка {code}: {message}')
    abort(code, message=message)


class Lab13API(Resource):
    def get(self, device, function):
        if device == "trm202" or device == "pressure_sensor":  # устройство лабы "Опытное определение показателя адиабаты воздуха"
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
        connection_timeout = d["connection_timeout"]
        start_address = None
        count = None
        if device == "pressure_sensor":   
            count = 2
            start_address = d["lab13"]["pressure_sensor"]["first_register"]
        else:
            if function == "get_temp":  # по ручке получаем регистр
                count = 1
                start_address = d["lab13"]["trm202"]["first_register"]
            else:
                log_error(404, f"Нет функции {function}")

        async with device_locks[device]:
            try:
                client = AsyncModbusTcpClient(host, port=port)
                await asyncio.wait_for(client.connect(), timeout=connection_timeout)
                try:
                    data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)
                    if not data.isError():
                        print(data.registers)
                        if device == "pressure_sensor":
                            value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                        else:
                            value_float32 = data.registers[0] / 10
                        lab13_logger.info(
                            f"Лаб13, прибор {device}, функция {function}, прочитано значение {value_float32}")
                        result = [{'Прибор': device, 'Функция': function, 'Значение': value_float32}]
                        reg_fields = {'Прибор': fields.String, 'Функция': fields.String, 'Значение': fields.Float}
                        return {'Полученные значения': [marshal(reg, reg_fields) for reg in result]}
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
            except Exception as e:
                log_error(502, f"Ошибка Modbus: {str(e)}")
        log_error(500, "Не удалось получить данные")

    def post(self, device, function):
        if device == "trm202":  # запись только для устройства trm202
            try:
                data = asyncio.run(self._write_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _write_device_data(self, device, function):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("value", type=str, location="args")  # получение значения для записи
        query = parser.parse_args()
        if device == "trm202":
            slave_id = d[lab_num][device]["slave_id"]
            value = query["value"]
            host = d["server_host"]
            port = d["server_port"]
            connection_timeout = d["connection_timeout"]
            start_address = None
            if device == "trm202" and function == "set_valve":  # проверяем наличие функции
                if value == "on" or value == "off":
                    start_address = d[lab_num][device]["pump_register"]
                elif value == "release":
                    start_address = d[lab_num][device]["valve_register"]
                else:
                    log_error(404, message="Неверное значение")
            else:
                log_error(404, message="Нет функции {}".format(function))
            async with device_locks[device]:
                client = AsyncModbusTcpClient(host, port=port)
                await asyncio.wait_for(client.connect(), timeout=connection_timeout)
                try:
                    if value == "on" or value == "off":  # функция on и off
                        value = 1000 if value == "on" else 0
                        data = await client.write_registers(address=7, values=[1],
                                                            slave=slave_id)  # запись данных
                        if not data.isError():
                            lab13_logger.info(f"Лаб13, внешнее управление насоса включено")
                        data = await client.write_registers(address=start_address, values=[value],
                                                            slave=slave_id)  # запись данных
                        if not data.isError():
                            lab13_logger.info(f"Лаб13, прибор {device}, функция {function}, значение {value} записано")
                            return {'Функция сработала': True}
                        else:
                            log_error(502, "Ошибка: {}".format(data))
                    else:  # функция release
                        value = 0
                        data = await client.write_registers(address=8, values=[1],
                                                            slave=slave_id)  # запись данных
                        if not data.isError():
                            lab13_logger.info(f"Лаб13, внешнее управление клапана включено")
                        data = await client.write_registers(address=start_address, values=[value],
                                                            slave=slave_id)  # запись данных
                        if not data.isError():
                            lab13_logger.info(f"Лаб13, прибор {device}, функция {function}, значение {value} записано")
                        else:
                            log_error(502, "Ошибка: {}".format(data))
                        await asyncio.sleep(1)
                        value = 1000
                        data = await client.write_registers(address=start_address, values=[value],
                                                            slave=slave_id)  # запись данных
                        if not data.isError():
                            lab13_logger.info(f"Лаб13, прибор {device}, функция {function}, значение {value} записано")
                            return {'Функция release сработала': True}
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


api.add_resource(Lab13API, '/lab13/<string:device>/<string:function>')


# Функция удаления логов по прошествии n дней
def delete_logs():
    log_file = "lab13.log"
    log_dir = os.path.dirname(log_file)
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
