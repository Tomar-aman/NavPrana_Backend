# Celery Email Integration Examples

This file provides practical examples of how to integrate Celery email tasks with your views and webhooks.

## Order Payment Success Integration

### In Cashfree Webhook (transactions/cashfree_webhook.py)

```python
from orders.tasks import send_payment_success_email, send_invoice_email
from transactions.models import TransactionLog

class CashfreeWebhookView(APIView):
    # ... existing code ...
    
    def _handle_payment_success(self, data: dict) -> Response:
        """Handle successful payment webhook"""
        try:
            order_data = data.get("order", {})
            payment_data = data.get("payment", {})
            order_id = order_data.get("order_id")
            
            # ... existing transaction logic ...
            
            txn = TransactionLog.objects.select_related("order").get(
                transaction_order_id=order_id
            )
            
            # Mark payment as successful
            txn.mark_cashfree_success({
                "order": order_data,
                "payment": payment_data
            })
            
            # Send success email asynchronously
            send_payment_success_email.delay(
                order_id=txn.order.id,
                transaction_id=order_id
            )
            
            # Send invoice email (optional, with delay)
            send_invoice_email.apply_async(
                args=[txn.order.id],
                countdown=5  # Send after 5 seconds
            )
            
            logger.info(f"Payment success processed: {order_id}")
            
            return Response(
                {"success": True, "message": "Payment processed"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error processing payment success: {str(e)}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_payment_failed(self, data: dict) -> Response:
        """Handle failed payment webhook"""
        try:
            order_data = data.get("order", {})
            payment_data = data.get("payment", {})
            order_id = order_data.get("order_id")
            
            # ... existing transaction logic ...
            
            txn = TransactionLog.objects.select_related("order").get(
                merchant_transaction_id=order_id
            )
            
            error_msg = (
                payment_data.get("error_details", {}).get("error_description")
                or "Payment failed"
            )
            
            # Mark transaction as failed
            txn.mark_as_failed(error_msg)
            
            # Send failure email asynchronously
            from orders.tasks import send_payment_failed_email
            
            send_payment_failed_email.delay(
                order_id=txn.order.id,
                error_message=error_msg
            )
            
            logger.info(f"Payment failed: {order_id}")
            
            return Response({"success": True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing payment failure: {str(e)}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
```

## Order Creation Integration

### In Orders Views (orders/views.py)

```python
from orders.tasks import send_order_confirmation_email
from django.db import transaction

class CreateOrderView(GenericAPIView):
    """Create a new order and send confirmation email"""
    
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create order
                order = Order.create_order(
                    user=request.user,
                    products_data=validated_products,
                    coupon_code=coupon_code,
                    tax_percentage=tax_percentage,
                    notes=notes,
                    address_id=address_id
                )
                
                # Send confirmation email asynchronously
                send_order_confirmation_email.delay(order_id=order.id)
                
                return Response({
                    'success': True,
                    'order_id': order.id,
                    'message': 'Order created successfully. Confirmation email sent.'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## User Registration Integration

### In Users Views (users/views.py)

```python
from users.tasks import send_welcome_email, send_email_verification_email
import uuid

class UserRegistrationView(GenericAPIView):
    """Register new user and send welcome email"""
    
    def post(self, request):
        try:
            serializer = UserRegistrationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create user
            user = serializer.save()
            
            # Generate verification code
            verification_code = str(uuid.uuid4())
            
            # Store verification code in cache or database
            # cache.set(f'email_verification_{user.id}', verification_code, timeout=3600)
            
            # Send welcome email
            send_welcome_email.delay(user_id=user.id)
            
            # Send verification email
            send_email_verification_email.delay(
                user_id=user.id,
                verification_code=verification_code
            )
            
            return Response({
                'success': True,
                'message': 'User registered successfully. Check your email to verify account.',
                'user_id': user.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Password Reset Integration

### In Password Reset View (users/views.py)

```python
from users.tasks import send_password_reset_email
import uuid

class PasswordResetView(GenericAPIView):
    """Request password reset and send reset email"""
    
    def post(self, request):
        email = request.data.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            reset_token = str(uuid.uuid4())
            
            # Store reset token in cache with expiration
            # cache.set(f'password_reset_{user.id}', reset_token, timeout=3600)
            
            # Send password reset email
            send_password_reset_email.delay(
                user_id=user.id,
                reset_token=reset_token
            )
            
            return Response({
                'success': True,
                'message': 'Password reset link sent to your email.'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Don't reveal if user exists
            return Response({
                'success': True,
                'message': 'If this email exists, you will receive a password reset link.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error requesting password reset: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Order Status Update Integration

### Signals for Automatic Email Sending (orders/signals.py)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from orders.tasks import (
    send_order_shipped_email,
    send_order_delivered_email
)

@receiver(post_save, sender=Order)
def send_order_status_emails(sender, instance, created, update_fields, **kwargs):
    """
    Send appropriate email when order status changes
    """
    if not created and update_fields:
        # Order was updated, not created
        
        if 'status' in update_fields:
            # Status was changed
            if instance.status == 'processing':
                # Send order confirmation if not already sent
                from orders.tasks import send_order_confirmation_email
                send_order_confirmation_email.delay(order_id=instance.id)
            
            elif instance.status == 'shipped':
                # Send shipped notification
                send_order_shipped_email.delay(
                    order_id=instance.id,
                    tracking_number=None  # Update with actual tracking number
                )
            
            elif instance.status == 'completed':
                # Send delivery notification
                send_order_delivered_email.delay(order_id=instance.id)

# In orders/apps.py
from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    
    def ready(self):
        import orders.signals  # Import signals when app is ready
```

## Contact Form Integration

### In Contact Views (contact/views.py)

```python
from orders.tasks import send_contact_reply_email

class ContactFormView(GenericAPIView):
    """Handle contact form submission"""
    
    def post(self, request):
        serializer = ContactFormSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Save contact form
            contact = serializer.save()
            
            # Send acknowledgment email
            send_contact_reply_email.delay(
                email_to=contact.email,
                name=contact.name,
                subject="We've received your message",
                message=f"""
                Thank you for contacting NavPrana!
                
                We have received your message and will get back to you within 24 hours.
                
                Message: {contact.message}
                
                Best regards,
                NavPrana Team
                """
            )
            
            return Response({
                'success': True,
                'message': 'Your message has been sent. We will contact you soon.'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error processing contact form: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Task Scheduling Examples

### Send Daily Digest Email

```python
# In orders/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def send_daily_digest_email():
    """Send daily sales digest to admin"""
    try:
        # Get orders from last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        orders = Order.objects.filter(
            created_at__gte=yesterday,
            payment_status='paid'
        )
        
        total_sales = sum(order.final_amount for order in orders)
        
        # Send email to admin
        from django.core.mail import send_mail
        from django.conf import settings
        
        message = f"""
        Daily Sales Digest
        
        Total Orders: {orders.count()}
        Total Sales: ₹{total_sales}
        
        See admin dashboard for more details.
        """
        
        send_mail(
            'Daily Sales Digest',
            message,
            settings.DEFAULT_FROM_EMAIL,
            ['admin@navprana.com'],
            fail_silently=False,
        )
        
        logger.info('Daily digest email sent')
        return True
        
    except Exception as e:
        logger.error(f'Error sending daily digest: {str(e)}')
        return False

# In config/celery.py - add to CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {
    'send-daily-digest': {
        'task': 'orders.tasks.send_daily_digest_email',
        'schedule': crontab(hour=8, minute=0),  # 8 AM UTC daily
    },
}
```

## Error Handling Best Practices

```python
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

@shared_task(bind=True, max_retries=3, time_limit=300)
def send_critical_email(self, user_id, email_type):
    """Send critical email with proper error handling"""
    try:
        # Your email logic here
        pass
        
    except SoftTimeLimitExceeded:
        # Task is about to be killed
        logger.error(f'Task timeout for user {user_id}')
        # Don't retry
        return False
        
    except ConnectionError as e:
        # Network error - retry
        logger.error(f'Connection error: {str(e)}')
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    except Exception as e:
        # Generic error - retry
        logger.error(f'Error sending email: {str(e)}')
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

---

## Testing Celery Tasks

### Test Task Execution

```python
# In tests
from django.test import TestCase
from orders.tasks import send_order_confirmation_email

class OrderEmailTestCase(TestCase):
    
    def setUp(self):
        self.order = Order.objects.create(
            user=self.user,
            total_amount=1000,
            final_amount=1000,
        )
    
    def test_send_order_confirmation_email(self):
        """Test order confirmation email task"""
        # Execute task synchronously in tests
        result = send_order_confirmation_email(self.order.id)
        self.assertTrue(result)
```

---

Enjoy seamless email delivery with Celery! 🚀
