"""
Bu tests fayli kodlar qanchalik to'g'ri ishlayotgani va kod o'zgartirganda xar
safar swaggerga kirirb o'tirmay python manage.py tests qilib
 tezroq sinab ko'rish uchun yozilgan
"""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import DriverProfile
from apps.users.otp_service import generate_otp, verify_otp, get_remaining_seconds, is_blocked
import uuid
User = get_user_model()


def make_client(phone="+77001110001", name="Mijoz Test"):
    return User.objects.create_user(phone=phone, full_name=name, role="client", is_active=True)


def make_driver(phone="+77001110002"):
    user = User.objects.create_user(phone=phone, full_name="Haydovchi Test", role="driver", is_active=True)
    profile = DriverProfile.objects.create(user=user, car_model="Cobalt", car_number=f"TEST{uuid.uuid4().hex[:6].upper()}", is_available=True)
    return user, profile


def make_admin(phone="+77000000001"):
    return User.objects.create_user(phone=phone, full_name="Admin", role="admin", is_active=True, is_staff=True)


# ─── OTP Service ──────────────────────────────────────────────────────────────

class OtpServiceTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_generate_6_digit_code(self):
        code = generate_otp("+77001234567")
        self.assertIsNotNone(code)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_cooldown_blocks_second_call(self):
        generate_otp("+77001234567")
        self.assertIsNone(generate_otp("+77001234567"))

    def test_verify_correct_code(self):
        code = generate_otp("+77001234567")
        self.assertTrue(verify_otp("+77001234567", code))

    def test_verify_wrong_code(self):
        generate_otp("+77001234567")
        self.assertFalse(verify_otp("+77001234567", "000000"))

    def test_code_single_use(self):
        code = generate_otp("+77001234567")
        verify_otp("+77001234567", code)
        self.assertFalse(verify_otp("+77001234567", code))

    def test_brute_force_blocks_after_max_attempts(self):
        generate_otp("+77001234567")
        for _ in range(5):
            verify_otp("+77001234567", "000000")
        self.assertTrue(is_blocked("+77001234567"))
        # Bloklangandan keyin to'g'ri kod ham ishlamaydi
        code = generate_otp("+77001234568")
        self.assertFalse(verify_otp("+77001234567", code if code else "123456"))

    def test_new_otp_clears_attempts(self):
        phone = "+77001234569"
        generate_otp(phone)
        for _ in range(3):
            verify_otp(phone, "000000")
        # Yangi OTP yaratilganda urinishlar tozalanadi
        cache.delete(f"otp_cooldown:{phone}")  # cooldown ni bypass (test uchun)
        generate_otp(phone)
        self.assertFalse(is_blocked(phone))

    def test_remaining_seconds_no_crash(self):
        generate_otp("+77001234567")
        remaining = get_remaining_seconds("+77001234567")
        self.assertGreaterEqual(remaining, 0)


# ─── Send OTP ─────────────────────────────────────────────────────────────────

class SendOtpTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        cache.clear()

    @patch("apps.users.views.send_otp_sms", return_value=True)
    @patch("apps.users.views.generate_otp", return_value="123456")
    def test_new_user_is_registered_false(self, *_):
        res = self.api.post("/api/users/auth/send-otp/", {"phone": "+77001234567"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_registered"])

    @patch("apps.users.views.send_otp_sms", return_value=True)
    @patch("apps.users.views.generate_otp", return_value="123456")
    def test_existing_user_is_registered_true(self, *_):
        User.objects.create_user(phone="+77001234567", full_name="Test")
        res = self.api.post("/api/users/auth/send-otp/", {"phone": "+77001234567"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_registered"])

    @patch("apps.users.views.generate_otp", return_value=None)
    def test_cooldown_returns_429(self, _):
        res = self.api.post("/api/users/auth/send-otp/", {"phone": "+77001234567"})
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_phone_without_plus_returns_400(self):
        res = self.api.post("/api/users/auth/send-otp/", {"phone": "77001234567"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.send_otp_sms", return_value=False)
    @patch("apps.users.views.generate_otp", return_value="123456")
    def test_sms_failure_returns_503(self, *_):
        res = self.api.post("/api/users/auth/send-otp/", {"phone": "+77001234567"})
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# ─── Register ─────────────────────────────────────────────────────────────────

class RegisterTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        cache.clear()

    @patch("apps.users.views.verify_otp", return_value=True)
    def test_register_success(self, _):
        res = self.api.post("/api/users/auth/register/", {
            "phone": "+77001234567", "full_name": "Ali Karimov", "code": "123456",
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", res.data)
        self.assertEqual(res.data["role"], "client")
        self.assertTrue(User.objects.filter(phone="+77001234567").exists())

    @patch("apps.users.views.verify_otp", return_value=False)
    def test_wrong_otp_returns_400(self, _):
        res = self.api.post("/api/users/auth/register/", {
            "phone": "+77001234567", "full_name": "Ali", "code": "000000",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.verify_otp", return_value=True)
    def test_duplicate_phone_returns_400(self, _):
        User.objects.create_user(phone="+77001234567", full_name="Ali")
        res = self.api.post("/api/users/auth/register/", {
            "phone": "+77001234567", "full_name": "Ali", "code": "123456",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        cache.clear()
        self.user = User.objects.create_user(phone="+77001234567", full_name="Test", is_active=True)

    @patch("apps.users.views.verify_otp", return_value=True)
    def test_login_returns_tokens(self, _):
        res = self.api.post("/api/users/auth/verify-otp/", {"phone": "+77001234567", "code": "123456"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("role", res.data)

    @patch("apps.users.views.verify_otp", return_value=False)
    def test_wrong_code_returns_400(self, _):
        res = self.api.post("/api/users/auth/verify-otp/", {"phone": "+77001234567", "code": "000000"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.users.views.verify_otp", return_value=True)
    def test_nonexistent_phone_returns_404(self, _):
        res = self.api.post("/api/users/auth/verify-otp/", {"phone": "+77009999999", "code": "123456"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


# ─── Logout ───────────────────────────────────────────────────────────────────

class LogoutTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.user = make_client()

    def test_logout_with_valid_refresh(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        self.api.force_authenticate(user=self.user)
        res = self.api.post("/api/users/auth/logout/", {"refresh": str(refresh)})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_logout_without_token_returns_400(self):
        self.api.force_authenticate(user=self.user)
        res = self.api.post("/api/users/auth/logout/", {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Me ───────────────────────────────────────────────────────────────────────

class MeTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.user = make_client()
        self.api.force_authenticate(user=self.user)

    def test_get_profile(self):
        res = self.api.get("/api/users/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["phone"], "+77001110001")

    def test_patch_full_name(self):
        res = self.api.patch("/api/users/me/", {"full_name": "Yangi Ism"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Yangi Ism")

    def test_cannot_change_role_via_patch(self):
        self.api.patch("/api/users/me/", {"role": "admin"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "client")

    def test_unauthenticated_returns_401(self):
        self.api.force_authenticate(user=None)
        res = self.api.get("/api/users/me/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── Driver Location ──────────────────────────────────────────────────────────

class DriverLocationTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        driver_user, self.profile = make_driver()
        self.api.force_authenticate(user=driver_user)

    def test_update_location(self):
        res = self.api.patch("/api/users/driver/location/", {
            "lat": "42.308800", "lon": "69.737200", "is_available": True,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_available)

    def test_client_cannot_update_location(self):
        client_user = make_client(phone="+77001119997")
        self.api.force_authenticate(user=client_user)
        res = self.api.patch("/api/users/driver/location/", {"lat": "42.3", "lon": "69.7"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


# ─── Admin ────────────────────────────────────────────────────────────────────

class AdminTests(TestCase):

    def setUp(self):
        self.api = APIClient()
        self.admin = make_admin()
        self.api.force_authenticate(user=self.admin)

    def test_create_driver_success(self):
        res = self.api.post("/api/users/admin/drivers/create/", {
            "phone": "+77001112233", "full_name": "Haydovchi Ism",
            "car_model": "Cobalt", "car_number": "01A123BC", "car_color": "Oq",
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(phone="+77001112233", role="driver").exists())

    def test_list_users_paginated(self):
        make_client()
        res = self.api.get("/api/users/admin/users/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        self.assertIn("count", res.data)

    def test_toggle_user_active(self):
        user = make_client(phone="+77001119999")
        res = self.api.post(f"/api/users/admin/users/{user.pk}/toggle-active/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_client_cannot_access_admin(self):
        client_user = make_client(phone="+77001119996")
        self.api.force_authenticate(user=client_user)
        res = self.api.get("/api/users/admin/users/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_toggle_nonexistent_returns_404(self):
        res = self.api.post("/api/users/admin/users/99999/toggle-active/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
