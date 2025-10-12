# from django.views import View
# from django.http import HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# import stripe
# import logging
# from notification.models import Notification
# from .models import TransactionLog
# from orders.models import Order
# from django.utils import timezone



# logger = logging.getLogger('transaction.webhooks')

# @method_decorator(csrf_exempt, name='dispatch')
# class StripeWebhookView(View):
#     def post(self, request, *args, **kwargs):
#         payload = request.body
#         sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
#         event = None

#         try:
#             stripe_settings = StripeSettings.objects.latest('created_at')
#             if not stripe_settings.webhook_secret:
#                 logger.error('Webhook secret not configured')
#                 return HttpResponse(status=500)

#             try:
#                 event = stripe.Webhook.construct_event(
#                     payload, sig_header, stripe_settings.webhook_secret
#                 )
#             except stripe.error.SignatureVerificationError as e:
#                 logger.error(f'⚠️ Webhook signature verification failed: {str(e)}')
#                 return HttpResponse(status=400)
#             except Exception as e:
#                 logger.error(f'⚠️ Webhook error: {str(e)}')
#                 return HttpResponse(status=400)

#             # Handle the event
#             handler = self.get_handler(event.type)
#             if handler:
#                 handler(event.data.object)
#             else:
#                 logger.info(f'Unhandled event type {event.type}')

#             return HttpResponse(status=200)
#         except Exception as e:
#             logger.error(f'💥 Critical webhook error: {str(e)}')
#             return HttpResponse(status=500)
        
    
#     def get_handler(self, event_type):
#         handlers = {
#             # One-time payment handlers
#             'payment_intent.succeeded': self.handle_successful_payment,
#             'payment_intent.payment_failed': self.handle_failed_payment,
#             'payment_intent.canceled': self.handle_canceled_payment,

#             # Subscription invoice handlers
#             'invoice.payment_succeeded': self.handle_invoice_payment_succeeded,
#             'invoice.payment_failed': self.handle_invoice_payment_failed,

#             # subscription lifecycle handlers
#             'customer.subscription.created': self.handle_subscription_created,
#             'customer.subscription.updated': self.handle_subscription_updated,
#             'customer.subscription.deleted': self.handle_subscription_deleted,

#         }
#         return handlers.get(event_type)
    
#     def handle_successful_payment(self, payment_intent):
#         """Handle one-time payment success"""
#         try:
#             transaction = TransactionLog.objects.get(payment_intent_id=payment_intent.id)
#             transaction.status = "success"
#             transaction.transaction_id = payment_intent.latest_charge
#             transaction.payment_details.update({
#                 'payment_method': payment_intent.payment_method,
#                 'payment_method_details': payment_intent
#             })
#             transaction.save()
            
#             order = transaction.order
#             order.status = 'completed'
#             order.payment_status = 'paid'
#             # order.save(update_fields=['status','payment_status'])
#             order.save()
            
#             # Handle coupon usage
#             coupon = order.coupon
#             if coupon:
#                 coupon.used += 1
#                 coupon.record_usage(order.user)
#                 coupon.save()
                
#             # Check for Apple Pay
#             services = StripePaymentService()
#             invoice_url = services.get_invoice(payment_intent.latest_charge)
#             transaction.invoice_url = invoice_url
#             transaction.save()
#             # payment_method = services.get_payment_method(payment_intent.payment_method)
#             # if payment_method.card.wallet.apple_pay.type == 'apple_pay':
#             #     transaction.payment_method = 'apple_pay'
#             #     transaction.save()

#             # Create or update subscription
#             subscription, created = UserSubscription.objects.get_or_create(
#                 user=order.user,
#                 defaults={
#                     'plan': order.plan,
#                     'start_date': timezone.now(),
#                     'end_date': timezone.now() + timezone.timedelta(
#                         days=365 if order.plan.interval == 'yearly' else 30
#                     ),
#                 }
#             )
            
#             if not created:
#                 subscription.plan = order.plan
#                 subscription.start_date = timezone.now()
#                 subscription.end_date = timezone.now() + timezone.timedelta(
#                     days=365 if order.plan.interval == 'yearly' else 30
#                 )
#                 subscription.save()
            
#             user = order.user
#             user.plan = order.plan
#             user.save()

#             # ✅ Reset usage after subscription creation/renewal
#             usage, _ = UserUsage.objects.get_or_create(user=user)
#             usage.reset_usage()

#             # Notify user about successful payment
#             Notification.objects.create(
#                 title='Thanks for subscribing!',
#                 message=f'Your payment was successful for {order.plan.name}. Thank you!',
#                 user=user
#             )

#             logger.info(f'Payment successful for transaction {payment_intent.id}')
#         except TransactionLog.DoesNotExist:
#             logger.error(f'Transaction not found for payment {payment_intent.id}')
#         except Exception as e:
#             logger.error(f'Error processing successful payment: {str(e)}')

#     def handle_failed_payment(self, payment_intent):
#         """Handle one-time payment failure"""
#         try:
#             transaction = TransactionLog.objects.get(payment_intent_id=payment_intent.id)
#             transaction.status = 'failed'
#             transaction.error_message = payment_intent.last_payment_error.message if payment_intent.last_payment_error else None
#             transaction.save()
#             order = transaction.order
#             order.status = 'failed'
#             order.payment_status = 'failed'
#             order.save()
#             # Notify user about failed payment
#             Notification.objects.create(
#                 title='Payment Declined',
#                 message='Your payment has been declined. Please try again.',
#                 user=order.user
#             )
#             logger.error(f'Payment failed for transaction {payment_intent.id}: {transaction.error_message}')
#         except TransactionLog.DoesNotExist:
#             logger.error(f'Transaction not found for failed payment {payment_intent.id}')
#         except Exception as e:
#             logger.error(f'Error processing failed payment: {str(e)}')

#     def handle_canceled_payment(self, payment_intent):
#         """Handle one-time payment cancellation"""
#         try:
#             transaction = TransactionLog.objects.get(payment_intent_id=payment_intent.id)
#             transaction.status = 'cancelled'
#             transaction.save()
#             order = transaction.order
#             order.status = 'cancelled'
#             order.payment_status = 'cancelled'
#             order.save()
#             # Notify user about cancelled payment
#             Notification.objects.create(
#                 title='Payment Cancelled',
#                 message='Your payment has been cancelled.',
#                 user=order.user
#             )
#             logger.info(f'Payment cancelled for transaction {payment_intent.id}')
#         except TransactionLog.DoesNotExist:
#             logger.error(f'Transaction not found for cancelled payment {payment_intent.id}')
#         except Exception as e:
#             logger.error(f'Error processing cancelled payment: {str(e)}')

#     def handle_invoice_payment_succeeded(self, invoice):
#         """Handle subscription invoice payment success"""
#         try:
#             subscription_id = invoice.parent.subscription_details.subscription
#             subscription_metadata = invoice.parent.subscription_details.metadata
#             order_id = subscription_metadata.get('order_id')

#             transaction = TransactionLog.objects.filter(subscription_id=subscription_id, status="pending").first()

#             if transaction:
#                 # If there's a pending transaction for this subscription, update it
#                 transaction.status = 'success'
#                 transaction.transaction_id = invoice.id
#                 transaction.payment_details.update({
#                     'invoice_id': invoice.id,
#                     'invoice_number': invoice.number,
#                     'billing_reason': invoice.billing_reason,
#                     'period_start': invoice.period_start,
#                     'period_end': invoice.period_end,
#                     'customer_email': invoice.customer_email,
#                     'customer_name': invoice.customer_name,
#                     'hosted_invoice_url': invoice.hosted_invoice_url,
#                     'invoice_pdf': invoice.invoice_pdf,
#                     'collection_method': invoice.collection_method,
#                     'status': invoice.status,
#                     **transaction.payment_details
#                 })
#                 transaction.invoice_url = invoice.hosted_invoice_url
#                 transaction.save()
                
#                 order = transaction.order
#                 order.status = 'completed'
#                 order.payment_status = 'paid'
#                 order.save()
            
#             else:
#                 # No pending transaction found, create a new one
#                 order = Order.objects.get(id=order_id)
#                 transaction = TransactionLog.objects.create(
#                     order=order,
#                     payment_method='stripe',
#                     user=order.user,
#                     subscription_id=subscription_id,
#                     amount=invoice.amount_paid / 100,  # Convert cents to dollars
#                     currency=invoice.currency,
#                     status='success',
#                     transaction_id=invoice.id,
#                     payment_details={
#                         'invoice_id': invoice.id,
#                         'invoice_number': invoice.number,
#                         'billing_reason': invoice.billing_reason,
#                         'period_start': invoice.period_start,
#                         'period_end': invoice.period_end,
#                         'customer_email': invoice.customer_email,
#                         'customer_name': invoice.customer_name,
#                         'hosted_invoice_url': invoice.hosted_invoice_url,
#                         'invoice_pdf': invoice.invoice_pdf,
#                         'collection_method': invoice.collection_method,
#                         'status': invoice.status,
#                     }
#                 )
#                 order.status = 'completed'
#                 order.payment_status = 'paid'
#                 order.save()


#             # Update subscription end date
#             subscription, created = UserSubscription.objects.get_or_create(
#                 user=order.user,
#                 defaults={
#                     'plan': order.plan,
#                     'start_date': timezone.now(),
#                     'end_date': timezone.now() + timezone.timedelta(
#                         days=365 if order.plan.interval == 'year' else 30
#                     ),
#                 }
#             )
            
#             if not created:
#                 subscription.plan = order.plan
#                 subscription.start_date = timezone.now()
#                 subscription.end_date = timezone.now() + timezone.timedelta(
#                     days=365 if order.plan.interval == 'year' else 30
#                 )
#                 subscription.save()
            
#             user = order.user
#             user.plan = order.plan
#             user.save()

#             # ✅ Reset usage after subscription creation/renewal
#             usage, _ = UserUsage.objects.get_or_create(user=user)
#             usage.reset_usage()

#             # Notify user about successful payment
#             Notification.objects.create(
#                 title='Thanks for subscribing!',
#                 message=f'Your payment was successful for {order.plan.name}. Thank you!',
#                 user=user
#             )

#             logger.info(f'Invoice payment succeeded for subscription {subscription_id}')
#         except Exception as e:
#             logger.error(f'Error processing invoice payment succeeded: {str(e)}')

#     def handle_invoice_payment_failed(self, invoice):
#         """Handle subscription invoice payment failure"""
#         try:
#             subscription_id = invoice.parent.subscription_details.subscription
#             transaction = TransactionLog.objects.filter(subscription_id=subscription_id).last()
            
#             if transaction:
#                 TransactionLog.objects.create(
#                     order=transaction.order,
#                     payment_method='stripe_subscription',
#                     user=transaction.user,
#                     stripe_customer_id=transaction.stripe_customer_id,
#                     subscription_id=subscription_id,
#                     amount=invoice.amount_due / 100,
#                     currency=invoice.currency,
#                     payment_frequency=transaction.payment_frequency,
#                     status='failed',
#                     error_message=f"Subscription payment failed for invoice {invoice.id}",
#                     payment_details={
#                         'invoice_id': invoice.id,
#                         'billing_reason': invoice.billing_reason,
#                         'attempt_count': invoice.attempt_count,
#                         **transaction.payment_details
#                     }
#                 )

#             logger.error(f'Subscription payment failed for subscription {subscription_id}: {transaction.error_message}')
#         except Exception as e:
#             logger.error(f'Transaction not found for failed subscription {subscription_id}: {str(e)}')

#     def handle_subscription_created(self, subscription):
#         """Handle subscription creation"""
#         try:
#             order_id = subscription.metadata.get('order_id')
#             if order_id:
#                 order = Order.objects.get(id=order_id)
#                 txn = TransactionLog.objects.filter(order=order).last()
#                 if txn:
#                     txn.subscription_id = subscription.id
#                     txn.save(update_fields=['subscription_id'])

#                 # ✅ Cancel old active subscriptions for this user (except the new one)
#                 active_subs = TransactionLog.objects.filter(
#                     user=order.user,
#                     status='success'
#                 ).exclude(subscription_id=subscription.id)

#                 for old_txn in active_subs:
#                     try:
#                         stripe.Subscription.delete(old_txn.subscription_id)
#                         old_txn.status = 'cancelled'
#                         old_txn.save(update_fields=['status'])
#                         old_order = old_txn.order
#                         old_order.status = 'cancelled'
#                         old_order.save(update_fields=['status'])

#                         logger.info(f'Cancelled old subscription {old_txn.subscription_id} for user {order.user.email}')

#                     except Exception as e:
#                         logger.error(f'Error cancelling old subscription {old_txn.subscription_id}: {str(e)}')

#             logger.info(f'Subscription created: {subscription.id}')
#         except Exception as e:
#             logger.error(f'Error processing subscription creation: {str(e)}')

#     def handle_subscription_updated(self, subscription):
#         """Handle subscription updates"""
#         try:
#             transaction = TransactionLog.objects.filter(subscription_id=subscription.id).first()
#             if transaction:
#                 transaction.payment_details.update({
#                     'subscription_status': subscription.status,
#                     'current_period_start': subscription.current_period_start,
#                     'current_period_end': subscription.current_period_end,
#                     'cancel_at_period_end': subscription.cancel_at_period_end
#                 })
#                 transaction.save()
                
#             logger.info(f'Subscription updated: {subscription.id} - Status: {subscription.status}')
#         except Exception as e:
#             logger.error(f'Error processing subscription update: {str(e)}')

#     def handle_subscription_deleted(self, subscription):
#         """Handle subscription deletion/cancellation"""
#         try:
#             transaction = TransactionLog.objects.filter(subscription_id=subscription.id).first()
#             if transaction:
#                 transaction.status = 'cancelled'
#                 transaction.save()
                
#                 # Update order status
#                 order = transaction.order
#                 order.status = 'cancelled'
#                 order.save(update_fields=['status'])
                
#             logger.info(f'Subscription deleted: {subscription.id}')
#         except Exception as e:
#             logger.error(f'Error processing subscription deletion: {str(e)}')

    