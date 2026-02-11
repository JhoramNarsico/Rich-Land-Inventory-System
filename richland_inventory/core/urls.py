# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from inventory.views import CustomLoginView 

# Import views from the current directory (core/views.py)
from . import views 

urlpatterns = [
    # 1. Homepage -> Dashboard
    path('', views.home, name='home'),
    
    # 2. Admin Panel
    path('admin/', admin.site.urls),
    
    # 3. Custom Login (Overrides default)
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    
    # 4. Standard Auth URLs (Logout, Password Reset)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # 5. API & Documentation
    path('api/', include(('inventory.api_urls', 'inventory-api'))),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # 6. Inventory App URLs (This handles product_list, etc.)
    path('inventory/', include('inventory.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)