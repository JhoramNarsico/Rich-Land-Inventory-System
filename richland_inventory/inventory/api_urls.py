# inventory/api_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# --- ADD THIS LINE ---
app_name = 'inventory-api'

# Create a router and register our viewsets with it.
router = DefaultRouter()
# Note: I changed basename to 'product' which is more standard.
# This makes the URL names 'product-list' and 'product-detail'.
router.register(r'products', views.ProductViewSet, basename='product')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]