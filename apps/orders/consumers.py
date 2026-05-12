"""Bu fayl ba'zi APIlarni Web Socketda ishlashi uchun yaratildi"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Order

logger = logging.getLogger(__name__)


def order_group_name(order_id: int) -> str:
    """Bitta buyurtma uchun channel group nomi."""
    return f"order_{order_id}"


def driver_group_name() -> str:
    """Barcha haydovchilar uchun umumiy group nomi."""
    return "drivers_pending"


class OrderStatusConsumer(AsyncWebsocketConsumer):
    """
    Mijoz va haydovchi buyurtma holatini real vaqtda kuzatadi.

    Ulanish: wss://taxifast.uz/ws/orders/{order_id}/?token=eyJ...

    Qoidalar:
    - Faqat autentifikatsiyalangan foydalanuvchi ulana oladi
    - Mijoz faqat o'zining buyurtmasini kuzata oladi
    - Haydovchi faqat unga tegishli buyurtmani kuzata oladi
    - Admin istalgan buyurtmani kuzata oladi

    Server tomonidan yuboriladigan xabar:
    {
        "type": "order.update",
        "order_id": 42,
        "status": "accepted",
        "status_display": "Haydovchi qabul qildi",
        "driver_name": "Alisher",
        "driver_phone": "+77001112233",
        "driver_car": "Cobalt — 01A111AA",
        "driver_car_color": "Oq",
        "driver_rating": 4.8,
        "final_price": null
    }
    """

    async def connect(self):
        user = self.scope.get("user")
        order_id = self.scope["url_route"]["kwargs"]["order_id"]

        # Autentifikatsiya tekshiruvi
        if not user or isinstance(user, AnonymousUser):
            logger.warning(f"WS ulanish rad etildi: autentifikatsiya yo'q, order #{order_id}")
            await self.close(code=4001)
            return

        # Buyurtmaga kirish huquqi tekshiruvi
        has_access = await self._check_access(user, int(order_id))
        if not has_access:
            logger.warning(f"WS ulanish rad etildi: {user.phone} order #{order_id} ga kirish yo'q")
            await self.close(code=4003)
            return

        self.order_id = order_id
        self.group_name = order_group_name(int(order_id))

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WS ulandi: {user.phone} → order #{order_id}")

        await self._send_current_status()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """ Mijozdan xabar kutilmaydi — faqat server habar yuboradi"""
        pass

    async def order_update(self, event):
        """
        services.py dan group_send orqali kelgan xabar.
        Ulanib turgan barcha clientlarga uzatiladi.
        """
        await self.send(text_data=json.dumps(event["data"]))

    async def location_update(self, event):
        """
        Haydovchi joylashuvi yangilanganda mijozga yuboriladi.
        """
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def _check_access(self, user, order_id: int) -> bool:
        try:
            order = Order.objects.select_related("driver__user").get(pk=order_id)
        except Order.DoesNotExist:
            return False

        if user.role == "admin":
            return True
        if user.role == "client":
            return order.client_id == user.id
        if user.role == "driver":
            return order.driver is not None and order.driver.user_id == user.id

        return False

    async def _send_current_status(self):
        """Ulanganida hozirgi buyurtma holatini yuboradi."""
        data = await self._get_order_data()
        if data:
            await self.send(text_data=json.dumps({"type": "order.update", **data}))

    @database_sync_to_async
    def _get_order_data(self) -> dict | None:
        try:
            order = Order.objects.select_related(
                "client", "driver__user"
            ).get(pk=self.order_id)
            return _build_order_payload(order)
        except Order.DoesNotExist:
            return None


class DriverOrdersConsumer(AsyncWebsocketConsumer):
    """
    Haydovchi yangi pending buyurtmalarni real vaqtda oladi.
    Buyurtma yaratilganda — server barcha ulangan haydovchilarga xabar yuboradi.

    Ulanish: wss://taxifast.uz/ws/driver/?token=eyJ...

    Server tomonidan yuboriladigan xabar:
    {
        "type": "new.order",
        "order_id": 42,
        "from_address": "Sayram bozori",
        "to_address": "Shymkent vokzali",
        "estimated_price": 1540,
        "distance_km": "12.40",
        "created_at": "2026-05-10T10:00:00Z"
    }
    """

    async def connect(self):
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        if user.role != "driver":
            await self.close(code=4003)
            return

        self.group_name = driver_group_name()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"Driver WS ulandi: {user.phone}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Haydovchidan xabar kutilmaydi
        pass

    async def new_order(self, event):
        """
        Yangi buyurtma yaratilganda barcha ulangan haydovchilarga yuboriladi.
        """
        await self.send(text_data=json.dumps(event["data"]))


def _build_order_payload(order: Order) -> dict:
    """REST serializer ishlatmasdan yengil dict yasaydi — WebSocket uchun."""
    driver = order.driver
    return {
        "order_id": order.pk,
        "status": order.status,
        "status_display": order.get_status_display(),
        "from_address": order.from_address,
        "to_address": order.to_address,
        "estimated_price": order.estimated_price,
        "final_price": order.final_price,
        "distance_km": str(order.distance_km) if order.distance_km else None,
        "driver_name": driver.user.full_name if driver else None,
        "driver_phone": driver.user.phone if driver else None,
        "driver_car": f"{driver.car_model} — {driver.car_number}" if driver else None,
        "driver_car_color": driver.car_color if driver else None,
        "driver_rating": float(driver.rating) if driver else None,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }
