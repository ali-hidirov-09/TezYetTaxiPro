from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id", "client", "driver", "status",
        "estimated_price", "final_price", "distance_km", "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["client__phone", "client__full_name", "from_address", "to_address"]
    raw_id_fields = ["client", "driver"]
    readonly_fields = ["created_at", "accepted_at", "completed_at"]
    ordering = ["-created_at"]
