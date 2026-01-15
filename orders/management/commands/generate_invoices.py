"""
Management command to generate/regenerate invoices for orders
"""

from django.core.management.base import BaseCommand
from orders.models import Order
from orders.invoice_utils import regenerate_invoice


class Command(BaseCommand):
    help = 'Generate or regenerate invoices for paid orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=int,
            help='Generate invoice for specific order ID',
        )
        parser.add_argument(
            '--all-paid',
            action='store_true',
            help='Generate invoices for all paid orders without invoices',
        )
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Regenerate invoices even if they exist',
        )

    def handle(self, *args, **options):
        order_id = options.get('order_id')
        all_paid = options.get('all_paid')
        regenerate = options.get('regenerate')

        if order_id:
            # Generate for specific order
            try:
                order = Order.objects.get(id=order_id)
                if order.payment_status != 'paid':
                    self.stdout.write(
                        self.style.WARNING(f'Order {order_id} is not paid yet')
                    )
                    return

                if order.invoice and not regenerate:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Order {order_id} already has an invoice. Use --regenerate to overwrite.'
                        )
                    )
                    return

                success = regenerate_invoice(order)
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'Invoice generated for order {order_id}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to generate invoice for order {order_id}')
                    )

            except Order.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Order {order_id} not found')
                )

        elif all_paid:
            # Generate for all paid orders
            if regenerate:
                orders = Order.objects.filter(payment_status='paid')
                msg = 'Regenerating invoices for all paid orders'
            else:
                orders = Order.objects.filter(payment_status='paid', invoice='')
                msg = 'Generating invoices for paid orders without invoices'

            self.stdout.write(msg)
            
            total = orders.count()
            success_count = 0
            fail_count = 0

            for order in orders:
                if regenerate_invoice(order):
                    success_count += 1
                    self.stdout.write(f'✓ Order {order.id}')
                else:
                    fail_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'✗ Order {order.id}')
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\nCompleted: {success_count} successful, {fail_count} failed out of {total} orders'
                )
            )

        else:
            self.stdout.write(
                self.style.ERROR('Please specify --order-id or --all-paid')
            )
