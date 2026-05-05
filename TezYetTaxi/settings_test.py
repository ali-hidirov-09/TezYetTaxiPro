"""
Test muhiti uchun settings.
SQLite in-memory, LocMemCache, SMS o'chirilgan, throttling yo'q.
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,testserver")
os.environ.setdefault("POSTGRES_PASSWORD", "test")

from .settings import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SMS_SKIP_IN_DEV = True
GOOGLE_MAPS_API_KEY = ""

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# Tezlashtirilgan parol hash
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# HTTPS sozlamalari testda kerak emas, shuning uchun False qilamiz
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
