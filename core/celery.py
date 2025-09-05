import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.develop')

app = Celery('core')

# Load configuration from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Explicitly ensure broker and backend are set from settings (avoids kombu fallback)
try:
    broker = getattr(settings, 'CELERY_BROKER_URL', None) or getattr(settings, 'REDIS_URL', None)
    result_backend = getattr(settings, 'CELERY_RESULT_BACKEND', None) or getattr(settings, 'REDIS_URL', None)
    if broker:
        app.conf.broker_url = broker
    if result_backend:
        app.conf.result_backend = result_backend
except Exception:
    # If settings are not ready, ignore and rely on config_from_object
    pass

# Make this app the current/default Celery app (prevents kombu default fallback)
try:
    app.set_default()
    app.set_current()
except Exception:
    pass

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
