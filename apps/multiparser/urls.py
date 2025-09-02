from django.urls import path
from . import views, api_views

app_name = 'multiparser'

urlpatterns = [
    # API URLs
    path('api/products/', api_views.ProductListCreateView.as_view(), name='product-list-create'),
    path('api/products/<int:pk>/', api_views.ProductDetailView.as_view(), name='product-detail'),
    path('api/sellers/', api_views.SellerListCreateView.as_view(), name='seller-list-create'),
    path('api/sellers/<str:pk>/', api_views.SellerDetailView.as_view(), name='seller-detail'),
    path('api/documents/', api_views.DocumentListCreateView.as_view(), name='document-list-create'),
    path('api/documents/<uuid:pk>/', api_views.DocumentDetailView.as_view(), name='document-detail'),
    
    # Main URLs
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('sellers/', views.seller_list, name='seller_list'),
    path('sellers/<str:pk>/', views.seller_detail, name='seller_detail'),
]
