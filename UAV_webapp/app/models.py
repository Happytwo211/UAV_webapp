import uuid
from django.db import models
from django.contrib.auth.models import User


class UAV(models.Model):
    """Модель БПЛА"""
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    uav_name = models.CharField(max_length=100)
    serial_num = models.CharField(max_length=50, unique=True)  # Changed from UUID to CharField
    weight = models.FloatField(null=True, blank=True)
    max_flight_time = models.IntegerField(null=True, blank=True)
    max_range = models.IntegerField(null=True, blank=True)
    max_speed = models.IntegerField(null=True, blank=True)
    battery_capacity = models.IntegerField(null=True, blank=True)

    # Добавим статус для управления
    status = models.CharField(
        max_length=20,
        choices=[
            ('available', 'Доступен'),
            ('in_use', 'В использовании'),
            ('maintenance', 'На обслуживании'),
        ],
        default='available'
    )

    # Для управления
    is_connected = models.BooleanField(default=False)
    connection_token = models.CharField(max_length=100, blank=True)


class Pilot(models.Model):
    """Модель пилота"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    pilot_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    is_allowed = models.BooleanField(default=False)

    # Разрешения на конкретные дроны
    allowed_uavs = models.ManyToManyField(UAV, through='PilotPermission')


class PilotPermission(models.Model):
    """Разрешения пилота на конкретный БПЛА"""
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE)
    uav = models.ForeignKey(UAV, on_delete=models.CASCADE)
    can_control = models.BooleanField(default=False)
    valid_until = models.DateTimeField(null=True, blank=True)


class FlightStatus(models.Model):
    """Статус полета"""
    FLIGHT_STATUS = [
        ('active', 'Активен'),
        ('non-active', 'Неактивен'),
        ('unavailable', 'Недоступен'),
    ]

    MISSION_TYPES = [
        ('surveillance', 'Наблюдение'),
        ('mapping', 'Картографирование'),
        ('inspection', 'Инспекция'),
        ('delivery', 'Доставка'),
        ('training', 'Тренировка'),
        ('other', 'Другое'),
    ]

    flight_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    flight_type = models.CharField(max_length=20, choices=MISSION_TYPES, verbose_name='Тип миссии')
    drone = models.ForeignKey(UAV, on_delete=models.CASCADE, verbose_name='БПЛА')
    pilot = models.ForeignKey(Pilot, on_delete=models.SET_NULL, null=True, verbose_name='Оператор')
    status = models.CharField(max_length=20, choices=FLIGHT_STATUS, default='non-active')

    # Для управления
    control_session_id = models.CharField(max_length=100, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)


class ControlCommand(models.Model):
    """Модель для хранения команд управления"""
    COMMAND_TYPES = [
        ('connect', 'Подключение'),
        ('disconnect', 'Отключение'),
        ('takeoff', 'Взлет'),
        ('land', 'Посадка'),
        ('move', 'Движение'),
        ('stop', 'Стоп'),
        ('rtl', 'Возврат'),
        ('emergency', 'Авария'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flight = models.ForeignKey(FlightStatus, on_delete=models.CASCADE, null=True, blank=True)
    command_type = models.CharField(max_length=20, choices=COMMAND_TYPES)
    parameters = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    executed = models.BooleanField(default=False)
    result = models.TextField(blank=True)

    # Для движения (используем вашу UI модель)
    direction = models.CharField(max_length=20, blank=True, choices=[
        ('up', 'Вверх'),
        ('down', 'Вниз'),
        ('left', 'Влево'),
        ('right', 'Вправо'),
        ('up_left', 'Вверх-влево'),
        ('up_right', 'Вверх-вправо'),
        ('down_left', 'Вниз-влево'),
        ('down_right', 'Вниз-вправо'),
    ])
    speed = models.FloatField(default=0.5)
    duration = models.FloatField(default=1.0)


class Translating(models.Model):
    """Видео трансляция"""
    video_tr = models.FileField(upload_to='Flight_Vid')
    flight = models.ForeignKey(FlightStatus, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)