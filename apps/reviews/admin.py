from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "client", "driver", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["client__phone", "client__full_name", "driver__user__full_name"]
    raw_id_fields = ["order", "client", "driver"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
