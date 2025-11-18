# inventory/views.py

import csv
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q, F, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_POST
from rest_framework import viewsets, permissions

from core.views import clear_dashboard_cache

from .forms import (
    ProductCreateForm, ProductUpdateForm, StockTransactionForm, ProductFilterForm,
    TransactionFilterForm, TransactionReportForm, ProductHistoryFilterForm,
    CategoryCreateForm, PurchaseOrderFilterForm
)
from .models import Product, StockTransaction, Category, PurchaseOrder, Supplier
from .serializers import ProductSerializer
from .utils import render_to_pdf

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'
    paginate_by = 12
    permission_required = 'inventory.view_product'

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
            
            # --- THIS IS THE CORRECTED LOGIC BLOCK ---
            if stock_status == 'in_stock':
                # An item is "in stock" if its quantity is greater than its reorder level.
                queryset = queryset.filter(quantity__gt=F('reorder_level'))
            elif stock_status == 'low_stock':
                # An item is "low stock" if its quantity is > 0 but <= its reorder level.
                queryset = queryset.filter(quantity__gt=0, quantity__lte=F('reorder_level'))
            elif stock_status == 'out_of_stock':
                # An item is "out of stock" if its quantity is 0.
                queryset = queryset.filter(quantity=0)
            # --- END OF CORRECTION ---

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
        context['transaction_form'] = StockTransactionForm()
        return context
    def post(self, request, *args, **kwargs):
        product_object = self.get_object()
        form = StockTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.product = product_object
            transaction.user = request.user
            transaction_type = form.cleaned_data.get('transaction_type')
            quantity = form.cleaned_data.get('quantity')
            if transaction_type == 'OUT':
                if product_object.quantity < quantity:
                    messages.error(request, f'Cannot stock out more than the available quantity ({product_object.quantity}).')
                    return redirect(product_object.get_absolute_url())
                Product.objects.filter(pk=product_object.pk).update(quantity=F('quantity') - quantity)
                transaction.selling_price = product_object.price
            else:
                Product.objects.filter(pk=product_object.pk).update(quantity=F('quantity') + quantity)
            transaction.save()
            clear_dashboard_cache()
            messages.success(request, "Stock was adjusted successfully.")
        else:
            messages.error(request, "There was an error with your submission.")
        return redirect(product_object.get_absolute_url())

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
    def get_success_url(self):
        return self.object.get_absolute_url()

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_product'
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Only administrators are allowed to permanently delete products. Consider deactivating it instead.")
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
    return redirect(product.get_absolute_url())

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(status=Product.Status.ACTIVE)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

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
            if form.cleaned_data.get('product'):
                queryset = queryset.filter(product=form.cleaned_data['product'])
            if form.cleaned_data.get('transaction_type'):
                queryset = queryset.filter(transaction_type=form.cleaned_data['transaction_type'])
            if form.cleaned_data.get('user'):
                queryset = queryset.filter(user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'):
                queryset = queryset.filter(timestamp__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'):
                queryset = queryset.filter(timestamp__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-timestamp')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = TransactionFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
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
            if form.cleaned_data.get('product'):
                queryset = queryset.filter(id=form.cleaned_data['product'].id)
            if form.cleaned_data.get('user'):
                queryset = queryset.filter(history_user=form.cleaned_data['user'])
            if form.cleaned_data.get('start_date'):
                queryset = queryset.filter(history_date__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'):
                queryset = queryset.filter(history_date__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-history_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for record in context['history_list']:
            record.change_summary = get_change_summary(record)
        context['filter_form'] = ProductHistoryFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
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
    def get_queryset(self):
        return self.product.history.select_related('history_user').all().order_by('-history_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for record in context['history_list']:
            record.change_summary = get_change_summary(record)
        context['product'] = self.product
        return context

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
        sales_transactions = transactions_base.filter(transaction_type='OUT', selling_price__isnull=False)
        summary = sales_transactions.aggregate(total_revenue=Sum(F('selling_price') * F('quantity')), total_items_sold=Sum('quantity'))
        top_sellers = sales_transactions.values('product__name').annotate(total_quantity_sold=Sum('quantity')).order_by('-total_quantity_sold')[:5]
        context = {'transactions': transactions_base.order_by('timestamp'), 'start_date': start_date, 'end_date': end_date, 'summary': summary, 'top_sellers': top_sellers}
        pdf = render_to_pdf('inventory/transaction_report_pdf.html', context)
        if not isinstance(pdf, HttpResponse): return HttpResponse("Error generating PDF.", status=500)
        pdf['Content-Disposition'] = 'attachment; filename="general_sales_report.pdf"'
        return pdf

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
            if form.cleaned_data.get('supplier'):
                queryset = queryset.filter(supplier=form.cleaned_data['supplier'])
            if form.cleaned_data.get('status'):
                queryset = queryset.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('start_date'):
                queryset = queryset.filter(order_date__date__gte=form.cleaned_data['start_date'])
            if form.cleaned_data.get('end_date'):
                queryset = queryset.filter(order_date__date__lte=form.cleaned_data['end_date'])
        return queryset.order_by('-order_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = PurchaseOrderFilterForm(self.request.GET)
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        return context

class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'inventory/purchaseorder_detail.html'
    context_object_name = 'po'
    permission_required = 'inventory.view_purchaseorder'
    def get_queryset(self):
        return super().get_queryset().prefetch_related('items__product')

@login_required
@require_POST
def add_category_ajax(request):
    form = CategoryCreateForm(request.POST)
    if form.is_valid():
        category = form.save()
        return JsonResponse({'status': 'success', 'category': {'id': category.id, 'name': category.name}})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
def sales_chart_data(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sales_data = StockTransaction.objects.filter(
        transaction_type='OUT',
        timestamp__gte=thirty_days_ago,
        selling_price__isnull=False
    ).annotate(day=TruncDate('timestamp')).values('day').annotate(
        total_sales=Sum(F('selling_price') * F('quantity'))
    ).order_by('day')
    labels = [sale['day'].strftime('%b %d') for sale in sales_data]
    data = [float(sale['total_sales']) for sale in sales_data]
    return JsonResponse({'labels': labels, 'data': data})

class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier_list.html'
    context_object_name = 'supplier_list'
    paginate_by = 20
    permission_required = 'inventory.view_purchaseorder'
    def get_queryset(self):
        return Supplier.objects.order_by('name')

class SupplierDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Supplier
    template_name = 'inventory/supplier_detail.html'
    context_object_name = 'supplier'
    permission_required = 'inventory.view_purchaseorder'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()
        context['purchase_orders'] = PurchaseOrder.objects.filter(
            supplier=supplier
        ).order_by('-order_date')
        return context
