import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from mavsdk import System


class DroneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Принимаем соединение от браузера
        await self.accept()
        print('--- WebSocket подключен ---')

        self.drone = System()

        try:
            # Используем udpout для активной инициализации связи на порту 14560
            print("Форсируем подключение к jMAVSim (udpout://127.0.0.1:14560)...")
            await self.drone.connect(system_address="udpout://127.0.0.1:14560")

            # Запускаем задачи управления и телеметрии
            # Мы используем create_task, чтобы они работали параллельно
            asyncio.create_task(self.arm_and_takeoff())
            asyncio.create_task(self.stream_telemetry())

        except Exception as e:
            print(f"Ошибка при попытке подключения: {e}")

    async def arm_and_takeoff(self):
        try:
            print("Ожидание подтверждения связи (Heartbeat)...")
            # 1. Проверяем, что MAVSDK действительно видит симулятор
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    print("Связь с автопилотом установлена!")
                    break
                await asyncio.sleep(1)

            print("Проверка готовности датчиков и GPS...")
            # 2. Ждем готовности систем к взлету
            async for health in self.drone.telemetry.health():
                if health.is_global_position_ok and health.is_home_position_ok:
                    print("Дрон готов! GPS и точка дома определены.")
                    break
                else:
                    print("Настройка навигации... Дайте симулятору 10-20 секунд.")
                    await asyncio.sleep(2)

            # 3. Команда на запуск моторов
            print("Отправка команды: ARM")
            await self.drone.action.arm()

            # Небольшая пауза, чтобы симулятор успел среагировать
            await asyncio.sleep(2)

            # 4. Команда на взлет
            print("Отправка команды: TAKEOFF (Взлет на 2.5 метра)")
            await self.drone.action.takeoff()

        except Exception as e:
            print(f"Ошибка в логике взлета: {e}")

    async def stream_telemetry(self):
        try:
            print("Поток телеметрии запущен.")
            # Подписываемся на данные о позиции
            async for pos in self.drone.telemetry.position():
                altitude = round(pos.relative_altitude_m, 2)

                # Отправляем высоту в реальном времени в браузер
                await self.send(text_data=json.dumps({
                    "altitude": altitude
                }))
        except Exception as e:
            print(f"Ошибка передачи телеметрии: {e}")

    async def disconnect(self, close_code):
        print(f"--- WebSocket отключен (код: {close_code}) ---")