# inventory/admin.py

from django.contrib import admin
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder, PurchaseOrderItem

# --- THIS IS THE CORRECTED IMPORT ---
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
    
    def save_model(self, request, obj, form, change):
        original_obj = self.model.objects.get(pk=obj.pk) if obj.pk else None
        super().save_model(request, obj, form, change)
        
        if obj.status == 'COMPLETED' and (original_obj is None or original_obj.status != 'COMPLETED'):
            completed_time = timezone.now()
            for item in obj.items.all():
                StockTransaction.objects.create(
                    product=item.product,
                    transaction_type='IN',
                    quantity=item.quantity,
                    user=request.user,
                    notes=f'Received from Purchase Order PO #{obj.id}'
                )
                product = item.product
                product.quantity += item.quantity
                product.last_purchase_date = completed_time
                product.save()

            clear_dashboard_cache()