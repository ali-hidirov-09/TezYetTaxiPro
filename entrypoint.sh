#!/bin/sh
set -e

echo "==> DB tayyor bo'lishini kutamiz..."
python manage.py check --database default 2>/dev/null || {
    echo "DB ulanishi tekshirilmoqda..."
    sleep 3
    python manage.py check --database default
}

echo "==> Migrations..."
python manage.py migrate --noinput

echo "==> Static files..."
python manage.py collectstatic --noinput

echo "==> Server ishga tushmoqda (Daphne ASGI)..."
exec daphne \
    -b 0.0.0.0 \
    -p 8000 \
    --access-log - \
    --proxy-headers \
    TezYetTaxi.asgi:application
