from rest_framework import serializers
from transactions.models import TransactionLog
from orders.models import Order, OrderItem
from product.models import Product
from users.models import UserAddress


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


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for product details in order items"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'size',
            'category_name',
            'details',
            'price',
            'max_price',
            'discount_precent',
            'image'
        ]
        read_only_fields = fields
    
    def get_image(self, obj):
        """Get feature image or first image"""
        # Try to get feature image first
        feature_image = obj.images.filter(is_feature=True).first()
        if feature_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(feature_image.image.url)
            return feature_image.image.url
        
        # Otherwise get first image
        first_image = obj.images.first()
        if first_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first_image.image.url)
            return first_image.image.url
        
        return None


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating order and initiating payment"""
    PAYMENT_METHOD_CHOICES = ('cashfree', 'cod')

    products = ProductItemSerializer(many=True)
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address_id = serializers.IntegerField(required=False)
    payment_method = serializers.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        default='cashfree'
    )
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
    product = ProductDetailSerializer(read_only=True)
    item_total = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'item_total', 'created_at']
        read_only_fields = fields
    
    def get_item_total(self, obj):
        """Calculate total for this item"""
        return float(obj.quantity * obj.price)


class UserAddressSerializer(serializers.ModelSerializer):
    """Serializer for user address"""
    
    class Meta:
        model = UserAddress
        fields = [
            'id',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'postal_code',
            'country',
            'is_default'
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for order list (minimal data)"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    items_count = serializers.SerializerMethodField()
    first_product_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'payment_method',
            'payment_method_display',
            'total_amount',
            'discount_amount',
            'tax_amount',
            'final_amount',
            'items_count',
            'first_product_image',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_items_count(self, obj):
        """Get total number of items in order"""
        return obj.items.count()
    
    def get_first_product_image(self, obj):
        """Get image of first product in order"""
        first_item = obj.items.first()
        if first_item and first_item.product:
            product = first_item.product
            # Try feature image first
            feature_image = product.images.filter(is_feature=True).first()
            if feature_image:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(feature_image.image.url)
                return feature_image.image.url
            
            # Otherwise first image
            first_image = product.images.first()
            if first_image:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(first_image.image.url)
                return first_image.image.url
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed order view"""
    items = OrderItemSerializer(many=True, read_only=True)
    address = UserAddressSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    coupon_code = serializers.CharField(source='coupon.coupon_code', read_only=True, allow_null=True)
    invoice_url = serializers.SerializerMethodField()
    latest_transaction = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'payment_method',
            'payment_method_display',
            'address',
            'total_amount',
            'discount_amount',
            'coupon_code',
            'tax_percentage',
            'tax_amount',
            'final_amount',
            'transaction_id',
            'invoice_url',
            'notes',
            'created_at',
            'updated_at',
            'items',
            'latest_transaction'
        ]
        read_only_fields = fields
    
    def get_invoice_url(self, obj):
        """Get invoice download URL if available"""
        if obj.payment_status == 'paid' and obj.invoice:
            url = obj.invoice.url # Ensure URL is accessible
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
        return None
    
    def get_latest_transaction(self, obj):
        """Get latest transaction information"""
        transaction = obj.transaction_logs.order_by('-created_at').first()
        if transaction:
            return {
                'id': transaction.id,
                'transaction_order_id': transaction.transaction_order_id,
                'gateway_payment_id': transaction.gateway_payment_id,
                'bank_reference': transaction.bank_reference,
                'payment_method': transaction.get_payment_method_display(),
                'payment_instrument_type': transaction.payment_instrument_type,
                'status': transaction.status,
                'amount': float(transaction.amount),
                # 'created_at': transaction.created_at,
                'updated_at': transaction.updated_at
            }
        return None


class RefundSerializer(serializers.Serializer):
    """Serializer for refund initiation"""
    transaction_id = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
    )