# 1-bosqich: Python 3.12-slim asosida boshlang'ich qolipni olish
FROM python:3.12-slim as base

# Paketlar ro'yxatini yangilash va kerakli kutubxonalarni o'rnatish
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogini yaratish
WORKDIR /app

# Talablar faylini nusxalash va kutubxonalarni o'rnatish
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements/production.txt

# 2-bosqich: Ishga tushirish uchun tayyor qolip
FROM python:3.12-slim

# Tika Server uchun Java'ni o'rnatish va netcat o'rnatish
# YANGILANDI: Java versiyasi 17 dan 21 ga o'zgartirildi
RUN apt-get update && apt-get install -y openjdk-21-jre-headless netcat-openbsd && apt-get clean

# Zarur paketlarni avvalgi bosqichdan nusxalash
COPY --from=base /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/
COPY --from=base /usr/include/ /usr/include/

# Ishchi katalogini belgilash
WORKDIR /app

# Loyiha fayllari va yordamchi skriptlarni nusxalash
COPY . .

# entrypoint skriptiga ishlash huquqini berish
RUN chmod +x /app/entrypoint.sh

# Django uchun 8000-portni ochish
EXPOSE 8000

# Konteyner ishga tushganda bajariladigan buyruq
ENTRYPOINT ["/app/entrypoint.sh"]