# serializers.py

from rest_framework import serializers

from api_settings.models import PricingSettings

from .models import InstagramReel


class InstagramReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramReel
        fields = ["id", "instagram_url", "thumbnail", "caption", "sort_order", "created_at"]


class PricingSettingsSerializer(serializers.ModelSerializer):
    """
    The figures the storefront needs to quote a total that matches the one the
    backend will charge.

    Sent as numbers rather than strings so the checkout page can add them up
    without parsing; nothing here is secret, and every value is already visible
    to any shopper who reaches the payment step.
    """

    cod_handling_fee = serializers.FloatField(read_only=True)
    shipping_fee = serializers.FloatField(read_only=True)
    free_shipping_threshold = serializers.FloatField(read_only=True)
    prepaid_discount = serializers.FloatField(read_only=True)

    class Meta:
        model = PricingSettings
        fields = [
            "cod_handling_fee",
            "shipping_fee",
            "free_shipping_threshold",
            "prepaid_discount_enabled",
            "prepaid_discount",
            "updated_at",
        ]
