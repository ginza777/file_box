# apps/multiparser/management/commands/clear_product_data.py

import os
import shutil
import subprocess
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from redis import Redis
from apps.multiparser.models import Product, Document, Seller, ProductView

class Command(BaseCommand):
    """
    Product, Document, Seller, ProductView modellaridagi barcha ma'lumotlarni o'chiradi,
    media papkasini tozalaydi, search index'ni qayta quradi va Redis keshini bo'shatadi.
    """
    help = (
        'Deletes all data from specified tables, clears the media folder, '
        'rebuilds the search index, and flushes Redis.'
    )

    def handle(self, *args, **options):
        confirmation = input(
            self.style.WARNING(
                "DIQQAT! Bu buyruq quyidagi amallarni bajaradi:\n"
                "1. 'Product', 'Document', 'Seller', 'ProductView' jadvallaridagi BARCHA ma'lumotlarni o'chiradi.\n"
                "2. Docker tashqarisidagi (bog'langan) 'media' papkasining BARCHA tarkibini o'chiradi.\n"
                "3. Elasticsearch/OpenSearch dagi index'larni qayta quradi ('search_index --rebuild').\n"
                "4. Redis'dagi BARCHA keshlarni o'chiradi ('flushall').\n"
                "\nBu amallarni orqaga qaytarib bo'lmaydi.\n"
                "Davom etish uchun 'yes' deb yozing va Enter bosing: "
            )
        )

        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR("Operatsiya bekor qilindi."))
            return

        # 1. BAZANI TOZALASH
        self.stdout.write(self.style.NOTICE("\n1. Ma'lumotlar bazasini tozalash boshlandi..."))
        try:
            with transaction.atomic():
                ProductView.objects.all().delete()
                Product.objects.all().delete()
                Document.objects.all().delete()
                Seller.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Baza muvaffaqiyatli tozalandi! ✅"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"O'chirish vaqtida xatolik yuz berdi: {e}"))
            return

        # 2. MEDIA PAPKASINI TOZALASH
        self.stdout.write(self.style.NOTICE(f"\n2. Media papkasini tozalash ({settings.MEDIA_ROOT})..."))
        media_root = settings.MEDIA_ROOT
        if media_root and os.path.exists(media_root):
            try:
                # Papka ichidagilarni o'chirish
                for filename in os.listdir(media_root):
                    file_path = os.path.join(media_root, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                self.stdout.write(self.style.SUCCESS(f"'{media_root}' papkasi tarkibi muvaffaqiyatli tozalandi."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Media papkasini tozalashda xatolik: {e}"))
        else:
            self.stdout.write(self.style.WARNING(f"Media papkasi topilmadi yoki MEDIA_ROOT sozlanmagan."))

        # 3. SEARCH INDEX'NI QAYTA QURISH
        self.stdout.write(self.style.NOTICE("\n3. Search index'ni qayta qurish ('search_index --rebuild')..."))
        try:
            call_command('search_index', '--rebuild', '-f')
            self.stdout.write(self.style.SUCCESS("Search index muvaffaqiyatli qayta qurildi."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Search index'ni qayta qurishda xatolik: {e}"))

        # 4. REDIS KESHINI TOZALASH
        self.stdout.write(self.style.NOTICE("\n4. Redis keshini tozalash..."))
        try:
            # Redis klient yaratish
            redis_client = Redis(
                host=settings.REDIS_HOST,  # Docker compose'dagi servis nomi
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                socket_connect_timeout=5,
                decode_responses=True
            )
            # Barcha keshlarni tozalash
            redis_client.flushall()
            self.stdout.write(self.style.SUCCESS("Redis kesh muvaffaqiyatli tozalandi!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Redis keshini tozalashda xatolik yuz berdi: {e}"))

        self.stdout.write(self.style.SUCCESS("\nBarcha operatsiyalar to'liq yakunlandi! 🔥"))