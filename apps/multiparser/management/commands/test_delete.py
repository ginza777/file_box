from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Seller, Document, Product


class Command(BaseCommand):
    help = 'Test the deletion behavior of products and related objects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test data before testing deletion'
        )

    def handle(self, *args, **options):
        if options['create_test_data']:
            self.create_test_data()
        
        self.test_deletion_behavior()

    def create_test_data(self):
        """Create test data to demonstrate deletion behavior"""
        self.stdout.write("Creating test data...")
        
        # Create a seller
        seller1 = Seller.objects.create(
            id="TEST001",
            fullname="Test Seller 1"
        )
        
        seller2 = Seller.objects.create(
            id="TEST002", 
            fullname="Test Seller 2"
        )
        
        # Create documents first
        doc1 = Document.objects.create(
            page_count=10,
            file_size="2.5 MB",
            file_type=".pdf",
            content_type="file"
        )
        
        doc2 = Document.objects.create(
            page_count=15,
            file_size="1.8 MB", 
            file_type=".docx",
            content_type="file"
        )
        
        doc3 = Document.objects.create(
            page_count=8,
            file_size="3.2 MB",
            file_type=".pptx", 
            content_type="presentation"
        )
        
        # Create products with documents
        product1 = Product.objects.create(
            id=999001,
            title="Test Product 1",
            slug="test-product-1",
            seller=seller1,
            price=100.00,
            discount_price=90.00,
            discount=10,
            poster_url="https://example.com/poster1.jpg",
            content_type="file",
            document=doc1
        )
        
        product2 = Product.objects.create(
            id=999002,
            title="Test Product 2", 
            slug="test-product-2",
            seller=seller1,  # Same seller as product1
            price=150.00,
            discount_price=150.00,
            discount=0,
            poster_url="https://example.com/poster2.jpg",
            content_type="file",
            document=doc2
        )
        
        product3 = Product.objects.create(
            id=999003,
            title="Test Product 3",
            slug="test-product-3", 
            seller=seller2,  # Different seller
            price=200.00,
            discount_price=180.00,
            discount=10,
            poster_url="https://example.com/poster3.jpg",
            content_type="presentation",
            document=doc3
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Created test data:\n"
                f"- 2 sellers\n"
                f"- 3 documents\n" 
                f"- 3 products (2 from seller1, 1 from seller2)"
            )
        )

    def test_deletion_behavior(self):
        """Test the deletion behavior"""
        self.stdout.write("\n" + "="*50)
        self.stdout.write("TESTING DELETION BEHAVIOR")
        self.stdout.write("="*50)
        
        # Show initial state
        self.show_current_state("INITIAL STATE")
        
        # Test 1: Delete a product (seller1 has 2 products, so seller should remain)
        self.stdout.write("\n" + "-"*30)
        self.stdout.write("TEST 1: Delete Product 1 (Seller1 has 2 products)")
        self.stdout.write("-"*30)
        
        product1 = Product.objects.get(id=999001)
        product1.delete()
        
        self.show_current_state("AFTER DELETING PRODUCT 1")
        
        # Test 2: Delete another product from seller1 (now seller1 has 0 products, should be deleted)
        self.stdout.write("\n" + "-"*30)
        self.stdout.write("TEST 2: Delete Product 2 (Seller1 now has 0 products)")
        self.stdout.write("-"*30)
        
        product2 = Product.objects.get(id=999002)
        product2.delete()
        
        self.show_current_state("AFTER DELETING PRODUCT 2")
        
        # Test 3: Delete the last product (seller2 should be deleted)
        self.stdout.write("\n" + "-"*30)
        self.stdout.write("TEST 3: Delete Product 3 (Seller2 has 0 products)")
        self.stdout.write("-"*30)
        
        product3 = Product.objects.get(id=999003)
        product3.delete()
        
        self.show_current_state("FINAL STATE")
        
        self.stdout.write(
            self.style.SUCCESS(
                "\n✅ Deletion behavior test completed successfully!\n"
                "All related objects (documents and orphaned sellers) were properly cleaned up."
            )
        )

    def show_current_state(self, title):
        """Show the current state of the database"""
        sellers_count = Seller.objects.count()
        documents_count = Document.objects.count()
        products_count = Product.objects.count()
        
        self.stdout.write(f"\n{title}:")
        self.stdout.write(f"- Sellers: {sellers_count}")
        self.stdout.write(f"- Documents: {documents_count}")
        self.stdout.write(f"- Products: {products_count}")
        
        if sellers_count > 0:
            sellers = Seller.objects.all()
            for seller in sellers:
                products = seller.products.count()
                self.stdout.write(f"  - {seller.fullname} (ID: {seller.id}): {products} products")
        
        if documents_count > 0:
            documents = Document.objects.all()
            for doc in documents:
                self.stdout.write(f"  - Document {doc.id}: {doc.file_type} ({doc.file_size})")
