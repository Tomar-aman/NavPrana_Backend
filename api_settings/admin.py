from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import PricingSettings, SMTPSettings


@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    """
    A settings page rather than a list: clicking "Pricing Settings" in the
    admin goes straight to the one row, which is created on first view.
    """

    readonly_fields = ('updated_at',)
    fieldsets = (
        (
            'Cash on Delivery',
            {
                'fields': ('cod_handling_fee',),
                'description': (
                    'Charged on top of the order when the shopper pays at the '
                    'door. Applies to new orders only — orders already placed '
                    'keep the fee they were quoted.'
                ),
            },
        ),
        (
            'Delivery',
            {'fields': ('shipping_fee', 'free_shipping_threshold')},
        ),
        (
            'Encourage online payment',
            {
                'fields': ('prepaid_discount_enabled', 'prepaid_discount'),
                'description': (
                    'Turns the COD fee into a prepaid discount instead. The '
                    'checkout page rewords itself to match.'
                ),
            },
        ),
        ('Timestamps', {'classes': ('collapse',), 'fields': ('updated_at',)}),
    )

    def has_add_permission(self, request):
        # There is one row and it is created on demand — an "Add" button would
        # only ever offer to overwrite it.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Skip the one-row list and open the settings themselves."""
        settings_obj = PricingSettings.load()
        return HttpResponseRedirect(
            reverse('admin:api_settings_pricingsettings_change', args=[settings_obj.pk])
        )

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
    
