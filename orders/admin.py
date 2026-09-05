import logging

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html

from .invoice_utils import generate_and_merge_invoices_pdf
from .models import Order, OrderItem


logger = logging.getLogger(__name__)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_method', 'courier', 'awb_number', 'final_amount', 'handling_fee', 'total_amount', 'created_at', 'updated_at')
    list_filter = ('status', 'courier', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'id', 'awb_number')
    # handling_fee and prepaid_discount are snapshots of what this order was
    # charged. They are shown because the totals do not add up without them,
    # and kept read-only because editing one would leave final_amount stating a
    # different sum from the rows above it.
    readonly_fields = ('created_at', 'updated_at', 'track_link', 'handling_fee', 'prepaid_discount')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    actions = ('download_all_invoices_single_pdf',)
    fieldsets = (
        (None, {'fields': ('user','address', 'status','payment_status' , 'payment_method' , 'final_amount', 'total_amount','tax_percentage','tax_amount', 'shipping_fee', 'handling_fee', 'prepaid_discount', 'discount_amount',  'coupon', 'transaction_id','invoice',)}),
        ('Shipping', {'fields': ('courier', 'awb_number', 'track_link')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    inlines = [OrderItemInline]

    @admin.display(description='Tracking link')
    def track_link(self, obj):
        if not obj.tracking_url:
            return '—'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Track on {} website</a>',
            obj.tracking_url, obj.courier_label
        )

    @admin.action(description='Download selected invoices as a single PDF')
    def download_all_invoices_single_pdf(self, request, queryset):
        queryset = queryset.order_by('created_at')

        if not queryset.exists():
            self.message_user(request, 'No selected orders found to prepare invoices.', level=messages.ERROR)
            return None
        try:
            merged_file, generated_count, failed_order_ids = generate_and_merge_invoices_pdf(queryset)
            merged_count = queryset.count() - len(failed_order_ids)
            if merged_count <= 0:
                self.message_user(
                    request,
                    'No valid invoices could be prepared for the selected orders.',
                    level=messages.ERROR,
                )
                return None

            merged_file.seek(0)
            response = HttpResponse(merged_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{merged_file.name}"'

            success_message = (
                f'Download prepared with {merged_count} invoices. '
                f'Generated {generated_count} missing invoices.'
            )
            self.message_user(request, success_message, level=messages.SUCCESS)

            if failed_order_ids:
                self.message_user(
                    request,
                    f'Could not include invoices for order IDs: {", ".join(map(str, failed_order_ids))}',
                    level=messages.WARNING,
                )

            return response
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return None
        except Exception:
            logger.exception('Failed preparing merged invoice PDF from admin action.')
            self.message_user(
                request,
                'Unexpected error while preparing single PDF invoices.',
                level=messages.ERROR,
            )
            return None

