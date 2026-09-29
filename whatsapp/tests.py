import hashlib
import hmac
import json
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Conversation, Message

User = get_user_model()
SECRET = 'test-app-secret'
WEBHOOK = '/api/whatsapp/webhook/'


def payload(messages=(), statuses=(), wa_id='919876543210', name='Asha'):
    value = {'messaging_product': 'whatsapp', 'contacts': [{'wa_id': wa_id, 'profile': {'name': name}}]}
    if messages:
        value['messages'] = list(messages)
    if statuses:
        value['statuses'] = list(statuses)
    return {'object': 'whatsapp_business_account', 'entry': [{'changes': [{'field': 'messages', 'value': value}]}]}


def text_msg(msg_id='wamid.1', body='Hello', wa_id='919876543210'):
    return {'from': wa_id, 'id': msg_id, 'timestamp': str(int(timezone.now().timestamp())),
            'type': 'text', 'text': {'body': body}}


class PrivateStorageMixin:
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.mkdtemp()
        field = Message._meta.get_field('media_file')
        patcher = mock.patch.object(field, 'storage', FileSystemStorage(location=self.media_dir))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.media_dir, True)


@override_settings(WHATSAPP_APP_SECRET=SECRET, WHATSAPP_VERIFY_TOKEN='vt', ALLOWED_HOSTS=['*'])
class WebhookTests(PrivateStorageMixin, TestCase):

    def post(self, body):
        raw = json.dumps(body).encode()
        sig = 'sha256=' + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
        return self.client.post(WEBHOOK, raw, content_type='application/json', HTTP_X_HUB_SIGNATURE_256=sig)

    def test_verify_handshake(self):
        ok = self.client.get(WEBHOOK, {'hub.mode': 'subscribe', 'hub.verify_token': 'vt', 'hub.challenge': '42'})
        self.assertEqual((ok.status_code, ok.content), (200, b'42'))
        bad = self.client.get(WEBHOOK, {'hub.mode': 'subscribe', 'hub.verify_token': 'nope', 'hub.challenge': '42'})
        self.assertEqual(bad.status_code, 403)

    def test_unsigned_post_is_rejected(self):
        response = self.client.post(WEBHOOK, json.dumps(payload([text_msg()])), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.exists())

    def test_inbound_text_opens_conversation_and_links_customer(self):
        customer = User.objects.create_user('asha@example.com', 'pw-Str0ng!123', phone_number='+91 98765 43210', is_active=True)
        self.assertEqual(self.post(payload([text_msg()])).status_code, 200)

        conversation = Conversation.objects.get()
        self.assertEqual(conversation.wa_id, '919876543210')
        self.assertEqual(conversation.profile_name, 'Asha')
        self.assertEqual(conversation.user, customer)
        self.assertEqual(conversation.unread_count, 1)
        self.assertTrue(conversation.window_open)
        self.assertEqual(conversation.messages.get().body, 'Hello')

    def test_redelivered_message_is_stored_once(self):
        self.post(payload([text_msg()]))
        self.post(payload([text_msg()]))
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.get().unread_count, 1)

    def test_inbound_document_is_downloaded_into_private_storage(self):
        doc = {'from': '919876543210', 'id': 'wamid.doc', 'timestamp': '1700000000', 'type': 'document',
               'document': {'id': 'media-9', 'mime_type': 'application/pdf', 'filename': 'report.pdf',
                            'caption': 'my lab report'}}
        with mock.patch('whatsapp.services.client.download_media', return_value=(b'%PDF-1.4', 'application/pdf')), \
                mock.patch('whatsapp.tasks.fetch_inbound_media.delay',
                           side_effect=lambda pk: __import__('whatsapp.tasks').tasks.fetch_inbound_media(pk)), \
                self.captureOnCommitCallbacks(execute=True):
            self.post(payload([doc]))

        message = Message.objects.get()
        self.assertEqual((message.msg_type, message.body, message.media_filename),
                         ('document', 'my lab report', 'report.pdf'))
        self.assertTrue(message.media_file.name.endswith('.pdf'))
        with message.media_file.open('rb') as fh:
            self.assertEqual(fh.read(), b'%PDF-1.4')

    def test_status_ticks_never_move_backwards(self):
        conversation = Conversation.objects.create(wa_id='919876543210')
        message = Message.objects.create(conversation=conversation, direction=Message.OUTBOUND,
                                         wa_message_id='wamid.out', status=Message.SENT)
        self.post(payload(statuses=[{'id': 'wamid.out', 'status': 'read'}]))
        self.post(payload(statuses=[{'id': 'wamid.out', 'status': 'delivered'}]))
        message.refresh_from_db()
        self.assertEqual(message.status, Message.READ)

        self.post(payload(statuses=[{'id': 'wamid.out', 'status': 'failed',
                                     'errors': [{'code': 131047, 'title': 'Re-engagement message'}]}]))
        message.refresh_from_db()
        self.assertEqual((message.status, message.error), (Message.FAILED, 'Re-engagement message'))


@override_settings(ALLOWED_HOSTS=['*'])
class InboxPanelTests(PrivateStorageMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        cls.reader = User.objects.create_user('reader@example.com', 'pw-Str0ng!123', is_staff=True, is_active=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename='view_conversation'))
        cls.shopper = User.objects.create_user('shopper@example.com', 'pw-Str0ng!123', is_active=True)

    def setUp(self):
        super().setUp()
        self.conversation = Conversation.objects.create(
            wa_id='919876543210', profile_name='Asha', unread_count=2,
            last_inbound_at=timezone.now(), last_message_at=timezone.now(),
        )
        Message.objects.create(conversation=self.conversation, direction=Message.INBOUND,
                               wa_message_id='wamid.in', body='Where is my order?', status=Message.RECEIVED)

    def reply(self, **data):
        return self.client.post(reverse('admin_panel:whatsapp_reply', args=[self.conversation.pk]), data)

    def test_non_staff_cannot_open_inbox(self):
        self.client.force_login(self.shopper)
        response = self.client.get(reverse('admin_panel:whatsapp'))
        self.assertEqual(response.status_code, 403)

    def test_opening_a_thread_shows_messages_and_clears_unread(self):
        self.client.force_login(self.admin)
        with mock.patch('admin_panel.views.whatsapp.mark_read') as mark_read:
            response = self.client.get(reverse('admin_panel:whatsapp_thread', args=[self.conversation.pk]))
        self.assertContains(response, 'Where is my order?')
        mark_read.assert_called_once_with('wamid.in')
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.unread_count, 0)

    def test_sidebar_badge_counts_unread_chats(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertContains(response, 'nav-link__badge')

    def test_reader_without_add_permission_cannot_reply(self):
        self.client.force_login(self.reader)
        with mock.patch('whatsapp.services.client.send_text') as send_text:
            self.assertEqual(self.reply(text='hi').status_code, 403)
        send_text.assert_not_called()

    def test_text_reply_is_sent_and_recorded(self):
        self.client.force_login(self.admin)
        with mock.patch('whatsapp.services.client.send_text', return_value='wamid.reply') as send_text:
            self.reply(text='It ships today')
        send_text.assert_called_once_with('919876543210', 'It ships today')
        sent = self.conversation.messages.get(direction=Message.OUTBOUND)
        self.assertEqual((sent.status, sent.wa_message_id, sent.sent_by), (Message.SENT, 'wamid.reply', self.admin))

    def test_file_reply_uploads_then_sends(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile('invoice.pdf', b'%PDF-1.4', content_type='application/pdf')
        with mock.patch('whatsapp.services.client.upload_media', return_value='media-1') as up, \
                mock.patch('whatsapp.services.client.send_media', return_value='wamid.file') as send:
            self.reply(text='Your invoice', file=upload)
        up.assert_called_once()
        send.assert_called_once_with('919876543210', 'document', 'media-1', 'Your invoice', 'invoice.pdf')
        sent = self.conversation.messages.get(direction=Message.OUTBOUND)
        self.assertTrue(sent.media_file)

    def test_closed_window_blocks_free_form_reply(self):
        Conversation.objects.filter(pk=self.conversation.pk).update(
            last_inbound_at=timezone.now() - timedelta(hours=25))
        self.client.force_login(self.admin)
        with mock.patch('whatsapp.services.client.send_text') as send_text:
            self.reply(text='hello?')
        send_text.assert_not_called()
        self.assertFalse(self.conversation.messages.filter(direction=Message.OUTBOUND).exists())

    def test_failed_send_is_kept_with_its_reason(self):
        from whatsapp.client import WhatsAppError

        self.client.force_login(self.admin)
        with mock.patch('whatsapp.services.client.send_text', side_effect=WhatsAppError('Invalid number')):
            self.reply(text='hi')
        failed = self.conversation.messages.get(direction=Message.OUTBOUND)
        self.assertEqual((failed.status, failed.error), (Message.FAILED, 'Invalid number'))

    def test_media_is_served_to_staff_only_and_html_downloads(self):
        message = Message.objects.create(conversation=self.conversation, direction=Message.INBOUND,
                                         msg_type='document', media_mime='text/html', status=Message.RECEIVED)
        message.media_file.save('x.html', ContentFile(b'<script>alert(1)</script>'))
        url = reverse('admin_panel:whatsapp_media', args=[message.pk])

        self.client.force_login(self.shopper)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', response['Content-Disposition'])
