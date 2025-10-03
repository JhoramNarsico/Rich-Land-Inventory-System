# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('inventory/', include('inventory.urls')),
    path('api/', include('inventory.api_urls')),  # Add this line for the API
    path('accounts/', include('django.contrib.auth.urls')),
    path('', RedirectView.as_view(url='/inventory/', permanent=True)),
]