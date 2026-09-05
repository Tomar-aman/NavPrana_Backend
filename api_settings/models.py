from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class PricingSettings(models.Model):
    """
    Storefront pricing, edited in the admin instead of in the source.

    One row, always. Orders price themselves against it, and the storefront
    reads the same values over ``/api/v1/public/pricing/`` so the checkout page
    quotes exactly what the backend will charge. Both sides used to carry their
    own hardcoded copy of these numbers and had already drifted once.

    Editing these values never re-prices an order that already exists: an Order
    writes what it charged into its own columns when it is created, and never
    recalculates them afterwards.
    """

    SINGLETON_ID = 1

    cod_handling_fee = models.DecimalField(
        _('COD handling fee'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('49.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_(
            'Added to the total when the shopper chooses Cash on Delivery. '
            'Set 0 to charge nothing for COD.'
        ),
    )
    shipping_fee = models.DecimalField(
        _('shipping fee'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_('Flat delivery charge on orders below the free shipping threshold.'),
    )
    free_shipping_threshold = models.DecimalField(
        _('free shipping above'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('599.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_(
            'Orders with a subtotal above this ship free. The public Shipping '
            'Policy page quotes this figure — update the page to match.'
        ),
    )

    prepaid_discount_enabled = models.BooleanField(
        _('reward prepaid instead of charging COD'),
        default=False,
        help_text=_(
            'On: paying online takes the discount below off the total, and COD '
            'is charged no handling fee. Off: COD pays the handling fee above '
            'and paying online gets nothing. The gap the shopper sees is the '
            'same either way — a discount simply persuades more of them.'
        ),
    )
    prepaid_discount = models.DecimalField(
        _('prepaid discount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_(
            'Taken off the total when the shopper pays online. Ignored while '
            'the switch above is off.'
        ),
    )

    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Pricing Settings')
        verbose_name_plural = _('Pricing Settings')

    def __str__(self):
        return 'Pricing Settings'

    def clean(self):
        if self.prepaid_discount_enabled and self.prepaid_discount <= 0:
            raise ValidationError({
                'prepaid_discount': _(
                    'Set a discount above 0, or switch off "reward prepaid '
                    'instead of charging COD" — as it stands both payment '
                    'options cost the shopper exactly the same.'
                ),
            })
        if self.free_shipping_threshold <= 0 and self.shipping_fee > 0:
            raise ValidationError({
                'free_shipping_threshold': _(
                    'A threshold of 0 ships every order free, which leaves the '
                    'shipping fee above unreachable.'
                ),
            })

    def save(self, *args, **kwargs):
        # Any save is a save of THE row — a second one would be a second set of
        # prices with no rule deciding which of them wins.
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Ignored. The row is the configuration; losing it loses the prices."""
        return 0, {}

    @classmethod
    def load(cls):
        """
        The current pricing, created with the defaults above on first use.

        Read straight from the database every time, deliberately. This is a
        single row fetched by primary key, so caching it saves almost nothing
        while costing a great deal: with a per-process cache an edit would take
        until the entry expired to reach the other workers, a read landing
        between the invalidation and the commit would restore the old figures
        for that long again, and a rolled-back save would leave figures cached
        that were never committed. Uncached, a change in the admin is live on
        the storefront the moment it is saved.
        """
        obj, _created = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return obj


class SMTPSettings(models.Model):
    host = models.CharField(
        _('SMTP Host'),
        max_length=255,
        help_text=_('SMTP server hostname')
    )
    port = models.IntegerField(
        _('SMTP Port'),
        help_text=_('SMTP server port number')
    )
    username = models.CharField(
        _('SMTP Username'),
        max_length=255,
        help_text=_('SMTP authentication username')
    )
    password = models.CharField(
        _('SMTP Password'),
        max_length=255,
        help_text=_('SMTP authentication password')
    )
    from_email = models.EmailField(
        _('From Email'),
        help_text=_('Default sender email address')
    )
    use_tls = models.BooleanField(
        _('Use TLS'),
        default=True,
        help_text=_('Enable TLS encryption for SMTP connection')
    )
    created_at = models.DateTimeField(
        _('Created At'), 
        auto_now_add=True
        )
    updated_at = models.DateTimeField(
        _('Updated At'), 
        auto_now=True
        )

    class Meta:
        verbose_name = _('SMTP Setting')
        verbose_name_plural = _('SMTP Settings')
        ordering = ['-updated_at']

    def __str__(self):
        return f"SMTP Settings - {self.host} ({self.username})"
