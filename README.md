# TezYet Taxi API

Sayram tumani uchun mahalliy taxi platformasi — backend API.

---

## Texnologiyalar

| Texnologiya          | Versiya | Maqsad                                       |
|----------------------|---------|----------------------------------------------|
| Python               | 3.11    | Asosiy til                                   |
| Django               | 5.1.3   | Web framework                                |
| Django REST Framework| 3.16    | REST API                                     |
| Django Channels      | 4.1     | WebSocket (real-time)                        |
| Daphne               | 4.1     | ASGI server (HTTP + WebSocket)               |
| Simple JWT           | 5.3     | Autentifikatsiya + Logout (blacklist)        |
| drf-spectacular      | 0.27    | Swagger / OpenAPI hujjatlash                 |
| PostgreSQL           | 16      | Asosiy baza                                  |
| Redis                | 7       | OTP saqlash (TTL) + WebSocket channel layer  |
| Infobip              | —       | SMS yuborish (UZB + KZ)                      |
| Google Maps API      | —       | Masofa hisoblash (fallback: haversine)       |
| WhiteNoise           | 6.7     | Static fayllar                               |
| Docker + Nginx       | —       | Deploy                                       |
| GitHub Actions       | —       | CI/CD                                        |
| Sentry               | 2.14    | Xatolarni kuzatish (ixtiyoriy)               |

---

## Loyiha tuzilmasi

```
TezYetTaxiPro/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Test + lint + docker build
│       └── deploy.yml          # SSH orqali server deploy
├── TezYetTaxi/
│   ├── settings.py             # Asosiy sozlamalar
│   ├── settings_test.py        # Test muhiti (SQLite, LocMemCache)
│   ├── urls.py                 # URL router + health check
│   ├── asgi.py                 # ASGI — HTTP + WebSocket
│   └── wsgi.py
├── apps/
│   ├── users/                  # Auth, profil, haydovchi, admin
│   ├── orders/                 # Buyurtmalar, WebSocket consumers
│   └── reviews/                # Reytinglar
├── nginx/
│   ├── nginx.conf              # Docker nginx config (SSL)
│   └── nginx_host.conf         # Host nginx config (server da ishlatiladi)
├── docker-compose.yml          # Development
├── docker-compose.server.yml   # Production (host nginx bilan)
├── docker-compose.prod.yml     # Production (docker nginx bilan)
├── Dockerfile
├── entrypoint.sh               # migrate + collectstatic + daphne
├── requirements.txt
├── requirements-dev.txt        # + coverage, test tools
├── .env.example                # Yangi developer uchun shablon
└── .env                        # Development (gitignore da)
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
docker compose up -d --build
```

### 3. Superuser yaratish

```bash
docker compose exec web python manage.py createsuperuser
```

### 4. Testlarni ishlatish

```bash
# Oddiy
docker compose exec web python manage.py test apps.users apps.orders apps.reviews -v 2

# Coverage bilan
docker compose exec web bash -c "
  DJANGO_SETTINGS_MODULE=TezYetTaxi.settings_test \
  coverage run manage.py test apps.users apps.orders apps.reviews -v 2 && \
  coverage report
"
```

### 5. Swagger va health check

```
http://localhost:8000/swagger/     # API hujjatlash (faqat DEBUG=True)
http://localhost:8000/redoc/       # ReDoc (faqat DEBUG=True)
http://localhost:8000/health/      # Server holati
```

---

## Rollar

| Rol      | Kim                    | Qanday qo'shiladi                               |
|----------|------------------------|-------------------------------------------------|
| `client` | Taxi buyurtma beruvchi | `/api/users/auth/register/` orqali o'zi         |
| `driver` | Haydovchi              | Faqat admin: `/api/users/admin/drivers/create/` |
| `admin`  | Tizim boshqaruvchisi   | `createsuperuser` yoki Django admin panel       |

---

## REST API Endpointlar

### Auth

| Method | URL                              | Tavsif                                 | Login kerakmi |
|--------|----------------------------------|----------------------------------------|---------------|
| POST   | `/api/users/auth/send-otp/`      | OTP yuborish (SMS)                     | Yo'q          |
| POST   | `/api/users/auth/register/`      | Yangi mijoz ro'yxatdan o'tish          | Yo'q          |
| POST   | `/api/users/auth/verify-otp/`    | Mavjud foydalanuvchi kirishi           | Yo'q          |
| POST   | `/api/users/auth/token/refresh/` | Access tokenni yangilash               | Yo'q          |
| POST   | `/api/users/auth/logout/`        | Chiqish (refresh token bekor qilinadi) | Ha            |

### Profil

| Method | URL              | Tavsif           | Kim     |
|--------|------------------|------------------|---------|
| GET    | `/api/users/me/` | Profilni ko'rish | Hammasi |
| PATCH  | `/api/users/me/` | Ism tahrirlash   | Hammasi |

### Haydovchi

| Method | URL                           | Tavsif                                    | Kim    |
|--------|-------------------------------|-------------------------------------------|--------|
| GET    | `/api/users/driver/profile/`  | Haydovchi profili + statistika            | Driver |
| PATCH  | `/api/users/driver/location/` | Joylashuv yangilash (WebSocket ga uzatadi)| Driver |

### Admin

| Method | URL                                             | Tavsif                  | Kim   |
|--------|-------------------------------------------------|-------------------------|-------|
| GET    | `/api/users/admin/users/`                       | Barcha foydalanuvchilar | Admin |
| POST   | `/api/users/admin/users/{id}/toggle-active/`    | Bloklash/faollashtirish | Admin |
| GET    | `/api/users/admin/drivers/`                     | Barcha haydovchilar     | Admin |
| POST   | `/api/users/admin/drivers/create/`              | Haydovchi qo'shish      | Admin |

### Buyurtmalar

| Method | URL                             | Tavsif                           | Kim             |
|--------|---------------------------------|----------------------------------|-----------------|
| POST   | `/api/orders/estimate/`         | Narx va masofa taxmini           | Login qilganlar |
| GET    | `/api/orders/`                  | O'z buyurtmalar tarixi           | Client          |
| POST   | `/api/orders/`                  | Yangi buyurtma yaratish          | Client          |
| GET    | `/api/orders/{id}/`             | Buyurtma tafsiloti               | Client / Driver |
| POST   | `/api/orders/{id}/cancel/`      | Buyurtmani bekor qilish          | Client          |
| GET    | `/api/orders/driver/available/` | Pending buyurtmalar ro'yxati     | Driver          |
| GET    | `/api/orders/driver/my/`        | Haydovchi o'z safarlar tarixi    | Driver          |
| POST   | `/api/orders/{id}/accept/`      | Buyurtmani qabul qilish          | Driver          |
| POST   | `/api/orders/{id}/start/`       | Safarni boshlash                 | Driver          |
| POST   | `/api/orders/{id}/complete/`    | Safarni yakunlash                | Driver          |
| GET    | `/api/orders/admin/all/`        | Barcha buyurtmalar + status filtr| Admin           |

### Reytinglar

| Method | URL                         | Tavsif                          | Kim     |
|--------|-----------------------------|---------------------------------|---------|
| POST   | `/api/reviews/`             | Haydovchiga baho berish         | Client  |
| GET    | `/api/reviews/driver/{id}/` | Haydovchi reytinglari (paginated)| Hammaga |

### Boshqa

| Method | URL        | Tavsif                              |
|--------|------------|-------------------------------------|
| GET    | `/health/` | Server holati — DB + Cache tekshiradi|

---

## WebSocket Endpointlar

Backend **Daphne ASGI** server ishlatadi — HTTP va WebSocket bitta portda ishlaydi.

### Endpointlar

| URL                                        | Kim uchun          | Nima keladi                         |
|--------------------------------------------|--------------------|-------------------------------------|
| `wss://taxifast.uz/ws/orders/{id}/?token=` | Mijoz va Haydovchi | Buyurtma holati o'zgarishi          |
| `wss://taxifast.uz/ws/driver/?token=`      | Faqat Haydovchi    | Yangi pending buyurtmalar           |

### Xabar turlari

| `type`          | Qachon keladi                         | Asosiy maydonlar                                           |
|-----------------|---------------------------------------|-----------------------------------------------------------|
| `order.update`  | Buyurtma holati o'zgarganda           | `status`, `driver_name`, `driver_phone`, `driver_car`, `final_price` |
| `location.update`| Haydovchi joylashuvi yangilanganda   | `lat`, `lon`                                               |
| `new.order`     | Yangi buyurtma yaratilganda           | `order_id`, `from_address`, `to_address`, `estimated_price`|

### Ulanish kodi (JavaScript)

```javascript
const token = localStorage.getItem('access_token')

// Buyurtma holati — mijoz yoki haydovchi
const ws = new WebSocket(`wss://taxifast.uz/ws/orders/42/?token=${token}`)

ws.onopen = () => console.log('WS ulandi')

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'order.update') {
    console.log('Holat:', data.status, 'Haydovchi:', data.driver_name)
  }
  if (data.type === 'location.update') {
    console.log('Joylashuv:', data.lat, data.lon)
  }
}

ws.onclose = (e) => {
  if (e.code === 4001) console.log('Token kerak — qayta login qiling')
  if (e.code === 4003) console.log('Bu buyurtma sizga tegishli emas')
  if (e.code === 1006) console.log('Tarmoq muammosi — qayta ulanish...')
}

// Yangi buyurtmalar — faqat haydovchi
const driverWs = new WebSocket(`wss://taxifast.uz/ws/driver/?token=${token}`)

driverWs.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // data.type === 'new.order'
  console.log('Yangi buyurtma:', data.order_id, data.estimated_price)
}
```

### Close kodlari

| Kod  | Ma'nosi                          | Frontend da nima qilish            |
|------|----------------------------------|------------------------------------|
| 4001 | Token yo'q yoki noto'g'ri        | Login sahifasiga yo'naltiring      |
| 4003 | Ruxsat yo'q                      | Xabar ko'rsating                   |
| 1000 | Normal yopildi                   | Hech narsa qilmang                 |
| 1006 | Tarmoq muammosi                  | Qayta ulanishni sinab ko'ring      |

---

## Auth oqimi

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
[Mijoz]                                    [Haydovchi]
   |                                             |
   | POST /orders/estimate/                      |
   | ← { distance_km, estimated_price }          |
   |                                             |
   | POST /orders/                               |
   | ← { id, status: "pending" }                 |
   |                                             |── WS: new.order ──────────────►|
   |                                             |
   |                              GET /orders/driver/available/
   |                              ← [ ...pending orders ]
   |                                             |
   |                              POST /orders/{id}/accept/
   |                              ← { detail, order_id }
   |                                             |
   |◄── WS: order.update (accepted) ────────────|
   |                                             |
   |                              POST /orders/{id}/start/
   |◄── WS: order.update (in_progress) ─────────|
   |                                             |
   |          PATCH /driver/location/ (har 3-5 sekunda)
   |◄── WS: location.update (lat, lon) ─────────|
   |                                             |
   |                              POST /orders/{id}/complete/
   |◄── WS: order.update (completed) ───────────|
   |                                             |
   | POST /reviews/                              |
   | { order_id, rating, comment }               |
   | ← { id, rating, ... }                      |
```

---

## Narx formulasi

```
Narx (tenge) = 300 + (km × 100)
Minimum narx: 300 tenge

Misol:
  1 km  →  400 tenge
  5 km  →  800 tenge
  10 km → 1300 tenge
```

`GOOGLE_MAPS_API_KEY` bo'lsa — haqiqiy yo'l masofasi (Google Distance Matrix API).
Bo'lmasa — haversine formula (to'g'ri chiziq, taxminiy).

---

## OTP mexanizmi

| Parametr              | Qiymat                                          |
|-----------------------|-------------------------------------------------|
| Kod uzunligi          | 6 raqam                                         |
| Amal qilish muddati   | 2 daqiqa (120 sekund)                           |
| Qayta yuborish        | 60 sekund kutish kerak                          |
| Noto'g'ri urinish     | 5 martadan keyin kod bekor qilinadi             |
| Bir martalik          | Ha — tekshirilgandan keyin o'chadi              |
| Dev rejimida          | SMS yuborilmaydi, Docker logda ko'rinadi        |

---

## Xavfsizlik

- JWT Bearer token autentifikatsiya (access + refresh)
- Refresh token blacklist — logout dan keyin token ishlamaydi
- Rol asosida ruxsat: `IsClient`, `IsDriver`, `IsAdminUser`
- OTP bruteforce himoyasi — 5 noto'g'ri urinishdan keyin blok
- OTP kriptografik: `secrets.randbelow()` — taxmin qilib bo'lmaydi
- CORS: dev da ochiq, prod da `CORS_ALLOWED_ORIGINS` bilan cheklangan
- Throttling: anonim 30/daqiqa, foydalanuvchi 200/daqiqa
- HTTPS majburiy (prod da `SECURE_SSL_REDIRECT=True`)
- HSTS, X-Frame-Options, XSS filter — prod da yoniq
- WebSocket: JWT middleware, `AllowedHostsOriginValidator`
- Race condition himoyasi: `select_for_update()` + `transaction.atomic()`

---

## CI/CD

**GitHub Actions** — `.github/workflows/ci.yml`:
- Har `push` da: test (coverage ≥75%) + lint + docker build
- Test o'tmasa — merge bloklanadi

**Deploy** — `.github/workflows/deploy.yml`:
- `main` ga push bo'lganda SSH orqali serverga avtomatik deploy
- CI o'tgandan keyingina deploy ishga tushadi (`needs: [test, lint, docker]`)

### GitHub Secrets (Settings → Secrets → Actions)

| Secret           | Qiymati                         |
|------------------|---------------------------------|
| `SERVER_HOST`    | Server IP (masalan: 54.123.45.67)|
| `SERVER_USER`    | SSH foydalanuvchi (`ec2-user`)  |
| `SERVER_SSH_KEY` | SSH private key (to'liq)        |

---

## Production Deploy

Batafsil qo'llanma: `TezYet_Deploy_Guide_v3.pdf`

### Qisqacha

```bash
# Serverda (Amazon Linux 2023):
git clone https://github.com/username/TezYetTaxiPro.git /opt/tezyettaxi
cd /opt/tezyettaxi
nano .env   # qiymatlarni to'ldiring

# Nginx o'rnatish va sozlash
sudo yum install nginx -y
sudo cp nginx/nginx_host.conf /etc/nginx/conf.d/tezyettaxi.conf
sudo nginx -t && sudo systemctl reload nginx

# Docker bilan ishga tushirish
docker-compose -f docker-compose.server.yml up -d --build

# Health check
curl http://localhost:8000/health/
# Javob: {"status": "ok", "db": "ok", "cache": "ok"}
```

### Production `.env` (minimal)

```bash
SECRET_KEY=<python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=taxifast.uz,www.taxifast.uz

POSTGRES_DB=tezyettaxi
POSTGRES_USER=tezyetuser
POSTGRES_PASSWORD=<kuchli_parol>
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

CORS_ALLOWED_ORIGINS=https://taxifast.uz,https://www.taxifast.uz

INFOBIP_API_KEY=<infobip_api_key>
INFOBIP_BASE_URL=xxxxx.api.infobip.com
INFOBIP_SENDER=TezYet
SMS_SKIP_IN_DEV=False

GOOGLE_MAPS_API_KEY=
SENTRY_DSN=

NGINX_SERVER_NAME=taxifast.uz
```

### Nginx config fayllari

| Fayl                    | Qachon ishlatiladi                        |
|-------------------------|-------------------------------------------|
| `nginx/nginx_host.conf` | Serverga o'rnatilgan nginx uchun (asosiy) |
| `nginx/nginx.conf`      | Docker nginx uchun (`docker-compose.prod.yml`) |

---

## Keyingi deploylar (avtomatik)

```bash
git add .
git commit -m "feat: ..."
git push origin main
# GitHub Actions o'zi deploy qiladi
```