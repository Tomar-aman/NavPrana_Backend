# Celery Email Setup - Implementation Summary

## 🎯 What Has Been Implemented

A complete Celery asynchronous email system has been set up for the NavPrana Backend. This allows emails to be sent in the background without blocking the main application.

---

## 📦 Files Created/Modified

### Core Configuration Files
- **`config/celery.py`** - Main Celery configuration
- **`config/__init__.py`** - Celery app initialization
- **`config/settings.py`** - Updated with Celery configuration and apps

### Task Modules
- **`orders/tasks.py`** - Email tasks for orders:
  - `send_order_confirmation_email(order_id)`
  - `send_payment_success_email(order_id, transaction_id)`
  - `send_payment_failed_email(order_id, error_message)`
  - `send_order_shipped_email(order_id, tracking_number)`
  - `send_order_delivered_email(order_id)`
  - `send_invoice_email(order_id)`
  - `send_contact_reply_email(email_to, name, subject, message)`

- **`users/tasks.py`** - Email tasks for users:
  - `send_welcome_email(user_id)`
  - `send_email_verification_email(user_id, verification_code)`
  - `send_password_reset_email(user_id, reset_token)`
  - `clean_expired_tokens()` - Periodic task

### Email Templates
All templates have both HTML and plain text versions:
- `templates/email/order_confirmation.{html,txt}`
- `templates/email/payment_success.{html,txt}`
- `templates/email/payment_failed.{html,txt}`
- `templates/email/order_shipped.{html,txt}`
- `templates/email/order_delivered.{html,txt}`
- `templates/email/send_invoice.{html,txt}`
- `templates/email/welcome.{html,txt}`
- `templates/email/verify_email.{html,txt}`
- `templates/email/password_reset.{html,txt}`

### Documentation & Setup Scripts
- **`CELERY_EMAIL_SETUP.md`** - Comprehensive setup guide
- **`setup_celery.sh`** - Linux/macOS quick start script
- **`setup_celery.bat`** - Windows quick start script
- **`requirements.txt`** - Updated with Celery packages

---

## ⚙️ Configuration Details

### Installed Packages
```
celery==5.3.4
django-celery-beat==2.7.0
django-celery-results==2.7.0
redis==5.0.1
```

### Celery Settings (in settings.py)
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
```

### Beat Schedule (Periodic Tasks)
```python
CELERY_BEAT_SCHEDULE = {
    'clean-expired-tokens': {
        'task': 'users.tasks.clean_expired_tokens',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Run setup script
bash setup_celery.sh        # Linux/macOS
setup_celery.bat           # Windows

# Or manually
pip install -r requirements.txt
```

### 2. Set Environment Variables (.env)
```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DJANGO_DEFAULT_FROM_EMAIL=your-email@gmail.com
```

### 3. Install & Run Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:7-alpine

# Windows - Download from https://github.com/microsoftarchive/redis/releases
```

### 4. Run Celery
```bash
# Terminal 1: Celery Worker
celery -A config worker -l info

# Terminal 2: Celery Beat (optional, for scheduled tasks)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 3: Django Development Server
python manage.py runserver
```

---

## 📧 Task Usage Examples

### Send Order Confirmation Email
```python
from orders.tasks import send_order_confirmation_email

# Async execution
send_order_confirmation_email.delay(order_id=123)

# Sync execution (not recommended in production)
send_order_confirmation_email(123)
```

### Send Payment Success Email
```python
from orders.tasks import send_payment_success_email

send_payment_success_email.delay(order_id=123, transaction_id='TXN123')
```

### Send Welcome Email
```python
from users.tasks import send_welcome_email

send_welcome_email.delay(user_id=456)
```

---

## 🔧 Integration Points

### In Payment Webhook (transactions/cashfree_webhook.py)
```python
from orders.tasks import send_payment_success_email

# After marking payment as successful
send_payment_success_email.delay(
    order_id=order.id,
    transaction_id=transaction_id
)
```

### In Order Creation (orders/views.py)
```python
from orders.tasks import send_order_confirmation_email

# After creating order
send_order_confirmation_email.delay(order_id=order.id)
```

### In User Registration (users/views.py)
```python
from users.tasks import send_welcome_email

# After user creation
send_welcome_email.delay(user_id=user.id)
```

---

## 🎛️ Advanced Features

### Task Retries
All email tasks automatically retry up to 3 times with exponential backoff:
- 1st retry: 60 seconds
- 2nd retry: 120 seconds
- 3rd retry: 240 seconds

### Task Timeouts
- Hard limit: 30 minutes
- Soft limit: 25 minutes

### Error Handling
- Tasks log all errors
- Failed tasks are tracked
- Retries prevent transient failures

### Monitoring
Install Flower for task monitoring:
```bash
pip install flower
celery -A config flower --port=5555
# Access at http://localhost:5555
```

---

## 📋 Feature Checklist

- ✅ Celery configuration
- ✅ Redis broker setup
- ✅ Email task templates
- ✅ HTML and text email versions
- ✅ Task retry mechanism
- ✅ Error logging
- ✅ Periodic tasks support
- ✅ Complete documentation
- ✅ Quick start scripts
- ✅ Environment configuration examples

---

## 🔐 Security Notes

1. **Gmail Configuration**: Use App Passwords, not regular passwords
2. **Sensitive Data**: Don't commit `.env` file
3. **Task Parameters**: Avoid passing sensitive data in task parameters
4. **Redis**: Secure Redis with password in production
5. **Logging**: Monitor logs for failed tasks

---

## 🐛 Troubleshooting

### Redis Connection Error
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis if not running
redis-server
```

### Tasks Not Executing
1. Ensure Celery worker is running
2. Check Redis connection
3. Look for errors in worker logs

### Email Not Sending
1. Verify SMTP credentials
2. Check email templates exist
3. Look for errors in task logs (logs/debug.txt)

---

## 📚 Documentation Links

- [Celery Documentation](https://docs.celeryproject.org/)
- [Django Celery Integration](https://docs.celeryproject.org/en/stable/django/)
- [Redis Documentation](https://redis.io/docs/)
- [Django Email Documentation](https://docs.djangoproject.com/en/5.1/topics/email/)

---

## ✨ Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Run Redis**: `redis-server`
3. **Start Celery**: `celery -A config worker -l info`
4. **Test email sending**: Send test order
5. **Monitor with Flower**: `celery -A config flower`

---

## 📞 Support

Refer to `CELERY_EMAIL_SETUP.md` for detailed configuration and troubleshooting.

Happy emailing! 🎉
