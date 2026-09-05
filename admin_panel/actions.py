"""
Bulk actions.

Each handler takes ``(request, queryset)`` and returns either a message to show
the operator or an :class:`~django.http.HttpResponse` to send instead of a
redirect (used by the invoice download).

Handlers save row by row rather than calling ``queryset.update()`` on purpose:
several models in this project put real logic in ``save()`` — ``Product``
recomputes its selling price, ``Order`` normalises its AWB — and a bulk UPDATE
would skip all of it. Selections are bounded by the page size, so the
extra queries are a fair trade for correct data and a complete audit trail.
"""

import logging

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from .audit import log_change, log_deletion


logger = logging.getLogger(__name__)


def _apply_field(request, queryset, field, value, verb):
    """Set ``field`` to ``value`` on each row, logging every success."""
    changed, skipped = 0, 0
    for obj in queryset:
        if getattr(obj, field, None) == value:
            continue
        try:
            setattr(obj, field, value)
            obj.save()
        except Exception:
            logger.exception('Bulk %s failed for %r', verb, obj)
            skipped += 1
            continue
        log_change(request.user, obj, [field])
        changed += 1

    message = f'{changed} record{"s" if changed != 1 else ""} {verb}.'
    if skipped:
        message += f' {skipped} could not be updated and were skipped.'
    return message


def activate_records(request, queryset):
    return _apply_field(request, queryset, 'is_active', True, 'activated')


def deactivate_records(request, queryset):
    """Deactivate rows, never including the operator's own account."""
    model = queryset.model
    if model is type(request.user) and queryset.filter(pk=request.user.pk).exists():
        queryset = queryset.exclude(pk=request.user.pk)
        suffix = ' Your own account was left untouched.'
    else:
        suffix = ''
    return _apply_field(request, queryset, 'is_active', False, 'deactivated') + suffix


def bulk_status_setter(status):
    """Build a handler that moves orders to ``status``.

    Shipping is excluded deliberately: an order cannot be marked shipped
    without a courier and AWB, and those are per-order values that belong on
    the order form rather than in a bulk action.
    """

    def handler(request, queryset):
        return _apply_field(request, queryset, 'status', status, f'marked {status}')

    handler.__name__ = f'mark_{status}'
    return handler


def delete_expired_otps(request, queryset):
    """Delete the expired codes among the selected rows, keeping the live ones.

    Narrowing the selection rather than trusting it is the whole point: a live
    code is one a customer may be about to type, and deleting it turns a
    routine clean-up into a support call. A code with no expiry recorded counts
    as expired, exactly as ``OTP.is_expired()`` treats it.
    """
    now = timezone.now()
    expired = queryset.filter(Q(expires_at__lte=now) | Q(expires_at__isnull=True))

    # Materialised before the delete so each row can be logged individually,
    # and so the count reported back is the count actually removed.
    doomed = list(expired)
    if not doomed:
        return 'Nothing was deleted: every selected code is still live.'

    for otp in doomed:
        log_deletion(request.user, otp)
    expired.delete()

    kept = queryset.count()
    message = f'{len(doomed)} expired code{"s" if len(doomed) != 1 else ""} deleted.'
    if kept:
        message += f' {kept} still-live code{"s were" if kept != 1 else " was"} left alone.'
    return message


def download_order_invoices(request, queryset):
    """Merge the selected orders' invoices into one PDF.

    Reuses ``orders.invoice_utils.generate_and_merge_invoices_pdf``, the same
    helper the existing Django admin action uses, so both admins produce
    identical documents.
    """
    from orders.invoice_utils import generate_and_merge_invoices_pdf

    queryset = queryset.order_by('created_at')
    if not queryset.exists():
        return 'Select at least one order to download invoices for.'

    try:
        merged_file, generated_count, failed_order_ids = generate_and_merge_invoices_pdf(queryset)
    except ValueError as exc:
        return str(exc)
    except Exception:
        logger.exception('Panel invoice merge failed.')
        return 'The invoices could not be prepared. The error has been logged.'

    if queryset.count() - len(failed_order_ids) <= 0:
        return 'No valid invoices could be prepared for the selected orders.'

    merged_file.seek(0)
    response = HttpResponse(merged_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{merged_file.name}"'
    return response
