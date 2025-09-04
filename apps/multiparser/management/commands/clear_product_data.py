# apps/multiparser/management/commands/clear_product_data.py

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.multiparser.models import Product, Document, Seller, ProductView

class Command(BaseCommand):
    """
    Product, Document, Seller va ProductView modellaridagi barcha ma'lumotlarni
    tasdiq bilan o'chiruvchi buyruq.
    """
    help = 'Deletes all data from Product, Document, Seller, and ProductView tables after confirmation.'

    def handle(self, *args, **options):
        confirmation = input(
            self.style.WARNING(
                "DIQQAT! Bu buyruq 'Product', 'Document', 'Seller' va 'ProductView' jadvallaridagi BARCHA ma'lumotlarni "
                "butunlay o'chirib yuboradi.\n"
                "Bu amalni orqaga qaytarib bo'lmaydi.\n"
                "Davom etish uchun 'yes' deb yozing va Enter bosing: "
            )
        )

        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR("Operatsiya bekor qilindi."))
            return

        self.stdout.write(self.style.NOTICE("Ma'lumotlarni o'chirish boshlandi..."))

        try:
            with transaction.atomic():
                # ProductView'larni o'chirish (Product o'chirilganda avtomatik o'chadi, lekin aniqlik uchun)
                deleted_views_count, _ = ProductView.objects.all().delete()
                self.stdout.write(f"O'chirildi: {deleted_views_count} ta ProductView yozuvi.")

                # Product'larni o'chirish. Bunga bog'liq Document'lar ham CASCADE tufayli avtomatik o'chadi.
                deleted_products_count, _ = Product.objects.all().delete()
                self.stdout.write(f"O'chirildi: {deleted_products_count} ta Product (va unga bog'liq Document) yozuvi.")

                # Qolgan Document'larni tozalash (agar mustaqil Document'lar bo'lsa)
                deleted_docs_count, _ = Document.objects.all().delete()
                self.stdout.write(f"O'chirildi: {deleted_docs_count} ta qo'shimcha Document yozuvi.")

                # Barcha Seller'larni o'chirish
                deleted_sellers_count, _ = Seller.objects.all().delete()
                self.stdout.write(f"O'chirildi: {deleted_sellers_count} ta Seller yozuvi.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"O'chirish vaqtida xatolik yuz berdi: {e}"))
            return

        self.stdout.write(self.style.SUCCESS("\nBaza muvaffaqiyatli tozalandi! ✅"))