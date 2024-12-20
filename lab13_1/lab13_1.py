import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from flask import Blueprint
from flask_restful import Api, Resource, marshal, fields, abort
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

lab_num = "lab13_1"

lab_13_1 = Blueprint('lab13_1', __name__)
api = Api(lab_13_1)

with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)


def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


lab13_logger = create_logger("lab13_logger", "modbusRESTAPI/lab13_1/lab13_1.log")


def log_error(code, message):
    lab13_logger.error(f'Ошибка {code}: {message}')
    abort(code, message=message)


class Lab13_1API(Resource):
    def get(self, device, function):
        if device == "trm202":
            try:
                data = asyncio.run(self._read_device_data(device, function))
                return data
            except Exception as e:
                log_error(500, f"Unexpected error: {str(e)}")
        else:
            log_error(404, "Нет устройства {} в {}".format(device, lab_num))

    async def _read_device_data(self, device, function):
        slave_id = d[lab_num][device]["slave_id"]
        host = "10.2.147.7"
        port = 502
        start_address = None
        count = 2
        if function == "get_temp":
            start_address = 4105
        elif function == "get_pressure":
            start_address = 4107
        else:
            log_error(404, f"Нет функции {function}")

        client = AsyncModbusTcpClient(host, port=port)
        await client.connect()

        try:
            data = await client.read_holding_registers(address=start_address, count=count, slave=slave_id)
            if not data.isError():
                value_float32 = client.convert_from_registers(data.registers, data_type=client.DATATYPE.FLOAT32)
                lab13_logger.info(
                    f"Лаб13_1, прибор {device}, функция {function}, прочитано значение {value_float32}")
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


api.add_resource(Lab13_1API, '/lab13_1/<string:device>/<string:function>')
