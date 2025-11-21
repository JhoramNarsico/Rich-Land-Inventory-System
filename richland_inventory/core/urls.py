# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from inventory.views import CustomLoginView # <--- IMPORT THIS

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    
    # --- USE CUSTOM LOGIN VIEW ---
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    
    # Keep the rest for logout/password reset
    path('accounts/', include('django.contrib.auth.urls')),
    
    path('api/', include(('inventory.api_urls', 'inventory-api'))),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    path('inventory/', include('inventory.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)