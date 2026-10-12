"""
Customer emails about an order's status.

Status emails are sent from the places where staff deliberately move one order
— the panel's quick status buttons, the panel's order form and Django admin —
and never from ``Order.save()``. Bulk actions and payment webhooks also save
orders, and neither should email a customer about it: bulk moves are
housekeeping, and the payment flow sends its own confirmation and invoice.

Every email gets an :class:`~orders.models.OrderEmailLog` row before it is
queued, which the sending task then marks sent or failed.
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


#: Order status -> (subject, template base name under templates/). Statuses
#: missing here have nothing to tell the customer: ``pending`` is an order
#: still waiting on payment, and a failed payment has its own email.
STATUS_EMAILS = {
    'accepted': ('Order Confirmed - Order #{id}', 'email/order_confirmation'),
    'processing': ('Your Order Is Being Prepared - Order #{id}', 'email/order_processing'),
    'shipped': ('Your Order Shipped - Order #{id}', 'email/order_shipped'),
    'delivered': ('Order Delivered - Order #{id}', 'email/order_delivered'),
    'cancelled': ('Order Cancelled - Order #{id}', 'email/order_cancelled'),
    'returned': ('Return Received - Order #{id}', 'email/order_returned'),
}


def has_status_email(status):
    return status in STATUS_EMAILS


def queue_status_email(order, *, trigger, sent_by=None):
    """Log and queue the email for the order's current status.

    Returns the log row, or ``None`` when there is nothing to send: a status
    with no email, or a customer with no email address (OTP sign-up leaves it
    optional).
    """
    from .models import OrderEmailLog
    from .tasks import send_order_status_email

    if not has_status_email(order.status) or not order.user.email:
        return None

    log = OrderEmailLog.objects.create(
        order=order,
        status=order.status,
        recipient=order.user.email,
        trigger=trigger,
        sent_by=sent_by if getattr(sent_by, 'pk', None) else None,
    )

    def _dispatch():
        try:
            send_order_status_email.delay(log.pk)
        except Exception as exc:
            # The broker being down must not fail the status change that
            # triggered this; record it so staff can see it and retry.
            logger.exception('Could not queue status email %s', log.pk)
            OrderEmailLog.objects.filter(pk=log.pk).update(
                state='failed', error=f'Could not queue the email: {exc}'[:1000],
            )

    transaction.on_commit(_dispatch)
    return log


def notify_status_change(order, previous_status, sent_by=None):
    """Email the customer about a status change, if Order Email Settings allow.

    Call after the order has been saved with its new status. Returns the log
    row when an email was queued, else ``None``.
    """
    from api_settings.models import OrderEmailSettings

    if order.status == previous_status:
        return None
    if not OrderEmailSettings.load().sends_for(order.status):
        return None
    return queue_status_email(order, trigger='auto', sent_by=sent_by)
