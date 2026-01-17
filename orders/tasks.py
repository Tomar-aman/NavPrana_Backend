"""
Celery tasks for sending order-related emails

This module contains all async email tasks for order notifications.
"""

from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_confirmation_email(self, order_id):
    """
    Send order confirmation email to customer
    
    Args:
        order_id: ID of the order
    """
    try:
        from orders.models import Order
        
        order = Order.objects.select_related(
            'user', 'address', 'coupon'
        ).prefetch_related('items__product').get(id=order_id)
        
        context = {
            'order': order,
            'user': order.user,
            'items': order.items.all(),
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/order_confirmation.html',
            context
        )
        text_message = render_to_string(
            'email/order_confirmation.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Order Confirmation - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Order confirmation email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending order confirmation email for order {order_id}: {str(exc)}')
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_payment_success_email(self, order_id, transaction_id):
    """
    Send payment success email to customer
    
    Args:
        order_id: ID of the order
        transaction_id: Transaction ID for reference
    """
    try:
        from orders.models import Order
        
        order = Order.objects.select_related(
            'user', 'address'
        ).prefetch_related('items__product').get(id=order_id)
        
        context = {
            'order': order,
            'user': order.user,
            'transaction_id': transaction_id,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/payment_success.html',
            context
        )
        text_message = render_to_string(
            'email/payment_success.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Payment Successful - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Payment success email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending payment success email for order {order_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_payment_failed_email(self, order_id, error_message=None):
    """
    Send payment failure notification email to customer
    
    Args:
        order_id: ID of the order
        error_message: Error message explaining the failure
    """
    try:
        from orders.models import Order
        
        order = Order.objects.select_related('user').get(id=order_id)
        
        context = {
            'order': order,
            'user': order.user,
            'error_message': error_message or 'An error occurred during payment processing',
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/payment_failed.html',
            context
        )
        text_message = render_to_string(
            'email/payment_failed.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Payment Failed - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Payment failure email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending payment failed email for order {order_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_order_shipped_email(self, order_id, tracking_number=None):
    """
    Send order shipped notification email to customer
    
    Args:
        order_id: ID of the order
        tracking_number: Shipping tracking number (optional)
    """
    try:
        from orders.models import Order
        
        order = Order.objects.select_related(
            'user', 'address'
        ).prefetch_related('items__product').get(id=order_id)
        
        context = {
            'order': order,
            'user': order.user,
            'tracking_number': tracking_number,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/order_shipped.html',
            context
        )
        text_message = render_to_string(
            'email/order_shipped.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Your Order Shipped - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Order shipped email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending order shipped email for order {order_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_order_delivered_email(self, order_id):
    """
    Send order delivery confirmation email to customer
    
    Args:
        order_id: ID of the order
    """
    try:
        from orders.models import Order
        
        order = Order.objects.select_related(
            'user', 'address'
        ).prefetch_related('items__product').get(id=order_id)
        
        context = {
            'order': order,
            'user': order.user,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/order_delivered.html',
            context
        )
        text_message = render_to_string(
            'email/order_delivered.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=f'Order Delivered - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Order delivered email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending order delivered email for order {order_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_invoice_email(self, order_id):
    """
    Send invoice email with attachment to customer
    
    Args:
        order_id: ID of the order
    """
    try:
        from orders.models import Order
        from django.core.mail import EmailMessage
        
        order = Order.objects.select_related('user').get(id=order_id)
        
        if not order.invoice:
            logger.warning(f'Invoice not available for order {order_id}')
            return False
        
        context = {
            'order': order,
            'user': order.user,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/send_invoice.html',
            context
        )
        text_message = render_to_string(
            'email/send_invoice.txt',
            context
        )
        
        # Create email with attachment
        email = EmailMessage(
            subject=f'Invoice - Order #{order.id}',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        
        # Attach HTML alternative
        email.attach_alternative(html_message, "text/html")
        
        # Attach invoice PDF
        if order.invoice:
            invoice_file = order.invoice.open('rb')
            email.attach(
                f'invoice_{order.id}.pdf',
                invoice_file.read(),
                'application/pdf'
            )
            invoice_file.close()
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Invoice email sent for order {order_id}')
        return True
        
    except Order.DoesNotExist:
        logger.error(f'Order {order_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending invoice email for order {order_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def send_contact_reply_email(email_to, name, subject, message):
    """
    Send contact form reply email
    
    Args:
        email_to: Email address to send to
        name: Name of the recipient
        subject: Email subject
        message: Email message
    """
    try:
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Hello {name},</h2>
                <p>{message}</p>
                <br>
                <p>Best regards,<br>NavPrana Team</p>
            </body>
        </html>
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_to]
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f'Contact reply email sent to {email_to}')
        return True
        
    except Exception as exc:
        logger.error(f'Error sending contact reply email to {email_to}: {str(exc)}')
        return False
