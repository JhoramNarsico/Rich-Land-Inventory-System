# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from inventory.models import Product, StockTransaction

@login_required
def home(request):
    """View for the homepage dashboard with trends and caching."""
    
    # --- PART 1: LIVE DATA (Critical Alerts) ---
    # We query this EVERY time so alerts are never stale.
    active_products = Product.objects.filter(status=Product.Status.ACTIVE)
    
    low_stock_products = active_products.filter(
        Q(quantity=0) | Q(quantity__lte=F('reorder_level'))
    ).order_by('quantity')
    
    low_stock_products_count = low_stock_products.count()

    # --- PART 2: CACHED DATA (Heavy Math/Charts) ---
    cache_key = 'dashboard_data_v2' 
    dashboard_data = cache.get(cache_key)

    if not dashboard_data:
        # --- Dates for Trends ---
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # --- Totals ---
        total_products = active_products.count()
        
        total_stock_value_agg = active_products.aggregate(
            total_value=Sum(F('price') * F('quantity'))
        )
        total_stock_value = total_stock_value_agg['total_value'] or 0
        
        # --- TREND INDICATORS ---
        
        # A. SALES REVENUE TREND
        revenue_current = StockTransaction.objects.filter(
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            timestamp__gte=thirty_days_ago
        ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

        revenue_previous = StockTransaction.objects.filter(
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            timestamp__gte=sixty_days_ago,
            timestamp__lt=thirty_days_ago
        ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

        if revenue_previous > 0:
            revenue_trend = ((revenue_current - revenue_previous) / revenue_previous) * 100
        else:
            revenue_trend = 100 if revenue_current > 0 else 0

        # --- Lists for Tables ---
        recent_products = Product.objects.order_by('-date_created')[:5]
        
        top_stocked_in = StockTransaction.objects.filter(
            transaction_type='IN', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_in=Sum('quantity')).order_by('-total_in')[:5]

        top_stocked_out = StockTransaction.objects.filter(
            transaction_type='OUT', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_out=Sum('quantity')).order_by('-total_out')[:5]

        # Pack cached data
        dashboard_data = {
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'recent_products': recent_products,
            'top_stocked_in': top_stocked_in,
            'top_stocked_out': top_stocked_out,
            'monthly_revenue': revenue_current,
            'revenue_trend': revenue_trend,
        }
        # Cache for 5 minutes
        cache.set(cache_key, dashboard_data, 300) 
    
    # --- MERGE LIVE DATA INTO CONTEXT ---
    # This ensures low_stock is always fresh, while the rest is cached
    context = dashboard_data.copy()
    context['low_stock_products'] = low_stock_products
    context['low_stock_products_count'] = low_stock_products_count
    
    return render(request, 'home.html', context)