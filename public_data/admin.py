from django.contrib import admin
from .models import InstagramReel

@admin.register(InstagramReel)
class InstagramReelAdmin(admin.ModelAdmin):
    list_display = ("caption", "instagram_url", "is_active", "sort_order", "created_at")
    list_editable = ("is_active", "sort_order")
    search_fields = ("caption", "instagram_url")
    ordering = ("sort_order", "-created_at")
    fieldsets = (
        (None, {
            "fields": ("instagram_url", "thumbnail", "caption", "is_active", "sort_order")
        }),
    )

