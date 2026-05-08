from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import DriverProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["phone", "full_name", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["phone", "full_name"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Ma'lumotlar", {"fields": ("full_name", "role")}),
        ("Ruxsatlar", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "full_name", "role", "password1", "password2"),
        }),
    )


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "car_number", "car_model", "car_color", "is_available", "rating", "total_trips"]
    list_filter = ["is_available"]
    search_fields = ["user__phone", "user__full_name", "car_number"]
    raw_id_fields = ["user"]
