# """
# Cashfree Webhook Handler

# Handles server-to-server callbacks from Cashfree for payment notifications
# """

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# import json
# import logging

# from transactions.cashfree_service import CashfreePaymentService
# from transactions.models import TransactionLog

# logger = logging.getLogger(__name__)


# @method_decorator(csrf_exempt, name='dispatch')
# class CashfreeWebhookView(APIView):
#     """
#     Handle server-to-server callback from Cashfree
    
#     POST /api/payments/cashfree/webhook/
    
#     Cashfree sends webhook in this format:
#     Headers:
#         x-webhook-signature: <signature>
#         x-webhook-timestamp: <timestamp>
#     Body: {
#         "type": "PAYMENT_SUCCESS_WEBHOOK",
#         "data": {
#             "order": {
#                 "order_id": "ORDER_123",
#                 "order_amount": 100.00,
#                 "order_currency": "INR",
#                 "order_status": "PAID"
#             },
#             "payment": {
#                 "cf_payment_id": 123456,
#                 "payment_status": "SUCCESS",
#                 "payment_amount": 100.00,
#                 "payment_time": "2023-01-01T12:00:00+05:30",
#                 "payment_method": "UPI",
#                 "payment_group": "upi",
#                 "bank_reference": "123456789",
#                 "auth_id": "auth_123"
#             },
#             "customer_details": {...}
#         }
#     }
    
#     Webhook Types:
#     - PAYMENT_SUCCESS_WEBHOOK: Payment successful
#     - PAYMENT_FAILED_WEBHOOK: Payment failed
#     - PAYMENT_USER_DROPPED_WEBHOOK: User abandoned payment
#     - REFUND_STATUS_WEBHOOK: Refund status update
#     """
#     permission_classes = []  # No authentication for webhooks
#     authentication_classes = []
    
#     def post(self, request, *args, **kwargs):
#         """Handle webhook callback from Cashfree"""
#         try:
#             # Get signature and timestamp from headers
#             signature = request.headers.get('x-webhook-signature')
#             timestamp = request.headers.get('x-webhook-timestamp')
            
#             # Get raw body
#             webhook_body = request.body.decode('utf-8')
            
#             if not signature or not timestamp:
#                 logger.error("Missing signature or timestamp in webhook")
#                 return Response({
#                     'success': False,
#                     'error': 'Invalid webhook payload'
#                 }, status=status.HTTP_400_BAD_REQUEST)
            
#             # Initialize Cashfree service
#             cashfree_service = CashfreePaymentService()
            
#             # Verify webhook signature
#             is_valid = cashfree_service.verify_webhook_signature(
#                 webhook_body,
#                 signature,
#                 timestamp
#             )
            
#             if not is_valid:
#                 logger.error("Webhook signature verification failed")
#                 return Response({
#                     'success': False,
#                     'error': 'Invalid signature'
#                 }, status=status.HTTP_401_UNAUTHORIZED)
            
#             # Parse webhook data
#             webhook_data = json.loads(webhook_body)
#             webhook_type = webhook_data.get('type')
#             data = webhook_data.get('data', {})
            
#             logger.info(f"Webhook received - Type: {webhook_type}")
            
#             # Route to appropriate handler
#             if webhook_type == 'PAYMENT_SUCCESS_WEBHOOK':
#                 return self.handle_payment_success(data)
#             elif webhook_type == 'PAYMENT_FAILED_WEBHOOK':
#                 return self.handle_payment_failed(data)
#             elif webhook_type == 'PAYMENT_USER_DROPPED_WEBHOOK':
#                 return self.handle_payment_dropped(data)
#             elif webhook_type == 'REFUND_STATUS_WEBHOOK':
#                 return self.handle_refund_status(data)
#             else:
#                 logger.warning(f"Unhandled webhook type: {webhook_type}")
#                 return Response({
#                     'success': True,
#                     'message': 'Webhook received but not processed'
#                 }, status=status.HTTP_200_OK)
            
#         except json.JSONDecodeError as e:
#             logger.error(f"Invalid JSON in webhook: {str(e)}")
#             return Response({
#                 'success': False,
#                 'error': 'Invalid JSON'
#             }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
#             return Response({
#                 'success': False,
#                 'error': 'Internal server error'
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def handle_payment_success(self, data: dict) -> Response:
#         """
#         Handle successful payment webhook
        
#         Args:
#             data: Webhook data containing order and payment info
#         """
#         try:
#             order_data = data.get('order', {})
#             payment_data = data.get('payment', {})
            
#             order_id = order_data.get('order_id')
            
#             logger.info(f"Processing payment success for order: {order_id}")
            
#             # Get transaction log
#             try:
#                 transaction_log = TransactionLog.objects.select_related('order').get(
#                     merchant_transaction_id=order_id
#                 )
#             except TransactionLog.DoesNotExist:
#                 logger.error(f"Transaction not found: {order_id}")
#                 return Response({
#                     'success': False,
#                     'error': 'Transaction not found'
#                 }, status=status.HTTP_404_NOT_FOUND)
            
#             # Check if already processed
#             if transaction_log.status == 'success':
#                 logger.info(f"Transaction already marked as successful: {order_id}")
#                 return Response({
#                     'success': True,
#                     'message': 'Already processed'
#                 }, status=status.HTTP_200_OK)
            
#             # Prepare response data
#             cashfree_response = {
#                 'order_id': order_id,
#                 'order_status': order_data.get('order_status'),
#                 'order_amount': order_data.get('order_amount'),
#                 'payment_info': {
#                     'cf_payment_id': payment_data.get('cf_payment_id'),
#                     'payment_status': payment_data.get('payment_status'),
#                     'payment_amount': payment_data.get('payment_amount'),
#                     'payment_method': payment_data.get('payment_method'),
#                     'payment_group': payment_data.get('payment_group'),
#                     'bank_reference': payment_data.get('bank_reference'),
#                     'auth_id': payment_data.get('auth_id'),
#                     'payment_time': payment_data.get('payment_time')
#                 }
#             }
            
#             # Mark transaction as successful
#             transaction_log.mark_cashfree_success(cashfree_response)
            
#             logger.info(f"Transaction {order_id} marked as successful")
            
#             return Response({
#                 'success': True,
#                 'message': 'Payment processed successfully'
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             logger.error(f"Error processing payment success: {str(e)}", exc_info=True)
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def handle_payment_failed(self, data: dict) -> Response:
#         """
#         Handle failed payment webhook
        
#         Args:
#             data: Webhook data containing order and payment info
#         """
#         try:
#             order_data = data.get('order', {})
#             payment_data = data.get('payment', {})
            
#             order_id = order_data.get('order_id')
#             error_details = payment_data.get('error_details', {})
            
#             logger.info(f"Processing payment failure for order: {order_id}")
            
#             # Get transaction log
#             try:
#                 transaction_log = TransactionLog.objects.select_related('order').get(
#                     merchant_transaction_id=order_id
#                 )
#             except TransactionLog.DoesNotExist:
#                 logger.error(f"Transaction not found: {order_id}")
#                 return Response({
#                     'success': False,
#                     'error': 'Transaction not found'
#                 }, status=status.HTTP_404_NOT_FOUND)
            
#             # Prepare error message
#             error_message = error_details.get('error_description', 'Payment failed')
            
#             # Mark transaction as failed
#             transaction_log.mark_as_failed(error_message)
            
#             logger.info(f"Transaction {order_id} marked as failed")
            
#             return Response({
#                 'success': True,
#                 'message': 'Payment failure processed'
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             logger.error(f"Error processing payment failure: {str(e)}", exc_info=True)
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def handle_payment_dropped(self, data: dict) -> Response:
#         """
#         Handle user dropped payment webhook
#         User abandoned the payment before completion
        
#         Args:
#             data: Webhook data containing order info
#         """
#         try:
#             order_data = data.get('order', {})
#             order_id = order_data.get('order_id')
            
#             logger.info(f"Processing payment drop for order: {order_id}")
            
#             # Get transaction log
#             try:
#                 transaction_log = TransactionLog.objects.select_related('order').get(
#                     merchant_transaction_id=order_id
#                 )
#             except TransactionLog.DoesNotExist:
#                 logger.error(f"Transaction not found: {order_id}")
#                 return Response({
#                     'success': False,
#                     'error': 'Transaction not found'
#                 }, status=status.HTTP_404_NOT_FOUND)
            
#             # Mark as cancelled
#             transaction_log.status = 'cancelled'
#             transaction_log.error_message = 'Payment abandoned by user'
#             transaction_log.save()
            
#             # Update order
#             transaction_log.order.status = 'cancelled'
#             transaction_log.order.save()
            
#             logger.info(f"Transaction {order_id} marked as cancelled")
            
#             return Response({
#                 'success': True,
#                 'message': 'Payment drop processed'
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             logger.error(f"Error processing payment drop: {str(e)}", exc_info=True)
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def handle_refund_status(self, data: dict) -> Response:
#         """
#         Handle refund status update webhook
        
#         Args:
#             data: Webhook data containing refund info
#         """
#         try:
#             refund_data = data.get('refund', {})
#             order_id = refund_data.get('order_id')
#             refund_status = refund_data.get('refund_status')
            
#             logger.info(f"Processing refund status for order: {order_id}, status: {refund_status}")
            
#             # Get transaction log
#             try:
#                 transaction_log = TransactionLog.objects.get(
#                     merchant_transaction_id=order_id
#                 )
#             except TransactionLog.DoesNotExist:
#                 logger.error(f"Transaction not found: {order_id}")
#                 return Response({
#                     'success': False,
#                     'error': 'Transaction not found'
#                 }, status=status.HTTP_404_NOT_FOUND)
            
#             # Update refund status
#             if refund_status == 'SUCCESS':
#                 transaction_log.status = 'refunded'
#                 transaction_log.payment_details['refund_data'] = refund_data
#                 transaction_log.save()
                
#                 # Update order
#                 transaction_log.order.payment_status = 'refunded'
#                 transaction_log.order.save()
            
#             logger.info(f"Refund status updated for order: {order_id}")
            
#             return Response({
#                 'success': True,
#                 'message': 'Refund status processed'
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             logger.error(f"Error processing refund status: {str(e)}", exc_info=True)
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
Cashfree Webhook Handler (PG v3)

- Secure signature verification
- Dashboard test support
- Idempotent processing
- Production safe
"""

import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from transactions.cashfree_service import CashfreePaymentService
from transactions.models import TransactionLog

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class CashfreeWebhookView(APIView):
    """
    POST /api/payments/cashfree/webhook/
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Entry point for Cashfree webhooks
        """
        signature = request.headers.get("x-webhook-signature")
        timestamp = request.headers.get("x-webhook-timestamp")
        raw_body = request.body.decode("utf-8")

        # --------------------------------------------------
        # 1. Allow Cashfree Dashboard "Test Webhook"
        # --------------------------------------------------
        if not signature or not timestamp:
            logger.warning("Cashfree dashboard test webhook received")
            return Response(
                {"success": True, "message": "Test webhook accepted"},
                status=status.HTTP_200_OK
            )

        # --------------------------------------------------
        # 2. Verify webhook signature (REAL payments)
        # --------------------------------------------------
        cashfree_service = CashfreePaymentService()

        if not cashfree_service.verify_webhook_signature(
            raw_body, signature, timestamp
        ):
            logger.error("Invalid Cashfree webhook signature")
            return Response(
                {"success": False, "error": "Invalid signature"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # --------------------------------------------------
        # 3. Parse payload
        # --------------------------------------------------
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            return Response(
                {"success": False, "error": "Invalid JSON"},
                status=status.HTTP_400_BAD_REQUEST
            )

        webhook_type = payload.get("type")
        data = payload.get("data", {})
        # print(f"Webhook payload: {json.dumps(payload, indent=2)}")

        logger.info(f"Cashfree webhook received: {webhook_type}")

        # --------------------------------------------------
        # 4. Route webhook
        # --------------------------------------------------
        handler_map = {
            "PAYMENT_SUCCESS_WEBHOOK": self._handle_payment_success,
            "PAYMENT_FAILED_WEBHOOK": self._handle_payment_failed,
            "PAYMENT_USER_DROPPED_WEBHOOK": self._handle_payment_dropped,
            "REFUND_STATUS_WEBHOOK": self._handle_refund_status,
        }

        handler = handler_map.get(webhook_type)

        if not handler:
            logger.warning(f"Unhandled webhook type: {webhook_type}")
            return Response(
                {"success": True, "message": "Webhook ignored"},
                status=status.HTTP_200_OK
            )

        return handler(data)

    # ======================================================
    # HANDLERS
    # ======================================================

    def _handle_payment_success(self, data: dict) -> Response:
        order_data = data.get("order", {})
        payment_data = data.get("payment", {})

        order_id = order_data.get("order_id")

        if not order_id:
            return Response(
                {"success": False, "error": "Order ID missing"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                txn = TransactionLog.objects.select_for_update().select_related(
                    "order"
                ).get(transaction_order_id=order_id)

                # Idempotency check
                if txn.status == "success":
                    logger.info(f"Webhook duplicate ignored: {order_id}")
                    return Response(
                        {"success": True, "message": "Already processed"},
                        status=status.HTTP_200_OK
                    )

                txn.mark_cashfree_success({
                    "order": order_data,
                    "payment": payment_data
                })

                logger.info(f"Payment success processed: {order_id}")

                return Response(
                    {"success": True, "message": "Payment processed"},
                    status=status.HTTP_200_OK
                )

        except TransactionLog.DoesNotExist:
            logger.error(f"Transaction not found: {order_id}")
            return Response(
                {"success": False, "error": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def _handle_payment_failed(self, data: dict) -> Response:
        order_data = data.get("order", {})
        payment_data = data.get("payment", {})

        order_id = order_data.get("order_id")

        if not order_id:
            return Response(
                {"success": False, "error": "Order ID missing"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                txn = TransactionLog.objects.select_for_update().select_related(
                    "order"
                ).get(transaction_order_id=order_id)

                # Store payment details
                error_msg = (
                    payment_data.get("error_details", {}).get("error_description")
                    or "Payment failed"
                )
                
                # Save complete payment details
                txn.payment_details = {
                    "order": order_data,
                    "payment": payment_data,
                    "error_details": payment_data.get("error_details", {})
                }
                
                # Extract payment method details if available
                if payment_data.get("cf_payment_id"):
                    txn.gateway_payment_id = payment_data.get("cf_payment_id")
                if payment_data.get("payment_group"):
                    txn.payment_group = payment_data.get("payment_group")
                if payment_data.get("bank_reference"):
                    txn.bank_reference = payment_data.get("bank_reference")

                txn.mark_as_failed(error_msg)

                logger.info(f"Payment failed: {order_id}, Error: {error_msg}")

                return Response(
                    {"success": True, "message": "Payment failure processed"},
                    status=status.HTTP_200_OK
                )

        except TransactionLog.DoesNotExist:
            logger.error(f"Transaction not found: {order_id}")
            return Response(
                {"success": False, "error": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def _handle_payment_dropped(self, data: dict) -> Response:
        order_data = data.get("order", {})
        order_id = order_data.get("order_id")

        try:
            txn = TransactionLog.objects.select_related("order").get(
                transaction_order_id=order_id
            )

            txn.status = "cancelled"
            txn.error_message = "User abandoned payment"
            txn.save(update_fields=["status", "error_message"])

            txn.order.status = "cancelled"
            txn.order.save(update_fields=["status"])

            logger.info(f"Payment dropped: {order_id}")

            return Response({"success": True}, status=status.HTTP_200_OK)

        except TransactionLog.DoesNotExist:
            return Response(
                {"success": False, "error": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def _handle_refund_status(self, data: dict) -> Response:
        refund = data.get("refund", {})
        order_id = refund.get("order_id")
        refund_status = refund.get("refund_status")

        if refund_status != "SUCCESS":
            return Response({"success": True}, status=status.HTTP_200_OK)

        try:
            txn = TransactionLog.objects.get(
                transaction_order_id=order_id
            )

            txn.status = "refunded"
            txn.payment_details["refund"] = refund
            txn.save(update_fields=["status", "payment_details"])

            txn.order.payment_status = "refunded"
            txn.order.save(update_fields=["payment_status"])

            logger.info(f"Refund processed: {order_id}")

            return Response({"success": True}, status=status.HTTP_200_OK)

        except TransactionLog.DoesNotExist:
            return Response(
                {"success": False, "error": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND
            )

