from django.contrib import admin
from django.utils.html import format_html

# Import bot models only
from apps.bot.models import User, SubscribeChannel, Location, SearchQuery, Broadcast
from apps.multiparser.models import Seller, Document, Product, ProductView


class CustomAdminSite(admin.AdminSite):
    """Custom admin site with statistics"""

    def index(self, request, extra_context=None):
        """Add statistics to admin index"""
        extra_context = extra_context or {}

        # Get statistics
        total_files = Document.objects.count()
        total_products = Product.objects.count()
        total_sellers = Seller.objects.count()

        # Calculate file size statistics
        documents = Document.objects.all()
        total_size_mb = 0
        file_count = 0

        for doc in documents:
            try:
                # Extract numeric value from file_size (e.g., "1.2 MB" -> 1.2)
                size_str = doc.file_size
                if 'MB' in size_str:
                    size_value = float(size_str.replace(' MB', ''))
                    total_size_mb += size_value
                    file_count += 1
                elif 'KB' in size_str:
                    size_value = float(size_str.replace(' KB', '')) / 1024
                    total_size_mb += size_value
                    file_count += 1
                elif 'GB' in size_str:
                    size_value = float(size_str.replace(' GB', '')) * 1024
                    total_size_mb += size_value
                    file_count += 1
            except (ValueError, AttributeError):
                continue

        avg_size = total_size_mb / file_count if file_count > 0 else 0

        # Format statistics for display
        stats = {
            'total_files': total_files,
            'total_products': total_products,
            'total_sellers': total_sellers,
            'total_size_mb': round(total_size_mb, 2),
            'avg_size_mb': round(avg_size, 2),
            'file_count': file_count,
        }

        extra_context['stats'] = stats
        return super().index(request, extra_context)


# Create custom admin site instance
admin.site = CustomAdminSite(name='multiparser_admin')
admin.site.site_header = "Multi Parser Administration"
admin.site.site_title = "Multi Parser Admin Portal"
admin.site.index_title = "Welcome to Multi Parser Admin"


class SellerAdmin(admin.ModelAdmin):
    """Admin interface for Seller model"""
    list_display = ['id', 'fullname', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['id', 'fullname']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('products')

    def products_count(self, obj):
        return obj.products.count()

    products_count.short_description = 'Products Count'

from django.contrib import admin
from django.utils.html import format_html
from .models import Document, Product, Seller


class ProductInline(admin.StackedInline):
    """Inline view for Product linked to Document"""
    model = Product
    extra = 0
    fields = (
        'id', 'title', 'slug', 'seller', 'price', 'discount_price',
        'discount', 'poster_url', 'views_count', 'content_type',
        'demo_link', 'file_url', 'file_url_2', 'json_data',
        'created_at', 'updated_at'
    )
    readonly_fields = ('id', 'created_at', 'updated_at')
    show_change_link = True


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin interface for Document model with inline Product"""
    list_display = [
        'id', 'content_type', 'file_type', 'file_size',
        'page_count', 'download_status_display',
        'telegram_status', 'file_url_display',
        'file_path_display', 'is_indexed', 'created_at','parsed_content'
    ]
    list_filter = ['content_type', 'file_type', 'download_status', 'telegram_status', 'is_indexed']
    search_fields = ['id', 'file_type', 'content_type', 'file_url']
    readonly_fields = [
        'id', 'created_at', 'updated_at',
        'download_started_at', 'download_completed_at',
        'telegram_file_id', 'file_id', 'sent_at'
    ]
    inlines = [ProductInline]
    list_per_page = 25

    fieldsets = (
        ('📄 Document Info', {
            'fields': (
                'id', 'content_type', 'file_type',
                'file_size', 'file_size_bytes', 'page_count',

            )
        }),
        ('⬇️ Download Details', {
            'fields': (
                'download_status', 'download_started_at',
                'download_completed_at', 'download_error',
                'file_url', 'file_path', 'file_upload',
                'short_content_url', 'content_duration','parsed_content'
            ),
            'classes': ('collapse',)
        }),
        ('📲 Telegram', {
            'fields': (
                'telegram_status', 'telegram_file_id',
                'file_id', 'sent_to_channel', 'sent_at'
            ),
            'classes': ('collapse',)
        }),
        ('⚙️ Flags', {
            'fields': ('is_indexed', 'delete_from_server'),
            'classes': ('collapse',)
        }),
        ('⏱️ Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def download_status_display(self, obj):
        """Display download status with colors and icons"""
        status_colors = {
            'pending': '#6c757d',
            'downloading': '#ffc107',
            'downloaded': '#28a745',
            'failed': '#dc3545',
            'skipped': '#6f42c1',
        }
        color = status_colors.get(obj.download_status, '#6c757d')
        status_icons = {
            'pending': '⏳',
            'downloading': '⬇️',
            'downloaded': '✅',
            'failed': '❌',
            'skipped': '⏭️',
        }
        icon = status_icons.get(obj.download_status, '❓')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_download_status_display()
        )
    download_status_display.short_description = 'Download Status'
    download_status_display.admin_order_field = 'download_status'

    def file_url_display(self, obj):
        """Clickable file URL"""
        if obj.file_url:
            return format_html('<a href="{}" target="_blank">📄 File Link</a>', obj.file_url)
        return format_html('<span style="color: #6c757d;">❌ None</span>')
    file_url_display.short_description = 'File URL'

    def file_path_display(self, obj):
        """Show local file path status"""
        if obj.file_path:
            return format_html('<span style="color: #28a745;">✅ {}</span>', obj.file_path)
        return format_html('<span style="color: #6c757d;">❌ Not Downloaded</span>')
    file_path_display.short_description = 'Local File'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion if linked to product"""
        if obj and hasattr(obj, 'product'):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model"""
    list_display = ['id', 'title', 'seller', 'price', 'discount_price',
                    'discount_percentage', 'views_count',
                    'content_type', 'created_at']
    list_filter = ['content_type', 'created_at', 'seller']
    search_fields = ['id', 'title', 'seller__fullname']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_per_page = 25

    fieldsets = (
        ('📦 Product Info', {
            'fields': ('id', 'title', 'slug', 'content_type')
        }),
        ('💰 Pricing', {
            'fields': ('price', 'discount_price', 'discount')
        }),
        ('🔗 Relations', {
            'fields': ('seller', 'document')
        }),
        ('📝 Additional', {
            'fields': ('poster_url', 'views_count', 'demo_link', 'file_url', 'file_url_2', 'json_data'),
            'classes': ('collapse',)
        }),
        ('⏱️ Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def discount_percentage(self, obj):
        return f"{obj.get_discount_percentage()}%"
    discount_percentage.short_description = 'Discount %'


class ProductViewAdmin(admin.ModelAdmin):
    """Admin interface for ProductView model"""
    list_display = ['id', 'product', 'ip_address', 'viewed_at']
    list_filter = ['viewed_at', 'product']
    search_fields = ['product__title', 'ip_address','product__slug']
    readonly_fields = ['id', 'viewed_at']
    list_per_page = 25


# Simple admin classes for bot models
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'last_name', 'is_admin', 'is_blocked', 'last_active')
    list_filter = ('is_admin', 'is_blocked', 'last_active')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
    readonly_fields = ('telegram_id', 'created_at', 'updated_at')


class BotSubscribeChannelAdmin(admin.ModelAdmin):
    list_display = ('channel_username', 'channel_id', 'active', 'private', 'created_at')
    list_filter = ('active', 'private', 'created_at')
    search_fields = ('channel_username', 'channel_id')
    readonly_fields = ('created_at', 'updated_at')


class BotLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'latitude', 'longitude', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__first_name')
    readonly_fields = ('created_at',)


class BotSearchQueryAdmin(admin.ModelAdmin):
    list_display = ('query_text', 'user', 'is_deep_search', 'found_results', 'created_at')
    list_filter = ('is_deep_search', 'found_results', 'created_at')
    search_fields = ('query_text', 'user__username')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class BotBroadcastAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'scheduled_time', 'created_at')
    list_filter = ('status', 'scheduled_time', 'created_at')
    search_fields = ('from_chat_id', 'message_id')
    readonly_fields = ('from_chat_id', 'message_id', 'created_at')


# Register bot models with custom admin site
admin.site.register(User, BotUserAdmin)
admin.site.register(SubscribeChannel, BotSubscribeChannelAdmin)
admin.site.register(Location, BotLocationAdmin)
admin.site.register(SearchQuery, BotSearchQueryAdmin)
admin.site.register(Broadcast, BotBroadcastAdmin)
admin.site.register(Seller, SellerAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductView, ProductViewAdmin)
