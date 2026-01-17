from django.urls import path
from .views import MyOrdersView, OrderDetailView, DownloadInvoiceView
# from .views import (
#     CreateOrderAndPaymentView,
#     CheckPaymentStatusView,
#     PaymentCallbackView,
#     RecentTransactionView,
#     InitiateRefundView,
# )
# from .webhook import PhonePeWebhookView, TestWebhookView

urlpatterns = [
    # Order Management
    path('my-orders/', MyOrdersView.as_view(), name='my_orders'),
    path('<int:order_id>/', OrderDetailView.as_view(), name='order_detail'),
    path('<int:order_id>/invoice/', DownloadInvoiceView.as_view(), name='download_invoice'),
    # Order and Payment Creation
    # path('create-order/', CreateOrderAndPaymentView.as_view(), name='create_order_payment'),
    
    # # Payment Status Check
    # path('status/', CheckPaymentStatusView.as_view(), name='payment_status'),
    
    # # Payment Callback (redirect from PhonePe)
    # path('callback/', PaymentCallbackView.as_view(), name='payment_callback'),
    
    # # Webhook (server-to-server callback)
    # path('webhook/phonepe/', PhonePeWebhookView.as_view(), name='phonepe_webhook'),
    
    # # Test webhook (development only)
    # path('webhook/test/', TestWebhookView.as_view(), name='test_webhook'),
    
    # # Transactions
    # path('recent-transactions/', RecentTransactionView.as_view(), name='recent_transactions'),
    
    # # Refund
    # path('refund/', InitiateRefundView.as_view(), name='initiate_refund'),
    
    # # Order Details
    # path('order/<int:order_id>/', OrderDetailsView.as_view(), name='order_details'),
]