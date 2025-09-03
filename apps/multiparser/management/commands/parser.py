import requests
import re
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.multiparser.models import Seller, Document, Product
from decimal import Decimal
from apps.multiparser.tasks import process_document


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

        base_api_url = "https://soff.uz/_next/data/HT2g6Ps9UGEtaSpYNC9G6/scientific-resources/all.json"

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
                i=1
                for item in results:
                    print(f"{id}---------------")
                    product_id = item.get("id")
                    print(item)
                    if not product_id:
                        continue

                    try:
                        with transaction.atomic():
                            seller_data = item.get("seller", {})
                            seller, _ = Seller.objects.get_or_create(
                                id=seller_data.get("id"),
                                defaults={'fullname': seller_data.get("fullname", "Noma'lum Sotuvchi")}
                            )

                            document_data = item.get("document", {})
                            file_url = extract_file_url(item.get("poster_url", ""))

                            product, created = Product.objects.update_or_create(
                                id=product_id,
                                defaults={
                                    'title': item.get("title", ""),
                                    'slug': item.get("slug", f"product-{product_id}"),
                                    'seller': seller,
                                    'price': Decimal(str(item.get("price", 0))),
                                    'poster_url': item.get("poster_url", ""),
                                    'file_url_2': item.get("file_url", ""),
                                    'views_count': item.get("views_count", 0),
                                    'content_type': item.get("content_type", "file"),
                                    'json_data': item
                                }
                            )

                            if created or not product.document:
                                document = Document.objects.create(
                                    page_count=document_data.get("page_count", 0),
                                    file_size=document_data.get("file_size", "0 MB"),
                                    file_type=document_data.get("file_type", ""),
                                    content_type=document_data.get("content_type", "file"),
                                    file_url=file_url
                                )
                                product.document = document

                                product.save()

                                if document.file_url:
                                    process_document.delay(document.id)
                                    self.stdout.write(
                                        self.style.SUCCESS(f"Task scheduled for NEW product {product.id}"))
                            else:
                                self.stdout.write(f"Product {product_id} updated.")
                        product.json_data = item
                        product.save()
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing item ID {product_id}: {e}"))
                i=i+1
                time.sleep(1)
            except requests.exceptions.HTTPError as e:
                self.stdout.write(self.style.ERROR(f"HTTP Error on page {page}: {e}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"An unexpected error occurred on page {page}: {e}"))

        self.stdout.write(self.style.SUCCESS("\nParsing completed!"))

