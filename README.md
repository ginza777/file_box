# Kuku Bot — Django + python-telegram-bot

Tezkor, modulli va **webhook** orqali ishlaydigan Telegram bot loyihasi. Loyihada Django (DRF), Celery, Redis va `python-telegram-bot` (v21, async) ishlatiladi. Ushbu README aynan siz bergan zip dagi **mavjud kod** va funksiyalar asosida yozildi.

> **Asosiy g‘oya:** Bitta Django ilovasi ichida bir nechta botlarni yuritish, foydalanuvchilarni va kanal obunalarini boshqarish, ma’muriy (admin) imkoniyatlar (ommalashtirish/broadcast, statistikalar, zaxira nusxa), ko‘p tillilik va Swagger hujjatlari.

---

## 📁 Loyihaning tuzilishi (asosiy fayllar)

```
Kuku_Bot/
├─ apps/
│  └─ common_bot/
│     ├─ admin.py                # Admin paneli: Bot, User, SubscribeChannel, Broadcast, ...
│     ├─ keyboard.py             # Inline/Reply klaviatura generatorlari
│     ├─ models.py               # Bot, User, SubscribeChannel, Broadcast, BroadcastRecipient, Location
│     ├─ tasks.py                # Celery vazifalari (broadcast yuborish)
│     ├─ translation.py          # Matnlar va tugmalar (uz/ru/en/tr)
│     ├─ urls.py                 # /api/bot/<token> webhooks
│     ├─ webhook.py              # Telegram webhook qabul qiluvchi view
│     └─ handler.py / views.py   # /start, /help, /broadcast, /stats, /backup_db va h.k.
│
├─ core/
│  ├─ celery.py                  # Celery konfiguratsiyasi
│  ├─ settings/
│  │  ├─ base.py                 # Asosiy sozlamalar (.env orqali)
│  │  ├─ develop.py              # Dev rejimi (CELERY_TASK_ALWAYS_EAGER=True)
│  │  └─ production.py           # Prodga mos patch
│  ├─ swagger/                   # drf-yasg sozlamalari
│  ├─ urls.py                    # admin, rosetta, __debug__, api/, swagger/
│  └─ views.py                   # index va yordamchi viewlar
│
├─ manage.py
├─ requirements/
│  └─ base.txt                   # Kutubxonalar (Django, DRF, PTB v21, Celery, Redis, ...)
└─ db.sqlite3                    # Dev rejim uchun standart baza
```

---

## ✨ Mavjud funksiyalar

### Botlar va webhook
- **Bot modeli (`apps.common_bot.models.Bot`)**: `token` kiritsangiz, saqlash chog‘ida botning **nomi/username** Telegram API dan olinadi va **webhook** avtomatik o‘rnatiladi.
- **Webhook endpoint**: `POST /api/bot/<token>` — barcha Telegram yangilanishlari shu URL ga keladi.
- **Webhook URL** `settings.WEBHOOK_URL` orqali olinadi va har bir bot uchun `WEBHOOK_URL + "/api/bot/<token>"` tarzida o‘rnatiladi.
- **Management command**: `python manage.py webhook` — bazadagi barcha botlar uchun webhookni qayta o‘rnatish.

### Majburiy kanal(lar)ga obuna
- **SubscribeChannel** modeli: kanal `username` va `channel_id` bilan saqlanadi.
- Admin panelda kanal qo‘shilganda **botning kanalga adminligi** tekshiriladi (formada `check_bot_is_admin_in_channel`).
- Botdagi harakatlar oldidan **obuna tekshiruvi** ishlaydi; foydalanuvchiga kanal ro‘yxati va **“Obunani tekshirish”** tugmasi ko‘rsatiladi.

### Foydalanuvchilar va til
- **User** modeli: `telegram_id`, `is_admin`, `left`, `selected_language` (uz/ru/en/tr) kabilar saqlanadi.
- **/start**: agar til tanlanmagan bo‘lsa — inline tillar (🇺🇿 🇷🇺 🇬🇧 🇹🇷). Tanlangan bo‘lsa — asosiy menyuga o‘tadi.
- Matnlar va tugmalar **translation.py** dan olinadi — foydalanuvchining tanlangan tiliga mos ko‘rinadi.

### Admin imkoniyatlari
- **/admin**: yashirin admin menyu (matnlar `translation.py` da).
- **/broadcast**: ommaviy xabar yuborish dialogi (tasdiqlash bilan). Xabarlar Celery orqali **BroadcastRecipient** lar bo‘yicha yuboriladi, har birining holati (`PENDING/SENT/FAILED`) qayd etiladi.
- **/stats**: foydalanuvchilar soni, so‘nggi 24 soat faol bo‘lganlar va h.k.
- **/export_users**: `users.csv` ni generatsiya qilib yuboradi.
- **/backup_db**: bazaning zaxira nusxasini yaratish (sqlite/postgresga mos ketma-ketlik kiritilgan).

### Lokatsiya
- **/ask_location** → foydalanuvchidan lokatsiya so‘rash, yuborilgan lokatsiyalar **Location** modelida saqlanadi.

### Swagger hujjatlar
- **Swagger/Redoc**: `/<project>/swagger/`, `/<project>/redoc/` (aniq URL: `core/swagger/schema.py`). Asosiy UI: **`/swagger/`**.

---

## 🚀 O‘rnatish (Dev)

### Talablar
- Python **3.10+** (tavsiya 3.11)
- (Dev) SQLite avtomatik ishlaydi
- (Prod) PostgreSQL va Redis

### 1) Repo va kutubxonalar
```bash
git clone <repo-url>
cd Kuku_Bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements/base.txt
```

### 2) .env
`.env` faylini loyihaning ildizida (Kuku_Bot ichida) yarating:

```env
# Django
DJANGO_SETTINGS_MODULE=core.settings.develop
SECRET_KEY=change_me
DEBUG=1

# Webhook bazaviy URL (tunnel yoki domeningiz)
WEBHOOK_URL=https://<your-domain-or-tunnel>

# Celery/Redis (dev uchun ixtiyoriy)
CELERY_BROKER_URL=redis://localhost:6379
```

> `develop.py` rejimida Celery **eager** ishlaydi (ya’ni worker majburiy emas).

### 3) Migratsiyalar va superuser
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

### 4) Admin paneldan Bot qo‘shish
1. `/admin` ga kiring → **Bots** → **Add**.
2. **token** ni kiriting va saqlang — bot nomi/username to‘ldiriladi, webhook avtomatik o‘rnatiladi.
3. Agar kerak bo‘lsa: `python manage.py webhook` bilan ham eslatib o‘tishingiz mumkin.

### 5) Majburiy kanallar
- `/admin` → **Subscribe channels** → **Add** qiling (username, channel_id).
- Saqlashda botning **kanalga adminligi** avtomatik tekshiriladi.

---

## 🧩 Ishga tushirish (Prod)

`.env` ni prod uchun moslang (PostgreSQL + Redis + DEBUG=0):

```env
DJANGO_SETTINGS_MODULE=core.settings.base
SECRET_KEY=<strong_random_key>
DEBUG=0

# Postgres
DB_ENGINE=django.db.backends.postgresql_psycopg2
DB_NAME=<db_name>
DB_USER=<db_user>
DB_PASSWORD=<db_password>
DB_HOST=<db_host>
DB_PORT=5432

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379

# Webhook bazaviy URL (https kerak)
WEBHOOK_URL=https://<your-domain>
```

Keyin:

```bash
python manage.py collectstatic --noinput
python manage.py migrate

# Django
gunicorn core.wsgi:application --bind 0.0.0.0:8000

# Celery worker va beat
celery -A core worker -l info
celery -A core beat -l info

# Botlar uchun webhook
python manage.py webhook
```

> **Eslatma:** Webhook endpoint — `https://<your-domain>/api/bot/<BOT_TOKEN>`.
`WEBHOOK_URL` faqat **bazaviy** URL bo‘lishi kerak (endpoint qo‘shmang) — kod o‘zi to‘g‘ri formatlab beradi.

---

## 🔐 Admin rollari
- Foydalanuvchini admin qilish uchun `/admin` → **Users** dan kerakli `User` yozuvini topib **is_admin** ni yoqing.
- Adminlar `/admin`, `/broadcast`, `/stats`, `/export_users`, `/backup_db` kabi buyruqlardan foydalana oladi.

---

## 🗣️ Ko‘p tillilik
- `translation.py` ichida barcha matnlar mavjud (🇺🇿 🇷🇺 🇬🇧 🇹🇷).
- `/start` bosilgach odam til tanlamagan bo‘lsa — inline tugmalar chiqadi. Tanlanganidan so‘ng barcha matnlar va tugmalar shu tilga mos ko‘rinadi.

---

## 📊 Broadcast qanday ishlaydi?
1. Admin `/broadcast` ni ishga tushiradi.
2. Bot xabar matnini qabul qiladi → tasdiqlash (inline) so‘raydi.
3. Tasdiqlansa — **Celery** ishga tushadi: barcha **User** lar bo‘yicha **BroadcastRecipient** yozuvlari yaratiladi va xabar yuboriladi.
4. Har bir qabul qiluvchi uchun holat: **PENDING → SENT/FAILED**. Failed larni admin paneldan qayta navbatga qo‘yish aksiyasi bor.

---

## 🔌 Swagger / Rosetta / Debug toolbar
- Swagger UI: **`/swagger/`**
- Redoc: **`/redoc/`**
- Rosetta (i18n): **`/rosetta/`**
- Django Debug Toolbar: **`/__debug__/`**

---

## ❗Muammolar va yechimlar

- **Webhook setWebhook xatosi**: `WEBHOOK_URL` to‘g‘ri va tashqi dunyodan HTTPS bilan ochiq bo‘lishi shart (ngrok/jprq/Cloudflare Tunnel).
- **Kanal adminligi xatosi**: SubscribeChannel saqlanganda chiqsa — botni kanalingizda **Admin** qiling, so‘ngra qayta saqlang.
- **Broadcast yubormayapti**: prod rejimda Celery **worker** va **beat** ishga tushganini tekshiring; Redis ulanishi to‘g‘ri ekanligiga ishonch hosil qiling.
- **Til o‘zgarmayapti**: `translation.py` dagi kalitlar va handlerlarda tilni aniqlash qismiga e’tibor bering; userning `selected_language` maydoni yangilanayotganini tekshiring.

---

## 🧪 Tez start (lokal, dev)
```bash
# 1) Venv va o‘rnatish
pip install -r requirements/base.txt

# 2) .env (develop)
echo "DJANGO_SETTINGS_MODULE=core.settings.develop
SECRET_KEY=dev_key
DEBUG=1
WEBHOOK_URL=https://example-tunnel.local
CELERY_BROKER_URL=redis://localhost:6379" > .env

# 3) Migratsiya va ishga tushirish
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# 4) Admin panel: Bot qo‘shing (token), SubscribeChannel kiriting
# 5) Chatda /start ni bosing
```

---

## 📄 Litsenziya
Loyihadagi kodlar egasiga tegishli. Ichki ehtiyoj uchun foydalanyapsiz — mualliflik huquqlarini hurmat qiling.

