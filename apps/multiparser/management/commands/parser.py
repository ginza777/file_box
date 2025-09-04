import re
import time
from decimal import Decimal

import requests
from celery import chain
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.multiparser.models import Seller, Document, Product
from apps.multiparser.tasks import download_file_task, send_telegram_task, index_document_task, delete_local_file_task, \
    process_document


def extract_file_url(poster_url):
    """
    Extract the actual file URL from poster_url.
    This function is specific to the old API structure.
    """
    if not poster_url:
        return None
    match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', poster_url)
    if match:
        file_id = match.group(1)
        file_ext_match = re.search(r'\.(pdf|docx|doc|pptx|ppt|xlsx|xls|txt|rtf|odt|ods|odp)(?:_page|$)', poster_url,
                                   re.IGNORECASE)
        if file_ext_match:
            file_extension = file_ext_match.group(1).lower()
            return f"https://d2co7bxjtnp5o.cloudfront.net/media/documents/{file_id}.{file_extension}"
    return None


class Command(BaseCommand):
    help = 'Parse products data from soff.uz API and save to database'

    def add_arguments(self, parser):
        parser.add_argument('--start-page', type=int, default=1, help='Starting page number')
        parser.add_argument('--end-page', type=int, default=7000, help='Ending page number')
        parser.add_argument('--clear-data', action='store_true', help='Clear all existing data before parsing')

    def handle(self, *args, **options):
        start_page = options['start_page']
        end_page = options['end_page']

        base_api_url = "https://soff.uz/_next/data/n8FdePPcOhgY7lG6qCGKI/scientific-resources/all.json"

        headers = {
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "referer": "https://soff.uz/scientific-resources/all"
        }

        cookies = {
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU3Mzc5NDYwLCJpYXQiOjE3NTY1MTU0NjAsImp0aSI6IjlhZWE1NmEzNjUxNjQxYTU4N2I4MGFkNmI4YzNlYjMwIiwidXNlcl9pZCI6MjAyNTgwfQ.ADzRUwBFKsZKaQwNF7Qhzjf7WeUrCe8dryxx4LW3Zzd7eP2llz9CKaqDx8A1i7EOtNU2h9CjSZYnnLqYAHYt1OcBgIX5Wul0uMwvlSvmQHKQ0qcPHiIkd0L088kv1ys8naCfdMFuRnvmAeWJUGz69rjO0MmW4l4zIN-sJgQjQ6wDhQUy1Jwj3vq4R2RMVw2AxHVDunHZrjIT-gFvaAbPQiK7LBl9YfQ2za6dXEqeDGJVuGwY4p9CXjJ5KmIHEQ2u7Dyii9rOi_KP2rAA7w9tf2gVLBLAa-RxeNJn2Abq64-xXH6FJMKj5SVo04swBUrxvp6BKzEmu7NOH5fnyfPcYA"}

        if options['clear_data']:
            self.stdout.write(self.style.WARNING('Clearing all existing data...'))
            Product.objects.all().delete()
            Document.objects.all().delete()
            Seller.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Data cleared!'))

        for page in range(start_page, end_page + 1):
            self.stdout.write(f"Processing page {page}...")
            params = {'search': '', 'page': page, 'slug': 'all'}

            try:
                response = requests.get(base_api_url, headers=headers, cookies=cookies, params=params)

                if response.status_code == 404:
                    self.stdout.write(self.style.ERROR(f"XATO: URL manzil ({base_api_url}) eskirgan."))
                    break

                response.raise_for_status()
                json_data = response.json()
                results = json_data.get("pageProps", {}).get("productsData", {}).get("results", [])

                if not results:
                    self.stdout.write(self.style.SUCCESS(f"No more results on page {page}. Stopping."))
                    break

                for item in results:
                    product_id = item.get("id")
                    if not product_id:
                        continue

                    try:
                        with transaction.atomic():
                            # 1. Sotuvchini olamiz yoki yaratamiz
                            seller_data = item.get("seller", {})
                            seller, _ = Seller.objects.get_or_create(
                                id=seller_data.get("id"),
                                defaults={'fullname': seller_data.get("fullname", "Noma'lum Sotuvchi")}
                            )

                            # 2. Mahsulot mavjudligini tekshiramiz (document'ni ham birga olamiz)
                            product = Product.objects.select_related('document').filter(id=product_id).first()

                            if product:
                                # --- MAVJUD MAHSULOT UCHUN MANTIQ ---

                                # Maydonlarni yangilaymiz
                                product.title = item.get("title", "")
                                product.slug = item.get("slug", f"product-{product_id}")
                                product.seller = seller
                                product.price = Decimal(str(item.get("price", 0)))
                                product.poster_url = item.get("poster_url", "")
                                product.file_url_2 = item.get("file_url", "")
                                product.views_count = item.get("views_count", 0)
                                product.content_type = item.get("content_type", "file")
                                product.json_data = item
                                product.save()
                                self.stdout.write(f"Product {product_id} updated.")

                                # Hujjat holatini tekshirib, kerak bo'lsa vazifani qayta navbatga qo'yamiz
                                document = product.document
                                if document and document.file_url and document.download_status not in ['downloaded',
                                                                                                       'downloading']:
                                    document.download_status = 'pending'
                                    document.save(update_fields=['download_status'])

                                    task_chain = chain(
                                        download_file_task.s(document.id),
                                        send_telegram_task.s(),
                                        index_document_task.s(),
                                        delete_local_file_task.s()
                                    )
                                    task_chain.apply_async()
                                    self.stdout.write(
                                        self.style.SUCCESS(f"Task chain RE-SCHEDULED for EXISTING product {product.id}")
                                    )

                            else:
                                # --- YANGI MAHSULOT UCHUN MANTIQ ---

                                # Avval Hujjatni yaratamiz
                                document_data = item.get("document", {})
                                file_url = extract_file_url(item.get("poster_url", ""))
                                document = Document.objects.create(
                                    page_count=document_data.get("page_count", 0),
                                    file_size=document_data.get("file_size", "0 MB"),
                                    file_type=document_data.get("file_type", ""),
                                    content_type=document_data.get("content_type", "file"),
                                    file_url=file_url
                                )

                                # Endi Hujjat bilan birga Mahsulotni yaratamiz
                                product = Product.objects.create(
                                    id=product_id,
                                    document=document,
                                    title=item.get("title", ""),
                                    slug=item.get("slug", f"product-{product_id}"),
                                    seller=seller,
                                    price=Decimal(str(item.get("price", 0))),
                                    poster_url=item.get("poster_url", ""),
                                    file_url_2=item.get("file_url", ""),
                                    views_count=item.get("views_count", 0),
                                    content_type=item.get("content_type", "file"),
                                    json_data=item
                                )
                                self.stdout.write(self.style.SUCCESS(f"NEW product {product.id} created."))

                                # Yangi mahsulot uchun vazifani navbatga qo'yamiz
                                if document.file_url:
                                    process_document(document.id)
                                    self.stdout.write(
                                        self.style.SUCCESS(f"Task chain scheduled for NEW product {product.id}")
                                    )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing item ID {product_id}: {e}"))

                time.sleep(1)
            except requests.exceptions.HTTPError as e:
                self.stdout.write(self.style.ERROR(f"HTTP Error on page {page}: {e}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"An unexpected error occurred on page {page}: {e}"))

        self.stdout.write(self.style.SUCCESS("\nParsing completed!"))
