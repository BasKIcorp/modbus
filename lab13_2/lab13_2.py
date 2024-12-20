import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler

from flask import Blueprint
from flask_restful import Api, Resource, reqparse, marshal, fields, abort
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

lab_num = "lab13_2"

lab_13_2 = Blueprint('lab13_2', __name__)
api = Api(lab_13_2)
with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)


def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


lab12_logger = create_logger("lab12_logger", "modbusRESTAPI/lab13_2/lab13_2.log")


def log_error(code, message):
    lab12_logger.error(f'Ошибка {code}: {message}')
    abort(code, message=message)


class Lab13_2API(Resource):
    def get(self, device, function):
        if device in ["trm200", "trm210"]:
            try:
                data = asyncio.run(self._read_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _read_device_data(self, device, function):
        slave_id = d[lab_num][device]["slave_id"]
        host = d[lab_num][device]["host"]
        port = d[lab_num][device]["port"]
        client = AsyncModbusTcpClient(
            host,
            port=port
        )
        start_address = None
        count = 2
        if (device == "trm200" and function == "get_temp_1") or \
                (device == "trm210" and function == "get_pressure"):
            start_address = 4105
        elif device == "trm200" and function == "get_temp_2":
            start_address = 4107
        else:
            log_error(404, message="Нет функции {}".format(function))
        await client.connect()

        try:
            data = client.read_holding_registers(address=start_address, count=count, slave=slave_id)
            if not data.isError():
                value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                lab12_logger.info(f"Лаб13_2, прибор {device}, функция {function}, прочитано значение {value_float32}")
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


    def post(self, device, function):
        if device == "trm210":
            try:
                data = asyncio.run(self._write_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _write_device_data(self, device, function):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("value", type=int, location="args")
        query = parser.parse_args()
        if device == "trm210":
            slave_id = d[lab_num][device]["slave_id"]
            value = query["value"]
            host = d[lab_num][device]["host"]
            port = d[lab_num][device]["port"]
            start_address = None
            if device == "trm210" and function == "set_voltage":
                start_address = 4105
                value = value // 100
            else:
                log_error(404, message="Нет функции {}".format(function))

            client = AsyncModbusTcpClient(
                host,
                port=port
            )

            await client.connect()

            try:
                data = await client.write_register(address=start_address, value=value, slave=slave_id)
                if not data.isError():
                    lab12_logger.info(f"Лаб12, прибор {device}, функция {function}, значение {value} записано")
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

        else:
            log_error(404, message="Нет устройства {} в {}".format(device, lab_num))


api.add_resource(Lab13_2API, '/lab13_2/<string:device>/<string:function>')
