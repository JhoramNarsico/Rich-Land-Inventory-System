# inventory/models.py

from django.db import models
from django.urls import reverse

class Product(models.Model):
    name = models.CharField(max_length=200, help_text='Enter the product name')
    sku = models.CharField(max_length=100, unique=True, help_text='Enter the Stock Keeping Unit (SKU)')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Enter the price')
    quantity = models.PositiveIntegerField(default=0, help_text='Enter the available quantity')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created'] # Show newest products first

    def get_absolute_url(self):
        """Returns the URL to access a detail record for this product."""
        return reverse('product-detail', args=[str(self.id)])

    def __str__(self):
        """String for representing the Model object."""
        return self.name