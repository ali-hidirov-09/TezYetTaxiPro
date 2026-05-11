import logging
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key: str):
    """
    JWT tokendan foydalanuvchini oladi.
    Token noto'g'ri yoki foydalanuvchi topilmasa — AnonymousUser qaytaradi.
    """
    try:
        UntypedToken(token_key)
        decoded = jwt_decode(
            token_key,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        user_id = decoded.get("user_id")
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist, Exception) as e:
        logger.debug(f"WS auth xato: {e}")
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    WebSocket ulanishida JWT tokenni tekshiradi.
    Token query parameter orqali uzatiladi:
        wss://taxifast.uz/ws/orders/42/?token=eyJ...
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
