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
