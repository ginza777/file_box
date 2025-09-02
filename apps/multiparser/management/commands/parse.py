import requests
import re
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.multiparser.models import Seller, Document, Product
from decimal import Decimal


def extract_file_url(poster_url):
    """
    Extract the actual file URL from poster_url
    Example: 
    Input: "https://d2co7bxjtnp5o.cloudfront.net/media/Images/14cddf99-da72-4844-a1ba-2dfdea3000f0.pdf_page-1_generate.webp"
    Output: "https://d2co7bxjtnp5o.cloudfront.net/media/documents/14cddf99-da72-4844-a1ba-2dfdea3000f0.pdf"
    """
    if not poster_url:
        return None
    
    # Extract file ID from poster_url
    # Pattern: extract UUID-like string before "_page"
    match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', poster_url)
    if match:
        file_id = match.group(1)
        
        # Extract file extension from poster_url
        # Look for common file extensions
        file_ext_match = re.search(r'\.(pdf|docx|doc|pptx|ppt|xlsx|xls|txt|rtf|odt|ods|odp)(?:_page|$)', poster_url, re.IGNORECASE)
        if file_ext_match:
            file_extension = file_ext_match.group(1).lower()
            # Construct the actual document URL
            document_url = f"https://d2co7bxjtnp5o.cloudfront.net/media/documents/{file_id}.{file_extension}"
            return document_url
    
    return None


class Command(BaseCommand):
    help = 'Parse products data from soff.uz API and save to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-page',
            type=int,
            default=1,
            help='Starting page number (default: 1)'
        )
        parser.add_argument(
            '--end-page',
            type=int,
            default=6761,
            help='Ending page number (default: 6761)'
        )
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='Clear all existing data before parsing'
        )

    def handle(self, *args, **options):
        start_page = options['start_page']
        end_page = options['end_page']
        clear_data = options['clear_data']

        # API configuration
        base_url = "https://soff.uz/_next/data/3Ic0NEWbEiJ5wF3V1C6Gt/scientific-resources/all.json?search=&page={}&slug=all"
        
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,uz;q=0.8,tr;q=0.7",
            "priority": "u=1, i",
            "referer": "https://soff.uz/scientific-resources/all?search=&page=6760",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "x-nextjs-data": "1"
        }

        cookies = {
            "_ym_uid": "1756515357892662175",
            "_ym_d": "1756515357",
            "_ga": "GA1.1.380989533.1756515357",
            "_ym_isad": "2",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU3Mzc5NDYwLCJpYXQiOjE3NTY1MTU0NjAsImp0aSI6IjlhZWE1NmEzNjUxNjQxYTU4N2I4MGFkNmI4YzNlYjMwIiwidXNlcl9pZCI6MjAyNTgwfQ.ADzRUwBFKsZKaQwNF7Qhzjf7WeUrCe8dryxx4LW3Zzd7eP2llz9CKaqDx8A1i7EOtNU2h9CjSZYnnLqYAHYt1OcBgIX5Wul0uMwvlSvmQHKQ0qcPHiIkd0L088kv1ys8naCfdMFuRnvmAeWJUGz69rjO0MmW4l4zIN-sJgQjQ6wDhQUy1Jwj3vq4R2RMVw2AxHVDunHZrjIT-gFvaAbPQiK7LBl9YfQ2za6dXEqeDGJVuGwY4p9CXjJ5KmIHEQ2u7Dyii9rOi_KP2rAA7w9tf2gVLBLAa-RxeNJn2Abq64-xXH6FJMKj5SVo04swBUrxvp6BKzEmu7NOH5fnyfPcYA",
            "_ga_H60GJQ0WF2": "GS2.1.s1756525838$o2$g1$t1756526489$j1$l0$h0",
            "_ga_6WBEBBT4YD": "GS2.1.s1756525838$o2$g1$t1756526489$j1$l0$h0"
        }

        if clear_data:
            self.stdout.write(
                self.style.WARNING('Clearing all existing data...')
            )
            with transaction.atomic():
                Product.objects.all().delete()
                Document.objects.all().delete()
                Seller.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS('All existing data cleared successfully!')
            )

        total_products = 0
        total_sellers = 0
        total_documents = 0

        for page in range(start_page, end_page + 1):
            self.stdout.write(f"Processing page {page}...")
            url = base_url.format(page)
            
            try:
                response = requests.get(url, headers=headers, cookies=cookies)
                response.raise_for_status()
                json_data = response.json()
                
                results = json_data.get("pageProps", {}).get("productsData", {}).get("results", [])
                
                if not results:
                    self.stdout.write(f"No results found on page {page}")
                    continue
                
                page_products = 0
                
                for item in results:
                    try:
                        # Extract seller data
                        seller_data = item.get("seller", {})
                        seller_id = seller_data.get("id")
                        seller_fullname = seller_data.get("fullname", "Unknown Seller")
                        
                        if not seller_id:
                            continue
                        
                        # Get or create seller
                        seller, seller_created = Seller.objects.get_or_create(
                            id=seller_id,
                            defaults={'fullname': seller_fullname}
                        )
                        
                        if seller_created:
                            total_sellers += 1
                        
                        # Extract document data
                        document_data = item.get("document", {})
                        if not document_data:
                            continue
                        
                        # Extract file URL from poster_url
                        poster_url = item.get("poster_url", "")
                        file_url = extract_file_url(poster_url)
                        
                        # Create document
                        document = Document.objects.create(
                            page_count=document_data.get("page_count", 1),
                            file_size=document_data.get("file_size", "0 MB"),
                            file_type=document_data.get("file_type", ""),
                            content_type=document_data.get("content_type", "file"),
                            file_url=file_url
                        )
                        total_documents += 1
                        
                        # Create product
                        product = Product.objects.create(
                            id=item.get("id"),
                            title=item.get("title", ""),
                            slug=item.get("slug", ""),
                            seller=seller,
                            price=Decimal(str(item.get("price", 0))),
                            discount_price=Decimal(str(item.get("discount_price", 0))),
                            discount=item.get("discount", 0),
                            poster_url=poster_url,
                            views_count=item.get("views_count", 0),
                            content_type=item.get("content_type", "file"),
                            demo_link=item.get("demo_link"),
                            file_url=item.get("file_url"),
                            document=document
                        )
                        
                        page_products += 1
                        total_products += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Error processing item on page {page}: {e}")
                        )
                        continue
                
                self.stdout.write(
                    self.style.SUCCESS(f"Page {page}: {page_products} products processed")
                )
                
                # Rate limiting
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                self.stdout.write(
                    self.style.ERROR(f"Request error on page {page}: {e}")
                )
                continue
            except ValueError as e:
                self.stdout.write(
                    self.style.ERROR(f"JSON parsing error on page {page}: {e}")
                )
                continue
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Unexpected error on page {page}: {e}")
                )
                continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nParsing completed successfully!\n"
                f"Total products: {total_products}\n"
                f"Total sellers: {total_sellers}\n"
                f"Total documents: {total_documents}"
            )
        )
