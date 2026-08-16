"""Dashboard view. All numbers come from :mod:`admin_panel.metrics`."""

from django.views.generic import TemplateView

from ..audit import describe
from ..columns import ORDER_STATUS_TONES, PAYMENT_STATUS_TONES
from ..metrics import (
    get_kpis,
    get_low_stock_products,
    get_new_customers_series,
    get_payment_method_split,
    get_recent_activity,
    get_recent_orders,
    get_revenue_series,
    get_status_distribution,
    get_top_products,
)
from ..mixins import PanelContextMixin
from ..registry import registry


class DashboardView(PanelContextMixin, TemplateView):
    """Operational overview: headline figures, trends and things needing action."""

    template_name = 'panel/dashboard.html'
    nav_key = 'dashboard'
    page_title = 'Dashboard'
    page_subtitle = 'Store performance at a glance'

    def _can_view(self, resource_key: str) -> bool:
        """Only surface a section the user is actually allowed to open."""
        resource = registry.get(resource_key)
        return resource is not None and resource.user_can(self.request.user, 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        show_orders = self._can_view('orders')
        show_products = self._can_view('products')
        show_users = self._can_view('users')

        revenue_series = get_revenue_series() if show_orders else []
        status_distribution = get_status_distribution() if show_orders else []
        payment_split = get_payment_method_split() if show_orders else []
        top_products = get_top_products() if show_orders and show_products else []
        customer_series = get_new_customers_series() if show_users else []

        orders_resource = registry.get('orders')
        recent_orders = []
        if show_orders:
            for order in get_recent_orders():
                recent_orders.append(
                    {
                        'obj': order,
                        'url': orders_resource.detail_url(order),
                        'status_tone': ORDER_STATUS_TONES.get(order.status, 'neutral'),
                        'payment_tone': PAYMENT_STATUS_TONES.get(order.payment_status, 'neutral'),
                    }
                )

        activity = []
        if user.has_perm('admin.view_logentry'):
            activity = [{'entry': entry, **describe(entry)} for entry in get_recent_activity()]

        products_resource = registry.get('products')
        low_stock = []
        if show_products:
            for product in get_low_stock_products():
                low_stock.append(
                    {
                        'obj': product,
                        'url': products_resource.detail_url(product),
                        'percent': (
                            round(product.available_quantity / product.max_quantity * 100)
                            if product.max_quantity else 0
                        ),
                    }
                )

        context.update(
            {
                'kpis': get_kpis(),
                'revenue_series': revenue_series,
                'status_distribution': status_distribution,
                'payment_split': payment_split,
                'top_products': top_products,
                'customer_series': customer_series,
                'recent_orders': recent_orders,
                'recent_activity': activity,
                'low_stock': low_stock,
                'orders_list_url': orders_resource.url('list') if show_orders else '',
                'products_list_url': products_resource.url('list') if show_products else '',
                # Charts read their data from a <script type="application/json">
                # block via {{ ...|json_script }}, so figures are never
                # interpolated into an executable context.
                'chart_data': {
                    'revenue': revenue_series,
                    'customers': customer_series,
                },
            }
        )
        return context
