#!/bin/sh

# .env faylidan olingan o'zgaruvchilar bilan ulanishni kutish
# Bu yerda Django ulanadigan xostni (pgbouncer yoki postgres) tekshiramiz
echo "Ma'lumotlar bazasi ulanishini kutmoqda: ${POSTGRES_HOST}:${POSTGRES_PORT}..."
while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 0.1
done
echo "Ma'lumotlar bazasiga ulanish o'rnatildi."

# Ma'lumotlar bazasi migratsiyalarini qo'llash
echo "Ma'lumotlar bazasi migratsiyalari qo'llanmoqda..."
python manage.py migrate

# Statik fayllarni yig'ish
echo "Statik fayllar yig'ilmoqda..."
python manage.py collectstatic --no-input --clear

# Agar superuser mavjud bo'lmasa, uni yaratish
# O'zgaruvchilar to'g'ri o'qilishi uchun qo'shtirnoq (") ishlatildi
echo "Superuser tekshirilmoqda..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="$SUPER_USER_NAME").exists():
    User.objects.create_superuser("$SUPER_USER_NAME", "$SUPER_USER_EMAIL", "$SUPER_USER_PASSWORD")
    print('Superuser yaratildi.')
else:
    print('Superuser allaqachon mavjud.')
END

# Asosiy buyruqni ishga tushirish (docker-compose.yml dagi command)
exec "$@"