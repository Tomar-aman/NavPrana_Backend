from django.urls import path
# from .views import CreatePaymentIntentView, ConfirmPaymentView, RecentTransactionView
# from .webhooks import StripeWebhookView
from .cashfree_views import (
    CashfreeCreateOrderAndPaymentView,
    CashfreePaymentStatusView,
    CashfreePaymentReturnView,
    CashfreeRefundView
)
from .cashfree_webhook import CashfreeWebhookView

urlpatterns = [
    # Stripe payments
    # path('create/', CreatePaymentIntentView.as_view(), name="create_payment_intent"),
    # path('confirm/', ConfirmPaymentView.as_view(), name='confirm_payment'),
    # path('recent-transactions/', RecentTransactionView.as_view(), name='recent_transactions'),
    # path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    
    # Cashfree payments
    path('cashfree/create-order/', CashfreeCreateOrderAndPaymentView.as_view(), name='cashfree_create_order'),
    path('cashfree/status/<str:order_id>/', CashfreePaymentStatusView.as_view(), name='cashfree_payment_status'),
    path('cashfree/return/', CashfreePaymentReturnView.as_view(), name='cashfree_return'),
    path('cashfree/refund/', CashfreeRefundView.as_view(), name='cashfree_refund'),
    path('cashfree/webhook/', CashfreeWebhookView.as_view(), name='cashfree_webhook'),
]
