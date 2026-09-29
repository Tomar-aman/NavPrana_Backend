"""
WhatsApp Cloud API webhook.

GET  — Meta's one-time subscription handshake. It sends hub.mode=subscribe,
       hub.verify_token and hub.challenge, and expects the challenge echoed
       back as plain text when the token matches WHATSAPP_VERIFY_TOKEN.
POST — Message status updates (sent/delivered/read/failed) and customer
       replies. Each request is signed with the app secret in the
       X-Hub-Signature-256 header; anything that fails the check is dropped.

Meta retries a POST that does not get a 200 quickly, so the handler only
writes rows; downloading a customer's file is left to a Celery task.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .services import apply_status, record_inbound

logger = logging.getLogger(__name__)


def _signature_is_valid(raw_body, header):
    secret = settings.WHATSAPP_APP_SECRET
    if not secret or not header or not header.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len('sha256='):])


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):

    def get(self, request, *args, **kwargs):
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge', '')

        verify_token = settings.WHATSAPP_VERIFY_TOKEN
        if mode == 'subscribe' and verify_token and hmac.compare_digest(token or '', verify_token):
            logger.info("WhatsApp webhook verified")
            return HttpResponse(challenge, content_type='text/plain')

        logger.warning("WhatsApp webhook verification failed (mode=%s)", mode)
        return HttpResponseForbidden()

    def post(self, request, *args, **kwargs):
        if not _signature_is_valid(request.body, request.headers.get('X-Hub-Signature-256')):
            logger.warning("WhatsApp webhook rejected: bad or missing signature")
            return HttpResponseForbidden()

        try:
            payload = json.loads(request.body)
        except ValueError:
            logger.warning("WhatsApp webhook rejected: body is not JSON")
            return HttpResponse(status=400)

        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                for st in value.get('statuses', []):
                    try:
                        apply_status(st)
                    except Exception:
                        logger.exception("WhatsApp status not applied: %s", st.get('id'))
                for msg in value.get('messages', []):
                    try:
                        record_inbound(value, msg)
                    except Exception:
                        # Logged, not raised: a 500 makes Meta retry the whole
                        # batch, and one bad message would block the rest.
                        logger.exception("WhatsApp inbound not stored: %s", msg.get('id'))

        return HttpResponse(status=200)
