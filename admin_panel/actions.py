"""
Bulk actions.

Each handler takes ``(request, queryset)`` and returns either a message to show
the operator or an :class:`~django.http.HttpResponse` to send instead of a
redirect (used by the invoice download).

Handlers save row by row rather than calling ``queryset.update()`` on purpose:
several models in this project put real logic in ``save()`` — ``Order``
recalculates its totals, ``Product`` recomputes its selling price — and a bulk
UPDATE would skip all of it. Selections are bounded by the page size, so the
extra queries are a fair trade for correct data and a complete audit trail.
"""

import logging

from django.http import HttpResponse

from .audit import log_change


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
