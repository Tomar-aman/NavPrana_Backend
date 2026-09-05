"""
Resource registrations.

One entry per model the panel manages. The choices here are deliberate rather
than mechanical: which columns earn a place in a list, what an operator
actually searches by, which fields are safe to edit given what the model's
``save()`` does, and which bulk actions make sense for the business.

Read this file as the answer to "how should each model behave in the admin".
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count

from api_settings.models import PricingSettings, SMTPSettings
from blogs.models import Blog, BlogCategory
from cart.models import Cart
from contact.models import (
    Address as ContactAddress,
    Email as ContactEmail,
    FAQCategory,
    FAQs,
    PhoneNumber,
    SendUsQuery,
    SocialMediaLink,
    Subscriber,
)
from coupon.models import Coupon, CouponUsage, TempCoupon, UserSpinLimit
from lab_report.models import LabReport
from orders.couriers import COURIER_CHOICES
from orders.models import Order
from product.models import Category, Product, ProductReview
from public_data.models import InstagramReel
from transactions.models import TransactionLog
from users.models import OTP, UserAddress

from .actions import (
    activate_records,
    bulk_status_setter,
    deactivate_records,
    delete_expired_otps,
    download_order_invoices,
)
from .columns import (
    Column,
    ORDER_STATUS_TONES,
    PAYMENT_STATUS_TONES,
    TRANSACTION_STATUS_TONES,
)
from .filters import (
    BooleanFilter,
    ChoiceFilter,
    DateRangeFilter,
    ExpiryFilter,
    RelationFilter,
)
from .forms import (
    PanelCouponForm,
    PanelGroupForm,
    PanelOrderForm,
    PanelProductForm,
    PanelSMTPSettingsForm,
    PanelUserForm,
)
from .registry import BulkAction, DetailPanel, PanelResource, registry


User = get_user_model()

#: Tones for the derived OTP state column. A live code is a working credential,
#: so it reads as the notable one; an expired code is inert history.
OTP_STATE_TONES = {'Live': 'success', 'Expired': 'neutral'}


def _distinct_payment_methods():
    """Payment methods actually present in the orders table.

    ``Order.create_order`` writes ``payment_method='cashfree'``, a value absent
    from ``PAYMENT_METHOD_CHOICES``. Building the filter from ``choices`` alone
    would hide the overwhelming majority of real orders, so the list is drawn
    from the data and only labelled from the choices.
    """
    labels = dict(Order.PAYMENT_METHOD_CHOICES)
    values = (
        Order.objects.exclude(payment_method='')
        .values_list('payment_method', flat=True)
        .distinct()
        .order_by('payment_method')
    )
    return [(value, labels.get(value, value.replace('_', ' ').title())) for value in values]


class OrderResource(PanelResource):
    """Orders get a purpose-built detail page: items, money, shipping, payments."""

    detail_template = 'panel/orders/detail.html'

    def base_queryset(self):
        return Order.objects.all()

    def object_title(self, obj):
        return f'Order #{obj.pk}'


class UserResource(PanelResource):
    def object_title(self, obj):
        name = f'{obj.first_name} {obj.last_name}'.strip()
        return name or obj.email or f'User #{obj.pk}'


class OTPResource(PanelResource):
    """Verification codes, listed so support can see what a customer received."""

    def object_title(self, obj):
        # Deliberately not ``str(otp)``, which ends in the code itself: this
        # title becomes the breadcrumb and the audit-log description, and a
        # live code has no business being copied into either.
        email = getattr(obj.user, 'email', '') or f'user #{obj.user_id}'
        return f'OTP #{obj.pk} for {email}'


class PricingSettingsResource(PanelResource):
    """The storefront's fees and thresholds — one row, edited as a page."""

    def base_queryset(self):
        # ``load()`` creates the row with its model defaults the first time
        # anybody opens this section, so a fresh install has something to edit
        # rather than an empty list and a disabled Add button.
        PricingSettings.load()
        return PricingSettings.objects.all()

    def object_title(self, obj):
        return 'Pricing Settings'


# ---------------------------------------------------------------------------
# Commerce
# ---------------------------------------------------------------------------

registry.register(
    OrderResource(
        key='orders',
        model=Order,
        group='Commerce',
        icon='cart',
        label_plural='Orders',
        description='Every order placed through the storefront.',
        # Orders originate from checkout, where the cart, coupon and payment
        # session are created together. Hand-building one here would produce a
        # row no payment gateway knows about, so creation stays disabled.
        can_add=False,
        columns=(
            Column('id', 'Order', kind='text', prefix='#', is_link=True, sort_field='id'),
            Column('user.email', 'Customer', sort_field='user__email', truncate=32),
            Column('status', 'Status', kind='badge', tones=ORDER_STATUS_TONES),
            Column('payment_status', 'Payment', kind='badge', tones=PAYMENT_STATUS_TONES),
            Column('payment_method', 'Method'),
            Column('final_amount', 'Total', kind='currency'),
            Column('courier', 'Courier', accessor=lambda o: o.courier_label, sort_field='courier'),
            Column('awb_number', 'AWB', truncate=18),
            Column('created_at', 'Placed', kind='datetime'),
        ),
        search_fields=(
            'id__exact_int', 'user__email', 'user__first_name', 'user__last_name',
            'awb_number', 'transaction_id',
        ),
        search_hint='Order #, customer, AWB or transaction ID',
        filters=(
            ChoiceFilter('status', 'Status', Order.STATUS_CHOICES),
            ChoiceFilter('payment_status', 'Payment status', Order.PAYMENT_STATUS_CHOICES),
            ChoiceFilter('payment_method', 'Payment method', _distinct_payment_methods),
            ChoiceFilter('courier', 'Courier', COURIER_CHOICES),
            DateRangeFilter('placed', 'Order date', field='created_at'),
        ),
        select_related=('user', 'coupon', 'address'),
        prefetch_related=('items__product',),
        default_ordering='-created_at',
        ordering_fields=('final_amount', 'created_at', 'id', 'status'),
        form_class=PanelOrderForm,
        fieldsets=(
            ('Fulfilment', ('status', 'payment_status')),
            ('Shipping', ('courier', 'awb_number')),
            ('Internal', ('notes',)),
        ),
        bulk_actions=(
            BulkAction('mark_processing', 'Mark as processing', bulk_status_setter('processing'), confirm='Move the selected orders to processing?'),
            BulkAction('mark_delivered', 'Mark as delivered', bulk_status_setter('delivered'), confirm='Mark the selected orders delivered?'),
            BulkAction('mark_cancelled', 'Mark as cancelled', bulk_status_setter('cancelled'), tone='danger', confirm='Cancel the selected orders?'),
            BulkAction('download_invoices', 'Download invoices (single PDF)', download_order_invoices, permission='view'),
        ),
        help_text=(
            'Every total is fixed when the order is placed, from the fees in '
            'System → Pricing Settings. Changing those settings re-prices new '
            'orders only, so the figures here cannot be edited and never move '
            'under a customer who has already been quoted.'
        ),
        empty_message='No orders match these filters.',
    )
)

registry.register(
    PanelResource(
        key='transactions',
        model=TransactionLog,
        group='Commerce',
        icon='credit-card',
        label_plural='Transactions',
        description='Payment gateway records, kept as an immutable audit trail.',
        # A payment log must mirror the gateway exactly; editing it by hand
        # would destroy its value as evidence during a dispute.
        can_add=False,
        can_edit=False,
        columns=(
            Column('transaction_order_id', 'Reference', is_link=True, truncate=28),
            Column('user.email', 'Customer', sort_field='user__email', truncate=28),
            Column('order_id', 'Order', prefix='#', sort_field='order__id'),
            Column('payment_method', 'Method', kind='badge', tones={}),
            Column('amount', 'Amount', kind='currency'),
            Column('status', 'Status', kind='badge', tones=TRANSACTION_STATUS_TONES),
            Column('created_at', 'Created', kind='datetime'),
        ),
        search_fields=(
            'transaction_order_id', 'gateway_payment_id', 'cashfree_order_id',
            'bank_reference', 'user__email', 'order__id__exact_int',
        ),
        search_hint='Reference, gateway ID or customer',
        filters=(
            ChoiceFilter('status', 'Status', TransactionLog.STATUS_CHOICES),
            ChoiceFilter('payment_method', 'Method', TransactionLog.PAYMENT_METHODS),
            DateRangeFilter('created', 'Created', field='created_at'),
        ),
        select_related=('user', 'order'),
        default_ordering='-created_at',
        ordering_fields=('amount', 'created_at', 'status'),
    )
)

registry.register(
    PanelResource(
        key='carts',
        model=Cart,
        group='Commerce',
        icon='basket',
        label_plural='Active Carts',
        description='Items customers have left in their cart.',
        can_add=False,
        can_edit=False,
        columns=(
            Column('user.email', 'Customer', sort_field='user__email', is_link=True),
            Column('product.name', 'Product', sort_field='product__name', truncate=40),
            Column('quantity', 'Qty', kind='number'),
            Column('created_at', 'Added', kind='datetime'),
            Column('updated_at', 'Updated', kind='datetime'),
        ),
        search_fields=('user__email', 'user__first_name', 'product__name'),
        search_hint='Customer or product',
        filters=(DateRangeFilter('added', 'Added', field='created_at'),),
        select_related=('user', 'product'),
        default_ordering='-created_at',
        empty_message='No carts have items right now.',
    )
)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

registry.register(
    PanelResource(
        key='products',
        model=Product,
        group='Catalog',
        icon='box',
        label_plural='Products',
        description='Catalogue, pricing and stock levels.',
        columns=(
            Column('name', 'Product', is_link=True, truncate=44),
            Column('size', 'Size'),
            Column('category.name', 'Category', sort_field='category__name'),
            Column('max_price', 'MRP', kind='currency'),
            Column('discount_precent', 'Discount', kind='number', suffix='%'),
            Column('price', 'Selling price', kind='currency'),
            Column('available_quantity', 'In stock', kind='number'),
            Column('is_active', 'Active', kind='bool'),
        ),
        search_fields=('name', 'description', 'details'),
        search_hint='Product name or description',
        filters=(
            RelationFilter('category', 'Category', lambda: Category.objects.order_by('name'), label_attr='name'),
            ChoiceFilter('size', 'Size', Product.SIZE_CHOICES),
            BooleanFilter('is_active', 'Active', true_label='Active', false_label='Inactive'),
        ),
        select_related=('category',),
        prefetch_related=('images',),
        default_ordering='-created_at',
        ordering_fields=('name', 'price', 'available_quantity', 'created_at'),
        form_class=PanelProductForm,
        fieldsets=(
            ('Product', ('name', 'size', 'category', 'is_active')),
            ('Pricing', ('max_price', 'discount_precent')),
            ('Stock', ('max_quantity', 'available_quantity')),
            ('Copy', ('description', 'details')),
        ),
        bulk_actions=(
            BulkAction('activate', 'Publish', activate_records),
            BulkAction('deactivate', 'Unpublish', deactivate_records, tone='danger'),
        ),
        help_text='The selling price is derived from MRP and discount whenever a product is saved.',
    )
)

registry.register(
    PanelResource(
        key='categories',
        model=Category,
        group='Catalog',
        icon='layers',
        label_plural='Categories',
        columns=(
            Column('name', 'Category', is_link=True),
            Column('description', 'Description', truncate=70, sortable=False),
            Column('product_count', 'Products', kind='number', sortable=False,
                   accessor=lambda obj: getattr(obj, 'product_count', 0)),
            Column('is_active', 'Active', kind='bool'),
            Column('created_at', 'Created', kind='date'),
        ),
        search_fields=('name', 'description'),
        filters=(BooleanFilter('is_active', 'Active'),),
        default_ordering='name',
        form_fields=('name', 'description', 'is_active'),
        bulk_actions=(
            BulkAction('activate', 'Activate', activate_records),
            BulkAction('deactivate', 'Deactivate', deactivate_records, tone='danger'),
        ),
    )
)

registry.register(
    PanelResource(
        key='reviews',
        model=ProductReview,
        group='Catalog',
        icon='star',
        label_plural='Product Reviews',
        description='Customer reviews awaiting moderation or already published.',
        # Reviews belong to customers; staff moderate them rather than write them.
        can_add=False,
        columns=(
            Column('product.name', 'Product', sort_field='product__name', is_link=True, truncate=34),
            Column('user.email', 'Reviewer', sort_field='user__email', truncate=28),
            Column('rating', 'Rating', kind='number', suffix='★'),
            Column('review', 'Review', truncate=64, sortable=False),
            Column('is_active', 'Published', kind='bool'),
            Column('created_at', 'Submitted', kind='date'),
        ),
        search_fields=('product__name', 'user__email', 'review'),
        search_hint='Product, reviewer or review text',
        filters=(
            ChoiceFilter('rating', 'Rating', [(str(n), f'{n} star{"s" if n > 1 else ""}') for n in range(1, 6)]),
            BooleanFilter('is_active', 'Published', true_label='Published', false_label='Hidden'),
            DateRangeFilter('submitted', 'Submitted', field='created_at'),
        ),
        select_related=('product', 'user'),
        default_ordering='-created_at',
        ordering_fields=('rating', 'created_at'),
        form_fields=('rating', 'review', 'is_active'),
        bulk_actions=(
            BulkAction('activate', 'Publish', activate_records),
            BulkAction('deactivate', 'Hide', deactivate_records, tone='danger'),
        ),
    )
)

registry.register(
    PanelResource(
        key='lab-reports',
        model=LabReport,
        group='Catalog',
        icon='flask',
        label_plural='Lab Reports',
        description='Batch test certificates. A QR code is generated on save.',
        columns=(
            Column('batch_number', 'Batch', is_link=True),
            Column('product.name', 'Product', sort_field='product__name', truncate=36),
            Column('report_date', 'Report date', kind='date'),
            Column('report_file', 'File', kind='file', sortable=False),
            Column('qr_code', 'QR', kind='image', sortable=False),
            Column('is_active', 'Active', kind='bool'),
        ),
        search_fields=('batch_number', 'product__name'),
        search_hint='Batch number or product',
        filters=(
            RelationFilter('product', 'Product', lambda: Product.objects.order_by('name'), label_attr='name'),
            DateRangeFilter('report', 'Report date', field='report_date', is_datetime=False),
        ),
        select_related=('product',),
        default_ordering='-report_date',
        form_fields=('product', 'batch_number', 'report_file', 'report_date', 'is_active'),
        help_text='Each product may only have one report per batch number.',
    )
)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

registry.register(
    UserResource(
        key='users',
        model=User,
        group='Customers',
        icon='users',
        label_plural='Users',
        description='Customers and staff accounts.',
        columns=(
            Column('email', 'Email', is_link=True, truncate=34),
            Column('full_name', 'Name', sortable=False,
                   accessor=lambda u: f'{u.first_name} {u.last_name}'.strip()),
            Column('phone_number', 'Phone'),
            Column('is_active', 'Active', kind='bool'),
            Column('is_staff', 'Staff', kind='bool'),
            Column('email_verified', 'Email verified', kind='bool'),
            Column('date_joined', 'Joined', kind='datetime'),
        ),
        search_fields=('email', 'first_name', 'last_name', 'phone_number'),
        search_hint='Email, name or phone',
        filters=(
            BooleanFilter('is_active', 'Account status', true_label='Active', false_label='Inactive'),
            BooleanFilter('is_staff', 'Staff access', true_label='Staff', false_label='Customer'),
            BooleanFilter('email_verified', 'Email verified'),
            BooleanFilter('is_guest', 'Guest checkout', true_label='Guest', false_label='Registered'),
            DateRangeFilter('joined', 'Joined', field='date_joined'),
        ),
        prefetch_related=('groups',),
        default_ordering='-date_joined',
        ordering_fields=('email', 'date_joined', 'last_login'),
        form_class=PanelUserForm,
        fieldsets=(
            ('Identity', ('first_name', 'last_name', 'email', 'country_code', 'phone_number', 'profile_picture')),
            ('Verification', ('email_verified', 'phone_verified')),
            ('Access', ('is_active', 'is_staff', 'is_superuser', 'groups')),
        ),
        bulk_actions=(
            BulkAction('activate', 'Activate accounts', activate_records),
            BulkAction('deactivate', 'Deactivate accounts', deactivate_records, tone='danger'),
        ),
        help_text='Passwords are set from the user detail page and are never displayed.',
    )
)

registry.register(
    PanelResource(
        key='addresses',
        model=UserAddress,
        group='Customers',
        icon='map-pin',
        label_plural='Addresses',
        columns=(
            Column('user.email', 'Customer', sort_field='user__email', is_link=True, truncate=28),
            Column('address_line1', 'Address', truncate=40),
            Column('city', 'City'),
            Column('state', 'State'),
            Column('postal_code', 'PIN'),
            Column('is_default', 'Default', kind='bool'),
            Column('created_at', 'Added', kind='date'),
        ),
        search_fields=('user__email', 'address_line1', 'city', 'state', 'postal_code'),
        search_hint='Customer, city or PIN code',
        filters=(
            BooleanFilter('is_default', 'Default address'),
            BooleanFilter('is_active', 'Active'),
        ),
        select_related=('user',),
        default_ordering='-created_at',
        can_add=False,
        form_fields=(
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'country', 'is_default', 'is_active',
        ),
    )
)

registry.register(
    OTPResource(
        key='otps',
        model=OTP,
        group='Customers',
        icon='key',
        label='OTP',
        label_plural='OTPs',
        description='Verification codes issued to customers, newest first.',
        # Codes are issued by the login and verification flows; one typed in
        # here would not match anything the customer was ever sent, and editing
        # one after the fact only breaks the record of what was.
        can_add=False,
        can_edit=False,
        # No CSV: a spreadsheet of live codes is a file of working credentials,
        # and this page exists to answer "what did this customer get", which is
        # a lookup rather than a download.
        can_export=False,
        columns=(
            Column('user.email', 'Customer', sort_field='user__email', is_link=True, truncate=30),
            Column('otp_code', 'Code', css_class='cell-code'),
            Column('state', 'State', kind='badge', sortable=False,
                   accessor=lambda otp: 'Expired' if otp.is_expired() else 'Live',
                   tones=OTP_STATE_TONES),
            Column('created_at', 'Issued', kind='datetime'),
            Column('expires_at', 'Expires', kind='datetime'),
        ),
        search_fields=(
            'otp_code', 'user__email', 'user__first_name', 'user__last_name',
            'user__phone_number',
        ),
        search_hint='Customer email, phone or the code itself',
        filters=(
            ExpiryFilter('state', 'State', field='expires_at'),
            DateRangeFilter('issued', 'Issued', field='created_at'),
        ),
        select_related=('user',),
        default_ordering='-created_at',
        ordering_fields=('created_at', 'expires_at'),
        per_page=50,
        bulk_actions=(
            BulkAction(
                'purge_expired', 'Delete expired codes', delete_expired_otps,
                permission='delete', tone='danger',
                confirm='Delete the expired codes among the selected rows?',
            ),
        ),
        help_text=(
            'A code shown here is the one the customer was sent, so anybody who '
            'can open this page can complete that customer’s login. Grant the '
            '"Can view OTP" permission only to the people who handle support.'
        ),
        empty_message='No codes have been issued yet.',
    )
)

registry.register(
    PanelResource(
        key='subscribers',
        model=Subscriber,
        group='Customers',
        icon='mail',
        label_plural='Newsletter Subscribers',
        columns=(
            Column('email', 'Email', is_link=True),
            Column('is_active', 'Subscribed', kind='bool'),
            Column('created_at', 'Joined', kind='datetime'),
        ),
        search_fields=('email',),
        filters=(
            BooleanFilter('is_active', 'Subscribed'),
            DateRangeFilter('joined', 'Joined', field='created_at'),
        ),
        default_ordering='-created_at',
        form_fields=('email', 'is_active'),
    )
)


# ---------------------------------------------------------------------------
# Marketing
# ---------------------------------------------------------------------------

registry.register(
    PanelResource(
        key='coupons',
        model=Coupon,
        group='Marketing',
        icon='ticket',
        label_plural='Coupons',
        description='Discount codes, their limits and how often they have been redeemed.',
        columns=(
            Column('coupon_code', 'Code', is_link=True),
            Column('discount_type', 'Type', kind='badge',
                   tones={'amount': 'info', 'percent': 'purple', 'shipping': 'success'}),
            Column('amount', 'Amount', kind='currency'),
            Column('percent', 'Percent', kind='number', suffix='%'),
            Column('minimum_cart_amount', 'Min. cart', kind='currency'),
            Column('usage', 'Used', sortable=False,
                   accessor=lambda c: f'{c.used} / {c.max_use}'),
            Column('end_date', 'Expires', kind='date'),
            Column('status', 'Active', kind='bool'),
        ),
        search_fields=('coupon_code', 'coupon_id'),
        search_hint='Coupon code or ID',
        filters=(
            BooleanFilter('status', 'Status', true_label='Active', false_label='Inactive'),
            ChoiceFilter('discount_type', 'Discount type', Coupon.DISCOUNT_TYPE_CHOICES),
            BooleanFilter('free_shipping', 'Free shipping'),
            DateRangeFilter('expiry', 'Expires', field='end_date', is_datetime=False),
        ),
        default_ordering='-created_at',
        ordering_fields=('coupon_code', 'end_date', 'used', 'created_at'),
        form_class=PanelCouponForm,
        fieldsets=(
            ('Code', ('coupon_code', 'discount_type', 'status')),
            ('Discount', ('amount', 'percent', 'free_shipping', 'minimum_cart_amount')),
            ('Validity', ('start_date', 'end_date')),
            ('Limits', ('max_use', 'uses_per_user')),
        ),
        help_text='The coupon ID is generated automatically the first time a coupon is saved.',
    )
)

registry.register(
    PanelResource(
        key='coupon-usage',
        model=CouponUsage,
        group='Marketing',
        icon='history',
        label_plural='Coupon Redemptions',
        can_add=False,
        can_edit=False,
        columns=(
            Column('coupon.coupon_code', 'Coupon', sort_field='coupon__coupon_code', is_link=True),
            Column('user.email', 'Customer', sort_field='user__email', truncate=32),
            Column('used_count', 'Times used', kind='number'),
            Column('first_used_at', 'First used', kind='datetime'),
            Column('last_used_at', 'Last used', kind='datetime'),
        ),
        search_fields=('coupon__coupon_code', 'user__email'),
        search_hint='Coupon code or customer',
        filters=(DateRangeFilter('used', 'Last used', field='last_used_at'),),
        select_related=('coupon', 'user'),
        default_ordering='-last_used_at',
    )
)

registry.register(
    PanelResource(
        key='temp-coupons',
        model=TempCoupon,
        group='Marketing',
        icon='refresh',
        label_plural='Spin-Wheel Coupons',
        description='One-off codes issued by the spin wheel.',
        can_add=False,
        can_edit=False,
        columns=(
            Column('coupon_code', 'Code', is_link=True),
            Column('user.email', 'Customer', sort_field='user__email', truncate=30),
            Column('discount_type', 'Type'),
            Column('amount', 'Amount', kind='currency'),
            Column('percent', 'Percent', kind='number', suffix='%'),
            Column('is_used', 'Redeemed', kind='bool'),
            Column('created_at', 'Issued', kind='datetime'),
        ),
        search_fields=('coupon_code', 'user__email'),
        filters=(
            BooleanFilter('is_used', 'Redeemed'),
            BooleanFilter('free_shipping', 'Free shipping'),
            DateRangeFilter('issued', 'Issued', field='created_at'),
        ),
        select_related=('user',),
        default_ordering='-created_at',
    )
)

registry.register(
    PanelResource(
        key='spin-limits',
        model=UserSpinLimit,
        group='Marketing',
        icon='refresh',
        label_plural='Spin Limits',
        description='Daily spin allowance per customer.',
        can_add=False,
        columns=(
            Column('user.email', 'Customer', sort_field='user__email', is_link=True),
            Column('spin_count', 'Spins', kind='number'),
            Column('last_spin_date', 'Last spin', kind='date'),
            Column('allowed_by_admin', 'Extra spin granted', kind='bool'),
        ),
        search_fields=('user__email',),
        filters=(BooleanFilter('allowed_by_admin', 'Extra spin granted'),),
        select_related=('user',),
        default_ordering='-last_spin_date',
        form_fields=('spin_count', 'allowed_by_admin'),
        help_text='Enable "extra spin" to let a customer spin again on the same day.',
    )
)


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

registry.register(
    PanelResource(
        key='blogs',
        model=Blog,
        group='Content',
        icon='book',
        label_plural='Blog Posts',
        columns=(
            Column('thumbnail', 'Cover', kind='image', sortable=False),
            Column('title', 'Title', is_link=True, truncate=46),
            Column('category.name', 'Category', sort_field='category__name'),
            Column('read_time', 'Read time'),
            Column('is_featured', 'Featured', kind='bool'),
            Column('is_active', 'Published', kind='bool'),
            Column('created_at', 'Created', kind='date'),
        ),
        search_fields=('title', 'excerpt', 'content', 'meta_title'),
        search_hint='Title or content',
        filters=(
            RelationFilter('category', 'Category', lambda: BlogCategory.objects.order_by('name'), label_attr='name'),
            BooleanFilter('is_featured', 'Featured'),
            BooleanFilter('is_active', 'Published'),
            DateRangeFilter('created', 'Created', field='created_at'),
        ),
        select_related=('category',),
        default_ordering='-created_at',
        ordering_fields=('title', 'created_at'),
        form_fields=(
            'title', 'slug', 'category', 'excerpt', 'content', 'thumbnail',
            'read_time', 'is_featured', 'is_active', 'meta_title', 'meta_description',
        ),
        fieldsets=(
            ('Post', ('title', 'slug', 'category', 'thumbnail', 'read_time')),
            ('Content', ('excerpt', 'content')),
            ('SEO', ('meta_title', 'meta_description')),
            ('Visibility', ('is_featured', 'is_active')),
        ),
        bulk_actions=(
            BulkAction('activate', 'Publish', activate_records),
            BulkAction('deactivate', 'Unpublish', deactivate_records, tone='danger'),
        ),
        help_text='Leave the slug blank to generate it from the title.',
    )
)

registry.register(
    PanelResource(
        key='blog-categories',
        model=BlogCategory,
        group='Content',
        icon='layers',
        label_plural='Blog Categories',
        columns=(
            Column('name', 'Category', is_link=True),
            Column('slug', 'Slug'),
            Column('is_active', 'Active', kind='bool'),
            Column('created_at', 'Created', kind='date'),
        ),
        search_fields=('name', 'slug'),
        filters=(BooleanFilter('is_active', 'Active'),),
        default_ordering='name',
        form_fields=('name', 'slug', 'is_active'),
        help_text='Leave the slug blank to generate it from the name.',
    )
)

registry.register(
    PanelResource(
        key='faqs',
        model=FAQs,
        group='Content',
        icon='help-circle',
        label_plural='FAQs',
        columns=(
            Column('question', 'Question', is_link=True, truncate=64),
            Column('category.name', 'Category', sort_field='category__name'),
            Column('order', 'Order', kind='number'),
            Column('is_active', 'Published', kind='bool'),
        ),
        search_fields=('question', 'answer'),
        search_hint='Question or answer text',
        filters=(
            RelationFilter('category', 'Category', lambda: FAQCategory.objects.order_by('order', 'name'), label_attr='name'),
            BooleanFilter('is_active', 'Published'),
        ),
        select_related=('category',),
        default_ordering='order',
        ordering_fields=('order', 'created_at'),
        form_fields=('category', 'question', 'answer', 'order', 'is_active'),
        bulk_actions=(
            BulkAction('activate', 'Publish', activate_records),
            BulkAction('deactivate', 'Unpublish', deactivate_records, tone='danger'),
        ),
    )
)

registry.register(
    PanelResource(
        key='faq-categories',
        model=FAQCategory,
        group='Content',
        icon='layers',
        label_plural='FAQ Categories',
        columns=(
            Column('name', 'Category', is_link=True),
            Column('slug', 'Slug'),
            Column('order', 'Order', kind='number'),
            Column('is_active', 'Active', kind='bool'),
        ),
        search_fields=('name', 'slug'),
        filters=(BooleanFilter('is_active', 'Active'),),
        default_ordering='order',
        form_fields=('name', 'slug', 'order', 'is_active'),
    )
)

registry.register(
    PanelResource(
        key='reels',
        model=InstagramReel,
        group='Content',
        icon='image',
        label_plural='Instagram Reels',
        columns=(
            Column('thumbnail', 'Thumbnail', kind='image', sortable=False),
            Column('caption', 'Caption', is_link=True, truncate=54),
            Column('instagram_url', 'URL', truncate=40),
            Column('sort_order', 'Order', kind='number'),
            Column('is_active', 'Visible', kind='bool'),
        ),
        search_fields=('caption', 'instagram_url'),
        filters=(BooleanFilter('is_active', 'Visible'),),
        default_ordering='sort_order',
        ordering_fields=('sort_order', 'created_at'),
        form_fields=('instagram_url', 'thumbnail', 'caption', 'sort_order', 'is_active'),
        bulk_actions=(
            BulkAction('activate', 'Show', activate_records),
            BulkAction('deactivate', 'Hide', deactivate_records, tone='danger'),
        ),
    )
)

registry.register(
    PanelResource(
        key='social-links',
        model=SocialMediaLink,
        group='Content',
        icon='link',
        label_plural='Social Links',
        columns=(
            Column('platform_name', 'Platform', kind='badge', is_link=True,
                   tones={'facebook': 'info', 'instagram': 'purple', 'youtube': 'danger',
                          'twitter': 'info', 'linkedin': 'info'}),
            Column('url', 'URL', truncate=52),
            Column('is_active', 'Active', kind='bool'),
        ),
        search_fields=('platform_name', 'url'),
        filters=(
            ChoiceFilter('platform_name', 'Platform', SocialMediaLink.PLATEFORM_CHOICES),
            BooleanFilter('is_active', 'Active'),
        ),
        default_ordering='platform_name',
        form_fields=('platform_name', 'url', 'is_active'),
    )
)


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------

registry.register(
    PanelResource(
        key='queries',
        model=SendUsQuery,
        group='Support',
        icon='inbox',
        label_plural='Contact Queries',
        description='Messages submitted through the website contact form.',
        # Submissions are a record of what a customer actually sent; editing
        # one would falsify it, so they are read-only.
        can_add=False,
        can_edit=False,
        columns=(
            Column('name', 'From', sortable=False, is_link=True,
                   accessor=lambda q: f'{q.first_name} {q.last_name}'.strip() or q.email),
            Column('email', 'Email', truncate=30),
            Column('phone_number', 'Phone'),
            Column('subject', 'Subject', truncate=40),
            Column('message', 'Message', truncate=60, sortable=False),
            Column('created_at', 'Received', kind='datetime'),
        ),
        search_fields=('first_name', 'last_name', 'email', 'subject', 'message', 'phone_number'),
        search_hint='Name, email or subject',
        filters=(DateRangeFilter('received', 'Received', field='created_at'),),
        default_ordering='-created_at',
        empty_message='No contact queries yet.',
    )
)

registry.register(
    PanelResource(
        key='contact-phones',
        model=PhoneNumber,
        group='Support',
        icon='phone',
        label_plural='Contact Numbers',
        description='Phone numbers published on the website.',
        columns=(
            Column('phone_number', 'Phone number', is_link=True),
            Column('is_active', 'Published', kind='bool'),
            Column('created_at', 'Added', kind='date'),
        ),
        search_fields=('phone_number',),
        filters=(BooleanFilter('is_active', 'Published'),),
        default_ordering='-created_at',
        form_fields=('phone_number', 'is_active'),
    )
)

registry.register(
    PanelResource(
        key='contact-emails',
        model=ContactEmail,
        group='Support',
        icon='mail',
        label_plural='Contact Emails',
        description='Email addresses published on the website.',
        columns=(
            Column('email', 'Email', is_link=True),
            Column('is_active', 'Published', kind='bool'),
            Column('created_at', 'Added', kind='date'),
        ),
        search_fields=('email',),
        filters=(BooleanFilter('is_active', 'Published'),),
        default_ordering='-created_at',
        form_fields=('email', 'is_active'),
    )
)

registry.register(
    PanelResource(
        key='contact-addresses',
        model=ContactAddress,
        group='Support',
        icon='map-pin',
        label_plural='Office Addresses',
        columns=(
            Column('address_line1', 'Address', is_link=True, truncate=44),
            Column('city', 'City'),
            Column('state', 'State'),
            Column('postal_code', 'PIN'),
            Column('country', 'Country'),
            Column('is_active', 'Published', kind='bool'),
        ),
        search_fields=('address_line1', 'city', 'state', 'postal_code', 'country'),
        filters=(BooleanFilter('is_active', 'Published'),),
        default_ordering='-created_at',
        form_fields=(
            'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country', 'is_active',
        ),
    )
)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

registry.register(
    PanelResource(
        key='roles',
        model=Group,
        group='System',
        icon='shield',
        label_plural='Roles',
        label='Role',
        description='Permission bundles. Assign a role to a user to grant panel access.',
        columns=(
            Column('name', 'Role', is_link=True),
            Column('permission_count', 'Permissions', kind='number', sortable=False,
                   accessor=lambda g: getattr(g, 'permission_count', 0)),
            Column('member_count', 'Members', kind='number', sortable=False,
                   accessor=lambda g: getattr(g, 'member_count', 0)),
        ),
        search_fields=('name',),
        default_ordering='name',
        form_class=PanelGroupForm,
        form_template='panel/crud/form_role.html',
        help_text='Roles reuse Django permissions, so they apply to both this panel and /admin/.',
        empty_message='No roles defined yet. Create one to delegate access without granting superuser.',
    )
)

registry.register(
    PricingSettingsResource(
        key='pricing',
        model=PricingSettings,
        group='System',
        icon='rupee',
        label='Pricing settings',
        label_plural='Pricing Settings',
        description='COD handling, delivery charges and the prepaid discount.',
        # One row, created on demand: adding a second set of prices would leave
        # nothing to decide which of them the storefront should quote.
        can_add=False,
        can_delete=False,
        can_export=False,
        columns=(
            Column('cod_handling_fee', 'COD handling', kind='currency', is_link=True),
            Column('shipping_fee', 'Shipping', kind='currency'),
            Column('free_shipping_threshold', 'Free above', kind='currency'),
            Column('prepaid_discount_enabled', 'Prepaid reward', kind='bool'),
            Column('prepaid_discount', 'Prepaid discount', kind='currency'),
            Column('updated_at', 'Updated', kind='datetime'),
        ),
        default_ordering='pk',
        form_fields=(
            'cod_handling_fee', 'shipping_fee', 'free_shipping_threshold',
            'prepaid_discount_enabled', 'prepaid_discount',
        ),
        fieldsets=(
            ('Cash on delivery', ('cod_handling_fee',)),
            ('Delivery', ('shipping_fee', 'free_shipping_threshold')),
            ('Encourage online payment', ('prepaid_discount_enabled', 'prepaid_discount')),
        ),
        detail_panels=(
            DetailPanel(
                title='Cash on delivery',
                columns=(Column('cod_handling_fee', 'COD handling fee', kind='currency', sortable=False),),
            ),
            DetailPanel(
                title='Delivery',
                columns=(
                    Column('shipping_fee', 'Shipping fee', kind='currency', sortable=False),
                    Column('free_shipping_threshold', 'Free shipping above', kind='currency', sortable=False),
                ),
            ),
            DetailPanel(
                title='Encourage online payment',
                columns=(
                    Column('prepaid_discount_enabled', 'Reward prepaid instead of charging COD', kind='bool', sortable=False),
                    Column('prepaid_discount', 'Prepaid discount', kind='currency', sortable=False),
                    Column('updated_at', 'Last updated', kind='datetime', sortable=False),
                ),
            ),
        ),
        help_text=(
            'These figures are quoted at checkout and charged by the order. '
            'A change applies to orders placed from now on — orders already '
            'placed keep what their customer was quoted. The Shipping Policy '
            'page states the free-delivery threshold in words, so update that '
            'page too when you change it here.'
        ),
    )
)

registry.register(
    PanelResource(
        key='email-settings',
        model=SMTPSettings,
        group='System',
        icon='settings',
        label_plural='Email Settings',
        label='SMTP configuration',
        description='Outgoing mail server used for customer emails.',
        columns=(
            Column('host', 'Host', is_link=True),
            Column('port', 'Port', kind='number'),
            Column('username', 'Username', truncate=28),
            Column('from_email', 'From address'),
            Column('use_tls', 'TLS', kind='bool'),
            Column('updated_at', 'Updated', kind='datetime'),
        ),
        search_fields=('host', 'username', 'from_email'),
        default_ordering='-updated_at',
        form_class=PanelSMTPSettingsForm,
        can_export=False,
        help_text=(
            'The most recently updated record is the one the application uses. '
            'Passwords are stored but never displayed.'
        ),
    )
)


# Resources whose list pages benefit from a count annotation. Kept here rather
# than in each config so the annotation and the column stay in one place.
COUNT_ANNOTATIONS = {
    'categories': {'product_count': Count('products', distinct=True)},
    'roles': {
        'permission_count': Count('permissions', distinct=True),
        'member_count': Count('user', distinct=True),
    },
}


def annotate_queryset(resource, queryset):
    """Apply the resource's count annotations, if it declares any."""
    annotations = COUNT_ANNOTATIONS.get(resource.key)
    return queryset.annotate(**annotations) if annotations else queryset
