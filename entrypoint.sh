#!/bin/sh

# Baza ulanishini kutish
echo "PostgreSQL'ni kutmoqda..."
while ! nc -z postgres 5432; do
  sleep 0.1
done
echo "PostgreSQL ishga tushdi."

# Ma'lumotlar bazasi migratsiyalarini qo'llash
python manage.py migrate

# Statik fayllarni yig'ish
python manage.py collectstatic --no-input --clear

# Agar superuser mavjud bo'lmasa, uni yaratish
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$SUPER_USER_NAME').exists():
    User.objects.create_superuser('$SUPER_USER_NAME', '$SUPER_USER_EMAIL', '$SUPER_USER_PASSWORD')
    print('Superuser yaratildi.')
END

# Asosiy buyruqni ishga tushirish (Dockerfile'dagi CMD yoki docker-compose'dagi command)
exec "$@"