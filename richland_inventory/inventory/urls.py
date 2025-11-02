# inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # C(R)UD: List/Read
    path('', views.ProductListView.as_view(), name='product_list'),
    
    # (C)RUD: Create
    path('product/create/', views.ProductCreateView.as_view(), name='product_create'),
    
    # --- THIS IS THE CORRECTED LINE ---
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    
    # CR(U)D: Update
    path('product/<slug:slug>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    
    # CRU(D): Delete
    path('product/<slug:slug>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),

    # URL for adjusting stock
    path('product/<slug:slug>/adjust-stock/', views.ProductTransactionCreateView.as_view(), name='product_adjust_stock'),
]