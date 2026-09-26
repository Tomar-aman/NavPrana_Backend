"""
Order detail.

Orders are the one model where a generic field dump genuinely is not good
enough: fulfilling one means seeing the line items, the money breakdown, the
shipping address and the payment attempts together on one screen.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import View

from ..audit import log_change
from ..forms import PanelOrderItemFormSet
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
                # The contents and the payment method are only offered while
                # the order is still unpaid and unshipped; see Order.is_editable.
                'can_edit_items': order.is_editable and self.resource.user_can(
                    self.request.user, 'change'
                ),
                'items_formset': PanelOrderItemFormSet(instance=order),
                'items_url': reverse('admin_panel:order_items', args=[order.pk]),
                'payment_method_url': reverse(
                    'admin_panel:order_payment_method', args=[order.pk]
                ),
                'payment_method_choices': order.PAYMENT_METHOD_CHOICES,
            }
        )
        return context


class OrderActionView(View):
    """Shared guards for the inline actions on the order detail page.

    Each of them is a bare POST from a card on that page rather than a full
    form view, so they all need the same three checks and the same
    "where do I send them back to" answer.
    """

    def load_order(self, request, pk):
        """Return ``(order, redirect_target)`` or raise :class:`PermissionDenied`."""
        from ..registry import registry

        resource = registry.get('orders')
        user = request.user

        if not (user.is_authenticated and user.is_active and user.is_staff):
            raise PermissionDenied('An admin panel account is required.')
        if not resource.user_can(user, 'change'):
            raise PermissionDenied('You do not have permission to edit orders.')

        order = get_object_or_404(resource.get_queryset(), pk=pk)
        return order, safe_redirect_target(request, resource.url('detail', order.pk))


class OrderStatusUpdateView(OrderActionView):
    """One-click status change from the order detail page.

    Shipping is not offered here — that transition needs a courier and AWB, so
    it goes through the full edit form where both can be validated.
    """

    BLOCKED_STATUSES = ('shipped',)

    def post(self, request, pk):
        order, back = self.load_order(request, pk)
        target = request.POST.get('status', '')
        valid = {value for value, _ in order.STATUS_CHOICES} - set(self.BLOCKED_STATUSES)

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


class OrderItemsUpdateView(OrderActionView):
    """Change what an unpaid order contains.

    Products can be swapped, quantities corrected and lines removed. Saving
    re-sums the subtotal and re-prices the order, because ``total_amount`` is
    stored rather than derived — without that the summary card would keep
    quoting the figure from checkout.
    """

    def post(self, request, pk):
        order, back = self.load_order(request, pk)

        if not order.is_editable:
            messages.error(
                request,
                'A paid, shipped or closed order cannot have its items changed.',
            )
            return redirect(back)

        formset = PanelOrderItemFormSet(request.POST, instance=order)
        if not formset.is_valid():
            for error in formset.non_form_errors():
                messages.error(request, error)
            for form in formset.forms:
                for field, errors in form.errors.items():
                    label = form.fields[field].label if field in form.fields else field
                    for error in errors:
                        messages.error(request, f'{label}: {error}')
            return redirect(back)

        # An order priced at zero with nothing in it is not a correction, it is
        # a cancellation — and there is a status for that.
        keeps = [
            form for form in formset.forms
            if form.cleaned_data.get('product') and not form.cleaned_data.get('DELETE')
        ]
        if not keeps:
            messages.error(
                request,
                'An order has to keep at least one item. Cancel it instead of emptying it.',
            )
            return redirect(back)

        previous_total = order.final_amount
        with transaction.atomic():
            formset.save()
            order.resync_from_items()

        log_change(request.user, order, ['items', 'total_amount', 'final_amount'])
        invalidate_alerts()
        messages.success(
            request,
            f'Order #{order.pk} items updated. Total is now '
            f'₹{order.final_amount} (was ₹{previous_total}).',
        )
        return redirect(back)


class OrderPaymentMethodUpdateView(OrderActionView):
    """Switch an unpaid order between COD and the prepaid methods.

    The COD handling fee and the prepaid discount both hang off this field, so
    the order is re-priced rather than simply relabelled.
    """

    def post(self, request, pk):
        order, back = self.load_order(request, pk)

        if not order.is_editable:
            messages.error(
                request,
                'A paid, shipped or closed order cannot change payment method.',
            )
            return redirect(back)

        target = request.POST.get('payment_method', '')
        if target not in {value for value, _ in order.PAYMENT_METHOD_CHOICES}:
            messages.error(request, 'That is not a payment method this order can use.')
            return redirect(back)

        if order.payment_method == target:
            messages.info(request, 'The order already uses that payment method.')
            return redirect(back)

        previous_label = order.get_payment_method_display()
        previous_total = order.final_amount

        with transaction.atomic():
            order.payment_method = target
            order.save(update_fields=['payment_method'])
            # reprice() settles the handling fee and the prepaid discount, both
            # of which read payment_method, so it has to run after that save.
            order.reprice()

        log_change(request.user, order, ['payment_method', 'final_amount'])
        invalidate_alerts()
        messages.success(
            request,
            f'Order #{order.pk} moved from {previous_label} to '
            f'{order.get_payment_method_display()}. Total is now '
            f'₹{order.final_amount} (was ₹{previous_total}).',
        )
        return redirect(back)
