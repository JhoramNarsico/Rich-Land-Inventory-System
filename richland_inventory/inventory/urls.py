# inventory/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Example: localhost:8000/
    path('', views.ProductListView.as_view(), name='product-list'),

    # Example: localhost:8000/product/5/
    path('product/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),

    # Example: localhost:8000/product/create/
    path('product/create/', views.ProductCreateView.as_view(), name='product-create'),

    # Example: localhost:8000/product/5/update/
    path('product/<int:pk>/update/', views.ProductUpdateView.as_view(), name='product-update'),

    # Example: localhost:8000/product/5/delete/
    path('product/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),
]