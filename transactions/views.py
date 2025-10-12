from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import GenericAPIView, CreateAPIView

from transactions.models import TransactionLog
from .serializers import PaymentConfirmationSerializer, PaymentIntentSerializer, TransactionLogSerializer
from plan.models import SubscriptionPlan
from transactions.stripe import StripePaymentService
from orders.models import Order
from coupon.models import Coupon
from decimal import Decimal
from django.utils import timezone

class CreatePaymentIntentView(GenericAPIView):
    serializer_class = PaymentIntentSerializer
    
    def calculate_discounted_amount(self, price: Decimal, coupon: Coupon) -> Decimal:
        """Calculate final amount after applying coupon"""
        if coupon.percent > 0:
            discount = (price * coupon.percent) / Decimal('100')
        else:
            discount = coupon.amount
        
        final_amount = price - discount
        return max(final_amount, Decimal('0'))
    
    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Get plan
            plan = SubscriptionPlan.objects.get(id=serializer.validated_data['plan_id'])
            final_amount = Decimal(plan.price)
            applied_coupon = None

            # Handle coupon if provided
            coupon_code = serializer.validated_data.get('coupon_code')
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(coupon_code=coupon_code)
                    final_amount = self.calculate_discounted_amount(plan.price, coupon)
                    applied_coupon = coupon
                    
                except Coupon.DoesNotExist:
                    raise ValueError("Invalid coupon code")
            
            # Initialize Stripe service
            stripe_service = StripePaymentService()
            
            # Get or create Stripe customer
            customer_id = stripe_service.get_or_create_customer(user)

            # Create order with proper Decimal handling
            order = Order.objects.create(
                user=user,
                plan=plan,
                total_amount=final_amount, 
                payment_method='stripe',
                status='pending'
            )
            if applied_coupon:
                order.coupon = applied_coupon
                order.save()

            # Create payment intent
            subscription_data = stripe_service.create_subscription(
                customer=customer_id,
                order=order,
                amount=final_amount,
                frequency=plan.interval,
                metadata={
                    'order_id': str(order.id),
                    'plan_id': str(plan.id),
                    'user_id': str(user.id),
                    'coupon_code': coupon_code if applied_coupon else ''
                },
                coupon=applied_coupon
            )

            return Response({
                **subscription_data,
                'order_summary': {
                    'subscription_id': subscription_data.get('subscription_id'),
                    'subscription_status': subscription_data.get('status'),
                    'plan_name': plan.name,
                    'plan_interval': plan.interval,
                    'original_amount': float(plan.price),
                    'discount_amount': float(plan.price - final_amount),
                    'final_amount': float(final_amount),
                    'coupon_applied': bool(applied_coupon)
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        

class ConfirmPaymentView(CreateAPIView):
    serializer_class = PaymentConfirmationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            payment_service = StripePaymentService()
            payment_intent = payment_service.confirm_payment(
                serializer.validated_data['payment_intent_id']
            )
            
            return Response({
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RecentTransactionView(GenericAPIView):
    serializer_class = TransactionLogSerializer

    def get_queryset(self):
        user = self.request.user
        return TransactionLog.objects.filter(user=user, status='success').order_by('-updated_at')

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)