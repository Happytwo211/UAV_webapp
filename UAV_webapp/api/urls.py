# api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Подключение/отключение
    path('uav/<uuid:uav_id>/connect/', views.connect_to_uav, name='connect_uav'),
    path('flight/<uuid:flight_id>/disconnect/', views.disconnect_from_uav, name='disconnect_uav'),

    # Управление
    path('flight/<uuid:flight_id>/command/', views.send_command, name='send_command'),
    path('flight/<uuid:flight_id>/manual/', views.manual_control, name='manual_control'),

    # Статус и телеметрия
    path('flight/<uuid:flight_id>/status/', views.get_flight_status, name='flight_status'),
    path('uav/<uuid:uav_id>/telemetry/', views.get_uav_telemetry, name='uav_telemetry'),
]