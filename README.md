# TezYet Taxi API

Sayram  tumani uchun mahalliy taxi platformasi backend API si.

---

## Texnologiyalar

| Texnologiya            | Versiya | Maqsad                                  |
|------------------------|---------|-----------------------------------------|
| Python                 | 3.12    | Asosiy til                              |
| Django                 | 5.2     | Web framework                           |
| Django REST Framework  | 3.16    | API                                     |
| Simple JWT             | 5.5     | Autentifikatsiya + Logout (blacklist)   |
| drf-spectacular        | 0.29    | Swagger / OpenAPI                       |
| Redis                  | 7       | OTP saqlash (TTL)                       |
| Infobip                | —       | SMS yuborish (KZ + UZB)                 |
| Google Maps API        | —       | Masofa hisoblash (fallback: haversine)  |
| Docker + Nginx         | —       | Deploy                                  |
| GitHub Actions         | —       | CI/CD                                   |

---

## Tuzilma

```
TezYet/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Test + lint + docker build
│       └── deploy.yml      # SSH orqali server deploy
├── TezYetTaxi/
│   ├── settings.py         # Asosiy sozlamalar
│   ├── settings_test.py    # Test muhiti (in-memory DB, LocMemCache)
│   ├── urls.py             # URL router + health check
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── users/              # Auth, profil, haydovchi, admin
│   ├── orders/             # Buyurtmalar, narx hisoblash, safar oqimi
│   └── reviews/            # Reytinglar
├── nginx/
│   └── nginx.conf          # Production nginx config
├── docker-compose.yml      # Development
├── docker-compose.prod.yml # Production (nginx bilan)
├── Dockerfile
├── entrypoint.sh           # migrate + collectstatic + gunicorn
├── requirements.txt
├── requirements-dev.txt    # + coverage
├── .env                    # Development (gitignore'da)
└── .env.example            # Yangi developer uchun shablon
```

---

## Ishga tushirish (Development)

### 1. `.env` tayyorlash

```bash
cp .env.example .env
# .env ni oching va qiymatlarni to'ldiring
```

### 2. Docker bilan ishga tushirish

```bash
docker-compose up --build
```

### 3. Migratsiya va superuser

```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### 4. Testlarni ishlatish

```bash
# Oddiy
docker-compose exec web python manage.py test apps.users apps.orders apps.reviews -v 2

# Coverage bilan
docker-compose exec web bash -c "
  DJANGO_SETTINGS_MODULE=TezYetTaxi.settings_test \
  coverage run manage.py test apps.users apps.orders apps.reviews -v 2 && \
  coverage report
"
```

### 5. Swagger

```
http://localhost:8000/swagger/
http://localhost:8000/redoc/
http://localhost:8000/health/
```

---

## Rollar

| Rol      | Kim                    | Qanday qo'shiladi                               |
|----------|------------------------|-------------------------------------------------|
| `client` | Taxi buyurtma beruvchi | `/api/users/auth/register/` orqali o'zi         |
| `driver` | Haydovchi              | Faqat admin: `/api/users/admin/drivers/create/` |
| `admin`  | Tizim boshqaruvchisi   | `createsuperuser` yoki admin panel              |

---

## API Endpointlar

### Auth

| Method | URL                              | Tavsif                                 | Login |
|--------|----------------------------------|----------------------------------------|-------|
| POST   | `/api/users/auth/send-otp/`      | OTP yuborish                           | Yo'q  |
| POST   | `/api/users/auth/register/`      | Yangi mijoz ro'yxatdan o'tish          | Yo'q  |
| POST   | `/api/users/auth/verify-otp/`    | Mavjud foydalanuvchi kirishi           | Yo'q  |
| POST   | `/api/users/auth/token/refresh/` | Access tokenni yangilash               | Yo'q  |
| POST   | `/api/users/auth/logout/`        | Chiqish (refresh tokenni bekor qilish) | Ha    |

### Profil

| Method | URL              | Tavsif           | Kim     |
|--------|------------------|------------------|---------|
| GET    | `/api/users/me/` | Profilni ko'rish | Hammasi |
| PATCH  | `/api/users/me/` | Ism tahrirlash   | Hammasi |

### Haydovchi

| Method | URL                           | Tavsif              | Kim    |
|--------|-------------------------------|---------------------|--------|
| GET    | `/api/users/driver/profile/`  | Profil              | Driver |
| PATCH  | `/api/users/driver/location/` | Joylashuv yangilash | Driver |

### Admin

| Method | URL                                          | Tavsif                  | Kim   |
|--------|----------------------------------------------|-------------------------|-------|
| GET    | `/api/users/admin/users/`                    | Barcha foydalanuvchilar | Admin |
| POST   | `/api/users/admin/users/{id}/toggle-active/` | Bloklash/faollashtirish | Admin |
| GET    | `/api/users/admin/drivers/`                  | Barcha haydovchilar     | Admin |
| POST   | `/api/users/admin/drivers/create/`           | Haydovchi qo'shish      | Admin |

### Buyurtmalar

| Method | URL                             | Tavsif              | Kim             |
|--------|---------------------------------|---------------------|-----------------|
| POST   | `/api/orders/estimate/`         | Narx taxmini        | Login qilganlar |
| GET    | `/api/orders/`                  | O'z tarixi          | Client          |
| POST   | `/api/orders/`                  | Yangi buyurtma      | Client          |
| GET    | `/api/orders/{id}/`             | Tafsilot            | Client / Driver |
| POST   | `/api/orders/{id}/cancel/`      | Bekor qilish        | Client          |
| GET    | `/api/orders/driver/available/` | Pending buyurtmalar | Driver          |
| GET    | `/api/orders/driver/my/`        | O'z safarlar        | Driver          |
| POST   | `/api/orders/{id}/accept/`      | Qabul qilish        | Driver          |
| POST   | `/api/orders/{id}/start/`       | Safarni boshlash    | Driver          |
| POST   | `/api/orders/{id}/complete/`    | Safarni yakunlash   | Driver          |
| GET    | `/api/orders/admin/all/`        | Barchasi + filter   | Admin           |

### Reytinglar

| Method | URL                         | Tavsif                | Kim     |
|--------|-----------------------------|-----------------------|---------|
| POST   | `/api/reviews/`             | Baho berish           | Client  |
| GET    | `/api/reviews/driver/{id}/` | Haydovchi reytinglari | Hammaga |

### Boshqa

| Method | URL        | Tavsif                 |
|--------|------------|------------------------|
| GET    | `/health/` | Server holati (200 OK) |

---

## Frontend uchun — Auth oqimi

### Yangi foydalanuvchi

```
1. POST /api/users/auth/send-otp/
   Body:  { "phone": "+77001234567" }
   Javob: { "detail": "Kod yuborildi", "is_registered": false }

2. POST /api/users/auth/register/
   Body:  { "phone": "+77001234567", "full_name": "Ali Karimov", "code": "123456" }
   Javob: { "access": "...", "refresh": "...", "role": "client" }
```

### Mavjud foydalanuvchi

```
1. POST /api/users/auth/send-otp/
   Javob: { "detail": "Kod yuborildi", "is_registered": true }

2. POST /api/users/auth/verify-otp/
   Body:  { "phone": "+77001234567", "code": "123456" }
   Javob: { "access": "...", "refresh": "...", "role": "client" }
```

### Keyingi so'rovlarda

```
Header: Authorization: Bearer <access_token>
```

### Token yangilash

```
POST /api/users/auth/token/refresh/
Body:  { "refresh": "<refresh_token>" }
Javob: { "access": "<yangi_access_token>" }
```

### Chiqish

```
POST /api/users/auth/logout/
Body:  { "refresh": "<refresh_token>" }
```

> Access token — 30 daqiqa. Refresh token — 7 kun.

---

## Buyurtma oqimi

```
[Mijoz]                              [Haydovchi]
   |                                      |
   | POST /orders/estimate/               |
   | ← { distance_km, estimated_price }   |
   |                                      |
   | POST /orders/                        |
   | ← { id, status: "pending" }          |
   |                                      |
   |                 GET /orders/driver/available/
   |                 ← [ ...pending orders ]
   |                                      |
   |                 POST /orders/{id}/accept/
   |                 ← { detail, order_id }
   |                                      |
   |                 POST /orders/{id}/start/
   |                                      |
   |                 POST /orders/{id}/complete/
   |                 ← { final_price, distance_km }
   |                                      |
   | POST /reviews/                       |
   | { order_id, rating, comment }        |
   | ← { id, rating, ... }               |
```

---

## Narx formulasi

```
Narx (tenge) = 300 + (km × 100)
Minimum: 300 tenge

Misol: 10 km → 1300 tenge
       5 km  → 800 tenge
       1 km  → 400 tenge
```

Google Maps API kalit bo'lsa — haqiqiy yo'l masofasi.
Bo'lmasa — haversine (to'g'ri chiziq, taxminiy).

---

## OTP mexanizmi

| Parametr                | Qiymat                                 |
|-------------------------|----------------------------------------|
| Kod uzunligi            | 6 xona                                 |
| Amal qilish muddati     | 2 daqiqa                               |
| Qayta yuborish cooldown | 60 sekund                              |
| Bir martalik            | Ha (tekshirilgandan keyin o'chadi)     |
| Dev rejimida            | SMS yuborilmaydi, Docker logga chiqadi |

---

## CI/CD

**GitHub Actions** `.github/workflows/ci.yml`:
- Har `push` da test + lint + docker build
- Test muvaffaqiyatli bo'lmasa — merge bloklanadi

**Deploy** `.github/workflows/deploy.yml`:
- `main` ga push bo'lganda SSH orqali serverga avtomatik deploy

### GitHub Secrets (Settings → Secrets → Actions):

| Secret           | Qiymat                                |
|------------------|---------------------------------------|
| `SERVER_HOST`    | Server IP yoki domain                 |
| `SERVER_USER`    | SSH foydalanuvchi (masalan: `ubuntu`) |
| `SERVER_SSH_KEY` | SSH private key                       |

---

## Production Deploy

### Server tayyorlash (birinchi marta)

```bash
# Server da:
git clone https://github.com/username/tezyettaxi.git /opt/tezyettaxi
cd /opt/tezyettaxi
cp .env.example .env
# .env ni to'ldiring (DEBUG=False, real kalitlar)

docker compose -f docker-compose.prod.yml up -d --build
```

### `.env` production uchun

```
DEBUG=False
SECRET_KEY=<python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
SMS_SKIP_IN_DEV=False
INFOBIP_API_KEY=real_key
GOOGLE_MAPS_API_KEY=real_key
```

### Keyingi deploylar (avtomatik)

`main` branchga push qilish yetarli — GitHub Actions o'zi deploy qiladi.

---

## Xavfsizlik

- JWT Bearer token autentifikatsiya
- Refresh token blacklist (logout qilgandan keyin token ishlamaydi)
- Rol asosida ruxsat (IsClient, IsDriver, IsAdminUser)
- OTP cooldown — brute-force dan himoya
- CORS: dev da ochiq, prod da `CORS_ALLOWED_ORIGINS` bilan cheklangan
- Throttling: anonim 30/min, foydalanuvchi 200/min
