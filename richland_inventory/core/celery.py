# core/celery.py

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# --- CELERY BEAT (SCHEDULER) CONFIGURATION ---
app.conf.beat_schedule = {
    # Name of the task
    'send-low-stock-alerts-daily': {
        # The task to run (app_name.tasks.task_name)
        'task': 'inventory.tasks.send_low_stock_alerts_task',
        # Schedule: Run every day at 8:00 AM
        'schedule': crontab(hour=8, minute=0),
    },
}