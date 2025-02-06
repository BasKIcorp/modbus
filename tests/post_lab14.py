import requests


def test_post_set_heat():
    value = 1000  # значение для передачи в запросе
    url = "http://127.0.0.1:3000/lab14/trm210/set_voltage"

    # выполнение POST-запроса
    response = requests.post(f"{url}?value={value}")

    # вывод результата запроса
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)


test_post_set_heat()
