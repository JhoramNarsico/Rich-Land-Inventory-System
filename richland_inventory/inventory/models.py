# inventory/models.py

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings

class Product(models.Model):
    name = models.CharField(max_length=200, unique=True, help_text='Enter the product name')
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text='Unique URL-friendly name, leave blank to auto-generate')
    sku = models.CharField(max_length=100, unique=True, help_text='Enter the Stock Keeping Unit (SKU)')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Enter the price')
    quantity = models.PositiveIntegerField(default=0, help_text='Enter the available quantity')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created']

    def get_absolute_url(self):
        """Returns the URL to access a detail record for this product."""
        return reverse('inventory:product_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        """Override the save method to auto-generate the slug if it is not set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        """String for representing the Model object."""
        return self.name

# --- NEW MODEL ADDED BELOW ---

class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, help_text="Reason for the transaction (e.g., 'Sale to customer X', 'New shipment received')")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        # Add permissions for this new model
        permissions = [
            ("can_adjust_stock", "Can adjust stock quantities"),
        ]

    def __str__(self):
        return f'{self.transaction_type} - {self.product.name} ({self.quantity}) on {self.timestamp.strftime("%Y-%m-%d")}'