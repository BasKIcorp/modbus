# ModBus REST API

## Общий вид запросов
### Запрос на чтение одного регистра (номер функции - 3)
- GET-запрос: /lab_num/device_num/get_function

### Запрос на запись (номер функции - 16), n - записываемое значение
- POST-запрос: /lab_num/device_num/set_function?value=n

## Запросы по лабораторным работам
### Лабораторная работа 13
#### ТРМ202
- Чтение температуры - GET /lab13/trm202/get_temp
- Запуск насоса - POST /lab13/trm202/set_valve?value=on
- Отключение насоса - POST /lab13/trm202/set_valve?value=off
- Клапан - POST /lab13/trm202/set_valve?value=release
#### Датчик давления
- Чтение изменения давления - GET /lab13/pressure_sensor/get_pressure
  
### Лабораторная работа 14
#### ТРМ210
- Запись напряжения - POST /lab14/trm210/set_voltage?value=n
- Чтение давления - GET /lab14/trm210/get_pressure
#### ТРМ200
- Чтение температуры на стенке емкости постоянного объема - GET /lab14/trm200/get_temp_1
- Чтение температуры воздуха внутри емкости газового термометра - GET /lab14/trm200/get_temp_2
### Датчик
- Чтение изменения давления - GET /lab14/sensor/get_deltap
## Инструкция по запуску
### Клонирование репозитория
```
git clone https://github.com/BasKIcorp/modbus.git
cd modbus
```
### Создание виртуального окружения
```
python3 -m venv venv
```
### Активация виртуального окружения
```
source venv/bin/activate
```
### Установка необходимых библиотек
```
pip install -r requirements.txt
```
### Запуск приложения
```
python3 app.py
```
