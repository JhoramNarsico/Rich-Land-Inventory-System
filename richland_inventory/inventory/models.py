# inventory/models.py

from django.db import models, transaction
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from decimal import Decimal

# --- NEW MODEL: POS SALE HEADER ---
class POSSale(models.Model):
    """
    Represents a single POS transaction (Receipt).
    Groups multiple StockTransactions (items) together.
    """
    receipt_id = models.CharField(max_length=50, unique=True, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "POS Sale"
        verbose_name_plural = "POS Sales"

    def __str__(self):
        return f"Receipt #{self.receipt_id}"

# --- EXISTING MODELS ---

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
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DEACTIVATED = 'DEACTIVATED', 'Deactivated'

    name = models.CharField(max_length=200, unique=True, help_text='Enter the product name', db_index=True)
    sku = models.CharField(max_length=100, unique=True, help_text='Enter the Stock Keeping Unit (SKU)', db_index=True)
    
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text='Unique URL-friendly name, leave blank to auto-generate')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text='Enter the price in PHP',
        validators=[MinValueValidator(Decimal('0.00'))] 
    )
    
    quantity = models.PositiveIntegerField(default=0, help_text='Enter the available quantity')
    reorder_level = models.PositiveIntegerField(default=5, help_text="Automatically alert when stock quantity falls to this level.")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    last_purchase_date = models.DateTimeField(null=True, blank=True, help_text="Date this product was last restocked.")

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
    
    class TransactionReason(models.TextChoices):
        SALE = 'SALE', 'Sale (Revenue)'
        PURCHASE_ORDER = 'PO', 'Purchase Order (Restock)'
        DAMAGE = 'DAMAGE', 'Damaged / Expired (Loss)'
        INTERNAL = 'INTERNAL', 'Internal Use / Demo'
        CORRECTION = 'CORRECTION', 'Inventory Correction / Mistake'
        RETURN = 'RETURN', 'Customer Return'
        INITIAL = 'INITIAL', 'Initial Stock'
        OTHER = 'OTHER', 'Other'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    
    # NEW: Link transaction to a POS Sale (Optional, as not all transactions are POS sales)
    pos_sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    transaction_reason = models.CharField(max_length=20, choices=TransactionReason.choices, default=TransactionReason.SALE)
    
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True, null=True, help_text="Reason for the transaction")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    selling_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Price per item at the time of a 'Stock Out' transaction.",
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        ordering = ['-timestamp']
        permissions = [
            ("can_adjust_stock", "Can adjust stock quantities"),
            ("can_view_history", "Can view product edit history"),
            ("can_view_reports", "Can view and generate reports"),
        ]
        indexes = [
            models.Index(fields=['transaction_type', 'timestamp']),
            models.Index(fields=['transaction_reason']),
        ]

    def __str__(self):
        return f'{self.transaction_type} ({self.get_transaction_reason_display()}) - {self.product.name}'

class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    
    def get_absolute_url(self):
        return reverse('inventory:supplier_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending (In Delivery)'),
        ('COMPLETED', 'Arrived (Ready to Receive)'),
        ('RECEIVED', 'Received & Stocked'),
        ('CANCELED', 'Canceled'),
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    def get_absolute_url(self):
        return reverse('inventory:purchaseorder_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"PO #{self.id} from {self.supplier.name}"

    def complete_order(self, user):
        if self.status == 'RECEIVED':
            return 

        with transaction.atomic():
            self.status = 'RECEIVED'
            self.save()

            for item in self.items.all():
                product = item.product
                
                StockTransaction.objects.create(
                    product=product,
                    transaction_type='IN',
                    transaction_reason=StockTransaction.TransactionReason.PURCHASE_ORDER,
                    quantity=item.quantity,
                    user=user,
                    notes=f'Received from Purchase Order PO #{self.id}'
                )
                
                product.quantity += item.quantity
                product.last_purchase_date = timezone.now()
                product.save()

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Price per item in PHP at time of purchase",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    def __str__(self):
        return f"{self.quantity} of {self.product.name}"