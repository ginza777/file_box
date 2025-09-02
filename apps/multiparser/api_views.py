from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from .models import Seller, Document, Product, ProductView
from .serializers import (
    SellerSerializer, SellerDetailSerializer,
    DocumentSerializer, DocumentDetailSerializer,
    ProductSerializer, ProductListSerializer, ProductDetailSerializer,
    ProductViewSerializer
)


class SellerListCreateView(generics.ListCreateAPIView):
    """List all sellers or create a new seller"""
    queryset = Seller.objects.all()
    serializer_class = SellerSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['fullname', 'email', 'phone', 'address']
    ordering_fields = ['fullname', 'created_at', 'updated_at']
    ordering = ['fullname']

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SellerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a seller"""
    queryset = Seller.objects.all()
    serializer_class = SellerDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        return Seller.objects.prefetch_related('products')


class DocumentListCreateView(generics.ListCreateAPIView):
    """List all documents or create a new document"""
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'file_type']
    search_fields = ['file_type', 'content_type']
    ordering_fields = ['created_at', 'file_size', 'page_count']
    ordering = ['-created_at']

    @method_decorator(cache_page(60 * 10))  # Cache for 10 minutes
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a document"""
    queryset = Document.objects.all()
    serializer_class = DocumentDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        return Document.objects.select_related('product')


class ProductListCreateView(generics.ListCreateAPIView):
    """List all products or create a new product"""
    queryset = Product.objects.select_related('seller', 'document')
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'is_featured', 'is_active', 'seller']
    search_fields = ['title', 'description', 'tags', 'seller__fullname']
    ordering_fields = ['title', 'price', 'views_count', 'created_at', 'discount']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Filter by discount
        has_discount = self.request.query_params.get('has_discount')
        if has_discount == 'true':
            queryset = queryset.filter(discount__gt=0)
        elif has_discount == 'false':
            queryset = queryset.filter(discount=0)
        
        return queryset

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a product"""
    queryset = Product.objects.select_related('seller', 'document')
    serializer_class = ProductDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        return Product.objects.select_related('seller', 'document').prefetch_related('view_records')

    def retrieve(self, request, *args, **kwargs):
        """Track product view when retrieving"""
        instance = self.get_object()
        
        # Create view record
        ProductView.objects.create(
            product=instance,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=request.META.get('HTTP_REFERER', ''),
            session_id=request.session.session_key or 'anonymous'
        )
        
        # Update view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ProductViewListCreateView(generics.ListCreateAPIView):
    """List all product views or create a new view"""
    queryset = ProductView.objects.select_related('product')
    serializer_class = ProductViewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'ip_address']
    search_fields = ['product__title', 'ip_address', 'session_id']
    ordering_fields = ['viewed_at', 'product__title']
    ordering = ['-viewed_at']


class ProductViewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a product view"""
    queryset = ProductView.objects.select_related('product')
    serializer_class = ProductViewSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'


class ProductSearchView(generics.ListAPIView):
    """Advanced product search with multiple criteria"""
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['title', 'price', 'views_count', 'created_at', 'discount']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Product.objects.select_related('seller', 'document').filter(is_active=True)
        
        # Get search parameters
        query = self.request.query_params.get('q', '')
        content_type = self.request.query_params.get('content_type', '')
        seller_id = self.request.query_params.get('seller_id', '')
        min_price = self.request.query_params.get('min_price', '')
        max_price = self.request.query_params.get('max_price', '')
        has_discount = self.request.query_params.get('has_discount', '')
        is_featured = self.request.query_params.get('is_featured', '')
        
        # Apply filters
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__icontains=query) |
                Q(seller__fullname__icontains=query)
            )
        
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        if seller_id:
            queryset = queryset.filter(seller_id=seller_id)
        
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
        
        if has_discount == 'true':
            queryset = queryset.filter(discount__gt=0)
        elif has_discount == 'false':
            queryset = queryset.filter(discount=0)
        
        if is_featured == 'true':
            queryset = queryset.filter(is_featured=True)
        elif is_featured == 'false':
            queryset = queryset.filter(is_featured=False)
        
        return queryset

    @method_decorator(cache_page(60 * 3))  # Cache for 3 minutes
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductAnalyticsView(generics.ListAPIView):
    """Product analytics and statistics"""
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Product.objects.select_related('seller', 'document')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Calculate statistics
        total_products = queryset.count()
        active_products = queryset.filter(is_active=True).count()
        featured_products = queryset.filter(is_featured=True).count()
        products_with_discount = queryset.filter(discount__gt=0).count()
        
        # Price statistics
        avg_price = queryset.aggregate(avg_price=Avg('price'))['avg_price'] or 0
        total_views = queryset.aggregate(total_views=Sum('views_count'))['total_views'] or 0
        
        # Content type distribution
        content_type_stats = queryset.values('content_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Top viewed products
        top_viewed = queryset.order_by('-views_count')[:10]
        
        # Recent products
        recent_products = queryset.order_by('-created_at')[:5]
        
        data = {
            'statistics': {
                'total_products': total_products,
                'active_products': active_products,
                'featured_products': featured_products,
                'products_with_discount': products_with_discount,
                'average_price': round(avg_price, 2),
                'total_views': total_views,
            },
            'content_type_distribution': content_type_stats,
            'top_viewed_products': ProductListSerializer(top_viewed, many=True).data,
            'recent_products': ProductListSerializer(recent_products, many=True).data,
        }
        
        return Response(data)


class SellerAnalyticsView(generics.RetrieveAPIView):
    """Seller analytics and statistics"""
    serializer_class = SellerDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        seller = self.get_object()
        
        # Get seller's products
        products = seller.products.all()
        
        # Calculate statistics
        total_products = products.count()
        active_products = products.filter(is_active=True).count()
        featured_products = products.filter(is_featured=True).count()
        total_views = products.aggregate(total_views=Sum('views_count'))['total_views'] or 0
        avg_price = products.aggregate(avg_price=Avg('price'))['avg_price'] or 0
        
        # Content type distribution
        content_type_stats = products.values('content_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Top performing products
        top_products = products.order_by('-views_count')[:5]
        
        data = {
            'seller_info': SellerSerializer(seller).data,
            'statistics': {
                'total_products': total_products,
                'active_products': active_products,
                'featured_products': featured_products,
                'total_views': total_views,
                'average_price': round(avg_price, 2),
            },
            'content_type_distribution': content_type_stats,
            'top_products': ProductListSerializer(top_products, many=True).data,
        }
        
        return Response(data)
