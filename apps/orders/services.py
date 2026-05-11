import math
import logging
import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone
from django.db.models import F
from apps.users.models import DriverProfile

from .models import Order

logger = logging.getLogger(__name__)

BASE_PRICE = 300
PRICE_PER_KM = 100
MIN_PRICE = 300


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """To'g'ri chiziq masofa — Google Maps API ishlamasa fallback."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def get_distance_km(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
) -> float:
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return _haversine_km(from_lat, from_lon, to_lat, to_lon)

    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": f"{from_lat},{from_lon}",
                "destinations": f"{to_lat},{to_lon}",
                "mode": "driving",
                "key": api_key,
            },
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        element = data["rows"][0]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Google Maps element status: {element['status']}")
        return round(element["distance"]["value"] / 1000, 2)
    except Exception as exc:
        logger.error(f"Google Maps API xato: {exc} — haversine ishlatiladi.")
        return _haversine_km(from_lat, from_lon, to_lat, to_lon)


def calculate_price(distance_km: float) -> int:
    return max(int(BASE_PRICE + distance_km * PRICE_PER_KM), MIN_PRICE)


def estimate_route(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
) -> dict:
    distance_km = get_distance_km(from_lat, from_lon, to_lat, to_lon)
    return {
        "distance_km": distance_km,
        "estimated_price": calculate_price(distance_km),
    }


# ── WebSocket yordamchi funksiyalari ──────────────────────

def _notify_order_update(order: Order) -> None:
    """
    Buyurtma holati o'zgarganda barcha ulangan foydalanuvchilarga xabar yuboradi.
    Bu funksiya sinxron kod ichidan chaqiriladi (views.py, services.py).
    """
    from .consumers import order_group_name, _build_order_payload

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            order_group_name(order.pk),
            {
                "type": "order.update",
                "data": _build_order_payload(order),
            }
        )
    except Exception as e:
        # WebSocket xatosi butun so'rovni to'xtatmasin
        logger.error(f"WS notify xato order #{order.pk}: {e}")


def _notify_new_order(order: Order) -> None:
    """
    Yangi pending buyurtma yaratilganda barcha ulangan haydovchilarga xabar yuboradi.
    """
    from .consumers import driver_group_name

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            driver_group_name(),
            {
                "type": "new.order",
                "data": {
                    "type": "new.order",
                    "order_id": order.pk,
                    "from_address": order.from_address,
                    "to_address": order.to_address,
                    "estimated_price": order.estimated_price,
                    "distance_km": str(order.distance_km) if order.distance_km else None,
                    "created_at": order.created_at.isoformat(),
                }
            }
        )
    except Exception as e:
        logger.error(f"WS driver notify xato: {e}")


# ── Asosiy servis funksiyalari ────────────────────────────

def accept_order(order: Order, driver_profile) -> Order:
    order.driver = driver_profile
    order.status = Order.STATUS_ACCEPTED
    order.accepted_at = timezone.now()
    order.save(update_fields=["driver", "status", "accepted_at"])
    logger.info(f"Order #{order.pk} accepted by driver #{driver_profile.pk}")

    _notify_order_update(order)
    return order


def start_order(order: Order) -> Order:
    order.status = Order.STATUS_IN_PROGRESS
    order.save(update_fields=["status"])
    logger.info(f"Order #{order.pk} started")

    _notify_order_update(order)
    return order


def complete_order(order: Order) -> Order:
    if order.distance_km:
        distance_km = float(order.distance_km)
    else:
        distance_km = get_distance_km(
            float(order.from_lat), float(order.from_lon),
            float(order.to_lat), float(order.to_lon),
        )

    order.status = Order.STATUS_COMPLETED
    order.completed_at = timezone.now()
    order.distance_km = distance_km
    order.final_price = calculate_price(distance_km)
    order.save(update_fields=["status", "completed_at", "distance_km", "final_price"])

    DriverProfile.objects.filter(pk=order.driver.pk).update(
        total_trips=F("total_trips") + 1
    )


    logger.info(
        f"Order #{order.pk} completed. "
        f"Price: {order.final_price} tenge, distance: {distance_km} km"
    )

    _notify_order_update(order)
    return order


def cancel_order(order: Order) -> Order:
    order.status = Order.STATUS_CANCELLED
    order.save(update_fields=["status"])
    logger.info(f"Order #{order.pk} cancelled")

    _notify_order_update(order)
    return order


def notify_new_order_created(order: Order) -> None:
    """
    views.py dan chaqiriladi — yangi buyurtma yaratilganida haydovchilarga xabar.
    """
    _notify_new_order(order)
