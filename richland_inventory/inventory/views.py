# inventory/views.py

# --- Python/Django Core Imports ---
import csv
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from rest_framework import viewsets

# --- App-Specific Imports ---
from .forms import ProductForm, StockTransactionForm, ProductFilterForm, TransactionFilterForm, TransactionReportForm
from .models import Product, StockTransaction, Category
from .serializers import ProductSerializer
from .utils import render_to_pdf

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'
    paginate_by = 12
    permission_required = 'inventory.view_product'

    def get_queryset(self):
        # --- OPTIMIZED QUERY WITH select_related ---
        queryset = Product.objects.select_related('category').all()
        # --- END OF MODIFICATION ---
        
        form = ProductFilterForm(self.request.GET)
        if form.is_valid():
            query = self.request.GET.get('q')
            if query: 
                queryset = queryset.filter(Q(name__icontains=query) | Q(sku__icontains=query))
            category = form.cleaned_data.get('category')
            if category: 
                queryset = queryset.filter(category=category)
            stock_status = form.cleaned_data.get('stock_status')
            if stock_status == 'in_stock': 
                queryset = queryset.filter(quantity__gt=10)
            elif stock_status == 'low_stock': 
                queryset = queryset.filter(quantity__gt=0, quantity__lte=10)
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
        context['filter_form'] = ProductFilterForm(self.request.GET)
        context['query_params'] = self.request.GET.urlencode()
        return context

# --- REVISED ProductDetailView ---
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
        self.object = self.get_object()
        form = StockTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.product = self.object
            transaction.user = request.user
            transaction_type = form.cleaned_data.get('transaction_type')
            quantity = form.cleaned_data.get('quantity')
            if transaction_type == 'OUT':
                if self.object.quantity < quantity:
                    messages.error(request, f'Cannot stock out more than the available quantity ({self.object.quantity}).')
                    return redirect(self.object.get_absolute_url())
                self.object.quantity -= quantity
            else: # 'IN'
                self.object.quantity += quantity
            self.object.save()
            transaction.save()
            messages.success(request, "Stock was adjusted successfully.")
        else:
            # Re-render the page with the form errors
            messages.error(request, "There was an error with your submission.")
        return redirect(self.object.get_absolute_url())

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Product
    form_class = ProductForm
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
        return response

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')
    success_message = "Product was updated successfully!"
    permission_required = 'inventory.change_product'
    
    def form_valid(self, form):
        old_quantity = self.get_object().quantity
        new_quantity = form.cleaned_data.get('quantity', 0)
        response = super().form_valid(form)
        quantity_difference = new_quantity - old_quantity
        if quantity_difference > 0:
            StockTransaction.objects.create(
                product=self.object, 
                transaction_type='IN', 
                quantity=quantity_difference, 
                user=self.request.user, 
                notes='Manual quantity update from product edit form.'
            )
        elif quantity_difference < 0:
            StockTransaction.objects.create(
                product=self.object, 
                transaction_type='OUT', 
                quantity=abs(quantity_difference), 
                user=self.request.user, 
                notes='Manual quantity update from product edit form.'
            )
        return response

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_product'
    
    def form_valid(self, form):
        messages.success(self.request, "The product was deleted successfully.")
        return super().form_valid(form)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

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
        context['query_params'] = self.request.GET.urlencode()
        return context

class ReportingView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'inventory/reporting.html'
    permission_required = 'inventory.view_product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Inventory Reports"
        context['transaction_report_form'] = TransactionReportForm()
        return context
    
    def get(self, request, *args, **kwargs):
        export_type = request.GET.get('export')
        if export_type == 'inventory_csv': 
            return self.export_inventory_csv()
        elif export_type == 'transaction_pdf': 
            return self.export_transactions_pdf(request)
        return super().get(request, *args, **kwargs)
    
    def export_inventory_csv(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="current_inventory_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product Name', 'SKU', 'Category', 'Quantity', 'Price per Item', 'Current Stock Value'])
        products = Product.objects.select_related('category').all()
        for product in products:
            category_name = product.category.name if product.category else 'N/A'
            stock_value = product.quantity * product.price
            writer.writerow([product.name, product.sku, category_name, product.quantity, product.price, stock_value])
        return response
    
    def export_transactions_pdf(self, request):
        transactions = StockTransaction.objects.select_related('product', 'user').all()
        form = TransactionReportForm(request.GET)
        start_date, end_date = None, None
        if form.is_valid():
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            if start_date: 
                transactions = transactions.filter(timestamp__date__gte=start_date)
            if end_date: 
                transactions = transactions.filter(timestamp__date__lte=end_date)
        context = {'transactions': transactions, 'start_date': start_date, 'end_date': end_date}
        pdf = render_to_pdf('inventory/transaction_report_pdf.html', context)
        pdf['Content-Disposition'] = 'attachment; filename="transaction_history_report.pdf"'
        return pdf