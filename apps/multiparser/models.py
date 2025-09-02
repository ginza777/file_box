import uuid
from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator


def upload_to(instance, filename):
    """Generate upload path for files"""
    return f'documents/{instance.id}/{filename}'


class Seller(models.Model):
    """Seller model for product vendors"""
    id = models.CharField(max_length=50, primary_key=True, verbose_name="Seller ID")
    fullname = models.CharField(max_length=200, verbose_name="Full Name")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Seller"
        verbose_name_plural = "Sellers"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.fullname} ({self.id})"

    def get_absolute_url(self):
        return reverse('admin:multiparser_seller_change', args=[str(self.id)])


class Document(models.Model):
    """Document model for file information"""
    CONTENT_TYPE_CHOICES = [
        ('file', 'File'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('presentation', 'Presentation'),
    ]
    
    DOWNLOAD_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('downloading', 'Downloading'),
        ('downloaded', 'Downloaded'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page_count = models.PositiveIntegerField(blank=True, null=True, verbose_name="Page Count")
    file_size = models.CharField(max_length=50, verbose_name="File Size")
    file_type = models.CharField(max_length=20, verbose_name="File Type")
    short_content_url = models.URLField(blank=True, null=True, verbose_name="Short Content URL")
    content_duration = models.DurationField(blank=True, null=True, verbose_name="Content Duration")
    content_type = models.CharField(
        max_length=20, 
        choices=CONTENT_TYPE_CHOICES, 
        default='file',
        verbose_name="Content Type"
    )
    file_url = models.URLField(blank=True, null=True, verbose_name="File URL", help_text="Direct link to the document file")
    file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Local File Path", help_text="Path where file is saved locally")
    file_upload = models.FileField(upload_to=upload_to, blank=True, null=True, verbose_name="File Upload", help_text="Uploaded file for processing")
    download_status = models.CharField(
        max_length=20,
        choices=DOWNLOAD_STATUS_CHOICES,
        default='pending',
        verbose_name="Download Status"
    )
    download_started_at = models.DateTimeField(blank=True, null=True, verbose_name="Download Started At")
    download_completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Download Completed At")
    download_error = models.TextField(blank=True, null=True, verbose_name="Download Error")
    
    # Telegram integration
    file_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Telegram File ID", help_text="File ID after sending to Telegram channel")
    sent_to_channel = models.BooleanField(default=False, verbose_name="Sent to Channel")
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Sent to Channel At")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.content_type} - {self.file_type} ({self.file_size})"

    def get_absolute_url(self):
        return reverse('admin:multiparser_document_change', args=[str(self.id)])
    
    def get_file_url_display(self):
        """Get a clickable file URL for admin display"""
        if self.file_url:
            return f'<a href="{self.file_url}" target="_blank">Download File</a>'
        return 'No file URL available'
    
    def has_file_url(self):
        """Check if document has a file URL"""
        return bool(self.file_url)


class Product(models.Model):
    """Product model for digital products"""
    id = models.IntegerField(primary_key=True, verbose_name="Product ID")
    title = models.CharField(max_length=500, verbose_name="Title")
    slug = models.SlugField(max_length=500, unique=True, verbose_name="Slug")
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='products', verbose_name="Seller")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Discount Price")
    discount = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
        verbose_name="Discount Percentage"
    )
    poster_url = models.URLField(blank=True, null=True, verbose_name="Poster URL")
    views_count = models.PositiveIntegerField(default=0, verbose_name="Views Count")
    content_type = models.CharField(max_length=20, default='file', verbose_name="Content Type")
    demo_link = models.URLField(blank=True, null=True, verbose_name="Demo Link")
    file_url = models.URLField(blank=True, null=True, verbose_name="File URL")
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='product', verbose_name="Document")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('admin:multiparser_product_change', args=[str(self.id)])

    def get_discount_percentage(self):
        """Calculate discount percentage"""
        if self.discount_price and self.price:
            return round(((self.price - self.discount_price) / self.price) * 100, 2)
        return 0

    def delete(self, *args, **kwargs):
        """Custom delete method to handle cleanup"""
        # Store references before deletion
        seller_id = self.seller.id
        seller_fullname = self.seller.fullname
        
        # Delete the product first (this will cascade to document)
        super().delete(*args, **kwargs)
        
        # Check if seller has no more products and delete if orphaned
        try:
            seller = Seller.objects.get(id=seller_id)
            if seller.products.count() == 0:
                seller.delete()
        except Seller.DoesNotExist:
            pass  # Seller was already deleted


class ProductView(models.Model):
    """Product view tracking model"""
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='views', verbose_name="Product")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP Address")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    viewed_at = models.DateTimeField(auto_now_add=True, verbose_name="Viewed At")

    class Meta:
        verbose_name = "Product View"
        verbose_name_plural = "Product Views"
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.product.title} - {self.viewed_at}"
