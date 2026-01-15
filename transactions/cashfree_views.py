"""
Cashfree Payment Views

Handles:
1. Create Order & Payment Session
2. Payment Verification
3. Payment Status Check
4. Return URL handling
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction as db_transaction
from django.shortcuts import redirect
from decimal import Decimal
import logging

from .cashfree_service import CashfreePaymentService
from transactions.models import TransactionLog
from orders.models import Order
from orders.serializers import CreateOrderSerializer

logger = logging.getLogger(__name__)


class CashfreeCreateOrderAndPaymentView(APIView):
    """
    Create order and initiate Cashfree payment
    
    POST /api/payments/cashfree/create-order/
    Body: {
        "products": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 3, "quantity": 1}
        ],
        "coupon_code": "SAVE20",  // optional
        "tax_percentage": 18.0,    // optional
        "notes": "Gift wrap required",  // optional
        "return_url": "https://yourapp.com/payment-success",  // optional
        "notify_url": "https://yourbackend.com/api/payments/cashfree/webhook/"  // optional
    }
    
    Response: {
        "success": true,
        "order_id": "ORD_123",
        "transaction_id": "TXN_123",
        "payment_session_id": "session_xxx",
        "payment_url": "https://cashfree.com/...",
        "order_summary": {...}
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Validate user contact details
        if not user.phone_number or not user.email:
            return Response({
                'success': False,
                'error': 'Please update your phone number and email before proceeding'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CreateOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Create order with items
                # print(serializer.validated_data)
                order = Order.create_order(
                    user=user,
                    address= serializer.validated_data.get('address_id'),
                    products_data=serializer.validated_data['products'],
                    coupon_code=serializer.validated_data.get('coupon_code').upper().strip() if serializer.validated_data.get('coupon_code') else None,
                    tax_percentage=serializer.validated_data.get('tax_percentage'),
                    notes=serializer.validated_data.get('notes')
                )
                
                # Initialize Cashfree service
                cashfree_service = CashfreePaymentService()
                
                # Prepare customer details
                customer_details = {
                    'customer_id': str(user.id),
                    'customer_phone': str(user.phone_number),
                    'customer_email': user.email,
                    'customer_name': user.get_full_name() or user.first_name
                }
                
                # Prepare order metadata
                order_meta = {
                    'return_url': request.data.get('return_url', 
                        f'{request.scheme}://{request.get_host()}/payment-success'),
                    'notify_url': request.data.get('notify_url',
                        f'{request.scheme}://{request.get_host()}/api/payments/cashfree/webhook/'),
                    'payment_methods': 'cc,dc,nb,upi,app'  # Example: credit card, debit card, net banking, UPI, wallet
                }
                
                # Create Cashfree order
                payment_response = cashfree_service.create_order(
                    order_id=f"NAV_ORDER_{order.id}_{order.created_at.timestamp()}",
                    amount=order.final_amount,
                    customer_details=customer_details,
                    order_meta=order_meta,
                    order_note=serializer.validated_data.get('notes', '')
                )
                
                if not payment_response.get('success'):
                    raise ValueError(payment_response.get('error', 'Payment initiation failed'))
                
                # Create transaction log
                transaction_log = TransactionLog.create_cashfree_transaction(
                    order=order,
                    order_id=payment_response['order_id'],
                    amount=order.final_amount,
                    cashfree_order_id=payment_response.get('cf_order_id'),
                    payment_session_id=payment_response['payment_session_id'],
                    order_token=payment_response.get('order_token')
                )
                
                # Update order with transaction ID
                order.transaction_id = payment_response['order_id']
                order.payment_method = 'cashfree'
                order.save()
                
                # Get payment URL
                # payment_url = cashfree_service.get_payment_url(
                #     payment_response['payment_session_id']
                # )
                
                return Response({
                    'success': True,
                    'order_id': order.id,
                    'transaction_id': payment_response['order_id'],
                    'payment_session_id': payment_response['payment_session_id'],
                    # 'payment_url': payment_url,
                    # 'order_token': payment_response.get('order_token'),  # For SDK integration
                    'order_summary': {
                        'order_number': order.id,
                        'total_amount': float(order.total_amount),
                        'discount_amount': float(order.discount_amount),
                        'tax_amount': float(order.tax_amount),
                        'final_amount': float(order.final_amount),
                        'currency': 'INR',
                        'items_count': order.items.count()
                    }
                }, status=status.HTTP_201_CREATED)
                
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Cashfree order creation error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An error occurred while creating the order'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CashfreePaymentStatusView(APIView):
    """
    Check payment status from Cashfree
    
    GET /api/payments/cashfree/status/<order_id>/
    
    Response: {
        "success": true,
        "order_id": "ORDER_123",
        "payment_status": true,
        "order_status": "PAID",
        "payment_method": "UPI",
        ...
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id, *args, **kwargs):
        try:
            # Get transaction log
            transaction_log = TransactionLog.objects.select_related('order').get(
                merchant_transaction_id=order_id,
                user=request.user
            )
            
            # Initialize Cashfree service
            cashfree_service = CashfreePaymentService()
            
            # Verify payment from Cashfree
            verification_result = cashfree_service.verify_payment(order_id)

            if not verification_result.get('success'):
                return Response({
                    'success': False,
                    'error': 'Payment verification failed'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'order_id': order_id,
                'payment_status': verification_result.get('payment_status'),
                'order_status': verification_result.get('order_status'),
                'payment_method': verification_result.get('payment_method'),
                'payment_time': verification_result.get('payment_time'),
                'bank_reference':verification_result.get('bank_reference'),
                'amount': float(transaction_log.amount),
                'transaction_status': transaction_log.status
            }, status=status.HTTP_200_OK)
            
        except TransactionLog.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment status check error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An error occurred while checking payment status'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CashfreePaymentReturnView(APIView):
    """
    Handle return URL after payment
    User is redirected here after completing payment
    
    GET /api/payments/cashfree/return/?order_id=ORDER_123
    """
    permission_classes = []  # Public endpoint
    authentication_classes = []
    
    def get(self, request, *args, **kwargs):
        order_id = request.GET.get('order_id')
        
        if not order_id:
            return Response({
                'success': False,
                'error': 'Order ID not provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get transaction
            transaction_log = TransactionLog.objects.select_related('order').get(
                merchant_transaction_id=order_id
            )
            
            # Initialize Cashfree service
            cashfree_service = CashfreePaymentService()
            
            # Verify payment
            verification_result = cashfree_service.verify_payment(order_id)
            
            if verification_result.get('success'):
                payment_status = verification_result.get('payment_status')
                order_status = verification_result.get('order_status')
                
                # Redirect to success/failure page based on status
                if payment_status:
                    redirect_url = f"/payment-success?order_id={order_id}&status=success"
                else:
                    redirect_url = f"/payment-failed?order_id={order_id}&status=failed"
                
                return redirect(redirect_url)
            else:
                return redirect(f"/payment-failed?order_id={order_id}&status=error")
                
        except TransactionLog.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Return URL handler error: {str(e)}", exc_info=True)
            return redirect(f"/payment-failed?order_id={order_id}&status=error")


class CashfreeRefundView(APIView):
    """
    Initiate refund for a payment
    
    POST /api/payments/cashfree/refund/
    Body: {
        "order_id": "ORDER_123",
        "refund_amount": 100.00,  // optional, defaults to full amount
        "refund_note": "Customer requested refund"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        user = request.user
        order_id = request.data.get('order_id')
        refund_note = request.data.get('refund_note', '')
        
        if not order_id:
            return Response({
                'success': False,
                'error': 'Order ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get transaction
            transaction_log = TransactionLog.objects.select_related('order').get(
                merchant_transaction_id=order_id,
                user=user,
                status='success'
            )
            
            # Check if already refunded
            if transaction_log.status == 'refunded':
                return Response({
                    'success': False,
                    'error': 'Payment already refunded'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get refund amount
            refund_amount = request.data.get('refund_amount')
            if refund_amount:
                refund_amount = Decimal(str(refund_amount))
            else:
                refund_amount = transaction_log.amount
            
            # Validate refund amount
            if refund_amount > transaction_log.amount:
                return Response({
                    'success': False,
                    'error': 'Refund amount cannot exceed payment amount'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Initialize Cashfree service
            cashfree_service = CashfreePaymentService()
            
            # Generate refund ID
            refund_id = f"REFUND_{transaction_log.order.id}_{int(transaction_log.created_at.timestamp())}"
            
            # Initiate refund
            refund_result = cashfree_service.refund_payment(
                order_id=order_id,
                refund_amount=refund_amount,
                refund_id=refund_id,
                refund_note=refund_note
            )
            
            if not refund_result.get('success'):
                return Response({
                    'success': False,
                    'error': refund_result.get('error', 'Refund initiation failed')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark transaction as refunded
            transaction_log.mark_as_refunded(refund_result.get('cf_refund_id'))
            
            return Response({
                'success': True,
                'refund_id': refund_result.get('refund_id'),
                'cf_refund_id': refund_result.get('cf_refund_id'),
                'refund_status': refund_result.get('refund_status'),
                'refund_amount': float(refund_amount)
            }, status=status.HTTP_200_OK)
            
        except TransactionLog.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Transaction not found or not eligible for refund'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Refund initiation error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An error occurred while processing refund'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
