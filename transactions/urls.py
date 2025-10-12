from django.urls import path
from .views import CreatePaymentIntentView, ConfirmPaymentView, RecentTransactionView
from .webhooks import StripeWebhookView

urlpatterns = [
    path('create/', CreatePaymentIntentView.as_view(), name="create_payment_intent"),
    path('confirm/', ConfirmPaymentView.as_view(), name='confirm_payment'),
    path('recent-transactions/', RecentTransactionView.as_view(), name='recent_transactions'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
]
