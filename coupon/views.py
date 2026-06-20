from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
import random
import string
from django.utils.translation import gettext_lazy as _
# from orders.models import DeliveryChargesAndTax
from .models import Coupon, CouponUsage, TempCoupon, UserSpinLimit
from .serializers import ApplyCouponSerializer

class ApplyCouponView(GenericAPIView):
    serializer_class = ApplyCouponSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        coupon_code = serializer.validated_data['coupon_code'].upper().strip()
        order_total = serializer.validated_data['order_total']
        user = request.user

        # 1. Try permanent Coupon first
        try:
            coupon = Coupon.objects.get(
                coupon_code=coupon_code,
                status=True,
                start_date__lte=timezone.now().date()
            )

            # Validate coupon expiry
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
                discount = delivery_charges.delivery_charges if delivery_charges else 0
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
                'is_temp': False,
                'message': _('Coupon applied successfully')
            }, status=status.HTTP_200_OK)

        except Coupon.DoesNotExist:
            # 2. Try TempCoupon second
            try:
                temp_coupon = TempCoupon.objects.get(
                    coupon_code=coupon_code,
                    start_date__lte=timezone.now().date()
                )

                # Validate temp coupon
                if temp_coupon.user != user:
                    return Response(
                        {'error': _('This coupon is not valid for your account')},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if temp_coupon.is_used:
                    return Response(
                        {'error': _('This coupon has already been used')},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if temp_coupon.end_date and temp_coupon.end_date < timezone.now().date():
                    return Response(
                        {'error': _('This coupon has expired')},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Special check for free 500ml product
                if temp_coupon.coupon_code.startswith("NAV-FREE500-"):
                    from cart.models import Cart
                    cart_items = Cart.objects.filter(user=user, product__size='500ml')
                    if not cart_items.exists():
                        return Response(
                            {'error': _('This coupon is only valid when a 500ml product is in your cart')},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    # Set discount to the price of the 500ml product
                    discount = cart_items.first().product.price
                else:
                    # General temp coupon discount calculation
                    if temp_coupon.percent > 0:
                        discount = (order_total * temp_coupon.percent) / 100
                    elif temp_coupon.free_shipping:
                        discount = 0  # Free shipping discount is handled separately or as 0 here
                    else:
                        discount = temp_coupon.amount

                if discount > order_total:
                    discount = order_total

                return Response({
                    'coupon_id': f"TEMP_{temp_coupon.id}",
                    'coupon_code': temp_coupon.coupon_code,
                    'discount_amount': discount,
                    'is_temp': True,
                    'message': _('Coupon applied successfully')
                }, status=status.HTTP_200_OK)

            except TempCoupon.DoesNotExist:
                return Response(
                    {'error': _('Invalid coupon code')},
                    status=status.HTTP_404_NOT_FOUND
                )


class SpinWheelCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        limit, created = UserSpinLimit.objects.get_or_create(user=user)

        if limit.last_spin_date == today and not limit.allowed_by_admin:
            return Response({
                "can_spin": False,
                "message": _("You have already used your spin for today. Check back tomorrow!"),
                "last_spin_date": limit.last_spin_date
            }, status=status.HTTP_200_OK)
        
        return Response({
            "can_spin": True,
            "message": _("You are eligible to spin the wheel!")
        }, status=status.HTTP_200_OK)


class SpinWheelSpinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        today = timezone.now().date()

        # Check if user can spin
        limit, created = UserSpinLimit.objects.get_or_create(user=user)
        if limit.last_spin_date == today and not limit.allowed_by_admin:
            return Response(
                {"error": _("You have already spun the wheel today. Please check back tomorrow!")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Weighted wheel choices
        prizes = [
            {"id": "free_500ml", "name": "Free Product 500ml", "weight": 10},
            {"id": "discount_10", "name": "10% OFF", "weight": 25},
            {"id": "discount_100", "name": "₹100 OFF", "weight": 15},
            {"id": "free_shipping", "name": "Free Shipping", "weight": 25},
            {"id": "discount_50", "name": "₹50 OFF", "weight": 20},
            {"id": "try_again", "name": "Try Again", "weight": 5},
        ]
        
        choices = []
        for p in prizes:
            choices.extend([p] * p["weight"])
        
        won_prize = random.choice(choices)

        coupon_code = None
        if won_prize["id"] != "try_again":
            rand_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            
            if won_prize["id"] == "free_500ml":
                prefix = "NAV-FREE500"
                discount_type = "amount"
                amount = 1119.00  # Default Ghee 500ml price
                percent = 0.00
                free_shipping = False
            elif won_prize["id"] == "discount_10":
                prefix = "NAV-10OFF"
                discount_type = "percent"
                amount = 0.00
                percent = 10.00
                free_shipping = False
            elif won_prize["id"] == "discount_100":
                prefix = "NAV-100OFF"
                discount_type = "amount"
                amount = 100.00
                percent = 0.00
                free_shipping = False
            elif won_prize["id"] == "free_shipping":
                prefix = "NAV-FREESHIP"
                discount_type = "shipping"
                amount = 0.00
                percent = 0.00
                free_shipping = True
            else: # discount_50
                prefix = "NAV-50OFF"
                discount_type = "amount"
                amount = 50.00
                percent = 0.00
                free_shipping = False

            coupon_code = f"{prefix}-{rand_str}"
            
            # Create TempCoupon
            TempCoupon.objects.create(
                coupon_code=coupon_code,
                user=user,
                discount_type=discount_type,
                amount=amount,
                percent=percent,
                free_shipping=free_shipping,
                start_date=today,
                end_date=today + timedelta(days=7),
                is_used=False
            )

        # Update spin limits
        limit.last_spin_date = today
        limit.allowed_by_admin = False
        limit.save()

        return Response({
            "prize_id": won_prize["id"],
            "prize_name": won_prize["name"],
            "coupon_code": coupon_code,
            "message": _("Congratulations! You won {}").format(won_prize["name"]) if coupon_code else _("Better luck next time!")
        }, status=status.HTTP_200_OK)


class MyCouponsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        temp_coupons = TempCoupon.objects.filter(user=user).order_by('-created_at')
        
        data = []
        for tc in temp_coupons:
            is_expired = False
            if tc.end_date and tc.end_date < timezone.now().date():
                is_expired = True
                
            data.append({
                "id": tc.id,
                "coupon_code": tc.coupon_code,
                "discount_type": tc.discount_type,
                "amount": tc.amount,
                "percent": tc.percent,
                "free_shipping": tc.free_shipping,
                "is_used": tc.is_used,
                "is_expired": is_expired,
                "start_date": tc.start_date,
                "end_date": tc.end_date,
                "created_at": tc.created_at,
            })
            
        return Response(data, status=status.HTTP_200_OK)


class AdminUserSpinListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        is_simulation = request.query_params.get('simulate', 'false').lower() == 'true'
        if not request.user.is_staff and not is_simulation:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
            
        spin_limits = UserSpinLimit.objects.all().select_related('user').order_by('-last_spin_date')
        
        data = []
        for sl in spin_limits:
            data.append({
                "user_id": sl.user.id,
                "email": sl.user.email,
                "first_name": sl.user.first_name,
                "last_name": sl.user.last_name,
                "last_spin_date": sl.last_spin_date,
                "allowed_by_admin": sl.allowed_by_admin,
            })
        return Response(data, status=status.HTTP_200_OK)


class AdminResetSpinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        is_simulation = request.query_params.get('simulate', 'false').lower() == 'true'
        if not request.user.is_staff and not is_simulation:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
            
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            limit = UserSpinLimit.objects.get(user__email=email)
            limit.allowed_by_admin = True
            limit.save()
            return Response({
                "message": f"Successfully unlocked spin limits for {email}. They can spin again today!"
            }, status=status.HTTP_200_OK)
        except UserSpinLimit.DoesNotExist:
            # Check if user exists first to initialize their spin limit
            from users.models import User
            try:
                user = User.objects.get(email=email)
                limit = UserSpinLimit.objects.create(user=user, allowed_by_admin=True)
                return Response({
                    "message": f"Successfully initialized and unlocked spin limits for {email}."
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
