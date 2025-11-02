# core/views.py

import json
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.db.models.functions import TruncDay
from django.shortcuts import render
from django.utils import timezone

from inventory.models import Product, StockTransaction

@login_required
def home(request):
    """
    View for the homepage dashboard with metrics and tabbed stock movement data.
    """
    # --- Metric calculations (unchanged) ---
    total_products = Product.objects.count()
    total_stock_value_agg = Product.objects.aggregate(
        total_value=Sum(F('price') * F('quantity'))
    )
    total_stock_value = total_stock_value_agg['total_value'] or 0
    low_stock_products_count = Product.objects.filter(quantity__lte=5).count()
    recent_products = Product.objects.order_by('-date_created')[:5]

    # --- Graphing Logic (unchanged) ---
    now = timezone.now()
    start_date = now - timedelta(days=29)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    transactions = StockTransaction.objects.filter(timestamp__gte=start_date) \
        .annotate(day=TruncDay('timestamp')) \
        .values('day', 'transaction_type') \
        .annotate(total_quantity=Sum('quantity')) \
        .order_by('day')
    stock_in_map = {t['day'].date(): t['total_quantity'] for t in transactions if t['transaction_type'] == 'IN'}
    stock_out_map = {t['day'].date(): t['total_quantity'] for t in transactions if t['transaction_type'] == 'OUT'}
    date_range = [(start_date.date() + timedelta(days=i)) for i in range(30)]
    graph_labels = [d.strftime('%b %d') for d in date_range]
    stock_in_values = [stock_in_map.get(d, 0) for d in date_range]
    stock_out_values = [stock_out_map.get(d, 0) for d in date_range]

    # --- ADD THIS LINE to get recent transactions for the data table ---
    recent_transactions = StockTransaction.objects.select_related('product', 'user').all()[:10]

    context = {
        'total_products': total_products,
        'total_stock_value': f'{total_stock_value:,.2f}',
        'low_stock_products_count': low_stock_products_count,
        'recent_products': recent_products,
        'graph_labels': json.dumps(graph_labels),
        'stock_in_values': json.dumps(stock_in_values),
        'stock_out_values': json.dumps(stock_out_values),
        'recent_transactions': recent_transactions, # Add the new data to the context
    }
    return render(request, 'home.html', context)