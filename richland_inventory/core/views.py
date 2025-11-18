# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from inventory.models import Product, StockTransaction

# The clear_dashboard_cache function is NO LONGER HERE. It has been moved.

@login_required
def home(request):
    """View for the homepage dashboard with caching and improved low-stock alerts."""
    
    cache_key = 'dashboard_data' # This key must match the one in cache_utils.py
    dashboard_data = cache.get(cache_key)

    if not dashboard_data:
        active_products = Product.objects.filter(status=Product.Status.ACTIVE)

        total_products = active_products.count()
        
        total_stock_value_agg = active_products.aggregate(
            total_value=Sum(F('price') * F('quantity'))
        )
        total_stock_value = total_stock_value_agg['total_value'] or 0
        
        low_stock_products = active_products.filter(
            Q(quantity=0) | Q(quantity__lt=F('reorder_level'))
        ).order_by('quantity')
        
        low_stock_products_count = low_stock_products.count()

        recent_products = Product.objects.order_by('-date_created')[:5]
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        top_stocked_in = StockTransaction.objects.filter(
            transaction_type='IN', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_in=Sum('quantity')).order_by('-total_in')[:5]

        top_stocked_out = StockTransaction.objects.filter(
            transaction_type='OUT', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_out=Sum('quantity')).order_by('-total_out')[:5]

        dashboard_data = {
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_products_count': low_stock_products_count,
            'low_stock_products': low_stock_products,
            'recent_products': recent_products,
            'top_stocked_in': top_stocked_in,
            'top_stocked_out': top_stocked_out,
        }
        cache.set(cache_key, dashboard_data, 300) 
    
    return render(request, 'home.html', dashboard_data)