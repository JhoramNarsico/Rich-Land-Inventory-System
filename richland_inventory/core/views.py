# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta

# Import both models
from inventory.models import Product, StockTransaction

@login_required
def home(request):
    """
    View for the homepage dashboard with calculated metrics and "Top Movers" widgets.
    """
    # --- Standard metric calculations (unchanged) ---
    total_products = Product.objects.count()
    total_stock_value_agg = Product.objects.aggregate(
        total_value=Sum(F('price') * F('quantity'))
    )
    total_stock_value = total_stock_value_agg['total_value'] or 0
    low_stock_products_count = Product.objects.filter(quantity__lte=5).count()
    recent_products = Product.objects.order_by('-date_created')[:5]

    # --- NEW: Top Movers Logic ---
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Query for Top 5 products with the most "Stock In" transactions
    top_stocked_in = StockTransaction.objects.filter(
        transaction_type='IN',
        timestamp__gte=thirty_days_ago
    ).values('product__name', 'product__slug') \
     .annotate(total_in=Sum('quantity')) \
     .order_by('-total_in')[:5]

    # Query for Top 5 products with the most "Stock Out" transactions
    top_stocked_out = StockTransaction.objects.filter(
        transaction_type='OUT',
        timestamp__gte=thirty_days_ago
    ).values('product__name', 'product__slug') \
     .annotate(total_out=Sum('quantity')) \
     .order_by('-total_out')[:5]

    context = {
        'total_products': total_products,
        'total_stock_value': f'{total_stock_value:,.2f}',
        'low_stock_products_count': low_stock_products_count,
        'recent_products': recent_products,
        
        # Add the new "Top Movers" data to the context
        'top_stocked_in': top_stocked_in,
        'top_stocked_out': top_stocked_out,
    }
    return render(request, 'home.html', context)