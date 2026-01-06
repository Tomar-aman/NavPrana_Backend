from rest_framework import serializers
from .models import Cart

class CartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ['id', 'product', 'quantity', 'created_at', 'updated_at']
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