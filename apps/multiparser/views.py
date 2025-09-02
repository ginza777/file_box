from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from apps.multiparser.models import Product, Seller, Document
from django.db import models


def home(request):
    """Home page view"""
    return render(request, 'multiparser/home.html', {
        'total_products': Product.objects.count(),
        'total_sellers': Seller.objects.count(),
        'total_documents': Document.objects.count(),
    })


def product_list(request):
    """Product list view"""
    products = Product.objects.select_related('seller', 'document').all()
    return render(request, 'multiparser/product_list.html', {'products': products})


def product_detail(request, pk):
    """Product detail view"""
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'multiparser/product_detail.html', {'product': product})


def seller_list(request):
    """Seller list view"""
    sellers = Seller.objects.prefetch_related('products').all()
    return render(request, 'multiparser/seller_list.html', {'sellers': sellers})


def seller_detail(request, pk):
    """Seller detail view"""
    seller = get_object_or_404(Seller, pk=pk)
    return render(request, 'multiparser/seller_detail.html', {'seller': seller})


@login_required
def admin_dashboard(request):
    """Admin dashboard view"""
    stats = {
        'total_products': Product.objects.count(),
        'total_sellers': Seller.objects.count(),
        'total_documents': Document.objects.count(),
        'recent_products': Product.objects.select_related('seller').order_by('-created_at')[:10],
        'recent_documents': Document.objects.order_by('-created_at')[:10],
    }
    return render(request, 'multiparser/admin_dashboard.html', stats)


def search_documents(request):
    """Search documents view"""
    query = request.GET.get('q', '')
    if query:
        # Basic search implementation - can be enhanced with Elasticsearch
        documents = Document.objects.filter(
            models.Q(file_type__icontains=query) |
            models.Q(content_type__icontains=query)
        )
    else:
        documents = Document.objects.none()
    
    return render(request, 'multiparser/search_results.html', {
        'documents': documents,
        'query': query
    })
