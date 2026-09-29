"""
Turning webhook payloads into inbox rows, and sending replies from the panel.
"""

import logging
import mimetypes
from datetime import datetime, timezone as dt_timezone

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Replace
from django.utils import timezone

from . import client
from .models import Conversation, Message

logger = logging.getLogger(__name__)


def _digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _match_user(wa_id):
    """The customer account whose phone number ends in the same 10 digits.

    Accounts store numbers in whatever shape the customer typed them
    (``98765…``, ``+91 98765…``, ``091-…``), so separators are stripped and
    only the last 10 digits compared.
    """
    from users.models import User

    tail = wa_id[-10:]
    if len(tail) < 10:
        return None
    digits = F('phone_number')
    for sep in (' ', '-', '+', '(', ')'):
        digits = Replace(digits, Value(sep), Value(''))
    return (
        User.objects.filter(phone_number__isnull=False)
        .annotate(phone_digits=digits)
        .filter(phone_digits__endswith=tail)
        .order_by('-date_joined')
        .first()
    )


def _when(unix_seconds):
    try:
        return datetime.fromtimestamp(int(unix_seconds), tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return timezone.now()


def _describe(msg):
    """``(msg_type, body, media)`` for one inbound message dict from Meta."""
    kind = msg.get('type', 'unknown')
    part = msg.get(kind) or {}

    if kind == 'text':
        return kind, part.get('body', ''), None
    if kind in Message.MEDIA_TYPES:
        media = {
            'id': part.get('id', ''),
            'mime': part.get('mime_type', ''),
            'filename': part.get('filename', ''),
        }
        return kind, part.get('caption', ''), media
    if kind == 'location':
        where = ' · '.join(filter(None, [part.get('name'), part.get('address')]))
        link = f"https://maps.google.com/?q={part.get('latitude')},{part.get('longitude')}"
        return kind, f'📍 {where}\n{link}'.strip(), None
    if kind == 'button':
        return kind, part.get('text', ''), None
    if kind == 'interactive':
        reply = part.get('button_reply') or part.get('list_reply') or {}
        return kind, reply.get('title', ''), None
    if kind == 'reaction':
        return kind, part.get('emoji', '') or '(reaction removed)', None
    if kind == 'contacts':
        names = [c.get('name', {}).get('formatted_name', '') for c in msg.get('contacts', [])]
        return kind, 'Shared contact: ' + ', '.join(filter(None, names)), None
    return kind, f'[{kind} message — not supported by the WhatsApp API]', None


def record_inbound(value, msg):
    """Store one customer message. Returns the new :class:`Message`, or None
    when Meta is redelivering one we already have."""
    wa_id = _digits(msg.get('from'))
    if not wa_id:
        return None
    if Message.objects.filter(wa_message_id=msg.get('id')).exists():
        return None

    profile = next(
        (c.get('profile', {}).get('name', '') for c in value.get('contacts', []) if c.get('wa_id') == wa_id),
        '',
    )
    kind, body, media = _describe(msg)
    when = _when(msg.get('timestamp'))

    try:
        with transaction.atomic():
            conversation, created = Conversation.objects.select_for_update().get_or_create(
                wa_id=wa_id, defaults={'profile_name': profile, 'user': _match_user(wa_id)},
            )
            message = Message.objects.create(
                conversation=conversation,
                wa_message_id=msg.get('id'),
                direction=Message.INBOUND,
                msg_type=kind,
                body=body,
                media_id=(media or {}).get('id', ''),
                media_mime=(media or {}).get('mime', ''),
                media_filename=(media or {}).get('filename', ''),
                status=Message.RECEIVED,
                raw=msg,
                timestamp=when,
            )
            updates = {'unread_count': F('unread_count') + 1, 'last_message_at': when, 'last_inbound_at': when}
            if profile and profile != conversation.profile_name:
                updates['profile_name'] = profile
            if not created and conversation.user_id is None:
                updates['user'] = _match_user(wa_id)
            Conversation.objects.filter(pk=conversation.pk).update(**updates)
    except IntegrityError:
        # Two deliveries of the same message raced past the exists() check.
        return None

    if media and media['id']:
        from .tasks import fetch_inbound_media

        transaction.on_commit(lambda: _queue(fetch_inbound_media, message.pk))
    return message


def _queue(task, *args):
    try:
        task.delay(*args)
    except Exception:
        # Broker down: fetch inline rather than lose the file. Meta keeps
        # inbound media for a limited time only.
        logger.exception('Could not queue %s; running inline', task.name)
        task(*args)


def apply_status(status):
    """Move an outbound message's ticks forward from a status webhook."""
    message = Message.objects.filter(wa_message_id=status.get('id')).first()
    if message is None:
        return
    errors = status.get('errors') or []
    error = '; '.join(
        (e.get('error_data', {}).get('details') or e.get('title') or e.get('message') or str(e.get('code')))
        for e in errors
    )
    changed = message.advance_status(status.get('status', ''), error)
    if changed:
        message.save(update_fields=changed)


def store_inbound_media(message):
    """Download an inbound file from Meta into private storage."""
    content, mime = client.download_media(message.media_id)
    mime = (mime or message.media_mime or '').split(';')[0].strip()
    ext = mimetypes.guess_extension(mime) or ''
    name = message.media_filename or f'{message.msg_type}{ext}'
    message.media_mime = mime
    message.media_file.save(name, ContentFile(content), save=False)
    message.save(update_fields=['media_file', 'media_mime'])


def send_reply(conversation, user, text='', upload=None):
    """Send staff's reply and record it. Raises :class:`client.WhatsAppError`.

    The row is saved first, as ``pending``, so a failed send still shows in
    the thread with its reason instead of silently vanishing.
    """
    if not conversation.window_open:
        raise client.WhatsAppError(
            'The 24-hour reply window has closed. The customer has to message first, '
            'or you need to send an approved template.'
        )

    kind, mime = 'text', ''
    if upload is not None:
        mime = (upload.content_type or mimetypes.guess_type(upload.name)[0] or 'application/octet-stream')
        kind = client.outbound_media_type(mime)
        limit = client.OUTBOUND_MEDIA[kind][1]
        if upload.size > limit:
            raise client.WhatsAppError(
                f'{upload.name} is {upload.size // (1024 * 1024)} MB; WhatsApp allows '
                f'{limit // (1024 * 1024)} MB for a {kind}.'
            )

    message = Message(
        conversation=conversation,
        direction=Message.OUTBOUND,
        msg_type=kind,
        body=text,
        media_mime=mime,
        media_filename=upload.name if upload is not None else '',
        status=Message.PENDING,
        sent_by=user,
    )
    if upload is not None:
        message.media_file.save(upload.name, upload, save=False)
    message.save()

    try:
        if upload is None:
            wa_id = client.send_text(conversation.wa_id, text)
        else:
            with message.media_file.open('rb') as fh:
                message.media_id = client.upload_media(fh, upload.name, mime)
            wa_id = client.send_media(conversation.wa_id, kind, message.media_id, text, upload.name)
    except client.WhatsAppError as exc:
        message.status, message.error = Message.FAILED, str(exc)
        message.save(update_fields=['status', 'error', 'media_id'])
        raise

    message.wa_message_id, message.status = wa_id, Message.SENT
    message.save(update_fields=['wa_message_id', 'status', 'media_id'])
    Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.timestamp)
    return message
