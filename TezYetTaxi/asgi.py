import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TezYetTaxi.settings")

# Django ASGI app ni channels dan oldin olishimiz kerak
django_asgi_app = get_asgi_application()

# Import routing faqat Django tayyor bo'lganidan keyin
from apps.orders.routing import websocket_urlpatterns  # noqa: E402
from apps.orders.middleware import JwtAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter({
    # Oddiy HTTP so'rovlar — avvalgiday ishlaydi
    "http": django_asgi_app,

    # WebSocket so'rovlar — JWT autentifikatsiya bilan
    "websocket": AllowedHostsOriginValidator(
        JwtAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
