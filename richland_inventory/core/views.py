# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

# These models are needed for the dashboard queries
from inventory.models import Product, StockTransaction

# --- NEW UTILITY FUNCTION TO BUST THE CACHE ---
def clear_dashboard_cache():
    """Removes the dashboard data from the cache."""
    cache.delete('dashboard_data')


@login_required
def home(request):
    """View for the homepage dashboard with caching implemented."""
    
    cache_key = 'dashboard_data'
    dashboard_data = cache.get(cache_key)

    if not dashboard_data:
        # This block will only run if the cache is empty (or has been cleared)
        total_products = Product.objects.count()
        total_stock_value_agg = Product.objects.aggregate(
            total_value=Sum(F('price') * F('quantity'))
        )
        total_stock_value = total_stock_value_agg['total_value'] or 0
        # Assuming low stock is quantity <= 5, adjust if needed
        low_stock_products_count = Product.objects.filter(quantity__lte=5).count()
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
            'recent_products': recent_products,
            'top_stocked_in': top_stocked_in,
            'top_stocked_out': top_stocked_out,
        }
        # Keep the cache time reasonably high (10 minutes) for performance
        cache.set(cache_key, dashboard_data, 600) 
    
    return render(request, 'home.html', dashboard_data)