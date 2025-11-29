# inventory/api_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'inventory-api'

router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'categories', views.CategoryViewSet, basename='category') # Added this

urlpatterns = [
    path('', include(router.urls)),
    path('sales-chart-data/', views.sales_chart_data, name='sales-chart-data'),
]