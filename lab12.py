import json
import logging
from logging.handlers import RotatingFileHandler

from flask import Blueprint
from flask_restful import Api, Resource, reqparse, marshal, fields, abort
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ParameterException, NoSuchSlaveException, \
    NotImplementedException, InvalidMessageReceivedException, MessageRegisterException

lab_num = "lab12"

lab_12 = Blueprint('lab12', __name__)
api = Api(lab_12)
with open('./config.json') as f:
    d = json.load(f)


def create_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=3000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger


lab12_logger = create_logger("lab12_logger", "lab12/lab12.log")


def log_error(code, message):
    lab12_logger.error(f'Ошибка {code}: {message}')
    abort(code, message=message)


class Lab12API(Resource):
    def get(self, device, function):
        if device in ["trm200", "trm202_1", "trm202_2"]:
            port = d[lab_num][device]["port"]
            baudrate = d[lab_num][device]["baudrate"]
            parity = d[lab_num][device]["parity"]
            timeout = d[lab_num][device]["timeout"]
            slave_id = d[lab_num][device]["slave_id"]
            stopbits = d[lab_num][device]["stopbits"]

            client = ModbusClient(method='rtu', port=port, baudrate=baudrate,
                                  parity=parity, timeout=timeout, stopbits=stopbits)
            client.connect()
            count = 1
            if (device == "trm200" and function == "get_temp_1") or \
                    (device == "trm202_1" and function == "get_heat") or \
                    (device == "trm202_2" and function == "get_res"):
                start_address = 1
            elif (device == "trm200" and function == "get_temp_2") or \
                    (device == "trm202_2" and function == "get_air"):
                start_address = 2
            else:
                log_error(404, message="Нет функции {}".format(function))

            try:
                data = client.read_holding_registers(start_address, count, unit=slave_id)
            except ConnectionException:
                log_error(502, "Нет соединения с устройством")
                print("jopa")
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

            if not data.isError():
                lab12_logger.info(f"Лаб12, прибор {device}, функция {function}, прочитано значение {data.registers[0]}")
                result = [{'Прибор': device, 'Функция': function, 'Значение': data.registers[0]}]
                reg_fields = {'Прибор': fields.String, 'Функция': fields.String, 'Значение': fields.Integer}
                return {'Полученные значения': [marshal(reg, reg_fields) for reg in result]}
            else:
                log_error(502, "Ошибка: {}".format(data))
        else:
            log_error(404, message="Нет устройства {} в {}".format(device, lab_num))

    def post(self, device, function):
        parser = reqparse.RequestParser(bundle_errors=True)
        parser.add_argument("value", type=int, location="args")
        query = parser.parse_args()
        if device in ["trm200", "trm202_1", "trm202_2"]:
            port = d[lab_num][device]["port"]
            baudrate = d[lab_num][device]["baudrate"]
            parity = d[lab_num][device]["parity"]
            timeout = d[lab_num][device]["timeout"]
            slave_id = d[lab_num][device]["slave_id"]
            stopbits = d[lab_num][device]["stopbits"]
            value = query["value"]
            client = ModbusClient(method='rtu', port=port, baudrate=baudrate,
                                  parity=parity, timeout=timeout, stopbits=stopbits)
            client.connect()

            if (device == "trm202_1" and function == "set_heat") or \
                    (device == "trm202_2" and function == "set_air"):
                start_address = 5
                value = value // 100
            else:
                log_error(404, message="Нет функции {}".format(function))

            try:
                data = client.write_register(start_address, value, unit=slave_id)
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

            if not data.isError():
                lab12_logger.info(f"Лаб12, прибор {device}, функция {function}, значение {value} записано")
                return {'Значение записано': True}
            else:
                log_error(502, "Ошибка: {}".format(data))
        else:
            log_error(404, message="Нет устройства {} в {}".format(device, lab_num))


api.add_resource(Lab12API, '/lab12/<string:device>/<string:function>')