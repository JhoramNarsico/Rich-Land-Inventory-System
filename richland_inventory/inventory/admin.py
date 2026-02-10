# inventory/admin.py

from django.contrib import admin
from django.utils import timezone
from django.db import transaction
from simple_history.admin import SimpleHistoryAdmin
from .models import Product, StockTransaction, Category, Supplier, PurchaseOrder, PurchaseOrderItem, POSSale, HydraulicSow, Expense, ExpenseCategory
from core.cache_utils import clear_dashboard_cache

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',) 

@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'sku', 'category', 'quantity', 'price', 'status', 'last_edited_on', 'last_edited_by')
    list_filter = ('category', 'status', 'date_created', 'date_updated')
    search_fields = ('name', 'sku') 
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('quantity', 'price', 'status')
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions and not request.user.is_superuser:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
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
    list_display = ('product', 'transaction_type', 'transaction_reason', 'quantity', 'selling_price', 'user', 'timestamp')
    list_filter = ('transaction_type', 'transaction_reason', 'timestamp', 'user')
    search_fields = ('product__name',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        clear_dashboard_cache()

# --- NEW: POS SALE ADMIN ---
class StockTransactionInline(admin.TabularInline):
    model = StockTransaction
    fields = ('product', 'quantity', 'selling_price')
    readonly_fields = ('product', 'quantity', 'selling_price')
    extra = 0
    can_delete = False

@admin.register(POSSale)
class POSSaleAdmin(admin.ModelAdmin):
    list_display = ('receipt_id', 'timestamp', 'cashier', 'total_amount', 'amount_paid')
    search_fields = ('receipt_id', 'cashier__username')
    list_filter = ('timestamp', 'cashier')
    inlines = [StockTransactionInline]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'contact_person')
    search_fields = ('name', 'email')

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    autocomplete_fields = ['product'] 

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    # UPDATED: Use order_id instead of id
    list_display = ('order_id', 'supplier', 'status', 'order_date')
    list_filter = ('status', 'supplier', 'order_date')
    inlines = [PurchaseOrderItemInline]
    
    # UPDATED: Search by order_id
    search_fields = ('order_id', 'supplier__name')
    autocomplete_fields = ['supplier'] 

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        
        obj = form.instance
        
        if not hasattr(self, '_previous_status'):
            return

        previous_status = self._previous_status
        current_status = obj.status
        
        # Logic: If changing FROM Received TO something else, revert stock.
        # (Receiving stock is usually done via the "Receive" button in the frontend or custom action)
        if previous_status == 'RECEIVED' and current_status != 'RECEIVED':
             self._adjust_stock(request, obj, 'OUT')
        
        clear_dashboard_cache()

    def save_model(self, request, obj, form, change):
        if change:
            original = PurchaseOrder.objects.get(pk=obj.pk)
            self._previous_status = original.status
        else:
            self._previous_status = None
            
        super().save_model(request, obj, form, change)

    def _adjust_stock(self, request, po, type):
        with transaction.atomic():
            for item in po.items.all():
                product = item.product
                qty = item.quantity
                
                if type == 'IN':
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='IN',
                        transaction_reason=StockTransaction.TransactionReason.PURCHASE_ORDER,
                        quantity=qty,
                        user=request.user,
                        notes=f'Received from Purchase Order {po.order_id}'
                    )
                    product.quantity += qty
                    product.last_purchase_date = timezone.now()
                
                elif type == 'OUT':
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='OUT',
                        transaction_reason=StockTransaction.TransactionReason.CORRECTION,
                        quantity=qty,
                        user=request.user,
                        notes=f'Correction: Reverted Purchase Order {po.order_id} status'
                    )
                    product.quantity = max(0, product.quantity - qty)
                
                product.save()

# --- EXPENSE ADMIN ---
@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'category', 'amount', 'expense_date', 'recorded_by')
    list_filter = ('category', 'expense_date', 'recorded_by')
    search_fields = ('description', 'category__name')