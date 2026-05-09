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

echo "==> Server ishga tushmoqda..."
WORKERS=${GUNICORN_WORKERS:-3}
exec gunicorn TezYetTaxi.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "$WORKERS" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
