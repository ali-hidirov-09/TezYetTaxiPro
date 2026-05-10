"""
Bu tests fayli kodlar qanchalik to'g'ri ishlayotgani va kod o'zgartirganda xar
safar swaggerga kirirb o'tirmay python manage.py tests qilib
 tezroq sinab ko'rish uchun yozilgan
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import DriverProfile
from apps.orders.services import calculate_price, _haversine_km
from .models import Order
import uuid
User = get_user_model()


def make_client(phone="+77001110001"):
    return User.objects.create_user(phone=phone, full_name="Mijoz Test", role="client", is_active=True)


def make_driver(phone="+77001110002"):
    user = User.objects.create_user(phone=phone, full_name="Haydovchi Test", role="driver", is_active=True)
    profile = DriverProfile.objects.create(user=user, car_model="Cobalt",  car_number=f"TEST{uuid.uuid4().hex[:6].upper()}", is_available=True)
    return user, profile


def make_admin(phone="+77000000001"):
    return User.objects.create_user(phone=phone, full_name="Admin", role="admin", is_active=True, is_staff=True)


ORDER_PAYLOAD = {
    "from_address": "Sayram bozori",
    "from_lat": "42.308800", "from_lon": "69.737200",
    "to_address": "Shymkent vokzali",
    "to_lat": "42.340000", "to_lon": "69.600000",
}


class ServiceTests(TestCase):

    def test_min_price_enforced(self):
        self.assertEqual(calculate_price(0), 300)

    def test_price_formula(self):
        self.assertEqual(calculate_price(10), 1300)

    def test_haversine_positive(self):
        km = _haversine_km(42.3088, 69.7372, 42.3400, 69.6000)
        self.assertGreater(km, 0)

    def test_haversine_same_point(self):
        self.assertEqual(_haversine_km(42.3, 69.7, 42.3, 69.7), 0.0)


class EstimatePriceTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=make_client())

    def test_returns_price_and_distance(self):
        res = self.api.post("/api/orders/estimate/", {
            "from_lat": "42.308800", "from_lon": "69.737200",
            "to_lat": "42.340000", "to_lon": "69.600000",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data["estimated_price"], 300)


class CreateOrderTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.client_user = make_client()
        self.api.force_authenticate(user=self.client_user)

    def test_create_success(self):
        res = self.api.post("/api/orders/", ORDER_PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "pending")

    def test_same_coordinates_rejected(self):
        payload = {**ORDER_PAYLOAD, "to_lat": ORDER_PAYLOAD["from_lat"], "to_lon": ORDER_PAYLOAD["from_lon"]}
        res = self.api.post("/api/orders/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_active_order_rejected(self):
        self.api.post("/api/orders/", ORDER_PAYLOAD)
        res = self.api.post("/api/orders/", ORDER_PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_driver_cannot_create_order(self):
        driver_user, _ = make_driver()
        self.api.force_authenticate(user=driver_user)
        res = self.api.post("/api/orders/", ORDER_PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class OrderListPaginationTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.client_user = make_client()
        self.api.force_authenticate(user=self.client_user)

    def test_list_returns_paginated_response(self):
        self.api.post("/api/orders/", ORDER_PAYLOAD)
        res = self.api.get("/api/orders/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Pagination formatini tekshirish
        self.assertIn("results", res.data)
        self.assertIn("count", res.data)
        self.assertIn("next", res.data)


class CancelOrderTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.client_user = make_client()
        self.api.force_authenticate(user=self.client_user)
        res = self.api.post("/api/orders/", ORDER_PAYLOAD)
        self.order_id = res.data["id"]

    def test_cancel_pending(self):
        res = self.api.post(f"/api/orders/{self.order_id}/cancel/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(Order.objects.get(pk=self.order_id).status, Order.STATUS_CANCELLED)

    def test_cancel_completed_returns_400(self):
        Order.objects.filter(pk=self.order_id).update(status=Order.STATUS_COMPLETED)
        res = self.api.post(f"/api/orders/{self.order_id}/cancel/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_client_cannot_cancel(self):
        other = make_client(phone="+77001119998")
        self.api.force_authenticate(user=other)
        res = self.api.post(f"/api/orders/{self.order_id}/cancel/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class DriverFlowTests(TestCase):

    def setUp(self):
        self.client_user = make_client()
        self.driver_user, self.driver_profile = make_driver()
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.client_user)
        self.driver_api = APIClient()
        self.driver_api.force_authenticate(user=self.driver_user)
        res = self.client_api.post("/api/orders/", ORDER_PAYLOAD)
        self.order_id = res.data["id"]

    def test_driver_sees_pending_orders(self):
        res = self.driver_api.get("/api/orders/driver/available/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [o["id"] for o in res.data["results"]]
        self.assertIn(self.order_id, ids)

    def test_full_trip_flow(self):
        self.assertEqual(self.driver_api.post(f"/api/orders/{self.order_id}/accept/").status_code, 200)
        self.assertEqual(self.driver_api.post(f"/api/orders/{self.order_id}/start/").status_code, 200)
        res = self.driver_api.post(f"/api/orders/{self.order_id}/complete/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("final_price", res.data)

        order = Order.objects.get(pk=self.order_id)
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.driver_profile.refresh_from_db()
        self.assertEqual(self.driver_profile.total_trips, 1)

    def test_two_drivers_cannot_accept_same_order(self):
        driver2, _ = make_driver(phone="+77001110003")
        api2 = APIClient()
        api2.force_authenticate(user=driver2)
        self.driver_api.post(f"/api/orders/{self.order_id}/accept/")
        res = api2.post(f"/api/orders/{self.order_id}/accept/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_without_start_returns_400(self):
        self.driver_api.post(f"/api/orders/{self.order_id}/accept/")
        res = self.driver_api.post(f"/api/orders/{self.order_id}/complete/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class AdminOrderTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        admin = make_admin()
        self.api.force_authenticate(user=admin)
        client_user = make_client()
        client_api = APIClient()
        client_api.force_authenticate(user=client_user)
        client_api.post("/api/orders/", ORDER_PAYLOAD)

    def test_admin_sees_paginated_orders(self):
        res = self.api.get("/api/orders/admin/all/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        self.assertIn("count", res.data)

    def test_filter_by_status(self):
        res = self.api.get("/api/orders/admin/all/?status=pending")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for o in res.data["results"]:
            self.assertEqual(o["status"], "pending")
