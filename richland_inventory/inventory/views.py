# inventory/views.py

import csv
import json
from datetime import timedelta
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Q, F, Sum, Count, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate, TruncDay
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, permissions

from core.cache_utils import clear_dashboard_cache

from .forms import (
    ProductCreateForm, ProductUpdateForm, StockTransactionForm, ProductFilterForm,
    TransactionFilterForm, TransactionReportForm, ProductHistoryFilterForm,
    CategoryCreateForm, PurchaseOrderFilterForm, StockOutForm, AnalyticsFilterForm,
    RefundForm
)
from .models import Product, StockTransaction, Category, PurchaseOrder, Supplier
from .serializers import ProductSerializer
from .utils import render_to_pdf

# --- AUTHENTICATION ---

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        remember_me = self.request.POST.get('remember_me')
        if remember_me:
            self.request.session.set_expiry(1209600) # 2 weeks
        else:
            self.request.session.set_expiry(1800) # 30 mins rolling
        return response

# --- PRODUCT MANAGEMENT ---

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'
    paginate_by = 12
    permission_required = 'inventory.view_product'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['inventory/partials/product_list_rows.html']
        return ['inventory/product_list.html']

    def get_queryset(self):
        queryset = Product.objects.select_related('category').all()
        form = ProductFilterForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('q')
            if query:
                queryset = queryset.filter(Q(name__icontains=query) | Q(sku__icontains=query))
            category = form.cleaned_data.get('category')
            if category:
                queryset = queryset.filter(category=category)
            product_status = form.cleaned_data.get('product_status')
            if product_status:
                queryset = queryset.filter(status=product_status)
            stock_status = form.cleaned_data.get('stock_status')
            if stock_status == 'in_stock':
                queryset = queryset.filter(quantity__gt=F('reorder_level'))
            elif stock_status == 'low_stock':
                queryset = queryset.filter(quantity__gt=0, quantity__lte=F('reorder_level'))
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(quantity=0)
            sort_by = form.cleaned_data.get('sort_by')
            if sort_by:
                queryset = queryset.order_by(sort_by)
            else:
                queryset = queryset.order_by('-date_created')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProductFilterForm(self.request.GET or {'product_status': 'ACTIVE'})
        context['category_form'] = CategoryCreateForm()
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

    def post(self, request, *args, **kwargs):
        category_form = CategoryCreateForm(request.POST)
        if category_form.is_valid():
            category_form.save()
            messages.success(request, "Category was added successfully!")
        else:
            error_msg = ". ".join([f"{field.title()}: {error[0]}" for field, error in category_form.errors.items()])
            messages.error(request, f"Error adding category: {error_msg}")
        return redirect('inventory:product_list')

class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'
    permission_required = 'inventory.view_product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = StockTransaction.objects.filter(product=self.object).order_by('-timestamp')[:10]
        context['transaction_form'] = StockOutForm()
        context['refund_form'] = RefundForm()
        return context
    
    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            product_object = Product.objects.select_for_update().get(pk=self.get_object().pk)
            form = StockOutForm(request.POST)
            
            if form.is_valid():
                transaction_obj = form.save(commit=False)
                transaction_obj.product = product_object
                transaction_obj.user = request.user
                transaction_obj.transaction_type = 'OUT'
                
                transaction_reason = form.cleaned_data.get('transaction_reason')
                quantity = form.cleaned_data.get('quantity')
                
                if product_object.quantity < quantity:
                    messages.error(request, f'Cannot stock out more than available ({product_object.quantity}).')
                    return redirect(product_object.get_absolute_url())
                
                product_object.quantity -= quantity
                product_object.save()
                
                if transaction_reason in [StockTransaction.TransactionReason.SALE, StockTransaction.TransactionReason.DAMAGE]:
                    transaction_obj.selling_price = product_object.price
                else:
                    transaction_obj.selling_price = None 
                
                transaction_obj.save()
                clear_dashboard_cache()
                messages.success(request, "Stock Out recorded successfully.")
            else:
                messages.error(request, "Error recording transaction.")
        return redirect(product_object.get_absolute_url())

@login_required
@require_POST
@permission_required('inventory.can_adjust_stock', raise_exception=True)
def product_refund(request, slug):
    product = get_object_or_404(Product, slug=slug)
    form = RefundForm(request.POST)
    
    if form.is_valid():
        with transaction.atomic():
            quantity = form.cleaned_data['quantity']
            StockTransaction.objects.create(
                product=product,
                transaction_type='IN',
                transaction_reason=StockTransaction.TransactionReason.RETURN,
                quantity=quantity,
                user=request.user,
                selling_price=product.price, 
                notes=f"Refund/Return: {form.cleaned_data.get('notes')}"
            )
            product.quantity += quantity
            product.save()
            clear_dashboard_cache()
            messages.success(request, f"Refund processed. {quantity} items returned to stock.")
    else:
        messages.error(request, "Invalid refund data.")
    return redirect(product.get_absolute_url())

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Product
    form_class = ProductCreateForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')
    success_message = "Product was created successfully!"
    permission_required = 'inventory.add_product'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        initial_quantity = form.cleaned_data.get('quantity', 0)
        if initial_quantity > 0:
            StockTransaction.objects.create(
                product=self.object,
                transaction_type='IN',
                transaction_reason=StockTransaction.TransactionReason.INITIAL,
                quantity=initial_quantity,
                user=self.request.user,
                notes='Initial stock on product creation.'
            )
        clear_dashboard_cache()
        return response

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    form_class = ProductUpdateForm
    template_name = 'inventory/product_form.html'
    success_message = "Product was updated successfully!"
    permission_required = 'inventory.change_product'
    def form_valid(self, form):
        clear_dashboard_cache()
        return super().form_valid(form)
    def get_success_url(self): return self.object.get_absolute_url()

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_product'
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Only administrators are allowed to permanently delete products.")
            product = self.get_object()
            return redirect(product.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)
    def form_valid(self, form):
        clear_dashboard_cache()
        messages.success(self.request, "The product was permanently deleted successfully.")
        return super().form_valid(form)

@require_POST
@permission_required('inventory.change_product', raise_exception=True)
def product_toggle_status(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if product.status == Product.Status.ACTIVE:
        product.status = Product.Status.DEACTIVATED
        messages.success(request, f"'{product.name}' has been deactivated.")
    else:
        product.status = Product.Status.ACTIVE
        messages.success(request, f"'{product.name}' has been activated.")
    product.save()
    clear_dashboard_cache() 
    return redirect(product.get_absolute_url())

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(status=Product.Status.ACTIVE)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

# --- TRANSACTION & HISTORY ---

class TransactionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StockTransaction
    template_name = 'inventory/transaction_list.html'
    context_object_name = 'transaction_list'
    paginate_by = 25
    permission_required = 'inventory.view_stocktransaction'
    def get_queryset(self):
        queryset = StockTransaction.objects.select_related('product', 'user').all()
        form = TransactionFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('product'): queryset = queryset.filter(product=form.cleaned_data['product'])
            if form.cleaned_data.get('transaction_type'): queryset = queryset.filter(transaction_type=form.cleaned_data['transaction_type'])
            if form.cleaned_data.get('transaction_reason'): queryset = queryset.filter(transaction_reason=form.cleaned_data['transaction_reason'])
            if form.cleaned_data.get('user'): queryset = queryset.filter(user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'): queryset = queryset.filter(timestamp__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'): queryset = queryset.filter(timestamp__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-timestamp')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = TransactionFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params: query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

def get_change_summary(record):
    if record.history_type == '+': return "Product created."
    if record.history_type == '-': return f"Deleted Product: {record.name} (SKU: {record.sku})"
    old_record = record.prev_record
    if not old_record: return "No previous record found to compare."
    delta = record.diff_against(old_record)
    changes = []
    for change in delta.changes:
        field_name = change.field.replace('_', ' ').title()
        if change.field == 'category':
            try: old_display_value = Category.objects.get(pk=change.old).name if change.old else 'None'
            except Category.DoesNotExist: old_display_value = f"Deleted Category (ID: {change.old})"
            try: new_display_value = Category.objects.get(pk=change.new).name if change.new else 'None'
            except Category.DoesNotExist: new_display_value = f"Deleted Category (ID: {change.new})"
            changes.append(f"Changed <strong>{field_name}</strong> from '{old_display_value}' to '{new_display_value}'")
        else:
            changes.append(f"Changed <strong>{field_name}</strong> from '{change.old}' to '{change.new}'")
    return ". ".join(changes) if changes else "No changes detected."

class ProductHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product.history.model
    template_name = 'inventory/product_history_list.html'
    context_object_name = 'history_list'
    paginate_by = 20
    permission_required = 'inventory.can_view_history'
    def get_queryset(self):
        queryset = super().get_queryset().select_related('history_user')
        form = ProductHistoryFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('product'): queryset = queryset.filter(id=form.cleaned_data['product'].id)
            if form.cleaned_data.get('user'): queryset = queryset.filter(history_user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'): queryset = queryset.filter(history_date__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'): queryset = queryset.filter(history_date__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-history_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for record in context['history_list']: record.change_summary = get_change_summary(record)
        context['filter_form'] = ProductHistoryFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params: query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

class ProductHistoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product.history.model
    template_name = 'inventory/product_history_detail.html'
    context_object_name = 'history_list'
    paginate_by = 20
    permission_required = 'inventory.can_view_history'
    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, slug=self.kwargs['slug'])
        return super().dispatch(request, *args, **kwargs)
    def get_queryset(self): return self.product.history.select_related('history_user').all().order_by('-history_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for record in context['history_list']: record.change_summary = get_change_summary(record)
        context['product'] = self.product
        return context

# --- REPORTING ---

@method_decorator(xframe_options_exempt, name='dispatch')
class ReportingView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'inventory/reporting.html'
    permission_required = 'inventory.can_view_reports'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Inventory Reports"
        context['transaction_report_form'] = TransactionReportForm(self.request.GET)
        return context
    def get(self, request, *args, **kwargs):
        export_type = request.GET.get('export')
        if export_type == 'inventory_csv': return self.export_inventory_csv()
        elif export_type == 'transaction_pdf': return self.export_transactions_pdf(request)
        return super().get(request, *args, **kwargs)
    def export_inventory_csv(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="current_inventory_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product Name', 'SKU', 'Category', 'Status', 'Quantity', 'Price per Item', 'Current Stock Value', 'Last Restocked'])
        products = Product.objects.select_related('category').all()
        for product in products:
            category_name = product.category.name if product.category else 'N/A'
            stock_value = product.quantity * product.price
            writer.writerow([product.name, product.sku, category_name, product.get_status_display(), product.quantity, product.price, stock_value, product.last_purchase_date])
        return response
    def export_transactions_pdf(self, request):
        transactions_base = StockTransaction.objects.select_related('product', 'user').all()
        form = TransactionReportForm(request.GET)
        start_date, end_date = None, None
        if form.is_valid():
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            if start_date: transactions_base = transactions_base.filter(timestamp__date__gte=start_date)
            if end_date: transactions_base = transactions_base.filter(timestamp__date__lte=end_date)
        
        all_transactions = transactions_base.annotate(row_total=ExpressionWrapper(F('selling_price') * F('quantity'), output_field=DecimalField())).order_by('-timestamp')
        revenue_summary = transactions_base.filter(transaction_type='OUT', transaction_reason=StockTransaction.TransactionReason.SALE).aggregate(total_revenue=Sum(F('selling_price') * F('quantity')), total_items_sold=Sum('quantity'))
        
        gross_sales = revenue_summary['total_revenue'] or 0
        total_refunds = transactions_base.filter(transaction_type='IN', transaction_reason=StockTransaction.TransactionReason.RETURN).aggregate(val=Sum(F('selling_price') * F('quantity')))['val'] or 0
        net_revenue = gross_sales - total_refunds
        
        loss_summary = transactions_base.filter(transaction_type='OUT').exclude(transaction_reason=StockTransaction.TransactionReason.SALE).values('transaction_reason').annotate(total_qty=Sum('quantity'), total_val=Sum(F('selling_price') * F('quantity')), count=Count('id')).order_by('transaction_reason')
        inflow_summary = transactions_base.filter(transaction_type='IN').values('transaction_reason').annotate(total_qty=Sum('quantity'), count=Count('id')).order_by('transaction_reason')
        top_sellers = transactions_base.filter(transaction_reason=StockTransaction.TransactionReason.SALE).values('product__name').annotate(total_quantity_sold=Sum('quantity')).order_by('-total_quantity_sold')[:5]
        
        context = { 'transactions': all_transactions, 'start_date': start_date, 'end_date': end_date, 'summary': revenue_summary, 
                   'gross_sales': gross_sales, 'total_refunds': total_refunds, 'net_revenue': net_revenue, 'total_items_sold': revenue_summary['total_items_sold'] or 0,
                   'loss_summary': loss_summary, 'inflow_summary': inflow_summary, 'top_sellers': top_sellers }
        pdf = render_to_pdf('inventory/transaction_report_pdf.html', context, request=request)
        if not isinstance(pdf, HttpResponse): return HttpResponse("Error generating PDF.", status=500)
        if request.GET.get('preview'): disposition = 'inline'
        else: disposition = 'attachment'
        pdf['Content-Disposition'] = f'{disposition}; filename="stock_movement_report.pdf"'
        return pdf

# --- ANALYTICS ---

@login_required
@permission_required('inventory.can_view_reports', raise_exception=True)
def analytics_dashboard(request):
    form = AnalyticsFilterForm(request.GET)
    start_date = timezone.now() - timedelta(days=30)
    end_date = timezone.now()

    if form.is_valid():
        if form.cleaned_data.get('start_date'): start_date = form.cleaned_data['start_date']
        if form.cleaned_data.get('end_date'): end_date = form.cleaned_data['end_date']

    sales_query = StockTransaction.objects.filter(
        transaction_type='OUT',
        transaction_reason=StockTransaction.TransactionReason.SALE,
        selling_price__isnull=False,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    )
    gross_sales = sales_query.aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0
    total_units_sold = sales_query.aggregate(Sum('quantity'))['quantity__sum'] or 0

    refunds_query = StockTransaction.objects.filter(
        transaction_type='IN',
        transaction_reason=StockTransaction.TransactionReason.RETURN,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    )
    total_refunds = refunds_query.aggregate(val=Sum(F('quantity') * F('product__price')))['val'] or 0
    
    damage_query = StockTransaction.objects.filter(
        transaction_type='OUT',
        transaction_reason=StockTransaction.TransactionReason.DAMAGE,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    )
    total_loss = damage_query.aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

    net_revenue = gross_sales - total_refunds

    # FIX: Use sales_query for charts, NOT base_query
    cat_data = sales_query.values('product__category__name').annotate(total_revenue=Sum(F('quantity') * F('selling_price'))).order_by('-total_revenue')
    cat_labels = [entry['product__category__name'] or "Uncategorized" for entry in cat_data]
    cat_values = [float(entry['total_revenue'] or 0) for entry in cat_data]

    prod_data = sales_query.values('product__name').annotate(total_revenue=Sum(F('quantity') * F('selling_price'))).order_by('-total_revenue')[:5]
    prod_labels = [p['product__name'] for p in prod_data]
    prod_values = [float(p['total_revenue']) for p in prod_data]

    daily_data = sales_query.annotate(day=TruncDay('timestamp')).values('day').annotate(daily_revenue=Sum(F('quantity') * F('selling_price'))).order_by('day')
    date_labels = [d['day'].strftime('%b %d') for d in daily_data]
    date_values = [float(d['daily_revenue']) for d in daily_data]

    context = {
        'page_title': 'Business Analytics',
        'filter_form': form,
        'start_date': start_date,
        'end_date': end_date,
        'total_revenue': net_revenue,
        'gross_sales': gross_sales,
        'total_refunds': total_refunds,
        'total_loss': total_loss,
        'total_units': total_units_sold,
        'cat_labels': json.dumps(cat_labels, cls=DjangoJSONEncoder),
        'cat_values': json.dumps(cat_values, cls=DjangoJSONEncoder),
        'prod_labels': json.dumps(prod_labels, cls=DjangoJSONEncoder),
        'prod_values': json.dumps(prod_values, cls=DjangoJSONEncoder),
        'date_labels': json.dumps(date_labels, cls=DjangoJSONEncoder),
        'date_values': json.dumps(date_values, cls=DjangoJSONEncoder),
    }
    return render(request, 'inventory/analytics.html', context)

@login_required
def sales_chart_data(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sales_data = StockTransaction.objects.filter(
        transaction_type='OUT',
        transaction_reason=StockTransaction.TransactionReason.SALE,
        timestamp__gte=thirty_days_ago,
        selling_price__isnull=False
    ).annotate(day=TruncDate('timestamp')).values('day').annotate(total_sales=Sum(F('selling_price') * F('quantity'))).order_by('day')
    labels = [sale['day'].strftime('%b %d') for sale in sales_data]
    data = [float(sale['total_sales']) for sale in sales_data]
    return JsonResponse({'labels': labels, 'data': data})

# --- PURCHASE ORDER & SUPPLIER ---

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'inventory/purchaseorder_list.html'
    context_object_name = 'po_list'
    paginate_by = 20
    permission_required = 'inventory.view_purchaseorder'
    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related('supplier').all()
        form = PurchaseOrderFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('supplier'): queryset = queryset.filter(supplier=form.cleaned_data['supplier'])
            if form.cleaned_data.get('status'): queryset = queryset.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('start_date'): queryset = queryset.filter(order_date__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'): queryset = queryset.filter(order_date__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-order_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = PurchaseOrderFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params: query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'inventory/purchaseorder_detail.html'
    context_object_name = 'po'
    permission_required = 'inventory.view_purchaseorder'
    def get_queryset(self): return super().get_queryset().prefetch_related('items__product')

@login_required
@permission_required('inventory.change_purchaseorder', raise_exception=True)
def receive_purchase_order(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        if po.status == 'COMPLETED':
             try:
                po.complete_order(request.user)
                clear_dashboard_cache()
                messages.success(request, f"Stock from Purchase Order #{po.id} has been added to inventory.")
             except Exception as e:
                messages.error(request, f"Error receiving order: {e}")
        elif po.status == 'RECEIVED': messages.warning(request, f"Purchase Order #{po.id} has already been received.")
        else: messages.warning(request, f"Purchase Order #{po.id} must be marked as 'Arrived' (Completed) by Admin before receiving.")
    return redirect('inventory:purchaseorder_list')

class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier_list.html'
    context_object_name = 'supplier_list'
    paginate_by = 20
    permission_required = 'inventory.view_purchaseorder'
    def get_queryset(self): return Supplier.objects.order_by('name')

class SupplierDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Supplier
    template_name = 'inventory/supplier_detail.html'
    context_object_name = 'supplier'
    permission_required = 'inventory.view_purchaseorder'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()
        context['purchase_orders'] = PurchaseOrder.objects.filter(supplier=supplier).order_by('-order_date')
        return context

@login_required
@require_POST
def add_category_ajax(request):
    form = CategoryCreateForm(request.POST)
    if form.is_valid():
        category = form.save()
        return JsonResponse({'status': 'success', 'category': {'id': category.id, 'name': category.name}})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)