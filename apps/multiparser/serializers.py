from rest_framework import serializers
from .models import Seller, Document, Product, ProductView


class SellerSerializer(serializers.ModelSerializer):
    """Serializer for Seller model"""
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Seller
        fields = [
            'id', 'fullname', 'email', 'phone', 'address', 
            'is_active', 'created_at', 'updated_at', 'products_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'products_count']
    
    def get_products_count(self, obj):
        return obj.products.count()


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model"""
    
    class Meta:
        model = Document
        fields = [
            'id', 'page_count', 'file_size', 'file_type', 
            'short_content_url', 'content_duration', 'content_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductViewSerializer(serializers.ModelSerializer):
    """Serializer for ProductView model"""
    
    class Meta:
        model = ProductView
        fields = [
            'id', 'product', 'ip_address', 'user_agent', 
            'referrer', 'viewed_at', 'session_id'
        ]
        read_only_fields = ['id', 'viewed_at']


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model"""
    seller = SellerSerializer(read_only=True)
    seller_id = serializers.CharField(write_only=True)
    document = DocumentSerializer(read_only=True)
    document_id = serializers.UUIDField(write_only=True)
    discount_percentage = serializers.SerializerMethodField()
    is_on_sale = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'seller', 'seller_id', 'price', 
            'discount_price', 'discount', 'discount_percentage', 'is_on_sale',
            'final_price', 'poster_url', 'views_count', 'content_type',
            'demo_link', 'file_url', 'document', 'document_id', 'description',
            'tags', 'is_featured', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'views_count', 'created_at', 'updated_at']
    
    def get_discount_percentage(self, obj):
        return obj.get_discount_percentage()
    
    def get_is_on_sale(self, obj):
        return obj.is_on_sale()
    
    def get_final_price(self, obj):
        return obj.get_final_price()
    
    def validate(self, data):
        """Custom validation for product data"""
        price = data.get('price', 0)
        discount_price = data.get('discount_price', 0)
        
        if discount_price > price:
            raise serializers.ValidationError(
                "Discount price cannot be higher than original price"
            )
        
        return data
    
    def create(self, validated_data):
        """Create product with automatic discount calculation"""
        seller_id = validated_data.pop('seller_id')
        document_id = validated_data.pop('document_id')
        
        try:
            seller = Seller.objects.get(id=seller_id)
            document = Document.objects.get(id=document_id)
        except (Seller.DoesNotExist, Document.DoesNotExist):
            raise serializers.ValidationError("Invalid seller or document ID")
        
        validated_data['seller'] = seller
        validated_data['document'] = document
        
        # Auto-calculate discount percentage
        if validated_data.get('price', 0) > 0 and validated_data.get('discount_price', 0) < validated_data['price']:
            validated_data['discount'] = round(
                ((validated_data['price'] - validated_data['discount_price']) / validated_data['price']) * 100
            )
        else:
            validated_data['discount'] = 0
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update product with automatic discount calculation"""
        if 'seller_id' in validated_data:
            seller_id = validated_data.pop('seller_id')
            try:
                seller = Seller.objects.get(id=seller_id)
                validated_data['seller'] = seller
            except Seller.DoesNotExist:
                raise serializers.ValidationError("Invalid seller ID")
        
        if 'document_id' in validated_data:
            document_id = validated_data.pop('document_id')
            try:
                document = Document.objects.get(id=document_id)
                validated_data['document'] = document
            except Document.DoesNotExist:
                raise serializers.ValidationError("Invalid document ID")
        
        # Auto-calculate discount percentage
        price = validated_data.get('price', instance.price)
        discount_price = validated_data.get('discount_price', instance.discount_price)
        
        if price > 0 and discount_price < price:
            validated_data['discount'] = round(((price - discount_price) / price) * 100)
        else:
            validated_data['discount'] = 0
        
        return super().update(instance, validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for product listing"""
    seller_name = serializers.CharField(source='seller.fullname', read_only=True)
    document_type = serializers.CharField(source='document.file_type', read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'seller_name', 'price', 'discount_price',
            'discount_percentage', 'poster_url', 'views_count', 'content_type',
            'is_featured', 'is_active', 'created_at'
        ]
    
    def get_discount_percentage(self, obj):
        return obj.get_discount_percentage()


class ProductDetailSerializer(ProductSerializer):
    """Detailed serializer for single product view"""
    views = ProductViewSerializer(many=True, read_only=True, source='view_records')
    
    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['views']


class SellerDetailSerializer(SellerSerializer):
    """Detailed serializer for seller with products"""
    products = ProductListSerializer(many=True, read_only=True)
    
    class Meta(SellerSerializer.Meta):
        fields = SellerSerializer.Meta.fields + ['products']


class DocumentDetailSerializer(DocumentSerializer):
    """Detailed serializer for document with product info"""
    product_title = serializers.CharField(source='product.title', read_only=True)
    
    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ['product_title']
