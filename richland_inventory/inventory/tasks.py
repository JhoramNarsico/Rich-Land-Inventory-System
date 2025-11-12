# inventory/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import F

from .models import Product

@shared_task
def send_low_stock_alerts_task():
    """
    A Celery task that finds low-stock products and sends an email alert.
    """
    print('Executing send_low_stock_alerts_task...') # For logging

    # Find products where quantity is at or below the reorder level and are active
    low_stock_products = Product.objects.filter(
        quantity__lte=F('reorder_level'),
        status=Product.Status.ACTIVE
    )

    if low_stock_products.exists():
        print(f'Found {low_stock_products.count()} products with low stock.')

        # You can configure this list in your settings or a database model
        recipient_list = ['manager@example.com'] 

        email_context = {
            'products': low_stock_products,
        }
        email_body = render_to_string('inventory/email/low_stock_alert.html', email_context)

        try:
            send_mail(
                subject='[Inventory System] Low Stock Alert',
                message='Some products are running low on stock. See the HTML version for details.', # Fallback
                html_message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            return f'Successfully sent low stock alert for {low_stock_products.count()} products.'
        except Exception as e:
            return f'Failed to send email: {e}'
    else:
        print('No products with low stock found.')
        return 'No products with low stock. No alert sent.'