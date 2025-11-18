# core/cache_utils.py

from django.core.cache import cache

def clear_dashboard_cache():
    """Removes the dashboard data from the cache."""
    # This key must match the one used in the home view.
    # To avoid magic strings, you could define this key in your settings,
    # but for now, this is a direct fix.
    cache.delete('dashboard_data')