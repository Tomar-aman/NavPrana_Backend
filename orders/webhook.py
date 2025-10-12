from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

from transactions.phonepe_service import PhonePePaymentService
from transactions.models import TransactionLog

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PhonePeWebhookView(APIView):
    """
    Handle server-to-server callback from PhonePe
    
    POST /api/payments/webhook/phonepe/
    
    PhonePe sends callback in this format:
    {
        "response": "base64_encoded_response",
        "x-verify": "checksum"
    }
    """
    permission_classes = []  # No authentication for webhooks
    authentication_classes = []
    
    def post(self, request, *args, **kwargs):
        """Handle webhook callback from PhonePe"""
        try:
            # Get base64 response and checksum from request
            base64_response = request.data.get('response')
            checksum = request.headers.get('X-VERIFY') or request.data.get('x-verify')
            
            if not base64_response or not checksum:
                logger.error("Missing response or checksum in webhook")
                return Response({
                    'success': False,
                    'error': 'Invalid webhook payload'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize PhonePe service
            phonepe_service = PhonePePaymentService()
            
            # Validate and decode callback
            decoded_response = phonepe_service.validate_callback(
                base64_response, 
                checksum
            )
            
            if not decoded_response:
                logger.error("Webhook validation failed - Invalid checksum")
                return Response({
                    'success': False,
                    'error': 'Invalid checksum'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Extract payment data
            payment_data = decoded_response.get('data', {})
            merchant_transaction_id = payment_data.get('merchantTransactionId')
            payment_status = payment_data.get('state')  # SUCCESS, FAILED, PENDING
            
            logger.info(f"Webhook received for transaction: {merchant_transaction_id}, status: {payment_status}")
            
            # Get transaction log
            try:
                transaction_log = TransactionLog.objects.select_related('order').get(
                    merchant_transaction_id=merchant_transaction_id
                )
            except TransactionLog.DoesNotExist:
                logger.error(f"Transaction not found: {merchant_transaction_id}")
                return Response({
                    'success': False,
                    'error': 'Transaction not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Process based on payment status
            if payment_status == 'SUCCESS':
                # Mark transaction as successful
                transaction_log.mark_as_success(payment_data)
                logger.info(f"Transaction {merchant_transaction_id} marked as successful")
                
            elif payment_status == 'FAILED':
                # Mark transaction as failed
                error_message = payment_data.get('message', 'Payment failed')
                transaction_log.mark_as_failed(error_message)
                logger.info(f"Transaction {merchant_transaction_id} marked as failed")
                
            elif payment_status == 'PENDING':
                # Keep as pending
                logger.info(f"Transaction {merchant_transaction_id} is still pending")
            
            # Return success response to PhonePe
            return Response({
                'success': True,
                'message': 'Webhook processed successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.exception(f"Error processing webhook: {str(e)}")
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestWebhookView(APIView):
    """
    Test webhook endpoint for development
    
    POST /api/payments/webhook/test/
    Body: {
        "merchant_transaction_id": "TXN123_1234567890",
        "status": "SUCCESS"  // or "FAILED"
    }
    """
    permission_classes = []
    
    def post(self, request, *args, **kwargs):
        """Manually trigger webhook processing for testing"""
        merchant_transaction_id = request.data.get('merchant_transaction_id')
        test_status = request.data.get('status', 'SUCCESS')
        
        if not merchant_transaction_id:
            return Response({
                'error': 'merchant_transaction_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            transaction_log = TransactionLog.objects.get(
                merchant_transaction_id=merchant_transaction_id
            )
            
            if test_status == 'SUCCESS':
                # Simulate successful payment
                mock_payment_data = {
                    'transactionId': f'PHONEPE_{merchant_transaction_id}',
                    'responseCode': 'SUCCESS',
                    'state': 'SUCCESS',
                    'paymentInstrument': {
                        'type': 'UPI',
                        'utr': '123456789012'
                    }
                }
                transaction_log.mark_as_success(mock_payment_data)
                message = 'Transaction marked as successful'
                
            elif test_status == 'FAILED':
                # Simulate failed payment
                transaction_log.mark_as_failed('Test failure')
                message = 'Transaction marked as failed'
            else:
                return Response({
                    'error': 'Invalid status. Use SUCCESS or FAILED'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': message,
                'transaction_id': merchant_transaction_id
            }, status=status.HTTP_200_OK)
            
        except TransactionLog.DoesNotExist:
            return Response({
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)