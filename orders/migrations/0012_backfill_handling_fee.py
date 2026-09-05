"""
Fill in ``handling_fee`` for orders placed before the column existed.

Until now the fee was a constant that ``get_handling_fee()`` re-read on every
call, so nothing recorded what any individual order was actually charged. The
figure is not lost though — it is still inside ``final_amount``, which was
worked out as::

    final_amount = round(total_amount - discount_amount)
                   + shipping_fee
                   + handling_fee

so the fee comes back out by rearranging. That is worth doing rather than
writing today's fee onto every old row: the constant was 20.00 before it became
49.00, and orders from either era have to keep the fee their customer paid.
"""

from decimal import Decimal

from django.db import migrations

BATCH = 500


def backfill(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')

    pending = []
    # Only COD orders ever carried a handling fee; everything else is correct
    # at the column default of 0.
    queryset = Order.objects.filter(payment_method='cod').only(
        'id', 'total_amount', 'discount_amount', 'shipping_fee', 'final_amount',
    )

    for order in queryset.iterator(chunk_size=BATCH):
        after_discount = Decimal(str(round(order.total_amount - order.discount_amount)))
        charged = order.final_amount - after_discount - order.shipping_fee

        # calculate_final_amount() clamped the total at zero, so a heavily
        # discounted order can reconstruct to a negative fee. It was never
        # charged one.
        order.handling_fee = charged if charged > 0 else Decimal('0.00')
        pending.append(order)

        if len(pending) >= BATCH:
            Order.objects.bulk_update(pending, ['handling_fee'])
            pending = []

    if pending:
        Order.objects.bulk_update(pending, ['handling_fee'])


def unbackfill(apps, schema_editor):
    """Back to the column default; final_amount still holds the real figure."""
    Order = apps.get_model('orders', 'Order')
    Order.objects.update(handling_fee=Decimal('0.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_order_handling_fee_order_prepaid_discount'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
