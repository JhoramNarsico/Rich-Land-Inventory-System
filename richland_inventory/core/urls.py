# in core/urls.py

from django.contrib import admin
from django.urls import path, include

# --- ADD THESE TWO IMPORTS ---
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api/', include('inventory.api_urls')), # Handles API urls
    path('inventory/', include('inventory.urls')), # Handles user-facing urls
]

# --- ADD THIS IF STATEMENT AT THE VERY BOTTOM ---
# This is the line that tells the development server to serve static files
if settings.DEBUG:

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
