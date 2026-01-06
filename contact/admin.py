from django.contrib import admin
from .models import SendUsQuery, PhoneNumber, Email, Address, FAQs, SocialMediaLink

@admin.register(SendUsQuery)
class SendUsQueryAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'subject', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('first_name', 'last_name', 'email', 'subject', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('first_name', 'last_name', 'email', 'phone_number', 'subject', 'message', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'subject', 'message')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'created_at')
    search_fields = ('phone_number',)
    ordering = ('-created_at',)
    readonly_fields = ( 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('phone_number',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at')
    search_fields = ('email',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('email',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('address_line1', 'city', 'state', 'postal_code', 'country', 'created_at')
    search_fields = ('address_line1', 'city', 'state', 'postal_code', 'country')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(FAQs)
class FAQsAdmin(admin.ModelAdmin):
    list_display = ('question', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ( 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('question', 'answer')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(SocialMediaLink)
class SocialMediaLinkAdmin(admin.ModelAdmin):
    list_display = ('platform_name', 'url', 'created_at')
    search_fields = ('platform_name',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('platform_name', 'url')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
