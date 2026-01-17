from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Prefetch
from config.pagination import CustomPageNumberPagination
from .models import Order, OrderItem
from .serializers import OrderListSerializer, OrderDetailSerializer


class MyOrdersView(GenericAPIView):
    """
    Get user's orders with pagination and search
    
    GET /api/orders/my-orders/
    Query params:
        - search: Search by order ID, product name, or transaction ID
        - status: Filter by order status (pending, processing, completed, cancelled)
        - payment_status: Filter by payment status (pending, paid, failed, refunded)
        - page: Page number (default: 1)
        - page_size: Items per page (default: 10)
    """
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    
    def get_queryset(self):
        """Get orders for current user with search and filtering"""
        user = self.request.user
        
        # Optimize queries with select_related and prefetch_related
        queryset = Order.objects.filter(user=user).select_related(
            'address', 'coupon'
        ).prefetch_related(
            Prefetch(
                'items', 
                queryset=OrderItem.objects.select_related(
                    'product__category'
                ).prefetch_related('product__images')
            )
        ).order_by('-created_at')
        
        # Search functionality
        search_query = self.request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(id__icontains=search_query) |
                Q(items__product__name__icontains=search_query) |
                Q(status__icontains=search_query) |
                Q(transaction_id__icontains=search_query)
            ).distinct()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by payment status
        payment_status_filter = self.request.query_params.get('payment_status', None)
        if payment_status_filter:
            queryset = queryset.filter(payment_status=payment_status_filter)
        
        return queryset
    
    def get(self, request, *args, **kwargs):
        """Get paginated and filtered list of user's orders"""
        try:
            queryset = self.get_queryset()
            
            # Apply pagination
            paginated_queryset = self.paginate_queryset(queryset)
            if paginated_queryset is not None:
                serializer = self.get_serializer(
                    paginated_queryset, 
                    many=True,
                    context={'request': request}
                )
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(
                queryset, 
                many=True,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_200_OK) 
        
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderDetailView(GenericAPIView):
    """
    Get detailed information for a specific order
    
    GET /api/orders/<order_id>/
    """
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id, *args, **kwargs):
        """Get detailed order information"""
        try:
            # Get order with optimized queries
            order = Order.objects.select_related(
                'address', 'coupon', 'user'
            ).prefetch_related(
                Prefetch(
                    'items', 
                    queryset=OrderItem.objects.select_related(
                        'product__category'
                    ).prefetch_related('product__images')
                ),
                'transaction_logs'
            ).get(id=order_id, user=request.user)
            
            serializer = self.get_serializer(order, context={'request': request})
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# from rest_framework.permissions import IsAuthenticated
# from django.db import transaction as db_transaction
# from decimal import Decimal

# from transactions.models import TransactionLog
# from .serializers import (
#     CreateOrderSerializer,
#     PaymentStatusSerializer,
#     TransactionLogSerializer
# )
# from orders.models import Order
# from transactions.phonepe_service import PhonePePaymentService


# class CreateOrderAndPaymentView(GenericAPIView):
#     """
#     Create order and initiate PhonePe payment
    
#     POST /api/payments/create-order/
#     Body: {
#         "products": [
#             {"product_id": 1, "quantity": 2},
#             {"product_id": 3, "quantity": 1}
#         ],
#         "coupon_code": "SAVE20",  // optional
#         "tax_percentage": 18.0,    // optional
#         "notes": "Gift wrap required"  // optional
#     }
#     """
#     serializer_class = CreateOrderSerializer
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request, *args, **kwargs):
#         user = request.user
#         serializer = self.serializer_class(data=request.data)
        
#         if not serializer.is_valid():
#             return Response(
#                 serializer.errors, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             with db_transaction.atomic():
#                 # Create order with items
#                 order = Order.create_order(
#                     user=user,
#                     products_data=serializer.validated_data['products'],
#                     coupon_code=serializer.validated_data.get('coupon_code'),
#                     tax_percentage=serializer.validated_data.get('tax_percentage'),
#                     notes=serializer.validated_data.get('notes')
#                 )
                
#                 # Initialize PhonePe service
#                 phonepe_service = PhonePePaymentService()
                
#                 # Create payment
#                 payment_response = phonepe_service.create_payment(
#                     order=order,
#                     amount=order.final_amount,
#                     user=user
#                 )
                
#                 if not payment_response.get('success'):
#                     raise ValueError(payment_response.get('error', 'Payment initiation failed'))
                
#                 # Create transaction log
#                 transaction_log = TransactionLog.create_transaction(
#                     order=order,
#                     transaction_id=payment_response['transaction_id'],
#                     amount=order.final_amount
#                 )
                
#                 # Update order with transaction ID
#                 order.transaction_id = payment_response['transaction_id']
#                 order.save()
                
#                 return Response({
#                     'success': True,
#                     'order_id': order.id,
#                     'transaction_id': payment_response['transaction_id'],
#                     'payment_url': payment_response['payment_url'],
#                     'order_summary': {
#                         'order_number': order.id,
#                         'total_amount': float(order.total_amount),
#                         'discount_amount': float(order.discount_amount),
#                         'tax_amount': float(order.tax_amount),
#                         'final_amount': float(order.final_amount),
#                         'currency': 'INR',
#                         'items_count': order.items.count()
#                     }
#                 }, status=status.HTTP_201_CREATED)
                
#         except ValueError as e:
#             return Response({
#                 'success': False,
#                 'error': str(e)
#             }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response({
#                 'success': False,
#                 'error': f'An error occurred: {str(e)}'
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class CheckPaymentStatusView(GenericAPIView):
#     """
#     Check payment status from PhonePe
    
#     GET /api/payments/status/?transaction_id=TXN123_1234567890
#     """
#     serializer_class = PaymentStatusSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request, *args, **kwargs):
#         transaction_id = request.query_params.get('transaction_id')
        
#         if not transaction_id:
#             return Response({
#                 'error': 'transaction_id is required'
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Get transaction log
#             transaction_log = TransactionLog.objects.get(
#                 merchant_transaction_id=transaction_id,
#                 user=request.user
#             )
            
#             # Check status from PhonePe
#             phonepe_service = PhonePePaymentService()
#             payment_status = phonepe_service.check_payment_status(transaction_id)
            
#             if payment_status.get('success'):
#                 phonepe_status = payment_status.get('status')
                
#                 # Update transaction based on status
#                 if phonepe_status == 'SUCCESS':
#                     transaction_log.mark_as_success(payment_status)
#                 elif phonepe_status == 'FAILED':
#                     transaction_log.mark_as_failed(
#                         error_message=payment_status.get('message')
#                     )
                
#                 return Response({
#                     'success': True,
#                     'status': phonepe_status.lower(),
#                     'order_id': transaction_log.order.id,
#                     'transaction_id': transaction_id,
#                     'amount': float(payment_status.get('amount', 0)),
#                     'payment_instrument': payment_status.get('payment_instrument', {}),
#                     'message': payment_status.get('message')
#                 }, status=status.HTTP_200_OK)
#             else:
#                 return Response({
#                     'success': False,
#                     'error': payment_status.get('error', 'Status check failed')
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#         except TransactionLog.DoesNotExist:
#             return Response({
#                 'error': 'Transaction not found'
#             }, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class PaymentCallbackView(GenericAPIView):
#     """
#     Handle redirect callback from PhonePe after payment
    
#     POST /api/payments/callback/
#     """
#     permission_classes = []  # No authentication required for callback
    
#     def post(self, request, *args, **kwargs):
#         """Handle POST redirect from PhonePe"""
#         try:
#             order_id = request.query_params.get('order_id')
            
#             if not order_id:
#                 return Response({
#                     'error': 'Order ID not found'
#                 }, status=status.HTTP_400_BAD_REQUEST)
            
#             order = Order.objects.get(id=order_id)
#             transaction_id = order.transaction_id
            
#             # Check payment status
#             phonepe_service = PhonePePaymentService()
#             payment_status = phonepe_service.check_payment_status(transaction_id)
            
#             if payment_status.get('success'):
#                 # Get transaction log
#                 transaction_log = TransactionLog.objects.get(
#                     merchant_transaction_id=transaction_id
#                 )
                
#                 phonepe_status = payment_status.get('status')
                
#                 if phonepe_status == 'SUCCESS':
#                     transaction_log.mark_as_success(payment_status)
#                     message = 'Payment successful'
#                     payment_success = True
#                 elif phonepe_status == 'FAILED':
#                     transaction_log.mark_as_failed(
#                         error_message=payment_status.get('message')
#                     )
#                     message = 'Payment failed'
#                     payment_success = False
#                 else:
#                     message = 'Payment pending'
#                     payment_success = False
                
#                 return Response({
#                     'success': payment_success,
#                     'message': message,
#                     'order_id': order_id,
#                     'status': phonepe_status.lower()
#                 }, status=status.HTTP_200_OK)
#             else:
#                 return Response({
#                     'success': False,
#                     'error': payment_status.get('error', 'Status check failed')
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#         except Order.DoesNotExist:
#             return Response({
#                 'error': 'Order not found'
#             }, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DownloadInvoiceView(GenericAPIView):
    """
    Download invoice PDF for an order
    
    GET /api/orders/<order_id>/invoice/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id, *args, **kwargs):
        """Download invoice PDF"""
        try:
            # Get order for current user
            order = Order.objects.get(id=order_id, user=request.user)
            
            # Check if order is paid
            if order.payment_status != 'paid':
                return Response({
                    'success': False,
                    'error': 'Invoice is only available for paid orders'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate invoice if not exists
            if not order.invoice:
                try:
                    from .invoice_utils import generate_invoice_pdf
                    pdf_file = generate_invoice_pdf(order)
                    order.invoice.save(pdf_file.name, pdf_file, save=True)
                except Exception as e:
                    return Response({
                        'success': False,
                        'error': f'Failed to generate invoice: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Return file response
            from django.http import FileResponse
            
            try:
                response = FileResponse(
                    order.invoice.open('rb'),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'
                return response
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Failed to download invoice: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)


# class RecentTransactionView(GenericAPIView):
#     """
#     Get user's recent successful transactions
    
#     GET /api/payments/recent-transactions/
#     """
#     serializer_class = TransactionLogSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         user = self.request.user
#         return TransactionLog.objects.filter(
#             user=user, 
#             status='success'
#         ).select_related('order').order_by('-updated_at')[:10]
    
#     def get(self, request, *args, **kwargs):
#         queryset = self.get_queryset()
#         serializer = self.get_serializer(queryset, many=True)
#         return Response({
#             'success': True,
#             'transactions': serializer.data
#         }, status=status.HTTP_200_OK)


# class InitiateRefundView(GenericAPIView):
#     """
#     Initiate refund for a transaction
    
#     POST /api/payments/refund/
#     Body: {
#         "transaction_id": "TXN123_1234567890",
#         "amount": 500.00  // optional, full refund if not provided
#     }
#     """
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request, *args, **kwargs):
#         transaction_id = request.data.get('transaction_id')
#         refund_amount = request.data.get('amount')
        
#         if not transaction_id:
#             return Response({
#                 'error': 'transaction_id is required'
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Get transaction log
#             transaction_log = TransactionLog.objects.get(
#                 merchant_transaction_id=transaction_id,
#                 user=request.user,
#                 status='success'
#             )
            
#             # Use transaction amount if refund amount not provided
#             if not refund_amount:
#                 refund_amount = transaction_log.amount
#             else:
#                 refund_amount = Decimal(str(refund_amount))
                
#                 # Validate refund amount
#                 if refund_amount > transaction_log.amount:
#                     return Response({
#                         'error': 'Refund amount cannot exceed transaction amount'
#                     }, status=status.HTTP_400_BAD_REQUEST)
            
#             # Initiate refund
#             phonepe_service = PhonePePaymentService()
#             refund_response = phonepe_service.initiate_refund(
#                 transaction_id=transaction_id,
#                 amount=refund_amount
#             )
            
#             if refund_response.get('success'):
#                 transaction_log.mark_as_refunded(
#                     refund_response['refund_transaction_id']
#                 )
                
#                 return Response({
#                     'success': True,
#                     'message': 'Refund initiated successfully',
#                     'refund_transaction_id': refund_response['refund_transaction_id'],
#                     'amount': float(refund_amount)
#                 }, status=status.HTTP_200_OK)
#             else:
#                 return Response({
#                     'success': False,
#                     'error': refund_response.get('error', 'Refund initiation failed')
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#         except TransactionLog.DoesNotExist:
#             return Response({
#                 'error': 'Transaction not found or not eligible for refund'
#             }, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class OrderDetailsView(GenericAPIView):
#     """
#     Get order details with items and transaction info
    
#     GET /api/payments/order/<order_id>/
#     """
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request, order_id, *args, **kwargs):
#         try:
#             order = Order.objects.prefetch_related(
#                 'items__product',
#                 'transaction_logs'
#             ).get(id=order_id, user=request.user)
            
#             # Prepare order items
#             items = [{
#                 'product_id': item.product.id,
#                 'product_name': item.product.name,
#                 'quantity': item.quantity,
#                 'price': float(item.price),
#                 'total': float(item.price * item.quantity)
#             } for item in order.items.all()]
            
#             # Get latest transaction
#             latest_transaction = order.transaction_logs.order_by('-created_at').first()
            
#             transaction_info = None
#             if latest_transaction:
#                 transaction_info = {
#                     'transaction_id': latest_transaction.merchant_transaction_id,
#                     'status': latest_transaction.status,
#                     'payment_method': latest_transaction.get_payment_method_display(),
#                     'amount': float(latest_transaction.amount),
#                     'created_at': latest_transaction.created_at.isoformat()
#                 }
            
#             return Response({
#                 'success': True,
#                 'order': {
#                     'id': order.id,
#                     'status': order.status,
#                     'payment_status': order.payment_status,
#                     'total_amount': float(order.total_amount),
#                     'discount_amount': float(order.discount_amount),
#                     'tax_amount': float(order.tax_amount),
#                     'final_amount': float(order.final_amount),
#                     'notes': order.notes,
#                     'created_at': order.created_at.isoformat(),
#                     'items': items,
#                     'transaction': transaction_info
#                 }
#             }, status=status.HTTP_200_OK)
            
#         except Order.DoesNotExist:
#             return Response({
#                 'error': 'Order not found'
#             }, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({
#                 'error': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)