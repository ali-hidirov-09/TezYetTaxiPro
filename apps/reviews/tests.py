from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import DriverProfile
from apps.orders.models import Order
from .models import Review
import uuid
User = get_user_model()


def make_client(phone="+77001110010"):
    return User.objects.create_user(
        phone=phone, full_name="Ali Karimov", role="client", is_active=True
    )


def make_driver(phone="+77001110011"):
    user = User.objects.create_user(
        phone=phone, full_name="Haydovchi Test", role="driver", is_active=True
    )
    profile = DriverProfile.objects.create(
        user=user, car_model="Cobalt", car_number=f"TEST{uuid.uuid4().hex[:6].upper()}",
    )
    return user, profile


def make_completed_order(client, driver_profile):
    return Order.objects.create(
        client=client,
        driver=driver_profile,
        from_address="A", from_lat="42.3", from_lon="69.7",
        to_address="B", to_lat="42.4", to_lon="69.6",
        estimated_price=600,
        final_price=600,
        distance_km="10.00",
        status=Order.STATUS_COMPLETED,
    )


class CreateReviewTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.client_user = make_client()
        _, self.driver_profile = make_driver()
        self.order = make_completed_order(self.client_user, self.driver_profile)
        self.api.force_authenticate(user=self.client_user)

    def test_create_success(self):
        res = self.api.post("/api/reviews/", {
            "order_id": self.order.pk, "rating": 5, "comment": "Zo'r!",
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["rating"], 5)

    def test_client_name_only_first_name(self):
        res = self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 4})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Familiya ko'rinmasligi kerak — faqat "Ali"
        self.assertEqual(res.data["client_name"], "Ali")
        self.assertNotIn("Karimov", res.data["client_name"])

    def test_driver_rating_recalculated(self):
        self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 4})
        self.driver_profile.refresh_from_db()
        self.assertEqual(float(self.driver_profile.rating), 4.0)

    def test_pending_order_returns_400(self):
        pending = Order.objects.create(
            client=self.client_user,
            from_address="A", from_lat="42.3", from_lon="69.7",
            to_address="B", to_lat="42.4", to_lon="69.6",
            estimated_price=600, status=Order.STATUS_PENDING,
        )
        res = self.api.post("/api/reviews/", {"order_id": pending.pk, "rating": 4})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_review_returns_409(self):
        self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 5})
        res = self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 3})
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_other_client_returns_403(self):
        other = make_client(phone="+77001110099")
        self.api.force_authenticate(user=other)
        res = self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 5})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_rating_returns_400(self):
        res = self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 6})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_401(self):
        self.api.force_authenticate(user=None)
        res = self.api.post("/api/reviews/", {"order_id": self.order.pk, "rating": 5})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class DriverReviewListTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.anon_api = APIClient()
        self.client_user = make_client()
        _, self.driver_profile = make_driver()
        order = make_completed_order(self.client_user, self.driver_profile)
        Review.objects.create(
            order=order, client=self.client_user,
            driver=self.driver_profile, rating=5, comment="Ajoyib!",
        )

    def test_list_paginated_no_auth(self):
        res = self.anon_api.get(f"/api/reviews/driver/{self.driver_profile.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_reviews", res.data["results"])
        self.assertIn("rating", res.data["results"])
        self.assertIn("reviews", res.data["results"])

    def test_client_name_is_first_name_only(self):
        res = self.api.get(f"/api/reviews/driver/{self.driver_profile.pk}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        reviews = res.data.get("results", {}).get("reviews", [])
        if reviews:
            self.assertNotIn("Karimov", reviews[0]["client_name"])

    def test_nonexistent_driver_returns_404(self):
        res = self.api.get("/api/reviews/driver/99999/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_reviews(self):
        _, new_driver = make_driver(phone="+77001110020")
        res = self.api.get(f"/api/reviews/driver/{new_driver.pk}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
