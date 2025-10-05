# inventory/views.py
from django.shortcuts import render 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .models import Product

# Add these imports for the API
from rest_framework import viewsets
from .serializers import ProductSerializer

def home(request):
    """
    View for the homepage.
    """
    return render(request, 'home.html')

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    context_object_name = 'product_list'
    template_name = 'inventory/product_list.html'

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'

# in inventory/views.py

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    fields = ['name', 'sku', 'price', 'quantity']
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list')

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    fields = ['name', 'sku', 'price', 'quantity']
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list')

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('product-list')


# Add this ViewSet for the API
class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows products to be viewed or edited.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
