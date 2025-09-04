# apps/multiparser/management/commands/check_services.py

import requests
from celery import current_app
from django.conf import settings
from django.core.management.base import BaseCommand
from elasticsearch import Elasticsearch

# Tika serverining standart manzilini belgilaymiz.
# Buni settings.py fayliga qo'shib, o'zgartirsa ham bo'ladi.
TIKA_URL = getattr(settings, 'TIKA_URL', 'http://localhost:9998')


class Command(BaseCommand):
    """
    Tashqi xizmatlarning (Celery, Elasticsearch, Tika) holatini tekshiruvchi Django buyrug'i.
    """
    help = 'Checks the status of Celery workers, Elasticsearch, and Apache Tika server.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Tashqi xizmatlar holatini tekshirish boshlandi..."))

        # Har bir xizmatni alohida funksiyada tekshiramiz
        all_ok = all([
            self._check_elasticsearch(),
            self._check_tika(),
            self._check_celery(),
        ])

        if all_ok:
            self.stdout.write(self.style.SUCCESS("\nBarcha xizmatlar muvaffaqiyatli ishlamoqda! ✅"))
        else:
            self.stdout.write(self.style.WARNING("\nBa'zi xizmatlarda muammolar aniqlandi. Yuqoridagi xabarlarni tekshiring. ❌"))

    def _check_elasticsearch(self):
        """Elasticsearch ulanishini tekshiradi."""
        self.stdout.write("\n--- 1. Elasticsearch tekshirilmoqda ---")
        if not settings.ES_URL:
            self.stdout.write(self.style.ERROR("XATO: .env faylida ES_URL o'rnatilmagan."))
            return False

        try:
            es_client = Elasticsearch(settings.ES_URL, request_timeout=5)
            if es_client.ping():
                self.stdout.write(self.style.SUCCESS("✔ Elasticsearch bilan ulanish mavjud."))
                return True
            else:
                self.stdout.write(self.style.ERROR("✖ Elasticsearch bilan ulanish mavjud emas (ping javob bermadi)."))
                return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✖ Elasticsearch bilan ulanishda xatolik: {e}"))
            return False

    def _check_tika(self):
        """Apache Tika serverining holatini tekshiradi."""
        self.stdout.write("\n--- 2. Apache Tika tekshirilmoqda ---")
        tika_status_url = f"{TIKA_URL}/tika"
        try:
            response = requests.get(tika_status_url, timeout=5)
            response.raise_for_status()  # 200 bo'lmasa xatolik beradi
            version_info = response.text.strip()
            self.stdout.write(self.style.SUCCESS(f"✔ Tika serveri ishlamoqda (Versiya: {version_info})."))
            return True
        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR(f"✖ Tika serveriga ulanib bo'lmadi ({TIKA_URL}). Server ishga tushirilganmi?"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✖ Tika serverini tekshirishda xatolik: {e}"))
            return False

    def _check_celery(self):
        """Celery worker'larining mavjudligini tekshiradi."""
        self.stdout.write("\n--- 3. Celery Worker'lar tekshirilmoqda ---")
        try:
            celery_app = current_app
            # Barcha faol worker'larga "ping" so'rovini yuborish
            inspector = celery_app.control.inspect(timeout=3)
            active_workers = inspector.ping()

            if not active_workers:
                self.stdout.write(self.style.ERROR("✖ Hech qanday faol Celery worker topilmadi! Broker (Redis) ishlayaptimi?"))
                return False

            self.stdout.write(self.style.SUCCESS(f"✔ {len(active_workers)} ta faol Celery worker topildi:"))
            for worker_name in active_workers.keys():
                self.stdout.write(f"  - {worker_name}")
            return True
        except IOError as e:
            self.stdout.write(self.style.ERROR(f"✖ Celery broker (Redis) bilan bog'lanib bo'lmadi: {e}"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✖ Celery holatini tekshirishda kutilmagan xatolik: {e}"))
            return False