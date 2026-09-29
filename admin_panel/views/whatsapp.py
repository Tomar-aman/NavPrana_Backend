"""
WhatsApp inbox.

A two-pane chat screen: conversations on the left, the open thread and a
reply box on the right. Customer messages arrive through the webhook in
``whatsapp.webhook``; replies go out through ``whatsapp.services.send_reply``.

Viewing needs ``whatsapp.view_conversation``; replying also needs
``whatsapp.add_message``. Superusers have both.
"""

import mimetypes

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, Subquery
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from whatsapp.client import WhatsAppError, mark_read
from whatsapp.models import Conversation, Message
from whatsapp.services import send_reply

from ..mixins import PanelAccessMixin, PanelContextMixin
from ..registry import registry

VIEW_PERM = 'whatsapp.view_conversation'
REPLY_PERM = 'whatsapp.add_message'
THREAD_LIMIT = 200

#: Served inline in the browser; anything else downloads, so a customer's
#: HTML or SVG file can never run script on the panel's origin.
INLINE_MIME_PREFIXES = ('image/jpeg', 'image/png', 'image/webp', 'image/gif',
                        'video/', 'audio/', 'application/pdf')


class WhatsAppAccessMixin:
    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm(VIEW_PERM):
            raise PermissionDenied('You do not have permission to view WhatsApp chats.')


class WhatsAppInboxView(WhatsAppAccessMixin, PanelContextMixin, TemplateView):
    template_name = 'panel/whatsapp/inbox.html'
    nav_key = 'whatsapp'
    page_title = 'WhatsApp'
    page_subtitle = 'Chat with customers on the business WhatsApp number'

    def get_breadcrumbs(self):
        return [('Support', ''), ('WhatsApp', '')]

    def get_conversations(self, term):
        latest = Message.objects.filter(conversation=OuterRef('pk')).order_by('-timestamp', '-pk')
        queryset = Conversation.objects.select_related('user').annotate(
            last_body=Subquery(latest.values('body')[:1]),
            last_type=Subquery(latest.values('msg_type')[:1]),
            last_direction=Subquery(latest.values('direction')[:1]),
        )
        if term:
            digits = ''.join(ch for ch in term if ch.isdigit())
            match = (
                Q(profile_name__icontains=term)
                | Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
                | Q(user__email__icontains=term)
            )
            if digits:
                match |= Q(wa_id__contains=digits)
            queryset = queryset.filter(match)
        return queryset.order_by('-last_message_at')[:100]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        term = (self.request.GET.get('q') or '').strip()
        active = None

        if 'pk' in self.kwargs:
            active = get_object_or_404(Conversation.objects.select_related('user'), pk=self.kwargs['pk'])
            if active.unread_count:
                Conversation.objects.filter(pk=active.pk).update(unread_count=0)
                last_in = active.messages.filter(direction=Message.INBOUND).order_by('-timestamp').first()
                if last_in and last_in.wa_message_id:
                    mark_read(last_in.wa_message_id)
                active.unread_count = 0

        thread = []
        customer_url = ''
        if active is not None:
            thread = list(
                active.messages.select_related('sent_by').order_by('-timestamp', '-pk')[:THREAD_LIMIT]
            )[::-1]
            users = registry.get('users')
            if active.user_id and users and users.user_can(self.request.user, 'view'):
                customer_url = users.detail_url(active.user)

        context.update(
            {
                'conversations': self.get_conversations(term),
                'active': active,
                'thread': thread,
                'thread_truncated': len(thread) == THREAD_LIMIT,
                'customer_url': customer_url,
                'can_reply': self.request.user.has_perm(REPLY_PERM),
                'search_term': term,
            }
        )
        return context


class WhatsAppReplyView(WhatsAppAccessMixin, PanelAccessMixin, View):
    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm(REPLY_PERM):
            raise PermissionDenied('You do not have permission to reply on WhatsApp.')

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        back = reverse('admin_panel:whatsapp_thread', args=[pk])
        text = (request.POST.get('text') or '').strip()
        upload = request.FILES.get('file')

        if not text and upload is None:
            messages.error(request, 'Type a message or attach a file.')
            return redirect(back)
        if len(text) > 4096:
            messages.error(request, 'WhatsApp messages are limited to 4096 characters.')
            return redirect(back)

        try:
            send_reply(conversation, request.user, text=text, upload=upload)
        except WhatsAppError as exc:
            messages.error(request, f'Not sent: {exc}')
        return redirect(back)


class WhatsAppMediaView(WhatsAppAccessMixin, PanelAccessMixin, View):
    """Stream a stored chat file to staff. The only way these files are served."""

    def get(self, request, pk):
        message = get_object_or_404(Message, pk=pk)
        if not message.media_file:
            raise Http404('This file has not been downloaded yet.')

        mime = message.media_mime or mimetypes.guess_type(message.media_file.name)[0] or 'application/octet-stream'
        inline = mime.startswith(INLINE_MIME_PREFIXES) and 'download' not in request.GET
        response = FileResponse(
            message.media_file.open('rb'),
            content_type=mime if inline else 'application/octet-stream',
            as_attachment=not inline,
            filename=message.media_filename or message.media_file.name.rsplit('/', 1)[-1],
        )
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, max-age=3600'
        return response
