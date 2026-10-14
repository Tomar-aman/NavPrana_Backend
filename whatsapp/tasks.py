import logging

from celery import shared_task

from .client import WhatsAppError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4, default_retry_delay=60)
def fetch_inbound_media(self, message_id):
    """Pull a customer's file from Meta into private storage."""
    from .models import Message
    from .services import store_inbound_media

    message = Message.objects.filter(pk=message_id).first()
    if message is None or message.media_file or not message.media_id:
        return
    try:
        store_inbound_media(message)
    except WhatsAppError as exc:
        logger.warning('WhatsApp media %s not fetched yet: %s', message.media_id, exc)
        if self.request.called_directly:
            raise
        raise self.retry(exc=exc)


@shared_task(ignore_result=True)
def record_otp_message(phone, purpose, occurred_at, wa_message_id='', error=''):
    """Add a sent (or failed) OTP to the inbox; see services.record_otp_message."""
    from django.utils.dateparse import parse_datetime

    from .services import record_otp_message as record

    record(phone, purpose, parse_datetime(occurred_at), wa_message_id=wa_message_id, error=error)


@shared_task(bind=True, ignore_result=True, max_retries=3, default_retry_delay=10)
def apply_status_later(self, status):
    """Re-apply a status whose message had not been written yet (an OTP whose
    inbox row was still in the queue). Gives up quietly after a few tries."""
    from .models import Message
    from .services import apply_status

    if not Message.objects.filter(wa_message_id=status.get('id')).exists():
        if self.request.retries >= self.max_retries:
            return
        raise self.retry()
    apply_status(status, _retrying=True)
