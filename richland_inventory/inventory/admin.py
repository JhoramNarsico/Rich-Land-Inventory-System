# inventory/admin.py

from django.contrib import admin
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder, PurchaseOrderItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'quantity', 'price', 'date_updated')
    list_filter = ('category', 'date_created', 'date_updated')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('quantity', 'price')

@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'transaction_type', 'quantity', 'user', 'timestamp')
    list_filter = ('transaction_type', 'timestamp', 'user')
    search_fields = ('product__name',)

# --- NEW ADMIN CONFIGURATIONS FOR PURCHASING ---

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'contact_person')
    search_fields = ('name', 'email')

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1 # Show one empty line for a new item by default

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'status', 'order_date')
    list_filter = ('status', 'supplier', 'order_date')
    inlines = [PurchaseOrderItemInline]
    
    def save_model(self, request, obj, form, change):
        # We need the original object to check if the status changed
        original_obj = self.model.objects.get(pk=obj.pk) if obj.pk else None
        
        super().save_model(request, obj, form, change)
        
        # Check if the status has just been changed to 'COMPLETED'
        if obj.status == 'COMPLETED' and (original_obj is None or original_obj.status != 'COMPLETED'):
            # This is a one-time action when the PO is finalized
            for item in obj.items.all():
                # 1. Create the StockTransaction record
                StockTransaction.objects.create(
                    product=item.product,
                    transaction_type='IN',
                    quantity=item.quantity,
                    user=request.user,
                    notes=f'Received from Purchase Order PO #{obj.id}'
                )
                # 2. Update the master quantity on the Product model
                item.product.quantity += item.quantity
                item.product.save()