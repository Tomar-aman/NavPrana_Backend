from django.contrib import admin
from web_content.models import SocialLinks, WebContent
# Register your models here.

@admin.register(SocialLinks)
class SocialLinksAdmin(admin.ModelAdmin):
    list_display = ['twitter', 'instagram', 'linkedin', 'facebook', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['twitter', 'instagram', 'linkedin', 'facebook']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('twitter', 'instagram', 'linkedin', 'facebook', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(WebContent)
class WebContentAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'title', 'is_active', 'created_at', 'updated_at']
    list_filter = ['content_type', 'is_active', 'created_at', 'updated_at']
    search_fields = ['content_type', 'title', 'content']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('content_type', 'title', 'content', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
