# inventory/admin.py

from django.contrib import admin
from django.utils import timezone
from django.db import transaction
from simple_history.admin import SimpleHistoryAdmin
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder, PurchaseOrderItem
from core.cache_utils import clear_dashboard_cache

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'sku', 'category', 'quantity', 'price', 'status', 'last_edited_on', 'last_edited_by')
    list_filter = ('category', 'status', 'date_created', 'date_updated')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('quantity', 'price', 'status')
    
    def get_actions(self, request):
        """Remove the 'delete_selected' action for non-superusers."""
        actions = super().get_actions(request)
        if 'delete_selected' in actions and not request.user.is_superuser:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of products by non-superusers."""
        return request.user.is_superuser

    @admin.display(description='Last Edited On')
    def last_edited_on(self, obj):
        last_record = obj.history.first()
        if last_record:
            return last_record.history_date.strftime('%Y-%m-%d %H:%M')
        return "N/A"

    @admin.display(description='Last Edited By')
    def last_edited_by(self, obj):
        last_record = obj.history.first()
        if last_record and last_record.history_user:
            return last_record.history_user.username
        return "N/A"

@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'transaction_type', 'quantity', 'selling_price', 'user', 'timestamp')
    list_filter = ('transaction_type', 'timestamp', 'user')
    search_fields = ('product__name',)

    # FIX: Prevent manual creation/updates via Admin to avoid desync with Product.quantity
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # FIX: Ensure cache is cleared if a superuser deletes a transaction
    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        clear_dashboard_cache()

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'contact_person')
    search_fields = ('name', 'email')

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'status', 'order_date')
    list_filter = ('status', 'supplier', 'order_date')
    inlines = [PurchaseOrderItemInline]
    
    # FIX: Completely rewritten logic to handle status changes and inline items correctly
    def save_related(self, request, form, formsets, change):
        """
        This method runs AFTER the parent model (PO) is saved and AFTER inlines are saved.
        This is critical because we need the Items to exist before we add stock.
        """
        super().save_related(request, form, formsets, change)
        
        obj = form.instance
        
        # Get the state of the object BEFORE the user made changes in this request.
        # We stored this in save_model below, or we can check DB if it's a new object.
        # However, since save_related runs after save_model, we need to rely on what we determined earlier.
        
        if not hasattr(self, '_previous_status'):
            # If for some reason save_model didn't run or logic failed, assume no change to be safe
            return

        previous_status = self._previous_status
        current_status = obj.status
        
        # 1. PENDING -> COMPLETED (Add Stock)
        if current_status == 'COMPLETED' and previous_status != 'COMPLETED':
            self._adjust_stock(request, obj, 'IN')
            obj.items.all().update(last_purchase_date=timezone.now()) # Helper if needed, though logic is below

        # 2. COMPLETED -> PENDING (Remove Stock - Correction)
        elif previous_status == 'COMPLETED' and current_status != 'COMPLETED':
            self._adjust_stock(request, obj, 'OUT')
        
        clear_dashboard_cache()

    def save_model(self, request, obj, form, change):
        """
        Capture the status of the PO before the changes are committed.
        """
        if change:
            # Fetch the existing object from DB to see what the status WAS
            original = PurchaseOrder.objects.get(pk=obj.pk)
            self._previous_status = original.status
        else:
            self._previous_status = None # New object
            
        super().save_model(request, obj, form, change)

    def _adjust_stock(self, request, po, type):
        """
        Helper to iterate items and adjust stock.
        type: 'IN' (Adding stock) or 'OUT' (Reverting stock)
        """
        with transaction.atomic():
            for item in po.items.all():
                product = item.product
                qty = item.quantity
                
                if type == 'IN':
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='IN',
                        quantity=qty,
                        user=request.user,
                        notes=f'Received from Purchase Order PO #{po.id}'
                    )
                    product.quantity += qty
                    product.last_purchase_date = timezone.now()
                
                elif type == 'OUT':
                    # Create a correction transaction
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='OUT',
                        quantity=qty,
                        user=request.user,
                        notes=f'Correction: Reverted Purchase Order PO #{po.id} status'
                    )
                    # Ensure we don't go negative if possible, though logic dictates we remove what we added
                    product.quantity = max(0, product.quantity - qty)
                
                product.save()