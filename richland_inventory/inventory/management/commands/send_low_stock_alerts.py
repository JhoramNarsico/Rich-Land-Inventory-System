# inventory/management/commands/send_low_stock_alerts.py

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models

# --- THIS IS THE CORRECTED IMPORT ---
from inventory.models import Product

class Command(BaseCommand):
    help = 'Checks for products with low stock and sends an email alert.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Checking for low stock products...')

        # Find products where quantity is at or below the reorder level and are active
        low_stock_products = Product.objects.filter(
            quantity__lte=models.F('reorder_level'),
            status=Product.Status.ACTIVE
        )

        if low_stock_products.exists():
            self.stdout.write(self.style.WARNING(f'Found {low_stock_products.count()} products with low stock.'))

            # --- Configure your recipients here ---
            # Ideally, this would come from a settings file or a user model with a specific role
            recipient_list = ['stock.controller@example.com', 'manager@example.com']

            email_context = {
                'products': low_stock_products,
            }
            email_body = render_to_string('inventory/email/low_stock_alert.html', email_context)

            try:
                send_mail(
                    subject='[Inventory System] Low Stock Alert',
                    message='Some products are running low on stock. Please see the attached HTML for details.', # Fallback message
                    html_message=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@example.com',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS('Successfully sent low stock alert email.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send email: {e}'))

        else:
            self.stdout.write(self.style.SUCCESS('No products with low stock. No alert sent.'))