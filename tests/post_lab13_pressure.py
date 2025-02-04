import requests


def test_post_set_pressure():
    value = 10  # значение для передачи в запросе
    url = "http://127.0.0.1:3000/lab13/trm202/set_pressure"

    # выполнение POST-запроса
    response = requests.post(f"{url}?value={value}")

    # вывод результата запроса
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)


test_post_set_pressure()
