from django.contrib import admin
from .models import SMTPSettings

@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    list_display = ('host', 'username', 'from_email', 'use_tls', 'updated_at')
    list_filter = ('use_tls',)
    search_fields = ('host', 'username', 'from_email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('host', 'port', 'username', 'password', 'from_email', 'use_tls')
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
