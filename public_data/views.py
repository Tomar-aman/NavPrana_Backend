# views.py

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from api_settings.models import PricingSettings

from .models import InstagramReel
from .serializers import InstagramReelSerializer, PricingSettingsSerializer


class PricingSettingsView(RetrieveAPIView):
    """
    GET /api/v1/public/pricing/

    The COD handling fee, delivery charges and prepaid discount currently in
    force. The storefront reads this rather than keeping its own copy of the
    numbers, so the total shown at checkout is the total the order is created
    with. Public — nothing here is secret, and a shopper reaching the payment
    step sees every one of these figures anyway.
    """
    serializer_class = PricingSettingsSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return PricingSettings.load()


class InstagramReelListView(ListAPIView):
    """
    GET /api/v1/social/reels/
    Returns all active Instagram reels, ordered by sort_order then newest first.
    Public endpoint — no authentication required.
    """
    serializer_class = InstagramReelSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return InstagramReel.objects.filter(is_active=True)
