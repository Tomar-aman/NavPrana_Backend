"""
Celery tasks for user-related emails

This module contains async email tasks for user notifications.
"""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from config.utils import send_mail as send_mail_util
import logging

logger = logging.getLogger(__name__)


# @shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """
    Send welcome email to new user
    
    Args:
        user_id: ID of the user
    """
    try:
        from users.models import User
        
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
        }
        
        # Render email template
        html_message = render_to_string(
            'email/welcome.html',
            context
        )
        text_message = render_to_string(
            'email/welcome.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject='Welcome to NavPrana!',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Welcome email sent to user {user_id}')
        return True
        
    except User.DoesNotExist:
        logger.error(f'User {user_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending welcome email to user {user_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# @shared_task(bind=True, max_retries=3)
def send_email_verification_email(self, user_id, verification_code):
    """
    Send email verification code to user
    
    Args:
        user_id: ID of the user
        verification_code: Email verification code
    """
    try:
        from users.models import User
        
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'verification_code': verification_code,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
            'verification_link': f"{settings.FRONTEND_URL}/verify-email?code={verification_code}",
        }
        
        # Render email template
        html_message = render_to_string(
            'email/verify_email.html',
            context
        )
        text_message = render_to_string(
            'email/verify_email.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject='Verify Your Email Address',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Email verification code sent to user {user_id}')
        return True
        
    except User.DoesNotExist:
        logger.error(f'User {user_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending email verification to user {user_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# @shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_id, reset_token):
    """
    Send password reset email to user
    
    Args:
        user_id: ID of the user
        reset_token: Password reset token
    """
    try:
        from users.models import User
        
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'reset_token': reset_token,
            'site_url': settings.SITE_URL,
            'frontend_url': settings.FRONTEND_URL,
            'reset_link': f"{settings.FRONTEND_URL}/reset-password?token={reset_token}",
        }
        
        # Render email template
        html_message = render_to_string(
            'email/password_reset.html',
            context
        )
        text_message = render_to_string(
            'email/password_reset.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject='Reset Your Password',
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f'Password reset email sent to user {user_id}')
        return True
        
    except User.DoesNotExist:
        logger.error(f'User {user_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending password reset email to user {user_id}: {str(exc)}')
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def clean_expired_tokens():
    """Clean up expired tokens from the token blacklist"""
    try:
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from django.utils import timezone
        from datetime import timedelta
        
        # Delete tokens that have been blacklisted for more than 30 days
        expiration_date = timezone.now() - timedelta(days=30)
        BlacklistedToken.objects.filter(
            blacklisted_at__lt=expiration_date
        ).delete()
        
        logger.info('Expired tokens cleaned up successfully')
        return True
        
    except Exception as exc:
        logger.error(f'Error cleaning expired tokens: {str(exc)}')
        return False


@shared_task(bind=True, max_retries=3)
def send_otp_email(self, subject, template_name, user_id, otp_code):
    """Send OTP email asynchronously using existing mail utility."""
    try:
        from users.models import User

        user = User.objects.get(id=user_id)
        send_mail_util(
            subject=subject,
            email_template_name=template_name,
            context={
                "user": user,
                "otp_code": otp_code,
            },
            to_email=user.email,
        )
        logger.info(f'OTP email sent to {user.email}')
        return True
    except User.DoesNotExist:
        logger.error(f'User {user_id} not found for OTP email')
        return False
    except Exception as exc:
        logger.error(f'Error sending OTP email to user {user_id}: {exc}')
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
