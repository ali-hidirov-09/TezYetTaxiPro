from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Telefon raqami kiritilishi shart")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    ROLE_CLIENT = "client"
    ROLE_DRIVER = "driver"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_CLIENT, "Mijoz"),
        (ROLE_DRIVER, "Haydovchi"),
        (ROLE_ADMIN, "Admin"),
    ]

    phone = models.CharField(max_length=15, unique=True)
    full_name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    is_active = models.BooleanField(default=False)  # OTP tasdiqlanguncha False
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class DriverProfile(models.Model):
    """Haydovchi qo'shimcha ma'lumotlari — faqat admin yaratadi."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="driver_profile"
    )
    car_model = models.CharField(max_length=100)
    car_number = models.CharField(max_length=20, unique=True)
    car_color = models.CharField(max_length=50, blank=True, default="")
    is_available = models.BooleanField(default=False)
    current_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    total_trips = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "driver_profiles"
        verbose_name = "Haydovchi profili"
        verbose_name_plural = "Haydovchi profillari"

    def __str__(self):
        return f"{self.user.full_name} — {self.car_number}"
