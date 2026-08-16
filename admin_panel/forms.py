"""
Panel forms.

:func:`build_resource_form` produces a sensible form for any registered model —
correct input types, consistent styling, no hand-written HTML. Below it sit the
handful of models whose ``save()`` methods carry business logic that a naive
ModelForm would trip over.
"""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.utils.translation import gettext_lazy as _

from api_settings.models import SMTPSettings
from coupon.models import Coupon
from orders.models import Order
from product.models import Product


User = get_user_model()

TEXT_INPUT_CLASS = 'field-input'
SELECT_CLASS = 'field-select'
TEXTAREA_CLASS = 'field-textarea'
CHECKBOX_CLASS = 'field-checkbox'
FILE_CLASS = 'field-file'


class PanelFormMixin:
    """Applies panel styling and native input types to every bound widget.

    Accepts an optional ``panel_request`` so a form can vary by the acting
    user — see :class:`PanelUserForm`, which refuses to show privilege
    escalation controls to non-superusers.
    """

    def __init__(self, *args, panel_request=None, **kwargs):
        self.panel_request = panel_request
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            self._style_field(field)

    @staticmethod
    def _style_field(field):
        widget = field.widget

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault('class', CHECKBOX_CLASS)
            return

        if isinstance(widget, forms.CheckboxSelectMultiple):
            widget.attrs.setdefault('class', 'field-checkbox-list')
            return

        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault('class', SELECT_CLASS)
            return

        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('class', TEXTAREA_CLASS)
            widget.attrs.setdefault('rows', 5)
            return

        if isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
            widget.attrs.setdefault('class', FILE_CLASS)
            return

        # Swap plain text boxes for the matching native control so mobile
        # keyboards and the browser's own pickers do the work.
        if isinstance(widget, forms.DateTimeInput):
            widget.input_type = 'datetime-local'
            widget.format = '%Y-%m-%dT%H:%M'
        elif isinstance(widget, forms.DateInput):
            widget.input_type = 'date'
            widget.format = '%Y-%m-%d'
        elif isinstance(widget, forms.TimeInput):
            widget.input_type = 'time'
        elif isinstance(field, forms.EmailField):
            widget.input_type = 'email'
        elif isinstance(field, forms.URLField):
            widget.input_type = 'url'
        elif isinstance(field, forms.DecimalField):
            widget.input_type = 'number'
            widget.attrs.setdefault('step', '0.01')
        elif isinstance(field, forms.IntegerField):
            widget.input_type = 'number'
            widget.attrs.setdefault('step', '1')

        widget.attrs.setdefault('class', TEXT_INPUT_CLASS)

    def visible_fieldsets(self, fieldsets):
        """Regroup bound fields into ``(title, [fields])`` for the template."""
        if not fieldsets:
            return [(None, list(self))]

        grouped, claimed = [], set()
        for title, names in fieldsets:
            rows = [self[name] for name in names if name in self.fields]
            claimed.update(name for name in names if name in self.fields)
            if rows:
                grouped.append((title, rows))

        leftover = [self[name] for name in self.fields if name not in claimed]
        if leftover:
            grouped.append((None, leftover))
        return grouped


class PanelModelForm(PanelFormMixin, forms.ModelForm):
    """Base class for every generated resource form."""


def build_resource_form(resource):
    """ModelForm for ``resource``, honouring its declared field list."""
    fields = list(resource.form_fields)
    if not fields:
        fields = [
            f.name
            for f in resource.model._meta.fields
            if f.editable and not f.auto_created and f.name not in resource.readonly_fields
        ]
    return modelform_factory(resource.model, form=PanelModelForm, fields=fields)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class PanelLoginForm(PanelFormMixin, AuthenticationForm):
    """Email + password sign-in, restricted to active staff.

    ``ModelBackend`` already rejects inactive accounts; this adds the staff
    requirement so a regular shopper's credentials can never open the panel.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': _('Incorrect email or password.'),
        'not_staff': _('This account does not have access to the admin panel.'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Email address')
        self.fields['username'].widget.attrs.update(
            {'autofocus': True, 'autocomplete': 'email', 'placeholder': 'you@navprana.com'}
        )
        self.fields['username'].widget.input_type = 'email'
        self.fields['password'].widget.attrs.update(
            {'autocomplete': 'current-password', 'placeholder': '••••••••'}
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(self.error_messages['not_staff'], code='not_staff')


class PanelProfileForm(PanelFormMixin, forms.ModelForm):
    """The signed-in admin's own details — no permission fields here."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'country_code', 'phone_number', 'profile_picture')

    def clean_phone_number(self):
        # ``phone_number`` is unique but nullable; '' would collide on a second
        # blank save, so normalise empties back to NULL.
        return self.cleaned_data.get('phone_number') or None


# ---------------------------------------------------------------------------
# Model-specific forms
# ---------------------------------------------------------------------------


class PanelUserForm(PanelFormMixin, forms.ModelForm):
    """Staff/customer editor.

    Password is never exposed here — it has its own dedicated screen. Privilege
    fields are removed outright (not just disabled) for non-superusers, so they
    cannot be granted by crafting a POST body either.
    """

    PRIVILEGE_FIELDS = ('is_staff', 'is_superuser', 'groups')

    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'email', 'country_code', 'phone_number',
            'profile_picture', 'is_active', 'email_verified', 'phone_verified',
            'is_staff', 'is_superuser', 'groups',
        )
        widgets = {'groups': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actor = getattr(self.panel_request, 'user', None)
        if actor is None or not actor.is_superuser:
            for name in self.PRIVILEGE_FIELDS:
                self.fields.pop(name, None)
        if 'groups' in self.fields:
            self.fields['groups'].help_text = _('Roles decide which panel sections this user can open.')

    def clean_phone_number(self):
        return self.cleaned_data.get('phone_number') or None

    def clean(self):
        cleaned = super().clean()
        actor = getattr(self.panel_request, 'user', None)
        # Locking yourself out mid-session is a support ticket, not a feature.
        if actor is not None and self.instance.pk == actor.pk:
            if 'is_active' in self.fields and not cleaned.get('is_active'):
                self.add_error('is_active', _('You cannot deactivate your own account.'))
            if 'is_staff' in self.fields and not cleaned.get('is_staff'):
                self.add_error('is_staff', _('You cannot remove your own staff access.'))
        return cleaned


class PanelProductForm(PanelFormMixin, forms.ModelForm):
    """Product editor that respects ``Product.save()``.

    That method recomputes ``price`` from ``max_price`` and ``discount_precent``
    and raises bare ``ValueError`` on bad input — including ``TypeError`` when
    ``max_price`` is NULL. So ``price`` is not offered for editing, ``max_price``
    is made mandatory, and every rule ``save()`` enforces is checked here first
    where it can surface as a proper field error.
    """

    class Meta:
        model = Product
        fields = (
            'name', 'size', 'category', 'description', 'details',
            'max_price', 'discount_precent', 'max_quantity', 'available_quantity',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['max_price'].required = True
        self.fields['max_price'].help_text = _('MRP. The selling price is derived from this and the discount.')
        self.fields['discount_precent'].help_text = _('0–100. Selling price = MRP − (MRP × discount%).')
        self.fields['name'].required = True

    def clean_discount_precent(self):
        value = self.cleaned_data.get('discount_precent') or Decimal('0')
        if value < 0 or value > 100:
            raise ValidationError(_('Discount must be between 0 and 100.'))
        return value

    def clean_max_price(self):
        value = self.cleaned_data.get('max_price')
        if value is None or value < 0:
            raise ValidationError(_('Enter a valid MRP.'))
        return value

    def clean(self):
        cleaned = super().clean()
        available = cleaned.get('available_quantity')
        maximum = cleaned.get('max_quantity')
        if available is not None and maximum is not None and available > maximum:
            self.add_error(
                'available_quantity',
                _('Available quantity cannot exceed the maximum quantity (%(max)s).') % {'max': maximum},
            )
        return cleaned

    @property
    def derived_price(self):
        """Selling price preview for the form template."""
        mrp = self.initial.get('max_price') or getattr(self.instance, 'max_price', None)
        discount = self.initial.get('discount_precent') or getattr(self.instance, 'discount_precent', None)
        if mrp is None:
            return None
        return round(Decimal(mrp) - (Decimal(mrp) * Decimal(discount or 0) / 100))


class PanelOrderForm(PanelFormMixin, forms.ModelForm):
    """Fulfilment editor.

    Deliberately excludes every money field: ``Order.save()`` recalculates
    ``discount_amount``, ``tax_amount``, ``shipping_fee`` and ``final_amount``
    from the coupon and subtotal on each write, so anything typed into them is
    silently discarded. Editing them would only mislead.
    """

    class Meta:
        model = Order
        fields = ('status', 'payment_status', 'courier', 'awb_number', 'notes')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['awb_number'].widget.attrs['placeholder'] = _('Tracking number on the label')
        self.fields['notes'].widget.attrs['rows'] = 3

    def clean(self):
        cleaned = super().clean()
        courier = cleaned.get('courier')
        awb = (cleaned.get('awb_number') or '').strip()

        if awb and not courier:
            self.add_error('courier', _('Choose the shipping partner for this tracking number.'))
        if courier and not awb:
            self.add_error('awb_number', _('Enter the tracking number for this courier.'))
        if cleaned.get('status') in ('shipped', 'delivered') and not awb:
            self.add_error('awb_number', _('Add courier and tracking details before marking an order shipped.'))
        return cleaned


class PanelCouponForm(PanelFormMixin, forms.ModelForm):
    """Coupon editor. ``coupon_id`` is generated by ``Coupon.save()``."""

    class Meta:
        model = Coupon
        fields = (
            'coupon_code', 'discount_type', 'amount', 'percent',
            'minimum_cart_amount', 'start_date', 'end_date',
            'max_use', 'uses_per_user', 'free_shipping', 'status',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['coupon_code'].help_text = _('Stored in upper case. Must be unique.')
        self.fields['amount'].help_text = _('Set either a fixed amount or a percentage, not both.')

    def clean_coupon_code(self):
        return (self.cleaned_data.get('coupon_code') or '').upper().strip()

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount') or Decimal('0')
        percent = cleaned.get('percent') or Decimal('0')
        free_shipping = cleaned.get('free_shipping')

        if amount > 0 and percent > 0:
            self.add_error('percent', _('Use either a fixed amount or a percentage, not both.'))
        elif amount == 0 and percent == 0 and not free_shipping:
            self.add_error('amount', _('Set an amount, a percentage, or enable free shipping.'))

        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', _('The end date must fall after the start date.'))

        max_use = cleaned.get('max_use')
        if max_use is not None and self.instance.pk and self.instance.used > max_use:
            self.add_error(
                'max_use',
                _('This coupon has already been used %(used)s times.') % {'used': self.instance.used},
            )
        return cleaned


class PanelSMTPSettingsForm(PanelFormMixin, forms.ModelForm):
    """SMTP credentials, with the password write-only.

    The stored password is never sent to the browser. Leaving the box empty on
    an existing record keeps whatever is already saved.
    """

    password = forms.CharField(
        label=_('SMTP password'),
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text=_('Leave blank to keep the current password.'),
    )

    class Meta:
        model = SMTPSettings
        fields = ('host', 'port', 'username', 'password', 'from_email', 'use_tls')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password'].required = True
            self.fields['password'].help_text = ''

    def clean_password(self):
        value = self.cleaned_data.get('password')
        if not value and self.instance.pk:
            return self.instance.password
        return value


class PanelGroupForm(PanelFormMixin, forms.ModelForm):
    """Role editor over Django's own ``auth.Group``.

    Permissions are grouped by app in :meth:`permission_groups` so 196 rows
    stay navigable instead of becoming one endless checkbox column.
    """

    class Meta:
        model = Group
        fields = ('name', 'permissions')
        widgets = {'permissions': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].queryset = (
            Permission.objects.select_related('content_type')
            .order_by('content_type__app_label', 'content_type__model', 'codename')
        )
        self.fields['name'].help_text = _('Role name, e.g. "Fulfilment" or "Content editor".')

    def permission_groups(self):
        """``[(app label, [bound checkbox, ...]), ...]`` for the template.

        Each subwidget's value is a ``ModelChoiceIteratorValue``, which carries
        the ``Permission`` instance we need to read the app label from.
        """
        buckets = {}
        for checkbox in self['permissions']:
            permission = getattr(checkbox.data.get('value'), 'instance', None)
            app_label = permission.content_type.app_label if permission else 'other'
            buckets.setdefault(app_label, []).append(checkbox)
        return sorted(buckets.items())
