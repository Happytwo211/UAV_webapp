import os
import sys
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MIK.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from drone_control.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
            URLRouter(
                        websocket_urlpatterns  # Используем импортированную переменную напрямую
                            )
                                    ),
            })