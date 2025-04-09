import asyncio

device_locks = {
    "trm202": asyncio.Lock(),
    "pressure_sensor": asyncio.Lock(),
    "trm200": asyncio.Lock(),
    "sensor": asyncio.Lock(),
    "trm210": asyncio.Lock()
}