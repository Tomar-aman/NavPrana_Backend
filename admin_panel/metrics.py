"""
Dashboard query logic.

Everything the dashboard shows is computed here from the live database — no
placeholder numbers. Views call these functions and pass the results straight
to the template, so no aggregation logic leaks into presentation.

Query budget: each function below is one aggregate or one grouped query, and
the row lists use ``select_related``, so a dashboard render stays flat rather
than growing with the number of orders.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from contact.models import SendUsQuery
from coupon.models import Coupon
from orders.models import Order, OrderItem
from product.models import Product


User = get_user_model()

ZERO = Decimal('0.00')
MONEY = DecimalField(max_digits=14, decimal_places=2)

#: Orders that have been paid for but not yet handed to a courier.
OPEN_FULFILMENT_STATUSES = ('pending', 'accepted', 'processing')

#: A product is "low stock" once this share of its maximum is left.
LOW_STOCK_RATIO = Decimal('0.2')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_start(moment):
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _previous_month_start(month_start):
    return _month_start(month_start - timedelta(days=1))


def _percent_change(current, previous):
    """Signed percentage change, or ``None`` when there is no baseline."""
    current = Decimal(current or 0)
    previous = Decimal(previous or 0)
    if previous == 0:
        return None
    return float(((current - previous) / previous) * 100)


def _paid_orders():
    return Order.objects.filter(payment_status='paid')


# ---------------------------------------------------------------------------
# Headline figures
# ---------------------------------------------------------------------------


def get_kpis():
    """The metric cards along the top of the dashboard."""
    now = timezone.now()
    this_month = _month_start(now)
    last_month = _previous_month_start(this_month)
    thirty_days_ago = now - timedelta(days=30)

    paid = _paid_orders()

    revenue = paid.aggregate(
        total=Coalesce(Sum('final_amount'), Value(ZERO), output_field=MONEY),
        current=Coalesce(
            Sum('final_amount', filter=Q(created_at__gte=this_month)), Value(ZERO), output_field=MONEY
        ),
        previous=Coalesce(
            Sum('final_amount', filter=Q(created_at__gte=last_month, created_at__lt=this_month)),
            Value(ZERO),
            output_field=MONEY,
        ),
        average=Coalesce(Avg('final_amount'), Value(ZERO), output_field=MONEY),
    )

    orders = Order.objects.aggregate(
        total=Count('id'),
        current=Count('id', filter=Q(created_at__gte=this_month)),
        previous=Count('id', filter=Q(created_at__gte=last_month, created_at__lt=this_month)),
        awaiting=Count('id', filter=Q(payment_status='paid', status__in=OPEN_FULFILMENT_STATUSES)),
        failed_payments=Count('id', filter=Q(payment_status='failed', created_at__gte=thirty_days_ago)),
    )

    customers = User.objects.filter(is_staff=False).aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        current=Count('id', filter=Q(date_joined__gte=this_month)),
        previous=Count('id', filter=Q(date_joined__gte=last_month, date_joined__lt=this_month)),
    )

    return [
        {
            'key': 'revenue',
            'label': 'Paid revenue',
            'value': revenue['total'],
            'format': 'currency',
            'sub': f"{_format_money(revenue['current'])} this month",
            'delta': _percent_change(revenue['current'], revenue['previous']),
            'icon': 'rupee',
            'tone': 'primary',
        },
        {
            'key': 'orders',
            'label': 'Orders',
            'value': orders['total'],
            'format': 'number',
            'sub': f"{orders['current']} this month",
            'delta': _percent_change(orders['current'], orders['previous']),
            'icon': 'cart',
            'tone': 'info',
        },
        {
            'key': 'awaiting',
            'label': 'Awaiting fulfilment',
            'value': orders['awaiting'],
            'format': 'number',
            'sub': 'Paid, not yet shipped',
            'delta': None,
            'icon': 'truck',
            'tone': 'warning',
        },
        {
            'key': 'customers',
            'label': 'Customers',
            'value': customers['total'],
            'format': 'number',
            'sub': f"{customers['active']} active · {customers['current']} new this month",
            'delta': _percent_change(customers['current'], customers['previous']),
            'icon': 'users',
            'tone': 'success',
        },
        {
            'key': 'aov',
            'label': 'Average order value',
            'value': revenue['average'],
            'format': 'currency',
            'sub': 'Across all paid orders',
            'delta': None,
            'icon': 'chart',
            'tone': 'purple',
        },
        {
            'key': 'failed',
            'label': 'Failed payments',
            'value': orders['failed_payments'],
            'format': 'number',
            'sub': 'Last 30 days',
            'delta': None,
            'icon': 'alert',
            'tone': 'danger',
        },
    ]


def _format_money(value):
    from .columns import format_currency

    return format_currency(value or ZERO)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def get_revenue_series(months: int = 12):
    """Paid revenue and order count per calendar month, oldest first.

    Months with no orders are emitted as zeros so the x-axis stays evenly
    spaced instead of skipping gaps.
    """
    now = timezone.now()
    start = _month_start(now)
    for _ in range(months - 1):
        start = _previous_month_start(start)

    rows = (
        _paid_orders()
        .filter(created_at__gte=start)
        .annotate(bucket=TruncMonth('created_at'))
        .values('bucket')
        .annotate(
            revenue=Coalesce(Sum('final_amount'), Value(ZERO), output_field=MONEY),
            orders=Count('id'),
        )
        .order_by('bucket')
    )
    found = {row['bucket'].date().replace(day=1): row for row in rows if row['bucket']}

    series, cursor = [], start
    for _ in range(months):
        key = cursor.date().replace(day=1)
        row = found.get(key)
        series.append(
            {
                'label': cursor.strftime('%b'),
                'full_label': cursor.strftime('%B %Y'),
                'revenue': float(row['revenue']) if row else 0.0,
                'orders': row['orders'] if row else 0,
            }
        )
        cursor = _month_start(cursor + timedelta(days=32))
    return series


def get_new_customers_series(months: int = 12):
    """Customer sign-ups per month, oldest first."""
    now = timezone.now()
    start = _month_start(now)
    for _ in range(months - 1):
        start = _previous_month_start(start)

    rows = (
        User.objects.filter(is_staff=False, date_joined__gte=start)
        .annotate(bucket=TruncMonth('date_joined'))
        .values('bucket')
        .annotate(total=Count('id'))
        .order_by('bucket')
    )
    found = {row['bucket'].date().replace(day=1): row['total'] for row in rows if row['bucket']}

    series, cursor = [], start
    for _ in range(months):
        key = cursor.date().replace(day=1)
        series.append(
            {
                'label': cursor.strftime('%b'),
                'full_label': cursor.strftime('%B %Y'),
                'value': found.get(key, 0),
            }
        )
        cursor = _month_start(cursor + timedelta(days=32))
    return series


def get_status_distribution():
    """Order counts by status, using the model's own display labels."""
    from .columns import ORDER_STATUS_TONES

    labels = dict(Order.STATUS_CHOICES)
    rows = Order.objects.values('status').annotate(total=Count('id')).order_by('-total')
    return [
        {
            'key': row['status'],
            'label': labels.get(row['status'], row['status'].title()),
            'value': row['total'],
            'tone': ORDER_STATUS_TONES.get(row['status'], 'neutral'),
        }
        for row in rows
    ]


def get_payment_method_split():
    """Orders by payment method.

    Labels come from the database value first and only fall back to the model's
    ``choices``: most rows carry ``payment_method='cashfree'``, which
    ``Order.create_order`` writes but ``PAYMENT_METHOD_CHOICES`` never declared.
    """
    labels = dict(Order.PAYMENT_METHOD_CHOICES)
    rows = Order.objects.values('payment_method').annotate(total=Count('id')).order_by('-total')
    return [
        {
            'key': row['payment_method'],
            'label': labels.get(row['payment_method'], (row['payment_method'] or 'Unknown').replace('_', ' ').title()),
            'value': row['total'],
        }
        for row in rows
    ]


def get_top_products(limit: int = 5):
    """Best sellers by units shipped against paid orders."""
    rows = (
        OrderItem.objects.filter(order__payment_status='paid')
        .values('product__name', 'product__size')
        .annotate(
            units=Coalesce(Sum('quantity'), 0),
            revenue=Coalesce(Sum('total_price'), Value(ZERO), output_field=MONEY),
        )
        .order_by('-units')[:limit]
    )
    return [
        {
            'label': row['product__name'] or 'Unnamed product',
            'sub': row['product__size'] or '',
            'value': row['units'],
            'revenue': row['revenue'],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Row lists
# ---------------------------------------------------------------------------


def get_recent_orders(limit: int = 8):
    return list(
        Order.objects.select_related('user').order_by('-created_at')[:limit]
    )


def get_recent_activity(limit: int = 8):
    return list(
        LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:limit]
    )


def get_low_stock_products(limit: int = 5):
    """Active products down to their last :data:`LOW_STOCK_RATIO` of stock."""
    return list(
        Product.objects.filter(is_active=True, max_quantity__gt=0)
        .annotate(threshold=F('max_quantity') * LOW_STOCK_RATIO)
        .filter(available_quantity__lte=F('threshold'))
        .order_by('available_quantity')[:limit]
    )


# ---------------------------------------------------------------------------
# Header alerts
# ---------------------------------------------------------------------------

ALERT_CACHE_KEY = 'panel:alerts:v2'
ALERT_CACHE_SECONDS = 60


def get_alerts(user=None, force: bool = False):
    """Actionable counts for the header bell.

    These are real operational signals — orders waiting, unanswered queries,
    stock running out, payments failing — not a notification feed.

    The counts are cached for a minute (the header renders on every page) and
    then filtered per user: an operator who cannot view orders must not learn
    how many are pending, nor be shown a link that will 403.
    """
    return _filter_alerts(_compute_alerts(force), user)


def _filter_alerts(items, user):
    from .registry import registry

    visible = []
    for item in items:
        resource = registry.get(item['resource'])
        if resource is None:
            continue
        if user is not None and not resource.user_can(user, 'view'):
            continue
        if item['count']:
            visible.append(item)
    return {'items': visible, 'total': sum(item['count'] for item in visible)}


def _compute_alerts(force: bool = False):
    """Raw, user-independent alert counts. Cached; filter before display."""
    if not force:
        cached = cache.get(ALERT_CACHE_KEY)
        if cached is not None:
            return cached

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    order_counts = Order.objects.aggregate(
        awaiting=Count('id', filter=Q(payment_status='paid', status__in=OPEN_FULFILMENT_STATUSES)),
        failed=Count('id', filter=Q(payment_status='failed', created_at__gte=week_ago)),
    )
    new_queries = SendUsQuery.objects.filter(created_at__gte=week_ago).count()
    low_stock = (
        Product.objects.filter(is_active=True, max_quantity__gt=0)
        .annotate(threshold=F('max_quantity') * LOW_STOCK_RATIO)
        .filter(available_quantity__lte=F('threshold'))
        .count()
    )
    expiring_coupons = Coupon.objects.filter(
        status=True, end_date__isnull=False, end_date__gte=now.date(), end_date__lte=(now + timedelta(days=7)).date()
    ).count()

    items = [
        {
            'label': 'orders awaiting fulfilment',
            'count': order_counts['awaiting'],
            'tone': 'warning',
            'resource': 'orders',
            'query': '?payment_status=paid&status=pending',
        },
        {
            'label': 'failed payments this week',
            'count': order_counts['failed'],
            'tone': 'danger',
            'resource': 'orders',
            'query': '?payment_status=failed',
        },
        {
            'label': 'new contact queries this week',
            'count': new_queries,
            'tone': 'info',
            'resource': 'queries',
            'query': '',
        },
        {
            'label': 'products low on stock',
            'count': low_stock,
            'tone': 'warning',
            'resource': 'products',
            'query': '?sort=available_quantity',
        },
        {
            'label': 'coupons expiring within 7 days',
            'count': expiring_coupons,
            'tone': 'info',
            'resource': 'coupons',
            'query': '?status=yes',
        },
    ]
    cache.set(ALERT_CACHE_KEY, items, ALERT_CACHE_SECONDS)
    return items


def invalidate_alerts():
    """Drop the cached header counts after a write that could change them."""
    cache.delete(ALERT_CACHE_KEY)
