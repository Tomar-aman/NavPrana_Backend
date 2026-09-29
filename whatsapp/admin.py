from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('timestamp', 'direction', 'msg_type', 'body', 'status', 'error')
    readonly_fields = fields
    can_delete = False
    ordering = ('-timestamp',)
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('wa_id', 'profile_name', 'user', 'unread_count', 'last_message_at')
    search_fields = ('wa_id', 'profile_name', 'user__email', 'user__first_name')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'last_message_at', 'last_inbound_at')
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'conversation', 'direction', 'msg_type', 'status')
    list_filter = ('direction', 'msg_type', 'status')
    search_fields = ('body', 'wa_message_id', 'conversation__wa_id')
    raw_id_fields = ('conversation', 'sent_by')
    readonly_fields = ('raw',)
