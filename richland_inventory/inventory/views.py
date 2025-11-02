# inventory/views.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from rest_framework import viewsets

from .forms import ProductForm, StockTransactionForm
from .models import Product, StockTransaction
from .serializers import ProductSerializer


class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    # ... (This view is unchanged)
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'
    paginate_by = 10
    permission_required = 'inventory.view_product'

    def get_queryset(self):
        query = self.request.GET.get('q')
        if query:
            return Product.objects.filter(
                Q(name__icontains=query) | Q(sku__icontains=query)
            ).order_by('-date_created')
        return Product.objects.all().order_by('-date_created')


class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    # ... (This view is unchanged)
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'
    permission_required = 'inventory.view_product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = StockTransaction.objects.filter(
            product=self.object
        ).order_by('-timestamp')[:10]
        return context


class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')
    success_message = "Product was created successfully!"
    permission_required = 'inventory.add_product'

    # --- ADD THIS METHOD TO LOG INITIAL STOCK ---
    def form_valid(self, form):
        response = super().form_valid(form)
        # self.object is the new Product instance that was just created
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

    # --- ADD THIS METHOD TO LOG STOCK CHANGES ---
    def form_valid(self, form):
        # Get the product instance before it's saved
        old_quantity = self.get_object().quantity
        new_quantity = form.cleaned_data.get('quantity', 0)
        
        # Let the parent class save the form and update the product
        response = super().form_valid(form)

        quantity_difference = new_quantity - old_quantity

        if quantity_difference > 0:
            # This is a Stock In
            StockTransaction.objects.create(
                product=self.object,
                transaction_type='IN',
                quantity=quantity_difference,
                user=self.request.user,
                notes='Manual quantity update from product edit form.'
            )
        elif quantity_difference < 0:
            # This is a Stock Out
            StockTransaction.objects.create(
                product=self.object,
                transaction_type='OUT',
                quantity=abs(quantity_difference), # Use absolute value for quantity
                user=self.request.user,
                notes='Manual quantity update from product edit form.'
            )
        
        return response


class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    # ... (This view is unchanged)
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    permission_required = 'inventory.delete_product'

    def form_valid(self, form):
        messages.success(self.request, "The product was deleted successfully.")
        return super().form_valid(form)


class ProductTransactionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    # ... (This view is unchanged)
    model = StockTransaction
    form_class = StockTransactionForm
    template_name = 'inventory/product_transaction_form.html'
    permission_required = 'inventory.can_adjust_stock'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = Product.objects.get(slug=self.kwargs.get('slug'))
        return context

    def form_valid(self, form):
        product = Product.objects.get(slug=self.kwargs.get('slug'))
        form.instance.product = product
        form.instance.user = self.request.user
        
        transaction_type = form.cleaned_data['transaction_type']
        quantity = form.cleaned_data['quantity']

        if transaction_type == 'OUT':
            if product.quantity < quantity:
                form.add_error('quantity', f'Cannot stock out more than the available quantity ({product.quantity}).')
                return self.form_invalid(form)
            product.quantity -= quantity
        else: # 'IN'
            product.quantity += quantity
        
        product.save()
        messages.success(self.request, "Stock transaction recorded successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.product.get_absolute_url()


class ProductViewSet(viewsets.ModelViewSet):
    # ... (This view is unchanged)
    queryset = Product.objects.all()
    serializer_class = ProductSerializer