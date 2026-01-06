from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.utils import timezone
# from orders.models import DeliveryChargesAndTax
from .models import Coupon, CouponUsage
from .serializers import ApplyCouponSerializer
from django.utils.translation import gettext_lazy as _

class ApplyCouponView(GenericAPIView):
    serializer_class = ApplyCouponSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        coupon_code = serializer.validated_data['coupon_code'].upper().strip()
        order_total = serializer.validated_data['order_total']

        try:
            coupon = Coupon.objects.get(
                coupon_code=coupon_code,
                status=True,
                start_date__lte=timezone.now().date()
            )

            # Validate coupon
            if coupon.end_date and coupon.end_date < timezone.now().date():
                return Response(
                    {'error': _('This coupon has expired')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if coupon.used >= coupon.max_use:
                return Response(
                    {'error': _('This coupon has reached its usage limit')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if coupon.minimum_cart_amount > order_total:
                return Response(
                    {'error': _('Your order amount is low for this coupon')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = request.user
            usage = CouponUsage.objects.filter(user=user, coupon=coupon).first()

            if usage and usage.used_count >= coupon.uses_per_user:
                return Response(
                    {'error': _('You have reached the usage limit for this coupon')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Calculate discount
            if coupon.percent > 0:
                discount = (order_total * coupon.percent) / 100

            elif coupon.free_shipping:
                # delivery_charges = DeliveryChargesAndTax.objects.first()
                delivery_charges = None
                if delivery_charges:
                    discount = delivery_charges.delivery_charges
                else:
                    discount = 0
            else:
                discount = coupon.amount

            if discount > order_total:
                return Response(
                    {'error': _('Discount amount cannot be greater than the order total')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'coupon_id': coupon.coupon_id,
                'coupon_code': coupon.coupon_code,
                'discount_amount': discount,
                # 'is_free_shipping':coupon.free_shipping,
                'message': _('Coupon applied successfully')
            }, status=status.HTTP_200_OK)

        except Coupon.DoesNotExist:
            return Response(
                {'error': _('Invalid coupon code')},
                status=status.HTTP_404_NOT_FOUND
            )
