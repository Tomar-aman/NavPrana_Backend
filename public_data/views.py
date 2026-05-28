# views.py

from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from .models import InstagramReel
from .serializers import InstagramReelSerializer


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
