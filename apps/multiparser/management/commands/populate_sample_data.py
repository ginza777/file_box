from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Seller, Document, Product
import random


class Command(BaseCommand):
    help = 'Populate database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create sample sellers
        sellers_data = [
            {
                'id': '201745',
                'fullname': 'Exclusive qog\'ozlar',
                'email': 'exclusive@example.com',
                'phone': '+998901234567',
                'address': 'Tashkent, Uzbekistan'
            },
            {
                'id': '201746',
                'fullname': 'Digital Solutions',
                'email': 'digital@example.com',
                'phone': '+998901234568',
                'address': 'Samarkand, Uzbekistan'
            },
            {
                'id': '201747',
                'fullname': 'Creative Studio',
                'email': 'creative@example.com',
                'phone': '+998901234569',
                'address': 'Bukhara, Uzbekistan'
            }
        ]
        
        sellers = []
        for seller_data in sellers_data:
            seller, created = Seller.objects.get_or_create(
                id=seller_data['id'],
                defaults=seller_data
            )
            sellers.append(seller)
            if created:
                self.stdout.write(f'Created seller: {seller.fullname}')
        
        # Create sample documents
        documents_data = [
            {
                'page_count': 1,
                'file_size': '17.81 KB',
                'file_type': '.docx',
                'content_type': 'file'
            },
            {
                'page_count': 25,
                'file_size': '2.5 MB',
                'file_type': '.pdf',
                'content_type': 'file'
            },
            {
                'page_count': 15,
                'file_size': '1.8 MB',
                'file_type': '.pptx',
                'content_type': 'presentation'
            },
            {
                'page_count': 0,
                'file_size': '45.2 MB',
                'file_type': '.mp4',
                'content_type': 'video',
                'content_duration': timezone.timedelta(minutes=15)
            }
        ]
        
        documents = []
        for doc_data in documents_data:
            document = Document.objects.create(**doc_data)
            documents.append(document)
            self.stdout.write(f'Created document: {document.content_type} - {document.file_type}')
        
        # Create sample products
        products_data = [
            {
                'id': 369803,
                'title': 'Yashil iqtisodiyot strategiyalari',
                'slug': 'taqdimotlar-iqtisodiyot-yashil-iqtisodiyot-strategiyalari',
                'price': 16500,
                'discount_price': 16500,
                'discount': 0,
                'poster_url': 'https://d2co7bxjtnp5o.cloudfront.net/media/Images/403b5a6b-fca8-43aa-9149-b764918621de.docx_page-1_generate.webp',
                'content_type': 'file',
                'description': 'Comprehensive guide to green economy strategies and sustainable development approaches.',
                'tags': 'green economy, sustainability, strategy, development',
                'is_featured': True
            },
            {
                'id': 369804,
                'title': 'Digital Marketing Fundamentals',
                'slug': 'digital-marketing-fundamentals-course',
                'price': 25000,
                'discount_price': 20000,
                'discount': 20,
                'poster_url': 'https://example.com/poster2.jpg',
                'content_type': 'course',
                'description': 'Learn the basics of digital marketing including SEO, social media, and content marketing.',
                'tags': 'digital marketing, SEO, social media, content',
                'is_featured': False
            },
            {
                'id': 369805,
                'title': 'Business Strategy Masterclass',
                'slug': 'business-strategy-masterclass-presentation',
                'price': 30000,
                'discount_price': 30000,
                'discount': 0,
                'poster_url': 'https://example.com/poster3.jpg',
                'content_type': 'presentation',
                'description': 'Advanced business strategy concepts and implementation frameworks.',
                'tags': 'business strategy, management, leadership, planning',
                'is_featured': True
            },
            {
                'id': 369806,
                'title': 'Python Programming for Beginners',
                'slug': 'python-programming-beginners-ebook',
                'price': 18000,
                'discount_price': 15000,
                'discount': 17,
                'poster_url': 'https://example.com/poster4.jpg',
                'content_type': 'ebook',
                'description': 'Complete beginner guide to Python programming with practical examples.',
                'tags': 'python, programming, beginners, coding',
                'is_featured': False
            }
        ]
        
        for i, product_data in enumerate(products_data):
            product_data['seller'] = sellers[i % len(sellers)]
            product_data['document'] = documents[i % len(documents)]
            
            product = Product.objects.create(**product_data)
            self.stdout.write(f'Created product: {product.title}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created sample data!')
        )
        self.stdout.write(f'Created {len(sellers)} sellers')
        self.stdout.write(f'Created {len(documents)} documents')
        self.stdout.write(f'Created {len(products_data)} products')
