# Celery Email Configuration Guide

This document provides a complete guide for setting up and using Celery for sending emails asynchronously in the NavPrana Backend.

## Overview

Celery is an asynchronous task queue system that allows us to send emails and perform other time-consuming operations in the background without blocking the main application.

## Prerequisites

- Redis (as message broker)
- Celery and Django Celery Beat packages

## Installation

### 1. Install Required Packages

```bash
pip install celery==5.3.4
pip install redis==5.0.1
pip install django-celery-beat==2.7.0
pip install django-celery-results==2.7.0
```

### 2. Update requirements.txt

```
celery==5.3.4
redis==5.0.1
django-celery-beat==2.7.0
django-celery-results==2.7.0
```

### 3. Install and Run Redis

#### On Ubuntu/Debian:
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### On macOS:
```bash
brew install redis
brew services start redis
```

#### On Windows:
Download and install Redis from: https://github.com/microsoftarchive/redis/releases

#### Using Docker:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## Configuration

### 1. Environment Variables (.env)

Add the following to your `.env` file:

```env
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email Configuration (existing settings)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DJANGO_DEFAULT_FROM_EMAIL=your-email@gmail.com
```

### 2. Settings.py Configuration

The configuration has been added to `config/settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_RESULT_EXPIRES = 3600
```

### 3. Celery Configuration File

The main Celery configuration is in `config/celery.py`:

```python
from celery import Celery
from celery.schedules import crontab
from decouple import config

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('navprana_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

### 4. Config __init__.py

The file `config/__init__.py` imports and initializes Celery:

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

## Running Celery

### Start Celery Worker

```bash
# Basic worker
celery -A config worker -l info

# With multiple worker processes
celery -A config worker -l info --concurrency=4

# On Windows (without thread-based worker)
celery -A config worker -l info --pool=solo
```

### Start Celery Beat (Scheduler)

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Monitor Celery Tasks (optional)

```bash
pip install flower
celery -A config flower --port=5555
# Access at http://localhost:5555
```

## Available Email Tasks

### 1. Order Confirmation Email

```python
from orders.tasks import send_order_confirmation_email

# Send async
send_order_confirmation_email.delay(order_id=123)
```

### 2. Payment Success Email

```python
from orders.tasks import send_payment_success_email

send_payment_success_email.delay(order_id=123, transaction_id='TXN123')
```

### 3. Payment Failed Email

```python
from orders.tasks import send_payment_failed_email

send_payment_failed_email.delay(order_id=123, error_message='Insufficient funds')
```

### 4. Order Shipped Email

```python
from orders.tasks import send_order_shipped_email

send_order_shipped_email.delay(order_id=123, tracking_number='TRACK123')
```

### 5. Order Delivered Email

```python
from orders.tasks import send_order_delivered_email

send_order_delivered_email.delay(order_id=123)
```

### 6. Invoice Email

```python
from orders.tasks import send_invoice_email

send_invoice_email.delay(order_id=123)
```

### 7. Welcome Email

```python
from users.tasks import send_welcome_email

send_welcome_email.delay(user_id=456)
```

### 8. Email Verification

```python
from users.tasks import send_email_verification_email

send_email_verification_email.delay(user_id=456, verification_code='ABC123')
```

### 9. Password Reset Email

```python
from users.tasks import send_password_reset_email

send_password_reset_email.delay(user_id=456, reset_token='TOKEN123')
```

## Integration with Views/Webhooks

### Example: Send Email After Payment Success

In `transactions/cashfree_webhook.py`:

```python
from orders.tasks import send_payment_success_email

def _handle_payment_success(self, data: dict) -> Response:
    # ... existing code ...
    
    # Send success email asynchronously
    send_payment_success_email.delay(
        order_id=order.id,
        transaction_id=transaction_id
    )
    
    return Response({...}, status=status.HTTP_200_OK)
```

### Example: Send Email After Order Creation

In `orders/views.py`:

```python
from orders.tasks import send_order_confirmation_email

def post(self, request, *args, **kwargs):
    # ... create order ...
    
    # Send confirmation email asynchronously
    send_order_confirmation_email.delay(order_id=order.id)
    
    return Response({...}, status=status.HTTP_201_CREATED)
```

## Periodic Tasks (Celery Beat)

Currently configured in `config/celery.py`:

```python
CELERY_BEAT_SCHEDULE = {
    'clean-expired-tokens': {
        'task': 'users.tasks.clean_expired_tokens',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

### Add More Periodic Tasks

Example: Send daily digest emails at 9 AM UTC

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'send-daily-digest': {
        'task': 'orders.tasks.send_daily_digest_email',
        'schedule': crontab(hour=9, minute=0),  # 9 AM UTC daily
    },
}
```

## Email Templates

Email templates are located in `templates/email/`:

```
templates/email/
├── order_confirmation.html/.txt
├── payment_success.html/.txt
├── payment_failed.html/.txt
├── order_shipped.html/.txt
├── order_delivered.html/.txt
├── send_invoice.html/.txt
├── welcome.html/.txt
├── verify_email.html/.txt
└── password_reset.html/.txt
```

Each email has both HTML and plain text versions.

## Task Retry Configuration

All email tasks are configured with automatic retries:

```python
@shared_task(bind=True, max_retries=3)
def send_order_confirmation_email(self, order_id):
    # Retries up to 3 times with exponential backoff
    # Waits 60s, then 120s, then 240s
    raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## Error Handling

All tasks include:
- Try-except blocks
- Proper logging
- Retry mechanisms
- Graceful failure handling

Check logs in `logs/debug.txt` and `logs/error.txt` for task execution details.

## Development vs Production

### Development

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Django Development Server
python manage.py runserver
```

### Production

Use a process manager like Supervisor or systemd:

```ini
# /etc/supervisor/conf.d/celery.conf
[program:navprana_celery]
command=celery -A config worker -l info --concurrency=4
directory=/path/to/NavPrana_Backend
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker.log

[program:navprana_celery_beat]
command=celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/path/to/NavPrana_Backend
user=www-data
stdout_logfile=/var/log/celery/beat.log
stderr_logfile=/var/log/celery/beat.log
```

## Troubleshooting

### Tasks Not Being Executed

1. Ensure Redis is running: `redis-cli ping` (should return PONG)
2. Check Celery worker is running: Look for worker startup messages
3. Check logs: `tail logs/debug.txt`

### Connection Refused to Redis

```bash
# Check Redis is running
redis-cli ping

# If not running, start it
redis-server
```

### Tasks Stuck in Queue

```bash
# Clear pending tasks (use with caution)
celery -A config purge

# Check queue status
celery -A config inspect active
celery -A config inspect scheduled
```

### Email Not Sending

1. Verify email credentials in `.env`
2. Check logs for SMTP errors
3. For Gmail, use App Password (not regular password)
4. Enable "Less secure app access" or use OAuth

## Best Practices

1. **Always use `.delay()` or `.apply_async()`** - Never call tasks directly in production
2. **Set appropriate timeouts** - Prevent hung tasks
3. **Use retry with exponential backoff** - Better than immediate retries
4. **Monitor task execution** - Use Flower or similar tools
5. **Test tasks locally** - Before deploying to production
6. **Keep tasks idempotent** - Safe to retry without side effects
7. **Log important events** - Help with debugging
8. **Use appropriate serializers** - JSON is safer than pickle

## Further Reading

- [Celery Documentation](https://docs.celeryproject.org/)
- [Django Celery Best Practices](https://docs.celeryproject.org/en/stable/django/)
- [Redis Documentation](https://redis.io/docs/)
