"""
Celery configuration for NavPrana Backend

This module configures Celery for handling async tasks like sending emails,
generating reports, and other time-consuming operations.
"""

import os
from celery import Celery
from celery.schedules import crontab
from decouple import config

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Load configuration from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Task configuration
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes (soft limit before hard timeout)

# Beat Schedule (Periodic Tasks)
CELERY_BEAT_SCHEDULE = {
    # Example: Clean up expired tokens every hour
    'clean-expired-tokens': {
        'task': 'users.tasks.clean_expired_tokens',
        'schedule': crontab(minute=0),  # Every hour
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
