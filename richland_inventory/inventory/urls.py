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
    path('product/<slug:slug>/toggle_status/', views.product_toggle_status, name='product_toggle_status'),
    
    path('category/add/ajax/', views.add_category_ajax, name='add_category_ajax'),

    path('history/', views.ProductHistoryListView.as_view(), name='product_history_list'),
    path('product/<slug:slug>/history/', views.ProductHistoryDetailView.as_view(), name='product_history_detail'),
    
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('reports/', views.ReportingView.as_view(), name='reporting'),

    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchaseorder_list'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchaseorder_detail'),

    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),

    # Add under existing reporting path
    path('reports/dashboard/', views.ReportsDashboardView.as_view(), name='reports_dashboard'),

]