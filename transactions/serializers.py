from rest_framework import serializers
from orders.models import Order
from transactions.models import TransactionLog

class PaymentIntentSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    coupon_code = serializers.CharField(required=False, allow_blank=True)

class PaymentConfirmationSerializer(serializers.Serializer):
    payment_intent_id = serializers.CharField()

class TransactionLogSerializer(serializers.ModelSerializer):
    plan = serializers.SerializerMethodField()
    class Meta:
        model = TransactionLog
        fields = ['id', 'user', 'plan' ,'order', 'payment_method', 'amount', 'currency', 'status', 'transaction_id','invoice_url','updated_at']

    def get_plan(self, obj):
        plan = obj.order.plan
        return {
            'id': plan.id,
            'name': plan.name,
            'price': plan.price,
            'interval': plan.interval
        }