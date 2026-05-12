from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


def health_check(request):
    checks = {"status": "ok", "db": "ok", "cache": "ok"}

    try:
        connection.ensure_connection()
    except Exception:
        checks["db"] = "error"
        checks["status"] = "degraded"

    try:
        cache.set("health_check_ping", "1", timeout=5)
        if cache.get("health_check_ping") != "1":
            raise ValueError("Cache read/write mismatch")
    except Exception:
        checks["cache"] = "error"
        checks["status"] = "degraded"

    http_status = 200 if checks["status"] == "ok" else 503
    return JsonResponse(checks, status=http_status)


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),

    path("api/users/", include("apps.users.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/reviews/", include("apps.reviews.urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("", RedirectView.as_view(url="/swagger/"), name="home"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),		
]
