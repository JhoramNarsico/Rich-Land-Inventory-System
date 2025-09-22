# inventory/views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .models import Product

class ProductListView(ListView):
    model = Product
    context_object_name = 'product_list' # Custom name for the list in the template
    template_name = 'inventory/product_list.html'

class ProductDetailView(DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'

class ProductCreateView(CreateView):
    model = Product
    fields = ['name', 'sku', 'price', 'quantity'] # Fields to display in the form
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list') # Redirect to the list view after creation

class ProductUpdateView(UpdateView):
    model = Product
    fields = ['name', 'sku', 'price', 'quantity']
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list') # Redirect after update

class ProductDeleteView(DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('product-list')