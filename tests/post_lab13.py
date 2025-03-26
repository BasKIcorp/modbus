import requests
from pyModbusTCP.client import ModbusClient
from time import sleep

# trm_202 = ModbusClient(host="10.2.147.7", port=502, unit_id=16, auto_open=True)

def test_post_set_valve():
    value = 'off' # значение для передачи в запросе
    url = "http://127.0.0.1:3000/lab13/trm202/set_valve"

    # выполнение POST-запроса
    response = requests.post(f"{url}?value={value}")

    # вывод результата запроса
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)


test_post_set_valve()
# print(trm_202.read_holding_registers(7, 4))