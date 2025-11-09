# inventory/api_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'inventory-api'

router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
    # --- NEW: Add this URL for the dashboard chart data ---
    path('sales-chart-data/', views.sales_chart_data, name='sales-chart-data'),
]