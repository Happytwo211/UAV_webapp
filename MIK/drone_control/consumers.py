import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from mavsdk import System

class DroneConsumer(AsyncWebsocketConsumer):


    async def connect(self):
        print('попытка подключения - accept')
        await self.accept()
        print('сеть подключена')
        print('попытка подключения - system')
        self.drone = System()
        try:
            print("Попытка связи с 14560...")
            await self.drone.connect(system_address="udpout://127.0.0.1:14560")
            print('проверка безопасности - арм и взлет')
            asyncio.create_task(self.arm_and_takeoff())
            print('проверка безопасности- телеметрия')
            asyncio.create_task(self.stream_telemetry())


        except Exception as e:
            print(f"Ошибка в connect: {e}")

    async def arm_and_takeoff(self):
        try:
            print('проверка gps')
            async for health in self.drone.telemetry.health():
                if health.is_global_position_ok:
                    print('готов')
                    break
            print('ждем спутники')
            await asyncio.sleep(2)
            await self.drone.action.arm()
            print("взлет")
            await self.drone.action.takeoff()
        except Exception as e:
            print(f'ошибка взлета -{e}')


    async def stream_telemetry(self):
        try:
            print('Поток высоты запущен')
            async for pos in self.drone.telemetry.position():
                alt = round(pos.relative_altitude_m, 2)
                await self.send(text_data=json.dumps({"altitude": alt}))
        except Exception as e:
            print(f'ошибка данных - {e}')