"""
Thin client for the WhatsApp Cloud API (graph.facebook.com).

Every call raises :class:`WhatsAppError` with Meta's own error text, so the
panel can show staff exactly why a send was refused.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 20

#: What Meta accepts per outbound media type, and the size cap for each.
#: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media#supported-media-types
OUTBOUND_MEDIA = {
    'image': ({'image/jpeg', 'image/png'}, 5 * 1024 * 1024),
    'video': ({'video/mp4', 'video/3gpp'}, 16 * 1024 * 1024),
    'audio': ({'audio/aac', 'audio/amr', 'audio/mpeg', 'audio/mp4', 'audio/ogg'}, 16 * 1024 * 1024),
    'document': (None, 100 * 1024 * 1024),
}


class WhatsAppError(Exception):
    pass


def _base():
    return f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}'


def _headers():
    return {'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}'}


def _check(response):
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.ok and 'error' not in data:
        return data
    err = data.get('error', {})
    detail = err.get('error_data', {}).get('details') or err.get('message') or response.text[:300]
    raise WhatsAppError(f'{detail} (code {err.get("code", response.status_code)})')


def _post_message(payload):
    url = f'{_base()}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages'
    body = {'messaging_product': 'whatsapp', 'recipient_type': 'individual', **payload}
    try:
        response = requests.post(url, json=body, headers=_headers(), timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise WhatsAppError(f'Could not reach WhatsApp: {exc}') from exc
    return _check(response)['messages'][0]['id']


def outbound_media_type(mime):
    """Pick the WhatsApp message type Meta will accept for a file of ``mime``."""
    for kind in ('image', 'video', 'audio'):
        if mime in OUTBOUND_MEDIA[kind][0]:
            return kind
    return 'document'


def send_text(to, text):
    """Send a free-form text. Returns Meta's message id (``wamid.…``)."""
    return _post_message({'to': to, 'type': 'text', 'text': {'body': text, 'preview_url': True}})


def upload_media(fileobj, filename, mime):
    """Upload a file to Meta and return its media id, for use in :func:`send_media`."""
    url = f'{_base()}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media'
    try:
        response = requests.post(
            url,
            headers=_headers(),
            data={'messaging_product': 'whatsapp', 'type': mime},
            files={'file': (filename, fileobj, mime)},
            timeout=120,
        )
    except requests.RequestException as exc:
        raise WhatsAppError(f'Could not upload the file: {exc}') from exc
    return _check(response)['id']


def send_media(to, kind, media_id, caption='', filename=''):
    media = {'id': media_id}
    # Meta rejects a caption on audio, and only documents carry a filename.
    if caption and kind != 'audio':
        media['caption'] = caption
    if kind == 'document' and filename:
        media['filename'] = filename
    return _post_message({'to': to, 'type': kind, kind: media})


def download_media(media_id):
    """Fetch an inbound file. Returns ``(content_bytes, mime_type)``.

    Meta hands out a short-lived URL first; the file itself needs the same
    bearer token, so it cannot be linked to directly.
    """
    try:
        meta = _check(requests.get(f'{_base()}/{media_id}', headers=_headers(), timeout=TIMEOUT))
        response = requests.get(meta['url'], headers=_headers(), timeout=120)
    except requests.RequestException as exc:
        raise WhatsAppError(f'Could not download media {media_id}: {exc}') from exc
    if not response.ok:
        raise WhatsAppError(f'Media download failed with HTTP {response.status_code}')
    return response.content, meta.get('mime_type', response.headers.get('Content-Type', ''))


def mark_read(wa_message_id):
    """Show the customer blue ticks on their message. Best effort."""
    url = f'{_base()}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages'
    try:
        _check(requests.post(
            url,
            json={'messaging_product': 'whatsapp', 'status': 'read', 'message_id': wa_message_id},
            headers=_headers(),
            timeout=TIMEOUT,
        ))
    except (WhatsAppError, requests.RequestException) as exc:
        logger.info('WhatsApp mark_read failed for %s: %s', wa_message_id, exc)
