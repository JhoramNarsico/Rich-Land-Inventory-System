# in core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import views from the local 'core' app, not the 'inventory' app
from . import views

urlpatterns = [
    # It now correctly points to the 'home' view within this 'core' app
    path('', views.home, name='home'),

    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # --- THIS IS THE CORRECTED LINE ---
    # This tuple format tells Django that the included URLs
    # belong to the 'inventory-api' namespace.
    path('api/', include(('inventory.api_urls', 'inventory-api'))),
    
    # This correctly includes all the URLs from the inventory app
    path('inventory/', include('inventory.urls')),
]

# This part is perfect, do not change it
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)