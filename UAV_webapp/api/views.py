from django.shortcuts import render
# api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404
import json
from .models import UAV, Pilot, FlightStatus, ControlCommand, PilotPermission
from .serializers import ControlCommandSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def connect_to_uav(request, uav_id):
    """Подключение к БПЛА"""
    try:
        # Получаем пилота
        pilot = get_object_or_404(Pilot, user=request.user)

        # Проверяем доступ
        permission = PilotPermission.objects.filter(
            pilot=pilot,
            uav_id=uav_id,
            can_control=True,
            valid_until__gte=timezone.now()
        ).first()

        if not permission:
            return Response(
                {'error': 'Нет разрешения на управление этим БПЛА'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем БПЛА
        uav = get_object_or_404(UAV, id=uav_id)

        # Проверяем доступность
        if uav.status != 'available':
            return Response(
                {'error': 'БПЛА недоступен для управления'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем сессию полета
        flight = FlightStatus.objects.create(
            flight_type='training',  # или другой тип
            drone=uav,
            pilot=pilot,
            status='active',
            start_time=timezone.now(),
            control_session_id=str(uuid.uuid4())
        )

        # Обновляем статус БПЛА
        uav.status = 'in_use'
        uav.is_connected = True
        uav.save()

        # Создаем команду подключения
        ControlCommand.objects.create(
            flight=flight,
            command_type='connect',
            parameters={'session_id': flight.control_session_id},
            executed=True,
            result='Подключение успешно'
        )

        return Response({
            'status': 'connected',
            'session_id': flight.control_session_id,
            'flight_id': str(flight.flight_id),
            'message': 'Успешно подключено к БПЛА',
            'uav_name': uav.uav_name,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        return Response(
            {'error': f'Ошибка подключения: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disconnect_from_uav(request, flight_id):
    """Отключение от БПЛА"""
    try:
        flight = get_object_or_404(FlightStatus, flight_id=flight_id, pilot__user=request.user)

        # Проверяем, активен ли полет
        if flight.status != 'active':
            return Response(
                {'error': 'Полет не активен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обновляем статусы
        flight.status = 'non-active'
        flight.end_time = timezone.now()
        flight.save()

        uav = flight.drone
        uav.status = 'available'
        uav.is_connected = False
        uav.save()

        # Создаем команду отключения
        ControlCommand.objects.create(
            flight=flight,
            command_type='disconnect',
            executed=True,
            result='Отключение успешно'
        )

        return Response({
            'status': 'disconnected',
            'message': 'Успешно отключено от БПЛА',
            'flight_duration': (flight.end_time - flight.start_time).total_seconds() if flight.end_time else 0,
            'timestamp': timezone.now().isoformat()
        })

    except FlightStatus.DoesNotExist:
        return Response(
            {'error': 'Сессия полета не найдена'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_command(request, flight_id):
    """Отправка команды управления"""
    try:
        flight = get_object_or_404(FlightStatus, flight_id=flight_id, pilot__user=request.user)

        # Проверяем активность полета
        if flight.status != 'active':
            return Response(
                {'error': 'Полет не активен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Валидируем команду
        serializer = ControlCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        command_data = serializer.validated_data

        # Создаем команду
        command = ControlCommand.objects.create(
            flight=flight,
            command_type=command_data['command_type'],
            parameters=command_data.get('parameters', {}),
            direction=command_data.get('direction', ''),
            speed=command_data.get('speed', 0.5),
            duration=command_data.get('duration', 1.0)
        )

        # Здесь будет интеграция с реальным БПЛА
        # Например, отправка через MAVLink, ROS и т.д.
        result = execute_drone_command(flight, command)

        # Обновляем результат команды
        command.executed = result['success']
        command.result = result['message']
        command.save()

        return Response({
            'status': 'command_sent',
            'command_id': str(command.id),
            'command_type': command.command_type,
            'executed': command.executed,
            'message': command.result,
            'timestamp': command.timestamp.isoformat()
        })

    except FlightStatus.DoesNotExist:
        return Response(
            {'error': 'Сессия полета не найдена'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_control(request, flight_id):
    """Ручное управление (джойстик)"""
    try:
        flight = get_object_or_404(FlightStatus, flight_id=flight_id, pilot__user=request.user)

        if flight.status != 'active':
            return Response(
                {'error': 'Полет не активен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем параметры управления
        direction = request.data.get('direction')
        speed = float(request.data.get('speed', 0.5))
        duration = float(request.data.get('duration', 0.1))

        # Валидация направления (используем вашу UI модель)
        valid_directions = ['up', 'down', 'left', 'right',
                            'up_left', 'up_right', 'down_left', 'down_right']

        if direction not in valid_directions:
            return Response(
                {'error': f'Неверное направление. Допустимые: {valid_directions}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем команду движения
        command = ControlCommand.objects.create(
            flight=flight,
            command_type='move',
            direction=direction,
            speed=speed,
            duration=duration
        )

        # Исполняем команду
        result = execute_movement_command(flight, direction, speed, duration)

        command.executed = result['success']
        command.result = result['message']
        command.save()

        return Response({
            'status': 'moving',
            'direction': direction,
            'speed': speed,
            'duration': duration,
            'executed': command.executed,
            'message': command.result,
            'timestamp': command.timestamp.isoformat()
        })

    except Exception as e:
        return Response(
            {'error': f'Ошибка управления: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_flight_status(request, flight_id):
    """Получение статуса полета"""
    try:
        flight = get_object_or_404(FlightStatus, flight_id=flight_id, pilot__user=request.user)

        # Получаем последние команды
        recent_commands = ControlCommand.objects.filter(
            flight=flight
        ).order_by('-timestamp')[:10]

        commands_list = []
        for cmd in recent_commands:
            commands_list.append({
                'type': cmd.command_type,
                'direction': cmd.direction,
                'timestamp': cmd.timestamp.isoformat(),
                'executed': cmd.executed,
                'result': cmd.result
            })

        return Response({
            'flight_id': str(flight.flight_id),
            'status': flight.status,
            'flight_type': flight.flight_type,
            'uav_name': flight.drone.uav_name,
            'start_time': flight.start_time.isoformat() if flight.start_time else None,
            'end_time': flight.end_time.isoformat() if flight.end_time else None,
            'recent_commands': commands_list,
            'is_connected': flight.drone.is_connected,
            'battery_level': flight.drone.battery_capacity  # Здесь должна быть реальная телеметрия
        })

    except FlightStatus.DoesNotExist:
        return Response(
            {'error': 'Полет не найден'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_uav_telemetry(request, uav_id):
    """Получение телеметрии БПЛА"""
    try:
        # Проверяем разрешение
        pilot = get_object_or_404(Pilot, user=request.user)
        permission = PilotPermission.objects.filter(
            pilot=pilot,
            uav_id=uav_id,
            can_control=True
        ).exists()

        if not permission:
            return Response(
                {'error': 'Нет доступа к этому БПЛА'},
                status=status.HTTP_403_FORBIDDEN
            )

        uav = get_object_or_404(UAV, id=uav_id)

        # Здесь должна быть реальная телеметрия от БПЛА
        # Пока симулируем
        import random
        telemetry = {
            'uav_name': uav.uav_name,
            'status': uav.status,
            'is_connected': uav.is_connected,
            'battery': random.randint(20, 100),  # Симуляция
            'altitude': random.uniform(0, 100),
            'speed': random.uniform(0, uav.max_speed) if uav.max_speed else 0,
            'latitude': 55.7558 + random.uniform(-0.01, 0.01),
            'longitude': 37.6173 + random.uniform(-0.01, 0.01),
            'timestamp': timezone.now().isoformat()
        }

        return Response(telemetry)

    except Exception as e:
        return Response(
            {'error': f'Ошибка получения телеметрии: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Вспомогательные функции (заглушки для реальной реализации)
def execute_drone_command(flight, command):
    """Заглушка для исполнения команды"""
    # Здесь будет реальная интеграция с БПЛА
    # MAVLink, ROS, или другой протокол

    return {
        'success': True,
        'message': f'Команда {command.command_type} принята к исполнению'
    }


def execute_movement_command(flight, direction, speed, duration):
    """Заглушка для движения"""
    # Здесь преобразуем направление в команды для БПЛА
    movement_map = {
        'up': {'pitch': speed, 'roll': 0, 'throttle': 0.7},
        'down': {'pitch': -speed, 'roll': 0, 'throttle': 0.3},
        'left': {'pitch': 0, 'roll': -speed, 'throttle': 0.5},
        'right': {'pitch': 0, 'roll': speed, 'throttle': 0.5},
        'up_left': {'pitch': speed, 'roll': -speed, 'throttle': 0.6},
        'up_right': {'pitch': speed, 'roll': speed, 'throttle': 0.6},
        'down_left': {'pitch': -speed, 'roll': -speed, 'throttle': 0.4},
        'down_right': {'pitch': -speed, 'roll': speed, 'throttle': 0.4},
    }

    if direction in movement_map:
        movement = movement_map[direction]
        # Здесь отправляем движение в БПЛА
        return {
            'success': True,
            'message': f'Движение {direction} со скоростью {speed}'
        }

    return {
        'success': False,
        'message': 'Неизвестное направление'
    }
# Create your views here.
