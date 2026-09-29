"""
WhatsApp inbox storage.

One :class:`Conversation` per customer WhatsApp number, holding every
:class:`Message` in both directions. Inbound rows are written by the webhook,
outbound rows by the panel's reply form.

Meta only allows free-form (non-template) replies within 24 hours of the
customer's last message, so the conversation keeps ``last_inbound_at`` to
answer "can staff still type a reply?" without scanning messages.
"""

import uuid
from datetime import timedelta
from pathlib import PurePath

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


#: Customer files live outside MEDIA_ROOT (which is served publicly) and are
#: only handed out by the staff-only panel view.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)

REPLY_WINDOW = timedelta(hours=24)


def media_upload_path(instance, filename):
    # A random name, so nothing about the customer or the file ends up on disk.
    ext = PurePath(filename).suffix.lower()[:10]
    return f'whatsapp/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}'


class Conversation(models.Model):
    wa_id = models.CharField(
        _('WhatsApp number'), max_length=20, unique=True,
        help_text=_('Digits only, with country code, as Meta sends it (e.g. 919876543210).'),
    )
    profile_name = models.CharField(_('WhatsApp name'), max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='whatsapp_conversations', verbose_name=_('customer account'),
    )
    last_message_at = models.DateTimeField(_('last message at'), null=True, blank=True, db_index=True)
    last_inbound_at = models.DateTimeField(_('last customer message at'), null=True, blank=True)
    unread_count = models.PositiveIntegerField(_('unread'), default=0)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('WhatsApp conversation')
        verbose_name_plural = _('WhatsApp conversations')
        ordering = ['-last_message_at']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.user_id and self.user.first_name:
            return f'{self.user.first_name} {self.user.last_name}'.strip()
        return self.profile_name or f'+{self.wa_id}'

    @property
    def window_expires_at(self):
        return self.last_inbound_at + REPLY_WINDOW if self.last_inbound_at else None

    @property
    def window_open(self):
        expires = self.window_expires_at
        return bool(expires and expires > timezone.now())


class Message(models.Model):
    INBOUND = 'in'
    OUTBOUND = 'out'
    DIRECTION_CHOICES = ((INBOUND, _('From customer')), (OUTBOUND, _('From us')))

    # Statuses only ever move forward; see RANK and Message.advance_status.
    RECEIVED = 'received'
    PENDING = 'pending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    STATUS_CHOICES = (
        (RECEIVED, _('Received')),
        (PENDING, _('Sending')),
        (SENT, _('Sent')),
        (DELIVERED, _('Delivered')),
        (READ, _('Read')),
        (FAILED, _('Failed')),
    )
    RANK = {PENDING: 0, SENT: 1, DELIVERED: 2, READ: 3}

    MEDIA_TYPES = ('image', 'video', 'audio', 'document', 'sticker')

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages',
    )
    wa_message_id = models.CharField(
        _('WhatsApp message id'), max_length=128, unique=True, null=True, blank=True,
    )
    direction = models.CharField(_('direction'), max_length=3, choices=DIRECTION_CHOICES)
    msg_type = models.CharField(_('type'), max_length=20, default='text')
    body = models.TextField(_('text'), blank=True)

    media_id = models.CharField(_('Meta media id'), max_length=128, blank=True)
    media_file = models.FileField(
        _('file'), storage=private_storage, upload_to=media_upload_path, blank=True,
    )
    media_mime = models.CharField(_('file type'), max_length=100, blank=True)
    media_filename = models.CharField(_('file name'), max_length=255, blank=True)

    status = models.CharField(_('status'), max_length=12, choices=STATUS_CHOICES)
    error = models.TextField(_('error'), blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('sent by'),
    )
    raw = models.JSONField(_('raw payload'), default=dict, blank=True)
    timestamp = models.DateTimeField(_('time'), default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _('WhatsApp message')
        verbose_name_plural = _('WhatsApp messages')
        ordering = ['timestamp', 'pk']

    def __str__(self):
        return f'{self.get_direction_display()} · {self.msg_type} · {self.timestamp:%d %b %H:%M}'

    @property
    def is_media(self):
        return self.msg_type in self.MEDIA_TYPES

    @property
    def is_image(self):
        return self.msg_type in ('image', 'sticker') or self.media_mime.startswith('image/')

    def advance_status(self, new_status, error=''):
        """Apply a webhook status without ever moving backwards.

        Meta can deliver ``delivered`` after ``read`` for the same message, so
        a later webhook must not undo a tick the customer already produced.
        Returns the fields that changed.
        """
        if new_status == self.FAILED:
            self.status, self.error = self.FAILED, error
            return ['status', 'error']
        if self.RANK.get(new_status, -1) > self.RANK.get(self.status, -1):
            self.status = new_status
            return ['status']
        return []
