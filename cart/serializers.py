from rest_framework import serializers
from product.models import Product
from product.serializers import ProductImageSerializer
from .models import Cart


class CartProductSerializer(serializers.ModelSerializer):
    """
    Product fields the cart and checkout screens render.

    Nesting these means the frontend no longer has to pull the whole catalogue
    just to resolve cart rows.
    """
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'size',
            'price',
            'max_price',
            'discount_precent',
            'images',
        ]
        read_only_fields = fields


class CartSerializer(serializers.ModelSerializer):
    # 'product' stays a plain ID so POST/PATCH keep working unchanged;
    # 'product_detail' is the read-only expansion.
    product_detail = CartProductSerializer(source='product', read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'product', 'product_detail', 'quantity', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs.get('product')
        if product and Cart.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("This product is already in your cart.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return Cart.objects.create(**validated_data)
