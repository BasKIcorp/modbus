import asyncio

from poll_params import _read_params

try:
    data = await _read_params()
    if data is not None:
        print("Чтение успешно, данные:")
        print(data)
except asyncio.CancelledError:
    print("Ошибка чтения данных. Проверьте подключение")
except Exception as e:
    print(f"Ошибка: {str(e)}")