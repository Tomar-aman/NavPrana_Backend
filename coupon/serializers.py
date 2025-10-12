from rest_framework import serializers
from .models import Coupon

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['coupon_code', 'amount', 'percent', 'free_shipping' ,'start_date', 'end_date']

class ApplyCouponSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(max_length=255)
    order_total = serializers.DecimalField(max_digits=10, decimal_places=2)