"""
Order detail.

Orders are the one model where a generic field dump genuinely is not good
enough: fulfilling one means seeing the line items, the money breakdown, the
shipping address and the payment attempts together on one screen.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import View

from ..audit import log_change
from ..columns import ORDER_STATUS_TONES, PAYMENT_STATUS_TONES, TRANSACTION_STATUS_TONES
from ..metrics import invalidate_alerts
from ..utils import safe_redirect_target
from .crud import ResourceDetailView


class OrderDetailView(ResourceDetailView):
    """Everything needed to fulfil or investigate a single order."""

    def get_queryset(self):
        return (
            self.resource.get_queryset()
            .prefetch_related('items__product', 'transaction_logs')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        items = list(order.items.all())
        context.update(
            {
                'items': items,
                'item_count': sum(item.quantity for item in items),
                'transactions': [
                    {
                        'obj': txn,
                        'tone': TRANSACTION_STATUS_TONES.get(txn.status, 'neutral'),
                    }
                    # Prefetched, so this sorts in Python rather than re-querying.
                    for txn in sorted(
                        order.transaction_logs.all(), key=lambda t: t.created_at, reverse=True
                    )
                ],
                'status_tone': ORDER_STATUS_TONES.get(order.status, 'neutral'),
                'payment_tone': PAYMENT_STATUS_TONES.get(order.payment_status, 'neutral'),
                # Both are what this order was charged, read from its own
                # columns rather than from today's Pricing Settings, so the
                # breakdown always adds up to the total beside it.
                'handling_fee': order.get_handling_fee(),
                'prepaid_discount': order.prepaid_discount,
                'tracking_url': order.tracking_url,
                'courier_label': order.courier_label,
                'status_choices': [
                    (value, label, ORDER_STATUS_TONES.get(value, 'neutral'))
                    for value, label in order.STATUS_CHOICES
                ],
                'quick_status_url': reverse('admin_panel:order_status', args=[order.pk]),
            }
        )
        return context


class OrderStatusUpdateView(View):
    """One-click status change from the order detail page.

    Shipping is not offered here — that transition needs a courier and AWB, so
    it goes through the full edit form where both can be validated.
    """

    BLOCKED_STATUSES = ('shipped',)

    def post(self, request, pk):
        from ..registry import registry

        resource = registry.get('orders')
        user = request.user

        if not (user.is_authenticated and user.is_active and user.is_staff):
            raise PermissionDenied('An admin panel account is required.')
        if not resource.user_can(user, 'change'):
            raise PermissionDenied('You do not have permission to edit orders.')

        order = get_object_or_404(resource.get_queryset(), pk=pk)
        target = request.POST.get('status', '')
        valid = {value for value, _ in order.STATUS_CHOICES} - set(self.BLOCKED_STATUSES)
        back = safe_redirect_target(request, resource.url('detail', order.pk))

        if target not in valid:
            messages.error(request, 'That status change is not available from here.')
            return redirect(back)

        if order.status == target:
            messages.info(request, 'The order is already in that status.')
            return redirect(back)

        previous = order.get_status_display()
        order.status = target
        # Money is settled when the order is created and left alone afterwards,
        # so this save moves the status and nothing else.
        order.save()

        log_change(request.user, order, ['status'])
        invalidate_alerts()
        messages.success(
            request,
            f'Order #{order.pk} moved from {previous} to {order.get_status_display()}.',
        )
        return redirect(back)
