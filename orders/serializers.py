from rest_framework import serializers
from transactions.models import TransactionLog
from orders.models import Order, OrderItem
from product.models import Product


class ProductItemSerializer(serializers.Serializer):
    """Serializer for product items in order"""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    
    def validate_product_id(self, value):
        """Validate product exists"""
        try:
            Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        return value


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating order and initiating payment"""
    products = ProductItemSerializer(many=True)
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address_id = serializers.IntegerField(required=False)
    tax_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_products(self, value):
        """Validate products list is not empty"""
        if not value:
            raise serializers.ValidationError("At least one product is required")
        return value


class PaymentStatusSerializer(serializers.Serializer):
    """Serializer for payment status check"""
    transaction_id = serializers.CharField(max_length=255)


class TransactionLogSerializer(serializers.ModelSerializer):
    """Serializer for transaction log"""
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_number = serializers.IntegerField(source='order.id', read_only=True)
    
    class Meta:
        model = TransactionLog
        fields = [
            'id',
            'order_number',
            'merchant_transaction_id',
            'phonepe_transaction_id',
            'payment_method',
            'payment_method_display',
            'payment_instrument_type',
            'amount',
            'currency',
            'status',
            'status_display',
            'upi_id',
            'card_type',
            'card_network',
            'bank_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price', 'created_at']
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for order"""
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id',
            'user',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'total_amount',
            'discount_amount',
            'tax_amount',
            'final_amount',
            'payment_method',
            'transaction_id',
            'notes',
            'created_at',
            'updated_at',
            'items'
        ]
        read_only_fields = fields


class RefundSerializer(serializers.Serializer):
    """Serializer for refund initiation"""
    transaction_id = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
    )