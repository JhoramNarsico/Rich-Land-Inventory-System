# inventory/urls.py
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('product/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<slug:slug>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('product/<slug:slug>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    # The 'adjust-stock' URL has been removed from the line below.
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('reports/', views.ReportingView.as_view(), name='reporting'),
]