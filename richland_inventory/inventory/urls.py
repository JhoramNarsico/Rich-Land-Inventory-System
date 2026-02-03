# inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # --- PRODUCT MANAGEMENT ---
    path('', views.ProductListView.as_view(), name='product_list'),
    path('product/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<slug:slug>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('product/<slug:slug>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    # Custom Actions
    path('product/<slug:slug>/toggle_status/', views.product_toggle_status, name='product_toggle_status'),
    path('product/<slug:slug>/refund/', views.product_refund, name='product_refund'),
    
    # AJAX
    path('category/add/ajax/', views.add_category_ajax, name='add_category_ajax'),

    # --- HISTORY & AUDIT ---
    path('history/', views.ProductHistoryListView.as_view(), name='product_history_list'),
    path('product/<slug:slug>/history/', views.ProductHistoryDetailView.as_view(), name='product_history_detail'),
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),

    # --- REPORTS & ANALYTICS ---
    path('reports/', views.ReportingView.as_view(), name='reporting'),
    path('analytics/', views.analytics_dashboard, name='analytics'),

    # --- PROCUREMENT (PURCHASE ORDERS) ---
    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchaseorder_list'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchaseorder_detail'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order, name='purchaseorder_receive'),
    
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),

    # --- POINT OF SALE (POS) ---
    path('pos/', views.pos_dashboard, name='pos_dashboard'),
    path('pos/checkout/', views.pos_checkout, name='pos_checkout'),
    
    # NEW: POS History & Receipt Viewing
    path('pos/history/', views.POSHistoryListView.as_view(), name='pos_history'),
    path('pos/receipt/<str:receipt_id>/', views.POSReceiptDetailView.as_view(), name='pos_receipt_detail'),
]