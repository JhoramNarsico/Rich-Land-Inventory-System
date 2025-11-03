# inventory/models.py

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Product(models.Model):
    # --- ADD db_index=True to these fields ---
    name = models.CharField(max_length=200, unique=True, help_text='Enter the product name', db_index=True)
    sku = models.CharField(max_length=100, unique=True, help_text='Enter the Stock Keeping Unit (SKU)', db_index=True)
    
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text='Unique URL-friendly name, leave blank to auto-generate')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Enter the price in PHP')
    quantity = models.PositiveIntegerField(default=0, help_text='Enter the available quantity')
    reorder_level = models.PositiveIntegerField(default=5, help_text="Automatically alert when stock quantity falls to this level.")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    class Meta:
        ordering = ['-date_created']
    def get_absolute_url(self):
        return reverse('inventory:product_detail', kwargs={'slug': self.slug})
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self):
        return self.name

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
        permissions = [("can_adjust_stock", "Can adjust stock quantities")]
    def __str__(self):
        return f'{self.transaction_type} - {self.product.name} ({self.quantity}) on {self.timestamp.strftime("%Y-%m-%d")}'

class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('CANCELED', 'Canceled'),
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    def __str__(self):
        return f"PO #{self.id} from {self.supplier.name}"

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per item in PHP at time of purchase")
    def __str__(self):
        return f"{self.quantity} of {self.product.name}"